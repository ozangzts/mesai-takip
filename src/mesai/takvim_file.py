"""Reading and writing the calendar file without losing what it says about itself.

`config/takvim-<yıl>.yaml` is loaded like any other config, but it is also the one
config file the **window** writes back to. That rules out dumping it with PyYAML: the
file carries thirty lines of comments explaining where each date came from, which of
them are inferred, and what depends on the file — and the comment about what depends on
it has already been wrong once (ADR-040). A round-trip that deletes those comments would
delete the only warning a future reader gets.

So the two date blocks are edited **as lines**. Everything outside them — comments,
`weekly_rest_days`, `half_days`, blank lines, the order of the file — is copied through
untouched. The blocks themselves are simple enough for this to be safe rather than
clever: one `  YYYY-MM-DD: "label"` per line, and nothing else is allowed in them.

**One** kind of non-working day. There were briefly two — statutory and
administrative — and they were merged again on the day they shipped, for the reason
that killed the distinction: nothing calculated them differently. Both took the day out
of the expected working days and nothing else, so the split bought a label and cost the
operator a decision at every click. A day is a holiday or it is not (ADR-043).

`admin_holidays` is still **read** if a file has it, and folded into the one map, so a
calendar written during the day the split existed does not silently lose days.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

HOLIDAYS = "holidays"
# Read for compatibility, never written. See the module docstring.
_RETIRED = "admin_holidays"
BLOCKS = (HOLIDAYS,)

_ENTRY = re.compile(r"^(\s+)(\d{4}-\d{2}-\d{2})\s*:\s*(.*?)\s*$")
_BLOCK_START = re.compile(r"^([a-z_]+):\s*$")
_INDENT = "  "


class CalendarFileError(Exception):
    """The file cannot be edited safely — never a partial write."""


def path_for(config_dir: Path, year: int) -> Path:
    return config_dir / f"takvim-{year}.yaml"


def read(path: Path) -> dict[str, dict[date, str]]:
    """The two date blocks, as `{block: {date: label}}`. Missing blocks come back empty.

    Deliberately not `yaml.safe_load`: writing goes through the line editor below, and
    reading the same way is what keeps the two halves agreeing about what a block is.
    """
    found: dict[str, dict[date, str]] = {name: {} for name in BLOCKS}
    if not path.is_file():
        return found
    readable = (*BLOCKS, _RETIRED)

    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0] if raw.lstrip().startswith("#") else raw
        if not line.strip():
            continue
        start = _BLOCK_START.match(line)
        if start:
            current = start.group(1) if start.group(1) in readable else None
            continue
        if current is None:
            continue
        if not line.startswith(" "):        # a new top-level key ends the block
            current = None
            continue
        entry = _ENTRY.match(line)
        if entry:
            day = date.fromisoformat(entry.group(2))
            block = HOLIDAYS if current == _RETIRED else current
            found[block][day] = _unquote(entry.group(3).split("#", 1)[0].strip())
    return found


def write(path: Path, blocks: dict[str, dict[date, str]]) -> None:
    """Replace the date block in place, leaving every other line alone.

    A block that exists in the file is rewritten where it stands; one that does not is
    appended with its own heading. Written to a temporary file and moved into place, so
    an interrupted save cannot leave a half-written calendar behind — this file decides
    which days are working days.
    """
    for name in blocks:
        if name not in BLOCKS:
            raise CalendarFileError(f"bilinmeyen blok: {name!r}")

    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    # A retired block is taken over rather than left standing. Leaving it would write
    # the same day twice — once here, once in a block nothing writes any more — and
    # un-marking the day later would bring it back from the stale copy.
    retired = _parse_block(_block_body(lines, _RETIRED)).labels
    if retired:
        adopted = dict(blocks.get(HOLIDAYS) or {})
        for day, label in retired.items():
            adopted.setdefault(day, label)
        blocks = {**blocks, HOLIDAYS: adopted}
        lines = _drop_block(lines, _RETIRED)

    for name, entries in blocks.items():
        lines = _replace_block(lines, name, entries)

    text = "\n".join(lines).rstrip("\n") + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)



def _block_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    start = next((index for index, line in enumerate(lines)
                  if _BLOCK_START.match(line)
                  and _BLOCK_START.match(line).group(1) == name), None)
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


def _block_body(lines: list[str], name: str) -> list[str]:
    bounds = _block_bounds(lines, name)
    return lines[bounds[0] + 1:bounds[1]] if bounds else []


def _drop_block(lines: list[str], name: str) -> list[str]:
    bounds = _block_bounds(lines, name)
    if bounds is None:
        return lines
    start, end = bounds
    while start > 0 and not lines[start - 1].strip():
        start -= 1                    # take the blank line that separated it
    return lines[:start] + lines[end:]


def _replace_block(lines: list[str], name: str,
                   entries: dict[date, str]) -> list[str]:
    bounds = _block_bounds(lines, name)
    if bounds is None:
        if not entries:
            return lines
        return lines + ["", f"{name}:"] + [
            f"{_INDENT}{day.isoformat()}: {_quote(label)}"
            for day, label in sorted(entries.items())]
    start, end = bounds

    # A comment sitting above an entry explains THAT entry — the shipped file has two
    # lines above 15 July saying why it is not an inference — so it travels with the
    # date and is dropped with it. Comments before the first entry describe the block
    # and stay at its top. Hoisting everything to the top instead passed every
    # synthetic test and changed the real file, which is what
    # `test_the_real_config_survives_a_round_trip_unchanged` is for.
    old = _parse_block(lines[start + 1:end])
    body: list[str] = []
    for day, label in sorted(entries.items()):
        body.extend(old.above.get(day, ()))
        # A trailing note like `# INFERRED` describes the label beside it, so it is
        # kept only while that label is unchanged. Carrying "INFERRED" onto a date
        # somebody has just relabelled would turn a preserved comment into a false one.
        was = old.labels.get(day)
        suffix = old.trailing.get(day, "") if was == label else ""
        body.append(f"{_INDENT}{day.isoformat()}: {_quote(label)}{suffix}")
    return lines[:start] + [f"{name}:"] + old.heading + body + lines[end:]


@dataclass(frozen=True)
class _Block:
    heading: list[str]                    # comments introducing the block
    above: dict[date, list[str]]          # comment lines belonging to one date
    trailing: dict[date, str]             # the `# ...` after a date's value
    labels: dict[date, str]               # the label each date had on disk


def _parse_block(block: list[str]) -> _Block:
    """Take a block apart so a rewrite can put every comment back where it was.

    One ambiguity has to be resolved by convention: a comment run immediately before
    the FIRST entry reads as an introduction to the block, while a run before any later
    entry explains that entry. Both shapes are in the shipped file — the note about
    listing the whole year opens the block, the two lines about 15 July belong to
    15 July — and this is the reading that keeps both in place.
    """
    heading: list[str] = []
    above: dict[date, list[str]] = {}
    trailing: dict[date, str] = {}
    labels: dict[date, str] = {}
    pending: list[str] = []
    first = True

    for line in block:
        entry = _ENTRY.match(line)
        if entry:
            day = date.fromisoformat(entry.group(2))
            if first:
                heading, first = pending, False
            else:
                above[day] = pending
            pending = []
            value = entry.group(3)
            marker = value.find("#")
            labels[day] = _unquote(value[:marker].strip() if marker >= 0
                                   else value.strip())
            if marker >= 0:
                trailing[day] = value[len(value[:marker].rstrip()):]
        elif line.lstrip().startswith("#"):
            pending.append(line)

    # Comments after the last entry belong to no date. They are block-level notes and
    # must survive, so they join the heading rather than being dropped.
    if first:
        heading = pending
    else:
        heading = heading + pending
    return _Block(heading=heading, above=above, trailing=trailing, labels=labels)


def _quote(label: str) -> str:
    cleaned = label.replace('"', "'").strip() or "Tatil"
    return f'"{cleaned}"'


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value
