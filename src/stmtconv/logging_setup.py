"""Redaction at handler boundaries; never serialize arbitrary object reprs."""

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

PRIVATE_FIELDS = {
    "description",
    "raw_text",
    "payee",
    "name",
    "api_key",
    "password",
    "token",
    "secret",
    "authorization",
}
MANAGED_HANDLERS: list[logging.Handler] = []
STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def redact_text(text: str) -> str:
    text = re.sub(r"\d{8,}", lambda match: "*" * (len(match[0]) - 4) + match[0][-4:], text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REDACTED]", text)
    return re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[KEY REDACTED]", text)


def private_field(key: str) -> bool:
    return key.lower() in PRIVATE_FIELDS or key.lower().endswith(
        ("_api_key", "_password", "_token", "_secret")
    )


def redact_value(value: object, key: str = "") -> object:
    if private_field(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        # Identifier-like integers must also be masked.
        return redact_text(str(value)) if isinstance(value, int) and len(str(value)) >= 8 else value
    return "[UNSUPPORTED VALUE]"


def private_strings(value: object, key: str = "") -> list[str]:
    if private_field(key) and isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for k, v in value.items() for text in private_strings(v, str(k))]
    if isinstance(value, (list, tuple)):
        return [text for v in value for text in private_strings(v)]
    return []


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        extras = {k: v for k, v in record.__dict__.items() if k not in STANDARD_FIELDS}
        private = private_strings(extras) + private_strings(record.args)
        message = record.getMessage()
        for text in private:
            if text:
                message = message.replace(text, "[REDACTED]")
        record.msg = redact_text(message)
        record.args = ()
        for key, value in extras.items():
            setattr(record, key, redact_value(value, key))
        if record.exc_info:
            record.error_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            record.exc_info = None
        # Traceback/stack text may contain transaction data and is not logged.
        record.exc_text = None
        record.stack_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": {k: v for k, v in record.__dict__.items() if k not in STANDARD_FIELDS},
        }
        return json.dumps(payload, ensure_ascii=False, default=lambda value: "[UNSUPPORTED VALUE]")


def configure_logging(workspace: Path, level: str) -> logging.Logger:
    directory = workspace / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in MANAGED_HANDLERS:
        root.removeHandler(handler)
        handler.close()
    MANAGED_HANDLERS.clear()
    for handler in root.handlers:
        handler.addFilter(RedactionFilter())
    file_handler = RotatingFileHandler(
        directory / "stmtconv.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    console = RichHandler(show_time=False, show_path=False, markup=False, rich_tracebacks=False)
    for handler in [file_handler, console]:
        handler.addFilter(RedactionFilter())
        MANAGED_HANDLERS.append(handler)
        root.addHandler(handler)
    root.setLevel(level)
    for name in ["docling", "rapidocr", "RapidOCR", "pdfminer"]:
        logging.getLogger(name).setLevel(logging.WARNING)
    return logging.getLogger("stmtconv")
