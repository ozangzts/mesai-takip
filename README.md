# Mesai Takip

DEICO personelinin aylık çalışma sürelerini, ham kart okuyucu (turnike) çıktılarından
otomatik olarak hesaplayıp tek bir temiz Excel raporuna dönüştüren araç.

> **Durum: Faz 1 çalışıyor.** Mayıs, Haziran ve Temmuz 2026 raporları üretiliyor.
> Fazla mesai, vardiya ve Multinet henüz yok (Faz 2). Üretilen rapor bir **doğrulama
> koşusudur**, bordro için nihai değildir — sebepleri raporun `Kontrol` sayfasında.
>
> **Temmuz raporu eksiktir:** Teknopark dosyası ayın yalnızca 1–19'unu kapsıyor.
> Program bunu raporun en üstünde kırmızıyla yazıyor ve `5` koduyla çıkıyor.

---

## Neden

Her ay iki ayrı lokasyondan gelen ham giriş-çıkış dosyaları elle
işleniyor. Kaynak veri sağlıklı değil: Macunköy dosyasındaki 1 209 satırın 388'inde
giriş veya çıkış kaydı eksik, 29 satırda süre negatif çıkıyor, 23 kayıt aslında
personel değil (ziyaretçi/geçici kart). Üstelik **76 kişi iki dosyada birden** yer
alıyor — düz toplama yapılırsa bu kişilerin saatleri çift sayılıyor. (Sebebi
anlaşıldı: bu kişilerin 75'i Teknopark'ta çalışıyor ve gün içinde Macunköy'e
gidiyor.)

Bu araç bunları otomatik ve her seferinde aynı şekilde hallediyor.

> **Sayılar nasıl çıkıyor?** Bütün hesaplama kuralları tek yerde ve sade Türkçe:
> **[docs/KURALLAR.md](docs/KURALLAR.md)**. Rapordaki bir sayıyı sorgulayan herkese gösterilebilir.

## Girdi dosyaları ve klasör yapısı

```
data/
├── personel/                       ← aya bağlı DEĞİL, bir kez konur
│   └── calisan_listesi.xlsx
├── raw/2026-05/                    ← her ay için ayrı klasör
│   ├── Macunköy Mayıs Mesai giriş-çıkış.xlsx
│   ├── Teknopark - Mayıs Mesai Takip Exceli.xlsx
│   └── HCMT34_MAYIS_IZIN.xlsx
└── out/2026-05/                    ← komut satırından çalıştırılırsa buraya
    ├── mesai-raporu-2026-05.xlsx   ← açılacak rapor dosyası
    └── gonderim-2026-05.json       ← raporun makine-okunur eşleniği

Masaüstü/                           ← pencereden çalıştırılırsa buraya (varsayılan)
└── 2026-05 Rapor/
    ├── mesai-raporu-2026-05.xlsx
    └── gonderim-2026-05.json
```

**Rapor ve veri dosyası her zaman aynı klasörde.** Nerede olacağını pencereden sen
seçersin (varsayılan Masaüstü, seçim hatırlanır); komut satırı `data/out/<ay>/`
kullanmaya devam eder.

Veri dosyası (`gonderim-<ay>.json`) raporla aynı koşuda yazılıyor ve raporun içindeki
sayıların makine tarafından okunabilir hâlini tutuyor. Faz 4'te e-posta adımı **bunu**
okuyacak, Excel'i değil. İçinde isim, e-posta ve saat var; git'e dahil değil,
paylaşılmaz.

| Dosya | Ne | Kişi |
| --- | --- | --- |
| `SYST03_...` | Personel ana listesi — e-posta, tesis, bölüm, görev | 181 |
| `Macunköy ...` | Ham kart kayıtları, Macunköy | 128 |
| `Teknopark ...` | Puantaj raporu, Teknopark | 110 |
| `HCMT34_..._IZIN` | İzin kayıtları | 162 |

**Personel listesi neden ayrı klasörde:** diğer üçü bir aya ait hareket kaydı, o ise
"şu anda kim çalışıyor" anlık görüntüsü. Her ay klasörüne kopyalamak, o aya aitmiş
gibi görünmesine yol açar. Bir kez `data/personel/` içine koy, bütün aylar onu
kullanır. Yeni bir liste geldiğinde eskisinin üzerine yaz.

Program önce `data/personel/`'e, bulamazsa ay klasörüne bakar — dört dosya birlikte
geldiğinde de çalışsın diye.

Listenin **alınma tarihi dosyanın kendisinden okunuyor** ve raporun `Kontrol`
sayfasında rapor dönemine göre kaç ay uzakta olduğuyla birlikte yazılıyor. Mayıs
koşusunda: `28.07.2026 — Rapor döneminden 2 ay SONRA alınmış`. Ayrılan 11 kişinin ve
listede olup Mayıs'ta görünmeyen 20 kişinin tek satırlık açıklaması bu.

