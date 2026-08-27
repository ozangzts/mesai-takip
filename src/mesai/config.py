"""Configuration loading and validation.

A typo in a config key must fail immediately, not produce a wrong number silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path

import yaml

from .normalize import display_name, fold, name_key


class ConfigError(Exception):
    pass


def _time(value: object, where: str) -> time:
    try:
        hh, mm = str(value).strip().split(":")[:2]
        return time(int(hh), int(mm))
    except Exception as exc:  # noqa: BLE001 - config errors must be loud
        raise ConfigError(f"{where}: geçersiz saat değeri {value!r}") from exc


def _require(mapping: dict, key: str, where: str):
    if key not in mapping:
        raise ConfigError(f"{where}: '{key}' anahtarı eksik")
    return mapping[key]


@dataclass(frozen=True)
class BreakRule:
    minutes: int
    window_from: time
    window_to: time
    min_workday: timedelta
    # False = pay through the break (ADR-016). The arithmetic below still exists and
    # is still tested; this only decides whether it is applied.
    deduct: bool = True

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.minutes)


@dataclass(frozen=True)
class Plausibility:
    max_duration: timedelta          # per person-day — flags a long day, never excludes
    short_day: timedelta             # per person-day — catches a barely-worked day
    # per interval, and only one WE repaired — rejects a failed midnight-crossing
    # guess. Deliberately separate from max_duration; see ADR-033.
    repair_max: timedelta = timedelta(hours=20)
    # per person-month — catches a month that is mostly unaccounted for. ADR-030.


@dataclass(frozen=True)
class Multinet:
    """When a day earns a Multinet. One rule, and it lives in `config/`.

    `daily_hours` is measured against the day's **gross** figure — first entry to last
    exit, which is what the report pays (ADR-015, ADR-016). Using net would mean the
    entitlement changed the day somebody flipped `break.deduct`, and that switch is
    about payroll hours, not about meal vouchers.

    Required, not defaulted, for the same reason as `daily_hours` and `break.deduct`: a
    config file predating this must not silently apply "no Multinet at all" and look
    like a month where nobody earned one. AGENTS §6.

    This is the SIMPLE daily rule that was asked for. `PRODUCT.md` §2 describes a
    weekly/monthly entitlement as well, still blocked on Q6 — so nothing here should be
    read as the final Multinet calculation.
    """
    daily_hours: timedelta


@dataclass(frozen=True)
class NominalDay:
    """The source system's placeholder for a workday it has no turnstile data for.

    Counted as worked time (ADR-017); this exists only so the report can tell a
    reader which records are placeholders and which are real punches.
    """
    source: str
    entry: time
    exit: time

    def matches(self, record_source: str, entry, exit_) -> bool:
        if record_source != self.source or entry is None or exit_ is None:
            return False
        return ((entry.hour, entry.minute) == (self.entry.hour, self.entry.minute)
                and (exit_.hour, exit_.minute) == (self.exit.hour, self.exit.minute))


@dataclass(frozen=True)
class Calendar:
    """Which days are not working days. A set of dates, and the weekly rest days.

    The holidays used to be a `{date: name}` map, with a second map beside it for the
    company's own closures. Both are gone (ADR-043, ADR-045): nothing in the program ever
    read a name or told the two kinds apart, and the person marking the days is the
    person who knows why. A day is a holiday or it is not.
    """
    holidays: frozenset[date]
    rest_weekdays: frozenset[int]     # 0 = Monday

    def label(self, day: date) -> str:
        if day in self.holidays:
            return "Tatil"
        return ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")[day.weekday()]

    def is_holiday(self, day: date) -> bool:
        return day in self.holidays

    def is_rest_day(self, day: date) -> bool:
        return day.weekday() in self.rest_weekdays

    def expected_workdays(self, year: int, month: int) -> list[date]:
        from calendar import monthrange
        days = []
        for d in range(1, monthrange(year, month)[1] + 1):
            day = date(year, month, d)
            if not self.is_rest_day(day) and not self.is_holiday(day):
                days.append(day)
        return days


@dataclass(frozen=True)
class Personnel:
    exclude_prefixes: tuple[str, ...]
    aliases: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    alias_pairs: tuple[tuple[str, str], ...] = ()   # (variant, canonical) for the report

    def resolve(self, key: tuple[str, str]) -> tuple[str, str]:
        return self.aliases.get(key, key)


DAILY_HOURS_METHODS = ("envelope", "union")
REMOTE_REPLACE_MODES = ("nominal_only", "always", "never")


@dataclass(frozen=True)
class Settings:
    shift_start: time
    shift_end: time
    brk: BreakRule
    plausibility: Plausibility
    sources: dict[str, tuple[str, ...]]
    worked_leave_types: frozenset[str]
    calendar: Calendar
    personnel: Personnel
    multinet: Multinet
    # "envelope" (first entry -> last exit) or "union" (sum of intervals). ADR-015.
    daily_hours: str = "envelope"
    # Optional: absent from the config means "no placeholder pattern known".
    nominal_day: NominalDay | None = None
    # "nominal_only" | "always" | "never" — see ADR-018.
    remote_replaces: str = "nominal_only"
    # Folded substring -> what the report calls that facility. Empty means the
    # roster's own wording is shown unchanged, which is the safe direction. ADR-026.
    facility_labels: tuple[tuple[str, str], ...] = ()

    def facility(self, raw: str | None) -> str:
        """What to call the facility the roster wrote as `raw`.

        Unmatched values pass through exactly as written. A label table that has
        fallen behind the source file must not silently rename the wrong site, and an
        unfamiliar name in the report is how somebody notices.
        """
        if not raw:
            return ""
        folded = fold(raw)
        for needle, label in self.facility_labels:
            if needle in folded:
                return label
        return raw


_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        example = path.with_name(path.stem + ".example" + path.suffix)
        if example.exists():
            raise ConfigError(
                f"config dosyası bulunamadı: {path}\n\n"
                f"Bu dosya gerçek personel isimleri içerdiği için git'e dahil "
                f"edilmiyor. Örnekten kopyalayıp doldurun:\n"
                f"    copy {example} {path}"
            )
        raise ConfigError(f"config dosyası bulunamadı: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: sözlük beklenirken {type(data).__name__} bulundu")
    return data


def _as_date(value: object, where: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"{where}: geçersiz tarih {value!r}") from exc


def _facility_labels(raw: object) -> tuple[tuple[str, str], ...]:
    """`{needle: label}` -> folded pairs, longest needle first.

    Longest first so a more specific entry can be added later without the shorter one
    shadowing it. Folding here rather than at every lookup keeps the comparison
    Turkish-safe and does it once.
    """
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ConfigError(
            "settings.yaml:facility_labels bir eşleme olmalı, örn. "
            "{MACUNKOY: \"Macunköy\"}")
    pairs = [(fold(str(needle)), str(label)) for needle, label in raw.items()]
    return tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True))


def load(config_dir: Path, period: str) -> Settings:
    """Load settings, the calendar for `period`'s year, and personnel overrides."""
    raw = _load_yaml(config_dir / "settings.yaml")

    shift = _require(raw, "normal_shift", "settings.yaml")
    brk_raw = _require(raw, "break", "settings.yaml")
    pl_raw = _require(raw, "plausibility", "settings.yaml")

    brk = BreakRule(
        minutes=int(_require(brk_raw, "minutes", "settings.yaml:break")),
        window_from=_time(_require(brk_raw, "window_from", "settings.yaml:break"),
                          "settings.yaml:break.window_from"),
        window_to=_time(_require(brk_raw, "window_to", "settings.yaml:break"),
                        "settings.yaml:break.window_to"),
        min_workday=timedelta(hours=float(brk_raw.get("min_workday_hours", 6.0))),
        deduct=bool(_require(brk_raw, "deduct", "settings.yaml:break")),
    )
    plaus = Plausibility(
        max_duration=timedelta(hours=float(pl_raw.get("max_shift_hours", 16))),
        repair_max=timedelta(hours=float(pl_raw.get("repair_max_hours", 20))),
        short_day=timedelta(hours=float(pl_raw.get("short_day_hours", 2))),
        # Absent means 0, which disables the check rather than inventing a threshold.
        # This one decides who a human is asked about, and a made-up default would
        # either accuse people or hide them, silently either way.
    )

    # A payroll-affecting switch: required, and validated rather than defaulted, so a
    # typo fails the run instead of quietly reverting to the other rule.
    daily_hours = str(_require(raw, "daily_hours", "settings.yaml")).strip().lower()
    if daily_hours not in DAILY_HOURS_METHODS:
        raise ConfigError(
            f"settings.yaml:daily_hours: {daily_hours!r} geçersiz — "
            f"beklenen: {' | '.join(DAILY_HOURS_METHODS)}"
        )

    # Payroll-affecting, so required and validated — same reasoning as daily_hours.
    remote_replaces = str(_require(
        raw, "remote_day_replaces_attendance", "settings.yaml")).strip().lower()
    if remote_replaces not in REMOTE_REPLACE_MODES:
        raise ConfigError(
            f"settings.yaml:remote_day_replaces_attendance: {remote_replaces!r} "
            f"geçersiz — beklenen: {' | '.join(REMOTE_REPLACE_MODES)}"
        )

    # Optional — it is a source-file quirk, not a rule, so a config without it is
    # valid and simply loses the placeholder/real distinction in the report.
    nominal_raw = raw.get("nominal_day")
    nominal = None
    if nominal_raw:
        nominal = NominalDay(
            source=str(_require(nominal_raw, "source", "settings.yaml:nominal_day")),
            entry=_time(_require(nominal_raw, "entry", "settings.yaml:nominal_day"),
                        "settings.yaml:nominal_day.entry"),
            exit=_time(_require(nominal_raw, "exit", "settings.yaml:nominal_day"),
                       "settings.yaml:nominal_day.exit"),
        )

    sources_raw = _require(raw, "sources", "settings.yaml")
    sources = {name: tuple(patterns) for name, patterns in sources_raw.items()}
    for needed in ("roster", "izin", "macunkoy", "teknopark"):
        if needed not in sources:
            raise ConfigError(f"settings.yaml:sources: '{needed}' deseni eksik")

    year = int(period.split("-")[0])
    cal_path = config_dir / f"takvim-{year}.yaml"
    cal_raw = _load_yaml(cal_path)
    # Read through `takvim_file`, the same reader the window writes with, so the two
    # halves cannot disagree about what the file means. It accepts the older shapes
    # (named dates, and the retired `admin_holidays` block) as well.
    from . import takvim_file

    holidays = frozenset(takvim_file.read(cal_path))

    rest_names = cal_raw.get("weekly_rest_days") or ["saturday", "sunday"]
    try:
        rest = frozenset(_WEEKDAYS[str(n).lower()] for n in rest_names)
    except KeyError as exc:
        raise ConfigError(f"{cal_path}: bilinmeyen gün adı {exc}") from exc
    calendar = Calendar(holidays=holidays, rest_weekdays=rest)

    per_raw = _load_yaml(config_dir / "personel.yaml")
    prefixes = tuple(str(p).upper() for p in (per_raw.get("exclude_prefixes") or []))
    aliases: dict[tuple[str, str], tuple[str, str]] = {}
    pairs: list[tuple[str, str]] = []
    for variant, canonical in (per_raw.get("aliases") or {}).items():
        vk, ck = name_key(variant), name_key(canonical)
        if vk == ck:
            continue    # the key already bridges them; the entry is harmless but useless
        aliases[vk] = ck
        pairs.append((display_name(variant), display_name(canonical)))

    return Settings(
        shift_start=_time(_require(shift, "start", "settings.yaml:normal_shift"),
                          "settings.yaml:normal_shift.start"),
        shift_end=_time(_require(shift, "end", "settings.yaml:normal_shift"),
                        "settings.yaml:normal_shift.end"),
        brk=brk,
        plausibility=plaus,
        sources=sources,
        worked_leave_types=frozenset(raw.get("worked_leave_types") or []),
        calendar=calendar,
        personnel=Personnel(exclude_prefixes=prefixes, aliases=aliases,
                            alias_pairs=tuple(pairs)),
        multinet=Multinet(daily_hours=timedelta(
            hours=float(_require(raw.get("multinet") or {}, "daily_hours",
                                 "settings.yaml:multinet")))),
        daily_hours=daily_hours,
        nominal_day=nominal,
        remote_replaces=remote_replaces,
        facility_labels=_facility_labels(raw.get("facility_labels")),
    )
