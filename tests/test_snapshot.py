"""The report's machine-readable companion.

The point of these tests is the contract between a run and whatever reads it later
(the mail step, the window's "use the existing report" path). If a snapshot cannot be
written and read back to the same figures, that later step is guessing.
"""

from datetime import date, datetime, timedelta

import pytest

from mesai.anomalies import Anomaly, AnomalyKind, Collector
from mesai.models import Employee, MonthSummary, RunStats, SourceCoverage
from mesai import snapshot as snap

KEY_A = ("AYSE", "DENEME")
KEY_B = ("VELI", "ORNEK")


def _employee(key, name, email="a@example.com", in_roster=True) -> Employee:
    return Employee(
        key=key, display_name=name, personnel_no="8801", department="TEST EKİBİ",
        job_title="TEST MÜHENDİSİ", facility="DEICO TESİS", email=email,
        in_roster=in_roster, sources=frozenset({"teknopark"}),
    )


def _summary(employee, minutes=579, has_attendance=True, notes=()) -> MonthSummary:
    return MonthSummary(
        employee=employee, period="2026-07",
        gross=timedelta(minutes=minutes), net=timedelta(minutes=minutes),
        worked_days=14, remote_days=1.0, leave_days=2.5, anomaly_count=1,
        has_attendance=has_attendance, notes=notes,
    )


def _anomalies() -> Collector:
    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.MISSING_EXIT, source="macunkoy", source_row=7, key=KEY_A,
        raw_name="AYŞE DENEME", date=date(2026, 7, 3)))
    collector.add(Anomaly(
        kind=AnomalyKind.SHORT_DAY, source="teknopark", source_row=9, key=KEY_A,
        raw_name="AYŞE DENEME", date=date(2026, 7, 6)))
    # `info` severity — expected behaviour, must NOT become a "problem" to mail about.
    collector.add(Anomaly(
        kind=AnomalyKind.REMOTE_REPLACED_NOMINAL, source="izin", source_row=11, key=KEY_B,
        raw_name="VELİ ÖRNEK", date=date(2026, 7, 8)))
    return collector


def _stats(partial=False) -> RunStats:
    trailing = tuple(date(2026, 7, d) for d in (20, 21, 22)) if partial else ()
    return RunStats(coverage={
        "teknopark": SourceCoverage("teknopark", 13 if partial else 23, 23, trailing),
        "macunkoy": SourceCoverage("macunkoy", 23, 23, ()),
    })


def _build(settings, partial=False) -> snap.Snapshot:
    return snap.build(
        "2026-07",
        [_summary(_employee(KEY_A, "AYŞE DENEME")),
         _summary(_employee(KEY_B, "VELİ ÖRNEK", email=None), minutes=1200)],
        _anomalies(), _stats(partial), settings, datetime(2026, 8, 18, 10, 0),
    )


# --- round trip -------------------------------------------------------------

def test_a_snapshot_survives_the_round_trip(tmp_path, settings):
    original = _build(settings)
    path = snap.save(original, tmp_path / "veri" / "gonderim-2026-07.json")
    loaded = snap.load(path)

    assert loaded.period == original.period
    assert loaded.generated_at == original.generated_at
    assert loaded.rules == original.rules
    assert loaded.coverage == original.coverage
    assert loaded.people == original.people, "people must compare equal, field for field"


def test_hours_survive_as_minutes_not_floats(tmp_path, settings):
    """579 minutes is 9:39. A float round trip is how 9:39 becomes 9:38."""
    path = snap.save(_build(settings), tmp_path / "s.json")
    person = next(p for p in snap.load(path).people if p.name == "AYŞE DENEME")

    assert person.minutes == 579
    assert person.hours_text == "9:39"


def test_the_active_rules_travel_with_the_data(tmp_path, settings):
    """Without them, the same numbers mean different things a month later."""
    loaded = snap.load(snap.save(_build(settings), tmp_path / "s.json"))

    assert loaded.rules["daily_hours"] == "envelope"
    assert loaded.rules["break_deducted"] is False
    assert loaded.rules["short_day_hours"] == 2.0
    assert loaded.rules["remote_replaces_attendance"] == "nominal_only"


