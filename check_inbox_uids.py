from imapclient import IMAPClient
import sqlite3
from app.utils.crypto import decrypt_credential

conn = sqlite3.connect('email_manager.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

account = cur.execute("""
    SELECT * FROM email_accounts
    WHERE email_address = 'mcintyre@corrinbox.com'
""").fetchone()

if not account:
    print("Account not found!")
    exit(1)

# Get latest UID from DB
latest_db = cur.execute("""
    SELECT MAX(original_uid) as max_uid FROM email_messages
    WHERE account_id = ?
""", (account['id'],)).fetchone()

max_db_uid = latest_db['max_uid'] or 0

print(f"Latest UID in DB: {max_db_uid}")

# Decrypt credentials
username = decrypt_credential(account['imap_username'])
password = decrypt_credential(account['imap_password'])

# Connect to IMAP
print(f"Connecting to {account['imap_host']}...")
client = IMAPClient(account['imap_host'], port=account['imap_port'], ssl=bool(account['imap_use_ssl']))
client.login(username, password)
client.select_folder('INBOX')

# Get all UIDs
uids = client.search('ALL')
print(f"\nTotal emails in INBOX: {len(uids)}")
print(f"UID range: {min(uids)} - {max(uids)}")

if max(uids) > max_db_uid:
    unfetched_uids = [uid for uid in uids if uid > max_db_uid]
    print(f"\n🚨 UNFETCHED EMAILS: {len(unfetched_uids)} emails (UIDs {min(unfetched_uids)}-{max(unfetched_uids)})")
    
    # Get subjects
    fetch_data = client.fetch(unfetched_uids, ['ENVELOPE'])
    print(f"\nUnfetched email details:")
    for uid in sorted(unfetched_uids):
        data = fetch_data[uid]
        envelope = data[b'ENVELOPE']
        subject = envelope.subject.decode() if envelope.subject else "(no subject)"
        from_addr = str(envelope.from_[0]) if envelope.from_ else "unknown"
        print(f"  UID {uid}: {subject} (from: {from_addr})")
        
        # Check if has invoice
        if 'invoice' in subject.lower():
            print(f"    ⚠️  THIS EMAIL SHOULD HAVE BEEN INTERCEPTED!")
else:
    print(f"\n✅ No unfetched emails. DB is up to date.")

client.logout()
conn.close()
