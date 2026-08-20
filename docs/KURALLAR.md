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
| Diğer bütün izin türleri | ❌ | İzin, çalışma değil |

Üç ayda (Mayıs–Temmuz 2026) izin dosyasında görülen **on iki** tür:
`Yıllık İzin`, `Uzaktan Çalışma`, `Mazeret`, `Eğitim İzni`, `Doğum Günü İzni`,
`İstirahat (Raporlu)`, `Doğum İzni (Tam Ödeme)`, `Babalık İzni`, `Ücretsiz İzin`,
`Ücretli İzin`, `Evlilik İzni`, `Cenaze İzni`.

**`Uzaktan Çalışma` dışında hepsi izin sayılır — `Eğitim İzni` dahil. İK bunu
onayladı.** Liste kapalıdır: yeni bir türün çalışma sayılması ayrı bir karar gerektirir.

Bir izin türü "çalışma" olabilir diye düşündürten şey, kayıtlarında saat bulunması
olmuştu. Ama **her izin türünün her satırında saat var** — yıllık izin dahil. O saat
iznin başlangıç/bitiş saati, kişinin işte olduğunun kanıtı değil.

Türler ay ay değişiyor: Temmuz'da `Ücretli İzin`, `Evlilik İzni` ve `Cenaze İzni` ilk
kez göründü. Karara bağlanmamış bir tür izin sayılır; kişinin ayı kısa görünür ve not
alır, sessizce saat kazanmaz.

`Uzaktan Çalışma` çift sayılmaz: saat olarak çalışmaya, gün olarak
`Uzaktan Çalışma (Gün)` kolonuna girer — `İzin Günü` kolonuna girmez.

**Uzaktan çalışma günü, sistemin varsayılan gününün yerine geçer.** Aynı gün için hem
uzaktan çalışma beyanı hem sistemin `09:00–18:00`'i varsa, uzaktan çalışmanın gerçek
saatleri kullanılır. Ama **gerçek bir kart okumasının yerine asla geçmez** — kişi
gerçekten binaya girmişse o kayıt esastır.

---

## 4. Hafta sonu ve resmi tatil çalışması

**Hafta sonu ve resmi tatilde yapılan çalışma tam olarak sayılır.** Kaydı varsa
toplamdadır; hiçbir gün türü göz ardı edilmez.

Mayıs 2026'da ölçülen:

| | Kişi-gün | Saat | Kişi |
| --- | --- | --- | --- |
| İş günü | 1 752 | 16 614:24 | 145 |
| Hafta sonu | 30 | **164:31** | 20 |
| Resmi tatil | 41 | **325:01** | 21 |
| **Toplam** | **1 823** | **17 103:58** | |

`Günlük Detay` sayfasında her satır hangi güne ait olduğunu yazar: `Cmt`, `Paz` ya da
`Resmi Tatil`. Yani hafta sonu çalışması hem sayılır hem de ayırt edilebilir.

### Tatil listesi nereden geliyor

**İK vermedi.** Şu an iki kaynağı var:

| Tür | Nereden | Örnek |
| --- | --- | --- |
| Sabit tarihli resmi tatiller | **Kanun** — her yıl aynı, yılın tamamı yazılı | 1 Ocak, 23 Nisan, 1 Mayıs, 19 Mayıs, 15 Temmuz, 30 Ağustos, 29 Ekim |
| Dini bayramlar ve köprü günleri | **Veriden çıkarıldı**, onay bekliyor | Kurban Bayramı bloğu (25–29 Mayıs 2026) |

Dini bayramlar her yıl kayar, yani kanundan hesaplanamaz; o ayı çalıştırmadan önce
elle girilmesi gerekir. Bir ayda hiç tatil tanımlı değilse rapor bunu `Kontrol`
sayfasında turuncuyla yazar — sessiz kalmaz, çünkü sessizlik "tatil yoktu" gibi okunur.

