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

2026-08-03 · Status: **Superseded by ADR-016** · Decided by: project owner

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

2026-08-03 · Status: **Superseded by ADR-016** — no break is deducted at all as of
2026-08-17. The rule below remains implemented and tested behind
`break.deduct: true`, because it is the fallback if HR reverses ADR-016. ·
Decided by: project owner (problem raised), implementation (rule proposed)

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

---

## ADR-015 — A person-day is measured first entry → last exit, not as the sum of intervals

2026-08-17 · Status: **Accepted** · Decided by: project owner

### Context

ADR-001 unions each person-day's intervals so that cross-site overlap is counted
once. Until now the day's *hours* were then the sum of those merged intervals, which
excludes any gap inside the day. `DOMAIN-RULES.md §4.2` argued for this at length and
called earliest-to-latest a "shortcut" that "pays for an hour nobody worked".

The project owner rejected that framing: for this company the classic timesheet
reading is intended — the day starts when you first badge in and ends when you last
badge out, and time in between is not the report's business. Asked directly whether
gaps should be deducted, the answer was no.

This is a policy question, not an arithmetic one. §4.2's numbers were never wrong;
what was wrong was treating a company policy choice as a correctness argument.

### Options considered

1. **Envelope** — earliest entry to latest exit; in-day gaps are paid
2. Union of merged intervals — gaps unpaid (the previous rule)
3. Envelope, but collapse to the longest single interval when the day carries a
   nominal `09:00–18:00` Teknopark row
4. Envelope with a cap on how large a single paid gap may be

(3) was considered because it was one reading of the owner's instruction; it was
withdrawn once the instruction was clarified to mean (1). It also cost only 20 h
across May while adding a second, inconsistent rule. (4) invents a threshold nobody
asked for, which is the same mistake ADR-008 was written to avoid.

### Decision

Option 1, as `daily_hours: envelope` in `config/settings.yaml`. Option 2 stays
available as `daily_hours: union` and is still covered by tests.

The union itself is **unchanged and still mandatory** — it is what stops the 76
dual-site employees being double-counted. ADR-001 governs de-duplication; this ADR
governs only how the merged day becomes a number.

### Consequences

- May 2026: +159 h 11 m across **171 person-days** that have more than one interval.
  1 652 of 1 823 person-days are unaffected, having a single interval.
- 46 of those days have a gap over 1 h and 10 over 2 h. The largest is
  `07:30–08:00` + `12:37–19:10`: presence 7 h 03, now paid 11 h 40. Reported, not
  suppressed — see below.
- `Günlük Detay` gains a **`Gün İçi Boşluk`** column, so every paid gap is visible
  and `Son Çıkış − İlk Giriş = Çalışma Süresi` can be checked by subtraction. Without
  it the rule would be unauditable from the report alone.
- The reconciliation guard had to be restated. "Σ per-person == Σ accepted interval
  durations" is false under this rule by design; it is now "Σ per-person == Σ measured
  person-days", with presence and gap totals shown separately on `Kontrol` so the
  cost of this decision is a number on the report rather than a hidden difference.
- `DOMAIN-RULES.md §4.2` was rewritten. It now separates the union (correctness) from
  the daily measure (policy) instead of arguing against this decision.
- Phase 2 thresholds will be computed on a figure that includes in-day gaps. This
  partly answers ROADMAP Q6 ("gross or net?") — gross, necessarily.

---

## ADR-016 — Do not deduct the unpaid break; the badged day is the payroll figure

2026-08-17 · Status: **Accepted** · Decided by: project owner

### Context

ADR-002 reported gross and net side by side; ADR-008 defined net as gross minus the
*residual* break — 45 minutes less whatever unpaid gap the day already contained.
Because of that residual construction, essentially every full day lost about 45
minutes one way or the other: as a real gap, or as a deduction. Across May 2026 the
deduction removed **1 291 h 52 m**, roughly 42.5 minutes per person-day.

The project owner instructed that breaks are not to be deducted: entry and exit are
what count. Combined with ADR-015, the badged day is the payroll figure.

### Options considered

1. **Do not deduct** — one hours figure, equal to the measured day
2. Keep deducting (ADR-008)
3. Keep both columns but leave net equal to gross
4. Delete the break code entirely

