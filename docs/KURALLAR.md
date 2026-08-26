# Mesai Raporu — Hesaplama Kuralları

**Bu belge, raporun sayılarının nasıl çıktığını teknik bilgi gerektirmeden anlatır.**
Rapordaki bir sayıyı sorgulayan herkese gösterilebilir.

Buradaki her eşik programın ayar dosyasında (`config/settings.yaml`) yazılıdır ve
değiştirilebilir. Bir kural değişirse bu belge de değişir; ikisi birlikte
güncellenir.

> **Bu rapor bir doğrulama koşusudur, bordro için nihai değildir.** Fazla mesai,
> vardiya ve Multinet hesapları henüz yapılmıyor — bkz. "Henüz yapılmayanlar".

---

## 1. Program ne yapıyor

Her ay iki tesisten gelen ham kart okuyucu çıktıları ile izin dosyasını okur,
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

**`Uzaktan Çalışma` dışında hepsi izin sayılır — `Eğitim İzni` dahil.** Liste kapalıdır: yeni bir türün çalışma sayılması ayrı bir karar gerektirir.

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
`Tatil`. Yani hafta sonu çalışması hem sayılır hem de ayırt edilebilir.

### Tatil listesi nereden geliyor

**Programı kullanan kişi işaretler.** Başka bir kaynağı yok: program hiçbir günü
kendisi tatil yapmaz, hiçbir öneri göstermez, hiçbir yerden tatil listesi çekmez.

Takvimde tarihlerden başka bir şey tutulmaz — hangi bayram olduğu, kanundan mı geldiği,
şirketin kararı mı olduğu yazılmaz. Hesap açısından hepsi aynı: o gün çalışılmıyor.

### Tatil günleri programa nasıl giriliyor

Pencerede **Takvim** ekranı var. Ayın günleri ızgara halinde duruyor; bir güne tıklamak
onu **tatil** yapıyor, tekrar tıklamak iş gününe döndürüyor. Hafta sonlarına
tıklanamıyor, zaten tatil.

**Tek tür var: tatil.** Bir gün ya çalışılan gündür ya tatildir. Resmi tatil ile
şirketin kapandığı gün program açısından aynı şey — ikisi de günü beklenen iş
günlerinden çıkarır — o yüzden ayrı kategori tutulmuyor.

Günün **ne olduğu** yine yazılı: takvimde her tarihin yanında adı duruyor
(`Emek ve Dayanışma Günü`, `Toplu İzin (köprü)`), ve `Kontrol` sayfasında tarih tarih
görünüyor. Yani "bu gün kanundan mı geliyor, sizin kararınız mı" sorusu hâlâ
cevaplanabilir; sadece programın hesabında bir farkı yok.

Kaydetmek, takvim dosyasını günceller. **Kaydettikten sonra raporu yeniden üretmek
gerekir** — saatler o dosyaya göre hesaplanır. Tıklamak tek başına hiçbir rakamı
değiştirmez; ekran da bunu söylüyor.

### "İş günü" kavramı nerede kullanılıyor

Program bir de "beklenen iş günü" sayısı tutar — hafta içi günler, resmi tatiller
çıkarılmış hâli. Bu sayı **çalışma süresini etkilemez.** Yalnızca iki yerde kullanılır:

1. **Kaynak dosya ayın tamamını kapsıyor mu** kontrolünde (bkz. bölüm 9).
2. **Hangi günlerin kaydı beklenir** sorusunda: `Hem giriş hem çıkış yok` notu yalnızca
   beklenen iş günleri için düşer, hafta sonu ve tatiller için düşmez.

Tatil listesinin saatlere dokunduğu **tek** yer var: **birden fazla günü kapsayan**
bir uzaktan çalışma beyanı güne bölünürken tatiller atlanır. Kart basan kimsenin
saatine hiçbir tatil dokunmaz.

Bir gün tatil olarak işaretlenmezse program bunu fark etmez — o gün beklenen iş günü
sayılır. Bu, işaretlemeyi yapan kişinin sorumluluğunda.

### Henüz yapılmayan

Hafta sonu ve resmi tatil çalışması **saat olarak sayılıyor ama farklı ücretlendirilmiyor** —
tatil çalışmasının ücret ya da izin karşılığı henüz karara bağlanmadı. Bkz. bölüm 10.

Kullanılan resmi tatil listesi raporun `Kontrol` sayfasında tarih tarih yazılıdır.

---

## 5. Raporun düştüğü notlar

