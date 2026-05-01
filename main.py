import asyncio
import os
import random
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ─── Config ────────────────────────────────────────────────────────────────────
LOGIN_URL      = "https://mc4.in/login"
DASHBOARD_URL  = "https://mc4.in/dashboard"
SESSION_FILE   = "storage_state.json"
CYCLE_INTERVAL = 900          # 15 minutes
MAX_RETRIES    = 3
ACTION_TIMEOUT = 30_000       # ms
NAV_TIMEOUT    = 60_000       # ms

USERNAME = os.environ.get("MC4_USERNAME", "")
PASSWORD = os.environ.get("MC4_PASSWORD", "")

# ─── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running", 200

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

# ─── Logging ───────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ─── Human-like delay ──────────────────────────────────────────────────────────
async def human_delay(lo: float = 1.0, hi: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(lo, hi))

# ─── Browser factory ──────────────────────────────────────────────────────────
async def create_browser(playwright):
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,900",
        ],
    )
    ctx_kwargs = dict(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="th-TH",
        timezone_id="Asia/Bangkok",
        java_script_enabled=True,
    )
    if Path(SESSION_FILE).exists():
        log("Loading saved session …")
        ctx_kwargs["storage_state"] = SESSION_FILE

    context = await browser.new_context(**ctx_kwargs)
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context

# ─── Login ─────────────────────────────────────────────────────────────────────
async def do_login(page) -> bool:
    log("Navigating to login page …")
    await page.goto(LOGIN_URL, timeout=NAV_TIMEOUT, wait_until="networkidle")
    await human_delay()

    try:
        await page.wait_for_selector(
            "input[name='username'], input[type='text']",
            timeout=ACTION_TIMEOUT,
        )
        username_sel = "input[name='username'], input[type='text']"
        password_sel = "input[name='password'], input[type='password']"

        await page.fill(username_sel, "")
        await human_delay(0.3, 0.8)
        await page.type(username_sel, USERNAME, delay=random.randint(60, 130))

        await page.fill(password_sel, "")
        await human_delay(0.3, 0.8)
        await page.type(password_sel, PASSWORD, delay=random.randint(60, 130))

        await human_delay()
        submit_sel = (
            "button[type='submit'], input[type='submit'], "
            "button:has-text('Login'), button:has-text('เข้าสู่ระบบ')"
        )
        await page.click(submit_sel, timeout=ACTION_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)

        if "login" in page.url.lower():
            log("ERROR: Still on login page – check credentials.")
            return False

        log("Login success ✓")
        await page.context.storage_state(path=SESSION_FILE)
        return True

    except PlaywrightTimeoutError as e:
        log(f"Login timeout: {e}")
        return False

# ─── Session check ─────────────────────────────────────────────────────────────
async def ensure_logged_in(page) -> bool:
    try:
        await page.goto(DASHBOARD_URL, timeout=NAV_TIMEOUT, wait_until="networkidle")
        if "login" in page.url.lower():
            log("Session expired – re-logging in …")
            return await do_login(page)
        log("Session valid ✓")
        return True
    except PlaywrightTimeoutError:
        log("Navigation timeout checking session.")
        return False

# ─── Safe click with popup guard ───────────────────────────────────────────────
async def safe_click(page, selector: str, context=None, label: str = "") -> None:
    await page.wait_for_selector(selector, timeout=ACTION_TIMEOUT, state="visible")
    await human_delay()
    log(f"Clicking: {label or selector}")

    if context:
        async with context.expect_page(timeout=8_000) as popup_info:
            await page.click(selector, timeout=ACTION_TIMEOUT)
        try:
            popup = await popup_info.value
            log(f"Popup/new tab detected ({popup.url}) – closing …")
            await popup.close()
            await page.bring_to_front()
        except Exception:
            pass
    else:
        await page.click(selector, timeout=ACTION_TIMEOUT)

