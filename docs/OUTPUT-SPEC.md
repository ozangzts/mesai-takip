# OUTPUT-SPEC.md — The Report Workbook, Sheet by Sheet

**Status: BUILT.** Sheets 1–6 are implemented and generating. Phase 2 sheets (§3)
are still proposals.

Each run produces **two** files:

| File | For | Contents |
| --- | --- | --- |
| `data/out/<period>/mesai-raporu-<period>.xlsx` | people | the six sheets below |
| `gonderim-<period>.json`, beside the workbook | programs | the same figures, machine-readable |

The workbook is a **presentation artifact** and is never read back. Durations are
`HH:MM` strings, cells are merged, headers are Turkish, and e-mail addresses are
deliberately absent (§1). Its column layout also changes when a rule changes — the four
gross/net columns became one `Çalışma Süresi` pair on 2026-08-17. Anything downstream
(the mail step, a "use last month's report" screen) loads the JSON instead. See
`src/mesai/snapshot.py`.

Both come from the same computed objects in the same run, so they cannot disagree, and
since ADR-024 they are written **into the same folder** — one directory per month
holding the pair. The JSON holds names, e-mail addresses and hours; `gonderim-*.json`
is git-ignored by name, wherever the user pointed the output.

Sheet names, column headers and all visible text are **Turkish** — HR reads this.

The `Sorun` column holds a **keyword**, not a sentence — it is what the people screen
filters on — and `İnceleme Listesi` explains each one once, under the table. No two
kinds may share a label; a test enforces that, because the label is the filter key
(ADR-027).

The `Tesis` column shows `Macunköy` / `Teknopark`, not the roster's `MACUNKÖY TESİSİ` /
`DEICO TESİS` — same words the `Kayıt Kaynağı` column uses, so one building has one
name in the workbook. The mapping is `config/settings.yaml:facility_labels` and every
value seen is listed on `Kontrol` §8 (ADR-026).

---

## 1. Why not copy the MEYER layout

The MEYER sample devotes a whole workbook to **one** employee: a dashboard with
that person's month, a daily table, their weekly overtime, their Multinet. With 162
employees that pattern would mean 162 workbooks or 1 782 sheets.

So the structure is inverted:

- **one row per employee** on the summary sheet
- **one row per employee-day** on the detail sheet
- per-employee dashboards, if wanted, become Phase 4 e-mail bodies — which is where
  the MEYER single-person layout actually fits

---

## 1b. The workbook is written for HR, not for us

Nothing in any sheet may reference this repository. No `ADR-0NN`, no `ROADMAP.md Q4`,
no `config/` paths, no module names, no phase numbers. The person who opens this file
will never open the code, so a pointer they cannot follow is pure noise — and it makes
the sheet look like a debug dump rather than a report.

48 cells in the May 2026 report broke this rule before 2026-08-18. Each explanation
was rewritten to stand on its own:

| Was | Now |
| --- | --- |
| `İzin kaydı var, kart kaydı yok — ROADMAP.md Q4` | `İzin kaydı var, kart kaydı yok. Bu kişilerin ayı eksik — İK/IT ile kontrol edilmeli` |
| `Zarf kuralıyla ödendi — ADR-015` | `Ödenen süreye dahil — gün içindeki boşluklar düşülmez` |
| `config/personel.yaml:exclude_prefixes` | `Ziyaretçi / geçici / stajyer kartları — kişiye atfedilemediği için özetten düşer` |
| `Fazla mesai … — Faz 2 (Q5, Q6)` | `Fazla mesai ve eksik çalışma hesabı` |

The trade-off is real and was made deliberately: traceability from a cell back to the
decision that produced it is lost. It is recovered by the `Kontrol` sheet stating each
active rule in words — an auditor can read what the rule *is* without being told where
it is written down. `tests/test_report.py::test_no_developer_references_reach_the_workbook`
fails on the next reference somebody appends.

---

