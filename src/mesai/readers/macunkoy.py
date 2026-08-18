"""Macunköy badge-terminal export — flat log, one row per person-day.

Layout is discovered, never assumed. As of July 2026 this file has changed shape
three times in three months (docs/DATA-SOURCES.md D10):

    May/June    .xlsx, header on row 1, 11 columns incl. `Personel`
    July        .xls,  header on row 2 (a title line above it), 10 columns,
                `Personel` dropped so everything after it shifted left

So: the container is opened by `base.open_sheets` (which handles both formats), the
header row is *found*, and every column is addressed **by name**. The previous version
used fixed indices and would have read `SicilNo` as the employee name and `Bolum` as
the date — confidently wrong, and only stopped by the header check.

Only `Ad`, `Soyad`, `MesaiTarih`, `Giris` and `Cikis` are required. `Personel`,
`SicilNo`, `Bolum` and `SureSaat` are used when present and skipped when not: the
full name can always be rebuilt from `Ad` + `Soyad`.

Health: poor. 388 of 1 209 May rows are missing a punch, 29 have a negative duration,
23 identities are visitor/temporary badges. None of that is fixed here — the reader
passes it through and the rules layer decides.
"""

from __future__ import annotations

from pathlib import Path

from ..anomalies import Anomaly, AnomalyKind
from ..config import Settings
from ..models import PunchRecord
from ..normalize import fold, is_excluded, name_key
from .base import (
    LayoutError, as_date, as_datetime, as_text, clean_name, find_header_row,
    open_sheets,
)

SOURCE = "macunkoy"

# Without these the file cannot be interpreted at all.
REQUIRED_HEADERS = ("Ad", "Soyad", "MesaiTarih", "Giris", "Cikis")
# Used when present. `Personel` is the pre-July full-name column.
OPTIONAL_HEADERS = ("Personel", "SicilNo", "Bolum", "SureSaat")


def read(path: Path, settings: Settings) -> tuple[list[PunchRecord], list[Anomaly], int, int]:
    """Returns (records, anomalies, rows_read, excluded_badge_rows)."""
    sheets = open_sheets(path)
    if not sheets:
        raise LayoutError(f"{path.name}: dosyada hiç sayfa yok")
    sheet = sheets[0]

    header_row, columns = find_header_row(sheet, REQUIRED_HEADERS)
    col = {name: columns[name] for name in REQUIRED_HEADERS}
    for name in OPTIONAL_HEADERS:
        if name in columns:
            col[name] = columns[name]

    records: list[PunchRecord] = []
    anomalies: list[Anomaly] = []
    rows_read = 0
    excluded = 0

    def cell(row: tuple, name: str) -> object:
        index = col.get(name)
        if index is None or index > len(row):
            return None
        return row[index - 1]

    for offset, row in enumerate(sheet.rows(header_row + 1)):
        row_no = header_row + 1 + offset
        if row is None or all(c is None for c in row):
            continue
        rows_read += 1

        full = as_text(cell(row, "Personel"))
        given = as_text(cell(row, "Ad"))
        surname = as_text(cell(row, "Soyad"))
        if not full and not given:
            anomalies.append(Anomaly(
                kind=AnomalyKind.UNPARSEABLE_ROW, source=SOURCE, source_row=row_no,
                detail="isim kolonu boş",
            ))
            continue
        display = clean_name(full or f"{given} {surname or ''}")

        if is_excluded(display, given, surname, settings.personnel.exclude_prefixes):
            excluded += 1
            continue

        raw_date = cell(row, "MesaiTarih")
        day = as_date(raw_date)
        if day is None:
            anomalies.append(Anomaly(
                kind=AnomalyKind.UNPARSEABLE_ROW, source=SOURCE, source_row=row_no,
                raw_name=display, detail=f"tarih okunamadı: {raw_date!r}",
            ))
            continue

        records.append(PunchRecord(
            source=SOURCE,
            source_row=row_no,
            raw_name=display,
            key=settings.personnel.resolve(name_key(display)),
            date=day,
            entry=as_datetime(cell(row, "Giris")),
            exit=as_datetime(cell(row, "Cikis")),
            badge_id=_badge(cell(row, "SicilNo")),
            department=as_text(cell(row, "Bolum")),
            reported_duration=as_text(cell(row, "SureSaat")),
        ))

    if not records:
        raise LayoutError(
            f"{path.name}: {rows_read} satır okundu ama hiç kayıt üretilemedi — "
            "başlık bulundu ama veri satırları beklenen biçimde değil."
        )
    return records, anomalies, rows_read, excluded


def _badge(value: object) -> str | None:
    """Keep only numeric personnel numbers. `SN`-prefixed values are card numbers
    that do not correspond to anything else (docs/DATA-SOURCES.md D5) and must
    never reach the report."""
    text = as_text(value)
    if not text:
        return None
    if fold(text).startswith("SN"):
        return None
    return text