Personel listesi kimlik eşleştirmenin çıpası ama **beyaz liste değil**: listede
olmayıp mesai kaydı olan biri yine çalışmıştır, yine raporda yer alır.

---

# Kurulum

Gereken tek şey **Miniconda** (ya da Anaconda). Yoksa:
<https://docs.conda.io/en/latest/miniconda.html>

Yeni bir bilgisayarda, **bir kez**:

```powershell
git clone <repo-adresi> mesai-takip
cd mesai-takip
conda env create -f environment.yml
conda activate mesai
pip install -e . --no-deps
python -m pytest
```

Son satır **339 passed** demeli. Demiyorsa kurulum bozuk, aşağıdaki tabloya bak.

### Yeni bilgisayarda: git'ten gelmeyen iki dosya

Klonlamak yetmiyor, ikisini elden almak gerekiyor:

| Dosya | Nereden |
| --- | --- |
| `config/personel.yaml` | Çalışan bir kurulumdan kopyala. Gerçek isim eşleştirmeleri içerdiği için git'te yok |
| `data/personel/` içindeki çalışan listesi | mevcut kurulumdan |

`personel.yaml` olmadan program çalışır ama **sessizce eksik çalışır**: soyadı
değişmiş ya da ilk adı kısaltılmış kişiler raporda ikiye bölünür ve hiçbir uyarı
çıkmaz.

Kontrol yolu: raporu üret, `Kontrol` sayfasının **6. bölümüne** bak. Orada
eşleştirmeler listeliyse yüklü, boşsa eksik.

Notlar:

- `environment.yml` Python 3.12 + `openpyxl` + `pyyaml` + `pytest` kuruyor.
- `pip install -e .` paketi **kaynaktan** kurar; kodda değişiklik yapınca yeniden
  kurmak gerekmez.
- `--no-deps` gerekli: bağımlılıklar conda'dan geldi, pip'in aynılarını PyPI'dan
  tekrar çekmesi gerekmiyor. **`--no-deps`'i `environment.yml` olmadan
  kullanma** — o zaman hiçbir bağımlılık kurulmaz.

## Her yeni terminalde

```powershell
conda activate mesai
```

Bunu yapmadan `mesai` komutu bulunamaz. Bu kasıtlı: komut ortama kurulu, yanlış
Python'la çalışma riski yok.

Aktive etmek istemiyorsan `rapor.cmd` sarmalayıcısını kullan (aşağıda) — ortamı
kendi bulur.

| Belirti | Sebep | Çözüm |
| --- | --- | --- |
| `mesai : command not found` | Ortam aktif değil | `conda activate mesai` |
| `No module named pytest` | Bağımlılıklar kurulmamış | `conda env create -f environment.yml` ile ortamı baştan kur |
| `No module named openpyxl` | Aynı sebep | Aynı çözüm |
| `conda : command not found` | Miniconda kurulu değil / PATH'te yok | Anaconda Prompt'tan çalıştır |

Ortamı sıfırdan kurmak:

```powershell
conda deactivate
conda env remove -n mesai -y
conda env create -f environment.yml
conda activate mesai
pip install -e . --no-deps
```

## Bağımlılıklar neden iki dosyada

| Dosya | Ne söyler | Biçim |
| --- | --- | --- |
| `pyproject.toml` | Paket **neye ihtiyaç duyar** | Aralık: `openpyxl>=3.1` |
| `environment.yml` | Ortam **tam olarak neyden oluşur** | Sabit: `openpyxl=3.1.5` |

`requirements.txt` yok: bağımlılık bildirmenin standardı artık `pyproject.toml`
(PEP 621), sabit sürüm dosyası işini de `environment.yml` görüyor.

Sürümler neden sabit — bu araç bordroya giden sayılar üretiyor ve ayda bir
zamanlanmış görev olarak çalışacak. `openpyxl`'in bir sonraki sürümü tarih
ayrıştırmasını değiştirirse çıktı sessizce kayabilir. Yükselttiğinde `pytest`
çalıştır, sonra bir ayı yeniden üretip Kontrol sayfasındaki mutabakatın hâlâ
**TAMAM** olduğunu doğrula.

---

# Kullanım

## Pencere ile: `arayuz.cmd`

**Terminal kullanmak istemiyorsan bu yol.** `arayuz.cmd`'ye çift tıkla; konsol
açılmaz, bir pencere gelir.

