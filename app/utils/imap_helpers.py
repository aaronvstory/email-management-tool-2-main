"""
IMAP Helper Functions

Extracted from simple_app.py to eliminate circular dependencies in blueprints.
Provides IMAP connection, quarantine management, and message moving utilities.
"""

import imaplib
from typing import Tuple, Optional

from app.utils.crypto import decrypt_credential


def _imap_connect_account(account_row) -> Tuple[imaplib.IMAP4, bool]:
    """Connect to IMAP account and return (imap_obj, supports_move)"""
    host = account_row['imap_host']
    port = int(account_row['imap_port'] or 993)
    username = account_row['imap_username']
    password = decrypt_credential(account_row['imap_password'])
    if not (host and username and password):
        raise RuntimeError("Missing IMAP credentials")
    if port == 993:
        imap_obj = imaplib.IMAP4_SSL(host, port)
    else:
        imap_obj = imaplib.IMAP4(host, port)
        try:
            imap_obj.starttls()
        except Exception:
            pass
    pwd: str = password  # type: ignore[assignment]
    imap_obj.login(username, pwd)
    try:
        typ, caps = imap_obj.capability()
        supports_move = any(b'MOVE' in c.upper() for c in caps) if isinstance(caps, list) else False
    except Exception:
        supports_move = False
    return imap_obj, supports_move


def _ensure_quarantine(imap_obj: imaplib.IMAP4, folder_name: str = "Quarantine") -> str:
    """Ensure a quarantine folder exists and return the effective mailbox name."""
    candidates = [folder_name]
    candidates.extend([
        f"INBOX/{folder_name}",
        f"INBOX.{folder_name}"
    ])
    seen = []
    variations = []
    for candidate in candidates:
        if candidate not in seen:
            seen.append(candidate)
            variations.append(candidate)

    original_mailbox = 'INBOX'
    try:
        imap_obj.select(original_mailbox)
    except Exception:
        original_mailbox = None  # leave as-is if selection fails

    for candidate in variations:
        try:
            typ, _ = imap_obj.select(candidate)
            if typ == 'OK':
                if original_mailbox:
                    try:
                        imap_obj.select(original_mailbox)
                    except Exception:
                        pass
                return candidate
        except Exception:
            try:
                imap_obj.create(candidate)
                typ, _ = imap_obj.select(candidate)
                if typ == 'OK':
                    if original_mailbox:
                        try:
                            imap_obj.select(original_mailbox)
                        except Exception:
                            pass
                    return candidate
            except Exception:
                continue

    if original_mailbox:
        try:
            imap_obj.select(original_mailbox)
        except Exception:
            pass
    return folder_name


def _move_uid_to_quarantine(imap_obj: imaplib.IMAP4, uid: str, quarantine: str = "Quarantine") -> bool:
    """Move message to quarantine using MOVE or COPY+DELETE fallback"""
    target_folder = _ensure_quarantine(imap_obj, quarantine) or quarantine
    uid_str = str(uid)
    try:
        imap_obj.select('INBOX')
    except Exception:
        pass

    try:
        typ, _ = imap_obj.uid('MOVE', uid_str, target_folder)
        if typ == 'OK':
            return True
    except Exception:
        pass

    try:
        typ, _ = imap_obj.uid('COPY', uid_str, target_folder)
        if typ == 'OK':
            try:
                imap_obj.uid('STORE', uid_str, '+FLAGS', r'(\Deleted)')
            except Exception:
                pass
            try:
                imap_obj.expunge()
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False