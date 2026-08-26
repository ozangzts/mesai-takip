"""Period handling and input discovery.

These guard the failure mode that matters most for the monthly automation: pointing
the tool at the wrong folder, or at a folder holding two months, and getting a
confident report full of the wrong numbers.
"""

from datetime import date, datetime, timedelta

import openpyxl
import pytest

from mesai.models import LeaveRecord, PunchRecord, RunStats
from mesai.pipeline import (
    InputError, _filter_to_period, _locate, _locate_roster, period_bounds,
)
from mesai.readers.base import find_sources


def punch(day: str, source: str = "macunkoy") -> PunchRecord:
    d = date.fromisoformat(day)
    return PunchRecord(
        source=source, source_row=1, raw_name="AYŞE DENEME", key=("AYSE", "DENEME"),
        date=d, entry=datetime.combine(d, datetime.min.time().replace(hour=8)),
        exit=datetime.combine(d, datetime.min.time().replace(hour=17)),
    )


def leave_record(day: str) -> LeaveRecord:
    return LeaveRecord(
        key=("AYSE", "DENEME"), raw_name="AYŞE DENEME", personnel_no="1",
        leave_type="Yıllık İzin", status="Kullanıldı",
        start=datetime.fromisoformat(f"{day} 07:30"),
        end=datetime.fromisoformat(f"{day} 16:30"),
        days=1.0, department="EKİP", source_row=2,
    )


# --- period bounds ---------------------------------------------------------

