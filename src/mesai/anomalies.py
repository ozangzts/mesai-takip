"""Anomalies are a first-class output, not a log.

Every input row ends up either in a computed total or in this list. A row that
vanishes is a bug; a row given an invented value is a worse bug.
See AGENTS.md §2.2.
"""

from __future__ import annotations

from collections.abc import Iterable
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
    SHORT_DAY = "SHORT_DAY"                    # the whole day is under the threshold
    REMOTE_REPLACED_NOMINAL = "REMOTE_REPLACED_NOMINAL"
    CROSS_SITE_EXTENDED = "CROSS_SITE_EXTENDED"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    LONG_DAY = "LONG_DAY"                  # the whole day is over the ceiling
    NO_ATTENDANCE_DATA = "NO_ATTENDANCE_DATA"
    # One question, not two: did the day carry a real punch as well as the
    # declaration? See ADR-017 and ADR-034.
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
# no less clear than before — the İnceleme Listesi sheet prints it in its own column.
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
# Families, in the order a filter list shows them. Frequency ordering alone scattered
# them: "Giriş yok" landed four rows below "Çıkış yok" because fewer people had it,
# which is exactly the neighbour somebody is looking for when they pick one of the two.
# Most actionable family first; "Diğer" last because it holds the leftovers.
GROUPS = ("Eksik kayıt", "Süre", "Uzaktan çalışma", "Diğer")

