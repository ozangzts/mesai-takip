# ARCHITECTURE.md — Modules, Data Flow, and Why

**Status: BUILT.** Phase 1 is implemented, 475 tests pass, and three months (May,
June and July 2026) have been generated with the reconciliation invariant holding.
July's Teknopark export covers only part of the month and the run says so — ADR-020.
Phase 2/3/4 modules listed below are still design.

---

## 1. Shape of the system

A **command-line batch tool**. One command, one month, one workbook out.

```
mesai rapor --ay 2026-05                  # or: python -m mesai rapor ...
rapor.cmd --ay 2026-05                    # wrapper: no conda activate needed
```

Not a service, not a GUI, not a notebook. Reasons: it runs once a month; the output
is a file HR opens in Excel; it must be schedulable (Windows Task Scheduler) for the
Phase 4 e-mail job; and a CLI is trivially testable.

## 2. Pipeline

Six stages, each a pure function of the previous one's output. No stage reaches
back. No stage mutates global state.

```
  config/*.yaml     data/personel/*.xlsx     data/raw/2026-05/*.xlsx
        |                    |                        |
        v                    v                        v
   [1] load config    [2] read roster FIRST    [2] read the 3 monthly files
        |                    |                        |
        +---------+----------+------------------------+
                  v
           [2b] filter to period  -> anything outside the month is dropped
                  v
           [2c] coverage check     -> does each source cover the period? ADR-020
                  v
           [3] normalize          -> identities resolved against the roster,
                  |                   non-employee badges excluded
                  v
           [4] merge              -> WorkDay[]  (interval union per person-day)
                  v
           [5] compute            -> gross/net, anomalies  [Phase 2: FM, Multinet]
                  v
           [6] report             -> data/out/2026-05/mesai-raporu-2026-05.xlsx
                  |                   data/out/2026-05/gonderim-2026-05.json
                  v
                            [Phase 4: mail reads the JSON, never the workbook]
```

Stage 2b is not cosmetic. Before it existed, `--ay 2026-06` over May's folder
produced a confident report titled "HAZİRAN 2026" full of May figures — ADR-014.

Stage 2 finds each monthly export by glob inside `input_dir`, which is the normal case
and stays the default. `run(chosen={"izin": path})` names one source's file outright
instead, for the month whose exports did not all arrive in the same place (ADR-022). It
bypasses the glob for that one source and nothing else — stage 2b still drops anything
outside the month, so a file pulled in from elsewhere cannot smuggle in another period.

Stage 2b also fails the run when a **single** source read records and kept none of
them (ADR-023). Its older, global form — "no record anywhere is in the month" — passes
when one file of three is the wrong month, and stage 2c cannot catch it either: 2c
builds its source list from the records 2b let through, so a source reduced to nothing
is not there to be flagged. That combination produced a report 72 % short with no
warning of any kind.

Stage 5 is where all business rules live. Stages 2 and 6 are the only ones that
touch Excel. Stages 3–5 never import `openpyxl` — that boundary is what makes the
rules testable without fixture files.

## 3. Module layout

Built (✅) and planned (○):