def test_period_bounds_handles_month_lengths():
    assert period_bounds("2026-05") == (date(2026, 5, 1), date(2026, 5, 31))
    assert period_bounds("2026-06") == (date(2026, 6, 1), date(2026, 6, 30))
    assert period_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert period_bounds("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


# --- period filter ---------------------------------------------------------

def test_records_outside_the_period_are_dropped():
    stats = RunStats()
    records = [punch("2026-06-01"), punch("2026-06-30"),
               punch("2026-05-31"), punch("2026-07-01")]
    kept, _ = _filter_to_period(records, [], "2026-06", stats)

    assert len(kept) == 2
    assert stats.out_of_period == {"macunkoy": 2}


def test_leave_outside_the_period_is_dropped():
    stats = RunStats()
    leave = [leave_record("2026-06-10"), leave_record("2026-05-10")]
    _, kept = _filter_to_period([punch("2026-06-01")], leave, "2026-06", stats)

    assert len(kept) == 1
    assert stats.out_of_period_leave == 1


# --- one source is the wrong month (ADR-023) --------------------------------
#
# Measured before this guard existed, on the real May data with June's Teknopark
# export substituted: the run SUCCEEDED, reported 4869:58 against a true 17103:58,
# and said nothing. All 2 557 Teknopark rows dropped out of period; the coverage
# check never saw the source, because it only looks at what survived the filter.

def test_one_source_entirely_outside_the_period_fails_the_run():
    """The global check passes here — the other source kept records — and used to."""
    stats = RunStats()
    records = [punch("2026-05-04", "macunkoy"), punch("2026-05-20", "macunkoy"),
               punch("2026-06-03", "teknopark"), punch("2026-06-11", "teknopark")]

    with pytest.raises(InputError, match="teknopark"):
        _filter_to_period(records, [], "2026-05", stats)


def test_the_wrong_month_message_names_the_dates_it_actually_found():
    stats = RunStats()
    records = [punch("2026-05-04", "macunkoy"), punch("2026-06-03", "teknopark")]

    with pytest.raises(InputError) as caught:
        _filter_to_period(records, [], "2026-05", stats)

    message = str(caught.value)
    assert "2026-06-03" in message, "say what the file holds"
    assert "2026-05-01 .. 2026-05-31" in message, "and what was expected"


def test_a_source_with_no_records_at_all_is_not_an_error():
    """Teknopark legitimately has none while the office is shut.

    Read nothing and kept nothing is a quiet month. Read 2 557 rows and kept none is
    the wrong file. Only the second is an error.
    """
    stats = RunStats()
    kept, _ = _filter_to_period([punch("2026-05-04", "macunkoy")], [], "2026-05", stats)

    assert len(kept) == 1


def test_a_source_keeping_even_one_record_is_not_flagged():
    """A stray row from the previous month is a data quirk, not a wrong file."""
    stats = RunStats()
    records = [punch("2026-05-04", "macunkoy"),
               punch("2026-04-30", "teknopark"), punch("2026-05-02", "teknopark")]
    kept, _ = _filter_to_period(records, [], "2026-05", stats)

    assert len(kept) == 2
    assert stats.out_of_period == {"teknopark": 1}


def test_wrong_month_raises_instead_of_reporting_the_wrong_data():
    """The real bug: --ay 2026-06 over May's folder produced a report titled
    "HAZİRAN 2026" full of May figures, and said nothing."""
    stats = RunStats()
    records = [punch("2026-05-04"), punch("2026-05-21")]
    with pytest.raises(InputError, match="hiçbir kayıt 2026-06 dönemine ait değil"):
        _filter_to_period(records, [], "2026-06", stats)


def test_empty_input_does_not_raise():
    stats = RunStats()
    kept, _ = _filter_to_period([], [], "2026-06", stats)
    assert kept == []


def test_boundary_dates_are_inside_the_period():
    stats = RunStats()
    kept, _ = _filter_to_period(
        [punch("2026-06-01"), punch("2026-06-30")], [], "2026-06", stats)
    assert len(kept) == 2
    assert stats.out_of_period == {}


# --- input discovery -------------------------------------------------------

def blank_workbook(path):
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "x"
    workbook.save(path)


def test_find_sources_ignores_lock_files_and_our_own_output(tmp_path):
    blank_workbook(tmp_path / "Teknopark - Mayıs.xlsx")
    blank_workbook(tmp_path / "~$Teknopark - Mayıs.xlsx")
    blank_workbook(tmp_path / "mesai-raporu-2026-05.xlsx")

    found = find_sources(tmp_path, ("*Teknopark*.xlsx", "mesai-raporu*.xlsx"))
    assert [p.name for p in found] == ["Teknopark - Mayıs.xlsx"]


def test_find_sources_deduplicates_overlapping_patterns(tmp_path):
    blank_workbook(tmp_path / "HCMT34_MAYIS_IZIN.xlsx")
    found = find_sources(tmp_path, ("*IZIN*.xlsx", "*MAYIS*.xlsx"))
    assert len(found) == 1


def test_two_months_in_one_folder_is_an_error(settings, tmp_path):
    """Picking one arbitrarily would silently report the wrong month."""
    blank_workbook(tmp_path / "Teknopark - Mayıs Mesai Takip Exceli.xlsx")
    blank_workbook(tmp_path / "Teknopark - Haziran Mesai Takip Exceli.xlsx")

    with pytest.raises(InputError, match="2 dosya bulundu"):
        _locate(tmp_path, settings, "teknopark")


def test_missing_file_names_the_patterns_it_looked_for(settings, tmp_path):
    with pytest.raises(InputError, match="Teknopark"):
        _locate(tmp_path, settings, "teknopark")


# --- naming one source outright (ADR-022) -----------------------------------
#
# The three exports do not always arrive in the same place. A named file bypasses the
# glob for that one source; everything downstream, the period filter included, is
# unchanged.

def test_a_named_file_is_used_instead_of_the_folder(settings, tmp_path):
    elsewhere = tmp_path / "posta"
    elsewhere.mkdir()
    named = elsewhere / "gecen ay.xlsx"
    blank_workbook(named)
    blank_workbook(tmp_path / "Teknopark - Mayıs Mesai Takip Exceli.xlsx")

    assert _locate(tmp_path, settings, "teknopark", {"teknopark": named}) == named


def test_a_named_file_settles_a_folder_holding_two_months(settings, tmp_path):
    """Two matches is otherwise an error; pointing at one is a legitimate answer."""
    mayis = tmp_path / "Teknopark - Mayıs Mesai Takip Exceli.xlsx"
    blank_workbook(mayis)
    blank_workbook(tmp_path / "Teknopark - Haziran Mesai Takip Exceli.xlsx")

    assert _locate(tmp_path, settings, "teknopark", {"teknopark": mayis}) == mayis


def test_a_named_file_that_is_gone_fails_rather_than_falling_back(settings, tmp_path):
    """Silently globbing instead would read a different file than the one chosen."""
    blank_workbook(tmp_path / "Teknopark - Mayıs Mesai Takip Exceli.xlsx")

    with pytest.raises(InputError, match="seçilen dosya bulunamadı"):
        _locate(tmp_path, settings, "teknopark", {"teknopark": tmp_path / "yok.xlsx"})


def test_naming_one_source_leaves_the_others_on_the_folder(settings, tmp_path):
    named = tmp_path / "elle.xlsx"
    blank_workbook(named)
    izin = tmp_path / "HCMT34_MAYIS_IZIN.xlsx"
    blank_workbook(izin)

    chosen = {"teknopark": named}
    assert _locate(tmp_path, settings, "teknopark", chosen) == named
    assert _locate(tmp_path, settings, "izin", chosen) == izin


# --- roster lookup (not a monthly file) ------------------------------------

def test_roster_found_in_its_own_folder(settings, tmp_path):
    """The roster is a point-in-time snapshot, so it lives outside the month
    folder and is shared by every period (ADR-011)."""
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "SYST03_TEMPIASUSERS.xlsx")
    month_dir = tmp_path / "2026-06"
    month_dir.mkdir()

    found = _locate_roster(roster_dir, month_dir, settings)
    assert found.parent == roster_dir


