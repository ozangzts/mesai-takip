"""Wiring: config -> read -> normalize -> merge -> compute -> report.

Each stage is a function of the previous stage's output. No stage reaches back.
"""

from __future__ import annotations

import calendar as _calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .anomalies import Anomaly, AnomalyKind, Collector
from .config import Settings
from .merge import build_workdays
from .models import (
    Employee, LeaveRecord, MonthSummary, NameKey, PunchRecord, RunStats,
    SourceCoverage, WorkDay,
)
from .readers import LayoutError, find_sources, izin, macunkoy, roster, teknopark
from .report import workbook as report_workbook


class InputError(Exception):
    pass


def period_bounds(period: str) -> tuple[date, date]:
    year, month = (int(part) for part in period.split("-"))
    last = _calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def run(input_dir: Path, output_path: Path, period: str, settings: Settings,
        generated_at: datetime | None = None,
        roster_dir: Path | None = None) -> dict[str, object]:
    generated_at = generated_at or datetime.now()
    stats = RunStats()

    # --- stage 2: read -----------------------------------------------------
    # The roster is not a monthly file — it is a point-in-time snapshot of who
    # works here (ADR-011), so it lives outside the month folder. Still accepted
    # inside `input_dir` for the case where all four files arrive together.
    roster_path = _locate_roster(roster_dir, input_dir, settings)
    roster_entries, roster_duplicates = roster.read(roster_path)
    stats.files["roster"] = roster_path.name
    stats.rows_read["roster"] = len(roster_entries) + len(roster_duplicates)
    stats.records_built["roster"] = len(roster_entries)
    stats.roster_duplicates = roster_duplicates
    # Its export date matters: a roster newer than the reporting period explains
    # leavers and new hires (ADR-011). Taken from the file, never hard-coded.
    stats.roster_date = datetime.fromtimestamp(roster_path.stat().st_mtime).date()

    anomalies = Collector()
    records: list[PunchRecord] = []

    mac_path = _locate(input_dir, settings, "macunkoy")
    mac_records, mac_anomalies, mac_rows, excluded = macunkoy.read(mac_path, settings)
    records += mac_records
    anomalies.extend(mac_anomalies)
    stats.files["macunkoy"] = mac_path.name
    stats.rows_read["macunkoy"] = mac_rows
    stats.records_built["macunkoy"] = len(mac_records)
    stats.excluded_badges = excluded

    tek_path = _locate(input_dir, settings, "teknopark")
    tek_records, tek_anomalies, tek_rows = teknopark.read(tek_path, settings)
    records += tek_records
    anomalies.extend(tek_anomalies)
    stats.files["teknopark"] = tek_path.name
    stats.rows_read["teknopark"] = tek_rows
    stats.records_built["teknopark"] = len(tek_records)

    izin_path = _locate(input_dir, settings, "izin")
    leave, remote, izin_anomalies, izin_rows, subtotals = izin.read(izin_path, settings)
    records += remote
    anomalies.extend(izin_anomalies)
    stats.files["izin"] = izin_path.name
    stats.rows_read["izin"] = izin_rows
    stats.records_built["izin"] = len(leave)
    stats.records_built["izin_uzaktan"] = len(remote)
    stats.rows_read["izin_ara_toplam_atlanan"] = subtotals

    # --- stage 2b: keep only what belongs to the reporting period ----------
    records, leave = _filter_to_period(records, leave, period, stats)

    # --- stage 2c: does each source actually cover the period? -------------
    # A file can be internally perfect and still describe half a month. July 2026's
    # Teknopark export stopped on the 19th and every other guard passed. ADR-020.
    stats.coverage = _coverage(records, period, settings)

    # --- stage 3: normalize / resolve identity -----------------------------
    employees = _resolve_employees(records, leave, roster_entries)

    # --- stage 4 + 5: merge and compute ------------------------------------
    workdays, merge_anomalies, accepted, union_total, measured_total = build_workdays(
        records, settings)
    anomalies.extend(merge_anomalies)
    stats.intervals_accepted = accepted
    stats.union_total = union_total
    stats.accepted_total = measured_total

    summaries = _summarise(period, employees, workdays, leave, anomalies, settings)

    # --- stage 6: report ---------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_workbook.build(
        path=output_path, period=period, summaries=summaries, workdays=workdays,
        employees=employees, leave=leave, anomalies=anomalies, stats=stats,
        settings=settings, generated_at=generated_at,
    )

    return {
        "output": output_path,
        "people": len(summaries),
        "with_attendance": sum(1 for s in summaries if s.has_attendance),
        "without_attendance": sum(1 for s in summaries if not s.has_attendance),
        "not_in_roster": sum(1 for s in summaries if not s.employee.in_roster),
        "workdays": len(workdays),
        "anomalies": len(anomalies),
        "excluded_anomalies": sum(
            1 for a in anomalies.items if a.severity == "excluded"),
        "partial_sources": [c for c in stats.coverage.values() if c.is_partial],
        "gross": measured_total,
        "stats": stats,
    }