15 Temmuz 2026 bir süre listede yoktu ve kimse fark etmedi: kimsenin saati yanlış
değildi, sadece iki kişi haksız yere "ayı boş" diye işaretlenmişti. Veri o günü tek
başına gösteriyordu — hafta içi ortanca 130 kişi, o gün 7 kişi.

### Program tatil olabilecek günleri kendisi soruyor

Takvimde olmayan ama **neredeyse kimsenin gelmediği** bir iş günü varsa, rapor bunu
`Kontrol` sayfasında sayılarıyla sorar:

> `15.07.2026  Çar  —  7 kişi, o ayın normal günü 130 kişi (%5)`

**Program bunu kendisi tatil olarak işaretlemez.** Bir günün neden boş olduğunu — resmi
tatil mi, şirket kapalı mıydı, başka bir şey mi — yalnızca insan bilir, ve Faz 2'de
resmi tatil ile şirket kapanması farklı ücretlenecek. Program tahmin etmez, sorar.

Eşik: o ayın normal gününün **%35'i**. Bu sayı ölçümden geliyor — üç ayda tatil olduğu
bilinen sekiz günün hepsi %2–14 arasında, tatil olmayan en boş gün ise %72. Aradaki
boşluğa hiçbir gün düşmüyor.

Bu soru bir **gün** hakkındadır, kişi hakkında değil — yani kimsenin satırına not
düşmez. Şirketin kapalı olduğu bir gün için yirmi kişiye not düşmek, gerçekten kişiyle
ilgili olan notları gömerdi.

### "İş günü" kavramı nerede kullanılıyor

Program bir de "beklenen iş günü" sayısı tutar — hafta içi günler, resmi tatiller
çıkarılmış hâli. Bu sayı **çalışma süresini etkilemez.** Yalnızca iki yerde kullanılır:

1. **Kaynak dosya ayın tamamını kapsıyor mu** kontrolünde (bkz. bölüm 9).
2. **`Ay büyük ölçüde boş`** notunun paydası olarak.

Hafta sonu çalışması bu paydayı büyütmez, yani hafta sonu çalışan biri bu yüzden
haksız yere işaretlenmez.

Tatil listesinin saatlere dokunduğu **tek** yer var: **birden fazla günü kapsayan**
bir uzaktan çalışma beyanı güne bölünürken tatiller atlanır. Kart basan kimsenin
saatine hiçbir tatil dokunmaz.

### Henüz yapılmayan

Hafta sonu ve resmi tatil çalışması **saat olarak sayılıyor ama farklı ücretlendirilmiyor** —
tatil çalışmasının ücret ya da izin karşılığı henüz karara bağlanmadı. Bkz. bölüm 10.

Kullanılan resmi tatil listesi raporun `Kontrol` sayfasında tarih tarih yazılıdır.

---

## 5. Raporun düştüğü notlar

Her notun bir **ağırlığı** var:

| Renk | Anlamı |
| --- | --- |
| 🔴 Kırmızı | O gün **0 saat** sayıldı — gerçek bir kayıp |
| 🟡 Sarı | Sayıldı, ama kontrol edilmeli |
| ⚪ Gri | Sayıldı, **beklenen durum** — kimsenin sorunu değil |

Aşağıdaki liste programın üretebileceği **bütün** notları içerir. Bazıları bugüne kadar
hiç görülmedi; onlar `—` ile işaretli. Bunlar boşuna durmuyor: her biri programın bir
şeyi **uydurmak zorunda kalacağı** ya da **okuyamayacağı** durumu karşılıyor, ve o
durum çıktığında sessizce geçilmesin diye tanımlı.

Sayılar Mayıs, Haziran ve Temmuz 2026'nın toplamıdır (kişi-gün).

