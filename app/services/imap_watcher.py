"""
IMAP watcher implementing rapid copy+purge interception.

Contract:
- Input: account settings: host, port, username, password, ssl, folders
- Behavior: maintain an IDLE loop on INBOX; on new message UIDs, immediately copy to Quarantine, then delete from INBOX
- Fallback: if UID MOVE supported, prefer it over copy+purge
- Reliability: auto-reconnect with exponential backoff

This module is intentionally decoupled from Flask; it can be used by a runner script.
"""
from __future__ import annotations

import imaplib
import logging
import os
import socket
import ssl as sslmod
import time
from dataclasses import dataclass
import sqlite3
import json
from datetime import datetime
from email import message_from_bytes, policy
from email.utils import getaddresses
from typing import Optional, List

import backoff
from imapclient import IMAPClient

from app.utils.rule_engine import evaluate_rules
from app.utils.email_markers import RELEASE_BYPASS_HEADER, RELEASE_EMAIL_ID_HEADER


log = logging.getLogger(__name__)


@dataclass
class AccountConfig:
    imap_host: str
    imap_port: int = 993
    username: str = ""
    password: str = ""
    use_ssl: bool = True
    inbox: str = "INBOX"
    quarantine: str = "Quarantine"
    idle_timeout: int = 25 * 60  # 25 minutes typical server limit < 30m
    idle_ping_interval: int = 14 * 60  # break idle to keep alive
    mark_seen_quarantine: bool = True
    account_id: Optional[int] = None  # Database account ID for storing emails
    db_path: str = "email_manager.db"  # Path to database


