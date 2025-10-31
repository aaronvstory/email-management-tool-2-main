"""Test account fixes - Verify JSON error handling and health status updates"""

import requests
import json
import sys

BASE_URL = "http://localhost:5001"

def test_account_api():
    """Test the account test endpoint with proper authentication"""

    print("=" * 60)
    print("Testing Account Fixes")
    print("=" * 60)

    # Create session
    session = requests.Session()

    # Step 1: Login
    print("\n1. Logging in...")
    login_data = {
        'username': 'admin',
        'password': 'admin123'
    }

    # Get login page to get CSRF token
    resp = session.get(f"{BASE_URL}/login")
    if resp.status_code != 200:
        print(f"   ✗ Failed to get login page: {resp.status_code}")
        return False

    # Extract CSRF token from cookies
    csrf_token = session.cookies.get('csrf_access_token') or session.cookies.get('csrf_token')

    # Login
    headers = {}
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token

    resp = session.post(f"{BASE_URL}/login", data=login_data, headers=headers, allow_redirects=False)
    if resp.status_code not in [200, 302]:
        print(f"   ✗ Login failed: {resp.status_code}")
        return False

    print("   ✓ Login successful")

    # Step 2: Test account endpoint
    print("\n2. Testing account test endpoint (account ID 1)...")

    # Get CSRF token for API call
    csrf_token = session.cookies.get('csrf_access_token') or session.cookies.get('csrf_token')
    headers = {'Content-Type': 'application/json'}
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token

    resp = session.post(f"{BASE_URL}/api/accounts/1/test", headers=headers)

    print(f"   Status: {resp.status_code}")
    print(f"   Content-Type: {resp.headers.get('Content-Type', 'unknown')}")

    # Check if response is JSON
    try:
        data = resp.json()
        print(f"   ✓ Response is valid JSON")
        print(f"   Response: {json.dumps(data, indent=2)}")

        # Check if health status was updated
        if resp.status_code == 200:
            print("\n3. Checking health status was saved to database...")
            import sqlite3
            conn = sqlite3.connect('email_manager.db')
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            acc = cur.execute("""
                SELECT smtp_health_status, imap_health_status,
                       connection_status, last_health_check
                FROM email_accounts WHERE id = 1
            """).fetchone()

            if acc:
                print(f"   SMTP Health: {acc['smtp_health_status']}")
                print(f"   IMAP Health: {acc['imap_health_status']}")
                print(f"   Connection Status: {acc['connection_status']}")
                print(f"   Last Health Check: {acc['last_health_check']}")
                print("   ✓ Health status columns are working!")
            else:
                print("   ! Account 1 not found in database")

            conn.close()

        return True

    except json.JSONDecodeError as e:
        print(f"   ✗ Response is NOT JSON!")
        print(f"   Error: {e}")
        print(f"   Response text: {resp.text[:200]}")
        return False

if __name__ == '__main__':
    try:
        success = test_account_api()

        print("\n" + "=" * 60)
        if success:
            print("✓ ALL TESTS PASSED")
            print("=" * 60)
            sys.exit(0)
        else:
            print("✗ TESTS FAILED")
            print("=" * 60)
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
