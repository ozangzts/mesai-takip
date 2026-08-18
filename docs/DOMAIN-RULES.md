# DOMAIN-RULES.md — The Actual Business Math

This is the specification the code implements. Every rule here must be
mechanically reproducible by a human with a calculator. If a rule cannot be stated
precisely enough to unit-test, it is not ready to implement — raise it as an open
question instead of guessing.

Parameter values shown here are **defaults that live in `config/`**. This document
explains the *rule*; the config holds the *number*. Never hard-code a threshold.

---

## 1. Vocabulary

| Turkish | English | Meaning here |
| --- | --- | --- |
| Mesai | Working time | |
| Giriş / Çıkış | Entry / Exit | A badge event |
| Vardiya | Shift | |
| Fazla mesai (FM) | Overtime | Time beyond the expected day |
| Eksik çalışma | Shortfall | Time short of the expected day |
| Puantaj | Timesheet | |
| Hakediş | Entitlement | |
| Resmi tatil | Public holiday | |
| Hafta tatili | Weekly rest day | |
| Mazeret izni | Excused absence | |
| Toplu izin | Company-wide leave | |

**Interval** — a `(start, end)` pair of `datetime`s with `end > start`.
**Person-day** — one employee on one calendar date, the unit of aggregation.
**Gross** — badge time as recorded, lunch included.
**Net** — gross minus the unpaid break. This is the payroll-relevant figure.

---

## 2. Baseline parameters

From `PRODUCT.md §2`, defaults for `config/settings.yaml`:

```yaml
normal_shift:
  start: "07:30"
  end:   "16:30"
lunch:
  start: "11:30"
  end:   "12:15"
  minutes: 45
  min_workday_for_deduction_hours: 6   # see §5
expected_daily_net_hours: 8.25         # STALE — see below
```

> **`expected_daily_net_hours: 8.25` is known to be wrong** and is not used by any
> code. It assumed `16:30 − 07:30 = 9 h 00` minus a 45-minute lunch. Since ADR-016 the
> break is not deducted, so a full day is **9 hours** — and the leave export's own
> arithmetic independently agrees, dividing hours by 9 to produce `Kullanılan Gün`
> (`DATA-SOURCES.md` D7). Fix the key before wiring any Phase 2 overtime rule. Q5.

---

## 3. Building a clean interval from one raw record

Applied per raw row, in order. The first rule that matches decides the outcome.

**3.1 Both punches present, exit after entry.**
Interval is `(entry, exit)`. Normal case.

**3.2 Both present, exit before entry → midnight crossing.**
Affects 29 Macunköy rows (`docs/DATA-SOURCES.md` D2). Add 24 h to the exit, then:

- if the resulting duration is **≤ `max_plausible_shift_hours` (default 16 h)** →
  accept the interval and tag the day `gece-geçişi`
- otherwise → reject, emit anomaly `IMPLAUSIBLE_DURATION`

Worked example:
```
entry 2026-05-28 23:59:42, exit 2026-05-28 08:07:06
-> exit + 24 h = 2026-05-29 08:07:06
-> duration 8 h 07 m 24 s, ≤ 16 h, accept
(the source file's own value, "-15:-52", is discarded)
```

**3.3 Exactly one punch present.**
No interval can be computed. Attempt cross-site repair (§4.3). If that fails,
contribute **zero** hours and emit anomaly `MISSING_ENTRY` or `MISSING_EXIT`.
**Never substitute a default time.** (ADR-003.)

**3.4 Neither punch present.** Emit `EMPTY_RECORD`. Zero hours.

**3.5 Implausibly short interval.**
Duration below `min_plausible_minutes` (default 5) — e.g. the real
`13:32 → 13:34` = 2 min. Keep the interval in the total, but emit anomaly
`SUSPICIOUS_SHORT` so HR can see it. It is real badge data; we do not delete it.

**3.6 Implausibly long interval.**
Above `max_plausible_shift_hours` (default 16) without a shift explanation.
Emit `IMPLAUSIBLE_DURATION` and **exclude** it from totals — a stuck badge should
not silently add 30 hours to someone's month.

> Rules 3.5 and 3.6 differ deliberately: a suspiciously short interval is
> harmless if wrong, a suspiciously long one is not.

