"""Configuration loading and validation.

A typo in a config key must fail immediately, not produce a wrong number silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path

import yaml

from .normalize import display_name, name_key


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

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.minutes)


@dataclass(frozen=True)
class Plausibility:
    min_duration: timedelta
    max_duration: timedelta


@dataclass(frozen=True)
class Calendar:
    holidays: dict[date, str]
    half_days: frozenset[date]
    rest_weekdays: frozenset[int]     # 0 = Monday

    def label(self, day: date) -> str:
        if day in self.holidays:
            return "Resmi Tatil"
        if day.weekday() in self.rest_weekdays:
            return ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")[day.weekday()]
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
    )
    plaus = Plausibility(
        min_duration=timedelta(minutes=float(pl_raw.get("min_minutes", 5))),
        max_duration=timedelta(hours=float(pl_raw.get("max_shift_hours", 16))),
    )

    sources_raw = _require(raw, "sources", "settings.yaml")
    sources = {name: tuple(patterns) for name, patterns in sources_raw.items()}
    for needed in ("roster", "izin", "macunkoy", "teknopark"):
        if needed not in sources:
            raise ConfigError(f"settings.yaml:sources: '{needed}' deseni eksik")

    year = int(period.split("-")[0])
    cal_path = config_dir / f"takvim-{year}.yaml"
    cal_raw = _load_yaml(cal_path)
    holidays = {_as_date(k, str(cal_path)): str(v)
                for k, v in (cal_raw.get("holidays") or {}).items()}
    half_days = frozenset(_as_date(d, str(cal_path))
                          for d in (cal_raw.get("half_days") or []))
    rest_names = cal_raw.get("weekly_rest_days") or ["saturday", "sunday"]
    try:
        rest = frozenset(_WEEKDAYS[str(n).lower()] for n in rest_names)
    except KeyError as exc:
        raise ConfigError(f"{cal_path}: bilinmeyen gün adı {exc}") from exc
    calendar = Calendar(holidays=holidays, half_days=half_days, rest_weekdays=rest)

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
    )
