# ROADMAP.md — Phases, Status, Open Questions

Update the status table as work completes. An agent finishing a phase updates this
file as part of that work.

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Understand the data, agree the plan | **Done** — 2026-08-03 |
| 1 | Total hours worked per employee per month | **Done** — 2026-08-03 |
| 1b | Validate against a second month | **Done** — June 2026 runs clean |
| 2 | Overtime, shifts, Multinet, holidays | Blocked on Q5–Q8 |
| 3 | Leave integration, excused absence, assignments | Not started |
| 4a | Drive ingestion automation | **Deferred** — manual by decision, 2026-08-03 (Q21) |
| 4c | Desktop window, no terminal needed | **Done** — 2026-08-18, `arayuz.cmd` |
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
| "This is how many hours person X actually worked in May" | **No** — ~426 days are unaccounted for, and the report marks every one of them |
| "This is ready for payroll" | **Only after the marked days are checked by hand** — see ADR-071 |
| "This can be e-mailed to employees" | **No** — Q18, plus the three delivery decisions in `HANDOVER.md §1` |

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
- [x] `rules/worktime.py` — midnight crossing, daily measure, residual break
- [x] Report sheets per `OUTPUT-SPEC.md §2` — six of them, including
      `İnceleme Listesi` (per-person worklist) and `Kontrol` (reconciliation)
- [x] `cli.py` plus `rapor.cmd` — runs without activating the conda environment
- [x] 127 unit tests, all passing
- [x] Determinism verified: two runs produce 23 273 identical cells
- [x] Reconciliation invariant holds: Σ per-person == Σ measured person-days
- [x] **2026-08-17 — calculation rules revised.** No break deduction (ADR-016), the
      day measured first entry → last exit (ADR-015), remote hours overriding a
      nominal placeholder (ADR-018), and days under 2 h flagged (ADR-019). All are
      config switches. Reproducing the pre-2026-08-17 report takes three of them
      together — `break.deduct: true`, `daily_hours: union`,
      `remote_day_replaces_attendance: never` — verified end to end: June brüt
      `26 964:33`, net `24 971:48`.
- [ ] **Remaining:** HR spot-checks three people against the source files

Input files are located by glob pattern rather than fixed name, so a Drive-synced
folder can be pointed at directly — the Phase 4 automation needs no renaming step.

### Three months generated

Measured from the three workbooks on 2026-08-26, not carried over from an earlier
version of this table. Several rows had drifted: the without-attendance counts moved
when ADR-067 redefined what "has attendance" means, June's presence figure was 47
minutes stale, and the anomaly counts predate ADR-060/061.

| | May 2026 | June 2026 | July 2026 |
| --- | --- | --- | --- |
| People in the report | 171 | 163 | 176 |
| with attendance data | 148 | 146 | 150 |
| without attendance data (`Kart bilgisi yok`) | 23 | 17 | 26 |
| not in the roster (probable leavers) | 11 | 9 | 9 |
| **roster entry, no trace at all** (ADR-071) | **21** | **27** | **14** |
| Person-days | 1 823 | 2 822 | 2 731 |
| Presence (Σ intervals) | 16 931:16 | 26 881:43 | 26 014:34 |
| In-day gaps, paid (ADR-015) | 172:41 | 284:35 | 218:43 |
| **Total reported** | **17 103:58** | **27 166:19** | **26 233:17** |
| Anomalies | 365 (295 excluded) | 622 (469 excluded) | 689 (537 excluded) |
| Reconciliation | TAMAM | TAMAM | TAMAM |
| Teknopark blocks disagreeing with their own total | 0 / 110 | 0 / 110 | 0 / 112 |

**July is in this table now.** It was excluded while its Teknopark export covered only
1–19 July (13 of 23 working days) and its `16 078:44` was not comparable; the full-month
file arrived on 2026-08-20 and the run exits `0`. The guard that caught the partial file
is unchanged — red banner on `Aylık Özet`, `3. Dönem kapsamı` on `Kontrol`, exit code 5.
See ADR-020 and Q23.

The anomaly counts rose from 257/441 without a single hour moving: ADR-060 and ADR-061
flag days that have no record at all, which had been invisible rather than accounted for.

