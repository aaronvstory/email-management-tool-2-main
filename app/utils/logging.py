import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging import Logger
from pathlib import Path
from typing import Any, Dict

_DEF_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON with fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name
    - message: Log message
    - module: Module name
    - function: Function name
    - line: Line number
    - exc_info: Exception info (if present)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        # Add extra fields if present (for structured logging)
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, default=str)


class _Formatter(logging.Formatter):
    """Simple formatter for console output."""
    def format(self, record: logging.LogRecord) -> str:
        # Minimal structured fields; avoid leaking sensitive data
        record.message = record.getMessage()
        return super().format(record)


def setup_app_logging(app, log_dir: str = "logs", log_level: str = "INFO") -> None:
    """
    Attach timestamped file logging and console logging to Flask app.logger.

    Features:
    - Timestamped log files (app_YYYY-MM-DD_HHMMSS.log)
    - Keeps only last 3 log files (auto-cleanup)
    - JSON and text formats
    - Console logging with simple format for development
    - Thread-safe operation

    Args:
        app: Flask application instance
        log_dir: Directory for log files (default: "logs")
        log_level: Minimum log level (default: "INFO")
    """
    try:
        logger: Logger = app.logger  # type: ignore

        # Get log level from environment or parameter
        level_name = os.getenv("LOG_LEVEL", log_level).upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)

        # Create log directory if it doesn't exist
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Create timestamped log filenames
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        json_log_file = log_path / f"app_{timestamp}.json.log"
        text_log_file = log_path / f"app_{timestamp}.log"

        # Cleanup old log files - keep only last 3 of each type
        def cleanup_old_logs(pattern: str, keep: int = 3):
            """Remove old log files, keeping only the most recent 'keep' files."""
            try:
                log_files = sorted(log_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
                for old_log in log_files[keep:]:
                    try:
                        old_log.unlink()
                        print(f"[Cleanup] Removed old log: {old_log.name}", file=sys.stderr)
                    except Exception as e:
                        print(f"[Cleanup] Failed to remove {old_log.name}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[Cleanup] Failed to cleanup logs: {e}", file=sys.stderr)

        cleanup_old_logs("app_*.json.log", keep=3)
        cleanup_old_logs("app_*.log", keep=3)

        # Remove existing file handlers (if any) to force fresh timestamped files
        # Keep track of whether we had a console handler
        had_console_handler = False
        for handler in logger.handlers[:]:  # Copy list to avoid modification during iteration
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
                handler.close()
            elif isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                had_console_handler = True

        # 1. JSON File Handler (timestamped) - always create fresh
        json_handler = logging.FileHandler(
            json_log_file,
            encoding="utf-8"
        )
        json_handler.setLevel(level)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

        # 2. Plain Text File Handler (timestamped) - always create fresh
        text_handler = logging.FileHandler(
            text_log_file,
            encoding="utf-8"
        )
        text_handler.setLevel(level)
        text_handler.setFormatter(_Formatter(_DEF_FORMAT))
        logger.addHandler(text_handler)

        # 3. Console Handler (for development) - only add if not already present
        if os.getenv("TESTING") != "1" and not had_console_handler:  # Skip console in tests
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(_Formatter(_DEF_FORMAT))
            logger.addHandler(console_handler)

        # Add request/response logging via before/after hooks if Flask app context supports it
        try:
            from flask import request
            @app.before_request
            def _log_request():
                logger.info(f"HTTP {request.method} {request.path}")
            @app.after_request
            def _log_response(resp):
                try:
                    logger.info(f"HTTP {request.method} {request.path} -> {resp.status_code}")
                except Exception:
                    pass
                return resp
        except Exception:
            pass

        logger.propagate = False

        # Also capture Werkzeug (HTTP request) logs into the same files
        try:
            wz = logging.getLogger('werkzeug')
            wz.setLevel(level)
            for h in logger.handlers:
                wz.addHandler(h)
            wz.propagate = False
        except Exception:
            pass

        logger.info(f"Logging initialized: level={level_name}, json_log={json_log_file}, text_log={text_log_file}")

    except Exception as e:
        # Fallback to stderr if logging setup fails
        print(f"ERROR: Failed to setup logging: {e}", file=sys.stderr)


__all__ = ["setup_app_logging", "JSONFormatter"]
