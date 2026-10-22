import json
import sqlite3
from typing import Any, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from hush.db import get_db, init_db, get_unclassified_notifications, insert_judgment
from hush.collector import collect_macos_notifications
from hush.classifier import classify_notification
from hush.router import generate_brief
from hush.drill import run_fire_drill
from hush.interrupt import handle_interrupt
from hush.normaliser import to_classifier_projection
from hush.config import T_HIGH

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hush · Local Attention Router</title>
    <style>
        :root {
            --bg: #090d16;
            --surface: #131b26;
            --surface-hover: #1b2636;
            --border: #212e40;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-blue: #58a6ff;
            --accent-red: #f85149;
            --accent-green: #3fb950;
            --accent-purple: #bc8cff;
            --accent-amber: #d29922;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, monospace;
            padding: 32px 20px;
            line-height: 1.5;
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
        }
        header {
            margin-bottom: 28px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid var(--border);
            padding-bottom: 18px;
        }
        .brand h1 {
            font-size: 24px;
            letter-spacing: 2px;
            font-weight: 700;
            color: #fff;
            text-transform: uppercase;
        }
        .brand p {
            color: var(--text-secondary);
            font-size: 13px;
            margin-top: 4px;
        }
        .actions {
            display: flex;
            gap: 10px;
        }
        button {
            background: var(--surface);
            color: var(--text-primary);
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        button:hover {
            background: var(--surface-hover);
            border-color: var(--accent-blue);
        }
        button.primary {
            background: #1f6feb;
            border-color: #388bfd;
            color: white;
        }
        button.primary:hover {
            background: #388bfd;
        }
        .section-title {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-secondary);
            margin: 28px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title::after {
            content: "";
            flex: 1;
            height: 1px;
            background: var(--border);
        }
        /* The Card */
        .card-container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            box-shadow: 0 12px 32px rgba(0,0,0,0.4);
            overflow: hidden;
        }
        .card-header {
            padding: 14px 20px;
            background: #0f1620;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header .title {
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 2px;
            color: var(--accent-blue);
            text-transform: uppercase;
        }
        .card-header .window {
            font-size: 12px;
            color: var(--text-secondary);
        }
        .brief-item {
            display: flex;
            align-items: flex-start;
            padding: 14px 20px;
            border-bottom: 1px solid var(--border);
            gap: 12px;
            font-size: 14px;
        }
        .brief-item:last-child {
            border-bottom: none;
        }
        .tag {
            font-size: 10px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            min-width: 68px;
            text-align: center;
        }
        .tag-deadline { background: #490202; color: #ff7b72; border: 1px solid #ff7b7244; }
        .tag-money { background: #033a16; color: #7ee787; border: 1px solid #7ee78744; }
        .tag-person { background: #3d1b54; color: #d2a8ff; border: 1px solid #d2a8ff44; }
        .tag-reply { background: #0c2d6b; color: #79c0ff; border: 1px solid #79c0ff44; }
        .tag-today { background: #212e40; color: #8b949e; border: 1px solid #8b949e44; }
        .source-pill {
            font-size: 11px;
            font-weight: 700;
            color: var(--accent-amber);
            min-width: 44px;
        }
        .item-content {
            flex: 1;
        }
        .item-title {
            font-weight: 600;
            color: #fff;
            margin-right: 6px;
        }
        .item-body {
            color: var(--text-primary);
        }
        .item-borrowed {
            font-size: 11px;
            color: var(--text-muted);
            margin-left: 6px;
            font-style: italic;
        }
        .card-footer {
            padding: 12px 20px;
            background: #0f1620;
            border-top: 1px solid var(--border);
            text-align: center;
            font-size: 13px;
            color: var(--text-secondary);
        }
        .cut-highlight {
            color: var(--accent-amber);
            font-weight: 700;
        }
        /* Matrix & Metrics */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 16px;
        }
        .metric-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 22px;
            font-weight: 700;
            margin-top: 4px;
            color: #fff;
        }
        /* Table */
        .table-wrap {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow-x: auto;
            max-height: 400px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }
        th {
            background: #0f1620;
            padding: 10px 14px;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 1;
        }
        td {
            padding: 10px 14px;
            border-bottom: 1px solid #1c2736;
            color: var(--text-primary);
        }
        tr:hover td {
            background: var(--surface-hover);
        }
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-tp { background: #033a16; color: #7ee787; }
        .badge-fn { background: #490202; color: #ff7b72; }
        .badge-fp { background: #452a05; color: #e3b341; }
        .badge-tn { background: #1c2736; color: #8b949e; }
        .status-bar {
            margin-top: 16px;
            padding: 8px 14px;
            border-radius: 6px;
            background: #111a24;
            border: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>Hush</h1>
                <p>A local attention router that reads every notification so you only have to read four.</p>
            </div>
            <div class="actions">
                <button onclick="syncNotifications()">Sync Notifications</button>
                <button onclick="runClassify()">Run Classifier</button>
                <button class="primary" onclick="runFireDrill()">Run Fire Drill</button>
            </div>
        </header>

        <!-- 1. The Brief Card -->
        <div class="section-title">The Four Lines (3-Hour Brief)</div>
        <div class="card-container" id="brief-card">
            <div class="card-header">
                <span class="title">H U S H   B R I E F</span>
                <span class="window" id="brief-window">Loading window...</span>
            </div>
            <div id="brief-items">
                <div style="padding: 24px; text-align: center; color: var(--text-muted);">Loading brief...</div>
            </div>
            <div class="card-footer" id="brief-footer">
                <span class="cut-highlight">0 cut</span> · Next brief at --:--
            </div>
        </div>

        <!-- 2. Fire Drill & Scorecard -->
        <div class="section-title">Notification Fire Drill · Ground Truth & Miss Log</div>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Staged Emergencies Recall</div>
                <div class="metric-value" id="metric-recall" style="color: var(--accent-green);">--%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Interrupt Precision</div>
                <div class="metric-value" id="metric-precision" style="color: var(--accent-blue);">--%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Decision Latency</div>
                <div class="metric-value" id="metric-latency">--s</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Silence Integrity</div>
                <div class="metric-value" id="metric-silence" style="color: var(--accent-purple);">--%</div>
            </div>
        </div>

        <div class="table-wrap" id="drill-table-wrap" style="margin-bottom: 24px;">
            <table>
                <thead>
                    <tr>
                        <th>Drill ID</th>
                        <th>Sender / Title</th>
                        <th>Category</th>
                        <th>Score</th>
                        <th>Decision</th>
                        <th>Verdict</th>
                        <th>Latency</th>
                    </tr>
                </thead>
                <tbody id="drill-tbody">
                    <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Click "Run Fire Drill" to test 10 staged emergencies against the ground truth.</td></tr>
                </tbody>
            </table>
        </div>

        <!-- 3. The Discard Pile / Rejection Log -->
        <div class="section-title">The Rejection Log (The Discard Pile)</div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>App / Source</th>
                        <th>Sender</th>
                        <th>Message Excerpt</th>
                        <th>Score</th>
                        <th>Reason Rejected</th>
                    </tr>
                </thead>
                <tbody id="rejection-tbody">
                    <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading discard pile...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="status-bar" id="status-bar">
            <span>System Status: Local SQLite connected · Privacy boundary intact (no payload leaves device)</span>
            <span id="model-status">Model: Loading...</span>
        </div>
    </div>

    <script>
        async function loadBrief() {
            try {
                const res = await fetch('/api/brief');
                const data = await res.json();
                
                document.getElementById('brief-window').innerText = 
                    `${data.window_start.substring(0,16).replace('T', ' ')} – ${data.window_end.substring(11,16)}`;
                
                const container = document.getElementById('brief-items');
                if (!data.lines || data.lines.length === 0) {
                    container.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted);">All clear. No notifications cleared the bar.</div>';
                } else {
                    container.innerHTML = data.lines.map(line => {
                        const tag = (line.reason_tag || 'today').toUpperCase();
                        const tagClass = 'tag-' + tag.toLowerCase();
                        const src = (line.source || 'other').toUpperCase();
                        const borrowed = line.slot_source === 'spillover' ? '<span class="item-borrowed">(borrowed slot)</span>' : '';
                        return `
                            <div class="brief-item">
                                <span class="tag ${tagClass}">${tag}</span>
                                <span class="source-pill">[${src}]</span>
                                <div class="item-content">
                                    <span class="item-title">${escapeHtml(line.title || 'Unknown')}:</span>
                                    <span class="item-body">${escapeHtml(line.body || '')}</span>
                                    ${borrowed}
                                </div>
                            </div>
                        `;
                    }).join('');
                }

                document.getElementById('brief-footer').innerHTML = 
                    `<span class="cut-highlight">${data.cut_count} cut</span> · Next brief at <strong>${data.next_brief_time}</strong>`;

                loadRejectionLog(data.rejected_log || []);
            } catch (err) {
                console.error("Failed to load brief", err);
            }
        }

        function loadRejectionLog(log) {
            const tbody = document.getElementById('rejection-tbody');
            if (!log || log.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No items in the discard pile.</td></tr>';
                return;
            }
            tbody.innerHTML = log.map(item => {
                const notif = item.notification;
                const time = (notif.received_at || '').substring(11, 19);
                return `
                    <tr>
                        <td style="color: var(--text-muted);">${time}</td>
                        <td style="color: var(--accent-amber); font-weight: 600;">${escapeHtml(notif.app_id || notif.source)}</td>
                        <td><strong>${escapeHtml(notif.title || '')}</strong></td>
                        <td>${escapeHtml((notif.body || '').substring(0, 50))}</td>
                        <td style="font-family: monospace;">${Number(notif.score || 0).toFixed(2)}</td>
                        <td style="color: var(--text-secondary);">${escapeHtml(item.rejection_reason || '')}</td>
                    </tr>
                `;
            }).join('');
        }

        async function syncNotifications() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerText = "Syncing...";
            try {
                const res = await fetch('/api/collect', { method: 'POST' });
                const r = await res.json();
                alert(`Scanned ${r.scanned} records (${r.inserted} new, ${r.duplicates} duplicates)`);
                await loadBrief();
            } finally {
                btn.disabled = false;
                btn.innerText = "Sync Notifications";
            }
        }

        async function runClassify() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerText = "Classifying...";
            try {
                const res = await fetch('/api/classify', { method: 'POST' });
                const r = await res.json();
                alert(`Classified ${r.classified} notifications.`);
                await loadBrief();
            } finally {
                btn.disabled = false;
                btn.innerText = "Run Classifier";
            }
        }

        async function runFireDrill() {
            const btn = event.target;
            btn.disabled = true;
            btn.innerText = "Running Drill...";
            try {
                const res = await fetch('/api/drill', { method: 'POST' });
                const r = await res.json();
                
                const s = r.summary;
                document.getElementById('metric-recall').innerText = `${(s.recall * 100).toFixed(0)}%`;
                document.getElementById('metric-precision').innerText = `${(s.precision * 100).toFixed(0)}%`;
                document.getElementById('metric-latency').innerText = `${s.avg_latency_sec}s`;
                document.getElementById('metric-silence').innerText = `${s.silence_integrity_pct}%`;

                const tbody = document.getElementById('drill-tbody');
                tbody.innerHTML = r.cases.map(c => {
                    let badgeClass = 'badge-tn';
                    if (c.verdict.includes('TP')) badgeClass = 'badge-tp';
                    if (c.verdict.includes('FN')) badgeClass = 'badge-fn';
                    if (c.verdict.includes('FP')) badgeClass = 'badge-fp';
                    return `
                        <tr>
                            <td style="color: var(--accent-blue); font-family: monospace;">${c.drill_id}</td>
                            <td>${escapeHtml(c.title)}</td>
                            <td>${c.decision}</td>
                            <td style="font-family: monospace;">${Number(c.score).toFixed(2)}</td>
                            <td><strong>${c.decision.toUpperCase()}</strong></td>
                            <td><span class="badge ${badgeClass}">${c.verdict}</span></td>
                            <td style="text-align: right; font-family: monospace;">${c.latency_ms}ms</td>
                        </tr>
                    `;
                }).join('');

                await loadBrief();
            } finally {
                btn.disabled = false;
                btn.innerText = "Run Fire Drill";
            }
        }

        function escapeHtml(str) {
            return (str || '').replace(/[&<>"']/g, function(m) {
                return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[m];
            });
        }

        window.onload = () => {
            loadBrief();
        };
    </script>
</body>
</html>
"""


class HushHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_str: str, status_code: int = 200):
        body = html_str.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_html(HTML_PAGE)
        elif path == "/api/brief":
            with get_db() as conn:
                brief_data = generate_brief(conn)
                self._send_json(brief_data)
        elif path == "/api/drill":
            with get_db() as conn:
                drill_data = run_fire_drill(conn, verbose=False)
                self._send_json(drill_data)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/collect":
            with get_db() as conn:
                stats = collect_macos_notifications(dest_conn=conn)
                self._send_json(stats)
        elif path == "/api/classify":
            with get_db() as conn:
                unclassified = get_unclassified_notifications(conn, limit=50)
                classified_count = 0
                for row in unclassified:
                    notif = dict(row)
                    proj = to_classifier_projection(notif)
                    judgment = classify_notification(proj)
                    insert_judgment(conn, judgment)
                    if judgment["score"] >= T_HIGH:
                        handle_interrupt(conn, notif, judgment)
                    classified_count += 1
                conn.commit()
                self._send_json({"classified": classified_count})
        elif path == "/api/drill":
            with get_db() as conn:
                drill_data = run_fire_drill(conn, verbose=False)
                self._send_json(drill_data)
        else:
            self.send_error(404, "Not Found")


def run_server(port: int = 8484):
    init_db()
    server_address = ("", port)
    httpd = HTTPServer(server_address, HushHTTPHandler)
    print(f"Hush UI running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
