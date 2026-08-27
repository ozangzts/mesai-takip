# HANDOVER.md — Nerede kaldık

**Son güncelleme: 2026-08-26, commit `c5ba7d6`.**

> Bu dosya kalıcı bilgi tutmaz, sadece **akıştaki işi**, **beklenen cevapları** ve
> **tuzakları** tutar. Kalıcı olan her şey aşağıdaki dosyalarda ve onlar güncel:
>
> | Ne öğrenmek istiyorsan | Nereye bak |
> | --- | --- |
> | Nasıl çalışılır, tavizsiz kurallar | [AGENTS.md](../AGENTS.md) — **önce bunu oku** |
> | Neden böyle karar verildi (81 ADR) | [DECISIONS.md](DECISIONS.md) |
| **Programı kullanacak kişi için** | [KULLANIM.txt](../KULLANIM.txt) — sade Türkçe, exe ile birlikte gidiyor |
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

Faz 1 çalışıyor, **üç ayın üçü de tam**, **575 test geçiyor**.

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Toplam çalışma süresi | 17 103:58 | 27 166:19 | 26 233:17 |
| Kişi | 171 | 163 | 176 |
| Şüpheli kayıt | 365 | 622 | 689 |
| `Sorunu olanlar` | 83 | 73 | 88 |
| Mail listesine girecek gün | 216 | 352 | 419 |
| Panelde teklif edilen, işaretsiz gelen sayılan gün | 28 | 41 | 52 |
| **Listede olup hiç kaydı olmayan** (ADR-071) | 21 | 27 | 14 |

Üçü de `0` koduyla çıkıyor, mutabakat TAMAM, kapsama tam. Son satır yeni ve **hiçbir
satırı olmayan** kişileri sayıyor: personel listesinde var, o ayda ne kart ne izin kaydı
yok. `Kontrol` §5'te adlarıyla, tesise göre gruplu (ADR-071). Masaüstündeki üç ayın raporu ve
veri dosyası **`format_version` 11** ile güncel.

> Şüpheli kayıt 250/427/436'dan buraya çıktı ve **hiçbir saat değişmedi**. Sebebi
> ADR-060/061: kaydı hiç olmayan günler de artık işaretleniyor. O günlerde sayılacak bir
> şey yoktu, yalnızca hiç görünmüyorlardı. Sayıyı CLI çıktısından al — raporun
> `Şüpheli Kayıtlar` sayfasını satır sayarak ölçmek 3 satırlık alt notu da katıyor.

Çalıştırma: `arayuz.cmd` (pencere) ya da `rapor.cmd --ay 2026-07` (komut satırı).

**Pencerede üç ekran var:** Rapor, Kişiler, Takvim. Akış: klasörü seç → tatilleri
işaretle → raporu üret → Kişiler'den listeyi çıkar → **kişi kişi mail at**.

> `Sorunu olanlar` 75/73/85'ten **83/73/88**'e çıktı (ADR-072: günü sayılmış notlar artık
> kendi kişilerini getiriyor; panel 6 derken filtrenin 0 demesi hataydı). **Gün sayısı
> değişmedi ve değişmemesi gerekiyordu** — ADR-072 bir ara 238/380/446 yapmıştı, içine 27
> tane *sayılmış* gün karışmıştı. ADR-074 düzeltti: `Sorunlu gün` yalnızca **sayılmamış**
> günü sayıyor ve **işaretlerden bağımsız**. Hiçbir saat değişmedi.

**Kişiler ekranı iki panelli** (ADR-064): solda kişi listesi, sağda seçilen kişinin
sorunlu günleri gün gün, her biri seçilebilir. Adın solundaki kareye tıklamak kişiyi
listeden çıkarır; adın kendisine tıklamak günlerini açar.

**Sağdaki panel işaretlere bağlı değil** (ADR-074). Önce sayılmayan günler (işaretli
gelir), sonra `SAYILAN GÜNLER` başlığı ve altında süresi sayılmış günler — **işaretsiz**
gelirler, istenirse tek tek seçilir. `Sorunlu gün` kolonu yalnızca sayılmayanları sayar.
İşaretler **kimin listede olduğuna** karar verir, kişinin günlerinin ne olduğuna karar
vermez. **İki tür gün panelde hiç yok**, o yüzden `days_by_cost` bilerek bir bölünme
değil: izin kapsayan gün (ADR-075) ve **notu yalnızca "damga eksik" olan sayılan gün**
(ADR-076). İkincisi şu: tek taraflı damga aralık üretmiyor (ADR-067), yani günün süresi
varsa o günü **başka bir kayıt tamamen kapatmış** — kişi kart basmış, öteki tesiste. O
yüzden `Hem giriş hem çıkış yok` ile 9:05 aynı satırda çelişki oluyordu. İkisi de
`Şüpheli Kayıtlar` ve `İnceleme Listesi`'nde duruyor, kaydın akıbeti oraya ait.

