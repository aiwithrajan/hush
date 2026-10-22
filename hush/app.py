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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#090d16">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Hush · Local Attention Router</title>
    <style>
        :root {
            --bg: #090d16;
            --surface: #121824;
            --surface-card: #162030;
            --surface-hover: #1c293d;
            --border: #223247;
            --border-light: #2c415c;
            --text-primary: #e6edf3;
            --text-secondary: #8b9bb0;
            --text-muted: #5f7087;
            --accent-blue: #58a6ff;
            --accent-blue-bg: #1f6feb;
            --accent-red: #ff7b72;
            --accent-green: #3fb950;
            --accent-purple: #d2a8ff;
            --accent-amber: #e3b341;
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body {
            background-color: var(--bg);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 24px 16px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        
        /* Header */
        header {
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 16px;
        }
        .brand-title-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .brand h1 {
            font-size: 26px;
            letter-spacing: 2px;
            font-weight: 800;
            color: #ffffff;
            text-transform: uppercase;
        }
        .badge-live {
            background: #033a16;
            color: #7ee787;
            border: 1px solid #7ee78744;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 12px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .brand p {
            color: var(--text-secondary);
            font-size: 13px;
            margin-top: 4px;
            line-height: 1.4;
            max-width: 480px;
        }
        .actions {
            display: flex;
            gap: 8px;
            flex-shrink: 0;
        }
        button {
            background: var(--surface);
            color: var(--text-primary);
            border: 1px solid var(--border);
            padding: 9px 15px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            white-space: nowrap;
        }
        button:hover {
            background: var(--surface-hover);
            border-color: var(--accent-blue);
        }
        button:active {
            transform: scale(0.97);
        }
        button.primary {
            background: var(--accent-blue-bg);
            border-color: #388bfd;
            color: white;
            box-shadow: 0 2px 8px rgba(31, 111, 235, 0.4);
        }
        button.primary:hover {
            background: #388bfd;
        }

        /* Mobile Tab Switcher */
        .mobile-tabs {
            display: none;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 4px;
            margin-bottom: 18px;
            gap: 4px;
        }
        .tab-btn {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 600;
            padding: 8px 6px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            text-align: center;
        }
        .tab-btn.active {
            background: var(--surface-card);
            color: #ffffff;
            box-shadow: 0 1px 4px rgba(0,0,0,0.3);
            border: 1px solid var(--border-light);
        }

        /* Section Headings */
        .section-title {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-muted);
            margin: 24px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-title::after {
            content: "";
            flex: 1;
            height: 1px;
            background: var(--border);
        }

        /* The 4-Line Brief Card */
        .card-container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: 0 12px 36px rgba(0,0,0,0.45);
            overflow: hidden;
            margin-bottom: 24px;
        }
        .card-header {
            padding: 14px 18px;
            background: #0d141e;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: nowrap;
            gap: 10px;
        }
        .card-header .title {
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: var(--accent-blue);
            text-transform: uppercase;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .card-header .window-badge {
            font-size: 11px;
            font-weight: 500;
            color: var(--text-secondary);
            background: #151f2e;
            padding: 3px 9px;
            border-radius: 12px;
            border: 1px solid var(--border);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Brief Card Rows */
        .brief-item {
            padding: 14px 18px;
            border-bottom: 1px solid var(--border);
            transition: background 0.15s ease;
        }
        .brief-item:last-child {
            border-bottom: none;
        }
        .brief-item:hover {
            background: rgba(255,255,255,0.015);
        }
        .item-meta-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }
        .tag {
            font-size: 10px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            text-align: center;
            flex-shrink: 0;
        }
        .tag-deadline { background: #490202; color: #ff7b72; border: 1px solid #ff7b7255; }
        .tag-money { background: #033a16; color: #7ee787; border: 1px solid #7ee78755; }
        .tag-person { background: #3d1b54; color: #d2a8ff; border: 1px solid #d2a8ff55; }
        .tag-reply { background: #0c2d6b; color: #79c0ff; border: 1px solid #79c0ff55; }
        .tag-today { background: #1c2738; color: #8b9bb0; border: 1px solid #8b9bb033; }
        .tag-work { background: #26213b; color: #bc8cff; border: 1px solid #bc8cff44; }
        .source-pill {
            font-size: 11px;
            font-weight: 800;
            color: var(--accent-amber);
            flex-shrink: 0;
        }
        .item-sender {
            font-size: 13.5px;
            font-weight: 700;
            color: #ffffff;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .item-body {
            font-size: 13.5px;
            color: var(--text-primary);
            line-height: 1.45;
            word-break: break-word;
        }
        .item-borrowed {
            display: inline-block;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            font-style: italic;
        }
        .card-footer {
            padding: 13px 18px;
            background: #0d141e;
            border-top: 1px solid var(--border);
            text-align: center;
            font-size: 12.5px;
            color: var(--text-secondary);
        }
        .cut-highlight {
            color: var(--accent-amber);
            font-weight: 800;
        }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 14px 16px;
        }
        .metric-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        .metric-value {
            font-size: 22px;
            font-weight: 800;
            margin-top: 4px;
            color: #fff;
        }

        /* Tables & Discard Pile */
        .table-wrap {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            max-height: 420px;
            margin-bottom: 24px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
            min-width: 580px;
        }
        th {
            background: #0d141e;
            padding: 10px 14px;
            color: var(--text-secondary);
            font-weight: 700;
            font-size: 11.5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 2;
        }
        td {
            padding: 11px 14px;
            border-bottom: 1px solid #192333;
            color: var(--text-primary);
        }
        tr:hover td {
            background: var(--surface-hover);
        }
        .badge {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }
        .badge-tp { background: #033a16; color: #7ee787; }
        .badge-fn { background: #490202; color: #ff7b72; }
        .badge-fp { background: #452a05; color: #e3b341; }
        .badge-tn { background: #1c2736; color: #8b949e; }

        /* System Status Bar */
        .status-bar {
            margin-top: 18px;
            padding: 10px 16px;
            border-radius: var(--radius-sm);
            background: #0d141e;
            border: 1px solid var(--border);
            font-size: 11.5px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }

        /* Mobile Toast */
        #toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: #1f6feb;
            color: #fff;
            padding: 10px 20px;
            border-radius: 30px;
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 1000;
            pointer-events: none;
            white-space: nowrap;
        }
        #toast.show {
            transform: translateX(-50%) translateY(0);
        }

        /* ============================================================== */
        /* RESPONSIVE DESIGN FOR ANDROID PHONES & SMALL VIEWPORTS (<= 640px) */
        /* ============================================================== */
        @media (max-width: 640px) {
            body {
                padding: 16px 12px 40px 12px;
            }
            header {
                flex-direction: column;
                align-items: stretch;
                gap: 14px;
                margin-bottom: 14px;
                padding-bottom: 14px;
            }
            .brand h1 {
                font-size: 22px;
            }
            .brand p {
                font-size: 12px;
                max-width: 100%;
            }
            .actions {
                display: grid;
                grid-template-columns: 1fr 1fr 1.2fr;
                gap: 6px;
                width: 100%;
            }
            button {
                padding: 10px 6px;
                font-size: 12px;
                min-height: 42px;
            }
            .mobile-tabs {
                display: flex;
            }
            .card-header {
                padding: 12px 14px;
            }
            .card-header .title {
                font-size: 12px;
                letter-spacing: 1px;
            }
            .card-header .window-badge {
                font-size: 10px;
                padding: 2px 7px;
            }
            .brief-item {
                padding: 12px 14px;
            }
            .item-sender {
                font-size: 13px;
            }
            .item-body {
                font-size: 13px;
            }
            .card-footer {
                padding: 11px 14px;
                font-size: 12px;
            }
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }
            .metric-card {
                padding: 12px 14px;
            }
            .metric-value {
                font-size: 20px;
            }
            .status-bar {
                flex-direction: column;
                text-align: center;
                gap: 4px;
            }
            /* Section tab toggling */
            .tab-section {
                display: block;
            }
            .tab-section.tab-hidden-mobile {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <div class="brand-title-row">
                    <h1>Hush</h1>
                    <span class="badge-live">Local Gemma</span>
                </div>
                <p>A local attention router that reads every notification so you only have to read four.</p>
            </div>
            <div class="actions">
                <button onclick="syncNotifications()" id="btn-sync">🔄 Sync</button>
                <button onclick="runClassify()" id="btn-classify">⚡ Classify</button>
                <button class="primary" onclick="runFireDrill()" id="btn-drill">🎯 Fire Drill</button>
            </div>
        </header>

        <!-- Mobile View Switcher -->
        <div class="mobile-tabs">
            <button class="tab-btn active" onclick="switchMobileTab('brief', this)">📋 Brief</button>
            <button class="tab-btn" onclick="switchMobileTab('drill', this)">🎯 Fire Drill</button>
            <button class="tab-btn" onclick="switchMobileTab('discard', this)">🗑️ Discard Pile</button>
        </div>

        <!-- 1. The Brief Card -->
        <div id="section-brief" class="tab-section">
            <div class="section-title">The Four Lines (3-Hour Brief)</div>
            <div class="card-container" id="brief-card">
                <div class="card-header">
                    <span class="title">H U S H   B R I E F</span>
                    <span class="window-badge" id="brief-window">Loading window...</span>
                </div>
                <div id="brief-items">
                    <div style="padding: 28px; text-align: center; color: var(--text-muted); font-size: 13px;">Loading brief...</div>
                </div>
                <div class="card-footer" id="brief-footer">
                    <span class="cut-highlight">0 cut</span> · Next brief at --:--
                </div>
            </div>
        </div>

        <!-- 2. Fire Drill & Scorecard -->
        <div id="section-drill" class="tab-section tab-hidden-mobile">
            <div class="section-title">Notification Fire Drill · Ground Truth & Miss Log</div>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Emergency Recall</div>
                    <div class="metric-value" id="metric-recall" style="color: var(--accent-green);">--%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Precision</div>
                    <div class="metric-value" id="metric-precision" style="color: var(--accent-blue);">--%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Decision Latency</div>
                    <div class="metric-value" id="metric-latency">--s</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Silence Integrity</div>
                    <div class="metric-value" id="metric-silence" style="color: var(--accent-purple);">--%</div>
                </div>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Drill ID</th>
                            <th>Sender / Title</th>
                            <th>Category</th>
                            <th>Score</th>
                            <th>Decision</th>
                            <th>Verdict</th>
                            <th style="text-align: right;">Latency</th>
                        </tr>
                    </thead>
                    <tbody id="drill-tbody">
                        <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">Tap "Fire Drill" to test 10 staged emergencies against ground truth.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 3. The Discard Pile / Rejection Log -->
        <div id="section-discard" class="tab-section tab-hidden-mobile">
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
                        <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Loading discard pile...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="status-bar">
            <span>Local SQLite · 100% On-Device Gemma · Zero Cloud Egress</span>
            <span id="model-status">Cadence: 3h Durable Timer</span>
        </div>
    </div>

    <!-- Mobile Toast Notification -->
    <div id="toast">Notification synced</div>

    <script>
        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2500);
        }

        function switchMobileTab(tabKey, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');

            const sections = {
                'brief': document.getElementById('section-brief'),
                'drill': document.getElementById('section-drill'),
                'discard': document.getElementById('section-discard'),
            };

            for (const [k, sec] of Object.entries(sections)) {
                if (k === tabKey) {
                    sec.classList.remove('tab-hidden-mobile');
                } else {
                    sec.classList.add('tab-hidden-mobile');
                }
            }
        }

        async function loadBrief() {
            try {
                const res = await fetch('/api/brief');
                const data = await res.json();
                
                const startStr = data.window_start.substring(0,16).replace('T', ' ');
                const endStr = data.window_end.substring(11,16);
                document.getElementById('brief-window').innerText = `${startStr} – ${endStr}`;
                
                const container = document.getElementById('brief-items');
                if (!data.lines || data.lines.length === 0) {
                    container.innerHTML = '<div style="padding: 28px; text-align: center; color: var(--text-muted); font-size: 13px;">All clear. No notifications cleared the bar.</div>';
                } else {
                    container.innerHTML = data.lines.map(line => {
                        const tag = (line.reason_tag || 'today').toUpperCase();
                        const tagClass = 'tag-' + tag.toLowerCase();
                        const src = (line.source || 'other').toUpperCase();
                        const borrowed = line.slot_source === 'spillover' ? '<span class="item-borrowed">↳ (borrowed slot)</span>' : '';
                        return `
                            <div class="brief-item">
                                <div class="item-meta-row">
                                    <span class="tag ${tagClass}">${tag}</span>
                                    <span class="source-pill">[${src}]</span>
                                    <span class="item-sender">${escapeHtml(line.title || 'Unknown')}</span>
                                </div>
                                <div class="item-body">${escapeHtml(line.body || '')}</div>
                                ${borrowed}
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
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">No items in the discard pile.</td></tr>';
                return;
            }
            tbody.innerHTML = log.map(item => {
                const notif = item.notification;
                const time = (notif.received_at || '').substring(11, 19);
                return `
                    <tr>
                        <td style="color: var(--text-muted); font-family: monospace; font-size: 12px;">${time}</td>
                        <td style="color: var(--accent-amber); font-weight: 700;">${escapeHtml(notif.app_id || notif.source)}</td>
                        <td><strong>${escapeHtml(notif.title || '')}</strong></td>
                        <td style="color: var(--text-secondary);">${escapeHtml((notif.body || '').substring(0, 55))}</td>
                        <td style="font-family: monospace; font-weight: 600;">${Number(notif.score || 0).toFixed(2)}</td>
                        <td style="color: var(--text-muted); font-size: 12px;">${escapeHtml(item.rejection_reason || '')}</td>
                    </tr>
                `;
            }).join('');
        }

        async function syncNotifications() {
            const btn = document.getElementById('btn-sync');
            btn.disabled = true;
            btn.innerText = "⏳ Syncing...";
            try {
                const res = await fetch('/api/collect', { method: 'POST' });
                const r = await res.json();
                showToast(`Scanned ${r.scanned} records (${r.inserted} new)`);
                await loadBrief();
            } catch (e) {
                showToast("Sync failed");
            } finally {
                btn.disabled = false;
                btn.innerText = "🔄 Sync";
            }
        }

        async function runClassify() {
            const btn = document.getElementById('btn-classify');
            btn.disabled = true;
            btn.innerText = "⏳ Classifying...";
            try {
                const res = await fetch('/api/classify', { method: 'POST' });
                const r = await res.json();
                showToast(`Classified ${r.classified} notifications`);
                await loadBrief();
            } catch (e) {
                showToast("Classification error");
            } finally {
                btn.disabled = false;
                btn.innerText = "⚡ Classify";
            }
        }

        async function runFireDrill() {
            const btn = document.getElementById('btn-drill');
            btn.disabled = true;
            btn.innerText = "⏳ Running...";
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
                            <td style="color: var(--accent-blue); font-family: monospace; font-size: 12px;">${c.drill_id}</td>
                            <td><strong>${escapeHtml(c.title)}</strong></td>
                            <td style="color: var(--text-secondary);">${c.decision}</td>
                            <td style="font-family: monospace; font-weight: 600;">${Number(c.score).toFixed(2)}</td>
                            <td><strong>${c.decision.toUpperCase()}</strong></td>
                            <td><span class="badge ${badgeClass}">${c.verdict}</span></td>
                            <td style="text-align: right; font-family: monospace; font-size: 12px;">${c.latency_ms}ms</td>
                        </tr>
                    `;
                }).join('');

                showToast(`Drill complete: Recall ${(s.recall * 100).toFixed(0)}%`);
                // Switch to drill tab automatically so user sees results immediately
                switchMobileTab('drill', document.querySelectorAll('.tab-btn')[1]);
                await loadBrief();
            } catch (e) {
                showToast("Drill failed");
            } finally {
                btn.disabled = false;
                btn.innerText = "🎯 Fire Drill";
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
