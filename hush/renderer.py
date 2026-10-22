from typing import Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def render_brief_text(brief_data: Dict[str, Any]) -> str:
    """Renders the 4-line brief card as plain text."""
    lines = brief_data.get("lines", [])
    cut_count = brief_data.get("cut_count", 0)
    next_time = brief_data.get("next_brief_time", "in 3 hours")
    window_start = brief_data.get("window_start", "")[:16].replace("T", " ")
    window_end = brief_data.get("window_end", "")[11:16]

    out = []
    out.append("━" * 52)
    out.append(f"  H U S H   B R I E F  ·  {window_start} – {window_end}")
    out.append("━" * 52)

    if not lines:
        out.append("  (All clear. No notifications cleared the bar.)")
    else:
        for idx, item in enumerate(lines, 1):
            tag = item.get("reason_tag", "today").upper()
            src = item.get("source", "other").upper()
            title = item.get("title") or "Unknown"
            body = item.get("body") or ""
            # Clean newlines and truncate body
            clean_body = " ".join(body.split())
            if len(clean_body) > 65:
                clean_body = clean_body[:62] + "..."

            spillover_note = ""
            if item.get("slot_source") == "spillover":
                spillover_note = " ↳ [borrowed slot]"

            out.append(f"  {idx}. [{tag:8}] [{src:4}] {title}: {clean_body}{spillover_note}")

    out.append("━" * 52)
    out.append(f"  {cut_count} cut · Next brief at {next_time}")
    out.append("━" * 52)
    return "\n".join(out)


def render_brief_rich(brief_data: Dict[str, Any]):
    """Renders the brief card using rich terminal formatting."""
    lines = brief_data.get("lines", [])
    cut_count = brief_data.get("cut_count", 0)
    next_time = brief_data.get("next_brief_time", "in 3 hours")
    window_start = brief_data.get("window_start", "")[:16].replace("T", " ")
    window_end = brief_data.get("window_end", "")[11:16]

    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("Tag", style="bold cyan", width=12)
    table.add_column("Source", style="bold yellow", width=8)
    table.add_column("Content", style="white")

    tag_colors = {
        "deadline": "bold red",
        "money": "bold green",
        "person": "bold magenta",
        "reply": "bold blue",
        "today": "dim white",
    }

    if not lines:
        table.add_row("", "", "[dim italic]All clear. No notifications cleared the bar.[/dim italic]")
    else:
        for idx, item in enumerate(lines, 1):
            tag = item.get("reason_tag", "today")
            color = tag_colors.get(tag.lower(), "bold cyan")
            tag_text = f"[{color}][{tag.upper()}][/{color}]"

            src = f"[{item.get('source', 'other').upper()}]"
            title = item.get("title") or "Unknown"
            body = item.get("body") or ""
            clean_body = " ".join(body.split())
            if len(clean_body) > 75:
                clean_body = clean_body[:72] + "..."

            spillover_note = ""
            if item.get("slot_source") == "spillover":
                spillover_note = " [dim](borrowed slot)[/dim]"

            content_text = f"[bold]{title}:[/bold] {clean_body}{spillover_note}"
            table.add_row(tag_text, src, content_text)

    footer = f"[bold yellow]{cut_count} cut[/bold yellow]  ·  Next brief at [bold cyan]{next_time}[/bold cyan]"
    title_header = f"[bold white]H U S H   B R I E F[/bold white]  ·  [dim]{window_start} – {window_end}[/dim]"

    panel = Panel(
        table,
        title=title_header,
        subtitle=footer,
        subtitle_align="center",
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(panel)


def render_brief_html(brief_data: Dict[str, Any]) -> str:
    """Renders the brief card as a self-contained, elegant dark-mode HTML card."""
    lines = brief_data.get("lines", [])
    cut_count = brief_data.get("cut_count", 0)
    next_time = brief_data.get("next_brief_time", "in 3 hours")
    window_start = brief_data.get("window_start", "")[:16].replace("T", " ")
    window_end = brief_data.get("window_end", "")[11:16]

    rows_html = []
    for idx, item in enumerate(lines, 1):
        tag = item.get("reason_tag", "today").upper()
        src = item.get("source", "other").upper()
        title = item.get("title") or "Unknown"
        body = item.get("body") or ""
        clean_body = " ".join(body.split())
        spillover_html = '<span class="borrowed">(borrowed slot)</span>' if item.get("slot_source") == "spillover" else ""
        rows_html.append(f"""
        <div class="brief-row">
            <span class="tag tag-{tag.lower()}">{tag}</span>
            <span class="source">{src}</span>
            <div class="content">
                <strong>{title}:</strong> {clean_body} {spillover_html}
            </div>
        </div>
        """)

    if not rows_html:
        rows_html.append('<div class="empty-state">All clear. No notifications cleared the bar.</div>')

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Hush Brief</title>
    <style>
        body {{
            background: #0d1117;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            width: 100%;
            max-width: 680px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            overflow: hidden;
        }}
        .card-header {{
            padding: 16px 20px;
            border-bottom: 1px solid #21262d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .title {{
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 2px;
            color: #58a6ff;
            text-transform: uppercase;
        }}
        .window {{
            font-size: 12px;
            color: #8b949e;
        }}
        .card-body {{
            padding: 12px 20px;
        }}
        .brief-row {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid #21262d;
            font-size: 14px;
            line-height: 1.4;
        }}
        .brief-row:last-child {{
            border-bottom: none;
        }}
        .tag {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
            letter-spacing: 0.5px;
            min-width: 65px;
            text-align: center;
        }}
        .tag-deadline {{ background: #490202; color: #ff7b72; }}
        .tag-money {{ background: #033a16; color: #7ee787; }}
        .tag-person {{ background: #3d1b54; color: #d2a8ff; }}
        .tag-reply {{ background: #0c2d6b; color: #79c0ff; }}
        .tag-today {{ background: #21262d; color: #8b949e; }}
        .source {{
            font-size: 11px;
            color: #d29922;
            font-weight: bold;
            min-width: 45px;
        }}
        .content {{
            flex: 1;
        }}
        .borrowed {{
            font-size: 11px;
            color: #8b949e;
            font-style: italic;
        }}
        .card-footer {{
            padding: 14px 20px;
            border-top: 1px solid #21262d;
            text-align: center;
            font-size: 13px;
            color: #8b949e;
            background: #12161c;
        }}
        .cut-badge {{
            color: #e3b341;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="title">H U S H   B R I E F</span>
            <span class="window">{window_start} – {window_end}</span>
        </div>
        <div class="card-body">
            {''.join(rows_html)}
        </div>
        <div class="card-footer">
            <span class="cut-badge">{cut_count} cut</span> · Next brief at <strong>{next_time}</strong>
        </div>
    </div>
</body>
</html>"""