```
┌──────────────────────────────────────────────────────┐
│  Mesai Raporu                                        │
│  Aylık çalışma süresi raporu                         │
├──────────┬───────────────────────────────────────────┤
│          │  KAYNAK KLASÖR                            │
│  Rapor   │  [ Y:\... - 2026            ] [ Gözat… ]   │
│          │   ✓ Macunköy   ...xlsx                    │
│          │   ✓ Teknopark  ...xlsx                    │
│          │   ✗ İzin       bulunamadı       [ Seç… ]  │
│          │                                           │
│          │  DÖNEM                                    │
│          │  [ 2026-07 ]   Temmuz 2026                │
│          │                                           │
│          │  RAPOR KLASÖRÜ                            │
│          │  [ C:\Users\...\Desktop  ] [ Değiştir… ]   │
│          │  Bu koşu şu klasörü oluşturacak:          │
│          │  2026-07 Rapor  (rapor ve veri birlikte)  │
│          │                                           │
│          │  ┌────────── Rapor Oluştur ────────────┐  │
│          │  └─────────────────────────────────────┘  │
│          │  ┌─────────────────────────────────────┐  │
│          │  │ Temmuz 2026 raporu yazıldı — EKSİK  │  │
│          │  │ Toplam çalışma süresi : 16078:44    │  │
│          │  │ ⚠ EKSİK VERİ — teknopark dosyası …  │  │
│          │  │                                     │  │
│          │  │ RAPOR DOSYASI                       │  │
│          │  │ C:\...\mesai-raporu-2026-07.xlsx     │  │
│          │  │ VERİ DOSYASI                        │  │
│          │  │ C:\...\gonderim-2026-07.json         │  │
│          │  └─────────────────────────────────────┘  │
│          │         [ Raporu Aç ]  [ Klasörü Aç ]     │
└──────────┴───────────────────────────────────────────┘
```

Akış: **Gözat** ile üç mesai dosyasının bulunduğu klasörü seç → pencere hangi
dosyaları bulduğunu hemen yazar → **Rapor Oluştur**.

Solda bir gezinme paneli var. Şu an tek bölüm (`Rapor`) çünkü tek iş var; e-posta
adımı geldiğinde oradan geçilecek.

- **Varsayılan klasör yok ve önceki seçim geri yüklenmez.** Yanlış bir tahmin boş
  alandan kötüdür, çünkü kullanıcı yanlış klasörden okunduğunu fark edemez. Program
  her açılışta boş gelir.
- **Sadece "Gözat"ın başlayacağı yer hatırlanır.** Girdi klasörü aya özel
  (`07 - 2026`), dolayısıyla önceki seçimi geri yüklemek ikinci aydan itibaren **her
  zaman bitmiş bir ayı** gösterir — üstelik dönem alanını da o ayla doldururdu.
  Ağustos'ta pencereyi açıp Temmuz'u çalışmaya hazır görmek tam olarak kaçındığımız
  hata türü. Hatırlanan şey klasörün **üst dizini**, yani Gözat doğru paylaşımda
  açılır ama seçimi sen yaparsın.
- Klasörde eksik veya fazla dosya varsa **Rapor Oluştur** pasif kalır ve neyin eksik
  olduğu yazılır. Aynı klasörde iki ay varsa "2 dosya eşleşti" der. Bulunanlar yeşil,
  bulunamayan kırmızı — üçü tek renge boyanmaz.
- **Dosyalar farklı yerlerdeyse tek tek gösterebilirsin.** Bulunamayan (ya da iki
  dosyanın eşleştiği) kaynağın satırında bir `Seç…` düğmesi çıkar; o dosyayı nerede
  olursa olsun seçersin, ötekiler klasörden gelmeye devam eder. Elle seçilen satırda
  `(elle seçildi)` yazar ve `Geri al` ile klasöre döndürülür. Beklendiği yerde bulunan
  bir dosyaya düğme çıkmaz — düzeltilecek bir şey yok.
  Klasörü değiştirdiğinde elle seçimler unutulur; önceki aya aitlerdi.
  Seçtiğin dosyanın adı o kaynağa benzemiyorsa **uyarılır ama yine de kullanılır** —
  yeniden adlandırılmış bir dosya da o dosyadır, ve içeriği okunurken zaten denetlenir.
  Dosyanın adında dönemden başka bir ay geçiyorsa (`... Haziran ...` seçilip dönem
  `2026-05` ise) satırda turuncu bir uyarı çıkar. Uyarı engellemez — karar, dosyanın
  **içindeki tarihlere** aittir, adına değil.