(3) prints two identical columns and invites an HR reader to ask which one payroll
uses — the exact ambiguity that produces payroll errors. (4) throws away a rule that
took a real decision to design and that HR may reinstate; a config switch costs
almost nothing to keep.

### Decision

Option 1, as `break.deduct: false`. ADR-008's arithmetic stays in
`rules/worktime.py`, still unit-tested, and `break.deduct: true` reproduces the
previous report exactly — verified end to end: brüt `17009:01`, net `15717:08`.

`worktime.measure()` is the only place the switch is read. No other module decides
whether a break applies.

Both switches are **required** keys in `settings.yaml`, not defaulted, and an
unknown `daily_hours` value fails the run. A payroll-affecting rule must not be
silently assumed by a config that predates it.

### Consequences

- May 2026 total goes from `15717:08` to `17168:13` (+1 451 h 04, +9.2 %), of which
  1 291 h 52 is this ADR and 159 h 11 is ADR-015.
- With no deduction, gross and net are the same number, so the report shows **one**
  pair of columns named `Çalışma Süresi` / `Çalışma (Saat)`. The four-column
  gross/net layout of ADR-002 returns automatically if the switch is flipped back.
- Every hours sheet carries a one-line `HESAP KURALI:` banner stating the active
  rule. The rule is now configurable, so the report must say which way it ran rather
  than let the reader assume last month's rule.
- ROADMAP Q3 ("does a 42-minute gap count as the break taken?") is moot while this
  stands: no gap is measured against a break at all.
- Phase 2's `expected_daily_net_hours: 8.25` is now inconsistent with a 9-hour paid
  day. It is unused and unconfirmed (Q5), but must be revisited before any overtime
  rule ships.

---

## ADR-017 — A nominal timesheet day is worked time; the overlap is information, not a defect

2026-08-17 · Status: **Accepted** · Decided by: project owner

### Context

Investigating why `Uzaktan Çalışma` days collide with attendance records surfaced an
undocumented pattern in the Teknopark timesheet: **319 of 1 607 May rows and 418 of
2 557 June rows are exactly `09:00–18:00` with duration exactly `09:00`.** Four
findings say these are not turnstile readings:

1. Real punches carry odd minutes (`07:17`, `18:46`); this pattern never does.
2. In every remote-overlap case it is the *only* record for that person-day — no
   physical trace anywhere.
3. On 25–26 May, the holiday bridge with the office closed, 15 of 15 and 15 of 16
   records are exactly this pattern.
4. 19 May person-days carry it while the person was on leave, including one day of
   `İstirahat (Raporlu)`.

The owner's position, given directly: how the data got into the source system is not
this project's concern. If a day has an attendance record, count it. The company most
likely credits remote workers with the standard shift, and asking each case is not
worth it.

A prior version of this analysis over-claimed here, and the correction matters for
anyone reading the numbers later. "91–94 % of overlaps have a nominal record on the
attendance side" is conditional on already being an overlap and says nothing about
what triggers the pattern. Measured the other way round, **90 % (May) and 82 % (June)
of nominal rows have no remote-work declaration behind them at all**, and the heaviest
users of the pattern — 11 and 16 nominal days — have zero and zero remote
declarations. So the placeholder is written for *an expected workday with no turnstile
data*, of which declared remote work is one minor trigger, not the cause.

That distinction does not change the decision. It changes what the report should
claim.

### Options considered

1. **Count it, and report the overlap as information** — no defect language
2. Count it, and report nothing
3. Exclude nominal rows from totals
4. Ask HR to confirm each case before counting

(3) would remove roughly 17 % of reported hours on a pattern the source system's own
`Dönemdeki Toplam` counts as work — we would be overruling the source. (4) is 21
people × several days a month of manual work, for a pattern that is stable across two
months. (2) loses the audit trail: a reader could no longer tell that a remote day and
a timesheet day were reconciled rather than added.

### Decision

Option 1, with the overlap **split into two anomaly kinds**, because they are two
different questions:

| Kind | Severity | May / June |
| --- | --- | --- |
| `REMOTE_OVERLAP` — attendance side is the nominal placeholder | `info` | 35 / 75 |
| `REMOTE_OVERLAP_REAL` — attendance side is a real punch | `included` | 2 / 7 |

A third severity, `info`, was added: counted, expected, **not a problem**. Info items
do not count towards a person's `Şüpheli Kayıt` figure, do not shade their summary
row, sort last, and are shaded grey with the impact text
`Toplama dahil edildi — beklenen durum`.

