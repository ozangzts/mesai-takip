# DATA-SOURCES.md — Anatomy and Defects of Every Input File

All figures in this document were measured against the real May 2026 exports on
2026-08-03, not estimated. If you re-measure and get a different number, the data
changed — update this file.

Period covered: **2026-05-01 … 2026-05-31** (30 distinct dates present; see §5).

---

## 1. `Macunköy Mayıs Mesai giriş-çıkış.xlsx`

Raw badge-terminal export for the Macunköy production site.

**Shape.** Single sheet `Sayfa1`, header on row 1, 1 209 data rows, 11 columns.
Flat log: one row per person per day.

| Col | Header | Type | Notes |
| --- | --- | --- | --- |
| A | `Ad` | str | Given name(s), uppercase |
| B | `Soyad` | str | Surname, uppercase |
| C | `Personel` | str | `Ad + " " + Soyad`. **Use this as the name field.** |
| D | `SicilNo` | str | Two formats: numeric (`1001`) or `SN`-prefixed (`SN100001`) |
| E | `Birim` | str | Always `DEICO` in this export |
| F | — | — | **Always empty.** Unnamed column, do not index by header position |
| G | `Bolum` | str | Department, e.g. `ÜRETİM EKİBİ-1`, `DONANIM` |
| H | `MesaiTarih` | datetime | Date at 00:00:00 |
| I | `Giris` | datetime | Full timestamp, **may be None** |
| J | `Cikis` | datetime | Full timestamp, **may be None** |
| K | `SureSaat` | str | `"HH:MM"`. Present only when I and J both present. **Unreliable — see D3** |

Rows are ordered newest date first.

### Defects

**D1 — Missing punches: 388 of 1 209 rows (32 %).**
98 rows have no entry, 338 have no exit (some rows have neither).
Of these 388, **82 have a same-day record in the Teknopark export**, and in those
cases the Teknopark record is typically the complete one. See ADR-003 for handling.

**D2 — Negative durations: 29 rows.** The source system subtracts without handling
midnight crossing. Real example, row 17:

```
Giris  = 2026-05-28 23:59:42
Cikis  = 2026-05-28 08:07:06      <- same calendar date, earlier time
SureSaat = "-15:-52"              <- not even a valid duration string
```

The intent is a night shift ending the next morning. Correct duration is 8 h 07 m.
Handling: if `Cikis < Giris`, add 24 h — but only if the result is plausible
(< 16 h) and the entry time falls in a night-shift window. Otherwise flag it.

**D3 — Do not trust column K.** It is `None` whenever a punch is missing and it is
wrong for every midnight crossing. Recompute from `Giris`/`Cikis`; use K only as a
cross-check and report disagreements.

**D4 — 34 non-employee identities, 420 rows.** Shared/numbered badges recorded as
people, in three families:

| Family | Examples | Count |
| --- | --- | --- |
| `ZİYARETÇİ*` (visitor) | `ZİYARETÇİ33`, `ZİYARETÇİ35` | |
| `GEÇİCİ*` (temporary) | `GEÇİCİ3`, `GEÇİCİ6`, `GEÇİCİ10`, `GEÇİCİ17` | |
| `STJ*` (intern) | `STJ4` … `STJ21` | 11 |

Both name fields carry the same token, so `Personel` reads
`ZİYARETÇİ35 ZİYARETÇİ35`. They accumulate large totals (one reached 169 h, the
highest in the file) and corrupt any ranking if not excluded. Together they account
for **420 of the 1 208 data rows** — a third of the file.

Filter: `Ad == Soyad` **and** the token matches a prefix in `config/personel.yaml`.
Both conditions are required. `Ad == Soyad` alone would drop a legitimate `X X`
name; the prefix alone would drop a real surname like `STJEPANOVIC`.

Excluding them leaves **788 rows / 117 identities** in this file. `STJ*` badges are
interns who do work, but the badge is numbered rather than named, so their hours
cannot be attributed to a person — see Q11.

**D5 — Badge ID is not a stable key.** `SN`-prefixed values are card numbers, not
personnel numbers. The same person appears as `SN100002` here and `8801` in the
leave export. Roughly half the rows use the numeric form which *does* match the
leave export. Join on normalized name; use the numeric ID as a confirmation only.

**D10 — Layout is not stable. Discover it, never assume it.**

The Macunköy export changed shape three times in three months (ADR-020):

