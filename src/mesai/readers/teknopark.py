"""Teknopark timesheet export — per-person blocks, not a table.

1 224 rows x 14 columns, 4 105 merged ranges, 110 per-person blocks laid out in two
independent vertical streams: blocks starting in column A (56 of them) and blocks
starting in column H (54).

Block anatomy, `c` = the block's first column (1 for A, 8 for H):

    row r        c   : "Adı Soyadı:"        c+3 : <employee name>
    row r+k      c   : "Tarih"              c+2 : "Giriş Tarih Saat"
                                            c+4 : "Çıkış Tarih Saat"
                                            c+5 : "Çalışma Süresi"
    ...          c   : <date>               c+2 : entry (STRING)
                                            c+4 : exit  (STRING)
                                            c+5 : duration
    row t        c+1 : "Dönemdeki Toplam Çalışma Süresi"   c+5 : <total>

Three traps, all of which produced silently wrong output before being fixed:

1. **`k` is not constant.** The header sits 1 row below the marker in 61 blocks,
   2 rows in 9, and 3 rows in 40. Never assume a fixed offset — locate the header by
   searching for the literal "Tarih" in the block's own column.

2. **Blank rows appear between data rows.** Stopping at the first empty date cell
   loses more than half the file: 769 rows read instead of 1 607. The block ends at
   its "Dönemdeki Toplam" line, not at the first gap.

3. **Entry and exit are STRINGS** (`04.05.2026 07:35`), not datetimes. A naive
   isinstance(v, datetime) check yields zero hours for all 110 people while
   appearing to succeed.

The total line is also a gift: it is the source system's own figure per person, so
every block is cross-checked against it and a disagreement is reported.

`base.open_sheets` reads the whole sheet up front, which sidesteps the merged-range
problem entirely — openpyxl's `read_only` mode is what mishandles them.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ..anomalies import Anomaly, AnomalyKind
from ..config import Settings
from ..models import PunchRecord
from ..normalize import name_key
from .base import (
    LayoutError, as_date, as_datetime, as_duration, as_text, clean_name, open_sheets,
)

SOURCE = "teknopark"
MARKER = "Adı Soyadı"
HEADER = "Tarih"
TOTAL = "Dönemdeki Toplam"

_OFF_NAME = 3
_OFF_ENTRY = 2
_OFF_EXIT = 4
_OFF_DURATION = 5
_OFF_TOTAL_LABEL = 1
_OFF_TOTAL_VALUE = 5

# Tolerance when comparing our computed block total against the file's own figure.
# The source rounds to whole minutes per row, so small drift is expected.
_TOTAL_TOLERANCE = timedelta(minutes=2)


def read(path: Path, settings: Settings) -> tuple[list[PunchRecord], list[Anomaly], int]:
    """Returns (records, anomalies, rows_read)."""
    sheets = open_sheets(path)
    if not sheets:
        raise LayoutError(f"{path.name}: dosyada hiç sayfa yok")
    sheet = sheets[0]

    markers: list[tuple[int, int]] = []
    headers: set[tuple[int, int]] = set()
    totals: dict[tuple[int, int], object] = {}

    for row_no in range(1, sheet.nrows + 1):
        for col_no in range(1, sheet.ncols + 1):
            value = sheet.value(row_no, col_no)
            if not isinstance(value, str):
                continue
            if MARKER in value:
                markers.append((row_no, col_no))
            elif value.strip() == HEADER:
                headers.add((row_no, col_no))
            elif TOTAL in value:
                # Label sits one column right of the block's first column.
                totals[(row_no, col_no - _OFF_TOTAL_LABEL)] = sheet.value(
                    row_no, col_no - _OFF_TOTAL_LABEL + _OFF_TOTAL_VALUE)

    if not markers:
        raise LayoutError(
            f"{path.name}: '{MARKER}' işaretçisi hiç bulunamadı — dosya yapısı "
            "değişmiş olabilir."
        )

    header_rows_by_col: dict[int, list[int]] = {}
    for row_no, col in headers:
        header_rows_by_col.setdefault(col, []).append(row_no)
    for rows in header_rows_by_col.values():
        rows.sort()

    total_rows_by_col: dict[int, list[int]] = {}
    for (row_no, col) in totals:
        total_rows_by_col.setdefault(col, []).append(row_no)
    for rows in total_rows_by_col.values():
        rows.sort()

    records: list[PunchRecord] = []
    anomalies: list[Anomaly] = []
    rows_read = 0

    for header_row_marker, col in sorted(markers):
        name = as_text(sheet.value(header_row_marker, col + _OFF_NAME))
        if not name:
            anomalies.append(Anomaly(
                kind=AnomalyKind.UNPARSEABLE_ROW, source=SOURCE,
                source_row=header_row_marker, detail="blok başlığında isim yok",
            ))
            continue

        header_row = _next_after(header_rows_by_col.get(col, []), header_row_marker)
        if header_row is None:
            anomalies.append(Anomaly(
                kind=AnomalyKind.UNPARSEABLE_ROW, source=SOURCE,
                source_row=header_row_marker, raw_name=clean_name(name),
                detail=f"'{HEADER}' başlık satırı bulunamadı",
            ))
            continue

        end_row = _next_after(total_rows_by_col.get(col, []), header_row)
        if end_row is None:
            end_row = sheet.nrows + 1

        display = clean_name(name)
        key = settings.personnel.resolve(name_key(display))
        block_records: list[PunchRecord] = []

        for row_no in range(header_row + 1, end_row):
            date_cell = sheet.value(row_no, col)
            if date_cell is None:
                continue                      # blank spacer row, not the block end
            if isinstance(date_cell, str) and MARKER in date_cell:
                break
            rows_read += 1

            day = as_date(date_cell)
            if day is None:
                anomalies.append(Anomaly(
                    kind=AnomalyKind.UNPARSEABLE_ROW, source=SOURCE,
                    source_row=row_no, raw_name=display,
                    detail=f"tarih okunamadı: {date_cell!r}",
                ))
                continue

            block_records.append(PunchRecord(
                source=SOURCE,
                source_row=row_no,
                raw_name=display,
                key=key,
                date=day,
                entry=as_datetime(sheet.value(row_no, col + _OFF_ENTRY)),
                exit=as_datetime(sheet.value(row_no, col + _OFF_EXIT)),
                reported_duration=as_text(sheet.value(row_no, col + _OFF_DURATION)),
            ))

        records.extend(block_records)

        note = _check_block_total(
            display, key, block_records, totals.get((end_row, col)), end_row)
        if note is not None:
            anomalies.append(note)

    if not records:
        raise LayoutError(
            f"{path.name}: {len(markers)} blok bulundu ama hiç kayıt okunamadı — "
            "giriş/çıkış hücrelerinin biçimi değişmiş olabilir."
        )
    return records, anomalies, rows_read


def _next_after(sorted_rows: list[int], after: int) -> int | None:
    for row_no in sorted_rows:
        if row_no > after:
            return row_no
    return None


def _check_block_total(
    display: str, key: tuple[str, str], block: list[PunchRecord],
    reported: object, row_no: int,
) -> Anomaly | None:
    """Cross-check the block against the source system's own period total.

    This is the strongest available validation of the block parser: if we lose rows
    or read the wrong column, the totals diverge and the report says so.
    """
    expected = as_duration(reported) if reported is not None else None
    if expected is None:
        return None

    computed = timedelta()
    for record in block:
        row_duration = as_duration(record.reported_duration)
        if row_duration is not None:
            computed += row_duration

    if abs(computed - expected) <= _TOTAL_TOLERANCE:
        return None

    return Anomaly(
        kind=AnomalyKind.DURATION_MISMATCH, source=SOURCE, source_row=row_no,
        key=key, raw_name=display,
        detail=(f"blok toplamı uyuşmuyor: satırların toplamı "
                f"{_hhmm(computed)}, dosyadaki 'Dönemdeki Toplam' "
                f"{_hhmm(expected)} ({len(block)} satır okundu)"),
    )


def _hhmm(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    return f"{total // 3600}:{(total % 3600) // 60:02d}"
