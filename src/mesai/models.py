"""The vocabulary of the whole system.

Frozen dataclasses throughout: a pipeline stage returns new objects rather than
editing what it was given, so a bug cannot travel backwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

NameKey = tuple[str, str]


@dataclass(frozen=True)
class PunchRecord:
    """One raw row from one source. Faithful to the source, warts included.

    `entry is None` is not an error condition — it is the most common shape in the
    Macunköy export, and the type must say so.
    """
    source: str                      # "macunkoy" | "teknopark" | "izin"
    source_row: int
    raw_name: str
    key: NameKey
    date: date
    entry: datetime | None
    exit: datetime | None
    badge_id: str | None = None
    department: str | None = None
    reported_duration: str | None = None
    tag: str | None = None           # e.g. "uzaktan" for remote-work intervals


@dataclass(frozen=True)
class RosterEntry:
    key: NameKey
    display_name: str                # abbreviated form as stored in the roster
    email: str | None
    facility: str | None
    department: str | None
    job_title: str | None
    row: int


@dataclass(frozen=True)
class Employee:
    key: NameKey
    display_name: str                # full name from the transaction files
    personnel_no: str | None = None
    department: str | None = None
    job_title: str | None = None
    facility: str | None = None
    email: str | None = None
    in_roster: bool = False
    sources: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    sources: frozenset[str] = frozenset()

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True)
class WorkDay:
    key: NameKey
    date: date
    intervals: tuple[Interval, ...]       # already merged
    # The day's measured working time, per `settings.daily_hours` — by default the
    # span from first entry to last exit, so it is NOT necessarily the sum of
    # `intervals` (ADR-015). `net` equals it whenever the break deduction is off,
    # which is the shipped configuration (ADR-016).
    gross: timedelta
    break_deduction: timedelta
    net: timedelta
    tags: frozenset[str] = frozenset()

    @property
    def first_entry(self) -> datetime | None:
        return self.intervals[0].start if self.intervals else None

    @property
    def last_exit(self) -> datetime | None:
        return self.intervals[-1].end if self.intervals else None

    @property
    def interval_total(self) -> timedelta:
        """Presence only — the summed intervals, excluding in-day gaps."""
        return sum((iv.duration for iv in self.intervals), timedelta())

    @property
    def gap_total(self) -> timedelta:
        """In-day time between intervals. Paid under the envelope rule."""
        if not self.intervals:
            return timedelta()
        span = self.intervals[-1].end - self.intervals[0].start
        return span - self.interval_total

    @property
    def sources(self) -> frozenset[str]:
        out: set[str] = set()
        for iv in self.intervals:
            out |= iv.sources
        return frozenset(out)


@dataclass(frozen=True)
class LeaveRecord:
    key: NameKey
    raw_name: str
    personnel_no: str | None
    leave_type: str
    status: str | None
    start: datetime | None
    end: datetime | None
    days: float
    department: str | None
    source_row: int


@dataclass(frozen=True)
class MonthSummary:
    employee: Employee
    period: str
    gross: timedelta
    net: timedelta
    worked_days: int
    remote_days: float
    leave_days: float
    anomaly_count: int
    has_attendance: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceCoverage:
    """How much of the reporting period one source actually covers.

    Exists because the July 2026 Teknopark export stopped at the 19th — it was taken
    mid-month — and the pipeline produced a confident full-month report from it, with
    the reconciliation reading TAMAM. Every other guard passed, because the file was
    internally consistent: it was complete data about an incomplete period.

    `trailing_missing` is the signal, not the raw count of absent days. Teknopark
    legitimately has no records on days the office is shut while Macunköy production
    runs, so "fewer days than the other source" means nothing. An unbroken run of
    expected working days at the END of the period means the export was cut short.
    """
    source: str
    present: int                  # expected working days with at least one record
    expected: int                 # expected working days in the period
    trailing_missing: tuple[date, ...] = ()

    @property
    def is_partial(self) -> bool:
        """More than one trailing working day missing — an export taken mid-period.

        One day is tolerated: an export run on the last working day of the month
        legitimately has nothing for that day yet.
        """
        return len(self.trailing_missing) > 1


@dataclass
class RunStats:
    """Reconciliation counters for the Kontrol sheet."""
    rows_read: dict[str, int] = field(default_factory=dict)
    records_built: dict[str, int] = field(default_factory=dict)
    excluded_badges: int = 0
    intervals_accepted: int = 0
    # Presence (summed intervals) vs what the report pays (may include in-day gaps).
    # Both are reported so the envelope rule's cost is visible — see ADR-015.
    union_total: timedelta = timedelta()
    accepted_total: timedelta = timedelta()
    files: dict[str, str] = field(default_factory=dict)
    roster_duplicates: list[str] = field(default_factory=list)
    out_of_period: dict[str, int] = field(default_factory=dict)
    out_of_period_leave: int = 0
    # Per attendance source: (expected working days present, expected total, the
    # trailing run of expected working days with no record at all). The last one is
    # the partial-export signal — see SourceCoverage and ADR-020.
    coverage: dict[str, "SourceCoverage"] = field(default_factory=dict)
    roster_date: date | None = None      # roster export date, from the file itself
