from dataclasses import replace
from datetime import time, timedelta

import pytest

from mesai.config import (
    BreakRule, Calendar, Multinet, NominalDay, Personnel, Plausibility, Settings,
)


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    """No test may open an SMTP connection. Autouse, so nothing can opt out.

    **This is here because it happened.** `sender.send` takes a `transport` for the
    tests, and the suite was clean for exactly as long as no test reached the real path.
    Then `PeopleScreen` started taking its `config_dir` from the shell — correctly — and
    the GUI fixture points that at the repository's own `config/`, which on a working
    machine holds a real `gmail.yaml`. A test written to prove that a MISSING account
    file is reported instead of raising found a present one, went down the live path, and
    submitted a message to Gmail addressed to the fixture's `a@b.c`.

    Nobody real was written to, and the message bounced. But the lesson is not "point
    that test somewhere else": a guard belongs where the evidence is (ADR-044), and the
    evidence is that any test can reach `smtplib` from three modules away. So the socket
    is taken away from the whole suite. A test that wants to exercise sending passes a
    `transport`; a test that reaches the network fails loudly instead of sending.
    """
    import smtplib

    def refuse(*_args, **_kwargs):
        raise AssertionError(
            "Bir test gerçek SMTP bağlantısı açmaya çalıştı. Gönderim testleri "
            "`sender.send(..., transport=...)` kullanır; hiçbir test posta göndermez.")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


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
            max_duration=timedelta(hours=16),
            repair_max=timedelta(hours=20),
            short_day=timedelta(hours=2),
            # Mirrors config/settings.yaml. Left out, it defaults to 0 — which
            # DISABLES the check, so every test would pass against a rule the program
            # actually runs. test_config.py fails if these drift.
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
        calendar=Calendar(holidays=frozenset(), rest_weekdays=frozenset({5, 6})),
        # Mirrors config/settings.yaml:multinet. test_config.py fails if this
        # drifts — the fixture has silently disagreed with the real config
        # before, and a whole suite then passes against a rule nobody runs.
        multinet=Multinet(daily_hours=timedelta(hours=12)),
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
