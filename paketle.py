"""Build the shippable zip from `dist/MesaiTakip/`, refusing to ship anything private.

    python paketle.py            -> Masaüstüne MesaiTakip-<tarih>-<commit>.zip

**Why this is separate from `derle.cmd`.** `derle.cmd` produces `dist/MesaiTakip/`, and
that folder is also where the build gets *installed and tested* — so the real
`personel.yaml`, the real `gmail.yaml`, the roster workbook and generated reports all
end up in it during normal use. Zipping that folder directly is how a live Gmail app
password and 181 employees' names get handed to somebody.

That is not hypothetical. Both happened while packaging by hand on 2026-08-27, and both
were caught only because a check happened to be there:

* `config/gmail.yaml` and `config/personel.yaml` had been copied in for testing,
* `data/personel/SYST03_TEMPIASUSERS.xlsx` — the roster, 181 real people — was sitting
  in the folder the package creates for it.

So the zip is built from a **staging copy**, the private things are removed by name and
by rule, and then the result is checked again before it is written. The second check
matters: the first pass only knew about the two YAML files, and the roster walked past it.

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

# Removed by name. Both are git-ignored and both were found in the folder by hand.
ADIYLA = ("config/personel.yaml", "config/gmail.yaml", "arayuz-ayarlari.json")

# Nothing may ship with these extensions or shapes. A whitelist would be safer still,
# but `_internal/` holds a thousand files nobody should have to enumerate — so this is a
# deny rule written to catch the *kinds* of thing that carry personal data, rather than
# the two specific files that got caught once.
YASAK_UZANTI = (".xlsx", ".xls", ".xlsm", ".xlsb", ".docx")
YASAK_AD = ("personel.yaml", "gmail.yaml", "arayuz-ayarlari.json")


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


def _surum_dosyasi(hedef: Path, kisa: str, uzun: str) -> None:
    """What is in this zip and what the person installing it still has to do.

    Written into the package rather than only into the repository, because the question
    "hangi sürüm bu?" gets asked about a folder somebody was handed months ago.
    """
    (hedef / "SURUM.txt").write_text(
        "MESAI TAKIP - SURUM BILGISI\n"
        + "=" * 79 + "\n\n"
        f"Derleme tarihi : {date.today():%d.%m.%Y}\n"
        f"Kaynak kod     : {kisa}   ({uzun})\n"
        "Depo           : https://github.com/ozangzts/mesai-takip\n\n"
        "Bu klasorun tamami birlikte calisir. MesaiTakip.exe'yi klasorden cikarmayin.\n"
        "Nasil kullanilacagi: KULLANIM.txt\n\n"
        + "-" * 79 + "\n"
        "KURAN KISININ ELLE KOYMASI GEREKEN IKI DOSYA\n"
        + "-" * 79 + "\n\n"
        "  config\\personel.yaml    ornegi: config\\personel.example.yaml\n"
        "  config\\gmail.yaml       ornegi: config\\gmail.example.yaml\n\n"
        "Bunlar pakete BILEREK konmadi: biri gercek calisan adlarini, oteki bir giris\n"
        "bilgisini tasiyor.\n\n"
        "personel.yaml olmadan program calisir ama dokuz isim varyanti eslesmez ve o\n"
        "kisiler raporda IKI SATIR olarak gorunur, uyari da vermez. Kontrolu: raporun\n"
        "'Kontrol' sayfasi, bolum 7 - orada uygulanan eslestirmeler listelenir. Bos ise\n"
        "dosya yuklenmemis demektir.\n\n"
        + "-" * 79 + "\n"
        "NEREYE KONULACAK\n"
        + "-" * 79 + "\n\n"
        "Masaustu ya da Belgeler. 'Program Files' OLMAZ: program kendi ayarlarini ve\n"
        "isaretlenen tatilleri yanindaki config klasorune yaziyor, Windows oraya yazma\n"
        "izni vermiyor.\n",
        encoding="utf-8")


def _temizle(hedef: Path) -> list[str]:
    """Remove what must not ship. Returns what was removed, for the operator to read."""
    cikan: list[str] = []
    for parca in ADIYLA:
        yol = hedef / parca
        if yol.is_file():
            yol.unlink()
            cikan.append(parca)

    # `data/` exists in the package only to give the roster an obvious home; the note
    # explains what goes there. Anything else in it is the operator's own data — the
    # roster workbook, a generated report, a snapshot.
    data = hedef / "data"
    if data.is_dir():
        for yol in sorted(data.rglob("*")):
            if yol.is_file() and yol.name != NOT_DOSYASI:
                yol.unlink()
                cikan.append(str(yol.relative_to(hedef)))
    return cikan


def denetle(hedef: Path) -> list[str]:
    """Anything still present that must never ship. Empty means the package is clean.

    Run after `_temizle`, not instead of it. The point is that the rule is broader than
    the removals: a file nobody thought of is caught by its kind.
    """
    return sorted(
        str(yol.relative_to(hedef))
        for yol in hedef.rglob("*")
        if yol.is_file() and (yol.suffix.lower() in YASAK_UZANTI
                              or yol.name in YASAK_AD
                              or yol.name.startswith("gonderim-"))
    )


def main() -> int:
    if not KAYNAK.is_dir():
        print(f"HATA: {KAYNAK} yok. Once derle.cmd calistirin.")
        return 1

    kisa, uzun = _surum()
    with tempfile.TemporaryDirectory() as gecici:
        hedef = Path(gecici) / "MesaiTakip"
        shutil.copytree(KAYNAK, hedef)

        for parca in _temizle(hedef):
            print(f"  cikarildi: {parca}")
        _surum_dosyasi(hedef, kisa, uzun)

        kalan = denetle(hedef)
        if kalan:
            print("\nHATA: pakete girmemesi gereken dosyalar var, zip YAZILMADI:")
            for parca in kalan:
                print(f"  {parca}")
            return 2

        zip_yolu = (Path.home() / "Desktop"
                    / f"MesaiTakip-{date.today():%Y-%m-%d}-{kisa}.zip")
        with zipfile.ZipFile(zip_yolu, "w", zipfile.ZIP_DEFLATED) as arsiv:
            for yol in sorted(hedef.rglob("*")):
                if yol.is_file():
                    arsiv.write(yol, Path("MesaiTakip") / yol.relative_to(hedef))

    boyut = zip_yolu.stat().st_size / (1024 * 1024)
    print(f"\nTAMAM: {zip_yolu}  ({boyut:.1f} MB)")
    print("\nGitHub Releases'e yuklemek icin: depo sayfasi > Releases > Draft a new "
          "release > zip'i surukle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
