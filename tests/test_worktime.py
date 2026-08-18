"""Interval construction, union, the daily measure, and the residual break rule.

Every expected value here was computed by hand.
"""

from datetime import date, datetime, timedelta

from mesai.anomalies import AnomalyKind
from mesai.models import Interval, PunchRecord
from mesai.rules.worktime import (
    break_deduction, build_interval, decimal_hours, envelope_duration,
    gap_duration, gross_duration, hhmm, measure, merge_intervals,
)


def punch(entry: str | None, exit_: str | None, day: str = "2026-05-21",
          source: str = "macunkoy", tag: str | None = None,
          reported: str | None = None) -> PunchRecord:
    def stamp(value: str | None) -> datetime | None:
        if value is None:
            return None
        d, t = (value.split(" ") + [""])[:2] if " " in value else (day, value)
        return datetime.fromisoformat(f"{d} {t}")

    return PunchRecord(
        source=source, source_row=1, raw_name="TEST KİŞİ", key=("TEST", "KISI"),
        date=date.fromisoformat(day), entry=stamp(entry), exit=stamp(exit_),
        tag=tag, reported_duration=reported,
    )


def iv(start: str, end: str, day: str = "2026-05-21", sources=("macunkoy",)) -> Interval:
    return Interval(
        start=datetime.fromisoformat(f"{day} {start}"),
        end=datetime.fromisoformat(f"{day} {end}"),
        sources=frozenset(sources),
    )


# --- interval construction -------------------------------------------------

def test_normal_day(settings):
    interval, notes = build_interval(punch("08:00", "17:00"), settings)
    assert interval is not None
    assert interval.duration == timedelta(hours=9)
    assert notes == []


def test_midnight_crossing_is_repaired(settings):
    # The real Macunköy row 17: source reports "-15:-52"; the truth is 8:07.
    record = punch("23:59:42", "08:07:06", reported="-15:-52")
    interval, notes = build_interval(record, settings)
    assert interval is not None
    assert hhmm(interval.duration) == "8:07"
    assert any(n.kind is AnomalyKind.NEGATIVE_DURATION for n in notes)


def test_one_sided_record_yields_no_interval(settings):
    # merge.py decides these, since only it can see the other source.
    assert build_interval(punch("08:00", None), settings)[0] is None
    assert build_interval(punch(None, "17:00"), settings)[0] is None


def test_empty_record_is_flagged(settings):
    interval, notes = build_interval(punch(None, None), settings)
    assert interval is None
    assert [n.kind for n in notes] == [AnomalyKind.EMPTY_RECORD]


def test_short_interval_is_kept_but_flagged(settings):
    # The real 01.05.2026 13:32 -> 13:34 row.
    interval, notes = build_interval(punch("13:32", "13:34"), settings)
    assert interval is not None, "a suspicious short interval is real data"
    assert any(n.kind is AnomalyKind.SUSPICIOUS_SHORT for n in notes)


def test_long_but_plausible_interval_is_kept(settings):
    # 15:30 is under the 16 h ceiling — long shifts happen and must be counted.
    interval, notes = build_interval(punch("07:00", "22:30"), settings)
    assert interval is not None
    assert hhmm(interval.duration) == "15:30"
    assert notes == []


def test_implausibly_long_interval_is_excluded(settings):
    # A stuck badge must not silently add 24 hours to someone's month.
    record = PunchRecord(
        source="macunkoy", source_row=2, raw_name="TEST KİŞİ", key=("TEST", "KISI"),
        date=date(2026, 5, 21),
        entry=datetime(2026, 5, 21, 6, 0), exit=datetime(2026, 5, 22, 6, 0),
    )
    interval, notes = build_interval(record, settings)
    assert interval is None
    assert [n.kind for n in notes] == [AnomalyKind.IMPLAUSIBLE_DURATION]


def test_reported_duration_mismatch_is_reported(settings):
    _, notes = build_interval(punch("08:00", "17:00", reported="05:00"), settings)
    assert any(n.kind is AnomalyKind.DURATION_MISMATCH for n in notes)


# --- union -----------------------------------------------------------------

def test_overlapping_intervals_count_once():
    # The ZEYNEP DENEME case: Teknopark 07:09-19:45 plus a Macunköy site visit.
    merged = merge_intervals([
        iv("07:09", "19:45", sources=("teknopark",)),
        iv("13:20", "14:05", sources=("macunkoy",)),
    ])
    assert len(merged) == 1
    assert hhmm(gross_duration(merged)) == "12:36", "must not be 13:21"
    assert merged[0].sources == frozenset({"teknopark", "macunkoy"})


def test_touching_intervals_merge():
    merged = merge_intervals([iv("08:00", "12:00"), iv("12:00", "17:00")])
    assert len(merged) == 1
    assert hhmm(gross_duration(merged)) == "9:00"


def test_real_gap_is_preserved():
    merged = merge_intervals([iv("08:00", "12:00"), iv("13:00", "17:00")])
    assert len(merged) == 2
    assert hhmm(gross_duration(merged)) == "8:00"


def test_contained_interval_is_absorbed():
    merged = merge_intervals([iv("08:00", "18:00"), iv("10:00", "11:00")])
    assert len(merged) == 1
    assert hhmm(gross_duration(merged)) == "10:00"


