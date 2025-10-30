#!/usr/bin/env python3
"""Test accounts page functionality"""
import time
from playwright.sync_api import sync_playwright
import requests

def test_accounts_page():
    print("Testing accounts page functionality...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Show browser for debugging
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # Enable console logging
        page.on('console', lambda msg: print(f"Console {msg.type}: {msg.text}"))
        page.on('pageerror', lambda err: print(f"Page error: {err}"))

        # Login
        print("1. Logging in...")
        page.goto("http://localhost:5001/login")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click("button[type='submit']")
        time.sleep(1)

        # Go to accounts page
        print("2. Navigating to accounts page...")
        page.goto("http://localhost:5001/accounts")
        time.sleep(1)

        # Check for account cards
        print("3. Checking for account cards...")
        account_cards = page.locator(".stat-card-modern[id^='account-']").all()
        print(f"   Found {len(account_cards)} account cards")

        if len(account_cards) > 0:
            # Try to get the first account's ID
            first_card = account_cards[0]
            card_id = first_card.get_attribute("id")
            if card_id:
                account_id = card_id.replace("account-", "")
                print(f"   First account ID: {account_id}")

                # Try clicking Test button
                print(f"4. Testing account {account_id}...")
                test_button = first_card.locator("button:has-text('Test')").first
                if test_button.is_visible():
                    test_button.click()
                    time.sleep(2)
                    print("   Test button clicked")

                # Try clicking Start button
                print(f"5. Starting watcher for account {account_id}...")
                start_button = first_card.locator("button:has-text('Start')").first
                if start_button.is_visible():
                    start_button.click()
                    time.sleep(2)
                    print("   Start button clicked")

                # Check for any error toasts
                error_toasts = page.locator(".toast-body:has-text('error')").all()
                if error_toasts:
                    print("\n⚠️ Errors found:")
                    for toast in error_toasts:
                        print(f"   - {toast.text_content()}")
                else:
                    print("\n✅ No errors detected!")

        # Take screenshot
        page.screenshot(path="screenshots/accounts_test.png")
        print("\nScreenshot saved to screenshots/accounts_test.png")

        # Keep browser open for manual inspection
        input("\nPress Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    test_accounts_page()