## 2. Phase 1 sheets

Six sheets. Sheet 1 is the deliverable; the rest exist so sheet 1 can be trusted.

### Sheet 1 — `Aylık Özet`

One row per employee, sorted by name. **This is what the project was asked for.**

| # | Header | Example | Notes |
| --- | --- | --- | --- |
| A | Ad Soyad | `ZEYNEP DENEME` | **The key and the primary sort** (ADR-009). Full name from the transaction files, not the roster's abbreviated form |
| B | Sicil No | `1003` | Informational only. From the leave export after the name match; blank if unavailable. `SN` card numbers and IAS `Kontak No` never appear here |
| C | Departman | `YAZILIM TASARIM EKİBİ` | From the IAS roster; attendance-file department as fallback |
| D | Görev | `YAZILIM TASARIM MÜHENDİSİ` | From the IAS roster |
| E | Tesis | `DEICO TESİS` / `MACUNKÖY TESİSİ` | **Home facility from the roster** — a fact about the employee (ADR-010) |
| F | Kayıt Kaynağı | `Macunköy + Teknopark` / `Macunköy` / `Teknopark + Uzaktan` … | Which sources contributed. Differs from Tesis for site visitors — that difference is informative, not an error. **This is where you find the dual-site people**: 79 in May 2026 have both sites (58 badge-only + 21 also remote) |
| G | Çalışılan Gün | `19` | days with a non-zero interval, remote days included |
| H | Çalışma Süresi | `168:37` | `HH:MM`, may exceed 24. Σ of `last exit − first entry` per day (§5.0) |
| I | Çalışma (Saat) | `168.62` | decimal, for HR's own formulas |
| J | Uzaktan Çalışma | `4.0` | days counted as worked from the leave export (ADR-007) |
| K | İzin Günü | `1.5` | genuine leave — **excludes** `Uzaktan Çalışma` |
| L | Şüpheli Kayıt | `3` | records still outstanding for this person; >0 shaded amber |
| M | Not | `Eksik çıkış var` | short human-readable summary |

**The hours block is one pair of columns, not two.** With `break.deduct: false`
(ADR-016) gross and net are the same number, and printing both would make a reader ask
which one payroll uses. Flip the switch back to `true` and columns H–I become the
four-column `Brüt Süre` / `Brüt (Saat)` / `Net Süre` / `Net (Saat)` layout of ADR-002,
shifting J–M right by two. Column positions in the writer are derived from the header
list for exactly this reason — never hard-code an index here.

Sorted by name (ADR-009). Header row frozen, autofilter on. A `TOPLAM` row at the
bottom for reconciliation.

A second banner under the first states the active calculation rule
(`HESAP KURALI: …`), because that rule is a config switch and the reader must not
have to assume last month's applied.

Columns J and K must never overlap: a `Uzaktan Çalışma` day is worked time and is
already inside H, so counting it again as leave would misrepresent both.

**E-mail is deliberately not a column here.** It exists in the roster and is needed
for Phase 4, but putting 162 addresses in a circulated workbook serves no reporting
purpose. It stays in the mail step's own data.

**People with no attendance data** (Q4) appear as rows with G–I blank — **not
zero** — and `Kart bilgisi yok` in the Not column. A blank and a zero mean different
things and the sheet must preserve the difference.

**People with attendance but no roster entry** (11 in May 2026, Q4b) get full hour
figures with C, D, E blank and `Personel listesinde yok` in the Not column. Their
hours are real and are counted; only their metadata is missing.

**`TOPLAM` for May 2026 is `17103:58`.** If a run produces `15717:08` instead it is
using the pre-2026-08-17 rules — check `break.deduct`, `daily_hours` and
`remote_day_replaces_attendance`.

> A visible banner above the table states: *flagged records count as zero hours;
> see the `Şüpheli Kayıtlar` sheet.* Without it the totals will be read as final.

### Sheet 2 — `Günlük Detay`

