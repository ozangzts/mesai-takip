"""Cross-site reconciliation — the correctness-critical stage.

76 employees appear in both attendance exports because Teknopark-based staff visit
the Macunköy site. Their records overlap in wall-clock time, so hours must be
measured on the UNION of intervals per person-day, not the sum of the files.

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
) -> tuple[list[WorkDay], list[Anomaly], int, timedelta]:
    """Group records per person-day, union their intervals, compute hours.

    Returns (workdays, anomalies, accepted_interval_count, accepted_total_duration).
    The last two feed the reconciliation invariant on the Kontrol sheet.
    """
    grouped: dict[tuple[NameKey, object], list[PunchRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.key, record.date)].append(record)

    workdays: list[WorkDay] = []
    anomalies: list[Anomaly] = []
    accepted_count = 0
    accepted_total = timedelta()

    for (key, day), day_records in grouped.items():
        complete: list[Interval] = []
        orphans: list[PunchRecord] = []

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
        gross = worktime.gross_duration(merged)
        accepted_total += gross

        deduction = worktime.break_deduction(merged, gross, settings)
        net = gross - deduction
        if net < timedelta():
            net = timedelta()

        for interval in merged:
            if "uzaktan" in interval.sources:
                tags.add("uzaktan")
            if len(interval.sources - {"uzaktan"}) > 1:
                tags.add("çapraz-tesis")
        if any(a.kind is AnomalyKind.NEGATIVE_DURATION and a.key == key
               and a.date == day for a in anomalies):
            tags.add("gece-geçişi")

        remote_note = _remote_overlap(day_records, merged, key)
        if remote_note is not None:
            anomalies.append(remote_note)
            tags.add("uzaktan-çakışma")

        workdays.append(WorkDay(
            key=key, date=day, intervals=merged, gross=gross,
            break_deduction=deduction, net=net, tags=frozenset(tags),
        ))

    workdays.sort(key=lambda w: (w.key, w.date))
    return workdays, anomalies, accepted_count, accepted_total


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
    day_records: list[PunchRecord], merged: tuple[Interval, ...], key: NameKey
) -> Anomaly | None:
    """Flag a remote-work day where the person also physically badged in.

    The union already counts the overlap once; this only surfaces it for review.
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
                return Anomaly(
                    kind=AnomalyKind.REMOTE_OVERLAP, source="izin",
                    source_row=r.source_row, key=key, raw_name=r.raw_name,
                    date=r.date,
                    raw_entry=f"{r.entry:%H:%M}-{r.exit:%H:%M} (uzaktan)",
                    raw_exit=f"{b.entry:%H:%M}-{b.exit:%H:%M} ({b.source})",
                    detail="çakışan süre bir kez sayıldı",
                )
    return None


def _note(kind: AnomalyKind, record: PunchRecord, detail: str = "") -> Anomaly:
    return Anomaly(
        kind=kind, source=record.source, source_row=record.source_row,
        key=record.key, raw_name=record.raw_name, date=record.date,
        raw_entry=record.entry.strftime("%d.%m.%Y %H:%M:%S") if record.entry else "",
        raw_exit=record.exit.strftime("%d.%m.%Y %H:%M:%S") if record.exit else "",
        detail=detail,
    )