**3.7 Short person-day (ADR-019).** A different question from 3.5, and checked in a
different place. 3.5 asks "is this record broken?" and looks at one interval; this asks
"did this person barely work today?" and looks at the **whole day**, after §5 has
measured it.

```
if measured_day < plausibility.short_day_hours   (2.0, HR's number):
        emit SHORT_DAY, tag the day `kısa-gün`, keep the hours
```

Strictly less than the threshold — exactly 2:00 does not flag, so there is no boundary
ambiguity. The hours are **not** changed: a genuinely short day exists (someone left
ill) and the tool must not decide which is which. 15 person-days in May 2026, 20 in
June.

Note this cannot be done by raising `min_minutes` to two hours: a 20-minute afternoon
segment of a normal split day is not a problem, and flagging it would bury the real
signal.

---

## 4. Merging the two sites — the central rule

**Problem.** 76 employees appear in both attendance exports for May 2026. Their
badge records overlap in real time. Naive summing double-counts.

**Rule (ADR-001): union the intervals per person-day, then measure the union.**

### 4.1 Algorithm

For each `(employee, date)`:

1. Collect every accepted interval from every source for that person-day.
   Note that a single source can legitimately contribute several — 84 Teknopark
   person-days have split morning/afternoon records.
2. Sort by start time.
3. Merge intervals that overlap **or** touch.
4. Gross hours = sum of the merged intervals' durations.

```
input   07:09-19:45  (Teknopark)
        13:20-14:05  (Macunköy, mid-day site visit)
merged  07:09-19:45
gross   12 h 36 m          not 13 h 21 m
```

Merging touching intervals (`a.end == b.start`) is intentional: an exit at one
gate and an entry at another in the same minute is one continuous presence.

### 4.2 What the union is for — and what it is not

The union answers one question only: **did two sources record the same time twice?**
It is a de-duplication step, and it is not negotiable. Without it the 76 dual-site
employees are double-counted; that is ADR-001.

The union does **not** decide the day's hours. That is §5.0, and it is a company
policy choice rather than an arithmetic one. Keeping the two apart matters, because an
earlier version of this document conflated them and argued that measuring a day from
its earliest entry to its latest exit was simply *wrong*. It is not wrong; it is a
different policy, and it is the one this company uses (ADR-015).

The arithmetic in that argument still holds and is worth keeping, because it is the
cost of the chosen rule:

- `08:00–12:00` + `13:00–17:00` — union 2 intervals totalling **8 h**; earliest to
  latest is `08:00 → 17:00` = **9 h**. The extra hour is real time not present at a
  badge reader, and under ADR-015 it is paid.
- May 2026: **174 of 1 823 person-days have more than one interval**, and measuring
  them by span rather than by sum adds **172 h 41 m**. 49 of those days have a gap
  over 1 h, 13 over 2 h. Largest: `07:30–09:30` + `15:30–16:30` — presence 3 h 00,
  paid 9 h 00.
- The remaining 1 649 person-days have a single interval, where the two readings are
  identical by definition.

Where two sites' records genuinely overlap the question does not arise at all: 87 May
person-days collapse into one merged interval, so span and sum agree. Example:
entering at Macunköy `07:51` and leaving Teknopark `18:00` with overlapping coverage
yields one interval of 10 h 08 either way.

So the union removes double counting, and §5.0 decides what the merged day is worth.
Every paid gap is printed in the `Gün İçi Boşluk` column of `Günlük Detay`, so the
cost of the policy is visible per day rather than buried in a total.

### 4.3 Cross-site repair of a one-sided record

Applies to the 388 defective Macunköy rows. Before writing off a one-sided record:

1. Look for a **complete** interval for the same person-day from the other site.
2. If found (82 cases in May 2026):
   - if the orphan punch falls **inside** that interval → discard the orphan, it
     adds nothing. Tag the day `çapraz-eşleşti`.
   - if it falls **outside** → extend the union to cover it, and emit anomaly
     `CROSS_SITE_EXTENDED` so a human can confirm.
3. If not found → §3.3 applies: zero hours plus an anomaly.

**Repair never invents a timestamp.** It only reuses a timestamp that a badge
terminal actually recorded. This is the boundary between "reconciliation" and
"making things up", and it must not be crossed.

### 4.4 Identity resolution