Panelin altında **e-posta satırı** var: adres snapshot'tan dolu gelir, düzenlenebilir,
`E-posta gönder…` önizleme açar. Kişi kişi; toplu gönderme yok (ADR-073).

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

İşaretli notlar hem **kimi** hem **hangi günleri** seçer, ve **her not yalnızca kendi
günlerini getirir** (ADR-065, yönetici kararı). `Hem giriş hem çıkış yok` bir süre
`Giriş yok` / `Çıkış yok` seçimlerine de giriyordu (ADR-053); artık girmiyor. Üçü üç ayrı
soru: kaçta çıktın, kaçta geldin, o gün burada mıydın.

Temmuz'da not başına, **bekleyeni olan** kişi/gün: `Giriş yok` 15/23, `Çıkış yok` 31/143,
`Hem giriş hem çıkış yok` 44/343, `Günlük süre çok kısa` 2/2, `Kart bilgisi yok` 26 kişi
(günü yok, ay seviyesi).

**Artık her not kutu** (ADR-072). Günü sayılmış olanlar — Temmuz'da `Tesis birleştirme`
13 kişi/26 gün, `Gece geçişi` 6/21, `Uzaktan + kart kaydı` 5/5, `Günlük süre çok uzun`
4/5, `Giriş-çıkış tutarsız` 2/2 — bir süre metin satırıydı (ADR-069), çünkü işaretlenince
kimseyi getirmiyorlardı. O, notun özelliği değil **filtrenin hatasıydı**: `outstanding`
kuralı yalnızca kaybı olan günü seçiyor, bu notların ise hiç kayıp günü yok. Şimdi kendi
kişilerini getiriyorlar. `Günü sayılmayan` / `Günü sayılan` başlıkları duruyor — başlık
"hangisi saat kaybettirdi", sayı "kime sorabilirim" sorusunun cevabı.

Varsayılan ayarlarla mail listesi:

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Kişi | 75 | 73 | 85 |
| Mesaja girecek gün | 216 | 352 | 419 |
| **Adresi olmayan** | 8 | 8 | 8 |

Adreslerin tamamı `deico.com.tr`. Adresi olmayanlar **düşürülmez, bildirilir**
(`without_email`) — 30 kişilik bir listenin sessizce 22 olması kaçınılması gereken hata.

**Birinci karar verildi, ikisi duruyor** (ADR-073):

1. ~~Varsayılan davranış gönderim mi önizleme mi?~~ **İkisi de değil: kişi kişi, önizlemeli
   ve elle.** Gün panelinin altında adres alanı ve `E-posta gönder…` var; buton önizleme
   penceresi açıyor, pencerede hem adres hem konu hem gövde düzenlenebiliyor ve
   **ekranda ne varsa o gidiyor**. Toplu gönderme **yok** ve bir kontrol de sunmuyor —
   `sender.py`'de döngü kuran bir fonksiyon olmadığını test tutuyor.
2. Elle çıkarılan kişi kayda geçsin mi? ("kime gitmedi, neden") — **açık**
3. Eksik aydan mail atılsın mı? (`is_complete` bunu ayırt edebiliyor) — **açık**

İkisi de toplu gönderme hakkında, o yüzden ikisi de bunu bloke etmedi.

**Mail metni `config/mail-taslagi.yaml`'da, kodda değil** (ADR-078). Exe'ye geçileceği
için taşındı: koda gömülü metin ancak yeniden derlemeyle değişir. Metni değiştirmek artık
dosyayı düzenlemek. Tanınmayan bir alan adı ya da boş bir zorunlu alan programı durdurur
ve **gömülü yedek yoktur** — yedek olsa, düzenleyen kişi değişikliği göremez ve hangi
kopyanın kullanıldığını anlayamaz.

