"""
Send test email from mcintyre to mcintyre (self-send) with 'invoice' keyword
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
import time
import sqlite3
from app.utils.crypto import decrypt_credential

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get mcintyre account
account = cur.execute("""
    SELECT * FROM email_accounts
    WHERE id = 2
""").fetchone()

username = decrypt_credential(account['smtp_username'])
password = decrypt_credential(account['smtp_password'])

# Create email
msg = MIMEMultipart()
msg['From'] = account['email_address']
msg['To'] = account['email_address']
subject = f'PROOF TEST INVOICE #{int(time.time())}'
msg['Subject'] = subject
msg['Date'] = formatdate()
msg['Message-ID'] = make_msgid()

body = f"""This is a PROOF TEST to verify email interception is working.

This email contains the keyword 'invoice' and should be INTERCEPTED with:
- interception_status = 'INTERCEPTED'  
- risk_score = 75
- keywords_matched = ['invoice']

Sent at: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""

msg.attach(MIMEText(body, 'plain'))

print(f"📧 Sending test email (self-send)...")
print(f"  From/To: {account['email_address']}")
print(f"  Subject: {subject}")
print(f"  Via: {account['smtp_host']}:{account['smtp_port']}")

try:
    # Connect to SMTP
    if account['smtp_use_ssl'] and account['smtp_port'] == 465:
        smtp = smtplib.SMTP_SSL(account['smtp_host'], account['smtp_port'], timeout=10)
    else:
        smtp = smtplib.SMTP(account['smtp_host'], account['smtp_port'], timeout=10)
        if account['smtp_use_ssl']:
            smtp.starttls()
    
    smtp.login(username, password)
    smtp.send_message(msg)
    smtp.quit()
    
    print(f"\n✅ Email sent successfully!")
    print(f"\n⏳ Waiting 45 seconds for IMAP watcher to fetch and process...")
    
    time.sleep(45)
    
    # Check database
    print(f"\n🔍 Checking database for intercepted email...")
    conn2 = sqlite3.connect('email_manager.db')
    conn2.row_factory = sqlite3.Row
    cur2 = conn2.cursor()
    
    latest = cur2.execute("""
        SELECT id, subject, interception_status, risk_score, keywords_matched, created_at
        FROM email_messages
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    
    print(f"\n📧 Latest email in database:")
    print(f"  ID: {latest['id']}")
    print(f"  Subject: {latest['subject']}")
    print(f"  Status: {latest['interception_status']}")
    print(f"  Risk: {latest['risk_score']}")
    print(f"  Keywords: {latest['keywords_matched']}")
    print(f"  Created: {latest['created_at']}")
    
    if 'PROOF TEST INVOICE' in latest['subject']:
        print(f"\n✅ Found our test email!")
        if latest['interception_status'] == 'INTERCEPTED' and latest['risk_score'] == 75:
            print(f"\n🎉🎉🎉 SUCCESS! Email WAS intercepted correctly! 🎉🎉🎉")
            print(f"\n✅ PROOF OF INTERCEPTION:")
            print(f"  - interception_status = '{latest['interception_status']}' ✅")
            print(f"  - risk_score = {latest['risk_score']} ✅")
            print(f"  - keywords_matched = {latest['keywords_matched']} ✅")
            print(f"\n📊 SQL PROOF:")
            print(f"  SELECT id, subject, interception_status, risk_score, keywords_matched")
            print(f"  FROM email_messages WHERE id = {latest['id']};")
        else:
            print(f"\n❌ FAILED! Email was NOT intercepted:")
            print(f"  - interception_status = '{latest['interception_status']}' (should be 'INTERCEPTED')")
            print(f"  - risk_score = {latest['risk_score']} (should be 75)")
            print(f"  - keywords_matched = {latest['keywords_matched']} (should be ['invoice'])")
    else:
        print(f"\n⚠️  Latest email is not our test email. May need to wait longer or check manually.")
        print(f"\nSearch for subject: {subject}")
    
    conn2.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

conn.close()
