r"""Command line entry point. Wiring only — no business logic lives here.

    mesai rapor --ay 2026-05                             # data/raw/2026-05/
    mesai rapor --ay 2026-06 --girdi "G:\Drive\Mesai\2026-06"

Input files are discovered by glob pattern (config/settings.yaml:sources), so a
Drive-synced folder can be pointed at directly without renaming anything. One month
per input folder is a contract — see ADR-014.

Note the leading `r` on this docstring: Windows paths contain backslashes, and
`\2026` would otherwise be read as an octal escape.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from . import config
from . import snapshot
from .pipeline import InputError, run
from .readers import LayoutError
from .report.workbook import ReportLocked
from .rules.worktime import hhmm

PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")



def program_dir() -> Path:
    """Where the program keeps its own files — the snapshot, and later the mail log.

    Not the output folder: that one is what HR opens and should hold one workbook per
    month, nothing else. Not the current directory either, because the tool is invoked
    from anywhere. When frozen into an .exe, `sys.frozen` is set and the executable's
    own folder is the right home.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mesai", description="DEICO aylık mesai raporu üretici")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("rapor", help="Bir ay için Excel raporu üret")
    report.add_argument("--ay", required=True, metavar="YYYY-MM",
                        help="Rapor dönemi, örn. 2026-05")
    report.add_argument("--girdi", type=Path, default=None, metavar="KLASÖR",
                        help="Ham dosyaların bulunduğu klasör "
                             "(varsayılan: data/raw/<ay>)")
    report.add_argument("--cikti", type=Path, default=None, metavar="DOSYA",
                        help="Çıktı dosyası (varsayılan: "
                             "data/out/<ay>/mesai-raporu-<ay>.xlsx)")
    report.add_argument("--personel", type=Path, default=Path("data/personel"),
                        metavar="KLASÖR",
                        help="Personel listesinin bulunduğu klasör (varsayılan: "
                             "data/personel). Aya bağlı olmadığı için ayrı durur; "
                             "burada yoksa --girdi klasörüne de bakılır")
    report.add_argument("--config", type=Path, default=Path("config"),
                        metavar="KLASÖR", help="Config klasörü")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "rapor":
        return 2

    period: str = args.ay
    if not PERIOD_RE.match(period):
        print(f"HATA: --ay 'YYYY-MM' biçiminde olmalı, verilen: {period!r}",
              file=sys.stderr)
        return 2
    if not 1 <= int(period.split("-")[1]) <= 12:
        print(f"HATA: --ay içindeki ay 01-12 arasında olmalı, verilen: {period!r}",
              file=sys.stderr)
        return 2

    input_dir: Path = args.girdi or Path("data/raw") / period
    output: Path = args.cikti or (
        Path("data/out") / period / f"mesai-raporu-{period}.xlsx")

    if not input_dir.is_dir():
        print(f"HATA: girdi klasörü yok: {input_dir}", file=sys.stderr)
        return 2

    try:
        settings = config.load(args.config, period)
    except config.ConfigError as exc:
        print(f"CONFIG HATASI: {exc}", file=sys.stderr)
        return 2

    try:
        result = run(input_dir, output, period, settings, datetime.now(),
                     roster_dir=args.personel,
                     snapshot_path=snapshot.default_path(period, output))
    except LayoutError as exc:
        print(f"DOSYA YAPISI HATASI: {exc}", file=sys.stderr)
        return 3
    except InputError as exc:
        print(f"GİRDİ HATASI: {exc}", file=sys.stderr)
        return 2
    except ReportLocked as exc:
        print(f"YAZMA HATASI: {exc}", file=sys.stderr)
        return 4

    _report(result)
    # Non-zero so an unattended run is noticed. ARCHITECTURE.md: a scheduled job that
    # fails silently is not noticed until payroll. 5 = report written but incomplete.
    # Same code for both, because they mean the same thing to whoever is reading it:
    # the period is not fully covered, so the figures are not the month. ADR-020,
    # ADR-057.
    if result.get("partial_sources") or result.get("blank_workdays"):
        return 5
    return 0


def _report(result: dict) -> None:
    print(f"\n  Rapor yazıldı: {result['output']}")
    print(f"  {'-' * 58}")
    print(f"  Raporda yer alan kişi        : {result['people']}")
    print(f"    mesai verisi olan          : {result['with_attendance']}")
    print(f"    mesai verisi olmayan       : {result['without_attendance']}"
          f"   <- kart kaydı yok, ayı eksik")
    print(f"    personel listesinde olmayan: {result['not_in_roster']}"
          f"   <- ayrılmış olabilir")
    # The people the report has no row for at all. Printed beside the counts that are
    # blind to them, because they are the group a manual check cannot otherwise reach.
    # ADR-071.
    if result.get("roster_only"):
        print(f"  Personel listesinde olup kaydı olmayan: {result['roster_only']}"
              f"   <- elle bakılmalı, 'Kontrol' sayfasında")
    print(f"  Kişi-gün kaydı               : {result['workdays']}")
    print(f"  Toplam brüt süre             : {hhmm(result['gross'])}")
    for cov in result.get("partial_sources") or []:
        print("")
        print(f"  !! EKSİK VERİ: {cov.source} dosyası dönemin tamamını "
              f"içermiyor — {cov.trailing_missing[0]:%d.%m.%Y} ve sonrası yok "
              f"({cov.present}/{cov.expected} iş günü).")
        print("     Bu rapordaki saatler bordro için kullanılamaz.")
    bos = result.get("blank_workdays") or []
    if bos:
        print("")
        print(f"  !! BOŞ İŞ GÜNÜ: {len(bos)} beklenen iş gününde hiçbir tesiste "
              f"kayıt yok —")
        print("     " + ", ".join(f"{d:%d.%m}" for d in bos[:12])
              + (" ..." if len(bos) > 12 else ""))
        print("     O günler tatilse takvimde işaretlenmeli; değilse dosya eksik.")
    print(f"  Şüpheli kayıt                : {result['anomalies']}"
          f" ({result['excluded_anomalies']} tanesi toplama dahil edilmedi)")
    print(f"  {'-' * 58}")
    print("  Bu bir DOĞRULAMA koşusudur, bordro için nihai değildir.")
    print("  Varsayımlar ve mutabakat: raporun 'Kontrol' sayfası.\n")


if __name__ == "__main__":
    raise SystemExit(main())
