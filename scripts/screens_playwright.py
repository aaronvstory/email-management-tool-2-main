import os, asyncio, time, json
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from playwright.async_api import async_playwright

BASE = os.environ.get("BASE_URI", "http://127.0.0.1:5010").rstrip("/")
USER = os.environ.get("ET_USER", "admin")
PASS = os.environ.get("ET_PASS", "admin123")

ts = time.strftime("%Y%m%d_%H%M%S")
OUT_DIR = Path("screenshots") / ts
OUT_DIR.mkdir(parents=True, exist_ok=True)

# add or tweak as needed
ROUTES = [
    ("/dashboard",       "dashboard.png",    ["#recent-emails", "h1", "h2"]),
    ("/emails",          "emails.png",       ["#unified-inbox", "h1", "h2"]),
    ("/compose",         "compose.png",      ["form[action*='compose']", "h1", "h2"]),
    ("/watchers",        "watchers.png",     ["#watchers-table", "h1", "h2"]),
    ("/diagnostics",     "diagnostics.png",  ["#healthz", "h1", "h2"]),
]

def wait_for_healthz(timeout_s=30):
    deadline = time.time() + timeout_s
    url = f"{BASE}/healthz"
    while time.time() < deadline:
        try:
            with urlopen(Request(url, headers={"Accept":"application/json"}), timeout=3) as r:
                if r.status == 200:
                    data = json.loads(r.read().decode("utf-8"))
                    if data.get("ok") is True:
                        return True
        except URLError:
            pass
        time.sleep(1)
    return False

async def login(page):
    # Load login page
    await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    # CSRF token
    token = await page.get_attribute("input[name='csrf_token']", "value")
    await page.fill("input[name='username']", USER)
    await page.fill("input[name='password']", PASS)
    if token:
        await page.fill("input[name='csrf_token']", token)
    await page.click("button[type='submit']")
    # land on dashboard
    await page.wait_for_url(f"{BASE}/dashboard", wait_until="networkidle")

async def main():
    if not wait_for_healthz():
        raise SystemExit(f"Server not reachable at {BASE} (/healthz)")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)  # set False to watch
        ctx = await browser.new_context(viewport={"width":1440, "height":900})
        page = await ctx.new_page()

        await login(page)

        for path, fname, selectors in ROUTES:
            url = f"{BASE}{path}"
            await page.goto(url, wait_until="networkidle")
            # wait for any “page is ready” selector
            ready = False
            for sel in selectors:
                try:
                    await page.wait_for_selector(sel, timeout=1500)
                    ready = True
                    break
                except:
                    continue
            # still snap even if none matched (page likely loaded)
            out = OUT_DIR / fname
            await page.screenshot(path=str(out), full_page=True)
            print(f"saved: {out} (ready={ready})")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