Three rule changes landed on 2026-08-17. For May, starting from the previous
`15 717:08` net / `17 009:01` gross:

| Change | May | June |
| --- | --- | --- |
| ADR-016 — no break deduction | +1 291:52 | +1 992:45 |
| ADR-015 — in-day gaps paid | +159:11 | +284:35 |
| ADR-018 — remote hours override the placeholder | −64:15 | −129:45 |
| **Net effect vs the old net figure** | **+1 386:50** | **+2 147:36** |

ADR-019 added 15 (May) and 20 (June) `SHORT_DAY` flags, which is why the anomaly count
rose; it changes no hours.

The decomposition is a **sequence**, not independent parts. ADR-015's `+159:11` is what
paying in-day gaps was worth *before* ADR-018; dropping the placeholders afterwards
exposed three gaps a placeholder had been bridging, so the final gap figure in the table
above is `172:41`. Both numbers are right for what they measure.

All figures are the report's own `Kontrol` values. `HH:MM` truncates seconds, so
adding two displayed rows can differ from the displayed total by a minute — June's
does. The underlying `timedelta` arithmetic is exact; only the rendering rounds.

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
- **One-sided Macunköy records are mostly harmless.** 54 people have no complete
  pair in that file, and 47 of them are `DEICO TESİS` staff — the Macunköy terminal
  is recording site *visits*, which naturally produce a single punch. **49 of the 54
  have a Teknopark record for the same period**, so their real working day is
  captured; only 5 do not, and all 5 are absent from the roster (probable leavers or
  contractors). An earlier estimate of 31 was wrong — it came from a diagnostic
  script that did not apply alias resolution.
- **The real gap is on the Macunköy side, not Teknopark.** 20 employees whose home
  facility is `MACUNKÖY TESİSİ` have leave records and zero badge records. Same shape
  in June: 13 people, all Macunköy-based. That was Q4, closed as a manual step by
  ADR-071 — along with the second group the same paragraph had missed: people with a
  roster entry and **no leave record either**, who got no row at all.
- **Most remote-work days also carry a Teknopark record** — 37 of 56 in May, 83 of
  106 in June. Nearly all of those are the nominal `09:00–18:00` placeholder rather
  than a real punch (`DATA-SOURCES.md` D11), so since ADR-018 the declared remote hours
  are used and the placeholder is set aside. Only 2 May and 5 June records overlap a
  genuine punch, and those keep every hour.

Deliberately not in Phase 1: overtime, shortfall, shifts, Multinet, holiday
compensation, e-mail.

## Phase 2 — Overtime, shifts, Multinet, holidays

Blocked on Q5–Q8. Covers `PRODUCT.md` §2–§4 and the colour-coded holiday report.

- [ ] `config/takvim-2026.yaml` with confirmed public holidays
- [ ] `rules/calendar.py`, `rules/shifts.py`, `rules/overtime.py`,
      `rules/multinet.py`
- [ ] Sheets `Fazla Mesai`, `Haftalık FM`, `Multinet`, `Vardiya`, `Resmi Tatil`,
      `Hafta Tatili` (`Kontrol` already exists)
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

### 4c — Running it without a terminal ✅

Done 2026-08-18. `src/mesai/gui/`, launched by `arayuz.cmd`.

The operator will not be a developer, so "open a console and pass `--ay`" was never a
deliverable. `tkinter` from the standard library, so nothing new to install and it
packages into a single executable later.

It is a **thin shell over `pipeline.run()`** — the same call `cli.py` makes, no business
logic of its own. That cost nothing to add because `pipeline.py` had already been split
out of `cli.py` for exactly this.

Appearance was reworked on 2026-08-18 after the first version was fairly called
"Windows XP". The theme was already `vista` and the font already Segoe UI; what dated
it was everything sharing one flat grey, `relief="solid"` sunken borders, and a
`tk scaling` override that rendered text *smaller* than the system setting. Now: light
body, white cards, hairline borders, one accent-coloured primary action, and
`SetProcessDpiAwareness` so text is crisp rather than bitmap-stretched.