def test_roster_falls_back_to_the_month_folder(settings, tmp_path):
    """A Drive upload is likely to contain all four files together."""
    roster_dir = tmp_path / "personel"      # deliberately not created
    month_dir = tmp_path / "2026-06"
    month_dir.mkdir()
    blank_workbook(month_dir / "SYST03_TEMPIASUSERS.xlsx")

    found = _locate_roster(roster_dir, month_dir, settings)
    assert found.parent == month_dir


def test_roster_folder_wins_over_the_month_folder(settings, tmp_path):
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "SYST03_GUNCEL.xlsx")
    month_dir = tmp_path / "2026-06"
    month_dir.mkdir()
    blank_workbook(month_dir / "SYST03_ESKI.xlsx")

    assert _locate_roster(roster_dir, month_dir, settings).name == "SYST03_GUNCEL.xlsx"


def test_missing_roster_names_every_folder_it_searched(settings, tmp_path):
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    month_dir = tmp_path / "2026-06"
    month_dir.mkdir()

    with pytest.raises(InputError) as exc:
        _locate_roster(roster_dir, month_dir, settings)
    assert "personel" in str(exc.value)
    assert "2026-06" in str(exc.value)


def test_two_rosters_in_one_folder_is_an_error(settings, tmp_path):
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "SYST03_TEMMUZ.xlsx")
    blank_workbook(roster_dir / "SYST03_AGUSTOS.xlsx")

    with pytest.raises(InputError, match="2 dosya bulundu"):
        _locate_roster(roster_dir, tmp_path / "yok", settings)


def test_roster_matched_by_calisan_in_the_name(settings, tmp_path):
    """The file was renamed to calisan_listesi.xlsx; the pattern must follow."""
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "calisan_listesi.xlsx")
    assert _locate_roster(roster_dir, tmp_path / "yok", settings).name == \
        "calisan_listesi.xlsx"


def test_roster_pattern_is_case_insensitive_and_accepts_turkish(settings, tmp_path):
    for filename in ("CALISAN_LISTESI.xlsx", "Çalışan Listesi 2026.xlsx",
                     "personel_listesi.xlsx", "SYST03_TEMPIASUSERS.xlsx"):
        roster_dir = tmp_path / filename.replace(".", "_")
        roster_dir.mkdir()
        blank_workbook(roster_dir / filename)
        assert _locate_roster(roster_dir, tmp_path / "yok", settings).name == filename


def test_a_lone_spreadsheet_in_the_roster_folder_is_accepted(settings, tmp_path):
    """The folder normally holds exactly one file and gets renamed freely. The
    reader validates the layout afterwards, so a wrong file fails loudly."""
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "bambaska bir ad.xlsx")

    assert _locate_roster(roster_dir, tmp_path / "yok", settings).name == \
        "bambaska bir ad.xlsx"


def test_the_lone_file_fallback_does_not_apply_to_the_month_folder(settings, tmp_path):
    """Guessing inside the month folder would grab an attendance export."""
    month_dir = tmp_path / "2026-06"
    month_dir.mkdir()
    blank_workbook(month_dir / "Teknopark - Haziran.xlsx")

    with pytest.raises(InputError, match="Personel listesi bulunamadı"):
        _locate_roster(tmp_path / "personel", month_dir, settings)


def test_two_unnamed_spreadsheets_are_not_guessed(settings, tmp_path):
    roster_dir = tmp_path / "personel"
    roster_dir.mkdir()
    blank_workbook(roster_dir / "birinci.xlsx")
    blank_workbook(roster_dir / "ikinci.xlsx")

    with pytest.raises(InputError, match="Personel listesi bulunamadı"):
        _locate_roster(roster_dir, tmp_path / "yok", settings)


# --- CLI argument validation -----------------------------------------------

