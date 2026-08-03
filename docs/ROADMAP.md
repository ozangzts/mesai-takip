# ROADMAP.md — Phases, Status, Open Questions

Update the status table as work completes. An agent finishing a phase updates this
file as part of that work.

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Understand the data, agree the plan | **Done** — 2026-08-03 |
| 1 | Total hours worked per employee per month | **Done** — 2026-08-03 |
| 1b | Validate against a second month | **Done** — June 2026 runs clean |
| 2 | Overtime, shifts, Multinet, holidays | Blocked on Q5–Q8, Q16 |
| 3 | Leave integration, excused absence, assignments | Not started |
| 4a | Drive ingestion automation | **Deferred** — manual by decision, 2026-08-03 (Q21) |
| 4b | Automated per-employee e-mail | Blocked on Q18 — must not mail a leaver |
| 5 | Annual roll-up | Not started |

## How far the output can be trusted

The distinction that matters: **the tool can be complete and correct while the May
data is incomplete.** All Phase 1 code is buildable now. What the output may *claim*
is narrower than what it computes.

| Statement | Safe? |
| --- | --- |
| "This is the working time the badge systems recorded in May 2026" | **Yes** |
| "These records are internally consistent and correctly merged across sites" | **Yes** — verified algorithm, tested |
| "Here are all the records that are missing or suspect" | **Yes** — that is the anomaly sheet's job |
| "This is how many hours person X actually worked in May" | **No** — Q4, ~426 unaccounted days |
| "This is ready for payroll" | **No** — Q4, Q16 |
| "This can be e-mailed to employees" | **No** — Q4, Q18 |

The May run is therefore a **validation run**: it proves the pipeline, produces the
worklist HR needs to fix the source data, and is not circulated as final.

---

## Phase 0 — Discovery ✅