Taslak **HTML de taşıyor** ve mail `multipart/alternative` gidiyor: düz metin önce, HTML
sonra. Kişinin açıklama yazacağı **tablo hazır** — `html_gun_satiri`'ndaki son hücre boş
bırakıldı. Tabloyu değiştirmek dosya düzenlemesi, derleme değil. HTML alanlarını boşaltmak
düz metne döner.

> **Önizleme yalnızca düz metni çiziyor** — tkinter HTML çizemiyor. Tablonun kendisini
> görmek için penceredeki `HTML'i tarayıcıda gör` düğmesi var. Bu eksikti ve taslağı
> değiştirdikten sonra pencereye bakan operatöre "eski taslak duruyor" gibi göründü.
> **Gövdeyi düzenlersen HTML kısmı düşer:** eski metni taşıyan bir HTML parçası, okuyanın
> senin görmediğin bir şeyi okuması olurdu ve çoğu istemci tam o parçayı gösterir.

**Hiçbir test soket açamaz** — `conftest.py` bütün pakete `smtplib.SMTP`'yi kapatıyor.
Tedbir değil: *eksik* `gmail.yaml` raporlanıyor mu diye yazılmış bir test gerçeğini buldu
ve canlı mail gönderdi (`a@b.c`, bounce etti). Gönderim testleri `transport` kullanıyor.

**Gmail hesabı `config/gmail.yaml`'da**, git'e girmez (`personel.yaml` gibi — içinde giriş
bilgisi var). Anahtarlar `config/gmail.example.yaml`'da. **Uygulama şifresi** gerekiyor,
hesabın kendi şifresi değil: iki adımlı doğrulama açıkken Google 16 haneli ayrı bir şifre
üretiyor ve tek başına iptal edilebiliyor. Google onu dörtlü gruplar hâlinde gösteriyor;
boşlukları program kendisi atıyor, çünkü göründüğü gibi yapıştırılınca giriş başarısız
oluyor.

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

### 3. `.exe` paketi — **derlendi, temiz makinede denenmedi**

`derle.cmd` bütün işi yapıyor: testleri koşuyor, PyInstaller'ı çağırıyor, sonra teslim
klasörünü topluyor. Sonuç `dist\MesaiTakip\` — **bu klasörün tamamı** zip'lenip verilir,
23 MB.

```
dist\MesaiTakip\
  MesaiTakip.exe
  KULLANIM.txt          <- kullanacak kişi için, sade Türkçe
  config\               <- exe'nin YANINDA, içinde değil
  data\personel\        <- boş; personel listesi buraya, içinde açıklayan bir not var
  _internal\            <- Python ve kütüphaneler. Kullanıcı buraya hiç girmez.