**Every person, every day** — 3 917 rows for July 2026, all 176 people. The audit trail
for sheet 1, and since ADR-063 that means a row exists whether or not anything was
recorded. The row set is three things:

1. every **expected working day** of the period,
2. plus any weekend or holiday the person **worked**,
3. plus any weekend or holiday the person has a **record** on, **even a broken one**
   (ADR-077).

The third was missing and it is the one that mattered. A one-sided punch yields no
interval and therefore no `WorkDay` (ADR-067), so somebody who badged in on a Saturday
with no exit stamped had **no row at all** — while the people screen listed that day as
lost time and offered to ask them about it. 15 / 15 / 14 person-days over May–July, almost
every one a real stamp on a weekend or a public holiday, so these are lost **weekend**
hours. Two end-to-end tests now refuse any day the window would show that this sheet
cannot.

A weekend or holiday with **no record of any kind** still stays out: nobody accounts for a
day they were not expected on.

It held one row per measured day before, so a day with no usable record had no row and the
reader could not tell "did not come in" from "not in this sheet". July had 1 141 person-days
missing and 31 people appearing nowhere.

| # | Header | Notes |
| --- | --- | --- |
| A | Ad Soyad | |
| B | Tarih | `21.05.2026` |
| C | Gün | `Per` / `Cmt` / `Tatil` |
| D | İlk Giriş | earliest entry of the merged union; **empty** if nothing was recorded |
| E | Son Çıkış | latest exit; empty likewise |
| F | Aralık Sayısı | number of merged intervals — `>1` means a split day |
| G | Çalışma Süresi | `12:42` — **must equal E − D**; empty, never `00:00`, when there is no reading |
| H | Gün İçi Boşluk | `0:42` — time between intervals, paid under ADR-015 |
| I | Kaynak | `Teknopark`, `Macunköy`, `Macunköy + Teknopark`, `Uzaktan`, **`İzin`**, **`kayıt yok`** |
| J | Etiket | the day's tags; **empty** for an `İzin` row; `Hem giriş hem çıkış yok` for a `kayıt yok` one |

Three row colours: **red** where nothing accounts for the day, **grey** for leave and for
a worked holiday, **amber** where the day carries a tag. July: 853 rows read `kayıt yok`,
317 `İzin`, and the 2 731 that carry a duration are the same 2 731 as before — the
expansion adds no hours because there are none to add.

**The tags, and what to filter on** (May 2026 counts):

| Tag | May | Meaning |
| --- | --- | --- |
| `çapraz-eşleşti` | 165 | a one-sided record was resolved against the other site (ADR-003) |
| `çapraz-tesis` | 105 | the day genuinely spans both sites — the ADR-001 case |
| `uzaktan` | 52 | contains declared remote hours |
| `kısa-gün` | 15 | day under the 2-hour threshold (ADR-019) |
| `gece-geçişi` | 7 | midnight crossing repaired |
| `uzaktan-çakışma` | 2 | remote declaration **and** a real punch — the ones to ask about |

Grouped by employee, sorted by date. Rows carrying a tag are shaded. The same
`HESAP KURALI:` banner as sheet 1 sits above the table.

**Column H exists so the rule is auditable from the report alone.** ADR-015 pays
in-day gaps; without this column a reader could not tell a continuous 12-hour day from
a 7-hour day with a 5-hour gap. Sorting by it descending is how you find the
questionable days — 49 exceed 1 h in May 2026, 13 exceed 2 h.

With `break.deduct: true`, G–H become the three-column `Brüt` / `Öğle Kesintisi` /
`Net` layout and I–J shift right by one.

## 1e. Tags are printed in words

`Etiket` on `Günlük Detay` prints a day's tags through `anomalies.TAG_TEXT`, never the
internal name. Where a tag means what a note label means it uses that label's exact
words, so the same fact reads the same in the filter list, the `Not` column and here.

