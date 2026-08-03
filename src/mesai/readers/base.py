"""Shared reader helpers.

A reader is FAITHFUL: it does not fix, clean or interpret. Negative durations,
missing punches and visitor badges all pass through untouched. Correction happens
in rules/, once, for every source.

A reader NEVER raises on bad data — unparseable rows become anomalies. It raises
only when the file itself is unopenable or the layout is unrecognised, because a
structural change in a monthly export must fail loudly rather than quietly halve
someone's hours.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from ..normalize import display_name


class LayoutError(Exception):
    """The file does not have the structure this reader was written for."""


_DATETIME_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")


def as_datetime(value: object) -> datetime | None:
    """Parse a cell into a datetime. Handles both real datetimes and strings.

    The Teknopark export stores entry/exit as STRINGS (`04.05.2026 07:35`). A naive
    isinstance(v, datetime) check yields zero hours for every person while appearing
    to succeed — see docs/DATA-SOURCES.md §2.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time())
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


def as_time(value: object) -> time | None:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(text, fmt).time()
            except ValueError:
                continue
    return None


def as_duration(value: object) -> timedelta | None:
    """Parse an `HH:MM` duration. Returns None for the malformed values the
    Macunköy export produces on midnight crossing (`-15:-52`)."""
    if isinstance(value, timedelta):
        return value
    if isinstance(value, str) and ":" in value:
        parts = value.strip().split(":")
        try:
            hours, minutes = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        if hours < 0 or minutes < 0:
            return None
        return timedelta(hours=hours, minutes=minutes)
    if isinstance(value, (int, float)):
        return timedelta(days=float(value))
    return None


def as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_name(value: object) -> str:
    return display_name(value)


def find_sources(directory: Path, patterns: tuple[str, ...]) -> list[Path]:
    """Every distinct file in `directory` matching any pattern.

    Excel lock files (`~$...`) and our own output are ignored. Results are
    deduplicated because several patterns can match the same file — and because
    pathlib's glob is case-insensitive on Windows.
    """
    found: dict[Path, None] = {}
    for pattern in patterns:
        for candidate in sorted(directory.glob(pattern)):
            if candidate.name.startswith("~$"):
                continue
            if candidate.name.startswith("mesai-raporu"):
                continue
            found.setdefault(candidate.resolve(), None)
    return list(found)
