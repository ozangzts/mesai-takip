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
            person("BERK NUMUNE", email=None, problems=("Mesai verisi yok",)),
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


# --- "is there more going on with this person" ------------------------------

def test_the_extra_count_excludes_the_note_being_filtered_on(snap):
    ahmet = next(p for p in snap.people if p.name == "AHMET SINAMA")

    assert recipients.other_problems(ahmet, "Çıkış yok") == 1, "the short day remains"
    assert recipients.other_problems(ahmet, "Günlük süre çok kısa (<2 saat)") == 1
    assert recipients.other_problems(ahmet, recipients.ALL) == 2, "nothing to exclude"


def test_expected_behaviour_does_not_inflate_the_extra_count(snap):
    """It is not a problem. Counting it as one is the mistake ADR-017 exists for."""
    zeynep = next(p for p in snap.people if p.name == "ZEYNEP ÖRNEK")
    assert zeynep.expected
    assert recipients.other_problems(zeynep, recipients.ALL) == 0


def test_someone_with_one_note_shows_nothing_extra(snap):
    cagla = next(p for p in snap.people if p.name == "ÇAĞLA DENEME")
    assert recipients.other_problems(cagla, "Çıkış yok") == 0


# --- the problem group, and which notes count (ADR-048) ---------------------
#
# The workflow this exists for: pick the people whose records need chasing, and later
# mail them. Which notes make somebody one of those people is a decision that will
# change, so it is an argument rather than a constant — and the default is measured
# rather than guessed.

def test_the_problem_group_is_everybody_the_counted_notes_admit(snap):
    """`ÇAĞLA` and `AHMET` have `Çıkış yok`; nobody else does."""
    people = recipients.matching(snap, recipients.PROBLEM, ["Çıkış yok"])

    assert [p.name for p in people] == ["AHMET SINAMA", "ÇAĞLA DENEME"]


def test_a_person_with_two_notes_appears_once(snap):
    """`AHMET` has both, and a union is not a concatenation."""
    people = recipients.matching(
        snap, recipients.PROBLEM,
        ["Çıkış yok", "Günlük süre çok kısa (<2 saat)"])

    assert [p.name for p in people] == ["AHMET SINAMA", "ÇAĞLA DENEME"]


def test_no_counted_note_means_an_empty_list_not_everybody(snap):
    """The dangerous direction. An empty tick list must not quietly mean "all"."""
    assert recipients.matching(snap, recipients.PROBLEM, []) == ()


def test_the_default_counts_every_problem_note_but_the_two(snap):
    """A note added to `anomalies.py` later counts without anybody being told.

    For a list that decides who gets contacted, including somebody who should not have
    been is a correction; leaving somebody out is silence.
    """
    default = recipients.default_labels(snap)

    assert "Çıkış yok" in default
    assert "Mesai verisi yok" in default
    for label in recipients.DEFAULT_OFF:
        assert label not in default
    assert "Uzaktan + sistem kaydı" not in default, "expected behaviour is not a problem"


def test_the_two_switched_off_notes_can_be_switched_on(snap):
    """They are a default, not a rule. `Tesis birleştirme` is a repaired punch, but
    somebody may still want to look at those people."""
    snapshot = Snapshot(
        period=snap.period, generated_at=snap.generated_at, rules={},
        coverage=snap.coverage,
        people=(person("SEDA TASLAK", problems=("Tesis birleştirme",)),))

    assert recipients.matching(snapshot, recipients.PROBLEM) == ()
    admitted = recipients.matching(snapshot, recipients.PROBLEM,
                                   ["Tesis birleştirme"])
    assert [p.name for p in admitted] == ["SEDA TASLAK"]


def test_the_group_and_the_clean_group_partition_the_month(snap):
    """With every problem note counted, the two must add up to everybody exactly once.

    The complement is the property that makes the pair trustworthy: somebody reading
    `Sorunu olanlar (99)` beside `Sorunu olmayanlar (69)` on a 176-person month should
    be able to add them.
    """
    every = frozenset(label for _f, label, _c in recipients.problem_labels(snap))
    problem = {p.name for p in recipients.matching(snap, recipients.PROBLEM, every)}
    clean = {p.name for p in recipients.matching(snap, recipients.NO_PROBLEM)}

    assert problem | clean == {p.name for p in snap.people}
    assert problem & clean == set()


def test_the_count_in_the_list_is_the_count_of_rows(snap):
    """A filter list that says 12 and then shows 40 is worse than no number."""
    for labels in ([], ["Çıkış yok"], None):
        entry = next(c for c in recipients.choices(snap, labels)
                     if c.key == recipients.PROBLEM)
        assert entry.count == len(
            recipients.matching(snap, recipients.PROBLEM, labels))


def test_the_notes_offered_for_ticking_carry_their_family_and_count(snap):
    """Fifteen checkboxes read as a wall unless they are grouped (ADR-029)."""
    from mesai.anomalies import GROUPS

    offered = recipients.problem_labels(snap)

    assert offered, "a month with problems must offer something to tick"
    families = [family for family, _label, _count in offered]
    assert families == sorted(families, key=GROUPS.index), "families must not interleave"
    for _family, label, count in offered:
        assert count == len(recipients.matching(snap, label)), label
    assert all(label != "Uzaktan + sistem kaydı"
               for _f, label, _c in offered), "expected behaviour is not offered"


def test_removals_still_apply_to_the_problem_group(snap):
    people = recipients.selected(snap, recipients.PROBLEM, {"AHMET SINAMA"},
                                 ["Çıkış yok"])
    assert [p.name for p in people] == ["ÇAĞLA DENEME"]


def test_nothing_is_offered_or_admitted_without_a_snapshot():
    assert recipients.problem_labels(None) == ()
    assert recipients.default_labels(None) == frozenset()
    assert recipients.matching(None, recipients.PROBLEM) == ()