DESCRIPTIONS: dict[AnomalyKind, tuple[str, str, str, str]] = {
    AnomalyKind.MISSING_ENTRY: (
        "Giriş yok", "excluded",
        "Çıkış basılmış, giriş kaydı yok",
        "Eksik kayıt"),
    AnomalyKind.MISSING_EXIT: (
        "Çıkış yok", "excluded",
        "Giriş basılmış, çıkış kaydı yok",
        "Eksik kayıt"),
    # Was `Giriş-çıkış yok`, which the operator read as a compound noun — "no
    # entry-exit record" — where the point is the conjunction: *both* are missing. Under
    # the selection rule of ADR-053 that distinction is the whole thing, and the explicit
    # form does with words what an indent in the window failed to do: `Giriş yok (48)`
    # beside `Hem giriş hem çıkış yok (34)` reads as containment on its face. ADR-054.
    #
    # The explanation now carries what the label drops: a row EXISTS for that day. That
    # is what separates this from `Mesai verisi yok` — the day was expected and written
    # down, and only the times are absent.
    # Two shapes, one fact: no entry and no exit were recorded for that day. Either the
    # source file has a row with both times blank, or it has no row for that day at all
    # — the second was raising nothing until ADR-060, so somebody absent from the export
    # on five of twenty-two days carried no note. The `detail` on each record says which
    # of the two it was; the label says the thing the reader needs.
    AnomalyKind.EMPTY_RECORD: (
        "Hem giriş hem çıkış yok", "excluded",
        "O gün için giriş de çıkış da kaydedilmemiş — dosyada saatleri boş bir satır "
        "var ya da o güne ait hiç satır yok",
        "Eksik kayıt"),
    AnomalyKind.NEGATIVE_DURATION: (
        "Gece geçişi", "included",
        "Çıkış girişten önce görünüyor; gece yarısını geçen vardiya düzeltildi",
        "Süre"),
    # Was "Aralık çok uzun", and it was catching real 16-hour shifts. It now fires
    # only when the midnight-crossing repair produces an impossible figure — that is,
    # when OUR assumption failed, not when somebody worked a long day. ADR-032.
    # The threshold said 16 for the eleven weeks after ADR-033 moved the repair
    # ceiling to 20, so the report explained a rule the program was not applying.
    # `test_config.py` now checks every quoted threshold against the shipped config.
    # The "0 saat sayıldı" tail is gone: `IMPACT_TEXT` already prints it in its own
    # column, and a second number in the sentence is a second thing to keep in step.
    AnomalyKind.IMPLAUSIBLE_DURATION: (
        "Giriş-çıkış tutarsız (>20 saat)", "excluded",
        "Çıkış girişten önce görünüyor; gece geçişi varsayılıp düzeltilince süre "
        "20 saati aşıyor — kayıt kullanılamaz",
        "Süre"),
    # The threshold is in the label: somebody filtering a list should not have to look
    # up what "short" means, and the value is the whole content of the rule.
    AnomalyKind.LONG_DAY: (
        "Günlük süre çok uzun (>16 saat)", "included",
        "Günün ilk girişinden son çıkışına kadar geçen süre 16 saati aşıyor. "
        "Süre sayıldı — kontrol edilmeli",
        "Süre"),
    AnomalyKind.SHORT_DAY: (
        "Günlük süre çok kısa (<2 saat)", "included",
        "Günün ilk girişinden son çıkışına kadar geçen süre 2 saatin altında",
        "Süre"),
    # The label and the explanation describe the SITUATION; what was done about it
    # varies from day to day and lives in each record's own detail line. A second kind
    # used to carry the case where the replacement stood down, and the difference
    # between the two labels was invisible to everybody but the code — one day in two
    # months, reading as a third kind of remote work. ADR-034.
    AnomalyKind.REMOTE_REPLACED_NOMINAL: (
        "Uzaktan + sistem kaydı", "info",
        "Uzaktan çalışma günü; Teknopark kaydında kart okuması yok, sistem "
        "varsayılan tam gün yazmış. Çakışan süre bir kez sayıldı",
        "Uzaktan çalışma"),
    AnomalyKind.CROSS_SITE_EXTENDED: (
        "Tesis birleştirme", "included",
        "Eksik kayıt, kişinin aynı gün diğer tesisteki kaydıyla tamamlandı",
        "Diğer"),
    AnomalyKind.UNRESOLVED_IDENTITY: (
        "İsim eşleşmedi", "excluded",
        "Personel listesinde bu ismin karşılığı bulunamadı",
        "Diğer"),
    AnomalyKind.DURATION_MISMATCH: (
        "Süre uyuşmazlığı", "included",
        "Hesaplanan süre, kaynak dosyanın kendi yazdığı süreyle aynı değil",
        "Süre"),
    AnomalyKind.NO_ATTENDANCE_DATA: (
        "Mesai verisi yok", "excluded",
        "Dönem boyunca hiç kart kaydı yok",
        "Eksik kayıt"),
    AnomalyKind.REMOTE_OVERLAP_REAL: (
        "Uzaktan + kart kaydı", "included",
        "Uzaktan çalışma beyanı var ama o gün gerçek kart okuması da var — "
        "kişi binaya girmiş görünüyor",
        "Uzaktan çalışma"),
    AnomalyKind.MULTI_DAY_REMOTE: (
        "Çok günlü uzaktan", "included",
        "Tek izin satırı birden çok güne yayılmış, günlere bölündü",
        "Uzaktan çalışma"),
    AnomalyKind.UNPARSEABLE_ROW: (
        "Satır okunamadı", "excluded",
        "Kaynak dosyadaki satır ayrıştırılamadı",
        "Diğer"),
}

# One note is a STRICTER CASE of two others, and selecting on it has to say so.
#
# `Hem giriş hem çıkış yok` is a day with no entry *and* no exit — so it is also a day
# with no
# entry, and a day with no exit. The labels read as predicates ("girişi yok"), and a
# both-missing day satisfies both of them. Ticking `Giriş yok` and not getting those
# days back is the reading nobody expects.
#
# This is a **selection** relation, not a reporting one, and the difference is the whole
# design. The report states what happened to a record: a day with neither punch is one
# row, labelled `Hem giriş hem çıkış yok`, and expanding it into three rows would triple
# the
# sheet and invent two facts. The filter answers "who do I write to", where the broader
# reading is the correct one. So the counts in the window are deliberately larger than
# the row counts in `İnceleme Listesi`, and that is not a discrepancy — see ADR-053.
#
# Consequence to know before adding an entry here: the counts stop partitioning. Before
# this, June's 147 + 20 + 80 punch days summed to 247 with no overlap; now the same day
# is in two filters. Anything that ADDS note counts together is wrong.
IMPLIES: dict[str, tuple[str, ...]] = {
    "Hem giriş hem çıkış yok": ("Giriş yok", "Çıkış yok"),
}


