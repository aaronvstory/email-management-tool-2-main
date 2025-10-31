#!/usr/bin/env python3
"""
Professional Playwright screenshot kit with link discovery and selection
"""
import os, re, json, asyncio, sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# Configuration from environment
BASE = os.getenv("BASE_URI", os.getenv("SHOT_BASE", "http://127.0.0.1:5001")).rstrip("/")
USER = os.getenv("ET_USER", os.getenv("SHOT_USER", "admin"))
PASS = os.getenv("ET_PASS", os.getenv("SHOT_PASS", "admin123"))
HEADLESS = os.getenv("SHOT_HEADLESS", "0") == "1"
VIEW = os.getenv("SHOT_VIEW", "desktop")  # desktop|mobile|both
MAX = int(os.getenv("SHOT_MAX", "25"))
DISCOVER_ONLY = os.getenv("SHOT_DISCOVER_ONLY", "0") == "1"
QUICK = os.getenv("SHOT_QUICK", "0") == "1"

INCLUDE = set([p.strip() for p in os.getenv("SHOT_INCLUDE","/").split(",") if p.strip()])
EXCLUDE = set([p.strip() for p in os.getenv("SHOT_EXCLUDE","/logout,/static,/api").split(",") if p.strip()])

# Selected links from PowerShell UI (if provided)
SELECTED_LINKS_JSON = os.getenv("SHOT_SELECTED_LINKS", "")
SELECTED_LINKS = set(json.loads(SELECTED_LINKS_JSON)) if SELECTED_LINKS_JSON else set()

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "screenshots" / datetime.now().strftime("%Y%m%d_%H%M%S")

def _same_host(url: str) -> bool:
    """Check if URL is same host as BASE"""
    return urlparse(url).netloc == urlparse(BASE).netloc or url.startswith("/")

def _normalize(href: str) -> str:
    """Normalize href to absolute URL"""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return urljoin(BASE, href)
    return urljoin(BASE + "/", href)

def _allowed(path: str) -> bool:
    """Check if path matches include/exclude filters"""
    p = urlparse(path).path or "/"
    if any(p.startswith(x) for x in EXCLUDE):
        return False
    if INCLUDE and not any(p == i or p.startswith(i.rstrip("/") + "/") for i in INCLUDE):
        return False
    return True

async def login(page):
    """Login to the application"""
    print(f"🔐 Logging in as {USER}...")
    await page.goto(f"{BASE}/login", wait_until='domcontentloaded')

    # Fill credentials (only visible fields, not hidden CSRF)
    await page.get_by_placeholder("Username").or_(page.locator("input[name='username']")).fill(USER)
    await page.get_by_placeholder("Password").or_(page.locator("input[name='password']")).fill(PASS)

    # Submit form
    await page.locator("button[type='submit'], button:has-text('Login'), input[type='submit']").first.click()

    # Wait for redirect
    try:
        await page.wait_for_url(re.compile(r".*/(dashboard|emails|compose)"), timeout=6000)
    except PWTimeout:
        await page.wait_for_load_state("domcontentloaded")

    print("✅ Logged in successfully")

async def scan_links(page) -> list[str]:
    """Discover all navigable links in the application"""
    print("🔍 Discovering links...")

    # Collect all in-app links
    anchors = await page.locator("a[href]").evaluate_all("""els => els.map(e => e.getAttribute('href'))""")
    found = set()

    for a in anchors:
        if not a:
            continue
        url = _normalize(a)
        if _same_host(url) and _allowed(url):
            found.add(url.split("#")[0])  # Remove fragment

    # Add seed paths (canonical routes that might not be linked)
    seeds = [
        "/", "/dashboard", "/emails", "/compose", "/diagnostics",
        "/watchers", "/rules", "/accounts", "/import", "/settings",
        "/inbox", "/styleguide"
    ]
    for s in seeds:
        full = f"{BASE}{s if s.startswith('/') else '/'+s}"
        if _allowed(full):
            found.add(full)

    ordered = sorted(found)[:MAX]
    print(f"✅ Found {len(ordered)} links")

    return ordered

