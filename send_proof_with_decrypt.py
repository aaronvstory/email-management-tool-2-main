#!/usr/bin/env python3
"""
Send test email with proper credential decryption
"""
import smtplib
import time
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet

DB_PATH = 'email_manager.db'
KEY_FILE = 'key.txt'

def load_key():
    """Load encryption key"""
    with open(KEY_FILE, 'rb') as f:
        return f.read()

def decrypt_credential(encrypted_data: str) -> str:
    """Decrypt a credential"""
    key = load_key()
    cipher = Fernet(key)
    return cipher.decrypt(encrypted_data.encode()).decode()

def get_account_credentials():
    """Get decrypted credentials from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    result = cursor.execute("""
        SELECT smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_ssl
        FROM email_accounts
        WHERE email_address = ?
    """, ('mcintyre@corrinbox.com',)).fetchone()
    
    if not result:
        raise Exception("Account not found")
    
    smtp_pass = decrypt_credential(result['smtp_password'])
    conn.close()
    
    return {
        'host': result['smtp_host'],
        'port': result['smtp_port'],
        'username': result['smtp_username'],
        'password': smtp_pass,
        'use_ssl': bool(result['smtp_use_ssl'])
    }

def send_test_email():
    """Send test email with invoice keyword"""
    creds = get_account_credentials()
    
    timestamp = int(time.time())
    subject = f'PROOF TEST INVOICE #{timestamp}'
    
    msg = MIMEMultipart()
    msg['From'] = creds['username']
    msg['To'] = creds['username']
    msg['Subject'] = subject
    
    body = f"""This email contains the keyword 'invoice' and should be INTERCEPTED with:
- interception_status = 'INTERCEPTED'
- risk_score = 75
- keywords_matched = ['invoice']

Timestamp: {timestamp}
Test: Proof that ENABLE_WATCHERS=1 fix works
"""
    msg.attach(MIMEText(body, 'plain'))
    
    print(f"\n📧 Sending test email...")
    print(f"   Subject: {subject}")
    print(f"   From: {creds['username']}")
    print(f"   To: {creds['username']}")
    print(f"   SMTP: {creds['host']}:{creds['port']} (SSL={creds['use_ssl']})")
    
    try:
        if creds['use_ssl'] and creds['port'] == 465:
            with smtplib.SMTP_SSL(creds['host'], creds['port']) as server:
                server.login(creds['username'], creds['password'])
                server.send_message(msg)
        else:
            with smtplib.SMTP(creds['host'], creds['port']) as server:
                if creds['port'] == 587:
                    server.starttls()
                server.login(creds['username'], creds['password'])
                server.send_message(msg)
        
        print(f"✅ Email sent successfully at {time.strftime('%H:%M:%S')}")
        return subject
    except Exception as e:
        print(f"❌ Failed to send: {e}")
        return None

def verify_interception(subject, wait_time=60):
    """Check database for intercepted email"""
    print(f"\n⏳ Waiting {wait_time} seconds for IMAP watcher to fetch and process...")
    
    for i in range(wait_time):
        time.sleep(1)
        if (i + 1) % 15 == 0:
            print(f"   {i + 1}s elapsed...")
    
    print(f"\n🔍 Checking database for email with subject: {subject}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find the email
    result = cursor.execute("""
        SELECT id, subject, interception_status, risk_score, keywords_matched, created_at
        FROM email_messages
        WHERE subject = ?
        ORDER BY id DESC LIMIT 1
    """, (subject,)).fetchone()
    
    if not result:
        print(f"❌ Email not found in database yet")
        # Check latest emails
        latest = cursor.execute("""
            SELECT id, subject, interception_status, created_at
            FROM email_messages
            ORDER BY id DESC LIMIT 5
        """).fetchall()
        print(f"\n📋 Latest 5 emails in DB:")
        for row in latest:
            print(f"   ID {row['id']}: {row['subject']} [{row['interception_status']}] at {row['created_at']}")
        conn.close()
        return False
    
    email_id = result['id']
    interception_status = result['interception_status']
    risk_score = result['risk_score']
    keywords = result['keywords_matched']
    
    print(f"\n" + "="*70)
    print(f"📊 DATABASE PROOF - Email ID: {email_id}")
    print(f"="*70)
    print(f"   Subject: {result['subject']}")
    print(f"   Interception Status: {interception_status}")
    print(f"   Risk Score: {risk_score}")
    print(f"   Keywords Matched: {keywords}")
    print(f"   Created At: {result['created_at']}")
    print(f"="*70)
    
    # Verify expectations
    success = (
        interception_status == 'INTERCEPTED' and
        risk_score == 75 and
        'invoice' in (keywords or '').lower()
    )
    
    conn.close()
    
    if success:
        print(f"\n🎉🎉🎉 SUCCESS! Email WAS intercepted correctly! 🎉🎉🎉")
        print(f"\n📝 SQL PROOF QUERY:")
        print(f"SELECT id, subject, interception_status, risk_score, keywords_matched")
        print(f"FROM email_messages WHERE id = {email_id};")
        print(f"\n✅ VERIFICATION COMPLETE - Interception fix is WORKING!")
        return True
    else:
        print(f"\n❌ FAILURE - Email was NOT intercepted correctly")
        expected = "INTERCEPTED / risk=75 / keywords=['invoice']"
        actual = f"{interception_status} / risk={risk_score} / keywords={keywords}"
        print(f"   Expected: {expected}")
        print(f"   Actual: {actual}")
        return False

if __name__ == '__main__':
    print("="*70)
    print("PROOF TEST: Email Interception with ENABLE_WATCHERS=1")
    print("="*70)
    
    subject = send_test_email()
    if subject:
        success = verify_interception(subject, wait_time=60)
        exit(0 if success else 1)
    else:
        exit(1)
