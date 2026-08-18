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

DESCRIPTIONS: dict[AnomalyKind, tuple[str, str]] = {
    AnomalyKind.MISSING_ENTRY: ("Giriş kaydı yok", "excluded"),
    AnomalyKind.MISSING_EXIT: ("Çıkış kaydı yok", "excluded"),
    AnomalyKind.EMPTY_RECORD: ("Giriş ve çıkış kaydı yok", "excluded"),
    AnomalyKind.NEGATIVE_DURATION: ("Negatif süre (gece geçişi düzeltildi)", "included"),
    AnomalyKind.IMPLAUSIBLE_DURATION: ("Süre inandırıcı değil", "excluded"),
    AnomalyKind.SUSPICIOUS_SHORT: ("Süre çok kısa", "included"),
    AnomalyKind.SHORT_DAY: ("Günlük süre eşiğin altında", "included"),
    # The remote hours were used and a nominal placeholder was set aside. Expected,
    # so `info` — the day still has hours, just from the declaration (ADR-018).
    AnomalyKind.REMOTE_REPLACED_NOMINAL: (
        "Uzaktan çalışma günü, puantajdaki nominal gün yerine uzaktan saatler "
        "sayıldı", "info"),
    AnomalyKind.CROSS_SITE_EXTENDED: ("Diğer tesis kaydıyla tamamlandı", "included"),
    AnomalyKind.UNRESOLVED_IDENTITY: ("Kimlik eşleşmedi", "excluded"),
    AnomalyKind.DURATION_MISMATCH: ("Kaynak dosyadaki süre uyuşmuyor", "included"),
    AnomalyKind.NO_ATTENDANCE_DATA: ("Mesai verisi hiç yok", "excluded"),
    # Expected, not a defect: the Teknopark timesheet writes a nominal 9-hour day
    # for a workday with no turnstile data, and a remote-work day is one of the
    # things that triggers it. The union counts the shared time once. ADR-017.
    AnomalyKind.REMOTE_OVERLAP: (
        "Uzaktan çalışma günü, puantajda nominal gün olarak da kayıtlı", "info"),
    # The rare one: the person declared remote work and a turnstile really recorded
    # them. 2 of 39 in May 2026, 7 of 83 in June. This one is a genuine question.
    AnomalyKind.REMOTE_OVERLAP_REAL: (
        "Uzaktan çalışma beyanı var, o gün gerçek turnike kaydı da var", "included"),
    AnomalyKind.MULTI_DAY_REMOTE: ("Çok günlü uzaktan çalışma kaydı bölündü", "included"),
    AnomalyKind.UNPARSEABLE_ROW: ("Satır okunamadı", "excluded"),
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
