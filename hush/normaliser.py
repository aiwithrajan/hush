import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from hush.config import COCOA_EPOCH_OFFSET_SECONDS


def map_source(app_id: str, custom_rules: Optional[Dict[str, str]] = None) -> str:
    """Maps bundle identifier to normalized source category."""
    if custom_rules and app_id in custom_rules:
        return custom_rules[app_id]

    app_lower = (app_id or "").lower()
    if any(k in app_lower for k in ["whatsapp", "net.whatsapp"]):
        return "wa"
    elif any(k in app_lower for k in ["telegram", "org.telegram"]):
        return "telegram"
    elif any(k in app_lower for k in ["slack", "tinyspeck"]):
        return "slack"
    elif any(k in app_lower for k in ["discord"]):
        return "discord"
    elif any(k in app_lower for k in ["teams", "skype"]):
        return "teams"
    elif any(k in app_lower for k in ["signal", "whispersystems"]):
        return "signal"
    elif any(k in app_lower for k in ["calendar", "ical", "reminders"]):
        return "calendar"
    elif any(k in app_lower for k in ["mail", "outlook", "thunderbird", "gmail"]):
        return "mail"
    elif any(k in app_lower for k in ["mobilesms", "messages", "sms", "imessage"]):
        return "sms"
    return "other"


def cocoa_to_iso(cocoa_seconds: Optional[float]) -> str:
    """Converts Cocoa CoreData/UserNoted timestamp to ISO 8601 string."""
    if cocoa_seconds is None or cocoa_seconds < -1e9:
        return datetime.now(timezone.utc).isoformat()
    unix_ts = cocoa_seconds + COCOA_EPOCH_OFFSET_SECONDS
    # Use timezone-aware local or UTC datetime
    dt = datetime.fromtimestamp(unix_ts).astimezone()
    return dt.isoformat()


def compute_notification_id(app_id: str, title: str, body: str, received_at: str) -> str:
    """Computes deterministic sha256 hash across app, title, body, and timestamp."""
    content = f"{app_id}|{title}|{body}|{received_at}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_record(
    app_id: str,
    title: Optional[str],
    body: Optional[str],
    received_cocoa_ts: Optional[float],
    is_synthetic: bool = False,
    drill_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalizes raw input fields into standard Hush record."""
    norm_title = (title or "").strip()
    norm_body = (body or "").strip()
    norm_app = (app_id or "unknown").strip()
    source = map_source(norm_app)
    received_at_iso = cocoa_to_iso(received_cocoa_ts)
    notif_id = compute_notification_id(norm_app, norm_title, norm_body, received_at_iso)

    return {
        "id": notif_id,
        "source": source,
        "app_id": norm_app,
        "title": norm_title,
        "body": norm_body,
        "received_at": received_at_iso,
        "is_synthetic": 1 if is_synthetic else 0,
        "drill_id": drill_id,
    }


def to_classifier_projection(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces the privacy and ground-truth boundary:
    Omits 'is_synthetic' and 'drill_id' before passing to language model.
    """
    return {
        "id": record["id"],
        "source": record["source"],
        "app_id": record["app_id"],
        "title": record["title"],
        "body": record["body"],
        "received_at": record["received_at"],
    }
