"""Anomalies are a first-class output, not a log.

Every input row ends up either in a computed total or in this list. A row that
vanishes is a bug; a row given an invented value is a worse bug.
See AGENTS.md §2.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from .models import NameKey


class AnomalyKind(StrEnum):
    MISSING_ENTRY = "MISSING_ENTRY"
    MISSING_EXIT = "MISSING_EXIT"
    EMPTY_RECORD = "EMPTY_RECORD"
    NEGATIVE_DURATION = "NEGATIVE_DURATION"
    IMPLAUSIBLE_DURATION = "IMPLAUSIBLE_DURATION"
    SUSPICIOUS_SHORT = "SUSPICIOUS_SHORT"      # one interval is implausibly brief
    SHORT_DAY = "SHORT_DAY"                    # the whole day is under the threshold
    REMOTE_REPLACED_NOMINAL = "REMOTE_REPLACED_NOMINAL"
    CROSS_SITE_EXTENDED = "CROSS_SITE_EXTENDED"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    NO_ATTENDANCE_DATA = "NO_ATTENDANCE_DATA"
    # Two kinds, because they are two different questions. See ADR-017.
    REMOTE_OVERLAP = "REMOTE_OVERLAP"              # nominal placeholder — expected
    REMOTE_OVERLAP_REAL = "REMOTE_OVERLAP_REAL"    # a real punch — worth asking
    MULTI_DAY_REMOTE = "MULTI_DAY_REMOTE"
    UNPARSEABLE_ROW = "UNPARSEABLE_ROW"


# Turkish label and severity for the report. Three levels, and the difference
# between the last two matters to the reader:
#
#   "excluded" — the record contributed zero hours. A real problem.
#   "included" — it counted, but something about it deserves a second look.
#   "info"     — it counted and this is the expected behaviour. Recorded so the
#                audit trail is complete, NOT because anything is wrong. Info
#                items do not count towards a person's `Şüpheli Kayıt` figure and
#                do not shade their summary row (ADR-017).
SEVERITIES = ("excluded", "included", "info")

# `label` is a keyword, not a sentence, because it is what somebody filters on: the
# people screen builds its dropdown from these, and a dropdown of full sentences cannot
# be scanned. `explanation` carries the meaning the short form drops, so the report is
# no less clear than before — the Sorulacaklar sheet prints it in its own column.
#
# Two pairs are deliberately split rather than sharing a word:
#
#   "Aralık çok kısa" / "Gün çok kısa"  — one reading under 5 min versus a whole day
#       under 2 h. Both used to read "Süre çok kısa", so a filter on one selected the
#       other's people too.
#   "Giriş yok" / "Çıkış yok"           — never "sadece giriş", which reads equally as
#       "only the entry exists" and "only the entry is missing" — opposite people.
#
# See ADR-027.
DESCRIPTIONS: dict[AnomalyKind, tuple[str, str, str]] = {
    AnomalyKind.MISSING_ENTRY: (
        "Giriş yok", "excluded",
        "Çıkış basılmış, giriş kaydı yok"),
    AnomalyKind.MISSING_EXIT: (
        "Çıkış yok", "excluded",
        "Giriş basılmış, çıkış kaydı yok"),
    AnomalyKind.EMPTY_RECORD: (
        "Giriş-çıkış yok", "excluded",
        "Satır var ama giriş de çıkış da boş"),
    AnomalyKind.NEGATIVE_DURATION: (
        "Gece geçişi", "included",
        "Çıkış girişten önce görünüyor; gece yarısını geçen vardiya düzeltildi"),
    AnomalyKind.IMPLAUSIBLE_DURATION: (
        "Aralık çok uzun", "excluded",
        "Tek aralık 16 saati aşıyor — okuma hatası olabilir"),
    AnomalyKind.SUSPICIOUS_SHORT: (
        "Aralık çok kısa", "included",
        "Tek aralık 5 dakikanın altında — aynı kartın iki kez okunması olabilir"),
    AnomalyKind.SHORT_DAY: (
        "Süre çok kısa", "included",
        "Günlük toplam 2 saatin altında"),
    # This is the one that fires under the shipped config, so it carries the plain
    # name. ADR-018 REMOVES the system's default day and counts the remote hours, so
    # nothing is left to overlap with — measured on May 2026: 35 days here, 0 in
    # REMOTE_OVERLAP below. Switch `remote_replaces` to "never" and the counts swap.
    AnomalyKind.REMOTE_REPLACED_NOMINAL: (
        "Uzaktan + sistem kaydı", "info",
        "Uzaktan çalışma günü; Teknopark kaydında kart okuması yok, sistem "
        "varsayılan tam gün yazmış. Sistemin günü yerine uzaktan saatler sayıldı"),
    AnomalyKind.CROSS_SITE_EXTENDED: (
        "Tesis birleştirme", "included",
        "Eksik kayıt, kişinin aynı gün diğer tesisteki kaydıyla tamamlandı"),
    AnomalyKind.UNRESOLVED_IDENTITY: (
        "İsim eşleşmedi", "excluded",
        "Personel listesinde bu ismin karşılığı bulunamadı"),
    AnomalyKind.DURATION_MISMATCH: (
        "Süre uyuşmazlığı", "included",
        "Hesaplanan süre, kaynak dosyanın kendi yazdığı süreyle aynı değil"),
    AnomalyKind.NO_ATTENDANCE_DATA: (
        "Mesai verisi yok", "excluded",
        "Dönem boyunca hiç kart kaydı yok"),
    # The same situation, handled the other way: both records kept and unioned. Only
    # reachable with `remote_replaces: never`, hence the qualifier — two kinds may not
    # share a label, because the label is the filter key.
    AnomalyKind.REMOTE_OVERLAP: (
        "Uzaktan + sistem kaydı (birleştirildi)", "info",
        "Uzaktan çalışma günü; Teknopark kaydında kart okuması yok, sistem "
        "varsayılan tam gün yazmış. İki kayıt da tutuldu, çakışan süre bir kez "
        "sayıldı"),
    AnomalyKind.REMOTE_OVERLAP_REAL: (
        "Uzaktan + kart kaydı", "included",
        "Uzaktan çalışma beyanı var ama o gün gerçek kart okuması da var — "
        "kişi binaya girmiş görünüyor"),
    AnomalyKind.MULTI_DAY_REMOTE: (
        "Çok günlü uzaktan", "included",
        "Tek izin satırı birden çok güne yayılmış, günlere bölündü"),
    AnomalyKind.UNPARSEABLE_ROW: (
        "Satır okunamadı", "excluded",
        "Kaynak dosyadaki satır ayrıştırılamadı"),
}

# The single source of truth for "what happened to this record". The report imports
# it rather than keeping its own copy, so adding a severity here cannot leave a sheet
# raising KeyError on a month-end run.
IMPACT_TEXT = {
    "excluded": "Bu gün 0 saat sayıldı",
    "included": "Toplama dahil edildi",
    "info": "Toplama dahil edildi — beklenen durum",
}


@dataclass(frozen=True)
class Anomaly:
    kind: AnomalyKind
    source: str
    source_row: int
    key: NameKey | None = None
    raw_name: str = ""
    date: date | None = None
    raw_entry: str = ""
    raw_exit: str = ""
    detail: str = ""

    @property
    def label(self) -> str:
        return DESCRIPTIONS[self.kind][0]

    @property
    def severity(self) -> str:
        return DESCRIPTIONS[self.kind][1]

    @property
    def explanation(self) -> str:
        """The sentence the short label leaves out. For the report, not for filters."""
        return DESCRIPTIONS[self.kind][2]

    @property
    def impact(self) -> str:
        return IMPACT_TEXT[self.severity]

    @property
    def is_problem(self) -> bool:
        """False for `info` items — expected behaviour, recorded for the audit trail.

        Anything that counts anomalies *as problems* must use this rather than
        testing severity, or expected behaviour ends up shading people's rows.
        """
        return self.severity != "info"


@dataclass
class Collector:
    items: list[Anomaly] = field(default_factory=list)

    def add(self, anomaly: Anomaly) -> None:
        self.items.append(anomaly)

    def extend(self, anomalies: list[Anomaly]) -> None:
        self.items.extend(anomalies)

    def count_by_key(self) -> dict[NameKey, int]:
        """Per-person count of actual problems — `info` items are not problems."""
        counts: dict[NameKey, int] = {}
        for a in self.items:
            if a.key and a.is_problem:
                counts[a.key] = counts.get(a.key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self.items)