def _coverage(
    records: list[PunchRecord], period: str, settings: Settings,
) -> dict[str, SourceCoverage]:
    """Per attendance source, how much of the period's working days it covers.

    Leave records are excluded: `izin` is not an attendance source and legitimately
    covers only the days somebody was away.
    """
    year, month = (int(part) for part in period.split("-"))
    expected = settings.calendar.expected_workdays(year, month)

    by_source: dict[str, set[date]] = defaultdict(set)
    for record in records:
        if record.source != "izin":
            by_source[record.source].add(record.date)

    coverage: dict[str, SourceCoverage] = {}
    for source, days in by_source.items():
        trailing: list[date] = []
        for day in reversed(expected):
            if day in days:
                break
            trailing.append(day)
        trailing.reverse()
        coverage[source] = SourceCoverage(
            source=source,
            present=sum(1 for day in expected if day in days),
            expected=len(expected),
            trailing_missing=tuple(trailing),
        )
    return coverage


def _locate_roster(roster_dir: Path | None, input_dir: Path,
                   settings: Settings) -> Path:
    """Find the employee roster, checking its own folder first then the month folder.

    Two layouts are supported deliberately: the roster kept once in
    `data/personel/` and shared by every month, or all four files dropped into one
    folder (which is what a Drive upload is likely to look like).
    """
    searched: list[Path] = []
    for candidate_dir in (roster_dir, input_dir):
        if candidate_dir is None or not candidate_dir.is_dir():
            if candidate_dir is not None:
                searched.append(candidate_dir)
            continue
        searched.append(candidate_dir)
        matches = find_sources(candidate_dir, settings.sources["roster"])

        # Safety net: the roster folder normally holds exactly one file, and whoever
        # exports it renames it freely. If no pattern matched but there is a single
        # spreadsheet sitting alone here, use it — the reader validates the layout,
        # so a wrong file fails loudly rather than producing wrong numbers.
        if not matches and candidate_dir == roster_dir:
            alone = find_sources(candidate_dir, ("*.xlsx",))
            if len(alone) == 1:
                return alone[0]

        if len(matches) > 1:
            listing = "\n".join(f"  - {p.name}" for p in matches)
            raise InputError(
                f"Personel listesi için {len(matches)} dosya bulundu, hangisinin "
                f"kullanılacağı belirsiz:\n{listing}\n\nKlasör: {candidate_dir}"
            )
        if matches:
            return matches[0]

    listing = "\n".join(f"  - {p}" for p in searched)
    raise InputError(
        "Personel listesi bulunamadı. Aranan desenler: "
        f"{list(settings.sources['roster'])}\nBakılan klasörler:\n{listing}"
    )


def _locate(input_dir: Path, settings: Settings, name: str) -> Path:
    """Exactly one file per source.

    Two files matching the same pattern means two months sit in the folder. Picking
    one arbitrarily would silently report the wrong month, so it is an error.
    """
    matches = find_sources(input_dir, settings.sources[name])
    if not matches:
        raise InputError(
            f"'{name}' dosyası bulunamadı. Aranan desenler: "
            f"{list(settings.sources[name])} — klasör: {input_dir}"
        )
    if len(matches) > 1:
        listing = "\n".join(f"  - {p.name}" for p in matches)
        raise InputError(
            f"'{name}' için {len(matches)} dosya bulundu, hangisinin "
            f"kullanılacağı belirsiz:\n{listing}\n\n"
            "Her ay için ayrı bir klasör kullanın (örn. data/raw/2026-06/), ya da "
            "config/settings.yaml içindeki deseni daraltın."
        )
    return matches[0]


def _filter_to_period(
    records: list[PunchRecord], leave: list[LeaveRecord], period: str, stats: RunStats,
) -> tuple[list[PunchRecord], list[LeaveRecord]]:
    """Drop anything dated outside the reporting month.

    `--ay` must be a filter, not just a label. Without this, pointing the tool at
    May's folder with `--ay 2026-06` produced a report full of May figures titled
    "HAZİRAN 2026" — silently wrong, which is the worst kind.
    """
    start, end = period_bounds(period)

    kept: list[PunchRecord] = []
    dropped: dict[str, int] = defaultdict(int)
    for record in records:
        if start <= record.date <= end:
            kept.append(record)
        else:
            dropped[record.source] += 1

    kept_leave = [
        r for r in leave
        if r.start is None or start <= r.start.date() <= end
    ]

    stats.out_of_period = dict(dropped)
    stats.out_of_period_leave = len(leave) - len(kept_leave)

    if records and not kept:
        seen = sorted({r.date for r in records})
        raise InputError(
            f"Dosyalardaki hiçbir kayıt {period} dönemine ait değil.\n"
            f"  Beklenen aralık : {start} .. {end}\n"
            f"  Dosyadaki tarih : {seen[0]} .. {seen[-1]}\n\n"
            "Yanlış klasör ya da yanlış --ay değeri verilmiş olabilir."
        )
    return kept, kept_leave