Two of them have no label and say what they are: `İki tesisin kaydı çakışıyor` (an
interval carrying both sites' records — the overlap counted once) and `Eksik kayıt diğer
tesisten tamamlandı` (a missing punch resolved from the other site, whether or not that
added any time). The second deliberately does not borrow `Tesis birleştirme`'s wording,
because it is the broader case. ADR-050.

## 1d. One note, one wording

The `Not` column on `Aylık Özet` prints the person's **note labels** — the same strings
the filter list, `İnceleme Listesi` and `Şüpheli Kayıtlar` use, in the same family order.
It is not a separate list of sentences, and it was: five hand-written strings, four of
them re-wordings of a label and eleven labels missing, so 49 rows carried a note while
107 people had a problem. `Personel listesinde yok` is the one note that is not a label,
because it is a fact about the roster rather than a problem (ADR-011, ADR-049).

Enforced by `test_the_summary_notes_use_the_same_words_as_everything_else`.

## 1c. The workbook names nobody

No person, team or department appears in any wording the program produces, and nothing
is described as awaiting somebody's approval. `İK`, `IT`, a job title, "X talebiyle",
"onay bekliyor", "şu kişiye sorulacak" — none of it.

It reads as unprofessional, it is unusable (the reader cannot act on a pointer to a
department they may have no contact with), and it was **false**: the break line credited
a request that was never made, and the alias table claimed a confirmation nobody had
been asked for. Sheet 3 was called `Sorulacaklar` for the same reason and is now
`İnceleme Listesi` — the content, not an instruction about who to interrogate.

Enforced by `test_the_workbook_never_says_who_to_ask`, which matches whole words (`İK`
is a substring of `EKSİK`) and skips cells holding roster text, because real departments
and titles contain the word and the report is only passing them through. ADR-046,
ADR-047.

### Sheet 3 — `İnceleme Listesi`

The sheet you take to HR or IT and ask about. `Şüpheli Kayıtlar` is the audit trail
— one row per defective record, **402** of them for May 2026. This one collapses those
into a per-person question: **191 rows**, each naming the days.

| # | Header | Example |
| --- | --- | --- |
| A | Ad Soyad | `MUSTAFA ALİ DENEME` |
| B | Sicil No | |
| C | Tesis | `Teknopark` |
| D | Departman | |
| E | Sorun | `Çıkış yok` |
| F | Gün Sayısı | `15` |
| G | Günler | `4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 17, 18, 20 Mayıs` |
| H | Etki | `2 gün 0 saat sayıldı; 3 gün başka kayıttan sayıldı` |
| I | Ayrıntı | `22 iş gününün 2 tanesi açıklanıyor (%9) — çalışma 1 gün, izin 1 gün` |

One row per **(person, problem type)** pair — a person with both a missing entry and
a missing exit gets two rows, because they are two different questions.

**Below the table: `SORUNLARIN ANLAMI`**, one line per note that occurred this month
(11 in July 2026). This used to be an `Açıklama` column, 52 characters wide and
repeating the same sentence on every row carrying that note — the meaning does not vary
by person, so per row it bought nothing and cost the width the days needed. Under the
table rather than on `Kontrol`, because the reader who wants a meaning is looking at the
row that needs it. ADR-075.

`Ayrıntı` is the opposite: the record's **own** words, and it is filled only where the
row stands for a single record. That is always true of a month-level note, which is the
case the column exists for — `Kart bilgisi yok` says what it found about the month, and
until ADR-052 the only sheet showing it was the row-per-record audit trail. A note spanning several days has several different sentences and gets none;
printing one of them beside a count of fifteen would misdescribe fourteen days. Measured
on June 2026: 76 of 213 rows carry an `Ayrıntı`.

**Three colours, three meanings** (ADR-017):

| Colour | Severity | Meaning |
| --- | --- | --- |
| Red | `excluded` | those days counted as 0 hours — real lost time |
| Amber | `included` | counted, but worth a look |
| Grey | `info` | **expected behaviour, not a problem** — listed so the audit trail is complete |

Grey rows exist so that a genuine question is not buried among expected ones. For May
2026: **112 rows** where the days counted nothing, **25** where the record was refused but
the day counted anyway from another one, **3** split between the two, 29 amber and 19 grey.
The 112 are the ones somebody has to chase.

**Sorted by name**, Turkish alphabetical, like `Aylık Özet`, `Günlük Detay` and
`İzin Özeti`. It used to lead with severity and then descending day count — worst first,
which is right for triage and wrong for this sheet, because this is the sheet somebody
looks a person up in. Nothing is lost: the row colour states the severity, and Excel
sorts `Gün Sayısı` for whoever wants the old order. A fourth sheet with its own order is
one the reader has to relearn. ADR-075.

Problems with no specific date (`Kart bilgisi yok`, which covers the whole month) show
`tüm ay` in the `Günler` column.

### Sheet 4 — `Şüpheli Kayıtlar`

Every anomaly, with a pointer back to the original file — 245 rows for May 2026,
mostly `MISSING_EXIT`. `İnceleme Listesi` is the per-person view; this one is the per-record audit trail.

| # | Header | Notes |
| --- | --- | --- |
| A | Ad Soyad | |
| B | Tarih | |
| C | Sorun | `Çıkış kaydı yok`, `Negatif süre`, `Kimlik eşleşmedi`, … |
| D | Kaynak Dosya | `Macunköy` |
| E | Kaynak Satır | `17` — the row number in the original file |
| F | Ham Giriş | as recorded |
| G | Ham Çıkış | as recorded |
| H | Etki | `Bu gün 0 saat sayıldı` / `Bu kayıt sayılmadı; gün başka kayıttan 8:43 sayıldı` / `Toplama dahil edildi` / `Toplama dahil edildi — beklenen durum` |

**`Etki` is about the record, not the day** (ADR-055). An excluded record contributed no
hours; whether the *day* lost anything is a separate fact, and the two disagree often.
Measured over May–July 2026, of the rows carrying a missing-punch note, **52 / 99 / 90
counted eight hours or more** — the person is Teknopark staff who called at Macunköy, the
Macunköy row is the blank one, and their Teknopark record covers the day. This column used
to say `Bu gün 0 saat sayıldı` on every one of them, which was false. A grouped row on
`İnceleme Listesi` splits the count rather than picking one verdict.
| I | Açıklama | |

Colour-coded by severity: red = excluded from totals, amber = included but
questionable, grey = expected behaviour recorded for completeness (ADR-017).

The severity → impact-text map has **one** home, `anomalies.IMPACT_TEXT`. The writer
imports it. It used to keep a private copy, and adding the `info` severity then broke
every month-end run with `KeyError` while all 112 unit tests passed —
`tests/test_report.py` now builds a workbook containing every anomaly kind.

Column I is where a remote-work overlap says which it is: `puantajdaki kayıt nominal
tam gün, turnike okuması değil` versus `puantajdaki kayıt gerçek turnike okuması`.
Column G shows the attendance side's raw times, so `09:00-18:00 (teknopark)` is the
placeholder and anything with odd minutes is real.

### Sheet 5 — `İzin Özeti`

Per employee, days by leave type — from the HCM export, subtotal rows skipped.

| # | Header |
| --- | --- |
| A | Ad Soyad |
| B | Sicil No |
| C | Yıllık İzin |
| D | Mazeret |
| E | Uzaktan Çalışma |
| F | İstirahat (Raporlu) |
| G | Eğitim İzni |
| H | Diğer |
| I | Toplam Gün |
| J | Not |

**Free-text leave reasons are deliberately excluded.** The source file contains
medical and personal detail; it must not travel in a workbook circulated across HR.

People with leave records but no attendance record appear here with a note in
column J (23 in May 2026).

---

### Sheet 6 — `Kontrol`

Not a data sheet: it is how a human confirms in ten seconds that nothing was lost.
Numbered sections, and **the numbers are how everything else refers to it** — "section 7
lists every alias in effect" is the documented way to check that the alias table loaded
at all. A test reads the numbers back and fails on a duplicate.

`5. Kapsam` answers *who is in this report* and, since ADR-071, *who is not*:

| Line | Says |
| --- | --- |
| Raporda yer alan kişi | rows written |
| Mesai verisi olan | of those, with at least one badge reading |
| Mesai verisi olmayan | of those, with none — the `Kart bilgisi yok` group, red |
| Personel listesinde olmayan | rows with no roster entry — probable leavers |
| Personel listesinde olup bu ayda hiç kaydı olmayan | **roster entries with no row at all**, red, with the names grouped by facility |

The last line exists because every line above it is blind to the people it counts: no
badge record **and** no leave row means no `Employee`, so no row, no note, and no place
in any of those totals (ADR-011). 21 / 27 / 14 people over May–July 2026. It is omitted
entirely when the count is zero, and it never states a duration — the roster carries no
hire date, so a late joiner and a lost record are indistinguishable here (Q18) and the
note says so instead of guessing. ADR-071.

---

## 3. Phase 2 sheets — planned, not yet specified in detail

Added once the rules in `DOMAIN-RULES.md §7` are confirmed:

| Sheet | Content | Blocked on |
| --- | --- | --- |
| `Fazla Mesai` | daily/weekly/monthly excess and shortfall per employee | Q5, Q6 |
| `Haftalık FM` | one row per employee-week, banded 3–7.5 h / ≥7.5 h | Q6 |
| `Multinet` | weekly and monthly entitlement per employee | Q6 |
| `Vardiya` | shift distribution per employee | Q7 |
| `Tatil` | holiday work, colour-coded, pay-vs-time-off | Q8 + calendar |
| `Hafta Tatili` | rest day work | Q8 + calendar |
`Kontrol` was built in Phase 1 rather than deferred — it is how a human confirms in
ten seconds that nothing was lost.

---

## 4. Formatting rules

- **Names sort in Turkish alphabetical order**, never by codepoint. Python's default
  sort places Ç Ğ İ Ö Ş Ü after Z, so `ŞÜKRÜ` and `İBRAHİM` end up at the bottom of
  the list. Use `normalize.sort_key()` for every user-facing ordering.
- Header row: bold, dark fill, white text, frozen, autofilter.
- Durations as text `HH:MM`, right-aligned. **Never** Excel time format — it wraps
  past 24 h and `186:30` would display as `6:30`.
- Decimal columns: number format `0.00`.
- Dates: `dd.mm.yyyy`, left-aligned.
- Column widths set explicitly. Nothing shows `#####`.
- Colours from `report/styles.py`, never inline. Palette: amber = attention,
  red = excluded, green = reconciled, grey = informational. Colour is always
  accompanied by text — a colour-blind reader must lose nothing.
- Every sheet carries a footer with generation timestamp, period, source file
  names, and the tool version. When HR e-mails a workbook around, its provenance
  travels with it.

## 5. What the report must never contain

- Free-text leave reasons (medical, personal)
- Visitor and temporary badge identities (`ZİYARETÇİ*`, `GEÇİCİ*`) in the summary —
  if they must be visible at all, a separate clearly-labelled sheet
- Formulas that recompute business logic. Values only. HR must not be able to break
  a payroll figure by dragging a cell.

## 6. Open items for approval

1. Is `Aylık Özet` the right column set? Anything missing that HR needs on day one?
2. `Günlük Detay` is now ~3 900 rows for a 176-person month (ADR-063). Is that the
   right sheet to hand over, or does it want a filter — only the days that are not
   ordinary, say — with the full grid kept for the audit trail?
3. Should there be one workbook for everyone, or one per department?
4. Sorted by name, or by department then name?
