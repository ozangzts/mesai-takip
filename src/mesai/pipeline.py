"""Wiring: config -> read -> normalize -> merge -> compute -> report.

Each stage is a function of the previous stage's output. No stage reaches back.
"""

from __future__ import annotations

import calendar as _calendar
from collections import defaultdict
from collections.abc import Mapping
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
from . import snapshot as snapshot_module


class InputError(Exception):
    pass


def period_bounds(period: str) -> tuple[date, date]:
    year, month = (int(part) for part in period.split("-"))
    last = _calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def run(input_dir: Path, output_path: Path, period: str, settings: Settings,
        generated_at: datetime | None = None,
        roster_dir: Path | None = None,
        snapshot_path: Path | None = None,
        chosen: Mapping[str, Path] | None = None) -> dict[str, object]:
    """Read, compute, and write the report — plus its machine-readable snapshot.

    `snapshot_path` is where the data companion goes (see snapshot.py). Passing None
    skips it, which is what the tests do when they only care about figures.

    `chosen` names a file for a source outright, bypassing the glob in `input_dir` for
    that one source. The key `"roster"` works too, though the roster is not month
    specific and is looked up differently (ADR-035). It exists because the three exports do not always arrive in the
    same place — one may be e-mailed while the others sit on the share — and copying
    files around by hand before every run is the kind of step that eventually gets
    done wrong. Everything downstream is unchanged: the period filter still drops
    anything outside the month and still fails if a source contributes nothing
    (ADR-014), so a file from the wrong month cannot slip in this way. See ADR-022.
    """
    generated_at = generated_at or datetime.now()
    stats = RunStats()

    # --- stage 2: read -----------------------------------------------------
    # The roster is not a monthly file — it is a point-in-time snapshot of who
    # works here (ADR-011), so it lives outside the month folder. Still accepted
    # inside `input_dir` for the case where all four files arrive together.
    roster_path = _locate_roster(roster_dir, input_dir, settings,
                                 (chosen or {}).get("roster"))
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

    mac_path = _locate(input_dir, settings, "macunkoy", chosen)
    mac_records, mac_anomalies, mac_rows, excluded = macunkoy.read(mac_path, settings)
    records += mac_records
    anomalies.extend(mac_anomalies)
    stats.files["macunkoy"] = mac_path.name
    stats.rows_read["macunkoy"] = mac_rows
    stats.records_built["macunkoy"] = len(mac_records)
    stats.excluded_badges = excluded

    tek_path = _locate(input_dir, settings, "teknopark", chosen)
    tek_records, tek_anomalies, tek_rows = teknopark.read(tek_path, settings)
    records += tek_records
    anomalies.extend(tek_anomalies)
    stats.files["teknopark"] = tek_path.name
    stats.rows_read["teknopark"] = tek_rows
    stats.records_built["teknopark"] = len(tek_records)

    izin_path = _locate(input_dir, settings, "izin", chosen)
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
    stats.blank_workdays = _blank_workdays(records, period, settings)

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

    written_snapshot: Path | None = None
    if snapshot_path is not None:
        written_snapshot = snapshot_module.save(
            snapshot_module.build(period, summaries, anomalies, stats, settings,
                                  generated_at, workdays, leave),
            snapshot_path)

    return {
        "output": output_path,
        "snapshot": written_snapshot,
        "people": len(summaries),
        "with_attendance": sum(1 for s in summaries if s.has_attendance),
        "without_attendance": sum(1 for s in summaries if not s.has_attendance),
        "not_in_roster": sum(1 for s in summaries if not s.employee.in_roster),
        "workdays": len(workdays),
        "anomalies": len(anomalies),
        "excluded_anomalies": sum(
            1 for a in anomalies.items if a.severity == "excluded"),
        "partial_sources": [c for c in stats.coverage.values() if c.is_partial],
        "blank_workdays": list(stats.blank_workdays),
        "gross": measured_total,
        "stats": stats,
    }




