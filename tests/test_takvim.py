"""Which days get offered as "was the site shut?" — the rule, without a window.

The calendar cannot be hardcoded: religious holidays move every year, and a company
closure appears in no source file at all. So this is the one place the program is
allowed to *point at* a calendar day it was not told about — and it must only ever
point, never mark. An inferred holiday nobody confirmed is the same class of mistake as
an inferred punch (ADR-003, ADR-041).

The threshold comes from measurement, not taste: over May-July 2026 the eight days
already known to be holidays carried 2-14 % of their month's median headcount, and the
emptiest ordinary working day carried 72 %. Every expected value below is hand-computed.
"""

from dataclasses import replace
from datetime import date, datetime

import pytest

from mesai.models import PunchRecord
from mesai.rules import takvim

JULY = "2026-07"


def punch(day: date, who: int, source: str = "teknopark") -> PunchRecord:
    return PunchRecord(
        key=(f"KİŞİ{who:03d}", "DENEME"), raw_name=f"KİŞİ{who:03d} DENEME",
        source=source, date=day,
        entry=datetime.combine(day, datetime.min.time()).replace(hour=8),
        exit=datetime.combine(day, datetime.min.time()).replace(hour=17),
        source_row=who,
    )


def month(settings, present: dict[int, int], source: str = "teknopark"):
    """Attendance for July 2026: `{day of month: how many people}`."""
    records = []
    for day, count in present.items():
        for who in range(count):
            records.append(punch(date(2026, 7, day), who, source))
    return takvim.candidates(records, JULY, settings)


# --- what a normal month looks like -----------------------------------------

def test_a_month_where_everybody_shows_up_offers_nothing(settings):
    """22 expected working days in July 2026, 100 people on each of them."""
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    assert month(settings, {day: 100 for day in workdays}) == ()


def test_the_one_empty_day_is_offered_with_its_numbers(settings):
    """The real July case, reduced: one day at 7 people against a median of 130.

    5 % of the median, well under the 35 % threshold.
    """
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    present = {day: 130 for day in workdays}
    present[workdays[7]] = 7

    found = month(settings, present)

    assert len(found) == 1
    assert found[0].date == date(2026, 7, workdays[7])
    assert (found[0].people, found[0].median) == (7, 130)
    assert found[0].share == pytest.approx(7 / 130)


def test_a_five_day_closure_comes_back_as_five_days(settings):
    """The August case the operator described: the site shut for a working week."""
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    present = {day: 120 for day in workdays}
    for day in workdays[5:10]:
        present[day] = 4

    found = month(settings, present)

    assert [c.date.day for c in found] == workdays[5:10]
    assert all(c.people == 4 for c in found)


def test_the_days_come_back_in_date_order(settings):
    """They are read as a list by a human; frequency order would be unreadable."""
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    present = {day: 100 for day in workdays}
    present[workdays[12]], present[workdays[2]] = 1, 5

    assert [c.date.day for c in month(settings, present)] == \
        sorted([workdays[2], workdays[12]])


# --- what must NOT be offered -----------------------------------------------

def test_a_day_already_in_the_calendar_is_not_offered_again(settings):
    """A day in the calendar is an answered question, so it is not asked again.

    It also stops being an expected working day, which is what keeps the rest of the
    month's median honest — a known-empty day left in the denominator drags it down and
    makes every other day look busier than it is.

    (That the *shipped* calendar contains 15 July is asserted in `test_config.py`; the
    fixture calendar is deliberately empty, so the holiday is put there by hand here.)
    """
    marked = replace(settings, calendar=replace(
        settings.calendar, holidays={date(2026, 7, 15): "Demokrasi ve Millî Birlik"}))
    workdays = [d.day for d in marked.calendar.expected_workdays(2026, 7)]
    assert 15 not in workdays

    present = {day: 130 for day in workdays}
    present[15] = 7                      # records DO exist on the holiday
    assert month(marked, present) == ()


def test_a_weekend_is_never_offered(settings):
    """Saturdays and Sundays are already rest days; nobody needs telling."""
    saturday = date(2026, 7, 4)
    assert saturday.weekday() == 5
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]

    present = {day: 100 for day in workdays}
    present[4] = 1

    assert all(c.date != saturday for c in month(settings, present))


def test_leave_records_do_not_rescue_a_day(settings):
    """A day everybody took as collective leave is exactly the day being looked for.

    `izin` is not an attendance source — counting it would hide the closure it proves.
    """
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    present = {day: 100 for day in workdays}
    shut = workdays[9]
    present[shut] = 0

    records = []
    for day, count in present.items():
        records += [punch(date(2026, 7, day), who) for who in range(count)]
    records += [punch(date(2026, 7, shut), who, source="izin") for who in range(90)]

    found = takvim.candidates(records, JULY, settings)
    assert [c.date.day for c in found] == [shut]
    assert found[0].people == 0, "the leave records must not be counted as presence"


# --- the edges --------------------------------------------------------------

def test_no_records_at_all_offers_nothing(settings):
    """A wrong-month or empty source. The period guards report that on their terms.

    Offering all 22 days as possible holidays would be technically true and useless.
    """
    assert takvim.candidates([], JULY, settings) == ()


def test_a_zero_ratio_disables_the_check(settings):
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    present = {day: 100 for day in workdays}
    present[workdays[3]] = 0

    off = replace(settings,
                  plausibility=replace(settings.plausibility,
                                       holiday_candidate_ratio=0.0))
    assert takvim.candidates(
        [punch(date(2026, 7, d), w) for d, c in present.items() for w in range(c)],
        JULY, off) == ()


def test_the_threshold_is_a_share_of_the_median_not_a_headcount(settings):
    """A small site must be measured against itself, not against a fixed number.

    Ten people is a normal day at a ten-person site and a closed day at a hundred-person
    one, and the rule has to say the right thing at both.
    """
    workdays = [d.day for d in settings.calendar.expected_workdays(2026, 7)]
    small = {day: 10 for day in workdays}
    small[workdays[4]] = 3               # 30 % — under the threshold

    found = month(settings, small)
    assert [c.date.day for c in found] == [workdays[4]]
    assert found[0].median == 10

    small[workdays[4]] = 4               # 40 % — over it
    assert month(settings, small) == ()
