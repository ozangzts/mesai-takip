"""Cross-site reconciliation — where the bugs live.

76 employees appear in both attendance exports; getting this wrong either
double-counts or discards real hours.

`build_workdays` returns two totals and they are not the same thing: `union_total` is
presence (summed intervals), `measured_total` is what the report pays. Under ADR-015
the second includes the gaps inside each day. Tests assert on both, because a change
that quietly collapses them would erase the audit trail on the Kontrol sheet.
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
    workdays, _, count, union, measured = build_workdays([
        punch("07:09", "19:45", source="teknopark"),
        punch("13:20", "14:05", source="macunkoy"),
    ], settings)

    assert len(workdays) == 1
    assert hhmm(workdays[0].gross) == "12:36"
    assert count == 1
    assert union == measured == workdays[0].gross


def test_orphan_inside_a_known_interval_is_discarded(settings):
    """A site visit badge inside the working day adds nothing and is not an error."""
    workdays, anomalies, _, _, _ = build_workdays([
        punch("07:09", "19:45", source="teknopark"),
        punch("13:20", None, source="macunkoy", row=42),
    ], settings)

    assert hhmm(workdays[0].gross) == "12:36"
    assert "çapraz-eşleşti" in workdays[0].tags
    assert not [a for a in anomalies
                if a.kind in (AnomalyKind.MISSING_ENTRY, AnomalyKind.MISSING_EXIT)]


def test_orphan_entry_before_the_day_extends_it(settings):
    """Repair uses a timestamp a terminal really recorded — never an invented one."""
    workdays, anomalies, _, _, _ = build_workdays([
        punch("08:00", "16:30", source="teknopark"),
        punch("07:00", None, source="macunkoy", row=7),
    ], settings)

    assert hhmm(workdays[0].gross) == "9:30"
    assert any(a.kind is AnomalyKind.CROSS_SITE_EXTENDED for a in anomalies)


def test_orphan_exit_after_the_day_extends_it(settings):
    workdays, anomalies, _, _, _ = build_workdays([
        punch("08:00", "16:30", source="teknopark"),
        punch(None, "18:00", source="macunkoy", row=8),
    ], settings)

    assert hhmm(workdays[0].gross) == "10:00"
    assert any(a.kind is AnomalyKind.CROSS_SITE_EXTENDED for a in anomalies)


def test_unrepairable_orphan_contributes_zero(settings):
    """ADR-003: no default time is ever substituted."""
    workdays, anomalies, _, _, _ = build_workdays(
        [punch("08:00", None, source="macunkoy", row=9)], settings)

    assert workdays == []
    kinds = [a.kind for a in anomalies]
    assert kinds == [AnomalyKind.MISSING_EXIT]


def test_missing_entry_is_named_correctly(settings):
    _, anomalies, _, _, _ = build_workdays(
        [punch(None, "17:00", source="macunkoy", row=10)], settings)
    assert [a.kind for a in anomalies] == [AnomalyKind.MISSING_ENTRY]


def test_split_day_is_paid_through_the_gap(settings):
    """84 Teknopark person-days legitimately have two rows.

    ADR-015: the day is 08:21 -> 18:00, so the 42-minute gap is paid. Presence is
    still 8:57 and both figures are reported separately.
    """
    workdays, _, count, union, measured = build_workdays([
        punch("08:21", "13:48", source="teknopark", row=1),
        punch("14:30", "18:00", source="teknopark", row=2),
    ], settings)

    assert len(workdays) == 1
    assert len(workdays[0].intervals) == 2
    assert hhmm(workdays[0].gross) == "9:39"
    assert hhmm(workdays[0].gap_total) == "0:42"
    assert hhmm(workdays[0].interval_total) == "8:57"
    assert count == 2
    assert hhmm(union) == "8:57"
    assert hhmm(measured) == "9:39"


def test_split_day_under_the_old_rule(settings_break):
    """The pre-ADR-016 config must still produce the numbers HR signed off before."""
    workdays, _, _, union, measured = build_workdays([
        punch("08:21", "13:48", source="teknopark", row=1),
        punch("14:30", "18:00", source="teknopark", row=2),
    ], settings_break)

    assert hhmm(workdays[0].gross) == "8:57"
    assert workdays[0].break_deduction == timedelta(minutes=3)
    assert hhmm(workdays[0].net) == "8:54"
    assert union == measured, "under `union` the gaps must not be paid"


def test_no_break_is_deducted_by_default(settings):
    """The whole point of ADR-016: the badged day is the payroll figure."""
    workdays, _, _, _, _ = build_workdays(
        [punch("07:30", "16:30", source="teknopark")], settings)

    assert hhmm(workdays[0].gross) == "9:00", "not 8:15"
    assert workdays[0].break_deduction == timedelta()
    assert workdays[0].net == workdays[0].gross


def test_remote_work_interval_is_tagged(settings):
    workdays, _, _, _, _ = build_workdays(
        [punch("07:30", "16:30", source="izin", tag="uzaktan")], settings)

    assert "uzaktan" in workdays[0].tags
    assert hhmm(workdays[0].gross) == "9:00"


def test_remote_overlapping_a_real_punch_is_counted_once_and_flagged(settings):
    """A genuine punch on a declared remote day — the rare case worth asking about."""
    workdays, anomalies, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("08:00", "17:00", source="teknopark", row=6),
    ], settings)

    assert hhmm(workdays[0].gross) == "9:30", "07:30-17:00, not 18:00 worth"
    note = next(a for a in anomalies
                if a.kind is AnomalyKind.REMOTE_OVERLAP_REAL)
    assert note.severity == "included", "a real punch is a question, not just info"
    assert "uzaktan-çakışma" in workdays[0].tags


def test_nominal_placeholder_gives_way_to_the_remote_hours(settings):
    """ADR-018: on a remote day the declaration wins over a placeholder.

    The placeholder would otherwise stretch the day to 10:30 (07:30 -> 18:00) on the
    strength of a row nobody badged.
    """
    workdays, anomalies, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="teknopark", row=6),
    ], settings)

    assert hhmm(workdays[0].gross) == "9:00", "the declared hours, not 10:30"
    assert workdays[0].sources == frozenset({"izin", "uzaktan"})
    note = next(a for a in anomalies
                if a.kind is AnomalyKind.REMOTE_REPLACED_NOMINAL)
    assert note.severity == "info" and not note.is_problem
    assert "uzaktan-çakışma" not in workdays[0].tags
    assert "uzaktan" in workdays[0].tags


def test_a_real_punch_survives_a_remote_declaration(settings):
    """ADR-018: a turnstile reading is evidence and must not be discarded.

    The real 2026-06-23 shape: declaration ends 13:45, the person badges out at 18:34.
    Paying only the declaration would lose 4 h 49 of recorded work.
    """
    workdays, anomalies, _, _, _ = build_workdays([
        punch("07:30", "13:45", source="izin", tag="uzaktan", row=5),
        punch("07:30", "13:00", source="teknopark", row=6),
        punch("13:41", "18:34", source="teknopark", row=7),
    ], settings)

    assert hhmm(workdays[0].gross) == "11:04", "07:30-18:34, nothing discarded"
    assert not [a for a in anomalies
                if a.kind is AnomalyKind.REMOTE_REPLACED_NOMINAL]
    assert any(a.kind is AnomalyKind.REMOTE_OVERLAP_REAL for a in anomalies)


def test_one_real_punch_protects_the_whole_day(settings):
    """A placeholder AND a real punch — the day keeps both, because evidence exists."""
    workdays, _, _, _, _ = build_workdays([
        punch("10:00", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="teknopark", row=6),   # placeholder
        punch("07:36", "10:14", source="macunkoy", row=7),    # real
    ], settings)

    assert hhmm(workdays[0].gross) == "10:24", "07:36-18:00"


def test_remote_precedence_can_be_switched_off(settings):
    """`never` must reproduce the pre-ADR-018 figure exactly."""
    from dataclasses import replace
    old = replace(settings, remote_replaces="never")
    workdays, _, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="teknopark", row=6),
    ], old)

    assert hhmm(workdays[0].gross) == "10:30"


def test_remote_precedence_always_ignores_real_punches(settings):
    """`always` is HR's instruction read literally — and it does lose real hours."""
    from dataclasses import replace
    strict = replace(settings, remote_replaces="always")
    workdays, _, _, _, _ = build_workdays([
        punch("07:30", "13:45", source="izin", tag="uzaktan", row=5),
        punch("13:41", "18:34", source="teknopark", row=7),
    ], strict)

    assert hhmm(workdays[0].gross) == "6:15", "18:34 punch discarded by design"