def test_cli_rejects_a_month_outside_01_12(capsys):
    from mesai.cli import main
    assert main(["rapor", "--ay", "2026-13"]) == 2
    assert "01-12" in capsys.readouterr().err


def test_cli_rejects_a_malformed_period(capsys):
    from mesai.cli import main
    for bad in ("2026-5", "mayis", "2026/05", "26-05"):
        assert main(["rapor", "--ay", bad]) == 2
        assert "YYYY-MM" in capsys.readouterr().err


# --- period coverage (ADR-020) ---------------------------------------------

def _punch_on(day: str, source: str = "teknopark") -> PunchRecord:
    return punch(day, source=source)


def test_full_coverage_is_not_flagged(settings):
    """June 2026's shape: every expected working day present."""
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 6)
    records = [_punch_on(d.isoformat()) for d in days]
    cov = _coverage(records, "2026-06", settings)["teknopark"]

    assert cov.present == cov.expected == len(days)
    assert cov.trailing_missing == ()
    assert not cov.is_partial


def test_a_mid_month_export_is_flagged(settings):
    """The real July 2026 Teknopark file: stops on the 19th, ten working days short."""
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 7)
    kept = [d for d in days if d.day < 20]
    cov = _coverage([_punch_on(d.isoformat()) for d in kept], "2026-07", settings)

    teknopark = cov["teknopark"]
    assert teknopark.is_partial
    assert teknopark.present == len(kept)
    assert teknopark.trailing_missing[0].day == 20
    assert len(teknopark.trailing_missing) == len(days) - len(kept)


def test_a_gap_in_the_middle_is_not_a_partial_export(settings):
    """Only a TRAILING run means the export was cut short.

    A missing day mid-month is a different problem — a closed site, a terminal
    outage — and must not be reported as an incomplete export.
    """
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 6)
    kept = days[:5] + days[8:]          # hole in the middle, last day present
    cov = _coverage([_punch_on(d.isoformat()) for d in kept], "2026-06", settings)

    assert not cov["teknopark"].is_partial
    assert cov["teknopark"].present == len(kept)


def test_one_trailing_day_is_tolerated(settings):
    """An export run on the final working day has nothing for it yet. Not an alarm."""
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 6)
    cov = _coverage([_punch_on(d.isoformat()) for d in days[:-1]], "2026-06", settings)

    assert len(cov["teknopark"].trailing_missing) == 1
    assert not cov["teknopark"].is_partial


def test_leave_records_are_not_an_attendance_source(settings):
    """`izin` covers only days people were away; judging its coverage is meaningless."""
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 6)
    records = [_punch_on(days[0].isoformat(), source="izin")]
    assert _coverage(records, "2026-06", settings) == {}


def test_each_source_is_measured_separately(settings):
    """Teknopark being short must not be masked by Macunköy being complete."""
    from mesai.pipeline import _coverage
    days = settings.calendar.expected_workdays(2026, 7)
    records = ([_punch_on(d.isoformat(), "macunkoy") for d in days]
               + [_punch_on(d.isoformat(), "teknopark") for d in days if d.day < 20])
    cov = _coverage(records, "2026-07", settings)

    assert not cov["macunkoy"].is_partial
    assert cov["teknopark"].is_partial


# --- a month that is mostly unaccounted for (ADR-030) -----------------------
#
# The gap between two existing rules, found by looking at June 2026: one person had a
# single 2:30 day out of 22 expected working days and carried no note at all.
# `short_day_hours` asks about ONE day and theirs was above the threshold;
# NO_ATTENDANCE_DATA needs the month to be completely empty.

def _summaries(settings, workdays, leave=(), employees=None, records=None):
    """`_summarise` over one synthetic month.

    `records` defaults to one punch per workday, because that is what a real month looks
    like: a counted day always has a record behind it. Passing them separately is what
    lets a test set up the case where a record exists and could not be counted, which is
    the pair ADR-067 was about.
    """
    from mesai.anomalies import Collector
    from mesai.models import PunchRecord
    from mesai.pipeline import _summarise
    collector = Collector()
    if records is None:
        records = [PunchRecord(source="teknopark", source_row=n, raw_name="",
                               key=w.key, date=w.date, entry=None, exit=None)
                   for n, w in enumerate(workdays, start=1)]
    return _summarise("2026-06", employees, workdays, list(leave), collector,
                      settings, list(records)), collector


def _employee(key=("AYSE", "DENEME")):
    from mesai.models import Employee
    return Employee(key=key, display_name="AYŞE DENEME", personnel_no="8801",
                    department=None, job_title=None, facility=None, in_roster=True,
                    sources=frozenset({"teknopark"}))


