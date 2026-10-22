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
9. Social media activity (Facebook posts, group updates, Snapchat story/streak, likes, shares, friend requests): category: "promo", urgency: 0.05.
"""


VALID_CATEGORIES = {"health", "money", "person", "deadline", "work", "promo"}


def rule_based_fallback_classifier(notif: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-accuracy deterministic fallback classifier used when Ollama model
    is initializing, offline, or for fast unit testing.
    """
    text = f"{notif.get('title', '')} {notif.get('body', '')}".lower()

    # 1. Promotional / Marketing / Social Feed
    if any(k in text for k in ["personal loan of", "pre-approved", "discount", "offer", "sale", "flat 50%", "subscribe", "newsletter", "save up to", "cashback", "posted in a group", "shared a post", "sent a snap", "view story", "friend request"]):
        return {
            "urgency": 0.05,
            "category": "promo",
            "deadline_at": None,
            "reason": "Promotional or non-urgent social media feed activity",
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

    # Deterministic Safety Boundary & Clamping
    text_lower = f"{notif.get('title', '')} {notif.get('body', '')}".lower()

    # 1. Promotional & noise clamp: Marketing/sales/social updates are NEVER emergencies
    promo_indicators = [
        "discount", "offer", "sale", "flat 50%", "flat 40%", "coupon", "code feast",
        "pre-approved", "personal loan", "cashback", "save up to", "newsletter",
        "biryani", "food sales", "buy 1 get 1", "limited period offer",
        "posted a photo", "posted in a group", "shared a post", "sent a snap",
        "view story", "friend request", "streak with", "new followers", "appeared in searches",
        "order delivered", "swiggy", "zomato", "nykaa", "40% off"
    ]
    if any(k in text_lower for k in promo_indicators):
        judgment_data["category"] = "promo"
        judgment_data["urgency"] = min(judgment_data["urgency"], 0.10)
        judgment_data["reason"] = "Promotional or social feed noise (silenced by guardrail)"

    # 2. Family / Personal SOS emergency recognition
    person_sos_pattern = r"\b(broke down|accident|engine smoking|stranded|battery at \d%|pick me up|urgent phone|recharge / assistance|emergency landing)\b"
    if re.search(person_sos_pattern, text_lower):
        judgment_data["category"] = "person"
        judgment_data["urgency"] = max(judgment_data["urgency"], 0.88)
        judgment_data["reason"] = "Family or personal roadside/travel emergency"

    # 3. Work P0 production outage / Security incident recognition
    p0_pattern = r"\b(p0|prod outage|primary unresponsive|traffic failing|root credentials leaked|security incident|pagerduty)\b"
    if re.search(p0_pattern, text_lower):
        judgment_data["category"] = "work"
        judgment_data["urgency"] = max(judgment_data["urgency"], 0.90)
        judgment_data["deadline_at"] = notif.get("received_at")
        judgment_data["reason"] = "Critical P0 production outage or security escalation"

    # 4. Critical financial fraud / banking alert
    fraud_pattern = r"\b(unauthorized|suspicious debit|debit of|overdraft alert|freeze will apply|fraud prevention)\b"
    if re.search(fraud_pattern, text_lower):
        judgment_data["category"] = "money"
        judgment_data["urgency"] = max(judgment_data["urgency"], 0.90)
        judgment_data["reason"] = "Critical financial or bank fraud alert"

    # 5. Life safety / fire / evacuation
    life_safety_pattern = r"\b(fire|evacuate|flash flood|higher ground|weather alert|4-alarm fire|tsunami)\b"
    if re.search(life_safety_pattern, text_lower):
        judgment_data["category"] = "health"
        judgment_data["urgency"] = max(judgment_data["urgency"], 0.95)
        judgment_data["reason"] = "Life safety fire or environmental alert"

    # 6. Medical emergency validation: Prevent false health emergency classifications
    medical_pattern = r"\b(hospital|er|emergency|doctor|clinic|patient|collapse|prescription|allergy|accident|ambulance|cardiac|stroke|bleeding|injury|fire|flood|evacuate|safety|weather alert)\b"
    if judgment_data["category"] == "health" and not re.search(medical_pattern, text_lower):
        judgment_data["category"] = "work"
        judgment_data["urgency"] = min(judgment_data["urgency"], 0.30)
        judgment_data["reason"] = "De-escalated non-emergency notification"

    # 7. Routine financial alerts (non-fraud)
    if judgment_data["category"] == "money" and judgment_data["urgency"] > 0.50 and not re.search(fraud_pattern, text_lower):
        judgment_data["urgency"] = min(judgment_data["urgency"], 0.35)

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
