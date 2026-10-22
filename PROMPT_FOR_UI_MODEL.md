# Master UI Generation Prompt for "Hush"

> **How to use this prompt**: Copy and paste the entire prompt below into **Claude 3.5 Sonnet**, **v0.dev**, **Bolt.new**, **Cursor**, or **ChatGPT (GPT-4o)** to generate a dedicated, production-grade frontend UI (Next.js / React / Tailwind or Vue / Svelte / Mobile) for Hush.

---

```markdown
You are an elite principal product designer and senior frontend engineer.

Your task is to build a hyper-polished, responsive web and mobile application dashboard for **HUSH** — an on-device local AI attention router.

### 1. What is Hush? (Product Context)
Hush reads every incoming notification and email on the user's devices (macOS & Android) and filters the torrent of noise down to a **fixed 4-line brief delivered once every 3 hours** (configurable). It interrupts the user only for genuine life/financial/safety emergencies ($score \ge 0.55$). 
Hush is powered by an on-device **Gemma 2B** model running locally via Ollama with zero cloud egress, and orchestrated using **Temporal** durable workflows.

---

### 2. Design System & Aesthetics
- **Theme**: Ultra-clean Cyber-Minimalist Dark Mode (inspired by Linear, GitHub Dark Dimmed, and Apple Human Interface Guidelines).
- **Color Palette**:
  - Background: `#090d16` (Deep Obsidian)
  - Surface Container: `#121824`
  - Card / Panel: `#162030`
  - Borders: `#223247` (Hover: `#2c415c`)
  - Accent Primary: `#58a6ff` (Electric Blue)
  - Accent Alert / Emergency: `#ff7b72` (Soft Crimson)
  - Accent Success / Active: `#3fb950` (Emerald Green)
  - Accent Warning / Spillover: `#e3b341` (Amber)
  - Accent Purple (Person / Family): `#d2a8ff`
- **Typography**: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif`. Monospace for timestamps, IDs, and scores.
- **Mobile First**: 100% responsive, optimized for handheld mobile phone viewports (360px – 430px) and desktop (900px+). Minimum touch tap target 44px.

---

### 3. Live Backend API Specification (Base URL: `http://localhost:8484` or `http://<LAN_IP>:8484`)

The frontend will talk to a live Python HTTP REST backend with these exact endpoints:

#### A. Master Power & Status
- **`GET /api/status`**
  - Response: `{"status": "active" | "paused", "is_active": true | false}`
- **`POST /api/status`**
  - Request: `{"active": true | false}`
  - Response: `{"success": true, "status": "active" | "paused", "is_active": true | false}`

#### B. Cadence Settings
- **`GET /api/settings`**
  - Response: `{"cadence_minutes": 180}`
- **`POST /api/settings`**
  - Request: `{"cadence_minutes": 60}`
  - Response: `{"success": true, "cadence_minutes": 60}`

#### C. The 4-Line Brief & Discard Pile
- **`GET /api/brief`**
  - Response Schema:
    ```json
    {
      "brief_id": 18,
      "window_start": "2026-10-22T17:30:00+05:30",
      "window_end": "2026-10-22T20:30:00+05:30",
      "cadence_minutes": 180,
      "next_brief_time": "23:30",
      "total_evaluated": 50,
      "kept_count": 4,
      "cut_count": 46,
      "lines": [
        {
          "id": "hash-id",
          "source": "mail" | "wa" | "sms" | "telegram" | "slack" | "facebook" | "snapchat" | "other",
          "app_id": "com.apple.mail",
          "title": "Sender / Sender Title",
          "body": "Notification text snippet...",
          "received_at": "2026-10-22T19:42:00+05:30",
          "urgency": 0.95,
          "category": "health" | "money" | "person" | "deadline" | "work" | "promo",
          "score": 0.855,
          "reason": "Why it cleared the threshold",
          "reason_tag": "deadline" | "money" | "person" | "reply" | "today",
          "slot_source": "mail" | "wa" | "sms" | "spillover"
        }
      ],
      "borrowed": [
        {"item_id": "hash-id", "item_source": "other", "score": 0.95}
      ],
      "rejected_log": [
        {
          "notification": {
            "id": "hash",
            "app_id": "net.whatsapp.whatsapp",
            "source": "wa",
            "title": "Group Chat",
            "body": "Hey guys look at this meme",
            "score": 0.04,
            "received_at": "2026-10-22T19:10:00+05:30"
          },
          "rejection_reason": "Score 0.04 below brief threshold T_brief (0.15)"
        }
      ]
    }
    ```

