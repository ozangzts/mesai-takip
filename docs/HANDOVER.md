# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-24, commit `2d41f7e`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi**, **beklenen cevapları** ve
> **tuzakları** tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (53 ADR) | [DECISIONS.md](DECISIONS.md) |
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

Faz 1 çalışıyor, **üç ayın üçü de tam**, **441 test geçiyor**.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 26 233:17 |
| Kişi | 171 | 163 | 176 |
| Şüpheli kayıt | 250 | 427 | 436 |

Üçü de `0` koduyla çıkıyor, mutabakat TAMAM, kapsama tam.

> **Masaüstündeki üç ay `format_version 4`, program artık 5 istiyor** (ADR-052 bir etiketi
> değiştirdi). O dosyalar "yeniden üretin" diye reddedilir, yani **Kişiler ekranı üç ayın
> hiçbirini açamaz**. Üç ayı da yeniden üretmek gerekiyor; rakam değişmiyor, Haziran'da
> ölçüldü — 27 166:19 önce ve sonra.

Çalıştırma: `arayuz.cmd` (pencere) ya da `rapor.cmd --ay 2026-07` (komut satırı).

**Pencerede üç ekran var:** Rapor, Kişiler, Takvim. Akış: klasörü seç → tatilleri
işaretle → raporu üret → Kişiler'den listeyi çıkar.

---

## Sıradaki iş

### 1. E-posta gönderimi — veri hazır, kararlar değil

Veri tarafı tamam (ADR-048, ADR-051): Kişiler ekranında `Sorunu olanlar` filtresi ve
hangi notların sayılacağını seçen onay kutuları var; veri dosyası kişi başına **sorunlu
günleri** de taşıyor (tarih, giriş, çıkış, o günün etiketleri).

Kural şu ve artık **testte değil fonksiyonda**: `recipients.days_for()` — işaretli
notlar hem kimi hem hangi günleri seçer. Bir kişiye mail gider ama mesajda yalnızca
işaretli notlara ait günler yazılır.

**`Giriş-çıkış yok` iki notun daha katı hâli** (ADR-053): `Giriş yok` filtresi o günleri
de getirir, çünkü ikisi de olmayan bir günün girişi de yoktur. Yalnızca **seçimde** böyle;
rapor kaydın başına ne geldiğini yazıyor, o gün tek satır. Sonucu: **not sayıları
toplanmaz**, aynı gün iki filtrede. Pencere sayısı `İnceleme Listesi` satır sayısından
büyük, bu tasarım.

**Başlamadan önce üç karar gerekiyor.** Bunlar kararlaştırılmadı, uygulama tarafından
önerildi; kararlaştırılmış kısıt gibi davranılmamalı:

1. Varsayılan davranış **gönderim mi önizleme mi**? (162 kişiye mail geri alınamaz)
2. Elle çıkarılan kişi kayda geçsin mi? ("kime gitmedi, neden")
3. Eksik aydan mail atılsın mı? (`is_complete` bunu ayırt edebiliyor)

Metin yazılırken dikkat: **not bir kayıt hakkında, saatler gün hakkında.**
`Giriş-çıkış yok` satırı, o günü başka bir kayıt kapsadığı için on saat sayılmış bir
günde de durabiliyor — `01.07 · 07:27–18:26 · Giriş-çıkış yok` doğru ama çalışana
çelişki gibi görünür (ADR-051).

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
| 4 | Personel listesi **işe giriş / çıkış tarihi** kolonlarıyla alınabilir mi? | E-posta adımı, ve `Ay büyük ölçüde boş` notunun yanlış pozitifleri (Q18) |

Soru 4'ün cevabı "böyle bir liste yok" olabilir; o durumda alternatif düşünülecek.

### Bloke etmeyen ama cevaplanmalı

- **Uzaktan beyanı olup kart da basanlar** — 3 ayda 10 gün. Beyan mı geçerli, kart mı?
  Şu an ikisi birleştiriliyor ve işaretleniyor.
