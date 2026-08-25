# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-25, commit `9d731d9`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi**, **beklenen cevapları** ve
> **tuzakları** tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (64 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | **Kurallar, sade Türkçe — birine gösterilebilir** | [KURALLAR.md](KURALLAR.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Raporun sayfa sayfa şartnamesi | [OUTPUT-SPEC.md](OUTPUT-SPEC.md) |
> | Fazlar, açık sorular | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, **üç ayın üçü de tam**, **482 test geçiyor**.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 26 233:17 |
| Kişi | 171 | 163 | 176 |
| Şüpheli kayıt | 399 | 721 | 723 |
| `Sorunu olanlar` | 75 | 73 | 85 |

Üçü de `0` koduyla çıkıyor, mutabakat TAMAM, kapsama tam. Masaüstündeki üç ayın raporu ve
veri dosyası **`format_version` 9** ile güncel; Haziran'ı yeniden üretip karşılaştırdım,
üretim zamanı dışında birebir aynı.

> Şüpheli kayıt 250/427/436'dan buraya çıktı ve **hiçbir saat değişmedi**. Sebebi
> ADR-060/061: kaydı hiç olmayan günler de artık işaretleniyor. O günlerde sayılacak bir
> şey yoktu, yalnızca hiç görünmüyorlardı. Sayıyı CLI çıktısından al — raporun
> `Şüpheli Kayıtlar` sayfasını satır sayarak ölçmek 3 satırlık alt notu da katıyor.

Çalıştırma: `arayuz.cmd` (pencere) ya da `rapor.cmd --ay 2026-07` (komut satırı).

**Pencerede üç ekran var:** Rapor, Kişiler, Takvim. Akış: klasörü seç → tatilleri
işaretle → raporu üret → Kişiler'den listeyi çıkar.

**Kişiler ekranı iki panelli** (ADR-064): solda kişi listesi, sağda seçilen kişinin
sorunlu günleri gün gün, her biri seçilebilir. Adın solundaki kareye tıklamak kişiyi
listeden çıkarır; adın kendisine tıklamak günlerini açar.

---

## Sıradaki iş

### 1. E-posta gönderimi — veri hazır, kararlar değil

Veri tarafı tamam (ADR-048, ADR-051): Kişiler ekranında `Sorunu olanlar` filtresi ve
hangi notların sayılacağını seçen onay kutuları var; veri dosyası kişi başına **sorunlu
günleri** de taşıyor (tarih, giriş, çıkış, o günün etiketleri).

**Kimin mail alacağı kararlı** — `recipients.matching()` ve `recipients.days_for()`,
ikisi de tek kural altında (ADR-059, ADR-061):

> Bir gün listeye girer **ancak ve ancak** o gün hiçbir yerde sayılmamışsa ve izin
> kapsamıyorsa. Başka bir kayıttan sayılmışsa sorun yok; girişi bir tesisten çıkışı
> diğerinden olsa da sorun yok (birleşim günü zaten saymış); uzaktan çalışmaysa saate
> dönüştüğü için sorun yok.

İşaretli notlar hem **kimi** hem **hangi günleri** seçer, ve `Hem giriş hem çıkış yok`
günleri `Giriş yok` / `Çıkış yok` seçimlerine de girer (ADR-053) — ikisi de olmayan bir
günün girişi de yoktur. Yalnızca **seçimde** böyle; rapor kaydın başına ne geldiğini
yazıyor, o gün tek satır. Sonucu: **not sayıları toplanmaz**, aynı gün iki filtrede.

Varsayılan ayarlarla mail listesi:

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Kişi | 75 | 73 | 85 |
| Mesaja girecek gün | 210 | 379 | 389 |
| **Adresi olmayan** | 8 | 8 | 8 |

Adreslerin tamamı `deico.com.tr`. Adresi olmayanlar **düşürülmez, bildirilir**
(`without_email`) — 30 kişilik bir listenin sessizce 22 olması kaçınılması gereken hata.

**Başlamadan önce üç karar gerekiyor.** Bunlar kararlaştırılmadı, uygulama tarafından
önerildi; kararlaştırılmış kısıt gibi davranılmamalı:

1. Varsayılan davranış **gönderim mi önizleme mi**? (162 kişiye mail geri alınamaz)
2. Elle çıkarılan kişi kayda geçsin mi? ("kime gitmedi, neden")
3. Eksik aydan mail atılsın mı? (`is_complete` bunu ayırt edebiliyor)

Metin yazılırken dikkat: **not bir kayıt hakkında, saatler gün hakkında.** Mail listesi
artık yalnızca kaybı olan günleri taşıdığı için bu tuzak büyük ölçüde kapandı, ama günün
kendi etiketleri hâlâ birden fazla olabiliyor: `Çıkış yok` işaretliyken seçilen bir gün
ayrıca `Günlük süre çok kısa` da taşıyabilir (Temmuz'da 2 gün). Mesajda **yalnızca
işaretli notun** yazılması gerekiyor, yoksa sorulmayan bir şey söylenmiş olur.

### 2. İstisna listesi (4. dosya) — mekanizma hazır

"Bu kişilere mail atılmayacak" diye bir Excel bekleniyor.
`recipients.selected(snapshot, filtre, çıkarılanlar, etiketler)` zaten bir isim kümesi
alıp çıkarıyor.

Eklenecek: dosyayı okuyan fonksiyon (**`mail/recipients.py` içine, ekrana değil**), bir
onay kutusu, ve kalıcı istisna ile o oturumdaki elle çıkarmayı **ayrı tutmak** — biri
kural, öteki tercih.

> **Asıl risk arayüzde değil, isim eşleştirmede.** Haziran'da ölçüldü: 163 kişinin
> **126'sında sicil no var, 37'sinde yok**. İstisna listesi bir ismi farklı yazarsa **o
> kişi sessizce mail alır** — kaçınılması gereken hata türü. Liste eline geçtiğinde
> **ilk bakılacak şey: içinde sicil no var mı.** Yoksa eşleşmeyen her satır için uyarı
> verilecek; program tahmin etmez, söyler (AGENTS §2.1).

### 3. Tek `.exe` paketi (PyInstaller)

Asıl uğraş paketleme değil, **Python'un kurulu olmadığı bir makinede test etmek.**

- `config/` exe'nin içine gömülmemeli — kural değişikliği YAML düzenlemesi ve
  `personel.yaml` gerçek isim yazımlarını tutuyor.
- **`config/` yazılabilir olmalı.** Takvim ekranı `config/takvim-<yıl>.yaml`'a yazıyor
  (ADR-042), yani ADR-024'ün "programın kendi dizini yazılabilir olmak zorunda değil"
  ilkesi config klasörü için artık geçerli değil. Ölçüldü: salt-okunur bir dosyada kayıt
  sessizce başarısız olmuyor, ekranda kırmızıyla ne yapılacağını yazıyor ve dosya
  bozulmuyor. Yani hata durumu düzgün, ama exe + `config/` **Masaüstü ya da Belgeler
  gibi bir yere** konmalı — `Program Files`'a değil.
- İki giriş noktası da kontrol edilmeli: `arayuz.cmd`'nin `-m mesai.gui` çağrısı
  (`gui/__main__.py`) ve `pyproject.toml`'un `mesai.gui:main` girdisi.

---

## Cevap bekleyen sorular

Öncelik sırasıyla. Kimin cevaplayacağını program belirlemiyor (ADR-047).

| # | Soru | Neyi bloke ediyor |
| --- | --- | --- |
| 1 | **Macunköy dosyası o tesisin bütün turnikelerini kapsıyor mu?** Kart kaydı hiç olmayanların neredeyse hepsi Macunköy | Faz 1 onayı — **en kritik** (Q4) |
| 2 | **Dosyalar her ay ayın kaçında alınacak?** Ayın 20'sinde alınan bir dosya yine yarım olur; Temmuz'da bir kez yaşandı | Bir sonraki ay (Q23) |
| 3 | Dokuz isim eşleştirmesinin doğrulanması — `Kontrol` sayfası bölüm 7 | Yanlışsa iki kişinin bordro saatleri birleşir (Q4a) |
| 4 | Personel listesi **işe giriş / çıkış tarihi** kolonlarıyla alınabilir mi? | Ay içinde giren/ayrılanın `Hem giriş hem çıkış yok` yanlış pozitifleri — şu an elle çıkarılıyor (Q18) |

Soru 4'ün cevabı "böyle bir liste yok" olabilir; o durumda alternatif düşünülecek.

### Bloke etmeyen ama cevaplanmalı

- **Uzaktan beyanı olup kart da basanlar** — 3 ayda 10 gün. Beyan mı geçerli, kart mı?
  Şu an ikisi birleştiriliyor ve işaretleniyor.
- **Teknopark neden `09:00–18:00` yazıyor?** Raporun ~%17'si bu satırlardan geliyor.
  "Bordroda ödenmiyor" cevabı yeni bir ADR ve ciddi düşüş demek (Q20a).

---

## Son değişiklikler

Bu bölüm harita, kayıt değil. **Gerekçeler ADR'lerde** — burada yalnızca hangi ADR'nin
neye dokunduğu var, çünkü bir öncekinin yerini alan kararlar var ve sırayla okunmaları
gerekiyor.

| ADR | Ne | Etkisi |
| --- | --- | --- |
| 052 | Notun yazdığı eşik config'le aynı olmak zorunda; `Giriş-çıkış tutarsız (>20 saat)` | Açıklama 11 haftadır 16 diyordu, gerçek sınır 20. Bir test artık her notun yazdığı saati config'le karşılaştırıyor |
| 052 | `İnceleme Listesi`'ne `Ayrıntı` kolonu | Kaydın kendi kelimeleri, tek kaydı temsil eden satırlarda |
| 053 | `Hem giriş hem çıkış yok`, `Giriş yok` ve `Çıkış yok` seçimlerine de girer | Yalnızca **seçimde**; rapor kaydın başına ne geldiğini yazar |
| 054 | Etiket adı bağlaç oldu: `Giriş-çıkış yok` → `Hem giriş hem çıkış yok` | Birleşik isim gibi okunuyordu |
| 055 | `Etki` kolonu kayıt hakkında, gün hakkında değil | 52/99/90 satırda "0 saat sayıldı" yazıyordu, gün 8+ saat sayılmıştı |
| 055 | `ProblemDay.covered_by` — o günü kapatan izin | Yıllık izindeki adama "neredeydin" sorulmasın |
| 056 | Not paneli maliyete göre bölündü: `Günü sayılmayan` / `Günü sayılan` | Kayıp dağılımı etiketlerin verdiği izlenimin tersiydi |
| 057 | Hiçbir tesiste kaydı olmayan iş günü → çıkış kodu 5 | ADR-020 yalnızca dönemin **sonundaki** boşluğu görüyordu |
| 059 | **Filtre yalnızca bekleyen günleri seçer**, etiket başka bir şey yazmaz | ADR-055'in kuralı yanlış katmandaydı (mail adımına seçenek olarak) |
| 060 | Kaydı hiç olmayan gün de işaretlenir | Dosyada satır yoksa hiçbir anomali üretilmiyordu; 11 kişi notsuzdu |
| 061 | O işaretlemeye **hiçbir koşul yok** | İlk-kayıt çıpası ayda 45–60 günü saklıyordu |
| 062 | `Ay büyük ölçüde boş` kaldırıldı | Artık gereksiz: o kişilerin hepsi günlük notu taşıyor, seçim 0 kişi değişiyor |
| 063 | `Günlük Detay` herkesin her iş gününü tutuyor | Kaydı olmayan gün hiç satır almıyordu; Temmuz'da 1 141 kişi-günü ve 31 kişi sayfada yoktu |
| 064 | Kişiler ekranına gün paneli, günler seçilebilir | Hangi günler olduğu yalnızca raporda vardı; seçim için iki pencere arasında gidip gelmek gerekiyordu |

**Sırayla okunması gereken zincir:** 055 kuralı kurdu → 059 onu doğru katmana taşıdı →
060 kapsamı genişletti → 061 koşulları kaldırdı → 062 gereksizleşen notu sildi.

**Daha önce, 2026-08-20/21:** Temmuz tam ay dosyasıyla tamamlandı (16 078:44 →
26 233:17), Takvim ekranı geldi ve sadeleşti (042 → 045), pencerede dört hata düzeltildi
(038, 039), rapor tek not sözlüğüne indi (049, 050), rapor hiçbir departmanı adlandırmaz
oldu (046, 047).


## Gözden kaçmaması gerekenler

Buradaki her madde bir kez ısırdı.

### Veri ve gizlilik

- `data/` ve `gonderim-*.json` **kişisel veri**, git'e girmez. Veri dosyası artık
  kullanıcının seçtiği herhangi bir yere (Masaüstü dahil) düşebiliyor, o yüzden asıl
  koruma klasör kuralı değil **dosya adı kuralı**.
- Ekran görüntüsü alırken **tüm ekranı değil pencereyi** yakala (`PrintWindow`), ve
  Kişiler ekranını **sentetik veriyle** sür — gerçek veriyle alınan bir görüntü çalışan
  adlarını ve e-posta adreslerini gösterir.
- Commit öncesi sızıntı kontrolü: gerçek listeyi yükle, bütün isim varyantlarını topla,
  **eklenen satırlarda** tam kelime olarak ara. Türkçe sözcükler soyadlarla çakışıyor
  (`alır`, `uzun`, `örnek`), o yüzden alt dizgi araması gürültü verir.

### Uygulamanın dili

- **Hiçbir şey kişi, ekip ya da departman adlandırmaz** ve hiçbir yerde "onay
  bekleniyor" demez (ADR-046, ADR-047). Kendi aramızda — `docs/`, ADR, commit mesajı —
  kimin ne dediğini yazmak doğru ve gerekli; programın yazdığı yerde değil. Testle
  sabit: tam kelime eşleşmesi (`İK`, `EKSİK`'in içinde geçiyor) ve personel listesinden
  gelen hücreler atlanıyor (gerçek departman adları o kelimeyi taşıyor).
- **Bir olgunun tek bir yazımı var.** Not etiketleri filtrede, `Not` kolonunda,
  `İnceleme Listesi`'nde ve `Etiket` kolonunda aynı kelimelerle görünür. Bir etiketi
  yeniden adlandırmak **ya da kaldırmak** snapshot için kırıcı değişikliktir, düzeltme
  değil (ADR-027, ADR-049, ADR-050, ADR-054, ADR-062): eski adı taşıyan kayıtlı bir filtre
  ya da istisna listesi sessizce kimseyi tutmaz.
- **Etiketin yanına açıklayıcı sayı yazma.** Denendi ve kaldırıldı (ADR-058 → ADR-059):
  `27 kişi · 5/78 gün sayılmadı` hesap hatası gibi okunuyordu, ve filtre düzeltildikten
  sonra uzlaştırılacak ikinci bir sayı kalmadı. Panel `{not} ({kişi})` yazar.
- İçsel kod adları rapora girmez; `anomalies.TAG_TEXT` üzerinden kelimeye çevrilir. Yeni
  bir `tags.add(...)` eklerken karşılığını da ekle — bir test `merge.py`'yi tarıyor.

### Config ve dosyalar

- Bordroyu etkileyen üç config anahtarı **zorunlu**: `daily_hours`, `break.deduct`,
  `remote_replaces_attendance`. Eksikse program durur.
- **`tests/conftest.py` fixture'ı gerçek config'den sapabiliyor** ve birkaç kez saptı.
  Yeni bir config anahtarı eklerken fixture'a da ekle — yoksa bütün test paketi,
  kimsenin çalıştırmadığı bir kurala karşı geçmeye devam eder.
- Snapshot `format_version` **9**. Eski dosyalar "yeniden üret" diye reddediliyor. Bir
  **etiketi yeniden adlandırmak** bu sürümü yükseltir (ADR-027, ADR-052): eski yazımla
  yazılmış bir filtre ya da istisna listesi yeni yazımda **sessizce kimseyi** tutmaz.
- **`arayuz-ayarlari.json` `gui/settings.py` üzerinden yazılır** — oku, değiştir, yaz.
  Eskiden rapor ekranı kendi anahtarlarını bütün dosyanın üzerine yazıyordu; bir şey
  hatırlayan ikinci ekran birincisinin ayarını sessizce silecekti. Temizlenen değer
  açıkça `null` yazılıyor, çünkü anahtarı hiç yazmamak eski değeri dosyada bırakır.
- Takvim dosyası **satır satır** düzenlenir, `yaml.safe_dump` ile değil: dosya nelerin
  ona dayandığını anlatan yorumları taşıyor ve o not bir kez zaten yanlış çıktı. En sıkı
  test: gerçek takvimi kendi içeriğiyle yeniden yazmak **birebir aynı** dosyayı vermeli.

### Pencere

- **Uzun listeler `Treeview` ile.** Frame içinde label'larla çizmek 171 kişide 856
  widget demek ve tk her kaydırma adımında hepsini yeniden konumlandırıyor (ADR-039).
  Bilerek verilen tavizler: hücre bazlı renk, kolon bazlı yazı tipi, yerel onay kutusu.
- **`unbind_all("<MouseWheel>")`** yalnızca bu pencerede başka hiçbir şey o olayı `all`
  etiketine bağlamadığı için güvenli. Bağlayan bir şey eklenirse bu değişmeli.
- **Test pencereleri ekran dışına park edilir** (`+6000+6000`) — yeni bir fixture
  eklerken `_tk_root` kullan. Sadece konum; buradaki geometri kontrolleri boyut hakkında
  ve `wm geometry WxH` konuma dokunmuyor. `withdraw()` değil: haritalanmamış pencere
  boyutunu 1x1 bildirir ve testler bir şey test etmez olur.
- **GUI testleri "ekran yok" diye sessizce atlanmaz.** Ekranın varlığı bir kez ölçülür,
  sonrasında pencere kurulamazsa test kırmızı düşer. Sessizce atlanan test koruma
  sağlamaz.
- Kapatırken kaydedilmemiş iş varsa sorulur: bir ekran `unsaved()` metoduyla katılır,
  kabuk başka bir şey bilmez (ADR-042).
- **Not paneli iki kolon ve genişliği testle sabit**: en geniş kutu 243 px, kolon 336 px,
  93 px pay (ADR-058'in ölçümü, etiketler sadeleştikten sonra da geçerli). Panel daha önce
  dört kolonda kırpılmıştı. Bir etiket bunu aşarsa paneli genişlet ya da etiketi kısalt —
  kırpma yapma, okuyan hangi notu işaretlediğini göremez.
- **Pencere 880×620'den 2560×1400'e ve maximize'da ölçüldü** (ADR-059 turu, 11 test): iki
  ekran da pencereyi dolduruyor, liste pencereyle büyüyor, ekran değiştirmek maximize'ı
  bozmuyor. `_fit` yalnızca büyütür, asla küçültmez (ADR-038).

### Rapor ile filtre aynı soruyu sormaz

- **Rapor kaydın başına ne geldiğini yazar; filtre kime ulaşılacağını seçer.** Bu yüzden
  pencere sayıları `İnceleme Listesi` satır sayılarından farklı olabilir ve bu tutarsızlık
  değil (ADR-053, ADR-055). Rapordan bir satır **hiç düşmez** — her girdi satırı ya bir
  toplamda ya anomali listesinde olmak zorunda (AGENTS §2.2).
- **`Etki` kolonu kayıt hakkındadır.** Şiddet düzeyi kaydın özelliği; "bu gün 0 saat
  sayıldı" ise gün hakkında bir iddia. İkisi 52/99/90 satırda çelişiyordu ve rapor yanlış
  söylüyordu (ADR-055). Yeni bir şiddet metni yazarken hangisi hakkında konuştuğuna bak.

### Genel

- **Bir kontrol, kanıtının olduğu yere ait.** Aynı hesap raporda faydalı, pencerede tuhaf
  durabiliyor (ADR-044).
- **Gerekçe ölçülmeden yazılmaz.** "15 Temmuz'u bir ay önce yakalardı" iki ADR'ye girmiş
  ve tekrarlanmıştı; git log'daki tarihlere bakan olmadığı için yanlış olduğu fark
  edilmedi (ADR-045).
- Varsayılanlar, kime ulaşılacağını belirleyen listelerde **fazladan bir kişi** yönünde
  hata yapar. Fazlalık düzeltilir, eksik sessizliktir (ADR-017, ADR-048, ADR-061). Bu
  yüzden `Hem giriş hem çıkış yok` ay içinde işe girmiş olabilecekleri de listeler:
  yanlışsa bedeli listeden bir elle çıkarma, atlanırsa bedeli o kişinin saatleri.
