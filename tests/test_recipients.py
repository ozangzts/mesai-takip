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
            person("AHMET SINAMA", problems=("Çıkış yok", "Süre çok kısa")),
            person("ZEYNEP ÖRNEK", expected=("Uzaktan + sistem kaydı",)),
            person("BERK NUMUNE", email=None, problems=("Mesai verisi yok",)),
            person("SEDA TASLAK"),
        ),
    )


# --- the filter list --------------------------------------------------------

def test_the_filter_list_is_built_from_the_data_not_hard_coded(snap):
    """A note added to anomalies.py must appear here without this module changing."""
    keys = [c.key for c in recipients.choices(snap)]

    assert keys[:2] == [recipients.ALL, recipients.NO_PROBLEM]
    assert "Çıkış yok" in keys
    assert "Uzaktan + sistem kaydı" in keys


def test_problems_are_listed_before_expected_behaviour(snap):
    """A dropdown is read top-down; hours-losing rows belong above working-as-intended."""
    notes = [c for c in recipients.choices(snap) if c.key not in
             (recipients.ALL, recipients.NO_PROBLEM)]
    assert [c.is_problem for c in notes] == sorted(
        (c.is_problem for c in notes), reverse=True)


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
