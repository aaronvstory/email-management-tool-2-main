"""
Tests for JSON logging functionality.

Verifies that structured JSON logging works correctly with rotation.
"""
import json
import logging
import tempfile
from pathlib import Path

import pytest

from app.utils.logging import JSONFormatter, setup_app_logging


def test_json_formatter_creates_valid_json():
    """Test that JSONFormatter produces valid JSON output."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_func"
    )

    output = formatter.format(record)

    # Should be valid JSON
    log_data = json.loads(output)

    # Check required fields
    assert "timestamp" in log_data
    assert "level" in log_data
    assert "logger" in log_data
    assert "message" in log_data
    assert "module" in log_data
    assert "function" in log_data
    assert "line" in log_data

    # Check values
    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "test_logger"
    assert log_data["message"] == "Test message"
    assert log_data["function"] == "test_func"
    assert log_data["line"] == 42


def test_json_formatter_includes_exception_info():
    """Test that exceptions are included in JSON output."""
    formatter = JSONFormatter()

    try:
        raise ValueError("Test exception")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
            func="test_func"
        )

        output = formatter.format(record)
        log_data = json.loads(output)

        # Should include exception info
        assert "exc_info" in log_data
        assert "ValueError" in log_data["exc_info"]
        assert "Test exception" in log_data["exc_info"]


def test_setup_app_logging_creates_log_files(app, tmp_path):
    """Test that setup_app_logging creates log files in the correct directory."""
    log_dir = tmp_path / "test_logs"

    # Clear any existing handlers
    app.logger.handlers.clear()

    # Setup logging with custom directory
    setup_app_logging(app, log_dir=str(log_dir))

    # Verify log directory was created
    assert log_dir.exists()

    # Log a test message
    app.logger.info("Test log message")

    # Verify JSON log file exists (timestamped format: app_YYYY-MM-DD_HHMMSS.json.log)
    json_logs = list(log_dir.glob("app_*.json.log"))
    assert len(json_logs) > 0, "No JSON log files found"
    json_log = json_logs[0]
    assert json_log.exists()

    # Verify plain text log file exists (timestamped format: app_YYYY-MM-DD_HHMMSS.log)
    text_logs = list(log_dir.glob("app_*.log"))
    text_logs = [f for f in text_logs if not f.name.endswith('.json.log')]  # Exclude .json.log files
    assert len(text_logs) > 0, "No text log files found"
    text_log = text_logs[0]
    assert text_log.exists()

    # Verify JSON log contains valid JSON
    with open(json_log, 'r') as f:
        for line in f:
            if line.strip():
                log_data = json.loads(line)
                assert "timestamp" in log_data
                assert "message" in log_data


def test_json_log_rotation(app, tmp_path):
    """Test that timestamped log files are created and old files are cleaned up."""
    log_dir = tmp_path / "rotation_test"

    # Clear any existing handlers
    app.logger.handlers.clear()

    # Create multiple log sessions to test cleanup (keeps last 3)
    # Session 1
    setup_app_logging(app, log_dir=str(log_dir))
    app.logger.info("Session 1 message")
    app.logger.handlers.clear()

    # Session 2
    import time
    time.sleep(0.1)  # Ensure different timestamp
    setup_app_logging(app, log_dir=str(log_dir))
    app.logger.info("Session 2 message")
    app.logger.handlers.clear()

    # Session 3
    time.sleep(0.1)
    setup_app_logging(app, log_dir=str(log_dir))
    app.logger.info("Session 3 message")
    app.logger.handlers.clear()

    # Session 4 (should trigger cleanup of session 1 files)
    time.sleep(0.1)
    setup_app_logging(app, log_dir=str(log_dir))
    app.logger.info("Session 4 message")

    # Verify timestamped JSON log files exist
    json_logs = list(log_dir.glob("app_*.json.log"))
    # Should have at most 3 JSON log files (cleanup keeps last 3)
    assert len(json_logs) <= 3, f"Expected at most 3 JSON logs, found {len(json_logs)}"
    assert len(json_logs) > 0, "No JSON log files found"

    # Verify timestamped text log files exist
    text_logs = [f for f in log_dir.glob("app_*.log") if not f.name.endswith('.json.log')]
    # Should have at most 3 text log files (cleanup keeps last 3)
    assert len(text_logs) <= 3, f"Expected at most 3 text logs, found {len(text_logs)}"
    assert len(text_logs) > 0, "No text log files found"


def test_logging_respects_log_level_env_var(app, tmp_path, monkeypatch):
    """Test that LOG_LEVEL environment variable is respected."""
    log_dir = tmp_path / "level_test"

    # Clear any existing handlers
    app.logger.handlers.clear()

    # Set LOG_LEVEL to WARNING
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    setup_app_logging(app, log_dir=str(log_dir))

    # Log at different levels
    app.logger.debug("Debug message")
    app.logger.info("Info message")
    app.logger.warning("Warning message")
    app.logger.error("Error message")

    # Read JSON log (timestamped format: app_YYYY-MM-DD_HHMMSS.json.log)
    json_logs = list(log_dir.glob("app_*.json.log"))
    assert len(json_logs) > 0, "No JSON log files found"
    json_log = json_logs[0]

    logged_messages = []
    with open(json_log, 'r') as f:
        for line in f:
            if line.strip():
                log_data = json.loads(line)
                logged_messages.append(log_data["level"])

    # Should only have WARNING and ERROR (not DEBUG or INFO)
    assert "DEBUG" not in logged_messages
    assert "INFO" not in logged_messages
    assert "WARNING" in logged_messages
    assert "ERROR" in logged_messages
