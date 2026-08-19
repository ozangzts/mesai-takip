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
    """The folder one month's output goes in, as `06-2026 Rapor`.

    Named for the person who opens Explorer, not for the program: `2026-06` is how the
    period is written everywhere inside the tool, but a folder on someone's Desktop
    reads better with the month first and the word that says what it is.

    The cost is sort order — twelve of these sort by month, so December 2025 lands
    between November and... whichever month sorts next. Accepted deliberately: the
    folders are opened one at a time, right after being made.
    """
    year, month = period.split("-")
    return f"{month}-{year} Rapor"


def report_paths(output_dir: Path, period: str) -> tuple[Path, Path]:
    """The workbook and its snapshot, both inside one folder for the month."""
    folder = output_dir / report_folder_name(period)
    return (folder / f"mesai-raporu-{period}.xlsx",
            folder / f"gonderim-{period}.json")


def month_folder_label(period: str) -> str:
    """`Haziran 2026 · 06-2026 Rapor` — what the window shows under the folder box."""
    year, month = period.split("-")
    return f"{MONTHS[int(month) - 1]} {year} · {report_folder_name(period)}"