```
src/mesai/
├── __init__.py        ✅
├── __main__.py        ✅  python -m mesai
├── cli.py             ✅  argument parsing, wiring, exit codes
├── gui/               ✅  tkinter window over the same run(); no business logic
│   ├── app.py         ✅  the shell: header, screen registry, main()
│   ├── nav.py         ✅  the left rail — one item per registered screen
│   ├── rapor.py       ✅  the report screen: folder, period, run, result card
│   ├── people.py      ✅  the people screen: load a data file, filter, select
│   ├── takvim.py      ✅  the calendar screen: mark a month's non-working days
│   ├── settings.py    ✅  what the window remembers; read-modify-write, one place
│   ├── period.py      ✅  `07-2026` -> `2026-07` -> `Temmuz 2026`; pure, tested
│   └── widgets.py     ✅  palette, buttons, and the hand-drawn activity bar
├── snapshot.py        ✅  machine-readable companion: per person, and per
│                          problem DAY (ADR-051)
├── pipeline.py        ✅  the six stages; file discovery, period filter
├── config.py          ✅  YAML -> typed Settings; validates on load
├── models.py          ✅  the vocabulary of the whole system
├── normalize.py       ✅  Turkish casing, collation, identity keys
├── anomalies.py       ✅  anomaly kinds, Turkish labels, collector
├── merge.py           ✅  interval union, cross-site repair
├── readers/
│   ├── base.py        ✅  container abstraction (.xlsx/.xlsm/.xls), header
│   │                      discovery, parsing helpers, glob file discovery
│   ├── roster.py      ✅  employee registry — loaded FIRST, see below
│   ├── macunkoy.py    ✅  flat-log reader
│   ├── teknopark.py   ✅  block-layout reader
│   └── izin.py        ✅  leave reader + remote-work intervals
├── rules/
│   ├── worktime.py    ✅  daily measure (measure()), residual break, midnight crossing
│   ├── shifts.py      ○   automatic shift detection               [Phase 2]
│   ├── overtime.py    ○   daily/weekly/monthly excess, shortfall  [Phase 2]
│   ├── multinet.py    ○   weekly entitlement                      [Phase 2]
│   └── calendar.py    ○   holiday rules beyond labelling          [Phase 2]
├── report/
│   ├── workbook.py    ✅  all six sheets
│   └── styles.py      ✅  fills, fonts, widths, number formats
└── mail/
    ├── recipients.py  ✅  filter + exclusions -> the selection. No widget, no I/O
    ├── render.py      ○                                           [Phase 4]
    └── sender.py      ○                                           [Phase 4]
```

`pipeline.py` was not in the original design — `cli.py` was going to call the stages
directly. Splitting it out means the same `run()` can be driven by a scheduled task
or a Drive trigger in Phase 4 without going through argument parsing.

The planned `report/sheets/` package turned out to be unnecessary: one module per
sheet is more indirection than six functions in `workbook.py` justify. Revisit if
Phase 2 pushes the sheet count past a dozen.

Every module is importable and testable on its own. `cli.py` contains wiring only —
no business logic ever goes there.

## 3b. Two front ends, one pipeline

`cli.py` and `gui/` are both thin shells over `pipeline.run()`. Neither contains a
business rule; both display figures the pipeline computed. Splitting `pipeline.py` out
of `cli.py` was done for exactly this, and the window cost no restructuring when it
arrived.

```
cli.py  ──┐
          ├──> pipeline.run() ──> workbook.xlsx  (people)
gui/    ──┘                   └──> snapshot.json (programs)
```

### The window is a package, not a module

It was one 662-line `gui.py` until 2026-08-18. The split was made **before** the
e-mail step rather than during it, because all the growth points the same way — a
second work face, a list of people, a selection state — and adding that to the class
that already owns the report run produces one object with two jobs.

The shell/screen seam is the load-bearing one. `app.py` owns the toplevel, the header,
the navigation rail and the frame a screen is gridded into; `ReportScreen` owns every
widget inside it, its own state, and its own worker thread.

**A work face is one entry in `app.SCREENS`** — a key, a label, and a callable that
builds it. The rail is generated from that list, so registering a screen is the whole
change; nothing in `app.py` or in any existing screen is edited. `App` holds the list
it was constructed with rather than reading the module global on every call, so what
the rail offers and what `show()` accepts cannot drift apart (and a test can register
a screen without touching module state).

Two behaviours the tests pin down, both of which are bugs if they regress:

- A screen is built **at most once, on first opening**. The mail screen will want a
  snapshot, and loading one for a screen nobody opened is work done on spec.
- Switching away uses `grid_remove`, not `grid_forget`, so a hidden screen keeps its
  state. Losing a chosen folder because someone glanced at another tab is a defect.

`nav.py` is handed labels and hands back the key that was clicked. It knows nothing
about what a screen does, which is what keeps the registry the only thing to edit.

Seven presentation rules the window holds itself to, each of them a defect once:

- **Red means a problem.** "You have not picked a folder yet" is where every run
  starts, so it is not red; and when two of three exports are found, the two that were
  found are not painted in the colour of the one that was not.
- **Nothing may look further along than it is.** `ttk.Progressbar` draws a stub of
  filled bar at rest, which on an untouched window read as a job already part-done.
  `widgets.Progress` draws the sweep itself: nothing when idle, accent while running.
  (It also cannot be recoloured through ttk — the vista theme ignores `background`.)
- **Anything written must be reachable.** The result card scrolls, because a run
  against a partial source writes four extra lines per source and the snapshot path is
  last. It used to be printed in full and then clipped off the bottom.