- **Teknopark neden `09:00–18:00` yazıyor?** Raporun ~%17'si bu satırlardan geliyor.
  "Bordroda ödenmiyor" cevabı yeni bir ADR ve ciddi düşüş demek (Q20a).

---

## Bu turda ne yapıldı (2026-08-24)

**`Giriş-çıkış yok` artık `Giriş yok` ve `Çıkış yok` seçimlerine de giriyor** (ADR-053).
Gerekçe kullanıcının: ikisi de olmayan bir günün girişi de yoktur, etiket bir yüklem ve o
gün onu sağlıyor. İlişki `anomalies.IMPLIES`'te bildirilmiş, tek yerde uygulanıyor
(`with_implied`), ve **yalnızca seçen** her şeyden geçiyor — rapor eden hiçbir şeyden
geçmiyor. Rapor kaydın başına ne geldiğini yazıyor: ikisi de boş bir gün tek satır,
`Giriş-çıkış yok`. Üç satıra açmak, okunmamış iki damgayı okunmuş gibi yazmak olurdu.

Ölçülen etki — **varsayılan seçim hiç değişmedi** (90/103/99 kişi, 171/293/283 gün),
çünkü hepsi zaten işaretliydi. Değişen alt seçimler:

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| `Çıkış yok` | 51 kişi / 127 gün | 80 / 227 | 61 / 221 |
| `Giriş yok` | 41 / 68 | 48 / 100 | 40 / 101 |
| `Giriş-çıkış yok` | 24 / 48 | 34 / 80 | 27 / 78 |

**Reddedilen yol, kaydı için:** etiketleri `Giriş var, çıkış yok` / `Çıkış var, giriş yok`
diye yeniden adlandırıp ayrıklığı görünür kılmak. Kapsayıcılıkla **çelişiyor** —
`Giriş var, çıkış yok` girişi okunmamış günleri döndürmemeli. Yeniden adlandırmamak, şu
anki etiketleri doğru yapan şey. Yan faydası: `format_version` **5'te kaldı**, üç ayı
tekrar üretmek gerekmedi.

**`recipients.days_for()` geldi.** ADR-051'in kuralı bir testin içinde bir satır olarak
duruyordu; testte duran kural, çağıranı yazan kişi tarafından biraz farklı yeniden
yazılır.

**Not sayıları artık toplanmıyor** — aynı gün iki filtrede. Haziran'da 147 + 20 + 80 =
247'ydi, örtüşme yoktu. Pencere daha katı notu **girintiliyor** ki içerme görünsün; etiket
metnine dokunulmuyor, o bir filtre anahtarı. Bir test her sayının o filtrenin döndürdüğü
satır sayısına eşit olduğunu doğruluyor — korkulan hata `Giriş yok (48)` yazıp 15 kişi
vermek.

---

## Bu turda ne yapıldı (2026-08-24, erken)

**Bir notun eşiği yanlıştı.** `Giriş-çıkış tutarsız` açıklaması "16 saati aşıyor" diyordu;
gerçek üst sınır ADR-033'ten beri **20**. Yani rapor, programın uygulamadığı bir kuralı
anlatıyordu on bir haftadır. Hiçbir test görmedi, çünkü o sayı testler için düz metin.

Etiket artık **`Giriş-çıkış tutarsız (>20 saat)`** — `Süre` ailesindeki iki kardeşi gibi
eşiği kendi yazıyor. **Bir test artık her notun yazdığı saat rakamını gerçek config'le
karşılaştırıyor**, ve ikinci bir test "eşik yazan notlar tam olarak bunlar" diyor, yani
sonra eklenen bir not aynı şekilde kayamaz. Eşiği YAML'da değiştirip kelimeyi unutmak da
kırmızı düşüyor — bir sonraki sefer daha muhtemel olan yön bu.