| | May / June 2026 | July 2026 |
| --- | --- | --- |
| Container | `.xlsx` (ZIP) | **`.xls`** (OLE2/BIFF, magic `d0cf11e0`) |
| Header row | 1 | **2** — a title line `İLK GİRİŞ SON ÇIKIŞ PD` sits above it |
| Columns | 11, incl. `Personel` | **10** — `Personel` dropped, everything after it shifted left |

```
MAY    0 Ad  1 Soyad  2 Personel  3 SicilNo  4 Birim  5 —  6 Bolum  7 MesaiTarih  8 Giris  9 Cikis  10 SureSaat
JULY   0 Ad  1 Soyad  2 SicilNo   3 Birim    4 —      5 Bolum  6 MesaiTarih  7 Giris  8 Cikis  9 SureSaat
```

Consequences for anyone touching a reader:

- **Address columns by header name, never by index.** With fixed indices the July
  file reads `SicilNo` as the employee name and `Bolum` as the date — a complete,
  confident, wrong report. `base.find_header_row` locates the header within the first
  ten rows and returns a name → position map.
- **Only `Ad`, `Soyad`, `MesaiTarih`, `Giris`, `Cikis` are required.** `Personel`,
  `SicilNo`, `Bolum` and `SureSaat` are used when present. The full name is rebuilt
  from `Ad` + `Soyad`, so losing `Personel` costs nothing.
- **Globs are `*.xls*`**, covering `.xlsx`, `.xlsm` and `.xls`. A pattern tied to one
  container turns a format change into a misleading "file not found".
- `base.open_sheets` picks openpyxl or xlrd and returns the same `Sheet` either way.
  Note that xlrd hands back dates as bare floats — unconverted, every timestamp
  becomes meaningless and everybody gets zero hours while the run reports success.

The Teknopark reader is still block-offset based, because its layout is not a header
table. That remains a known fragility, held by the per-block `Dönemdeki Toplam` check.

### Confirmed non-issues

- No person has more than one row for the same date in this file (checked: 0).
- No person maps to more than one badge ID within this file (checked: 0).

---

## 2. `Teknopark - Mayıs Mesai Takip Exceli.xlsx`

Formatted report ("DÖNEMSEL AYRINTILI PUANTAJ RAPORU") for the Teknopark office.
Cleaner data, much harder structure.

**Shape.** Single sheet `Page1`, 1 224 rows × 14 columns, **4 105 merged cell
ranges**. Not a table — a page layout.

Preamble:

```
r1  A: DÖNEMSEL AYRINTILI PUANTAJ RAPORU
r3  A: Şirket Adı      D: DEICO MÜHENDİSLİK TASARIM İMALAT İNŞAAT ...
r4  A: Rapor Dönemi    D: MAYIS 2026
```

Then **110 per-person blocks**, laid out in two vertical streams: blocks starting
in column **A** (56 of them) and blocks starting in column **H** (54). The two
streams are independent — block heights vary with each person's row count, so a
block in column A at row 54 may sit beside a column-H block that started at row 24.

Block anatomy, where `c` is the block's first column (1 for A, 8 for H):

```
row r      c   : "Adı Soyadı:"        c+3 : <employee name>
row r+k    c   : "Tarih"              c+2 : "Giriş Tarih Saat"
                                      c+4 : "Çıkış Tarih Saat"
                                      c+5 : "Çalışma Süresi"
...        c   : <date>               c+2 : entry   c+4 : exit   c+5 : duration
           (blank spacer rows may appear between data rows)
row t      c+1 : "Dönemdeki Toplam Çalışma Süresi"      c+5 : <period total>
```

Data row columns, relative to `c`:

| Offset | Field | Type |
| --- | --- | --- |
| +0 | Date | datetime at 00:00:00 |
| +2 | Entry | **str** `"04.05.2026 07:35"` (`%d.%m.%Y %H:%M`) |
| +4 | Exit | **str**, same format |
| +5 | Duration | str `"11:16"` |

### Three traps, all of which produced silently wrong output

> An earlier version of the reader assumed `k = 1` and stopped at the first empty
> date cell. It read **769 of 1 607** rows — more than half the file lost — while
> reporting success and plausible-looking per-person totals. Nothing failed; the
> numbers were just wrong. Treat this section as load-bearing.

**T1 — `k` is not constant.** The header sits 1 row below the marker in 61 blocks,
2 rows in 9, and 3 rows in 40. Locate the header by searching for the literal
`"Tarih"` in the block's own column, never by offset.

**T2 — blank spacer rows appear between data rows.** The block ends at its
`"Dönemdeki Toplam"` line, not at the first gap. Skip blanks; do not break on them.

**T3 — entry and exit are STRINGS.** A naive `isinstance(v, datetime)` check yields
zero hours for all 110 people while appearing to succeed.

