import os
import email
import email.message
import imaplib
import socket
from email.header import decode_header
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from hush.db import (
    get_db,
    insert_notification,
    get_email_accounts,
    update_email_account_status,
)
from hush.normaliser import compute_notification_id


def decode_header_str(header_val: Optional[str]) -> str:
    """Decodes encoded email headers (e.g. UTF-8, base64) to clean string."""
    if not header_val:
        return ""
    try:
        decoded_parts = decode_header(header_val)
        text_parts = []
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                text_parts.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                text_parts.append(str(part))
        return " ".join(text_parts).strip()
    except Exception:
        return str(header_val)


def extract_body_snippet(msg: email.message.Message, max_len: int = 200) -> str:
    """Extracts plain text body snippet from email message."""
    snippet = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disp = str(part.get("Content-Disposition", ""))
                if content_type == "text/plain" and "attachment" not in content_disp:
                    payload = part.get_payload(decode=True)
                    if payload:
                        snippet = payload.decode("utf-8", errors="replace").strip()
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                snippet = payload.decode("utf-8", errors="replace").strip()
    except Exception:
        snippet = ""

    clean = " ".join(snippet.split())
    return clean[:max_len]


def verify_email_credentials(
    email_addr: str,
    password: str,
    host: str = "imap.gmail.com",
    port: int = 993,
    timeout_sec: float = 8.0,
) -> Tuple[bool, str]:
    """Tests IMAP SSL connection and credentials against server."""
    if not email_addr or not password:
        return False, "Email and password cannot be empty."

    try:
        client = imaplib.IMAP4_SSL(host, port, timeout=timeout_sec)
        client.login(email_addr.strip(), password.strip())
        client.logout()
        return True, "Connected successfully."
    except imaplib.IMAP4.error as err:
        err_msg = str(err)
        if "AUTHENTICATIONFAILED" in err_msg.upper() or "INVALID CREDENTIALS" in err_msg.upper():
            return False, "Invalid credentials. If using Gmail, make sure to use a 16-character Google App Password."
        return False, f"IMAP error: {err_msg}"
    except (socket.timeout, TimeoutError):
        return False, f"Connection to {host}:{port} timed out after {timeout_sec}s."
    except Exception as ex:
        return False, f"Connection failed: {str(ex)}"


def poll_imap_emails(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    folder: str = "INBOX",
    limit: int = 15,
    dest_conn=None,
) -> Dict[str, int]:
    """Connects to IMAP server, polls recent UNSEEN emails, and normalizes them into Hush DB."""
    imap_host = host or os.getenv("HUSH_IMAP_HOST")
    imap_user = username or os.getenv("HUSH_IMAP_USER")
    imap_pass = password or os.getenv("HUSH_IMAP_PASSWORD")

    stats = {"scanned": 0, "inserted": 0, "duplicates": 0, "errors": 0}

    if not imap_host or not imap_user or not imap_pass:
        return stats

    own_conn = False
    if dest_conn is None:
        dest_conn = get_db()
        own_conn = True

    try:
        client = imaplib.IMAP4_SSL(imap_host, timeout=10.0)
        client.login(imap_user, imap_pass)
        client.select(folder, readonly=True)

        status, messages = client.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            client.logout()
            return stats

        mail_ids = messages[0].split()
        recent_ids = mail_ids[-limit:]

        for m_id in reversed(recent_ids):
            stats["scanned"] += 1
            try:
                res, data = client.fetch(m_id, "(RFC822)")
                if res != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                sender = decode_header_str(msg.get("From", "Unknown Sender"))
                subject = decode_header_str(msg.get("Subject", "(No Subject)"))
                date_str = msg.get("Date")

                try:
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    received_iso = parsed_date.astimezone().isoformat()
                except Exception:
                    received_iso = datetime.now(timezone.utc).isoformat()

                snippet = extract_body_snippet(msg)
                body = f"{subject} — {snippet}" if snippet else subject

                app_id = "com.apple.mail"
                notif_id = compute_notification_id(app_id, sender, body, received_iso)

                record = {
                    "id": notif_id,
                    "source": "mail",
                    "app_id": app_id,
                    "title": sender,
                    "body": body,
                    "received_at": received_iso,
                    "is_synthetic": 0,
                    "drill_id": None,
                }

                inserted = insert_notification(dest_conn, record)
                if inserted:
                    stats["inserted"] += 1
                else:
                    stats["duplicates"] += 1

            except Exception:
                stats["errors"] += 1

        client.logout()
        if own_conn:
            dest_conn.commit()

    except Exception:
        stats["errors"] += 1
    finally:
        if own_conn:
            dest_conn.close()

    return stats


