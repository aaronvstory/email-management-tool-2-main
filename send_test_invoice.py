"""
Send a test email with 'invoice' keyword using the /api/test/send-email endpoint
"""
import requests
import time
import sqlite3
from datetime import datetime

# First login to get session
session = requests.Session()
login_resp = session.post('http://127.0.0.1:5001/login', data={
    'username': 'admin',
    'password': 'admin123'
})

if 'login' in login_resp.url.lower():
    print("❌ Login failed!")
    exit(1)

print("✅ Logged in successfully\n")

# Get account IDs
conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
accounts = cur.execute("SELECT id, email_address FROM email_accounts WHERE is_active=1").fetchall()

gmail_id = None
corrinbox_id = None

for acc in accounts:
    if 'ndayijecika@gmail.com' in acc['email_address']:
        gmail_id = acc['id']
    elif 'mcintyre@corrinbox.com' in acc['email_address']:
        corrinbox_id = acc['id']

print(f"Gmail account ID: {gmail_id}")
print(f"Corrinbox account ID: {corrinbox_id}\n")

if not gmail_id or not corrinbox_id:
    print("❌ Could not find both accounts!")
    conn.close()
    exit(1)

# Get count before sending
before_count = cur.execute("SELECT COUNT(*) as c FROM email_messages").fetchone()['c']
conn.close()

# Send test email
test_subject = f"TEST INVOICE #{int(time.time())}"
print(f"📧 Sending test email...")
print(f"   Subject: {test_subject}")
print(f"   From: Gmail (ID {gmail_id})")
print(f"   To: Corrinbox (ID {corrinbox_id})\n")

resp = session.post('http://127.0.0.1:5001/api/test/send-email', json={
    'from_account_id': gmail_id,
    'to_account_id': corrinbox_id,
    'subject': test_subject,
    'body': 'This is a test email to verify that the invoice keyword triggers interception.'
})

print(f"API Response: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"  {data}\n")
    
    if data.get('success'):
        print("✅ Email sent via SMTP proxy!")
        print("\n⏳ Waiting 30 seconds for IMAP watcher to fetch...\n")
        time.sleep(30)
        
        # Check if email was intercepted
        conn = sqlite3.connect('email_manager.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        new_emails = cur.execute("""
            SELECT id, subject, interception_status, risk_score, keywords_matched
            FROM email_messages
            WHERE id > ?
            ORDER BY id DESC
        """, (before_count,)).fetchall()
        
        print(f"🔍 New emails since test: {len(new_emails)}\n")
        
        for email in new_emails:
            print(f"📧 Email ID {email['id']}: {email['subject']}")
            print(f"   Status: {email['interception_status']}")
            print(f"   Risk: {email['risk_score']}")
            print(f"   Keywords: {email['keywords_matched']}")
            
            if email['interception_status'] == 'INTERCEPTED':
                print(f"   ✅ SUCCESS! Email was intercepted!")
            else:
                print(f"   ❌ FAILED! Email was {email['interception_status']}, not INTERCEPTED")
            print()
        
        conn.close()
    else:
        print(f"❌ Failed to send: {data}")
else:
    print(f"❌ Request failed: {resp.text}")
