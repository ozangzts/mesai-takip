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

from ..anomalies import DESCRIPTIONS
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


# The two groups the note panel is split into. Not the `anomalies.GROUPS` families:
# those say what KIND of thing a note is, and the question somebody scanning that panel
# is actually asking is "which of these cost somebody hours".
LOST = "Günü sayılmayan"
KEPT = "Günü sayılan"


def day_counts(snapshot: Snapshot | None) -> dict[str, tuple[int, int]]:
    """Per note, `(days it covers, how many of those lost time)`.

    Computed together so the two cannot drift: they were separate rules once and the
    panel showed the result, one obeying an implication the other did not, on the same
    line. The implication itself is gone (ADR-065); computing the pair in one place is
    what stays.

    July: `Hem giriş hem çıkış yok`
    covers 78 days and **5** of them lost time — the other 73 were counted from the
    person's Teknopark record. Printing 5 next to "27 kişi" and nothing else invites the
    reader to look for an arithmetic error rather than a fact.
    """
    if snapshot is None:
        return {}
    found: dict[str, list[int]] = {}
    for person in snapshot.people:
        for day in person.days:
            for label in day.problems:
                row = found.setdefault(label, [0, 0])
                row[0] += 1
                if not day.explained:
                    row[1] += 1
    return {label: (total, lost) for label, (total, lost) in found.items()}


def problem_labels(
    snapshot: Snapshot | None,
) -> tuple[tuple[str, str, int], ...]:
    """`(group, label, people)` for every problem note present, in filter order.

    `group` is `LOST` or `KEPT` (ADR-056): whether any of the note's days cost somebody
    hours. The panel needs nothing beyond the heading and the count — an earlier version
    printed the day ratio beside each label (`27 kişi · 5/78 gün sayılmadı`) and it was
    noise, because with the filter itself restricted to outstanding days there is no
    second number left to reconcile. The heading says which half of the list is the one
    to chase; that is the whole job.

    A note with no dated days — `Kart bilgisi yok` is the only one left — sits in
    `LOST`: a month nobody can account for is not the thing to file under "counted".
    """
    if snapshot is None:
        return ()
    days = day_counts(snapshot)
    return tuple(
        (LOST if (days.get(label, (0, 0))[1] or label not in days) else KEPT,
         label, len(matching(snapshot, label)))
        for label, _count, is_problem in snapshot.label_counts()
        if is_problem)


