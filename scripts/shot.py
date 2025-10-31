import os, re, json, asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE = os.getenv("BASE_URI", os.getenv("SHOT_BASE", "http://127.0.0.1:5010")).rstrip("/")
USER = os.getenv("ET_USER", os.getenv("SHOT_USER", "admin"))
PASS = os.getenv("ET_PASS", os.getenv("SHOT_PASS", "admin123"))
HEADLESS = os.getenv("SHOT_HEADLESS", "0") == "1"
VIEW = os.getenv("SHOT_VIEW", "desktop")  # desktop|mobile|both
MAX = int(os.getenv("SHOT_MAX", "25"))

INCLUDE = set([p.strip() for p in os.getenv("SHOT_INCLUDE","/").split(",") if p.strip()])
EXCLUDE = set([p.strip() for p in os.getenv("SHOT_EXCLUDE","/logout,/static,/api").split(",") if p.strip()])

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "screenshots" / datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

def _same_host(url: str) -> bool:
    return urlparse(url).netloc == urlparse(BASE).netloc or url.startswith("/")

def _normalize(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return urljoin(BASE, href)
    return urljoin(BASE + "/", href)

def _allowed(path: str) -> bool:
    p = urlparse(path).path or "/"
    if any(p.startswith(x) for x in EXCLUDE):
        return False
    if INCLUDE and not any(p == i or p.startswith(i.rstrip("/") + "/") for i in INCLUDE):
        return False
    return True

async def login(page):
    # Visit /login, fill *visible* fields only. Do NOT "fill" hidden csrf.
    await page.goto(f"{BASE}/login", wait_until='domcontentloaded')
    await page.get_by_placeholder("Username").or_(page.locator("input[name='username']")).fill(USER)
    await page.get_by_placeholder("Password").or_(page.locator("input[name='password']")).fill(PASS)
    # If the form has hidden csrf, submitting the form handles it; no need to set it manually.
    await page.locator("button[type='submit'], button:has-text('Login'), input[type='submit']").first.click()
    # Wait for redirect post-login
    try:
        await page.wait_for_url(re.compile(r".*/(dashboard|emails|compose)"), timeout=6000)
    except PWTimeout:
        # If the app sends to "/", accept that
        await page.wait_for_load_state("domcontentloaded")

async def scan_links(page) -> list[str]:
    # Collect all in-app links visible after login
    anchors = await page.locator("a[href]").evaluate_all("""els => els.map(e => e.getAttribute('href'))""")
    found = set()
    for a in anchors:
        if not a: continue
        url = _normalize(a)
        if _same_host(url) and _allowed(url):
            found.add(url.split("#")[0])
    # Add some canonical paths even if not linked on the landing page
    seeds = [f"{BASE}{p if p.startswith('/') else '/'+p}" for p in ["/", "/dashboard", "/emails", "/compose", "/diagnostics", "/watchers", "/rules", "/accounts", "/import"]]
    for s in seeds:
        if _allowed(s): found.add(s)
    ordered = sorted(found)
    return ordered[:MAX]

async def shoot(page, url: str, folder: Path, suffix=""):
    await page.goto(url, wait_until="domcontentloaded")
    # Give the page a sec to render widgets/toasts
    await page.wait_for_timeout(700)
    safe = re.sub(r"[^a-zA-Z0-9\-]+", "_", urlparse(url).path or "root").strip("_") or "root"
    fname = f"{safe}{suffix}.png"
    await page.screenshot(path=str(folder / fname), full_page=True)

async def run_for_view(play, device, viewname):
    context = await play.chromium.launch_persistent_context(
        user_data_dir=str(OUT_ROOT / f"profile_{viewname}"),
        headless=HEADLESS,
        viewport=None,
        args=[],
        device_scale_factor=device.get("device_scale_factor", 1)
    )
    if "user_agent" in device:
        await context.set_extra_http_headers({"User-Agent": device["user_agent"]})
    page = await context.new_page()
    try:
        await login(page)
        links = await scan_links(page)
        # Save the discovered routes list
        (OUT_ROOT / f"routes_{viewname}.json").write_text(json.dumps(links, indent=2))
        # Shoot the list
        for u in links:
            await shoot(page, u, OUT_ROOT / viewname)
    finally:
        await context.close()

async def main():
    OUT_ROOT.joinpath("desktop").mkdir(exist_ok=True)
    OUT_ROOT.joinpath("mobile").mkdir(exist_ok=True)

    devices = {
        "desktop": {},
        "mobile": {"user_agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15A372 Safari/604.1", "device_scale_factor": 3}
    }

    async with async_playwright() as p:
        tasks = []
        if VIEW in ("desktop","both"): tasks.append(run_for_view(p, devices["desktop"], "desktop"))
        if VIEW in ("mobile","both"):  tasks.append(run_for_view(p, devices["mobile"], "mobile"))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    print("=== Screenshot Kit ===")
    print(f"Base: {BASE}  Headless: {HEADLESS}  View: {VIEW}  Max: {MAX}")
    asyncio.run(main())