The nominal pattern lives in `config/settings.yaml:nominal_day`, not in code — it is a
vendor default that can change. **With no `nominal_day` configured, every overlap is
reported as the real-punch case**: the safe direction is over-asking, never silently
calling a real punch expected.

The `uzaktan-çakışma` tag is now applied only to the real-punch case. Tagging the
nominal case made 37 ordinary remote days read as defects on `Günlük Detay`.

### Consequences

- `Sorulacaklar` goes from 21 alarming rows to **2 real questions and 19 grey
  information rows** for May; 4 and 36 for June. The two real cases are now findable
  instead of buried among the expected ones.
- Nobody's `Şüpheli Kayıt` count is inflated by expected behaviour. May's total
  anomaly count is unchanged at 242, but 35 of them are now explicitly marked
  `bilgi amaçlı (sorun değil)` on the `Kontrol` sheet.
- **We are faithful to the source and no longer pretending otherwise.** The Teknopark
  file's own period total counts these rows as work; so do we. If HR later decides the
  placeholder should not be paid, that is a new ADR and a ~17 % reduction, and the
  `nominal_day` config already identifies exactly which rows are affected.
- The 19 leave-days carrying a nominal row — including one `İstirahat (Raporlu)` — are
  paid. This follows from the decision and is recorded here so it is a known
  consequence rather than a surprise found later.
- Adding a severity broke the report at runtime while all 112 unit tests passed,
  because `report/workbook.py` kept its own copy of the severity → impact-text map.
  The map now has one home in `anomalies.py`, and `tests/test_report.py` was added to
  build a workbook containing every anomaly kind and every severity.

---

## ADR-018 — On a declared remote-work day, the remote hours replace a nominal placeholder

2026-08-17 · Status: **Accepted** · Decided by: HR manager, via project owner

### Context

ADR-017 established that the Teknopark timesheet writes a nominal `09:00–18:00` row
for an expected workday with no turnstile data, and that a declared remote-work day is
one of the things that triggers it. Both records then entered the union, so a remote
day measured `07:30–18:00` = 10:30 — the declaration's start joined to the
placeholder's end.

HR's instruction, after reviewing the report: for remote days, take the remote hours.

### Options considered

1. **`nominal_only`** — the declaration replaces the attendance record only when every
   attendance record that day is a placeholder
2. `always` — the declaration always replaces the day's attendance records, HR's
   instruction read literally
3. `never` — keep unioning everything (pre-ADR-018)
4. Cap the placeholder's contribution instead of dropping it

(2) is the literal reading and it discards evidence. On seven person-days across May
and June the attendance side is a **real turnstile reading**, and dropping it loses
recorded work — `2026-06-23`: declaration `07:30–13:45`, but the person badged
`07:30–13:00` and again `13:41–18:34`. `always` pays 6:15 where the day is 11:04.
Nobody intended to take 4 h 49 off somebody who demonstrably worked it. (4) invents a
threshold, which is the mistake ADR-008 exists to avoid.

### Decision

Option 1, as `remote_day_replaces_attendance: nominal_only`.

A placeholder is not evidence, so it gives way to the declaration. A real punch is
evidence, so it survives and the day is unioned as before — and it is already reported
as `REMOTE_OVERLAP_REAL`, the two-to-seven cases worth a question.

**One real punch protects the whole day.** If a day carries a placeholder *and* a real
punch, nothing is dropped: the presence of any real timestamp means the day has
evidence we are not entitled to discard. A one-sided record counts as a real
timestamp for this purpose — it failed to be a placeholder, so the day is left alone.

`always` and `never` remain available as config values, both covered by tests.

### Consequences

- May 2026: `17168:13` → **`17103:58`** (−64:15) across 35 person-days.
  June: `27249:09` → **`27119:24`** (−129:45) across 74 person-days.
- The seven real-punch days keep their hours. `always` would have cost a further
  5:13 in May and 14:54 in June, taken from people who badged in.
- A new `info` anomaly, `REMOTE_REPLACED_NOMINAL`, records every day where this
  happened, with the discarded times in the `Ham Çıkış` column. Nothing is dropped
  silently — AGENTS.md §2.2.
- One June day still reports the old `REMOTE_OVERLAP`: its attendance side is a
  placeholder *plus* a one-sided record, so the day was not replaced. Correct under the
  rule above, and worth knowing the case exists.
