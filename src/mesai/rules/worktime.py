"""Turning raw punch records into clean intervals, and intervals into hours.

Everything here is per docs/DOMAIN-RULES.md §3 and §5. Two rules carry most of the
weight:

* Midnight crossing (§3.2): the source system produces "-15:-52" for a night shift.
  Add 24 h to the exit, accept only if the result is plausible.
* Residual break (§5.1): every employee owes 45 min of unpaid break per day. Time
  already outside the union is already unpaid, so deduct only what is still owed.
  A 42-minute gap yields a 3-minute deduction — no threshold, no judgement call.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from ..anomalies import Anomaly, AnomalyKind
from ..config import Settings
from ..models import Interval, PunchRecord

_DAY = timedelta(hours=24)


def build_interval(
    record: PunchRecord, settings: Settings
) -> tuple[Interval | None, list[Anomaly]]:
    """Clean interval from one raw record, plus any anomalies it raises.

    Returns (None, anomalies) when no interval can be derived. A one-sided record
    yields None here; merge.py then attempts cross-site repair before writing it off.
    """
    anomalies: list[Anomaly] = []
    entry, exit_ = record.entry, record.exit

    if entry is None and exit_ is None:
        return None, [_anomaly(AnomalyKind.EMPTY_RECORD, record)]
    if entry is None or exit_ is None:
        # Missing side is decided in merge.py, which can see the other source.
        return None, []

    tags: list[AnomalyKind] = []
    if exit_ < entry:
        exit_ = exit_ + _DAY
        tags.append(AnomalyKind.NEGATIVE_DURATION)

    duration = exit_ - entry
    if duration > settings.plausibility.max_duration:
        return None, [_anomaly(
            AnomalyKind.IMPLAUSIBLE_DURATION, record,
            detail=f"süre {_hhmm(duration)}, üst sınır "
                   f"{_hhmm(settings.plausibility.max_duration)}",
        )]

    for kind in tags:
        anomalies.append(_anomaly(
            kind, record,
            detail=f"çıkış girişten önce; +24 saat uygulandı, süre {_hhmm(duration)}",
        ))

    if duration < settings.plausibility.min_duration:
        anomalies.append(_anomaly(
            AnomalyKind.SUSPICIOUS_SHORT, record, detail=f"süre {_hhmm(duration)}"))

    reported = _reported(record)
    if reported is not None and abs(reported - duration) > timedelta(minutes=2):
        anomalies.append(_anomaly(
            AnomalyKind.DURATION_MISMATCH, record,
            detail=f"hesaplanan {_hhmm(duration)}, dosyadaki "
                   f"{record.reported_duration}",
        ))

    sources = {record.source}
    if record.tag:
        sources.add(record.tag)
    return Interval(start=entry, end=exit_, sources=frozenset(sources)), anomalies


def merge_intervals(intervals: list[Interval]) -> tuple[Interval, ...]:
    """Union of intervals. Overlapping AND touching intervals are merged.

    Touching is deliberate: an exit at one gate and an entry at another in the same
    minute is one continuous presence, not two.
    """
    if not intervals:
        return ()
    ordered = sorted(intervals, key=lambda iv: (iv.start, iv.end))
    merged: list[Interval] = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = Interval(
                start=last.start,
                end=max(last.end, current.end),
                sources=last.sources | current.sources,
            )
        else:
            merged.append(current)
    return tuple(merged)


def gross_duration(intervals: tuple[Interval, ...]) -> timedelta:
    total = timedelta()
    for interval in intervals:
        total += interval.duration
    return total


def break_deduction(
    intervals: tuple[Interval, ...], gross: timedelta, settings: Settings
) -> timedelta:
    """Residual unpaid break — see docs/DOMAIN-RULES.md §5.1 and ADR-008.

        deduction = clamp(owed - already_unpaid, 0, owed)

    where `already_unpaid` is gap time inside the break window, capped at `owed`.
    """
    rule = settings.brk
    owed = rule.duration
    if not intervals or gross < rule.min_workday:
        return timedelta()

    day = intervals[0].start.date()
    window_start = datetime.combine(day, rule.window_from)
    window_end = datetime.combine(day, rule.window_to)

    already = timedelta()
    for earlier, later in zip(intervals, intervals[1:]):
        overlap_start = max(earlier.end, window_start)
        overlap_end = min(later.start, window_end)
        if overlap_end > overlap_start:
            already += overlap_end - overlap_start

    if already > owed:
        already = owed
    remaining = owed - already
    return remaining if remaining > timedelta() else timedelta()


def _reported(record: PunchRecord) -> timedelta | None:
    from ..readers.base import as_duration
    return as_duration(record.reported_duration)


def _anomaly(kind: AnomalyKind, record: PunchRecord, detail: str = "") -> Anomaly:
    return Anomaly(
        kind=kind,
        source=record.source,
        source_row=record.source_row,
        key=record.key,
        raw_name=record.raw_name,
        date=record.date,
        raw_entry=_stamp(record.entry),
        raw_exit=_stamp(record.exit),
        detail=detail,
    )


def _stamp(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M:%S") if value else ""


def _hhmm(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600}:{(total % 3600) // 60:02d}"


def hhmm(delta: timedelta) -> str:
    """`HH:MM`, hours unbounded. Never an Excel time format — 186:30 must not
    display as 6:30."""
    return _hhmm(delta)


def decimal_hours(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 2)
