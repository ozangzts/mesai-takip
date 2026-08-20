# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-20, commit `c61e572`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi** ve **beklenen cevapları**
> tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (38 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | **Kurallar, sade Türkçe — yöneticiye gösterilebilir** | [KURALLAR.md](KURALLAR.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Fazlar, açık sorular | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, üç ay üretiliyor, **345 test geçiyor**.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 16 078:44 ⚠ |
| Kişi | 171 | 163 | 175 |
| Şüpheli kayıt | 250 | 427 | 554 |

⚠ **Temmuz eksik** — Teknopark dosyası ayın 1–19'unu kapsıyor, 20 Temmuz'da alınmış.
Program bunu kırmızıyla yazıyor ve `5` koduyla çıkıyor. Saatler bordroya uygun değil.

Çalıştırma: `arayuz.cmd` (pencere) veya `rapor.cmd --ay 2026-07` (komut satırı).

**Mayıs ve Haziran yeni kurallarla yeniden üretildi** (ADR-030, ADR-032, ADR-033
Haziran'ın toplamını 27 119:24'ten 27 166:19'a çıkarmıştı). Pencereden üretilen
kopyalar Masaüstünde, `snapshot format_version 3`; doğrulandı — aynı ay yeniden
üretildiğinde `gonderim-*.json` üretim saati dışında birebir aynı çıkıyor. Temmuz
bilerek yeniden üretilmedi, Teknopark dosyasının tam ay hâli bekleniyor.

---

## Sıradaki iş

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

## İK'dan / IT'den beklenen cevaplar

Proje sahibi soracak. Öncelik sırasıyla:

| # | Soru | Neyi bloke ediyor |
| --- | --- | --- |
| 1 | **Temmuz Teknopark dosyası tam ay için yeniden alınabilir mi?** Dosyalar her ay ayın kaçında alınacak? | Temmuz raporu (Q23) |
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

**Bir açık soru kapandı: `Eğitim İzni` izin sayılıyor, İK onayladı.** Çalışma sayılan
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
- **Etiketler artık filtre anahtarı** (ADR-027). Bir etiketi yeniden adlandırmak
  snapshot için kırıcı değişikliktir, düzeltme değil. İki tür aynı etiketi paylaşamaz.
- Snapshot `format_version` **3**. Eski dosyalar "yeniden üret" diye reddediliyor.
- Ekran görüntüsü alırken **tüm ekranı değil pencereyi** yakala (`PrintWindow`), ve
  Kişiler ekranını **sentetik veriyle** test et — gerçek veriyle açılan bir ekran
  görüntüsü çalışan adlarını ve e-posta adreslerini gösterir. Bu turda bir kez oldu.
