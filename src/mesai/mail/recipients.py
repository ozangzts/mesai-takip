"""Who is in the list: a filter over a snapshot, minus whoever was removed by hand.

Pure functions over `snapshot.Snapshot`. No widget, no file, no clock — so the rule
"only people missing an exit punch, except these two" can be stated in a test with a
hand-written expectation, which is the whole reason it is not in the window.

The vocabulary is deliberately small:

* a **filter** narrows the snapshot to a group — everyone, the clean ones, the ones with
  a problem, or one specific note,
* for the problem group, a set of **counted labels** says which notes make somebody a
  problem; the rest of the notes do not put anybody in the list,
* an **exclusion set** removes named individuals from whatever the filter returned,
* a **selection** is what survives both.

Excluding by name rather than by index matters: the list re-sorts and re-filters under
the user, and an index would silently come to mean somebody else.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..anomalies import DESCRIPTIONS, with_implied
from ..normalize import sort_key
from ..snapshot import Person, ProblemDay, Snapshot

# Two filters that are not a note. Kept as sentinels rather than magic strings at the
# call site so the window cannot invent a third by typo.
ALL = "__all__"
NO_PROBLEM = "__clean__"
PROBLEM = "__problem__"

ALL_LABEL = "Herkes"
NO_PROBLEM_LABEL = "Sorunu olmayanlar"
PROBLEM_LABEL = "Sorunu olanlar"

# The entries that are not a note. Named once: three call sites were keeping their own
# `(ALL, NO_PROBLEM)` tuple in step by hand, and the third one to be added would have
# been the one somebody forgot.
STANDING = (ALL, NO_PROBLEM, PROBLEM)

# Problem labels that do NOT count towards the problem group unless somebody ticks them.
# Both describe something already dealt with rather than something to take up with the
# person: `Tesis birleştirme` is a missing punch the program completed from the other
# site's record, and `Uzaktan + kart kaydı` is a remote day where the badge reading was
# counted too. Measured over May-July 2026 they are the whole difference between "anyone
# with a problem note" and the three categories actually wanted — 4, 8 and 8 people.
#
# In code rather than in `config/`, because these are OUR OWN labels from
# `anomalies.py`, which is the line AGENTS.md §6 draws: tables keyed on strings a source
# file writes belong in config, tables keyed on our identifiers do not.
DEFAULT_OFF = ("Tesis birleştirme", "Uzaktan + kart kaydı")


@dataclass(frozen=True)
class Choice:
    """One entry in the filter list: what it is called, and how many it matches."""
    key: str
    label: str
    count: int
    is_problem: bool = False

    @property
    def display(self) -> str:
        # Grouping by family means expected-behaviour notes no longer sit together at
        # the bottom, so each one says what it is. Without this, "working as intended"
        # would be indistinguishable from "somebody lost hours" (ADR-017).
        suffix = "" if self.is_problem or self.key in (ALL, NO_PROBLEM) \
            else "  ·  beklenen durum"
        return f"{self.label}  ({self.count}){suffix}"


def problem_labels(snapshot: Snapshot | None) -> tuple[tuple[str, str, int], ...]:
    """`(family, label, people)` for every problem note present, in filter order.

    The family comes along so a list of fifteen checkboxes can be grouped instead of
    read as one wall — the same grouping the filter list uses (ADR-029).
    """
    if snapshot is None:
        return ()
    family = {label: group for label, _s, _e, group in DESCRIPTIONS.values()}
    return tuple((family.get(label, "Diğer"), label, count)
                 for label, count, is_problem in snapshot.label_counts()
                 if is_problem)


def default_labels(snapshot: Snapshot | None) -> frozenset[str]:
    """Which notes count as a problem before anybody has said otherwise.

    Everything except `DEFAULT_OFF`. A note added to `anomalies.py` later therefore
    counts by default: for a list that decides who gets contacted, including somebody
    who should not have been is a correction, and leaving somebody out is silence.
    """
    return frozenset(label for _family, label, _count in problem_labels(snapshot)
                     if label not in DEFAULT_OFF)


def choices(snapshot: Snapshot | None,
            labels: Iterable[str] | None = None) -> tuple[Choice, ...]:
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
        # Counted against the ticked labels, not against "has any note at all", so the
        # number in the list is the number of rows the list will show.
        Choice(PROBLEM, PROBLEM_LABEL, len(matching(snapshot, PROBLEM, labels)),
               is_problem=True),
    ]
    entries += [Choice(label, label, count, is_problem)
                for label, count, is_problem in snapshot.label_counts()]
    return tuple(entries)


def matching(snapshot: Snapshot | None, filter_key: str,
             labels: Iterable[str] | None = None) -> tuple[Person, ...]:
    """Everyone the filter admits, in the order a person reads a list of names.

    `labels` applies to the problem group only: the notes that count. `None` means the
    default set, so a caller that does not care about the distinction gets a sensible
    list rather than an empty one.
    """
    if snapshot is None:
        return ()
    if filter_key == ALL:
        people = snapshot.people
    elif filter_key == NO_PROBLEM:
        people = tuple(p for p in snapshot.people if not p.problems)
    elif filter_key == PROBLEM:
        counted = (default_labels(snapshot) if labels is None
                   else frozenset(labels))
        people = tuple(p for p in snapshot.people
                       if counted.intersection(with_implied(p.problems)))
    else:
        people = snapshot.with_label(filter_key)
    return tuple(sorted(people, key=lambda p: sort_key(p.name)))


def selected(snapshot: Snapshot | None, filter_key: str, excluded: Iterable[str],
             labels: Iterable[str] | None = None) -> tuple[Person, ...]:
    """The filter's result minus the people removed by hand."""
    removed = set(excluded)
    return tuple(p for p in matching(snapshot, filter_key, labels)
                 if p.name not in removed)


