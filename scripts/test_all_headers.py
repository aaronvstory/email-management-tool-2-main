#!/usr/bin/env python3
"""Test all page headers are consistent"""
import time
from playwright.sync_api import sync_playwright
from datetime import datetime

def test_all_headers():
    print("Testing all page headers for consistency...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Login
        page.goto("http://localhost:5001/login")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click("button[type='submit']")
        time.sleep(1)

        # Test all pages
        pages = [
            ("Dashboard", "/dashboard"),
            ("Accounts", "/accounts"),
            ("Import Accounts", "/accounts/import"),
            ("Rules", "/rules"),
            ("Emails", "/emails-unified"),
            ("Compose", "/compose"),
            ("Watchers", "/watchers"),
            ("Diagnostics", "/diagnostics"),
            ("Style Guide", "/styleguide"),
            ("Interception Test", "/interception-test")
        ]

        results = []
        for name, url in pages:
            page.goto(f"http://localhost:5001{url}")
            time.sleep(0.5)

            # Check for page-header
            header = page.locator(".page-header").first
            if header.is_visible():
                # Get the h1 text
                h1_text = page.locator(".page-header h1").first.text_content()
                # Check for description
                has_desc = page.locator(".page-header p.text-muted").count() > 0
                # Check for header-actions
                has_actions = page.locator(".page-header .header-actions").count() > 0

                results.append({
                    'name': name,
                    'url': url,
                    'status': '✅',
                    'h1': h1_text.strip(),
                    'has_desc': '✓' if has_desc else '✗',
                    'has_actions': '✓' if has_actions else '✗'
                })
            else:
                results.append({
                    'name': name,
                    'url': url,
                    'status': '❌',
                    'h1': 'NO HEADER FOUND',
                    'has_desc': '✗',
                    'has_actions': '✗'
                })

        browser.close()

        # Print results
        print("=" * 80)
        print("PAGE HEADER CONSISTENCY TEST RESULTS")
        print("=" * 80)
        print(f"{'Page':<20} {'Status':<10} {'H1 Title':<30} {'Desc':<8} {'Actions':<8}")
        print("-" * 80)

        all_passed = True
        for r in results:
            print(f"{r['name']:<20} {r['status']:<10} {r['h1'][:28]:<30} {r['has_desc']:<8} {r['has_actions']:<8}")
            if r['status'] == '❌':
                all_passed = False

        print("=" * 80)
        if all_passed:
            print("✅ ALL PAGES HAVE CONSISTENT HEADERS!")
        else:
            print("❌ Some pages are missing proper headers")

        return all_passed

if __name__ == "__main__":
    test_all_headers()