# ─── Renewal flow ──────────────────────────────────────────────────────────────
async def renew_once(page, context) -> bool:
    try:
        log("Waiting for dashboard …")
        await page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)

        renew_btn_sel = "button:has-text('ต่ออายุฟรี'), a:has-text('ต่ออายุฟรี')"
        try:
            await safe_click(page, renew_btn_sel, label="ต่ออายุฟรี")
        except PlaywrightTimeoutError:
            log("'ต่ออายุฟรี' not found – reloading dashboard …")
            await page.goto(DASHBOARD_URL, timeout=NAV_TIMEOUT, wait_until="networkidle")
            await safe_click(page, renew_btn_sel, label="ต่ออายุฟรี (retry)")

        await human_delay()

        confirm_sel = "button:has-text('ยืนยันต่ออายุฟรี 1 ชั่วโมง')"
        await safe_click(page, confirm_sel, label="ยืนยันต่ออายุฟรี (1st)")
        await human_delay()

        ok_sel = "button:has-text('OK'), button:has-text('ตกลง')"
        await safe_click(page, ok_sel, label="OK (1st)")
        await human_delay()

        log("Waiting for success confirmation …")
        success_sel = (
            "text=สำเร็จ!, "
            ".swal2-success, "
            "[class*='success'], "
            "img[src*='success'], "
            "img[alt*='success']"
        )
        try:
            await page.wait_for_selector(success_sel, timeout=15_000)
            log("Success indicator found ✓")
        except PlaywrightTimeoutError:
            log("Success indicator not found – continuing anyway …")

        await human_delay()

        try:
            await safe_click(page, confirm_sel, label="ยืนยันต่ออายุฟรี (2nd)")
            await human_delay()
        except PlaywrightTimeoutError:
            log("Second confirm button not present – skipping …")

        try:
            await safe_click(page, ok_sel, context=context, label="OK (with popup guard)")
        except PlaywrightTimeoutError:
            log("Final OK not present – skipping …")

        await human_delay()
        log("Renew success ✓")
        return True

    except PlaywrightTimeoutError as e:
        log(f"Timeout during renew: {e}")
        return False
    except Exception as e:
        log(f"Unexpected error during renew: {e}")
        return False

# ─── One full cycle ────────────────────────────────────────────────────────────
async def run_cycle(playwright) -> None:
    browser, context = await create_browser(playwright)
    page = await context.new_page()

    try:
        if not await ensure_logged_in(page):
            log("Could not establish session – aborting cycle.")
            return

        for attempt in range(1, MAX_RETRIES + 1):
            log(f"Renew attempt {attempt}/{MAX_RETRIES} …")
            if attempt > 1:
                log("Reloading dashboard before retry …")
                try:
                    await page.goto(DASHBOARD_URL, timeout=NAV_TIMEOUT,
                                    wait_until="networkidle")
                except Exception:
                    pass

            success = await renew_once(page, context)
            if success:
                break
            log(f"Attempt {attempt} failed – "
                f"{'retrying' if attempt < MAX_RETRIES else 'giving up'}.")
            await asyncio.sleep(5)

    except Exception as e:
        log(f"Fatal cycle error: {e}")
    finally:
        try:
            await context.storage_state(path=SESSION_FILE)
        except Exception:
            pass
        await page.close()
        await context.close()
        await browser.close()

# ─── Async bot loop ────────────────────────────────────────────────────────────
async def bot_loop() -> None:
    log("Bot loop started.")
    async with async_playwright() as playwright:
        cycle = 0
        while True:
            cycle += 1
            log(f"═══ Cycle #{cycle} ═══")
            try:
                await run_cycle(playwright)
            except Exception as e:
                log(f"Unhandled cycle exception: {e}")
            log(f"Sleeping {CYCLE_INTERVAL}s until next cycle …")
            await asyncio.sleep(CYCLE_INTERVAL)

# ─── Thread entry point ────────────────────────────────────────────────────────
def start_bot_thread() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot_loop())
    except Exception as e:
        log(f"Bot thread crashed: {e}")
    finally:
        loop.close()

# ─── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        log("FATAL: MC4_USERNAME and MC4_PASSWORD environment variables must be set.")
        raise SystemExit(1)

    log("MC4.in Auto-Renew Bot (Web Service mode) starting …")
    log(f"Cycle interval: {CYCLE_INTERVAL}s | Max retries: {MAX_RETRIES}")

    bot = threading.Thread(target=start_bot_thread, daemon=True, name="bot-loop")
    bot.start()
    log("Bot thread launched. Starting Flask on 0.0.0.0:10000 …")

    app.run(host="0.0.0.0", port=10000, use_reloader=False)
