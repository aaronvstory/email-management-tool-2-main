"""
Send test email with 'invoice' keyword via SMTP to trigger interception
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
import time

# Create email
msg = MIMEMultipart()
msg['From'] = 'ndayijecika@gmail.com'
msg['To'] = 'mcintyre@corrinbox.com'
msg['Subject'] = f'PROOF TEST INVOICE #{int(time.time())}'
msg['Date'] = formatdate()
msg['Message-ID'] = make_msgid()

body = """This is a test email to prove that email interception is now working.

This email contains the keyword 'invoice' and should be INTERCEPTED with:
- interception_status = 'INTERCEPTED'
- risk_score = 75
- keywords_matched = ['invoice']

Sent at: """ + time.strftime('%Y-%m-%d %H:%M:%S')

msg.attach(MIMEText(body, 'plain'))

print(f"📧 Sending test email...")
print(f"  From: {msg['From']}")
print(f"  To: {msg['To']}")
print(f"  Subject: {msg['Subject']}")
print(f"  Via: Gmail SMTP (smtp.gmail.com:587)")

# Send via Gmail SMTP (using app password from DB)
import sqlite3
from app.utils.crypto import decrypt_credential

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get account credentials (matching 'gmail' in address)
account = cur.execute("""
    SELECT smtp_username, smtp_password, smtp_host, smtp_port
    FROM email_accounts
    WHERE email_address LIKE '%gmail%'
    LIMIT 1
""").fetchone()

if not account:
    print("❌ Account with 'gmail' in address not found in database!")
    exit(1)

username = decrypt_credential(account['smtp_username'])
password = decrypt_credential(account['smtp_password'])

try:
    # Connect to SMTP server
    smtp = smtplib.SMTP(account['smtp_host'], account['smtp_port'], timeout=10)
    smtp.starttls()
    smtp.login(username, password)
    smtp.send_message(msg)
    smtp.quit()

    print(f"\n✅ Email sent successfully!")
    print(f"\n⏳ Waiting 45 seconds for IMAP watcher to fetch and process...")

    import time
    time.sleep(45)

    # Check database for the email
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
            print(f"\n🎉 SUCCESS! Email WAS intercepted correctly!")
            print(f"\n✅ PROOF:")
            print(f"  - interception_status = '{latest['interception_status']}' ✅")
            print(f"  - risk_score = {latest['risk_score']} ✅")
            print(f"  - keywords_matched = {latest['keywords_matched']} ✅")
        else:
            print(f"\n❌ FAILED! Email was NOT intercepted:")
            print(f"  - interception_status = '{latest['interception_status']}' (should be 'INTERCEPTED')")
            print(f"  - risk_score = {latest['risk_score']} (should be 75)")
    else:
        print(f"\n⚠️  Latest email is not our test email. May need to wait longer.")

    conn2.close()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

conn.close()
