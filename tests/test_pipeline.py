"""Period handling and input discovery.

These guard the failure mode that matters most for the monthly automation: pointing
the tool at the wrong folder, or at a folder holding two months, and getting a
confident report full of the wrong numbers.
"""

from datetime import date, datetime

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