# --- what a later step actually asks it ------------------------------------

def test_problems_are_per_person_and_filterable(settings):
    """"Mail only the people with a missing exit" is the whole reason for this field."""
    built = _build(settings)

    assert built.with_problem("Çıkış yok") == \
        tuple(p for p in built.people if p.name == "AYŞE DENEME")
    assert built.with_problem("Bilinmeyen sorun") == ()


def test_info_anomalies_are_not_problems(settings):
    """An expected-behaviour note must not put somebody on a mailing list."""
    built = _build(settings)
    veli = next(p for p in built.people if p.name == "VELİ ÖRNEK")

    assert veli.problems == (), "REMOTE_REPLACED_NOMINAL is info severity"


def test_problem_labels_are_ordered_by_frequency(settings):
    built = _build(settings)
    assert set(built.problem_labels) == {"Çıkış yok", "Günlük süre çok kısa (<2 saat)"}


def test_a_partial_run_is_marked_incomplete(settings):
    """The mail step must be able to refuse a snapshot built from half a month."""
    assert _build(settings, partial=False).is_complete
    incomplete = _build(settings, partial=True)
    assert not incomplete.is_complete
    assert incomplete.coverage["teknopark"]["missing_from"] == "2026-07-20"


def test_a_missing_email_is_preserved_as_none(settings):
    """Silently turning it into "" would make it look like a deliverable address."""
    built = _build(settings)
    assert next(p for p in built.people if p.name == "VELİ ÖRNEK").email is None


# --- refusing rather than guessing -----------------------------------------

def test_a_missing_snapshot_says_what_to_do(tmp_path):
    with pytest.raises(snap.SnapshotError, match="yeniden üretin"):
        snap.load(tmp_path / "yok.json")


def test_an_unknown_format_version_is_refused(tmp_path, settings):
    """A newer or older file must not be read on a best-effort basis."""
    path = snap.save(_build(settings), tmp_path / "s.json")
    text = path.read_text(encoding="utf-8").replace(
        f'"format_version": {snap.FORMAT_VERSION}', '"format_version": 999')
    path.write_text(text, encoding="utf-8")

    with pytest.raises(snap.SnapshotError, match="sürümü 999"):
        snap.load(path)


def test_corrupt_json_is_refused(tmp_path):
    path = tmp_path / "bozuk.json"
    path.write_text("{ bu json degil", encoding="utf-8")
    with pytest.raises(snap.SnapshotError, match="okunamadı"):
        snap.load(path)


def test_no_temp_file_is_left_behind(tmp_path, settings):
    path = snap.save(_build(settings), tmp_path / "s.json")
    assert path.exists()
    assert not list(tmp_path.glob("*.tmp.json"))


# --- the problem days (ADR-051) ---------------------------------------------
#
# The mail step chooses people by the notes that were ticked, and then has to list
# **the days those notes are about** — not every day the person had a note on. Somebody
# with a missing exit on the 3rd and a cross-site repair on the 9th gets told about the
# 3rd only, if the repair was not ticked. So the day is the unit and the label travels
# with it.

def _workday(key, day, first, last, minutes):
    from mesai.models import Interval, WorkDay

    start = datetime(day.year, day.month, day.day, *first)
    end = datetime(day.year, day.month, day.day, *last)
    return WorkDay(
        key=key, date=day,
        intervals=(Interval(start, end, frozenset({"teknopark"})),),
        gross=timedelta(minutes=minutes), break_deduction=timedelta(),
        net=timedelta(minutes=minutes))


def test_a_person_carries_the_days_their_notes_are_about(settings):
    days = _build(settings).people
    ayse = next(p for p in days if p.name == "AYŞE DENEME")

    assert [d.date for d in ayse.days] == [date(2026, 7, 3), date(2026, 7, 6)]
    assert ayse.days[0].problems == ("Çıkış yok",)
    assert ayse.days[1].problems == ("Günlük süre çok kısa (<2 saat)",)


def test_the_days_are_in_date_order(settings):
    """They are read as a list of dates by a person; frequency order would be unreadable."""
    ayse = next(p for p in _build(settings).people if p.name == "AYŞE DENEME")

    assert [d.date for d in ayse.days] == sorted(d.date for d in ayse.days)


