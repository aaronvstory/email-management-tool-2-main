#!/usr/bin/env python3
"""
UI Diagnostics Script - Email Management Tool
Captures screenshots and diagnoses CSS/styling issues
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except ImportError:
    print("ERROR: Selenium not installed. Run: pip install selenium")
    sys.exit(1)

class UIDignostics:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.screenshots_dir = Path(__file__).parent.parent / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report = {
            "timestamp": self.timestamp,
            "pages": {},
            "issues": []
        }

        # Initialize Chrome driver
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            print(f"ERROR: Could not initialize Chrome WebDriver: {e}")
            print("\nPlease ensure ChromeDriver is installed and in PATH")
            print("Download from: https://chromedriver.chromium.org/")
            sys.exit(1)

    def login(self, username="admin", password="admin123"):
        """Login to the application"""
        print(f"\n[1/7] Navigating to login page...")
        self.driver.get(f"{self.base_url}/login")
        time.sleep(2)

        # Take screenshot of login page
        screenshot_path = self.screenshots_dir / f"01_login_{self.timestamp}.png"
        self.driver.save_screenshot(str(screenshot_path))
        print(f"  ✓ Screenshot saved: {screenshot_path.name}")

        # Fill login form
        print(f"  → Logging in as {username}...")
        username_field = self.wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_field = self.driver.find_element(By.NAME, "password")

        username_field.send_keys(username)
        password_field.send_keys(password)

        # Submit form
        login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()

        time.sleep(3)  # Wait for redirect
        print("  ✓ Login successful")

    def inspect_css_issues(self, page_name):
        """Inspect CSS for common issues"""
        issues = []

        print(f"    → Inspecting CSS for {page_name}...")

        # Check for panel-body padding
        panel_bodies = self.driver.find_elements(By.CLASS_NAME, "panel-body")
        for i, panel in enumerate(panel_bodies):
            padding = self.driver.execute_script(
                "return window.getComputedStyle(arguments[0]).padding;", panel
            )
            if padding == "0px":
                issues.append({
                    "element": f"panel-body #{i+1}",
                    "issue": "Missing padding",
                    "computed_style": {"padding": padding}
                })

        # Check for page-header flex layout
        page_headers = self.driver.find_elements(By.CLASS_NAME, "page-header")
        for i, header in enumerate(page_headers):
            display = self.driver.execute_script(
                "return window.getComputedStyle(arguments[0]).display;", header
            )
            if display != "flex":
                issues.append({
                    "element": f"page-header #{i+1}",
                    "issue": "Not using flex layout",
                    "computed_style": {"display": display}
                })

        # Check for inline styles (bad practice)
        elements_with_inline = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('[style]')).map(el => ({
                tag: el.tagName,
                class: el.className,
                style: el.getAttribute('style')
            }));
        """)

        if elements_with_inline:
            issues.append({
                "element": "Multiple elements",
                "issue": f"Found {len(elements_with_inline)} elements with inline styles",
                "details": elements_with_inline[:5]  # First 5 only
            })

        # Check panel sizing (look for unusually large panels)
        panels = self.driver.find_elements(By.CLASS_NAME, "panel")
        for i, panel in enumerate(panels):
            height = self.driver.execute_script("return arguments[0].offsetHeight;", panel)
            if height > 800:  # Unusually tall panel
                computed = self.driver.execute_script("""
                    const style = window.getComputedStyle(arguments[0]);
                    return {
                        height: style.height,
                        minHeight: style.minHeight,
                        padding: style.padding,
                        margin: style.margin
                    };
                """, panel)
                issues.append({
                    "element": f"panel #{i+1}",
                    "issue": f"Unusually large panel ({height}px tall)",
                    "computed_style": computed
                })

        # Check table-modern wrapper
        table_wrappers = self.driver.find_elements(By.CLASS_NAME, "table-modern")
        for i, wrapper in enumerate(table_wrappers):
            overflow = self.driver.execute_script(
                "return window.getComputedStyle(arguments[0]).overflow;", wrapper
            )
            if overflow == "visible":
                issues.append({
                    "element": f"table-modern #{i+1}",
                    "issue": "Missing overflow control",
                    "computed_style": {"overflow": overflow}
                })

        return issues

    def capture_dashboard(self):
        """Capture dashboard screenshots (all 3 tabs)"""
        print(f"\n[2/7] Capturing dashboard...")
        self.driver.get(f"{self.base_url}/dashboard")
        time.sleep(3)

        # Overview tab (default)
        screenshot_path = self.screenshots_dir / f"02_dashboard_overview_{self.timestamp}.png"
        self.driver.save_screenshot(str(screenshot_path))
        print(f"  ✓ Screenshot saved: {screenshot_path.name}")

        issues = self.inspect_css_issues("dashboard_overview")
        self.report["pages"]["dashboard_overview"] = {
            "url": f"{self.base_url}/dashboard",
            "screenshot": screenshot_path.name,
            "issues": issues
        }

        # Try to click on other tabs if they exist
        try:
            # Moderation tab
            moderation_tab = self.driver.find_element(By.CSS_SELECTOR, "a[href='#moderation']")
            moderation_tab.click()
            time.sleep(2)
            screenshot_path = self.screenshots_dir / f"03_dashboard_moderation_{self.timestamp}.png"
            self.driver.save_screenshot(str(screenshot_path))
            print(f"  ✓ Screenshot saved: {screenshot_path.name}")

            issues = self.inspect_css_issues("dashboard_moderation")
            self.report["pages"]["dashboard_moderation"] = {
                "url": f"{self.base_url}/dashboard#moderation",
                "screenshot": screenshot_path.name,
                "issues": issues
            }

            # Activity tab
            activity_tab = self.driver.find_element(By.CSS_SELECTOR, "a[href='#activity']")
            activity_tab.click()
            time.sleep(2)
            screenshot_path = self.screenshots_dir / f"04_dashboard_activity_{self.timestamp}.png"
            self.driver.save_screenshot(str(screenshot_path))
            print(f"  ✓ Screenshot saved: {screenshot_path.name}")

            issues = self.inspect_css_issues("dashboard_activity")
            self.report["pages"]["dashboard_activity"] = {
                "url": f"{self.base_url}/dashboard#activity",
                "screenshot": screenshot_path.name,
                "issues": issues
            }
        except Exception as e:
            print(f"  ⚠ Could not capture all dashboard tabs: {e}")

    def capture_accounts(self):
        """Capture accounts page"""
        print(f"\n[3/7] Capturing accounts page...")
        self.driver.get(f"{self.base_url}/accounts")
        time.sleep(3)

        screenshot_path = self.screenshots_dir / f"05_accounts_{self.timestamp}.png"
        self.driver.save_screenshot(str(screenshot_path))
        print(f"  ✓ Screenshot saved: {screenshot_path.name}")

        issues = self.inspect_css_issues("accounts")
        self.report["pages"]["accounts"] = {
            "url": f"{self.base_url}/accounts",
            "screenshot": screenshot_path.name,
            "issues": issues
        }

    def capture_rules(self):
        """Capture rules page"""
        print(f"\n[4/7] Capturing rules page...")
        self.driver.get(f"{self.base_url}/rules")
        time.sleep(3)

        screenshot_path = self.screenshots_dir / f"06_rules_{self.timestamp}.png"
        self.driver.save_screenshot(str(screenshot_path))
        print(f"  ✓ Screenshot saved: {screenshot_path.name}")

        issues = self.inspect_css_issues("rules")
        self.report["pages"]["rules"] = {
            "url": f"{self.base_url}/rules",
            "screenshot": screenshot_path.name,
            "issues": issues
        }

    def generate_report(self):
        """Generate diagnostic report"""
        print(f"\n[5/7] Generating diagnostic report...")

        # Compile all issues
        all_issues = []
        for page_name, page_data in self.report["pages"].items():
            for issue in page_data["issues"]:
                all_issues.append({
                    "page": page_name,
                    **issue
                })

        self.report["issues"] = all_issues
        self.report["summary"] = {
            "total_pages_captured": len(self.report["pages"]),
            "total_issues_found": len(all_issues),
            "issues_by_type": {}
        }

        # Count issues by type
        for issue in all_issues:
            issue_type = issue["issue"]
            if issue_type not in self.report["summary"]["issues_by_type"]:
                self.report["summary"]["issues_by_type"][issue_type] = 0
            self.report["summary"]["issues_by_type"][issue_type] += 1

        # Save report
        report_path = self.screenshots_dir / f"diagnostic_report_{self.timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=2)

        print(f"  ✓ Report saved: {report_path.name}")

        # Generate human-readable report
        text_report_path = self.screenshots_dir / f"diagnostic_report_{self.timestamp}.txt"
        with open(text_report_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("UI DIAGNOSTICS REPORT - Email Management Tool\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Timestamp: {self.timestamp}\n")
            f.write(f"Base URL: {self.base_url}\n\n")

            f.write("SUMMARY\n")
            f.write("-" * 80 + "\n")
            f.write(f"Pages Captured: {self.report['summary']['total_pages_captured']}\n")
            f.write(f"Total Issues Found: {self.report['summary']['total_issues_found']}\n\n")

            if self.report['summary']['issues_by_type']:
                f.write("Issues by Type:\n")
                for issue_type, count in self.report['summary']['issues_by_type'].items():
                    f.write(f"  • {issue_type}: {count}\n")
            else:
                f.write("✓ No issues found!\n")

            f.write("\n\nDETAILED FINDINGS\n")
            f.write("=" * 80 + "\n\n")

            for page_name, page_data in self.report["pages"].items():
                f.write(f"\nPage: {page_name}\n")
                f.write(f"URL: {page_data['url']}\n")
                f.write(f"Screenshot: {page_data['screenshot']}\n")
                f.write(f"Issues Found: {len(page_data['issues'])}\n")

                if page_data['issues']:
                    f.write("\nIssues:\n")
                    for i, issue in enumerate(page_data['issues'], 1):
                        f.write(f"\n  {i}. {issue['element']}\n")
                        f.write(f"     Issue: {issue['issue']}\n")
                        if 'computed_style' in issue:
                            f.write(f"     Computed Style: {json.dumps(issue['computed_style'], indent=6)}\n")
                        if 'details' in issue:
                            f.write(f"     Details: {json.dumps(issue['details'], indent=6)}\n")
                else:
                    f.write("  ✓ No issues detected\n")

                f.write("\n" + "-" * 80 + "\n")

        print(f"  ✓ Text report saved: {text_report_path.name}")

        return text_report_path

    def print_summary(self):
        """Print summary to console"""
        print(f"\n[6/7] Summary")
        print("=" * 80)
        print(f"✓ Captured {self.report['summary']['total_pages_captured']} pages")
        print(f"✓ Found {self.report['summary']['total_issues_found']} issues")

        if self.report['summary']['issues_by_type']:
            print("\nIssues by Type:")
            for issue_type, count in self.report['summary']['issues_by_type'].items():
                print(f"  • {issue_type}: {count}")
        else:
            print("\n✓ No CSS issues detected!")

        print(f"\nScreenshots saved to: {self.screenshots_dir}")
        print("=" * 80)

    def run(self):
        """Run complete diagnostic suite"""
        try:
            print("\n" + "=" * 80)
            print("EMAIL MANAGEMENT TOOL - UI DIAGNOSTICS")
            print("=" * 80)

            self.login()
            self.capture_dashboard()
            self.capture_accounts()
            self.capture_rules()
            report_path = self.generate_report()
            self.print_summary()

            print(f"\n[7/7] Complete!")
            print(f"\nFull report available at: {report_path}")

            return True

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            print("\n[Cleanup] Closing browser...")
            self.driver.quit()

def main():
    diagnostics = UIDignostics()
    success = diagnostics.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
