"""
Email Helper Utilities
Consolidated email detection and connection testing functions
Phase 3: Helper Consolidation - Extracted from simple_app.py and app/routes/accounts.py
"""

import os
import smtplib
import imaplib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Tuple, Optional, Dict
import ssl

_LOGGER: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Logger configured for console + rotating file under logs/connection_tests.log"""
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    logger = logging.getLogger("connection_tests")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logs_dir = Path("logs")
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fh = RotatingFileHandler(str(logs_dir / "connection_tests.log"), maxBytes=512_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        ch.setFormatter(fmt)
        fh.setFormatter(fmt)
        logger.addHandler(ch)
        logger.addHandler(fh)
        logger.propagate = False
    _LOGGER = logger
    return logger


def _get_timeout() -> int:
    try:
        t = int(os.getenv("EMAIL_CONN_TIMEOUT", "15"))
        return max(5, min(60, t))
    except Exception:
        return 15


def _map_error(msg: str) -> str:
    lower = (msg or "").lower()
    if "authenticationfailed" in lower or "535" in lower or "invalid credentials" in lower:
        return "Incorrect username or password"
    if "getaddrinfo failed" in lower or "name or service not known" in lower or "nodename nor servname provided" in lower:
        return "Server not found. Check hostname."
    if "timed out" in lower or "timeout" in lower:
        return "Connection timed out. Check firewall or port."
    if ("ssl" in lower and "wrong version number" in lower) or ("ssl" in lower and "certificate verify failed" in lower):
        return "SSL/TLS handshake failed. Verify port and TLS settings."
    if lower.strip() == "none":
        return "Server returned an error (protocol/port mismatch)."
    return msg


def detect_email_settings(email_address: str) -> dict:
    """
    Smart detection of SMTP/IMAP settings based on email domain.
    Returns dict with smtp_host, smtp_port, smtp_use_ssl, imap_host, imap_port, imap_use_ssl

    Args:
        email_address: Email address to detect settings for

    Returns:
        Dictionary with SMTP and IMAP configuration
    """
    domain = email_address.split('@')[-1].lower() if '@' in email_address else ''

    # Known provider configurations
    providers = {
        'gmail.com': {
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,  # STARTTLS on 587
            'imap_host': 'imap.gmail.com',
            'imap_port': 993,
            'imap_use_ssl': True
        },
        'corrinbox.com': {
            'smtp_host': 'smtp.hostinger.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,  # Direct SSL on 465
            'imap_host': 'imap.hostinger.com',
            'imap_port': 993,
            'imap_use_ssl': True
        },
        'outlook.com': {
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'imap_host': 'outlook.office365.com',
            'imap_port': 993,
            'imap_use_ssl': True
        },
        'hotmail.com': {
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'imap_host': 'outlook.office365.com',
            'imap_port': 993,
            'imap_use_ssl': True
        },
        'yahoo.com': {
            'smtp_host': 'smtp.mail.yahoo.com',
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'imap_host': 'imap.mail.yahoo.com',
            'imap_port': 993,
            'imap_use_ssl': True
        }
    }

    # Return provider settings or generic defaults
    if domain in providers:
        return providers[domain]
    else:
        # Generic defaults - try common patterns
        return {
            'smtp_host': f'smtp.{domain}',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'imap_host': f'imap.{domain}',
            'imap_port': 993,
            'imap_use_ssl': True
        }


def normalize_modes(smtp_port: int, smtp_use_ssl: bool, imap_port: int, imap_use_ssl: bool) -> Tuple[bool, bool]:
    """Normalize TLS modes by well-known ports. Returns (smtp_use_ssl, imap_use_ssl)."""
    if smtp_port == 465:
        smtp_use_ssl = True
    elif smtp_port == 587:
        smtp_use_ssl = False  # STARTTLS
    if imap_port == 993:
        imap_use_ssl = True
    elif imap_port == 143:
        imap_use_ssl = False  # STARTTLS
    return smtp_use_ssl, imap_use_ssl


def negotiate_smtp(host: str, username: str, password: str, port: Optional[int] = None, use_ssl: Optional[bool] = None) -> Dict[str, object]:
    """Probe SMTP in safe order and return chosen host/port/mode.
    Order: 587 STARTTLS → 465 SSL → fallback to provided.
    """
    timeout = _get_timeout()
    ctx = ssl.create_default_context()
    # Try 587 STARTTLS
    try:
        with smtplib.SMTP(host, 587, timeout=timeout) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo(); s.login(username, password)
            return {'smtp_host': host, 'smtp_port': 587, 'smtp_use_ssl': False}
    except Exception:
        pass
    # Try 465 SSL
    try:
        with smtplib.SMTP_SSL(host, 465, timeout=timeout, context=ctx) as s:
            s.login(username, password)
            return {'smtp_host': host, 'smtp_port': 465, 'smtp_use_ssl': True}
    except Exception:
        pass
    # Fallback: try provided settings if any
    if port:
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, int(port), timeout=timeout, context=ctx) as s:
                    s.login(username, password)
            else:
                with smtplib.SMTP(host, int(port), timeout=timeout) as s:
                    s.ehlo(); s.starttls(context=ctx); s.ehlo(); s.login(username, password)
            return {'smtp_host': host, 'smtp_port': int(port), 'smtp_use_ssl': bool(use_ssl)}
        except Exception:
            pass
    # As last resort, return default 587 STARTTLS
    return {'smtp_host': host, 'smtp_port': 587, 'smtp_use_ssl': False}


def negotiate_imap(host: str, username: str, password: str, port: Optional[int] = None, use_ssl: Optional[bool] = None) -> Dict[str, object]:
    """Probe IMAP in safe order and return chosen host/port/mode.
    Order: 993 SSL → 143 STARTTLS → fallback to provided.
    """
    timeout = _get_timeout()
    # Try 993 SSL
    try:
        with imaplib.IMAP4_SSL(host, 993, timeout=timeout) as c:
            c.login(username, password)
            return {'imap_host': host, 'imap_port': 993, 'imap_use_ssl': True}
    except Exception:
        pass
    # Try 143 STARTTLS
    try:
        c = imaplib.IMAP4(host, 143, timeout=timeout)
        try:
            c.starttls()
        except Exception:
            c.shutdown(); c.logout(); raise
        c.login(username, password); c.logout()
        return {'imap_host': host, 'imap_port': 143, 'imap_use_ssl': False}
    except Exception:
        pass
    # Fallback to provided
    if port:
        try:
            if use_ssl:
                with imaplib.IMAP4_SSL(host, int(port), timeout=timeout) as c:
                    c.login(username, password)
            else:
                c = imaplib.IMAP4(host, int(port), timeout=timeout)
                try:
                    c.starttls()
                except Exception:
                    c.shutdown(); c.logout(); raise
                c.login(username, password); c.logout()
            return {'imap_host': host, 'imap_port': int(port), 'imap_use_ssl': bool(use_ssl)}
        except Exception:
            pass
    return {'imap_host': host, 'imap_port': 993, 'imap_use_ssl': True}


def test_email_connection(kind: str, host: str, port: int, username: str, password: str, use_ssl: bool) -> Tuple[bool, str]:
    """
    Production-grade connectivity test for IMAP/SMTP with structured logging.
    Returns (success, message) and logs all attempts to console and log file.

    Args:
        kind: 'imap' or 'smtp'
        host: Server hostname
        port: Server port
        username: Authentication username
        password: Authentication password
        use_ssl: Whether to use SSL/TLS

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger = _get_logger()
    if not host or not port:
        logger.error("%s Test FAILED: Missing connection parameters", kind.upper())
        return False, "Missing connection parameters"
    if not username or not password:
        logger.error("%s Test FAILED: Username and password are required", kind.upper())
        return False, "Username and password are required"

    logger.info("Testing %s connection to %s:%s (use_ssl=%s, user=%s)", kind.upper(), host, port, use_ssl, username)

    try:
        if kind.lower() == 'imap':
            if use_ssl:
                logger.info("  → Connecting via IMAP4_SSL...")
                client = imaplib.IMAP4_SSL(host, int(port), timeout=_get_timeout())
            else:
                logger.info("  → Connecting via IMAP4 (plaintext)...")
                client = imaplib.IMAP4(host, int(port), timeout=_get_timeout())

            logger.info("  → Authenticating as %s...", username)
            client.login(username, password)
            client.logout()
            logger.info("✅ IMAP connection successful: %s:%s", host, port)
            return True, f"IMAP OK {host}:{port}"

        if kind.lower() == 'smtp':
            port_int = int(port)
            timeout = _get_timeout()

            if port_int == 465:
                logger.info("  → Connecting via SMTP_SSL (port 465 direct SSL)...")
                server = smtplib.SMTP_SSL(host, port_int, timeout=timeout)
            elif port_int == 587:
                logger.info("  → Connecting via SMTP with STARTTLS (port 587)...")
                server = smtplib.SMTP(host, port_int, timeout=timeout)
                server.ehlo()
                server.starttls()
                server.ehlo()
            elif use_ssl:
                logger.info("  → Connecting via SMTP_SSL (use_ssl=True)...")
                server = smtplib.SMTP_SSL(host, port_int, timeout=timeout)
            else:
                logger.info("  → Connecting via SMTP (plaintext)...")
                server = smtplib.SMTP(host, port_int, timeout=timeout)

            logger.info("  → Authenticating as %s...", username)
            server.login(username, password)
            server.quit()
            logger.info("✅ SMTP connection successful: %s:%s", host, port)
            return True, f"SMTP OK {host}:{port}"

        logger.error("❌ Unsupported connection kind: %s", kind)
        return False, f"Unsupported kind {kind}"

    except Exception as e:
        logger.error("❌ %s connection FAILED: %s: %s", kind.upper(), type(e).__name__, str(e))
        return False, _map_error(str(e))

# Prevent pytest from collecting this helper as a test
test_email_connection.__test__ = False  # type: ignore[attr-defined]
