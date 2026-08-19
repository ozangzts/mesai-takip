# Mesai Raporu — Hesaplama Kuralları

**Bu belge, raporun sayılarının nasıl çıktığını teknik bilgi gerektirmeden anlatır.**
Yöneticiye, İK'ya ya da rapordaki bir sayıyı sorgulayan herkese gösterilebilir.

Buradaki her eşik programın ayar dosyasında (`config/settings.yaml`) yazılıdır ve
değiştirilebilir. Bir kural değişirse bu belge de değişir; ikisi birlikte
güncellenir.

> **Bu rapor bir doğrulama koşusudur, bordro için nihai değildir.** Fazla mesai,
> vardiya ve Multinet hesapları henüz yapılmıyor — bkz. "Henüz yapılmayanlar".

---

## 1. Program ne yapıyor

Her ay iki tesisten gelen ham kart okuyucu çıktıları ile İK'nın izin dosyasını okur,
kişi başına aylık çalışma süresini hesaplar ve tek bir Excel raporu yazar.

Girdi dört dosya:

| Dosya | İçerik |
| --- | --- |
| Personel listesi | Kim çalışıyor — isim, e-posta, tesis, bölüm, görev |
| Macunköy | Macunköy tesisinin kart kayıtları |
| Teknopark | Teknopark tesisinin puantaj kayıtları |
| İzin (HCM) | İzin ve uzaktan çalışma kayıtları |

**Program hiçbir şey tahmin etmez.** Eksik bir kayıt uydurulmaz, eşleşmeyen bir isim
tahmin edilmez. Karar veremediği her şeyi rapora yazar ve insana bırakır.

---

## 2. Bir günün çalışma süresi nasıl hesaplanıyor

**Günün ilk girişinden son çıkışına kadar geçen süre.**

```
08:12 giriş → 12:30 çıkış → 13:15 giriş → 18:40 çıkış
Çalışma süresi: 08:12'den 18:40'a = 10 saat 28 dakika
```

İki önemli sonuç:

- **Gün içindeki boşluklar düşülmez.** Yukarıdaki 45 dakikalık ara sayılır.
- **Öğle arası için kesinti uygulanmaz.**

Bu iki karar birlikte alındı: kartın gösterdiği gün, bordronun kullanacağı gündür.
Program çalışanın binada olmadığı bir süreyi kendi kararıyla düşmez.

### İki tesiste birden kaydı olanlar

76 kişi hem Macunköy hem Teknopark dosyasında görünüyor. Bunlar aynı kişinin aynı
günü: Teknopark'ta çalışan biri gün içinde Macunköy'e gidiyor.

**İki dosya toplanmaz, birleştirilir.** Çakışan süre bir kez sayılır.

```
Teknopark : 07:09 → 19:45
Macunköy  : 13:20 → 14:10   (Teknopark saatlerinin içinde)
Sonuç: 12 saat 36 dakika — 50 dakika ikinci kez sayılmaz
```

---

## 3. Neler çalışma sayılıyor

| Kayıt türü | Sayılır mı | Neden |
| --- | --- | --- |
| Kart okuması | ✅ | Asıl kaynak |
| Teknopark'ın yazdığı varsayılan `09:00–18:00` gün | ✅ | Kart verisi olmayan iş gününe sistem bunu yazıyor; kaynak dosya da çalışma sayıyor |
| `Uzaktan Çalışma` izni | ✅ | Uzaktan çalışma izin değil, çalışmadır. Kaydında gerçek saat var |
| Yıllık izin, mazeret, rapor, doğum günü izni | ❌ | İzin, çalışma değil |

**Uzaktan çalışma günü, sistemin varsayılan gününün yerine geçer.** Aynı gün için hem
uzaktan çalışma beyanı hem sistemin `09:00–18:00`'i varsa, uzaktan çalışmanın gerçek
saatleri kullanılır. Ama **gerçek bir kart okumasının yerine asla geçmez** — kişi
gerçekten binaya girmişse o kayıt esastır.