- **Switching screens must not resize the window.** Tk shrink-wraps a toplevel to the
  requested size of whatever it is showing, and the two screens do not ask for the
  same height — so opening `Kişiler` used to snap the window down and going back threw
  it up again. `App._fit` grows the window to fit and never shrinks it (ADR-038).
- **A list that was replaced starts at its top.** A canvas keeps its scroll offset when
  its rows are destroyed and rebuilt, so a 2-person filter inherited a 60-person
  filter's position and showed an empty box. Reset is tied to the set of names shown,
  not to repainting: re-ticking the same people keeps its place (ADR-038).
- **A long list is a Treeview, not a frame of widgets.** 171 people meant 856 widgets
  and 58 ms per scroll step, because tk repositions every one of them; the rows smeared
  over each other while dragging. A Treeview draws text — 17.7 ms a step, 20 ms to
  redraw the list (ADR-039).
- **One gesture, one meaning.** The wheel scrolls the list from wherever the focus
  happens to be, and it can no longer step the filter box — ttk's own binding did that,
  silently reselecting who was listed and dropping the removals made by hand (ADR-039).
- **A default errs towards including somebody, not leaving them out.** The note
  selection stores which notes are switched OFF, so a note added later counts without
  anybody being told. On a list that decides who gets contacted, one person too many is
  a correction and one too few is silence (ADR-048).
- **Nothing is lost by closing the window.** A screen with unsaved work grows an
  `unsaved()` method; the shell asks before destroying the toplevel and knows nothing
  else about it. The calendar's month switch already asked, and the X — the route
  nobody thinks about — did not (ADR-042).

`rapor.py` keeps its Turkish name deliberately: `gui/report.py` would read as a
sibling of `mesai/report/`, the package that writes the workbook, which it is not.

`period.py` sits outside any one screen because a month is not a report-screen
concept — anything that reports on a period needs the same parsing and label. It is
the one part of the window with real logic in it, and it is tested without a display.
`places.py` is the same shape for a different question: where generated files go on
this machine, and what the month's folder is called (ADR-024).

**The workbook is never read back.** Anything downstream — the mail step, a future
"use last month's report" screen — loads the snapshot. The workbook is a presentation
artifact: `HH:MM` strings, merged cells, and no e-mail column by deliberate choice. It
also changes shape when a rule changes, as it did on 2026-08-17. See `snapshot.py`.

The window deliberately has **no e-mail item in the rail yet** — the rail lists only
screens that exist. Modularity lives in the module boundaries and in the registry, not
in a visible placeholder a user would have to ignore: an entry HR cannot press reads as
a promise. `snapshot.py` already answers "who has which problem", which is what such a
screen would need.

Anything that runs the pipeline must do so **off the UI thread** — it takes seconds,
and Windows will label a blocked window "not responding".

## 3c. Test surface

| File | Covers |
| --- | --- |
| `test_end_to_end.py` | **the whole pipeline** — four synthetic workbooks in, workbook + snapshot out |
| `test_readers.py` | each source layout and its documented defects |
| `test_worktime.py` | the daily measure and the residual break, hand-computed |
| `test_merge.py` | cross-site union, repair, remote precedence, short days |
| `test_snapshot.py` | the round trip the mail step depends on |
| `test_report.py` | that a workbook can actually be written, for every severity |
| `test_takvim_file.py` | editing the holiday list without losing the file's comments |
| `test_gui.py` | the window's period parsing, folder check, what it remembers, screen navigation, and the people screen's wiring |
| `test_recipients.py` | who a filter admits, minus who was removed — the rule, without a window |
| `test_config.py` | that the fixture has not drifted from the shipped config |
| `test_pipeline.py` | period filtering, file discovery, coverage |
| `builders.py` | synthetic workbook builders — **not** a test file |

`test_end_to_end.py` was the last one written and it closed a real hole: until then
nothing called `pipeline.run()`, so "does the assembled thing still work?" was answered
only by a human running it against `data/` — which is git-ignored and therefore
unreachable from any automated run. It builds a deliberately unpleasant month (missing
punch, midnight crossing, dual-site day, nominal placeholder colliding with a remote
declaration, short day) and asserts the hand-computed total.

Its first version asserted the month was complete and failed; the coverage guard was
right and the assumption was wrong. That assertion was inverted and now tests ADR-020
end to end.

