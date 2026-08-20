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

---

## ADR-024 — The window writes where the user chose, one folder per month, snapshot included

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

The window wrote its workbook to `data/out/<period>/` beneath the program, and its
snapshot to `veri/` beside the program. Both are fine for a developer running from a
clone. Neither is where the person who actually runs this every month would look.

Worse, the two halves of one run were in two unrelated directories, and
`snapshot.default_path` justified that in its own docstring — "deliberately NOT beside
the workbook: the folder HR opens should hold one file per month". ADR-021 had already
written the opposite: "the program finds the JSON beside the report". The code and the
decision had been contradicting each other since the snapshot was introduced, and
nobody noticed because both files were found by path, never by looking.

### Decision

1. **The window asks where output goes, and defaults to the Desktop.** The Desktop is
   resolved through `SHGetKnownFolderPath(FOLDERID_Desktop)`, not assumed to be
   `~/Desktop`: a machine with OneDrive redirection has it somewhere else, and writing
   the month's payroll report into a folder nobody opens is a silent failure.
2. **The choice is remembered between sessions.** This is the exact opposite of the
   rule for the *input* folder, and the difference is the reason: the input folder is
   month-specific, so restoring it offers a stale month pre-filled and ready to run.
   The output folder is not — the month lives in the subfolder — so last month's
   choice is still exactly right this month.
3. **One folder per month, named `06-2026 Rapor`.** Month first and the word that says
   what it is, because it is read in Explorer by a person, not sorted by a program.
   The cost is sort order: twelve of these sort by month, not by date. Accepted —
   they are opened one at a time, right after being made.
4. **The snapshot goes in that folder too**, resolving the contradiction above in
   favour of ADR-021. `snapshot.default_path` now takes the workbook's path and
   returns a sibling, so the CLI's snapshot follows its `--cikti` as well.
5. **The CLI default is unchanged**: `data/out/<period>/mesai-raporu-<period>.xlsx`,
   with the snapshot now beside it. The *layout* is the same in both front ends — one
   folder holding the pair — only the folder's name and location differ, and the name
   is a presentation choice for whoever opens it. No flag was added to the CLI for a
   need nobody has stated; `--cikti` already exists.
6. The window's caption for the snapshot no longer says "İK'nın açması gerekmez".
   Whether HR needs to open it is not that line's business; it says what the file is
   for and stops.

### Consequences

- **`veri/` is no longer written by either front end.** The `.gitignore` entry stays as
  belt and braces, and so does `gonderim-*.json`, which matches the file wherever it
  now lands — including a Desktop, which is the point of having a filename rule rather
  than a folder rule.
- The snapshot is personal data (names, e-mail addresses, hours) and now sits next to
  the workbook on somebody's Desktop. That folder already held names, badge-derived
  hours and department data; the addition is e-mail addresses. It is not a new class of
  exposure, but it is one more file to delete with the same care as `data/`.
- A run no longer needs the program's own directory to be writable. That matters for
  the packaged executable, which may end up somewhere read-only.
- `Klasörü Aç` now opens the month's folder with both files in it, rather than a
  directory of every month ever produced.

---

## ADR-025 — The month folder is `2026-06 Rapor`; a rerun overwrites in place

2026-08-19 · Status: **Accepted** · Decided by: project owner · Supersedes ADR-024 §3

### Context

ADR-024 named the folder `06-2026 Rapor`, month first, because that reads more
naturally in Turkish and the folder is opened by a person in Explorer. It also
recorded the cost and accepted it: twelve of those sort by month, not by date.

That cost is larger than it looked. The folders accumulate — one per month, in whatever
directory the user chose, for as long as the tool is in use. After a year the list
reads `01-2027, 02-2027, 05-2026, 06-2026, …`, with next January above last May. The
argument for accepting it was that folders are opened one at a time right after being
made, which is true of the newest one and false of every other.

Separately, the question came up of what a **second run for the same month** does, and
it had never been stated anywhere.

### Decision

1. **`2026-06 Rapor`.** Year first, so a directory of them sorts into date order with
   no effort. The trailing word still says what the folder is, which was the other half
   of ADR-024's reasoning and is kept.
2. **A rerun overwrites in place.** Measured rather than assumed: running the same
   month twice into the same folder rewrites both the workbook and the snapshot with
   fresh timestamps, does not recreate the folder, and leaves anything else in it
   untouched. That is the right behaviour — the report is derived, so regenerating it
   is how a corrected input gets applied — and it is now **said before the button**:
   when a report for that month is already there, the window says so in the caution
   colour instead of letting it be discovered afterwards.
3. If the workbook is open in Excel the run fails with `ReportLocked` and a plain
   "close it" message, as it already did (ADR-014 §4). Nothing is half-written.

### Consequences

- Folders made under ADR-024's naming (`06-2026 Rapor`) are not migrated. There are at
  most a handful, none of them referenced by anything, and a rename that touches a
  user's Desktop is not something this tool should do on its own.
- The overwrite notice is a statement, not a confirmation dialog. Nothing is lost that
  cannot be rebuilt by running again, and a prompt on every rerun of a routine monthly
  job trains people to dismiss prompts.

