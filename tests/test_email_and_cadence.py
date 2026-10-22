import pytest
from hush.db import (
    init_db,
    save_email_account,
    get_email_accounts,
    delete_email_account,
    get_setting,
    set_setting,
)
from hush.email_collector import simulate_sample_emails
from hush.router import generate_brief
from hush.interrupt import deliver_summary_notification


def test_email_accounts_and_settings(tmp_path):
    db_file = tmp_path / "test_email.db"
    init_db(db_file)

    from hush.db import get_db

    with get_db(db_file) as conn:
        # Settings
        assert get_setting(conn, "cadence_minutes", "180") == "180"
        set_setting(conn, "cadence_minutes", "60")
        assert get_setting(conn, "cadence_minutes") == "60"

        # Email accounts
        save_email_account(conn, "jarajan123@gmail.com", "app_pass_1234")
        save_email_account(conn, "imrajan098@gmail.com", "app_pass_5678")

        accounts = get_email_accounts(conn)
        assert len(accounts) == 2
        emails = [a["email"] for a in accounts]
        assert "jarajan123@gmail.com" in emails
        assert "imrajan098@gmail.com" in emails
        assert accounts[0]["has_password"] is True
        assert accounts[0]["password_masked"] == "••••••••"

        # Simulation
        inserted = simulate_sample_emails(conn, "jarajan123@gmail.com")
        assert len(inserted) >= 2

        # Delete
        delete_email_account(conn, "imrajan098@gmail.com")
        accounts_after = get_email_accounts(conn)
        assert len(accounts_after) == 1
        assert accounts_after[0]["email"] == "jarajan123@gmail.com"


def test_quiet_cadence_summary_silence_integrity(tmp_path):
    """Verifies that the summary notification never leaks raw message contents,

    surfacing only high-level kept/silenced counts.
    """
    sample_brief = {
        "kept_count": 4,
        "cut_count": 32,
        "lines": [
            {"source": "mail", "title": "Secret Payroll Info", "body": "Sensitive salary breakdown"},
            {"source": "mail", "title": "Health Portal", "body": "Confidential diagnosis"},
            {"source": "wa", "title": "Family", "body": "Personal chat"},
            {"source": "sms", "title": "Bank OTP", "body": "Your OTP is 892110"},
        ],
    }

    alert = deliver_summary_notification(sample_brief)

    # Silence integrity checks:
    # 1. Alert must show kept count and silenced count
    assert "4 Kept" in alert["title"]
    assert "32 silenced" in alert["subtitle"]
    # 2. Raw sensitive bodies or OTPs MUST NOT leak into the alert
    assert "Sensitive salary breakdown" not in alert["body"]
    assert "892110" not in alert["body"]
    assert "Confidential diagnosis" not in alert["body"]
