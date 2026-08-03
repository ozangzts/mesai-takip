# DECISIONS.md — Architecture Decision Record

Append-only. **Never edit or delete an existing ADR.** To change a decision, add a
new ADR that supersedes the old one and mark the old one `Superseded by ADR-NNN`.

Template:

```
## ADR-NNN — Title
Date · Status: Accepted | Superseded by ADR-NNN | Proposed
Decided by:
### Context
### Options considered
### Decision
### Consequences
```

---

## ADR-001 — Merge the two sites by unioning intervals per person-day

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

76 of 162 employees appear in both the Macunköy and the Teknopark attendance export
for May 2026. This is not a data error — people badge at the Teknopark office for
their working day and at the Macunköy production site during visits. Their badge
records overlap in wall-clock time.

Verified example, `ZEYNEP DENEME, 2026-05-21`: Teknopark shows a complete
`07:09–19:45`; Macunköy shows the same day with an entry and no exit.

### Options considered

1. **Union intervals per person-day**, count overlapping time once
2. Total each site separately, then add
3. Site precedence — Teknopark wins, ignore Macunköy for that person-day
4. Report both and let HR decide manually

(2) double-counts up to several hours a day for 47 % of the workforce. (3) discards
genuine extra hours worked at the other site — precisely the overtime this project
exists to measure. (4) pushes 76 people × ~20 days of manual work back onto HR.

### Decision

Option 1. For each employee-day, collect intervals from every source, sort, merge
overlapping **and touching** intervals, and measure the union.

### Consequences

- Correct totals; no double counting; no lost hours.
- The merge step becomes the most correctness-critical code in the project and
  needs the heaviest test coverage.
- Identity resolution across systems becomes mandatory — see ADR-004.
- Per-site subtotals are no longer simple sums of per-site files. If HR wants
  per-site figures, overlapping time must be attributed by an explicit rule that
  does not exist yet.

---

## ADR-002 — Report gross and net hours side by side

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

Standard day is 07:30–16:30 with an 11:30–12:15 unpaid lunch. Employees do **not**
badge out for lunch, so raw badge time overstates worked time by 45 minutes on a
typical day. But 84 Teknopark person-days *do* show a mid-day gap, so a blanket
deduction would double-count the break for those.

### Options considered

1. **Both columns** — gross (as badged) and net (lunch deducted)
2. Net only
3. Gross only

### Decision

Option 1. Report both. Net is computed per `DOMAIN-RULES.md §5`, which skips the
deduction when the day is short or when the person demonstrably badged out over
lunch.

### Consequences

- HR can reconcile against the source system (gross) and against payroll (net)
  without a code change.
- Both figures must be labelled unambiguously in the report, or they will be
  confused.
- The "did they already take lunch?" gap tolerance is unresolved — open question Q3.

---

## ADR-003 — Never invent a missing punch

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

388 of 1 209 Macunköy rows are missing an entry or an exit. Something must be done
with them.

### Options considered

1. **Cross-site repair first, then zero and flag** the remainder
2. Zero and flag everything, no repair
3. Fill with shift defaults (missing exit → 16:30, missing entry → 07:30)

Option 3 produces a report that *looks* complete and is quietly wrong; those numbers
would reach payroll and then the employee's inbox. It was rejected outright.

### Decision

Option 1:

1. Try to reconcile against a complete same-day record from the other site
   (82 of 388 in May 2026 have one).
2. Anything left contributes **zero** hours and appears in the anomaly sheet with
   its source file and row number.

Repair may only reuse a timestamp a badge terminal actually recorded. It may never
synthesise one.

### Consequences

- Reported totals are conservative — they understate rather than overstate.
- HR gets a worklist of roughly 300 rows to resolve at source. This is a feature:
  it surfaces a real operational problem that manual reporting has been absorbing.
- The report must state prominently that flagged records count as zero, or the
  totals will be misread as final.

---

## ADR-004 — Join on normalized name, not badge ID

2026-08-03 · Status: **Accepted** · Decided by: implementation constraint

### Context

