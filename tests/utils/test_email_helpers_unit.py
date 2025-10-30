import smtplib
from types import SimpleNamespace
import pytest

from app.utils import email_helpers as helpers


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("AuthenticationFailed for user", "Incorrect username or password"),
        ("535 Authentication credentials invalid", "Incorrect username or password"),
        ("getaddrinfo failed", "Server not found. Check hostname."),
        ("NAME OR SERVICE NOT KNOWN", "Server not found. Check hostname."),
        ("Connection timed out", "Connection timed out. Check firewall or port."),
        ("ssl wrong version number", "SSL/TLS handshake failed. Verify port and TLS settings."),
        ("ssl certificate verify failed", "SSL/TLS handshake failed. Verify port and TLS settings."),
        ("none", "Server returned an error (protocol/port mismatch)."),
    ],
)
def test_map_error_variants(raw, expected):
    assert helpers._map_error(raw) == expected


def test_detect_email_settings_known_provider():
    settings = helpers.detect_email_settings("user@gmail.com")
    assert settings["smtp_host"] == "smtp.gmail.com"
    assert settings["smtp_port"] == 587
    assert settings["imap_host"] == "imap.gmail.com"
    assert settings["imap_use_ssl"] is True


def test_detect_email_settings_generic_domain():
    settings = helpers.detect_email_settings("someone@acme.example")
    assert settings == {
        "smtp_host": "smtp.acme.example",
        "smtp_port": 587,
        "smtp_use_ssl": False,
        "imap_host": "imap.acme.example",
        "imap_port": 993,
        "imap_use_ssl": True,
    }


class _SMTPContext:
    def __init__(self, host, port, timeout, *, fail=False, starttls=True):
        if fail:
            raise RuntimeError("fail")
        self.host = host
        self.port = port
        self.timeout = timeout
        self._starttls_enabled = starttls
        self.login_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        if not self._starttls_enabled:
            raise RuntimeError("starttls disabled")

    def login(self, username, password):
        self.login_called = True


class _IMAPClient:
    def __init__(self, host, port, timeout, *, fail=False, allow_starttls=True):
        if fail:
            raise RuntimeError("fail")
        self.host = host
        self.port = port
        self.timeout = timeout
        self._allow_starttls = allow_starttls
        self._shutdown_called = False
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        if not self._allow_starttls:
            raise RuntimeError("starttls blocked")

    def login(self, username, password):
        self.logged_in = True

    def logout(self):
        pass

    def shutdown(self):
        self._shutdown_called = True


def test_negotiate_smtp_prefers_starttls(monkeypatch):
    smtp_calls = []

    def fake_smtp(host, port, timeout):
        smtp_calls.append(("SMTP", port))
        return _SMTPContext(host, port, timeout)

    def fake_smtp_ssl(host, port, timeout, context=None):
        pytest.fail("SMTP_SSL should not be used when STARTTLS succeeds")

    monkeypatch.setattr(helpers, "smtplib", SimpleNamespace(SMTP=fake_smtp, SMTP_SSL=fake_smtp_ssl))
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 9)

    result = helpers.negotiate_smtp("smtp.example.com", "user", "pw")
    assert result == {"smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_use_ssl": False}
    assert ("SMTP", 587) in smtp_calls


def test_negotiate_smtp_fallback_to_custom_port(monkeypatch):
    calls = []

    def fake_smtp(host, port, timeout):
        calls.append(("SMTP", port))
        if port == 587:
            raise RuntimeError("no starttls")
        return _SMTPContext(host, port, timeout)

    def fake_smtp_ssl(host, port, timeout, context=None):
        calls.append(("SMTP_SSL", port))
        raise RuntimeError("ssl fails")

    monkeypatch.setattr(helpers, "smtplib", SimpleNamespace(SMTP=fake_smtp, SMTP_SSL=fake_smtp_ssl))
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 9)

    result = helpers.negotiate_smtp(
        "smtp.example.com",
        "user",
        "pw",
        port=2525,
        use_ssl=False,
    )
    assert result == {"smtp_host": "smtp.example.com", "smtp_port": 2525, "smtp_use_ssl": False}
    assert ("SMTP", 2525) in calls


def test_negotiate_smtp_returns_default_when_all_fail(monkeypatch):
    def failing_smtp(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        helpers,
        "smtplib",
        SimpleNamespace(SMTP=failing_smtp, SMTP_SSL=failing_smtp),
    )
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 7)

    result = helpers.negotiate_smtp("smtp.example.com", "user", "pw", port=2000, use_ssl=True)
    assert result == {"smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_use_ssl": False}