def test_nominal_pattern_only_applies_to_its_own_source(settings):
    """09:00-18:00 from Macunköy is a real punch — the pattern is Teknopark's."""
    _, anomalies, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="macunkoy", row=6),
    ], settings)

    assert any(a.kind is AnomalyKind.REMOTE_OVERLAP_REAL for a in anomalies)


def test_without_a_nominal_pattern_every_overlap_is_a_question(settings):
    """No config entry must mean over-asking, never silently calling it expected."""
    from dataclasses import replace
    bare = replace(settings, nominal_day=None)
    _, anomalies, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="teknopark", row=6),
    ], bare)

    assert any(a.kind is AnomalyKind.REMOTE_OVERLAP_REAL for a in anomalies)


def test_info_anomalies_do_not_count_as_problems(settings):
    """An expected-behaviour row must not inflate anyone's Şüpheli Kayıt figure."""
    from mesai.anomalies import Collector
    _, anomalies, _, _, _ = build_workdays([
        punch("07:30", "16:30", source="izin", tag="uzaktan", row=5),
        punch("09:00", "18:00", source="teknopark", row=6),
    ], settings)

    collector = Collector()
    collector.extend(anomalies)
    assert collector.count_by_key().get(KEY, 0) == 0


def test_separate_days_stay_separate(settings):
    workdays, _, _, _, _ = build_workdays([
        punch("08:00", "17:00", day=date(2026, 5, 21)),
        punch("08:00", "17:00", day=date(2026, 5, 22)),
    ], settings)
    assert len(workdays) == 2