#### D. Sync & Classify Actions
- **`POST /api/collect`**: Scans macOS usernoted DB and IMAP mailboxes.
  - Response: `{"scanned": 86, "inserted": 4, "duplicates": 82, "errors": 0}`
- **`POST /api/classify`**: Runs Gemma 2B inference on unclassified notifications.
  - Response: `{"classified": 4}`

#### E. App Detection, Custom Routing & Testing
- **`GET /api/apps`**
  - Response:
    ```json
    {
      "detected": [
        {"app_id": "org.telegram.desktop", "display_name": "Telegram", "source": "telegram", "priority": "priority" | "normal" | "muted", "notif_count": 45, "last_seen": "ISO"}
      ],
      "rules": [
        {"app_id": "org.telegram.desktop", "name": "Telegram", "source": "telegram", "priority": "priority"}
      ]
    }
    ```
- **`POST /api/apps/save`**: Saves app rule.
  - Request: `{"app_id": "org.telegram.desktop", "name": "Telegram", "source": "telegram", "priority": "priority"}`
- **`POST /api/apps/delete`**: Deletes app rule.
  - Request: `{"app_id": "org.telegram.desktop"}`
- **`POST /api/apps/test-notify`**: Tests Gemma 2B categorization of any notification.
  - Request: `{"app_id": "com.toyopagroup.picaboo", "title": "Rahul on Snapchat", "body": "Emergency accident on Highway 101"}`
  - Response: `{"success": true, "judgment": {"score": 0.95, "category": "health", "urgency": 0.95}}`

#### F. Email IMAP Accounts (Zero-Notification Setup)
- **`GET /api/emails`**
  - Response: `[{"email": "jarajan123@gmail.com", "host": "imap.gmail.com", "port": 993, "label": "jarajan123", "is_active": 1, "last_polled_at": "ISO", "last_error": null, "has_password": true}]`
- **`POST /api/emails/save`**: `{"email": "...", "host": "imap.gmail.com", "password": "...", "port": 993}`
- **`POST /api/emails/delete`**: `{"email": "..."}`
- **`POST /api/emails/sync`**: Triggers immediate IMAP fetch.
- **`POST /api/emails/simulate`**: Injects test emails for immediate demo.
  - Request: `{"email": "jarajan123@gmail.com"}`

#### G. Cadence Summary Push Alert
- **`POST /api/notify-summary`**: Triggers OS push alert without leaking raw message bodies.
  - Response: `{"title": "Hush · Quiet Summary (4 Kept)", "subtitle": "2 Mail, 1 WA, 1 SMS · 46 silenced", "body": "Cadence window reached."}`

#### H. Fire Drill & Scorecard
- **`POST /api/drill`**: Evaluates 10 staged emergencies against ground truth.
  - Response:
    ```json
    {
      "summary": {
        "total_emergencies_planted": 10,
        "total_controls_planted": 5,
        "tp": 9, "fn": 1, "fp": 2, "tn": 3,
        "recall": 0.90, "precision": 0.818,
        "avg_latency_sec": 2.1,
        "silence_integrity_pct": 60.0
      },
      "cases": [
        {"drill_id": "drill-health-01", "title": "City Hospital ER", "score": 0.95, "decision": "interrupt", "verdict": "TP", "latency_ms": 2100}
      ]
    }
    ```

---

### 4. Required UI Components & Tabs