`Aylık Özet` sayfasındaki `Not` kolonu, o kişinin notlarını **aynı kelimelerle** yazar —
pencerede filtre olarak seçtiğin, `İnceleme Listesi`'nde ve `Şüpheli Kayıtlar`'da
gördüğün adlarla birebir aynı. Sorunu olan herkesin notu vardır; boş bir `Not` hücresi
"bu kişide bir şey yok" demektir.

Tek istisna `Personel listesinde yok`: bu bir sorun değil, personel listesiyle ilgili bir
bilgi. O kişi çalışmıştır ve bütün saatlerini alır.

`Günlük Detay` sayfasındaki `Etiket` kolonu da aynı kelimeleri kullanır. Karşılığı olmayan
iki tanesi şunlar:

| Etiket | Ne demek |
| --- | --- |
| `İki tesisin kaydı çakışıyor` | Kişi aynı saatlerde iki tesisin dosyasında da var; süre bir kez sayıldı |
| `Eksik kayıt diğer tesisten tamamlandı` | Giriş ya da çıkışı eksikti, diğer tesisin kaydıyla tamamlandı |

Her notun bir **ağırlığı** var:

| Renk | Anlamı |
| --- | --- |
| 🔴 Kırmızı | O gün **0 saat** sayıldı — gerçek bir kayıp |
| 🟡 Sarı | Sayıldı, ama kontrol edilmeli |
| ⚪ Gri | Sayıldı, **beklenen durum** — kimsenin sorunu değil |

**Renk ile "kime sorulacak" ayrı şeyler.** Sarı bir not "gün sayıldı" der, ama o gün
hakkında sorulacak bir şey olduğu anlamına da gelir — pencerede işaretlendiğinde kişileri
getirir. Bir süre getirmiyordu: `Gece geçişi` panelde 6 kişi yazarken filtrede kimse
çıkmıyordu, çünkü filtre yalnızca **saat kaybedilmiş** günleri seçiyordu ve bu notların
öyle bir günü hiç yok. Düzeltildi. Kırmızı notlarda kural aynı kaldı: `Çıkış yok`
işaretlendiğinde, girişi bir tesisten çıkışı diğerinden okunup gün zaten tam sayılmışsa o
gün listeye girmez — sorulacak bir şey yok.

Aşağıdaki liste programın üretebileceği **bütün** notları içerir. Bazıları bugüne kadar
hiç görülmedi; onlar `—` ile işaretli. Bunlar boşuna durmuyor: her biri programın bir
şeyi **uydurmak zorunda kalacağı** ya da **okuyamayacağı** durumu karşılıyor, ve o
durum çıktığında sessizce geçilmesin diye tanımlı.

Sayılar Mayıs, Haziran ve Temmuz 2026'nın toplamıdır (kişi-gün) ve **2026-08-26'da
üç raporun `Şüpheli Kayıtlar` sayfasından ölçüldü.** Bir not birden çok gün için düşebilir,
o yüzden bu sayılar toplanmaz — aynı gün iki notta birden görünebilir.