def _day(day: int, key=("AYSE", "DENEME")):
    from datetime import date as _date
    from mesai.models import Interval, WorkDay
    start = datetime(2026, 6, day, 9, 0)
    end = datetime(2026, 6, day, 18, 0)
    return WorkDay(key=key, date=_date(2026, 6, day),
                   intervals=(Interval(start, end, frozenset({"teknopark"})),),
                   gross=timedelta(hours=9), break_deduction=timedelta(),
                   net=timedelta(hours=9), tags=frozenset())


def test_one_ordinary_day_in_a_whole_month_is_flagged(settings):
    """The case `Ay büyük ölçüde boş` was written for — now answered day by day.

    Normal hours, so no per-day duration rule fires, and 1 day of 22. The month-level
    note is gone (ADR-062): every one of the other days now carries `Hem giriş hem çıkış
    yok`, which says the same thing and says which days.
    """
    key = ("AYSE", "DENEME")
    _, collector = _summaries(settings, [_day(3, key)], employees={key: _employee()})

    gunler = [a for a in collector.items if a.label == "Hem giriş hem çıkış yok"]
    assert len(gunler) > 15, "the empty month has to show up as its empty days"
    assert "Ay büyük ölçüde boş" not in [a.label for a in collector.items]


def test_a_full_month_is_not_flagged(settings):
    """Every expected working day worked, so nothing is unexplained."""
    key = ("AYSE", "DENEME")
    days = [_day(d, key) for d in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 15, 16, 17, 18,
                                   19, 22, 23, 24, 25, 26, 29, 30)]
    _, collector = _summaries(settings, days, employees={key: _employee()})

    assert "Hem giriş hem çıkış yok" not in [a.label for a in collector.items]


def test_leave_counts_towards_the_month_being_accounted_for(settings):
    """Somebody on leave for three weeks has an explained month, not a suspicious one.

    The leave dates are covered, so no day of them is flagged.
    """
    from mesai.models import LeaveRecord
    key = ("AYSE", "DENEME")
    leave = [LeaveRecord(key=key, raw_name="AYŞE DENEME", personnel_no="8801",
                         leave_type="Yıllık İzin", status="Kullanıldı",
                         start=datetime(2026, 6, 8), end=datetime(2026, 6, 26),
                         days=15.0, department=None, source_row=2)]
    _, collector = _summaries(settings, [_day(3, key)], leave=leave,
                              employees={key: _employee()})
    isaretli = {a.date for a in collector.items
                if a.label == "Hem giriş hem çıkış yok"}

    assert not any(date(2026, 6, 8) <= d <= date(2026, 6, 26) for d in isaretli)


def test_a_month_with_no_records_at_all_gets_only_the_louder_note(settings):
    """Two notes for one situation reads as two problems."""
    key = ("AYSE", "DENEME")
    _, collector = _summaries(settings, [], employees={key: _employee()})

    labels = [a.label for a in collector.items]
    assert "Kart bilgisi yok" in labels
    assert "Ay büyük ölçüde boş" not in labels


def test_a_named_roster_is_used_instead_of_searching(settings, tmp_path):
    """ADR-035: not month-specific, and a packaged program may have no data/personel/."""
    from mesai.pipeline import _locate_roster
    home = tmp_path / "personel"
    home.mkdir()
    blank_workbook(home / "calisan_listesi.xlsx")
    elsewhere = tmp_path / "masaustu"
    elsewhere.mkdir()
    named = elsewhere / "IK listesi.xlsx"
    blank_workbook(named)

    assert _locate_roster(home, tmp_path, settings, named) == named


def test_a_named_roster_that_is_gone_fails_rather_than_falling_back(settings, tmp_path):
    from mesai.pipeline import _locate_roster
    home = tmp_path / "personel"
    home.mkdir()
    blank_workbook(home / "calisan_listesi.xlsx")

    with pytest.raises(InputError, match="seçilen dosya bulunamadı"):
        _locate_roster(home, tmp_path, settings, tmp_path / "yok.xlsx")


# --- a hole in the MIDDLE of the period (ADR-057) ----------------------------

def _settings_with_calendar(*, holidays=()):
    """The shipped settings with a substituted calendar, so a holiday can be removed.

    `dataclasses.replace` rather than a hand-built Settings: a fixture that invented its
    own would drift from `config/settings.yaml` the way `conftest.py` twice did.
    """
    import dataclasses
    from pathlib import Path

    from mesai import config as config_module

    base = config_module.load(
        Path(__file__).resolve().parent.parent / "config", "2026-06")
    return dataclasses.replace(
        base,
        calendar=config_module.Calendar(holidays=frozenset(holidays),
                                       rest_weekdays=base.calendar.rest_weekdays))