Done 2026-08-03. Produced: `AGENTS.md`, `docs/DATA-SOURCES.md`,
`docs/DOMAIN-RULES.md`, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md` (ADR-001…006), `docs/OUTPUT-SPEC.md`, this file.

Key findings: three structurally different inputs; 76 employees overlap across the
two attendance exports; 388 of 1 209 Macunköy rows have a missing punch; 29 have a
negative duration; 23 identities are not employees; badge IDs do not join across
systems. All verified against the real files, not assumed.

Working prototypes exist in the session scratchpad (not committed): both attendance
files parse end-to-end and produce plausible per-person totals. The parsing risk is
retired — what remains is correctness of the rules.

## Phase 1 — Monthly total hours per employee ✅

Completed 2026-08-03.

- [x] Project skeleton, `config/` with all thresholds externalised
- [x] `models.py`, `config.py`, `normalize.py`, `anomalies.py`
- [x] Readers: `roster.py`, `macunkoy.py`, `teknopark.py`, `izin.py`
- [x] `merge.py` — interval union, cross-site repair (ADR-001, ADR-003)
- [x] `rules/worktime.py` — midnight crossing, gross/net, residual break
- [x] Report sheets 1–4 per `OUTPUT-SPEC.md §2`, plus a `Kontrol` sheet
- [x] `cli.py`: `python -m mesai rapor --ay 2026-05 --girdi <klasör>`
- [x] 65 unit tests, all passing
- [x] Determinism verified: two runs produce 23 273 identical cells
- [x] Reconciliation invariant holds: Σ per-person gross == Σ accepted intervals
- [ ] **Remaining:** HR spot-checks three people against the source files

Input files are located by glob pattern rather than fixed name, so a Drive-synced
folder can be pointed at directly — the Phase 4 automation needs no renaming step.

### Two months generated

| | May 2026 | June 2026 |
| --- | --- | --- |
| People in the report | 171 | 163 |
| with attendance data | 145 | 145 |
| without attendance data (Q4) | 26 | 18 |
| not in the roster (probable leavers) | 11 | 9 |
| Person-days | 1 823 | 2 820 |
| Total gross | 17 009:01 | 26 964:33 |
| Anomalies | 245 (175 excluded) | 421 (269 excluded) |
| Reconciliation | TAMAM | TAMAM |
| Teknopark block totals matching | 110 / 110 | 110 / 110 |

June is the more representative month: May had only 14 expected working days because
of the seven-day holiday block, June has ~22. That is the whole difference in gross
hours — not a data problem.

June also settled Q10 and Q19: **the readers needed no changes.** 2 557 Teknopark
rows instead of 1 607, same irregular block structure, all 110 blocks matching the
source system's own totals. The export format is stable month to month.

### What the build found that analysis had not

- **The Teknopark reader was losing 838 of 1 607 rows** while reporting success.
  Header offset is not constant (+1/+2/+3) and blank spacer rows sit between data
  rows. Caught by cross-checking each block against the file's own
  `Dönemdeki Toplam` figure — now 110/110 blocks agree. `DATA-SOURCES.md §2`.
- **`STJ*` intern badges** are a third family of shared badge alongside
  `ZİYARETÇİ*`/`GEÇİCİ*`. All three together are 420 of 1 208 Macunköy rows.
- **`İREM ÖRNEK` holds two roster accounts** after a surname change. ADR-013.
- **All 55 people whose Macunköy records are exclusively one-sided are
  `DEICO TESİS` staff** — not one is Macunköy-based. This sharpens Q4: the Macunköy
  terminal records site *visits*, which naturally produce one-sided punches; the
  real gap is 31 of those people having no Teknopark record either.
- **37 remote-work records overlap a badge record** on the same day. Hours are
  counted once, but HR should know.

Deliberately not in Phase 1: overtime, shortfall, shifts, Multinet, holiday
compensation, e-mail.

## Phase 2 — Overtime, shifts, Multinet, holidays

Blocked on Q5–Q8. Covers `PRODUCT.md` §2–§4 and the colour-coded holiday report.

- [ ] `config/takvim-2026.yaml` with confirmed public holidays
- [ ] `rules/calendar.py`, `rules/shifts.py`, `rules/overtime.py`,
      `rules/multinet.py`
- [ ] Sheets `Fazla Mesai`, `Haftalık FM`, `Multinet`, `Vardiya`, `Resmi Tatil`,
      `Hafta Tatili`, `Kontrol`
- [ ] Validate a full month of Multinet entitlements against HR's manual figures

## Phase 3 — Leave, excused absence, assignments

`PRODUCT.md` §5–§6. Introduces the first state that persists between runs
(provisional telephone-reported absences awaiting a form), and an input mechanism
for out-of-town assignments, which no current file provides.

## Phase 4 — Ingestion and delivery automation

Two halves, both currently manual and both blocked on decisions rather than code.

### 4a — Getting the source files in (Q21)

Source files land in a Google Drive folder each month. The tool already discovers
input by glob pattern and takes `--girdi`, so **no code change is needed** for a
mounted-drive approach — this is a deployment question.

| Option | Code needed | Blocked on |
| --- | --- | --- |
| Manual download (current) | none | — |
| Drive for Desktop (`G:` drive letter) | copy-to-temp + partial-upload guard | IT installing the client |
| Drive API (service account) | new `drive/` module, credential handling | Google Cloud project; also adds a network dependency to a payroll job, which cuts against ADR-005's spirit |
| Existing `Y:` network share | none | whether Drive is actually required |

Two robustness gaps to close before any mounted-drive automation:

- Drive for Desktop streams files rather than keeping them on disk. `openpyxl` needs
  a real read; copying to a temp folder first is safer than reading in place.
- A file still uploading can be read half-written. Wait for a stable size, or skip
  files modified in the last N minutes.
- A scheduled task must run **in the user's session** — Drive mounts per user, so
  "run whether user is logged on or not" leaves `G:` missing.

### 4b — Automated per-employee e-mail

Per-employee monthly summary by e-mail — this is where the MEYER single-person
dashboard layout actually belongs.

Hard requirements:

- `--dry-run` is the **default**; sending requires an explicit flag
- rendered output reviewable before any send
- SMTP credentials from environment variables, never committed
- an employee's mail contains only their own data
- a send log recording who was mailed, when, with which figures
- verified recipient addresses — a payroll figure sent to the wrong person is a
  personal-data breach, not a bug

## Phase 5 — Annual roll-up

`PRODUCT.md` §3: annual overtime and annual Multinet totals. Needs several months
of validated output first.

---

## 5. Open questions

Resolve with HR / the project owner. When one is answered, write an ADR and remove
it from this list.

### Resolved

| # | Question | Resolution |
| --- | --- | --- |
| Q2 | Does `Uzaktan Çalışma` count as worked time? | **Yes.** Worked time, hours taken from each record's own start/end times. ADR-007 |
| Q3 | Lunch: does a 42-minute gap count as the break taken? | **Residual deduction** — deduct `45 − already-unpaid`, no threshold. ADR-008 |
| Q9 | Which date is missing from the Macunköy export? | `2026-05-03`, a **Sunday with no activity in either file**. Not a data problem. `DATA-SOURCES.md §6.2` |
| Q14 | Is the Teknopark export truncated (only 21 of 31 dates)? | **No.** Missing dates are weekends plus the 27–31 May holiday block; the office was closed while Macunköy production ran. `DATA-SOURCES.md §6.2` |
| Q15 | Sort and identify by name or personnel number? | **Name is the key and the sort**; personnel number is informational, from the leave export only. ADR-009 |
| Q4b | 27 people have attendance records but are not in the IAS roster | **Leavers.** The roster is an August export; these people worked in May and left before August. They keep full rows and full hours. ADR-011 |
| Q4d | 20 roster employees appear in no May file at all | **Hired after May.** They get no row in a May report. ADR-011 |
| Q1 | Is the 76-person overlap genuine dual-site presence? | **Yes.** The IAS roster's `Tesis` field settles it: 75 of the 79 people in both files are based at `DEICO TESİS`, and **no** Macunköy-based employee appears in both. `DATA-SOURCES.md §3b`, ADR-010 |
| Q17 | Where do employee e-mail addresses come from for Phase 4? | The IAS roster — populated for all 181 employees. 84 % of people with attendance records are covered; the remaining 26 fall under Q4 |
| Q10 | Is the export format stable month to month? | **Yes.** June 2026 parsed with no reader changes: 2 557 Teknopark rows across 110 blocks, all 110 matching the file's own totals; reconciliation TAMAM |
| Q19 | Can HR export a second month to validate against? | **Done** — June 2026 was available and runs clean. A third month is no longer needed to prove the readers generalise |

### Open

| # | Question | Blocks | Why it matters |
| --- | --- | --- | --- |
| **Q4** | **26 people have May leave records but no usable attendance record.** Plus: of the 55 people whose Macunköy records are *exclusively* one-sided, **31 have no Teknopark record either** — so their working time is nowhere. Every one of those 55 is `DEICO TESİS`; not one is Macunköy-based. Question for IT: **does the Teknopark export cover all `DEICO TESİS` staff?** | Phase 1 sign-off | **The most important open question.** The Macunköy terminal records site *visits* (hence one-sided punches); the gap is on the Teknopark side. Until answered, no total is final |
| Q4a | Confirm the nine name-variant pairs in `DATA-SOURCES.md §6.1` are the same people, so they can be frozen into the alias table | Phase 1 | A wrong alias merges two people's payroll hours |
| Q4c | `İBRAHİM KAYRA SINAMA`, personnel no `9001` — the only leave-export person absent from the roster. Is the `9xxx` range interns or contractors? | Phase 1 | May indicate a whole employee category the roster omits |
| **Q18** | **Can the roster be re-exported with `İşe Giriş Tarihi` and `İşten Çıkış Tarihi`?** | Phase 1 accuracy, Phase 4 safety | Turns "hired later / left earlier / data missing" from inference into fact. Also prevents Phase 4 mailing a leaver. ADR-011 |
| **Q19** | **Can HR export the same four files for July 2026?** | Phase 1 validation | May is atypical (14 working days, 7-day holiday block) and its roster is 3 months stale. A contemporaneous month is needed before any figure is trusted. Also tests format stability (Q10). ADR-012 |
| Q5 | Is the standard day really 8 h 15 net (09:00 span − 45 min)? | Phase 2 | Drives every overtime figure |
| Q6 | Overtime week boundary (Mon–Sun?); does shortfall offset excess within a week; gross or net; behaviour exactly at 3 h and 7.5 h | Phase 2 | Multinet entitlement is money |
| Q7 | Exact entry-time windows for automatic shift assignment; `2. Vardiya` does not exist yet — when? | Phase 2 | Misassigned shift ⇒ wrong expected hours |
| Q8 | How is pay-vs-time-off compensation for holiday work decided, and where does that input come from? | Phase 2 | Not derivable from any current export |
| Q11 | Should `ZİYARETÇİ*` / `GEÇİCİ*` badges be reported anywhere, or dropped entirely? | Phase 1 | Currently dropped from the summary |
| Q12 | Who may receive the full workbook? Is per-department splitting required? | Phase 1 output | Personal data of 162 people in one file |
| Q13 | Does `Eğitim İzni` (training, 25 rows) count as worked time, like remote work does? | Phase 1 | Same shape of question as Q2; not yet asked |
| Q20 | **37 `Uzaktan Çalışma` records overlap a badge record on the same day.** Did the person cancel the remote day and come in, or work partly from each? | Phase 1 accuracy | Overlap is counted once, so no inflation — but the declared hours may be standing in for real ones |
| **Q21** | **Source files are uploaded to Google Drive each month. Which integration?** Manual (today), Drive for Desktop (drive letter, no code change), Drive API (headless, adds a network dependency), or the existing `Y:` network share. Also: is the folder per-month? Who has access to it? | Phase 4 | Decided 2026-08-03 to stay **manual for now**; folder layout and access are still unknown. See README "İleride: Drive otomasyonu" |
| Q16 | Confirm the May 2026 public holidays: 1 May, 19 May, and the Kurban Bayramı block (25 May bridge, 26 May half-day, 27–29 May) | Phase 2 | Inferred from the data, not stated by HR. Drives holiday pay |
