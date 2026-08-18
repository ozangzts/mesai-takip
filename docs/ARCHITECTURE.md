# ARCHITECTURE.md — Modules, Data Flow, and Why

**Status: BUILT.** Phase 1 is implemented, 96 tests pass, and two months (May and
June 2026) have been generated with the reconciliation invariant holding. Phase 2/3/4
modules listed below are still design.

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
           [3] normalize          -> identities resolved against the roster,
                  |                   non-employee badges excluded
                  v
           [4] merge              -> WorkDay[]  (interval union per person-day)
                  v
           [5] compute            -> gross/net, anomalies  [Phase 2: FM, Multinet]
                  v
           [6] report             -> data/out/2026-05/mesai-raporu-2026-05.xlsx
                                                        [Phase 4: e-mail]
```

Stage 2b is not cosmetic. Before it existed, `--ay 2026-06` over May's folder
produced a confident report titled "HAZİRAN 2026" full of May figures — ADR-014.

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
├── pipeline.py        ✅  the six stages; file discovery, period filter
├── config.py          ✅  YAML -> typed Settings; validates on load
├── models.py          ✅  the vocabulary of the whole system
├── normalize.py       ✅  Turkish casing, collation, identity keys
├── anomalies.py       ✅  anomaly kinds, Turkish labels, collector
├── merge.py           ✅  interval union, cross-site repair
├── readers/
│   ├── base.py        ✅  parsing helpers, glob-based file discovery
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
└── mail/              ○                                           [Phase 4]
    ├── render.py
    └── sender.py
```

`pipeline.py` was not in the original design — `cli.py` was going to call the stages
directly. Splitting it out means the same `run()` can be driven by a scheduled task
or a Drive trigger in Phase 4 without going through argument parsing.

The planned `report/sheets/` package turned out to be unnecessary: one module per
sheet is more indirection than six functions in `workbook.py` justify. Revisit if
Phase 2 pushes the sheet count past a dozen.

Every module is importable and testable on its own. `cli.py` contains wiring only —
no business logic ever goes there.

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
`NO_ATTENDANCE_DATA`, `REMOTE_OVERLAP`, `MULTI_DAY_REMOTE`, `UNPARSEABLE_ROW`.

Each kind carries a Turkish label and a severity — `excluded` (contributed zero
hours) or `included` (counted, but look at it) — which drives the report's colour
coding. Labels live with the enum in `anomalies.py`, not in the report layer.

Actual volume: **245 rows for May 2026, 421 for June**, dominated by `MISSING_EXIT`.
That is the true state of the input data, and hiding it would be the actual bug.

## 8. Report writing

`openpyxl` only. Six sheets, one function each in `workbook.py`, taking computed
data and writing cells. No sheet function computes anything.

`Aylık Özet`, `Günlük Detay`, `Sorulacaklar`, `Şüpheli Kayıtlar`, `İzin Özeti`,
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

Phase 4: Windows Task Scheduler invokes `rapor.cmd` monthly. Non-zero exit codes must
raise an alert (2 input, 3 layout, 4 locked output, 9 missing environment) — a monthly
job that fails silently is not noticed until payroll. The mail step reads SMTP
credentials from environment variables, never from a committed file, and defaults to
`--dry-run`. Sending to real people must require an explicit flag.

Drive ingestion is deferred and undecided — ROADMAP.md Q21.
