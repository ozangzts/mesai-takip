"""The test fixture must not drift from the shipped configuration.

Written after a real drift: `config/settings.yaml` was widened to `*.xls*` (ADR-020)
while `tests/conftest.py` kept `*.xlsx`. Three GUI tests then failed for a reason that
had nothing to do with the GUI, and — worse — every other test kept passing against
patterns the program no longer uses.

The fixture's docstring claims it mirrors the real config. This makes that a check
rather than a claim.
"""

from pathlib import Path

import pytest

from mesai import config

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
REAL = pytest.mark.skipif(
    not (CONFIG_DIR / "settings.yaml").exists(),
    reason="config/settings.yaml yok (personel.yaml git'e dahil değil)")


@pytest.fixture
def real_settings():
    return config.load(CONFIG_DIR, "2026-07")


@REAL
def test_the_fixture_mirrors_the_shipped_source_patterns(settings, real_settings):
    assert settings.sources == real_settings.sources


@REAL
def test_the_fixture_mirrors_the_shipped_facility_labels(settings, real_settings):
    """Not a payroll figure, but the same failure mode: a fixture that renames sites
    the shipped config does not would prove nothing about the report HR opens."""
    assert settings.facility_labels == real_settings.facility_labels


@REAL
def test_the_fixture_mirrors_the_shipped_rules(settings, real_settings):
    """The rules that change payroll figures. A silent divergence here is worse than
    a failing test: the suite would be proving something about a config nobody runs."""
    assert settings.daily_hours == real_settings.daily_hours
    assert settings.plausibility == real_settings.plausibility   # every field
    assert settings.brk.deduct == real_settings.brk.deduct
    assert settings.brk.minutes == real_settings.brk.minutes
    assert settings.remote_replaces == real_settings.remote_replaces
    assert settings.worked_leave_types == real_settings.worked_leave_types
    assert settings.plausibility.short_day == real_settings.plausibility.short_day
    assert settings.plausibility.max_duration == real_settings.plausibility.max_duration
    assert settings.nominal_day == real_settings.nominal_day
    assert settings.shift_start == real_settings.shift_start
    assert settings.shift_end == real_settings.shift_end


@REAL
def test_only_remote_work_counts_as_worked_time(real_settings):
    """The worked-leave list is closed at one entry — ADR-037.

    Training was the open case for seventeen days, on the reasoning that its rows carry
    real clock times. So does every other leave type, annual leave included: the time is
    when the leave began, not evidence anybody was present. HR confirmed training is
    leave, so this list is now a decision and a second entry has to be argued for in a
    new ADR rather than added.

    Measured cost of the alternative, in case it is ever revisited: adding `Eğitim
    İzni` moved May by +18:26 over 17 103:58 and June by +4:53, because most training
    hours already fell inside a badged day and the interval union had counted them.
    """
    assert real_settings.worked_leave_types == frozenset({"Uzaktan Çalışma"})


@REAL
def test_every_source_glob_accepts_all_supported_containers(real_settings):
    """A glob tied to one container turns a format change into "file not found"."""
    from mesai.readers.base import SUPPORTED_SUFFIXES

    for name, patterns in real_settings.sources.items():
        for pattern in patterns:
            assert pattern.endswith(".xls*"), \
                f"sources.{name}: {pattern!r} tek bir kaba bağlı"
    assert SUPPORTED_SUFFIXES == {".xlsx", ".xlsm", ".xls"}


@REAL
def test_payroll_switches_are_required_not_defaulted(tmp_path):
    """A config predating a rule change must fail, not quietly apply the old rule."""
    import shutil
    for name in ("settings.yaml", "takvim-2026.yaml", "personel.yaml"):
        source = CONFIG_DIR / name
        if source.exists():
            shutil.copy(source, tmp_path / name)

    text = (tmp_path / "settings.yaml").read_text(encoding="utf-8")
    for line, expected in (
        ("daily_hours: envelope", "daily_hours"),
        ("  deduct: false", "deduct"),
        ("remote_day_replaces_attendance: nominal_only", "remote_day"),
    ):
        assert line in text, line
        (tmp_path / "settings.yaml").write_text(
            text.replace(line, ""), encoding="utf-8")
        with pytest.raises(config.ConfigError, match=expected):
            config.load(tmp_path, "2026-07")