The join key is the **normalized name**, because badge IDs are inconsistent across
systems (`docs/DATA-SOURCES.md` D5).

Normalization (`src/mesai/normalize.py`) — order matters:

1. Unicode NFC
2. Collapse internal whitespace, strip
3. Turkish-aware uppercase via explicit mapping:
   `i→İ, ı→I, ş→Ş, ğ→Ğ, ü→Ü, ö→Ö, ç→Ç`, then `str.upper()`
   **Never** bare `.lower()`/`.upper()` — `"İ".lower()` gives `"i̇"` (two
   codepoints) and quietly breaks equality.
4. Remove titles/suffixes if any appear (none observed so far)

Then:

- exact normalized match → same person
- no exact match, but the name appears in the alias table in
  `config/personel.yaml` → same person
- otherwise → anomaly `UNRESOLVED_IDENTITY`. **Not** fuzzy-matched. A human reviews
  it and adds the alias to the config.

The alias table is required, not optional. Nine real cases exist in May 2026
(`DATA-SOURCES.md §6.1`): four are Turkish-character inconsistencies entered at
source (`KAYIKCI`/`KAYIKÇI`, `KUŞÇU`/`KUŞCU`), four are married names present in one
system and not the other (`SEDA DENEME ÖRNEK` / `SEDA DENEME`), and one is an
abbreviated given name (`MURAT KEREM ÖRNEK` / `M. KEREM ÖRNEK`).

```yaml
aliases:
  # canonical (leave export)          : also appears as
  "AYŞE DENEMECİ":              ["AYŞE DENEMEÇİ"]
  "SEDA DENEME ÖRNEK":                ["SEDA DENEME"]
  "MURAT KEREM ÖRNEK":                 ["M. KEREM ÖRNEK"]
```

A diagnostic script may *propose* alias candidates for a human to review; its output
is never applied automatically and it is not part of the pipeline.

### 4.5 Personnel numbers are informational, never a key

The canonical personnel number comes from the leave export, which has one for all
162 people. Populate it by name after matching. The Teknopark export has no ID
column at all, and 45 Macunköy rows carry an `SN` card number that does not
correspond to the personnel number. Where the leave export has no entry for a
person, the field stays blank — never guessed, never filled from a card number.

Exclusion filter for non-employees: `Ad == Soyad` **and** token matches a prefix in
`config/personel.yaml:exclude_prefixes` (default `ZİYARETÇİ`, `GEÇİCİ`, `MİSAFİR`,
`TEST`). Both conditions required.

---

## 5. Turning a merged day into hours

Two config switches decide this, and both are **required** keys in
`config/settings.yaml` — neither is defaulted, so a config predating a rule change
fails the run instead of silently applying the old rule.

| Switch | Shipped value | Effect |
| --- | --- | --- |
| `daily_hours` | `envelope` | first entry → last exit, in-day gaps paid (ADR-015) |
| `break.deduct` | `false` | no break deduction at all (ADR-016) |
| `remote_day_replaces_attendance` | `nominal_only` | a remote declaration overrides a nominal placeholder, but never a real punch (ADR-018) |

With the shipped values, **a person-day is worth exactly `last exit − first entry`**,
and gross equals net. `worktime.measure()` is the only place these combine; no other
module decides whether a break applies.

Every hours sheet in the report carries a `HESAP KURALI:` banner naming the active
rule, because the rule is configurable and a reader must not have to assume.

### 5.0 The daily measure (ADR-015)

```
measured = max(exit) − min(entry)          # daily_hours: envelope  (shipped)
measured = Σ interval durations            # daily_hours: union
```

The company's reading is the classic timesheet one: the day starts when you first
badge in and ends when you last badge out. Time in between is not deducted — see §4.2
for what that costs and why it is a policy choice, not an error.

`Günlük Detay` prints both `Çalışma Süresi` and `Gün İçi Boşluk`, so any row can be
checked by subtraction: `Son Çıkış − İlk Giriş = Çalışma Süresi`, of which
`Gün İçi Boşluk` was time away from the readers.

### 5.1 Residual break deduction (ADR-008 — implemented, currently OFF)

