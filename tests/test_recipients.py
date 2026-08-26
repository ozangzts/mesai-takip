"""Who ends up in the list — the rule, without a window.

This is the whole reason `mail/recipients.py` exists outside `gui/`. "Everyone missing
an exit punch, except these two" is a business rule; a rule that can only be exercised
by clicking is a rule nobody checks.
"""

from datetime import datetime

import pytest

from mesai.mail import recipients
from mesai.snapshot import Person, Snapshot


def person(name, *, problems=(), expected=(), email="a@b.c", minutes=480):
    return Person(
        name=name, email=email, personnel_no=None, department=None, facility=None,
        in_roster=True, has_attendance=True, worked_days=20, minutes=minutes,
        remote_days=0.0, leave_days=0.0,
        problems=tuple(problems), expected=tuple(expected), notes=(),
    )


@pytest.fixture
def snap():
    return Snapshot(
        period="2026-05",
        generated_at=datetime(2026, 8, 19, 10, 0),
        rules={},
        coverage={"macunkoy": {"partial": False}},
        people=(
            person("ÇAĞLA DENEME", problems=("Çıkış yok",)),
            person("AHMET SINAMA", problems=("Çıkış yok", "Günlük süre çok kısa (<2 saat)")),
            person("ZEYNEP ÖRNEK", expected=("Uzaktan + sistem kaydı",)),
            person("BERK NUMUNE", email=None, problems=("Kart bilgisi yok",)),
            person("SEDA TASLAK"),
        ),
    )


# --- the filter list --------------------------------------------------------

def test_the_filter_list_is_built_from_the_data_not_hard_coded(snap):
    """A note added to anomalies.py must appear here without this module changing."""
    keys = [c.key for c in recipients.choices(snap)]

    assert keys[:3] == [recipients.ALL, recipients.NO_PROBLEM,
                        recipients.PROBLEM]
    assert "Çıkış yok" in keys
    assert "Uzaktan + sistem kaydı" in keys


def test_the_two_standing_filters_come_first(snap):
    """Everyone, then the clean ones. Both are answers to "who", not notes."""
    entries = recipients.choices(snap)
    assert [c.key for c in entries[:3]] == [recipients.ALL, recipients.NO_PROBLEM,
                                           recipients.PROBLEM]
    assert all(c.key not in recipients.STANDING for c in entries[3:])


def test_each_entry_carries_its_own_count(snap):
    counts = {c.key: c.count for c in recipients.choices(snap)}

    assert counts[recipients.ALL] == 5
    assert counts[recipients.NO_PROBLEM] == 2, "ZEYNEP has only expected, SEDA nothing"
    assert counts["Çıkış yok"] == 2


def test_no_snapshot_offers_no_filters():
    assert recipients.choices(None) == ()
    assert recipients.matching(None, recipients.ALL) == ()


# --- what a filter admits ---------------------------------------------------

def test_expected_behaviour_is_filterable_without_counting_as_a_problem(snap):
    """ADR-028: it must be reachable, and it must not make somebody look defective."""
    assert [p.name for p in recipients.matching(snap, "Uzaktan + sistem kaydı")] == \
        ["ZEYNEP ÖRNEK"]
    assert "ZEYNEP ÖRNEK" in [
        p.name for p in recipients.matching(snap, recipients.NO_PROBLEM)]


def test_the_clean_filter_is_people_with_no_problem_at_all(snap):
    names = {p.name for p in recipients.matching(snap, recipients.NO_PROBLEM)}
    assert names == {"ZEYNEP ÖRNEK", "SEDA TASLAK"}


def test_people_come_back_in_reading_order(snap):
    """Turkish collation, not codepoint order — Ç sorts after C, not after Z."""
    names = [p.name for p in recipients.matching(snap, recipients.ALL)]
    assert names == sorted(names, key=lambda n: recipients.sort_key(n))
    assert names[0] == "AHMET SINAMA"


# --- removing individuals ---------------------------------------------------