```

> **İlk kurulumda çıkan tuzak:** `data\personel\` klasörü paketten çıkmıyordu ve
> "bulunamadı — 'personel' klasörüne konmalı" mesajı **olmayan bir yeri** işaret
> ediyordu. Üstelik `config\personel.yaml` neredeyse aynı ada sahip **başka** bir
> dosya. Mesaj artık düğmeyi gösteriyor (`sağdaki 'Seç…' ile gösterin`) ve klasör
> bir notla birlikte oluşturuluyor.

**Üç karar ve gerekçeleri:**

- **`--onedir`, `--onefile` değil.** Tek dosya her açılışta kendini geçici klasöre
  açıyor — tkinter uygulamasında her seferinde 3–8 saniye — ve antivirüs bu davranışa
  daha çok takılıyor. Klasör ~1 saniyede açılıyor. Bedeli: `MesaiTakip.exe` klasörün
  dışına çıkarılamaz, yanındaki dosyalara ihtiyacı var. `KULLANIM.txt` bunu iki yerde
  söylüyor.
- **`console=False`.** Pencere arayüzün kendisi; arkasında açılan siyah bir terminal,
  terminalin ne olduğunu bilmeyen birine bir şeyin ters gittiğini düşündürür. CLI ayrı
  giriş noktası ve pakete girmiyor.
- **UPX kapalı.** Sıkıştırma antivirüs tetikleyicisi ve kazancı bu boyutta anlamsız.

**`config/` neden dışarıda** — dördü de ayrı sebep: kural değişikliği YAML düzenlemesi
olmalı (AGENTS §6); Takvim ekranı `takvim-<yıl>.yaml`'a **yazıyor** (ADR-042), yani gerçek
ve yazılabilir bir dosya olmak zorunda; `gmail.yaml` bir giriş bilgisi ve derleme
yapmadan değiştirilebilmeli; `mail-taslagi.yaml` metin ve değişeceği belli (ADR-078).

> **PyInstaller 6 tuzağı:** `datas` listesine konan her şey `_internal\` altına gidiyor,
> program ise `config/`'i exe'nin **yanında** arıyor (`cli.program_dir`, donmuşken
> `Path(sys.executable).parent`). O yüzden `.spec` dosyasında `datas=[]` ve kopyalamayı
> `derle.cmd` yapıyor. Bunu atlarsan program açılır ve config bulamaz.

**Pakete girmeyen iki dosya, adıyla dışlanıyor** (glob'a güvenilmiyor: kazara çalışan bir
dışlama, biri yeni dosya ekleyince çalışmaz olur): `personel.yaml` gerçek isim yazımlarını,
`gmail.yaml` bir girişi taşıyor. Örnekleri gidiyor, gerçeklerini kuran kişi elle koyuyor —
temiz bir klonun zaten gerektirdiği aynı elle adım.

**Buradan yapılabilen en iyi vekil testi geçti.** Exe, `PATH` yalnızca
`C:\Windows\System32;C:\Windows` iken ve `PYTHONHOME`/`PYTHONPATH` boşaltılmışken de
açıldı. Yani DLL'ler `_internal`'dan yükleniyor, conda ortamından değil — bu makinede
conda zaten `PATH`'te değil (ölçüldü, 0 eşleşme). "Ortam hâlâ diskte olduğu için
çalışıyor" şüphesi bu kadarıyla kapandı.

**Kapanmayanlar, ve buradan ölçülemezler:** farklı bir Windows sürümü/yaması (bu makine
10.0.19045), antivirüs karantinası (buradaki Defender klasörü tanıyor), `config\`'e yazma
izni başka bir konumda, ve **`.xls` formatlı bir ayın exe'den koşulması** — `xlrd`
gerçekten pakete girdi mi ancak öyle anlaşılır.

**Denenecek sıra** (en çok yakalayan 4 ve 5; 7 ise sessiz hatayı yakalayan tek adım):

1. Klasörü zip'le, temiz makineye kopyala, **Masaüstü'ne** çıkar (`Program Files`'a değil).
2. `config\personel.yaml` ve `config\gmail.yaml` elle konsun.
3. Aç. SmartScreen "bilinmeyen yayıncı" derse "Ek bilgi > Yine de çalıştır".
4. **Takvim ekranında bir tatil işaretle ve kaydet** — yazma izni burada anlaşılıyor.
5. **`.xls` formatlı bir ay koş** (Temmuz'un Macunköy dosyası öyle) — `xlrd` gerçekten
   pakete girdi mi ancak böyle anlaşılır. `hiddenimports`'ta yazılı olmasının sebebi bu:
   o kütüphane yalnızca `.xls` karşısına çıkınca import ediliyor.
6. `Kontrol` sayfasında **`Mutabakat TAMAM`** gör, ve toplam süreyi bu depodaki
   rakamla karşılaştır (Temmuz **26 233:17**). Tutmuyorsa rapor kullanılmaz.
7. `Kontrol` sayfası **bölüm 7**'de isim eşleştirmeleri listeleniyor mu. **Bu adımı
   atlama:** `personel.yaml` yanlış yere konursa program açılır, rapor üretir ve **beş
   kişi ikiye bölünmüş** görünür — hiçbir uyarı vermez, çünkü çözülemeyen bir varyant
   iki farklı çalışandan ayırt edilemez. Bölüm boşsa tablo yüklenmemiş.
8. Bir kişiye mail at, Outlook'ta yanıtlayıp tabloya yaz.

**Antivirüs:** imzasız PyInstaller çıktısı sık sık "bilinmeyen yayıncı" uyarısı alıyor,
kurumsal antivirüs bazen doğrudan karantinaya alıyor. Kod imzalama sertifikası yoksa
çözüm ya istisna ekletmek ya da ortak bir klasörden çalıştırmak. Hedef makinede hangi
antivirüsün olduğu **henüz sorulmadı**.

### 3b. Teslim: zip **`paketle.cmd`** ile, `dist/` elle ziplenmez

`dist\MesaiTakip\` aynı zamanda kurulup **test edilen** klasör, yani içine gerçek
`personel.yaml`, gerçek `gmail.yaml`, personel listesi Excel'i ve üretilmiş raporlar
giriyor. 27.08'de o klasörde üçü de vardı. Depo **public**, ve `dist/` ignore'lu
olmasaydı bir `git add -A` canlı uygulama şifresini ve 181 kişinin adını yayınlayacaktı.

`paketle.cmd` zip'i bir **kopyadan** üretiyor, gizli olanları çıkarıyor, `SURUM.txt`
yazıyor ve **yazmadan önce tekrar kontrol ediyor**. İkinci kontrol asıl olan: elle
yapılan ilk tur `personel.yaml` ile `gmail.yaml`'ı adıyla çıkarıp "temiz" dedi, ve
**personel listesi Excel'i yanından geçti**. Kural artık türe göre: pakete hiçbir Excel
ve hiçbir `gonderim-*.json` girmiyor.

`dist/` git'e **konmadı** ve konmamalı: ignore kuralı yukarıdaki tek koruma, ve 38 MB her
derlemede geçmişe kalıcı olarak ekleniyor (`.git` 3,7 MB). Başka makineye hazır bir klasör
gerekiyorsa yolu **GitHub Releases** — zip bir ek olarak duruyor, geçmişe girmiyor,
klonda inmiyor.

### 4. Düzeltme turu — **istendi, yapılmadı** (ROADMAP 4d, Q24)

Mailden sonraki adım. Kişiler cevap veriyor, danışman eksik giriş-çıkışları tamamlayıp
saatleri sayan bir rapor istiyor.

> *"danışman o bizim hazırladığımız exceli düzenlemek isteyecek ... o noktadan sonra o
> rapora göre bu uygulama ve json falan yeniden düzenlenmesi gerekecek. artık o 3 excel
> dosyasını kullanmıyoruz."*

**Exe'den sonra mümkün mü? Evet — ama bu bir özellik, yani kod, yani yeni bir exe.**
Paketleme sorusunun tamamı hakkında akılda tutulacak çizgi bu: `config/`'e bilerek
bırakılan şeyler (mail metni, eşikler, tatiller, alias'lar, hesap) derleme olmadan
değişiyor. Programın **ne yaptığını** değiştiren her şey yeniden derleme.

**Yapılmayacak olan:** üretilen Excel'i düzenleyip programa geri okutmak. O dosya bir
sunum çıktısı — süreler `HH:MM` metni, hücreler birleşik, kolonlar yer değiştiriyor
(ADR-052'de ve tekrar ADR-075'te değişti) — ve `snapshot.py` tam bunu engellemek için var.
Hem girdi hem çıktı olması, bir koşunun kaynaklarından yeniden üretilememesi demek.

**Çalışan biçim:** üç kaynak dosya **taban olarak kalıyor**, yanına dördüncü ve amaca özel
bir dosya geliyor. Program yalnızca sorunlu günleri taşıyan bir düzeltme sayfası yazıyor,
danışman son üç kolonu dolduruyor, sonraki koşu onu üç dosyanın yanında okuyor ve
düzeltilen saatler `source="düzeltme"` ile kayıt oluyor. Yani rapor "güncellenmiyor",
**yeniden üretiliyor** — bir girdi fazlasıyla. Boru hattı girdilerinin fonksiyonu olarak
kalıyor, ki altı ay sonra bir sayı tartışıldığında aynı ayı yeniden üretebilmenin şartı bu.

Kısıtlar, gerekçeleri ve açık sorular `ROADMAP.md` 4d'de. En kritiği: **düzeltilmiş bir
saat, karttan okunmuş bir saatten ayırt edilebilir olmalı** — bu sayılar bordroya gidiyor.

---

## Cevap bekleyen sorular

Öncelik sırasıyla. Kimin cevaplayacağını program belirlemiyor (ADR-047).

| # | Soru | Neyi bloke ediyor |
| --- | --- | --- |
| 1 | **Dosyalar her ay ayın kaçında alınacak?** Ayın 20'sinde alınan bir dosya yine yarım olur; Temmuz'da bir kez yaşandı | Bir sonraki ay (Q23) |
| 2 | Personel listesi **işe giriş / çıkış tarihi** kolonlarıyla alınabilir mi? | Ay içinde giren/ayrılanın `Hem giriş hem çıkış yok` yanlış pozitifleri, ve `Kontrol` §5'teki "hiç kaydı olmayan" listesinin ayıklanması — şu an ikisi de elle (Q18) |
| 3 | Dokuz isim eşleştirmesinin doğrulanması — `Kontrol` sayfası bölüm 7 | Yanlışsa iki kişinin bordro saatleri birleşir (Q4a) |

Soru 2'nin cevabı "böyle bir liste yok" olabilir; o durumda alternatif düşünülecek.

**Q4 listeden çıktı** — kapatıldı, cevaplanmadı (ADR-071). *"ya sen o soruyu boşver.
direkt kart kaydı yok diye geçmiyor muyuz zaten o kişileri? onlar manuel kontrol edilecek
yönetici tarafından."* Doğru: cevap programın yaptığı hiçbir şeyi değiştirmezdi, kart
kaydı olmayana saat uydurulamaz. Kapatırken **başka bir boşluk** çıktı ve kapatıldı —
aşağıdaki `Son değişiklikler`'de ADR-071.

### Bloke etmeyen ama cevaplanmalı

- **Uzaktan beyanı olup kart da basanlar** — 3 ayda 12 gün. Beyan mı geçerli, kart mı?
  Şu an ikisi birleştiriliyor ve işaretleniyor.
- **İzinli görünüp kart basanlar.** Ölçerken çıktı (ADR-068): bir kişinin 13 Temmuz yıllık,
  14 Temmuz doğum günü izni var ve **14'ünde kart basmış**. `Günlük Detay` işi gösteriyor
  (oradaydı), `İzin Günü` HCM'in yazdığı 2'yi. İkisi de doğru ve **çakışmayı hiçbir şey
  işaretlemiyor** — uzaktan çalışmanın aynısı için not var (`Uzaktan + kart kaydı`), sıradan
  izin için yok. Çalışılmış bir izin günü izin mi, çalışma mı, ikisi birden mi sayılmalı?
  İzin verisinin sahibine sorulacak.
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
| **065** | **ADR-053 geri alındı: üç eksik-kayıt notu tamamen ayrı** | Yönetici kararı. `Giriş yok` artık ikisi de olmayan günleri getirmiyor |
| 066 | `Mesai verisi yok` → **`Kart bilgisi yok`**; `+N` kolonu → **`Gün`**; iki listeye kolon başlıkları | Aynı kişi için dört farklı sayı dolaşıyordu ve hangisinin ne olduğunu söyleyen bir şey yoktu |
| **067** | **Kullanılamayan bir kayıt da kayıttır** | Tek taraflı damga WorkDay üretmiyor; üç yer bunu "hiç kayıt yok" sanıyordu. Aynı gün hem `Giriş yok` hem `Hem giriş hem çıkış yok` yazıyordu |
| 068 | `Not` kolonu yalnızca bekleyen notları taşır | Özet `Hem giriş hem çıkış yok` derken `Günlük Detay` o gün için sıradan 9 saatlik gün gösteriyordu |
| 069 | `Şüpheli Kayıt` de öyle; `Günü sayılan` notlar kutu değil satır; kart kaydı olmayan panelde boş görünmüyor | Sayı ile notu aynı satırda çelişiyordu; `Tesis birleştirme (0)` "olmamış" gibi okunuyordu; kart kaydı hiç olmayan kişi panelde temiz görünüyordu |
| 070 | `Günlük Detay` izin satırında **yalnızca `İzin`**; panel uyarısı kırmızı ve sarılıyor | Sayfa, ada ve tarihe karşı `Doğum İzni (Tam Ödeme)` yazıyordu; uyarı "sorun yok" ile aynı renk ve fontta, tam ekran olmadan sığmıyordu |
| **071** | **Q4 kapandı; `Kontrol` §5 personel listesinde olup hiç kaydı olmayanları sayıyor** | Yönetici kararı: kart kaydı yoksa işaretle, elle bakılır. Ölçerken çıktı ki aynı şekilde eksik ama **hiç satırı olmayan** 21/27/14 kişi hiçbir sayıda görünmüyordu (%76'sı Macunköy — Q4'ün deseni). CLI'daki `<- ROADMAP.md Q4` de gitti, kullanıcıya gösterilen yerde depo referansıydı |
| **072** | **Günü sayılmış notlar da filtrede kişi getiriyor; her not kutu; `Sorunu olanlar` sayısı işaretlere bağlı değil; panel 267→152 px** | `Gece geçişi` panelde 6, filtrede 0 diyordu — ADR-059'un kuralı bu notlarda her günü siliyordu. Kolon 2'den 3'e çıktı ama bloklar kolona dağıtılınca 880×620'de gün paneline **11 px** kalıyordu; etiketler artık kolonlara akıyor, gün paneli 126 px |
| **073** | **Kişi kişi e-posta: adres alanı, `E-posta gönder…`, düzenlenebilir önizleme, Gmail SMTP** | Toplu gönderme **yok** ve bir kontrol sunmuyor. Ekranda ne varsa o gidiyor; gönderim anında metin kutusu okunuyor, pencereyi açan taslak değil. Hesap `config/gmail.yaml`, git'e girmez |
| **074** | **`Sorunlu gün` ve gün paneli işaretlerden bağımsız; sayılan günler ayrı başlık altında, işaretsiz** | Kolon 446 diyordu (27'si sayılmış gün), tek not işaretliyken 127; gerçek 419. ADR-072'nin yan etkisi ve ADR-066'nın "kolon = panel satırı" kuralının fazla dar yeri. Sayılmış bir gün için "eksik durum tespit edilmiştir" yazılması an meselesiydi |
| **075** | **İzinli gün panelden çıktı; mailde giriş-çıkış saatleri; konuda gün sayısı yok; `İnceleme Listesi` alfabetik ve `Açıklama` kolonu legend oldu** | Dördü de kullanırken çıktı. İzinli güne "sayılan ya da izinli" başlığı yazmak yanlış şeye dikkat etmekti — o gün için kimseye soru sorulmuyor. `Açıklama` her satırda aynı 52 karakterlik cümleyi tekrarlıyordu; artık tablonun altında not başına bir kez, yalnızca o ay olan notlar |
| **076** | **Notu yalnızca "damga eksik" olan sayılan gün panelden çıktı; `day_notes` o notu soru sorulan hiçbir yerde yazmıyor** | *"sorun kısmı var hem giriş hem çıkış yok diye. ama aynı zamanda da sayılmış? wtf"* — Macunköy satırının iki damgası boş, Teknopark aynı günü 9:05 saymış. Not kayıt hakkında, saat gün hakkında (ADR-055) ve panelde ikisini birleştiren bir şey yoktu. 52/97/87 gün. Aynı gün hem o notu hem `Tesis birleştirme` taşıyabildiği için `day_notes` de gerekti |
| **077** | **`Günlük Detay` kullanılamayan kaydın gününü de gösteriyor; Excel-pencere çapraz kontrolü artık test** | *"excelde bir şey yazıyor, guide başka bir şey yazıyor. hepsi aynı kökten gelmiyor mu?"* Veri tek kökten geliyor, ama "hangi günleri göstereyim" sorusunu üç tüketici ayrı ayrı cevaplıyordu. Cumartesi kart basıp damgası kırık olan 15/15/14 kişi-günü sayfada hiç yoktu, pencere onları soruyordu. Sayfa eksikti, pencere haklıydı |

**Sırayla okunması gereken zincir:** 055 kuralı kurdu → 059 onu doğru katmana taşıdı →
060 kapsamı genişletti → 061 koşulları kaldırdı → 062 gereksizleşen notu sildi.

**071 aynı ailenin devamı** ve tek başına okunmamalı: 060/061 *kaydı olmayan günü*
görünür yaptı, 071 *kaydı hiç olmayan kişiyi*. İkisinin de gerekçesi aynı — eksik olan
sessiz kalıyordu.

**077 bu ailenin kapanışı ve tek başına okunması gereken tek şey:** dört ADR'nin (072,
074, 075, 076) hepsi aynı sebepten çıktı — "hangi günleri göstereyim" sorusu üç yerde
ayrı ayrı cevaplanıyordu. Saatler hiç yanlış olmadı ve hiç değişmedi (17 103:58 /
27 166:19 / 26 233:17). Artık iki uçtan uca test Excel ile pencereyi gün gün
karşılaştırıyor; dördüncü bir yerde aynı soruyu cevaplayacaksan o testleri de genişlet.

**072 ise 059'u daraltıyor ve 069'un yarısını geri alıyor.** Sırayla: 059 filtreyi bekleyen
güne kısıtladı → 069 bu yüzden hiç kimseyi getirmeyen notları kutudan çıkardı → 072 asıl
sebebin filtre olduğunu bulup kısıtı o notlarda kaldırdı, kutuları geri getirdi. 069'un
*sebebi* hâlâ doğru: `(0)` yazan bir kutu "olmamış" diye okunur. Çözümü yanlıştı.

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
- Commit öncesi sızıntı kontrolü — **iki kez yanlış yapıldı, ikisi de burada**:
  - **Bütün commit'li dosyaları tara** (`git ls-files`), yalnızca eklenen satırları
    değil. Aylar önce girmiş bir ad da aynı derecede açık; eklenen-satır sürümü dört
    gerçek soyadın üzerinden temiz rapor veriyordu.
  - İsimleri **hem roster'dan hem `ISIM-ESLESMELERI.local.md`'den** yükle ve kısa
    olanları atlama — dördünden biri dört harfliydi ve uzunluk filtresi onu
    düşürüyordu.
  - **Yazarken adlarını yazma.** Bu maddenin ilk hâli dört soyadı tek tek saydı, yani
    az önce çıkarıldıkları yere geri koydu.
  - Türkçe sözcükler soyadlarla çakışıyor (`alır`, `uzun`, `örnek`; `elif` Python
    anahtar sözcüğü), o yüzden katlanmış metinde **tam kelime** ara ve gürültü bekle.

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
- Snapshot `format_version` **11**. Eski dosyalar "yeniden üret" diye reddediliyor. Bir
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
- **Bir uyarı, uyarı gibi görünmeli.** Panelin `Kart bilgisi yok` mesajı "sorun yok"
  mesajıyla aynı soluk gri ve aynı fonttaydı, ve sabit `wraplength` yüzünden tam ekran
  olmadan kırpılıyordu — ekrandaki en yüksek sesli mesaj, okunamayan mesaj olmuştu
  (ADR-070). Artık kırmızı, kalın, ve sarma uzunluğu `<Configure>` ile paneli takip
  ediyor. Sıradan boş hâl soluk gri kalıyor: her zaman açık olan bir uyarı stili,
  uyarı stili olmamakla aynı şey.
- **Pencere 880×620'den 2560×1400'e ve maximize'da ölçüldü** (ADR-059 turu, 11 test): iki
  ekran da pencereyi dolduruyor, liste pencereyle büyüyor, ekran değiştirmek maximize'ı
  bozmuyor. `_fit` yalnızca büyütür, asla küçültmez (ADR-038).

### İzin ve gizlilik

- **`Günlük Detay` izin gününe tip yazmaz, yalnızca `İzin`** (ADR-070). Kolon HCM'in
  yazdığı tipi taşıyordu ve sayfa **ada ve tarihe karşı** `Doğum İzni (Tam Ödeme)`,
  `İstirahat (Raporlu)` yazıyordu — kişinin doğum ve sağlık kaydı, İK'nın dolaştırdığı
  sayfada. Temmuz'da 44 + 61 + 5 satır. `Kaynak` zaten `İzin` diyor.
- **`İzin Özeti` hâlâ tipe göre kırıyor** ve istenmedi diye dokunulmadı. Ama
  `İstirahat (Raporlu)` bir adın yanında, tarih olmasa da aynı türden bir olgu. Aynı
  itiraz oraya da geçerliyse ayrı bir karar ve alınmaya değer.

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
  ADR-071 aynı kural: personel listesinde olup hiç kaydı olmayanların bir kısmı
  gerçekten sonradan işe girmiştir, ama hangisi olduğunu program bilemediği için hepsi
  sayılıyor.
- **Bir sayının "ölçüldü" demesi, bugün de doğru olduğu anlamına gelmiyor.** ADR-071
  turunda `KURALLAR.md`'nin not sayılarının çoğu bayat çıktı — `Hem giriş hem çıkış yok`
  226 yazıyordu, gerçek 798 (ADR-060/061 kapsamı genişletmiş), `Çıkış yok` 526 yazıyordu,
  gerçek 369 (ADR-067). `ROADMAP.md`'nin tablosunda Haziran'ın varlık süresi 47 dakika
  eskiydi ve Temmuz "bilerek yok" diye duruyordu, oysa Q23 ile tamamlanmıştı. Bir kuralı
  değiştiren ADR yazarken **o kuralın sayısını yazan dosyaları da** güncelle.
