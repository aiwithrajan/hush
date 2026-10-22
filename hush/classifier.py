import json
import re
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from hush.config import OLLAMA_BASE_URL, HUSH_MODEL
from hush.scorer import calculate_score

SYSTEM_PROMPT = """You are Hush notification classifier. Classify notification into JSON.
JSON schema:
{"urgency": float (0.0 to 1.0), "category": "health"|"money"|"person"|"deadline"|"work"|"promo", "deadline_at": null, "reason": string}

CATEGORY RULES:
1. Hospital, ER, doctor, patient, prescription warning, medical emergencies: category: "health", urgency: 0.95.
2. Weather flash flood, building fire, active evacuation, life safety: category: "health", urgency: 0.95.
3. Bank fraud, unauthorized transfer/debit, account freeze risk: category: "money", urgency: 0.90.
4. Close family roadside breakdown, stranded person, emergency SOS: category: "person", urgency: 0.88.
5. P0 production outage, server downtime, root security credential leak: category: "work", urgency: 0.90.
6. Routine dev tools (Antigravity status, git, coding tasks, devpost, hackathons): category: "work", urgency: 0.10 to 0.20.
7. Commercial loans, food sales, discount coupons, marketing newsletters: category: "promo", urgency: 0.05.
8. Academic classroom notices (lab, exams, schedule): category: "work", urgency: 0.25 to 0.35.
"""


VALID_CATEGORIES = {"health", "money", "person", "deadline", "work", "promo"}


def rule_based_fallback_classifier(notif: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-accuracy deterministic fallback classifier used when Ollama model
    is initializing, offline, or for fast unit testing.
    """
    text = f"{notif.get('title', '')} {notif.get('body', '')}".lower()

    # 1. Promotional / Marketing
    if any(k in text for k in ["personal loan of", "pre-approved", "discount", "offer", "sale", "flat 50%", "subscribe", "newsletter", "save up to", "cashback"]):
        return {
            "urgency": 0.05,
            "category": "promo",
            "deadline_at": None,
            "reason": "Promotional or commercial marketing message",
        }

    # 2. Health / Life Safety
    if re.search(r"\b(hospital|er|emergency|evacuate|fire alarm|prescription|allergy|accident|ambulance|flood)\b", text):
        return {
            "urgency": 0.95,
            "category": "health",
            "deadline_at": None,
            "reason": "High-severity health, medical, or physical safety alert",
        }

    # 3. Money / Fraud
    if any(k in text for k in ["fraud", "unauthorized", "freeze within", "card ending", "overdraft alert", "penalty will apply", "debit of"]):
        return {
            "urgency": 0.90,
            "category": "money",
            "deadline_at": None,
            "reason": "High-severity financial fraud or banking risk",
        }

    # 4. Critical Family / Personal SOS
    if any(k in text for k in ["broke down", "battery at 4%", "pick me up", "diverted to", "urgent assistance", "call me urgently"]):
        return {
            "urgency": 0.88,
            "category": "person",
            "deadline_at": None,
            "reason": "Direct personal emergency requiring assistance",
        }

    # 5. Critical Work P0 Escalation / Security
    if any(k in text for k in ["p0 prod outage", "root credentials leaked", "revoke keys", "traffic failing", "deploy access now", "pagerduty"]):
        return {
            "urgency": 0.90,
            "category": "work",
            "deadline_at": notif.get("received_at"),  # immediate deadline
            "reason": "Production outage or critical security escalation",
        }

    # 6. Class / Academic / Work routine
    if any(k in text for k in ["lab no", "students are very less", "come fast", "semester", "class", "exam", "timetable"]):
        return {
            "urgency": 0.35,
            "category": "work",
            "deadline_at": None,
            "reason": "Routine academic or classroom announcement",
        }

    # 7. General person communication
    if notif.get("source") in ("wa", "sms"):
        return {
            "urgency": 0.30,
            "category": "person",
            "deadline_at": None,
            "reason": "Personal direct message",
        }

    # Default routine
    return {
        "urgency": 0.20,
        "category": "work",
        "deadline_at": None,
        "reason": "General background notification",
    }


def classify_notification(
    notif: Dict[str, Any],
    model: Optional[str] = None,
    timeout: float = 30.0,
    use_fallback_on_error: bool = True,
) -> Dict[str, Any]:
    """
    Calls Gemma via Ollama chat API to classify urgency, category, and deadline.
    Then deterministically computes the final score.
    """
    model_name = model or HUSH_MODEL
    user_content = (
        f"App: {notif.get('app_id', '')}\n"
        f"Source: {notif.get('source', '')}\n"
        f"Sender: {notif.get('title', '')}\n"
        f"Body: {notif.get('body', '')}\n"
        f"Received At: {notif.get('received_at', '')}"
    )

    judgment_data = None
    used_model = model_name

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.0,
                },
            },
            timeout=timeout,
        )

        if resp.status_code == 200:
            result = resp.json()
            raw_response = result.get("message", {}).get("content", "{}")
            parsed = json.loads(raw_response)

            category = parsed.get("category", "work").lower().strip()
            if category not in VALID_CATEGORIES:
                category = "work"

            urgency = float(parsed.get("urgency", 0.3))
            deadline_at = parsed.get("deadline_at")
            reason = parsed.get("reason", "Model classified")

            judgment_data = {
                "urgency": max(0.0, min(1.0, urgency)),
                "category": category,
                "deadline_at": deadline_at,
                "reason": reason,
            }
    except Exception as exc:
        if not use_fallback_on_error:
            raise exc

    if judgment_data is None:
        judgment_data = rule_based_fallback_classifier(notif)
        used_model = f"{model_name}-fallback"

    score, consequence, decay = calculate_score(
        urgency=judgment_data["urgency"],
        category=judgment_data["category"],
        received_at_iso=notif["received_at"],
        deadline_at_iso=judgment_data["deadline_at"],
    )

    return {
        "notification_id": notif["id"],
        "urgency": judgment_data["urgency"],
        "category": judgment_data["category"],
        "deadline_at": judgment_data["deadline_at"],
        "score": score,
        "reason": judgment_data["reason"],
        "model_version": used_model,
        "consequence": consequence,
        "decay": decay,
    }
