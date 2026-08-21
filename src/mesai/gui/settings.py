"""What the window remembers between runs, in one file that no screen can clobber.

`arayuz-ayarlari.json` started as the report screen's private business — the browse
location, the output folder, the roster. Then a second screen needed to remember
something, and the way the first one saved was `write_text(json.dumps(its own three
keys))`: a full overwrite, built from scratch. Whichever screen saved last would have
silently dropped the other's setting, and nothing would have said so — the same silent
shape as the byte-order-mark bug this file already had once (ADR-036).

So writing is **read, modify, write**, in one place, and a screen names only the keys it
owns.

Read with `utf-8-sig`: a byte-order mark makes a perfectly valid file unreadable to the
strict decoder, and everything that writes this file other than us — Notepad,
PowerShell's `Set-Content` — adds one. Written as plain UTF-8, so we never add one
ourselves.

Failure is deliberately quiet in both directions. A window that cannot remember a folder
is a small inconvenience; a window that refuses to open because a settings file is
unreadable, or a run that fails because the install is read-only, is not.
"""

from __future__ import annotations

import json
from pathlib import Path

FILE_NAME = "arayuz-ayarlari.json"


def path_for(base: Path) -> Path:
    return base / FILE_NAME


def load(base: Path) -> dict[str, object]:
    """Everything the file holds, or an empty dict if it cannot be read."""
    try:
        stored = json.loads(path_for(base).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def update(base: Path, **values: object) -> None:
    """Set these keys, leave every other key in the file alone."""
    payload = load(base)
    payload.update(values)
    try:
        path_for(base).write_text(json.dumps(payload, ensure_ascii=False),
                                  encoding="utf-8")
    except OSError:
        pass            # a read-only install is not worth failing a run over
