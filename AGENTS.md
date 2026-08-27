# AGENTS.md — Working Agreement for AI Agents

> **This file is the entry point for any agent working on this repository.**
> Read it fully before touching anything. Then read the doc in `docs/` that
> matches your task.
>
> Picking up mid-project? `docs/HANDOVER.md` says what is in flight and which answers
> are being waited on. It holds no durable knowledge — if it is older than the last
> commit, trust the other docs instead.

---

## 0. Keep this file up to date

**You are required to update this file (and the relevant doc in `docs/`) whenever
you change something it describes.** This is not optional housekeeping — the next
agent has no memory of your session and will act on whatever is written here.

Update when you:

- add, remove, or rename a module, config key, or CLI command
- change a business rule (work hours, overtime, Multinet, shift boundaries)
- discover a new quirk or defect in a source Excel file
- make a decision that a future agent could plausibly reverse by accident
- complete a roadmap phase

Where things go:

| What changed | Update |
| --- | --- |
| Business rule | `docs/DOMAIN-RULES.md` **and** `docs/KURALLAR.md` |
| Source file structure or quirk | `docs/DATA-SOURCES.md` |
| Module layout, data flow | `docs/ARCHITECTURE.md` |
| A choice with alternatives | `docs/DECISIONS.md` (append a new ADR, never edit an old one) |
| Output workbook layout | `docs/OUTPUT-SPEC.md` |
| Phase status | `docs/ROADMAP.md` |
| What is in flight right now | `docs/HANDOVER.md` — short, and stale by design |
| Anything an agent needs day one | this file |

`docs/KURALLAR.md` is the same rules in Turkish, written for whoever is asked to
justify a number — a manager, HR, an employee querying their hours. It carries no
repository references and no jargon. A rule change means editing both it and
`DOMAIN-RULES.md`; a rule the operator cannot explain to their manager is a rule that
will be argued with instead of applied.

If a change spans several, update all of them. Stale docs here are worse than no
docs, because they are trusted.

---

## 1. What this project is

DEICO's HR team receives raw badge-terminal exports every month and currently
turns them into a payroll-facing overtime report **by hand**. This repository
automates that: read the raw exports, compute per-employee working time, and
write one clean Excel workbook.

The long-term target is defined by the customer requirements in
`docs/PRODUCT.md` (derived from `MEYER Programı Toplantı İçeriği 1.docx`):
overtime tracking, automatic shift detection, Multinet entitlement, holiday work,
and eventually automated e-mail delivery of per-employee summaries.

**Scope right now is deliberately narrow — see `docs/ROADMAP.md`.** Phase 1 is
*total hours worked per employee per month*, nothing else. Do not implement
Phase 2+ rules unless asked, but *do* leave seams for them.

---

## 2. Non-negotiable constraints

### 2.1 No AI at runtime — ever

The pipeline must be **fully deterministic**. No LLM call, no heuristic that
"usually works", no fuzzy guessing in the hot path. Same input file → byte-identical
output, every time.

Reason: these numbers feed payroll and will later be e-mailed directly to employees.
A wrong number is a real problem for a real person. Everything must be reproducible
and auditable by a human with a calculator.

Practical consequences:

- Name matching uses an explicit alias table, not fuzzy string distance.
  If a name does not resolve, it goes to the anomaly sheet — it is **not** guessed.
- Missing punches are never invented. See ADR-003.
- Any rule with a threshold lives in `config/`, not hard-coded in a module.

### 2.2 Never silently drop or fabricate a record

Every input row must end up in exactly one of: a computed total, or the anomaly
report. A row that vanishes is a bug. A row that gets an invented value is a
worse bug. When in doubt, surface it to the human.

### 2.3 This repository handles personal data

The source files contain real names, badge IDs, departments, daily movements, and
medical/parental leave records for ~162 identifiable employees. Treat accordingly:

- `data/` is git-ignored. **Never commit a real export.**
- Never send file contents to an external service.

### No real employee data in committed files — including docs and tests

This repository has a GitHub remote. Every committed file must be safe to publish.