### Eksik kayıt

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Giriş yok` | Çıkış basılmış, giriş kaydı yok | 🔴 | 78 |
| `Çıkış yok` | Giriş basılmış, çıkış kaydı yok | 🔴 | 526 |
| `Giriş-çıkış yok` | Satır var ama iki saat de boş | 🔴 | 206 |
| `Mesai verisi yok` | Dönem boyunca hiç kart kaydı yok | 🔴 | 75 |
| `Ay büyük ölçüde boş` | Çalışma + izin, iş günlerinin **yarısından azını** açıklıyor | 🟡 | 50 |

`Ay büyük ölçüde boş` şunun için var: bir kişinin tek bir normal 9 saatlik günü ve 21
eksik günü olabiliyor. Günü normal olduğu için günlük kural, kaydı olduğu için
"hiç veri yok" kuralı çalışmıyordu; bu kişiler hiçbir not almadan sorunsuz listede
duruyordu.

> **Bu not, kişi hakkında bir iddia değildir.** Personel listesinde işe giriş ve çıkış
> tarihi bulunmadığı için program, ay ortasında işe başlayan biriyle kayıtları eksik
> olan birini ayırt **edemiyor**. Not, "buna bakılmalı" demektir.

### Süre

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Günlük süre çok kısa (<2 saat)` | Günün toplamı 2 saatin altında | 🟡 | 61 |
| `Günlük süre çok uzun (>16 saat)` | Günün toplamı 16 saati aşıyor — **süre sayılır**, sadece kontrol için işaretlenir | 🟡 | 7 |
| `Gece geçişi` | Çıkış girişten önce görünüyor; gece yarısını geçen vardiya düzeltildi | 🟡 | 51 |
| `Giriş-çıkış tutarsız` | Çıkış girişten önce ve gece geçişi varsayılınca süre 20 saati aşıyor — kayıt kullanılamaz | 🔴 | 5 |
| `Süre uyuşmazlığı` | Hesaplanan süre, kaynak dosyanın kendi yazdığı süreyle aynı değil | 🟡 | — |

**Uzun gün sayılır, atılmaz.** 16 saati aşan bir gün gerçek olabilir; program onu
toplamdan çıkarmaz, sadece "buna bakın" der.

Atılan tek şey **kendi içinde tutarsız** kayıt: çıkışı girişten önce yazılmış olan.
Program böyle bir kaydı görünce "gece yarısını geçmiş" varsayıp 24 saat ekler — ve bu
varsayım **programın kendi tahminidir**. Tahmin 20 saati aşan bir sonuç veriyorsa
tahmin yanlıştır, kayıt kullanılmaz.

### Gece vardiyaları neden karışmıyor

Gerçek gece vardiyaları düzeltmeden sonra 9–10 saat çıkıyor (Mayıs–Haziran'da en uzunu
15:36). Atılan kayıtlar ise giriş ile çıkışı **dakikalar hatta saniyeler** arayla olan
kayıtlar; 24 saat eklenince neredeyse tam güne çıkıyorlar (21:56, 23:58, 23:59).

Sınır 20 saat — en uzun gerçek vardiyanın 4,5 saat üstünde, en kısa bozuk kaydın
2 saat altında.


### Uzaktan çalışma

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Uzaktan + sistem kaydı` | Uzaktan çalışma günü; Teknopark'ta kart okuması yok, sistem varsayılan tam gün yazmış. Çakışan süre bir kez sayıldı | ⚪ | 110 |
| `Uzaktan + kart kaydı` | Uzaktan çalışma beyanı var **ama o gün gerçek kart okuması da var** — kişi binaya girmiş görünüyor | 🟡 | 10 |
| `Çok günlü uzaktan` | Tek uzaktan çalışma satırı birden çok güne yayılmış. Kaynak günlük saati yazmadığı için **program normal vardiya saatini varsayar** — bu yüzden işaretlenir | 🟡 | — |

`Çok günlü uzaktan` bugüne kadar hiç görülmedi ama önemli: izin dosyası tek satırda
birden çok gün bildirirse, o satırda **günlük saat yazmıyor**. Program normal vardiya
saatini (07:30–16:30) varsayarak günlere böler — yani bir şey **uydurur**. Böyle bir
satır çıktığında sessizce geçilmesin diye bu not var.

Uzaktan çalışmayla ilgili tek soru şu: **o gün gerçekten kart basılmış mı?** Basılmamışsa
beklenen durum (⚪), basılmışsa bakılması gereken bir çelişki (🟡). Programın bu iki
durumu içeride nasıl işlediği `Şüpheli Kayıtlar` sayfasındaki açıklama satırında yazar.

### Diğer

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Tesis birleştirme` | Eksik kayıt, kişinin aynı gün diğer tesisteki kaydıyla tamamlandı | 🟡 | 52 |
| `İsim eşleşmedi` | Personel listesinde bu ismin karşılığı bulunamadı | 🔴 | — |
| `Satır okunamadı` | Kaynak dosyadaki satır ayrıştırılamadı | 🔴 | — |