def test_an_expected_behaviour_note_produces_no_day(settings):
    """VELİ's only note is `info`. Nobody is mailed about the program working (ADR-017)."""
    veli = next(p for p in _build(settings).people if p.name == "VELİ ÖRNEK")

    assert veli.days == ()
    assert veli.expected, "the note is still recorded, just not as a day"


def test_a_month_level_note_produces_no_day(settings):
    """`Kart bilgisi yok` has no date, so there is no day to tell anybody about."""
    from mesai.anomalies import Anomaly, AnomalyKind, Collector

    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.NO_ATTENDANCE_DATA, source="izin", source_row=0, key=KEY_A,
        raw_name="AYŞE DENEME"))                      # no date

    built = snap.build("2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))],
                       collector, _stats(), settings, datetime(2026, 8, 18, 10, 0))
    person = built.people[0]

    assert person.days == ()
    assert "Kart bilgisi yok" in person.problems, "still a problem, just not a day"


def test_a_day_that_counted_carries_the_measured_times(settings):
    """When the day produced an interval, the figures are the measured ones."""
    built = snap.build(
        "2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))], _anomalies(),
        _stats(), settings, datetime(2026, 8, 18, 10, 0),
        workdays=[_workday(KEY_A, date(2026, 7, 3), (7, 58), (18, 29), 631)])
    day = next(d for d in built.people[0].days if d.date == date(2026, 7, 3))

    assert (day.entry, day.exit) == ("07:58", "18:29")
    assert day.minutes == 631
    assert day.hours_text == "10:31"


def test_a_refused_record_falls_back_to_what_the_file_said(settings):
    """The case the reader most needs: no interval at all, so no measured time.

    A missing exit can mean the whole day was refused. `minutes` is then `None` — not
    zero, which would read as "worked nothing" rather than "nothing could be counted" —
    and the times come from the source's own stamps.
    """
    from mesai.anomalies import Anomaly, AnomalyKind, Collector

    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.MISSING_EXIT, source="macunkoy", source_row=7, key=KEY_A,
        raw_name="AYŞE DENEME", date=date(2026, 7, 3),
        raw_entry="08:12", raw_exit=""))

    built = snap.build("2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))],
                       collector, _stats(), settings, datetime(2026, 8, 18, 10, 0))
    day = built.people[0].days[0]

    assert (day.entry, day.exit) == ("08:12", "")
    assert day.minutes is None
    assert day.hours_text == "", "no measured time is empty, not 0:00"


def test_two_notes_on_one_day_are_one_day_with_two_labels(settings):
    from mesai.anomalies import Anomaly, AnomalyKind, Collector

    collector = Collector()
    for kind in (AnomalyKind.MISSING_EXIT, AnomalyKind.SHORT_DAY):
        collector.add(Anomaly(
            kind=kind, source="macunkoy", source_row=7, key=KEY_A,
            raw_name="AYŞE DENEME", date=date(2026, 7, 3)))

    built = snap.build("2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))],
                       collector, _stats(), settings, datetime(2026, 8, 18, 10, 0))

    assert len(built.people[0].days) == 1
    assert built.people[0].days[0].problems == (
        "Günlük süre çok kısa (<2 saat)", "Çıkış yok")


def test_the_days_survive_the_round_trip(tmp_path, settings):
    """A file that loses them would make the mail step guess, which is the whole point."""
    original = snap.build(
        "2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))], _anomalies(),
        _stats(), settings, datetime(2026, 8, 18, 10, 0),
        workdays=[_workday(KEY_A, date(2026, 7, 3), (7, 58), (18, 29), 631)])
    path = snap.save(original, tmp_path / "gonderim-2026-07.json")

    assert snap.load(path).people[0].days == original.people[0].days