def test_removing_someone_takes_them_out_of_the_selection(snap):
    chosen = recipients.selected(snap, "Çıkış yok", {"AHMET SINAMA"})
    assert [p.name for p in chosen] == ["ÇAĞLA DENEME"]


def test_removal_is_by_name_so_re_filtering_cannot_shift_it(snap):
    """The list re-sorts under the user; a remembered index would mean somebody else."""
    excluded = {"ÇAĞLA DENEME"}
    for key in (recipients.ALL, "Çıkış yok"):
        assert "ÇAĞLA DENEME" not in [
            p.name for p in recipients.selected(snap, key, excluded)]


def test_removing_a_name_that_is_not_in_this_filter_changes_nothing(snap):
    before = recipients.selected(snap, "Çıkış yok", set())
    after = recipients.selected(snap, "Çıkış yok", {"SEDA TASLAK"})
    assert before == after


# --- people who cannot be written to ----------------------------------------

def test_people_without_an_address_are_reported_not_dropped(snap):
    """Silently removing them would make a list of 5 quietly become 4."""
    chosen = recipients.selected(snap, recipients.ALL, set())
    assert len(chosen) == 5
    assert [p.name for p in recipients.without_email(chosen)] == ["BERK NUMUNE"]


# --- the order the filter list is read in (ADR-029) -------------------------

def test_related_notes_are_neighbours(snap):
    """Frequency ordering split the punch pair: "Giriş yok" landed four rows below
    "Çıkış yok" simply because fewer people had it — and those two are exactly each
    other's neighbour when somebody is choosing between them."""
    from mesai.anomalies import DESCRIPTIONS, GROUPS

    family = {label: group for label, _s, _e, group in DESCRIPTIONS.values()}
    notes = [c.label for c in recipients.choices(snap)
             if c.key not in recipients.STANDING]
    groups = [family[label] for label in notes]

    assert groups == sorted(groups, key=GROUPS.index), "families must not interleave"


def test_the_order_does_not_depend_on_how_many_people_have_each_note(snap):
    """A dropdown that reshuffles every month makes somebody re-find what they knew."""
    busy = Snapshot(
        period=snap.period, generated_at=snap.generated_at, rules={},
        coverage=snap.coverage,
        # "Günlük süre çok kısa (<2 saat)" now dwarfs "Çıkış yok"; the order must not move.
        people=snap.people + tuple(
            person(f"EK {n} DENEME", problems=("Günlük süre çok kısa (<2 saat)",)) for n in range(20)),
    )
    order = [c.label for c in recipients.choices(snap)]
    busier = [c.label for c in recipients.choices(busy)]

    assert [l for l in order if l in busier] == [l for l in busier if l in order]


def test_expected_behaviour_says_so_in_the_list(snap):
    """Grouping by family mixes them in with real problems, so each one is marked."""
    entries = {c.label: c.display for c in recipients.choices(snap)}

    assert "beklenen durum" in entries["Uzaktan + sistem kaydı"]
    assert "beklenen durum" not in entries["Çıkış yok"]


# --- appearing in more than one filter --------------------------------------

def test_someone_with_two_notes_appears_under_both(snap):
    """Measured on June 2026: 62 of 163 people carry more than one note. Being in one
    filter must never take somebody out of another."""
    for label in ("Çıkış yok", "Günlük süre çok kısa (<2 saat)"):
        assert "AHMET SINAMA" in [p.name for p in recipients.matching(snap, label)]


# --- how many days, not how many notes -------------------------------------

def test_the_day_count_is_what_the_person_row_shows(snap):
    """The people screen prints `Gün` per person, and it has to be the number of rows
    the day panel beside it will show — one number for one person, not four (ADR-066).

    It used to print `+2`, a count of the person's OTHER notes, which answered "how many
    filters is this person in". Nobody asks that, and it was the fourth number the screen
    carried for the same person.
    """
    for person in snap.people:
        gun = len(recipients.days_for(person, recipients.default_labels(snap)))
        assert gun == len([d for d in person.days
                           if not d.explained
                           and recipients.default_labels(snap)
                           .intersection(d.problems)])