---

## ADR-026 — The report calls the sites Macunköy and Teknopark, not what the HCM calls them

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

The roster's `Tesis` column holds two values: `MACUNKÖY TESİSİ` (53 people in May 2026)
and `DEICO TESİS` (107). They were passed through to the report untouched.

`DEICO TESİS` names the company, not the place. The site is Teknopark — `AGENTS.md` §4
already says so, and the attendance records from it are labelled `Teknopark` everywhere
else in the same workbook. A reader on `Aylık Özet` sees `Tesis: DEICO TESİS` next to
`Kayıt Kaynağı: Teknopark` and has to work out that these are the same building. The
suffix on the other one is noise for the same reason `Teknopark puantaj` was.

### Decision

`config/settings.yaml:facility_labels` maps a **folded substring** to a display label:

```yaml
facility_labels:
  MACUNKOY: "Macunköy"
  DEICO: "Teknopark"
```

- **In config, not in code.** The other label tables in `workbook.py` name keys this
  project owns (`macunkoy`, `teknopark`, `izin`) and those are stable. These keys come
  from a file the HCM writes and we do not control — the roster's filename and sheet
  name have already changed once — so changing them must be a YAML edit.
- **Substring on the folded form**, so `MACUNKÖY TESİSİ`, `MACUNKOY TESIS` and a future
  `MACUNKÖY TESİS 2` all resolve, and Turkish casing cannot break it. Longest needle
  wins, so a more specific entry can be added later without the shorter one shadowing
  it.
- **An unmatched value is shown exactly as the roster wrote it.** Never guessed. A
  label table that has fallen behind the source must not rename the wrong site, and an
  unfamiliar name appearing in the report is how somebody notices.
- **Section 8 of the `Kontrol` sheet lists every facility seen and what it was shown
  as**, with anything unmapped highlighted. Same shape as the alias table in section 7,
  and for the same reason: a mapping that silently stopped applying looks exactly like
  a mapping that had nothing to do.
- Not required, and no default in code: an absent key means no renaming, which is the
  safe direction. It is not a payroll figure, so it does not join the three keys that
  fail the run when missing.

### Consequences

- `tests/conftest.py` mirrors the table and `test_config.py` fails if the two drift.
  That guard exists because the fixture has drifted from the shipped config once
  before, and every test kept passing against patterns the program no longer used.
- The snapshot carries `facility` too, and it is **not** relabelled there — it holds
  what the roster said. The workbook is presentation; the snapshot is data, and a
  downstream consumer should see the source value.

---

## ADR-027 — Note labels are keywords; the sentence moves to its own column

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

Every anomaly kind carried one Turkish sentence used in three places: the `Sorun`
column of two report sheets, and — since ADR-021 — the `problems` list in the snapshot.
Sentences are fine in a column. They are not fine in a **filter**, and a filter is
exactly what the next screen needs: pick a note, see the people it applies to.
`Uzaktan çalışma beyanı var, o gün gerçek turnike kaydı da var` cannot be scanned in a
dropdown.

Two of the old labels were worse than long. `Süre çok kısa` named **two different
thresholds** — one reading under 5 minutes, and a whole day under 2 hours. Filtering on
it would have selected both groups. And the obvious short forms for the missing-punch
pair are ambiguous in Turkish: "sadece giriş" reads equally as *only the entry exists*
and *only the entry is missing*, which are opposite people.

A third thing surfaced while measuring, and it mattered more than the wording. The two
remote-work kinds had been documented from a measurement taken before ADR-018 changed
the order of operations. Re-measured on the real May 2026 data:

| `remote_replaces` | notes emitted |
| --- | --- |
| `nominal_only` (shipped) | replaced-nominal **35**, overlap **0**, real-punch **2** |
| `never` | replaced-nominal 0, overlap **35**, real-punch 2 |
| `always` | replaced-nominal 37, real-punch **0** |

ADR-018 *removes* the system's placeholder day and counts the remote hours, so nothing
is left to overlap with. The kind named for the overlap never fires under the shipped
configuration. The plain name had been put on it — a filter entry that would always
have come back empty.

### Decision

1. `DESCRIPTIONS[kind]` becomes `(label, severity, explanation)`. The **label is a
   keyword**; the **explanation is the sentence**, and `Sorulacaklar` gains an
   `Açıklama` column so the report says no less than before.
2. **No two kinds may share a label** — the label is the filter key, so a duplicate
   would silently merge two groups. A test enforces it, as does a length limit.
3. The ambiguous pairs are split by wording, not shortened into the ambiguity:
   `Giriş yok` / `Çıkış yok` / `Giriş-çıkış yok`, and `Aralık çok kısa` (one reading)
   versus `Gün çok kısa` (the whole day).
4. The remote pair is named for what the shipped config actually produces:
   `Uzaktan + sistem kaydı` (35 days) and `Uzaktan + kart kaydı` (2 days). The
   unreachable overlap kind keeps a qualified name, `Uzaktan + sistem kaydı
   (birleştirildi)`, so switching `remote_replaces` still produces a distinct,
   readable label rather than a collision.
