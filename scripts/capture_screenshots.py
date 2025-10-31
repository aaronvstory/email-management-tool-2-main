"""
Screenshot capture script for Email Management Tool
Captures screenshots of dashboard, accounts, and rules pages
"""

import time
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Configuration
BASE_URL = "http://localhost:5001"
USERNAME = "admin"
PASSWORD = "admin123"
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots"

# Create screenshots directory
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Timestamp for filenames
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

def setup_driver():
    """Set up Chrome driver with appropriate options"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # New headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    return driver

def login(driver):
    """Log in to the application"""
    print("Logging in...")
    driver.get(f"{BASE_URL}/login")

    # Wait for login form
    wait = WebDriverWait(driver, 10)
    username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))

    # Enter credentials
    username_field.send_keys(USERNAME)
    password_field = driver.find_element(By.NAME, "password")
    password_field.send_keys(PASSWORD)

    # Submit form
    submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_button.click()

    # Wait for redirect to dashboard
    wait.until(EC.url_contains("/dashboard"))
    print("Login successful!")

def capture_screenshot(driver, url, filename):
    """Capture screenshot of a specific page"""
    print(f"Capturing {filename}...")
    driver.get(url)

    # Wait for page to load
    time.sleep(2)

    # Take screenshot
    filepath = SCREENSHOT_DIR / filename
    driver.save_screenshot(str(filepath))
    print(f"Saved: {filepath}")

    return filepath

def main():
    """Main execution"""
    driver = None
    try:
        print("Starting screenshot capture...")
        print(f"Timestamp: {timestamp}")

        driver = setup_driver()

        # Login
        login(driver)

        # Capture screenshots
        screenshots = []

        # 1. Dashboard
        filepath = capture_screenshot(
            driver,
            f"{BASE_URL}/dashboard",
            f"fixed_dashboard_{timestamp}.png"
        )
        screenshots.append(filepath)

        # 2. Accounts page
        filepath = capture_screenshot(
            driver,
            f"{BASE_URL}/accounts",
            f"fixed_accounts_{timestamp}.png"
        )
        screenshots.append(filepath)

        # 3. Rules page
        filepath = capture_screenshot(
            driver,
            f"{BASE_URL}/rules",
            f"fixed_rules_{timestamp}.png"
        )
        screenshots.append(filepath)

        print("\n" + "="*60)
        print("Screenshot Capture Complete!")
        print("="*60)
        print(f"\nScreenshots saved to: {SCREENSHOT_DIR}")
        for screenshot in screenshots:
            print(f"  - {screenshot.name}")

        return screenshots

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    screenshots = main()