**Names, e-mail addresses, logins, personnel numbers and card numbers in `docs/`,
`tests/` and code comments are pseudonyms.** Surnames are drawn from an obviously
synthetic set (`DENEME`, `ÖRNEK`, `NUMUNE`, `TASLAK`, `MİSAL`, `SINAMA`) and numbers
sit outside the real range (`88xx`, `9xxx`, `SN1000xx`).

The pseudonyms **preserve structure**, which is why the examples still teach what
they need to: a Turkish-character pair still differs only in that character
(`AYŞE DENEMEÇİ` / `AYŞE DENEMECİ`), a middle-name pair still differs only in the
middle name (`AHMET SINAMA` / `AHMET CAN SINAMA`), a married-surname pair still
differs only in the added surname (`SEDA DENEME` / `SEDA DENEME ÖRNEK`).

The pseudonym → real mapping lives in `docs/ISIM-ESLESMELERI.local.md`, which
`.gitignore` keeps out of the repository (`*.local.md`).

**Two files cannot be pseudonymised and are therefore git-ignored:**

| File | Why | Committed instead |
| --- | --- | --- |
| `config/personel.yaml` | Its aliases must match the source files' real spellings exactly | `config/personel.example.yaml` |
| `docs/ISIM-ESLESMELERI.local.md` | It *is* the mapping | nothing |

**A fresh clone is therefore incomplete and fails silently.** The committed example
has an empty alias table, so the five real cases (four married surnames, one
abbreviated given name) stop resolving and those people appear as two rows each —
with no warning, because an unresolved variant is indistinguishable from two
different employees. `config/personel.yaml` has to be copied across by hand.

The check is the report's `Kontrol` sheet, section 7: it lists every alias in effect.
Empty there means the table did not load.

**Before committing**, re-check that no real name, address, login or number leaked
in — a one-off script, not part of the pipeline. Two things about how to run it, both
learned by it failing:

- Scan **every committed file** (`git ls-files`), not only the lines this change added.
  A name committed months ago is just as public, and the added-lines version had been
  reporting clean over **four real surnames** sitting in this file, `DOMAIN-RULES.md`,
  `normalize.py`, `personel.example.yaml`, `DECISIONS.md` and `test_normalize.py`. They
  were replaced with their pseudonyms on 2026-08-26.
- Load the names from **`docs/ISIM-ESLESMELERI.local.md` as well as the roster**, and do
  not skip short ones: one of the four was four letters and a length filter had been
  dropping it.
- **Do not name them when writing this up.** The first version of this very paragraph
  listed the four surnames, which put them back where they had just been taken from.

Turkish words collide with surnames (`alır`, `uzun`, `örnek`, and `elif` is a Python
keyword), so match whole words on the folded text and expect noise. A doc example never
needs a real person to make its point.

### 2.4 Turkish text will break naive code

- `"İ".lower()` in Python returns `"i̇"` (i + U+0307 combining dot), **not** `"i"`.
  `"I".lower()` returns `"i"`, but Turkish wants `"ı"`. Never use bare
  `.lower()` / `.upper()` / `.casefold()` on employee names. Use the
  normalization helper in `src/mesai/normalize.py`.
- Always read and write files as UTF-8 explicitly.
- Sheet names, column headers, and report labels are **Turkish** and stay Turkish —
  HR reads them. Only code, comments, and `docs/` are English.
- Input filenames contain non-ASCII characters (`Macunköy Mayıs Mesai
  giriş-çıkış.xlsx`); always quote paths in shell commands.

---

## 3. Repository layout

Planned structure (see `docs/ARCHITECTURE.md` for the reasoning):

