"""Where generated files go on this machine, and what the folder is called.

Separate from the screen that uses it because none of it is about widgets: finding the
Desktop is a platform question, and naming the output folder is a decision about what
the person who opens Explorer should see.
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from pathlib import Path

from .period import MONTHS

# FOLDERID_Desktop. Asked for by id rather than assumed to be `~/Desktop`, because a
# corporate machine with OneDrive redirection has its Desktop somewhere else entirely
# and writing the month's payroll report into a folder nobody looks at is a silent
# failure. Falls back to the obvious guess only when the API is unavailable.
_FOLDERID_DESKTOP = uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")


class _GUID(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, value: uuid.UUID) -> "_GUID":
        first, second, third = value.fields[:3]
        return cls(first, second, third, (ctypes.c_ubyte * 8)(*value.bytes[8:]))


def _known_desktop() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        buffer = ctypes.c_wchar_p()
        shell = ctypes.windll.shell32
        if shell.SHGetKnownFolderPath(ctypes.byref(_GUID.of(_FOLDERID_DESKTOP)), 0,
                                      None, ctypes.byref(buffer)) != 0:
            return None
        try:
            return Path(buffer.value) if buffer.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(buffer)
    except (AttributeError, OSError, ValueError):   # pragma: no cover - not Windows
        return None


def desktop_dir() -> Path:
    """The Desktop, or the best stand-in for it. Always an existing directory."""
    for candidate in (_known_desktop(), Path.home() / "Desktop", Path.home()):
        if candidate is not None and candidate.is_dir():
            return candidate
    return Path.home()                              # pragma: no cover - no home at all


def report_folder_name(period: str) -> str:
    """The folder one month's output goes in, as `2026-06 Rapor`.

    Year first so a directory of them sorts into date order on its own. This was
    briefly `06-2026 Rapor` — month first reads more naturally in Turkish — but twelve
    of those sort by month, putting January 2027 above May 2026. The trailing word
    still says what the folder is, which was the other half of the point. ADR-025.
    """
    return f"{period} Rapor"


def report_paths(output_dir: Path, period: str) -> tuple[Path, Path]:
    """The workbook and its snapshot, both inside one folder for the month."""
    folder = output_dir / report_folder_name(period)
    return (folder / f"mesai-raporu-{period}.xlsx",
            folder / f"gonderim-{period}.json")


def existing_report(output_dir: Path, period: str) -> Path | None:
    """The workbook a previous run left in this month's folder, if there is one.

    A second run for the same month overwrites in place — the folder is written into,
    not replaced — which is almost always what is wanted and is exactly what should be
    said out loud beforehand. Measured, not assumed: run twice and both files come back
    with fresh timestamps while anything else in the folder is left untouched.
    """
    workbook = report_paths(output_dir, period)[0]
    return workbook if workbook.is_file() else None
