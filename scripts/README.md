# Test Scripts & Utilities

This directory contains testing utilities and automation scripts for the Email Management Tool.

---

## Available Scripts

### 1. `test_interception_flow.sh`

**Purpose:** End-to-end automated test of the complete interception workflow.

**What It Tests:**
- Login authentication
- Watcher startup
- Control email (should NOT be intercepted)
- Keyword email (should be intercepted)
- Email editing
- Release to inbox
- Verification in unified inbox

**Requirements:**
- Bash shell (Git Bash on Windows, native on Linux/Mac)
- `curl` command
- `jq` for JSON parsing
- Running Email Management Tool (http://localhost:5001)
- Email account configured with active watcher

---

## Setup & Configuration

### Step 1: Create Configuration File

```bash
# Copy the example file
cp .env.interception_test.example .env.interception_test

# Edit with your values
```

**Configuration Options:**

```bash
# ============================================================================
# Email Management Tool - Interception Test Configuration
# ============================================================================

# Base URL of running application
BASE_URL=http://localhost:5001

# Login credentials
USERNAME=admin
PASSWORD=admin123

# Account ID to test (from /api/accounts)
ACCOUNT_ID=1

# Keyword to trigger interception (must match active rule)
KEYWORD=invoice

# Polling settings
POLL_INTERVAL=5          # Seconds between checks
POLL_MAX_TRIES=60        # Maximum attempts before timeout

# Cookie storage
COOKIE_JAR=cookie.txt
```

### Step 2: Install Dependencies

**Linux/Mac:**
```bash
# Usually pre-installed
which curl jq

# If missing:
# Ubuntu/Debian
sudo apt-get install curl jq

# Mac
brew install curl jq
```

**Windows (Git Bash):**
```bash
# curl comes with Git Bash
curl --version

# jq download from: https://stedolan.github.io/jq/download/
# Place jq.exe in your PATH or same directory as script
```

### Step 3: Make Script Executable

```bash
chmod +x test_interception_flow.sh
```

---

## Usage

### Basic Usage

```bash
# Run full test
./test_interception_flow.sh
```

**Expected Output:**
```
=== Email Management Tool - Interception Flow Test ===

[1/8] Logging in...
✓ Login successful

[2/8] Starting watcher for account 1...
✓ Watcher started

[3/8] Sending control email (no keyword)...
⏳ Waiting for delivery...
✓ Control email delivered to INBOX (not intercepted)

[4/8] Sending test email with keyword 'invoice'...
⏳ Waiting for interception...
✓ Email intercepted and held

[5/8] Editing held email...
✓ Email edited successfully

[6/8] Releasing edited email...
✓ Email released to INBOX

[7/8] Verifying in unified inbox...
✓ Released email found in inbox

[8/8] Cleanup...
✓ Test completed successfully

=== Summary ===
Total: 8 tests
Passed: 8
Failed: 0
```

### Stop Watcher After Test

```bash
# Manually stop watcher
./test_interception_flow.sh stop_watcher
```

### Debug Mode

```bash
# Enable verbose output
DEBUG=1 ./test_interception_flow.sh
```

---

## Manual API Testing (cURL Examples)

If you prefer manual testing, here's the step-by-step process:

### 1. Login

```bash
curl -c cookie.txt -X POST \
  -d "username=admin" \
  -d "password=admin123" \
  http://localhost:5001/login
```

### 2. List Accounts

```bash
curl -b cookie.txt http://localhost:5001/api/accounts | jq '.'
```

### 3. Start Watcher

```bash
# Replace 1 with your account ID
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/start | jq '.'
```

### 4. Send Test Email

(Use your email client - send TO the monitored inbox with keyword "invoice")

### 5. Check Held Queue

```bash
curl -b cookie.txt http://localhost:5001/api/interception/held | jq '.emails[0]'
```

### 6. Get Email ID

```bash
# From previous response, note the "id" field
EMAIL_ID=42  # Replace with actual ID
```

### 7. Edit Email

```bash
curl -b cookie.txt -H "Content-Type: application/json" -X POST \
  -d '{
    "subject": "[REVIEWED] Updated Subject",
    "body_text": "Cleaned body content"
  }' \
  "http://localhost:5001/api/email/${EMAIL_ID}/edit" | jq '.'
```

### 8. Release Email

```bash
curl -b cookie.txt -H "Content-Type: application/json" -X POST \
  -d '{"edited_subject": "[REVIEWED] Final", "edited_body": "Final text"}' \
  "http://localhost:5001/api/interception/release/${EMAIL_ID}" | jq '.'
```

### 9. Verify in Inbox

```bash
curl -b cookie.txt "http://localhost:5001/api/inbox?status=RELEASED" | jq '.messages[0]'
```

### 10. Check Health

```bash
curl http://localhost:5001/healthz | jq '.'
```

---

## Troubleshooting Test Script Failures

### Error: "jq: command not found"

**Cause:** `jq` JSON processor not installed

**Fix:**
```bash
# Ubuntu/Debian
sudo apt-get install jq

# Mac
brew install jq

# Windows: Download from https://stedolan.github.io/jq/download/
```

### Error: "Connection refused"

**Cause:** Email Management Tool not running

**Fix:**
```bash
# In another terminal
python simple_app.py

# Wait for "Running on http://127.0.0.1:5001"
# Then re-run test
```

### Error: "401 Unauthorized"

**Cause:** Login failed or session expired

**Fix:**
```bash
# Check credentials in .env.interception_test
# Default: admin / admin123

# Delete old cookies
rm cookie.txt

# Re-run test
```

### Error: "Watcher already running"

**Cause:** Previous test didn't clean up properly

**Fix:**
```bash
# Stop watcher manually
./test_interception_flow.sh stop_watcher

# Or via API
curl -b cookie.txt -X POST \
  http://localhost:5001/api/accounts/1/monitor/stop
```

### Error: "Email not intercepted"

**Cause:** Rule not active or keyword mismatch

**Fix:**
1. Check Rules page - ensure rule is "Active"
2. Verify keyword in `.env.interception_test` matches rule pattern
3. Check watcher status in Watchers page (should be "IDLE" or "POLLING")
4. Test with simple keyword like "test" first

### Warning: "Poll timeout"

**Cause:** Email took longer than expected to process

**Fix:**
```bash
# Increase timeout in .env.interception_test
POLL_MAX_TRIES=120  # 120 * 5s = 10 minutes max wait
```

---

## Advanced Usage

### Custom Test Scenarios

**Test 1: Attachment Stripping**

```bash
EMAIL_ID=42

# Release with attachment removal
curl -b cookie.txt -H "Content-Type: application/json" -X POST \
  -d '{"strip_attachments": true}' \
  "http://localhost:5001/api/interception/release/${EMAIL_ID}"
```

**Test 2: Discard Instead of Release**

```bash
EMAIL_ID=42

# Discard email permanently
curl -b cookie.txt -X POST \
  "http://localhost:5001/api/interception/discard/${EMAIL_ID}"
```

**Test 3: Batch Operations**

```bash
# Get all held emails
HELD_IDS=$(curl -s -b cookie.txt http://localhost:5001/api/interception/held | \
  jq -r '.emails[].id')

# Release all at once
for id in $HELD_IDS; do
  curl -s -b cookie.txt -X POST \
    "http://localhost:5001/api/interception/release/$id"
done
```

### CI/CD Integration

**GitHub Actions Example:**

```yaml
name: Integration Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          sudo apt-get install -y jq

      - name: Start application
        run: |
          python simple_app.py &
          sleep 10

      - name: Run interception test
        run: |
          cd scripts
          chmod +x test_interception_flow.sh
          ./test_interception_flow.sh
```

---

## Script Maintenance

### Updating Test Credentials

```bash
# Edit configuration
nano .env.interception_test

# Change account ID if testing different account
ACCOUNT_ID=2

# Change keyword if testing different rule
KEYWORD=urgent
```

### Adding New Test Cases

Edit `test_interception_flow.sh` and add functions:

```bash
test_new_feature() {
  echo "[X/Y] Testing new feature..."

  # Your test logic here
  curl -b $COOKIE_JAR ...

  if [ $? -eq 0 ]; then
    echo "✓ New feature test passed"
  else
    echo "✗ New feature test failed"
    exit 1
  fi
}

# Add to main test sequence
main() {
  test_login
  test_start_watcher
  test_new_feature  # <-- Add here
  test_cleanup
}
```

---

## Related Documentation

- [API Reference](../docs/API_REFERENCE.md) - Complete API documentation
- [User Guide](../docs/USER_GUIDE.md) - Step-by-step workflows
- [Troubleshooting](../docs/TROUBLESHOOTING.md) - Common issues

---

**Last Updated**: October 18, 2025