ADR-001 requires matching people across three systems. Badge IDs do not agree:
`KADİR NUMUNE` is `SN100002` in the Macunköy attendance export and `8801` in the
leave export. The `SN` values are card numbers; the numeric values are personnel
numbers, and only some rows carry the latter. The Teknopark export contains **no**
ID at all — only a name.

### Options considered

1. **Normalized exact name match**, with a manual alias table for failures
2. Badge ID with a name fallback — impossible, Teknopark has no IDs
3. Fuzzy name matching (Levenshtein / token similarity)

Option 3 is rejected under `AGENTS.md §2.1`: a fuzzy match that misfires silently
merges two people's payroll hours.

### Decision

Option 1. Normalized exact match, using the Turkish-safe normalizer in
`DOMAIN-RULES.md §4.4`. Failures become `UNRESOLVED_IDENTITY` anomalies and are
resolved by a human adding an entry to `config/personel.yaml`. The numeric badge ID
is used to *confirm* a name match, never to make one.

### Consequences

- Deterministic and auditable; the alias table is reviewable.
- Requires the Turkish casing helper everywhere — bare `.upper()`/`.lower()` on a
  name is a bug.
- Genuine duplicates (a name spelled two ways) need one manual config entry each,
  once.
- Two different employees with an identical name would be silently merged. Not
  present in the current data; must be re-checked with each new month, and would be
  resolved by adding badge ID to the key for those individuals.

---

## ADR-005 — Deterministic Python, no AI at runtime

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

The project owner asked explicitly whether this can be done with ordinary code
rather than AI, since Phase 4 will e-mail these figures directly to employees.

### Decision

The entire pipeline is plain Python: `openpyxl` for Excel, `PyYAML` for config,
`smtplib` for mail. No model call at any point in a production run. Same input →
byte-identical output.

An AI agent may *write* and *modify* this code; it never *executes as part of it*.

### Consequences

- Every number is reproducible and auditable by hand.
- No API cost, no network dependency, no rate limit, no vendor availability risk in
  a monthly payroll job.
- Ambiguity cannot be papered over by a model, so ambiguous rules must be resolved
  explicitly with HR — see the open questions in `ROADMAP.md §5`. This is a
  benefit, but it is why the open-question list is long.

---

## ADR-006 — Build our own report rather than adopting the MEYER format

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

`MEYER Örnek Rapor Taslağı 1.xlsx` is a vendor's sample output with 11 sheets. HR
was evaluating that product. The project owner's instruction: "we will do this work
ourselves."

The sample is also **single-employee** — every sheet shows one person's month. Our
report must cover 162 people.

### Decision

Treat the MEYER workbook as a **requirements artefact**, never as a template to
copy or a file to read as data. Our sheet set derives from it but is restructured
around a multi-employee report; see `OUTPUT-SPEC.md`.

### Consequences

- Freedom to design a layout that fits 162 people.
- If HR later buys the vendor product, our figures should be cross-checkable
  against theirs — the same underlying rules, so this stays possible.
- Sheet names stay Turkish and echo the MEYER vocabulary so HR recognises them.

---

## ADR-007 — `Uzaktan Çalışma` counts as worked time

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

The leave export contains 56 `Uzaktan Çalışma` (remote work) records across 31
people. They sit in the leave file, but the person was working — they just produced
no badge record. Treating them as leave makes remote workers look absent and
understates their month by up to a full working day each time.

### Decision

Remote work is worked time. Hours are taken from the record's own start and end
times (42 of 56 are `07:30–16:30`, the rest partial), never from a per-day constant.
Each becomes an interval entering the same union as badge intervals (ADR-001), so
overlap with a badge record is counted once and tagged for review.

Every other leave type remains non-worked time.

### Consequences

- Remote intervals must be visibly distinguishable in the detail sheet
  (`source = izin`, tag `uzaktan`). A figure that mixes badged and declared hours
  without saying so is not auditable.
- 48 of the 56 records belong to people who also badged that month, so the
  double-counting guard is load-bearing and needs a test.
- Remote days are self-declared, not measured. If HR wants them treated differently
  for overtime purposes, that is a Phase 2 rule.
- `Eğitim İzni` (training, 25 rows) is arguably the same situation. Not decided —
  open question Q13.

---

