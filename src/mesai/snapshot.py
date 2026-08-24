"""The machine-readable companion to the report workbook.

Why this exists: the mail step, and any later step, must **never parse the generated
workbook**. That file is a presentation artifact — durations are `HH:MM` strings, cells
are merged, headers are Turkish, and e-mail addresses are deliberately absent from it
(`OUTPUT-SPEC.md` §1). Deriving data back out of formatting also breaks the moment the
layout changes, which happened on 2026-08-17 when the four gross/net columns became a
single `Çalışma Süresi` pair.

So every run writes both: the workbook for people, and this for programs. Both come
from the same computed objects in the same run, so they cannot disagree.

It is also what makes "do not recompute, just use the existing report" possible.
Loading a snapshot returns exactly the figures a human reviewed, rather than a fresh
calculation that might differ because a source file changed in the meantime.

**This file contains personal data** — names, e-mail addresses, hours. It belongs next
to the program, not in the folder HR opens, and never in the repository.

Keys are English, like the rest of the code. Only what a human reads is Turkish.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as date_type, datetime
from pathlib import Path

from .anomalies import DESCRIPTIONS, GROUPS, Collector, with_implied
from .config import Settings
from .models import MonthSummary, RunStats, WorkDay

# Bump when a field changes meaning or disappears. A reader that meets a version it
# does not know refuses rather than guessing — see load().
#
# 2: `problems` carries the new keyword labels (ADR-027). The values changed, not the
#    shape, which is exactly the kind of change a version guard exists for: a filter
#    written against "Çıkış kaydı yok" would quietly match nobody under "Çıkış yok".
# 3: `expected` added — the `info`-severity labels, so they can be filtered on without
#    joining `problems` and making expected behaviour look like a defect (ADR-028).
# 4: `days` added — the person's problem days, for the mail step (ADR-051).
# 5: `Giriş-çıkış tutarsız` became `Giriş-çıkış tutarsız (>20 saat)`. A label, so the
#    same breaking change as version 2: a filter or an exclusion list written against
#    the old wording matches nobody under the new one, silently.
# 6: `Giriş-çıkış yok` became `Hem giriş hem çıkış yok` (ADR-054). Same reason.
FORMAT_VERSION = 6


class SnapshotError(Exception):
    """The snapshot is missing, unreadable, or of an unknown version."""


@dataclass(frozen=True)
class ProblemDay:
    """One person-day that carries at least one problem note.

    Exists for the mail step. A person is chosen by the notes that were ticked, and the
    message is supposed to list **the days those notes are about** — not every day the
    person had a note on. So the day has to be the unit, and the label has to travel
    with it: somebody with a missing exit on the 3rd and a cross-site repair on the 9th
    gets told about the 3rd only, if the repair was not ticked.

    `entry` and `exit` are strings, not times, and may be empty. A missing exit is the
    whole point of the row, and `""` says it where a `None` time would have to be
    explained. They are taken from the day's measured interval when there is one, and
    from the source's own raw stamp when the record was refused — which is exactly the
    case where the reader needs to see what the file actually said.
    """
    date: date_type
    problems: tuple[str, ...]
    entry: str = ""
    exit: str = ""
    minutes: int | None = None       # counted for that day; None if nothing counted

    @property
    def hours_text(self) -> str:
        if self.minutes is None:
            return ""
        return f"{self.minutes // 60}:{self.minutes % 60:02d}"


@dataclass(frozen=True)
class Person:
    """One employee's month, as a program needs it.

    `problems` carries the anomaly *labels* affecting this person, which is what a
    later step filters on ("only people with a missing exit"). Labels rather than enum
    names because they are already the wording HR recognises, while the enum is an
    implementation detail that has been renamed once already.
    """
    name: str
    email: str | None
    personnel_no: str | None
    department: str | None
    facility: str | None
    in_roster: bool
    has_attendance: bool
    worked_days: int
    minutes: int                  # integer minutes, so nothing drifts in transit
    remote_days: float
    leave_days: float
    problems: tuple[str, ...]
    # Labels of `info` severity — expected behaviour, recorded so the audit trail is
    # complete. Kept OUT of `problems` on purpose (ADR-017): 21 people's rows once read
    # as defective because of these, burying the 2 real questions among them. Carried
    # anyway so the people screen can offer them as a filter, clearly marked as not
    # being anybody's problem. ADR-028.
    expected: tuple[str, ...]
    notes: tuple[str, ...]
    # The person's problem days, for the mail step. Month-level notes
    # (`Mesai verisi yok`, `Ay büyük ölçüde boş`) carry no date and stay in
    # `problems` only — there is no day to tell somebody about.
    days: tuple[ProblemDay, ...] = ()

    @property
    def labels(self) -> tuple[str, ...]:
        """Everything this person can be filtered by, problems first."""
        return self.problems + self.expected

    @property
    def hours_text(self) -> str:
        return f"{self.minutes // 60}:{self.minutes % 60:02d}"


@dataclass(frozen=True)
class Snapshot:
    period: str
    generated_at: datetime
    rules: dict[str, object]
    coverage: dict[str, dict[str, object]]
    people: tuple[Person, ...]

    @property
    def is_complete(self) -> bool:
        """False when a source failed to cover the period — do not mail from this."""
        return not any(c.get("partial") for c in self.coverage.values())

    # `with_implied` on both: a note that is a stricter case of another selects under
    # the broader one too (`anomalies.IMPLIES`). Applied here rather than in each
    # caller, so `label_counts` and the filters cannot disagree about who a label
    # holds — the window showing 48 and handing back 15 is the bug this prevents.
    def with_problem(self, label: str) -> tuple[Person, ...]:
        return tuple(p for p in self.people if label in with_implied(p.problems))

    def with_label(self, label: str) -> tuple[Person, ...]:
        """People carrying `label`, whether it is a problem or expected behaviour."""
        return tuple(p for p in self.people if label in with_implied(p.labels))

    @property
    def problem_labels(self) -> tuple[str, ...]:
        """Distinct problem labels, most common first."""
        return tuple(label for label, _count, is_problem in self.label_counts()
                     if is_problem)

    def label_counts(self) -> tuple[tuple[str, int, bool], ...]:
        """`(label, people, is_problem)` — the filter list, grouped by family.

        Family first, frequency second. Ordering by frequency alone put "Giriş yok"
        four rows below "Çıkış yok" simply because fewer people had it, and those two
        are precisely each other's neighbour when somebody is choosing between them.
        A family that is entirely absent from this month never appears.
        """
        family = {label: group for label, _s, _e, group in DESCRIPTIONS.values()}
        order = {name: index for index, name in enumerate(GROUPS)}
        # Declaration order within a family, not frequency. Frequency reshuffles the
        # dropdown every month, so somebody who learned where a note sits has to find
        # it again; and it split the punch pair, putting "Mesai verisi yok" between
        # "Çıkış yok" and "Giriş yok".
        declared = {label: index for index, (label, _s, _e, _g)
                    in enumerate(DESCRIPTIONS.values())}

        # Counted with the implied labels included, because this list IS the filter:
        # a count that excluded them would promise 15 rows and the filter would show 41.
        # Problems and expected behaviour are expanded separately so an implication can
        # never quietly move a note across that line.
        seen: dict[str, tuple[int, bool]] = {}
        for person in self.people:
            for label in with_implied(person.problems):
                count, _ = seen.get(label, (0, True))
                seen[label] = (count + 1, True)
            for label in with_implied(person.expected):
                count, _ = seen.get(label, (0, False))
                seen[label] = (count + 1, False)

        def key(item: tuple[str, tuple[int, bool]]) -> tuple[int, int, str]:
            label, _value = item
            # An unknown label sorts last rather than crashing: labels come from a file
            # that a future version may have written.
            return (order.get(family.get(label, ""), len(GROUPS)),
                    declared.get(label, len(declared)), label)

        return tuple((label, count, is_problem)
                     for label, (count, is_problem) in sorted(seen.items(), key=key))


def default_path(period: str, output_path: Path) -> Path:
    """Where the snapshot for `period` lives: **beside its workbook.**

    It used to go to `veri/` next to the program instead, on the reasoning that the
    folder HR opens should hold one file per month and this one holds e-mail
    addresses. Two things were wrong with that. ADR-021 already described the pair as
    living together ("the program finds the JSON beside the report") — the code and
    the decision disagreed, and only one of them can be right. And once the window
    writes to a folder the user chose, `veri/` is next to the *program*, which is a
    place they never look; the two halves of one run would end up in two unrelated
    directories.

    They are one artifact pair from one run and they move together. See ADR-024.
    """
    return output_path.parent / f"gonderim-{period}.json"


def _problem_days(
    anomalies: Collector, workdays: list[WorkDay],
) -> dict[tuple[str, str], tuple[ProblemDay, ...]]:
    """Per person, the days carrying a problem note, in date order.

    Two sources, and both are needed. The **labels and the raw stamps** come from the
    anomalies, which is the only place that knows a record was refused and what the file
    actually said. The **measured figures** come from the WorkDay, when there is one —
    for a refused record there may be no interval at all, which is exactly the day the
    reader has to be told about.

    Month-level notes are skipped: they have no date, so there is no day to report.
    """
    days: dict[tuple[str, str], dict[date_type, dict]] = {}
    for anomaly in anomalies.items:
        if anomaly.key is None or anomaly.date is None or not anomaly.is_problem:
            continue
        entry = days.setdefault(anomaly.key, {}).setdefault(
            anomaly.date, {"labels": set(), "entry": "", "exit": ""})
        entry["labels"].add(anomaly.label)
        # First non-empty wins. A day can carry two records — one per site — and their
        # stamps differ; the audit sheet has every one of them, this needs a
        # representative pair rather than a merged fiction.
        entry["entry"] = entry["entry"] or anomaly.raw_entry
        entry["exit"] = entry["exit"] or anomaly.raw_exit

    measured = {(w.key, w.date): w for w in workdays}
    built: dict[tuple[str, str], tuple[ProblemDay, ...]] = {}
    for key, by_date in days.items():
        rows = []
        for day, found in sorted(by_date.items()):
            workday = measured.get((key, day))
            rows.append(ProblemDay(
                date=day,
                problems=tuple(sorted(found["labels"])),
                # The measured figures when the day counted, the file's own stamps when
                # it did not.
                entry=(workday.first_entry.strftime("%H:%M")
                       if workday and workday.first_entry else found["entry"]),
                exit=(workday.last_exit.strftime("%H:%M")
                      if workday and workday.last_exit else found["exit"]),
                minutes=(int(workday.gross.total_seconds() // 60)
                         if workday else None),
            ))
        built[key] = tuple(rows)
    return built


def build(
    period: str, summaries: list[MonthSummary], anomalies: Collector,
    stats: RunStats, settings: Settings, generated_at: datetime,
    workdays: list[WorkDay] | None = None,
) -> Snapshot:
    by_key: dict[tuple[str, str], set[str]] = {}
    expected_by_key: dict[tuple[str, str], set[str]] = {}
    for anomaly in anomalies.items:
        if anomaly.key is None:
            continue
        target = by_key if anomaly.is_problem else expected_by_key
        target.setdefault(anomaly.key, set()).add(anomaly.label)

    days_by_key = _problem_days(anomalies, workdays or [])

    people = tuple(
        Person(
            name=s.employee.display_name,
            email=s.employee.email,
            personnel_no=s.employee.personnel_no,
            department=s.employee.department,
            facility=s.employee.facility,
            in_roster=s.employee.in_roster,
            has_attendance=s.has_attendance,
            worked_days=s.worked_days,
            minutes=int(s.gross.total_seconds() // 60),
            remote_days=s.remote_days,
            leave_days=s.leave_days,
            problems=tuple(sorted(by_key.get(s.employee.key, ()))),
            expected=tuple(sorted(expected_by_key.get(s.employee.key, ()))),
            notes=tuple(s.notes),
            days=days_by_key.get(s.employee.key, ()),
        )
        for s in summaries
    )

    return Snapshot(
        period=period,
        generated_at=generated_at,
        # The active rules travel with the data. Without them a snapshot read months
        # later cannot be interpreted: the same numbers mean different things under a
        # different break or daily-measure setting.
        rules={
            "daily_hours": settings.daily_hours,
            "break_deducted": settings.brk.deduct,
            "break_minutes": settings.brk.minutes,
            "short_day_hours": settings.plausibility.short_day.total_seconds() / 3600,
            "remote_replaces_attendance": settings.remote_replaces,
        },
        coverage={
            source: {
                "present": cov.present,
                "expected": cov.expected,
                "partial": cov.is_partial,
                "missing_from": (cov.trailing_missing[0].isoformat()
                                 if cov.trailing_missing else None),
            }
            for source, cov in stats.coverage.items()
        },
        people=people,
    )


def save(snapshot: Snapshot, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": FORMAT_VERSION,
        "period": snapshot.period,
        "generated_at": snapshot.generated_at.isoformat(timespec="seconds"),
        "rules": snapshot.rules,
        "coverage": snapshot.coverage,
        "people": [
            {
                "name": p.name, "email": p.email, "personnel_no": p.personnel_no,
                "department": p.department, "facility": p.facility,
                "in_roster": p.in_roster, "has_attendance": p.has_attendance,
                "worked_days": p.worked_days, "minutes": p.minutes,
                "remote_days": p.remote_days, "leave_days": p.leave_days,
                "problems": list(p.problems), "expected": list(p.expected),
                "notes": list(p.notes),
                "days": [
                    {"date": d.date.isoformat(), "problems": list(d.problems),
                     "entry": d.entry, "exit": d.exit, "minutes": d.minutes}
                    for d in p.days
                ],
            }
            for p in snapshot.people
        ],
    }
    # Written to a temp file then moved, for the same reason the workbook is: a crash
    # mid-write must not leave a half-valid file that still parses.
    target = path.with_suffix(".tmp.json")
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    target.replace(path)
    return path


def load(path: Path) -> Snapshot:
    if not path.exists():
        raise SnapshotError(
            f"Bu raporun veri dosyası bulunamadı:\n  {path}\n\n"
            "Rapor eski bir sürümle üretilmiş olabilir. Raporu yeniden üretin."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"{path.name}: dosya okunamadı ({exc}).") from exc

    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise SnapshotError(
            f"{path.name}: veri dosyası sürümü {version}, beklenen {FORMAT_VERSION}. "
            "Raporu yeniden üretin."
        )

    return Snapshot(
        period=payload["period"],
        generated_at=datetime.fromisoformat(payload["generated_at"]),
        rules=payload.get("rules", {}),
        coverage=payload.get("coverage", {}),
        people=tuple(
            Person(
                name=p["name"], email=p.get("email"),
                personnel_no=p.get("personnel_no"), department=p.get("department"),
                facility=p.get("facility"), in_roster=p.get("in_roster", False),
                has_attendance=p.get("has_attendance", False),
                worked_days=p.get("worked_days", 0), minutes=p.get("minutes", 0),
                remote_days=p.get("remote_days", 0.0),
                leave_days=p.get("leave_days", 0.0),
                problems=tuple(p.get("problems", ())),
                expected=tuple(p.get("expected", ())),
                notes=tuple(p.get("notes", ())),
                days=tuple(
                    ProblemDay(
                        date=date_type.fromisoformat(d["date"]),
                        problems=tuple(d.get("problems", ())),
                        entry=d.get("entry", ""), exit=d.get("exit", ""),
                        minutes=d.get("minutes"))
                    for d in p.get("days", ())),
            )
            for p in payload.get("people", ())
        ),
    )