@REAL
def test_an_unknown_daily_hours_value_fails_loudly(tmp_path):
    import shutil
    for name in ("settings.yaml", "takvim-2026.yaml", "personel.yaml"):
        source = CONFIG_DIR / name
        if source.exists():
            shutil.copy(source, tmp_path / name)
    text = (tmp_path / "settings.yaml").read_text(encoding="utf-8")
    (tmp_path / "settings.yaml").write_text(
        text.replace("daily_hours: envelope", "daily_hours: zarf"), encoding="utf-8")

    with pytest.raises(config.ConfigError, match="geçersiz"):
        config.load(tmp_path, "2026-07")


# --- the calendar (ADR-040) -------------------------------------------------

# Turkey's fixed-date statutory holidays. Law, identical every year, and therefore the
# one part of the calendar that can be asserted rather than entered. Ramazan and Kurban
# Bayramı move with the lunar year and cannot go in this list — they are entered by
# hand, and a month with no holiday at all is flagged on the report instead.
_FIXED_HOLIDAYS_2026 = [
    (1, 1), (4, 23), (5, 1), (5, 19), (7, 15), (8, 30), (10, 29),
]


@REAL
def test_no_fixed_date_statutory_holiday_is_missing(real_settings):
    """15 July was absent, so July's report expected 23 working days instead of 22.

    Nothing failed: two people were flagged `Ay büyük ölçüde boş` against the wrong
    denominator, and the seven who badged in that day looked like ordinary attendance.
    Listing the whole year up front is what stops the next one being noticed a month
    late.
    """
    from datetime import date

    missing = [date(2026, m, d) for m, d in _FIXED_HOLIDAYS_2026
               if date(2026, m, d) not in real_settings.calendar.holidays]
    assert not missing, f"takvimde yok: {[str(d) for d in missing]}"


@REAL
def test_a_holiday_never_removes_a_working_day_from_somebody_who_worked(real_settings):
    """A holiday shortens the *expected* days, never the measured ones.

    Seven people badged in on 15 July 2026 and adding the holiday changed the reported
    total by nothing at all — this asserts the mechanism that makes that true: the
    calendar is consulted for what was expected, and hours come from records.
    """
    from datetime import date

    july = real_settings.calendar.expected_workdays(2026, 7)
    assert date(2026, 7, 15) not in july, "the holiday must leave the expected list"
    assert len(july) == 22, f"July 2026 has 22 expected working days, not {len(july)}"
    assert real_settings.calendar.is_holiday(date(2026, 7, 15))
    assert real_settings.calendar.label(date(2026, 7, 15)) == "Tatil"


# --- facility labels (ADR-026) ----------------------------------------------
#
# The roster writes MACUNKÖY TESİSİ and DEICO TESİS. The second names the company, not
# the place; the site is Teknopark, which is what the report calls its records from it.

def test_the_shipped_config_renames_both_facilities(settings):
    assert settings.facility("MACUNKÖY TESİSİ") == "Macunköy"
    assert settings.facility("DEICO TESİS") == "Teknopark"


def test_matching_survives_turkish_casing_and_a_changed_suffix():
    """Folded substring, not equality: `TESİSİ` losing its last letter must not break it."""
    from mesai.config import Settings, _facility_labels

    labels = _facility_labels({"MACUNKOY": "Macunköy", "DEICO": "Teknopark"})
    probe = Settings.__new__(Settings)
    object.__setattr__(probe, "facility_labels", labels)

    for written in ("MACUNKÖY TESİSİ", "MACUNKOY TESIS", "Macunköy Tesisi",
                    "MACUNKÖY TESİS 2"):
        assert Settings.facility(probe, written) == "Macunköy", written


def test_an_unknown_facility_is_shown_exactly_as_written(settings):
    """Never guessed. A stale label table must not rename the wrong site."""
    assert settings.facility("ANKARA OFİS") == "ANKARA OFİS"
    assert settings.facility(None) == ""
    assert settings.facility("") == ""


def test_no_labels_configured_means_no_renaming():
    from mesai.config import Settings

    probe = Settings.__new__(Settings)
    object.__setattr__(probe, "facility_labels", ())
    assert Settings.facility(probe, "DEICO TESİS") == "DEICO TESİS"


def test_a_longer_needle_wins_over_a_shorter_one():
    """So a more specific entry can be added later without the short one shadowing it."""
    from mesai.config import Settings, _facility_labels

    probe = Settings.__new__(Settings)
    object.__setattr__(probe, "facility_labels",
                       _facility_labels({"DEICO": "Teknopark",
                                         "DEICO ANKARA": "Ankara"}))
    assert Settings.facility(probe, "DEICO ANKARA TESİS") == "Ankara"
    assert Settings.facility(probe, "DEICO TESİS") == "Teknopark"