def test_a_working_day_nobody_recorded_anywhere_is_reported():
    """The trailing check cannot see a gap in the middle, and a per-source mid-period
    check would fire on a site that was simply shut — which AGENTS §3 forbids.

    A day on which NEITHER site recorded a single person is the one mid-period shape
    that can be asserted: 162 people do not all stay home on an ordinary working day.
    """
    from datetime import date, datetime

    from mesai.models import PunchRecord
    from mesai.pipeline import _blank_workdays

    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)
    bos = gunler[5]

    kayitlar = [
        PunchRecord(key=("AYSE", "DENEME"), raw_name="AYŞE DENEME",
                    date=g, source="teknopark",
                    entry=datetime.combine(g, datetime.min.time()).replace(hour=8),
                    exit=datetime.combine(g, datetime.min.time()).replace(hour=17),
                    source_row=1)
        for g in gunler if g != bos
    ]

    assert _blank_workdays(kayitlar, "2026-06", settings) == (bos,)


def test_a_holiday_is_never_a_blank_working_day():
    """The question the operator asked: how do we know 25 September was not a holiday?

    Because holidays leave `expected_workdays` before this check runs. May 2026 has
    only 14 expected working days for exactly this reason — 25-29 May is a five-day
    block plus the 1st and the 19th.
    """
    from mesai.pipeline import _blank_workdays

    gunler = _settings_with_calendar(holidays=()).calendar.expected_workdays(2026, 6)
    tatil = gunler[5]
    settings = _settings_with_calendar(holidays=(tatil,))

    # no records at all, and yet the marked day is not reported as blank
    assert tatil not in _blank_workdays([], "2026-06", settings)
    assert tatil not in settings.calendar.expected_workdays(2026, 6)


def test_an_unmarked_holiday_on_which_somebody_worked_raises_nothing():
    """The residual risk, and it turns out to be small — measured, not assumed.

    Ramazan and Kurban move and are entered by hand, so one can be forgotten; 15 July
    2026 was, for a month. But this check needs a day on which **nobody at either site**
    was recorded, and Macunköy production runs on holidays. Re-running all three months
    with `holidays: []` — every holiday deliberately removed — produced **no** blank
    working day at all. May's Ramazan block was caught by the trailing check instead
    (ADR-020), which is the loud, dismissible failure that is wanted.

    So an unmarked holiday raises this only if the site really was empty, which is
    itself worth a look.
    """
    from datetime import datetime

    from mesai.models import PunchRecord
    from mesai.pipeline import _blank_workdays

    settings = _settings_with_calendar(holidays=())          # nothing marked
    gunler = settings.calendar.expected_workdays(2026, 6)
    tatil = gunler[5]

    tek_kisi = [PunchRecord(
        key=("AYSE", "DENEME"), raw_name="AYŞE DENEME", date=tatil,
        source="macunkoy", source_row=1,
        entry=datetime.combine(tatil, datetime.min.time()).replace(hour=8),
        exit=datetime.combine(tatil, datetime.min.time()).replace(hour=17))]

    assert tatil not in _blank_workdays(tek_kisi, "2026-06", settings)
    # and with nobody at all, it does fire — the check is not inert
    assert tatil in _blank_workdays([], "2026-06", settings)


# --- days the person is simply absent from the export (ADR-060) ---------------

def _wd(key, day, hours=9):
    """One counted workday, enough for the checks that only look at dates."""
    from datetime import datetime, timedelta

    from mesai.models import Interval, WorkDay
    start = datetime.combine(day, datetime.min.time()).replace(hour=8)
    end = start + timedelta(hours=hours)
    return WorkDay(key=key, date=day,
                   intervals=(Interval(start, end, frozenset({"teknopark"})),),
                   gross=timedelta(hours=hours), break_deduction=timedelta(),
                   net=timedelta(hours=hours))


def _absent_employee(key):
    """Named apart from this file's older `_employee()`, which takes no argument."""
    from mesai.models import Employee
    return Employee(key=key, display_name="AYŞE DENEME", email=None,
                    personnel_no=None, department=None, facility=None,
                    in_roster=True, sources=frozenset({"teknopark"}))