- Remote days now measure exactly what the declaration says — usually 9:00 for a full
  day, which agrees with the 9-hour workday the leave file's own arithmetic implies
  (`DATA-SOURCES.md` D13).
- **Amends ADR-016's reproduction recipe.** Reproducing the pre-2026-08-17 report now
  needs three switches, not two: `break.deduct: true`, `daily_hours: union` **and**
  `remote_day_replaces_attendance: never`. Verified with all three: June brüt
  `26964:33`, net `24971:48`.

---

## ADR-019 — Flag a person-day shorter than two hours

2026-08-17 · Status: **Accepted** · Decided by: HR manager, via project owner

### Context

HR asked for days with less than two hours between entry and exit to be identified.
The project owner believed this already happened. It did not: `plausibility.min_minutes`
is **5 minutes** and applies to a single interval, catching badge-test artefacts like
`13:32 → 13:34`. Nothing looked at the day as a whole, so a 40-minute working day
passed without comment.

### Options considered

1. **A separate per-day check** with its own configured threshold
2. Raise `min_minutes` to 2 hours
3. Reuse `SUSPICIOUS_SHORT` for both

(2) would exclude or flag every legitimate short interval inside a normal split day —
a 20-minute afternoon segment is not a problem. (3) merges two different questions
under one label, so HR could not tell a bad record from a short day.

### Decision

Option 1. `plausibility.short_day_hours: 2.0`, checked against the day's **measured**
duration after ADR-015 and ADR-018 have been applied, emitting `SHORT_DAY`
("Günlük süre eşiğin altında") at `included` severity and tagging the day `kısa-gün`.

Strictly less than the threshold: exactly 2:00 is not "under 2 hours", so there is no
ambiguity at the boundary. `min_minutes` is unchanged and keeps doing its own job.

### Consequences

- 15 person-days in May 2026 (7:06 total) and 20 in June (about 10 h) are now
  surfaced. They were previously invisible.
- The hours do not change. These days are counted; the flag is a question, not an
  exclusion — a genuinely short day exists (someone left ill) and the tool must not
  decide which.
- `Sorulacaklar` gains a row per affected person, and `Günlük Detay` a `kısa-gün` tag,
  so the days are filterable.
- The threshold is HR's number. If they revise it, it is a YAML edit.

---

## ADR-020 — Read every Excel container, derive columns from the header, and check period coverage

2026-08-18 · Status: **Accepted** · Decided by: project owner

### Context

July 2026's inputs arrived and the run failed. Investigating produced three separate
findings, all in the Macunköy and Teknopark exports, all in one month:

1. **The container changed.** `Macunköy Temmuz Mesai giriş-çıkış.xls` is a genuine
   OLE2/BIFF file (`d0cf11e0`), not `.xlsx`. `openpyxl` cannot read it at all, and the
   glob only matched `*.xlsx`, so the run stopped at "file not found".
2. **A column was dropped.** `Personel` (the full-name column) is gone, shifting every
   column after it one place left: 11 columns became 10. A reader with fixed indices
   would have read `SicilNo` as the employee name and `Bolum` as the date.
3. **A title line appeared** above the header, so the header is no longer row 1.

And once those were fixed, a fourth, worse finding: **the Teknopark export covers only
1–19 July.** It was taken on the 20th. The pipeline produced a full-month report from
it — 16 029 h against June's 27 119 h — with every existing guard passing and the
reconciliation reading `TAMAM`. The file was internally consistent: complete data
about an incomplete period. That is the exact failure mode ADR-014 was written for, in
a form ADR-014 does not catch.

This also retires the answer to Q10. "Does the export format change month to month?"
was answered **No** on the strength of June. July says yes, three times over.

### Options considered

For the container: (1) **support `.xls` via xlrd**, (2) ask HR to re-export as `.xlsx`
every month, (3) convert manually. (2) and (3) put a manual step in front of a tool
whose whole point is that a non-technical person runs it unattended — the format will
change again and they will be stuck.

For the columns: (1) **derive positions from the header**, (2) add a second index
table for the July layout. (2) needs a new branch for every future variation and gets
it wrong silently.

For coverage: (1) **warn loudly and exit non-zero**, (2) fail the run outright,
(3) leave it. (2) blocks a legitimate mid-month "how are we doing" run. (3) is what
just happened, and the report was on its way to a manager.

