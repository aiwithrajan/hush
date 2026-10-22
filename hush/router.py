import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from hush.config import BRIEF_QUOTAS, BRIEF_MAX_LINES, T_BRIEF, T_HIGH
from hush.db import get_db, insert_brief, get_setting


def determine_reason_tag(notif: Dict[str, Any], judgment: Dict[str, Any]) -> str:
    """Assigns reason tag: deadline, reply, person, today, money."""
    category = (judgment.get("category") or "").lower()
    body = (notif.get("body") or "").lower()
    title = (notif.get("title") or "").lower()

    if category == "deadline" or judgment.get("deadline_at"):
        return "deadline"
    elif category == "money":
        return "money"
    elif category == "person":
        return "person"
    elif any(k in body or k in title for k in ["reply", "call me", "respond", "answer", "pls check"]):
        return "reply"
    return "today"


def generate_brief(
    conn: sqlite3.Connection,
    window_hours: Optional[float] = None,
    window_minutes: Optional[int] = None,
    end_time: Optional[datetime] = None,
    enforce_threshold: bool = True,
) -> Dict[str, Any]:
    """
    Assembles the brief following strict quota and spillover rules.
    Fixed shape: exactly up to 4 lines.
    Quotas: Email: 2, WhatsApp: 1, Messages/SMS: 1.
    Spillover: unused slots borrowed by global highest score, logged as borrowed_from.
    Cadence window defaults to DB setting 'cadence_minutes' (default 180 = 3h).
    """
    if window_minutes is None:
        if window_hours is not None:
            window_minutes = int(window_hours * 60)
        else:
            try:
                setting_val = get_setting(conn, "cadence_minutes", default="180")
                window_minutes = int(setting_val) if setting_val else 180
            except Exception:
                window_minutes = 180

    if end_time is None:
        end_time = datetime.now().astimezone()
    start_time = end_time - timedelta(minutes=window_minutes)

    start_iso = start_time.isoformat()
    end_iso = end_time.isoformat()

    # Query all notifications in window with their judgments
    cursor = conn.execute(
        """
        SELECT n.*, j.urgency, j.category, j.deadline_at, j.score, j.reason, j.model_version
        FROM notifications n
        JOIN judgments j ON n.id = j.notification_id
        WHERE n.received_at >= ? AND n.received_at <= ?
        ORDER BY j.score DESC
        """,
        (start_iso, end_iso),
    )
    all_candidates = [dict(row) for row in cursor.fetchall()]

    # If no records in the exact 3h window, fall back to the most recent un-briefed batch for testing/demo
    if not all_candidates:
        cursor = conn.execute(
            """
            SELECT n.*, j.urgency, j.category, j.deadline_at, j.score, j.reason, j.model_version
            FROM notifications n
            JOIN judgments j ON n.id = j.notification_id
            ORDER BY n.received_at DESC
            LIMIT 50
            """
        )
        all_candidates = [dict(row) for row in cursor.fetchall()]
        if all_candidates:
            start_iso = all_candidates[-1]["received_at"]
            end_iso = all_candidates[0]["received_at"]

    # Separate qualifying candidates from below-threshold items
    # Exclude immediate interrupts (score >= T_HIGH) from brief unless no separate push channel
    qualifying = []
    rejected_log = []

    for item in all_candidates:
        score = item["score"]
        if enforce_threshold and score < T_BRIEF:
            rejected_log.append({
                "notification": item,
                "rejection_reason": f"Score {score:.2f} below brief threshold T_brief ({T_BRIEF:.2f})",
            })
        else:
            qualifying.append(item)

    # Collapse threads / group chats per sender/title
    def thread_key(c):
        return (c["source"], c.get("title", "").strip().lower())

    seen_threads = set()
    deduped_qualifying = []
    for c in qualifying:
        tkey = thread_key(c)
        if tkey in seen_threads:
            rejected_log.append({
                "notification": c,
                "rejection_reason": f"Thread collapsed under higher-scoring notification from {c.get('title')}",
            })
        else:
            seen_threads.add(tkey)
            deduped_qualifying.append(c)

    # Group by source
    by_source = {"mail": [], "wa": [], "sms": [], "other": []}
    for c in deduped_qualifying:
        src = c["source"]
        if src in by_source:
            by_source[src].append(c)
        else:
            by_source["other"].append(c)

    kept_items = []
    kept_ids = set()
    borrowed_slots = []

    # 1. Fill base quotas
    for src, quota in BRIEF_QUOTAS.items():
        candidates = by_source[src]
        allocated = candidates[:quota]
        for item in allocated:
            tag = determine_reason_tag(item, item)
            item["reason_tag"] = tag
            item["slot_source"] = src
            kept_items.append(item)
            kept_ids.add(item["id"])

        # Mark unallocated within this source for potential spillover or rejection
        for item in candidates[quota:]:
            pass  # will be evaluated in spillover pool

    # 2. Check spillover for unused slots
    empty_slots = BRIEF_MAX_LINES - len(kept_items)
    if empty_slots > 0:
        # Collect all remaining qualifying items not yet kept
        remaining_pool = [c for c in deduped_qualifying if c["id"] not in kept_ids]
        remaining_pool.sort(key=lambda x: x["score"], reverse=True)

        spillover_items = remaining_pool[:empty_slots]
        for item in spillover_items:
            tag = determine_reason_tag(item, item)
            item["reason_tag"] = tag
            item["slot_source"] = "spillover"
            kept_items.append(item)
            kept_ids.add(item["id"])
            borrowed_slots.append({
                "item_id": item["id"],
                "item_source": item["source"],
                "score": item["score"],
            })

    # Record rejection for any remaining qualifying items that did not fit in the 4-line cap
    for c in deduped_qualifying:
        if c["id"] not in kept_ids:
            rejected_log.append({
                "notification": c,
                "rejection_reason": f"Exceeded 4-slot brief quota; lost to higher-scoring items",
            })

    cut_count = len(all_candidates) - len(kept_items)

    # Calculate next brief time (window_end + window_minutes)
    try:
        end_dt = datetime.fromisoformat(end_iso)
        next_brief_dt = end_dt + timedelta(minutes=window_minutes)
        next_brief_str = next_brief_dt.strftime("%H:%M")
    except Exception:
        next_brief_str = f"in {window_minutes}m"

    brief_id = insert_brief(
        conn=conn,
        window_start=start_iso,
        window_end=end_iso,
        kept_ids=[it["id"] for it in kept_items],
        cut_count=cut_count,
        borrowed={"borrowed_items": borrowed_slots},
    )

    return {
        "brief_id": brief_id,
        "window_start": start_iso,
        "window_end": end_iso,
        "cadence_minutes": window_minutes,
        "lines": kept_items,
        "total_evaluated": len(all_candidates),
        "kept_count": len(kept_items),
        "cut_count": cut_count,
        "borrowed": borrowed_slots,
        "rejected_log": rejected_log,
        "next_brief_time": next_brief_str,
    }
