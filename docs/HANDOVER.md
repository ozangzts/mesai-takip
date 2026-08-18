# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-18, commit `01632bd`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi** ve **beklenen cevapları**
> tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (21 ADR) | [DECISIONS.md](DECISIONS.md) |
> | Hesap kuralları | [DOMAIN-RULES.md](DOMAIN-RULES.md) |
> | Kaynak dosyaların kusurları (D1–D13) | [DATA-SOURCES.md](DATA-SOURCES.md) |
> | Fazlar, 28 açık soru | [ROADMAP.md](ROADMAP.md) |
> | Kullanım (Türkçe) | [README.md](../README.md) |
>
> **Bu dosya son commit'ten eskiyse ona değil, yukarıdakilere güven.**

---

## Durum

Faz 1 çalışıyor, üç ay üretiliyor, 203 test geçiyor.

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
2. **Sonraki teknik adım: tek `.exe` paketi** (PyInstaller). Asıl uğraş paketleme
   değil, **Python'un kurulu olmadığı bir makinede test etmek.** `config/` exe'nin
   içine gömülmemeli — kural değişikliği YAML düzenlemesi ve `personel.yaml` gerçek
   isim yazımlarını tutuyor.
3. **E-posta adımı henüz başlamadı** ve başlamamalı — aşağıdaki iki cevap gelmeden.

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
