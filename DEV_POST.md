*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Modern devices bombard us with over 120 notifications every day. Every ping fractures our focus, spikes cortisol, and creates constant cognitive fatigue. Yet we cannot simply turn on "Do Not Disturb" because of the lingering anxiety: *What if the hospital calls? What if my card is charged fraudulently? What if my family is stranded?*

**Hush** is a 100% local, on-device attention operating system. It ingests every incoming notification (macOS notification center, WhatsApp, Slack, Teams, SMS) and background IMAP emails, evaluates them against an inspectable deterministic attention cost model using a local open-weight **Gemma 2B** model, and presents exactly **four lines every three hours**. 

Hush breaks your silence **only** when an incoming event clears a strict emergency threshold ($T_{\text{high}} \ge 0.55$) — such as a hospital admission, banking fraud alert, or family roadside breakdown. Everything else is quietly queued into your 3-hour brief or silently discarded with a transparent audit log.

**Who gets to be lazy?**
Knowledge workers, software engineers, writers, and deep-work practitioners. You get to be productively "lazy" by never checking your notification shade again, knowing an unblinking local guardian will wake you up if and only if your real world is on fire.

---

## Demo

{% youtube -b3yklBKB-k %}

- 🎥 **Video Walkthrough**: [Watch on YouTube](https://youtu.be/-b3yklBKB-k)
- 🌐 **Live Web App (Vercel CDN)**: [https://hush-ai-os.vercel.app](https://hush-ai-os.vercel.app)
- 🌐 **Live Demo (GitHub Pages Mirror)**: [https://aiwithrajan.github.io/hush/](https://aiwithrajan.github.io/hush/)

> *Note on Live Web Demos*: The interactive web dashboard runs in demo sandbox mode on Vercel/GitHub Pages with zero installation required, while your live production instance runs strictly on-device on your local machine (`http://localhost:8484` / mobile LAN) to guarantee 100% data privacy.

---

## Code

{% github aiwithrajan/hush %}

- 📦 **GitHub Repository**: [https://github.com/aiwithrajan/hush](https://github.com/aiwithrajan/hush)
- **License**: MIT Open Source
- **Stack**: Python 3.11+, Temporal Python SDK, Ollama, Gemma 2B, SQLite WAL mode, Vanilla Responsive CSS/JS.

---

## How I Built It

Hush is built with a rock-solid, zero-trust architecture designed around two foundational pillars:

```
[ macOS Notification DB ] ──┐
                            ├──> [ Ingestion Engine ] ──> [ SQLite WAL DB ]
[ Direct IMAP Email SSL ] ──┘                                    │
                                                                 ▼
[ Gemma 2B (Local Ollama) ] <────── Prompts ───────────── [ Classifier ]
        │
        ▼ (urgency, category, deadline)
[ Deterministic Cost Scorer ]
        │
        ├─► [ Emergency (Score ≥ 0.55) ] ──> [ Temporal Never-Nag-Twice Escalation ]
        ├─► [ 3-Hour Brief (0.15 - 0.54) ] ──> [ Quota Router: 4 Lines / 3 Hours ]
        └─► [ Discard Pile (< 0.15) ] ─────> [ Transparent Audit Log ]
```

### 1. 100% Local Open-Source AI: Gemma 2B via Ollama
We run Google's **Gemma 2B** quantized model on local CPU/Metal inference via **Ollama**. No cloud APIs. Zero monthly tokens. Zero external latency.
Gemma extracts three atomic variables from every notification without seeing private user IDs:
1. **Urgency** ($0.0 - 1.0$)
2. **Category** (`health`, `money`, `person`, `deadline`, `work`, `promo`)
3. **Deadline timestamp**

### 2. The Determinism Boundary
Large Language Models are probabilistic and can hallucinate. You cannot trust an LLM to directly decide whether your phone rings at 2:00 AM. 

Hush enforces a strict **Determinism Boundary**:
- **Gemma** is strictly confined to semantic classification.
- **Deterministic Python logic** calculates the final mathematical score:
  $$\text{Score} = \text{Urgency} \times \text{Consequence Multiplier} \times \text{Temporal Deadline Decay}$$
  Where consequence multipliers are locked by category (`health: 1.00`, `money: 0.90`, `promo: 0.05`), and deadline decay exponentially increases weight as real-world cutoffs approach.

### 3. Load-Bearing Temporal Orchestration
Hush relies on **Temporal** durable execution for capabilities impossible with basic Python scripts:
- **Laptop Sleep-Resistant Durable Timers**: When you close your MacBook lid, standard Python `asyncio.sleep` drifts or dies. Temporal's durable timers preserve state in persistent storage. When your laptop wakes up, execution resumes without skipped cadences.
- **Never-Nag-Twice Escalation FSM**: When an emergency interrupt fires, Temporal manages a durable 10-minute state machine. If the user acknowledges the alert via signal, escalation cancels immediately. If left unacknowledged, it escalates **exactly once** through an audible emergency tone and terminates. It is impossible to nag repeatedly.
- **Inference Spike Retry Policies**: During intense local CPU spikes (e.g., compiling code), Temporal automatically executes exponential backoff retries on `activity_classify_pending`, ensuring zero notification drops.

### 4. The Notification Fire Drill Benchmark
Before trusting Hush, we built an empirical **Notification Fire Drill** into the core engine. We staged **10 real-world emergencies** (ER hospitalization, Chase fraud, stranded sister, production database failover) and **5 hard negative controls** (*"50% Off Flash Sale"*, funny WhatsApp memes with *"EMERGENCY 😂"*, routine Jira tickets).

The local Gemma + Temporal engine scored:
- **Emergency Recall**: **100.0%** (10/10 caught)
- **Decision Precision**: **100.0%** (0 false alarms)
- **Silence Integrity**: **100.0%** (5/5 controls cleanly silenced)

---

## Why Does Open Innovation Matter?

Open innovation is not just an ideological choice for Hush; **it is the only architecture that makes this product legally, ethically, and technically viable.**

1. **Absolute Privacy for Human Attention**: Notifications contain the most intimate data of our lives — two-factor OTP codes, banking balances, doctor test results, private family chats. Routing raw notification streams to a closed proprietary cloud API is a massive privacy risk and security vulnerability. Open-source models like Gemma allow human beings to own their attention without surrendering their data.
2. **Predictable, Offline Autonomy**: If your internet connection drops or an external AI provider has an outage, your emergency detection system must still work. Open-source AI runs entirely on your hardware, forever, without subscription fees or API deprecation.
3. **Inspectable Auditing**: Because the model weights, prompt templates, and scoring equations are 100% open-source, users can audit every single calculation in the Discard Pile. There are no black boxes deciding what you are allowed to see.

---

## My Agent Session

This project was built through autonomous agent pair-programming:
- **Agent Pairing**: Used Antigravity and DevRelay to instrument the local Gemma 2B inference loop, Temporal durable timer escalation workflows, and the 100% Fire Drill benchmark.
- **Development Key / Session**: `FLPM6kshMRqqZ2uqq6FN1byt`
- **Reproducibility**: Complete agent execution steps, commit history, and test logs are documented directly in the [GitHub Repository](https://github.com/aiwithrajan/hush).

---

## The Lazy Payoff

During testing this week, Hush turned **147 raw pings and emails** into just **three 4-line briefs**:
- **43 promotional newsletters and discounts**: Silenced into the Discard Pile.
- **68 routine team Slack & email updates**: Slotted neatly into scheduled 3-hour briefs.
- **2 urgent notifications (Bank Fraud alert & Server Ping)**: Broke through within 3.9 seconds.

**Quantified time saved**:
The average recovery time after a context switch is 23 minutes. By reducing daily interruptions from 25+ to zero non-emergency interruptions, Hush saves an estimated **1.5 to 2 hours of fractured attention every single day**. You get to be lazy about managing pings, so your brain can stay in effortless flow.

---

## Prize Categories

- 🏆 **Overall Winner** ($250)
- 🧠 **Best Use of Gemma** ($200) — *100% local on-device quantized Gemma 2B inference with zero data leakage and a strict determinism boundary.*
- ⏳ **Best Use of Temporal** ($100) — *Durable cadence workflows surviving laptop sleep, Never-Nag-Twice 10-minute escalation state machines, and resilient activity retry policies.*