Coloured controls are `tk` rather than `ttk` on purpose — the vista theme ignores
background/foreground on ttk widgets, so a ttk.Button cannot be given an accent colour
at all. Flat buttons then need explicit hover and disabled painting, which is what
`_button` and `_set_enabled` exist for.

Reworked further the same day, in this order:

- **Split into a `gui/` package** before the e-mail step rather than during it: shell
  (`app.py`), report screen (`rapor.py`), month parsing (`period.py`), shared widgets
  (`widgets.py`). One 662-line module with one class was about to acquire a second job.
- **A left navigation rail** (`nav.py`). Adding a work face is one entry in
  `app.SCREENS`; the rail is generated from it and a screen is built the first time it
  is opened. Only screens that exist are listed — no placeholder item.
- **Five presentation defects**, all found by opening the window and looking rather
  than by reading the code: an activity bar that showed part-filled at rest, a starting
  instruction painted in the colour of an error, found and missing sources sharing one
  colour, a summary aligned with spaces in a proportional font, and a result card that
  clipped the snapshot path it had just printed.
- **Naming one export outright** when it is not where the others are (ADR-022), and
- **failing the run when a source is the wrong month** (ADR-023) — which the previous
  item made easier to reach, and which was found by measuring rather than assuming: the
  run had been succeeding with a report 72 % short and no warning at all.
- **Writing where the user chose** (ADR-024): Desktop by default, the choice
  remembered, one folder per month named `2026-06 Rapor` (ADR-025) holding the workbook
  and its snapshot together. This is also what makes the packaged executable viable — a run no
  longer needs the program's own directory to be writable.

Design notes worth keeping:

- **No default input folder, and no restored selection.** A wrong guess is worse than
  an empty field: the user cannot tell it happened. They browse to the folder, and the
  window immediately lists which of the three exports it found — all three, not just
  the first failure.
- **Only the browse starting point is remembered.** Restoring the last chosen folder
  was tried and removed: the input folder is month-specific, so from the second month
  it always offered a finished month with the period pre-filled. The parent is kept
  instead, so the dialog opens on the right share while the selection stays
  deliberate.
- The work runs off the UI thread, or Windows labels the window "not responding".
- **No e-mail tab.** There is still none, and there does not need to be: sending is one
  button on the person already selected (ADR-073), not a screen of its own. Modularity
  belongs in module boundaries, not in a placeholder the user has to ignore.

Still to do for a machine without Python: package as a single `.exe` (PyInstaller). The
real work there is testing it where Python is absent, not the packaging itself. `config/`
must stay outside the executable — rule changes are YAML edits and `personel.yaml` holds
real spellings.

### 4b — Per-employee e-mail — **one at a time: BUILT** ✅ (ADR-073)

The window sends one person one message about the days ticked for them: an address
field prefilled from the snapshot and editable, an `E-posta gönder…` button, and an
editable preview whose contents are what actually leaves. Gmail SMTP,
`config/gmail.yaml` (git-ignored).

How the hard requirements below came out:

| Requirement | How it stands |
| --- | --- |
| `--dry-run` the default, sending explicit | **Stronger than asked.** There is no send-everybody path at all, so there is nothing to default. One person, chosen by hand, previewed. A test asserts `sender.py` has no function named for a loop |
| rendered output reviewable before any send | **Done** — the preview, and it is editable; what is on screen is read back at send time |
| credentials never committed | **Done** — `config/gmail.yaml`, git-ignored beside `personel.yaml`; an app password, not the account password. Not environment variables: `config/` is where a rule change already lives and is the one place guaranteed writable (ADR-042) |
| only their own data | **Done** — `compose(person, days, …)` takes one person and the days ticked for them, and only the **ticked** note is written |
| verified recipient addresses | **Not done, and this is the open risk.** The address comes from the roster or is typed by hand; nothing checks it belongs to the person. A payroll figure sent to the wrong person is a personal-data breach, not a bug |

Still open, both about a bulk send rather than this one (`HANDOVER.md` §1): whether a
manual removal is recorded ("who did not get one, and why"), and whether an incomplete
month may be written from at all. A send log belongs with those — logging one hand-sent
message the operator just watched go out buys little; logging 162 buys a lot.

