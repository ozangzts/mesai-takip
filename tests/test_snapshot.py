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
        kind=AnomalyKind.REMOTE_OVERLAP, source="izin", source_row=11, key=KEY_B,
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

    assert built.with_problem("Çıkış kaydı yok") == \
        tuple(p for p in built.people if p.name == "AYŞE DENEME")
    assert built.with_problem("Bilinmeyen sorun") == ()


def test_info_anomalies_are_not_problems(settings):
    """An expected-behaviour note must not put somebody on a mailing list."""
    built = _build(settings)
    veli = next(p for p in built.people if p.name == "VELİ ÖRNEK")

    assert veli.problems == (), "REMOTE_OVERLAP is info severity"


def test_problem_labels_are_ordered_by_frequency(settings):
    built = _build(settings)
    assert set(built.problem_labels) == {"Çıkış kaydı yok", "Günlük süre eşiğin altında"}


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