def _resolve_employees(
    records: list[PunchRecord], leave: list[LeaveRecord],
    roster_entries: dict[NameKey, object],
) -> dict[NameKey, Employee]:
    """Build the employee index.

    The roster ENRICHES identity and never determines it (ADR-011): a person with
    records but no roster entry is a leaver, gets a full row and keeps every hour.
    A roster entry with no activity in the period gets no row at all.
    """
    display: dict[NameKey, str] = {}
    sources: dict[NameKey, set[str]] = defaultdict(set)
    departments: dict[NameKey, str] = {}
    personnel_no: dict[NameKey, str] = {}

    for record in records:
        key = record.key
        sources[key].add(record.source)
        if record.department and key not in departments:
            departments[key] = record.department
        if record.badge_id and key not in personnel_no:
            personnel_no[key] = record.badge_id
        # Prefer the longest observed spelling: it carries the middle names the
        # roster drops, and HR recognises the full form.
        if len(record.raw_name) > len(display.get(key, "")):
            display[key] = record.raw_name

    for record in leave:
        key = record.key
        if record.personnel_no:
            personnel_no[key] = record.personnel_no   # HCM is canonical (ADR-009)
        if record.department and key not in departments:
            departments[key] = record.department
        if len(record.raw_name) > len(display.get(key, "")):
            display[key] = record.raw_name

    employees: dict[NameKey, Employee] = {}
    for key, name in display.items():
        entry = roster_entries.get(key)
        employees[key] = Employee(
            key=key,
            display_name=name,
            personnel_no=personnel_no.get(key),
            department=getattr(entry, "department", None) or departments.get(key),
            job_title=getattr(entry, "job_title", None),
            facility=getattr(entry, "facility", None),
            email=getattr(entry, "email", None),
            in_roster=entry is not None,
            sources=frozenset(sources.get(key, set())),
        )
    return employees


def _summarise(
    period: str, employees: dict[NameKey, Employee], workdays: list[WorkDay],
    leave: list[LeaveRecord], anomalies: Collector, settings: Settings,
) -> list[MonthSummary]:
    by_key: dict[NameKey, list[WorkDay]] = defaultdict(list)
    for workday in workdays:
        by_key[workday.key].append(workday)

    leave_days: dict[NameKey, float] = defaultdict(float)
    remote_days: dict[NameKey, float] = defaultdict(float)
    for record in leave:
        if record.leave_type in settings.worked_leave_types:
            remote_days[record.key] += record.days
        else:
            leave_days[record.key] += record.days

    anomaly_counts = anomalies.count_by_key()

    summaries: list[MonthSummary] = []
    for key, employee in employees.items():
        days = by_key.get(key, [])
        gross = timedelta()
        net = timedelta()
        for workday in days:
            gross += workday.gross
            net += workday.net

        notes: list[str] = []
        has_attendance = bool(days)
        if not has_attendance:
            notes.append("Mesai verisi yok")
            anomalies.add(Anomaly(
                kind=AnomalyKind.NO_ATTENDANCE_DATA, source="izin", source_row=0,
                key=key, raw_name=employee.display_name,
                detail="İzin kaydı var, hiçbir kart kaydı yok. Bu kişinin ayı eksik "
                       "görünüyor — kart sisteminden kontrol edilmeli",
            ))
        if not employee.in_roster:
            notes.append("Personel listesinde yok")
        if any("uzaktan-çakışma" in w.tags for w in days):
            notes.append("Uzaktan çalışma kart kaydıyla çakışıyor")
        if any("gece-geçişi" in w.tags for w in days):
            notes.append("Gece vardiyası düzeltmesi var")

        summaries.append(MonthSummary(
            employee=employee,
            period=period,
            gross=gross,
            net=net,
            worked_days=len(days),
            remote_days=round(remote_days.get(key, 0.0), 2),
            leave_days=round(leave_days.get(key, 0.0), 2),
            anomaly_count=anomaly_counts.get(key, 0),
            has_attendance=has_attendance,
            notes=tuple(notes),
        ))

    # Anomalies added above are not yet in the per-person counts; refresh them.
    refreshed = anomalies.count_by_key()
    return [
        MonthSummary(
            employee=s.employee, period=s.period, gross=s.gross, net=s.net,
            worked_days=s.worked_days, remote_days=s.remote_days,
            leave_days=s.leave_days,
            anomaly_count=refreshed.get(s.employee.key, 0),
            has_attendance=s.has_attendance, notes=s.notes,
        )
        for s in summaries
    ]