def test_negotiate_imap_prefers_ssl(monkeypatch):
    imap_ssl_calls = []

    def fake_imap_ssl(host, port, timeout):
        imap_ssl_calls.append(port)
        return _IMAPClient(host, port, timeout)

    def fake_imap(host, port, timeout):
        pytest.fail("Plain IMAP should not be used when SSL succeeds")

    monkeypatch.setattr(helpers, "imaplib", SimpleNamespace(IMAP4=fake_imap, IMAP4_SSL=fake_imap_ssl))
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 8)

    result = helpers.negotiate_imap("imap.example.com", "user", "pw")
    assert result == {"imap_host": "imap.example.com", "imap_port": 993, "imap_use_ssl": True}
    assert imap_ssl_calls == [993]


def test_negotiate_imap_fallback_to_starttls(monkeypatch):
    calls = []

    def fake_imap_ssl(host, port, timeout):
        raise RuntimeError("ssl blocked")

    class PlainImap(_IMAPClient):
        def __init__(self, host, port, timeout, *, fail=False):
            super().__init__(host, port, timeout, allow_starttls=True)
            calls.append(port)

    monkeypatch.setattr(
        helpers,
        "imaplib",
        SimpleNamespace(IMAP4=PlainImap, IMAP4_SSL=fake_imap_ssl),
    )
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 5)

    result = helpers.negotiate_imap("imap.example.com", "user", "pw")
    assert result == {"imap_host": "imap.example.com", "imap_port": 143, "imap_use_ssl": False}
    assert 143 in calls


def test_negotiate_imap_default_when_all_fail(monkeypatch):
    def failing_imap(*args, **kwargs):
        raise RuntimeError("imap failure")

    monkeypatch.setattr(
        helpers,
        "imaplib",
        SimpleNamespace(IMAP4=failing_imap, IMAP4_SSL=failing_imap),
    )
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 6)

    result = helpers.negotiate_imap("imap.example.com", "user", "pw", port=1993, use_ssl=False)
    assert result == {"imap_host": "imap.example.com", "imap_port": 993, "imap_use_ssl": True}


def test_normalize_modes_enforces_well_known_ports():
    smtp_ssl, imap_ssl = helpers.normalize_modes(465, False, 143, True)
    assert (smtp_ssl, imap_ssl) == (True, False)


class _StubLogger:
    def __init__(self):
        self.records = []

    def info(self, msg, *args):
        self.records.append(("info", msg % args if args else msg))

    def error(self, msg, *args):
        self.records.append(("error", msg % args if args else msg))


def test_test_email_connection_imap_success(monkeypatch):
    client = _IMAPClient("imap.example.com", 993, timeout=5)

    def fake_imap_ssl(host, port, timeout):
        assert (host, port) == ("imap.example.com", 993)
        return client

    monkeypatch.setattr(
        helpers,
        "imaplib",
        SimpleNamespace(IMAP4=fake_imap_ssl, IMAP4_SSL=fake_imap_ssl),
    )
    logger = _StubLogger()
    monkeypatch.setattr(helpers, "_get_logger", lambda: logger)
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 5)

    ok, message = helpers.test_email_connection("imap", "imap.example.com", 993, "user", "pw", True)
    assert ok is True
    assert "IMAP OK" in message
    assert any("IMAP connection successful" in rec[1] for rec in logger.records)


def test_test_email_connection_missing_parameters(monkeypatch):
    logger = _StubLogger()
    monkeypatch.setattr(helpers, "_get_logger", lambda: logger)

    ok, message = helpers.test_email_connection("imap", "", 0, "user", "pw", True)
    assert ok is False
    assert "Missing connection parameters" in message
    assert any("FAILED" in rec[1] for rec in logger.records)


def test_test_email_connection_unknown_kind(monkeypatch):
    logger = _StubLogger()
    monkeypatch.setattr(helpers, "_get_logger", lambda: logger)

    ok, message = helpers.test_email_connection("pop3", "host", 110, "user", "pw", False)
    assert ok is False
    assert "Unsupported kind" in message
    assert any("Unsupported connection kind" in rec[1] for rec in logger.records)


def test_test_email_connection_maps_error(monkeypatch):
    class FailingSMTP(_SMTPContext):
        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    def fake_smtp(host, port, timeout):
        return FailingSMTP(host, port, timeout)

    monkeypatch.setattr(
        helpers,
        "smtplib",
        SimpleNamespace(SMTP=fake_smtp, SMTP_SSL=lambda *args, **kwargs: fake_smtp(*args, **kwargs)),
    )
    monkeypatch.setattr(helpers, "_get_timeout", lambda: 5)
    logger = _StubLogger()
    monkeypatch.setattr(helpers, "_get_logger", lambda: logger)

    ok, message = helpers.test_email_connection("smtp", "smtp.example.com", 587, "user", "pw", False)
    assert ok is False
    assert message == "Incorrect username or password"
    assert any("FAILED" in rec[1] for rec in logger.records)