def default_labels(snapshot: Snapshot | None) -> frozenset[str]:
    """Which notes count as a problem before anybody has said otherwise.

    Everything except `DEFAULT_OFF`. A note added to `anomalies.py` later therefore
    counts by default: for a list that decides who gets contacted, including somebody
    who should not have been is a correction, and leaving somebody out is silence.
    """
    return frozenset(label for _g, label, _c in problem_labels(snapshot)
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
    clean = len(matching(snapshot, NO_PROBLEM))
    entries = [
        Choice(ALL, ALL_LABEL, len(snapshot.people)),
        Choice(NO_PROBLEM, NO_PROBLEM_LABEL, clean),
        # Counted against the ticked labels, not against "has any note at all", so the
        # number in the list is the number of rows the list will show.
        Choice(PROBLEM, PROBLEM_LABEL, len(matching(snapshot, PROBLEM, labels)),
               is_problem=True),
    ]
    entries += [Choice(label, label, len(matching(snapshot, label)), is_problem)
                for label, _count, is_problem in snapshot.label_counts()]
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
        people = tuple(p for p in snapshot.people if not _has_problem(p, snapshot))
    elif filter_key == PROBLEM:
        counted = (default_labels(snapshot) if labels is None
                   else frozenset(labels))
        people = tuple(p for p in snapshot.people if outstanding(p, counted))
    else:
        # A single note. `outstanding` rather than "carries the label", so ticking
        # `Giriş yok` brings the people whose entry is missing EVERYWHERE and nobody
        # else. Expected-behaviour notes have no dated problem days and fall through to
        # the month-level branch, so they still list their people.
        people = tuple(p for p in snapshot.people
                       if outstanding(p, {filter_key})
                       or filter_key in p.expected)
    return tuple(sorted(people, key=lambda p: sort_key(p.name)))


def _has_problem(person: Person, snapshot: Snapshot) -> bool:
    """Whether anything is outstanding for this person under any note.

    `Sorunu olmayanlar` is the complement of `Sorunu olanlar`, and a test holds the two
    to a partition of the month. So both have to ask the same question: not "does this
    person carry a note" but "did this person lose anything". Somebody whose Macunköy row
    was blank on a day their Teknopark record covered in full carries a note and has
    nothing outstanding — they belong with the clean.
    """
    return bool(outstanding(person, {label for _g, label, _c in
                                     problem_labels(snapshot)}))


def selected(snapshot: Snapshot | None, filter_key: str, excluded: Iterable[str],
             labels: Iterable[str] | None = None) -> tuple[Person, ...]:
    """The filter's result minus the people removed by hand."""
    removed = set(excluded)
    return tuple(p for p in matching(snapshot, filter_key, labels)
                 if p.name not in removed)


def days_for(person: Person, labels: Iterable[str] | None = None,
             snapshot: Snapshot | None = None) -> tuple[ProblemDay, ...]:
    """The person's days the ticked notes are about — and only the days that cost them.

    The rule, in the operator's words: *"bir adamın girişi yoksa hiçbir yerde ve uzaktan
    çalışmıyorsa ve izinli değilse o gün iptal."* So a day is here when its punch is
    missing **everywhere** — not at either site, not covered by a remote declaration, not
    covered by leave. A day the other site's record already covered is not a problem and
    never was; where the entry was read at one site and the exit at the other, the union
    counted the whole day.

    This used to be optional (`only_unexplained=False` by default), on the reasoning that
    the report might want every day. It does not — the report reads anomalies directly —
    so the flag existed only to be forgotten by a caller. `ProblemDay.explained` is the
    predicate and it applies here always.

    Ticked notes choose both *who* and *which days* (ADR-051). Each note brings only its
    own days: `Giriş yok` no longer returns a day that had neither punch (ADR-065).

    Measured over May-July 2026 with the three punch notes ticked: of 147 / 247 / 244
    days carrying a note, 92 / 146 / 152 are here. The rest were counted elsewhere or are
    leave.
    """
    if labels is None:
        if snapshot is None:
            return tuple(d for d in person.days if not d.explained)
        labels = default_labels(snapshot)
    counted = frozenset(labels)
    return tuple(day for day in person.days
                 if not day.explained
                 and counted.intersection(day.problems))


def outstanding(person: Person, labels: Iterable[str]) -> frozenset[str]:
    """Which of `labels` this person actually has something outstanding under.

    A note reaches somebody one of two ways, and only one of them can be explained away:

    * through a **day** — outstanding only if that day lost time (`days_for`),
    * through a **month-level note** with no date at all (`Kart bilgisi yok`) — there
      is no day to explain, so it always stands.

    Without the second case the 31 people whose July has no attendance record at all
    would drop out of every list, which is the opposite of the point.
    """
    counted = frozenset(labels)
    carried = counted.intersection(person.problems)
    if not carried:
        return frozenset()
    dated = {label for day in person.days for label in day.problems}
    from_days = {label for day in days_for(person, carried)
                 for label in day.problems}
    return frozenset(label for label in carried
                     if label in from_days or label not in dated)


def without_email(people: Iterable[Person]) -> tuple[Person, ...]:
    """Selected people who could not be written to.

    Reported rather than dropped. In May 2026 this is 11 people, all of them absent
    from the roster — leavers whose address the export no longer carries. Silently
    removing them would make a list of 30 quietly become 27.
    """
    return tuple(p for p in people if not p.email)