class ImapWatcher:
    def __init__(self, cfg: AccountConfig):
        self.cfg = cfg
        self._client: Optional[IMAPClient] = None  # set in _connect
        self._last_hb = 0.0
        self._last_uidnext = 1
        self._release_skip_uids: set[int] = set()
        # Hybrid IDLE+polling strategy tracking
        self._idle_failure_count = 0
        self._last_successful_idle = time.time()
        self._polling_mode_forced = False
        self._last_idle_retry = time.time()
        # Phase 5 Quick Wins: UID cache to reduce DB queries by 90%
        self._last_uid_cache: Optional[int] = None
        self._uid_cache_time = 0.0

    def _should_stop(self) -> bool:
        """Return True if the account is deactivated in DB (is_active=0)."""
        try:
            if not self.cfg.account_id:
                return False
            conn = sqlite3.connect(self.cfg.db_path)
            cur = conn.cursor()
            row = cur.execute("SELECT is_active FROM email_accounts WHERE id=?", (self.cfg.account_id,)).fetchone()
            conn.close()
            if not row:
                return True
            is_active = int(row[0]) if row[0] is not None else 0
            return is_active == 0
        except sqlite3.Error as e:
            log.warning(f"Failed to check account active status for account {self.cfg.account_id}: {e}")
            return False  # On DB error, do not force stop
        except Exception as e:
            log.error(f"Unexpected error checking account status for account {self.cfg.account_id}: {e}", exc_info=True)
            return False

    def _check_connection_alive(self, client) -> bool:
        """Check if IMAP connection is still alive using NOOP command.
        
        Returns:
            True if connection is alive, False if dead/unresponsive
        """
        if not client:
            return False
        try:
            client.noop()
            return True
        except Exception as e:
            log.warning(f"Connection health check failed for account {self.cfg.account_id}: {e}")
            return False

    def _record_failure(self, reason: str = "error"):
        """Increment failure counter and open circuit if threshold exceeded."""
        try:
            if not self.cfg.account_id:
                return
            conn = sqlite3.connect(self.cfg.db_path)
            cur = conn.cursor()
            # Ensure heartbeats table has error_count column
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker_id TEXT PRIMARY KEY,
                    last_heartbeat TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    error_count INTEGER DEFAULT 0
                )
                """
            )
            # Backfill column if table existed without error_count
            try:
                cols = [r[1] for r in cur.execute("PRAGMA table_info(worker_heartbeats)").fetchall()]
                if 'error_count' not in cols:
                    cur.execute("ALTER TABLE worker_heartbeats ADD COLUMN error_count INTEGER DEFAULT 0")
            except sqlite3.Error as e:
                log.debug(f"Failed to backfill error_count column (may already exist): {e}")
            wid = f"imap_{self.cfg.account_id}"
            # Upsert and increment error_count
            cur.execute(
                """
                INSERT INTO worker_heartbeats(worker_id, last_heartbeat, status, error_count)
                VALUES(?, datetime('now'), ?, 1)
                ON CONFLICT(worker_id) DO UPDATE SET
                  last_heartbeat = excluded.last_heartbeat,
                  status = excluded.status,
                  error_count = COALESCE(worker_heartbeats.error_count, 0) + 1
                """,
                (wid, reason),
            )
            # Check threshold
            row = cur.execute("SELECT error_count FROM worker_heartbeats WHERE worker_id=?", (wid,)).fetchone()
            count = int(row[0]) if row and row[0] is not None else 0
            if count >= int(os.getenv('IMAP_CIRCUIT_THRESHOLD', '5')):
                # Open circuit: disable account to stop retry loop
                cur.execute(
                    "UPDATE email_accounts SET is_active=0, last_error=? WHERE id=?",
                    (f"circuit_open:{reason}", self.cfg.account_id),
                )
            conn.commit(); conn.close()
        except sqlite3.Error as e:
            log.error(f"Failed to record failure for account {self.cfg.account_id}: {e}", exc_info=True)
        except Exception as e:
            log.error(f"Unexpected error recording failure for account {self.cfg.account_id}: {e}", exc_info=True)

    def _get_last_processed_uid(self) -> int:
        """Get the last processed UID from database for this account.
        
        Phase 5 Quick Wins: Uses 30-second cache to reduce DB queries by 90%
        """
        if not self.cfg.account_id:
            return 0
        
        # Check cache first (30-second TTL)
        now = time.time()
        if self._last_uid_cache is not None and (now - self._uid_cache_time) < 30:
            return self._last_uid_cache
        
        # Cache miss - query database
        try:
            conn = sqlite3.connect(self.cfg.db_path)
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT MAX(original_uid) FROM email_messages WHERE account_id=?",
                (self.cfg.account_id,)
            ).fetchone()
            conn.close()
            uid = int(row[0]) if row and row[0] else 0
            
            # Update cache
            self._last_uid_cache = uid
            self._uid_cache_time = now
            
            return uid
        except sqlite3.Error as e:
            log.warning(f"Database error getting last processed UID for account {self.cfg.account_id}: {e}")
            return self._last_uid_cache if self._last_uid_cache is not None else 0
        except Exception as e:
            log.error(f"Unexpected error getting last processed UID for account {self.cfg.account_id}: {e}", exc_info=True)
            return self._last_uid_cache if self._last_uid_cache is not None else 0

    def _connect(self) -> Optional[IMAPClient]:
        try:
            log.info("Connecting to IMAP %s:%s (ssl=%s)", self.cfg.imap_host, self.cfg.imap_port, self.cfg.use_ssl)
            ssl_context = sslmod.create_default_context() if self.cfg.use_ssl else None
            # Apply connection timeout from env (EMAIL_CONN_TIMEOUT, clamp 5..60, default 15)
            try:
                to = int(os.getenv("EMAIL_CONN_TIMEOUT", "15"))
                to = max(5, min(60, to))
            except (ValueError, TypeError) as e:
                log.debug(f"Invalid EMAIL_CONN_TIMEOUT value, using default 15s: {e}")
                to = 15
            client = IMAPClient(
                self.cfg.imap_host,
                port=self.cfg.imap_port,
                ssl=self.cfg.use_ssl,
                ssl_context=ssl_context,
                timeout=to
            )
            client.login(self.cfg.username, self.cfg.password)
            log.info("Logged in as %s", self.cfg.username)
            capabilities = client.capabilities()
            log.debug("Server capabilities: %s", capabilities)
            # Ensure folders (robust: try Quarantine variants with server delimiter)
            # Always ensure INBOX first
            try:
                client.select_folder(self.cfg.inbox, readonly=False)
            except (imaplib.IMAP4.error, Exception) as e:
                # Some servers require upper-case name
                log.debug(f"Failed to select {self.cfg.inbox}, trying INBOX: {e}")
                client.select_folder("INBOX", readonly=False)

            # Resolve folder delimiter and build robust candidate list
            delim = None
            try:
                folders = client.list_folders()
                # folders items: (flags, delimiter, name)
                if folders and len(folders[0]) >= 2:
                    delim = folders[0][1]
                    if isinstance(delim, bytes):
                        try:
                            delim = delim.decode('utf-8', errors='ignore')
                        except (UnicodeDecodeError, AttributeError):
                            pass
            except (imaplib.IMAP4.error, Exception) as e:
                log.debug(f"Failed to determine folder delimiter: {e}")
                delim = None

            # Try to ensure quarantine folder with several candidates (ordered by preference)
            pref = str(os.getenv('IMAP_QUARANTINE_PREFERENCE', 'auto')).lower()
            base_name = self.cfg.quarantine
            inbox_slash = f"INBOX/{base_name}"
            inbox_dot = f"INBOX.{base_name}"
            if pref == 'inbox':
                q_candidates = [inbox_slash, inbox_dot, base_name]
            elif pref == 'plain':
                q_candidates = [base_name, inbox_slash, inbox_dot]
            else:
                q_candidates = [base_name, inbox_slash, inbox_dot]
            # If we detected a delimiter we trust, add that specific variant too
            try:
                if delim in ("/", "."):
                    q_candidates.append(f"INBOX{delim}{self.cfg.quarantine}")
            except (TypeError, KeyError):
                pass  # Delimiter invalid, skip this candidate

            ensured = False
            for qname in q_candidates:
                try:
                    client.select_folder(qname, readonly=False)
                    self.cfg.quarantine = qname
                    ensured = True
                    if str(os.getenv('IMAP_LOG_VERBOSE','0')).lower() in ('1','true','yes'):
                        log.info("Using quarantine folder: %s", qname)
                    break
                except imaplib.IMAP4.error as e:
                    log.debug(f"Folder {qname} not found: {e}")
                    try:
                        client.create_folder(qname)
                        client.select_folder(qname, readonly=False)
                        self.cfg.quarantine = qname
                        ensured = True
                        log.info("Created folder %s", qname)
                        break
                    except imaplib.IMAP4.error as create_err:
                        log.debug(f"Could not create folder {qname}: {create_err}")
                        continue

            # Fall back to original inbox if quarantine couldn't be ensured (should be rare)
            try:
                client.select_folder(self.cfg.inbox, readonly=False)
            except imaplib.IMAP4.error:
                log.debug(f"Failed to select {self.cfg.inbox}, using INBOX")
                client.select_folder("INBOX", readonly=False)
            # If we still didn't ensure quarantine, default to INBOX.Quarantine for safety
            if not ensured:
                log.warning(f"Could not ensure quarantine folder for account {self.cfg.account_id}, defaulting to INBOX.Quarantine")
                self.cfg.quarantine = "INBOX.Quarantine"

            # FIX #2: Initialize UIDNEXT tracking from database, not server UIDNEXT
            # This ensures we don't skip UIDs that arrived while watcher was down
            try:
                status = client.folder_status(self.cfg.inbox, [b'UIDNEXT'])
                server_uidnext = int(status.get(b'UIDNEXT') or 1)
            except (imaplib.IMAP4.error, KeyError, ValueError, TypeError) as e:
                log.warning(f"Failed to get UIDNEXT from server for account {self.cfg.account_id}: {e}")
                server_uidnext = 1

            # Check database for last processed UID
            last_db_uid = self._get_last_processed_uid()

            # Resume from max(database UID + 1, 1)
            # This ensures we process ALL UIDs after the last one we stored
            self._last_uidnext = max(1, last_db_uid + 1)

            log.info(f"UIDNEXT tracking initialized: server={server_uidnext}, last_db_uid={last_db_uid}, resuming_from={self._last_uidnext}")

            return client
        except Exception as e:
            log.error(f"Failed to connect to IMAP for {self.cfg.username}: {e}")
            # Record failure and possibly trip circuit breaker with better taxonomy
            msg = str(e).lower()
            if ('auth' in msg or 'login' in msg):
                reason = 'auth_failed'
            elif ('ssl' in msg or 'tls' in msg):
                reason = 'tls_failed'
            elif 'timeout' in msg:
                reason = 'timeout'
            else:
                reason = 'error'
            self._record_failure(reason)
            return None

    def _supports_uid_move(self) -> bool:
        # Allow forcing COPY+DELETE+EXPUNGE via env for servers with MOVE quirks
        try:
            if str(os.getenv('IMAP_FORCE_COPY_PURGE', '0')).lower() in ('1','true','yes'):
                return False
            caps = set(self._client.capabilities()) if self._client else set()
            return b"UIDPLUS" in caps or b"MOVE" in caps
        except (imaplib.IMAP4.error, AttributeError, Exception) as e:
            log.debug(f"Failed to check MOVE capability: {e}")
            return False

    def _copy_purge(self, uids):
        """Copy to quarantine then purge from INBOX quickly to minimize traces."""
        if not uids:
            return
        client = self._client
        if client is None:
            return
        if str(os.getenv('IMAP_LOG_VERBOSE','0')).lower() in ('1','true','yes'):
            log.info("Copying %s to %s", uids, self.cfg.quarantine)
        else:
            log.debug("Copying %s to %s", uids, self.cfg.quarantine)
        # Attempt copy, retrying with alternate folder names on namespace errors
        copy_ok = False
        last_err = None
        alt_targets = [self.cfg.quarantine]
        # Add common INBOX-prefixed variants
        if self.cfg.quarantine not in (f"INBOX/{self.cfg.quarantine}", f"INBOX.{self.cfg.quarantine}"):
            alt_targets.extend([f"INBOX/{self.cfg.quarantine}", f"INBOX.{self.cfg.quarantine}"])
        # Also explicit defaults
        alt_targets.extend(["INBOX/Quarantine", "INBOX.Quarantine", "Quarantine"])  # ensure a few options
        tried = set()
        for tgt in alt_targets:
            if tgt in tried:
                continue
            tried.add(tgt)
            try:
                # Ensure target exists, try create if needed
                try:
                    client.select_folder(tgt, readonly=False)
                except imaplib.IMAP4.error:
                    try:
                        client.create_folder(tgt)
                    except imaplib.IMAP4.error as create_err:
                        log.debug(f"Could not create quarantine folder {tgt}: {create_err}")
                # Reselect INBOX (source) to ensure UIDs refer to current mailbox
                try:
                    client.select_folder(self.cfg.inbox, readonly=False)
                except imaplib.IMAP4.error:
                    client.select_folder("INBOX", readonly=False)
                client.copy(uids, tgt)
                # Success: pin quarantine to working target
                self.cfg.quarantine = tgt
                copy_ok = True
                break
            except Exception as e:
                last_err = e
                log.debug("Copy to %s failed: %s", tgt, e)
                continue
        if not copy_ok:
            # Surface a concise error but do not crash the loop
            log.error("All COPY attempts failed for UIDs %s: %s", uids, last_err)
            return
        # Mark seen in quarantine optionally to reduce badge noise
        if self.cfg.mark_seen_quarantine:
            try:
                client.select_folder(self.cfg.quarantine, readonly=False)
                client.add_flags(uids, [b"\\Seen"])  # same UIDs valid in target on many servers with UIDPLUS
            except imaplib.IMAP4.error as e:
                # If UIDs differ post-copy, ignore silently; not critical
                log.debug(f"Could not set Seen in quarantine (UIDs may differ): {e}")
            finally:
                client.select_folder(self.cfg.inbox, readonly=False)
        if str(os.getenv('IMAP_LOG_VERBOSE','0')).lower() in ('1','true','yes'):
            log.info("Purging from INBOX")
        else:
            log.debug("Purging from INBOX")
        # Ensure we're operating on INBOX
        try:
            client.select_folder(self.cfg.inbox, readonly=False)
        except (imaplib.IMAP4.error, Exception) as e:
            log.debug(f"Failed to select INBOX before expunge: {e}")
        # Mark \Deleted using UID semantics (IMAPClient uses UIDs by default)
        try:
            client.add_flags(uids, [b"\\Deleted"])  # mark for deletion
        except Exception as e:
            log.warning("Adding \\Deleted flag failed: %s", e)

        # Try standard EXPUNGE first
        expunged = False
        try:
            client.expunge()
            expunged = True
        except Exception as e:
            log.warning("EXPUNGE failed: %s", e)
        # If server supports UIDPLUS, try UID EXPUNGE for the specific UIDs
        if not expunged:
            try:
                caps = set(client.capabilities() or [])
                if b"UIDPLUS" in caps and hasattr(client, "uid_expunge"):
                    client.uid_expunge(uids)
                    expunged = True
            except Exception as e:
                log.warning("UID EXPUNGE failed: %s", e)
        # Final fallback: delete_messages helper then expunge
        if not expunged:
            try:
                if hasattr(client, "delete_messages"):
                    client.delete_messages(uids, silent=False)
                client.expunge()
                expunged = True
            except Exception as e:
                log.error("Failed to purge deleted messages: %s", e)

    def _move(self, uids):
        client = self._client
        if client is None or not uids:
            return
        try:
            client.move(uids, self.cfg.quarantine)
        except Exception as e:
            log.debug("MOVE failed (%s); fallback copy+purge", e)
            self._copy_purge(uids)

    def _store_in_database(self, client, uids) -> List[int]:
        """Store intercepted emails in database and return UIDs requiring quarantine."""
        if not self.cfg.account_id or not uids:
            return []

        held_uids: List[int] = []

        conn = None
        try:
            fetch_data = client.fetch(uids, ['RFC822', 'ENVELOPE', 'FLAGS', 'INTERNALDATE'])

            conn = sqlite3.connect(self.cfg.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for uid, data in fetch_data.items():
                uid_int = int(uid)
                try:
                    # FIX #3: Log at START of processing each UID
                    log.debug(f"🔍 [START] Processing UID={uid_int}")

                    raw_email = data[b'RFC822']
                    email_msg = message_from_bytes(raw_email, policy=policy.default)

                    release_marker = (email_msg.get(RELEASE_BYPASS_HEADER) or '').strip()
                    if release_marker:
                        email_row_id = (email_msg.get(RELEASE_EMAIL_ID_HEADER) or '').strip()
                        log.info("Skipping released email UID=%s marker=%s email_id=%s",
                                 uid_int,
                                 release_marker,
                                 email_row_id or "unknown")
                        self._release_skip_uids.add(uid_int)
                        continue

                    sender = str(email_msg.get('From', ''))
                    addr_fields = email_msg.get_all('To', []) + email_msg.get_all('Cc', [])
                    addr_list = [addr for _, addr in getaddresses(addr_fields)]
                    recipients_list = [a for a in addr_list if a] or ([email_msg.get('To', '')] if email_msg.get('To') else [])
                    recipients = json.dumps(recipients_list)
                    subject = str(email_msg.get('Subject', 'No Subject'))
                    original_msg_id = (email_msg.get('Message-ID') or '').strip() or None
                    message_id = original_msg_id or f"imap_{uid_int}_{datetime.now().timestamp()}"

                    log.info(f"   Message-ID: {original_msg_id if original_msg_id else '(none - will generate)'}")
                    log.info(f"   Subject: {subject}")

                    body_text = ""
                    body_html = ""
                    if email_msg.is_multipart():
                        for part in email_msg.walk():
                            ctype = part.get_content_type()
                            payload = part.get_payload(decode=True)
                            if ctype == "text/plain":
                                if isinstance(payload, bytes):
                                    body_text = payload.decode('utf-8', errors='ignore')
                                elif isinstance(payload, str):
                                    body_text = payload
                            elif ctype == "text/html":
                                if isinstance(payload, bytes):
                                    body_html = payload.decode('utf-8', errors='ignore')
                                elif isinstance(payload, str):
                                    body_html = payload
                    else:
                        content = email_msg.get_payload(decode=True)
                        if isinstance(content, bytes):
                            body_text = content.decode('utf-8', errors='ignore')
                        elif isinstance(content, str):
                            body_text = content

                    try:
                        if original_msg_id:
                            row = cursor.execute("SELECT id FROM email_messages WHERE message_id=?", (original_msg_id,)).fetchone()
                            if row:
                                log.debug(f"⚠️ [DUPLICATE] Skipping duplicate message_id={original_msg_id} (uid={uid_int}, existing_id={row[0]})")
                                continue
                    except sqlite3.Error as e:
                        log.warning(f"Failed to check duplicate message_id for UID {uid_int}: {e}")

                    internal_dt = None
                    try:
                        internal_obj = data.get(b'INTERNALDATE')
                        if internal_obj:
                            if isinstance(internal_obj, datetime):
                                internal_dt = internal_obj.isoformat()
                            else:
                                internal_dt = str(internal_obj)
                    except (KeyError, ValueError, AttributeError) as e:
                        log.debug(f"Failed to parse INTERNALDATE for UID {uid_int}: {e}")
                        internal_dt = None

                    rule_eval = evaluate_rules(subject, body_text, sender, recipients_list)
                    should_hold = bool(rule_eval.get('should_hold'))
                    interception_status = 'INTERCEPTED' if should_hold else 'FETCHED'
                    risk_score = rule_eval.get('risk_score', 0)
                    keywords_json = json.dumps(rule_eval.get('keywords', []))

                    # FIX #3: Add INFO-level logging before INSERT to track status mapping
                    log.info(f"[PRE-INSERT] UID={uid_int}, subject='{subject[:40]}...', rule_eval={rule_eval}, should_hold={should_hold}, interception_status='{interception_status}'")

                    cursor.execute('''
                        INSERT INTO email_messages
                        (message_id, sender, recipients, subject, body_text, body_html,
                         raw_content, account_id, interception_status, direction,
                         original_uid, original_internaldate, original_message_id,
                         risk_score, keywords_matched, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', (
                        message_id,
                        sender,
                        recipients,
                        subject,
                        body_text,
                        body_html,
                        raw_email,
                        self.cfg.account_id,
                        interception_status,
                        'inbound',
                        uid_int,
                        internal_dt,
                        original_msg_id,
                        risk_score,
                        keywords_json
                    ))

                    # FIX #3: Log successful INSERT with full details
                    if should_hold:
                        held_uids.append(uid_int)
                        log.info("✅ [POST-INSERT] Stored INTERCEPTED email (UID=%s, subject='%s', sender=%s, account=%s)", uid_int, subject[:40], sender, self.cfg.account_id)
                    else:
                        log.info("✅ [POST-INSERT] Stored FETCHED email (UID=%s, subject='%s', sender=%s, account=%s)", uid_int, subject[:40], sender, self.cfg.account_id)

                except Exception as e:
                    # FIX #3: Enhanced error logging with full context
                    log.error("❌ Failed to store email UID %s (subject='%s', sender=%s): %s", uid_int, subject[:40] if 'subject' in locals() else 'unknown', sender if 'sender' in locals() else 'unknown', e, exc_info=True)

            conn.commit()
            
            # Phase 5 Quick Wins: Invalidate UID cache after successful DB insert
            self._last_uid_cache = None
            self._uid_cache_time = 0.0

            # FIX #3: Summary logging to track success/failure ratio
            log.debug(f"📊 [STORAGE SUMMARY] Attempted={len(uids)}, Held={len(held_uids)}, Account={self.cfg.account_id}")

        except Exception as e:
            log.error("Failed to store emails in database: %s", e, exc_info=True)
            return []
        finally:
            try:
                if 'conn' in locals() and conn:
                    conn.close()
            except sqlite3.Error as e:
                log.debug(f"Failed to close database connection: {e}")

        return held_uids

    def _update_message_status(self, uids: List[int], new_status: str) -> None:
        if not self.cfg.account_id or not uids:
            return
        status_upper = str(new_status or '').upper()
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(self.cfg.db_path)
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(uids))
            params = [
                status_upper,
                self.cfg.quarantine,
                status_upper,
                status_upper,
                self.cfg.account_id,
                *[int(u) for u in uids],
            ]
            cursor.execute(
                f"""
                UPDATE email_messages
                SET interception_status = ?,
                    quarantine_folder = ?,
                    action_taken_at = datetime('now'),
                    status = CASE WHEN ? = 'HELD' THEN 'PENDING' ELSE status END,
                    latency_ms = CASE
                        WHEN ? = 'HELD' AND latency_ms IS NULL AND created_at IS NOT NULL
                        THEN CAST((julianday(datetime('now')) - julianday(created_at)) * 86400000 AS INTEGER)
                        ELSE latency_ms
                    END
                WHERE account_id = ? AND original_uid IN ({placeholders})
                """,
                params,
            )
            conn.commit()
        except sqlite3.Error as exc:
            log.error(f"Database error updating interception status for account {self.cfg.account_id} UIDs {uids}: {exc}", exc_info=True)
        except Exception as exc:
            log.error(f"Unexpected error updating interception status for account {self.cfg.account_id} UIDs {uids}: {exc}", exc_info=True)
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as e:
                    log.debug(f"Failed to close connection: {e}")

    def _update_heartbeat(self, status: str = "active"):
        """Best-effort upsert of a heartbeat record for /healthz."""
        try:
            if not self.cfg.account_id:
                return
            conn = sqlite3.connect(self.cfg.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker_id TEXT PRIMARY KEY,
                    last_heartbeat TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    error_count INTEGER DEFAULT 0
                )
                """
            )
            # Backfill column if missing
            try:
                cols = [r[1] for r in cur.execute("PRAGMA table_info(worker_heartbeats)").fetchall()]
                if 'error_count' not in cols:
                    cur.execute("ALTER TABLE worker_heartbeats ADD COLUMN error_count INTEGER DEFAULT 0")
            except sqlite3.Error as e:
                log.debug(f"Failed to backfill error_count column in heartbeat (may already exist): {e}")
            wid = f"imap_{self.cfg.account_id}"
            # Reset error_count to 0 on healthy heartbeat; otherwise preserve
            cur.execute(
                """
                INSERT INTO worker_heartbeats(worker_id, last_heartbeat, status, error_count)
                VALUES(?, datetime('now'), ?, CASE WHEN ?='active' THEN 0 ELSE 0 END)
                ON CONFLICT(worker_id) DO UPDATE SET
                  last_heartbeat = excluded.last_heartbeat,
                  status = excluded.status,
                  error_count = CASE WHEN excluded.status='active' THEN 0 ELSE COALESCE(worker_heartbeats.error_count, 0) END
                """,
                (wid, status, status),
            )
            conn.commit(); conn.close()
        except sqlite3.Error as e:
            log.debug(f"Failed to update heartbeat for account {self.cfg.account_id}: {e}")
        except Exception as e:
            log.error(f"Unexpected error updating heartbeat for account {self.cfg.account_id}: {e}", exc_info=True)

    def _update_last_checked(self):
        """Update the last_checked timestamp for this account."""
        try:
            if not self.cfg.account_id:
                return
            conn = sqlite3.connect(self.cfg.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE email_accounts
                SET last_checked = datetime('now')
                WHERE id = ?
                """,
                (self.cfg.account_id,)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            log.debug(f"Database error updating last_checked for account {self.cfg.account_id}: {e}")
        except Exception as e:
            log.error(f"Unexpected error updating last_checked for account {self.cfg.account_id}: {e}", exc_info=True)

    def _handle_new_messages(self, client, changed):
        # changed example: {b'EXISTS': 12}
        # Build a robust candidate set using UIDNEXT deltas + last-N sweep, then filter out already-processed UIDs
        candidates: list[int] = []
        try:
            client.select_folder(self.cfg.inbox, readonly=False)
            # 1) UIDNEXT delta
            try:
                st = client.folder_status(self.cfg.inbox, [b'UIDNEXT'])
                uidnext_now = int(st.get(b'UIDNEXT') or self._last_uidnext)
            except (imaplib.IMAP4.error, KeyError, ValueError, TypeError) as e:
                log.debug(f"Failed to get UIDNEXT in handle_new_messages: {e}")
                uidnext_now = self._last_uidnext
            if uidnext_now > self._last_uidnext:
                try:
                    all_uids = client.search('ALL')
                    delta = [int(u) for u in all_uids if self._last_uidnext <= int(u) < uidnext_now]
                    candidates.extend(delta)
                except (imaplib.IMAP4.error, ValueError, TypeError) as e:
                    log.debug(f"Failed to search for UIDs in delta range: {e}")
            # 2) Last-N sweep to catch provider quirks (e.g., flags set early)
            try:
                sweep_n = 50
                try:
                    sweep_n = max(10, min(500, int(os.getenv('IMAP_SWEEP_LAST_N', '50'))))
                except (ValueError, TypeError) as e:
                    log.debug(f"Invalid IMAP_SWEEP_LAST_N, using default 50: {e}")
                    sweep_n = 50
                all_uids2 = client.search('ALL')
                recent = sorted([int(u) for u in all_uids2])[-sweep_n:]
                candidates.extend(recent)
            except (imaplib.IMAP4.error, ValueError, TypeError) as e:
                log.debug(f"Failed to sweep last N UIDs: {e}")
        except (imaplib.IMAP4.error, Exception) as e:
            log.warning(f"Failed to build candidate UID list for account {self.cfg.account_id}: {e}")

        # De-dup candidates
        if not candidates:
            return
        uniq = sorted(set(candidates))

        if self._release_skip_uids:
            filtered = [u for u in uniq if u not in self._release_skip_uids]
            if not filtered:
                try:
                    self._last_uidnext = max(self._last_uidnext, max(uniq) + 1)
                except (ValueError, TypeError):
                    pass  # Empty uniq list
                return
            uniq = filtered

        # Filter out UIDs we've already stored for this account
        try:
            conn = sqlite3.connect(self.cfg.db_path)
            cur = conn.cursor()
            placeholders = ",".join(["?"] * len(uniq))
            params = [self.cfg.account_id] + uniq
            seen = set()
            try:
                rows = cur.execute(
                    f"SELECT original_uid FROM email_messages WHERE account_id=? AND original_uid IN ({placeholders})",
                    params,
                ).fetchall()
                seen = {int(r[0]) for r in rows if r and r[0] is not None}
            except sqlite3.Error as e:
                log.warning(f"Database error checking processed UIDs for account {self.cfg.account_id}: {e}")
                seen = set()
            finally:
                conn.close()
            to_process = [u for u in uniq if u not in seen]
        except sqlite3.Error as e:
            log.error(f"Failed to filter processed UIDs for account {self.cfg.account_id}: {e}", exc_info=True)
            to_process = uniq

        if not to_process:
            # Advance tracker to latest observed window
            try:
                self._last_uidnext = max(self._last_uidnext, max(uniq) + 1)
            except (ValueError, TypeError):
                pass  # Empty uniq list
            else:
                self._release_skip_uids = {u for u in self._release_skip_uids if u >= self._last_uidnext}
            return

        log.info("Intercepting %d messages (acct=%s): %s", len(to_process), self.cfg.account_id, to_process)

        held_uids = self._store_in_database(client, to_process)

        if held_uids:
            held_uids = sorted(set(held_uids))
            move_successful = False
            if self._supports_uid_move():
                try:
                    log.info("Attempting MOVE for %d held messages to %s (acct=%s)", len(held_uids), self.cfg.quarantine, self.cfg.account_id)
                    self._move(held_uids)
                    move_successful = True
                    log.info("MOVE succeeded for %d messages to %s (acct=%s)", len(held_uids), self.cfg.quarantine, self.cfg.account_id)
                except Exception as e:
                    log.warning("MOVE failed for %d messages (acct=%s): %s", len(held_uids), self.cfg.account_id, e)
                    log.info("Falling back to copy+purge for %d held messages (acct=%s)", len(held_uids), self.cfg.account_id)
                    try:
                        self._copy_purge(held_uids)
                        move_successful = True
                        log.info("Copy+purge succeeded for %d messages to %s (acct=%s)", len(held_uids), self.cfg.quarantine, self.cfg.account_id)
                    except Exception as e2:
                        log.error("Copy+purge failed for %d messages (acct=%s): %s", len(held_uids), self.cfg.account_id, e2)
                        move_successful = False
            else:
                log.info("Server lacks MOVE; using copy+purge for %d held messages (acct=%s)", len(held_uids), self.cfg.account_id)
                try:
                    self._copy_purge(held_uids)
                    move_successful = True
                    log.info("Copy+purge succeeded for %d messages to %s (acct=%s)", len(held_uids), self.cfg.quarantine, self.cfg.account_id)
                except Exception as e:
                    log.error("Copy+purge failed for %d messages (acct=%s): %s", len(held_uids), self.cfg.account_id, e)
                    move_successful = False

            if move_successful:
                self._update_message_status(held_uids, 'HELD')
            else:
                log.warning("Move failed for %d messages (acct=%s); leaving status as INTERCEPTED for retry", len(held_uids), self.cfg.account_id)
        else:
            log.debug("No rule-matched messages require quarantine (acct=%s, uids=%s)", self.cfg.account_id, to_process)

        # Advance tracker past the highest processed UID based on DB-visible progress
        try:
            last_db_uid = self._get_last_processed_uid()
            self._last_uidnext = max(self._last_uidnext, last_db_uid + 1, max(to_process) + 1)
        except (ValueError, TypeError) as e:
            log.debug(f"Failed to advance UID tracker: {e}")
        else:
            self._release_skip_uids = {u for u in self._release_skip_uids if u >= self._last_uidnext}

    @backoff.on_exception(backoff.expo, (socket.error, OSError, Exception), max_time=60 * 60)
    def run_forever(self):
        # Early stop if account disabled
        if self._should_stop():
            try:
                self._update_heartbeat("stopped")
            except Exception as e:
                log.debug(f"Failed to update heartbeat on early stop: {e}")
            return
        self._client = self._connect()
        client = self._client

        # Check if connection failed
        if not client:
            log.error("Failed to establish IMAP connection")
            time.sleep(10)  # Wait before retry
            return  # Let backoff handle retry

        last_idle_break = time.time()
        # Ensure tracker resumes from DB state at loop start
        try:
            self._last_uidnext = max(1, self._get_last_processed_uid() + 1)
        except Exception as e:
            log.warning(f"Failed to resume UIDNEXT from DB for account {self.cfg.account_id}: {e}")
        log.info(f"Starting IDLE loop with _last_uidnext={self._last_uidnext} (db-resumed)")
        # initial heartbeat
        self._update_heartbeat("active"); self._last_hb = time.time()

        # Get polling interval from environment (default 30 seconds) - define once outside loop
        try:
            poll_interval = int(os.getenv("IMAP_POLL_INTERVAL", "30"))
            poll_interval = max(5, min(300, poll_interval))  # Clamp between 5-300 seconds
        except (ValueError, TypeError) as e:
            log.debug(f"Invalid IMAP_POLL_INTERVAL, using default 30s: {e}")
            poll_interval = 30

        while True:
            # Stop if account was deactivated while running
            if self._should_stop():
                try:
                    self._update_heartbeat("stopped")
                except Exception as e:
                    log.debug(f"Failed to update heartbeat on stop: {e}")
                try:
                    if client:
                        client.logout()
                except (imaplib.IMAP4.error, Exception) as e:
                    log.debug(f"Failed to logout on stop: {e}")
                return
            # Ensure client is still connected
            if not client:
                log.error("IMAP client disconnected, attempting reconnect")
                self._client = self._connect()
                client = self._client
                if not client:
                    time.sleep(10)
                    continue

            # Check IDLE support and IMAP_DISABLE_IDLE environment variable
            try:
                can_idle = b"IDLE" in (client.capabilities() or [])
                # Force polling mode if IMAP_DISABLE_IDLE is set
                if str(os.getenv('IMAP_DISABLE_IDLE', '0')).lower() in ('1', 'true', 'yes'):
                    can_idle = False
                    log.info(f"IDLE disabled by IMAP_DISABLE_IDLE env var for account {self.cfg.account_id}")
                # Respect forced polling mode from repeated IDLE failures
                if self._polling_mode_forced:
                    can_idle = False
            except (imaplib.IMAP4.error, AttributeError) as e:
                log.debug(f"Failed to check IDLE capability for account {self.cfg.account_id}: {e}")
                can_idle = False

            if not can_idle:
                # Poll fallback mode
                log.info(f"IDLE not supported for account {self.cfg.account_id}, using polling mode (interval: {poll_interval}s)")
                
                # Retry IDLE mode every 15 minutes if we were forced into polling due to failures
                if self._polling_mode_forced and (time.time() - self._last_idle_retry) > 900:  # 15 minutes
                    log.info(f"Retrying IDLE mode for account {self.cfg.account_id} after polling period")
                    self._polling_mode_forced = False
                    self._idle_failure_count = 0
                    self._last_idle_retry = time.time()
                    continue  # Skip this poll iteration and try IDLE again
                
                time.sleep(poll_interval)
                try:
                    client.select_folder(self.cfg.inbox, readonly=False)
                    self._handle_new_messages(client, {})
                    self._update_last_checked()
                except Exception as e:
                    log.error(f"Polling check failed for account {self.cfg.account_id}: {e}")
                if time.time() - self._last_hb > 30:
                    self._update_heartbeat("polling"); self._last_hb = time.time()
                continue

            # Double-check client before IDLE
            if not client:
                log.error("Client lost before IDLE, restarting")
                break

            # Final check - client must not be None for context manager
            if client is None:
                log.error("Client is None before IDLE, restarting")
                break

            try:
                # Some imapclient versions do not return a context manager from idle(); use explicit start/stop
                client.idle()
                log.debug("Entered IDLE")
                start = time.time()
                while True:
                    responses = client.idle_check(timeout=30)
                    # Break and process on EXISTS/RECENT
                    changed = {k: v for (k, v) in responses} if responses else {}
                    if responses:
                        self._handle_new_messages(client, changed)
                        self._update_last_checked()
                        # Track successful IDLE operation
                        self._idle_failure_count = 0
                        self._last_successful_idle = time.time()
                    # periodic heartbeat
                    if time.time() - self._last_hb > 30:
                        self._update_heartbeat("idle"); self._last_hb = time.time()
                    # Check stop request periodically during IDLE
                    if self._should_stop():
                        try:
                            client.idle_done()
                        except (imaplib.IMAP4.error, Exception) as e:
                            log.debug(f"Failed to exit IDLE on stop request: {e}")
                        try:
                            client.logout()
                        except (imaplib.IMAP4.error, Exception) as e:
                            log.debug(f"Failed to logout on stop request: {e}")
                        try:
                            self._update_heartbeat("stopped")
                        except Exception as e:
                            log.debug(f"Failed to update heartbeat on stop: {e}")
                        return
                    # Keep alive / break idle periodically
                    now = time.time()
                    if (now - start) > self.cfg.idle_timeout or (now - last_idle_break) > self.cfg.idle_ping_interval:
                        # Check connection health BEFORE trying to exit IDLE
                        if not self._check_connection_alive(client):
                            log.warning(f"Connection dead before idle_done for account {self.cfg.account_id}, reconnecting")
                            self._client = None
                            break  # Exit inner loop to reconnect
                        
                        try:
                            client.idle_done()
                        except Exception as e:
                            log.warning(f"idle_done() failed for account {self.cfg.account_id}: {e}, reconnecting")
                            self._client = None
                            break  # Exit inner loop to reconnect
                        
                        client.noop()
                        # Opportunistic poll using UIDNEXT delta when possible
                        try:
                            client.select_folder(self.cfg.inbox, readonly=False)
                            try:
                                st2 = client.folder_status(self.cfg.inbox, [b'UIDNEXT'])
                                uidnext2 = int(st2.get(b'UIDNEXT') or self._last_uidnext)
                            except (imaplib.IMAP4.error, KeyError, ValueError, TypeError) as e:
                                log.debug(f"Failed to get UIDNEXT during opportunistic poll: {e}")
                                uidnext2 = self._last_uidnext
                            new_uids = []
                            if uidnext2 > self._last_uidnext:
                                try:
                                    all_uids2 = client.search('ALL')
                                    new_uids = [int(u) for u in all_uids2 if self._last_uidnext <= int(u) < uidnext2]
                                except (imaplib.IMAP4.error, ValueError, TypeError) as e:
                                    log.debug(f"Failed to search UIDs during IDLE sweep: {e}")
                                    new_uids = []
                            # Fallback to UNSEEN if no range detected
                            if not new_uids:
                                try:
                                    new_uids = [int(u) for u in client.search('UNSEEN')]
                                except (imaplib.IMAP4.error, ValueError, TypeError) as e:
                                    log.debug(f"Failed to search UNSEEN during IDLE sweep: {e}")
                                    new_uids = []
                            if new_uids:
                                # Persist and move
                                held_new = self._store_in_database(client, new_uids)
                                if held_new:
                                    held_new = sorted(set(int(u) for u in held_new))
                                    move_ok = False
                                    if self._supports_uid_move():
                                        try:
                                            self._move(held_new)
                                            move_ok = True
                                        except (imaplib.IMAP4.error, Exception) as move_exc:
                                            log.warning(f"MOVE during idle sweep failed for acct={self.cfg.account_id}: {move_exc}")
                                            try:
                                                self._copy_purge(held_new)
                                                move_ok = True
                                            except Exception as copy_exc:
                                                log.error(f"Copy+purge during idle sweep failed for acct={self.cfg.account_id}: {copy_exc}", exc_info=True)
                                    else:
                                        try:
                                            self._copy_purge(held_new)
                                            move_ok = True
                                        except Exception as copy_exc:
                                            log.error(f"Copy+purge during idle sweep failed for acct={self.cfg.account_id}: {copy_exc}", exc_info=True)

                                    if move_ok:
                                        self._update_message_status(held_new, 'HELD')
                                    else:
                                        log.warning("Idle sweep could not move %d messages for acct=%s", len(held_new), self.cfg.account_id)
                                # Advance tracker to just after the highest UID we processed
                                try:
                                    self._last_uidnext = max(self._last_uidnext, max(int(u) for u in new_uids) + 1)
                                except (ValueError, TypeError):
                                    self._last_uidnext = uidnext2
                            self._update_last_checked()
                        except (imaplib.IMAP4.error, Exception) as e:
                            log.debug(f"Opportunistic poll during idle_break failed for account {self.cfg.account_id}: {e}")
                        last_idle_break = now
                        break
            except Exception as e:
                # Track IDLE failure
                self._idle_failure_count += 1
                log.warning(f"IDLE failure #{self._idle_failure_count} for account {self.cfg.account_id}: {e}")
                
                # Force polling mode after 3 consecutive failures
                if self._idle_failure_count >= 3:
                    log.error(f"IDLE failed {self._idle_failure_count} times for account {self.cfg.account_id}, forcing polling mode")
                    self._polling_mode_forced = True
                    self._last_idle_retry = time.time()
                
                error_msg = str(e).lower()
                # Check if this is an IDLE failure that should trigger polling mode
                # Common patterns: protocol violations, timeouts, connection issues
                should_poll = any([
                    "violates" in error_msg,
                    "protocol" in error_msg,
                    "timeout" in error_msg,
                    "timed out" in error_msg,
                    "read from timed" in error_msg
                ])

                if should_poll or self._polling_mode_forced:
                    log.info(f"Switching to polling mode (interval: {poll_interval}s)")
                    # Sleep and then poll
                    time.sleep(poll_interval)
                    try:
                        client.select_folder(self.cfg.inbox, readonly=False)
                        self._handle_new_messages(client, {})
                    except Exception as poll_e:
                        log.error(f"Polling after IDLE failure failed: {poll_e}")
                    continue  # Continue loop in polling mode
                else:
                    log.error(f"IDLE failed: {e}, reconnecting...")
                    self._client = None
                    break  # Exit inner loop to reconnect

    def close(self):
        client = self._client
        try:
            if client:
                try:
                    client.logout()
                except Exception as e:
                    log.debug("IMAP logout failed during close", extra={'account_id': self.cfg.account_id, 'error': str(e)}, exc_info=True)
        finally:
            self._client = None


__all__ = ["AccountConfig", "ImapWatcher"]