**Not applied in the shipped configuration.** `break.deduct: false` since ADR-016:
breaks are not deducted, because entry and exit are what count. The rule below stays
implemented and unit-tested, and `break.deduct: true` reproduces the pre-ADR-016
report exactly — but it now takes three switches together, not just this one:
`break.deduct: true`, `daily_hours: union` and `remote_day_replaces_attendance: never`
(ADR-018). Verified end to end on June 2026: brüt `26964:33`, net `24971:48`.

Read the rest of this section as the fallback if HR reinstates the deduction, not as
a description of what the report currently does.

The naive rule — "deduct 45 minutes unless they badged out for at least 45 minutes"
— needs an arbitrary threshold, and a 42-minute gap then either loses 3 minutes of
break or gains 45. Neither is defensible, and nobody can state the cut-off.

The rule avoids the threshold entirely. The employee owes 45 minutes of unpaid
break per day. Time already outside the union is already unpaid. So deduct only
**what is still owed**:

```
already_unpaid = minutes of gap in the day's merged union that fall inside
                 the break-eligibility window
deduction      = clamp(break_minutes − already_unpaid, 0, break_minutes)
net            = gross − deduction
```

Worked examples, with a 45-minute break:

| Day | Gap in union | Already unpaid | Deduction | Note |
| --- | --- | --- | --- | --- |
| `08:00–17:00` continuous | 0 min | 0 | **45 min** | never badged out |
| `08:21–13:48` + `14:30–18:00` | 42 min | 42 | **3 min** | the real Teknopark case |
| `08:00–11:30` + `12:15–17:00` | 45 min | 45 | **0** | exactly the policy break |
| `08:00–11:00` + `14:00–18:00` | 180 min | 45 (capped) | **0** | long absence, break covered |
| `13:32–13:34` | n/a | 0 | **0** | below the minimum-day threshold |

This is continuous rather than stepped: no cliff edge, no tolerance parameter, no
judgement call. Every day gets exactly 45 minutes of unpaid break, wherever it fell.

Guards:

- deduction is 0 if `gross < min_workday_for_deduction_hours` (default 6 h) —
  a half-day does not carry a full break
- `already_unpaid` is capped at `break_minutes`, so a three-hour absence does not
  create a credit
- net never goes below zero

### 5.2 The break-eligibility window

Only gaps overlapping the window count as break. A gap from 15:00–16:00 is not
lunch. Configured per shift, generously — the point is to distinguish "mid-day
break" from "left early and came back", not to police the exact minute:

```yaml
break_windows:
  "Normal Mesai": {from: "11:00", to: "14:30", minutes: 45}
  "1. Vardiya":   {from: "19:00", to: "22:00", minutes: 45}
  "2. Vardiya":   {from: "03:00", to: "06:00", minutes: 45}
```

Shift-specific windows are Phase 2; Phase 1 uses the `Normal Mesai` window for
everyone and tags days whose entry falls far outside it.

### 5.5 Remote work days (ADR-007)

`Uzaktan Çalışma` records in the leave export are worked time. Each row carries a
start and end time, so hours come from the record itself:

```
remote_gross = end_datetime − start_datetime
```

A full-day row (`07:30–16:30`) yields 9 h gross, 8.25 h net after the break
deduction — identical to a badged normal day, which is the point.

**A remote day overrides a nominal placeholder (ADR-018).** Most remote days also carry
a nominal `09:00–18:00` row in the Teknopark timesheet (`DATA-SOURCES.md` D9) — the
timesheet filling in a day nobody badged. Unioning both stretched the day to
`07:30–18:00` = 10:30 on the strength of a row that is not evidence. So:

```
if the day has a remote declaration
   and EVERY attendance record that day is the nominal placeholder:
        measure the day from the remote records alone
else:
        union everything, as §4.1
```

**One real punch protects the whole day.** A single genuine turnstile reading — or even
a one-sided record, which by failing to match the placeholder counts as real — means
the day keeps all of its records. Discarding a real punch would take hours off somebody
who demonstrably worked them: on `2026-06-23` the declaration ends at 13:45 while the
person badged out at 18:34.

Days where the override applied get an `info` anomaly, `REMOTE_REPLACED_NOMINAL`, with
the discarded times recorded. Days where a real punch survived get
`REMOTE_OVERLAP_REAL` at `included` severity — 2 in May, 5 in June, and those are the
only ones worth asking HR about.