def _unrecorded(recorded_days, *, leave=()):
    """Run the check over one person and return the dates it flagged.

    `recorded_days` are the days the person appears in an attendance source — not the
    days that could be counted. Those are different facts and confusing them was the
    bug (ADR-067): a one-sided record yields no interval, so a day with a real badge
    reading looked unrecorded.
    """
    from mesai.anomalies import AnomalyKind, Collector
    from mesai.pipeline import _unrecorded_days

    key = ("AYSE", "DENEME")
    settings = _settings_with_calendar(holidays=())
    expected = settings.calendar.expected_workdays(2026, 6)
    collector = Collector()
    _unrecorded_days(
        collector, {key: _absent_employee(key)},
        {key: set(recorded_days)}, list(leave), expected)
    return sorted(a.date for a in collector.items
                  if a.kind is AnomalyKind.EMPTY_RECORD)


def test_a_day_with_no_record_anywhere_is_flagged():
    """The gap: `Hem giriş hem çıkış yok` needed a blank ROW, so a day with no row at
    all raised nothing. July 2026 had 11 people in that position with no note at all."""
    from mesai.pipeline import _blank_workdays  # noqa: F401  (same module)

    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)
    calisti = [g for g in gunler if g not in (gunler[3], gunler[7])]

    assert _unrecorded(calisti) == [gunler[3], gunler[7]]


def test_there_is_no_anchor_at_the_start_of_the_month():
    """An anchor at the first record was tried and removed (ADR-061).

    It swallowed the case it could not tell apart. Measured across June and July 2026: of
    the people whose first record falls after the month's first working day, **13 of 15
    and 11 of 16 had records in the previous month** — not new at all, and 60 and 45 days
    were being hidden. Telling a joiner from a gap needs a hire date, which the roster
    does not carry (ROADMAP Q18), so the program says what it found and a person decides.
    """
    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)

    # first record is the 15th expected day; the 14 before it are flagged too
    assert _unrecorded([gunler[14], gunler[15]]) == gunler[:14] + gunler[16:]


def test_a_day_covered_by_leave_is_not_flagged():
    from datetime import datetime

    from mesai.models import LeaveRecord

    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)
    izinli = gunler[3]
    izin = [LeaveRecord(
        key=("AYSE", "DENEME"), raw_name="AYŞE DENEME", personnel_no=None,
        leave_type="Yıllık İzin", status="Kullanıldı",
        start=datetime.combine(izinli, datetime.min.time()),
        end=datetime.combine(izinli, datetime.min.time()), days=1.0,
        department=None, source_row=3)]

    calisti = [g for g in gunler if g != izinli]
    assert _unrecorded(calisti, leave=izin) == []


def test_a_mostly_empty_month_is_flagged_day_by_day_as_well():
    """Skipping these people was tried too, and removed with the anchor (ADR-061).

    Both were a threshold deciding what the operator gets to see. Somebody with one
    worked day now carries that one day plus every other working day of the month, and
    the month-level note besides — which is what "yönetim karar versin" means.
    """
    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)

    assert _unrecorded([gunler[0]]) == gunler[1:]


def test_somebody_with_no_attendance_at_all_gets_no_daily_notes():
    """`Kart bilgisi yok` already says it, and says it louder."""
    assert _unrecorded([]) == []


# --- a record that could not be used is still a record (ADR-067) --------------

def test_a_one_sided_record_is_not_an_unrecorded_day():
    """The bug the operator found: 29 July said `Giriş yok` and `Hem giriş hem çıkış yok`
    on the same day, and there was an exit.

    A record with one punch yields no interval and therefore no `WorkDay`, and the check
    was deciding "was there a record" from the workdays. Measured on July 2026: 154
    person-days had a badge reading and were called unrecorded.
    """
    settings = _settings_with_calendar(holidays=())
    gunler = settings.calendar.expected_workdays(2026, 6)
    okunan = gunler[3]

    # the person appears on that day, though nothing could be counted for it
    assert okunan not in _unrecorded([okunan]), \
        "damgası okunmuş bir gün 'hiç kayıt yok' diye işaretlenemez"
    # and the days they do not appear on are still flagged
    assert _unrecorded([okunan]) == [d for d in gunler if d != okunan]