def test_choosing_labels_selects_a_subset_of_the_days(settings):
    """The mail rule, stated once here so it is not invented twice later.

    Measured on July 2026: with the three punch notes ticked, 64 people would be
    written to and 244 of their 284 problem days sent — the other 40 belong to notes
    nobody ticked.
    """
    ayse = next(p for p in _build(settings).people if p.name == "AYŞE DENEME")
    chosen = {"Çıkış yok"}

    sendable = [d for d in ayse.days if chosen & set(d.problems)]

    assert [d.date for d in sendable] == [date(2026, 7, 3)]
    assert len(ayse.days) == 2, "the other day stays out of the message"


def test_the_day_carries_the_leave_that_covers_it(settings):
    """`covered_by` exists so the mail step can tell "no record" from "on leave"."""
    from datetime import date, datetime

    from mesai.anomalies import Anomaly, AnomalyKind, Collector
    from mesai.models import LeaveRecord

    collector = Collector()
    for day in (3, 9):
        collector.add(Anomaly(
            kind=AnomalyKind.MISSING_EXIT, source="macunkoy", source_row=day, key=KEY_A,
            raw_name="AYŞE DENEME", date=date(2026, 7, day)))

    izin = [LeaveRecord(
        key=KEY_A, raw_name="AYŞE DENEME", personnel_no="8801",
        leave_type="Yıllık İzin", status="Kullanıldı",
        start=datetime(2026, 7, 3, 8, 0), end=datetime(2026, 7, 4, 18, 0),
        days=2.0, department="TEST EKİBİ", source_row=3)]

    built = snap.build("2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))],
                       collector, _stats(), settings, datetime(2026, 8, 25, 10, 0),
                       leave=izin)
    days = {d.date.day: d for d in built.people[0].days}

    assert days[3].covered_by == "Yıllık İzin", "multi-day row must cover both days"
    assert days[9].covered_by == ""
    assert days[3].explained and not days[9].explained


def test_covered_by_survives_the_round_trip(tmp_path, settings):
    from datetime import date, datetime

    from mesai.anomalies import Anomaly, AnomalyKind, Collector
    from mesai.models import LeaveRecord

    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.MISSING_EXIT, source="macunkoy", source_row=3, key=KEY_A,
        raw_name="AYŞE DENEME", date=date(2026, 7, 3)))
    izin = [LeaveRecord(
        key=KEY_A, raw_name="AYŞE DENEME", personnel_no="8801",
        leave_type="Mazeret", status="Kullanıldı",
        start=datetime(2026, 7, 3, 8, 0), end=datetime(2026, 7, 3, 12, 0),
        days=0.44, department="TEST EKİBİ", source_row=3)]

    original = snap.build("2026-07", [_summary(_employee(KEY_A, "AYŞE DENEME"))],
                          collector, _stats(), settings, datetime(2026, 8, 25, 10, 0),
                          leave=izin)
    path = snap.save(original, tmp_path / "gonderim-2026-07.json")

    assert snap.load(path).people[0].days[0].covered_by == "Mazeret"


def test_a_days_times_are_shown_as_a_clock_whatever_the_source_wrote():
    """`entry` keeps the file's own text for a refused record — right for the audit
    trail, wrong for a screen. The panel would read `01.07.2026 07:17:04` beside a
    column that already says the date and rows that read `07:41` (ADR-064).
    """
    from datetime import date

    from mesai.snapshot import ProblemDay

    def gun(entry):
        return ProblemDay(date=date(2026, 7, 1), problems=("Çıkış yok",), entry=entry)

    assert gun("01.07.2026 07:17:04").entry_text == "07:17"
    assert gun("2026-07-01 09:08:10").entry_text == "09:08"
    assert gun("07:41").entry_text == "07:41"
    assert gun("9:5").entry_text == "09:05"
    assert gun("").entry_text == ""
    # Not a time we recognise: shown as it stands rather than swallowed. A blank cell
    # would hide that the source wrote something.
    assert gun("garip").entry_text == "garip"


def test_the_stored_stamp_stays_exactly_what_the_file_said():
    """The formatting is at the boundary and only there — the report prints the raw
    text verbatim and must keep being able to."""
    from datetime import date

    from mesai.snapshot import ProblemDay

    day = ProblemDay(date=date(2026, 7, 1), problems=("Çıkış yok",),
                     entry="01.07.2026 07:17:04")
    assert day.entry == "01.07.2026 07:17:04"
