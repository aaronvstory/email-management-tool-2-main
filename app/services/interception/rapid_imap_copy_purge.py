"""
Rapid IMAP Copy+Purge Worker for Inbound Email Interception

This module implements real-time inbound email interception by:
1. Using IMAP IDLE to detect new messages immediately
2. COPY new messages to quarantine folder
3. DELETE+EXPUNGE originals from inbox (minimal dwell time ~100-300ms)
4. Recording metadata for later editing and release

Key features:
- Thread-per-account model
- Ultra-low latency (<300ms typical)
- UID EXPUNGE when supported (precise deletion)
- Graceful fallback for servers without UID EXPUNGE
- Persistent IDLE with automatic reconnection
"""

import time
import threading
import os
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from queue import Queue, Empty

# Optional shared heartbeat mapping (imported lazily to avoid circular import)
try:
    from simple_app import WORKER_HEARTBEATS  # type: ignore
except Exception:  # pragma: no cover - optional
    WORKER_HEARTBEATS = {}

try:
    from imapclient import IMAPClient
    from imapclient import exceptions as imap_exc
except ImportError:
    raise ImportError("imapclient required: pip install imapclient")

# Setup logging
logger = logging.getLogger(__name__)# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'email_manager.db')
RAW_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'inbound_raw')

# Ensure raw directory exists
os.makedirs(RAW_DIR, exist_ok=True)

# Constants
IDLE_TIMEOUT = 60  # seconds
IDLE_MAX_DURATION = 15 * 60  # 15 minutes before reconnecting
RETRY_DELAY = 3  # seconds between connection retries


