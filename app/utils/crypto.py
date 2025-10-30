"""Encryption utilities for credential management"""
from cryptography.fernet import Fernet, InvalidToken
import os
import logging
from functools import lru_cache
from typing import Optional

log = logging.getLogger(__name__)

KEY_FILE = "key.txt"

@lru_cache(maxsize=1)
def get_encryption_key() -> bytes:
    """Get or generate encryption key for passwords"""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key
    with open(KEY_FILE, "rb") as f:
        content = f.read().strip()
        # Handle both plain key and key with prefix
        if b'Generated encryption key:' in content:
            content = content.split(b':')[-1].strip()
        return content

def get_cipher() -> Fernet:
    """Get Fernet cipher instance"""
    return Fernet(get_encryption_key())

def encrypt_credential(text: Optional[str]) -> Optional[str]:
    """Encrypt credential text"""
    if text is None:
        return None
    return get_cipher().encrypt(text.encode("utf-8")).decode("utf-8")

def decrypt_credential(encrypted_text: Optional[str]) -> Optional[str]:
    """Decrypt credential text"""
    if not encrypted_text:
        return None
    try:
        return get_cipher().decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        log.warning(f"Failed to decrypt credential (invalid token or corrupted data): {e}")
        return None
    except (ValueError, UnicodeDecodeError) as e:
        log.warning(f"Failed to decrypt credential (encoding error): {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected decryption error: {e}", exc_info=True)
        return None