# ARCHITECTURE.md — Modules, Data Flow, and Why

**Status: proposed. No code exists yet.** This is the design to be approved before
implementation begins.

---

## 1. Shape of the system

A **command-line batch tool**. One command, one month, one workbook out.

```
python -m mesai rapor --ay 2026-05
```

Not a service, not a GUI, not a notebook. Reasons: it runs once a month; the output
is a file HR opens in Excel; it must be schedulable (Windows Task Scheduler) for the
Phase 4 e-mail job; and a CLI is trivially testable.

## 2. Pipeline

Six stages, each a pure function of the previous one's output. No stage reaches
back. No stage mutates global state.

```
  config/*.yaml            data/raw/2026-05/*.xlsx
        |                            |
        v                            v
   [1] load config          [2] read  -> PunchRecord[]      (one reader per file)
        |                            |
        +------------+---------------+
                     v
              [3] normalize  -> identities resolved, non-employees excluded
                     v
              [4] merge      -> WorkDay[]  (interval union per person-day)
                     v
              [5] compute    -> gross/net, anomalies    [Phase 2: FM, Multinet]
                     v
              [6] report     -> data/out/2026-05/mesai-raporu-2026-05.xlsx
                                                  [Phase 4: e-mail]
```

Stage 5 is where all business rules live. Stages 2 and 6 are the only ones that
touch Excel. Stages 3–5 never import `openpyxl` — that boundary is what makes the
rules testable without fixture files.

## 3. Module layout

```
src/mesai/
├── __init__.py
├── __main__.py           # python -m mesai
├── cli.py                # argument parsing, wiring, exit codes
├── config.py             # YAML -> typed Settings; validates on load
├── models.py             # the vocabulary of the whole system
├── normalize.py          # Turkish-safe name normalization, identity resolution
├── readers/
│   ├── __init__.py       # registry: file pattern -> reader
│   ├── base.py           # Reader protocol
│   ├── roster.py         # IAS employee registry — loaded FIRST, see below
│   ├── macunkoy.py       # flat-log reader
│   ├── teknopark.py      # block-layout reader
│   └── izin.py           # leave reader
├── merge.py              # interval union, cross-site repair
├── rules/
│   ├── worktime.py       # gross/net, lunch, midnight crossing     [Phase 1]
│   ├── shifts.py         # automatic shift detection               [Phase 2]
│   ├── overtime.py       # daily/weekly/monthly excess, shortfall  [Phase 2]
│   ├── multinet.py       # weekly entitlement                      [Phase 2]
│   └── calendar.py       # holidays, weekly rest days              [Phase 2]
├── anomalies.py          # anomaly types and collector
├── report/
│   ├── workbook.py       # orchestrates sheet writing
│   ├── sheets/           # one module per output sheet
│   └── styles.py         # fills, fonts, widths, number formats
└── mail/                 # [Phase 4]
    ├── render.py
    └── sender.py
```

Every module is importable and testable on its own. `cli.py` contains wiring only —
no business logic ever goes there.

## 4. Core types (`models.py`)

Frozen dataclasses. Immutability is deliberate: a stage returns new objects rather
than editing what it was given, so a bug cannot travel backwards through the
pipeline.

```python
@dataclass(frozen=True)
class PunchRecord:
    """One raw row from one source file. Faithful to the source, warts included."""
    source: str               # "macunkoy" | "teknopark"
    source_row: int           # for traceability back to the original file
    raw_name: str
    badge_id: str | None
    department: str | None
    date: date
    entry: datetime | None    # None is a real, expected state
    exit: datetime | None
    reported_duration: str | None   # source's own value; cross-check only

@dataclass(frozen=True)
class Employee:
    key: tuple[str, str]      # (first token, last token), normalized — ADR-010
    display_name: str         # full name as it appears in the transaction files
    roster_name: str | None   # abbreviated form from the registry, if matched
    personnel_no: str | None  # from the leave export only, informational
    department: str | None    # roster first, attendance file as fallback
    job_title: str | None     # roster only
    facility: str | None      # "DEICO TESİS" | "MACUNKÖY TESİSİ" — home site
    email: str | None         # roster only; required for Phase 4
    in_roster: bool           # False is legitimate: a leaver who worked in May

@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    sources: frozenset[str]

@dataclass(frozen=True)
class WorkDay:
    employee: Employee
    date: date
    intervals: tuple[Interval, ...]   # already merged
    gross: timedelta
    net: timedelta
    tags: frozenset[str]              # "gece-geçişi", "çapraz-eşleşti", ...

@dataclass(frozen=True)
class Anomaly:
    kind: AnomalyKind
    employee_key: str | None
    date: date | None
    source: str
    source_row: int
    detail: str

@dataclass(frozen=True)
class MonthSummary:
    employee: Employee
    period: str               # "2026-05"
    gross: timedelta
    net: timedelta
    worked_days: int
    leave_days: float
    anomaly_count: int
```

