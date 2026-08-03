# Mesai Takip

DEICO personelinin aylık çalışma sürelerini, ham kart okuyucu (turnike) çıktılarından
otomatik olarak hesaplayıp tek bir temiz Excel raporuna dönüştüren araç.

> **Durum: Faz 1 çalışıyor.** Mayıs 2026 raporu üretiliyor. Fazla mesai, vardiya ve
> Multinet henüz yok (Faz 2). Üretilen rapor bir **doğrulama koşusudur**, bordro
> için nihai değildir — sebepleri raporun `Kontrol` sayfasında.

---

## Neden

Her ay iki ayrı lokasyondan gelen ham giriş-çıkış dosyaları İK tarafından elle
işleniyor. Kaynak veri sağlıklı değil: Macunköy dosyasındaki 1 209 satırın 388'inde
giriş veya çıkış kaydı eksik, 29 satırda süre negatif çıkıyor, 23 kayıt aslında
personel değil (ziyaretçi/geçici kart). Üstelik **76 kişi iki dosyada birden** yer
alıyor — düz toplama yapılırsa bu kişilerin saatleri çift sayılıyor. (Sebebi
anlaşıldı: bu kişilerin 75'i Teknopark'ta çalışıyor ve gün içinde Macunköy'e
gidiyor.)

Bu araç bunları otomatik ve her seferinde aynı şekilde hallediyor.

## Girdi dosyaları ve klasör yapısı

```
data/
├── personel/                       ← aya bağlı DEĞİL, bir kez konur
│   └── SYST03_TEMPIASUSERS.xlsx
├── raw/2026-05/                    ← her ay için ayrı klasör
│   ├── Macunköy Mayıs Mesai giriş-çıkış.xlsx
│   ├── Teknopark - Mayıs Mesai Takip Exceli.xlsx
│   └── HCMT34_MAYIS_IZIN.xlsx
└── out/2026-05/
    └── mesai-raporu-2026-05.xlsx   ← çıktı
```

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

Son satır **81 passed** demeli. Demiyorsa kurulum bozuk, aşağıdaki tabloya bak.

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

## En kısa yol: `rapor.cmd`

Ortamı aktive etmeye, klasöre girmeye gerek yok. Nereden çağırırsan çalışır:

```powershell
c:\Users\stajyer13\repos\mesai-takip\rapor.cmd --ay 2026-05
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
cd c:\Users\stajyer13\repos\mesai-takip

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
cd c:\Users\stajyer13\repos\mesai-takip
mesai rapor --ay 2026-06

# 3. Çıktıyı Drive'a yükle
#    data\out\2026-06\mesai-raporu-2026-06.xlsx
```

Adım 2'de dosya adlarını değiştirmen gerekmez, config'e dokunmak gerekmez.
İstersen `config/takvim-2026.yaml`'a o ayın resmi tatillerini ekle — sadece Günlük
Detay'daki gün etiketlerini etkiler, hesabı etkilemez.

Raporu paylaşmadan önce **`Kontrol` sayfasına bak**: mutabakat `TAMAM` mı, dönem
dışı kayıt var mı, hangi varsayımlar doğrulanmamış.

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
| İzin | içinde `IZIN` / `İZİN` | `HCMT34_HAZIRAN_IZIN.xlsx`, `hcmt34_haziran_izin.xlsx` |
| Macunköy | içinde `Macunköy` / `Macunkoy` | `Macunkoy Haziran giris-cikis (1).xlsx` |
| Teknopark | içinde `Teknopark` | `TEKNOPARK haziran puantaj FINAL v2.xlsx` |

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
   geçmediği için bulunamaz; program `Aranan desenler: ['*Teknopark*.xlsx']` diye
   söyler. Ya dosyayı yeniden adlandır, ya `config/settings.yaml`'a desen ekle.

## Çıkış kodları

