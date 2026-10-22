import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from hush.normaliser import normalize_record, to_classifier_projection
from hush.classifier import classify_notification
from hush.scorer import route_decision
from hush.db import get_db, insert_notification, insert_judgment
from hush.config import T_HIGH

console = Console()

STAGED_EMERGENCIES = [
    {
        "drill_id": "drill-health-01",
        "app_id": "com.apple.MobileSMS",
        "title": "City Hospital ER",
        "body": "CRITICAL: Your father was admitted to ER Room 4 after a sudden collapse. Come immediately.",
        "category_expected": "health",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-money-01",
        "app_id": "com.apple.MobileSMS",
        "title": "Chase Fraud Prevention",
        "body": "URGENT: Suspicious unauthorized debit of $3,850.00 at 03:14 AM. Reply NO to block or YES to authorize.",
        "category_expected": "money",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-family-01",
        "app_id": "net.whatsapp.whatsapp",
        "title": "Pooja (Sister)",
        "body": "My car broke down on Highway 101, engine smoking and phone battery at 4%. Please pick me up right now!",
        "category_expected": "person",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-work-01",
        "app_id": "com.workbuddy.workbuddy-ai",
        "title": "PagerDuty P0",
        "body": "P0 prod outage: prod-db-primary unresponsive, 100% customer traffic failing. Need your deploy access NOW.",
        "category_expected": "work",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-safety-01",
        "app_id": "com.apple.MobileSMS",
        "title": "Building Management",
        "body": "EMERGENCY: Active 4-alarm fire reported on 4th floor. Evacuate building immediately via stairwells.",
        "category_expected": "health",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-health-02",
        "app_id": "net.whatsapp.whatsapp",
        "title": "Dr. Sharma Clinic",
        "body": "Prescription critical update: Doctor says stop taking medication X immediately due to acute allergy risk.",
        "category_expected": "health",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-money-02",
        "app_id": "com.apple.MobileSMS",
        "title": "Bank Overdraft Alert",
        "body": "Account overdraft alert: -Rs 45,000. Automated penalty and freeze will apply in 2 hours unless settled.",
        "category_expected": "money",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-family-02",
        "app_id": "net.whatsapp.whatsapp",
        "title": "Mom",
        "body": "Flight got diverted to emergency landing in Reno. Luggage lost and need urgent phone recharge / assistance.",
        "category_expected": "person",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-work-02",
        "app_id": "com.workbuddy.workbuddy-ai",
        "title": "AWS Security Hub",
        "body": "CRITICAL security incident: root credentials leaked in public commit. Revoke keys immediately.",
        "category_expected": "work",
        "should_interrupt": True,
    },
    {
        "drill_id": "drill-safety-02",
        "app_id": "com.apple.MobileSMS",
        "title": "National Weather Alert",
        "body": "Flash flood warning for your exact coordinates: seek higher ground immediately.",
        "category_expected": "health",
        "should_interrupt": True,
    },
]

STAGED_CONTROLS = [
    {
        "drill_id": "control-promo-01",
        "app_id": "com.apple.MobileSMS",
        "title": "QuickLoans",
        "body": "Pre-approved personal loan of 5,00,000 waiting! Click here to claim at 10.5% interest.",
        "category_expected": "promo",
        "should_interrupt": False,
    },
    {
        "drill_id": "control-chat-01",
        "app_id": "net.whatsapp.whatsapp",
        "title": "College Group",
        "body": "Anyone wants to grab pizza tonight after lab?",
        "category_expected": "person",
        "should_interrupt": False,
    },
    {
        "drill_id": "control-work-01",
        "app_id": "com.workbuddy.workbuddy-ai",
        "title": "Weekly Newsletter",
        "body": "Top 10 open-source repositories to watch this Hacktoberfest.",
        "category_expected": "promo",
        "should_interrupt": False,
    },
    {
        "drill_id": "control-academic-01",
        "app_id": "net.whatsapp.whatsapp",
        "title": "Department Office",
        "body": "Mid-semester exams timetable will be uploaded on portal by Friday evening.",
        "category_expected": "work",
        "should_interrupt": False,
    },
    {
        "drill_id": "control-promo-02",
        "app_id": "com.apple.MobileSMS",
        "title": "Zomato",
        "body": "Hungry? Flat 50% off on your favorite biryani order using code FEAST.",
        "category_expected": "promo",
        "should_interrupt": False,
    },
]