### Eksik kayıt

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Giriş yok` | Çıkış basılmış, giriş kaydı yok | 🔴 | 63 |
| `Çıkış yok` | Giriş basılmış, çıkış kaydı yok | 🔴 | 369 |
| `Hem giriş hem çıkış yok` | O gün için ne giriş ne çıkış kaydedilmiş: ya saatleri boş bir satır var, ya o güne ait hiç satır yok. İzin ve uzaktan çalışma da yok. **Koşulsuz** — ay içinde işe girmiş olabilecekler de listeye girer, kararı veren kişi çıkarır | 🔴 | 798 |
| `Kart bilgisi yok` | **Ayın hiçbir gününde** kart kaydı yok. Kişi dosyalarda yalnızca izin ya da personel kaydıyla görünüyor | 🔴 | 66 kişi |

`Kart bilgisi yok` satırındaki sayı **kişidir, kişi-gün değil**: bu not ayın tamamı
hakkında, tek bir gün hakkında değil, o yüzden bir tarihi yok.

Bu notu alan kişinin **satırı vardır** ve raporda görünür. Satırı hiç açılmayan bir grup
daha var — personel listesinde olup o ayda ne kart ne izin kaydı bulunanlar; onlar
`Kontrol` sayfasının `Kapsam` bölümünde sayılıyor (bölüm 8'e bakın).

`Hem giriş hem çıkış yok` notu, o gün için hiçbir yerde kayıt olmaması hâlinde de düşer.
Böylece tek bir normal 9 saatlik günü ve 21 kayıtsız günü olan biri de görünür — eskiden
günü normal olduğu için günlük kural, kaydı olduğu için "hiç veri yok" kuralı çalışmıyor
ve bu kişiler hiçbir not almadan sorunsuz listede duruyordu.

> **Bu not, kişi hakkında bir iddia değildir.** Personel listesinde işe giriş ve çıkış
> tarihi bulunmadığı için program, ay ortasında işe başlayan biriyle kayıtları eksik
> olan birini ayırt **edemiyor**. İkisini de listeler; hangisi olduğuna bakan kişi karar
> verir ve gerekiyorsa listeden çıkarır.

### Süre

| Not | Ne demek | Ağırlık | 3 ayda |
| --- | --- | --- | --- |
| `Günlük süre çok kısa (<2 saat)` | Günün toplamı 2 saatin altında | 🟡 | 50 |
| `Günlük süre çok uzun (>16 saat)` | Günün toplamı 16 saati aşıyor — **süre sayılır**, sadece kontrol için işaretlenir | 🟡 | 9 |
| `Gece geçişi` | Çıkış girişten önce görünüyor; gece yarısını geçen vardiya düzeltildi | 🟡 | 51 |
| `Giriş-çıkış tutarsız (>20 saat)` | Çıkış girişten önce ve gece geçişi varsayılınca süre 20 saati aşıyor — kayıt kullanılamaz | 🔴 | 5 |
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
| `Uzaktan + sistem kaydı` | Uzaktan çalışma günü; Teknopark'ta kart okuması yok, sistem varsayılan tam gün yazmış. Çakışan süre bir kez sayıldı | ⚪ | 190 |
| `Uzaktan + kart kaydı` | Uzaktan çalışma beyanı var **ama o gün gerçek kart okuması da var** — kişi binaya girmiş görünüyor | 🟡 | 12 |
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
| `Tesis birleştirme` | Eksik kayıt, kişinin aynı gün diğer tesisteki kaydıyla tamamlandı | 🟡 | 63 |
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
  kişiye satır açılmaz. Bu doğru: liste dönemden sonra alındığı için içinde o ay henüz
  işe başlamamış kişiler de var, ve onlara sıfır saatlik bir satır açmak çalışmadıklarını
  söylemek olur.

  **Ama kaç kişi olduğu raporda yazar.** `Kontrol` sayfasının `Kapsam` bölümü, personel
  listesinde olup o ayda **ne kart ne izin** kaydı bulunan kişileri sayar ve adlarını
  tesise göre gruplayarak yazar — Mayıs 21, Haziran 27, Temmuz 14 kişi. Sebebi şu: bu
  kişilerin satırı olmadığı için yukarıdaki bütün sayılar onları görmüyor, yani tek
  başına bırakıldığında bu grup hiçbir listede görünmüyordu. Kimin sonradan işe girdiğini
  program bilemiyor (listede işe giriş tarihi yok), o yüzden bir iddia değil, **elle
  bakılacak bir liste** olarak yazılıyor.
- **Alınma tarihi önemlidir** ve rapora yazılır. Mayıs raporunda kullanılan liste
  28.07.2026'da alınmış, yani dönemden 2 ay sonra: ayrılanlar listede görünmez,
  sonradan girenler mesai verisinde yoktur.

### Bir kişinin kaç sorunlu günü var

Pencerede kişinin yanındaki `Sorunlu gün` sayısı **o kişinin sayılmamış gün sayısıdır** ve
hangi notların işaretli olduğuna bağlı değildir. Temmuz'da 419 gün. Bir süre işaretlere
bağlıydı: tek not işaretliyken 127 gösteriyordu, varsayılanla 446 — ve o 446'nın 27'si
aslında **sayılmış** günlerdi. Bir kişiye ait bir olgu, bir kutucuğa bağlı olmamalı.

Sağdaki panel kişinin **bütün** sorunlu günlerini gösterir, iki blokta:

| Blok | Ne | İlk hâli |
| --- | --- | --- |
| (başlıksız, üstte) | O gün hiçbir yerde sayılmamış — gerçek kayıp | **işaretli** |
| `SAYILAN GÜNLER` | Süre sayıldı, kayıp yok | **işaretsiz** |

**İki tür gün panelde hiç görünmez**, çünkü ikisine de sorulacak bir şey yok:

- **İzin kapsayan günler.** Yıllık izindeki bir güne "neredeydin" diye sorulmaz. Ayda 2–3.
- **Günü başka bir kayıttan sayılmış eksik damgalar.** Bir tesiste satırın saatleri boş
  kalmış ama kişi o gün öteki tesiste kart basmış ve gün tam sayılmış — Temmuz'da 87 gün.
  Kişi kart basmış, sorulacak bir şey yok. Panelde `Hem giriş hem çıkış yok` yazarken
  yanında 9:05 süre görünüyordu; not o **kayıt** hakkında, süre ise **gün** hakkında.

İkisi de raporda duruyor: `Şüpheli Kayıtlar` o kayıt için `Bu kayıt sayılmadı; gün başka
kayıttan 9:05 sayıldı` yazıyor, `Günlük Detay` da hangi tesisin saydığını. Yani hiçbir şey
gizlenmiyor — sadece "kime soralım" listesinde yer almıyorlar.

İkinci blok teklif olarak duruyor: mesela gece vardiyası düzeltilmiş bir gün hakkında da
soru sorulabilir, ama o gün **sayıldığı için** kendiliğinden mesaja girmez. Girmesini
istiyorsanız tek tek işaretleyin. Sebebi basit: sayılmış bir gün için kişiye "eksik durum
tespit edilmiştir" yazmak doğru olmayan bir cümledir.

İşaretlerin işi **kimin listede olacağına** karar vermek; kişinin günlerinin ne olduğuna
karar vermek değil.

### Kişiye ne yazılıyor

Pencerede bir kişiyi seçip günlerini işaretledikten sonra o kişiye e-posta
gönderilebiliyor. Mesaj kısa ve içinde **yalnızca işaretlenen not** yazıyor:

```
Sayın <ad soyad>,

