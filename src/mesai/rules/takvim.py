"""Which working days look like the site was shut — a question, never an answer.

The calendar cannot be hardcoded. Religious holidays move every year, and a company
closure (an August week when the site is shut) appears in no source file at all: the
attendance exports simply have almost nothing on those days, and the leave export calls
it `Toplu İzin` if anybody bothered to enter it.

So the program measures what it can see and hands the days to a human. It marks nothing
itself — an inferred holiday nobody confirmed is the same mistake as an inferred punch.

Measured over May–July 2026, which is where the threshold comes from:

| | headcount, as a share of the month's weekday median |
| --- | --- |
| the eight days already known to be holidays | 2 % – 14 % |
| the emptiest ordinary working day (18 May) | 72 % |

The 35 % default sits in the middle of that gap. The two closest cases are the 25–26 May
bridge day and eve at 13–14 %, and most of their records are the Teknopark export's
nominal `09:00–18:00` placeholder — the vendor writes those on a company closure but not
on a statutory holiday, so a company closure reads as emptier-than-normal rather than
empty.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..config import Settings
from ..models import HolidayCandidate, PunchRecord


def candidates(records: list[PunchRecord], period: str,
               settings: Settings) -> tuple[HolidayCandidate, ...]:
    """Expected working days whose headcount collapsed, in date order.

    Days already in the calendar are not returned — they are answered questions. Leave
    records are ignored for the same reason `_coverage` ignores them: `izin` is not an
    attendance source, and a day everybody took off as collective leave is exactly the
    day being looked for.
    """
    ratio = settings.plausibility.holiday_candidate_ratio
    if ratio <= 0:
        return ()

    year, month = (int(part) for part in period.split("-"))
    expected = settings.calendar.expected_workdays(year, month)
    if not expected:
        return ()

    present: dict[date, set[tuple[str, str]]] = defaultdict(set)
    for record in records:
        if record.source != "izin":
            present[record.date].add(record.key)

    counts = sorted(len(present.get(day, ())) for day in expected)
    median = counts[len(counts) // 2]
    if median <= 0:
        # Nothing to compare against: an empty or wrong-month source, which the
        # coverage and period guards report on their own terms.
        return ()

    found = [HolidayCandidate(date=day, people=len(present.get(day, ())),
                              median=median)
             for day in expected if len(present.get(day, ())) < median * ratio]
    return tuple(sorted(found, key=lambda candidate: candidate.date))