If someone worked remotely 07:30–12:00 and badged in at 13:00 with no placeholder
involved, nothing is overridden: the union yields both periods, as it always did.

Remote intervals are tagged `uzaktan` and their source is `izin`, so the
`Günlük Detay` sheet always shows which hours came from a badge and which from a
declared remote day. They must never be silently indistinguishable.

Only `Uzaktan Çalışma` is treated this way. Every other leave type remains
non-worked time.

---

## 6. Monthly total per employee — the Phase 1 deliverable

```
for each employee:
    for each date in the period:
        intervals    = union of accepted intervals from all sources    (§3, §4)
        measured_day = last exit − first entry                         (§5.0)
        net_day      = measured_day − break_deduction                  (§5.1, off)
    measured_month = Σ measured_day
    worked_days    = count of dates with measured_day > 0
```

Reported alongside: anomaly count, and leave days from the HCM export.

**Invariant that must hold and must be unit-tested:**
`Σ over employees of measured_month == Σ measured_day over all person-days`.
If it does not, a record was double-counted or lost.

Note what this invariant is **not**. Before ADR-015 it read "== Σ duration of all
accepted merged intervals", which is false once in-day gaps are paid — it would fail
on every run by design. The two figures are still both reported on `Kontrol`, with the
difference labelled `Gün İçi Boşluklar`, so the gap between presence and paid time is
an explicit line on the report rather than a mismatch nobody can explain:

```
Kabul edilen aralıkların toplamı   16931:16   (presence)
Gün içi boşluklar                    172:41   (paid under ADR-015)
Günlük ölçülen sürelerin toplamı   17103:58   (what the report pays)
Kişi toplamlarının toplamı         17103:58   <- must equal the line above
```

---

## 7. Phase 2 rules — specified, not yet implemented

Do not implement these without confirming the open questions first.

### 7.1 Automatic shift detection

Assign by entry time:

```yaml
shifts:
  - {name: "Normal Mesai", entry_from: "05:00", entry_to: "11:59", start: "07:30", end: "16:30"}
  - {name: "1. Vardiya",   entry_from: "12:00", entry_to: "20:59", start: "16:00", end: "01:00"}
  - {name: "2. Vardiya",   entry_from: "21:00", entry_to: "04:59", start: "00:00", end: "08:00"}
```

Windows are contiguous and wrap at midnight. The `2. Vardiya` boundaries are a
guess based on the stated `24:00–08:00` and must be confirmed (Q7). For a
multi-interval day, the **first** entry of the day decides the shift.

### 7.2 Daily shortfall and excess

```
expected = shift's expected net hours     (Normal Mesai: 8.25 h)
excess   = max(0, net_day − expected)
shortfall= max(0, expected − net_day)
```

Applies only to days the employee was expected to work: not weekly rest days, not
public holidays, not approved leave days.

### 7.3 Weekly overtime and Multinet

```
weekly_overtime = Σ daily excess over the week
                    3 h ≤ x < 7.5 h  -> 1 Multinet
                    x ≥ 7.5 h        -> 2 Multinet
                    x < 3 h          -> 0
```

Undecided and required before implementing: week boundary (Mon–Sun assumed),
whether shortfall on one day offsets excess on another within the week, whether
overtime is computed on net or gross, and inclusive/exclusive behaviour exactly at
3 h and 7.5 h. Q5, Q6.

### 7.4 Public holiday and weekly rest day work

Any work on a date in `config/takvim-2026.yaml:holidays` or on a weekly rest day is
recorded separately with its full duration, and marked as compensated by **pay** or
**time off**. The compensation choice is not derivable from the exports — it needs
an input mechanism (Q8). Public-holiday rows are colour-coded in the report
(`PRODUCT.md §9`).

---

## 8. Rounding and presentation

- All arithmetic in `timedelta` at second resolution. **Never** accumulate floats.
- Round only at the final presentation step.
- Durations render as `HH:MM`, truncating seconds (`8:29`, not `8.48`).
  Hours may exceed 24 (`186:30`) — do not use a time-of-day format.
- A decimal-hours column may accompany `HH:MM` for spreadsheet arithmetic; it is
  derived from the `timedelta`, never the source of truth.
- Empty is empty. Never print `0:00` where no record exists — HR must be able to
  distinguish "worked zero" from "no data".