## ADR-008 — Deduct the *residual* break, not a fixed 45 minutes

2026-08-03 · Status: **Accepted** · Decided by: project owner (problem raised),
implementation (rule proposed)

### Context

Employees do not normally badge out for lunch, so gross badge time includes the
45-minute break. But 84 Teknopark person-days *do* show a mid-day gap — one real
case is 42 minutes.

The project owner's position: a 42-minute gap should not count as having taken the
break — but also asked, correctly, how that judgement could be made consistently
every time. Any threshold rule requires a cut-off nobody can justify: at 44 minutes
the employee loses 45 minutes, at 45 they lose nothing.

### Options considered

1. **Deduct the residual**: `45 − (unpaid gap already in the day)`, clamped to 0–45
2. Fixed 45 min deduction unless the gap ≥ 45 min (threshold rule)
3. Fixed 45 min always
4. Never deduct; report gross only

### Decision

Option 1. Every employee owes 45 minutes of unpaid break per day. Time already
outside the merged union is already unpaid. Deduct only the difference.

42-minute gap → 3 minutes deducted. No gap → 45 deducted. 3-hour gap → 0 deducted
(capped, no credit).

### Consequences

- No threshold, no tolerance parameter, no per-case judgement. Continuous and
  monotonic: badging out for longer never makes your net hours go up.
- Satisfies the owner's requirement — a 42-minute gap does *not* buy a full break —
  while remaining mechanically reproducible.
- Needs a break-eligibility window so an unrelated afternoon absence is not read as
  lunch. Window is generous and per-shift (`DOMAIN-RULES.md §5.2`).
- Explaining the rule to an employee takes one sentence: "you get 45 minutes of
  unpaid break a day; if you badged out for part of it, only the rest is deducted."

---

## ADR-009 — Personnel number is informational, name is the key

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

The owner's manager instructed that the report be organised **by name, not by
personnel number**, on the grounds that the numbers may be unreliable. The owner
added: include the number anyway if it is consistent.

Measured: the leave export has a numeric personnel number for all 162 people. The
Macunköy export has numeric numbers on 54 people — 49 match the leave export
exactly — and `SN`-prefixed **card** numbers on 45 more, which do not correspond.
The Teknopark export has no identifier column at all. The IAS roster's `Kontak No`
matches none of them (`DATA-SOURCES.md` D8).

The manager's instinct was right, for a more specific reason than "they may be
wrong": the numbers are *absent or of a different kind* in the attendance files, so
they cannot serve as a key even when correct.

### Decision

Name (normalized, ADR-004) is the sole matching key and the report's primary sort.
The personnel number is carried as an informational column, sourced only from the
leave export after the name match succeeds. Blank where unavailable. `SN` card
numbers and IAS `Kontak No` values never appear in the report.

### Consequences

- The report reads the way the manager asked, and still carries the number HR needs
  for payroll cross-reference.
- The number can never cause a wrong match, because it is never used to make one.
- Two employees sharing a name would collide. None do today; re-check monthly. If it
  happens, those individuals get a composite key and the number stops being purely
  informational — that would need a new ADR.

---

## ADR-010 — The IAS roster is the employee registry; match on (first name, surname)

2026-08-03 · Status: **Accepted** · Decided by: project owner (supplied the file),
implementation (matching rule)

Refines ADR-004 and ADR-009. Neither is superseded — name is still the key and the
personnel number is still informational. This ADR says *which* name list is
canonical and how to match against it.

### Context

`SYST03_TEMPIASUSERS.xlsx` arrived after the initial design: 181 active employees
with e-mail, home facility, department and job title. It is the only file that
states who currently works here; the other three are transaction logs.

It also resolves three things the design was blocked on. `Tesis` confirms the
dual-site model (75 of the 79 people appearing in both attendance files are based at
`DEICO TESİS`; **zero** Macunköy-based employees appear in both). `E-posta` is
populated for all 181, which unblocks Phase 4. `Bölüm` and `Görev` are cleaner than
the department strings in the attendance exports.

The complication: the roster stores only the **first** given name. `AHMET CAN SINAMA`
is `AHMET SINAMA`. Exact matching resolves only 77 of 128 Macunköy employees.