**Builders live in one place.** `test_readers.py` used to define its own copies, and the
two had already diverged on a header name. Layout knowledge belongs in `builders.py`
only — the same lesson as the duplicated impact-text map that broke report writing.

## 4. Core types (`models.py`)

Frozen dataclasses. Immutability is deliberate: a stage returns new objects rather
than editing what it was given, so a bug cannot travel backwards through the
pipeline.

Kept in sync with `models.py` — if they disagree, the code is right and this is stale.

```python
NameKey = tuple[str, str]     # (first token, last token), ASCII-folded

@dataclass(frozen=True)
class PunchRecord:
    """One raw row from one source. Faithful to the source, warts included."""
    source: str               # "macunkoy" | "teknopark" | "izin"
    source_row: int           # for traceability back to the original file
    raw_name: str
    key: NameKey              # resolved at read time, aliases applied
    date: date
    entry: datetime | None    # None is a real, expected state
    exit: datetime | None
    badge_id: str | None = None
    department: str | None = None
    reported_duration: str | None = None   # source's own value; cross-check only
    tag: str | None = None    # "uzaktan" for remote-work intervals

@dataclass(frozen=True)
class Employee:
    key: NameKey              # ADR-010
    display_name: str         # LONGEST observed spelling — carries middle names
    personnel_no: str | None  # from the leave export only, informational
    department: str | None    # roster first, attendance file as fallback
    job_title: str | None     # roster only
    facility: str | None      # "DEICO TESİS" | "MACUNKÖY TESİSİ" — home site
    email: str | None         # roster only; required for Phase 4
    in_roster: bool           # False is legitimate: a leaver who worked that month
    sources: frozenset[str]   # which files this person appeared in

@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    sources: frozenset[str]

@dataclass(frozen=True)
class WorkDay:
    key: NameKey              # not the Employee object — keeps merge.py free of it
    date: date
    intervals: tuple[Interval, ...]   # already merged
    gross: timedelta          # the MEASURED day per settings.daily_hours (ADR-015);
                              # by default last exit - first entry, so NOT
                              # necessarily the sum of `intervals`
    break_deduction: timedelta        # residual break, ADR-008 — zero while ADR-016
    net: timedelta                    # == gross whenever the deduction is off
    tags: frozenset[str]      # "gece-geçişi", "çapraz-eşleşti", "uzaktan", ...
    # interval_total / gap_total are derived properties: presence, and the in-day
    # gap the envelope rule pays. The Kontrol guard reconciles against them.

@dataclass(frozen=True)
class Anomaly:
    kind: AnomalyKind         # StrEnum; Turkish label + severity in anomalies.py
    source: str
    source_row: int           # row number in the ORIGINAL file — HR opens and looks
    key: NameKey | None
    raw_name: str
    date: date | None
    raw_entry: str            # as recorded, for the report
    raw_exit: str
    detail: str

@dataclass(frozen=True)
class MonthSummary:
    employee: Employee
    period: str               # "2026-05"
    gross: timedelta
    net: timedelta
    worked_days: int
    remote_days: float        # counted as worked, ADR-007
    leave_days: float         # genuine absence only
    anomaly_count: int
    has_attendance: bool      # False -> blank cells, not zeros
    notes: tuple[str, ...]
```

Two details that carry weight:

`PunchRecord.entry` being `None` is not an error condition — it is the single most
common shape in the Macunköy file, and the type must say so.

`MonthSummary.has_attendance` exists so the report can leave cells **blank** rather
than writing `0:00`. "Worked zero hours" and "no data for this person" are different
statements and the sheet must not conflate them.

`RunStats` (mutable, the one exception) carries reconciliation counters to the
`Kontrol` sheet: rows read and records built per file, excluded badges, accepted
interval count and total, out-of-period counts, roster export date, roster duplicates.

## 5. Readers

There is no `Reader` Protocol. Each reader returns what its file actually yields, and
`pipeline.py` wires them explicitly:

```python
macunkoy.read(path, settings) -> (records, anomalies, rows_read, excluded_badges)
teknopark.read(path, settings) -> (records, anomalies, rows_read)
izin.read(path, settings)      -> (leave, remote_punches, anomalies, rows, subtotals)
roster.read(path)              -> (entries_by_key, duplicate_notes)
```

A uniform signature was the original plan and it was wrong: the counters differ per
file because the reconciliation panel needs file-specific numbers (excluded badge
rows only exist for Macunköy, skipped subtotal rows only for the leave export). A
Protocol would have forced those into a bag of optional fields.

