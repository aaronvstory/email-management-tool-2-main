"""
Helper to re-append an edited MIME message back into the user's INBOX.

Usage:
    from app.services.mail_redeliver import append_to_inbox, AccountConfig
    append_to_inbox(cfg, raw_bytes)
"""
from __future__ import annotations

import datetime as dt
import logging
import ssl as sslmod
from dataclasses import dataclass

from imapclient import IMAPClient

log = logging.getLogger(__name__)


@dataclass
class AccountConfig:
    imap_host: str
    imap_port: int = 993
    username: str = ""
    password: str = ""
    use_ssl: bool = True
    inbox: str = "INBOX"


def append_to_inbox(cfg: AccountConfig, mime_bytes: bytes, mark_seen: bool = True):
    ssl_context = sslmod.create_default_context() if cfg.use_ssl else None
    client = IMAPClient(cfg.imap_host, port=cfg.imap_port, ssl=cfg.use_ssl, ssl_context=ssl_context)
    try:
        client.login(cfg.username, cfg.password)
        client.append(cfg.inbox, mime_bytes, flags=(b"\\Seen",) if mark_seen else (), msg_time=dt.datetime.now(dt.timezone.utc))
        log.info("Appended message to %s for %s", cfg.inbox, cfg.username)
    finally:
        try:
            client.logout()
        except Exception:
            pass


__all__ = ["AccountConfig", "append_to_inbox"]