### Options considered

1. **Match on (first token, last token)**, with a hard uniqueness assertion
2. Exact full-name match, alias table for the ~40 % that fail
3. Fuzzy / token-subset matching

Option 2 means roughly 70 manual alias entries and a new one whenever anyone is
hired — the table becomes the system. Option 3 is barred by `AGENTS.md §2.1`.

Option 1 is a heuristic, but a *checkable* one: the 181 roster names produce 181
distinct (first, last) keys with zero collisions, and the check is mechanical.

### Decision

The roster is the employee registry. Every other source resolves against it on the
normalized (first token, last token) key. Tokens of one character plus a full stop
(`M.`) are dropped before taking first and last.

The loader **must** build the key index and assert uniqueness. A collision — two
different employees sharing a first name and surname — **fails the run**. It does not
warn, and it does not pick one. Every monthly export re-runs the check.

The roster is a registry, **not a whitelist**: a person with attendance records who
is absent from it still gets a row and still has their hours counted.

Surname changes still need aliases. `SEDA DENEME` (attendance, maiden) and
`BÜŞRA ÜNAL` (roster, married) differ in the last token, so the key does not bridge
them. The five cases in `DATA-SOURCES.md §6.1` remain manual config entries.

### Consequences

- Identity coverage rises from 77/128 to 106/128 (Macunköy), 102/110 (Teknopark),
  161/162 (leave). 84 % of people with attendance records gain an e-mail address.
- Q1 closed: the report's location column comes from `Tesis`, a fact about the
  employee, rather than being inferred from which terminal they touched.
- Department and job title come from the roster, so the attendance files' department
  strings become a fallback only.
- **A hidden risk is accepted:** two employees with the same first name and surname
  would collide. None do today. The assertion turns a silent payroll error into a
  loud startup failure, which is the trade being made deliberately.
- 26 people have attendance but no roster entry, and 20 roster employees appear
  nowhere. Both need HR — Q4. Neither blocks Phase 1.

---

## ADR-011 — The roster is a point-in-time snapshot; never use it to decide who existed

2026-08-03 · Status: **Accepted** · Decided by: project owner

### Context

The IAS roster was exported in **August 2026**. The attendance and leave files are
from **May 2026**. Three months separate them, and the roster carries no hire or
termination dates — it is a snapshot of "who works here now", with no history.

Measured against May activity (anyone with an attendance or leave record):

| | Count | Reading |
| --- | --- | --- |
| Active in May, in the August roster | 161 | normal |
| Active in May, **not** in the roster | 27 | left between May and August |
| In the roster, **no** May trace at all | 20 | hired after May |

This explains both residues flagged in ADR-010. Neither is a data defect.

### Decision

The roster **enriches** identity — e-mail, facility, department, job title — and
never **determines** it. Specifically, for a report covering period P:

- A person with activity in P but no roster entry **gets a full row with full
  hours.** They worked during P. Their metadata columns are blank and the note reads
  `Personel listesinde yok`. They are not excluded and their hours are not discounted.
- A person in the roster with **no activity of any kind** in P gets **no row**.
  They were not employed during P; a "0 hours / no data" row for them is noise that
  makes a genuine data gap harder to spot.
- A person with a leave record but no attendance record in P **does** get a row,
  with hours blank and the note `Mesai verisi yok`. They were present in P; their
  attendance is genuinely missing. This is the case that matters.

The report footer states the roster's export date alongside the reporting period, so
a reader can see the gap.

### Consequences

- Correct for historical months, which is what makes back-filling earlier periods
  possible at all.
- Removes 20 phantom rows from the May report and keeps 27 real leavers in it.
- The distinction between "hired later", "left earlier" and "attendance missing"
  currently rests on inference from three files. **Hire and termination dates would
  make it a fact.** Requested from HR as Q18 — a roster export with
  `İşe Giriş Tarihi` / `İşten Çıkış Tarihi` resolves this class of problem
  permanently and should be asked for before Phase 4 mails anyone.
- Until those dates exist, the pipeline must be re-run with a roster contemporaneous
  with the period wherever possible. See ADR-012.

---

## ADR-012 — Validate on a recent month, not on May