def test_someone_whose_every_reading_was_refused_still_has_attendance(settings):
    """Seven people in July badged on 12 to 21 days and had every reading refused. They
    were told `Kart bilgisi yok` — that there was no card record for them at all.
    """
    from mesai.models import PunchRecord

    key = ("AYSE", "DENEME")
    kayitlar = [
        PunchRecord(source="macunkoy", source_row=n, raw_name="AYŞE DENEME", key=key,
                    date=date(2026, 6, gun), entry=datetime(2026, 6, gun, 8), exit=None)
        for n, gun in enumerate((1, 2, 3, 4, 5), start=1)]

    summaries, collector = _summaries(settings, [], employees={key: _employee()},
                                      records=kayitlar)

    assert summaries[0].has_attendance, "kaydı olan kişinin kaydı var sayılmalı"
    assert "Kart bilgisi yok" not in [a.label for a in collector.items]
    # their days are not silent either — the records' own notes speak for them
    assert not any(a.date in {date(2026, 6, d) for d in (1, 2, 3, 4, 5)}
                   and a.label == "Hem giriş hem çıkış yok"
                   for a in collector.items)


def test_no_day_carries_two_contradictory_missing_punch_notes(settings):
    """`Giriş yok` and `Hem giriş hem çıkış yok` on one day cannot both be true, and the
    reader is right to say so."""
    from mesai.models import PunchRecord

    key = ("AYSE", "DENEME")
    gun = date(2026, 6, 4)
    kayit = [PunchRecord(source="macunkoy", source_row=1, raw_name="AYŞE DENEME",
                         key=key, date=gun, entry=None,
                         exit=datetime(2026, 6, 4, 18, 26))]

    _summaries(settings, [], employees={key: _employee()}, records=kayit)
    _, collector = _summaries(settings, [], employees={key: _employee()},
                              records=kayit)
    o_gun = {a.label for a in collector.items if a.date == gun}

    assert "Hem giriş hem çıkış yok" not in o_gun, o_gun


def test_a_note_about_a_day_that_counted_is_not_the_persons_note(settings):
    """The operator's case: the summary said `Hem giriş hem çıkış yok` and the daily
    detail showed an ordinary nine-hour day for the same date (ADR-068).

    A blank Macunköy row on a day the person's Teknopark record covered in full. The
    record was refused, the day was counted, and there is nothing to chase — so the
    `Not` column, which is the one that says "look at this", must not carry it. The
    audit sheets keep the record either way.
    """
    from mesai.anomalies import Anomaly, AnomalyKind, Collector
    from mesai.models import PunchRecord

    key = ("AYSE", "DENEME")
    gun = date(2026, 6, 2)
    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.EMPTY_RECORD, source="macunkoy", source_row=4, key=key,
        raw_name="AYŞE DENEME", date=gun))

    # A record and a counted day on EVERY expected working day, so the only thing left
    # to produce a note is the blank row. Without this the person's other 21 days are
    # unrecorded and carry the same label for a reason that has nothing to do with the
    # case under test.
    from mesai.pipeline import _summarise
    gunler = _settings_with_calendar(holidays=()).calendar.expected_workdays(2026, 6)
    kayitlar = [PunchRecord(source="teknopark", source_row=n, raw_name="AYŞE DENEME",
                            key=key, date=d, entry=None, exit=None)
                for n, d in enumerate(gunler, start=1)]
    workdays = [_day(d.day, key) for d in gunler]
    summaries = _summarise("2026-06", {key: _employee()}, workdays, [],
                           collector, settings, kayitlar)

    assert "Hem giriş hem çıkış yok" not in summaries[0].notes, summaries[0].notes
    # the record is still counted and still in the audit trail
    assert summaries[0].anomaly_count >= 1
    assert any(a.label == "Hem giriş hem çıkış yok" for a in collector.items)


def test_a_note_about_a_day_that_counted_nothing_stays(settings):
    """The other half. A rule that never fires in the original direction is not a fix."""
    from mesai.anomalies import Anomaly, AnomalyKind, Collector
    from mesai.models import PunchRecord
    from mesai.pipeline import _summarise

    key = ("AYSE", "DENEME")
    gun = date(2026, 6, 3)
    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.MISSING_EXIT, source="macunkoy", source_row=4, key=key,
        raw_name="AYŞE DENEME", date=gun))

    gunler = _settings_with_calendar(holidays=()).calendar.expected_workdays(2026, 6)
    kayitlar = [PunchRecord(source="macunkoy", source_row=n, raw_name="AYŞE DENEME",
                            key=key, date=d, entry=None, exit=None)
                for n, d in enumerate(gunler, start=1)]
    # every day counted EXCEPT the one the note is about
    workdays = [_day(d.day, key) for d in gunler if d != gun]
    summaries = _summarise("2026-06", {key: _employee()}, workdays, [],
                           collector, settings, kayitlar)

    assert "Çıkış yok" in summaries[0].notes, summaries[0].notes