Also: gaps between consecutive marker rows are irregular (observed 18, 7, 23, 14, 9,
16, 21, **1**, 10, 17, 25). A gap of 1 occurs at rows 114/115 — the streams are not
aligned, so a marker row for one stream can fall inside the other's data range.
Merged cells make `read_only=True` unsafe; load the workbook normally.

### The total line is the parser's own alarm

Each block ends with the source system's own period total. Summing the block's rows
and comparing catches exactly the failure mode above. **All 110 blocks currently
match to within 2 minutes** — that is the strongest available evidence the parser is
correct. A mismatch is reported as `DURATION_MISMATCH`.

### Notes

- 110 blocks, 110 unique names — no person is split across two blocks.
- 1 607 data rows across **1 432 person-days**; **175 person-days have more than one
  row** (split days: out at lunch, back in the afternoon). These must be summed per
  day, not treated as duplicates. Example — `BURAK ÖRNEK, 2026-05-04`:
  `08:21–13:48` (5:27) plus `14:30–18:00` (3:30) = 8 h 57 m for the day.
- 25 distinct dates.
- Very short rows exist and are real: `01.05.2026 13:32 → 13:34` = `00:02`.
  Probably a badge test on a public holiday. Flag as suspicious, do not delete.

### D11 — The nominal `09:00–18:00` day is a placeholder, not a punch

**319 of 1 607 May rows and 418 of 2 557 June rows are exactly `09:00–18:00`, duration
exactly `09:00`.** They are structurally identical to real rows — same columns, same
string format, no marker of any kind. Four independent findings identify them:

1. **No odd minutes.** Real punches look like `07:17 → 18:46`. This pattern never
   deviates by a minute, across 737 rows over two months.
2. **Sole record for the day.** In every remote-work overlap it is the only record for
   that person-day, in either attendance file. No physical trace exists.
3. **Present when the office was shut.** On 25–26 May — the Kurban Bayramı bridge —
   15 of 15 and 15 of 16 Teknopark records are exactly this pattern. A closed office
   cannot produce 15 identical punches.
4. **Present during leave.** 19 May person-days carry it while the person was on
   leave, including one day of `İstirahat (Raporlu)`.

Distribution is consistent with "fill in an expected workday that has no turnstile
data": **never at a weekend** (0 rows Sat/Sun), 15–26 % of rows on each weekday, no
single-day concentration, and 81 people affected in May of whom **none** has only
nominal rows — everyone also has real punches.

**Do not read it as a remote-work marker.** Measured in that direction it fails: only
10 % (May) and 18 % (June) of nominal rows have a `Uzaktan Çalışma` declaration on the
same day, and the two people with the most nominal days (11 and 16) have no remote
declarations at all. Remote work is one trigger among several; the others are not
determinable from any file we have.

**It is nevertheless counted as worked time (ADR-017)**, because the file's own
`Dönemdeki Toplam` counts it and 110/110 blocks reconcile with that figure. The
pattern is declared in `config/settings.yaml:nominal_day` so the report can tell a
reader which side of a remote overlap was a placeholder. If the vendor's default
changes, change it there — no code knows the times.

Weight: 319 rows × 9 h = **2 871 h, about 17 % of May's reported total.** Anyone
revisiting whether these should be paid should start from that number.

### D12 — An export can be complete data about an incomplete period

July 2026's Teknopark file covers **1–19 July only**: 962 rows against June's 2 557,
13 of 23 expected working days, and it was exported on the 20th. Macunköy for the same
month covers 1–31.

Nothing in the file itself is wrong. Every block agrees with its own
`Dönemdeki Toplam`, the row counts reconcile, and the report read `Mutabakat: TAMAM`
while being short 16 000 hours' worth of month. This is the most dangerous shape a
source file can take, and it is why `SourceCoverage` exists (ADR-020): the check is a
**trailing run of expected working days with no records**, per source.

Do not check "fewer days than the other source" — Teknopark legitimately has nothing
on days the office is shut while Macunköy production runs. In May its 21 of 31 days
were entirely explained by weekends plus the Kurban Bayramı block (Q14).

---

## 3. `HCMT34_MAYIS_IZIN.xlsx`

Leave export from the HCM system.

**Shape.** Single sheet `HCMPERS`, header on row 1, 16 columns, 162 people.

> `openpyxl` reports `max_row = 1` for this sheet in `read_only` mode — the file
> has no dimension record. Iterate rows normally; the data is there. The file also
> triggers a "no default style" warning on load, which is harmless.

