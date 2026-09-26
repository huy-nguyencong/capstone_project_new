from __future__ import annotations

import json
import logging
import os
import re
import sys
import traceback
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, TextIO

REDACTED = "[REDACTED]"
CORRELATION_FIELDS = (
    "request_id",
    "worker_id",
    "job_id",
    "camera_id",
    "ai_config_version_id",
    "track_id",
)
MAX_LOG_STRING = 2000
MAX_LOG_DEPTH = 4
MAX_LOG_ITEMS = 50

SENSITIVE_KEY = re.compile(
    r"^(?:.*[_.-])?(password|password_hash|passwd|secret|token|api_key|apikey|access_key|"
    r"secret_key|private_key|credential|credentials|rtsp_credentials|authorization|cookie|"
    r"session_id|embedding|embeddings|vector|vectors|values|frame|frame_bytes|image|"
    r"image_bytes|image_base64|raw_image|content|rtsp_url|connection_url|signed_url|"
    r"presigned_url|query|query_text|text_query|prompt|description)$",
    re.IGNORECASE,
)
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
_SIGNED_QUERY = re.compile(
    r"(?P<key>[?&](?:X-Amz-[A-Za-z-]+|Signature|AWSAccessKeyId|Expires|Policy|"
    r"Key-Pair-Id|token|access_token|sig|se|sp|sv|sr)=)[^&\s\"']+",
    re.IGNORECASE,
)
_NUMERIC_VECTOR = re.compile(
    r"[\[(]\s*(?:[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*,\s*){15,}"
    r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*,?\s*[\])]"
)
_BASE64_BLOB = re.compile(r"(?:data:[a-z/+.-]+;base64,)?[A-Za-z0-9+/]{160,}={0,2}")
_BYTES_LITERAL = re.compile(r"b(['\"])(?:\\x[0-9a-fA-F]{2}|[^'\"\\]){32,}\1")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_LINE_BREAKS = re.compile(r"[\r\n]+")

_EMPTY: Mapping[str, str] = MappingProxyType({})
_context: ContextVar[Mapping[str, str]] = ContextVar(
    "person_search_log_context", default=_EMPTY
)


def redact_text(value: str, *, multiline: bool = False) -> str:
    cleaned = _URL_CREDENTIALS.sub(lambda match: f"{match['scheme']}{REDACTED}@", value)
    cleaned = _SIGNED_QUERY.sub(lambda match: f"{match['key']}{REDACTED}", cleaned)
    cleaned = _NUMERIC_VECTOR.sub(REDACTED, cleaned)
    cleaned = _BYTES_LITERAL.sub(REDACTED, cleaned)
    cleaned = _BASE64_BLOB.sub(REDACTED, cleaned)
    cleaned = _CONTROL_CHARACTERS.sub(" ", cleaned)
    if not multiline:
        cleaned = _LINE_BREAKS.sub(" ", cleaned)
    return cleaned


def _numeric_sequence(value: list[Any] | tuple[Any, ...]) -> bool:
    return len(value) > 16 and all(
        isinstance(item, int | float) and not isinstance(item, bool) for item in value
    )


def redact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_LOG_DEPTH:
        return REDACTED
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_LOG_ITEMS:
                clean["_truncated"] = True
                break
            name = redact_text(str(key))
            clean[name] = (
                REDACTED if SENSITIVE_KEY.match(name) else redact_value(item, depth=depth + 1)
            )
        return clean
    if isinstance(value, list | tuple | set | frozenset):
        items = list(value)
        if _numeric_sequence(items):
            return REDACTED
        clean_items = [redact_value(item, depth=depth + 1) for item in items[:MAX_LOG_ITEMS]]
        if len(items) > MAX_LOG_ITEMS:
            clean_items.append("…")
        return clean_items
    if isinstance(value, bytes | bytearray | memoryview):
        return REDACTED
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    text = redact_text(str(value))
    if len(text) > MAX_LOG_STRING:
        text = text[:MAX_LOG_STRING] + "…"
    return text


def _clean_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    safe = "".join(char for char in text if char.isalnum() or char in "._:-")
    return safe[:128] or None


def current_context() -> dict[str, str]:
    return dict(_context.get())


def _merged_context(values: Mapping[str, Any]) -> Mapping[str, str]:
    unknown = set(values) - set(CORRELATION_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported log context fields: {sorted(unknown)}")
    merged = dict(_context.get())
    for key, value in values.items():
        cleaned = _clean_identifier(value)
        if cleaned is None:
            merged.pop(key, None)
        else:
            merged[key] = cleaned
    return MappingProxyType(merged)


@contextmanager
def log_context(**values: Any) -> Iterator[dict[str, str]]:
    merged = _merged_context(values)
    token = _context.set(merged)
    try:
        yield dict(merged)
    finally:
        _context.reset(token)


def bind_context(**values: Any) -> Token[Mapping[str, str]]:
    return _context.set(_merged_context(values))


def reset_context(token: Token[Mapping[str, str]]) -> None:
    _context.reset(token)


_STANDARD_ATTRIBUTES = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
    | {"message", "asctime", "taskName"}
    | set(CORRELATION_FIELDS)
)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = _context.get()
        for field in CORRELATION_FIELDS:
            explicit = getattr(record, field, None)
            value = explicit if explicit is not None else context.get(field)
            setattr(record, field, _clean_identifier(value))
        return True


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_person_search_redacted", False):
            return True
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = redact_text(message)
        record.args = ()
        for key, value in list(vars(record).items()):
            if key in _STANDARD_ATTRIBUTES or key.startswith("_"):
                continue
            setattr(record, key, REDACTED if SENSITIVE_KEY.match(key) else redact_value(value))
        if record.exc_info and record.exc_info[0] is not None:
            text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = redact_text(text, multiline=True)
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact_text(record.exc_text, multiline=True)
        if record.stack_info:
            record.stack_info = redact_text(record.stack_info, multiline=True)
        record._person_search_redacted = True
        return True


def record_extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in vars(record).items()
        if key not in _STANDARD_ATTRIBUTES and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        body: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in CORRELATION_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                body[field] = value
        extras = record_extras(record)
        if extras:
            body["extra"] = extras
        if record.exc_text:
            body["exception"] = record.exc_text
        if record.stack_info:
            body["stack"] = record.stack_info
        return json.dumps(body, ensure_ascii=False, default=str)


_HANDLER_MARKER = "_person_search_handler"


def install_filters(handler: logging.Handler) -> logging.Handler:
    if not any(isinstance(item, ContextFilter) for item in handler.filters):
        handler.addFilter(ContextFilter())
    if not any(isinstance(item, RedactionFilter) for item in handler.filters):
        handler.addFilter(RedactionFilter())
    return handler


def configure_logging(
    level: str | int | None = None,
    *,
    stream: TextIO | None = None,
    json_format: bool | None = None,
) -> logging.Handler:
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return handler
    handler = logging.StreamHandler(stream or sys.stderr)
    setattr(handler, _HANDLER_MARKER, True)
    use_json = (
        json_format
        if json_format is not None
        else os.getenv("PERSON_SEARCH_LOG_FORMAT", "json").lower() != "text"
    )
    handler.setFormatter(
        JsonFormatter()
        if use_json
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    install_filters(handler)
    root.addHandler(handler)
    root.setLevel(level or os.getenv("PERSON_SEARCH_LOG_LEVEL", "INFO").upper())
    return handler
