# PRODUCT.md — What the Customer Asked For

Source: `MEYER Programı Toplantı İçeriği 1.docx` ("MEYER Programı Değerlendirme
Toplantısı — Mevcut Durum ve Taleplerimiz"). That document was written by DEICO HR
as a requirement list for a vendor evaluation. It is the authoritative statement of
what the finished system must do.

This file restates it in English and marks which phase covers each item.
**Do not invent requirements that are not here.** If HR asks for something new,
add it here first, then implement.

---

## 1. Users and the problem

**Primary user:** DEICO HR / payroll staff.
**Today:** raw badge exports arrive monthly and are turned into an overtime report
manually, per site, in Excel. It is slow and error-prone, and the source data is
known-bad (32 % of Macunköy rows have a missing punch).
**Wanted:** a repeatable, automatic monthly run producing a single trustworthy
workbook — and later, per-employee e-mails.

**Success for Phase 1:** HR can obtain a correct, defensible total-hours-worked
figure for all 162 employees for a given month, with every questionable record
visible rather than buried.

---

## 2. Working-time baseline (requirement §1)

- Standard working day: **07:30 – 16:30**
- Lunch break: **11:30 – 12:15** (45 minutes)
- Calculations are based on daily working duration.

Requested capabilities:

- View each employee's daily entry and exit times
- View daily **shortfall** (eksik çalışma) and **excess** (fazla çalışma)
- View monthly shortfall and excess totals
- Report weekly overtime **between 3 and 7.5 hours**
- Separately track weekly overtime of **7.5 hours and above**

→ Daily/monthly totals: **Phase 1–2.** Weekly overtime banding: **Phase 2.**

## 3. Shift management (requirement §2)

Existing shifts:

| Shift | Hours | Status |
| --- | --- | --- |
| Normal Mesai | 07:30 – 16:30 | active |
| 1. Vardiya | 16:00 – 01:00 | active |
| 2. Vardiya | 24:00 – 08:00 | **does not exist yet** — must be supported when introduced |

Requested:

- Shift determined **automatically from the entry time**
- Correct duration calculation for shift workers (i.e. across midnight)
- Shift-based reporting

→ **Phase 2.** Note that midnight crossing already affects Phase 1 data
(29 negative-duration rows), so the crossing fix cannot wait — see
`docs/DOMAIN-RULES.md §3`.

## 4. Overtime and Multinet (requirement §3)

Weekly overtime entitlement:

| Weekly overtime | Entitlement |
| --- | --- |
| 3 h – 7.5 h | **1 Multinet** |
| ≥ 7.5 h | **2 Multinet** |
| < 3 h | none |

Also requested: annual Multinet count, annual overtime total, and automatic
per-employee entitlement reports.

→ **Phase 2.** Unresolved: the boundary at exactly 3 h and exactly 7.5 h, whether
the week is Mon–Sun, and whether overtime is computed on gross or net hours.
Open questions Q5–Q6 in `docs/ROADMAP.md`.

## 5. Public and weekly holiday work (requirement §4)

The system must automatically calculate:

- work performed on public holidays (resmi tatil)
- work performed on weekly rest days (hafta tatili)
- whether each is compensated as **pay** or as **time off**

→ **Phase 2.** Requires a holiday calendar (`config/takvim-2026.yaml`). Note the
May 2026 data shows a company-wide `Toplu İzin` / `Bayram Tatili` block around
25–26 May.

## 6. Excused-absence management (requirement §5)

- Excused absences reported **by telephone** must be recordable provisionally
- When the signed leave form arrives, it must be matched to the provisional record
- Reports must reflect the correct state

→ **Phase 3.** Implies a small piece of mutable state that is *not* derived from
the monthly exports — the first thing in this project that needs to persist
between runs.

## 7. Out-of-town assignment (requirement §6)

Track: assignment duration, travel time, overtime generated.

→ **Phase 3.** No source file for this exists yet; input mechanism undecided.

## 8. Fields that must be calculated automatically (requirement §7)

| Field | Phase |
| --- | --- |
| Daily working duration | 1 |
| Daily shortfall | 2 |
| Daily excess | 2 |
| Weekly overtime | 2 |
| Monthly overtime | 2 |
| Public holiday work | 2 |
| Weekly rest day work | 2 |
| Multinet entitlement | 2 |

## 9. Reports required (requirement §8)

| Report | Phase |
| --- | --- |
| Daily entry–exit | 1 |
| Daily shortfall | 2 |
| Daily excess | 2 |
| Weekly overtime | 2 |
| Monthly overtime | 2 |
| Per-employee working summary | **1 — the Phase 1 deliverable** |
| Shift report | 2 |
| Multinet entitlement | 2 |
| Public holiday work (**with colour coding**) | 2 |
| Weekly rest day work | 2 |

The colour-coding note is explicit in the source document; the report writer must
support cell fills from the start.

---

## 10. Requirements this project adds

Not in the customer document, but forced by the actual data or by the deployment
plan:

- **R1 — Multi-site reconciliation.** The customer document assumes one attendance
  source. There are two, overlapping by 76 people. Non-negotiable; ADR-001.
- **R2 — Anomaly reporting.** With 388 defective rows in one file, silent handling
  is unacceptable. Every questionable record must be visible to HR. ADR-003.
- **R3 — Gross and net hours side by side.** Employees do not badge out for lunch,
  so raw badge time includes the 45-minute break. HR gets both figures. ADR-002.
- **R4 — Deterministic, no AI at runtime.** These numbers feed payroll and will be
  e-mailed to employees. See `AGENTS.md §2.1`.
- **R5 — Automated e-mail delivery** of per-employee summaries. Requested verbally
  by the project owner, 2026-08-03. **Phase 4.**

---

## 11. Explicitly out of scope for now

- Integration with the MEYER vendor product. We are producing our own report; the
  vendor sample is a shape reference only.
- Writing back to the HCM system. Read-only.
- A web interface. CLI plus Excel output.
- Payroll calculation. We produce hours; payroll is someone else's system.
- Historical months before May 2026, until a second month's exports are available
  to validate that the readers generalise.
