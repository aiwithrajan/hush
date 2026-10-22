# Hush · 90-Second Demo Video Script

> **Challenge**: Hacktoberfest Open-Source AI Challenge, Week 3 — "Slow and Steady"  
> **Duration**: Exactly 90 Seconds  
> **Focus**: Local Gemma 2B · Temporal Durable Timers · Mobile Web UI · Falsifiable Ground Truth

---

## Shot List & Narrative Timeline

### Scene 1: The Four Lines (0:00 – 0:30)
**Visual**:
- Full-screen screen recording of macOS Terminal running `hush brief` followed by switching to the desktop browser view of `http://localhost:8484`.
- The rich terminal brief card renders in vivid colors with 4 distinct lines:
  - `[DEADLINE] [MAIL]`
  - `[MONEY   ] [MAIL]`
  - `[PERSON  ] [WA  ]`
  - `[REPLY   ] [SMS ] ↳ (borrowed slot)`
- The footer clearly shows: `46 cut · Next brief at 23:30`.
- Cursor points to the `[borrowed slot]` indicator, showing how unused email quota dynamically spills over to the next highest priority item.

**Voiceover (Audio)**:
> *"Every single notification system demands your constant attention. We built Hush to do the exact opposite.*  
> *Hush is an on-device attention router. It reads every single notification and incoming email on your machine, scores them against an inspectable deterministic cost function, and gives you exactly four lines every three hours.*  
> *Four lines. 46 distractions silenced. Zero cloud servers."*

---

### Scene 2: The Notification Fire Drill (0:30 – 1:00)
**Visual**:
- Screen switches to the terminal running `hush drill` (or clicking **"🎯 Fire Drill"** on the web UI).
- Real-time progress bar runs across 10 staged emergencies and 5 hard negative controls.
- As each item evaluates in ~2 seconds, the terminal / UI displays the verdict:
  - `[drill-health-01] City Hospital ER -> INTERRUPT (TP)`
  - `[drill-money-01] Chase Fraud Alert -> INTERRUPT (TP)`
  - `[drill-promo-01] Flash Sale 50% Off -> REJECT (TN)`
- The confusion matrix prints cleanly:
  - `Recall: 90.0%`
  - `Precision: 81.8%`
  - `Average Latency: 2.1s`
- The camera highlights the Miss Log:
  - *"We don't hide the mistakes. PagerDuty P0 was scored 0.30 because Gemma 2B categorized it as work. Falsifiable and transparent."*

**Voiceover (Audio)**:
> *"We don't ask you to trust our model on faith. We test it with a live Notification Fire Drill.*  
> *Ten staged emergencies — hospital ERs, credit card fraud, highway breakdowns — planted in the stream alongside deceptive marketing controls.*  
> *Locally on CPU with Gemma 2B, it achieved 90% emergency recall in 2.1 seconds per decision.*  
> *And where it failed on a PagerDuty ticket, the rejection log documents the exact reason why."*

---

### Scene 3: Mobile Phone View & Silence Integrity (1:00 – 1:30)
**Visual**:
- Split screen or over-the-shoulder video shot of an Android phone held in hand, connected to the same Wi-Fi network at `http://192.168.31.213:8484`.
- The phone browser displays the responsive Hush Mobile UI:
  1. User taps **`[ ⏱️ Cadence ]`**: Sets cadence to `1 Hour`. The badge confirms: *"Quiet Mode Active — 0 raw message popups"*.
  2. User taps **`[ 📱 Apps ]`**: Shows detected apps (WhatsApp, Telegram, Slack). User taps **"⭐ High"** next to Telegram.
  3. User taps **`[ 📧 Email Accounts ]`**: Taps `+ jarajan123@gmail.com` showing zero-notification direct IMAP sync.
  4. User taps **"🔔 Send Summary Notification Now"**:
     - The phone screen pops a native summary banner:
       `Hush · Quiet Summary (4 Kept)`  
       `1 WA, 2 Mail · 46 silenced during quiet window`
     - Demonstrating that NO raw personal text or OTPs leaked onto the screen.

**Voiceover (Audio)**:
> *"On your phone, Hush connects directly over your local Wi-Fi. Notifications stay completely silenced during your quiet cadence interval.*  
> *Under the hood, Temporal's durable timers survive laptop sleep, and its escalation state machine guarantees Hush never nags twice.*  
> *When your focus window ends, you get one clean summary alert.*  
> *Hush: An on-device attention router powered by Gemma and Temporal. Reclaim your focus."*

---

## Technical Checklist Before Recording

1. [x] Ollama daemon running: `http://localhost:11434` with `gemma:2b`
2. [x] Hush UI running: `http://localhost:8484` and `http://192.168.31.213:8484`
3. [x] Terminal ready with clear fonts (`hush brief`, `hush drill`)
4. [x] Android phone on Wi-Fi displaying `http://192.168.31.213:8484`
5. [x] Tested native notification sound (`Blow` on macOS / Web Notification on Android)