| Col | Header | Notes |
| --- | --- | --- |
| A | `Sicil No` | Numeric personnel number — the canonical ID |
| B | `Görünen Ad` | Full name |
| C | `Bölüm Kodu` | Department |
| D | `Görev` | Job title |
| E | `İzin Tipi` | Leave type — **empty on subtotal rows, see D6** |
| F | `Onay Durumu` | `Onaylandı` |
| G | `İzin Durumu` | `Kullanıldı` (taken) / `Planlandı` (planned) |
| H–I | `Başlangıç Tarihi` / `Saati` | `dd.mm.yyyy` string + `HH:MM` |
| J–K | `Bitiş Tarihi` / `Saati` | same |
| L | `Mesai Kaydet` | Observed value: `Mesai Kaydetme` (do not count as work) |
| M | `Bordro Kodu` | `NORM` |
| N–O | `Açıklama` / `İzin Sebebi` | Free text, often duplicated |
| P | `Kullanılan Gün` | Days used, fractional (`0.22`, `0.5`, `1.0`, `1.5`) — see D7 |

**D6 — Per-person subtotal row. This will silently double every total if missed.**
The first row for each person has columns E–O empty and column P holding the sum
of that person's subsequent rows:

```
r2  8801  SEDAT TASLAK  ...  E..O empty         P=1.5   <- SUBTOTAL, skip
r3  8801  SEDAT TASLAK  ...  Yıllık İzin ...    P=1.0
r4  8801  SEDAT TASLAK  ...  Yıllık İzin ...    P=0.5
```

Rule: skip any row where `İzin Tipi` is empty.

**Leave types present, with row counts:**

| Type | Rows | Counts as worked time? |
| --- | --- | --- |
| `Yıllık İzin` (annual) | 378 | No |
| `Uzaktan Çalışma` (remote work) | 56 | **Yes — see below** |
| `Mazeret` (excused absence) | 41 | No |
| `Eğitim İzni` (training) | 25 | No — decided, ADR-037 |
| `Doğum Günü İzni` (birthday) | 10 | No |
| `İstirahat (Raporlu)` (medical) | 8 | No |
| `Doğum İzni (Tam Ödeme)` (parental, paid) | 2 | No |
| `Ücretsiz İzin` (unpaid) | 2 | No |

**D13 — `Kullanılan Gün` is hours ÷ 9, and that tells us the workday is 9 hours.**

Fractional day values are not noise. For a single-day row the HCM computes

```
Kullanılan Gün = round((Bitiş − Başlangıç) / 9 saat, 2)
```

Verified: the ratio is exactly **9.0** for 346 of 347 single-day annual-leave rows.
The apparent outliers (9.09, 8.93) are the 2-decimal rounding read backwards — 1 hour
÷ 9 = 0.1111 is stored as `0.11`, which divides back to 9.09.

| Duration | Days | | Duration | Days |
| --- | --- | --- | --- | --- |
| 1 h | 0.11 | | 5 h | 0.56 |
| 2 h | 0.22 | | 6 h | 0.67 |
| 3 h | 0.33 | | 7 h | 0.78 |
| 4 h | 0.44 | | 8 h | 0.89 |
| 4.5 h | 0.50 | | 9 h | 1.00 |

**Multi-day rows are different**: there `Kullanılan Gün` is the count of working days
covered, not the span ÷ 9. `07.05 07:30 → 08.05 16:30` spans 33 hours and is recorded
as `2.0`.

A person's monthly figure is the sum, which is why the `İzin Özeti` sheet is full of
values like `3.78`. A real May example:

```
Uzaktan Çalışma   05.05  07:30-16:30   9.00 h  ->  1.0
Mazeret           15.05  14:00-16:30   2.50 h  ->  0.28
Yıllık İzin       20.05  07:30-16:30   9.00 h  ->  1.0
Yıllık İzin       25.05  07:30-16:30   9.00 h  ->  1.0
Yıllık İzin       26.05  07:30-12:00   4.50 h  ->  0.5
                                                  ─────  3.78
```

149 of 160 people in May have a fractional total. It is the norm, not an anomaly.

**Why this matters beyond the leave sheet:** the HCM's own workday is **9 hours**, and
a June row splits one day as `Mazeret 0.44` + `Uzaktan Çalışma 0.56` = exactly `1.00`.
That is independent confirmation of the 9-hour day the report now pays after ADR-016,
and it is evidence that `overtime.expected_daily_net_hours: 8.25` in
`config/settings.yaml` is wrong. The key is unused (Phase 2, Q5) but must be corrected
before any overtime rule ships.