---

## 6. Eşiklerin tam listesi

| Eşik | Değer | Neyi ölçer |
| --- | --- | --- |
| Günlük kısa süre | 2 saat | Bir günün toplamı |
| Günlük uzun süre | 16 saat | Bir günün toplamı (işaretlenir, çıkarılmaz) |
| Düzeltme üst sınırı | 20 saat | Gece geçişi varsayımı bunu aşarsa kayıt kullanılmaz |
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

Kullanılan eşleştirmeler raporun `Kontrol` sayfasında tek tek listeleniyor, tek tek
kontrol edilebilsin diye.

---

## 8. Personel listesi hakkında

Rapor **dört** dosyayla çalışır ve dördüncüsü personel listesidir. Saatleri
etkilemez — onu çıkarsanız toplam süre bire bir aynı kalır, kimse eksilmez. Sağladığı
şey kişiye dair bilgidir:

| Alan | Haziran 2026 | Başka kaynağı var mı |
| --- | --- | --- |
| **E-posta** | 154 kişi | **Yok** — hiçbir mesai dosyasında e-posta kolonu yok |
| **Tesis** | 154 kişi | Yok |
| **Görev** | 154 kişi | Yok |
| Departman | 162 kişi | Var, mesai dosyalarında da geçiyor |

E-posta yalnızca burada olduğu için, kişilere kendi saatlerini göndermek bu liste
olmadan mümkün değil.

Listede olmayan 9 kişi, ayrılmış olanlar — onların e-postası da yok.

**Listeyi bir kez göstermeniz yeterli.** Aya bağlı olmadığı için pencere seçiminizi
hatırlar; dosya yerinde durduğu sürece her ay yeniden seçmeniz gerekmez. Yerini
değiştirirseniz pencere bunu fark eder ve listede yazar.


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

## 10. Uzaktan çalışmada açık kalan sorular

Hesap çalışıyor ama iki şey henüz karara bağlanmadı:

| Soru | Durum | Etkisi |
| --- | --- | --- |
| Uzaktan beyanı olup **kart da basanlar** | Sayılıyor ve işaretleniyor (3 ayda 10 gün) | Beyan mı geçerli, kart mı? Şu an ikisi birleştiriliyor |
| Teknopark neden `09:00–18:00` yazıyor? | Çalışma sayılıyor | Raporun yaklaşık **%17'si** bu satırlardan geliyor. "Bordroda ödenmiyor" denirse ciddi düşüş demek |

---

## 11. Henüz yapılmayanlar

Bunlar bilinçli olarak ertelendi; kuralları henüz karara bağlanmadı:

- **Fazla mesai hesabı** — günlük normal çalışma süresinin kaç saat sayılacağı belli değil
- **Vardiya tespiti**
- **Multinet hak edişi**
- **Hafta sonu ve resmi tatil çalışmasının karşılığı** — saatler sayılıyor, ücret
  ya da izin karşılığı hesaplanmıyor
- **Kişilere otomatik e-posta gönderimi** — kişi seçme ekranı hazır, gönderim yok

---

## 12. Nerede yazılı

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