def test_the_problem_count_is_the_month_and_not_the_ticks(snap):
    """`Sorunu olanlar` counts everybody with something outstanding, always.

    It used to follow the tick panel, so unticking everything but one note made the
    entry read `Sorunu olanlar (15)` — a number describing a state you have to already
    be inside this filter to reach. It also broke the partition: `Sorunu olmayanlar`
    never followed the ticks, so the two stopped adding up to the month.
    """
    counts = set()
    for labels in ([], ["Çıkış yok"], None):
        entry = next(c for c in recipients.choices(snap, labels)
                     if c.key == recipients.PROBLEM)
        counts.add(entry.count)
    assert len(counts) == 1, f"the count moved with the ticks: {counts}"


def test_the_two_standing_filters_partition_the_month(snap):
    """Every person is in exactly one of them, whatever is ticked."""
    for labels in ([], ["Çıkış yok"], None):
        entries = {c.key: c.count for c in recipients.choices(snap, labels)}
        assert entries[recipients.PROBLEM] + entries[recipients.NO_PROBLEM] ==             entries[recipients.ALL]


def test_the_notes_offered_for_ticking_carry_their_group_and_counts(snap):
    """Fifteen checkboxes read as a wall unless they are grouped.

    The grouping is `Günü sayılmayan` / `Günü sayılan` (ADR-056), not the note's kind:
    the question somebody scanning that panel asks is which of these cost hours.
    """
    offered = recipients.problem_labels(snap)

    assert offered, "a month with problems must offer something to tick"
    assert {g for g, _l, _c in offered} <= {recipients.LOST, recipients.KEPT}
    for _group, label, count in offered:
        assert count == len(recipients.matching(snap, label)), label
    assert all(label != "Uzaktan + sistem kaydı"
               for _g, label, _c in offered), "expected behaviour is not offered"


def test_a_note_is_grouped_by_whether_its_days_cost_anybody_hours():
    """June: `Çıkış yok` lost 126 days; `Hem giriş hem çıkış yok` lost ONE of 80.

    The alarming-sounding label is the harmless one, and the panel has to say so or it
    invites the wrong priority.
    """
    kayipli = _person_with(_day(3), _day(9))                       # minutes None
    sayilan = Person(**{**person("ESRA DENEME",
                                problems=("Tesis birleştirme",)).__dict__,
                        "days": (_day(4, minutes=523,
                                      problems=("Tesis birleştirme",)),)})
    snap = Snapshot(period="2026-06", generated_at=datetime(2026, 8, 25, 10, 0),
                    rules={}, coverage={}, people=(kayipli, sayilan))

    by_label = {l: (g, c) for g, l, c in recipients.problem_labels(snap)}
    assert by_label["Çıkış yok"] == (recipients.LOST, 1)
    # Still in KEPT — the heading is about cost and that has not changed. But it now
    # SELECTS its person: a note that counts 1 and filters to 0 read as a bug, and was
    # one (`counted_only_labels`). The heading answers "which of these cost hours"; the
    # count answers "who can I ask about it", and those are different questions.
    assert by_label["Tesis birleştirme"] == (recipients.KEPT, 1)


def test_a_counted_only_note_selects_its_days():
    """`Gece geçişi  (6)` used to filter to nobody — the operator caught it.

    Every day under such a note was counted, so the `outstanding` rule (ADR-059) removed
    all of them and the list came back empty. A repaired night crossing is still a real
    thing to ask somebody about; it is just not a lost day.
    """
    gun = _day(4, minutes=523, problems=("Gece geçişi",))
    kisi = Person(**{**person("ESRA DENEME", problems=("Gece geçişi",)).__dict__,
                     "days": (gun,)})
    snap = Snapshot(period="2026-06", generated_at=datetime(2026, 8, 25, 10, 0),
                    rules={}, coverage={}, people=(kisi,))

    assert recipients.counted_only_labels(snap) == frozenset({"Gece geçişi"})
    assert [p.name for p in recipients.matching(snap, "Gece geçişi")] == ["ESRA DENEME"]
    assert recipients.days_for(kisi, {"Gece geçişi"}, snapshot=snap) == (gun,)


