# MC4.in Auto-Renew Bot — Web Service Edition

Headless Playwright bot that auto-renews a free Minecraft server on mc4.in every 15 minutes.
Runs as a **Render Free Web Service** with Flask keeping the process alive and UptimeRobot preventing idle shutdown.

---

## Project structure

```
.
├── main.py           # Flask + bot thread
├── requirements.txt  # Dependencies
└── README.md
```

---

## Render Deployment

### 1 — Create Web Service

1. Push all files to a GitHub repo.
2. Go to **dashboard.render.com → New → Web Service**.
3. Connect the repo.

### 2 — Service settings

| Setting | Value |
|---|---|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium` |
| **Start Command** | `python main.py` |
| **Instance Type** | Free |
| **Port** | `10000` |

### 3 — Environment variables

In Render → **Environment** tab:

| Key | Value |
|---|---|
| `MC4_USERNAME` | your mc4.in username |
| `MC4_PASSWORD` | your mc4.in password |

### 4 — Deploy

Click **Create Web Service**. Render builds, installs Playwright + Chromium, and starts the bot.

---

## UptimeRobot — Anti-sleep pings

Render Free tier sleeps after ~15 min of no HTTP traffic. Pin UptimeRobot to prevent this.

1. Register free at [uptimerobot.com](https://uptimerobot.com).
2. **New Monitor → HTTP(s)**.
3. Set **URL** to your Render service URL, e.g. `https://your-service.onrender.com/health`.
4. Set **Monitoring Interval** to **5 minutes**.
5. Save.

The `/health` endpoint returns `{"status": "ok"}` — lightweight and always fast.

---

## Endpoints

| Route | Response |
|---|---|
| `GET /` | `Bot is running` (200) |
| `GET /health` | `{"status": "ok"}` (200) |

---

## How it works

| Phase | Detail |
|---|---|
| Startup | Flask starts on `0.0.0.0:10000`; bot runs in a `daemon` thread |
| Session | Saves `storage_state.json` after first login; reused every cycle |
| Login fallback | Auto re-authenticates when session expires |
| Renew flow | ต่ออายุฟรี → ยืนยันต่ออายุฟรี 1 ชั่วโมง → OK (×2 with popup guard) |
| Popup guard | `context.expect_page()` catches and closes Shopee / ad tabs |
| Retry | Up to 3 attempts per cycle |
| Loop | `while True` with 900 s (15 min) sleep between cycles |
| Anti-detection | Random 1–3 s delays; `navigator.webdriver` spoofed |

---

## Sample logs

```
[2026-05-01 10:00:00] MC4.in Auto-Renew Bot (Web Service mode) starting …
[2026-05-01 10:00:00] Cycle interval: 900s | Max retries: 3
[2026-05-01 10:00:00] Bot thread launched. Starting Flask on 0.0.0.0:10000 …
[2026-05-01 10:00:01] Bot loop started.
[2026-05-01 10:00:01] ═══ Cycle #1 ═══
[2026-05-01 10:00:02] Loading saved session …
[2026-05-01 10:00:04] Session valid ✓
[2026-05-01 10:00:04] Renew attempt 1/3 …
[2026-05-01 10:00:07] Clicking: ต่ออายุฟรี
[2026-05-01 10:00:10] Clicking: ยืนยันต่ออายุฟรี (1st)
[2026-05-01 10:00:12] Clicking: OK (1st)
[2026-05-01 10:00:14] Success indicator found ✓
[2026-05-01 10:00:17] Clicking: OK (with popup guard)
[2026-05-01 10:00:17] Popup/new tab detected (https://shopee.co.th/…) – closing …
[2026-05-01 10:00:19] Renew success ✓
[2026-05-01 10:00:19] Sleeping 900s until next cycle …
```