5. "Nominal" and "puantaj" are gone from every user-facing string. They described how
   a vendor system happens to record a day; the reader never has to make that
   distinction.

### Consequences

- **The snapshot's `problems` values change**, because they are labels. Its
  `format_version` goes up, and `snapshot.py` already refuses an unknown version with
  "regenerate" rather than parsing it. Reports and snapshots produced before this are
  not comparable by label.
- The label is now load-bearing in a way it was not: it is an identifier a person
  filters on, not only text. Renaming one is a breaking change to any saved selection,
  which is a reason to keep them stable once the people screen exists.
- `Şüpheli Kayıtlar` keeps its per-row `Açıklama` (the record's own detail) — that is a
  different thing from the kind's explanation, and both earn their place.

---

## ADR-028 — A people screen: filter a month's data file by note, pick who is in the list

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

The report answers "how many hours did everybody work". The next question is "who do I
need to do something about" — everyone missing an exit punch, everyone with no
attendance at all — and until now that meant scrolling a workbook.

Two things were already in place for this and had been since ADR-021: the run writes a
machine-readable data file, and that file carries each person's note labels. ADR-027
then made those labels keywords, which is what makes them usable as a filter.

### Decision

**A second work face**, registered as one entry in `app.SCREENS` — the rail, the lazy
construction and the state-preserving switch all come from ADR-022's shell for free.

1. **The rule lives in `mail/recipients.py`, not in the window.** A filter, an
   exclusion set, and the selection that survives both — pure functions over a
   `Snapshot`, tested with hand-written expectations. `ARCHITECTURE.md` §3 already says
   `cli.py` holds no business logic; a widget is a worse place for one, because a rule
   that can only be exercised by clicking is a rule nobody checks.
2. **The filter list is built from the loaded file, never hard-coded.** A note nobody
   has does not appear; a note added to `anomalies.py` later appears with no change
   here. The list of things worth filtering by is a property of the data.
3. **`info` labels are carried in the data file, in their own `expected` field**
   (`format_version` 3). They must be reachable — "show me everyone whose remote day
   the system filled in" is a real question for a manager — but they must not join
   `problems`, because ADR-017 exists precisely because expected behaviour once made 21
   people look defective and buried the 2 real questions among them. The screen lists
   problems above expected behaviour for the same reason.
4. **Removal is by name, not by row.** The list re-sorts and re-filters under the user;
   a remembered index would quietly come to mean somebody else.
5. **Changing the filter forgets removals.** They belonged to the group they were made
   in. Carrying them across would keep somebody out of a list they were never removed
   from — and it would be invisible.
6. **A person with no address is shown and counted, not dropped.** Eleven of May's 171
   are leavers the roster no longer carries an address for. Silently removing them
   would make a list of 30 quietly become 27.
7. **An incomplete month says so** in the error colour, above the list. ADR-020's
   `is_complete` already knew; this is the last screen before somebody acts on it.
8. **The report screen hands its data file over when a run finishes.** Neither screen
   knows the other exists — the shell holds `last_snapshot` and passes it on. A screen
   nobody has opened is not built just to receive it; it loads on first opening
   instead, and the two paths agree.

**No sending.** The screen filters, selects and copies a list. The three open questions
about mail — preview or send, whether a hand-removed person is recorded, whether an
incomplete month may be mailed at all — are untouched, and the screen is useful without
them.

### Consequences

- `format_version` 3. A file from before this is refused with "regenerate" rather than
  read with an empty `expected`, which would have looked like "no expected notes" and
  been indistinguishable from a month that genuinely had none.
- Label stability now matters more than it did. The label is what a person filters on;
  ADR-027 already made it a key, and a saved selection would break on a rename.
- The exclusion list is in memory only. A future "these people never get mail" file —
  the owner expects one — is a different thing: a standing rule rather than one
  session's choice, and it belongs in `recipients.py` beside the filter, not in the
  screen.

---

## ADR-029 — The filter list is grouped by family and ordered by declaration, not frequency

2026-08-19 · Status: **Accepted** · Decided by: project owner · Corrects ADR-027

### Context

The people screen ordered its filter list by how many people carried each note. In
June 2026 that produced:

```
Çıkış yok (54)   Giriş-çıkış yok (34)   Aralık çok kısa (20)   Mesai verisi yok (18)
Tesis birleştirme (18)   Süre çok kısa (17)   Giriş yok (15)   ...
```

`Giriş yok` sits four rows below `Çıkış yok`, separated by three unrelated notes,
purely because fewer people happened to have it — and those two are precisely each
other's neighbour when somebody is deciding which one they want.

Frequency ordering has a second cost that only shows up over time: the list reshuffles
every month. Somebody who learned where a note sits has to find it again in July.

Separately, ADR-027 stated that `REMOTE_OVERLAP` was "only reachable with
`remote_replaces: never`". **That was wrong.** June 2026 has one. The day held a remote
declaration, the system's default `09:00–18:00`, *and* a broken Macunköy record with no
exit punch. The replacement rule stands down when the day carries an attendance record
that is not the system's default, so nothing was replaced and everything was merged.
The label it carried — `Uzaktan + sistem kaydı (birleştirildi)` — explained none of
that, and the project owner reasonably asked what it was doing there.

### Decision

1. Every note declares a **family**: `Eksik kayıt`, `Süre`, `Uzaktan çalışma`, `Diğer`.
   The filter list is ordered by family, then by **declaration order** within it. Both
   halves are curated, so the list is identical every month and related notes are
   adjacent.
2. Frequency no longer affects order at all. The count is still shown — it is what
   tells somebody whether a filter is worth opening — it just does not move the row.
3. Grouping mixes expected-behaviour notes in among real problems, which is what
   ADR-017 spent its effort separating. So each one now **says so in the list**:
   `Uzaktan + sistem kaydı  (36)  ·  beklenen durum`. Position no longer carries that
   meaning, so the text has to.
4. `REMOTE_OVERLAP` is renamed `Uzaktan + sistem + ek kayıt`, and its explanation says
   what actually happened: another card record on the same day meant no replacement was
   made. It is rare — one day in June, none in May — but it is real, and a label whose
   only content is "(birleştirildi)" tells the reader nothing.

### Consequences

- Adding a note now means choosing its family. A note with an unfamiliar family sorts
  last rather than failing, because labels arrive from a data file that a future
  version may have written.
- A test that asserted "problems are listed before expected behaviour" was **removed,
  not adapted**: family grouping makes it false — June's `Uzaktan + kart kaydı` is a
  problem and sits below an expected note. A test that keeps passing while stating
  something untrue is worse than no test.
- ADR-027 stays as written, including the claim this corrects. ADRs are appended to,
  never edited; the record of having been wrong is part of what the log is for.

---

## ADR-030 — A month that is mostly unaccounted for gets a note

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

Two rules already looked at how little somebody worked, and there was a gap between
them wide enough to drive a month through.

* `short_day_hours` (ADR-019) flags **one day** under two hours.
* `NO_ATTENDANCE_DATA` flags a person with **no card record at all**.

Neither catches a person with one perfectly ordinary day and twenty-one missing ones.
Found by the project owner looking at June 2026's "no problems" list and asking why
some of them had two-digit monthly totals. Measured:

| Total | Worked days | Leave | Of 22 expected days, explained |
| --- | --- | --- | --- |
| 2:30 | 1 | 0 | **1** |
| 9:00 | 1 | 1 | 2 |
| 9:00 | 1 | 0 | **1** |
| 18:00 | 2 | 5 | 7 |

All four carried **no note whatsoever** and sat in the clean list. Their days were
above the two-hour threshold, so no per-day rule fired; they had records, so the
empty-month rule did not fire either. A person with 2.5 hours in a month appeared
alongside people with 180, with nothing to distinguish them.

That is the failure mode AGENTS.md §2.2 exists to prevent: not a wrong number, but a
real question that nothing surfaces.

### Decision

A person **with attendance** whose worked days plus leave days cover less than
`plausibility.sparse_month_ratio` of the period's expected working days gets the note
`Ay büyük ölçüde boş`. The threshold ships at **0.5** — the project owner's choice from
measured options.

- **`included`, not `excluded`.** Their hours are real and stay in the total. This
  changes no figure anywhere; May 2026 still reports 17 103:58.
- **A flag for a human, never an exclusion.** The roster carries no hire or leaving
  dates (ROADMAP Q18), so somebody who started on the 20th is indistinguishable from
  somebody whose records went missing. The tool must not pretend to know which — and
  the person it cannot classify is exactly the person worth asking HR about.
- **Leave counts as explanation.** Three weeks of annual leave is an accounted-for
  month, not a suspicious one.
- **Not applied to a month with no records at all.** That already has the louder
  `Mesai verisi yok`, and two notes for one situation reads as two problems.
- **An absent threshold disables the check** rather than defaulting to a number. This
  rule decides who a human is asked about; a made-up default would either accuse
  people or hide them, and silently either way.

### Consequences

- June 2026's clean list drops from 51 people to 47, and nobody under 20 hours remains
  in it. May gains 5 notes. No hours move.
- `tests/conftest.py` mirrors the threshold and `test_config.py` compares the whole
  `Plausibility` object, not field by field — the fixture had already drifted from the
  shipped config twice, and leaving the ratio out would have disabled the rule for the
  entire suite while every test still passed.
- It will flag legitimate mid-month joiners and leavers until the roster carries dates.
  That is understood and accepted: the note says so in its own explanation, so nobody
  reading the report has to guess what it is claiming.

---

## ADR-031 — Drop the per-interval short-reading note; the day is the unit

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

`plausibility.min_minutes` flagged any single entry→exit interval under five minutes —
the `13:32 → 13:34` badge test. It was introduced to surface a bad *record*, and it
did that faithfully: 11 people in May 2026, 20 in June.

The trouble is what it meant to whoever read the list. Of the people whose **only**
note it was — 3 in May, 5 in June — every single one had an entirely ordinary month
behind them: 106 to 242 hours over 11 to 24 days. The note was reporting a stray
reading, not a person who needed looking at, and it put them in the same list as
somebody with no attendance data at all.

The project owner's judgement: the question worth asking is per-day, and
`Süre çok kısa` (a whole day under two hours) already asks it.

### Decision

Remove `SUSPICIOUS_SHORT` and the `min_minutes` threshold. A two-minute interval is
still read and still counted — it is real badge data, and ADR-003 has always held that
we do not delete records. It simply no longer raises a note on its own.

The day-level checks are unchanged and are now the only ones: `Süre çok kısa` (under
two hours in a day) and `Ay büyük ölçüde boş` (under half the month accounted for).

### Consequences

- May's anomaly count falls from 262 to 250, June's from 449 to 426. **No hours move** —
  May still reports 17 103:58.
- June's clean list grows from 47 to 52. Those five have ordinary months and nothing
  else to say about them, which is the point.
- The 16-hour ceiling (`Aralık çok uzun`) is untouched and remains **per interval and
  excluding** — it is the one plausibility rule that changes a payroll figure, and the
  project owner has explicitly reserved it for a separate conversation: whether
  somebody can genuinely work more than sixteen hours, and whether counting such a day
  as zero is the right answer. That question is open.

---

## ADR-032 — The 16-hour ceiling rejects our own repair, not a long day

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

`plausibility.max_shift_hours` excluded any interval over sixteen hours, counting that
person-day as **zero**. It was the only plausibility rule that changed a payroll figure,
and the project owner asked the obvious question: can somebody not genuinely work more
than sixteen hours?

All six exclusions across May and June 2026, opened one at a time:

| Date | Raw record | Duration | What it is |
| --- | --- | --- | --- |
| 21.05 | `13:58:56 → 13:57:50` | 23:58 | exit one minute **before** entry |
| 14.05 | `18:08:28 → 16:04:41` | 21:56 | exit before entry |
| 09.06 | `09:08:10 → 09:08:06` | 23:59 | four seconds apart |
| 22.06 | `07:24:38 → 23:31:25` | **16:06** | **a real shift** |
| 30.06 | `07:19:04 → 23:58:21` | **16:39** | **a real shift** |
| 30.06 | `08:28 → 07:37 (+1d)` | 23:09 | source states it plainly; implausible but stated |

Two people had a day they actually worked counted as zero.

The first three share a property the others do not: the exit **precedes** the entry, so
the tool assumes the shift crossed midnight and adds 24 hours. That assumption is
*ours*. When it produces 23:58 out of two timestamps a minute apart, the assumption was
wrong — and rejecting the record is right.

Simply removing the ceiling was measured and is worse: it admits those three, adding
45:46 to May and 63:20 to June out of nothing.

### Decision

Split the rule along the line the data draws.

1. **A repaired interval over the ceiling is refused**, as before, under a label that
   now says why: `Giriş-çıkış tutarsız`. We do not trust a guess of ours that produces
   an impossible figure.
2. **An interval the source states plainly is kept, however long.** ADR-003's principle
   applied in the other direction: we do not invent data, and we do not discard what the
   source plainly says either.
3. **A person-day over sixteen hours is flagged, not excluded** —
   `Günlük süre çok uzun (>16 saat)`, counted, `included`. It is the mirror of
   `Günlük süre çok kısa (<2 saat)`, measured the same way, at the same level.
4. Both short and long labels **carry their threshold in the name**. Somebody choosing
   a filter should not have to look up what "short" means, and the value is the whole
   content of the rule.

### Consequences

- **May is unchanged at 17 103:58** — both of its cases were repairs. **June goes from
  27 119:24 to 27 166:19, +46:55**, which is exactly `16:06 + 16:39 + (23:09 − the 9:00
  already counted that day)`. Three person-days that were zero are now real.
- The 23:09 case is now counted and flagged rather than silently dropped. It is
  probably a missing exit paired with the next entry, but the tool cannot know that,
  and a visible figure a human can question beats an invisible zero.
- `max_shift_hours` now does two jobs — the repair ceiling and the day-level flag — and
  they are deliberately the same number. If they ever need to differ, that is a second
  config key and a new decision, not a quiet reinterpretation of this one.

---

## ADR-033 — The repair ceiling is its own number, and it is 20 hours

2026-08-19 · Status: **Accepted** · Decided by: project owner · Refines ADR-032

### Context

ADR-032 gave `max_shift_hours` two jobs on purpose: flag a person-day over sixteen
hours, and refuse an interval whose midnight-crossing repair lands above sixteen hours.
It also said that if the two ever needed to differ, that would be a second key and a new
decision. They need to differ.

Every midnight crossing in May and June 2026 — 33 records where the exit precedes the
entry — measured:

| | Repaired and kept | Refused |
| --- | --- | --- |
| May | 7 (longest **15:36**) | 2 — at 21:56 and 23:58 |
| June | 23 (longest 10:16) | 1 — at 23:59 |

The genuine crossings are a tight cluster: a 15:30-ish entry against a 01:00-ish exit,
nine to ten hours. The refused ones are records whose two stamps are minutes or seconds
apart, so adding 24 hours lands them just under a full day.

The gap between the two groups is wide — 15:36 to 21:56 — but the ceiling sat at 16:00,
**24 minutes above the longest real crossing**. A sixteen-hour night shift is not
impossible, and it would have been thrown away.

### Decision

`plausibility.repair_max_hours: 20`, separate from `max_shift_hours: 16`.

- **20 hours**, because it clears the longest observed genuine crossing by four and a
  half hours while still catching all three broken records, which land at 21:56, 23:58
  and 23:59.
- **The day-level flag stays at 16 hours.** A long day is still worth pointing at; it
  is simply never removed.
- Two keys rather than one reused. Tying them together is what cost two people a day
  they had worked, and the two thresholds answer different questions: one asks "is this
  day worth a look", the other asks "did our own guess produce something impossible".

### Consequences

- **Nothing moves.** May stays at 17 103:58 and June at 27 166:19, and the same three
  records are refused. The change buys headroom, not figures — which is the point of
  making it before a long night shift turns up rather than after.
- `tests/conftest.py` mirrors the new key, and `test_config.py` compares the whole
  `Plausibility` object, so a fixture that forgot it would fail rather than quietly
  test a ceiling nobody runs.
- If a genuine crossing ever exceeds 20 hours it will still be refused. That is a
  deliberate floor on absurdity: at that point the record is indistinguishable from a
  stuck badge, and the day is visible on the anomaly sheet either way.

---

## ADR-034 — One remote-work note for the placeholder case, not two

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

A declared remote-work day that also carries the Teknopark placeholder produced one of
two notes, depending on what the tool then did with it:

* `Uzaktan + sistem kaydı` — the placeholder was set aside and the remote hours counted.
  36 people in June 2026.
* `Uzaktan + sistem + ek kayıt` — the day also held a record that was **not** a
  placeholder, so the replacement stood down and everything was merged. **One person.**

Together with `Uzaktan + kart kaydı` that made three remote entries in the filter list,
and the project owner — reading the list, which is what it is for — could not tell what
the middle one was doing there. Fairly: the two `info` labels describe the same
situation. What differs between them is which internal rule fired, and that is not a
distinction anybody filtering a list needs to make.

The measured case behind the second label is instructive. That day held a remote
declaration, the system's `09:00–18:00`, and a real Macunköy badge-in at `01:39:44`
with no exit. The rule correctly stood down — there was real evidence it may not throw
away — and the day already carries `Tesis birleştirme` and
`Günlük süre çok uzun (>16 saat)`. Anybody who needs to look at it will.

### Decision

`REMOTE_OVERLAP` is removed. The overlap path emits `REMOTE_REPLACED_NOMINAL`, so both
cases carry the single label `Uzaktan + sistem kaydı`.

The label and its explanation now describe the **situation** — a remote day whose
attendance side is the system's placeholder, counted once. **What was actually done
stays in each record's own detail line** on `Şüpheli Kayıtlar`, where the two cases
still read differently. Nothing is lost from the audit trail; what is lost is a filter
entry nobody could use.

### Consequences

- Two remote entries in the filter instead of three. June: `Uzaktan + sistem kaydı` 36,
  `Uzaktan + kart kaydı` 4. **No figure changes** — May stays 17 103:58, June 27 166:19.
- The real-punch case keeps its own kind and its own severity. That one *is* a
  different question, and it is the only remote note that is not expected behaviour.
- ADR-027's rule that two kinds may not share a label still holds: rather than sharing
  one, the two kinds became one.

---

## ADR-035 — The window checks the roster too, can be pointed at one, and remembers it

2026-08-19 · Status: **Accepted** · Decided by: project owner

### Context

The run needs four files. The window checked three.

`inspect_sources` listed Macunköy, Teknopark and İzin, and the `Rapor Oluştur` button
went green on those three alone. The employee roster was looked up only when the run
started, so a missing one surfaced *after* pressing the button — the exact failure the
pre-flight check exists to prevent, and the thing `inspect_sources`' own docstring
promises it prevents.

This became more likely, not less, with ADR-024: the program can now write anywhere,
and a packaged executable sitting on somebody's desktop has no `data/personel/` beside
it at all.

The project owner asked the fair question: is the roster needed? Measured on June 2026,
163 people:

| Field | People with it | Another source? |
| --- | --- | --- |
| **E-mail** | 154 | **none** — no monthly export carries an address |
| **Tesis** | 154 | none |
| **Görev** | 154 | none |
| Departman | 162 | yes, the attendance files carry one |
| Sicil no | 126 | yes, the leave export |

And the roster does **not** affect identity at all: `_resolve_employees` looks it up by
a key already built from the records. Dropping it would leave every hour identical and
every person present. What it would take away is the e-mail address — and mailing
people their own figures is the point of Phase 4.

The nine people without an address are exactly the nine absent from the roster:
leavers. Every person the roster does carry has all four fields.

### Decision

Keep it, and stop it being a surprise.

1. **The window checks it**, as a fourth row beside the three monthly sources, using
   `pipeline._locate_roster` itself rather than a copy of its rules — the lone-file
   fallback and the month-folder second chance are subtle and a copy would drift.
2. **The button is disabled without it**, like any other missing source.
3. **It can be named outright** with `Seç…`, via `chosen["roster"]` in `run()` — the
   same escape hatch ADR-022 gave the monthly files, and needed here for a reason of
   its own: a packaged program may have no `data/personel/`.
4. **A chosen roster is remembered between sessions**, and this is the same distinction
   ADR-024 drew for the output folder: it is **not month-specific**, so restoring it is
   right rather than stale. The input folder is still never restored.
5. **A remembered path that no longer exists is dropped**, not held onto — the normal
   lookup takes over and the row reports what it found. A memory that blocks the button
   forever is worse than no memory.
6. **It is never cleared when the month folder changes.** The three monthly picks are;
   this one belongs to the company, not to a month.

### Consequences

- The row's note is deliberately short — `bulunamadı — 'personel' klasörüne konmalı`.
  The exception's own text names four glob patterns and two paths, and putting it in
  the row stretched the window half as wide again. A run that gets that far still
  prints all of it.
- `arayuz-ayarlari.json` gains `roster_file`. It holds a path, never employee data, and
  is already git-ignored.
- The roster row offers `Değiştir…` **even when it was found**, unlike the three
  monthly sources. Those have a folder picker, so changing one means changing the
  folder; the roster has no folder of its own, and without the button the only
  reachable list was whichever one the lookup happened to find. The project owner hit
  exactly that.
- The row is shown **before a month folder is picked**, for the same reason: it is not
  month-specific, so gating it behind a month is an ordering constraint with nothing
  behind it. The run button stays disabled until a folder is chosen.
- The roster row never says `(elle seçildi)` and never offers `Geri al`. Both are
  meaningful for the monthly three — one distinguishes "found in the folder you chose"
  from "you pointed at it", the other returns to the folder. Neither is meaningful
  here: the roster has no folder of its own, so every roster is pointed at in some
  sense, and "revert" would undo the user's setup and leave a program with no
  `data/personel/` holding nothing at all. It offers `Değiştir…` and that is all.
- Making the roster optional was considered and rejected. A report with no addresses
  produces a data file with no addresses, and the mail step would then receive a
  silently empty list — trading a loud failure now for a quiet one later.

---

## ADR-036 — A file the library cannot open says so in words

2026-08-19 · Status: **Accepted** · Decided by: implementation

### Context

The readers were careful about the wrong *shape* — a workbook whose columns are not
the ones expected raises `LayoutError` naming the file and what was missing — and
careless about the wrong *file*. Asked what happens if the roster cannot be read,
measured:

| Given | Result |
| --- | --- |
| workbook with the wrong columns | `LayoutError: beklenen kolonları taşıyan sayfa bulunamadı` |
| empty workbook | the same |
| **a `.xlsx` that is not a workbook** | **`BadZipFile: File is not a zip file`** |

The last one is what a renamed CSV, a half-downloaded file or a corrupt one produces,
and it reached the window as `Beklenmeyen hata: BadZipFile`. It names a library and a
container format, and tells the person holding the file nothing about what to do.

### Decision

Both container openers wrap the library call and raise `LayoutError` naming the file
and the remedy: open it in Excel, save as `.xlsx`, try again. The original exception is
appended in brackets so a developer still has it.

Separately, `arayuz-ayarlari.json` is now read with `utf-8-sig`. A byte-order mark
makes a perfectly valid file unreadable to the strict decoder, and everything that
writes such a file other than this program — Notepad, PowerShell's `Set-Content` —
adds one. The failure was silent and total: every remembered path reverted at once and
nothing said why. Found while testing the roster memory, in the harness rather than the
program, which is exactly how a user would meet it.

### Consequences

- One pre-existing defect fixed on the way: the `.xls` missing-dependency message
  printed its `pip install xlrd` line twice.
- `UnsupportedFormat` still handles a suffix we do not read at all (`.xlsb`), which is
  a different question from a file we cannot open.

---

## ADR-037 — The worked-leave list is closed, and training is leave

2026-08-20 · Status: **Accepted** · Decided by: project owner (asked HR), confirmed
against the data by implementation

### Context

ADR-007 made `Uzaktan Çalışma` worked time and left one loose end: "`Eğitim İzni`
(training, 25 rows) is arguably the same situation. Not decided — open question Q13."
It stayed open for seventeen days and was the only Phase 1 rule question that could
still move a payroll figure.

The argument for reopening it was that training rows *carry real clock times*
(`07:30–11:30`, `12:15–16:30`), so counting them as work would need no assumption —
exactly the property that made remote work countable.

Measured across May, June and July, that argument does not hold. **Every leave row
carries a clock time, in all twelve types:**

| Type | May | June | July | rows with a clock time |
| --- | --- | --- | --- | --- |
| `Yıllık İzin` | 378 | 48 | 81 | all |
| `Uzaktan Çalışma` | 56 | 106 | 106 | all |
| `Mazeret` | 41 | 89 | 138 | all |
| `Eğitim İzni` | 25 | 14 | 2 | all |
| the other eight types | 22 | 20 | 45 | all |

The time is when the leave started and ended, not evidence that anybody was present.
Annual leave has one too. So "it carries a time" never distinguished training from
any other absence, and the case for treating it as work rested on a property shared
by the thing it was being contrasted with.

What the alternative would have cost, measured by running the real months with
`Eğitim İzni` added to `worked_leave_types`:

| | Reported total | With training as work | Difference | People affected |
| --- | --- | --- | --- | --- |
| May | 17 103:58 | 17 122:24 | **+18:26** | 5 of the 7 with training |
| June | 27 166:19 | 27 171:12 | **+4:53** | 6 of the 8 |

Smaller than the row counts suggest, and for a reason worth recording: most training
hours fall inside a day the person also badged, so the interval union (ADR-001) had
already counted them. Two of May's seven people gained nothing at all — their training
sat entirely inside a badged day.

### Decision

**The list of leave types counted as worked time is closed at exactly one entry:
`Uzaktan Çalışma`.** Every other type in the HCM export is absence — training
included. HR confirmed this.

### Consequences

- **No code or config change.** This is what the program already did; ADR-007's
  default was right. What changes is that it is now a decision rather than an
  unexamined default, which is the difference between a rule that survives the next
  agent and one that gets "fixed".
- A test asserts `worked_leave_types == {"Uzaktan Çalışma"}` against the real config,
  so adding a second entry now fails loudly and has to be argued for in a new ADR.
  Without it, the closed list is a comment.
- **A leave type nobody has decided about is absence.** New types keep appearing —
  July brought `Ücretli İzin`, `Evlilik İzni` and `Cenaze İzni`, none of which existed
  in May. They need no decision to be handled correctly, and the direction of the
  error if one is eventually wanted is visible: the person's month looks short and
  earns a note, rather than silently gaining hours nobody can trace.
- Q13 is closed. Q20a (the nominal `09:00–18:00` rows, ~17 % of reported hours) is now
  the only open question that can still move a Phase 1 total.

---

## ADR-038 — The window grows to fit a screen and never shrinks; a new list starts at its top

2026-08-20 · Status: **Accepted** · Decided by: project owner (both defects reported),
implementation

### Context

Two defects, found by using the window rather than by reading it. Both are about state
the window keeps, which is why neither showed up in a test suite that deliberately
asserts no geometry.

**1. Switching screens resized the window.** Tk shrink-wraps a toplevel to the
requested size of whatever it is showing, for as long as no explicit geometry has been
set. The two screens do not request the same height — measured on a 1.333-scaled
display, the report screen asks for 791 px and the people screen 597 — so opening
`Kişiler` snapped the window down to the 620 px floor and going back threw it up
again. Reported as the window being cropped from the bottom.

An explicit geometry ends the shrink-wrap, but only once the window has been mapped.
Pinning the size during construction, which is where it would naturally go, left the
behaviour exactly as it was.

**2. A shorter list kept the longer list's scroll offset.** A canvas does not re-clamp
its offset when its contents are replaced, and the scrollregion was only recomputed
from the inner frame's `<Configure>` event. Going from a 60-person filter, scrolled to
the bottom, to a 2-person filter left the view **972 px below** the only two rows: an
apparently empty list that had to be dragged back up by hand, with the scrollbar
already hidden because the content now fitted. The list also had no way back — the
scrollbar it needed was the one that had just correctly hidden itself.

### Decision

**The window grows to fit the screen being shown and never shrinks.** `App._fit` runs
on every switch, takes the maximum of what the screen requests and what the window
already is, and re-asserts it every time rather than only when the number changes —
that is what makes the pin stick after mapping. A maximized window is left alone: the
size is the user's, and calling `geometry` on it would restore it down.

**Every repaint puts the view back inside the list, and a repaint that changed *which*
people are listed starts at the top.** The clamp is arithmetic in pixels, not in
`yview` fractions: the fractions are relative to the scrollregion being replaced, which
is the value that cannot be trusted at that moment. It is deferred to `after_idle`
because a row's height is not known until the layout it was just given has been
processed — measuring earlier measures the previous list, which is how the offset
survived a repaint in the first place.

### Consequences

- **Reset is tied to the set of names, not to repainting.** `Temizle` and
  `Tümünü seç` repaint the same people with different ticks and keep their place;
  throwing somebody back to the top of a 60-row list because they unticked a box
  halfway down is a second defect, not a fix for the first.
- `tests/test_gui.py` now asserts a geometry, against its own opening statement. The
  file says why: both defects are relationships (the window did not get shorter, the
  first row is at the top of its viewport) rather than pixel counts, and nothing else
  catches them. Three of the five new tests fail against the previous code — checked
  by reverting the fix and running them.
- The people screen is exercised with a **synthetic** month, as the screenshot rule
  already required: a failure dump from this screen loaded with a real data file would
  carry employee names and addresses.
- `_fit` makes the window's size depend on the tallest screen ever opened. A future
  screen that wants to be shorter cannot make the window smaller — which is the point,
  but it does mean an unusually tall screen sets the floor for the session.