def get_db_connection():
    """Get database connection with Row factory for dict-like access"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


class RapidCopyPurgeWorker(threading.Thread):
    """
    Thread-based worker that monitors an IMAP account for new messages,
    copies them to quarantine folder, and deletes originals immediately.

    Minimal inbox dwell time: typically 100-300ms
    """
    daemon = True
    def __init__(self, account_id: int, imap_host: str, imap_port: int,
                 username: str, password: str, use_ssl: bool = True,
                 quarantine_folder: str = "InterceptHold"):
        """
        Initialize the rapid copy+purge worker

        Args:
            account_id: Database ID of the email account
            imap_host: IMAP server hostname
            imap_port: IMAP server port
            username: IMAP username
            password: IMAP password
            use_ssl: Use SSL/TLS connection
            quarantine_folder: Name of quarantine folder (created if not exists)
        """
        super().__init__(name=f"inbound-copy-purge-{account_id}")
        self.account_id = account_id
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.quarantine = quarantine_folder
        self._stop = threading.Event()
        self._client = None  # type: ignore
        self._raw_fetch_queue = Queue()
        self._fetch_thread = threading.Thread(target=self._raw_fetch_loop, name=f"raw-fetch-{account_id}", daemon=True)
        logger.info(f"Worker initialized for account {account_id} ({imap_host})")
    def stop(self):
        """Signal the worker to stop"""
        logger.info(f"Stopping worker for account {self.account_id}")
        self._stop.set()

    def _connect(self) -> IMAPClient:
        """
        Establish IMAP connection and ensure quarantine folder exists

        Returns:
            IMAPClient instance
        """
        logger.debug(f"Connecting to {self.imap_host}:{self.imap_port}")

        client = IMAPClient(self.imap_host, port=self.imap_port, ssl=self.use_ssl)
        client.login(self.username, self.password)

        # Ensure quarantine folder exists
        try:
            client.select_folder(self.quarantine)
            logger.debug(f"Quarantine folder '{self.quarantine}' exists")
        except imap_exc.IMAPClientError:
            logger.info(f"Creating quarantine folder '{self.quarantine}'")
            client.create_folder(self.quarantine)

        # Switch to INBOX for monitoring
        client.select_folder("INBOX")
        logger.info(f"Connected and monitoring INBOX for account {self.account_id}")

        return client
    def run(self):
        """
        Main worker loop with IDLE monitoring and auto-reconnection
        """
        logger.info(f"Starting rapid copy+purge worker for account {self.account_id}")

        while not self._stop.is_set():
            try:
                # Connect and get initial state
                self._client = self._connect()
                if not self._fetch_thread.is_alive():
                    self._fetch_thread.start()
                status = self._client.folder_status("INBOX", [b'UIDNEXT'])
                last_uidnext = status[b'UIDNEXT']
                logger.info(f"Initial UIDNEXT: {last_uidnext}")
                WORKER_HEARTBEATS[self.account_id] = time.time()

                idle_start = time.time()

                # Main IDLE loop
                while not self._stop.is_set():
                    # Enter IDLE mode
                    logger.debug("Entering IDLE mode")
                    self._client.idle()

                    # Wait for activity or timeout
                    responses = self._client.idle_check(timeout=IDLE_TIMEOUT)
                    self._client.idle_done()

                    # Check if we need to reconnect (IDLE duration limit)
                    if time.time() - idle_start > IDLE_MAX_DURATION:
                        logger.info("IDLE duration limit reached, reconnecting")
                        break

                    # Check for new messages
                    st2 = self._client.folder_status("INBOX", [b'UIDNEXT'])
                    nxt2 = st2[b'UIDNEXT']
                    if nxt2 > last_uidnext:
                        # New messages detected!
                        new_first = last_uidnext
                        target_last = nxt2 - 1
                        logger.info(f"New messages detected: UIDs {new_first}:{target_last}")

                        # Search for UIDs in range (string criteria form avoids older list syntax issues)
                        try:
                            uids = self._client.search(f"UID {new_first}:{target_last}")
                        except Exception as e:
                            logger.error(f"Search failed for UID range {new_first}:{target_last}: {e}")
                            uids = []

                        if uids:
                            # Process new messages immediately
                            self._process_new_messages(uids)
                            WORKER_HEARTBEATS[self.account_id] = time.time()

                        # Update tracking
                        last_uidnext = nxt2
                        idle_start = time.time()  # Reset IDLE timer

                # Clean disconnect
                if self._client:
                    self._client.logout()
                WORKER_HEARTBEATS[self.account_id] = time.time()

            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                if self._client:
                    try:
                        self._client.logout()
                    except:
                        pass
                    self._client = None

                if not self._stop.is_set():
                    logger.info(f"Reconnecting in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)

        logger.info(f"Worker stopped for account {self.account_id}")
    def _process_new_messages(self, uids: List[int]):
        r"""Rapid copy+purge operation for new messages.

        Steps:
        1. COPY to quarantine folder (capture payload)
        2. STORE +FLAGS (\\Deleted) on originals
        3. UID EXPUNGE (or fallback EXPUNGE) to remove from inbox
        4. Record metadata to database

        Target latency: <300ms typical
        """
        t0 = time.time()
        logger.info(f"Processing {len(uids)} new messages")
        client = self._client
        if client is None:
            logger.error("IMAP client unavailable in _process_new_messages")
            return
        try:
            # Step 1: Copy to quarantine with one retry
            logger.debug(f"Copying UIDs {uids} to {self.quarantine}")
            try:
                client.copy(uids, self.quarantine)
            except imap_exc.IMAPClientError as e:
                logger.warning(f"Copy failed, retrying: {e}")
                time.sleep(0.1)
                client.copy(uids, self.quarantine)

            # Step 2: Mark originals as deleted
            logger.debug(f"Marking UIDs {uids} as deleted")
            client.add_flags(uids, [b'\\Deleted'])

            # Step 3: Expunge (prefer UID EXPUNGE if supported)
            expunged = False
            try:
                caps = client.capabilities() or []
                if b'UIDPLUS' in caps:
                    uid_str = ','.join(str(u) for u in uids)
                    client._imap.uid('EXPUNGE', uid_str)  # type: ignore[attr-defined]
                    expunged = True
                    logger.debug(f"UID EXPUNGE successful for {uid_str}")
            except Exception:
                logger.debug("UID EXPUNGE attempt failed; will fallback")

            if not expunged:
                try:
                    client.expunge()
                except Exception as e:
                    logger.warning(f"Regular EXPUNGE failed: {e}")

            latency_ms = int((time.time() - t0) * 1000)
            logger.info(f"Copy+purge completed in {latency_ms}ms for {len(uids)} messages")

            # Step 4: Record to database
            self._record_messages(uids, latency_ms)
        except Exception as e:
            logger.error(f"Error processing messages: {e}", exc_info=True)
            raise

    def _record_messages(self, copied_uids: List[int], latency_ms: int):
        """Record intercepted messages to database with metadata.

        Fetches minimal headers from quarantine folder, stores metadata,
        and queues full message fetch for later (async pattern).
        """
        client = self._client
        if client is None:
            logger.error("IMAP client unavailable in _record_messages")
            return
        try:
            client.select_folder(self.quarantine)
        except Exception as e:
            logger.error(f"Unable to select quarantine folder: {e}")
            return

        fetch_map = client.fetch(copied_uids, [
            b'ENVELOPE',
            b'INTERNALDATE',
            b'BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM TO DATE)]'
        ])

        now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        cur = conn.cursor()
        for uid, data in fetch_map.items():
            try:
                # Extract envelope data
                env = data.get(b'ENVELOPE')
                internal_date = data.get(b'INTERNALDATE')
                raw_header = data.get(b'BODY[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM TO DATE)]', b'')
                if isinstance(raw_header, bytes):
                    raw_header_str = raw_header.decode('utf-8', errors='replace')
                else:
                    raw_header_str = str(raw_header)

                # Parse Message-ID
                msg_id = None
                subject = None
                sender = None
                recipients = None

                for line in raw_header_str.splitlines():
                    lower_line = line.lower()
                    if lower_line.startswith('message-id:'):
                        msg_id = line.split(':', 1)[1].strip()
                    elif lower_line.startswith('subject:'):
                        subject = line.split(':', 1)[1].strip()
                    elif lower_line.startswith('from:'):
                        sender = line.split(':', 1)[1].strip()
                    elif lower_line.startswith('to:'):
                        recipients = line.split(':', 1)[1].strip()

                # Format internal date as string
                internal_date_str = None
                if isinstance(internal_date, datetime):
                    internal_date_str = internal_date.strftime('%Y-%m-%d %H:%M:%S')

                # Insert record
                cur.execute("""
                    INSERT INTO email_messages
                      (account_id, direction, interception_status, quarantine_folder,
                       original_uid, original_internaldate, original_message_id,
                       sender, recipients, subject, status,
                       raw_path, created_at, latency_ms)
                    VALUES (?, 'inbound', 'HELD', ?, ?, ?, ?, ?, ?, ?, 'PENDING', NULL, ?, ?)
                """, (
                    self.account_id,
                    self.quarantine,
                    uid,
                    internal_date_str,
                    msg_id,
                    sender,
                    recipients,
                    subject,
                    now_ts,
                    latency_ms
                ))
                # Enqueue for raw fetch using the LAST INSERT ROWID
                row_id = cur.lastrowid
                self._raw_fetch_queue.put((row_id, uid))

                logger.debug(f"Recorded message UID {uid} to database")

            except Exception as e:
                logger.error(f"Error recording message UID {uid}: {e}", exc_info=True)

        conn.commit()
        conn.close()

        # Switch back to INBOX for next iteration (best-effort)
        try:
            client.select_folder("INBOX")
        except Exception:
            pass

        logger.info(f"Recorded {len(fetch_map)} messages to database")

    def _raw_fetch_loop(self):
        """Background loop that fetches full RFC822 for quarantined messages and stores to disk."""
        while True:
            try:
                item = self._raw_fetch_queue.get(timeout=1)
            except Empty:
                if self._stop.is_set():
                    return
                continue
            row_id: Optional[int] = None
            try:
                row_id, uid = item
                client = self._client
                if not client:
                    continue
                try:
                    client.select_folder(self.quarantine)
                except Exception:
                    continue
                full = client.fetch([uid], [b'RFC822'])
                data = full.get(uid, {})
                raw_bytes = data.get(b'RFC822')
                if not isinstance(raw_bytes, (bytes, bytearray)):
                    continue
                filename = f"msg_{row_id}_{uid}.eml"
                path = os.path.join(RAW_DIR, filename)
                with open(path, 'wb') as f:
                    f.write(raw_bytes)
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("UPDATE email_messages SET raw_path=? WHERE id=?", (path, row_id))
                conn.commit()
                conn.close()
                logger.debug(f"Stored raw message UID {uid} at {path}")
            except Exception as e:
                logger.error(f"Raw fetch loop error: {e}")
            finally:
                try:
                    self._raw_fetch_queue.task_done()
                except Exception:
                    pass