def run_fire_drill(conn=None, model=None, verbose=True) -> Dict[str, Any]:
    """
    Executes the 10-case notification fire drill plus 5 non-urgent control cases.
    Measures:
    - Recall (Target >= 9/10)
    - Precision (Target >= 70%)
    - Ingest -> interrupt latency
    - Silence integrity
    - Miss log with scores and reasons
    """
    if conn is None:
        conn = get_db()

    all_test_cases = STAGED_EMERGENCIES + STAGED_CONTROLS

    results = []
    tp = 0
    fn = 0
    fp = 0
    tn = 0
    miss_log = []
    latencies_ms = []

    now_base = datetime.now().astimezone()

    for idx, test_case in enumerate(all_test_cases):
        t_start = time.perf_counter()

        # Interleave with slight timestamp offset
        case_time = now_base - timedelta(minutes=(len(all_test_cases) - idx) * 2)

        record = normalize_record(
            app_id=test_case["app_id"],
            title=test_case["title"],
            body=test_case["body"],
            received_cocoa_ts=case_time.timestamp() - 978307200,
            is_synthetic=True,
            drill_id=test_case["drill_id"],
        )

        # Store in DB
        insert_notification(conn, record)

        # Projection strictly omits is_synthetic and drill_id
        projected = to_classifier_projection(record)

        judgment = classify_notification(projected, model=model)
        insert_judgment(conn, judgment)

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        latencies_ms.append(elapsed_ms)

        score = judgment["score"]
        decision = route_decision(score, t_high=T_HIGH)
        is_interrupt = (decision == "interrupt")

        should_interrupt = test_case["should_interrupt"]

        if should_interrupt and is_interrupt:
            tp += 1
            verdict = "TP"
        elif should_interrupt and not is_interrupt:
            fn += 1
            verdict = "FN (MISS)"
            miss_log.append({
                "drill_id": test_case["drill_id"],
                "title": test_case["title"],
                "body": test_case["body"],
                "score": score,
                "urgency": judgment["urgency"],
                "category": judgment["category"],
                "reason": judgment["reason"],
            })
        elif not should_interrupt and is_interrupt:
            fp += 1
            verdict = "FP (FALSE ALARM)"
        else:
            tn += 1
            verdict = "TN (SILENCED)"

        results.append({
            "drill_id": test_case["drill_id"],
            "title": test_case["title"],
            "score": score,
            "decision": decision,
            "expected_interrupt": should_interrupt,
            "verdict": verdict,
            "latency_ms": round(elapsed_ms, 1),
        })

    conn.commit()

    total_emergencies = len(STAGED_EMERGENCIES)
    recall = tp / total_emergencies if total_emergencies > 0 else 0.0
    total_interrupts = tp + fp
    precision = tp / total_interrupts if total_interrupts > 0 else 0.0
    avg_latency_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0

    output = {
        "summary": {
            "total_emergencies_planted": total_emergencies,
            "emergencies_caught_tp": tp,
            "emergencies_missed_fn": fn,
            "false_alarms_fp": fp,
            "correctly_silenced_tn": tn,
            "recall": round(recall, 3),
            "precision": round(precision, 3),
            "avg_latency_sec": round(avg_latency_ms / 1000.0, 3),
            "silence_integrity_pct": round((tn / len(STAGED_CONTROLS)) * 100, 1),
        },
        "confusion_matrix": {
            "TP": tp,
            "FN": fn,
            "FP": fp,
            "TN": tn,
        },
        "miss_log": miss_log,
        "cases": results,
    }

    if verbose:
        display_drill_report(output)

    return output


def display_drill_report(data: Dict[str, Any]):
    """Pretty prints the drill results and confusion matrix."""
    s = data["summary"]
    table = Table(title="Notification Fire Drill Results", expand=True)
    table.add_column("Drill ID", style="cyan")
    table.add_column("Sender / Title", style="white")
    table.add_column("Score", justify="right")
    table.add_column("Decision", style="bold")
    table.add_column("Outcome", justify="center")
    table.add_column("Latency (ms)", justify="right")

    for c in data["cases"]:
        score_style = "bold red" if c["score"] >= T_HIGH else "dim white"
        verdict_style = (
            "bold green" if "TP" in c["verdict"] or "TN" in c["verdict"]
            else "bold red"
        )
        table.add_row(
            c["drill_id"],
            c["title"],
            f"[{score_style}]{c['score']:.2f}[/{score_style}]",
            c["decision"].upper(),
            f"[{verdict_style}]{c['verdict']}[/{verdict_style}]",
            str(c["latency_ms"]),
        )

    console.print(table)

    cm_text = (
        f"[bold white]Confusion Matrix:[/bold white]\n"
        f"  TP: [bold green]{s['emergencies_caught_tp']}[/bold green]  |  FN: [bold red]{s['emergencies_missed_fn']}[/bold red]\n"
        f"  FP: [bold yellow]{s['false_alarms_fp']}[/bold yellow]  |  TN: [bold green]{s['correctly_silenced_tn']}[/bold green]\n\n"
        f"Recall: [bold cyan]{s['recall'] * 100:.1f}%[/bold cyan] (Target: ≥ 90%)\n"
        f"Precision: [bold cyan]{s['precision'] * 100:.1f}%[/bold cyan] (Target: ≥ 70%)\n"
        f"Avg Latency: [bold cyan]{s['avg_latency_sec']}s[/bold cyan] (Target: < 90s)\n"
        f"Silence Integrity: [bold cyan]{s['silence_integrity_pct']}%[/bold cyan]"
    )

    console.print(Panel(cm_text, title="Scorecard & Metrics", border_style="green"))

    if data["miss_log"]:
        console.print("[bold red]Miss Log:[/bold red]")
        for m in data["miss_log"]:
            console.print(f"  • {m['drill_id']} ({m['title']}): score={m['score']} reason='{m['reason']}'")