- **Aylar karışırsa program durur.** Seçilen dosyalardan birinin bütün kayıtları
  dönemin dışındaysa rapor **üretilmez**; hangi dosya, beklenen aralık, dosyadaki
  aralık ve kaç kayıt atıldığı yazılır. Bu kontrol olmadan Mayıs'a Haziran Teknopark
  dosyası konduğunda program sorunsuz bitiyor ve 17 103:58 yerine 4 869:54 yazıyordu —
  hiçbir uyarı vermeden.
  Hiç kaydı olmayan bir kaynak hata değildir: ofis kapalıyken Teknopark'ta satır
  olmaması normaldir. Hata olan, **satır okuyup hiçbirinin o aya ait olmaması**.
- **Dönem listesi kaldırıldı.** Eskiden seçtiğin klasörün *komşusu* olan aylar bir
  açılır listede görünüyordu; nereden geldikleri belirsizdi ve `07 - 2026` klasörünü
  seçip listeden `2026-05`'i seçmek gibi bir hataya davetiye çıkarıyordu. Dönem artık
  seçtiğin klasörden geliyor.
- **Dönem klasör adından okunur ve yazım esnek.** Şunların hepsi anlaşılır:
  `2026-07`, `07-2026`, `2026_07`, `202607`, `Temmuz 2026`, `Mesai 2026-07 Girdi`.
  Ay adı Türkçe yazılabilir, büyük/küçük harf ve Türkçe karakter fark etmez.
  Alana elle de aynı esneklikle yazılabilir; girdiğin yazım `2026-07` biçimine
  çevrilip alanda gösterilir.
- **Belirsiz yazım kabul edilmez.** `03-04` reddedilir — hangisinin ay hangisinin yıl
  olduğu belli değil. Yıl dört haneli olmalı. Program tahmin yürütüp yanlış ayı
  raporlamaz, alanı boş bırakıp yazımını bekler.
- **Dönem alanının yanındaki not ne yazacağını söyler:** anlaşıldıysa ayın adını,
  anlaşılmadıysa sebebini, klasörle uyuşmuyorsa `⚠ klasör 2026-07 dönemine ait
  görünüyor` uyarısını. Bu son durum yanlış ayın dosyalarını yanlış dönemle okumayı
  engelliyor.
- **Raporun nereye yazılacağını sen seçersin.** Varsayılan **Masaüstü**. `Değiştir…`
  ile başka bir klasör seçebilirsin ve seçtiğin yer sonraki açılışlarda hatırlanır.
  Girdi klasörü bilerek hatırlanmıyor ama çıktı klasörü hatırlanıyor; fark şu: girdi
  klasörü aya özel, çıktı klasörü değil — ay, içinde açılan alt klasörün adında.
- **Her ay için bir klasör açılır: `2026-05 Rapor`.** Rapor ve veri dosyası bu klasöre
  birlikte yazılır, yani `Klasörü Aç` ikisinin birden durduğu yeri açar. Seçtiğin
  klasörün altında hangi klasörün açılacağı, düğmeye basmadan önce yazıyor.
  Yıl önce yazılıyor ki klasörler kendiliğinden tarih sırasına dizilsin.
- **Aynı ay ikinci kez çalıştırılırsa üzerine yazılır.** Klasör yeniden oluşturulmaz,
  içindeki rapor ve veri dosyası yenilenir; klasördeki başka dosyalara dokunulmaz.
  O ay için zaten bir rapor varsa pencere **düğmeye basmadan önce** turuncu yazıyla
  söyler. Rapor türetilmiş bir dosya — düzeltilmiş bir girdinin uygulanma yolu zaten
  yeniden çalıştırmak. Dosya Excel'de açıksa yazılmaz, "kapatın" der.
- **Rapor ve veri dosyasının tam yolu sonuç panelinde yazıyor**, sadece adı değil.
  `Raporu Aç` ve `Klasörü Aç` düğmeleri de aynı dosyayı açar. Panel sığmadığında
  kaydırılır — eksik veri uyarısı uzun olduğunda veri dosyasının yolu en altta kalır.
- **Rapor Oluştur'un altındaki çubuk yalnızca hesaplama sürerken görünür.** Boştayken
  hiçbir şey görünmez; "biraz ilerlemiş" gibi duran bir çubuk yanıltıcı olurdu.
- Eksik veri varsa sonuç panelinde turuncu uyarı çıkar — Temmuz'da olduğu gibi.

Pencere hesap yapmıyor; komut satırının çağırdığı **aynı** kodu çağırıyor, dolayısıyla
iki yol her zaman aynı sonucu verir.

## En kısa yol: `rapor.cmd`

Ortamı aktive etmeye, klasöre girmeye gerek yok. Nereden çağırırsan çalışır:

```powershell
C:\yol\mesai-takip\rapor.cmd --ay 2026-05
```

Script `mesai` conda ortamını kendi bulur (aktifse onu kullanır), kendi dizinine
geçer, işi yapar ve çıkış kodunu aynen döndürür. Aylık rutin için bunu kullan.

