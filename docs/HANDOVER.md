# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-18, commit `b065325`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi** ve **beklenen cevapları**
> tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (35 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Fazlar, 28 açık soru | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
> | **Kurallar, sade Türkçe — yöneticiye gösterilebilir** | [KURALLAR.md](KURALLAR.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, üç ay üretiliyor, 333 test geçiyor.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 16 029:17 ⚠ |

⚠ **Temmuz eksik** — Teknopark dosyası ayın 1–19'unu kapsıyor, 20 Temmuz'da alınmış.
Program bunu kırmızıyla yazıyor ve `5` koduyla çıkıyor. Saatler bordroya uygun değil.

Çalıştırma: `arayuz.cmd` (pencere) veya `rapor.cmd --ay 2026-07` (komut satırı).

## Akıştaki iş

1. **GUI denendi, bir eksik bulundu ve düzeltildi:** klasör adı `06-2026` gibi
   ay-yıl sırasındaysa dönem okunamıyordu. Artık `2026-07`, `07-2026`, `202607`,
   `Temmuz 2026` ve daha uzun isimlerin içine gömülü hâlleri anlaşılıyor; belirsiz
   olanlar (`03-04`) bilinçli olarak reddediliyor.
   İki eksik daha düzeltildi: komşu klasörleri listeleyen dönem açılır listesi
   kaldırıldı (nereden geldiği belirsizdi ve yanlış ay seçmeye davetiye çıkarıyordu),
   ve rapor + veri dosyasının **tam yolu** artık sonuç panelinde yazıyor.
   **Kaynak dosyaların yeri belli oldu:** `Y:` ağ paylaşımı, ay başına ayrı klasör,
   `AA - YYYY` biçiminde adlandırılmış. Drive API'ye gerek yok — ROADMAP Q21'in bir
   kısmı cevaplandı, erişim yetkisi hâlâ açık.
2. **`gui.py` → `gui/` paketine bölündü.** Tek 662 satırlık modül dörde ayrıldı:
   `gui/app.py` (pencere kabuğu, başlık bandı, `main()`), `gui/rapor.py` (rapor
   ekranı — `ReportScreen`), `gui/period.py` (dönem okuma/yazma, saf ve testli),
   `gui/widgets.py` (palet ve ortak düğme/etiket yardımcıları). **Davranış birebir
   aynıydı**; o günkü 217 testin hepsi değişmeden geçti (bugünkü sayı yukarıda).
   Asıl kazanç kabuk/ekran ayrımı: `App` toplevel'i ve ekranın oturduğu çerçeveyi
   tutuyor, `ReportScreen` içindeki her şeyi. **Sol panel artık yeniden yapılandırma
   değil** — `App.content` yanına öğe koymak ve hangi ekranın grid'lendiğini
   değiştirmek. `gui/mail.py` bilerek açılmadı: içi boş bir modül, olmayan bir
   modülden daha az bilgi verir.
3. **Sonraki teknik adım: tek `.exe` paketi** (PyInstaller). Asıl uğraş paketleme
   değil, **Python'un kurulu olmadığı bir makinede test etmek.** `config/` exe'nin
   içine gömülmemeli — kural değişikliği YAML düzenlemesi ve `personel.yaml` gerçek
   isim yazımlarını tutuyor.
   Not: `arayuz.cmd` `python -m mesai.gui` çağırıyor, `pyproject.toml` ise
   `mesai.gui:main`. İkisi de bölmeden sonra çalışıyor (`gui/__main__.py` ve
   `gui/__init__.py`'daki dışa aktarım). Paketlemede ikisini de kontrol et.
4. **Sol panel eklendi.** Pencerede artık solda bir gezinme rayı var; şu an tek öğe
   (`Rapor`) çünkü tek iş yüzü var. Ekran kaydı `gui/app.py:SCREENS`, ray ondan
   üretiliyor. Ayrıca boş dönem alanının yanındaki ipucu (`Örn. 2026-07 · ...`) ilk
   açılışta hiç görünmüyordu — yalnızca alana yazıldığında tetikleniyordu, yani tam
   olarak yazıldığı durum için erişilemezdi. Düzeltildi, testi var.
5. **Pencere görsel olarak elden geçirildi.** İlerleme çubuğu ttk'nın yerine elle
   çiziliyor (`widgets.Progress`): boştayken hiçbir şey görünmüyor, koşarken accent
   renginde bir tarama. Eskisi duruşta bile bir parça dolu görünüyordu ve vista teması
   rengini yok sayıp yeşile boyuyordu. Ayrıca: klasör seçilmemiş hâli artık kırmızı
   değil (hata değil, başlangıç); bulunan/bulunamayan kaynaklar ayrı ayrı renkleniyor;
   özet rakamları sabit genişlikli yazı tipinde, yani iki noktalar hizalı; sonuç kartı
   **kaydırılabilir** — veri dosyasının yolu yazılıyor ama kartın altında kesiliyordu.
6. **Dosyalar farklı yerlerdeyse artık elle gösterilebiliyor (ADR-022).** Klasör
   seçilir, program bulabildiğini bulur, bulamadığı kaynağın satırında bir `Seç…`
   düğmesi çıkar. Elle seçilen dosya o kaynak için glob'u atlar, ötekiler klasörden
   gelmeye devam eder; `Geri al` klasöre döndürür. Klasör değişince elle seçimler
   unutuluyor (eski aya aitler). ADR-014 kırılmadı: dönem filtresi hâlâ ay dışını
   düşürüyor, yani başka klasörden gelen bir dosya başka bir ayı içeri sokamıyor.
   Kaynak etiketleri de kısaldı: `Macunköy`, `Teknopark`, `İzin`.
7. **Yanlış aylı dosya artık koşuyu durduruyor (ADR-023).** ADR-022'yi eklerken
   sorulan soru buydu ve cevabı ölçüldü: Mayıs verisine Haziran Teknopark dosyası
   konup Mayıs olarak koşulduğunda program **başarıyla bitiyordu** — 17 103:58 yerine
   4 869:54, hiçbir uyarı yok. 2 557 satır sessizce dönem dışı diye düşüyordu; ADR-014
   kontrolü global olduğu için (Macunköy'de Mayıs kaydı vardı) tetiklenmiyor, ADR-020
   kapsama kontrolü de kaynak listesini *filtreden geçenlerden* kurduğu için o kaynağı
   hiç görmüyordu.
   Artık **kayıt okuyup dönem içinde hiç kayıt tutmayan** kaynak koşuyu düşürüyor.
   Ayrım şu: *hiç okumadı* sorun değil (ofis kapalıyken Teknopark'ta satır olmaz),
   *okudu ama hiçbiri aya ait değil* yanlış dosya demek.
   Pencere ayrıca dosya **adında** başka bir ay geçiyorsa düğmeye basılmadan önce
   turuncu uyarı veriyor — karar vermiyor, sadece keşfi öne alıyor.
8. **Rapor artık kullanıcının seçtiği klasöre yazılıyor (ADR-024).** Varsayılan
   Masaüstü (`SHGetKnownFolderPath`, `~/Desktop` varsayımı değil — OneDrive
   yönlendirmesi olan makinede Masaüstü başka yerde). Seçim hatırlanıyor; girdi
   klasörünün aksine, çünkü çıktı klasörü aya özel değil. Ay başına tek klasör:
   `2026-06 Rapor` (yıl önce, klasörler tarih sırasına dizilsin diye — ADR-025),
   içinde rapor ve veri dosyası birlikte. Aynı ay ikinci kez çalıştırılırsa üzerine
   yazılıyor ve pencere bunu **önceden** söylüyor.
   Bu arada mevcut bir çelişki çözüldü: `snapshot.default_path`'in docstring'i
   "bilerek raporun yanında DEĞİL" diyordu, ADR-021 ise "program JSON'u raporun
   yanında bulur" diyordu. ADR-021 lehine çözüldü.
   CLI varsayılanı değişmedi (`data/out/<ay>/`), sadece veri dosyası artık orada da
   raporun yanında.
9. **Raporda tesis adları sadeleşti (ADR-026).** `MACUNKÖY TESİSİ` → `Macunköy`,
   `DEICO TESİS` → `Teknopark`. Eşleme `config/settings.yaml:facility_labels`'da,
   kodda değil: bu anahtarlar HCM'in yazdığı değerler, bizim değil. Eşleşmeyen bir
   değer personel listesindeki hâliyle yazılıyor (tahmin edilmiyor) ve `Kontrol`
   sayfası §8 görülen bütün tesis değerlerini listeliyor.
   **Sorulan soru şuydu: uzaktan çalışma için not düşülüyor mu?** Düşülüyor, üç ayrı
   yerde — cevap için ADR-017/018 ve `Aylık Özet`'in `Kayıt Kaynağı` kolonu.
10. **Kişiler ekranı eklendi (ADR-028).** Sol rayda ikinci öğe. Rapor bitince veri
    dosyası kendiliğinden yükleniyor; eski bir ay için `Aç…` var. Filtre dropdown'ı
    **yüklenen dosyadan** üretiliyor — not eklenirse kendiliğinden görünür. Kişiler
    tek tek seçilip çıkarılabiliyor, çıkarma **isim üzerinden** (liste yeniden
    sıralandığında satır numarası başkasını gösterirdi). Filtre değişince çıkarmalar
    unutuluyor. E-postası olmayan gösteriliyor ve sayılıyor, atılmıyor.
    Seçim mantığı `mail/recipients.py`'de, pencerede değil — pencere olmadan test
    edilebiliyor.
    Filtre listesi **ailelere göre** sıralı (Eksik kayıt / Süre / Uzaktan çalışma /
    Diğer), aile içinde bildirim sırasına göre — sıklığa göre değil, çünkü o her ay
    listeyi yeniden diziyordu (ADR-029). Satırda kişinin **öteki sorun sayısı** `+2`
    diye görünüyor; notların kendisi yazılmıyor, liste metin duvarına dönüşmesin diye.
    Kolon olarak ne ekleneceği (departman, sicil, izin günü…) **henüz açık**.
    Notlar da anahtar kelimeye çevrildi (ADR-027) ve gri notlar veri dosyasına
    `expected` alanıyla girdi (`format_version` 3).
    **Gönderme yok.** HANDOVER'daki üç mail kararı hâlâ cevapsız ve ekran onlarsız
    çalışıyor. Sıradaki: "bu kişilere mail atılmayacak" istisna listesi — proje sahibi
    böyle bir Excel bekliyor; o bir *kalıcı kural*, bir oturumun seçimi değil, ve
    `recipients.py`'ye filtrenin yanına girmeli, ekrana değil.
11. **"Ay büyük ölçüde boş" notu eklendi (ADR-030).** Kişiler ekranını kullanırken
    çıktı: Haziran'da sorunsuz görünen 51 kişinin 4'ü 20 saatin altındaydı ve **hiç
    notu yoktu**. Sebep, iki kural arasındaki boşluk — `Süre çok kısa` *günlük*
    çalışıyor (bu kişilerin günleri normaldi), `Mesai verisi yok` ise ancak hiç kayıt
    yoksa. Bir tam gün + 21 eksik gün ikisinin arasına düşüyordu.
    Artık çalışma + izin, beklenen iş gününün **%50'sinden azını** açıklıyorsa not
    düşülüyor. Saatlere dokunmuyor (Mayıs yine 17 103:58). Haziran'ın sorunsuz listesi
    51 → 47 oldu.
    **Uyarı:** personel listesinde işe giriş/çıkış tarihi olmadığı için (ROADMAP Q18)
    ay ortasında başlayan biriyle kaydı eksik olan biri ayırt edilemiyor. Bu yüzden
    dışlama değil, insana gösterilen işaret.
12. **`Aralık çok kısa` kaldırıldı (ADR-031)** ve **`docs/KURALLAR.md` yazıldı.**
    Beş dakikanın altındaki tek okuma artık not düşmüyor — sadece o notu taşıyan
    kişilerin hepsinin ayı sıradandı (106–242 saat, 11–24 gün), yani kayıt tuhaflığını
    kişi sorunu gibi gösteriyordu. Saatler değişmedi (Mayıs 17 103:58); şüpheli kayıt
    Mayıs'ta 262→250, Haziran'da 449→426.
    `KURALLAR.md` bütün hesaplama kurallarını sade Türkçe, jargonsuz ve depo referansı
    olmadan tek yerde topluyor — proje sahibi yöneticisine gösterebilsin diye. Kural
    değişirse ikisi birlikte güncellenir.
    **AÇIK KONU:** 16 saat üst sınırı (`Aralık çok uzun`) el değmeden duruyor ve
    **tek başına bir günü 0 saat sayan tek kural**. Proje sahibi bunu ayrıca konuşmak
    istiyor: biri gerçekten 16 saatten fazla çalışmış olabilir mi, ve o günü tamamen
    sıfırlamak doğru mu? Mayıs'ta 1, Haziran'da 3 kişi etkileniyor.

    Ayrıca soruldu: **hafta sonu çalışması sıfırlanıyor mu?** Ölçüldü — **hayır**.
    Mayıs'ta 30 hafta sonu kişi-günü (164:31) ve 41 resmi tatil kişi-günü (325:01)
    toplamın içinde. Hafta içi takvimi yalnızca (a) kaynak dosya ayı kapsıyor mu
    kontrolünde ve (b) `Ay büyük ölçüde boş` notunun paydasında kullanılıyor; saatlere
    hiç dokunmuyor. `tests/test_merge.py` bunu artık sabitliyor.
13. **16 saat kuralı düzeltildi (ADR-032) — AÇIK KONU KAPANDI.**
    Altı vaka tek tek açıldı: üçü bozuk kayıt (çıkış girişten önce, düzeltilince
    21–24 saat çıkıyor), **üçü gerçek** — 16:06, 16:39 ve 23:09. İki kişi gerçekten
    çalıştıkları günü 0 saat alıyordu.
    Ayrım şu: **çıkışı girişten önce olup bizim +24 saat ekleyerek onardığımız** kayıt
    reddediliyor (onarım bizim tahminimiz, imkânsız sonuç veriyorsa tahmin yanlıştır);
    kaynağın düpedüz yazdığı uzun gün ise sayılıp **işaretleniyor**.
    Mayıs değişmedi (17 103:58). **Haziran 27 119:24 → 27 166:19, +46:55.**
    Yeni etiketler: `Günlük süre çok uzun (>16 saat)` ve `Giriş-çıkış tutarsız`.
    `Günlük süre çok kısa (<2 saat)` de eşiği adında taşıyor artık.
    **ADR-033 ile düzeltme üst sınırı ayrı bir anahtar oldu ve 20 saate çıktı.**
    Sebebi ölçüldü: gerçek gece vardiyalarının en uzunu 15:36, yani 16 saatlik sınırın
    yalnızca 24 dakika altında — 16 saatlik bir gece vardiyası imkânsız değil. Bozuk
    kayıtlar 21:56 / 23:58 / 23:59'da olduğu için üçü de hâlâ reddediliyor ve
    **hiçbir rakam değişmedi**. Günlük 16 saat işaretlemesi olduğu gibi duruyor.
14. **Uzaktan çalışma notu ikiye indi (ADR-034).** `Uzaktan + sistem + ek kayıt`
    kaldırıldı; iki `info` etiket aynı durumu anlatıyordu ve aradaki fark yalnızca
    içeride hangi kuralın çalıştığıydı. Artık `Uzaktan + sistem kaydı` (⚪) ve
    `Uzaktan + kart kaydı` (🟡). Hangi kuralın çalıştığı `Şüpheli Kayıtlar`'daki
    açıklama satırında duruyor. Rakam değişmedi.
15. **SIRADAKİ İŞ — istisna listesi (4. dosya).** Proje sahibi "bu kişilere mail
    atılmayacak" diye bir Excel bekliyor. Yapı hazır:

    - `recipients.selected(snapshot, filtre, çıkarılanlar)` zaten bir isim kümesi alıp
      çıkarıyor. Mekanizma var, doldurulması gerekiyor.
    - Eklenecek: dosyayı okuyan fonksiyon (**`mail/recipients.py` içine, ekrana
      değil**), bir onay kutusu (`☑ İstisna listesindekileri çıkar`) ve kalıcı istisna
      ile o oturumdaki elle çıkarmayı **ayrı tutmak** — biri kural, öteki tercih.
      Filtrede görünmemeleri bundan doğal olarak gelir.

    **Asıl risk arayüzde değil, isim eşleştirmede.** Haziran'da ölçüldü: 163 kişinin
    **126'sında sicil no var, 37'sinde yok** (personel listesinde olmayanlar). İsimler
    benzersiz ama isimle eşleştirmek bu projenin bilinen zor problemi — Türkçe karakter,
    evlilik soyadı, kısaltılmış ad. İstisna listesi ismi farklı yazarsa **o kişi
    sessizce mail alır**, ki tam da kaçınılması gereken hata türü.

    Liste eline geçtiğinde **ilk bakılacak şey: içinde sicil no var mı.** Varsa
    eşleştirme güvenli. Yoksa isim eşleştirmesi kurulacak ve **eşleşmeyen her satır
    için uyarı verilecek** — program tahmin etmez, söyler (AGENTS §2.1).
16. **Pencere dört dosyanın üçünü kontrol ediyordu (ADR-035).** Personel listesi
    yalnızca koşu başlayınca aranıyordu, yani `Rapor Oluştur` yeşil oluyor ve hata
    düğmeye basıldıktan sonra çıkıyordu. Artık dördüncü satır olarak listede, eksikse
    düğme kilitli, `Seç…` ile gösterilebiliyor.
    **Seçim hatırlanıyor** — aya bağlı olmadığı için (çıktı klasörüyle aynı mantık,
    girdi klasörünün tersi). Dosya taşınmışsa hatırlanan yol düşürülüyor ve normal
    arama devreye giriyor.
    Proje sahibi "liste gerekli mi" diye sordu; ölçüldü: **saatleri hiç etkilemiyor**
    (çıkarılsa toplam aynı kalır) ama **e-posta, tesis ve görev alanlarının tek
    kaynağı** — Haziran'da 154 kişi. E-posta adımı onsuz mümkün değil.
17. **E-posta adımı henüz başlamadı** ve başlamamalı — aşağıdaki iki cevap gelmeden.

## Genişletirken

E-posta ve kişi seçme eklenecek. Yapı bunu kaldırır ama iki yer zorlanır.

**Bu bölümdeki maddelerin ağırlığı farklı.** Sol panel ve `gui/` bölmesi proje
sahibiyle konuşuldu ve yön olarak kabul edildi. Geri kalanı uygulama tavsiyesi —
karar verilmiş gibi davranılmamalı, sorulmalı.

### 1. `gui/` bölmesi ve sol panel ✅ ikisi de yapıldı

Sıra doğruydu: önce bölme, sonra panel. İkisi de bitti.

**Yeni bir iş yüzü eklemek `gui/app.py:SCREENS`'e tek bir kayıt.** Anahtar, etiket ve
ekranı kuran bir çağrılabilir. Sol panel bu listeden üretiliyor; ne `app.py`'de ne de
mevcut bir ekranda başka bir düzenleme gerekmiyor:

```python
SCREENS = (
    Screen("rapor", "Rapor", _report),
    Screen("mail", "E-posta", _mail),      # eklenecek tek satır bu
)
```

İki davranış testle sabitlendi, ikisi de bozulursa hata sayılır:

- Ekran **en fazla bir kez, ilk açılışta** kuruluyor. Mail ekranı snapshot isteyecek;
  kimsenin açmadığı bir ekran için snapshot yüklemek boşa iş.
- Ekran değiştirirken `grid_forget` değil **`grid_remove`** kullanılıyor, yani gizli
  ekran durumunu koruyor. Başka bir bölüme bakıp dönünce seçilen klasörün kaybolması
  kusurdur.

`gui/mail.py` bilerek açılmadı — içi boş bir modül, olmayan bir modülden daha az bilgi
verir. Panelde de yalnızca **var olan** ekranlar listeleniyor: basılamayan bir öğe
İK'ya verilmiş bir söz olur (`ARCHITECTURE.md` §3b).

Bunun istisnası, HANDOVER'ın daha önce not ettiği **çalışma zamanı durumu**: mail
ekranı var olduğunda, snapshot yüklenmemişse öğesi pasif kalıp sebebini yazabilir. Bu
"henüz yazılmadı" demekten farklı — biri durumu anlatır, diğeri hiçbir şey anlatmaz.

### 2. Seçim mantığı pencereye girmemeli

"Şu kategoriye düşenler, eksi elle çıkarılanlar" bir **iş kuralı**, arayüz detayı
değil. Bu bir tavsiye ama dayanağı mevcut bir konvansiyon: `ARCHITECTURE.md` §3 zaten
"`cli.py` yalnızca bağlama içerir — iş mantığı asla oraya girmez" diyor, ve pencere
için de aynısı geçerli.

Önerilen yer `mail/recipients.py` gibi bir modül: snapshot + filtre + istisna listesi
alır, alıcı listesi döndürür, pencere olmadan test edilir. Pencerenin içine girerse
test edilemez; test edilemeyince güvenilmez.

`snapshot.py` bunun için hazır: `with_problem(etiket)`, `problem_labels`,
`is_complete`.

### 3. Mail adımı için ÖNERİLER — henüz karar değil

> **Bunlar kararlaştırılmadı.** Dördü de bu oturumda uygulama tarafından önerildi,
> proje sahibi hiçbirini onaylamadı ya da reddetmedi. Mail işine başlarken **önce
> sorulmaları** gerekiyor; kararlaştırılmış kısıt gibi davranılmamalı. Karar verilirse
> ADR olarak yazılıp buradan çıkarılsınlar.

1. **Varsayılan davranış göndermek değil, önizleme olsun.** Gerekçe: 162 kişiye mail
   geri alınamaz. Taslaklar bir klasöre yazılır, İK bakar, ayrı bir onayla gönderilir.
2. **Elle çıkarılan kişi kayda geçsin.** Gerekçe: "kime gitmedi, neden" sorusunun bir
   cevabı olmalı — bordroya komşu bir iletişim.
3. **Eksik snapshot'tan mail atılmasın.** `is_complete` alanı bunu ayırt edebiliyor
   (ADR-020'den geliyor), ama *gönderimi reddetmek* bir politika kararı ve verilmedi.
4. **Gmail şifresi repoya girmesin.** Bu dördüncüsü aslında öneri değil, mevcut kural:
   `AGENTS.md` §2.3 zaten sırların commit edilmemesini gerektiriyor ve `.env`
   `.gitignore`'da. Sadece hatırlatma — `arayuz-ayarlari.json`'un bir kez commit'e
   girdiği görüldü.

Ayrıca `gui/rapor.py`'daki `Result` dataclass'ı rapora göre şekillenmiş. Mail koşusunun
sonucu farklı (kişi başına gönderildi / hata / atlandı), onu germek yerine kendi tipini
almalı — zaten artık ayrı modülde duruyor, paylaşmaya davet eden bir yerde değil.

## İK'dan / IT'den beklenen cevaplar

Proje sahibi soracak. Öncelik sırasıyla:

| # | Soru | Neyi bloke ediyor |
| --- | --- | --- |
| 1 | **Temmuz Teknopark dosyası tam ay için yeniden alınabilir mi?** Ayrıca: dosyalar her ay ayın kaçında alınacak? | Temmuz raporu (ROADMAP Q23) |
| 2 | **Macunköy dosyası o tesisin bütün turnikelerini ve personelini kapsıyor mu?** 26–31 kişinin hiç kart kaydı yok, neredeyse hepsi Macunköy | Faz 1 onayı — **en kritik** (Q4) |
| 3 | Dokuz isim eşleştirmesinin onayı — `Kontrol` sayfası bölüm 7'de listeli | Yanlışsa iki kişinin bordro saatleri birleşir (Q4a) |
| 4 | Mayıs'ın 7 resmi tatili doğru mu (veriden çıkarıldı, İK söylemedi) | Tatil çalışması ücreti (Q16) |
| 5 | Personel listesi **işe giriş / çıkış tarihi** kolonlarıyla alınabilir mi? | E-posta adımı — ayrılmış birine maaş maili gitmemeli (Q18) |

Soru 5'in cevabı "böyle bir liste yok" olabilir; o durumda alternatif düşünülecek.

## Cevaplanmayı bekleyen ama bloke etmeyen

- **Q20a** — Teknopark puantajındaki nominal `09:00–18:00` satırları neden yazılıyor?
  Mayıs'ta 319, Haziran'da 418 satır; raporun ~%17'si. Şu an çalışma sayılıyor
  (ADR-017, kaynak dosyanın kendi toplamı da öyle sayıyor). Cevap "bordroda
  ödenmiyor" olursa yeni bir ADR ve ~%17 düşüş demek.
- **Q13** — `Eğitim İzni` uzaktan çalışma gibi çalışma sayılacak mı? Kayıtlarda
  gerçek saat var, yani cevap "evet" ise varsayım gerekmeden hesaplanır.

## Bu turda alınan kararlar (ADR'lere yazıldı, tekrar tartışılmasın)

- Mola kesintisi **yok**, gün **ilk giriş → son çıkış** (ADR-015, ADR-016)
- Nominal puantaj günü **çalışma sayılır**; uzaktan çalışma günü onu **ezer**, ama
  gerçek turnike okumasını **asla ezmez** (ADR-017, ADR-018)
- 2 saatin altındaki günler işaretlenir (ADR-019)
- Okuyucular kabı ve kolon konumlarını **keşfeder**, varsaymaz (ADR-020)
- Rapor **asla geri okunmaz**; her koşu `gonderim-<ay>.json` yazar ve aşağı akış onu
  okur (ADR-021). Bu dosya artık **raporun yanında** duruyor (ADR-024)
- Raporda **depoya ait hiçbir referans olmaz** (`ADR-015`, `Q4` gibi) — bir test
  bunu koruyor
- Commit mesajları **Türkçe** (AGENTS.md §6'da düzeltildi, pratik buydu)

## Gözden kaçmaması gerekenler

- `data/` ve `gonderim-*.json` **kişisel veri**, git'e girmez. `veri/` neredeyse
  commit edilecekti; `.gitignore`'a eklendi. `veri/` artık yazılmıyor (ADR-024) ama
  `.gitignore` girdisi duruyor — asıl koruma dosya adı kuralı, çünkü veri dosyası artık
  kullanıcının seçtiği herhangi bir yere (Masaüstü dahil) düşebiliyor.
- Bordroyu etkileyen üç config anahtarı **zorunlu**: `daily_hours`,
  `break.deduct`, `remote_day_replaces_attendance`. Eksikse program durur.
- `tests/conftest.py` fixture'ı gerçek config'den **sapabiliyor** — bir kez saptı ve
  testler programın kullanmadığı desenlere karşı geçmeye devam etti.
  `tests/test_config.py` artık bunu yakalıyor.
- Eski raporu geri üretmek için **üç** anahtar birlikte: `break.deduct: true`,
  `daily_hours: union`, `remote_day_replaces_attendance: never`.
