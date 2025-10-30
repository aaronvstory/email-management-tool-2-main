"""
Release Editor - Append edited messages back to inbox

After reviewing and editing intercepted messages, this module
handles releasing them back to the inbox as if they were the original.

Key features:
- APPEND edited MIME to INBOX with original internal date
- Update database with release status
- Preserve message chronology
- Track edited message IDs for audit trail
"""

import time
import sqlite3
import logging
import os
from typing import Optional
from datetime import datetime

try:
    from imapclient import IMAPClient
except ImportError:
    raise ImportError("imapclient required: pip install imapclient")

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'email_manager.db')


def get_db_connection():
    """Get database connection with Row factory"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def append_edited(
    account_id: int,
    message_db_id: int,
    imap_host: str,
    imap_port: int,
    username: str,
    password: str,
    edited_mime_bytes: bytes,
    use_ssl: bool = True,
    original_internaldate: Optional[float] = None,
    new_message_id: Optional[str] = None
) -> bool:
    """
    Append edited message back to INBOX
    
    This function releases an intercepted message by appending the edited
    version to the INBOX. The original remains in quarantine for audit.
    
    Args:
        account_id: Database ID of email account
        message_db_id: Database ID of the intercepted message
        imap_host: IMAP server hostname
        imap_port: IMAP server port
        username: IMAP username
        password: IMAP password
        edited_mime_bytes: Complete MIME message as bytes
        use_ssl: Use SSL/TLS connection
        original_internaldate: Original message timestamp (Unix timestamp)
        new_message_id: Message-ID of edited message
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Releasing message {message_db_id} to INBOX for account {account_id}")
        
        # Connect to IMAP server
        with IMAPClient(imap_host, port=imap_port, ssl=use_ssl) as client:
            client.login(username, password)            
            # Determine message time (use original if provided, otherwise current)
            msg_time = original_internaldate if original_internaldate else time.time()
            
            # Append to INBOX
            logger.debug(f"Appending edited message to INBOX")
            client.append('INBOX', edited_mime_bytes, msg_time=msg_time)
            
            logger.info(f"Successfully appended edited message to INBOX")
        
        # Update database to mark as released
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE email_messages
            SET interception_status = 'RELEASED',
                edited_message_id = ?,
                action_taken_at = datetime('now'),
                status = 'SENT'
            WHERE id = ? AND account_id = ?
        """, (new_message_id, message_db_id, account_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database updated: message {message_db_id} marked as RELEASED")
        return True
        
    except Exception as e:
        logger.error(f"Error releasing message {message_db_id}: {e}", exc_info=True)
        return False

def get_held_message(message_db_id: int) -> Optional[dict]:
    """
    Retrieve held message details from database
    
    Args:
        message_db_id: Database ID of intercepted message
    
    Returns:
        Dictionary with message details or None if not found
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM email_messages
        WHERE id = ? AND direction = 'inbound' AND interception_status = 'HELD'
    """, (message_db_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def build_edited_mime(sender: str, recipients: str, subject: str, 
                     body_text: str, body_html: Optional[str] = None,
                     message_id: Optional[str] = None) -> bytes:
    """
    Build edited MIME message from components
    
    Args:
        sender: From address
        recipients: To addresses (comma-separated)
        subject: Email subject
        body_text: Plain text body
        body_html: HTML body (optional)
        message_id: Custom Message-ID (optional, auto-generated if not provided)
    
    Returns:
        Complete MIME message as bytes
    """
    from email.message import EmailMessage
    import uuid
    
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipients
    msg['Subject'] = subject
    
    if message_id:        msg['Message-ID'] = message_id
    else:
        msg['Message-ID'] = f"<{uuid.uuid4()}@intercepted.local>"
    
    msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    
    # Set body content
    if body_html:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype='html')
    else:
        msg.set_content(body_text)
    
    return msg.as_bytes()