Not built and deliberately not: a monthly summary of somebody's own hours. This message
asks about problem days. Telling people their figures is a different message with a
different risk, and the address is not verified yet.

### 4d — The correction round-trip: **asked for, not built** (Q24)

The step after the mail. People reply with what actually happened — *"14.07'de 18:30'da
çıktım, kart okutmadım"* — and somebody has to put those answers back in and get a report
that counts them.

> *"danışman o bizim hazırladığımız exceli düzenlemek isteyecek eksik giriş çıkışları
> tamamlamak için günlük detaydan. o noktadan sonra o rapora göre bu uygulama ve json
> falan yeniden düzenlenmesi gerekecek."*

**Is it possible after the `.exe`? Yes — but it is a feature, so it is code, so it needs a
new `.exe`.** That is the line to hold in your head about the whole packaging question:
the things deliberately left in `config/` (mail wording, thresholds, holidays, aliases,
the account) change without a rebuild. Anything that changes what the program *does* is a
rebuild. There is no way around that and no reason to pretend otherwise.

#### The one thing not to do

Do **not** let the consultant edit `mesai-raporu-<ay>.xlsx` and have the program read that
back. The workbook is a presentation artifact — durations are `HH:MM` strings, cells are
merged, columns move when the layout changes (they moved in ADR-052 and again in ADR-075).
`snapshot.py` exists precisely because nothing may parse it, and making it both output and
input would mean a run could no longer be reproduced from its sources. It also means the
first person to sort a column or widen a cell silently changes payroll input.

#### The shape that works

A **fourth input file, purpose-built**, and the three exports stay as the base:

1. The program **writes a correction sheet** — only the problem days, one row each, with
   `Ad Soyad | Tarih | Okunan Giriş | Okunan Çıkış | Düzeltilmiş Giriş | Düzeltilmiş Çıkış
   | Açıklama`. Small, and the last three columns are empty and are the only ones anybody
   touches.
2. The consultant fills it from the replies.
3. The next run takes that file **alongside** the three exports and the corrected times
   become records like any other — with `source="düzeltme"`, so `Günlük Detay` shows
   `Kaynak: Düzeltme` and `Kontrol` counts how many were applied.

Note the consequence: this is not "updating" the report. It is **re-running** with one more
input. The pipeline stays a function of its inputs, which is what makes the same month
reproducible six months later when somebody argues about a figure (AGENTS §2.1).

#### Four things it must not break

- **A corrected hour must never look like a badge-read hour.** These figures go to payroll
  and get argued about. `Kaynak: Düzeltme` on the day, a count on `Kontrol`, and the
  original reading kept beside the corrected one — the same reasoning as ADR-055's `Etki`
  column and ADR-067's "a record that could not be used is still a record".
- **Determinism.** Same three exports + same correction file = byte-identical output. So
  the correction file is data, never a free-text note the program has to interpret.
- **A correction cannot invent a day nobody recorded.** It completes a reading; it does
  not create attendance out of nothing. A row for a date with no record at all is an
  anomaly to surface, not a day to count — otherwise the file becomes a way to type hours
  in, and this program's whole premise is that it never does that (ADR-003).
- **The reply itself is not evidence the program can check.** Whether somebody really left
  at 18:30 is a human judgement, made by the person filling the sheet. The program records
  *that a correction was made*, not that it was right.

#### Open before it can be built

- Who is allowed to fill that sheet, and does the report need to say a day was corrected
  without saying by whom (AGENTS §6 forbids naming a person in output)?
- Does a corrected month get regenerated in place, overwriting the report already sent to
  payroll, or does it become a second file? A figure that changed after somebody acted on
  it needs to be visible as changed.
- What happens to a mail already sent about a day that has since been corrected. Nothing
  currently records what was sent to whom (`HANDOVER.md` §1, still open).

## Phase 5 — Annual roll-up

`PRODUCT.md` §3: annual overtime and annual Multinet totals. Needs several months
of validated output first.

---

## 5. Açık sorular / Open questions