```
mesai-takip/
├── AGENTS.md                  # you are here
├── README.md                  # human-facing, Turkish
├── KULLANIM.txt               # the operator's guide. Ships next to the .exe
├── baslat.py                  # the FROZEN entry point. Absolute imports only — ADR-079
├── MesaiTakip.spec            # PyInstaller recipe. Resolves conda's DLLs itself
├── derle.cmd                  # test, build, assemble dist/MesaiTakip/
├── pyproject.toml
├── rapor.cmd                  # CLI wrapper, no conda activate needed
├── arayuz.cmd                 # opens the window; double-clickable, no console
├── config/
│   ├── settings.yaml          # rules and thresholds — a rule change is a YAML edit
│   ├── takvim-2026.yaml       # public holidays, weekend definition
│   └── personel.yaml          # alias map, exclusions — GIT-IGNORED, holds real names
├── data/                      # GIT-IGNORED
│   ├── personel/              # employee roster — NOT month-specific
│   ├── raw/2026-05/           # monthly exports, one month per folder
│   └── out/2026-05/           # generated workbooks — what HR opens
│                              # The window writes elsewhere — see below.
├── docs/
│   ├── PRODUCT.md             # what the customer asked for
│   ├── DATA-SOURCES.md        # anatomy + defects of every input file
│   ├── DOMAIN-RULES.md        # the actual business math
│   ├── ARCHITECTURE.md        # modules, data flow, why
│   ├── OUTPUT-SPEC.md         # the report workbook, sheet by sheet
│   ├── DECISIONS.md           # ADR log
│   └── ROADMAP.md             # phases and status
├── src/mesai/
│   ├── cli.py                 # front end 1 — argument parsing, exit codes
│   ├── gui/                   # front end 2 — tkinter window. No business logic.
│   │   ├── app.py             # the shell: header, SCREENS registry, main()
│   │   ├── nav.py             # the left rail — one item per registered screen
│   │   ├── rapor.py           # the report screen
│   │   ├── people.py          # people screen — two panels: filter and pick
│   │   │                      # people left, that person's days right
│   │   ├── period.py          # month parsing and labels — pure, tested
│   │   ├── places.py          # where output goes; the month folder name
│   │   └── widgets.py         # palette and shared widget primitives
│   ├── pipeline.py            # the stages. Both front ends call run().
│   ├── snapshot.py            # writes gonderim-<ay>.json beside the workbook.
│   │                          # Read it, never the workbook.
│   ├── readers/               # one per source file; base.py hides the container
│   ├── mail/                  # who the figures go to, and what they are told
│   │   ├── recipients.py      # the filters — pure, no widget
│   │   ├── message.py         # which days, which note — pure, no SMTP, no wording
│   │   ├── template.py        # the wording, from config/mail-taslagi.yaml
│   │   └── sender.py          # Gmail SMTP. ONE person per call, never a loop
│   ├── rules/                 # the business math
│   └── report/                # the workbook
└── tests/
```

**Current state: Phase 1 complete and running.** 562 tests pass. The layout above is
real: inputs live in `data/raw/<YYYY-MM>/`, reports in `data/out/<YYYY-MM>/`, and
the vendor reference files in `docs/reference/`.

```bash
conda activate mesai
mesai rapor --ay 2026-05          # --girdi defaults to data/raw/2026-05/
python -m pytest
```

Two front ends, both thin shells over `pipeline.run()` — `cli.py` and `gui/`
(tkinter, `arayuz.cmd` to launch). **Neither may contain a business rule.** Adding a
window screen is one entry in `gui/app.py:SCREENS`; the left rail is generated from it.
Only screens that exist are registered — no placeholder items. Every run
also writes `gonderim-<ay>.json` **beside the workbook**, the machine-readable
companion to it. Anything downstream reads that, **never the workbook** — see
`src/mesai/snapshot.py` for why. It holds names, e-mail addresses and hours, so
`gonderim-*.json` is git-ignored wherever it lands.

The two front ends put that pair in different places, deliberately (ADR-024). The CLI
keeps `data/out/<ay>/`. The **window asks**, defaults to the Desktop, remembers the
answer, and makes one folder per month named `2026-06 Rapor` holding both files. A
second run for the same month overwrites in place and says so beforehand (ADR-025). The
output folder is remembered precisely because it is *not* month-specific — the opposite
of the input folder, which is never restored.

Input files are found by glob pattern (`config/settings.yaml:sources`), not by exact
name, so a Drive-synced folder can be pointed at with `--girdi` without renaming
anything. One month per folder is a contract (ADR-014).

Three guards exist specifically to catch the kinds of bug this data produces. Do not
weaken any of them without an ADR:

1. **Reconciliation invariant** — Σ per-person total must equal Σ measured
   person-days. Written to the report's `Kontrol` sheet every run, alongside the
   presence total and the in-day gap total, whose difference it is. Note it is *not*
   "Σ accepted interval durations": in-day gaps are paid since ADR-015, so that older
   form would fail every run by design.
