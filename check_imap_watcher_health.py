"""
Check if IMAP watcher is actually running and processing emails
"""
import sqlite3
import time
from datetime import datetime, timedelta

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 80)
print("IMAP WATCHER HEALTH CHECK")
print("=" * 80)

# Check account status
account = cur.execute("""
    SELECT id, email_address, imap_health_status, last_health_check,
           last_successful_connection, last_checked
    FROM email_accounts
    WHERE email_address = 'mcintyre@corrinbox.com'
""").fetchone()

if not account:
    print("\n❌ Account mcintyre@corrinbox.com NOT FOUND!")
    conn.close()
    exit(1)

print(f"\n📧 Account: {account['email_address']}")
print(f"  ID: {account['id']}")
print(f"  IMAP Health: {account['imap_health_status']}")
print(f"  Last Health Check: {account['last_health_check']}")
print(f"  Last Successful Connection: {account['last_successful_connection']}")
print(f"  Last Checked: {account['last_checked']}")

# Check latest email for this account
latest = cur.execute("""
    SELECT id, subject, created_at, original_uid
    FROM email_messages
    WHERE account_id = ?
    ORDER BY id DESC
    LIMIT 1
""", (account['id'],)).fetchone()

if latest:
    print(f"\n📬 Latest email from this account:")
    print(f"  ID: {latest['id']}")
    print(f"  Subject: {latest['subject']}")
    print(f"  UID: {latest['original_uid']}")
    print(f"  Created: {latest['created_at']}")
    
    # Time since last email
    if latest['created_at']:
        try:
            created = datetime.fromisoformat(latest['created_at'])
            age = datetime.now() - created
            print(f"  Age: {age}")
            
            if age > timedelta(minutes=10):
                print(f"\n⚠️  No new emails in {age}!")
                print(f"     Possible issues:")
                print(f"     - IMAP watcher not running")
                print(f"     - No new emails in inbox")
                print(f"     - Watcher stuck/crashed")
        except:
            pass

conn.close()

# Check if we can query the watcher status via API
print(f"\n🔍 Checking IMAP watcher via API...")
import requests

try:
    # Try to get watcher status
    session = requests.Session()
    
    # First try without login (might be public endpoint)
    resp = session.get('http://127.0.0.1:5001/api/smtp-health', timeout=5)
    print(f"  SMTP Health: HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"    {data}")
except Exception as e:
    print(f"  ❌ Failed: {e}")

print(f"\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

print(f"""
1. **Check if emails are in Gmail inbox:**
   - Log into ndayijecika@gmail.com
   - Check SENT folder - did emails actually send?
   
2. **Check if emails are in Corrinbox inbox:**
   - Log into mcintyre@corrinbox.com  
   - Check if test emails with "invoice" arrived
   
3. **Check IMAP watcher is fetching:**
   - Look for latest UID in mcintyre inbox
   - Compare with DB UID (currently {latest['original_uid'] if latest else 'N/A'})
   
4. **Force manual fetch test:**
   - Restart app to trigger fresh IMAP fetch
   - Or check logs for IMAP errors
""")

print(f"\n💡 To verify IMAP watcher is working:")
print(f"   Run: tail -f server5001.log | grep -i 'IMAP\\|watcher\\|UID'")