> Bu bölüm bilinçli olarak **Türkçe** — İK ve IT'ye sorulacak sorular burada,
> onları soran kişi bu listeyi okuyup konuşuyor. Dökümanın geri kalanı İngilizce
> (ajanlar için). Soru numaraları (`Qn`) değişmez; kod ve diğer dökümanlar bu
> numaralarla buraya referans veriyor.

**Karara bağlanmamış her şeyin tek listesi burasıdır.** Depoda geçen her `Qn`
referansı bu bölümü işaret eder.

Nasıl okunur:

- Numaralar **kronolojik** — sorunun ortaya çıktığı sıra, önem sırası değil.
  Harfler (`Q4a`, `Q4c`) bağlı oldukları sorunun devamıdır.
- **Kalın** satırlar gerçekten bir şeyi bloke edenler.
- `Bloke ettiği` kolonu, cevap gelmediği için neyin beklediğini söyler.
- Bir soru cevaplanınca **silinmez**, yukarıdaki **Cevaplananlar** tablosuna
  cevabıyla taşınır. Cevap birkaç seçenek arasından seçim gerektirdiyse ayrıca
  `DECISIONS.md` içine bir ADR olarak geçer. Sonradan gelen birinin o sorunun
  sorulduğunu bilmesi gerekiyor.

