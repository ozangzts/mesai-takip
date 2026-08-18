"""Reading a human spelling of a month, and writing one back.

Pure functions, no widgets: this is the part of the window with real logic in it, and
it is tested without a display. It lives outside any one screen because the period is
not a report-screen concept — anything that reports on a month needs the same parsing
and the same Turkish label.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..normalize import fold

MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
          "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{MONTHS[int(month) - 1]} {year}"


# Nobody names their folders the way the tool would like. Observed in practice:
# `2026-07`, `06-2026`, `Temmuz 2026`. Rather than demand one spelling, recognise the
# ones a person would plausibly type — and refuse the genuinely ambiguous ones.
_YEAR_MIN, _YEAR_MAX = 2000, 2099

# Folded (ASCII, uppercase) Turkish month names -> number. Folding matters: `MAYIS`
# and `MAYıS` must both match, which bare .upper() gets wrong in Turkish.
_MONTH_BY_NAME = {fold(name): number for number, name in enumerate(MONTHS, start=1)}

# Two numbers with an optional separator, or six run-together digits.
_NUMERIC = re.compile(r"(?<!\d)(\d{1,4})\s*[-_./\ ]\s*(\d{1,4})(?!\d)")
_SIX_DIGITS = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _is_year(value: int) -> bool:
    return _YEAR_MIN <= value <= _YEAR_MAX


def _is_month(value: int) -> bool:
    return 1 <= value <= 12


def parse_period(text: str) -> str | None:
    """Normalise a human spelling of a month into `YYYY-MM`, or None if unclear.

    Accepts, in any of `- _ . / \\ space` or run together:
        2026-07   2026-7   202607   2026 Temmuz
        07-2026   7-2026   072026   Temmuz 2026
    and finds them inside a longer name (`Mesai 2026-07 Girdi`).

    **Refuses rather than guesses** when the year is not identifiable — `03-04` could
    be March 2004 or April 2003, and picking one silently is exactly the kind of
    plausible-wrong answer this project exists to avoid. The order is resolved by
    which part is a four-digit year, never by assuming a convention.
    """
    if not text:
        return None
    raw = text.strip()

    # A month NAME plus a year settles the order on its own.
    folded = fold(raw)
    for name, number in _MONTH_BY_NAME.items():
        if name in folded:
            for match in re.finditer(r"(?<!\d)(\d{4})(?!\d)", raw):
                if _is_year(int(match.group(1))):
                    return f"{int(match.group(1))}-{number:02d}"
            return None                      # month named, year missing or implausible

    for first, second in _NUMERIC.findall(raw):
        a, b = int(first), int(second)
        year_first = len(first) == 4 and _is_year(a) and _is_month(b)
        year_second = len(second) == 4 and _is_year(b) and _is_month(a)
        if year_first and not year_second:
            return f"{a}-{b:02d}"
        if year_second and not year_first:
            return f"{b}-{a:02d}"
        # Neither part is a four-digit year, or somehow both are: ambiguous, refuse.

    for (digits,) in ((m.group(1),) for m in _SIX_DIGITS.finditer(raw)):
        head, tail = int(digits[:4]), int(digits[4:])
        if _is_year(head) and _is_month(tail):
            return f"{head}-{tail:02d}"
        head2, tail2 = int(digits[:2]), int(digits[2:])
        if _is_year(tail2) and _is_month(head2):
            return f"{tail2}-{head2:02d}"
    return None


def guess_period(folder: Path) -> str | None:
    """The month this folder is for, read off its own name then its parent's."""
    for candidate in (folder.name, folder.parent.name if folder.parent else ""):
        period = parse_period(candidate)
        if period:
            return period
    return None