def test_separate_people_stay_separate(settings):
    workdays, _, _, _, _ = build_workdays([
        punch("08:00", "17:00", key=("ZEYNEP", "DENEME")),
        punch("08:00", "17:00", key=("VELI", "ORNEK")),
    ], settings)
    assert len(workdays) == 2


def _invariant_records():
    return [
        punch("07:09", "19:45", source="teknopark", key=("A", "A")),
        punch("13:20", "14:05", source="macunkoy", key=("A", "A")),
        punch("08:21", "13:48", source="teknopark", key=("B", "B"), row=3),
        punch("14:30", "18:00", source="teknopark", key=("B", "B"), row=4),
        punch("23:00", "02:00", source="macunkoy", key=("C", "C"), row=5),
        punch("08:00", None, source="macunkoy", key=("D", "D"), row=6),
    ]


def test_reconciliation_invariant(settings):
    """Σ per-person == Σ measured person-days. docs/DOMAIN-RULES.md §6.

    This is the guard on the Kontrol sheet. It compares like with like: per-person
    totals against the measured total, not against presence.
    """
    workdays, _, _, _, measured = build_workdays(_invariant_records(), settings)

    summed = timedelta()
    for workday in workdays:
        summed += workday.gross
    assert summed == measured


def test_reconciliation_invariant_holds_under_the_old_rule(settings_break):
    workdays, _, _, union, measured = build_workdays(
        _invariant_records(), settings_break)

    summed = timedelta()
    for workday in workdays:
        summed += workday.gross
    assert summed == measured == union


def test_gap_total_accounts_for_the_difference(settings):
    """measured − union must be exactly the in-day gaps, or the Kontrol sheet lies."""
    workdays, _, _, union, measured = build_workdays(_invariant_records(), settings)

    gaps = timedelta()
    for workday in workdays:
        gaps += workday.gap_total
    assert measured - union == gaps


def test_a_day_under_the_threshold_is_flagged(settings):
    """ADR-019: HR asked for days under 2 hours to be surfaced."""
    workdays, anomalies, _, _, _ = build_workdays(
        [punch("08:00", "09:30", source="teknopark")], settings)

    note = next(a for a in anomalies if a.kind is AnomalyKind.SHORT_DAY)
    assert note.severity == "included", "counted, but HR wants to see it"
    assert "kısa-gün" in workdays[0].tags
    assert hhmm(workdays[0].gross) == "1:30"


