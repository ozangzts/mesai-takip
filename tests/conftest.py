from datetime import time, timedelta

import pytest

from mesai.config import (
    BreakRule, Calendar, Personnel, Plausibility, Settings,
)


@pytest.fixture
def settings() -> Settings:
    """Defaults mirroring config/settings.yaml, with no aliases or holidays."""
    return Settings(
        shift_start=time(7, 30),
        shift_end=time(16, 30),
        brk=BreakRule(
            minutes=45,
            window_from=time(11, 0),
            window_to=time(14, 30),
            min_workday=timedelta(hours=6),
        ),
        plausibility=Plausibility(
            min_duration=timedelta(minutes=5),
            max_duration=timedelta(hours=16),
        ),
        sources={
            "roster": ("SYST03*.xlsx",), "izin": ("*IZIN*.xlsx",),
            "macunkoy": ("*Macunköy*.xlsx",), "teknopark": ("*Teknopark*.xlsx",),
        },
        worked_leave_types=frozenset({"Uzaktan Çalışma"}),
        calendar=Calendar(holidays={}, half_days=frozenset(),
                          rest_weekdays=frozenset({5, 6})),
        personnel=Personnel(exclude_prefixes=("ZIYARETCI", "GECICI", "STJ")),
    )