**`İnceleme Listesi`'ne `Ayrıntı` kolonu geldi** (ADR-052). `Ay büyük ölçüde boş` ayın
yüzde kaçını açıklayamadığını zaten hesaplıyordu (`22 iş gününün 2 tanesi açıklanıyor
(%9)`) ama o sayı yalnızca `Şüpheli Kayıtlar`'da duruyordu — kimsenin toplantıya
götürmediği sayfa. `Açıklama` bunu taşıyamaz, o etiketten okunuyor ve her satırda aynı
(ADR-049). Kolon **tek bir kaydı temsil eden satırlarda** dolu; on beş günlük bir satırın
yanına bir günün cümlesini yazmak on dört günü yanlış anlatır. Haziran'da 213 satırın 76'sı
dolu.

**Etiket değiştiği için `format_version` 4 → 5.** Masaüstündeki üç ay yeniden üretilmeli;
rakam değişmiyor.

**Ölçülen bir soru: eksik kayıt notları birbirini kapsıyor mu?** Kapsamıyor. Bir *kayıt*
için `Giriş yok` / `Çıkış yok` / `Giriş-çıkış yok` birbirini dışlıyor (`merge.py` tek dal
seçiyor), ve üç ayın **820 sorunlu gününün hiçbiri** bunlardan birden fazlasını taşımıyor.
Gün seviyesinde yapısal garanti **yok** — aynı gün iki tesisin kaydı olabilir ve
`ProblemDay.problems` bir küme — ama pratikte hiç olmamış. *Kişi* seviyesinde ise çakışma
bol: aynı kişinin bir günü girişsiz, başka günü çıkışsız olabiliyor (Mayıs 12, Haziran 20,
Temmuz 17 kişi). Mail adımında önemi şu: yalnızca `Çıkış yok` işaretlenirse bu kişiler
yine mail alır ama `Giriş yok` günleri mesajda yazmaz.

---

## Bu turda ne yapıldı (2026-08-20 / 21)

Kararların tamamı ADR olarak yazılı; burası yalnızca harita.

**Temmuz tamamlandı.** Teknopark'ın tam ay dosyası geldi; 16 078:44 → **26 233:17**
(fark 10 154:33, ayın yarısı). Guard'ın doğru davrandığı da böylece ölçüldü: ayı "tam"
saymayı reddetti, kapsadığı günlerin rakamlarını reddetmedi.

**Takvim ekranı geldi, sonra sadeleşti** (ADR-042 → ADR-045). Ay ızgarası, bir tıklama
günü tatil yapıyor, kaydetmek `config/takvim-<yıl>.yaml`'a yazıyor. Dosya **tarih
listesi**, başka bir şey değil — adlar, ikinci kategori (resmi/idari) ve `half_days`
silindi. Boş gün tespiti de silindi: tutma gerekçem ölçülünce yanlış çıktı ve kontrol
yalnızca verisi elde olan ayı görebiliyordu.

**Pencerede dört hata düzeltildi**, hepsi kullanırken bulundu:

| Ne | Ölçülen | ADR |
| --- | --- | --- |
| Ekran değiştirince pencere küçülüp alttan kırpılıyordu | Rapor 791 px istiyor, Kişiler 597 | ADR-038 |
| Kalabalık filtreden az kişilik filtreye geçince liste boş görünüyordu | Görünüm içeriğin 972 px altında kalıyor | ADR-038 |
| Sürüklerken satırlar üst üste biniyordu | 171 kişi = **856 widget**, adım başına 58 ms (en kötü 145) → 17,7 ms | ADR-039 |
| Filtre seçtikten sonra teker çalışmıyordu | olay odaktaki widget'a gidiyor, satırlar yutuyordu | ADR-039 |

Teker düzeltilirken **bildirilmeyen daha ciddi bir hata** çıktı: ttk'nın combobox sınıf
bağlantısı her çentikte filtreyi değiştiriyordu (iki çentikte 43 kişi → 3 kişi) ve her
değişim elle yapılan çıkarmaları siliyordu.