async def shoot(page, url: str, folder: Path, suffix=""):
    """Capture screenshot of a single URL"""
    await page.goto(url, wait_until="domcontentloaded")

    # Give page time to render widgets/toasts
    await page.wait_for_timeout(700)

    # Generate safe filename
    safe = re.sub(r"[^a-zA-Z0-9\-]+", "_", urlparse(url).path or "root").strip("_") or "root"
    fname = f"{safe}{suffix}.png"
    fpath = folder / fname

    await page.screenshot(path=str(fpath), full_page=True)

    # Show progress
    rel_path = urlparse(url).path or "/"
    print(f"  📸 {rel_path} → {fname}")

async def run_for_view(play, device, viewname):
    """Run screenshot capture for a specific viewport (desktop/mobile)"""
    print(f"\n📱 Capturing {viewname} screenshots...")

    context = await play.chromium.launch_persistent_context(
        user_data_dir=str(OUT_ROOT / f"profile_{viewname}"),
        headless=HEADLESS,
        viewport=device.get("viewport"),
        args=[],
        device_scale_factor=device.get("device_scale_factor", 1)
    )

    if "user_agent" in device:
        await context.set_extra_http_headers({"User-Agent": device["user_agent"]})

    page = await context.new_page()

    try:
        await login(page)
        links = await scan_links(page)

        # If discovery-only mode, output links and exit
        if DISCOVER_ONLY:
            # Output as special marker that PowerShell can parse
            print(f"DISCOVERED_LINKS_JSON:{json.dumps(links)}")
            return

        # Filter to selected links if provided
        if SELECTED_LINKS:
            links = [l for l in links if l in SELECTED_LINKS]
            print(f"📋 Using {len(links)} selected links")

        # Save discovered routes
        routes_file = OUT_ROOT / f"routes_{viewname}.json"
        routes_file.write_text(json.dumps(links, indent=2))
        print(f"💾 Saved route list to {routes_file.name}")

        # Create output folder
        out_folder = OUT_ROOT / viewname
        out_folder.mkdir(parents=True, exist_ok=True)

        # Capture screenshots
        for i, url in enumerate(links, 1):
            print(f"\n[{i}/{len(links)}] {url}")
            await shoot(page, url, out_folder)

        print(f"\n✅ {viewname.title()} screenshots complete!")

    finally:
        await context.close()

async def main():
    """Main execution flow"""
    if not DISCOVER_ONLY:
        OUT_ROOT.joinpath("desktop").mkdir(parents=True, exist_ok=True)
        OUT_ROOT.joinpath("mobile").mkdir(parents=True, exist_ok=True)
        print(f"📁 Output: {OUT_ROOT}")

    # Device configurations
    devices = {
        "desktop": {
            "viewport": {"width": 1920, "height": 1080}
        },
        "mobile": {
            "viewport": {"width": 390, "height": 844},  # iPhone 14 Pro
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15A372 Safari/604.1",
            "device_scale_factor": 3
        }
    }

    async with async_playwright() as p:
        tasks = []

        # Run for selected viewports
        if VIEW in ("desktop", "both"):
            tasks.append(run_for_view(p, devices["desktop"], "desktop"))
        if VIEW in ("mobile", "both"):
            tasks.append(run_for_view(p, devices["mobile"], "mobile"))

        await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Banner
    if not DISCOVER_ONLY:
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║             📸 Playwright Screenshot Kit                     ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print(f"\n⚙️  Configuration:")
        print(f"   Base:     {BASE}")
        print(f"   User:     {USER}")
        print(f"   Mode:     {'Headless' if HEADLESS else 'Headed (visible)'}")
        print(f"   Viewport: {VIEW}")
        print(f"   Max:      {MAX} links")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)