def test_split_day_sums():
    # The real BURAK ÖRNEK, 2026-05-04.
    merged = merge_intervals([iv("08:21", "13:48"), iv("14:30", "18:00")])
    assert hhmm(gross_duration(merged)) == "8:57"


def test_merge_of_nothing():
    assert merge_intervals([]) == ()
    assert gross_duration(()) == timedelta()


# --- daily measure: envelope (ADR-015) -------------------------------------

def test_envelope_spans_first_entry_to_last_exit():
    # The real BURAK ÖRNEK, 2026-05-04: out at 13:48, back at 14:30.
    merged = merge_intervals([iv("08:21", "13:48"), iv("14:30", "18:00")])
    assert hhmm(envelope_duration(merged)) == "9:39"
    assert hhmm(gross_duration(merged)) == "8:57", "presence is still 8:57"
    assert hhmm(gap_duration(merged)) == "0:42"


def test_envelope_equals_union_on_a_continuous_day():
    merged = merge_intervals([iv("07:30", "16:30")])
    assert envelope_duration(merged) == gross_duration(merged)
    assert gap_duration(merged) == timedelta()


def test_envelope_of_nothing():
    assert envelope_duration(()) == timedelta()
    assert gap_duration(()) == timedelta()


def test_envelope_ignores_a_contained_interval():
    # A Macunköy visit inside a Teknopark day changes neither figure.
    merged = merge_intervals([iv("07:09", "19:45"), iv("13:20", "14:05")])
    assert hhmm(envelope_duration(merged)) == "12:36"
    assert gap_duration(merged) == timedelta()


def test_measure_pays_the_gap_and_deducts_nothing(settings):
    merged = merge_intervals([iv("08:21", "13:48"), iv("14:30", "18:00")])
    worked, deduction, net = measure(merged, settings)
    assert hhmm(worked) == "9:39"
    assert deduction == timedelta()
    assert net == worked, "with the break off, net must equal the measured day"


def test_measure_under_the_old_rule(settings_break):
    """The pre-ADR-016 configuration must still reproduce the old numbers."""
    merged = merge_intervals([iv("08:21", "13:48"), iv("14:30", "18:00")])
    worked, deduction, net = measure(merged, settings_break)
    assert hhmm(worked) == "8:57"
    assert deduction == timedelta(minutes=3)
    assert hhmm(net) == "8:54"


def test_measure_of_an_empty_day(settings):
    assert measure((), settings) == (timedelta(), timedelta(), timedelta())


def test_envelope_never_undercounts_presence(settings):
    """The measured day can exceed presence but must never fall below it."""
    for gap_minutes in range(0, 240, 15):
        start = datetime(2026, 5, 21, 8, 0)
        first_end = datetime(2026, 5, 21, 11, 30)
        second_start = first_end + timedelta(minutes=gap_minutes)
        merged = merge_intervals([
            Interval(start, first_end),
            Interval(second_start, second_start + timedelta(hours=4)),
        ])
        worked, _, _ = measure(merged, settings)
        assert worked >= gross_duration(merged)


# --- residual break (ADR-008, disabled by ADR-016 but still shipped) --------

def test_continuous_day_pays_the_full_break(settings):
    merged = merge_intervals([iv("08:00", "17:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == \
        timedelta(minutes=45)


def test_forty_two_minute_gap_deducts_only_three(settings):
    # The whole point of ADR-008: no threshold, no cliff edge.
    merged = merge_intervals([iv("08:21", "13:48"), iv("14:30", "18:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == \
        timedelta(minutes=3)


def test_exact_break_gap_deducts_nothing(settings):
    merged = merge_intervals([iv("08:00", "11:30"), iv("12:15", "17:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == timedelta()


def test_long_absence_creates_no_credit(settings):
    merged = merge_intervals([iv("08:00", "11:00"), iv("14:00", "18:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == timedelta()


def test_gap_outside_the_window_is_not_lunch(settings):
    # 15:00-16:00 is not a lunch break, so the full 45 minutes is still owed.
    merged = merge_intervals([iv("07:30", "15:00"), iv("16:00", "19:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == \
        timedelta(minutes=45)


def test_short_day_gets_no_deduction(settings):
    merged = merge_intervals([iv("08:00", "12:00")])
    assert break_deduction(merged, gross_duration(merged), settings) == timedelta()


def test_deduction_is_monotonic(settings):
    """Badging out for longer must never increase net hours."""
    previous = None
    for minutes in range(0, 90, 5):
        end = datetime(2026, 5, 21, 11, 30)
        restart = end + timedelta(minutes=minutes)
        merged = merge_intervals([
            Interval(datetime(2026, 5, 21, 8, 0), end),
            Interval(restart, datetime(2026, 5, 21, 18, 0)),
        ])
        gross = gross_duration(merged)
        net = gross - break_deduction(merged, gross, settings)
        if previous is not None:
            assert net <= previous + timedelta(seconds=1)
        previous = net


# --- formatting ------------------------------------------------------------

def test_hhmm_exceeds_24_hours():
    assert hhmm(timedelta(hours=186, minutes=30)) == "186:30"


def test_decimal_hours():
    assert decimal_hours(timedelta(hours=8, minutes=15)) == 8.25
