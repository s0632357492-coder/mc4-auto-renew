# MC4.in Auto-Renew Bot

Headless Playwright bot that automatically renews a free Minecraft server on [mc4.in](https://mc4.in) every 15 minutes.

---

## Project structure

```
.
├── main.py           # Bot entry point
├── requirements.txt  # Python dependencies
└── README.md
```

---

## Local development

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium   # Linux only
```

### Run

```bash
export MC4_USERNAME="your_username"
export MC4_PASSWORD="your_password"
python main.py
```

---

## Deploy to Render (Background Worker)

### 1 – Create a new service

1. Go to [https://dashboard.render.com](https://dashboard.render.com) → **New → Background Worker**
2. Connect your GitHub repo (push `main.py` + `requirements.txt` + `README.md`).

### 2 – Build & Start commands

| Field | Value |
|---|---|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium` |
| **Start Command** | `python main.py` |

### 3 – Environment variables

In Render → **Environment** tab, add:

| Key | Value |
|---|---|
| `MC4_USERNAME` | your mc4.in username |
| `MC4_PASSWORD` | your mc4.in password |

> ⚠️ Never commit credentials to source control.

### 4 – Deploy

Click **Create Background Worker**. Render will build, install Playwright + Chromium, and start the bot automatically.

---

## How it works

| Phase | Detail |
|---|---|
| Session | Saves `storage_state.json` after first login; reuses it on every cycle |
| Login fallback | If session is expired the bot re-authenticates automatically |
| Renew flow | Clicks **ต่ออายุฟรี → ยืนยันต่ออายุฟรี 1 ชั่วโมง → OK** (twice, with popup guard on the second OK) |
| Popup guard | Uses `context.expect_page()` to catch and close any Shopee / ad tabs instantly |
| Retry | Each cycle retries up to 3 times before sleeping |
| Loop | Runs forever; waits 900 s (15 min) between cycles |
| Anti-detection | Random 1–3 s delays between actions; navigator.webdriver spoofed |
| Logging | Timestamped stdout logs — visible in Render's log stream |

---

## Logs

Example output:

```
[2026-05-01 10:00:00] MC4.in Auto-Renew Bot starting …
[2026-05-01 10:00:00] Cycle interval: 900s | Max retries: 3
[2026-05-01 10:00:00] ═══ Cycle #1 ═══
[2026-05-01 10:00:01] Loading saved session …
[2026-05-01 10:00:03] Session valid ✓
[2026-05-01 10:00:03] Renew attempt 1/3 …
[2026-05-01 10:00:06] Clicking: ต่ออายุฟรี
[2026-05-01 10:00:09] Clicking: ยืนยันต่ออายุฟรี (1st)
[2026-05-01 10:00:11] Clicking: OK (1st)
[2026-05-01 10:00:13] Success indicator found ✓
[2026-05-01 10:00:16] Clicking: OK (with popup guard)
[2026-05-01 10:00:16] Popup/new tab detected (https://shopee.co.th/…) – closing …
[2026-05-01 10:00:18] Renew success ✓
[2026-05-01 10:00:18] Sleeping 900s until next cycle …
```