### `Uzaktan Çalışma` is worked time (ADR-007)

Confirmed by the project owner, 2026-08-03: remote work is **not** leave. The person
worked; they simply produced no badge record. Excluding it makes remote workers look
absent.

The rows carry usable times, so the hours are computable without any assumption:

- 56 records, 31 people
- **42 records are a full day**: `07:30–16:30`, `Kullanılan Gün = 1.0`
- 14 are partial: `07:30–09:30` (0.22 d), `11:30–16:30`, `07:30–11:45`, … Fractional
  day values run 0.11 – 0.89
- **48 of the 56 belong to people who also have badge records** in the same month,
  so double-counting is a live risk — see `DOMAIN-RULES.md §5.5`

Because start and end times are present on every row, remote hours are derived from
the record itself, not from a per-day constant.

**Most remote days also appear in the Teknopark timesheet, and that is expected.**
39 of 56 May records and 83 of 106 June records overlap an attendance record for the
same person-day. In 37 of 39 and 76 of 83 the attendance side is the nominal
`09:00–18:00` placeholder of D11, not a real punch — the timesheet filling in a day
with no turnstile data. The union counts the shared time once, and the report records
these at `info` severity: expected, not a defect (ADR-017).

The residue is the interesting part: **2 May records and 7 June records overlap a real
punch.** Those are the only cases where somebody declared remote work and a turnstile
genuinely recorded them, and they appear on `Sorulacaklar` as their own question.

**Free-text fields contain sensitive personal detail** (medical reasons, personal
excuses). They must not be reproduced in any report that is circulated more widely
than the individual concerned, and must never appear in a test fixture.

---

## 3b. The employee roster — the master registry

Added 2026-08-03. Export of active users from the IAS access-control system. **This
is the authoritative answer to "who is an employee".** Every other file is a
transaction log; this one is the roster.

**The filename is not stable.** It arrived as `SYST03_TEMPIASUSERS.xlsx` and was
renamed to `calisan_listesi.xlsx` on 2026-08-03; whoever exports it renames it
freely. Consequently:

- Matched by pattern, not name: `*calisan*`, `*çalışan*`, `*personel*`, `SYST03*`
  (`config/settings.yaml`). Globs are case-insensitive on Windows, but Turkish
  characters are **not** folded — `çalışan` needs its own pattern.
- If no pattern matches and the roster folder holds exactly **one** spreadsheet,
  that file is used. The reader then validates the layout, so a wrong file fails
  loudly rather than producing wrong numbers. This fallback applies **only** to the
  roster folder — guessing inside a month folder would grab an attendance export.
- The **sheet** is located by its columns, not its name, for the same reason. See
  below.

**Shape.** Two sheets, 181 employees, 14 columns. `TEMPIASUSERS` is the real one;
`Sayfa1` is a derived `isim` + `E-posta` pair list with no extra information —
picking it would silently lose facility, department and job title.

Because the sheet name may change along with the filename, the reader **finds the
sheet by header text**: the first sheet carrying all of `Kullanıcı`, `Kontak No`,
`İsim`, `Soyad`, `E-posta`. `TEMPIASUSERS` is tried first only as a fast path.
Column positions are also derived from the header, so a reordered export still works.

| Header | Example | Use |
| --- | --- | --- |
| `Kullanıcı` | `ADENEME` | login — distinguishes duplicate accounts (D9) |
| `Kontak No` | `000000004001` | IAS contact ID — **not** a personnel number, see D8 |
| `İsim` | `ALİ` | **first given name only** — middle names are dropped (D7) |
| `Soyad` | `AKPINAR` | |
| `E-posta` | `adeneme@ornek.com.tr` | **all 181 populated** — unblocks Phase 4 |
| `Bölüm` | `KONTROL VE OTOMASYON SİSTEMLERİ` | better than the attendance files' |
| `Tesis` | `DEICO TESİS` / `MACUNKÖY TESİSİ` | **home facility** — 112 / 69 |
| `Görev` | `ELEKTRONİK TASARIM MÜHENDİSİ` | job title |

The first five are required; `Bölüm`, `Tesis` and `Görev` are used when present.
`Açıklama` is empty throughout, `Kontak Tipi` is `Çalışan` and `Firma` is `DEICO`
for all 181 rows, and `Profil`, `Dosya Yolu`, `Sektör Kodu` are unused.

### D7 — Middle names are dropped

The roster stores only the first given name. The attendance and leave exports store
the full name:

| Roster | Elsewhere |
| --- | --- |
| `AHMET SINAMA` | `AHMET CAN SINAMA` |
| `AYLA MİSAL` | `AYLA NUR MİSAL` |
| `CAN DENEME` | `CAN TEKİN DENEME` |
| `HANDE ÖRNEK TASLAK` | `HANDE NUR ÖRNEK TASLAK` |

Exact-name matching therefore fails for ~40 % of people. Matching on
**(first token, last token)** fixes it: coverage jumps from 77/128 to 106/128 on the
Macunköy file, and 161 of 162 people in the leave export resolve.

**Guard.** The 181 roster names produce **181 distinct (first, last) keys — zero
collisions** in this export. The rule is only safe while that holds. The loader must
build the index, assert uniqueness, and **fail loudly** on a collision rather than
silently merging two people. Re-checked on every monthly export. See ADR-010.

### D9 — Duplicate accounts for one person

`İREM ÖRNEK` appears twice, rows 108 and 110, with **identical** contact number
(`8803`), e-mail, department and job title. The only difference is the login:
`IOREK` and `IYENI` — a surname change where the old account was never closed and
the `İsim`/`Soyad` fields were never updated on the new one.

This is a duplicate, not a collision: same person, two rows. The reader
deduplicates on matching contact number or e-mail and reports it on the report's
`Kontrol` sheet. It raises **only** when a repeated key belongs to genuinely
different identity data. See ADR-013.

### D8 — `Kontak No` matches nothing

Tested against every ID in every other file: **0 matches** out of 162 leave-export
personnel numbers, 44 numeric Macunköy IDs, and 35 `SN` card numbers. It is an
internal IAS identifier. Do not attempt to use it as a join key.

### The facility field settles the dual-site question

Cross-tabulating which attendance file a person appears in against their `Tesis`:

| Appears in | Count | `DEICO TESİS` | `MACUNKÖY TESİSİ` | not in roster |
| --- | --- | --- | --- | --- |
| Both files | 79 | **75** | **0** | 4 |
| Teknopark only | 31 | 27 | 0 | 4 |
| Macunköy only | 49 | 0 | 31 | 18 |

The pattern is clean: people based at `DEICO TESİS` (the Teknopark office) appear in
both files because they visit the Macunköy site; people based at `MACUNKÖY TESİSİ`
appear only in the Macunköy file. **Not one Macunköy-based employee shows up in
both.** This is exactly what ADR-001's dual-presence model predicts, and it closes
open question Q1.

Consequence: `Tesis` is the correct source for the report's location column. It is a
fact about the employee, not an artefact of which terminal they happened to touch.

### Coverage against the other files

| | People | Resolve to roster |
| --- | --- | --- |
| Leave export | 162 | **161** (missing: `İBRAHİM KAYRA SINAMA`, personnel no `9001` — the `9xxx` range suggests intern or contractor) |
| Macunköy (real staff) | 128 | 106 |
| Teknopark | 110 | 102 |
| Attendance union | 162 | 136 (**84 %**) |

Two residues, both needing HR:

- **26 people have attendance records but are not in the roster.** Likely leavers
  who worked part of May, or contractors outside the IAS registry. They worked; they
  must still be reported. Their hours are real.
- **20 roster employees appear in no file at all** — 15 `MACUNKÖY TESİSİ`,
  5 `DEICO TESİS`. Combined with the 24 leave-only people who are also
  Macunköy-based, roughly **39 of the 69 Macunköy-facility employees have no badge
  data**. That is more than half the site and is unlikely to be 39 individual
  absences — it points to a second Macunköy terminal or a partial export. Q4.

**Do not treat the roster as a whitelist.** Someone absent from it who has attendance
records still worked and still gets a row. The roster enriches identity; it does not
authorise it.

A vendor's sample output. **Never read this as data.** It defines the shape HR
wants and is the reference for `docs/OUTPUT-SPEC.md`.

11 sheets, all tiny (2–15 rows) because it is a mock-up: `Dashboard`,
`Günlük Giriş-Çıkış`, `Haftalık FM`, `Aylık Özet`, `Vardiya`, `Resmi Tatil`,
`Hafta Tatili`, `Multinet`, `Yıllık Özet`, `Mazeret İzni`, `Görevlendirme`.

Note the mock-up is **single-employee** — every sheet shows one person's month.
Our report must cover 162 people, so the layout cannot be copied literally.
See `docs/OUTPUT-SPEC.md §1`.

---

## 5. `MEYER Programı Toplantı İçeriği 1.docx` — requirements, not input

The customer's requirement list, taken verbatim into `docs/PRODUCT.md`. It is the
authoritative source for every business rule. Read it there.

---

