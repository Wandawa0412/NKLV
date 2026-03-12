"""Shared date parsing and formatting helpers."""
from __future__ import annotations

from datetime import date, datetime


DISPLAY_DATE_FORMAT = "%d/%m/%Y"
STORAGE_DATE_FORMAT = "%Y-%m-%d"

_KNOWN_FORMATS = (
    STORAGE_DATE_FORMAT,
    DISPLAY_DATE_FORMAT,
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)


def parse_date(value: object) -> date | None:
    """Parse a date-like value into a ``date`` object."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    for fmt in _KNOWN_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_display_date(value: object) -> str:
    parsed = parse_date(value)
    return parsed.strftime(DISPLAY_DATE_FORMAT) if parsed else ""


def format_storage_date(value: object) -> str:
    parsed = parse_date(value)
    return parsed.strftime(STORAGE_DATE_FORMAT) if parsed else ""


def month_key(value: object) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m") if parsed else ""