def _unrecorded_days(
    anomalies: Collector, employees: dict[NameKey, Employee],
    by_key: dict[NameKey, list[WorkDay]], leave: list[LeaveRecord],
    expected: list[date],
) -> None:
    """An expected working day with no record of the person anywhere.

    No entry, no exit, no leave, no remote declaration, at either site. `EMPTY_RECORD`,
    the same note as a row whose times are blank, because the fact is the same: nothing
    was recorded for that day. It therefore also selects under `Giriş yok` and
    `Çıkış yok` (ADR-053).

    The gap this closed. `Hem giriş hem çıkış yok` needed a **row** with both times
    blank, so a day with no row at all raised nothing; `Ay büyük ölçüde boş` needs under
    half the month unaccounted for and `Mesai verisi yok` needs it entirely empty.
    Somebody who worked 17 of 22 days with nothing explaining the other five carried no
    note at all — 11 people in July 2026, the worst with 10 such days.

    **No condition of any kind.** Two were tried and both are gone (ADR-061):

    * an anchor at the person's first record of the month, so a mid-month joiner was not
      asked about days before they existed — but it silently swallowed the case it could
      not tell apart. Measured across June and July: of the people whose first record
      falls after the month's first working day, **13 of 15 and 11 of 16 had records in
      the previous month**, so they were not new at all and 60 and 45 days were being
      hidden. Distinguishing the two needs a hire date, which the roster does not carry
      (ROADMAP Q18).
    * skipping people already flagged `Ay büyük ölçüde boş`, to keep the tail quiet.
      Same shape: a threshold deciding what the operator gets to see.

    The rule is now the operator's: *"o kişinin günleri boşsa giriş-çıkış yok diye
    ekleyelim, yönetim karar versin."* Flagging somebody who turns out to have joined on
    the 20th costs one manual removal from a list; not flagging somebody whose records
    went missing costs their hours. This program says what it found and never guesses at
    payroll input (AGENTS §2.1).
    """
    if not expected:
        return
    covered: dict[NameKey, set[date]] = {}
    for record in leave:
        if record.start is None:
            continue
        day, last = record.start.date(), (record.end or record.start).date()
        while day <= last:
            covered.setdefault(record.key, set()).add(day)
            day += timedelta(days=1)

    for key, employee in employees.items():
        worked = {w.date for w in by_key.get(key, [])}
        if not worked:
            continue                 # `Mesai verisi yok` already says it, louder
        leave_days = covered.get(key, set())
        for day in expected:
            if day in worked or day in leave_days:
                continue
            anomalies.add(Anomaly(
                kind=AnomalyKind.EMPTY_RECORD, source="kayit-yok", source_row=0,
                key=key, raw_name=employee.display_name, date=day,
                detail="o gün için hiçbir tesiste kayıt yok; izin ve uzaktan "
                       "çalışma da yok",
            ))


def _blank_workdays(
    records: list[PunchRecord], period: str, settings: Settings,
) -> tuple[date, ...]:
    """Expected working days on which no attendance source recorded anything.

    The trailing check in `_coverage` cannot see a hole in the middle of an export, and
    a per-source mid-period check would fire on a site that was simply shut that day —
    which AGENTS §3 forbids for exactly that reason. A day where **neither** site saw a
    single person is the one mid-period shape that can be asserted: 162 people did not
    all stay home on an ordinary working day.

    Measured over May-July 2026: none. Not one expected working day is even missing from
    a single source, because the shut days are marked holidays and drop out of
    `expected_workdays` before this runs.
    """
    year, month = (int(part) for part in period.split("-"))
    seen = {r.date for r in records if r.source != "izin"}
    return tuple(day for day in settings.calendar.expected_workdays(year, month)
                 if day not in seen)


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
                   settings: Settings, chosen: Path | None = None) -> Path:
    """Find the employee roster, checking its own folder first then the month folder.

    Two layouts are supported deliberately: the roster kept once in
    `data/personel/` and shared by every month, or all four files dropped into one
    folder (which is what a Drive upload is likely to look like).

    `chosen` names the file outright, for the same reason the monthly sources can be
    named (ADR-022) and one more: this file is **not month-specific**, so once the
    program stopped running from a clone — a packaged executable on somebody's desktop
    — `data/personel/` beside it may simply not exist. ADR-035.
    """
    if chosen is not None:
        if not chosen.is_file():
            raise InputError(
                f"Personel listesi için seçilen dosya bulunamadı: {chosen}")
        return chosen

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