`PunchRecord.entry` being `None` is not an error condition — it is the single most
common shape in the Macunköy file, and the type must say so.

## 5. Readers

```python
class Reader(Protocol):
    name: str
    def read(self, path: Path) -> tuple[list[PunchRecord], list[Anomaly]]: ...
```

Rules:

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

- if the `(first, last)` key is not unique across the roster (ADR-010) — a collision
  would silently merge two people's payroll hours
- if the `E-posta` column is missing, since Phase 4 depends on it

It reads the `TEMPIASUSERS` sheet. The `Sayfa1` sheet is a derived name/e-mail pair
list carrying no extra information; ignore it.

## 6. Configuration

Three YAML files, loaded into typed objects and validated at startup — a typo in a
config key must fail immediately, not produce a wrong number silently.

| File | Holds |
| --- | --- |
| `config/settings.yaml` | shifts, lunch, plausibility bounds, overtime thresholds, Multinet counts |
| `config/takvim-2026.yaml` | public holidays, weekly rest day definition |
| `config/personel.yaml` | exclusion prefixes, name aliases, per-person overrides |

`personel.yaml` is the human escape hatch. When identity resolution fails, a person
adds an alias there — nobody edits code and nobody adds a fuzzy matcher.

## 7. Anomalies

A first-class output, not a log. Collected through the pipeline into a single list
and written to a report sheet with a link back to `(source, source_row)` so HR can
open the original file and look.

Kinds: `MISSING_ENTRY`, `MISSING_EXIT`, `EMPTY_RECORD`, `NEGATIVE_DURATION`,
`IMPLAUSIBLE_DURATION`, `SUSPICIOUS_SHORT`, `CROSS_SITE_EXTENDED`,
`UNRESOLVED_IDENTITY`, `DURATION_MISMATCH`, `LEAVE_WITHOUT_ATTENDANCE`.

Expected volume for May 2026: roughly 400 rows, dominated by `MISSING_EXIT`.
That is the true state of the input data, and hiding it would be the actual bug.

## 8. Report writing

`openpyxl` only. Every sheet is its own module under `report/sheets/`, taking
computed data and writing cells. No sheet module computes anything.

Styling lives in `styles.py`: named fills, fonts, column widths, and number formats
in one place, because the colour-coding requirement in `PRODUCT.md §9` will spread
otherwise.

Output is written to a temporary file and moved into place on success, so a crash
mid-write cannot leave HR with a half-written workbook that opens fine.

## 9. Dependencies

Deliberately minimal:

| Package | Why |
| --- | --- |
| `openpyxl` | `.xlsx` read/write. Already verified working (3.1.5). |
| `PyYAML` | config |

No `pandas`. The data is ~1 900 rows; the hard parts are irregular block layouts
and interval merging, neither of which a dataframe helps with, and dataframes make
the `None`-heavy, per-record-traceability requirements harder, not easier.

Standard library only for everything else: `datetime`, `dataclasses`, `pathlib`,
`argparse`, `smtplib`/`email` in Phase 4.

Python 3.14.6 is installed and confirmed.

## 10. Testing

```
tests/
├── test_normalize.py     # Turkish casing, İ/ı traps, alias resolution
├── test_merge.py         # interval union: overlap, touch, gap, containment,
│                         #   multi-source, split day
├── test_worktime.py      # midnight crossing, lunch deduction, plausibility bounds
├── test_readers/         # each reader against a small synthetic workbook
└── fixtures/             # SYNTHETIC names only — never real employees
```

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

A golden-file test over the real May 2026 data is valuable but **cannot be
committed** (personal data). Keep it as a local-only check gated on the presence of
`data/raw/`.

## 11. Deployment

Phase 1–3: run by hand from the repository.
Phase 4: Windows Task Scheduler invokes the CLI monthly; the mail step reads SMTP
credentials from environment variables, never from a committed file, and defaults
to `--dry-run` (render, do not send). Sending to 162 real people must require an
explicit flag.