Rules that do hold for every reader:

- A reader is **faithful**. It does not fix, clean, or interpret. Negative
  durations, missing punches, and visitor badges all pass through untouched.
  Correction happens in `rules/`, once, for all sources.
- A reader **never raises** on bad data. Unparseable rows become anomalies.
  It raises only when the file itself is unopenable or the layout is unrecognised —
  a structural change in a monthly export must fail loudly, not quietly halve
  someone's hours.
- A reader **validates its own layout** before parsing: header text, expected
  column offsets, the marker string it depends on. Vendors change export formats
  without warning.

Format-specific knowledge is fully contained per reader — see
`docs/DATA-SOURCES.md` §1 and §2. Notably, `teknopark.py` must parse entry/exit as
**strings** (`%d.%m.%Y %H:%M`), and must not use `read_only=True` because of the
4 105 merged ranges.

### The roster reader is different

`roster.py` does not return `PunchRecord`s. It builds the `Employee` index that
stage 3 resolves everything else against, and it runs **before** the other readers.

It is the one reader that **must** raise:

- if a repeated `(first, last)` key belongs to two **different** identities
  (ADR-010) — that would silently merge two people's payroll hours. A repeat with the
  same contact number or e-mail is one person with two accounts and is deduplicated
  instead (ADR-013)
- if no sheet carries the expected columns, `E-posta` included, since Phase 4
  depends on it

It finds its sheet **by header columns, not by name**, and derives column positions
from the header too. The file and sheet get renamed by whoever exports them
(`SYST03_TEMPIASUSERS.xlsx` became `calisan_listesi.xlsx`), and the workbook contains
a second `Sayfa1` with only name and e-mail that must not be picked.

## 6. Configuration

Three YAML files, loaded into typed objects and validated at startup — a typo in a
config key must fail immediately, not produce a wrong number silently.

| File | Holds |
| --- | --- |
| `config/settings.yaml` | shifts, lunch, plausibility bounds, overtime thresholds, Multinet counts |
| `config/takvim-2026.yaml` | public holidays, weekly rest day definition |
| `config/personel.yaml` | exclusion prefixes, name aliases |

`personel.yaml` is the human escape hatch. When identity resolution fails, a person
adds an alias there — nobody edits code and nobody adds a fuzzy matcher.

It is **git-ignored**, because its aliases have to match the source files' real
spellings and therefore cannot be pseudonymised. `config/personel.example.yaml` is
committed in its place, and `config.py` points at it when the real file is missing.
See AGENTS.md §2.3.

## 7. Anomalies

A first-class output, not a log. Collected through the pipeline into a single list
and written to a report sheet with a link back to `(source, source_row)` so HR can
open the original file and look.

Kinds (`AnomalyKind`, a `StrEnum`): `MISSING_ENTRY`, `MISSING_EXIT`,
`EMPTY_RECORD`, `NEGATIVE_DURATION`, `IMPLAUSIBLE_DURATION`, `SUSPICIOUS_SHORT`,
`CROSS_SITE_EXTENDED`, `UNRESOLVED_IDENTITY`, `DURATION_MISMATCH`,
`NO_ATTENDANCE_DATA`, `MULTI_DAY_REMOTE`, `UNPARSEABLE_ROW`.

Each kind carries a Turkish label and a severity — `excluded` (contributed zero
hours) or `included` (counted, but look at it) — which drives the report's colour
coding. Labels live with the enum in `anomalies.py`, not in the report layer.

Actual volume: **245 rows for May 2026, 421 for June**, dominated by `MISSING_EXIT`.
That is the true state of the input data, and hiding it would be the actual bug.

## 8. Report writing

`openpyxl` only. Six sheets, one function each in `workbook.py`, taking computed
data and writing cells. No sheet function computes anything.

`Aylık Özet`, `Günlük Detay`, `İnceleme Listesi`, `Şüpheli Kayıtlar`, `İzin Özeti`,
`Kontrol` — see `OUTPUT-SPEC.md`. Every user-facing ordering goes through
`normalize.sort_key()` for Turkish alphabetical order; Python's default sort puts
Ç Ğ İ Ö Ş Ü after Z.

Styling lives in `styles.py`: named fills, fonts, column widths, and number formats
in one place, because the colour-coding requirement in `PRODUCT.md §9` will spread
otherwise.