Temmuz 2026 dönemi giriş-çıkış kayıtları incelenmiştir.

Aşağıdaki günlerde kayıtlarınızda eksik ya da tutarsız bir durum tespit edilmiştir:

  · 03.07.2026 Cum — Çıkış yok (giriş 07:41, çıkış kaydı yok)
  · 14.07.2026 Sal — Çıkış yok (giriş 08:02, çıkış kaydı yok)

Yukarıdaki günlere ilişkin durumu bu e-postayı yanıtlayarak bildirmenizi rica ederiz.

İyi çalışmalar.
```

Üç şey bilerek böyle:

- **Aynı gün birden çok not taşıyabiliyor** ve mesajda yalnızca işaretlenen yazılıyor.
  Yoksa kişiye sorulmayan bir şey sorulmuş olur.
- **Her satırda o gün ne okunduğu yazıyor.** Eksik olan yarım tire ile değil kelimeyle
  söyleniyor ("çıkış kaydı yok"), çünkü bu mesaj bir kez, elde sayfa olmadan okunuyor.
- **Konuda sayı yok**, sadece ay ve yıl. Açılmadan okunan tek satırda bir sayı olması,
  mesajın konusunun o sayı olduğu izlenimi veriyordu.
- **Hiç kimse ve hiçbir birim adlandırılmıyor**, "onay bekleniyor" da denmiyor. Mesaj
  kayıtların ne gösterdiğini yazıp durumu sorar; kimin takip ettiği mesajın konusu değil.
- **Toplu gönderim yok.** Kişi kişi, ve gönderilmeden önce mesaj ekranda gösteriliyor.
  Ekranda görülen metin düzenlenebiliyor ve **giden, ekranda görünenin aynısı.** Geri
  alınamayan tek işlem bu olduğu için araya bir insan konuldu.

**Mail iki biçimde gidiyor.** HTML gösteren programlarda DEICO'nun bilgilendirme
maillerindeki biçim görünüyor: üstte başlık şeridi, altında tablo — `Tarih`, `Giriş`,
`Çıkış`, `Sebep` ve **boş bırakılmış `Açıklama`** kolonu. Kişi *Yanıtla*'ya basıp o
kolona, ilgili günün satırına açıklamasını yazıyor; Outlook masaüstü tabloyu yanıtın
içine alıyor ve hücreye yazmaya izin veriyor.

Tabloyu düzleştiren bir program (genellikle telefon uygulamaları) kullanan biri düz metni
görüyor, o da günü belirterek yanıtlamayı istiyor. İkisi aynı bilgiyi taşıyor; yalnızca
cevabın nasıl yazılacağı değişiyor, çünkü düz metinde doldurulacak bir tablo yok.

**Metin `config/mail-taslagi.yaml` dosyasında.** Değiştirmek için programı yeniden kurmak
gerekmiyor, dosyayı düzenleyip kaydetmek yeterli. Tanımadığı bir alan adı yazılırsa program
durup söylüyor — yanlış yazılmış bir alanla mail göndermiyor.

Adresi olmayan kişide alan boş geliyor ve elle yazılabiliyor — her ay 8 kişi böyle.
Yazılan adres hiçbir yere kaydedilmiyor, yalnızca o gönderim için geçerli.

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
