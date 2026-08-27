"""Build the shippable zip from `dist/MesaiTakip/`, refusing to ship what must not go.

    python paketle.py              -> temiz paket, gizli dosyalar cikarilmis
    python paketle.py --icerde     -> ic teslim paketi, gizli dosyalar DAHIL

**Why this is separate from `derle.cmd`.** `derle.cmd` produces `dist/MesaiTakip/`, and
that folder is also where the build gets *installed and tested* — so the real
`personel.yaml`, the real `gmail.yaml`, the roster workbook and generated reports all end
up in it during normal use. Zipping that folder directly is how a live Gmail app password
and 181 employees' names get handed to somebody.

Not hypothetical. Packaging by hand on 2026-08-27, all three were sitting in it, and the
first hand-written check — which looked for the two YAML files **by name** — reported the
zip clean while the roster workbook walked straight past it.

So: the zip is built from a **staging copy**, the private things are removed, and the
staged tree is checked **again** before anything is written. The second check is the
point. It works by *kind* — no spreadsheet, no `gonderim-*.json` — because the first pass
can only know about files somebody already thought of.

### Two audiences, two packages

`--icerde` includes `config/personel.yaml` and `config/gmail.yaml`, so the machine it is
unpacked on works immediately and nobody has to hand-copy anything. That is the right
package for a handover on a USB stick or an internal share, and the wrong one for
anywhere public: it carries real name spellings and a live app password, and a published
password has to be revoked rather than regretted. `SURUM.txt` says so inside the zip, and
the file name carries `-ICERIDE`.

The roster workbook and any generated report are stripped from **both**, always. Those
are the operator's own data, not part of the program.

Nothing here deletes anything from `dist/`. The operator's install stays as it is.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

KAYNAK = Path("dist") / "MesaiTakip"
NOT_DOSYASI = "BURAYA-PERSONEL-LISTESI-KOYUN.txt"

# The two files that carry real names and a credential.
GIZLI = ("config/personel.yaml", "config/gmail.yaml")

# This machine's own state: local paths, the chosen roster, one operator's note selection.
# Never shipped, in either mode — it is the wrong machine's settings, and it ships by
# accident rather than by decision.
YEREL = ("arayuz-ayarlari.json",)

# Nothing may ship with these extensions or shapes. A deny rule rather than a whitelist,
# because `_internal/` holds a thousand files nobody should have to enumerate — written
# to catch the *kinds* of thing that carry personal data.
YASAK_UZANTI = (".xlsx", ".xls", ".xlsm", ".xlsb", ".docx")


def _surum() -> tuple[str, str]:
    """`(short, long)` commit hash, or `("?", "?")` outside a checkout."""
    def git(*args: str) -> str:
        try:
            out = subprocess.run(("git", *args), capture_output=True, text=True,
                                 check=True)
        except (OSError, subprocess.CalledProcessError):
            return "?"
        return out.stdout.strip()
    return git("rev-parse", "--short", "HEAD"), git("rev-parse", "HEAD")


def _surum_dosyasi(hedef: Path, kisa: str, uzun: str, *, icerde: bool) -> None:
    """What is in this zip, and what the person installing it still has to do.

    Written into the package rather than only into the repository, because "hangi sürüm
    bu?" gets asked about a folder somebody was handed months ago.
    """
    cizgi = "-" * 75
    if icerde:
        orta = (
            "BU PAKET IC KULLANIM ICINDIR - PAYLASMAYIN\n"
            f"{cizgi}\n\n"
            "config\\personel.yaml ve config\\gmail.yaml PAKETE KONDU, yani program\n"
            "kutudan cikinca calisir.\n\n"
            "Bu zip'i public bir yere YUKLEMEYIN: gercek isim yazimlarini ve canli bir\n"
            "Gmail uygulama sifresini tasiyor. Yuklenmis bir sifre iptal edilmek\n"
            "zorundadir.\n\n"
        )
    else:
        orta = (
            "KURAN KISININ ELLE KOYMASI GEREKEN IKI DOSYA\n"
            f"{cizgi}\n\n"
            "  config\\personel.yaml    ornegi: config\\personel.example.yaml\n"
            "  config\\gmail.yaml       ornegi: config\\gmail.example.yaml\n\n"
            "Bunlar pakete BILEREK konmadi: biri gercek calisan adlarini, oteki bir\n"
            "giris bilgisini tasiyor.\n\n"
            "personel.yaml olmadan program calisir ama isim varyantlari eslesmez ve o\n"
            "kisiler raporda IKI SATIR olarak gorunur, uyari da vermez. Ustelik ayni\n"
            "kisinin iki tesisteki gunleri iki kisinin gunu sayildigi icin toplam\n"
            "SISER. Kontrolu: raporun 'Kontrol' sayfasi, bolum 7 - orada uygulanan\n"
            "eslestirmeler listelenir. Bos ise dosya yuklenmemis demektir.\n\n"
        )

    (hedef / "SURUM.txt").write_text(
        "MESAI TAKIP - SURUM BILGISI\n"
        + "=" * 75 + "\n\n"
        + f"Derleme tarihi : {date.today():%d.%m.%Y}\n"
        + f"Kaynak kod     : {kisa}   ({uzun})\n"
        + "Depo           : https://github.com/ozangzts/mesai-takip\n\n"
        + "Bu klasorun tamami birlikte calisir. MesaiTakip.exe'yi klasorden\n"
        + "cikarmayin. Nasil kullanilacagi: KULLANIM.txt\n\n"
        + cizgi + "\n" + orta
        + cizgi + "\n"
        + "NEREYE KONULACAK\n"
        + cizgi + "\n\n"
        + "Masaustu ya da Belgeler. 'Program Files' OLMAZ: program kendi ayarlarini ve\n"
        + "isaretlenen tatilleri yanindaki config klasorune yaziyor, Windows oraya\n"
        + "yazma izni vermiyor.\n\n"
        + "Zip'ten cikarirken: sag tik > Tumunu ayikla. Zip'in ICINDEN calistirmayin,\n"
        + "orada butun dosyalar salt okunur olur ve hicbir ayar kaydedilmez.\n",
        encoding="utf-8")


def _temizle(hedef: Path, *, icerde: bool) -> list[str]:
    """Remove what must not ship. Returns what was removed, for the operator to read."""
    cikan: list[str] = []
    atilacak = YEREL if icerde else YEREL + GIZLI
    for parca in atilacak:
        yol = hedef / parca
        if yol.is_file():
            yol.unlink()
            cikan.append(parca)

    # `data/` exists in the package only to give the roster an obvious home; the note
    # explains what goes there. Anything else in it is the operator's own data.
    data = hedef / "data"
    if data.is_dir():
        for yol in sorted(data.rglob("*")):
            if yol.is_file() and yol.name != NOT_DOSYASI:
                yol.unlink()
                cikan.append(str(yol.relative_to(hedef)))
    return cikan


def denetle(hedef: Path, *, icerde: bool = False) -> list[str]:
    """Anything still present that must never ship. Empty means the package is clean.

    Run after `_temizle`, not instead of it: the rule here is broader than the removals,
    so a file nobody thought of is caught by its kind.
    """
    adlar = {Path(p).name for p in YEREL}
    if not icerde:
        adlar |= {Path(p).name for p in GIZLI}
    return sorted(
        str(yol.relative_to(hedef))
        for yol in hedef.rglob("*")
        if yol.is_file() and (yol.suffix.lower() in YASAK_UZANTI
                              or yol.name in adlar
                              or yol.name.startswith("gonderim-"))
    )


def main() -> int:
    icerde = "--icerde" in sys.argv
    if not KAYNAK.is_dir():
        print(f"HATA: {KAYNAK} yok. Once derle.cmd calistirin.")
        return 1

    kisa, uzun = _surum()
    with tempfile.TemporaryDirectory() as gecici:
        hedef = Path(gecici) / "MesaiTakip"
        shutil.copytree(KAYNAK, hedef)

        for parca in _temizle(hedef, icerde=icerde):
            print(f"  cikarildi : {parca}")
        if icerde:
            for parca in GIZLI:
                if (hedef / parca).is_file():
                    print(f"  ICERIDE   : {parca} pakete KONDU")
                else:
                    print(f"  UYARI     : {parca} dist icinde yok, konulamadi")

        _surum_dosyasi(hedef, kisa, uzun, icerde=icerde)

        kalan = denetle(hedef, icerde=icerde)
        if kalan:
            print("\nHATA: pakete girmemesi gereken dosyalar var, zip YAZILMADI:")
            for parca in kalan:
                print(f"  {parca}")
            return 2

        etiket = "-ICERIDE" if icerde else ""
        zip_yolu = (Path.home() / "Desktop"
                    / f"MesaiTakip-{date.today():%Y-%m-%d}-{kisa}{etiket}.zip")
        with zipfile.ZipFile(zip_yolu, "w", zipfile.ZIP_DEFLATED) as arsiv:
            for yol in sorted(hedef.rglob("*")):
                if yol.is_file():
                    arsiv.write(yol, Path("MesaiTakip") / yol.relative_to(hedef))

    boyut = zip_yolu.stat().st_size / (1024 * 1024)
    print(f"\nTAMAM: {zip_yolu}  ({boyut:.1f} MB)")
    if icerde:
        print("\nBU PAKET GIZLI BILGI TASIYOR. Public bir Release'e yuklemeyin;")
        print("USB ya da ic paylasimla elden verin.")
    else:
        print("\nGitHub Releases'e yuklenebilir: depo > Releases > Draft a new release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