Kısayol yapmak istersen: `rapor.cmd`'ye sağ tık → Kısayol oluştur → kısayolun
özelliklerinde hedefin sonuna `--ay 2026-06` ekle. Çift tıkla çalışır.

Ortam bulunamazsa ne yapması gerektiğini söyleyip `9` koduyla çıkar.

## Uzun yol: ortamı aktive ederek

Geliştirme yaparken bu daha uygun — `pytest`, `pip` gibi komutlar da elinin altında
olur:

```powershell
conda activate mesai
cd C:\yol\mesai-takip

# Normal kullanım — girdi data/raw/2026-05/ klasöründen okunur:
mesai rapor --ay 2026-05

# Dosyalar başka bir klasördeyse (örn. Drive'dan senkronlanan):
mesai rapor --ay 2026-06 --girdi "G:\Ortak Drive'lar\İK\Mesai\2026-06"

# Çıktıyı başka yere yazdırmak için:
mesai rapor --ay 2026-05 --cikti "C:\gecici\deneme.xlsx"
```

`mesai` yerine `python -m mesai` de kullanılabilir, aynı işi yapar.

Çıktı dosyası Excel'de **açık olmamalı** — açıksa program yazamaz ve bunu söyler.

## Aylık iş akışı

Kaynak dosyalar Google Drive'a yükleniyor. Şu an akış **elle** — Drive otomasyonu
henüz kurulmadı, seçenekler aşağıda.

```powershell
# 1. Drive'dan ÜÇ aylık dosyayı indir, ay klasörüne koy
mkdir data\raw\2026-06
#    (personel listesi zaten data\personel\ içinde, tekrar koymana gerek yok —
#     yalnızca yeni bir liste geldiyse onun üzerine yaz)

# 2. Raporu üret
conda activate mesai
cd C:\yol\mesai-takip
mesai rapor --ay 2026-06

# 3. Çıktıyı Drive'a yükle
#    data\out\2026-06\mesai-raporu-2026-06.xlsx
```

Adım 2'de dosya adlarını değiştirmen gerekmez, config'e dokunmak gerekmez.
İstersen `config/takvim-2026.yaml`'a o ayın resmi tatillerini ekle — sadece Günlük
Detay'daki gün etiketlerini etkiler, hesabı etkilemez.

Adım 2'yi pencereden yapmak daha kolaysa `arayuz.cmd` de aynı işi yapar.

Raporu paylaşmadan önce **`Kontrol` sayfasına bak**, üç şeye:

1. **Bölüm 3 — Dönem kapsamı.** Her kaynak dosya ayın tamamını kapsıyor mu? Bir dosya
   ay bitmeden alınmışsa rapor eksiktir ve saatler bordroya uygun değildir.
2. **Bölüm 4 — Hesaplama mutabakatı.** `TAMAM` yazıyor mu?
3. **Bölüm 9 — Doğrulanmamış varsayımlar.** Hangi kural doğrulanmadı.

Program kapsama sorununu bulursa `5` koduyla çıkar ve raporun en üstüne kırmızı bir
satır yazar; yani gözden kaçması için özellikle uğraşmak gerekir.

### İleride: Drive otomasyonu

Üç yol var, hiçbiri henüz kurulmadı. Karar bekliyor — `docs/ROADMAP.md` Q21.

| Yol | Nasıl | Gereken | Not |
| --- | --- | --- | --- |
| **Elle** | Şu anki akış | Yok | Bugün çalışıyor |
| **Drive for Desktop** | Drive sürücü harfi olur (`G:`), `--girdi "G:\..."` | IT'nin uygulamayı kurması | Kod değişikliği yok; akış modu ve yarım yüklenmiş dosya için koruma eklenmeli |
| **Drive API** | Python indirir, işler, yükler | Google Cloud projesi + servis hesabı | Sunucuda gözetimsiz çalışır ama bordro işine ağ bağımlılığı ekler |

Ağ sürücüsü (`Y:`) da bir seçenek: zaten mount edilmiş, akış modu sorunu yok, IT
izni gerekmeyebilir.

**Otomasyona geçmeden önce çözülmesi gerekenler:**

- Klasör yapısı ay başına ayrı mı (`2026-06/`, `2026-07/`)? Aracın tek kuralı
  **klasör başına tek ay** — hepsi tek klasörde olursa ek kod gerekir.
- Kaynak dosyalar 162 çalışanın adını, sicilini, günlük hareketlerini ve **izin
  dosyası sağlık/doğum izni gerekçelerini** içeriyor. O Drive klasörüne kimlerin
  erişimi olacak? Birinin bilerek karar vermesi gerekiyor.

## Dosya isimleri