def test_a_note_that_can_lose_time_keeps_the_outstanding_rule():
    """The other half: `Çıkış yok` must NOT start returning days it never returned.

    Otherwise the fix above quietly reverses ADR-059 for every note, and a day the
    other site's record closed in full comes back into the mail list.
    """
    kapanmis = _day(4, minutes=523, problems=("Çıkış yok",))       # counted
    kayip = _day(5, problems=("Çıkış yok",))                       # minutes None
    kisi = Person(**{**person("ESRA DENEME", problems=("Çıkış yok",)).__dict__,
                     "days": (kapanmis, kayip)})
    snap = Snapshot(period="2026-06", generated_at=datetime(2026, 8, 25, 10, 0),
                    rules={}, coverage={}, people=(kisi,))

    assert "Çıkış yok" not in recipients.counted_only_labels(snap)
    assert recipients.days_for(kisi, {"Çıkış yok"}, snapshot=snap) == (kayip,)


def test_a_month_level_note_with_no_days_is_not_filed_as_counted():
    """`Kart bilgisi yok` has nothing to measure. A month nobody can account for is
    not the thing to put under "counted"."""
    kisi = person("KEREM DENEME", problems=("Kart bilgisi yok",))
    snap = Snapshot(period="2026-06", generated_at=datetime(2026, 8, 25, 10, 0),
                    rules={}, coverage={}, people=(kisi,))

    assert recipients.problem_labels(snap) == (
        (recipients.LOST, "Kart bilgisi yok", 1),)


def test_removals_still_apply_to_the_problem_group(snap):
    people = recipients.selected(snap, recipients.PROBLEM, {"AHMET SINAMA"},
                                 ["Çıkış yok"])
    assert [p.name for p in people] == ["ÇAĞLA DENEME"]


def test_nothing_is_offered_or_admitted_without_a_snapshot():
    assert recipients.problem_labels(None) == ()
    assert recipients.default_labels(None) == frozenset()
    assert recipients.matching(None, recipients.PROBLEM) == ()


# --- one note that is a stricter case of two others (ADR-053) ----------------
#
# `Hem giriş hem çıkış yok` is a day with no entry AND no exit, so it is also a day
# entry. The labels read as predicates, and a filter on `Giriş yok` that skipped those
# days was the reading nobody expects: "teknik olarak o gün de giriş yok".

def _both_missing():
    return Snapshot(
        period="2026-06", generated_at=datetime(2026, 8, 24, 10, 0), rules={},
        coverage={"macunkoy": {"partial": False}},
        people=(
            # only the both-missing note: the person the old behaviour lost
            person("KEREM DENEME", problems=("Hem giriş hem çıkış yok",)),
            person("ÇAĞLA DENEME", problems=("Çıkış yok",)),
            person("AHMET SINAMA", problems=("Giriş yok",)),
        ),
    )


def test_each_punch_note_brings_only_its_own_people():
    """The three notes are three separate questions — what time did you leave, what time
    did you arrive, were you here at all — and the third is not a case of the other two.

    They were linked for two days (ADR-053) and the link is gone (ADR-065). Asserted in
    both directions, because a half-removed relation would still pass one of them.
    """
    snap = _both_missing()

    assert {p.name for p in recipients.matching(snap, "Hem giriş hem çıkış yok")} == {
        "KEREM DENEME"}
    assert {p.name for p in recipients.matching(snap, "Giriş yok")} == {"AHMET SINAMA"}
    assert {p.name for p in recipients.matching(snap, "Çıkış yok")} == {"ÇAĞLA DENEME"}


