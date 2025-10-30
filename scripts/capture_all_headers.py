#!/usr/bin/env python3
"""Capture screenshots of all page headers to verify consistency"""
import time
from playwright.sync_api import sync_playwright
from datetime import datetime
import os

def capture_headers():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Login
        page.goto("http://localhost:5000/login")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click("button[type='submit']")
        time.sleep(1)

        # Capture all pages with headers
        pages = [
            ("dashboard", "/dashboard"),
            ("accounts", "/accounts"),
            ("rules", "/rules"),
            ("emails", "/emails-unified"),
            ("compose", "/compose"),
            ("watchers", "/watchers")
        ]

        for name, url in pages:
            print(f"Capturing {name}...")
            page.goto(f"http://localhost:5000{url}")
            time.sleep(1)

            # Capture just the header area
            header = page.locator(".page-header").first
            if header.is_visible():
                header.screenshot(path=f"{screenshot_dir}/header_{name}_{timestamp}.png")
                print(f"✓ Saved header_{name}_{timestamp}.png")
            else:
                print(f"✗ No page-header found on {name}")

        browser.close()

        print(f"\n✅ Screenshots saved to {screenshot_dir}/")

if __name__ == "__main__":
    capture_headers()