Dosyalar **tam isimle değil, içerdiği anahtar kelimeyle** bulunuyor
(`config/settings.yaml` → `sources`). Büyük/küçük harf farkı, Türkçe karakter
farkı, ek kelimeler sorun değil:

| Dosya | Aranan | Kabul edilen örnekler |
| --- | --- | --- |
| Personel listesi | içinde `calisan` / `çalışan` / `personel`, ya da `SYST03` ile başlayan | `calisan_listesi.xlsx`, `Çalışan Listesi 2026.xlsx`, `CALISAN_LISTESI.xlsx` |
| İzin | içinde `IZIN` / `İZİN` | `HCMT34_HAZIRAN_IZIN.xlsx`, `hcmt34_haziran_izinxlsx.xlsx` |
| Macunköy | içinde `Macunköy` / `Macunkoy` | `Macunkoy Haziran giris-cikis (1).xls` |
| Teknopark | içinde `Teknopark` | `TEKNOPARK haziran puantaj FINAL v2.xlsx` |

**Uzantı da esnek: `.xlsx`, `.xlsm` ve `.xls` kabul edilir.** Temmuz 2026'da Macunköy
dosyası hiçbir haber verilmeden `.xlsx`'ten eski `.xls` formatına döndü; sadece bir
uzantı arayan desen bunu "dosya bulunamadı"ya çevirmişti. Aynı ay o dosyadan bir kolon
da (`Personel`) kalktı ve başlığın üstüne bir satır eklendi — program artık kolonları
**başlık isminden** buluyor, sırasından değil. `.xlsb` desteklenmiyor; gelirse program
"Excel'de .xlsx olarak kaydedip tekrar deneyin" diyor.

Personel listesi için ek bir güvenlik ağı var: **`data/personel/` içinde tek bir
Excel dosyası varsa adı ne olursa olsun o kullanılır.** Yanlış dosya konursa program
okurken hata verir, sessizce yanlış sayı üretmez. Bu esneklik sadece personel
klasöründe geçerli — ay klasöründe tahmin yürütmek mesai dosyasını yanlışlıkla
personel listesi sanmaya yol açardı.

Personel listesinin **sayfa adı da** sabit değil: dosya içinde beklenen kolonları
(`Kullanıcı`, `Kontak No`, `İsim`, `Soyad`, `E-posta`) taşıyan sayfa aranıyor, adına
bakılmıyor. Kolon sırası değişse de çalışır.

Excel'in `~$...` geçici dosyaları ve önceki `mesai-raporu-*.xlsx` çıktıları
otomatik atlanır.

**İki kural:**

1. **Klasör başına tek ay.** Aynı klasörde iki ayın dosyası varsa program durur ve
   bulduklarını listeler — rastgele birini seçip yanlış ayı raporlamaz.
2. **Anahtar kelime isimde olmalı.** `Haziran Puantaj.xlsx` içinde "Teknopark"
   geçmediği için bulunamaz; program `Aranan desenler: ['*Teknopark*.xls*']` diye
   söyler. Ya dosyayı yeniden adlandır, ya `config/settings.yaml`'a desen ekle.

## Çıkış kodları

| Kod | Anlamı |
| --- | --- |
| 0 | Başarılı |
| 2 | Girdi hatası — dosya yok, geçersiz/yanlış ay, klasörde iki ay |
| 3 | Dosya yapısı hatası — dışa aktarım formatı değişmiş |
| 4 | Çıktı dosyası kilitli — Excel'de açık |
| **5** | **Rapor yazıldı ama bir kaynak dosya dönemin tamamını kapsamıyor** — saatler bordro için kullanılamaz |
| 9 | `rapor.cmd`: conda ortamı bulunamadı |

`5` kodu Temmuz 2026'da devreye girdi: Teknopark dosyası ayın 20'sinde alınmıştı,
yani 23 iş gününün 13'ünü içeriyordu. Dosya kendi içinde kusursuzdu ve diğer bütün
kontroller geçti — rapor "mutabakat TAMAM" diyerek eksik bir ay üretti. Kontrol artık
her kaynak için "dönemin sonunda kesintisiz eksik iş günü var mı" diye bakıyor.

Faz 4'te zamanlanmış göreve bağlanınca sıfır olmayan çıkış kodunda uyarı
kurulmalı — aylık iş sessizce patlarsa bordro zamanına kadar fark edilmez.

Çıktı: `data/out/2026-05/mesai-raporu-2026-05.xlsx`

Dosyalar **isimle değil desenle** bulunuyor (`config/settings.yaml:sources`), yani
Drive'a yüklenen klasör doğrudan gösterilebilir; yeniden adlandırma gerekmez.