def test_the_count_beside_a_note_is_the_number_of_rows_it_shows():
    """The bug this guards: the window offering `Giriş yok (48)` and handing back 15.

    `label_counts` and `matching` apply the same relation, so they cannot drift. Checked
    for every note in the list rather than the interesting one, because the next
    implication added will be the one nobody re-checked.
    """
    snap = _both_missing()

    for choice in recipients.choices(snap):
        if choice.key in recipients.STANDING:
            continue
        assert choice.count == len(recipients.matching(snap, choice.key)), choice.key


def test_the_problem_group_admits_only_the_ticked_notes_own_people():
    """Ticking `Giriş yok` reaches the people who have it and nobody else (ADR-065)."""
    snap = _both_missing()

    chosen = {p.name for p in recipients.matching(snap, recipients.PROBLEM,
                                                  labels={"Giriş yok"})}
    assert chosen == {"AHMET SINAMA"}

    # unticking everything empties the group rather than falling back to a default
    assert recipients.matching(snap, recipients.PROBLEM, labels=set()) == ()


# --- which days the message may speak about ---------------------------------

def _with_days(*days):
    from mesai.snapshot import ProblemDay
    p = person("KEREM DENEME", problems=tuple(
        {label for day in days for label in day.problems}))
    return Person(**{**p.__dict__, "days": tuple(days)})


def test_the_ticked_notes_choose_the_days_as_well_as_the_person():
    """ADR-051's rule, now in a function instead of only in a test."""
    from datetime import date

    from mesai.snapshot import ProblemDay
    bos = ProblemDay(date=date(2026, 6, 3), problems=("Hem giriş hem çıkış yok",))
    cikis = ProblemDay(date=date(2026, 6, 9), problems=("Çıkış yok",),
                       entry="07:41", minutes=0)
    kisa = ProblemDay(date=date(2026, 6, 11),
                      problems=("Günlük süre çok kısa (<2 saat)",), minutes=105)
    kisi = _with_days(bos, cikis, kisa)

    # each note brings its own day and no other (ADR-065)
    assert recipients.days_for(kisi, {"Giriş yok"}) == ()
    assert [d.date for d in recipients.days_for(kisi, {"Çıkış yok"})] == [cikis.date]
    assert [d.date for d in
            recipients.days_for(kisi, {"Hem giriş hem çıkış yok"})] == [bos.date]
    assert recipients.days_for(kisi, set()) == ()
    # no labels given: every day that cost something. `kisa` counted 1:45 and drops out
    # — a short day that was still paid is not a day anybody has to answer for.
    assert [d.date.day for d in recipients.days_for(kisi)] == [3, 9]


def test_the_report_is_not_inclusive_the_way_the_filter_is(tmp_path, settings):
    """A day with neither punch is ONE row, labelled for what happened.

    The relation is a selection rule, not a reporting one. Expanding it into the sheets
    would triple the row and state two things the record does not say: that an entry was
    read and that an exit was read.
    """
    import openpyxl

    from mesai.anomalies import Anomaly, AnomalyKind, Collector

    from datetime import date
    from mesai.report import workbook
    from tests.test_report import KEY, _employee, _summary, _workday

    collector = Collector()
    collector.add(Anomaly(
        kind=AnomalyKind.EMPTY_RECORD, source="macunkoy", source_row=7, key=KEY,
        raw_name="AYŞE DENEME", date=date(2026, 5, 4), detail="giriş de çıkış da boş"))

    path = tmp_path / "rapor.xlsx"
    workbook.build(
        path=path, period="2026-05", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=collector,
        stats=_stats_for_report(), settings=settings,
        generated_at=datetime(2026, 8, 24, 12, 0))

    rows = list(openpyxl.load_workbook(path, read_only=True)["İnceleme Listesi"]
                .iter_rows(values_only=True))
    notlar = [r[4] for r in rows[4:] if r and r[4]]

    assert notlar == ["Hem giriş hem çıkış yok"]
    assert "Giriş yok" not in notlar and "Çıkış yok" not in notlar