**Rapor tek sözlüğe indi** (ADR-049, ADR-050). `Aylık Özet`'in `Not` kolonu elle
yazılmış beş metindi; dördü bir etiketin farklı kelimelerle yazılmış hâli, kalan on bir
etiket o kolona hiç girmiyordu — Temmuz'da 107 kişinin sorunu varken 49 satırda not
vardı, **şimdi 109**. `Günlük Detay`'ın `Etiket` kolonu da içsel kod adları basıyordu
(`kısa-gün`, `çapraz-tesis`); artık kelime basıyor ve bir not etiketiyle aynı şeyi
anlatıyorsa onun **tam** kelimelerini kullanıyor. Aynı sayfanın `Kaynak` kolonu da ilk
giriş ile son çıkış farklı tesisteyse `Macunköy → Teknopark` yazıyor.

**Rapor artık hiçbir departmanı adlandırmıyor** (ADR-046, ADR-047) ve o satırların çoğu
**doğru da değildi** — hiç yapılmamış bir talebi ve hiç sorulmamış bir onayı yazıyordu.
3. sayfanın adı `Sorulacaklar` yerine **`İnceleme Listesi`**.

**`Sorunu olanlar` filtresi ve sayılacak notlar** (ADR-048): yöneticinin saydığı üç
kategori varsayılan, üç ayda 90 / 103 / 99 kişi. **Veri dosyası artık sorunlu günleri de
taşıyor** (ADR-051, sürüm 4) — mail adımı için.

**Kapanan açık sorular:** `Eğitim İzni` izin sayılıyor ve çalışma sayılan izin listesi
tek girdiyle kapalı (ADR-037); tatil listesi sorulacak bir şey değil, kullanan kişi
işaretliyor (Q16, ADR-045); Temmuz dosyası tam ay olarak geldi (Q23'ün bu kısmı).

---

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
  yeniden adlandırmak snapshot için kırıcı değişikliktir, düzeltme değil (ADR-027,
  ADR-049, ADR-050).
- İçsel kod adları rapora girmez; `anomalies.TAG_TEXT` üzerinden kelimeye çevrilir. Yeni
  bir `tags.add(...)` eklerken karşılığını da ekle — bir test `merge.py`'yi tarıyor.

### Config ve dosyalar

- Bordroyu etkileyen üç config anahtarı **zorunlu**: `daily_hours`, `break.deduct`,
  `remote_replaces_attendance`. Eksikse program durur.
- **`tests/conftest.py` fixture'ı gerçek config'den sapabiliyor** ve birkaç kez saptı.
  Yeni bir config anahtarı eklerken fixture'a da ekle — yoksa bütün test paketi,
  kimsenin çalıştırmadığı bir kurala karşı geçmeye devam eder.
- Snapshot `format_version` **5**. Eski dosyalar "yeniden üret" diye reddediliyor. Bir
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
- Not paneli en kötü durumda (15 etiket) 258 px; liste 189 px'e iner, 8 satır + scrollbar
  kalır, alt butonlar yerinde. Ölçüldü, taşma yok — ama panel büyürse liste kısalır.

### Genel

- **Bir kontrol, kanıtının olduğu yere ait.** Aynı hesap raporda faydalı, pencerede tuhaf
  durabiliyor (ADR-044).
- **Gerekçe ölçülmeden yazılmaz.** "15 Temmuz'u bir ay önce yakalardı" iki ADR'ye girmiş
  ve tekrarlanmıştı; git log'daki tarihlere bakan olmadığı için yanlış olduğu fark
  edilmedi (ADR-045).
- Varsayılanlar, kime ulaşılacağını belirleyen listelerde **fazladan bir kişi** yönünde
  hata yapar. Fazlalık düzeltilir, eksik sessizliktir (ADR-017, ADR-030, ADR-048).
