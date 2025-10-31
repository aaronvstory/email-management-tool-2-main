
# capture_screenshots_red.py
# Walks through EMAIL RED, logs in once, visits common pages, and saves screenshots.
#
# Usage:
#   pip install selenium webdriver-manager
#   python capture_screenshots_red.py --base-url http://localhost:5000 --user admin --password admin123
#   python capture_screenshots_red.py --base-url http://localhost:5001 --no-headless
#
# Output:
#   ./screenshots/red/<timestamp>/*.png

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

def main():
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
    except Exception as e:
        print("You need selenium and webdriver-manager installed:")
        print("  pip install selenium webdriver-manager")
        print(f"Import error: {e}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Screenshot runner for EMAIL RED")
    parser.add_argument("--base-url", required=True, help="Base URL (e.g., http://localhost:5000)")
    parser.add_argument("--user", default="admin", help="Login username")
    parser.add_argument("--password", default="admin123", help="Login password")
    parser.add_argument("--no-headless", action="store_true", help="Run with visible browser")
    parser.add_argument("--delay", type=float, default=0.8, help="Delay after navigation (seconds)")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path("screenshots") / "red" / ts
    out_root.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(options=options)  # Selenium Manager will fetch msedgedriver
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options = Options()
    options.add_argument("--headless=new")  # toggle via your flag as needed
    # IMPORTANT: drop ChromeDriverManager() entirely:
    driver = webdriver.Chrome(options=options)  # Selenium Manager fetches the right driver

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 10)

    def snap(name, subfolder=None):
        target_dir = out_root if not subfolder else out_root / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.png"
        driver.save_screenshot(str(path))
        print(f"Saved {path}")
        return path

    def goto(path, name=None, subfolder=None, wait_selector=None):
        url = f"{args.base_url}{path}"
        driver.get(url)
        time.sleep(args.delay)
        if wait_selector:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector)))
            except TimeoutException:
                print(f"[warn] Timeout waiting for {wait_selector} on {url}")
        snap(name or path.strip("/").replace("/", "_") or "root", subfolder=subfolder)

    try:
        # 1) Login
        driver.get(f"{args.base_url}/login")
        time.sleep(args.delay)
        # Heuristic selectors
        user_sel = None
        pass_sel = None
        submit_sel = None

        for sel in ["#username", "input[name='username']", "#email", "input[name='email']"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel)
                user_sel = sel
                break
            except NoSuchElementException:
                continue
        for sel in ["#password", "input[name='password']", "input[type='password']"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel)
                pass_sel = sel
                break
            except NoSuchElementException:
                continue
        for sel in ["button[type='submit']", "#submit", ".btn-primary[type='submit']", "button[name='login']"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel)
                submit_sel = sel
                break
            except NoSuchElementException:
                continue

        if not (user_sel and pass_sel and submit_sel):
            snap("login_page")
            print("[error] Could not find login fields. Saved login_page screenshot for reference.")
            driver.quit()
            sys.exit(2)

        driver.find_element(By.CSS_SELECTOR, user_sel).clear()
        driver.find_element(By.CSS_SELECTOR, user_sel).send_keys(args.user)
        driver.find_element(By.CSS_SELECTOR, pass_sel).clear()
        driver.find_element(By.CSS_SELECTOR, pass_sel).send_keys(args.password)
        driver.find_element(By.CSS_SELECTOR, submit_sel).click()

        try:
            wait.until(lambda d: "/login" not in d.current_url)
        except TimeoutException:
            print("[warn] Login redirect timeout; continuing. If pages require auth, screenshots may be of login.")
        time.sleep(args.delay)
        snap("01_dashboard", subfolder="root")

        # 2) Core pages
        pages = [
            ("/dashboard", "02_dashboard"),
            ("/accounts", "03_accounts"),
            ("/watchers", "04_watchers"),
            ("/emails", "05_emails"),
            ("/emails/unified", "06_emails_unified"),
            ("/compose", "07_compose"),
            ("/rules", "08_rules"),
            ("/settings", "09_settings"),
            ("/diagnostics/stitch", "10_diagnostics"),
            ("/interception/test/stitch", "11_interception_test"),
        ]
        for path, name in pages:
            goto(path, name=name, subfolder="root")

        # 3) Email detail from unified list
        driver.get(f"{args.base_url}/emails/unified")
        time.sleep(args.delay)
        snap("06_emails_unified_before_click", subfolder="details")
        detail_clicked = False
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/email/']")
            if anchors:
                anchors[0].click()
                time.sleep(args.delay)
                snap("12_email_detail", subfolder="details")
                detail_clicked = True
        except Exception as e:
            print(f"[warn] Could not open email detail: {e}")

        # 4) Attachments panel (best-effort)
        if detail_clicked:
            try:
                dl_all = driver.find_elements(By.XPATH, "//button[contains(., 'Download All')]")
                if dl_all:
                    _ = dl_all[0].location_once_scrolled_into_view
                    dl_all[0].click()
                    time.sleep(0.5)
                snap("13_email_attachments_panel", subfolder="details")
            except Exception as e:
                print(f"[warn] Attachments panel step failed: {e}")

        print(f"\nAll done. Folder: {out_root}")
        print("Tip: zip the folder to attach to PR or send to the team.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
