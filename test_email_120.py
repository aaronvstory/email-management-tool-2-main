import requests
import time

# Create session and login
session = requests.Session()
login_resp = session.post('http://localhost:5000/login', data={
    'username': 'admin',
    'password': 'admin123'
}, allow_redirects=False)

print(f"Login response: {login_resp.status_code}")

# Test with non-existent email ID 120
print("\n=== Testing Release API with non-existent email ID 120 ===")
release_resp = session.post('http://localhost:5000/api/interception/release/120', 
                            json={},
                            headers={'Content-Type': 'application/json'})

print(f"Status Code: {release_resp.status_code}")
print(f"Response Headers: {dict(release_resp.headers)}")

# Check if it's JSON or HTML
if 'application/json' in release_resp.headers.get('Content-Type', ''):
    print(f"JSON Response: {release_resp.json()}")
else:
    print(f"HTML Response (first 200 chars): {release_resp.text[:200]}")

# Wait a moment for logs to flush
time.sleep(1)

# Now check the logs
print("\n=== Checking application logs ===")
with open('logs/app.log', 'r') as f:
    lines = f.readlines()
    # Get last 30 lines
    for line in lines[-30:]:
        if 'release' in line.lower() or '120' in line or 'ERROR' in line:
            print(line.strip())