### Decision

All three, plus the guard:

**Container.** `readers/base.open_sheets` opens `.xlsx`/`.xlsm` with openpyxl and
`.xls` with xlrd, returning a uniform in-memory `Sheet` whatever the format. Container
handling lives in exactly one place; the four readers were migrated onto it and know
nothing about either library. `.xlsb` is deliberately **not** supported — it has never
arrived, and the error names it so the fix is obvious if it does.

Two traps handled inside the adapter: xlrd returns dates as bare floats (unconverted,
every timestamp becomes meaningless and every person gets zero hours, reported as
success), and reading whole sheets up front sidesteps the merged-range problem that
made `read_only` unsafe for Teknopark.

Source globs widened to `*.xls*`, so a container change is no longer "file not found".

**Columns.** `readers/base.find_header_row` locates the header within the first ten
rows and maps names to 1-based positions. `macunkoy.py` now addresses every column by
name, requires only `Ad`, `Soyad`, `MesaiTarih`, `Giris`, `Cikis`, and treats
`Personel`, `SicilNo`, `Bolum`, `SureSaat` as optional — the full name is rebuilt from
`Ad` + `Soyad` when `Personel` is absent. `AGENTS.md` §5 already demanded this for the
roster; it now holds for every source.

**Coverage.** `SourceCoverage` per attendance source: expected working days present,
and the **trailing run** of expected working days with no record. The trailing run is
the signal, not the raw absent count — Teknopark legitimately has nothing on days the
office is shut while Macunköy production runs, so "fewer days than the other source"
means nothing. A gap in the middle is a different problem and is not reported as a
partial export. More than one trailing day is partial; one is tolerated, because an
export run on the last working day has nothing for it yet.

When any source is partial: a red banner at the top of `Aylık Özet` above the table, a
`3. Dönem kapsamı` section on `Kontrol`, a CLI warning, and **exit code 5** so an
unattended run is noticed rather than discovered at payroll.

### Consequences

- July 2026 runs, and says plainly that it is incomplete: `13 / 23` working days for
  Teknopark, `20.07.2026 ve sonrası yok`. The hours in it must not be used.
- May and June are byte-for-byte unchanged after the reader migration — `17103:58` and
  `27119:24`, same anomaly counts, 127 tests green throughout. The migration was
  behaviour-preserving by construction and verified as such.
- New runtime dependency: `xlrd` (pure Python, `.xls` only). It must go into
  `environment.yml`, `pyproject.toml` and any packaged build.
- A future column rename still fails the run, but now with a message naming the
  missing column instead of a wrong number. Positional assumptions are gone from the
  Macunköy reader; the Teknopark reader is still block-offset based, because its
  layout is not a header table — that remains a known fragility, held by the
  per-block total check.
- HR must re-export July's Teknopark file for the full month. Q10 is reopened as Q23:
  the format is *not* stable, so every month's first run should be assumed to need a
  look at the `Kontrol` sheet.

---

## ADR-021 — Every run writes a machine-readable snapshot; nothing ever parses the workbook

2026-08-18 · Status: **Accepted** · Decided by: project owner

### Context

Phase 4 sends each employee their own figures. The obvious way to build it is to read
the workbook that was just produced — it already holds the numbers, and re-running the
pipeline to send mail feels wasteful. The project owner asked directly whether the
existing report could simply be selected and worked from.

It cannot, for three reasons that are specific rather than stylistic:

1. **The workbook is a presentation artifact.** Durations are `HH:MM` strings, cells are
   merged, headers are Turkish. Reading it back means deriving data from formatting.
2. **E-mail addresses are not in it, deliberately.** `OUTPUT-SPEC.md` §1 excludes them:
   putting 162 addresses in a circulated workbook serves no reporting purpose. So the
   one thing the mail step needs most is the one thing that file does not contain.
3. **Its layout changes when a rule changes.** On 2026-08-17 the four gross/net columns
   became a single `Çalışma Süresi` pair (ADR-016). A step parsing column J would have
   broken silently that day.

### Options considered

1. **Write a JSON companion in the same run**, and have everything downstream read it
2. Parse the workbook
3. Recompute from the source files whenever mail is sent
4. Add a hidden sheet inside the workbook carrying the raw data