def _locate(input_dir: Path, settings: Settings, name: str,
            chosen: Mapping[str, Path] | None = None) -> Path:
    """Exactly one file per source.

    Two files matching the same pattern means two months sit in the folder. Picking
    one arbitrarily would silently report the wrong month, so it is an error.

    A file named in `chosen` wins outright — it was pointed at deliberately, so there
    is nothing to be ambiguous about. It is still checked for existence rather than
    assumed: a path can go stale between choosing it and pressing the button.
    """
    picked = (chosen or {}).get(name)
    if picked is not None:
        if not picked.is_file():
            raise InputError(
                f"'{name}' için seçilen dosya bulunamadı: {picked}"
            )
        return picked

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

    # And the same test per source. The check above only fires when *every* source is
    # the wrong month; one wrong file among three passed it, because the other two
    # kept records. Measured on the real May data with June's Teknopark export
    # substituted: the run succeeded, reported 4869:54 instead of 17103:58, and said
    # nothing — every one of the 2 557 Teknopark rows dropped out of period and the
    # coverage check never saw the source at all, because it only looks at what
    # survived the filter. A report 72 % short that looks entirely normal is the exact
    # failure this project exists to prevent. ADR-023.
    #
    # A source that read NOTHING is untouched by this: Teknopark legitimately has no
    # rows while the office is shut. Read rows, kept none, is a different thing.
    kept_sources = {record.source for record in kept}
    for source in sorted({record.source for record in records} - kept_sources):
        seen = sorted({r.date for r in records if r.source == source})
        raise InputError(
            f"'{source}' dosyasındaki hiçbir kayıt {period} dönemine ait değil — "
            f"büyük ihtimalle başka bir ayın dosyası.\n"
            f"  Beklenen aralık : {start} .. {end}\n"
            f"  Dosyadaki tarih : {seen[0]} .. {seen[-1]}\n"
            f"  Atılan kayıt    : {dropped[source]}\n\n"
            "Diğer kaynaklar bu döneme ait kayıt içeriyor, yani sorun tek dosyada.\n"
            "Bu dosya olduğu gibi kullanılsaydı rapor sessizce eksik çıkardı."
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

    year, month = (int(part) for part in period.split("-"))
    expected_workdays = settings.calendar.expected_workdays(year, month)
    expected_days = len(expected_workdays)

    # Days with no record of the person anywhere. Added BEFORE the counts are taken, so
    # `Şüpheli Kayıt` includes them.
    _unrecorded_days(anomalies, employees, by_key, leave, expected_workdays)

    anomaly_counts = anomalies.count_by_key()

    summaries: list[MonthSummary] = []
    for key, employee in employees.items():
        days = by_key.get(key, [])
        gross = timedelta()
        net = timedelta()
        for workday in days:
            gross += workday.gross
            net += workday.net

        # The displayed notes are not built here any more — they are the person's own
        # note labels, assembled after this loop so that every anomaly added inside it
        # is included. See the `notes=` pass below and ADR-049.
        has_attendance = bool(days)
        if not has_attendance:
            anomalies.add(Anomaly(
                kind=AnomalyKind.NO_ATTENDANCE_DATA, source="izin", source_row=0,
                key=key, raw_name=employee.display_name,
                detail="İzin kaydı var, hiçbir kart kaydı yok. Bu kişinin ayı eksik "
                       "görünüyor — kart sisteminden kontrol edilmeli",
            ))
        elif expected_days and settings.plausibility.sparse_month_ratio:
            # Deliberately `elif`: somebody with no attendance at all already has the
            # louder note above, and two notes for one situation reads as two problems.
            izin = leave_days.get(key, 0.0)
            covered = len(days) + izin
            share = covered / expected_days
            if share < settings.plausibility.sparse_month_ratio:
                anomalies.add(Anomaly(
                    kind=AnomalyKind.SPARSE_MONTH, source="izin", source_row=0,
                    key=key, raw_name=employee.display_name,
                    detail=f"{expected_days} iş gününün {covered:g} tanesi "
                           f"açıklanıyor (%{share * 100:.0f}) — çalışma "
                           f"{len(days)} gün, izin {izin:g} gün",
                ))
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
        ))

    # Anomalies added above are not yet in the per-person counts; refresh them, and
    # build each person's displayed notes from their own labels. One vocabulary: the
    # filter list, the review list and this column now say the same words, because they
    # read the same strings (ADR-049).
    #
    # `Personel listesinde yok` is the one note that is not a label. It is a fact about
    # the roster rather than a problem — somebody absent from it worked and keeps every
    # hour (ADR-011) — so it must not become an anomaly, and it is added here.
    refreshed = anomalies.count_by_key()
    labels = anomalies.labels_by_key()
    return [
        MonthSummary(
            employee=s.employee, period=s.period, gross=s.gross, net=s.net,
            worked_days=s.worked_days, remote_days=s.remote_days,
            leave_days=s.leave_days,
            anomaly_count=refreshed.get(s.employee.key, 0),
            has_attendance=s.has_attendance,
            notes=(labels.get(s.employee.key, ())
                   + (() if s.employee.in_roster else ("Personel listesinde yok",))),
        )
        for s in summaries
    ]
