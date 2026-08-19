"""Who is in the list: a filter over a snapshot, minus whoever was removed by hand.

Pure functions over `snapshot.Snapshot`. No widget, no file, no clock — so the rule
"only people missing an exit punch, except these two" can be stated in a test with a
hand-written expectation, which is the whole reason it is not in the window.

The vocabulary is deliberately small:

* a **filter** narrows the snapshot to a group (everyone, the clean ones, or one note),
* an **exclusion set** removes named individuals from whatever the filter returned,
* a **selection** is what survives both.

Excluding by name rather than by index matters: the list re-sorts and re-filters under
the user, and an index would silently come to mean somebody else.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..normalize import sort_key
from ..snapshot import Person, Snapshot

# Two filters that are not a note. Kept as sentinels rather than magic strings at the
# call site so the window cannot invent a third by typo.
ALL = "__all__"
NO_PROBLEM = "__clean__"

ALL_LABEL = "Herkes"
NO_PROBLEM_LABEL = "Sorunu olmayanlar"


@dataclass(frozen=True)
class Choice:
    """One entry in the filter list: what it is called, and how many it matches."""
    key: str
    label: str
    count: int
    is_problem: bool = False

    @property
    def display(self) -> str:
        return f"{self.label}  ({self.count})"


def choices(snapshot: Snapshot | None) -> tuple[Choice, ...]:
    """The filter list for a UI, built from the snapshot rather than hard-coded.

    A note that nobody has does not appear, and a note added to `anomalies.py` later
    appears without anything here changing. That is the point: the list of things worth
    filtering by is a property of the data, not a list somebody has to remember to
    update in two places.
    """
    if snapshot is None:
        return ()
    clean = sum(1 for p in snapshot.people if not p.problems)
    entries = [
        Choice(ALL, ALL_LABEL, len(snapshot.people)),
        Choice(NO_PROBLEM, NO_PROBLEM_LABEL, clean),
    ]
    entries += [Choice(label, label, count, is_problem)
                for label, count, is_problem in snapshot.label_counts()]
    return tuple(entries)


def matching(snapshot: Snapshot | None, filter_key: str) -> tuple[Person, ...]:
    """Everyone the filter admits, in the order a person reads a list of names."""
    if snapshot is None:
        return ()
    if filter_key == ALL:
        people = snapshot.people
    elif filter_key == NO_PROBLEM:
        people = tuple(p for p in snapshot.people if not p.problems)
    else:
        people = snapshot.with_label(filter_key)
    return tuple(sorted(people, key=lambda p: sort_key(p.name)))


def selected(snapshot: Snapshot | None, filter_key: str,
             excluded: Iterable[str]) -> tuple[Person, ...]:
    """The filter's result minus the people removed by hand."""
    removed = set(excluded)
    return tuple(p for p in matching(snapshot, filter_key) if p.name not in removed)


def without_email(people: Iterable[Person]) -> tuple[Person, ...]:
    """Selected people who could not be written to.

    Reported rather than dropped. In May 2026 this is 11 people, all of them absent
    from the roster — leavers whose address the export no longer carries. Silently
    removing them would make a list of 30 quietly become 27.
    """
    return tuple(p for p in people if not p.email)