2. **Teknopark block totals** — each block is checked against the file's own
   `Dönemdeki Toplam` figure. This caught a reader that was silently dropping 838 of
   1 607 rows while appearing to succeed. Currently 110/110 agree.
3. **Roster key uniqueness** — a repeated `(first, last)` key belonging to two
   different identities fails the run rather than merging payroll hours (ADR-010,
   ADR-013).
4. **Period coverage** — each attendance source is checked for a *trailing* run of
   expected working days with no records. July 2026's Teknopark export covered only
   1–19 July and every other guard passed: it was complete data about an incomplete
   period. A partial source produces a red banner on `Aylık Özet`, a `Kontrol` section
   and **exit code 5** (ADR-020). Do not check "fewer days than the other source" —
   Teknopark legitimately has none while the office is shut.
5. **Period filter** — `--ay` is a filter, not a label. Records outside the month are
   dropped and counted; if *no* record falls inside the month, the run fails. A
   source pattern matching two files also fails. One month per input folder is a
   contract (ADR-014).

   A month whose files are **not all in one folder** is a different thing, and is
   allowed: `run(chosen={...})` names one source's file outright and bypasses the glob
   for that source only (ADR-022).

6. **Wrong-month source** — a source that **read records but kept none** inside the
   period fails the run (ADR-023). The check in 5 is global and only fires when
   *every* source is the wrong month; one wrong file among three passed it, because
   the others kept records. Measured on the real May data with June's Teknopark export
   substituted: the run succeeded, reported 4 869:54 against a true 17 103:58, and said
   nothing — the coverage check in 4 never saw the source, because it builds its list
   from records that survived the filter.

   The distinction is **read nothing** (fine — Teknopark has no rows while the office
   is shut) versus **read rows, kept none** (the wrong file). Do not weaken it into a
   count comparison; that is the check §4 explicitly forbids.

7. **Blank working day** — an expected working day on which **no source** recorded
   anybody fails the run (exit code 5, ADR-057). This is the mid-period hole §4 cannot
   see: that check looks only at a *trailing* run, because one source being empty proves
   nothing. Both being empty cannot be an ordinary working day. Holidays leave
   `expected_workdays` before it runs, so a marked holiday can never trigger it, and
   re-running all three months with every holiday removed produced no alarm at all —
   Macunköy production runs on holidays. Never turn this into a per-source check; that
   is §4 again.

---

## 4. The one thing most likely to trip you up

**76 employees appear in *both* the Macunköy and the Teknopark export for May 2026.**

They are not duplicates in the naive sense — a person badges into the Teknopark
building for a full day *and* badges at the Macunköy site during a mid-day visit.
Summing both files without reconciliation double-counts these people.

Worked example (verified in the real data):

```
ZEYNEP DENEME, 2026-05-21
  Teknopark : 07:09 -> 19:45   (complete, 12h36)
  Macunköy  : entry present, exit MISSING
  Correct answer is NOT 12h36 + <whatever>. The intervals must be unioned.
```

The resolution is interval union per employee-day — see ADR-001 and
`docs/DOMAIN-RULES.md §4`. If you are writing anything that aggregates hours and
you have not read that section, stop and read it.

The IAS roster confirmed why this happens: **75 of those 79 people are based at
`DEICO TESİS` (Teknopark), and not one Macunköy-based employee appears in both
files.** Teknopark staff visit the Macunköy site; the reverse does not occur.

---

## 5. Source data at a glance

Four inputs, all structurally different. Full anatomy and the complete defect list
are in `docs/DATA-SOURCES.md`.

| File | Shape | People | Health |
| --- | --- | --- | --- |
| roster (`calisan_listesi.xlsx`) | **Employee registry** — flat, name/e-mail/facility/department/title | 181 | Good |
| `Macunköy Mayıs Mesai giriş-çıkış.xlsx` | Flat log, 1 209 rows, one row per person-day | 151 (128 real + 23 visitor/temp) | **Poor** |
| `Teknopark - Mayıs Mesai Takip Exceli.xlsx` | Per-person blocks, two columns of blocks, 4 105 merged cells | 110 | Good |
| `HCMT34_MAYIS_IZIN.xlsx` | Flat leave table | 162 | Good |

