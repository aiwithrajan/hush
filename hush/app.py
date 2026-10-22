import json
import sqlite3
from typing import Any, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

from hush.db import (
    get_db,
    init_db,
    get_unclassified_notifications,
    insert_judgment,
    get_setting,
    set_setting,
    get_email_accounts,
    save_email_account,
    delete_email_account,
)
from hush.collector import collect_macos_notifications
from hush.email_collector import (
    poll_all_configured_emails,
    verify_email_credentials,
    simulate_sample_emails,
)
from hush.classifier import classify_notification
from hush.router import generate_brief
from hush.drill import run_fire_drill
from hush.interrupt import handle_interrupt, deliver_summary_notification
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
            padding: 24px 16px 48px 16px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }
        .container {
            max-width: 920px;
            margin: 0 auto;
        }
        
        /* Header */
        header {
            margin-bottom: 18px;
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
            max-width: 520px;
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
        button.success {
            background: #238636;
            border-color: #2ea043;
            color: white;
        }
        button.success:hover {
            background: #2ea043;
        }

        /* Navigation Bar / Tabs */
        .tabs-nav {
            display: flex;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 4px;
            margin-bottom: 20px;
            gap: 4px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .tab-btn {
            flex: 1;
            min-width: 90px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 12.5px;
            font-weight: 600;
            padding: 9px 8px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            text-align: center;
            white-space: nowrap;
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
            margin: 20px 0 12px 0;
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

        /* Generic Panels */
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 20px;
            margin-bottom: 24px;
        }
        .panel-desc {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 16px;
            line-height: 1.5;
        }
        .alert-box {
            background: #0d1a29;
            border: 1px solid #1f4270;
            border-radius: var(--radius-md);
            padding: 14px 16px;
            font-size: 13px;
            color: #b3d1ff;
            margin-bottom: 16px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
            line-height: 1.45;
        }
        .alert-box.success {
            background: #052613;
            border-color: #176332;
            color: #85e89d;
        }

        /* Cadence Controls */
        .preset-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            gap: 10px;
            margin-bottom: 16px;
        }
        .preset-btn {
            background: var(--surface-card);
            border: 1px solid var(--border);
            padding: 12px 10px;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 700;
            color: var(--text-primary);
            text-align: center;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .preset-btn:hover {
            border-color: var(--accent-blue);
            background: var(--surface-hover);
        }
        .preset-btn.active {
            background: #102a45;
            border-color: var(--accent-blue);
            color: #79c0ff;
            box-shadow: 0 0 10px rgba(88, 166, 255, 0.2);
        }
        .quiet-indicator {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #08121f;
            border: 1px solid #1b3a5b;
            border-radius: var(--radius-md);
            padding: 14px 18px;
            margin-top: 14px;
            flex-wrap: wrap;
            gap: 12px;
        }
        .quiet-status-text {
            font-size: 13px;
            font-weight: 600;
            color: #79c0ff;
        }

        /* Forms */
        .form-row {
            display: flex;
            gap: 10px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }
        .form-group {
            flex: 1;
            min-width: 220px;
        }
        .form-group label {
            display: block;
            font-size: 11.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }
        input, select {
            width: 100%;
            background: #0d141e;
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 10px 12px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            outline: none;
            transition: border 0.15s ease;
        }
        input:focus, select:focus {
            border-color: var(--accent-blue);
        }
        .chips-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 14px;
            flex-wrap: wrap;
        }
        .chip {
            background: #172233;
            border: 1px solid #283c56;
            color: #79c0ff;
            font-size: 12px;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 14px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .chip:hover {
            background: #20334d;
            border-color: var(--accent-blue);
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

        /* Tables */
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
        .badge-active { background: #033a16; color: #7ee787; border: 1px solid #7ee78744; }

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

        /* Tab sections */
        .tab-section {
            display: block;
        }
        .tab-hidden {
            display: none;
        }

        /* Mobile Adjustments */
        @media (max-width: 640px) {
            body {
                padding: 14px 10px 48px 10px;
            }
            header {
                flex-direction: column;
                align-items: stretch;
                gap: 12px;
            }
            .brand h1 {
                font-size: 22px;
            }
            .actions {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 6px;
            }
            button {
                padding: 10px 6px;
                font-size: 12px;
                min-height: 42px;
            }
            .preset-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .status-bar {
                flex-direction: column;
                text-align: center;
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
                <p>A local attention router that reads every notification and email so you only have to read four.</p>
            </div>
            <div class="actions">
                <button onclick="syncAll()" id="btn-sync">🔄 Sync</button>
                <button onclick="runClassify()" id="btn-classify">⚡ Classify</button>
                <button class="primary" onclick="runFireDrill()" id="btn-drill">🎯 Fire Drill</button>
            </div>
        </header>

        <!-- Navigation Tabs -->
        <nav class="tabs-nav">
            <button class="tab-btn active" onclick="switchTab('brief', this)">📋 Brief</button>
            <button class="tab-btn" onclick="switchTab('cadence', this)">⏱️ Cadence</button>
            <button class="tab-btn" onclick="switchTab('email', this)">📧 Email Accounts</button>
            <button class="tab-btn" onclick="switchTab('drill', this)">🎯 Fire Drill</button>
            <button class="tab-btn" onclick="switchTab('discard', this)">🗑️ Discard Pile</button>
        </nav>

        <!-- TAB 1: THE BRIEF -->
        <div id="section-brief" class="tab-section">
            <div class="section-title">The Four Lines (Attention Brief)</div>
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

        <!-- TAB 2: CADENCE & NOTIFICATION SETTER -->
        <div id="section-cadence" class="tab-section tab-hidden">
            <div class="section-title">Cadence & Quiet Window Controls</div>
            <div class="panel">
                <div class="alert-box">
                    <span>🤫</span>
                    <div>
                        <strong>Quiet Window Integrity:</strong>
                        All incoming raw notifications and emails remain <strong>completely silent</strong> during this interval.
                        No raw message alerts pop up. Only a single 4-line summary notification is delivered at the end of the window.
                    </div>
                </div>

                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px;">
                    Select Summary Cadence Interval
                </div>

                <div class="preset-grid">
                    <button class="preset-btn" onclick="setCadence(15, this)">⏱️ 15 Mins<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Quick Test)</span></button>
                    <button class="preset-btn" onclick="setCadence(30, this)">⏱️ 30 Mins<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Fast Sync)</span></button>
                    <button class="preset-btn" onclick="setCadence(60, this)">⏱️ 1 Hour<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Work Mode)</span></button>
                    <button class="preset-btn" onclick="setCadence(120, this)">⏱️ 2 Hours<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Deep Flow)</span></button>
                    <button class="preset-btn active" id="btn-cadence-180" onclick="setCadence(180, this)">⏱️ 3 Hours<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Hush Default)</span></button>
                    <button class="preset-btn" onclick="setCadence(240, this)">⏱️ 4 Hours<br><span style="font-size:11px;font-weight:400;color:var(--text-muted);">(Long Focus)</span></button>
                </div>

                <div class="quiet-indicator">
                    <div>
                        <div class="quiet-status-text" id="cadence-status-text">Active Cadence: Every 3 Hours (180 mins)</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                            Next summary scheduled for: <strong id="next-summary-label" style="color: #fff;">--:--</strong>
                        </div>
                    </div>
                    <button class="primary" onclick="triggerSummaryNotification()">
                        🔔 Send Summary Notification Now
                    </button>
                </div>
            </div>
        </div>

        <!-- TAB 3: EMAIL ACCOUNTS -->
        <div id="section-email" class="tab-section tab-hidden">
            <div class="section-title">Direct Mail Ingestion (Zero-Notification Setup)</div>
            <div class="panel">
                <div class="panel-desc">
                    Since email notifications stay off on your phone/laptop, Hush directly polls unread messages via secure IMAP SSL and assigns them to the <strong>2 reserved Email slots</strong> in the 4-line brief.
                </div>

                <div class="chips-row">
                    <span style="font-size: 12px; color: var(--text-secondary); font-weight: 600;">Quick Presets:</span>
                    <button class="chip" onclick="fillEmailPreset('jarajan123@gmail.com')">+ jarajan123@gmail.com</button>
                    <button class="chip" onclick="fillEmailPreset('imrajan098@gmail.com')">+ imrajan098@gmail.com</button>
                </div>

                <div class="form-row">
                    <div class="form-group" style="flex: 1.5;">
                        <label>Email Address</label>
                        <input type="email" id="email-input" placeholder="e.g. jarajan123@gmail.com">
                    </div>
                    <div class="form-group">
                        <label>IMAP Host</label>
                        <input type="text" id="host-input" value="imap.gmail.com">
                    </div>
                    <div class="form-group">
                        <label>Google App Password / Token</label>
                        <input type="password" id="pass-input" placeholder="16-character App Password">
                    </div>
                </div>

                <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px;">
                    <button class="success" onclick="saveEmailAccount()">💾 Connect & Save Account</button>
                    <button onclick="injectSimulatedEmail()">🧪 Inject Test Emails (jarajan123 / imrajan098)</button>
                    <button onclick="syncAllEmails()">🔄 Sync All Mailboxes</button>
                </div>

                <div style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4; background: #0c1521; padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border);">
                    💡 <strong>Tip for Gmail:</strong> Go to <em>Google Account &rarr; Security &rarr; 2-Step Verification &rarr; App Passwords</em> to generate a 16-character password. You can also tap "Inject Test Emails" to test immediately without setting a password.
                </div>
            </div>

            <div class="section-title">Connected Mailboxes</div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Account</th>
                            <th>Host</th>
                            <th>Status</th>
                            <th>Last Polled</th>
                            <th>Last Status</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody id="email-accounts-tbody">
                        <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">No mailboxes added yet.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 4: FIRE DRILL -->
        <div id="section-drill" class="tab-section tab-hidden">
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

        <!-- TAB 5: DISCARD PILE -->
        <div id="section-discard" class="tab-section tab-hidden">
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
        let currentCadenceMins = 180;

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2600);
        }

        function switchTab(tabKey, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');

            const sections = {
                'brief': document.getElementById('section-brief'),
                'cadence': document.getElementById('section-cadence'),
                'email': document.getElementById('section-email'),
                'drill': document.getElementById('section-drill'),
                'discard': document.getElementById('section-discard'),
            };

            for (const [k, sec] of Object.entries(sections)) {
                if (k === tabKey) {
                    sec.classList.remove('tab-hidden');
                } else {
                    sec.classList.add('tab-hidden');
                }
            }

            if (tabKey === 'email') loadEmailAccounts();
            if (tabKey === 'cadence') loadSettings();
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

                document.getElementById('next-summary-label').innerText = data.next_brief_time || '--:--';

                if (data.cadence_minutes) {
                    currentCadenceMins = data.cadence_minutes;
                    updateCadenceUI(currentCadenceMins);
                }

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

        async function syncAll() {
            const btn = document.getElementById('btn-sync');
            btn.disabled = true;
            btn.innerText = "⏳ Syncing...";
            try {
                const res = await fetch('/api/collect', { method: 'POST' });
                const r = await res.json();
                showToast(`Scanned ${r.scanned} records (${r.inserted} new)`);
                await loadBrief();
                if (r.inserted > 0) {
                    await runClassify();
                }
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
                switchTab('drill', document.querySelectorAll('.tab-btn')[3]);
                await loadBrief();
            } catch (e) {
                showToast("Drill failed");
            } finally {
                btn.disabled = false;
                btn.innerText = "🎯 Fire Drill";
            }
        }

        /* Cadence Controls */
        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                if (data.cadence_minutes) {
                    currentCadenceMins = data.cadence_minutes;
                    updateCadenceUI(currentCadenceMins);
                }
            } catch (e) {
                console.error("Failed to load settings", e);
            }
        }

        function updateCadenceUI(mins) {
            document.querySelectorAll('.preset-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            const text = mins >= 60 ? `${(mins / 60).toFixed(mins % 60 ? 1 : 0)} Hour(s)` : `${mins} Minutes`;
            document.getElementById('cadence-status-text').innerText = `Active Cadence: Every ${text} (${mins} mins)`;
            document.getElementById('model-status').innerText = `Cadence: ${text} Durable Timer`;
        }

        async function setCadence(mins, btn) {
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cadence_minutes: mins })
                });
                const data = await res.json();
                currentCadenceMins = mins;
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                if (btn) btn.classList.add('active');
                updateCadenceUI(mins);
                showToast(`Cadence updated to ${mins} mins`);
                await loadBrief();
            } catch (e) {
                showToast("Failed to update cadence");
            }
        }

        async function triggerSummaryNotification() {
            // Request browser notification permission if available
            if ("Notification" in window && Notification.permission !== "granted") {
                await Notification.requestPermission();
            }

            try {
                const res = await fetch('/api/notify-summary', { method: 'POST' });
                const r = await res.json();
                
                if ("Notification" in window && Notification.permission === "granted") {
                    new Notification(r.title, {
                        body: `${r.subtitle}\\n${r.body}`,
                        icon: "https://fav.farm/🤫"
                    });
                }
                showToast(`Summary notification sent! (0 raw alerts leaked)`);
            } catch (e) {
                showToast("Failed to send summary");
            }
        }

        /* Email Accounts Handling */
        function fillEmailPreset(email) {
            document.getElementById('email-input').value = email;
            document.getElementById('host-input').value = 'imap.gmail.com';
            showToast(`Filled ${email}`);
        }

        async function loadEmailAccounts() {
            try {
                const res = await fetch('/api/emails');
                const data = await res.json();
                const tbody = document.getElementById('email-accounts-tbody');
                
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">No mailboxes configured yet. Add jarajan123@gmail.com or imrajan098@gmail.com above!</td></tr>';
                    return;
                }

                tbody.innerHTML = data.map(acc => {
                    const statusText = acc.last_error ? `<span style="color: var(--accent-red);">${escapeHtml(acc.last_error)}</span>` : `<span style="color: var(--accent-green);">OK · Connected</span>`;
                    const polled = acc.last_polled_at ? acc.last_polled_at.substring(11, 19) : 'Never';
                    return `
                        <tr>
                            <td><strong>${escapeHtml(acc.email)}</strong></td>
                            <td style="color: var(--text-secondary); font-family: monospace;">${escapeHtml(acc.host)}:${acc.port}</td>
                            <td><span class="badge badge-active">Active</span></td>
                            <td style="font-family: monospace; font-size: 12px; color: var(--text-muted);">${polled}</td>
                            <td style="font-size: 12px;">${statusText}</td>
                            <td style="text-align: right;">
                                <button onclick="deleteEmailAccount('${escapeHtml(acc.email)}')" style="padding: 4px 10px; font-size: 11px; color: var(--accent-red); border-color: #490202;">Delete</button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (e) {
                console.error("Failed to load accounts", e);
            }
        }

        async function saveEmailAccount() {
            const email = document.getElementById('email-input').value.trim();
            const host = document.getElementById('host-input').value.trim() || 'imap.gmail.com';
            const pass = document.getElementById('pass-input').value.trim();

            if (!email) {
                showToast("Please enter an email address");
                return;
            }

            try {
                showToast("Verifying & saving account...");
                const res = await fetch('/api/emails/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, host, password: pass })
                });
                const r = await res.json();
                if (r.success) {
                    showToast("Mailbox added successfully!");
                    document.getElementById('pass-input').value = "";
                    await loadEmailAccounts();
                    await syncAll();
                } else {
                    showToast(r.message || "Failed to add mailbox");
                }
            } catch (e) {
                showToast("Error saving mailbox");
            }
        }

        async function deleteEmailAccount(email) {
            if (!confirm(`Delete mailbox ${email}?`)) return;
            try {
                await fetch('/api/emails/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                showToast("Account removed");
                await loadEmailAccounts();
            } catch (e) {
                showToast("Failed to delete account");
            }
        }

        async function injectSimulatedEmail() {
            const email = document.getElementById('email-input').value.trim() || 'jarajan123@gmail.com';
            showToast(`Injecting sample emails for ${email}...`);
            try {
                const res = await fetch('/api/emails/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                const r = await res.json();
                showToast(`Injected ${r.inserted} emails! Classifying...`);
                await runClassify();
                await loadBrief();
                switchTab('brief', document.querySelectorAll('.tab-btn')[0]);
            } catch (e) {
                showToast("Failed to inject test emails");
            }
        }

        async function syncAllEmails() {
            showToast("Polling configured mailboxes...");
            try {
                const res = await fetch('/api/emails/sync', { method: 'POST' });
                const r = await res.json();
                showToast(`Scanned ${r.scanned} emails (${r.inserted} new)`);
                await loadEmailAccounts();
                if (r.inserted > 0) {
                    await runClassify();
                }
                await loadBrief();
            } catch (e) {
                showToast("Sync mailboxes failed");
            }
        }

        function escapeHtml(str) {
            return (str || '').replace(/[&<>"']/g, function(m) {
                return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[m];
            });
        }

        window.onload = () => {
            loadBrief();
            loadSettings();
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

    def _read_json(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            try:
                return json.loads(raw_body)
            except Exception:
                return {}
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(HTML_PAGE)
        elif path == "/api/brief":
            with get_db() as conn:
                brief_data = generate_brief(conn)
                self._send_json(brief_data)
        elif path == "/api/settings":
            with get_db() as conn:
                mins_str = get_setting(conn, "cadence_minutes", "180")
                self._send_json({"cadence_minutes": int(mins_str)})
        elif path == "/api/emails":
            with get_db() as conn:
                accounts = get_email_accounts(conn)
                self._send_json(accounts)
        elif path == "/api/drill":
            with get_db() as conn:
                drill_data = run_fire_drill(conn, verbose=False)
                self._send_json(drill_data)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/collect":
            with get_db() as conn:
                mac_stats = collect_macos_notifications(dest_conn=conn)
                email_stats = poll_all_configured_emails(dest_conn=conn)
                total_stats = {
                    "scanned": mac_stats["scanned"] + email_stats["scanned"],
                    "inserted": mac_stats["inserted"] + email_stats["inserted"],
                    "duplicates": mac_stats["duplicates"] + email_stats["duplicates"],
                    "errors": mac_stats["errors"] + email_stats["errors"],
                }
                self._send_json(total_stats)

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

        elif path == "/api/settings":
            new_mins = body.get("cadence_minutes", 180)
            with get_db() as conn:
                set_setting(conn, "cadence_minutes", str(new_mins))
                self._send_json({"success": True, "cadence_minutes": int(new_mins)})

        elif path == "/api/emails/save":
            email_addr = body.get("email", "").strip()
            password = body.get("password", "").strip()
            host = body.get("host", "imap.gmail.com").strip()
            port = int(body.get("port", 993))
            label = body.get("label", email_addr.split("@")[0] if "@" in email_addr else "Mail")

            if not email_addr:
                self._send_json({"success": False, "message": "Email is required"}, 400)
                return

            with get_db() as conn:
                save_email_account(conn, email_addr, password, host, port, label)
                self._send_json({"success": True, "message": "Account saved successfully"})

        elif path == "/api/emails/delete":
            email_addr = body.get("email", "")
            with get_db() as conn:
                delete_email_account(conn, email_addr)
                self._send_json({"success": True})

        elif path == "/api/emails/sync":
            with get_db() as conn:
                stats = poll_all_configured_emails(dest_conn=conn)
                self._send_json(stats)

        elif path == "/api/emails/simulate":
            email_addr = body.get("email") or "jarajan123@gmail.com"
            with get_db() as conn:
                inserted = simulate_sample_emails(conn, email_addr)
                self._send_json({"success": True, "inserted": len(inserted)})

        elif path == "/api/notify-summary":
            with get_db() as conn:
                brief = generate_brief(conn)
                notif_info = deliver_summary_notification(brief)
                self._send_json(notif_info)

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
