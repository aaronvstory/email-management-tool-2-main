import requests

# Create session
session = requests.Session()

# Login
login_response = session.post('http://localhost:5001/login', data={
    'username': 'admin',
    'password': 'admin123'
})

print(f"Login status: {login_response.status_code}")

# Test 1: Non-existent email ID
print("\n=== Test 1: Non-existent Email ID 99999 ===")
response = session.post('http://localhost:5001/api/interception/release/99999', json={})
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text[:200]}")

# Test 2: Valid HELD email
print("\n=== Test 2: Valid HELD Email ID 226 ===")
response = session.post('http://localhost:5001/api/interception/release/226', json={})
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text[:500]}")

# Test 3: Check logs for debugging output
print("\n=== Checking logs for debug output ===")
import sqlite3
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
row = cur.execute("SELECT id, subject, interception_status FROM email_messages WHERE id=226").fetchone()
if row:
    print(f"Email 226: {row['subject']}, status={row['interception_status']}")
else:
    print("Email 226 not found!")
conn.close()
