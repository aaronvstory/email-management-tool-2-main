import requests
import json

# Create session and login
session = requests.Session()
login_resp = session.post('http://localhost:5001/login', data={
    'username': 'admin',
    'password': 'admin123'
}, allow_redirects=False)

print(f"Login response: {login_resp.status_code}")

# Test unified-stats API
print("\n=== Testing /api/unified-stats ===")
stats_resp = session.get('http://localhost:5001/api/unified-stats')
print(f"Status Code: {stats_resp.status_code}")

if stats_resp.status_code == 200:
    print(f"Response text (first 500 chars): {stats_resp.text[:500]}")
    try:
        data = stats_resp.json()
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Response headers: {dict(stats_resp.headers)}")
        data = None

    if data:
        print("\n=== Badge Counts Calculation ===")
        total = data.get('total', 0)
        held = data.get('held', 0)
        released = data.get('released', 0)
        rejected = data.get('rejected', 0)
        discarded = data.get('discarded', 0)

        # This is what JavaScript calculates for REJECTED badge
        rejected_badge = rejected + discarded

        print(f"ALL badge: {total}")
        print(f"HELD badge: {held}")
        print(f"RELEASED badge: {released}")
        print(f"REJECTED badge: {rejected} + {discarded} = {rejected_badge}")

        print("\n=== Expected Values ===")
        print("ALL: 417 (or similar)")
        print("HELD: Should match database")
        print("RELEASED: Should match database")
        print("REJECTED: Should be 269 (0 + 269)")
else:
    print(f"Error: {stats_resp.text[:200]}")