def test_a_day_on_the_threshold_is_not_flagged(settings):
    """Exactly 2 hours is not 'under 2 hours'. No cliff-edge ambiguity."""
    _, anomalies, _, _, _ = build_workdays(
        [punch("08:00", "10:00", source="teknopark")], settings)

    assert not [a for a in anomalies if a.kind is AnomalyKind.SHORT_DAY]


def test_short_day_looks_at_the_day_not_the_record(settings):
    """Two short records adding up past the threshold is a normal day, not a flag."""
    _, anomalies, _, _, _ = build_workdays([
        punch("08:00", "09:30", source="teknopark", row=1),
        punch("14:00", "15:00", source="teknopark", row=2),
    ], settings)

    assert not [a for a in anomalies if a.kind is AnomalyKind.SHORT_DAY], \
        "07:00 envelope is well over the threshold"


def test_short_day_threshold_comes_from_config(settings):
    from dataclasses import replace
    strict = replace(settings, plausibility=replace(
        settings.plausibility, short_day=timedelta(hours=4)))
    _, anomalies, _, _, _ = build_workdays(
        [punch("08:00", "11:00", source="teknopark")], strict)

    assert any(a.kind is AnomalyKind.SHORT_DAY for a in anomalies)


def test_net_never_goes_negative(settings):
    workdays, _, _, _, _ = build_workdays(
        [punch("11:00", "17:30", source="teknopark")], settings)
    assert workdays[0].net >= timedelta()


# --- weekends and public holidays are worked time ---------------------------
#
# Asked directly, and worth pinning: is Saturday work counted, or silently zeroed?
# Measured on May 2026 — 30 weekend person-days worth 164:31, and 41 public-holiday
# person-days worth 325:01, all of them inside the reported 17 103:58. The weekday
# calendar exists only to say how much of a month a SOURCE FILE covers and to give the
# "Ay büyük ölçüde boş" note a denominator. It never decides whether hours count.

def test_a_saturday_is_counted_like_any_other_day(settings):
    saturday = date(2026, 5, 23)
    assert saturday.weekday() == 5, "the fixture day must really be a Saturday"

    workdays, _notes, _accepted, _union, total = build_workdays(
        [punch("09:00", "17:30", day=saturday)], settings)

    assert len(workdays) == 1
    assert hhmm(total) == "8:30"


def test_a_public_holiday_is_counted_like_any_other_day(settings):
    # 19.05.2026 — a public holiday in the shipped calendar, and a Tuesday.
    holiday = date(2026, 5, 19)

    workdays, _notes, _accepted, _union, total = build_workdays(
        [punch("08:00", "16:00", day=holiday)], settings)

    assert len(workdays) == 1
    assert hhmm(total) == "8:00"


def test_the_weekday_calendar_does_not_touch_the_hours(settings):
    """Same records, one on a working day and one on a Sunday: identical totals."""
    weekday = build_workdays([punch("09:00", "18:00", day=date(2026, 5, 21))],
                             settings)[4]
    sunday = build_workdays([punch("09:00", "18:00", day=date(2026, 5, 24))],
                            settings)[4]

    assert date(2026, 5, 24).weekday() == 6
    assert weekday == sunday


def test_a_sixteen_hour_day_is_counted_and_flagged(settings):
    """The real 30.06.2026 case: 07:19 -> 23:58. It was being counted as zero."""
    workdays, notes, _accepted, _union, total = build_workdays(
        [punch("07:19", "23:58")], settings)

    assert hhmm(total) == "16:39", "the hours are real and stay"
    assert any(n.kind is AnomalyKind.LONG_DAY for n in notes), "and it is flagged"
    assert "uzun-gün" in workdays[0].tags


def test_a_day_just_under_the_ceiling_says_nothing(settings):
    _workdays, notes, _accepted, _union, total = build_workdays(
        [punch("07:00", "22:30")], settings)

    assert hhmm(total) == "15:30"
    assert not any(n.kind is AnomalyKind.LONG_DAY for n in notes)
