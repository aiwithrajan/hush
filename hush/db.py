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

CREATE TABLE IF NOT EXISTS email_accounts (
    email TEXT PRIMARY KEY,
    host TEXT NOT NULL DEFAULT 'imap.gmail.com',
    port INTEGER DEFAULT 993,
    password TEXT NOT NULL,
    label TEXT,
    is_active INTEGER DEFAULT 1,
    last_polled_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS app_rules (
    app_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'other',
    priority TEXT NOT NULL DEFAULT 'normal', -- priority | normal | muted
    is_active INTEGER DEFAULT 1,
    created_at TEXT
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


def get_setting(conn: sqlite3.Connection, key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves a persistent setting value."""
    cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    if row:
        return row[0]
    return default


def set_setting(conn: sqlite3.Connection, key: str, value: str):
    """Saves or updates a persistent setting."""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()


def get_email_accounts(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Fetches all registered email accounts."""
    cur = conn.execute(
        "SELECT email, host, port, password, label, is_active, last_polled_at, last_error FROM email_accounts ORDER BY email ASC"
    )
    accounts = []
    for r in cur.fetchall():
        d = dict(r)
        # Mask password for API / UI responses
        d["has_password"] = bool(d["password"])
        d["password_masked"] = "••••••••" if d["password"] else ""
        accounts.append(d)
    return accounts


def save_email_account(
    conn: sqlite3.Connection,
    email_addr: str,
    password: str,
    host: str = "imap.gmail.com",
    port: int = 993,
    label: Optional[str] = None,
    is_active: int = 1,
):
    """Registers or updates an email account for background IMAP sync."""
    conn.execute(
        """
        INSERT INTO email_accounts (email, host, port, password, label, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            host = excluded.host,
            port = excluded.port,
            password = CASE WHEN excluded.password != '' THEN excluded.password ELSE email_accounts.password END,
            label = excluded.label,
            is_active = excluded.is_active
        """,
        (email_addr.strip(), host.strip(), port, password.strip(), label or email_addr.split("@")[0], is_active),
    )
    conn.commit()


def delete_email_account(conn: sqlite3.Connection, email_addr: str):
    """Deletes a registered email account."""
    conn.execute("DELETE FROM email_accounts WHERE email = ?", (email_addr.strip(),))
    conn.commit()


def update_email_account_status(conn: sqlite3.Connection, email_addr: str, last_error: Optional[str] = None):
    """Updates last_polled_at and optional last_error for an email account."""
    now_iso = datetime.now().astimezone().isoformat()
    conn.execute(
        "UPDATE email_accounts SET last_polled_at = ?, last_error = ? WHERE email = ?",
        (now_iso, last_error, email_addr.strip()),
    )
    conn.commit()


def get_app_rules(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Returns custom app priority and channel routing rules."""
    cur = conn.execute("SELECT app_id, name, source, priority, is_active FROM app_rules ORDER BY name ASC")
    return [dict(r) for r in cur.fetchall()]


def save_app_rule(
    conn: sqlite3.Connection,
    app_id: str,
    name: str,
    source: str = "other",
    priority: str = "normal",
    is_active: int = 1,
):
    """Registers or updates app priority configuration."""
    now_iso = datetime.now().astimezone().isoformat()
    conn.execute(
        """
        INSERT INTO app_rules (app_id, name, source, priority, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(app_id) DO UPDATE SET
            name = excluded.name,
            source = excluded.source,
            priority = excluded.priority,
            is_active = excluded.is_active
        """,
        (app_id.strip(), name.strip(), source.strip().lower(), priority.strip().lower(), is_active, now_iso),
    )
    conn.commit()


def delete_app_rule(conn: sqlite3.Connection, app_id: str):
    """Deletes an app routing rule."""
    conn.execute("DELETE FROM app_rules WHERE app_id = ?", (app_id.strip(),))
    conn.commit()


def get_detected_apps(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Discovers all apps that have posted notifications to this device with counts."""
    cur = conn.execute(
        """
        SELECT 
            n.app_id,
            COUNT(*) as notif_count,
            MAX(n.received_at) as last_seen,
            COALESCE(r.name, n.app_id) as display_name,
            COALESCE(r.source, n.source) as source,
            COALESCE(r.priority, 'normal') as priority
        FROM notifications n
        LEFT JOIN app_rules r ON n.app_id = r.app_id
        WHERE n.app_id IS NOT NULL AND n.app_id != ''
        GROUP BY n.app_id
        ORDER BY notif_count DESC
        """
    )
    return [dict(r) for r in cur.fetchall()]




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