The roster is the odd one out twice over. The other three are transaction logs for
one period; it is an undated snapshot with no hire or termination dates. The May 2026
copy was exported **28.07.2026** — two months after the period — which explains the
residues: 11 people active in May are missing from it (they left), and 20 people in
it have no May trace (they were hired later).

Because it is not month-specific it lives in **`data/personel/`**, outside the month
folders, and is shared by every period. Its export date is read from the file
timestamp and reported on the `Kontrol` sheet — never hard-code it.

**Its filename and sheet name are not stable** — it arrived as
`SYST03_TEMPIASUSERS.xlsx` and became `calisan_listesi.xlsx`. So: the file is matched
by pattern (with a lone-file fallback in the roster folder), the sheet is found by
its header columns rather than its name, and column positions are derived from the
header. Do not reintroduce a hard-coded sheet name or column index here.

Two rules follow, both load-bearing (ADR-011):

- It is a **registry, not a whitelist**. Someone with attendance records who is
  absent from it worked, gets a full row, and keeps every hour.
- It **never decides who existed** in the reporting period. A roster entry with no
  activity in the period gets no row at all.

Both still hold, but the second one has a **counted** consequence since ADR-071. The
employee index is built from attendance records and leave rows, so somebody with no badge
record **and** no leave row gets no `Employee` — and therefore no row, no note, and no
place in any of the coverage counts, which are computed from the rows. That made them the
one group a manual check could not reach: 21 / 27 / 14 people over May-July 2026, of whom
16 / 22 / 13 are Macunköy-based, the same signature as `Kart bilgisi yok`. `Kontrol` §5
now counts them and lists the names by facility. Still no row and still no hours — the
roster has no hire date, so a late joiner and a lost record are indistinguishable (Q18),
and the line says that rather than guessing.

**The roster stores only the first given name** (`AHMET SINAMA` for
`AHMET CAN SINAMA`). Match on the **(first token, last token)** key, and assert the
key is unique across the roster before using it — a collision must fail the run, not
silently merge two people. ADR-010.

Headline defects (all verified, not assumed):

- **388 of 1 209** Macunköy rows are missing an entry or an exit (98 missing entry,
  338 missing exit). 82 of them have a same-day Teknopark record.
- **29** Macunköy rows have a negative duration — the source system does not handle
  midnight crossing (`23:59:42 in → 08:07:06 out → "-15:-52"`).
- **23** Macunköy identities are not employees (`ZİYARETÇİ35`, `GEÇİCİ6`, …).
- Badge ID is **not** a reliable join key across systems: `KADİR NUMUNE` is
  `SN100002` in the attendance export and `8801` in the leave export. The Teknopark
  export has no ID column at all. **Name is the key** (ADR-004, ADR-009).
- Nine employees are spelled differently between systems — Turkish characters
  entered inconsistently (`DENEMECİ`/`DENEMEÇİ`), married names present in one system
  only, one abbreviated given name. They live in the alias table in
  `config/personel.yaml`. No fuzzy matcher ships.
- The leave export has a **per-person subtotal row** before each person's real
  rows (leave-type column empty, "days used" column holds the sum). Skipping it
  is mandatory or every person's leave doubles. That row is also an unused checksum:
  it equals the sum of the person's real rows in 162 of 162 cases.
- `Uzaktan Çalışma` rows in the leave export are **worked time**, not leave
  (ADR-007). They carry start/end times and become intervals in the same union as
  badge records. It is the **only** such type — the list is closed and HR confirmed it,
  `Eğitim İzni` included (ADR-037). Every leave type's rows carry clock times, so that
  is never a reason to add one.
- **319 of 1 607 Teknopark rows are a nominal `09:00–18:00` placeholder**, not a badge
  reading — written when an expected workday has no turnstile data. They are counted
  as worked time (ADR-017) and are ~17 % of reported hours. Declared in
  `config/settings.yaml:nominal_day`. Do not read them as a remote-work marker: 90 %
  have no remote declaration behind them. `DATA-SOURCES.md` D11.