| Kod | Anlamı |
| --- | --- |
| 0 | Başarılı |
| 2 | Girdi hatası — dosya yok, geçersiz/yanlış ay, klasörde iki ay |
| 3 | Dosya yapısı hatası — dışa aktarım formatı değişmiş |
| 4 | Çıktı dosyası kilitli — Excel'de açık |
| 9 | `rapor.cmd`: conda ortamı bulunamadı |

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
| **Sorulacaklar** | Kişi başına eksik kayıt günleri — İK'ya/IT'ye sormak için |
| **Şüpheli Kayıtlar** | Eksik/hatalı her kayıt, kaynak dosya ve satır numarasıyla |
| **İzin Özeti** | HCM sisteminden gelen izin günleri |
| **Kontrol** | Mutabakat, doğrulanmamış varsayımlar, raporun kapsamadıkları |

İsimler **Türkçe alfabe sırasına** göre sıralı (İ→I'dan sonra, Ş→S'den sonra,
Ü→U'dan sonra). Python'un varsayılan sıralaması bu harfleri Z'den sonraya atıyor.

Ayrıntılı sayfa ve kolon tasarımı: [docs/OUTPUT-SPEC.md](docs/OUTPUT-SPEC.md)

### Mayıs 2026 sonucu

| | |
| --- | --- |
| Raporda yer alan kişi | 171 |
| mesai verisi olan | 145 |
| mesai verisi olmayan | 26 |
| personel listesinde olmayan (muhtemelen ayrılmış) | 11 |
| Kişi-gün kaydı | 1 823 |
| Toplam brüt süre | 17 009:01 |
| Şüpheli kayıt | 242 (175'i toplama dahil edilmedi) |

## Geliştirme

```bash
python -m pytest          # 65 test
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

## Yol haritası

| Faz | Kapsam | Durum |
| --- | --- | --- |
| 0 | Veri analizi ve planlama | ✅ Tamamlandı |
| 1 | Kişi başı aylık toplam çalışma süresi | Onay bekliyor |
| 2 | Fazla mesai, vardiya, Multinet, resmi tatil | Bekliyor |
| 3 | İzin entegrasyonu, mazeret, görevlendirme | Bekliyor |
| 4 | Otomatik personel maili | Bekliyor |
| 5 | Yıllık özet | Bekliyor |

Ayrıntı ve açık sorular: [docs/ROADMAP.md](docs/ROADMAP.md)

## Dökümanlar

| Dosya | İçerik |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Projede çalışacak AI ajanları için çalışma kuralları |
| [docs/PRODUCT.md](docs/PRODUCT.md) | İK'nın talep listesi (MEYER toplantı dökümanından) |
| [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md) | Her kaynak dosyanın yapısı ve tespit edilen tüm hataları |
| [docs/DOMAIN-RULES.md](docs/DOMAIN-RULES.md) | Hesaplama kuralları — işin matematiği |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modül yapısı ve veri akışı |
| [docs/OUTPUT-SPEC.md](docs/OUTPUT-SPEC.md) | Çıktı Excel'inin sayfa sayfa tasarımı |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Alınan kararlar ve gerekçeleri (ADR) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fazlar, durum, açık sorular |

## Kişisel veri uyarısı

Kaynak dosyalar 162 çalışanın adı, sicil numarası, departmanı, günlük hareketleri ve
sağlık/doğum izni kayıtlarını içeriyor.

- `data/` klasörü git'e **dahil edilmez**. Gerçek bir dosyayı asla commit'leme.
- Test verilerinde gerçek isim kullanılmaz.
- İzin dosyasındaki serbest metin açıklamalar (sağlık ve kişisel gerekçeler)
  rapora yazılmaz.

## Gereksinimler

- Python 3.14+ (kurulu: 3.14.6)
- `openpyxl` (kurulu: 3.1.5), `PyYAML`

`pandas` kullanılmıyor — veri küçük, zor kısımlar düzensiz Excel yerleşimi ve
zaman aralığı birleştirme; ikisinde de faydası yok.
