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


class UnsupportedFormat(LayoutError):
    """The container format cannot be opened with what is installed."""


# Container formats and what opens them. `.xlsx`/`.xlsm` are ZIP-based and go to
# openpyxl; `.xls` is the OLE2/BIFF format Excel 97-2003 wrote and needs xlrd, which
# reads nothing else. `.xlsb` is deliberately absent — it has never arrived, and
# adding pyxlsb for a format we have not seen would be a dependency on speculation.
# If it ever turns up, `open_sheets` names it in the error so the fix is obvious.
_OPENPYXL_SUFFIXES = frozenset({".xlsx", ".xlsm"})
_XLRD_SUFFIXES = frozenset({".xls"})
SUPPORTED_SUFFIXES = _OPENPYXL_SUFFIXES | _XLRD_SUFFIXES


class Sheet:
    """One worksheet, read the same way whatever the container format was.

    Exists because the Macunköy export arrived as `.xls` in July 2026 after two
    months of `.xlsx`. Rather than teach four readers two libraries each, container
    weirdness is confined here and the readers see one interface.

    Coordinates are **1-based**, matching openpyxl, because the readers were written
    against it. `value()` out of range returns None rather than raising: a short row
    is data, not a structural fault.
    """

    __slots__ = ("name", "nrows", "ncols", "_rows")

    def __init__(self, name: str, rows: list[tuple]):
        self.name = name
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = max((len(r) for r in rows), default=0)

    def value(self, row: int, col: int) -> object:
        if not (1 <= row <= self.nrows):
            return None
        line = self._rows[row - 1]
        if not (1 <= col <= len(line)):
            return None
        return line[col - 1]

    def rows(self, start: int = 1):
        """Yield rows as tuples, padded to `ncols` so column indexing is uniform."""
        width = self.ncols
        for line in self._rows[start - 1:]:
            if len(line) < width:
                yield tuple(line) + (None,) * (width - len(line))
            else:
                yield tuple(line)


def open_sheets(path: Path) -> list[Sheet]:
    """Read every worksheet in `path` into memory as `Sheet` objects.

    Reading whole sheets up front is affordable here — the largest input is ~2 500
    rows — and it buys a single code path plus deterministic behaviour: no lazy
    iterator whose state depends on which library opened the file.
    """
    suffix = path.suffix.lower()
    if suffix in _OPENPYXL_SUFFIXES:
        return _open_openpyxl(path)
    if suffix in _XLRD_SUFFIXES:
        return _open_xlrd(path)
    raise UnsupportedFormat(
        f"{path.name}: '{suffix}' uzantısı desteklenmiyor. "
        f"Desteklenen: {', '.join(sorted(SUPPORTED_SUFFIXES))}. "
        "Dosya .xlsb ise Excel'de .xlsx olarak kaydedip tekrar deneyin."
    )


def _open_openpyxl(path: Path) -> list[Sheet]:
    import warnings

    import openpyxl

    # data_only=True so formula cells yield their cached value. read_only is NOT used:
    # the Teknopark file's 4 105 merged ranges are unsafe to read that way.
    #
    # The HCM leave export carries no default cell style, so openpyxl warns on every
    # load. Expected and harmless — it substitutes its own default and we read values
    # only. Suppressed narrowly, by message, so real warnings still surface.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="Workbook contains no default style",
            category=UserWarning)
        workbook = openpyxl.load_workbook(path, data_only=True)
    try:
        return [Sheet(ws.title, [tuple(r) for r in ws.iter_rows(values_only=True)])
                for ws in workbook.worksheets]
    finally:
        workbook.close()


def _open_xlrd(path: Path) -> list[Sheet]:
    try:
        import xlrd
    except ImportError as exc:      # pragma: no cover - environment problem
        raise UnsupportedFormat(
            f"{path.name}: .xls okumak için 'xlrd' paketi gerekiyor ama "
            "kurulu değil.  Kurulum:  pip install xlrd"
            "Kurulum:  pip install xlrd"
        ) from exc

    book = xlrd.open_workbook(path, on_demand=False)
    sheets: list[Sheet] = []
    for ws in book.sheets():
        rows: list[tuple] = []
        for r in range(ws.nrows):
            rows.append(tuple(
                _xlrd_cell(ws.cell_type(r, c), ws.cell_value(r, c), book.datemode)
                for c in range(ws.ncols)
            ))
        sheets.append(Sheet(ws.name, rows))
    return sheets


def _xlrd_cell(cell_type: int, value: object, datemode: int) -> object:
    """Normalise one xlrd cell so it looks like what openpyxl would have returned.

    The trap: xlrd hands back dates as bare floats (`46234.316`) with the type in a
    parallel field. Passing that through unconverted would make every timestamp a
    meaningless number, and `as_datetime` would return None for the lot — zero hours
    for everybody, reported as success.
    """
    import xlrd

    if cell_type in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if cell_type == xlrd.XL_CELL_DATE:
        converted = xlrd.xldate_as_datetime(value, datemode)
        # A pure time-of-day is stored as a fraction of day 0; keep it a time so
        # `as_time` recognises it instead of seeing the year 1899.
        if converted.year == 1899 and converted.month == 12:
            return converted.time()
        if (converted.hour, converted.minute, converted.second) == (0, 0, 0):
            return converted.date()
        return converted
    if cell_type == xlrd.XL_CELL_BOOLEAN:
        return bool(value)
    if cell_type == xlrd.XL_CELL_ERROR:
        return None
    if cell_type == xlrd.XL_CELL_NUMBER and float(value).is_integer():
        return int(value)
    return value


def find_header_row(
    sheet: Sheet, required: tuple[str, ...], search_rows: int = 10
) -> tuple[int, dict[str, int]]:
    """Locate the header row and map each header name to its 1-based column.

    Two source changes in July 2026 are the reason this exists:

    * the Macunköy export gained a title line above the header, so the header is no
      longer the first row
    * it dropped its `Personel` column, shifting every column after it left by one

    A reader using fixed indices would have read `SicilNo` as the employee name and
    `Bolum` as the date — confidently wrong. Deriving positions from the header makes
    both changes non-events. `AGENTS.md` §5 already required this for the roster;
    the same rule applies to every source.

    Raises LayoutError naming what was missing, because a genuinely unrecognisable
    layout must stop the run.
    """
    best_missing: list[str] | None = None
    for row_no in range(1, min(search_rows, sheet.nrows) + 1):
        header = {}
        for col in range(1, sheet.ncols + 1):
            text = as_text(sheet.value(row_no, col))
            if text:
                header.setdefault(text, col)
        missing = [name for name in required if name not in header]
        if not missing:
            return row_no, header
        if best_missing is None or len(missing) < len(best_missing):
            best_missing = missing

    raise LayoutError(
        f"{sheet.name}: beklenen kolonlar bulunamadı: {best_missing} — "
        f"ilk {min(search_rows, sheet.nrows)} satırda başlık aranıyor. "
        "Dosya yapısı değişmiş olabilir."
    )


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
