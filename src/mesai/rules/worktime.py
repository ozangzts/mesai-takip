"""Turning raw punch records into clean intervals, and intervals into hours.

Everything here is per docs/DOMAIN-RULES.md §3 and §5. Three rules carry most of the
weight:

* Midnight crossing (§3.2): the source system produces "-15:-52" for a night shift.
  Add 24 h to the exit, accept only if the result is plausible.
* Daily measure (§5.0, ADR-015): a person-day is measured from its earliest entry to
  its latest exit. Gaps inside the day are paid. `daily_hours: union` in the config
  restores the older rule, which excluded those gaps.
* Residual break (§5.1, ADR-008): every employee owes 45 min of unpaid break per day.
  Time already outside the union is already unpaid, so deduct only what is still
  owed. A 42-minute gap yields a 3-minute deduction — no threshold, no judgement
  call. **Disabled by default since ADR-016** (`break.deduct: false`); the arithmetic
  stays here, tested, so re-enabling it is a config edit.

`measure()` is the single place those last two combine. Nothing outside this module
should decide whether a break is deducted.
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
    repaired = exit_ < entry
    if repaired:
        exit_ = exit_ + _DAY
        tags.append(AnomalyKind.NEGATIVE_DURATION)

    duration = exit_ - entry
    # The ceiling rejects OUR OWN GUESS, not a long day. When the exit precedes the
    # entry we assume the shift crossed midnight and add 24 hours; if that assumption
    # produces something over the ceiling, the assumption was wrong and the record is
    # unusable. All three May/June cases of it are minutes or seconds apart —
    # `13:58:56 -> 13:57:50` becomes 23:58.
    #
    # An interval the source states plainly is kept however long it is. Two June days
    # ran 16:06 and 16:39 — real people, real shifts — and were being counted as zero
    # because a ceiling meant for broken records caught them. ADR-032.
    if repaired and duration > settings.plausibility.max_duration:
        return None, [_anomaly(
            AnomalyKind.IMPLAUSIBLE_DURATION, record,
            detail=f"gece geçişi varsayılıp düzeltilince süre {_hhmm(duration)} "
                   f"çıkıyor, üst sınır "
                   f"{_hhmm(settings.plausibility.max_duration)} — kayıt kullanılamaz",
        )]

    for kind in tags:
        anomalies.append(_anomaly(
            kind, record,
            detail=f"çıkış girişten önce; +24 saat uygulandı, süre {_hhmm(duration)}",
        ))

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
    """Sum of the merged intervals — presence only, in-day gaps excluded."""
    total = timedelta()
    for interval in intervals:
        total += interval.duration
    return total


def envelope_duration(intervals: tuple[Interval, ...]) -> timedelta:
    """Earliest entry to latest exit, gaps included — ADR-015.

    This is the classic timesheet reading: the day starts when you first badge in and
    ends when you last badge out, and what happened in between is not deducted.
    """
    if not intervals:
        return timedelta()
    return max(iv.end for iv in intervals) - min(iv.start for iv in intervals)


def gap_duration(intervals: tuple[Interval, ...]) -> timedelta:
    """Time inside the day that is between intervals rather than in one.

    Paid under `envelope`, unpaid under `union`. Reported on the Kontrol sheet so the
    difference between the two rules is always visible and auditable.
    """
    return envelope_duration(intervals) - gross_duration(intervals)


def measure(
    intervals: tuple[Interval, ...], settings: Settings
) -> tuple[timedelta, timedelta, timedelta]:
    """One person-day's hours: `(measured, break_deduction, net)`.

    `measured` follows `settings.daily_hours`; the deduction is applied only when
    `settings.brk.deduct` is on. With the shipped config both totals are equal —
    that is ADR-016, not a bug.
    """
    if not intervals:
        return timedelta(), timedelta(), timedelta()

    if settings.daily_hours == "union":
        measured = gross_duration(intervals)
    else:
        measured = envelope_duration(intervals)

    deduction = (break_deduction(intervals, measured, settings)
                 if settings.brk.deduct else timedelta())
    net = measured - deduction
    if net < timedelta():
        net = timedelta()
    return measured, deduction, net


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