2026-08-03 · Status: **Proposed** · Decided by: implementation, pending owner

### Context

May 2026 is the month we have, and it is a poor production candidate:

- the roster post-dates it by three months (ADR-011)
- 14 expected working days, cut down by a seven-day holiday block — a short and
  atypical month
- 37 people with May activity have **no attendance record at all**, ~426 working
  days unaccounted for
- the public-holiday calendar underlying all of the above is **inferred**, not
  confirmed (Q16)

None of this blocks writing the code. All of it blocks trusting the output.

### Decision

Build and unit-test against May, then **validate against July 2026** (or the most
recent complete month), where the roster and the transaction data are
contemporaneous and the calendar is ordinary.

The May run is labelled a validation run, not a payroll run. Its figures are not
circulated as final and no e-mail is generated from them.

### Consequences

- Requires HR to export three more files for July. Low cost, and it doubles as the
  test of whether the export formats are stable month to month (Q10) — which the
  readers must survive anyway.
- Delays a trustworthy production number by however long that export takes.
- If July looks clean and May does not, the difference itself diagnoses Q4.

---

---

## ADR-013 — A repeated roster key is fatal only if the identities differ

2026-08-03 · Status: **Accepted** · Decided by: implementation

Refines ADR-010.

### Context

ADR-010 made a repeated `(first, last)` key fail the run, on the grounds that
merging two people's payroll hours is unacceptable. The guard fired on the first
real run — and what it caught was not two people.

`İREM ÖRNEK` occupies rows 108 and 110 of the roster with identical contact number
(`8803`), e-mail, department and job title. The logins differ: `IOREK` and
`IYENI`. It is one person with a stale second account after a surname change.

Failing the run on that would be wrong: nothing is ambiguous and no hours are at
risk. But relaxing the guard entirely would restore the original danger.

### Decision

On a repeated key, compare identity beyond the name:

* same contact number **or** same e-mail → **same person.** Deduplicate, keep the
  first row, and report it on the `Kontrol` sheet.
* otherwise → **collision.** Fail the run, naming both rows with their contact
  numbers and e-mails so a human can tell them apart.

### Consequences

- The guard still protects against the case it was written for, and no longer
  blocks on a data-hygiene artefact.
- Duplicate accounts stay visible rather than being silently swallowed — HR may
  want to close the stale one.
- If a genuine collision ever occurs, the error message now carries the
  distinguishing fields, which is what a human needs to resolve it.
- A duplicate account whose contact number *and* e-mail both differ would still be
  read as a collision. That is the safe direction to fail in.

---

## ADR-014 — `--ay` is a filter, not a label

2026-08-03 · Status: **Accepted** · Decided by: implementation

### Context

The first version passed the period string through to the report title and the
calendar year, but never compared it against the data. Running
`--ay 2026-06 --girdi "2026-mayıs"` produced a complete, confident report titled
**"HAZİRAN 2026"** containing every May figure, with no warning.

Related: `find_source` returned the *first* glob match. A folder holding both May and
June exports would have one picked arbitrarily by sort order.

Both matter more once files arrive via a synced Drive folder, where nobody is
checking by hand which month is present.

### Decision

1. Records dated outside the reporting month are **dropped**, and the count is
   reported on the `Kontrol` sheet per source. Leave records are filtered the same
   way.
2. If input files contain records but **none** fall inside the period, the run
   **fails**, printing the expected range and the range actually found.
3. A source pattern matching **more than one file** fails the run and lists the
   candidates, rather than choosing one.
4. `PermissionError` on the output file becomes a plain message telling the user to
   close it in Excel. It happens every month in practice.

### Consequences

- Wrong folder, wrong month, or two months in one folder all now fail loudly and
  early instead of producing a plausible wrong answer.
- The `Kontrol` sheet gains a line confirming zero out-of-period records, so a
  reader can see the check ran rather than inferring it from silence.
- One month per folder is now a contract. `data/raw/<YYYY-MM>/` is the convention
  and the Drive sync should follow it.
- An export legitimately spanning a month boundary would have the outside days
  dropped. Correct for a monthly report, but worth remembering if overtime weeks
  straddling months matter in Phase 2.
