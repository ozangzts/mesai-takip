from dataclasses import replace
from datetime import time, timedelta

import pytest

from mesai.config import (
    BreakRule, Calendar, NominalDay, Personnel, Plausibility, Settings,
)


@pytest.fixture
def settings() -> Settings:
    """Defaults mirroring config/settings.yaml, with no aliases or holidays."""
    return Settings(
        shift_start=time(7, 30),
        shift_end=time(16, 30),
        daily_hours="envelope",
        brk=BreakRule(
            minutes=45,
            window_from=time(11, 0),
            window_to=time(14, 30),
            min_workday=timedelta(hours=6),
            deduct=False,
        ),
        plausibility=Plausibility(
            min_duration=timedelta(minutes=5),
            max_duration=timedelta(hours=16),
            short_day=timedelta(hours=2),
        ),
        # Mirrors config/settings.yaml, including the `*.xls*` widening of ADR-020.
        # test_config.py fails if this drifts from the real file again.
        sources={
            "roster": ("*calisan*.xls*", "*çalışan*.xls*", "*personel*.xls*",
                       "SYST03*.xls*"),
            "izin": ("*IZIN*.xls*", "*İZİN*.xls*"),
            "macunkoy": ("*Macunköy*.xls*", "*Macunkoy*.xls*"),
            "teknopark": ("*Teknopark*.xls*",),
        },
        worked_leave_types=frozenset({"Uzaktan Çalışma"}),
        calendar=Calendar(holidays={}, half_days=frozenset(),
                          rest_weekdays=frozenset({5, 6})),
        personnel=Personnel(exclude_prefixes=("ZIYARETCI", "GECICI", "STJ")),
        # Mirrors config/settings.yaml:facility_labels. Already folded, exactly as
        # `_facility_labels` would produce it. test_config.py fails if this drifts.
        facility_labels=(("MACUNKOY", "Macunköy"), ("DEICO", "Teknopark")),
        nominal_day=NominalDay(source="teknopark", entry=time(9, 0),
                               exit=time(18, 0)),
    )


@pytest.fixture
def settings_break(settings: Settings) -> Settings:
    """The pre-ADR-016 rule: union of intervals, residual break deducted.

    Kept as a fixture because ADR-008's arithmetic is still shipped behind a config
    switch, and a rule that is still shipped must still be tested.
    """
    return replace(
        settings,
        daily_hours="union",
        brk=replace(settings.brk, deduct=True),
    )
