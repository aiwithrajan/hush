import sys
import time
from datetime import datetime
import click
from rich.console import Console
from rich.table import Table

from hush.config import COLLECTOR_POLL_INTERVAL_SECONDS, T_HIGH
from hush.db import (
    init_db,
    get_db,
    get_unclassified_notifications,
    insert_judgment,
)
from hush.collector import collect_macos_notifications
from hush.email_collector import poll_imap_emails
from hush.normaliser import to_classifier_projection
from hush.classifier import classify_notification
from hush.router import generate_brief
from hush.renderer import render_brief_rich, render_brief_text, render_brief_html
from hush.interrupt import handle_interrupt, check_and_escalate_unacknowledged
from hush.drill import run_fire_drill
from hush.app import run_server

console = Console()


@click.group()
def cli():
    """Hush: A local attention router that reads every notification so you only have to read four."""
    pass


@cli.command()
def init():
    """Initializes the local SQLite database schema."""
    init_db()
    console.print("[bold green]✔[/bold green] Hush SQLite database initialized.")


@cli.command()
def ingest():
    """Copies the macOS notification store and polls configured IMAP email into Hush DB."""
    init_db()
    try:
        stats = collect_macos_notifications()
        email_stats = poll_imap_emails()
        total_scanned = stats['scanned'] + email_stats['scanned']
        total_inserted = stats['inserted'] + email_stats['inserted']
        total_duplicates = stats['duplicates'] + email_stats['duplicates']
        email_note = f" (incl. {email_stats['inserted']} emails)" if email_stats['scanned'] > 0 else ""
        console.print(
            f"[bold green]✔ Ingest Complete:[/bold green] "
            f"Scanned [bold]{total_scanned}[/bold] records · "
            f"[bold green]{total_inserted} new inserted{email_note}[/bold green] · "
            f"[dim]{total_duplicates} duplicates skipped[/dim] · "
            f"[dim red]{stats['errors'] + email_stats['errors']} errors[/dim red]"
        )
    except Exception as e:
        console.print(f"[bold red]Ingest failed:[/bold red] {e}")


@cli.command()
@click.option("--limit", default=50, help="Maximum number of unclassified notifications to process.")
@click.option("--model", default=None, help="Override model name.")
def classify(limit, model):
    """Runs classification and scoring on pending notifications."""
    init_db()
    with get_db() as conn:
        unclassified = get_unclassified_notifications(conn, limit=limit)
        if not unclassified:
            console.print("[dim]No unclassified notifications found.[/dim]")
            return

        console.print(f"Classifying [bold]{len(unclassified)}[/bold] notifications...")
        for row in unclassified:
            notif = dict(row)
            projected = to_classifier_projection(notif)
            judgment = classify_notification(projected, model=model)
            insert_judgment(conn, judgment)

            score = judgment["score"]
            sender = notif.get("title", "")
            if score >= T_HIGH:
                handle_interrupt(conn, notif, judgment)
            else:
                console.print(f"  • {sender[:20]:20} -> score: {score:.2f} ({judgment['category']})")

        conn.commit()
        console.print(f"[bold green]✔[/bold green] Processed {len(unclassified)} notifications.")


@cli.command()
@click.option("--hours", default=3, help="Brief time window in hours.")
@click.option("--format", "fmt", type=click.Choice(["rich", "text", "html"]), default="rich")
def brief(hours, fmt):
    """Generates the fixed 4-line brief card for the current window."""
    init_db()
    with get_db() as conn:
        data = generate_brief(conn, window_hours=hours)
        if fmt == "rich":
            render_brief_rich(data)
        elif fmt == "text":
            print(render_brief_text(data))
        elif fmt == "html":
            html = render_brief_html(data)
            print(html)


@cli.command()
@click.option("--limit", default=30, help="Number of discarded items to show.")
def log(limit):
    """Displays the rejection log (the discard pile) with scores and reasons."""
    init_db()
    with get_db() as conn:
        data = generate_brief(conn)
        rejected = data.get("rejected_log", [])

        if not rejected:
            console.print("[dim]No discarded items in current brief window.[/dim]")
            return

        table = Table(title="Hush Rejection Log (Discard Pile)", expand=True)
        table.add_column("App / Source", style="yellow")
        table.add_column("Sender / Title", style="bold white")
        table.add_column("Message Excerpt", style="dim white")
        table.add_column("Score", justify="right", style="cyan")
        table.add_column("Reason for Discard", style="dim")

        for item in rejected[:limit]:
            notif = item["notification"]
            score = notif.get("score", 0.0)
            body = " ".join((notif.get("body") or "").split())[:50]
            table.add_row(
                notif.get("app_id") or notif.get("source"),
                notif.get("title") or "Unknown",
                body,
                f"{score:.2f}",
                item["rejection_reason"],
            )

        console.print(table)
        console.print(f"[dim]Total cut in window: {data.get('cut_count', 0)}[/dim]")


@cli.command()
@click.option("--model", default=None, help="Override model name for drill.")
def drill(model):
    """Executes the Notification Fire Drill (10 staged emergencies) and reports confusion matrix."""
    init_db()
    with get_db() as conn:
        run_fire_drill(conn, model=model, verbose=True)


@cli.command()
@click.option("--interval", default=COLLECTOR_POLL_INTERVAL_SECONDS, help="Seconds between ingest cycles.")
def daemon(interval):
    """Runs continuous background polling loop: ingest -> classify -> check escalations."""
    init_db()
    console.print(f"[bold cyan]Hush daemon started.[/bold cyan] Polling every {interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            with get_db() as conn:
                # 1. Ingest
                stats = collect_macos_notifications(dest_conn=conn)
                if stats["inserted"] > 0:
                    console.print(f"[{datetime.now().strftime('%H:%M:%S')}] Ingested {stats['inserted']} new notifications.")

                # 2. Classify pending
                unclassified = get_unclassified_notifications(conn, limit=20)
                for row in unclassified:
                    notif = dict(row)
                    proj = to_classifier_projection(notif)
                    judgment = classify_notification(proj)
                    insert_judgment(conn, judgment)
                    if judgment["score"] >= T_HIGH:
                        handle_interrupt(conn, notif, judgment)

                # 3. Check escalations for unacknowledged interrupts
                check_and_escalate_unacknowledged(conn)
                conn.commit()

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Hush daemon stopped.[/dim]")


@cli.command()
@click.option("--port", default=8484, help="Port to run local UI server on.")
def ui(port):
    """Starts the local web viewer (One card, one log, one confusion matrix)."""
    run_server(port=port)


@cli.group()
def temporal():
    """Temporal durable workflows, escalation state machine, and worker."""
    pass


@temporal.command("demo")
def temporal_demo():
    """Runs a self-contained end-to-end Temporal workflow demo with time-skipping."""
    import asyncio
    from hush.temporal.worker import run_self_contained_demo
    asyncio.run(run_self_contained_demo())


@temporal.command("worker")
@click.option("--host", default=None, help="Temporal server address.")
def temporal_worker(host):
    """Starts the Hush Temporal Worker connected to a Temporal cluster."""
    import asyncio
    from hush.temporal.worker import run_worker
    asyncio.run(run_worker())


if __name__ == "__main__":
    cli()
