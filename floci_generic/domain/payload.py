"""Turning what a cloud returns into something JSON-safe and small."""
import base64
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

OUTPUT_LIMIT = 20_000
BODY_READ_LIMIT = 64 * 1024


def _bytes(data: bytes | bytearray) -> str:
    try:
        return bytes(data).decode("utf-8")
    except UnicodeDecodeError:
        return base64.b64encode(bytes(data)).decode()


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def plain(obj: Any) -> Any:
    """Convert boto3 types (datetime, Decimal, bytes, streaming bodies) into JSON-safe values."""
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return _number(obj)
    if isinstance(obj, (bytes, bytearray)):
        return _bytes(obj)
    if hasattr(obj, "read") and hasattr(obj, "close"):  # StreamingBody
        data = obj.read(BODY_READ_LIMIT + 1)
        return _bytes(data[:BODY_READ_LIMIT]) + ("…[truncated]" if len(data) > BODY_READ_LIMIT else "")
    return obj


def cap(value: Any, limit: int = OUTPUT_LIMIT) -> Any:
    """Return value, or a preview of it when its JSON form is longer than limit characters."""
    text = json.dumps(value, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": True, "total_chars": len(text), "preview": text[:limit]}