## 6. Cross-file reconciliation

Measured overlap:

```
Macunköy identities                      151
  minus visitor/temp badges (D4)          -23
Macunköy real employees                  128
Teknopark employees                      110
Present in BOTH attendance files          76      <- the core problem
Union of real employees                  162
People in the leave export               162
Leave people with no attendance record     33
```

**The 76-person overlap** is the central design constraint of this project.
See ADR-001 and `docs/DOMAIN-RULES.md §4`.

### 6.1 The 33 unmatched people — resolved

Of the 33 people in the leave export with no attendance match, **9 are spelling
variants of people who do have attendance records**, and 24 genuinely have none.

**A — Turkish character differences (4). Certainly the same person:**

| Leave export | Attendance export |
| --- | --- |
| `AYŞE DENEMECİ` | `AYŞE DENEMEÇİ` |
| `VELİ ÖRNEKÇİ` | `VELİ ÖRNEKCİ` |
| `MELİK NUMUNE` | `MELIK NUMUNE` |
| `ÜMİT TASLAK` | `ÜMIT TASLAK` |

Note these differ in **both** directions — neither file is consistently correct.
`C`/`Ç`, `I`/`İ`, `S`/`Ş` are entered inconsistently at the data-entry layer.

**B — Surname additions and abbreviation (5). Almost certainly the same person,
requires human confirmation:**

| Leave export | Attendance export | Likely reason |
| --- | --- | --- |
| `SEDA DENEME ÖRNEK` | `SEDA DENEME` | married name |
| `ELİF SU MİSAL NUMUNE` | `ELİF SU MİSAL` | married name |
| `ZEHRA NAZ SINAMA DENEME` | `ZEHRA NAZ SINAMA` | married name |
| `NURAY TASLAK ÖRNEK` | `NURAY TASLAK` | married name |
| `MURAT KEREM ÖRNEK` | `M. KEREM ÖRNEK` | abbreviated given name |

All nine go into `config/personel.yaml` as explicit aliases (ADR-004). They are
**not** matched automatically — the list above was produced by a one-off diagnostic
script, reviewed by a human, and frozen into config. No fuzzy matcher ships.

**C — people with genuinely no attendance record.** Measured with the pipeline's own
resolved identities (an earlier diagnostic without alias resolution overstated this):

| | May 2026 | June 2026 |
| --- | --- | --- |
| People the report can produce no hours for | 26 | 18 |
| — explained by month-long leave (maternity, certified sick, unpaid) | 2 | 3 |
| — **in the roster, unexplained** | **18** | **10** |
| — absent from the roster, unexplained (probable leavers/contractors) | 6 | 5 |

**Filter out the long-term leave cases before taking this to IT.** Two to three
people each month are on paid maternity leave or certified sick leave covering the
whole month — their absence from the attendance export is correct, not a gap. Chasing
them wastes IT's time and weakens the real question.

The signature of a genuine gap is a **small** leave balance next to a whole missing
month: someone with 1–2.5 days of annual leave and zero badge records across 14–22
expected working days. One of the clearest cases filed a *Mazeret* (excused lateness)
in June, which only makes sense if they were expected at work — yet 21.4 of that
month's 22 working days have no badge record at all.

Two different problems sit in that table.

**The one that matters: 18 rostered employees never badged at all** (10 in June),
essentially all of them Macunköy-based. They are on the roster, they filed a day or
two of leave, and the attendance export has nothing for them. Hire date does not explain it
(the "recent hire" hypothesis was tested against the personnel-number range and
disproved). This is Q4, and the question is for IT: **does the Macunköy export cover
every terminal and every employee at that site?**

**The minor one: 5 people with only one-sided Macunköy rows.** All 5 are absent from
the roster, so probable leavers or contractors. Do not confuse these with the 54
people who have *no complete pair* in the Macunköy file — 49 of those have a Teknopark
record for the same period, so their real day is captured and the Macunköy row is
just a site visit. See §6.4.

Individual cases within the 21 vary: one person is on paid parental leave for the
whole month, so absence is expected. Another has 5.5 days of annual leave and no
attendance at all, leaving ~15 working days unaccounted for.

Do not report any of these people as "worked 0 hours" — report them as
**"no attendance data"**, which is a different statement.

### 6.4 One-sided Macunköy records are mostly a site-visit artefact

The Macunköy terminal records visits by Teknopark staff as well as its own site's
attendance. A visit often produces a single punch — badge in at the gate, leave by
another route — so a one-sided row is normal there, not a defect.

