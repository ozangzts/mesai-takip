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
expected_daily_net_hours: 8.25         # 09:00 span - 45 min
```

`16:30 − 07:30 = 9 h 00`, minus 45 min lunch = **8 h 15 (8.25 h) net expected per
working day**. Confirm this against payroll before Phase 2 — an 8.25 h standard day
is unusual and drives every overtime figure. Open question Q5.

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

### 4.2 Union, not "earliest entry to latest exit"

The tempting shortcut — take the earliest entry and the latest exit of the day — is
wrong, and measurably so.

If a person has `08:00–12:00` and `13:00–17:00`, the union is two intervals totalling
**8 h**. Earliest-to-latest would say `08:00 → 17:00` = **9 h**, paying for an hour
nobody worked.

Measured on May 2026: **171 person-days have more than one interval, and the shortcut
would add 159 h 11 m** across them. Worst single day:
`07:30–08:00` + `12:37–19:10` → union 7 h 03, shortcut 11 h 40, a 4 h 37 error.

Where the two coincide — and this is the case that makes the shortcut *feel* right —
is when the intervals genuinely overlap. 138 May person-days had two sites' records
collapse into a single merged interval; for those, the union **is** earliest entry to
latest exit. Example: entering at Macunköy `07:51` and leaving Teknopark `18:00` with
overlapping coverage yields one interval of 10 h 08.

So: union gives the intuitive answer whenever the intuition is correct, and the
correct answer when it is not. Only §5 handles the implicit lunch break for people
who never badge out.

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

## 5. Gross vs net hours

Employees do not badge out for lunch, so a normal day's badge span contains the
45-minute break. Both figures are reported (ADR-002).

### 5.1 Residual break deduction (ADR-008)

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

**Double-counting guard.** 48 of the 56 remote-work records belong to people who
also have badge records that month, so a remote interval is treated as just another
interval entering the union of §4.1. If someone worked remotely 07:30–12:00 and then
badged in at 13:00, the union yields both periods with no overlap. If a remote
record overlaps a badge record — remote work logged for a day the person was
physically present — the union counts the overlap once and the day is tagged
`uzaktan-çakışma` for HR review.

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
        intervals = union of accepted intervals from all sources   (§3, §4)
        gross_day = sum of interval durations
        net_day   = gross_day − lunch_deduction                    (§5)
    gross_month = Σ gross_day
    net_month   = Σ net_day
    worked_days = count of dates with gross_day > 0
```

Reported alongside: anomaly count, and leave days from the HCM export.

**Invariant that must hold and must be unit-tested:**
`Σ over employees of gross_month == Σ duration of all accepted merged intervals`.
If it does not, a record was double-counted or lost.

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