(3) is worse than it looks: mail would go out with figures that differ from the ones a
human reviewed, because a source file may have been re-uploaded in between. Sending
payroll-adjacent numbers that nobody approved is the failure this project exists to
avoid. (4) puts 162 e-mail addresses back into the circulated file, undoing a
deliberate choice, and still requires parsing.

### Decision

Option 1. `src/mesai/snapshot.py` writes `veri/gonderim-<period>.json` in the same run
that writes the workbook, from the same computed objects, so the two cannot disagree.

Deliberate details:

- **Next to the program, not beside the workbook.** The folder HR opens should hold one
  file per month; this one holds personal data. `veri/` and `gonderim-*.json` are
  git-ignored — they were one commit away from being committed.
- **Minutes as integers**, not floats or formatted text. A float round trip is how 9:39
  becomes 9:38.
- **The active rules travel with the data** (`daily_hours`, `break_deducted`,
  `short_day_hours`, `remote_replaces_attendance`). Without them a snapshot read months
  later cannot be interpreted: the same numbers mean different things under a different
  break setting.
- **Per-person problem labels**, so "mail only the people missing an exit punch" is a
  filter rather than new logic. `info`-severity anomalies are excluded — expected
  behaviour must not put somebody on a mailing list (ADR-017).
- **A format version, refused rather than guessed.** An unknown version, a corrupt file
  or a missing file all raise with an instruction to regenerate. No best-effort read.
- Written to a temp file and moved, like the workbook: a crash mid-write must not leave
  a half-valid file that still parses.

### Consequences

- The owner's "select the existing report and work from it" workflow is available, and
  it is what makes it possible — loading a snapshot returns exactly the figures a human
  reviewed. From the user's side nothing differs; the program finds the JSON beside the
  report. If it is absent (a report from an older version) the answer is a clear
  "regenerate", never a silent parse.
- `is_complete` lets a later step refuse a snapshot built from a partial month
  (ADR-020), so a mid-month export cannot quietly become 162 e-mails.
- The JSON is personal data and must be handled as such: never committed, never sent
  anywhere, deleted with the same care as `data/`.
- Two artifacts per run means two things to keep in step. They are built in one function
  from one set of objects specifically so that staying in step is not a discipline
  problem.

---

## ADR-022 — A source that is not in the folder can be named outright

2026-08-18 · Status: **Accepted** · Decided by: project owner

### Context

Until now the run took **one folder** and found all three monthly exports inside it by
glob. That is the normal case and it should stay the default: the files arrive together
on the share, one folder per month.

It is not the only case. One export can arrive by e-mail while the others sit on the
share, or be produced later than the rest. The only answer the tool offered was "copy
them all into one folder first" — a manual step before every run, done by hand, on
payroll inputs. That step is exactly the kind that eventually gets done wrong: the
wrong month copied, a stale file left behind, a half-finished folder run anyway.

The folder check already knew *which* source was missing — it reports all three, found
or not. It just had nothing to offer once it knew.

Doing this badly would be worse than not doing it. Guessing which nearby file is
"probably" the missing export, or silently searching parent folders, would put an
unreviewed file into a payroll figure. Whatever is chosen has to be chosen by a person.

### Decision

1. `pipeline.run()` accepts `chosen`, a mapping of source key → file path. A named
   file **bypasses the glob for that one source** and nothing else. The other sources
   still come from the folder.
2. A named file is **checked for existence, not assumed.** If it is gone by the time
   the run starts, the run fails naming it — it never silently falls back to globbing,
   because that would read a different file than the one a person approved.
3. A named file **settles an ambiguous folder too.** Two files matching one pattern is
   otherwise an error (ADR-014 §3); pointing at one of them is a legitimate answer to
   that error, not a way around it.
4. The window offers this **per source, only where it is needed**: a source that was
   found where it was expected gets no button. A missing or ambiguous one gets `Seç…`;
   a hand-picked one gets `Geri al`, which returns it to the folder.
5. Hand-picked files are **forgotten when the folder changes.** They belonged to the
   month they were picked alongside.
6. A hand-picked file whose name does not match the source's patterns is **flagged and
   still used.** The patterns are a convention, not a rule — a renamed export is still
   that export — and refusing it would disable the escape hatch in the one case it
   exists for. The reader validates the layout, so a genuinely wrong file still fails.
