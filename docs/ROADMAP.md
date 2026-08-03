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
- [x] Report sheets per `OUTPUT-SPEC.md §2` — six of them, including
      `Sorulacaklar` (per-person worklist) and `Kontrol` (reconciliation)
- [x] `cli.py` plus `rapor.cmd` — runs without activating the conda environment
- [x] 96 unit tests, all passing
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
- **One-sided Macunköy records are mostly harmless.** 54 people have no complete
  pair in that file, and 47 of them are `DEICO TESİS` staff — the Macunköy terminal
  is recording site *visits*, which naturally produce a single punch. **49 of the 54
  have a Teknopark record for the same period**, so their real working day is
  captured; only 5 do not, and all 5 are absent from the roster (probable leavers or
  contractors). An earlier estimate of 31 was wrong — it came from a diagnostic
  script that did not apply alias resolution.
- **The real gap is on the Macunköy side, not Teknopark.** 20 employees whose home
  facility is `MACUNKÖY TESİSİ` have leave records and zero badge records. Same shape
  in June: 13 people, all Macunköy-based. That is Q4.
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

**Önce kovalanması gereken dördü:** **Q4** (bir tesisin mesai verisi tamamen eksik
mi), **Q18** (işe giriş/çıkış tarihleri), **Q16** (resmi tatil takvimi),
**Q5/Q6** (Faz 2'nin başlayamadığı fazla mesai kuralları).

### Cevaplananlar

| # | Soru | Cevap |
| --- | --- | --- |
| Q1 | 76 kişinin iki mesai dosyasında birden görünmesi gerçekten çift tesis mi? | **Evet.** Personel listesindeki `Tesis` alanı çözdü: iki dosyada birden olan 79 kişinin 75'i `DEICO TESİS` çalışanı, ve **tek bir** Macunköy personeli iki dosyada birden yok. `DATA-SOURCES.md §3b`, ADR-010 |
| Q2 | `Uzaktan Çalışma` çalışma sayılacak mı? | **Evet.** Çalışma sayılıyor, saatler kaydın kendi başlangıç/bitiş saatinden alınıyor. ADR-007 |
| Q3 | Öğle arası: 42 dakikalık boşluk mola kullanılmış sayılır mı? | **Kalan mola kuralı** — `45 − zaten ücretsiz geçen` kadar kesiliyor, eşik yok. ADR-008 |
| Q9 | Macunköy dosyasında hangi gün eksik? | `2026-05-03`, **iki dosyada da hiç hareket olmayan bir Pazar**. Veri sorunu değil. `DATA-SOURCES.md §6.2` |
| Q10 | Dışa aktarım formatı ay ay değişiyor mu? | **Hayır.** Haziran 2026 okuyucularda hiç değişiklik olmadan işlendi: 110 blokta 2 557 Teknopark satırı, 110'unun 110'u dosyanın kendi toplamıyla tutuyor; mutabakat TAMAM |
| Q14 | Teknopark dosyası kesilmiş mi (31 günün sadece 21'i var)? | **Hayır.** Eksik günler hafta sonları artı 27–31 Mayıs tatil bloğu; ofis kapalıyken Macunköy üretimi çalışıyordu. `DATA-SOURCES.md §6.2` |
| Q15 | Sıralama ve eşleştirme isimle mi sicil numarasıyla mı? | **İsim anahtar ve sıralama ölçütü**; sicil numarası bilgi amaçlı ve sadece izin dosyasından. ADR-009 |
| Q17 | Faz 4 için personel e-posta adresleri nereden gelecek? | Personel listesinden — 181 kişinin hepsinde dolu. Mesai kaydı olanların %97'si kapsanıyor; kalanlar Q4 kapsamında |
| Q19 | İK doğrulama için ikinci bir ay verebilir mi? | **Tamamlandı** — Haziran 2026 elimizdeydi ve sorunsuz çalıştı. Okuyucuların genellendiğini kanıtlamak için üçüncü aya gerek yok |
| Q4b | 27 kişinin mesai kaydı var ama personel listesinde yok | **Ayrılmışlar.** Personel listesi Ağustos'ta alındı; bu kişiler Mayıs'ta çalışıp Ağustos'a kadar ayrılmış. Tam satır ve tam saatlerini alıyorlar. ADR-011 |
| Q4d | Personel listesindeki 20 kişi hiçbir Mayıs dosyasında yok | **Mayıs'tan sonra işe girmişler.** Mayıs raporunda satır almıyorlar. ADR-011 |

### Açık

| # | Soru | Bloke ettiği | Neden önemli |
| --- | --- | --- | --- |
| **Q4** | **18 kişinin personel listesinde kaydı ve izin kaydı var ama tek bir kart kaydı yok** (Haziran'da 10, aynı desen, neredeyse hepsi `MACUNKÖY TESİSİ`). Önce tam ay süren 2–3 doğum/rapor iznini ayırın — onların kaydı olmaması doğru. Geri kalanlar 1–2 gün izin almış ve 14–22 iş gününün hiçbirinde kart kaydı yok. **IT'ye sorulacak: Macunköy dosyası o tesisin bütün turnikelerini ve bütün personelini kapsıyor mu?** | Faz 1 onayı | **En önemli açık soru.** Bu kişilerin bütün ayı eksik. Cevap gelmeden hiçbir Macunköy toplamı nihai değil. `DATA-SOURCES.md §6.1 C` |
| Q4a | `DATA-SOURCES.md §6.1`'deki dokuz isim varyantı çiftinin aynı kişiler olduğunu onaylayın, alias tablosuna sabitlenebilsin | Faz 1 | Yanlış bir eşleştirme iki kişinin bordro saatlerini birleştirir |
| Q4c | Sicil `9001` — izin dosyasında olup personel listesinde olmayan tek kişi. `9xxx` aralığı stajyer mi, taşeron mu? | Faz 1 | Personel listesinin tamamen atladığı bir çalışan kategorisi olabilir |
| **Q18** | **Personel listesi `İşe Giriş Tarihi` ve `İşten Çıkış Tarihi` kolonlarıyla yeniden alınabilir mi?** | Faz 1 doğruluğu, Faz 4 güvenliği | "Sonradan girdi / önceden ayrıldı / verisi eksik" ayrımını çıkarımdan olguya çevirir. Ayrıca Faz 4'te ayrılmış birine mail gitmesini engeller. ADR-011 |
| Q5 | Standart gün gerçekten 8 saat 15 dakika net mi (09:00 aralık − 45 dk)? | Faz 2 | Bütün fazla mesai hesabı buna dayanıyor |
| Q6 | Fazla mesai hafta sınırı (Pzt–Paz mı); eksik çalışma hafta içinde fazla mesaiyi mahsup ediyor mu; brüt mü net mi; tam 3 saat ve tam 7,5 saatte davranış ne | Faz 2 | Multinet hakedişi para demek |
| Q7 | Otomatik vardiya atamasında giriş saati pencereleri tam olarak ne; `2. Vardiya` henüz yok — ne zaman devreye girecek? | Faz 2 | Yanlış vardiya ⇒ yanlış beklenen saat |
| Q8 | Resmi tatil çalışmasının ücret mi izin mi olacağına kim nasıl karar veriyor, bu bilgi nereden gelecek? | Faz 2 | Mevcut hiçbir dosyadan çıkarılamıyor |
| Q11 | `ZİYARETÇİ*` / `GEÇİCİ*` / `STJ*` kartları herhangi bir yerde raporlanacak mı, tamamen düşecek mi? Stajyerler çalışıyor ama kart isimli değil numaralı | Faz 1 | Macunköy'ün 1 208 satırının 420'si. Şu an özetten düşüyor |
| Q12 | Raporun tamamını kim alabilir? Departman bazlı bölünmesi gerekiyor mu? | Faz 1 çıktısı | 162 kişinin kişisel verisi tek dosyada |
| Q13 | **`Eğitim İzni` uzaktan çalışma gibi çalışma sayılacak mı?** Mayıs'ta 25 kayıt / 7 kişi, Haziran'da 14 / 8. Kayıtlarda gerçek saat var (`07:30–11:30`, `12:15–16:30`), yani cevap evetse uzaktan çalışmayla birebir aynı şekilde sayılır — varsayım gerekmez | Faz 1 | Q2 ile aynı şekilde bir soru, o "evet" cevaplandı. Şu an devamsızlık sayıldığı için eğitime giden az çalışmış görünüyor |
| Q16 | Mayıs 2026 resmi tatillerini onaylayın: 1 Mayıs, 19 Mayıs ve Kurban Bayramı bloğu (25 Mayıs köprü, 26 Mayıs yarım gün, 27–29 Mayıs) | Faz 2 | Veriden çıkarıldı, İK söylemedi. Tatil ücretini belirliyor |
| Q20 | **37 `Uzaktan Çalışma` kaydı aynı gün bir kart kaydıyla çakışıyor.** Kişi uzaktan çalışma talebini iptal edip geldi mi, yoksa günü ikiye mi böldü? | Faz 1 doğruluğu | Çakışan süre bir kez sayılıyor, yani şişme yok — ama beyan edilen saatler gerçek saatlerin yerine geçiyor olabilir |
| **Q21** | **Kaynak dosyalar her ay Google Drive'a yükleniyor. Hangi entegrasyon?** Elle (bugünkü), Drive for Desktop (sürücü harfi, kod değişikliği yok), Drive API (gözetimsiz, ağ bağımlılığı ekler), ya da mevcut `Y:` ağ sürücüsü. Ayrıca: klasör ay başına ayrı mı? Erişimi kimde? | Faz 4 | 2026-08-03'te **şimdilik elle** kalmasına karar verildi; klasör yapısı ve erişim hâlâ bilinmiyor. README "İleride: Drive otomasyonu" |
