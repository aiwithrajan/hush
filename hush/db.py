import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from hush.config import HUSH_DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,           -- sha256(app|title|body|received_at)
    source TEXT,                   -- wa | mail | sms | other
    app_id TEXT,
    title TEXT,
    body TEXT,
    received_at TEXT,              -- ISO 8601, epoch already corrected
    is_synthetic INTEGER DEFAULT 0, -- never passed to the classifier
    drill_id TEXT
);

CREATE TABLE IF NOT EXISTS judgments (
    notification_id TEXT PRIMARY KEY REFERENCES notifications(id),
    urgency REAL,                  -- 0.0 – 1.0
    category TEXT,                 -- health | money | person | deadline | work | promo
    deadline_at TEXT NULL,
    score REAL,
    reason TEXT,
    model_version TEXT,            -- pinned model name
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    window_start TEXT,
    window_end TEXT,
    kept_ids TEXT,                 -- JSON array of notification_id, max 4
    cut_count INTEGER,
    borrowed TEXT,                 -- JSON of {source: borrowed_count_or_detail}
    rendered_at TEXT
);

CREATE TABLE IF NOT EXISTS interrupts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id TEXT REFERENCES notifications(id),
    fired_at TEXT,
    acknowledged_at TEXT NULL,
    escalated_at TEXT NULL,
    verdict TEXT                   -- useful | noise | missed
);

CREATE TABLE IF NOT EXISTS calibration (
    day TEXT PRIMARY KEY,
    predicted REAL,
    acted_on INTEGER,
    factor REAL
);

CREATE INDEX IF NOT EXISTS idx_notifications_received_at ON notifications(received_at);
CREATE INDEX IF NOT EXISTS idx_judgments_score ON judgments(score);
"""


def get_db(db_path=None) -> sqlite3.Connection:
    path = db_path or HUSH_DB_PATH
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def insert_notification(conn: sqlite3.Connection, notif: Dict[str, Any]) -> bool:
    """Inserts a notification. Returns True if inserted, False if duplicate."""
    try:
        conn.execute(
            """
            INSERT INTO notifications (id, source, app_id, title, body, received_at, is_synthetic, drill_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notif["id"],
                notif["source"],
                notif.get("app_id", ""),
                notif.get("title", ""),
                notif.get("body", ""),
                notif["received_at"],
                1 if notif.get("is_synthetic") else 0,
                notif.get("drill_id"),
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def get_unclassified_notifications(conn: sqlite3.Connection, limit: int = 50) -> List[sqlite3.Row]:
    """Fetches notifications that do not yet have a judgment."""
    cursor = conn.execute(
        """
        SELECT n.*
        FROM notifications n
        LEFT JOIN judgments j ON n.id = j.notification_id
        WHERE j.notification_id IS NULL
        ORDER BY n.received_at ASC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def insert_judgment(conn: sqlite3.Connection, judgment: Dict[str, Any]):
    """Records a judgment for a notification."""
    now_iso = datetime.now().astimezone().isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO judgments (
            notification_id, urgency, category, deadline_at, score, reason, model_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            judgment["notification_id"],
            judgment["urgency"],
            judgment["category"],
            judgment.get("deadline_at"),
            judgment["score"],
            judgment["reason"],
            judgment["model_version"],
            judgment.get("created_at", now_iso),
        ),
    )


def insert_interrupt(conn: sqlite3.Connection, notification_id: str, fired_at: Optional[str] = None) -> int:
    """Records an interrupt alert event."""
    ts = fired_at or datetime.now().astimezone().isoformat()
    cur = conn.execute(
        """
        INSERT INTO interrupts (notification_id, fired_at, acknowledged_at, escalated_at, verdict)
        VALUES (?, ?, NULL, NULL, NULL)
        """,
        (notification_id, ts),
    )
    return cur.lastrowid


def acknowledge_interrupt(conn: sqlite3.Connection, interrupt_id: int, verdict: str = "useful"):
    """Acknowledges an interrupt within the 10-minute window."""
    now_iso = datetime.now().astimezone().isoformat()
    conn.execute(
        """
        UPDATE interrupts
        SET acknowledged_at = ?, verdict = ?
        WHERE id = ?
        """,
        (now_iso, verdict, interrupt_id),
    )


def escalate_interrupt(conn: sqlite3.Connection, interrupt_id: int):
    """Escalates an unacknowledged interrupt once."""
    now_iso = datetime.now().astimezone().isoformat()
    conn.execute(
        """
        UPDATE interrupts
        SET escalated_at = ?
        WHERE id = ? AND escalated_at IS NULL
        """,
        (now_iso, interrupt_id),
    )


def insert_brief(
    conn: sqlite3.Connection,
    window_start: str,
    window_end: str,
    kept_ids: List[str],
    cut_count: int,
    borrowed: Dict[str, Any],
) -> int:
    """Records a generated 3-hour brief card."""
    now_iso = datetime.now().astimezone().isoformat()
    cur = conn.execute(
        """
        INSERT INTO briefs (window_start, window_end, kept_ids, cut_count, borrowed, rendered_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            window_start,
            window_end,
            json.dumps(kept_ids),
            cut_count,
            json.dumps(borrowed),
            now_iso,
        ),
    )
    return cur.lastrowid