7. Nothing is remembered between sessions, for the same reason the input folder is not
   (see `gui/rapor.py`): a restored month-specific path is a plausible wrong default.

### Consequences

- **ADR-014 is unchanged.** `--ay` is still a filter: records outside the month are
  still dropped, and a source contributing nothing inside the month still fails the
  run. A file pulled in from another folder cannot smuggle in another month's data —
  the guard that catches it is the same one that always did.
- "One month per input folder" remains the contract for the *folder*. What is now
  possible is a month whose files are not all in one place, which is a different thing
  from a folder holding two months.
- The CLI is unaffected: `chosen` defaults to nothing and `rapor.cmd --ay` behaves
  exactly as before. It is reachable from the CLI if a use ever appears, but no flag
  was added for a need nobody has stated.
- The `Kontrol` sheet already records the file name used per source, so a report built
  from files in three different places still says which three files it read.

---

## ADR-023 — A source whose every record falls outside the month fails the run

2026-08-18 · Status: **Accepted** · Decided by: project owner (asked), implementation

### Context

ADR-014 made `--ay` a filter: records outside the month are dropped and counted, and
**if no record at all falls inside the month the run fails.** That last check is
global. It fires when every source is the wrong month — pointing at May's folder with
`--ay 2026-06` — and that was the only case it was written for, because until ADR-022
all three exports came from the same folder and were therefore the same month.

Once one source can be named separately, they can disagree. So the question was asked
directly: what happens if the three chosen files are different months?

**Measured, not reasoned about.** The real May inputs with June's Teknopark export
substituted, run as `2026-05`:

| | Mixed | Correct |
| --- | --- | --- |
| Total working time | **4 869:54** | 17 103:58 |
| People with attendance | 88 | 145 |
| Person-days | 526 | 1 823 |
| Warning, banner, exit code | **none** | — |

The run **succeeded**. All 2 557 Teknopark rows were dropped as out-of-period, the
report came out 72 % short, and nothing said so. The global check passed because
Macunköy still had May records. The coverage check (ADR-020) never saw the source at
all — it builds its source list from the records that *survived* the filter, so a
source reduced to nothing simply is not there to be flagged. The only trace was the
`out_of_period` count on the `Kontrol` sheet.

A confident, normal-looking report that is 72 % short is precisely the failure this
project exists to prevent, and it is worse than the ADR-014 bug it descends from: that
one at least had a wrong title on it.

### Decision

A source that **read records but kept none inside the period** fails the run, naming
the source, the range expected, the range the file actually holds, and how many
records were dropped.

The distinction that makes this safe is between *nothing read* and *nothing kept*:

- **Read nothing** → no error. Teknopark legitimately has no rows while the office is
  shut, which is exactly why AGENTS.md forbids a "fewer days than the other source"
  check.
- **Read rows, kept none** → the wrong file. There is no legitimate way for a month's
  export to contain records exclusively outside that month.
- **Kept even one** → no error. A stray row from the previous month is a data quirk,
  not a wrong file, and ADR-020's coverage check is what speaks to partial months.

Two supporting changes, neither of which decides anything:

1. The window warns from the **file name** when it mentions a different month than the
   period (`Teknopark - Haziran …` under `2026-05`). It moves the discovery to before
   the button rather than after it. The name is a weak signal — a file naming two
   months says nothing, and a file naming none is not suspicious — so it is a caution
   colour on a still-usable row, never a refusal. The dates inside the file remain the
   authority.
2. The window no longer files this under "Dosyalar okunamadı". A wrong-month export
   reads perfectly; what is wrong is which file was handed over.

### Consequences

- Exit code **2** (`GİRDİ HATASI`), same as any other input problem. Not code 5 —
  that means "the data is real but the period is incomplete" (ADR-020), which is a
  report you may still want. This is a report you must not have.
- The check is on `PunchRecord.source`, so it covers Macunköy, Teknopark, and the
  remote-work rows the leave export contributes. Leave rows without a start date are
  kept unconditionally by the filter, so a wrong-month leave file is caught by its
  remote-work rows rather than by its absences — worth knowing if that ever changes.
- ADR-014's global check is kept rather than folded into this one. It has a better
  message for the case it covers: when *everything* is the wrong month, naming one
  source would point at the wrong problem.
- It cannot be turned off, and there is deliberately no override. "Run it anyway" here
  means publishing payroll hours known to be missing a site.