**Tek kural: klasör başına tek ay.** Aynı klasörde iki ayın dosyası varsa program
durur ve hangilerini bulduğunu yazar — rastgele birini seçip yanlış ayı
raporlamaz. `--ay` bir etiket değil **filtre**: dönem dışı kayıtlar atılır, hiçbir
kayıt döneme ait değilse çalışma hata verir.

### Yeni bir ay geldiğinde

```bash
mkdir -p data/raw/2026-06        # 4 dosyayı buraya koy
python -m mesai rapor --ay 2026-06
```

Config'e dokunmak gerekmez. `config/takvim-2026.yaml` içine o ayın resmi tatilleri
eklenirse Günlük Detay sayfasındaki gün etiketleri doğru olur; Faz 1 hesaplarını
etkilemez.

Rapor 6 sayfadan oluşuyor:

| Sayfa | İçerik |
| --- | --- |
| **Aylık Özet** | Kişi başı toplam çalışma süresi — asıl istenen çıktı |
| **Günlük Detay** | Kişi-gün bazında döküm, özetin denetim izi |
| **İnceleme Listesi** | Kişi başına eksik kayıt günleri, incelenmek üzere |
| **Şüpheli Kayıtlar** | Eksik/hatalı her kayıt, kaynak dosya ve satır numarasıyla |
| **İzin Özeti** | HCM sisteminden gelen izin günleri |
| **Kontrol** | Mutabakat, doğrulanmamış varsayımlar, raporun kapsamadıkları |