def with_implied(labels: Iterable[str]) -> frozenset[str]:
    """`labels`, plus every broader note they also satisfy.

    The one place the relation is applied. Every filter, count and day selection goes
    through it, so the window cannot show 48 and hand back 15.
    """
    found = set(labels)
    for label in tuple(found):
        found.update(IMPLIES.get(label, ()))
    return frozenset(found)


# A day's tags, in words. `merge.py` sets short internal names on a WorkDay; the daily
# detail sheet printed them raw — `kısa-gün`, `uzaktan-çakışma`, and two that differ by
# one word: `çapraz-tesis` and `çapraz-eşleşti`. That was a THIRD vocabulary for facts
# the rest of the program already had names for, and the operator asked what the
# difference between the two cross ones was, which is the question a leaked identifier
# always produces. ADR-050.
#
# Where a tag means the same thing as a note label, it uses the label's exact words. The
# two that have no label say what they are:
#
#   çapraz-tesis    an interval carrying BOTH sites' records — the person appears in
#                   two files at the same hours, and the overlap was counted once.
#   çapraz-eşleşti  a MISSING punch resolved from the other site's record. Sometimes
#                   that added time (then the `Tesis birleştirme` note is raised too),
#                   sometimes the stamp simply fell inside a known interval and nothing
#                   had to be added — which is why this is broader than that note and
#                   cannot borrow its words.
TAG_TEXT = {
    "uzaktan": "Uzaktan çalışma",
    "uzaktan-çakışma": "Uzaktan + kart kaydı",
    "gece-geçişi": "Gece geçişi",
    "kısa-gün": "Günlük süre çok kısa (<2 saat)",
    "uzun-gün": "Günlük süre çok uzun (>16 saat)",
    "çapraz-tesis": "İki tesisin kaydı çakışıyor",
    "çapraz-eşleşti": "Eksik kayıt diğer tesisten tamamlandı",
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
    def group(self) -> str:
        return DESCRIPTIONS[self.kind][3]

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

    def labels_by_key(self) -> dict[NameKey, tuple[str, ...]]:
        """Per-person problem labels, in the order every list in the program uses.

        Family first, then declaration order — the same ordering as the filter list and
        the snapshot (ADR-029), so a person's notes read the same way wherever they are
        printed. This exists because they were NOT the same: the monthly summary's `Not`
        column was five hand-written strings, four of them re-wordings of a label
        (`Ayın çoğu açıklanmıyor` for `Ay büyük ölçüde boş`) and the other eleven labels
        missing entirely. See ADR-049.

        `info` items are excluded for the same reason they are excluded from the count:
        expected behaviour is not somebody's note (ADR-017).
        """
        family = {label: group for label, _s, _e, group in DESCRIPTIONS.values()}
        order = {name: index for index, name in enumerate(GROUPS)}
        declared = {label: index for index, (label, _s, _e, _g)
                    in enumerate(DESCRIPTIONS.values())}

        found: dict[NameKey, set[str]] = {}
        for anomaly in self.items:
            if anomaly.key and anomaly.is_problem:
                found.setdefault(anomaly.key, set()).add(anomaly.label)
        return {
            key: tuple(sorted(
                labels,
                key=lambda label: (order.get(family.get(label, ""), len(GROUPS)),
                                   declared.get(label, len(declared)), label)))
            for key, labels in found.items()}

    def count_by_key(self) -> dict[NameKey, int]:
        """Per-person count of actual problems — `info` items are not problems."""
        counts: dict[NameKey, int] = {}
        for a in self.items:
            if a.key and a.is_problem:
                counts[a.key] = counts.get(a.key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self.items)