**Önce kovalanması gereken üçü:** **Q18** (işe giriş/çıkış tarihleri),
**Q5/Q6** (Faz 2'nin başlayamadığı fazla mesai kuralları). Q4 kapandı — cevabı
beklenmiyor artık, işaretlenip elle bakılıyor (ADR-071).

### Cevaplananlar

| # | Soru | Cevap |
| --- | --- | --- |
| Q1 | 76 kişinin iki mesai dosyasında birden görünmesi gerçekten çift tesis mi? | **Evet.** Personel listesindeki `Tesis` alanı çözdü: iki dosyada birden olan 79 kişinin 75'i `DEICO TESİS` çalışanı, ve **tek bir** Macunköy personeli iki dosyada birden yok. `DATA-SOURCES.md §3b`, ADR-010 |
| Q2 | `Uzaktan Çalışma` çalışma sayılacak mı? | **Evet.** Çalışma sayılıyor, saatler kaydın kendi başlangıç/bitiş saatinden alınıyor. ADR-007 |
| Q3 | Öğle arası: 42 dakikalık boşluk mola kullanılmış sayılır mı? | **Soru geçersiz kaldı.** 2026-08-17: mola hiç kesilmiyor, giriş-çıkış esas. Hiçbir boşluk molaya karşı ölçülmüyor. ADR-016 (kalan mola kuralı ADR-008 olarak duruyor, `break.deduct: true` ile geri açılabilir) |
| Q3a | Gün içindeki boşluklar ödenecek mi? | **Evet.** Gün, ilk girişten son çıkışa kadar ölçülüyor; aradaki boşluk düşülmüyor. Mayıs'ta 174 kişi-günde +172:41 (ADR-018 sonrası nihai değer). ADR-015 |
| Q11 | `ZİYARETÇİ*` / `GEÇİCİ*` / `STJ*` kartları raporlanacak mı? | **Hayır, tamamen düşüyor** (proje sahibi, 2026-08-18). Kart numaralı, isimli değil; saatler bir kişiye atfedilemiyor. Zaten mevcut davranış bu — `config/personel.yaml:exclude_prefixes`. Düşen satır sayısı `Kontrol` sayfasında raporlanıyor, yani gizlenmiyor |
| Q20 | `Uzaktan Çalışma` kaydı aynı gün kart kaydıyla çakışanlar (Mayıs 37, Haziran 80) sorun mu? | **Hayır, beklenen durum.** Kaynak sistemde nasıl oluştuğu bizi ilgilendirmiyor; o gün kaydı varsa sayılıyor. Rapora `bilgi` seviyesinde düşüyor, kimsenin `Şüpheli Kayıt` sayısını artırmıyor. Çakışmaların %94'ünde (Mayıs) / %91'inde (Haziran) puantaj tarafı nominal `09:00–18:00` satırı, gerçek turnike okuması değil. ADR-017 |
| Q20b | Çakışmaların içinde gerçekten sorulacak olan var mı? | **Evet, ama sadece 2 (Mayıs) ve 5 (Haziran) kayıt** — puantaj tarafı gerçek turnike okuması olanlar. `İnceleme Listesi`'nde ayrı bir satır türü olarak, sarı renkte duruyorlar. ADR-017 |
| Q20c | Uzaktan çalışılan günde puantajdaki nominal gün ne olacak? | **Uzaktan saatler esas alınıyor, nominal gün hesaba katılmıyor** (İK talimatı, 2026-08-17). Ama gerçek turnike okuması varsa hiçbir şey atılmıyor — 7 kişi-gün böyle. Mayıs −64:15, Haziran −129:45. ADR-018 |
| Q22 | Günlük süresi 2 saatten az olanlar tespit edilsin | **Eklendi.** Eşik `plausibility.short_day_hours: 2.0`, kişi-gün bazında. Mayıs'ta 15, Haziran'da 20 gün. Daha önce yapılmıyordu — mevcut 5 dakikalık eşik kayıt bazlıydı ve günü hiç bakmıyordu. ADR-019 |
| Q5'in bir parçası | Standart iş günü kaç saat? | **9 saat.** İzin dosyasının kendi `Kullanılan Gün` kolonu saati 9'a bölüyor (347 kaydın 346'sında oran tam 9,0). Haziran'da bir gün `Mazeret 0,44` + `Uzaktan 0,56` = tam `1,00`. ADR-016 sonrası ödediğimiz tam gün de 9 saat. `DATA-SOURCES.md` D13 |
| Q9 | Macunköy dosyasında hangi gün eksik? | `2026-05-03`, **iki dosyada da hiç hareket olmayan bir Pazar**. Veri sorunu değil. `DATA-SOURCES.md §6.2` |
| Q10 | Dışa aktarım formatı ay ay değişiyor mu? | **DEĞİŞTİ — 2026-08-18'de bu cevap geçersiz kaldı.** Haziran hiçbir değişiklik gerektirmemişti, ama Temmuz'da Macunköy dosyası `.xls`'e döndü, `Personel` kolonu kalktı ve başlık satırı aşağı kaydı. Okuyucular artık kabı ve kolon konumlarını keşfediyor. ADR-020, `DATA-SOURCES.md` D10 |
| Q13 | **`Eğitim İzni` uzaktan çalışma gibi çalışma sayılacak mı?** | **Hayır — izin.** İK onayladı. `Uzaktan Çalışma` dışındaki bütün türler izin; liste kapalı. "Kayıtlarında saat var" gerekçesi eğitime özgü değildi: on iki türün hepsinde her satırda saat var, yıllık izin dahil. Ölçülen alternatif maliyeti: Mayıs +18:26, Haziran +4:53 — çoğu eğitim saati zaten kart basılan günün içinde kalıyor. ADR-037 |
| Q23 | **Temmuz Teknopark dosyası ayın tamamını kapsamıyordu (1–19 Temmuz). Tam ay için yeniden alınabilir mi?** | **Alındı — 2026-08-20.** `Teknopark - Temmuz.xlsx` ayın 1–31'ini kapsıyor; iki kaynak da 23 iş gününün 23'ünde kayıt taşıyor, koşu `0` koduyla çıkıyor. Toplam 16 078:44 → **26 233:17** (+10 154:33, ayın yarısı). Guard eksiği doğru yakalamış ve doğru bırakmıştı. **Dosyaların her ay ayın kaçında alınacağı hâlâ belirsiz** — bir sonraki ayın aynı hataya düşmemesi buna bağlı. ADR-020, `DATA-SOURCES.md` D12 |
| Q16 | Resmi tatil takvimini İK onaylasın mı? | **Hayır, İK'ya sorulacak bir şey değil.** Tatilleri programı kullanan kişi pencerede işaretliyor; takvimde tarihten başka bir şey tutulmuyor. ADR-045 |
| Q14 | Teknopark dosyası kesilmiş mi (31 günün sadece 21'i var)? | **Hayır.** Eksik günler hafta sonları artı 27–31 Mayıs tatil bloğu; ofis kapalıyken Macunköy üretimi çalışıyordu. `DATA-SOURCES.md §6.2` |
| Q15 | Sıralama ve eşleştirme isimle mi sicil numarasıyla mı? | **İsim anahtar ve sıralama ölçütü**; sicil numarası bilgi amaçlı ve sadece izin dosyasından. ADR-009 |
| Q17 | Faz 4 için personel e-posta adresleri nereden gelecek? | Personel listesinden — 181 kişinin hepsinde dolu. Mesai kaydı olanların %97'si kapsanıyor; kalanlar kart kaydı hiç olmayanlar |
| Q19 | İK doğrulama için ikinci bir ay verebilir mi? | **Tamamlandı** — Haziran 2026 elimizdeydi ve sorunsuz çalıştı. Okuyucuların genellendiğini kanıtlamak için üçüncü aya gerek yok |
| **Q4** | **Macunköy dosyası o tesisin bütün turnikelerini ve bütün personelini kapsıyor mu?** (Mayıs 18, Haziran 10 kişinin personel ve izin kaydı var, tek kart kaydı yok, neredeyse hepsi `MACUNKÖY TESİSİ`) | **Cevap beklenmiyor — soru kapandı** (2026-08-26, ADR-071). Cevap programın yaptığı hiçbir şeyi değiştirmezdi: kart kaydı yoksa saat uydurulamaz, yapılacak tek doğru şey ayı eksik diye işaretlemek ve birinin gidip bakması. `Kart bilgisi yok` notu bunu zaten yapıyor (Mayıs 23, Haziran 17, Temmuz 26 kişi) ve kişi her zaman listeye giriyor. Kapatırken çıkan gerçek boşluk ayrıydı ve kapatıldı: personel listesinde olup **ne kart ne izin** kaydı olan 21/27/14 kişi hiçbir yerde görünmüyordu, artık `Kontrol` §5'te adlarıyla duruyor |
| Q4b | 27 kişinin mesai kaydı var ama personel listesinde yok | **Ayrılmışlar.** Personel listesi Ağustos'ta alındı; bu kişiler Mayıs'ta çalışıp Ağustos'a kadar ayrılmış. Tam satır ve tam saatlerini alıyorlar. ADR-011 |
| Q4d | Personel listesindeki 20 kişi hiçbir Mayıs dosyasında yok | **Mayıs'tan sonra işe girmişler.** Mayıs raporunda satır almıyorlar. ADR-011 |

### Açık

| # | Soru | Bloke ettiği | Neden önemli |
| --- | --- | --- | --- |
| Q4a | `DATA-SOURCES.md §6.1`'deki dokuz isim varyantı çiftinin aynı kişiler olduğunu onaylayın, alias tablosuna sabitlenebilsin | Faz 1 | Yanlış bir eşleştirme iki kişinin bordro saatlerini birleştirir |
| Q4c | Sicil `9001` — izin dosyasında olup personel listesinde olmayan tek kişi. `9xxx` aralığı stajyer mi, taşeron mu? | Faz 1 | Personel listesinin tamamen atladığı bir çalışan kategorisi olabilir |
| **Q18** | **Personel listesi `İşe Giriş Tarihi` ve `İşten Çıkış Tarihi` kolonlarıyla yeniden alınabilir mi?** | Faz 1 doğruluğu, Faz 4 güvenliği | "Sonradan girdi / önceden ayrıldı / verisi eksik" ayrımını çıkarımdan olguya çevirir. Ayrıca Faz 4'te ayrılmış birine mail gitmesini engeller. ADR-011. **ADR-061'den sonra daha somut:** `Hem giriş hem çıkış yok` artık ay içinde işe girmiş olabilecekleri de listeliyor, çünkü program ikisini ayırt edemiyor — Temmuz'da 5 kişi 18–21 günle listede. Tarih gelirse çıpa `max(işe giriş, ayın 1'i)` olur ve o satırlar kendiliğinden düşer |
| Q24 | **Düzeltme dosyası (4d) hangi biçimde gelecek ve düzeltilen bir gün raporda nasıl görünecek?** Kişiler maile dönüş yapıyor, danışman eksik giriş-çıkışları tamamlamak istiyor. Üretilen Excel'i düzenleyip programa geri okutmak **yapılmayacak** — o dosya bir sunum çıktısı ve `snapshot.py` tam bunu engellemek için var. Doğru biçim: programın yazdığı, yalnızca sorunlu günleri taşıyan ayrı bir düzeltme dosyası, üç kaynak dosyanın **yanına** dördüncü girdi olarak | Faz 4d | Düzeltilmiş bir saat, karttan okunmuş bir saatten ayırt edilebilir olmalı — bu sayılar bordroya gidiyor. Ayrıca bordroya gönderilmiş bir raporun sonradan değişmesi görünür olmalı |
| Q5 | **Beklenen günlük süre `config/settings.yaml`'da hâlâ `expected_daily_net_hours: 8.25` yazıyor ve bu artık yanlış.** İş gününün 9 saat olduğu iki bağımsız kaynaktan doğrulandı (bkz. Cevaplananlar). İK'nın onaylaması gereken tek şey: fazla mesai eşiği 9 saatin üstünden mi başlıyor? | Faz 2 | Bütün fazla mesai hesabı buna dayanıyor. Kullanılmayan bir parametre, ama Faz 2 açılmadan düzeltilmeli |
| Q6 | Fazla mesai hafta sınırı (Pzt–Paz mı); eksik çalışma hafta içinde fazla mesaiyi mahsup ediyor mu; tam 3 saat ve tam 7,5 saatte davranış ne. **"Brüt mü net mi" kısmı cevaplandı: brüt** — ADR-016 ile net diye ayrı bir sayı kalmadı | Faz 2 | Multinet hakedişi para demek |
| Q7 | Otomatik vardiya atamasında giriş saati pencereleri tam olarak ne; `2. Vardiya` henüz yok — ne zaman devreye girecek? | Faz 2 | Yanlış vardiya ⇒ yanlış beklenen saat |
| Q8 | Resmi tatil çalışmasının ücret mi izin mi olacağına kim nasıl karar veriyor, bu bilgi nereden gelecek? | Faz 2 | Mevcut hiçbir dosyadan çıkarılamıyor |
| Q12 | Raporun tamamını kim alabilir? Departman bazlı bölünmesi gerekiyor mu? | Faz 1 çıktısı | 162 kişinin kişisel verisi tek dosyada |
| Q20a | **Teknopark puantajındaki nominal `09:00–18:00` satırları neden yazılıyor?** Mayıs'ta 319, Haziran'da 418 satır; %90'ının arkasında uzaktan çalışma beyanı yok, yani tetikleyici sadece uzaktan çalışma değil. Kalanların sebebi hiçbir dosyadan çıkmıyor (görev, seyahat, unutulan kart?) | Hiçbir şeyi bloke etmiyor — ADR-017 ile çalışma sayılıyor | Raporun ~%17'si bu satırlardan geliyor. Cevap "bordroda ödenmiyor" olursa yeni bir ADR ve ~%17 düşüş demek. `DATA-SOURCES.md` D11 |
| **Q21** | **Kaynak dosyalar her ay Google Drive'a yükleniyor. Hangi entegrasyon?** Elle (bugünkü), Drive for Desktop (sürücü harfi, kod değişikliği yok), Drive API (gözetimsiz, ağ bağımlılığı ekler), ya da mevcut `Y:` ağ sürücüsü. Ayrıca: klasör ay başına ayrı mı? Erişimi kimde? | Faz 4 | 2026-08-03'te **şimdilik elle** kalmasına karar verildi. **2026-08-18: klasör yapısı belli oldu** — dosyalar `Y:` ağ paylaşımında, ay başına ayrı klasör, `AA - YYYY` biçiminde adlandırılmış. Yani Drive API'ye gerek yok, mevcut ağ sürücüsü yeterli. Erişim yetkisinin kimde olduğu hâlâ bilinmiyor. README "İleride: Drive otomasyonu" |