---

## 4. Hangi günler iş günü sayılıyor

Hafta içi günler, resmi tatiller çıkarılarak. Cumartesi ve pazar iş günü değil.

Mayıs 2026'da 7 resmi tatil var. **Bu tatil listesi verilerden çıkarıldı, İK
onaylamadı** — raporun `Kontrol` sayfasında tek tek listeleniyor.

---

## 5. Raporun düştüğü notlar

Her notun bir **ağırlığı** var:

| Renk | Anlamı |
| --- | --- |
| 🔴 Kırmızı | O gün **0 saat** sayıldı — gerçek bir kayıp |
| 🟡 Sarı | Sayıldı, ama kontrol edilmeli |
| ⚪ Gri | Sayıldı, **beklenen durum** — kimsenin sorunu değil |

### Eksik kayıt

| Not | Ne demek | Ağırlık |
| --- | --- | --- |
| `Giriş yok` | Çıkış basılmış, giriş kaydı yok | 🔴 |
| `Çıkış yok` | Giriş basılmış, çıkış kaydı yok | 🔴 |
| `Giriş-çıkış yok` | Satır var ama iki saat de boş | 🔴 |
| `Mesai verisi yok` | Dönem boyunca hiç kart kaydı yok | 🔴 |
| `Ay büyük ölçüde boş` | Çalışma + izin, iş günlerinin **yarısından azını** açıklıyor | 🟡 |

`Ay büyük ölçüde boş` şunun için var: bir kişinin tek bir normal 9 saatlik günü ve 21
eksik günü olabiliyor. Günü normal olduğu için günlük kural, kaydı olduğu için
"hiç veri yok" kuralı çalışmıyordu; bu kişiler hiçbir not almadan sorunsuz listede
duruyordu.

> **Bu not, kişi hakkında bir iddia değildir.** Personel listesinde işe giriş ve çıkış
> tarihi bulunmadığı için program, ay ortasında işe başlayan biriyle kayıtları eksik
> olan birini ayırt **edemiyor**. Not, "buna bakılmalı" demektir.

### Süre

| Not | Ne demek | Ağırlık |
| --- | --- | --- |
| `Süre çok kısa` | Günlük toplam **2 saatin** altında | 🟡 |
| `Aralık çok uzun` | Tek bir giriş-çıkış **16 saati** aşıyor | 🔴 |
| `Gece geçişi` | Çıkış girişten önce görünüyor; gece yarısını geçen vardiya düzeltildi | 🟡 |
| `Süre uyuşmazlığı` | Hesaplanan süre, kaynak dosyanın kendi yazdığı süreyle aynı değil | 🟡 |

### Uzaktan çalışma

| Not | Ne demek | Ağırlık |
| --- | --- | --- |
| `Uzaktan + sistem kaydı` | Uzaktan çalışma günü; Teknopark'ta kart okuması yok, sistem varsayılan tam gün yazmış. Sistemin günü yerine uzaktan saatler sayıldı | ⚪ |
| `Uzaktan + kart kaydı` | Uzaktan çalışma beyanı var **ama o gün gerçek kart okuması da var** — kişi binaya girmiş görünüyor | 🟡 |
| `Uzaktan + sistem + ek kayıt` | Uzaktan gün; sistemin varsayılan günü dışında başka bir kart kaydı daha var, bu yüzden değiştirme yapılmadı | ⚪ |
| `Çok günlü uzaktan` | Tek izin satırı birden çok güne yayılmış, günlere bölündü | 🟡 |

### Diğer

| Not | Ne demek | Ağırlık |
| --- | --- | --- |
| `Tesis birleştirme` | Eksik kayıt, kişinin aynı gün diğer tesisteki kaydıyla tamamlandı | 🟡 |
| `İsim eşleşmedi` | Personel listesinde bu ismin karşılığı bulunamadı | 🔴 |
| `Satır okunamadı` | Kaynak dosyadaki satır ayrıştırılamadı | 🔴 |