- **Leave days are fractional because the HCM divides hours by 9** (`0.11` = 1 h,
  `0.44` = 4 h, `1.00` = 9 h). Multi-day rows instead count working days. Two
  independent sources therefore put the workday at **9 hours**, which is what the
  report now pays — and which makes `expected_daily_net_hours: 8.25` wrong (Q5).
  `DATA-SOURCES.md` D13.

After excluding visitors/temps and unioning both sites: **162 real employees**,
of whom 23 have no attendance record at all and must be reported as
"no data" rather than "zero hours" (it read 24 before ADR-067 changed what "has
attendance" means — a one-sided punch is a record).

---

## 6. Conventions

**Nothing in the workbook may reference this repository.** No `ADR-0NN`, no
`ROADMAP.md Q4`, no `config/` paths, no module or phase names. Whoever opens the report
never opens the code, so such a pointer is noise. Write the explanation so it stands
alone. A test enforces this — `OUTPUT-SPEC.md §1b`.

**Nothing the program shows may name a person, a team or a department, and nothing may
say that somebody's approval is pending.** Not the workbook, not the window, not the
CLI. No `İK`, no `IT`, no job title, no "X talebiyle", no "onay bekliyor", no "şu kişiye
sorulacak". This is a professional tool used inside a company, not a school project: it
states what it did and what is unresolved, in wording that names nobody.

Two reasons, and the second is the serious one. Such a line is unusable — the reader
cannot follow it anywhere. And it is usually **false**: the report said
`45 dk kesinti İK talebiyle kapatıldı` and no such request had ever been made, and
`İK onayı bekliyor` beside a name match nobody had ever been asked about. An
implementation choice was dressed up as a department's instruction, and the same
attribution then leaked into two ADRs. Between ourselves, in `docs/` and in commit
messages, saying who decided what is right and necessary — that is the record. In
anything the program prints, it is neither.

A test enforces it (`tests/test_report.py`), on whole words, skipping cells that carry
roster text — real departments and job titles contain `İK` and the report only passes
those through. See ADR-046 and ADR-047.

**Language.** Code, identifiers, comments, `docs/`: English.
**Commit messages: Turkish**, matching the existing history (all commits to date).
This line used to say English, which contradicted every commit in the log — practice
wins, and ASCII-folded Turkish is fine (`duzelt`, not `düzelt`).
User-facing output (Excel sheet names, headers, CLI messages), `README.md`: Turkish.

**Time.** Internally `datetime`/`timedelta`, never floats-as-hours and never
strings. Format to `HH:MM` only at the report boundary. Durations that must be
summed stay as `timedelta`. Rendering helper lives in one place — do not
reimplement `HH:MM` formatting inline.

**Config over constants.** Shift boundaries, lunch length, the 3 h / 7.5 h overtime
thresholds, Multinet counts, holiday dates: all in `config/`. A rule change must
be a YAML edit, never a code edit.

The same applies to **any table keyed on strings a source file writes** — the roster's
`Tesis` values are mapped to display names through `facility_labels` (ADR-026), not a
dict in `workbook.py`, because those keys belong to the HCM and have changed before.
Label tables keyed on *our own* identifiers (`macunkoy`, `teknopark`, `izin`) stay in
code; we control those.

Three of those keys change payroll figures directly — `daily_hours` (ADR-015),
`break.deduct` (ADR-016) and `remote_day_replaces_attendance` (ADR-018). All are
**required**, not defaulted, and an unknown value fails the run. A config file
predating a rule change must not silently apply the old rule. When adding another
switch of this kind, require it too.

**Readers return one shape.** Every reader in `src/mesai/readers/` returns the same
normalized record type regardless of how ugly its source file is. All
file-format weirdness is contained inside its reader and nowhere else.

**Container and column layout are discovered, never assumed.** `base.open_sheets`
opens `.xlsx`/`.xlsm`/`.xls` and hands every reader the same `Sheet`; no reader knows
which library was used. `base.find_header_row` finds the header and maps names to
positions. Source globs are `*.xls*`. This is not defensive over-engineering: the
Macunköy export changed container, dropped a column and gained a title row in a single
month (ADR-020, `DATA-SOURCES.md` D10). **Never reintroduce a fixed column index or a
single-container glob.**

**The workbook and the window may show different sets, but they may not disagree.**
Each consumer decides which days it shows — `Günlük Detay` is the audit grid, the day
panel is what to ask somebody, `İnceleme Listesi` is a record's fate — and that is
deliberate (ADR-055). What is **not** allowed is the same day being described two
different ways, which is what happened when the sheet omitted a Saturday the window was
offering to ask about (ADR-077). Two end-to-end tests walk both artifacts of one run and
refuse any disagreement. Do not answer "which days do I show" in a fourth place without
extending them.

**Errors are data.** Anomalies (missing punch, negative duration, unresolvable
name, implausible duration) are collected into a structured list and written to a
report sheet. They are not printed warnings and not silent skips.

**Internal identifiers never reach the workbook.** A `WorkDay`'s tags are short
names for the code (`kısa-gün`, `çapraz-tesis`); the report prints them through
`anomalies.TAG_TEXT`, using the note label's exact words wherever the tag means the same
thing. Two tests enforce it, one of which greps `merge.py` so a new tag without wording
fails rather than leaking (ADR-050).

**One note has one wording, everywhere.** The monthly summary's `Not` column was
five hand-written strings while every other list used the note labels: four were
re-wordings (`Ayın çoğu açıklanmıyor` for `Ay büyük ölçüde boş`) and the other eleven
labels never appeared at all, so most people with a problem had an empty `Not` cell.
Notes are assembled once, by `Collector.labels_by_key()`, and a test refuses any note in
the column that is not a label (ADR-049). The single exception is
`Personel listesinde yok`, which is a roster fact rather than a problem.

Anomaly **labels are keywords, and they are filter keys** (ADR-027) — the people
screen builds its dropdown from them. Two kinds may never share a label, no label may
grow back into a sentence, and the sentence lives in the kind's `explanation` instead.
Changing a label — or removing one — is a breaking change to the snapshot, not a copy
edit (ADR-054, ADR-062). Every note also declares a **family** (`anomalies.py:GROUPS`);
the **dropdown** is ordered by family then by declaration order, never by frequency, so it
reads the same every month (ADR-029). The **checkbox panel** is grouped differently, by
what each note cost — `Günü sayılmayan` / `Günü sayılan`, computed from the data (ADR-056)
— because the question asked there is which of these to chase.

**Each note brings only its own people and days.** `Hem giriş hem çıkış yok` used to
also select under `Giriş yok` and `Çıkış yok`, on the reading that a day with neither
punch is also a day with no entry (ADR-053). That is gone (ADR-065): the three are three
separate questions to ask somebody — what time did you leave, what time did you arrive,
were you here at all — and the third is not a case of the other two. There is no
implication table; the reasoning both ways is in ADR-053 and ADR-065, and neither should
be reintroduced without reading both.

**A filter selects only what is still outstanding** (`recipients.outstanding`, ADR-059,
ADR-061). Ticking `Giriş yok` returns the people whose entry is missing **everywhere** —
not the ones whose Macunköy row was blank on a day their Teknopark record covered in full.
A day is outstanding when nothing was counted for it and no leave covers it
(`ProblemDay.explained`); a note with no dated day at all (`Kart bilgisi yok`) has nothing
to explain and always stands. `Sorunu olmayanlar` asks the same question, so the two stay
a partition of the month.

**Except for the notes under which nothing was ever lost** (`counted_only_labels`,
ADR-072). For those the restriction removes every day they have and the note selects
nobody by construction — `Gece geçişi` said 6 people and filtered to 0, which is a repair
the program *made*, not a day that went missing. Those notes select whether or not the day
was counted. Do not widen this to the rest: the half that keeps `outstanding` is what
stops a day the union already covered from coming back into the mail list, and a test
holds each half separately.

**A person's problem days are not a view of the filter** (`days_by_cost`, ADR-074).
The `Sorunlu gün` column and the day panel take **no label set**: they are every problem
day the person has, split into what was lost and what was not. They were built from the
ticked set, so the column read 446 across July (27 of them days that were counted) and
127 with one note ticked, against a truth of 419. Ticks decide *who is in the list*;
what a person's days are is not up for selection. Counted days are offered in the panel
under their own heading and **start unticked** — the off-set is inverted for them on
purpose, because silence is the expensive mistake when a day was lost and a false
statement is the expensive one when it was not. Two kinds of day are in **neither**
half and reach the panel not at all, so `days_by_cost` is deliberately **not** a partition
of `person.days`: a **leave-covered** day (ADR-075) and a **counted day whose only notes
say a punch was missing** (ADR-076). The second one needs the reasoning: a one-sided stamp
yields no interval (ADR-067), so minutes on a day mean another record covered it in full —
the person did badge, at the other site — and `Hem giriş hem çıkış yok` beside a 9:05
duration is a contradiction on one row rather than a fact. `recipients.day_notes` strips
those notes from any day presented as a question, because a day can carry both that and
`Tesis birleştirme`. Both dropped kinds stay on `Şüpheli Kayıtlar` and `İnceleme Listesi`;
§2.2 is intact.

**The message wording lives in `config/mail-taslagi.yaml`, not in the code** (ADR-078).
The program ships frozen, and wording compiled into an `.exe` can only be changed by
rebuilding it — so this is §6's "a rule change is a YAML edit" applied to the only output
that leaves the building. What stays in code is which days are listed and which note is
written beside each; those have right answers. The loader refuses an unknown placeholder
and an empty required field, and there is **no built-in fallback** — a fallback is
invisible, so the operator would edit the file and see nothing change.

**No test may open a socket.** `conftest.py` takes `smtplib.SMTP` away from the whole
suite, autouse. This is not precaution: a test written to check that a *missing*
`gmail.yaml` is reported found a real one and sent a live message. Sending tests pass a
`transport`.

**Mail goes to one person per call and there is no bulk send** (ADR-073). Not an omission
— 162 e-mails cannot be recalled, and a loop is a decision nobody has taken. A test
asserts no function in `sender.py` is named for one. The credentials live in
`config/gmail.yaml`, git-ignored like `personel.yaml`: it holds a login, which §2.3 puts
in the same class as a name.

Three consequences to know before touching any of this:

- **Note counts do not partition.** The same day appears under two filters, so anything
  that adds note counts together is wrong.
- **A note may show `(0)`** — it occurred this month and nothing is outstanding under it.
  Do not drop those rows from the list: a bug in `explained` would then remove a whole
  note from the window silently, which is the failure ADR-017 and ADR-048 guard against.
- **Do not put an explanatory figure beside a label.** Tried and removed the same day
  (ADR-058 → ADR-059): `27 kişi · 5/78 gün sayılmadı` read as an arithmetic error, and
  once the filter itself is right there is no second number to reconcile. The panel prints
  `{label} ({people})`. An indent to mark the stricter note was tried and removed too.

Three severities, and the third one earns its keep: `excluded` (counted as zero
hours), `included` (counted, worth a look), `info` (counted, **expected behaviour**).
Info items are recorded for the audit trail but do not count as anybody's problem —
use `anomaly.is_problem`, never a severity comparison, when counting problems. Without
this, expected behaviour shades 21 people's rows and buries the 2 real questions
among them (ADR-017).

**Testing.** Every business rule gets a unit test with a hand-computed expected
value. Every reader gets a fixture test against a small synthetic workbook.
Reconciliation between the two sites gets its own test — that is where the bugs
will be.

---

## 7. Before you finish a task

- [ ] Rule changes reflected in `config/`, not hard-coded
- [ ] New quirk found in a source file → written to `docs/DATA-SOURCES.md`
- [ ] Decision made with a real alternative → ADR appended to `docs/DECISIONS.md`
- [ ] Structure or module change → `docs/ARCHITECTURE.md` and §3 of this file
- [ ] Tests written and passing
- [ ] Nothing under `data/`, and no `gonderim-*.json`, was committed
- [ ] No repository reference (`ADR-0NN`, `Q4`, a file path) reached the workbook
- [ ] No real employee name added to a test fixture
- [ ] Totals still reconcile: Σ per-person hours == Σ measured person-days, and the
      `Kontrol` sheet still shows presence and in-day gaps as separate lines

---

## 8. Open questions

Tracked in `docs/ROADMAP.md §5`. If you resolve one, move it into an ADR and
remove it from the list.