1. **Header**:
   - Brand Title `HUSH` + Subtitle *"Local Attention Router"*.
   - **Master Power Switch (`STATUS: [ON / OFF]`)**:
     - Toggle switch with instant visual feedback.
     - When `OFF`, show a persistent amber warning banner: *"Hush is PAUSED — Standard notifications flowing without quiet filtering."*
   - Global Action Buttons: `🔄 Sync`, `⚡ Classify`, `🎯 Fire Drill`.

2. **Navigation Tabs**:
   - `📋 The Brief` (Home)
   - `⏱️ Cadence` (Quiet Window Controls)
   - `📱 Apps & Channels` (Detected Apps, Presets, Priority Rules)
   - `📧 Email Accounts` (Zero-Notification IMAP Setup)
   - `🎯 Fire Drill` (Ground Truth Evaluation Matrix)
   - `🗑️ Discard Pile` (Audit Rejection Log)

3. **Tab 1: The Four Lines (The Brief Card)**:
   - Header: `H U S H   B R I E F` with live window bounds (`start – end`).
   - Up to 4 rows. Each row displays:
     - Reason Tag Badge: `[DEADLINE]` (red), `[MONEY]` (green), `[PERSON]` (purple), `[REPLY]` (blue), `[TODAY]` (gray).
     - Source Pill: `[MAIL]`, `[WA]`, `[SMS]`, `[TELEGRAM]`, `[SLACK]`, `[FACEBOOK]`, `[SNAPCHAT]`.
     - Sender / Title (bold white).
     - Body snippet (clean text).
     - Spillover footnote if applicable: `↳ (borrowed slot)` in italic amber.
   - Footer: Highlighted cut count (e.g. `46 cut`) and countdown to `Next brief at HH:MM`.

4. **Tab 2: Cadence & Quiet Window Controls**:
   - Silence Integrity Alert Box: Explaining that during the quiet interval, NO raw notifications pop up; only the summary alert is delivered.
   - Interval Selector Buttons: `15 Mins (Quick Test)`, `30 Mins`, `1 Hour`, `2 Hours`, `3 Hours (Default)`, `4 Hours`. Active selection is highlighted with glowing border.
   - Button: `🔔 Send Summary Notification Now` (supports HTML5 Web Notification API + backend notification).

5. **Tab 3: Apps & Channels**:
   - Quick App Preset Chips: `[+ Facebook]`, `[+ Snapchat]`, `[+ Telegram]`, `[+ Slack]`, `[+ Discord]`, `[+ Teams]`, `[+ Signal]`, `[+ Calendar]`. Clicking any chip populates the rule form.
   - Priority Selector: `⭐ Priority` (high consequence), `🔔 Normal`, `🔇 Muted` (silence always).
   - Live Test Route Sandbox: Allows user to test custom notification text through Gemma 2B and see instant scoring.
   - Detected Apps Table: Shows all detected apps on the device, notification counters, and quick priority toggles.

6. **Tab 4: Email Accounts (Zero-Notification Setup)**:
   - Presets: `[+ jarajan123@gmail.com]` and `[+ imrajan098@gmail.com]`.
   - IMAP setup form (Email, Host, App Password).
   - "Test Without Password" button: `🧪 Inject Sample Emails` (instantly seeds realistic emails into DB for demo).
   - Table of active mailboxes with status indicators.

7. **Tab 5: Fire Drill & Scorecard**:
   - 4-Stat Metric Cards: `Emergency Recall (%)`, `Precision (%)`, `Decision Latency (s)`, `Silence Integrity (%)`.
   - Staged Cases Table: Drill ID, Sender, Category, Score, Decision (`INTERRUPT` vs `BRIEF`), Verdict (`TP`, `FN`, `FP`, `TN`), Latency (ms).

8. **Tab 6: Discard Pile (Rejection Log)**:
   - Transparent table auditing every single silenced notification with received timestamp, app ID, sender, message excerpt, numerical score, and explicit rejection rationale (e.g. *"Thread collapsed"*, *"Below threshold 0.15"*, *"Exceeded brief quota"*).

---

### 5. Implementation Deliverable
Write clean, modular, production-ready code with full error handling, loading states, and toast notifications. Ensure the UI can connect directly to the existing Python backend over `fetch()` or `axios`.
```
