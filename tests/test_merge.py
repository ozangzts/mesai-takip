"""Cross-site reconciliation — where the bugs live.

76 employees appear in both attendance exports; getting this wrong either
double-counts or discards real hours.
"""

from datetime import date, datetime, timedelta

from mesai.anomalies import AnomalyKind
from mesai.merge import build_workdays
from mesai.models import PunchRecord
from mesai.rules.worktime import hhmm

DAY = date(2026, 5, 21)
KEY = ("ZEYNEP", "DENEME")


def punch(entry, exit_, source="macunkoy", tag=None, row=1, key=KEY, day=DAY):
    def stamp(value):
        return datetime.combine(day, datetime.strptime(value, "%H:%M").time()) \
            if value else None
    return PunchRecord(
        source=source, source_row=row, raw_name="ZEYNEP DENEME", key=key,
        date=day, entry=stamp(entry), exit=stamp(exit_), tag=tag,
    )


def test_dual_site_day_counts_overlap_once(settings):
    """The verified real case from docs/DATA-SOURCES.md."""
    workdays, _, count, total = build_workdays([
        punch("07:09", "19:45", source="teknopark"),
        punch("13:20", "14:05", source="macunkoy"),
    ], settings)

    assert len(workdays) == 1
    assert hhmm(workdays[0].gross) == "12:36"
    assert count == 1
    assert total == workdays[0].gross


def test_orphan_inside_a_known_interval_is_discarded(settings):
    """A site visit badge inside the working day adds nothing and is not an error."""
    workdays, anomalies, _, _ = build_workdays([
        punch("07:09", "19:45", source="teknopark"),
        punch("13:20", None, source="macunkoy", row=42),
    ], settings)

    assert hhmm(workdays[0].gross) == "12:36"
    assert "çapraz-eşleşti" in workdays[0].tags
    assert not [a for a in anomalies
                if a.kind in (AnomalyKind.MISSING_ENTRY, AnomalyKind.MISSING_EXIT)]


def test_orphan_entry_before_the_day_extends_it(settings):
    """Repair uses a timestamp a terminal really recorded — never an invented one."""
    workdays, anomalies, _, _ = build_workdays([
        punch("08:00", "16:30", source="teknopark"),
        punch("07:00", None, source="macunkoy", row=7),
    ], settings)

    assert hhmm(workdays[0].gross) == "9:30"
    assert any(a.kind is AnomalyKind.CROSS_SITE_EXTENDED for a in anomalies)


def test_orphan_exit_after_the_day_extends_it(settings):
    workdays, anomalies, _, _ = build_workdays([
        punch("08:00", "16:30", source="teknopark"),
        punch(None, "18:00", source="macunkoy", row=8),
    ], settings)

    assert hhmm(workdays[0].gross) == "10:00"
    assert any(a.kind is AnomalyKind.CROSS_SITE_EXTENDED for a in anomalies)


def test_unrepairable_orphan_contributes_zero(settings):
    """ADR-003: no default time is ever substituted."""
    workdays, anomalies, _, _ = build_workdays(
        [punch("08:00", None, source="macunkoy", row=9)], settings)

    assert workdays == []
    kinds = [a.kind for a in anomalies]
    assert kinds == [AnomalyKind.MISSING_EXIT]


def test_missing_entry_is_named_correctly(settings):
    _, anomalies, _, _ = build_workdays(
        [punch(None, "17:00", source="macunkoy", row=10)], settings)
    assert [a.kind for a in anomalies] == [AnomalyKind.MISSING_ENTRY]


def test_split_day_from_one_source_is_not_a_duplicate(settings):
    """84 Teknopark person-days legitimately have two rows."""
    workdays, _, count, _ = build_workdays([
        punch("08:21", "13:48", source="teknopark", row=1),
        punch("14:30", "18:00", source="teknopark", row=2),
    ], settings)

    assert len(workdays) == 1
    assert len(workdays[0].intervals) == 2
    assert hhmm(workdays[0].gross) == "8:57"
    assert count == 2


def test_remote_work_interval_is_tagged(settings):
    workdays, _, _, _ = build_workdays(
        [punch("07:30", "16:30", source="izin", tag="uzaktan")], settings)

    assert "uzaktan" in workdays[0].tags
    assert hhmm(workdays[0].gross) == "9:00"


def test_remote_overlapping_a_badge_day_is_counted_once_and_flagged(settings):
    workdays, anomalies, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("08:00", "17:00", source="teknopark", row=6),
    ], settings)

    assert hhmm(workdays[0].gross) == "9:30", "07:30-17:00, not 18:00 worth"
    assert any(a.kind is AnomalyKind.REMOTE_OVERLAP for a in anomalies)
    assert "uzaktan-çakışma" in workdays[0].tags


def test_separate_days_stay_separate(settings):
    workdays, _, _, _ = build_workdays([
        punch("08:00", "17:00", day=date(2026, 5, 21)),
        punch("08:00", "17:00", day=date(2026, 5, 22)),
    ], settings)
    assert len(workdays) == 2


def test_separate_people_stay_separate(settings):
    workdays, _, _, _ = build_workdays([
        punch("08:00", "17:00", key=("ZEYNEP", "DENEME")),
        punch("08:00", "17:00", key=("VELI", "ORNEK")),
    ], settings)
    assert len(workdays) == 2


def test_reconciliation_invariant(settings):
    """Σ per-person gross == Σ accepted interval durations. docs/DOMAIN-RULES.md §6."""
    records = [
        punch("07:09", "19:45", source="teknopark", key=("A", "A")),
        punch("13:20", "14:05", source="macunkoy", key=("A", "A")),
        punch("08:21", "13:48", source="teknopark", key=("B", "B"), row=3),
        punch("14:30", "18:00", source="teknopark", key=("B", "B"), row=4),
        punch("23:00", "02:00", source="macunkoy", key=("C", "C"), row=5),
        punch("08:00", None, source="macunkoy", key=("D", "D"), row=6),
    ]
    workdays, _, _, accepted_total = build_workdays(records, settings)

    summed = timedelta()
    for workday in workdays:
        summed += workday.gross
    assert summed == accepted_total


def test_net_never_goes_negative(settings):
    workdays, _, _, _ = build_workdays(
        [punch("11:00", "17:30", source="teknopark")], settings)
    assert workdays[0].net >= timedelta()