---

## 6. Eşiklerin tam listesi

| Eşik | Değer | Neyi ölçer |
| --- | --- | --- |
| Günlük kısa süre | 2 saat | Bir günün toplamı |
| Aralık üst sınırı | 16 saat | Tek bir giriş-çıkış |
| Ay kapsama oranı | %50 | Çalışma + izin ÷ beklenen iş günü |
| Sistemin varsayılan günü | `09:00–18:00` | Teknopark'ın kart verisi olmayan güne yazdığı saat |
| Öğle arası kesintisi | Yok | — |
| Hafta tatili | Cumartesi, Pazar | — |

---

## 7. İsimler nasıl eşleştiriliyor

**Kart numarası kullanılmıyor** — aynı kişinin numarası iki sistemde farklı olabiliyor
ve Teknopark dosyasında numara kolonu hiç yok. Eşleştirme **isim üzerinden**.

Dokuz kişinin adı sistemler arasında farklı yazılmış (Türkçe karakter farkı, evlilik
soyadı, kısaltılmış ad). Bunlar elle hazırlanmış bir eşleştirme tablosunda tutuluyor.
**Benzerlik tahmini yapılmaz** — eşleşmeyen isim tahmin edilmez, rapora yazılır.

Kullanılan eşleştirmeler raporun `Kontrol` sayfasında tek tek listeleniyor, İK
onaylayabilsin diye.

---

## 8. Personel listesi hakkında

- **Kayıt defteridir, beyaz liste değildir.** Listede olmayıp mesai kaydı olan biri
  yine çalışmıştır, raporda yer alır, saatlerini korur.
- **Kimin var olduğuna karar vermez.** Listede olup dönemde hiç hareketi olmayan
  kişiye satır açılmaz.
- **Alınma tarihi önemlidir** ve rapora yazılır. Mayıs raporunda kullanılan liste
  28.07.2026'da alınmış, yani dönemden 2 ay sonra: ayrılanlar listede görünmez,
  sonradan girenler mesai verisinde yoktur.

---

## 9. Rapor eksikse ne oluyor

Kaynak dosyalardan biri ayın tamamını kapsamıyorsa program bunu **raporun en üstünde
kırmızıyla yazar** ve hata koduyla çıkar.

Temmuz 2026 böyle: Teknopark dosyası ayın yalnızca 1–19'unu kapsıyor. O rapordaki
saatler bordro için kullanılamaz.

Ayrıca seçilen dosyalardan birinin **bütün kayıtları başka bir aya aitse** rapor
üretilmez; hangi dosya, beklenen aralık ve dosyadaki aralık yazılır.

---

## 10. Henüz yapılmayanlar

Bunlar bilinçli olarak ertelendi, İK'nın cevaplaması gereken sorular var:

- **Fazla mesai hesabı** — günlük normal çalışma süresinin kaç saat olduğu onaylanmadı
- **Vardiya tespiti**
- **Multinet hak edişi**
- **Tatil çalışması ücreti**
- **Kişilere otomatik e-posta gönderimi** — kişi seçme ekranı hazır, gönderim yok

---

## 11. Nerede yazılı

| Ne | Nerede |
| --- | --- |
| Eşikler ve kurallar (değiştirilebilir) | `config/settings.yaml` |
| Her koşunun kullandığı varsayımlar | Raporun `Kontrol` sayfası |
| Kararların gerekçeleri | `docs/DECISIONS.md` |
| Hesabın ayrıntısı | `docs/DOMAIN-RULES.md` |

**Raporun `Kontrol` sayfası her ay kendi kendini anlatır:** o koşuda hangi dosyalar
okundu, kaç satır işlendi, hangi isim eşleştirmeleri uygulandı, hangi tesis adları
kullanıldı, hangi varsayımlar onaylanmadı. Bir sayı sorgulandığında ilk bakılacak yer
orasıdır.
