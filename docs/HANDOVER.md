# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-18, commit `8e0ec7f`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi** ve **beklenen cevapları**
> tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (22 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Fazlar, 28 açık soru | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, üç ay üretiliyor, 242 test geçiyor.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 119:24 | 16 029:17 ⚠ |

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
   aynı**, 217 test geçmeye devam ediyor.
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
7. **E-posta adımı henüz başlamadı** ve başlamamalı — aşağıdaki iki cevap gelmeden.

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
- Rapor **asla geri okunmaz**; her koşu `veri/gonderim-<ay>.json` yazar ve
  aşağı akış onu okur (ADR-021)
- Raporda **depoya ait hiçbir referans olmaz** (`ADR-015`, `Q4` gibi) — bir test
  bunu koruyor
- Commit mesajları **Türkçe** (AGENTS.md §6'da düzeltildi, pratik buydu)

## Gözden kaçmaması gerekenler

- `veri/` ve `data/` **kişisel veri**, git'e girmez. `veri/` neredeyse commit
  edilecekti; `.gitignore`'a eklendi.
- Bordroyu etkileyen üç config anahtarı **zorunlu**: `daily_hours`,
  `break.deduct`, `remote_day_replaces_attendance`. Eksikse program durur.
- `tests/conftest.py` fixture'ı gerçek config'den **sapabiliyor** — bir kez saptı ve
  testler programın kullanmadığı desenlere karşı geçmeye devam etti.
  `tests/test_config.py` artık bunu yakalıyor.
- Eski raporu geri üretmek için **üç** anahtar birlikte: `break.deduct: true`,
  `daily_hours: union`, `remote_day_replaces_attendance: never`.
