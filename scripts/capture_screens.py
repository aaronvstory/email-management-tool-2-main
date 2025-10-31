import os
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

BASE = os.environ.get("BASE_URI", "http://127.0.0.1:5010")
USER = os.environ.get("ET_USER", "admin")
PASS = os.environ.get("ET_PASS", "admin123")
OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)

# Pages we want; we’ll try a few best-guess paths for list views
CANDIDATES = {
    "dashboard": ["/dashboard", "/"],
    "unified-list": ["/unified", "/emails", "/messages"],
    "interception": ["/interception", "/queue", "/held"],
    "attachments": ["/attachments"],
}


def goto_first(page, paths, wait_selector=None):
    for p in paths:
        url = BASE.rstrip("/") + p
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=5000)
            return url
        except PWTimeout:
            continue
        except Exception:
            continue
    # last try w/out wait
    page.goto(BASE, wait_until="domcontentloaded")
    return BASE


def login(page):
    page.goto(BASE + "/login", wait_until="domcontentloaded")
    # Try common login fields
    page.fill('input[name="username"]', USER)
    page.fill('input[name="password"]', PASS)
    # Handle CSRF token if present in the login form
    try:
        # not strictly needed if server accepts form field already
        pass
    except Exception:
        pass
    page.click('button[type="submit"], input[type="submit"]')
    # allow redirect
    page.wait_for_load_state("domcontentloaded")


def get_csrf_from_meta(page):
    # droid added a meta csrf tag in base.html
    # <meta name="csrf-token" content="...">
    try:
        el = page.locator('meta[name="csrf-token"]')
        if el.count() > 0:
            return el.first.get_attribute("content")
    except Exception:
        pass
    return None


def post_json_with_csrf(page, path, csrf):
    url = BASE.rstrip("/") + path
    js = """
    async ({ url, csrf }) => {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Accept': 'application/json'
        }
      });
      let text = await resp.text();
      let payload;
      try { payload = JSON.parse(text); } catch { payload = {raw: text, status: resp.status}; }
      return payload;
    }
    """
    return page.evaluate(js, {"url": url, "csrf": csrf})


def snap(page, key, full=True):
    fp = OUT / f"{key}.png"
    page.screenshot(path=str(fp), full_page=full)
    print(f"saved: {fp}")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1) Login
        login(page)

        # 2) Dashboard shot
        goto_first(page, CANDIDATES["dashboard"])
        snap(page, "dashboard")

        # 3) Get CSRF (for POSTs)
        csrf = get_csrf_from_meta(page)
        if not csrf:
            # try forcing a reload of a page that likely includes base.html
            goto_first(page, CANDIDATES["dashboard"])
            csrf = get_csrf_from_meta(page)

        # 4) Accounts actions (if CSRF present)
        if csrf:
            # test creds
            res = post_json_with_csrf(page, "/api/accounts/1/test", csrf)
            print("accounts/1/test:", res)
            time.sleep(0.5)  # let toasts render if any
            snap(page, "accounts-test-success")

            # start
            res = post_json_with_csrf(page, "/api/accounts/1/monitor/start", csrf)
            print("monitor/start:", res)
            time.sleep(0.8)
            snap(page, "accounts-start-success")

            # stop
            res = post_json_with_csrf(page, "/api/accounts/1/monitor/stop", csrf)
            print("monitor/stop:", res)
            time.sleep(0.8)
            snap(page, "accounts-stop-success")

            # circuit reset
            res = post_json_with_csrf(page, "/api/accounts/1/circuit/reset", csrf)
            print("circuit/reset:", res)
            time.sleep(0.8)
            snap(page, "accounts-reset-success")
        else:
            print("WARN: No CSRF meta found; skipping POST action screenshots")

        # 5) Other views
        goto_first(page, CANDIDATES["unified-list"])
        snap(page, "unified-list")

        goto_first(page, CANDIDATES["interception"])
        snap(page, "interception")

        goto_first(page, CANDIDATES["attachments"])
        snap(page, "attachments")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