def days_for(person: Person, labels: Iterable[str] | None = None,
             snapshot: Snapshot | None = None,
             only_unexplained: bool = False) -> tuple[ProblemDay, ...]:
    """The person's days the message may speak about: those the ticked notes are about.

    The rule ADR-051 states — ticked notes choose both *who* and *which days* — lives
    here rather than in the mail step, because it was stated only in a test and a rule
    stated in a test gets re-implemented slightly differently by whoever writes the
    caller. `with_implied` applies here for the same reason it applies to the person:
    ticking `Giriş yok` must return the day that has no entry *and* no exit, or the
    person is written to about a day the message then cannot mention.

    `labels=None` means the default set, which needs the snapshot to know what notes
    exist. Passing neither is "every day this person has a problem on".

    `only_unexplained` drops the days where **nothing was lost** — see
    `ProblemDay.explained`. A note is about a record; whether a minute went missing is a
    fact about the day. Measured over May-July 2026, with the three punch notes ticked:

        selected days                    147   247   244
        still counted (another record)  - 52  - 99  - 90
        counted nothing, but on leave   -  3  -  2  -  2
        actually lost                     92   146   152

    and by person, 58 / 82 / 64 becomes 34 / 42 / 36. Those dropped are Teknopark staff
    who called at Macunköy: the Macunköy row is the broken one, their day was recorded
    in full at Teknopark, and they lost nothing. Where the entry was read at one site
    and the exit at another, that is a complete day too — the union already counted it.

    Not the default, because this module also answers "what is wrong with this person's
    month", where an explained day is still worth showing. The mail step passes True.
    """
    if labels is None:
        if snapshot is None:
            days = person.days
            return tuple(d for d in days if not d.explained) if only_unexplained                 else days
        labels = default_labels(snapshot)
    counted = frozenset(labels)
    return tuple(day for day in person.days
                 if counted.intersection(with_implied(day.problems))
                 and not (only_unexplained and day.explained))


def with_unexplained_days(people: Iterable[Person],
                          labels: Iterable[str] | None = None) -> tuple[Person, ...]:
    """Those of `people` who still have a day left once the explained ones are dropped.

    Filtering days is not enough on its own: somebody every one of whose days was
    counted elsewhere would otherwise be written to with an empty list. 24 / 40 / 27
    people over May-July 2026 are exactly that.
    """
    return tuple(p for p in people
                 if days_for(p, labels, only_unexplained=True))


def without_email(people: Iterable[Person]) -> tuple[Person, ...]:
    """Selected people who could not be written to.

    Reported rather than dropped. In May 2026 this is 11 people, all of them absent
    from the roster — leavers whose address the export no longer carries. Silently
    removing them would make a list of 30 quietly become 27.
    """
    return tuple(p for p in people if not p.email)


def other_problems(person: Person, filter_key: str) -> int:
    """How many problems this person has *besides* the one being filtered on.

    A count, not a list. Under a specific note it answers "is there more going on with
    this person than the thing I filtered for"; under `Herkes` there is nothing to
    exclude, so it is simply how many problems they have.

    Expected-behaviour labels are not counted. They are not problems, and inflating a
    problem count with them is the mistake ADR-017 exists to prevent.

    Under the problem group there is no single note to subtract, so it is the whole
    count — which is what somebody scanning that list wants to know.
    """
    return sum(1 for label in person.problems if label != filter_key)
