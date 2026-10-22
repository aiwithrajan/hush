import os
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from hush.db import init_db, get_db, insert_notification, insert_judgment, insert_interrupt, escalate_interrupt
from hush.normaliser import (
    cocoa_to_iso,
    normalize_record,
    to_classifier_projection,
    compute_notification_id,
)
from hush.scorer import calculate_score, compute_decay, route_decision
from hush.router import generate_brief, determine_reason_tag
from hush.drill import STAGED_EMERGENCIES, STAGED_CONTROLS, run_fire_drill


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_hush.db"
    init_db(db_file)
    conn = get_db(db_file)
    yield conn
    conn.close()


def test_db_schema_initialization(test_db):
    tables = [
        r[0]
        for r in test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert "notifications" in tables
    assert "judgments" in tables
    assert "briefs" in tables
    assert "interrupts" in tables
    assert "calibration" in tables


def test_normaliser_cocoa_epoch():
    # Cocoa timestamp 0 is 2001-01-01 00:00:00 UTC (Unix ts 978307200)
    iso = cocoa_to_iso(0.0)
    dt = datetime.fromisoformat(iso)
    assert dt.year == 2001 or dt.timestamp() == 978307200

    # 1000 seconds after Cocoa epoch
    iso_1000 = cocoa_to_iso(1000.0)
    dt_1000 = datetime.fromisoformat(iso_1000)
    assert dt_1000.timestamp() == 978307200 + 1000


def test_normaliser_projection_privacy():
    rec = normalize_record(
        app_id="net.whatsapp.whatsapp",
        title="Arjun",
        body="call me when you're free",
        received_cocoa_ts=1000.0,
        is_synthetic=True,
        drill_id="drill-health-01",
    )
    assert rec["is_synthetic"] == 1
    assert rec["drill_id"] == "drill-health-01"

    # Enforced projection strictly omits is_synthetic and drill_id
    projected = to_classifier_projection(rec)
    assert "is_synthetic" not in projected
    assert "drill_id" not in projected
    assert "id" in projected
    assert "title" in projected
    assert "body" in projected
    assert "source" in projected


def test_scorer_deterministic_arithmetic():
    now_iso = datetime.now(timezone.utc).isoformat()

    # Health with urgency 0.9, no deadline -> score = 0.9 * 1.00 * 1.0 = 0.90
    score, consequence, decay = calculate_score(0.9, "health", now_iso, None)
    assert consequence == 1.00
    assert decay == 1.0
    assert score == 0.90
    assert route_decision(score) == "interrupt"

    # Promo with urgency 0.8, no deadline -> score = 0.8 * 0.05 * 1.0 = 0.04
    score_p, cons_p, _ = calculate_score(0.8, "promo", now_iso, None)
    assert cons_p == 0.05
    assert score_p == 0.04
    assert route_decision(score_p) == "reject"

    # Work with urgency 0.4, no deadline -> score = 0.4 * 0.50 * 1.0 = 0.20
    score_w, cons_w, _ = calculate_score(0.4, "work", now_iso, None)
    assert cons_w == 0.50
    assert score_w == 0.20
    assert route_decision(score_w) == "brief"


def test_scorer_decay_calculation():
    recv_dt = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    # Deadline 0 days away (today)
    deadline_dt = recv_dt
    decay = compute_decay(recv_dt.isoformat(), deadline_dt.isoformat())
    # 1 + 2 / (1 + 0) = 3.0
    assert decay == 3.0

    # Deadline 1 day away
    deadline_1d = recv_dt + timedelta(days=1)
    decay_1d = compute_decay(recv_dt.isoformat(), deadline_1d.isoformat())
    # 1 + 2 / (1 + 1) = 2.0
    assert decay_1d == 2.0


def test_router_quota_and_spillover(test_db):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Create 3 emails, 2 whatsapp, 1 sms
    items = [
        # 3 emails: scores 0.45, 0.40, 0.35 (Quota is 2)
        ("com.apple.mail", "Mail 1", "Body 1", 0.45, "mail"),
        ("com.apple.mail", "Mail 2", "Body 2", 0.40, "mail"),
        ("com.apple.mail", "Mail 3", "Body 3", 0.35, "mail"),
        # 2 whatsapp: scores 0.30, 0.25 (Quota is 1)
        ("net.whatsapp.whatsapp", "WA 1", "Body WA1", 0.30, "wa"),
        ("net.whatsapp.whatsapp", "WA 2", "Body WA2", 0.25, "wa"),
    ]

    for app_id, title, body, score, src in items:
        rec = normalize_record(app_id, title, body, now.timestamp() - 978307200)
        insert_notification(test_db, rec)
        test_db.execute(
            """
            INSERT INTO judgments (notification_id, urgency, category, score, reason, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (rec["id"], 0.5, "work", score, "test", "test-model", now_iso),
        )

    test_db.commit()

    brief_data = generate_brief(test_db, window_hours=3, end_time=now + timedelta(minutes=5))
    lines = brief_data["lines"]

    # Maximum 4 lines
    assert len(lines) <= 4

    # Email got 2 base quota
    mail_lines = [l for l in lines if l["source"] == "mail"]
    assert len(mail_lines) >= 2

    # SMS had 0 candidates, so spillover allowed remaining highest score (Mail 3 or WA 2) to borrow slot
    borrowed = brief_data["borrowed"]
    assert len(borrowed) > 0


def test_interrupt_never_nag_twice(test_db):
    now = datetime.now().astimezone()
    rec = normalize_record("net.whatsapp.whatsapp", "Urgent Contact", "Critical alert", now.timestamp() - 978307200)
    insert_notification(test_db, rec)

    int_id = insert_interrupt(test_db, rec["id"])
    assert int_id is not None

    # First escalation succeeds
    escalate_interrupt(test_db, int_id)
    cur = test_db.execute("SELECT escalated_at FROM interrupts WHERE id = ?", (int_id,)).fetchone()
    first_escalated_at = cur["escalated_at"]
    assert first_escalated_at is not None

    # Second escalation does nothing (escalated_at does not change)
    escalate_interrupt(test_db, int_id)
    cur2 = test_db.execute("SELECT escalated_at FROM interrupts WHERE id = ?", (int_id,)).fetchone()
    assert cur2["escalated_at"] == first_escalated_at


def test_fire_drill_execution(test_db):
    # Runs fire drill with deterministic fallback classifier for high-speed regression
    drill_results = run_fire_drill(conn=test_db, model="test-fallback", verbose=False)
    summary = drill_results["summary"]

    assert summary["total_emergencies_planted"] == len(STAGED_EMERGENCIES)
    # Target recall >= 90% (>= 9/10)
    assert summary["recall"] >= 0.90
    # Target precision >= 70%
    assert summary["precision"] >= 0.70
    assert "confusion_matrix" in drill_results
    assert "cases" in drill_results


def test_gemma_live_inference():
    """Tests live inference against the local Gemma model running in Ollama."""
    from hush.classifier import classify_notification
    test_notif = {
        "id": "live-test-01",
        "app_id": "com.apple.MobileSMS",
        "source": "sms",
        "title": "Hospital Emergency Alert",
        "body": "CRITICAL: Patient family contact required in ER immediately.",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    judgment = classify_notification(test_notif, model="gemma:2b", timeout=15.0)
    assert judgment["category"] in ["health", "person"]
    assert judgment["urgency"] >= 0.80
    assert judgment["score"] >= 0.55
