"""Cross-site reconciliation — the correctness-critical stage.

76 employees appear in both attendance exports because Teknopark-based staff visit
the Macunköy site. Their records overlap in wall-clock time, so the day's intervals
are UNIONED before anything is measured — never summed per file (ADR-001).

The union removes double counting; it is not itself the hours figure. How the merged
day becomes hours is `worktime.measure()` and, by default, spans first entry to last
exit (ADR-015).

This module also performs cross-site repair of one-sided records (ADR-003): a
missing punch may be resolved against a timestamp another terminal actually
recorded, but never against an invented one.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from .anomalies import Anomaly, AnomalyKind
from .config import Settings
from .models import Interval, NameKey, PunchRecord, WorkDay
from .rules import worktime


def build_workdays(
    records: list[PunchRecord], settings: Settings
) -> tuple[list[WorkDay], list[Anomaly], int, timedelta, timedelta]:
    """Group records per person-day, union their intervals, compute hours.

    Returns (workdays, anomalies, accepted_interval_count, union_total, measured_total).

    The last two are deliberately separate. `union_total` is presence only — the sum
    of the accepted intervals. `measured_total` is what the report pays, which under
    ADR-015 also includes the gaps inside each day. The Kontrol sheet reconciles
    per-person totals against `measured_total` and shows the difference between the
    two, so the cost of the envelope rule is never invisible.
    """
    grouped: dict[tuple[NameKey, object], list[PunchRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.key, record.date)].append(record)

    workdays: list[WorkDay] = []
    anomalies: list[Anomaly] = []
    accepted_count = 0
    union_total = timedelta()
    measured_total = timedelta()

    for (key, day), day_records in grouped.items():
        complete: list[Interval] = []
        orphans: list[PunchRecord] = []

        day_records, drop_note = _apply_remote_precedence(
            day_records, key, day, settings)
        if drop_note is not None:
            anomalies.append(drop_note)

        for record in day_records:
            interval, notes = worktime.build_interval(record, settings)
            anomalies.extend(notes)
            if interval is not None:
                complete.append(interval)
            elif record.entry is not None or record.exit is not None:
                if not any(n.kind is AnomalyKind.IMPLAUSIBLE_DURATION for n in notes):
                    orphans.append(record)

        tags: set[str] = set()
        repaired, repair_notes, repair_tags = _repair_orphans(
            orphans, complete, settings)
        complete.extend(repaired)
        anomalies.extend(repair_notes)
        tags |= repair_tags

        merged = worktime.merge_intervals(complete)
        if not merged:
            continue

        accepted_count += len(merged)
        union_total += worktime.gross_duration(merged)
        gross, deduction, net = worktime.measure(merged, settings)
        measured_total += gross

        for interval in merged:
            if "uzaktan" in interval.sources:
                tags.add("uzaktan")
            if len(interval.sources - {"uzaktan"}) > 1:
                tags.add("çapraz-tesis")
        if any(a.kind is AnomalyKind.NEGATIVE_DURATION and a.key == key
               and a.date == day for a in anomalies):
            tags.add("gece-geçişi")

        remote_note = _remote_overlap(day_records, merged, key, settings)
        if remote_note is not None:
            anomalies.append(remote_note)
            # Only the real-punch case gets a tag. The nominal case is expected
            # behaviour and is already marked by the `uzaktan` tag; tagging it
            # `çakışma` made 37 ordinary remote days read as defects (ADR-017).
            if remote_note.kind is AnomalyKind.REMOTE_OVERLAP_REAL:
                tags.add("uzaktan-çakışma")

        if gross < settings.plausibility.short_day:
            anomalies.append(Anomaly(
                kind=AnomalyKind.SHORT_DAY, source=day_records[0].source,
                source_row=day_records[0].source_row, key=key,
                raw_name=day_records[0].raw_name, date=day,
                raw_entry=f"{merged[0].start:%H:%M}",
                raw_exit=f"{merged[-1].end:%H:%M}",
                detail=f"günlük süre {worktime.hhmm(gross)}, eşik "
                       f"{worktime.hhmm(settings.plausibility.short_day)}",
            ))
            tags.add("kısa-gün")

        workdays.append(WorkDay(
            key=key, date=day, intervals=merged, gross=gross,
            break_deduction=deduction, net=net, tags=frozenset(tags),
        ))

    workdays.sort(key=lambda w: (w.key, w.date))
    return workdays, anomalies, accepted_count, union_total, measured_total


def _apply_remote_precedence(
    day_records: list[PunchRecord], key: NameKey, day: object, settings: Settings,
) -> tuple[list[PunchRecord], Anomaly | None]:
    """On a declared remote-work day, let the remote hours stand alone — ADR-018.

    HR's instruction: for a remote day, take the remote hours. The reason it is not
    unconditional is what the attendance side actually contains:

    * a nominal `09:00–18:00` placeholder is not evidence of anything. Dropping it and
      keeping the declaration loses nothing and stops a 9-hour placeholder stretching
      the day to 10:30. This is 35 of 37 May cases and 75 of 80 in June.
    * a real turnstile reading IS evidence — somebody walked through a door. Dropping
      it would discard recorded work: on 2026-06-23 the person badged out at 18:34
      while their declaration ended at 13:45, so `always` would pay 6:15 instead of
      11:04. Seven person-days across the two months are like this.

    `nominal_only` therefore drops placeholders and keeps real punches. `always`
    applies HR's instruction literally; `never` restores pre-ADR-018 behaviour.
    """
    mode = settings.remote_replaces
    if mode == "never":
        return day_records, None

    remote = [r for r in day_records if r.tag == "uzaktan"
              and r.entry is not None and r.exit is not None]
    if not remote:
        return day_records, None

    attendance = [r for r in day_records if r.tag != "uzaktan"]
    if not attendance:
        return day_records, None

    nominal = settings.nominal_day
    if mode == "nominal_only":
        if nominal is None:
            return day_records, None
        # Every attendance record must be a placeholder. A single real punch means the
        # day has evidence we are not entitled to throw away.
        if not all(nominal.matches(r.source, r.entry, r.exit) for r in attendance):
            return day_records, None

    dropped = ", ".join(
        f"{r.entry:%H:%M}-{r.exit:%H:%M}" if r.entry and r.exit else "eksik kayıt"
        for r in attendance)
    note = Anomaly(
        kind=AnomalyKind.REMOTE_REPLACED_NOMINAL, source="izin",
        source_row=remote[0].source_row, key=key, raw_name=remote[0].raw_name,
        date=remote[0].date,
        raw_entry=", ".join(f"{r.entry:%H:%M}-{r.exit:%H:%M}" for r in remote),
        raw_exit=dropped,
        detail="uzaktan çalışma saatleri esas alındı, puantajdaki kayıt "
               "hesaba katılmadı",
    )
    return remote, note


def _repair_orphans(
    orphans: list[PunchRecord], complete: list[Interval], settings: Settings
) -> tuple[list[Interval], list[Anomaly], set[str]]:
    """Resolve one-sided records against complete intervals from another source.

    Three outcomes per orphan:
      * its timestamp falls inside a known interval -> discard, it adds nothing
      * it falls outside and extends the day -> add the real gap as an interval
      * neither -> write it off as zero hours with a MISSING_* anomaly
    """
    if not orphans:
        return [], [], set()

    added: list[Interval] = []
    notes: list[Anomaly] = []
    tags: set[str] = set()

    known = worktime.merge_intervals(complete) if complete else ()

    for record in orphans:
        stamp = record.entry or record.exit
        is_entry = record.entry is not None
        missing_kind = (AnomalyKind.MISSING_EXIT if is_entry
                        else AnomalyKind.MISSING_ENTRY)

        if stamp is None:
            notes.append(_note(AnomalyKind.EMPTY_RECORD, record))
            continue

        if any(iv.start <= stamp <= iv.end for iv in known):
            tags.add("çapraz-eşleşti")
            continue

        if known:
            earliest = min(iv.start for iv in known)
            latest = max(iv.end for iv in known)
            if is_entry and stamp < earliest:
                gap = earliest - stamp
                if gap <= settings.plausibility.max_duration:
                    added.append(Interval(start=stamp, end=earliest,
                                          sources=frozenset({record.source})))
                    notes.append(_note(
                        AnomalyKind.CROSS_SITE_EXTENDED, record,
                        detail=f"giriş {stamp:%H:%M}, diğer tesis kaydı "
                               f"{earliest:%H:%M} başlıyor; arada "
                               f"{worktime.hhmm(gap)} eklendi"))
                    tags.add("çapraz-eşleşti")
                    continue
            if not is_entry and stamp > latest:
                gap = stamp - latest
                if gap <= settings.plausibility.max_duration:
                    added.append(Interval(start=latest, end=stamp,
                                          sources=frozenset({record.source})))
                    notes.append(_note(
                        AnomalyKind.CROSS_SITE_EXTENDED, record,
                        detail=f"çıkış {stamp:%H:%M}, diğer tesis kaydı "
                               f"{latest:%H:%M} bitiyor; arada "
                               f"{worktime.hhmm(gap)} eklendi"))
                    tags.add("çapraz-eşleşti")
                    continue

        notes.append(_note(missing_kind, record))

    return added, notes, tags


def _remote_overlap(
    day_records: list[PunchRecord], merged: tuple[Interval, ...], key: NameKey,
    settings: Settings,
) -> Anomaly | None:
    """Note a remote-work day that also carries an attendance record.

    **Expected, not a defect** (ADR-017). The Teknopark timesheet writes a nominal
    9-hour day when a workday has no turnstile data, and a declared remote day is one
    of the things that triggers it — 37 of 39 such overlaps in May 2026 and 76 of 83
    in June had a nominal `09:00–18:00` row on the attendance side rather than a real
    punch. Whichever it is, the record is counted and the union counts the shared time
    once. Emitted at `info` severity so the audit trail is complete without implying
    that 21 people did something wrong.
    """
    remote = [r for r in day_records if r.tag == "uzaktan"]
    badged = [r for r in day_records
              if r.tag != "uzaktan" and r.entry is not None and r.exit is not None]
    if not remote or not badged:
        return None

    for r in remote:
        if r.entry is None or r.exit is None:
            continue
        for b in badged:
            if b.entry is None or b.exit is None:
                continue
            if r.entry < b.exit and b.entry < r.exit:
                kind, detail = _classify_overlap(b, settings)
                return Anomaly(
                    kind=kind, source="izin",
                    source_row=r.source_row, key=key, raw_name=r.raw_name,
                    date=r.date,
                    raw_entry=f"{r.entry:%H:%M}-{r.exit:%H:%M} (uzaktan)",
                    raw_exit=f"{b.entry:%H:%M}-{b.exit:%H:%M} ({b.source})",
                    detail=detail,
                )
    return None


def _classify_overlap(
    badged: PunchRecord, settings: Settings
) -> tuple[AnomalyKind, str]:
    """Placeholder or real punch — two different questions, so two anomaly kinds.

    A nominal `09:00–18:00` line means the person did not badge in and the timesheet
    filled the day in: the overwhelming majority, and nothing to ask about. A real
    punch on a declared remote day is the rare case worth a question — 2 of 39 in
    May 2026, 7 of 83 in June.

    With no `nominal_day` configured every overlap is reported as the real-punch case.
    That is the safe direction: it over-asks rather than silently calling a real punch
    expected.
    """
    nominal = settings.nominal_day
    if nominal is not None and nominal.matches(
            badged.source, badged.entry, badged.exit):
        return (AnomalyKind.REMOTE_OVERLAP,
                "puantajdaki kayıt nominal tam gün, turnike okuması değil — "
                "çakışan süre bir kez sayıldı")
    return (AnomalyKind.REMOTE_OVERLAP_REAL,
            "puantajdaki kayıt gerçek turnike okuması — çakışan süre bir kez "
            "sayıldı, kişi o gün binaya girmiş görünüyor")


def _note(kind: AnomalyKind, record: PunchRecord, detail: str = "") -> Anomaly:
    return Anomaly(
        kind=kind, source=record.source, source_row=record.source_row,
        key=record.key, raw_name=record.raw_name, date=record.date,
        raw_entry=record.entry.strftime("%d.%m.%Y %H:%M:%S") if record.entry else "",
        raw_exit=record.exit.strftime("%d.%m.%Y %H:%M:%S") if record.exit else "",
        detail=detail,
    )
