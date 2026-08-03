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
    SUSPICIOUS_SHORT = "SUSPICIOUS_SHORT"
    CROSS_SITE_EXTENDED = "CROSS_SITE_EXTENDED"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    NO_ATTENDANCE_DATA = "NO_ATTENDANCE_DATA"
    REMOTE_OVERLAP = "REMOTE_OVERLAP"
    MULTI_DAY_REMOTE = "MULTI_DAY_REMOTE"
    UNPARSEABLE_ROW = "UNPARSEABLE_ROW"


# Turkish label and severity for the report. "excluded" means the record
# contributed zero hours; "included" means it counted but deserves a look.
DESCRIPTIONS: dict[AnomalyKind, tuple[str, str]] = {
    AnomalyKind.MISSING_ENTRY: ("Giriş kaydı yok", "excluded"),
    AnomalyKind.MISSING_EXIT: ("Çıkış kaydı yok", "excluded"),
    AnomalyKind.EMPTY_RECORD: ("Giriş ve çıkış kaydı yok", "excluded"),
    AnomalyKind.NEGATIVE_DURATION: ("Negatif süre (gece geçişi düzeltildi)", "included"),
    AnomalyKind.IMPLAUSIBLE_DURATION: ("Süre inandırıcı değil", "excluded"),
    AnomalyKind.SUSPICIOUS_SHORT: ("Süre çok kısa", "included"),
    AnomalyKind.CROSS_SITE_EXTENDED: ("Diğer tesis kaydıyla tamamlandı", "included"),
    AnomalyKind.UNRESOLVED_IDENTITY: ("Kimlik eşleşmedi", "excluded"),
    AnomalyKind.DURATION_MISMATCH: ("Kaynak dosyadaki süre uyuşmuyor", "included"),
    AnomalyKind.NO_ATTENDANCE_DATA: ("Mesai verisi hiç yok", "excluded"),
    AnomalyKind.REMOTE_OVERLAP: ("Uzaktan çalışma kart kaydıyla çakışıyor", "included"),
    AnomalyKind.MULTI_DAY_REMOTE: ("Çok günlü uzaktan çalışma kaydı bölündü", "included"),
    AnomalyKind.UNPARSEABLE_ROW: ("Satır okunamadı", "excluded"),
}

_IMPACT = {
    "excluded": "Bu gün 0 saat sayıldı",
    "included": "Toplama dahil edildi",
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
    def impact(self) -> str:
        return _IMPACT[self.severity]


@dataclass
class Collector:
    items: list[Anomaly] = field(default_factory=list)

    def add(self, anomaly: Anomaly) -> None:
        self.items.append(anomaly)

    def extend(self, anomalies: list[Anomaly]) -> None:
        self.items.extend(anomalies)

    def count_by_key(self) -> dict[NameKey, int]:
        counts: dict[NameKey, int] = {}
        for a in self.items:
            if a.key:
                counts[a.key] = counts.get(a.key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self.items)