Output is written to a temporary file and moved into place on success, so a crash
mid-write cannot leave HR with a half-written workbook that opens fine. If the target
is locked — open in Excel, which happens every month — it raises `ReportLocked` and
the CLI exits 4 with a plain instruction, leaving the existing file untouched.

## 9. Dependencies

Deliberately minimal:

| Package | Why |
| --- | --- |
| `openpyxl` | `.xlsx` read/write. Pinned to 3.1.5 in `environment.yml`. |
| `PyYAML` | config. Pinned to 6.0.3. |
| `pytest` | dev only, version range not pinned — it cannot affect output |

Runtime versions are pinned because they can change the numbers: a future `openpyxl`
that parses dates differently would shift the report silently. Dev tools are not.

No `pandas`. The data is ~1 900 rows; the hard parts are irregular block layouts
and interval merging, neither of which a dataframe helps with, and dataframes make
the `None`-heavy, per-record-traceability requirements harder, not easier.

Standard library only for everything else: `datetime`, `dataclasses`, `pathlib`,
`argparse`, `calendar`, `warnings`, `smtplib`/`email` in Phase 4.

Python 3.11+ required (`StrEnum`). Verified on 3.14.6 and 3.12.13; the conda
environment pins 3.12.

## 10. Testing

96 tests, all passing.

```
tests/
├── conftest.py           # a Settings fixture mirroring config/settings.yaml
├── test_normalize.py     # Turkish casing, İ/ı traps, collation, identity keys
├── test_merge.py         # interval union: overlap, touch, gap, containment,
│                         #   multi-source, split day, cross-site repair
├── test_worktime.py      # midnight crossing, residual break, plausibility bounds
├── test_readers.py       # each reader against a synthetic workbook built in-test
└── test_pipeline.py      # period filter, file discovery, roster lookup, CLI args
```

Fixtures are generated in-test with `openpyxl` rather than committed as files, so
there is nothing to keep in sync and no real employee data anywhere. All names are
SYNTHETIC.

Non-negotiable cases, each with a hand-computed expected value:

1. `"İ".lower()` must not be relied upon anywhere — assert normalization directly
2. Midnight crossing: `23:59:42 → 08:07:06` = `8:07`
3. Interval union: `07:09–19:45` ∪ `13:20–14:05` = `12:36`, **not** `13:21`
4. Touching intervals merge; a real gap does not
5. Split day sums: `08:21–13:48` + `14:30–18:00` = `8:57` gross
6. One-sided record contributes zero and produces exactly one anomaly
7. Subtotal rows in the leave export are skipped (else every total doubles)
8. The reconciliation invariant in `DOMAIN-RULES.md §6`
9. `(first, last)` matching: `AHMET CAN SINAMA` resolves to roster `AHMET SINAMA`
10. A roster containing two people with the same `(first, last)` key **raises**
11. Residual break: a 42-minute gap yields a 3-minute deduction, not 45 and not 0
12. A remote-work interval overlapping a badge interval is counted once and tagged

13. `--ay` outside 01-12, or over a folder holding another month, **fails**
14. A lone unnamed spreadsheet in the roster folder is accepted; two are not
15. The roster sheet is found by columns even when renamed, and `Sayfa1` is not picked

A golden-file test over the real data is valuable but **cannot be committed**
(personal data). The practical substitute is running two real months and checking the
`Kontrol` sheet: May and June 2026 both reconcile, and all 110 Teknopark blocks match
the source system's own totals in both.

## 11. Deployment

Phase 1–3: run by hand. `rapor.cmd` locates the conda environment itself, so no
activation and no fixed working directory are needed — which is also what makes it
schedulable without further work.

Exit codes: 0 = clean, 2 = bad input/config, 3 = file layout changed, 4 = output
locked, **5 = report written but a source does not cover the period** (ADR-020). A
scheduled job must treat anything non-zero as needing a human.

Phase 4: Windows Task Scheduler invokes `rapor.cmd` monthly. Non-zero exit codes must
raise an alert (2 input, 3 layout, 4 locked output, 9 missing environment) — a monthly
job that fails silently is not noticed until payroll. The mail step reads SMTP
credentials from environment variables, never from a committed file, and defaults to
`--dry-run`. Sending to real people must require an explicit flag.

Drive ingestion is deferred and undecided — ROADMAP.md Q21.
