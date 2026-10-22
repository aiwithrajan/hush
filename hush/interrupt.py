import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from rich.console import Console
from hush.db import get_db, insert_interrupt, escalate_interrupt, acknowledge_interrupt
from hush.config import INTERRUPT_ACK_WAIT_MINUTES

console = Console()


def deliver_macos_notification(title: str, subtitle: str, body: str, sound: str = "Submarine"):
    """Fires native macOS notification using osascript."""
    # Sanitize inputs for AppleScript string escaping
    safe_title = title.replace('"', '\\"').replace("'", "\\'")
    safe_subtitle = subtitle.replace('"', '\\"').replace("'", "\\'")
    safe_body = body.replace('"', '\\"').replace("'", "\\'")

    script = (
        f'display notification "{safe_body}" '
        f'with title "HUSH · {safe_title}" '
        f'subtitle "{safe_subtitle}" '
        f'sound name "{sound}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception as e:
        console.print(f"[dim yellow]Warning: could not trigger macOS notification: {e}[/dim yellow]")


def handle_interrupt(
    conn,
    notif: Dict[str, Any],
    judgment: Dict[str, Any],
) -> int:
    """
    Executes the interrupt path:
    1. Records event in interrupts table.
    2. Delivers immediate push containing message and reason it cleared the bar.
    """
    fired_at = datetime.now().astimezone().isoformat()
    interrupt_id = insert_interrupt(conn, notif["id"], fired_at)

    sender = notif.get("title", "Important")
    reason = judgment.get("reason", "High-urgency alert")
    score = judgment.get("score", 0.0)
    body = notif.get("body", "")

    console.print(
        f"\n[bold red]⚡ HUSH INTERRUPT FIRED (Score: {score:.2f})[/bold red]\n"
        f"[bold white]Sender:[/bold white] {sender}\n"
        f"[bold white]Reason:[/bold white] {reason}\n"
        f"[bold white]Message:[/bold white] {body}\n"
    )

    deliver_macos_notification(
        title=f"Emergency: {sender}",
        subtitle=f"Score {score:.2f} — {reason}",
        body=body[:100],
    )

    return interrupt_id


def check_and_escalate_unacknowledged(conn):
    """
    Checks all interrupts older than 10 minutes that have not been acknowledged.
    Escalates ONCE. Never twice.
    """
    now = datetime.now().astimezone()
    threshold_time = (now - timedelta(minutes=INTERRUPT_ACK_WAIT_MINUTES)).isoformat()

    cur = conn.execute(
        """
        SELECT i.id, i.fired_at, n.title, n.body, j.reason, j.score
        FROM interrupts i
        JOIN notifications n ON i.notification_id = n.id
        JOIN judgments j ON n.id = j.notification_id
        WHERE i.acknowledged_at IS NULL
          AND i.escalated_at IS NULL
          AND i.fired_at <= ?
        """,
        (threshold_time,),
    )
    unacked = cur.fetchall()

    for row in unacked:
        interrupt_id = row["id"]
        sender = row["title"]
        body = row["body"]
        reason = row["reason"]

        console.print(f"[bold yellow]⚠️  Escalating unacknowledged interrupt #{interrupt_id} from {sender}...[/bold yellow]")
        deliver_macos_notification(
            title=f"ESCALATION (Unacknowledged): {sender}",
            subtitle=f"No acknowledgement after 10m — {reason}",
            body=body[:100],
            sound="Sosumi",
        )
        escalate_interrupt(conn, interrupt_id)
        conn.commit()