İsimler **Türkçe alfabe sırasına** göre sıralı (İ→I'dan sonra, Ş→S'den sonra,
Ü→U'dan sonra). Python'un varsayılan sıralaması bu harfleri Z'den sonraya atıyor.

Ayrıntılı sayfa ve kolon tasarımı: [docs/OUTPUT-SPEC.md](docs/OUTPUT-SPEC.md)

### Mayıs 2026 sonucu

| | Mayıs | Haziran | Temmuz |
| --- | --- | --- | --- |
| Raporda yer alan kişi | 171 | 163 | 175 |
| mesai verisi olan | 145 | 145 | 144 |
| mesai verisi olmayan | 26 | 18 | 31 |
| personel listesinde olmayan (muhtemelen ayrılmış) | 11 | 9 | 9 |
| Kişi-gün kaydı | 1 823 | 2 822 | 1 729 |
| **Toplam çalışma süresi** | **17 103:58** | **27 166:19** | **16 078:44** |
| Şüpheli kayıt | 250 (175'i dahil edilmedi) | 427 (266) | 554 (449) |

**Temmuz sayıları eksik veriye dayanıyor** — Teknopark dosyası ayın 1–19'unu
kapsıyor. Karşılaştırma için kullanılmamalı.

Mayıs ve Haziran toplamları 2026-08-17'de yükseldi: öğle arası kesintisi kaldırıldı
ve gün "ilk giriş → son çıkış" olarak ölçülmeye başlandı. Mayıs için
eski değer `15 717:08` net / `17 009:01` brüt idi. Uzaktan çalışma günlerinde puantaja
otomatik yazılan nominal gün artık sayılmıyor, bu da bir miktar düşürdü.

## Geliştirme

```bash
python -m pytest          # 339 test
```

Doğrulama mekanizmaları:

- **Mutabakat değişmezi**: kişi toplamlarının toplamı == kabul edilen aralıkların
  toplamı. Tutmazsa bir kayıt çift sayılmış veya kaybolmuş demektir; `Kontrol`
  sayfası bunu yazar.
- **Blok toplamı çapraz kontrolü**: Teknopark dosyasındaki her kişi bloğu, dosyanın
  kendi "Dönemdeki Toplam Çalışma Süresi" rakamıyla karşılaştırılır. Şu an
  110/110 tutuyor. Bu kontrol, ayrıştırıcının satır kaybettiği gerçek bir hatayı
  yakaladı — sessizce yarım veriyle çalışıyordu.
- **Determinizm**: aynı girdiyle iki koşu, zaman damgası dışında 23 273 hücrenin
  hepsinde birebir aynı.

## Tasarımın iki temel kuralı

**1. Yapay zekâ çalışma anında devrede değildir.**
Tüm hesaplama düz Python. Aynı girdi her zaman aynı çıktıyı verir, her rakam elle
kontrol edilebilir. Bu sayılar bordroya gidecek ve ileride doğrudan personele
mail atılacak — orada tahmin yürüten bir sistem olmamalı.

**2. Hiçbir kayıt uydurulmaz, hiçbir kayıt sessizce kaybolmaz.**
Eksik çıkış kaydı "16:30 olsun" diye doldurulmaz. Önce aynı gün diğer lokasyonda
tam kayıt var mı diye bakılır; yoksa o gün 0 saat sayılır ve **Şüpheli Kayıtlar**
sayfasına kaynak satır numarasıyla yazılır. Rapor eksiği gizlemez, gösterir.

**3. Kural değişikliği YAML düzenlemesidir, kod değişikliği değil.**
Öğle arası kesintisi, günün nasıl ölçüldüğü, kısa gün eşiği — hepsi
`config/settings.yaml`'da. Bordroyu etkileyen üç anahtar **zorunlu**: eksik veya
hatalı yazılırsa program durur, sessizce eski kurala dönmez. Eski bir config dosyası
yanlışlıkla eski hesabı uygulayamaz.

## Yol haritası

| Faz | Kapsam | Durum |
| --- | --- | --- |
| 0 | Veri analizi ve planlama | ✅ Tamamlandı |
| 1 | Kişi başı aylık toplam çalışma süresi | Onay bekliyor |
| 2 | Fazla mesai, vardiya, Multinet, resmi tatil | Bekliyor |
| 3 | İzin entegrasyonu, mazeret, görevlendirme | Bekliyor |
| 4 | Kaynak dosya otomasyonu + otomatik personel maili | Bekliyor |
| 5 | Yıllık özet | Bekliyor |

Ayrıntı ve açık sorular: [docs/ROADMAP.md](docs/ROADMAP.md)

**Faz 4'ün mail kısmı iki cevaba bağlı** ve teknik değil, veri eksikliği:

- Personel listesinde **işe giriş / çıkış tarihi yok**. Ayrılmış birine maaş bilgisi
  maili gitmemeli; şu an "hâlâ çalışıyor mu" sorusunu veriden kesin cevaplayamıyoruz.
- Mesai kaydı hiç olmayan kişilere (Mayıs'ta 26) "bu ay 0 saat çalıştınız" maili
  gitmemeli — önce Macunköy kapsama sorusunun cevaplanması gerekiyor.

Kod tarafı bir günlük iş; bu ikisi çözülmeden başlanmamalı.

## Dökümanlar

| Dosya | İçerik |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Projede çalışacak AI ajanları için çalışma kuralları |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Müşteri talep listesi (MEYER toplantı dökümanından) |
| [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md) | Her kaynak dosyanın yapısı ve tespit edilen tüm hataları |
| [docs/DOMAIN-RULES.md](docs/DOMAIN-RULES.md) | Hesaplama kuralları — işin matematiği |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modül yapısı ve veri akışı |
| [docs/OUTPUT-SPEC.md](docs/OUTPUT-SPEC.md) | Çıktı Excel'inin sayfa sayfa tasarımı |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Alınan kararlar ve gerekçeleri (ADR) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fazlar, durum, açık sorular |
| [docs/HANDOVER.md](docs/HANDOVER.md) | Nerede kaldık, beklenen cevaplar — kısa |

Bu dosyalar geliştiriciler için. **Raporu kullanmak için hiçbirini okumak
gerekmez** — raporun `Kontrol` sayfası hangi kuralla çalıştığını kendi içinde yazar.

## Kişisel veri uyarısı

Kaynak dosyalar 162 çalışanın adı, sicil numarası, departmanı, günlük hareketleri ve
sağlık/doğum izni kayıtlarını içeriyor.

- `data/` klasörü git'e **dahil edilmez**. Gerçek bir dosyayı asla commit'leme.
- `gonderim-*.json` de dahil edilmez — raporun makine-okunur eşleniği isim, e-posta ve
  saat içeriyor.
- `config/personel.yaml` gerçek isim yazımlarını tuttuğu için git'te yok;
  `config/personel.example.yaml` onun yerine commit'lenir.
- Test verilerinde gerçek isim kullanılmaz.
- İzin dosyasındaki serbest metin açıklamalar (sağlık ve kişisel gerekçeler)
  rapora yazılmaz.
- Raporun içinde depoya ait hiçbir referans olmaz (`ADR-015`, `ROADMAP.md Q4` gibi).
  Raporu okuyan kişi kodu açmayacak; her açıklama kendi başına anlaşılır yazılır.

## Gereksinimler

- Python 3.11+ (test edilen: 3.12.13 ve 3.14.6)
- `openpyxl` (`.xlsx` / `.xlsm`), `xlrd` (`.xls`), `PyYAML`
- Pencere için ek bir şey gerekmez — `tkinter` standart kütüphanede

`pandas` kullanılmıyor — veri küçük, zor kısımlar düzensiz Excel yerleşimi ve
zaman aralığı birleştirme; ikisinde de faydası yok. `xlrd` sadece `.xls` okuyor,
Temmuz 2026'da Macunköy dosyası o formata döndüğü için eklendi.

Ağ erişimi gerektiren hiçbir paket yok; program internete bağlanamaz.
