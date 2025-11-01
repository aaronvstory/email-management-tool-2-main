#!/usr/bin/env python3
"""
Send test email to prove interception works.
Simplified version without app imports.
"""
import smtplib
import time
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Hostinger SMTP settings
SMTP_HOST = 'smtp.hostinger.com'
SMTP_PORT = 465
EMAIL = 'mcintyre@corrinbox.com'
import os
PASSWORD = os.environ.get('EMAIL_PASSWORD')
if not PASSWORD:
    raise ValueError("EMAIL_PASSWORD environment variable not set")

DB_PATH = 'email_manager.db'

def send_test_email():
    """Send test email with invoice keyword"""
    timestamp = int(time.time())
    subject = f'PROOF TEST INVOICE #{timestamp}'

    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = EMAIL
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
    print(f"   From: {EMAIL}")
    print(f"   To: {EMAIL}")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(EMAIL, PASSWORD)
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
        if (i + 1) % 10 == 0:
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
        conn.close()
        return False

    email_id = result['id']
    interception_status = result['interception_status']
    risk_score = result['risk_score']
    keywords = result['keywords_matched']

    print(f"\n📊 DATABASE PROOF:")
    print(f"   ID: {email_id}")
    print(f"   Subject: {result['subject']}")
    print(f"   Interception Status: {interception_status}")
    print(f"   Risk Score: {risk_score}")
    print(f"   Keywords Matched: {keywords}")
    print(f"   Created At: {result['created_at']}")

    # Verify expectations
    success = (
        interception_status == 'INTERCEPTED' and
        risk_score == 75 and
        'invoice' in (keywords or '').lower()
    )

    conn.close()

    if success:
        print(f"\n✅✅✅ SUCCESS! Email WAS intercepted correctly! ✅✅✅")
        print(f"\nSQL PROOF:")
        print(f"SELECT id, subject, interception_status, risk_score, keywords_matched")
        print(f"FROM email_messages WHERE id = {email_id};")
        return True
    else:
        print(f"\n❌ FAILURE - Email was NOT intercepted correctly")
        expected = "INTERCEPTED / risk=75 / keywords=['invoice']"
        actual = f"{interception_status} / risk={risk_score} / keywords={keywords}"
        print(f"   Expected: {expected}")
        print(f"   Actual: {actual}")
        return False

if __name__ == '__main__':
    subject = send_test_email()
    if subject:
        verify_interception(subject, wait_time=60)