def _stats_for_report():
    from datetime import date, timedelta

    from mesai.models import RunStats
    return RunStats(
        rows_read={"macunkoy": 1}, records_built={"macunkoy": 1},
        intervals_accepted=0, union_total=timedelta(), accepted_total=timedelta(),
        files={"macunkoy": "test.xlsx"}, roster_date=date(2026, 7, 28))


# --- days where nothing was actually lost (ADR-055) --------------------------

def _day(day, *, minutes=None, covered_by="", problems=("Çıkış yok",)):
    from datetime import date

    from mesai.snapshot import ProblemDay
    return ProblemDay(date=date(2026, 6, day), problems=tuple(problems),
                      entry="07:41", minutes=minutes, covered_by=covered_by)


def _person_with(*days):
    p = person("KEREM DENEME", problems=("Çıkış yok",))
    return Person(**{**p.__dict__, "days": tuple(days)})


def test_a_day_that_still_counted_is_not_a_day_anybody_lost():
    """The Macunköy visit: broken row there, full day recorded at Teknopark.

    Measured on June 2026 this is 99 of the 99 counted days — every one of them. The
    person lost nothing and has nothing to answer for.
    """
    kisi = _person_with(_day(3, minutes=523), _day(9))

    assert [d.date.day for d in recipients.days_for(kisi, {"Çıkış yok"})] == [9],         "the day counted from another record is not a problem and never was"


def test_a_day_covered_by_leave_is_not_asked_about():
    """Seven days over three months. Asking somebody where they were while on annual
    leave is the message that discredits every other message in the batch."""
    kisi = _person_with(_day(3, covered_by="Yıllık İzin"), _day(9))

    assert [d.date.day for d in
            recipients.days_for(kisi, {"Çıkış yok"})] == [9]
    assert _day(3, covered_by="Yıllık İzin").explained
    assert not _day(9).explained


def test_remote_work_needs_no_special_case():
    """A declared remote day becomes intervals like any record, so it has minutes."""
    assert _day(3, minutes=540).explained


def test_somebody_whose_every_day_was_explained_drops_out_of_the_list():
    """Filtering days is not enough: they would be written to with an empty list.

    24 / 40 / 27 people over May-July 2026 are exactly this — every one of their days
    counted somewhere else.
    """
    temiz = _person_with(_day(3, minutes=523), _day(9, covered_by="Mazeret"))
    kayipli = _person_with(_day(3, minutes=523), _day(9))

    assert recipients.outstanding(temiz, {"Çıkış yok"}) == frozenset()
    assert recipients.outstanding(kayipli, {"Çıkış yok"}) == {"Çıkış yok"}
    assert recipients.days_for(temiz, {"Çıkış yok"}) == ()


def test_days_by_cost_splits_every_problem_day_and_ignores_the_ticks():
    """The panel's and the column's source, and it takes no label set at all.

    That is the fix: `days_for` answers "which days are the ticked notes about", and it
    was driving a column that is supposed to say "how many of this person's days were
    not counted". The second question has no ticks in it.
    """
    sayilan = _day(4, minutes=523)
    izinli = _day(5, covered_by="Yıllık İzin")
    kayip = _day(6)
    kisi = Person(**{**person("ESRA DENEME", problems=("Çıkış yok",)).__dict__,
                     "days": (sayilan, izinli, kayip)})

    lost, kept = recipients.days_by_cost(kisi)
    assert lost == (kayip,)
    assert kept == (sayilan, izinli)
    # every problem day is in exactly one half
    assert len(lost) + len(kept) == len(kisi.days)


def test_days_by_cost_counts_a_leave_covered_day_as_no_loss():
    """Nothing went missing on a day annual leave covers, so nobody is asked about it.

    It is in `kept` rather than `lost` even though no minutes were counted — the window
    heading says "sayılan ya da izinli" rather than calling it counted.
    """
    izinli = _day(5, covered_by="Doğum İzni (Tam Ödeme)")
    kisi = Person(**{**person("ESRA DENEME", problems=("Çıkış yok",)).__dict__,
                     "days": (izinli,)})

    assert recipients.days_by_cost(kisi) == ((), (izinli,))