| | May 2026 | June 2026 |
| --- | --- | --- |
| People with **no** complete pair in the Macunköy file | 54 | 50 |
| of which `DEICO TESİS` (Teknopark-based) | 47 | 43 |
| of which `MACUNKÖY TESİSİ` | **0** | **0** |
| **have a Teknopark record too** → real day captured | **49** | **45** |
| no Teknopark record either → hours genuinely missing | 5 | 5 |
| People with both complete and one-sided rows | 42 | 61 |

Not one Macunköy-based employee falls in this group, in either month. That is the
evidence for the site-visit reading, and it is why these rows are a minor issue while
§6.1 group C is not.

### 6.2 Calendar coverage — resolved

Dates present per file:

| | Dates present | Missing |
| --- | --- | --- |
| Macunköy | 30 of 31 | `2026-05-03` |
| Teknopark | 21 of 31 | `05-02`, `05-03`, `05-10`, `05-23`, `05-24`, `05-27` … `05-31` |

**Neither file is truncated.** The pattern matches the calendar:

- `2026-05-03` is a **Sunday with no activity anywhere** — not missing data.
- Teknopark's missing dates are weekends plus **27–31 May**.
- The leave export shows company-wide `Toplu İzin` on **25 May (full day)** and
  **26 May 07:30–12:00 (half day)**.

Reading those together, May 2026 almost certainly ran: Mon 25 May bridge day,
Tue 26 May half-day eve (arefe), **Wed 27 – Fri 29 May Kurban Bayramı**, Sat 30 –
Sun 31 weekend. The Teknopark office was closed; Macunköy production kept running,
which is why Macunköy has records for 27–31 and Teknopark does not.

Two consequences:

1. The public-holiday calendar for `config/takvim-2026.yaml` is derivable:
   1 May (Friday, Labour Day), 19 May (Tuesday), and the Kurban Bayramı block.
   **Confirm the exact dates with HR before Phase 2** — this drives holiday pay.
2. Macunköy has genuine public-holiday working time, so the
   `Resmi Tatil` report will have real content from day one.

### 6.3 Personnel number availability

| Source | Personnel number |
| --- | --- |
| Leave export (`HCMT34`) | Numeric, all 162 people. **Canonical.** |
| Macunköy | 54 numeric (49 match the leave export exactly), 45 `SN`-prefixed card numbers |
| Teknopark | **None at all** — name is the only identifier |

Therefore: match on name (ADR-004), then fill the personnel number from the leave
export. Where the leave export has no entry, the field is blank — never guessed
and never back-filled from an `SN` card number.

---

## 7. Where the files live

```
data/personel/                    <- git-ignored, NOT month-specific
└── SYST03_TEMPIASUSERS.xlsx

data/raw/2026-05/                 <- git-ignored, one month per folder
├── Macunköy Mayıs Mesai giriş-çıkış.xlsx
├── Teknopark - Mayıs Mesai Takip Exceli.xlsx
└── HCMT34_MAYIS_IZIN.xlsx

data/out/2026-05/                 <- git-ignored
└── mesai-raporu-2026-05.xlsx

docs/reference/                   <- committed, no employee data
├── MEYER Örnek Rapor Taslağı 1.xlsx      (single-employee mock-up)
└── MEYER Programı Toplantı İçeriği 1.docx (the requirements)
```

**The roster sits outside the month folders on purpose.** The other three files are
transaction logs for one period; the roster is a snapshot of who works here (ADR-011)
and is shared by every month. Copying it into each month folder would imply it
belongs to that month, which is exactly the confusion ADR-011 exists to prevent.

Lookup order: `--personel` (default `data/personel/`), then the month folder. The
fallback matters because a Drive upload is likely to contain all four files together.

**The roster's export date is read from the file's timestamp**, never hard-coded, and
reported on the `Kontrol` sheet with how far it sits from the reporting period. The
May 2026 run shows `28.07.2026 — Rapor döneminden 2 ay SONRA alınmış`, which is the
one-line explanation for the 11 leavers and 20 later hires.

Month folder names are the **ISO period** (`2026-05`, not `2026-mayıs`) because that
makes them the CLI's default input path: `mesai rapor --ay 2026-05` needs no
`--girdi`. One month per folder is a contract — ADR-014.

**Never put the roster in `docs/reference/`.** That folder is committed to git and
the roster holds 181 employees' names, e-mail addresses, departments and job titles.
Only the two MEYER files belong there; they contain no employee data.

Filenames contain non-ASCII characters (`ı`, `ö`, `ş`). Quote paths in shell
commands. Files are matched by glob pattern, not exact name, so the names above are
examples rather than requirements.
