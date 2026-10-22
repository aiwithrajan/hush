from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from temporalio import activity
from temporalio.common import RetryPolicy

from hush.db import (
    get_db,
    insert_notification,
    insert_judgment,
    get_unclassified_notifications,
    insert_interrupt,
    acknowledge_interrupt,
    escalate_interrupt,
)
from hush.collector import collect_macos_notifications
from hush.email_collector import poll_imap_emails
from hush.classifier import classify_notification
from hush.normaliser import to_classifier_projection
from hush.router import generate_brief
from hush.interrupt import deliver_macos_notification
from hush.config import T_HIGH


# Retry Policy for Local Model inference:
# Absorbs local CPU spikes, Ollama queue contention, or brief timeouts.
LOCAL_MODEL_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=["ValueError", "KeyError"],
)


@dataclass
class IngestOutput:
    scanned: int
    inserted: int
    duplicates: int
    errors: int


@dataclass
class ClassificationItem:
    notification_id: str
    urgency: float
    category: str
    score: float
    reason: str
    is_interrupt: bool
    title: str
    body: str


@dataclass
class BriefSummary:
    brief_id: int
    window_start: str
    window_end: str
    kept_count: int
    cut_count: int
    next_brief_time: str


@activity.defn
async def activity_ingest_notifications() -> IngestOutput:
    """Safely ingests raw notifications from macOS database and optional IMAP email."""
    with get_db() as conn:
        stats = collect_macos_notifications(dest_conn=conn)
        email_stats = poll_imap_emails(dest_conn=conn)
        conn.commit()
    return IngestOutput(
        scanned=stats["scanned"] + email_stats["scanned"],
        inserted=stats["inserted"] + email_stats["inserted"],
        duplicates=stats["duplicates"] + email_stats["duplicates"],
        errors=stats["errors"] + email_stats["errors"],
    )


@activity.defn
async def activity_classify_pending(limit: int = 20) -> List[ClassificationItem]:
    """Classifies unjudged notifications using local Gemma with automatic activity retry."""
    classified = []
    with get_db() as conn:
        unclassified = get_unclassified_notifications(conn, limit=limit)
        for row in unclassified:
            notif = dict(row)
            proj = to_classifier_projection(notif)
            judgment = classify_notification(proj)
            insert_judgment(conn, judgment)

            score = judgment["score"]
            is_interrupt = score >= T_HIGH

            classified.append(
                ClassificationItem(
                    notification_id=notif["id"],
                    urgency=judgment["urgency"],
                    category=judgment["category"],
                    score=score,
                    reason=judgment["reason"],
                    is_interrupt=is_interrupt,
                    title=notif.get("title", ""),
                    body=notif.get("body", ""),
                )
            )
        conn.commit()
    return classified


@activity.defn
async def activity_generate_brief(window_hours: int = 3) -> BriefSummary:
    """Assembles the 4-line brief card with quotas and spillover."""
    with get_db() as conn:
        data = generate_brief(conn, window_hours=window_hours)
        conn.commit()
    return BriefSummary(
        brief_id=data["brief_id"],
        window_start=data["window_start"],
        window_end=data["window_end"],
        kept_count=data["kept_count"],
        cut_count=data["cut_count"],
        next_brief_time=data["next_brief_time"],
    )


@activity.defn
async def activity_send_interrupt_alert(item: ClassificationItem) -> int:
    """Fires initial push notification and records in interrupts table."""
    with get_db() as conn:
        # Ensure notification exists to satisfy foreign key constraint
        exists = conn.execute(
            "SELECT 1 FROM notifications WHERE id = ?", (item.notification_id,)
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT OR IGNORE INTO notifications (id, source, app_id, title, body, received_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.notification_id,
                    "other",
                    "test.app",
                    item.title,
                    item.body,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        interrupt_id = insert_interrupt(conn, item.notification_id)
        conn.commit()

    deliver_macos_notification(
        title=f"Emergency: {item.title}",
        subtitle=f"Score {item.score:.2f} — {item.reason}",
        body=item.body[:100],
    )
    return interrupt_id


@activity.defn
async def activity_check_acknowledgement(interrupt_id: int) -> bool:
    """Checks whether the user has acknowledged this interrupt."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT acknowledged_at FROM interrupts WHERE id = ?", (interrupt_id,)
        ).fetchone()
        if row and row["acknowledged_at"]:
            return True
    return False


@activity.defn
async def activity_send_escalation_alert(interrupt_id: int, title: str, body: str, reason: str):
    """Escalates an unacknowledged interrupt ONCE. Never twice."""
    with get_db() as conn:
        escalate_interrupt(conn, interrupt_id)
        conn.commit()

    deliver_macos_notification(
        title=f"ESCALATION (Unacknowledged): {title}",
        subtitle=f"No acknowledgement after 10m — {reason}",
        body=body[:100],
        sound="Sosumi",
    )