def poll_all_configured_emails(dest_conn=None) -> Dict[str, Any]:
    """Polls all active accounts from the DB and any configured via environment variables."""
    own_conn = False
    if dest_conn is None:
        dest_conn = get_db()
        own_conn = True

    total_stats = {
        "scanned": 0,
        "inserted": 0,
        "duplicates": 0,
        "errors": 0,
        "accounts_polled": 0,
        "details": [],
    }

    try:
        # 1. Accounts saved in SQLite
        accounts = get_email_accounts(dest_conn)
        active_accounts = [a for a in accounts if a.get("is_active", 1)]

        for acc in active_accounts:
            email_addr = acc["email"]
            host = acc.get("host") or "imap.gmail.com"
            password = acc["password"]

            st = poll_imap_emails(
                host=host,
                username=email_addr,
                password=password,
                limit=15,
                dest_conn=dest_conn,
            )

            total_stats["scanned"] += st["scanned"]
            total_stats["inserted"] += st["inserted"]
            total_stats["duplicates"] += st["duplicates"]
            total_stats["errors"] += st["errors"]
            total_stats["accounts_polled"] += 1

            err_msg = "Error syncing mailbox" if st["errors"] > 0 else None
            update_email_account_status(dest_conn, email_addr, last_error=err_msg)

            total_stats["details"].append({
                "email": email_addr,
                "stats": st,
            })

        # 2. Check if env vars have a distinct account not already polled
        env_user = os.getenv("HUSH_IMAP_USER")
        env_host = os.getenv("HUSH_IMAP_HOST")
        env_pass = os.getenv("HUSH_IMAP_PASSWORD")

        if env_user and env_user not in [a["email"] for a in active_accounts]:
            st = poll_imap_emails(
                host=env_host,
                username=env_user,
                password=env_pass,
                dest_conn=dest_conn,
            )
            total_stats["scanned"] += st["scanned"]
            total_stats["inserted"] += st["inserted"]
            total_stats["duplicates"] += st["duplicates"]
            total_stats["errors"] += st["errors"]
            total_stats["accounts_polled"] += 1
            total_stats["details"].append({"email": env_user, "stats": st})

        if own_conn:
            dest_conn.commit()
    finally:
        if own_conn:
            dest_conn.close()

    return total_stats


def simulate_sample_emails(
    dest_conn,
    email_account: str,
    scenario: str = "mix",
) -> List[Dict[str, Any]]:
    """Injects sample emails into Hush DB for testing accounts like jarajan123@gmail.com or imrajan098@gmail.com.

    This ensures user can instantly test email ingestion and brief routing even before generating App Passwords.
    """
    now = datetime.now().astimezone()
    samples = []

    if scenario in ("mix", "urgent"):
        samples.append({
            "sender": f"Security Alert <no-reply@accounts.google.com>",
            "subject": f"Critical security alert for {email_account}",
            "body": f"Critical security alert for {email_account} — A new sign-in was detected on Linux from Bucharest, Romania. Review activity immediately.",
            "source": "mail",
        })
    if scenario in ("mix", "normal"):
        samples.append({
            "sender": f"Finance Payroll <finance@company.org>",
            "subject": f"October Reimbursement Approved for {email_account.split('@')[0]}",
            "body": f"October Reimbursement Approved — Your expense report of $420.00 has been reviewed and queued for direct deposit on Friday.",
            "source": "mail",
        })
    if scenario in ("mix", "deadline"):
        samples.append({
            "sender": f"University Registrar <noreply@admissions.edu>",
            "subject": f"Tuition Fee Due Today for {email_account}",
            "body": f"Tuition Fee Due Today — Final reminder that fall semester fees must be settled before 11:59 PM tonight to avoid late penalty.",
            "source": "mail",
        })

    inserted_records = []
    app_id = "com.apple.mail"
    for s in samples:
        iso_str = now.isoformat()
        notif_id = compute_notification_id(app_id, s["sender"], s["body"], iso_str)
        record = {
            "id": notif_id,
            "source": "mail",
            "app_id": app_id,
            "title": s["sender"],
            "body": s["body"],
            "received_at": iso_str,
            "is_synthetic": 0,
            "drill_id": None,
        }
        if insert_notification(dest_conn, record):
            inserted_records.append(record)

    dest_conn.commit()
    return inserted_records
