# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-21, commit `bb38a74`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi** ve **beklenen cevapları**
> tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (48 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | **Kurallar, sade Türkçe — yöneticiye gösterilebilir** | [KURALLAR.md](KURALLAR.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Fazlar, açık sorular | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, **üç ayın üçü de tam**, **412 test geçiyor**.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 26 233:17 |
| Kişi | 171 | 163 | 176 |
| Şüpheli kayıt | 250 | 427 | 438 |

**Temmuz artık eksik değil.** Teknopark'ın tam ay dosyası geldi
(`Teknopark - Temmuz.xlsx`, ayın 1–31'i) ve rapor `0` koduyla çıkıyor: iki kaynak da
23 iş gününün 23'ünü kapsıyor, mutabakat TAMAM (Σ kişi = Σ günlük ölçülen =
26 233:17), Teknopark'ın 2 394 satırının 2 394'ü kayda dönüşüyor. Eksik hâlinde
16 078:44 okunuyordu — **fark 10 154:33**, yani ayın yarısı. Q23 kapandı.

Çalıştırma: `arayuz.cmd` (pencere) veya `rapor.cmd --ay 2026-07` (komut satırı).

**Mayıs ve Haziran yeni kurallarla yeniden üretildi** (ADR-030, ADR-032, ADR-033
Haziran'ın toplamını 27 119:24'ten 27 166:19'a çıkarmıştı). Pencereden üretilen
kopyalar Masaüstünde, `snapshot format_version 3`; doğrulandı — aynı ay yeniden
üretildiğinde `gonderim-*.json` üretim saati dışında birebir aynı çıkıyor. Temmuz
bilerek yeniden üretilmedi, Teknopark dosyasının tam ay hâli bekleniyor.

---

## Sıradaki iş

### 0. Yeni: `Sorunu olanlar` filtresi ve sayılacak notlar (ADR-048)

Kişiler ekranında artık `Sorunu olanlar` var; altındaki onay kutularından hangi notların
"sorunlu" saydığı işaretleniyor, seçim hatırlanıyor. Varsayılan, yöneticinin saydığı üç
kategori — üç gerçek ayda 90 / 103 / 99 kişi. `Tesis birleştirme` ve
`Uzaktan + kart kaydı` başlangıçta işaretsiz: ikisi de zaten çözülmüş bir durumu
anlatıyor.

**Saklanan şey KAPALI olan notlar**, açık olanlar değil — böylece `anomalies.py`'ye
sonradan eklenen bir not kendiliğinden sayılır. Kime ulaşılacağını belirleyen bir
listede fazladan bir kişi düzeltilir, eksik bir kişi sessizlik.

Mail adımı bundan bağımsız; bu sadece listenin kim olduğunu belirliyor.

### 1. İstisna listesi (4. dosya) — mekanizma hazır

Proje sahibi "bu kişilere mail atılmayacak" diye bir Excel bekliyor.
`recipients.selected(snapshot, filtre, çıkarılanlar)` zaten bir isim kümesi alıp
çıkarıyor.

Eklenecek olan: dosyayı okuyan fonksiyon (**`mail/recipients.py` içine, ekrana
değil**), bir onay kutusu (`☑ İstisna listesindekileri çıkar`), ve kalıcı istisna ile o
oturumdaki elle çıkarmayı **ayrı tutmak** — biri kural, öteki tercih.

> **Asıl risk arayüzde değil, isim eşleştirmede.** Haziran'da ölçüldü: 163 kişinin
> **126'sında sicil no var, 37'sinde yok**. İstisna listesi bir ismi farklı yazarsa
> **o kişi sessizce mail alır** — kaçınılması gereken hata türü.
>
> Liste eline geçtiğinde **ilk bakılacak şey: içinde sicil no var mı.** Varsa
> eşleştirme güvenli. Yoksa isim eşleştirmesi kurulacak ve **eşleşmeyen her satır için
> uyarı verilecek** — program tahmin etmez, söyler (AGENTS §2.1).

### 2. Tek `.exe` paketi (PyInstaller)

Asıl uğraş paketleme değil, **Python'un kurulu olmadığı bir makinede test etmek.**

- `config/` exe'nin içine gömülmemeli — kural değişikliği YAML düzenlemesi ve
  `personel.yaml` gerçek isim yazımlarını tutuyor.
- **Yeni kısıt: `config/` artık YAZILABİLİR olmalı.** Takvim ekranı
  `config/takvim-<yıl>.yaml`'a yazıyor (ADR-042), yani ADR-024'ün "program kendi
  dizininin yazılabilir olmasını gerektirmiyor" ilkesi config klasörü için artık
  geçerli değil. Exe `Program Files` gibi bir yere kurulursa takvim kaydedilemez.
  Ölçüldü: dosya salt-okunur yapıldığında kayıt sessizce başarısız olmuyor —
  ekranda kırmızıyla "bu klasöre yazma izni yok, programı ve config klasörünü
  yazılabilir bir yere taşıyın" yazıyor ve dosya bozulmuyor. Yani hata durumu
  düzgün, ama paketlerken exe + `config/` **Masaüstü ya da Belgeler gibi bir yere**
  konmalı.
- İki giriş noktası da kontrol edilmeli: `arayuz.cmd`'nin `-m mesai.gui` çağrısı
  (`gui/__main__.py`) ve `pyproject.toml`'un `mesai.gui:main` girdisi.
- ADR-024 bunu kolaylaştırdı: koşu artık programın kendi dizininin yazılabilir
  olmasını gerektirmiyor. ADR-035 de personel listesinin exe yanında olmasını
  gerektirmiyor.

### 3. E-posta gönderimi — başlamamalı

Aşağıdaki cevaplar gelmeden ve şu üç karar verilmeden başlanmamalı:

1. Varsayılan davranış **gönderim mi önizleme mi**? (162 kişiye mail geri alınamaz)
2. Elle çıkarılan kişi kayda geçsin mi? ("kime gitmedi, neden")
3. Eksik snapshot'tan mail atılsın mı? (`is_complete` bunu ayırt edebiliyor)

Bunlar **kararlaştırılmadı**, uygulama tarafından önerildi. Kararlaştırılmış kısıt gibi
davranılmamalı.

---

## Cevap bekleyen sorular

Proje sahibi soracak. Öncelik sırasıyla:

| # | Soru | Neyi bloke ediyor |
| --- | --- | --- |
| 1 | **Dosyalar her ay ayın kaçında alınacak?** Temmuz'un tam ay dosyası geldi, ama ayın 20'sinde alınan bir dosya yine yarım olur | Bir sonraki ay (Q23) |
| 2 | **Macunköy dosyası o tesisin bütün turnikelerini kapsıyor mu?** Kart kaydı hiç olmayanların neredeyse hepsi Macunköy | Faz 1 onayı — **en kritik** (Q4) |
| 3 | Dokuz isim eşleştirmesinin onayı — `Kontrol` sayfası bölüm 7 | Yanlışsa iki kişinin bordro saatleri birleşir (Q4a) |
| 4 | Mayıs'ın 7 resmi tatili doğru mu (veriden çıkarıldı) | Tatil çalışması ücreti (Q16) |
| 5 | Personel listesi **işe giriş / çıkış tarihi** kolonlarıyla alınabilir mi? | E-posta adımı, ve `Ay büyük ölçüde boş` notunun yanlış pozitifleri (Q18) |

Soru 5'in cevabı "böyle bir liste yok" olabilir; o durumda alternatif düşünülecek.

### Bloke etmeyen ama cevaplanmalı

- **Uzaktan beyanı olup kart da basanlar** — 3 ayda 10 gün. Beyan mı geçerli, kart mı?
  Şu an ikisi birleştiriliyor ve işaretleniyor.
- **Teknopark neden `09:00–18:00` yazıyor?** Raporun ~%17'si bu satırlardan geliyor.
  "Bordroda ödenmiyor" cevabı yeni bir ADR ve ciddi düşüş demek. (Q20a)

---

## Bu turda ne yapıldı (2026-08-20)

**Takvim sadeleşti: tarih listesi, başka bir şey yok** (ADR-045). Proje sahibinin iki
itirazı da haklı çıktı:

- **Boş gün kontrolü silindi.** Tutma gerekçem "15 Temmuz'u bir ay önce yakalardı"
  idi ve **yanlıştı** — Temmuz ilk kez 18–19 Ağustos'ta üretildi, eksik 20 Ağustos'ta
  fark edildi, yani kontrol bir gün kazandırırdı. Ayrıca kontrol sadece verisi elde
  olan bir ayı görebiliyor; Eylül hakkında hiçbir şey söyleyemez ve konuştuğunda o
  ayın raporu çoktan üretilmiş olur.
- **Tarihlerin adı silindi.** Programda hiçbir şey adı okumuyordu; İK'nın onaylaması
  için duruyorlardı, ama bu İK'ya sorulacak bir şey değil (Q16 kapandı).

Giden: `rules/takvim.py`, `HolidayCandidate`, config eşiği, `Kontrol` bölümü, 12 test,
ve `half_days` — o da `Calendar`'a okunup hiçbir yerde kullanılmıyordu, yani var olmayan
bir kuralı ima ediyordu. Takvim dosyası 40 satırdan 12 satıra indi.

**Kaybedilen:** bir tatil hiç işaretlenmezse artık kimse fark etmiyor. O gün beklenen
iş günü sayılır ve devamsız olmayan biri işaretlenebilir. Bu, işaretlemeyi yapan
kişinin tercihi.

**Tatil takvimi düzeltildi** (ADR-040). Üç bulgu, tek sorudan çıktı — "tatilleri neye
göre belirledin":

| Ne | Ölçülen |
| --- | --- |
| Temmuz raporu Mayıs'ın tatillerini listeliyordu | `Kontrol` sayfası takvimin tamamını yazıyordu; artık sadece o ayı |
| **15 Temmuz takvimde yoktu** | Sabit tarihli resmi tatil. Veri tek başına gösteriyor: hafta içi ortanca 130 kişi, o gün **7 kişi (%5)** |
| Takvim dosyasının kendi yorumu bayattı | "Hiçbir saat hesabı buna dayanmıyor" yazıyordu; oysa kapsama guard'ının ve `Ay büyük ölçüde boş` notunun paydası, ve çok günlü uzaktan çalışma bölmesi buna dayanıyor |

Sabit tarihli resmi tatillerin **yılın tamamı** yazıldı ve yedisi testle sabitlendi —
15 Temmuz'un unutulma sebebi, takvimin sadece çalıştırılmış aylar için doldurulmasıydı.
Üç ayda **kimsenin saati değişmedi**; Temmuz'da iki yanlış "ay boş" notu kalktı ve
beklenen iş günü 23 → 22 oldu. O gün çalışan 7 kişi her dakikasını korudu.

**Kişiler listesi `ttk.Treeview` oldu ve teker düzeldi** (ADR-039). İki şikâyet,
aynı jestin iki ucu:

| Ne | Ölçülen | Sonrası |
| --- | --- | --- |
| Sürüklerken satırlar üst üste biniyordu | 171 kişi = **856 widget**, adım başına 58 ms (en kötü 145) | adım başına 17,7 ms (en kötü 19), listeyi çizme 1065 → 20 ms |
| Filtre seçtikten sonra teker çalışmıyordu | olay odaktaki widget'a gidiyor, satırlar da onu yutuyordu | teker üç yerde yakalanıyor, çentik başına 3 satır |

Düzeltirken **bildirilmeyen daha ciddi bir hata** çıktı: ttk'nın combobox sınıf
bağlantısı her çentikte filtreyi değiştiriyordu — iki çentikte `Herkes` (43 kişi) →
`Çıkış yok` (3 kişi) — ve her değişim elle yapılan çıkarmaları siliyordu. Kime mail
gideceğini belirleyen ekranda, hiçbir şeyi hataya benzemeyen bir sessiz yeniden seçim.
Artık teker filtreyi değiştirmiyor.

**Temmuz tamamlandı.** Teknopark'ın tam ay dosyası geldi; rapor artık `0` koduyla
çıkıyor, 26 233:17 / 176 kişi. Eksik hâlinden farkı **10 154:33**. Guard'ın doğru
davrandığı da böylece ölçüldü: ayı "tam" saymayı reddetti, ama kapsadığı günlerin
rakamlarını reddetmedi. Dosya adı yine değişmiş (`Teknopark - Temmuz.xlsx`), glob
sayesinde kod değişmedi.

**`Kontrol` sayfasında iki bölüm de "9." numarasını taşıyordu** — 10. olması gereken
"Bu raporun kapsamadıkları". AGENTS.md de alias kontrolünü "bölüm 6" diye gösteriyordu,
doğrusu 7. Numaraların tekrarsız ve sıralı olduğunu doğrulayan bir test eklendi;
numaralar bu sayfaya yapılan bütün referansların dayanağı ve hiçbir şey onları geri
okumuyordu.

**Pencerede iki hata düzeltildi** — ikisi de proje sahibinin kullanırken bulduğu,
ikisi de pencerenin tuttuğu durumla ilgili, o yüzden hiçbiri "geometri test etmeyiz"
diyen test paketine yakalanmamıştı (ADR-038):

| Ne | Ölçülen | Düzeltme |
| --- | --- | --- |
| Ekran değiştirince pencere küçülüp alttan kırpılıyordu | Rapor 791 px istiyor, Kişiler 597; tk pencereyi istenen boya küçültüyor | Pencere gösterilen ekrana göre **büyür, asla küçülmez** |
| Kalabalık filtreden az kişilik filtreye geçince liste boş görünüyordu | Görünüm içeriğin **972 px** altında kalıyor, `scrollregion` eski | Her repaint görünümü içeriğe geri sokuyor; **kişiler değiştiyse** en üste döner |

İkinci hatanın ince yeri: sıfırlama repaint'e değil **listelenen isim kümesine** bağlı.
Yoksa 60 satırın ortasında bir kutu işaretleyen kişi her seferinde en üste fırlar —
birinci hatayı düzeltirken ikinci hata üretilmiş olurdu.

**Bir açık soru kapandı: `Eğitim İzni` izin sayılıyor.** Çalışma sayılan
izin türü listesi tek girdiyle **kapalı** (ADR-037). Program zaten böyle davranıyordu,
yani kod/config değişmedi — değişen şey, bunun artık gözden geçirilmemiş bir varsayılan
değil karar olması. Bir test listeyi sabitliyor, ikinci bir girdi eklemek yeni bir ADR
gerektiriyor. Yol boyunca ölçülen iki şey: her izin türünün her satırında saat var
(yıllık izin dahil), yani "saati var, çalışma olabilir" gerekçesi eğitime özgü değildi;
ve alternatifin maliyeti küçük — Mayıs +18:26, Haziran +4:53, çünkü eğitim saatlerinin
çoğu zaten kart basılan günün içinde.

---

## Geçen turda ne yapıldı (2026-08-19)

Kararların tamamı ADR olarak yazıldı; burası yalnızca harita.

**Pencere yeniden kuruldu.** `gui.py` → `gui/` paketi (kabuk / ekran ayrımı), sol
gezinme rayı, ve **ikinci bir ekran: Kişiler** — veri dosyasını okuyup kişileri nota
göre filtreliyor, seçim yapılabiliyor. Seçim mantığı `mail/recipients.py`'de, pencerede
değil (ADR-028, ADR-029).

**Girdi/çıktı esnekleşti.** Kaynak dosya başka klasördeyse tek tek gösterilebiliyor
(ADR-022). Rapor kullanıcının seçtiği klasöre yazılıyor, varsayılan Masaüstü, seçim
hatırlanıyor; ay başına `2026-06 Rapor` klasörü, veri dosyası yanında (ADR-024,
ADR-025). Personel listesi de kontrol ediliyor, gösterilebiliyor, hatırlanıyor
(ADR-035).

**Notlar elden geçti.** Etiketler anahtar kelimeye çevrildi ve **filtre anahtarı** oldu
(ADR-027); ailelere göre sıralanıyor (ADR-029); uzaktan çalışma üç nottan ikiye indi
(ADR-034); `Aralık çok kısa` kaldırıldı (ADR-031). Tesis adları `Macunköy` /
`Teknopark` oldu (ADR-026).

**Üç hesap hatası bulundu ve düzeltildi** — üçü de proje sahibinin sorusundan çıktı:

| Ne | Nasıl bulundu | Etki |
| --- | --- | --- |
| Yanlış aylı dosya sessizce geçiyordu | "Ya dosyaların ayları farklıysa?" | Rapor %72 eksik çıkıyor ve hiçbir şey söylemiyordu (ADR-023) |
| Ayı neredeyse boş kişiler işaretlenmiyordu | "Bunların nasıl sorunu olmuyor?" | 4 kişi hiç not almadan temiz listede (ADR-030) |
| 16 saati aşan **gerçek** vardiyalar 0 sayılıyordu | "16 saatten fazla çalışılamaz mı?" | Haziran +46:55 (ADR-032, ADR-033) |

**Belgeler.** `docs/KURALLAR.md` yazıldı: bütün hesaplama kuralları sade Türkçe,
jargonsuz, depo referansı olmadan — yöneticiye gösterilebilir. Her notun üç aylık
sayısı ve hiç görülmemiş olanlar işaretli.

---

## Gözden kaçmaması gerekenler

- `data/` ve `gonderim-*.json` **kişisel veri**, git'e girmez. Veri dosyası artık
  kullanıcının seçtiği herhangi bir yere (Masaüstü dahil) düşebiliyor, o yüzden asıl
  koruma klasör kuralı değil **dosya adı kuralı**.
- Bordroyu etkileyen üç config anahtarı **zorunlu**: `daily_hours`, `break.deduct`,
  `remote_replaces_attendance`. Eksikse program durur.
- **`tests/conftest.py` fixture'ı gerçek config'den sapabiliyor** ve bu turda iki kez
  daha saptı (`facility_labels`, `sparse_month_ratio`). `test_config.py` artık
  `Plausibility`'nin **tamamını** karşılaştırıyor. Yeni bir config anahtarı eklerken
  fixture'a da ekle — yoksa bütün test paketi, kimsenin çalıştırmadığı bir kurala karşı
  geçmeye devam eder.
- **`arayuz-ayarlari.json` artık `gui/settings.py` üzerinden yazılıyor** — oku,
  değiştir, yaz. Eskiden rapor ekranı kendi üç anahtarını bütün dosyanın üzerine
  yazıyordu, yani bir şey hatırlayan ikinci ekran birincisinin ayarını sessizce
  silecekti. Temizlenen bir değer açıkça `null` yazılıyor; anahtarı hiç yazmamak eski
  değeri dosyada bırakır.
- **Kişiler listesi artık widget yığını değil.** Uzun bir listeyi frame içinde
  label'larla çizmek 171 kişide 856 widget demek ve tk her kaydırma adımında hepsini
  yeniden konumlandırıyor. Yeni bir liste ekranı gerekirse `Treeview` ile başla
  (ADR-039). Karşılığında üç şey kaybedildi ve bilerek: hücre bazlı renk, kolon bazlı
  yazı tipi, yerel onay kutusu.
- **`unbind_all("<MouseWheel>")`** yalnızca bu pencerede başka hiçbir şey o olayı
  `all` etiketine bağlamadığı için güvenli. Bağlayan bir şey eklenirse bu değişmeli.
- **Uygulamanın gösterdiği hiçbir şey kişi, ekip ya da departman adlandırmaz** ve
  hiçbir yerde "onay bekleniyor" demez (ADR-046, ADR-047). `İK`, `IT`, unvan,
  "X talebiyle", "onay bekliyor", "şu kişiye sorulacak" — hiçbiri. Kendi aramızda
  (`docs/`, ADR, commit mesajı) kimin ne dediğini yazmak doğru ve gerekli, kayıt o;
  programın yazdığı yerde ise hem kullanılamaz hem de çoğu zaman yanlıştı — rapor
  hiç yapılmamış bir talebi ve hiç sorulmamış bir onayı yazıyordu. 3. sayfanın adı
  bu yüzden `Sorulacaklar` değil **`İnceleme Listesi`**. Testle sabit
  (`test_the_workbook_never_says_who_to_ask`): tam kelime eşleşmesi, çünkü `İK`
  `EKSİK`'in içinde geçiyor; personel listesinden gelen hücreler atlanıyor, çünkü
  gerçek departman ve unvan adları o kelimeyi taşıyor.
- **Test pencereleri ekranın dışına park ediliyor** (`+6000+6000`). Tam koşu
  140'tan fazla gerçek pencere açıp kapatıyor ve bunlar otuz saniye boyunca
  kullanıcının önünde yanıp sönüyordu. Sadece konum — buradaki bütün geometri
  kontrolleri **boyut** hakkında ve `wm geometry WxH` konuma dokunmuyor, yani
  ölçülen hiçbir şey değişmedi. `withdraw()` değil: haritalanmamış bir pencere
  boyutunu 1x1 diye bildirir ve pencere testleri bir şey test etmez olur. Yeni bir
  pencere fixture'ı eklerken `_tk_root` kullan.
- **Pencere hiçbir tatil önerisi göstermiyor** (ADR-044). Ekranda `?` işaretleri
  vardı, kaldırıldı: öneri o oturumdaki son koşudan geliyordu, yani yeni açılmış bir
  pencerenin söyleyecek sözü yoktu. Kontrol sayfasındaki satır duruyor — orada
  ayın kayıtları elde. Genel ders: **bir kontrol, kanıtının olduğu yere ait.**
- **GUI testleri artık "ekran yok" diye sessizce atlanmıyor.** Her `TclError` ekran
  yokluğu sayılıyordu; ekranın olup olmadığı bir kez ölçülüyor, sonrasında pencere
  kurulamazsa test kırmızı düşüyor. Nadiren (2-3 tam koşuda bir) bir pencere testi
  sessizce atlanıyordu ve her seferinde başka bir test — bu değişiklikten önce de
  vardı, pytest dışında 280 denemede tekrarlanmıyor.
- **Etiketler artık filtre anahtarı** (ADR-027). Bir etiketi yeniden adlandırmak
  snapshot için kırıcı değişikliktir, düzeltme değil. İki tür aynı etiketi paylaşamaz.
- Snapshot `format_version` **3**. Eski dosyalar "yeniden üret" diye reddediliyor.
- Ekran görüntüsü alırken **tüm ekranı değil pencereyi** yakala (`PrintWindow`), ve
  Kişiler ekranını **sentetik veriyle** test et — gerçek veriyle açılan bir ekran
  görüntüsü çalışan adlarını ve e-posta adreslerini gösterir. Bu turda bir kez oldu.
