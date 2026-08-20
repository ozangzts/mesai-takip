"""Reading and writing the holiday list without losing what the file says about itself.

`config/takvim-<yıl>.yaml` is loaded like any other config, but it is also the one config
file the **window** writes back to. That rules out dumping it with PyYAML: the file
carries the note explaining what depends on it, and that note has already been wrong
once (ADR-040). A round-trip that deletes it would delete the only warning a future
reader gets.

So the date block is edited **as lines**. Everything outside it — comments,
`weekly_rest_days`, blank lines, the order of the file — is copied through untouched.

**A list of dates, and nothing else.** The dates used to carry a name each
(`Emek ve Dayanışma Günü`) and there was briefly a second block for the company's own
closures. Both are gone: a day is a holiday or it is not, nothing in the program ever
read the name, and whoever marks the days knows why they marked them (ADR-045). The two
older shapes are still **read**, so an existing calendar is not silently emptied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HOLIDAYS = "holidays"
# An older shape, read and migrated on the next save, never written.
_RETIRED_BLOCK = "admin_holidays"

_ITEM = re.compile(r"^\s+-\s*(\d{4}-\d{2}-\d{2})\s*(#.*)?$")
_MAPPING = re.compile(r"^\s+(\d{4}-\d{2}-\d{2})\s*:.*$")
_BLOCK_START = re.compile(r"^([a-z_]+):\s*$")
_INDENT = "  "


class CalendarFileError(Exception):
    """The file cannot be edited safely — never a partial write."""


def path_for(config_dir: Path, year: int) -> Path:
    return config_dir / f"takvim-{year}.yaml"


def read(path: Path) -> set[date]:
    """Every holiday in the file, whichever of the three shapes it is written in."""
    if not path.is_file():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    days = set(_dates(_body(lines, HOLIDAYS)))
    days.update(_dates(_body(lines, _RETIRED_BLOCK)))
    return days


def write(path: Path, days: set[date]) -> None:
    """Replace the holiday block, leaving every other line alone.

    Written to a temporary file and moved into place: this file decides which days are
    working days, and a half-written one is worse than an unwritten one.
    """
    if not isinstance(days, (set, frozenset)):
        raise CalendarFileError(f"tarih kümesi beklendi, {type(days).__name__} geldi")

    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    # A retired block is taken over rather than left standing. Leaving it would keep the
    # same day in two places, and un-marking it later would bring it back from the one
    # nothing writes any more.
    if _bounds(lines, _RETIRED_BLOCK):
        days = set(days) | set(_dates(_body(lines, _RETIRED_BLOCK)))
        lines = _drop(lines, _RETIRED_BLOCK)
    lines = _replace(lines, HOLIDAYS, days)

    text = "\n".join(lines).rstrip("\n") + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


# --- the block, as lines ----------------------------------------------------

def _bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    start = next((index for index, line in enumerate(lines)
                  if (match := _BLOCK_START.match(line)) and match.group(1) == name),
                 None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines):
        if lines[end].strip() and not lines[end].startswith(" "):
            break
        end += 1
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    return start, end


def _body(lines: list[str], name: str) -> list[str]:
    bounds = _bounds(lines, name)
    return lines[bounds[0] + 1:bounds[1]] if bounds else []


def _dates(body: list[str]) -> list[date]:
    found = []
    for line in body:
        match = _ITEM.match(line) or _MAPPING.match(line)
        if match:
            found.append(date.fromisoformat(match.group(1)))
    return found


def _drop(lines: list[str], name: str) -> list[str]:
    bounds = _bounds(lines, name)
    if bounds is None:
        return lines
    start, end = bounds
    while start > 0 and not lines[start - 1].strip():
        start -= 1                    # and the blank line that separated it
    return lines[:start] + lines[end:]


@dataclass(frozen=True)
class _Comments:
    heading: list[str]                # comments introducing the block
    above: dict[date, list[str]]      # comment lines belonging to one date


def _comments(body: list[str]) -> _Comments:
    """Take the block apart so a rewrite can put every comment back where it was.

    One ambiguity is resolved by convention: a comment run immediately before the FIRST
    date reads as an introduction to the block, while a run before any later date
    explains that date. Both shapes have been in the shipped file.
    """
    heading: list[str] = []
    above: dict[date, list[str]] = {}
    pending: list[str] = []
    first = True
    for line in body:
        match = _ITEM.match(line) or _MAPPING.match(line)
        if match:
            day = date.fromisoformat(match.group(1))
            if first:
                heading, first = pending, False
            else:
                above[day] = pending
            pending = []
        elif line.lstrip().startswith("#"):
            pending.append(line)
    # Comments after the last date belong to no date; they are block-level notes and
    # have to survive, so they join the heading.
    return _Comments(heading=(pending if first else heading + pending), above=above)


def _replace(lines: list[str], name: str, days: set[date]) -> list[str]:
    bounds = _bounds(lines, name)
    if bounds is None:
        if not days:
            return lines
        return lines + ["", f"{name}:"] + [
            f"{_INDENT}- {day.isoformat()}" for day in sorted(days)]

    start, end = bounds
    comments = _comments(lines[start + 1:end])
    body: list[str] = []
    for day in sorted(days):
        body.extend(comments.above.get(day, ()))
        body.append(f"{_INDENT}- {day.isoformat()}")
    return lines[:start] + [f"{name}:"] + comments.heading + body + lines[end:]
