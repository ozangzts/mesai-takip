"""The calendar work face: mark a month's non-working days, and save them to the file.

Why the window edits a **file** rather than holding the answer for one run: two runs of
the same month must produce the same workbook (AGENTS §2.1), and a report whose figures
depend on what was clicked in a dialog is not reproducible or auditable. So this screen
is an editor for `config/takvim-<yıl>.yaml`, nothing more — `takvim_file.py` does the
writing and keeps the file's own comments intact.

Why the window at all: the dates cannot be computed. The fixed-date statutory holidays
are in the file already (ADR-040), but the religious ones move every lunar year, and a
company closure — the site shut for a week in August — appears in no source file at all.
Somebody has to say so, and that somebody should not have to open a YAML file.

What makes it usable is the suggestion, not the grid: after a run, the days on which
almost nobody was present are marked with a `?`, with their headcount. That is how
15 July was found, and it is how a five-day closure will be found without anybody having
to remember which week it was. The program still marks nothing itself — see ADR-041.

Two kinds, kept apart because Phase 2 pays them differently and because HR will be
asked about them separately: `Resmi tatil` is law, `İdari tatil` is this company closing
its own site.
"""

from __future__ import annotations

import calendar as _calendar
import tkinter as tk
from datetime import date
from pathlib import Path

from .. import takvim_file
from ..config import ConfigError
from ..models import HolidayCandidate
from . import widgets as w
from .period import period_label

# What one click cycles through. `None` is an ordinary working day.
WORKDAY = None
STATUTORY = takvim_file.STATUTORY
ADMIN = takvim_file.ADMIN
_CYCLE = (WORKDAY, STATUTORY, ADMIN)

_DEFAULT_LABEL = {STATUTORY: "Resmi tatil", ADMIN: "İdari tatil — şirket kapalı"}
_KIND_NAME = {WORKDAY: "İş günü", STATUTORY: "Resmi tatil",
              ADMIN: "İdari tatil (şirket kapalı)"}
_DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

_CELL_WIDTH = 5
_MARK = {STATUTORY: w.ACCENT_SOFT, ADMIN: "#fdf0d5"}


class CalendarScreen:
    def __init__(self, parent: tk.Misc, *, root: tk.Misc, config_dir: Path,
                 period: str | None = None,
                 candidates: tuple[HolidayCandidate, ...] = ()) -> None:
        self.root = root
        self.config_dir = config_dir
        self.period = period or date.today().strftime("%Y-%m")
        self.candidates: dict[date, HolidayCandidate] = {}
        # {date: kind}, only for days in the month on display. The rest of the file is
        # held separately and written back untouched — a year's other months are not
        # this screen's business and must survive a save.
        self.marks: dict[date, str] = {}
        self._other: dict[str, dict[date, str]] = {}
        self._labels: dict[date, str] = {}
        self._cells: dict[date, tk.Label] = {}
        self._dirty = False

        self._build(parent)
        self.load(self.period, candidates)

    # --- layout ------------------------------------------------------------
    def _build(self, parent: tk.Misc) -> None:
        body = self.frame = tk.Frame(parent, background=w.BG)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)

        w.caption(body, "AY", row=0)
        head = tk.Frame(body, background=w.BG)
        head.grid(row=1, column=0, sticky="ew")
        head.columnconfigure(2, weight=1)
        w.button(head, "‹ Önceki", lambda: self._step(-1), primary=False).grid(
            row=0, column=0)
        w.button(head, "Sonraki ›", lambda: self._step(1), primary=False).grid(
            row=0, column=1, padx=(8, 0))
        self.month_label = tk.Label(head, background=w.BG, foreground=w.INK,
                                    font=(w.FACE, 12, "bold"), anchor="w")
        self.month_label.grid(row=0, column=2, sticky="w", padx=(16, 0))

        self.note = tk.Label(body, background=w.BG, foreground=w.MUTED,
                            font=(w.FACE, 9), anchor="w", justify="left")
        self.note.grid(row=2, column=0, sticky="ew", pady=(10, 14))

        w.caption(body, "GÜNLER — TIKLAYARAK İŞARETLE", row=3)
        self.grid_frame = tk.Frame(body, background=w.CARD,
                                   highlightthickness=1, highlightbackground=w.LINE)
        self.grid_frame.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        for column in range(7):
            self.grid_frame.columnconfigure(column, weight=1)

        legend = tk.Frame(body, background=w.BG)
        legend.grid(row=5, column=0, sticky="nw")
        for index, (kind, text) in enumerate(
                ((STATUTORY, "Resmi tatil"), (ADMIN, "İdari tatil (şirket kapalı)"))):
            tk.Label(legend, text="  ", background=_MARK[kind],
                     highlightthickness=1, highlightbackground=w.LINE).grid(
                row=index, column=0, sticky="w", pady=1)
            tk.Label(legend, text=f" {text}", background=w.BG, foreground=w.MUTED,
                     font=(w.FACE, 9)).grid(row=index, column=1, sticky="w")
        tk.Label(legend, text="?", background=w.BG, foreground=w.WARN,
                 font=(w.FACE, 9, "bold")).grid(row=2, column=0, sticky="e")
        self.candidate_note = tk.Label(
            legend, background=w.BG, foreground=w.MUTED, font=(w.FACE, 9),
            anchor="w", justify="left")
        self.candidate_note.grid(row=2, column=1, sticky="w")

        actions = tk.Frame(body, background=w.BG)
        actions.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(1, weight=1)
        self.save_button = w.button(actions, "Takvimi kaydet", self._save,
                                    primary=True)
        self.save_button.grid(row=0, column=0, sticky="w")
        self.status = tk.Label(actions, background=w.BG, foreground=w.MUTED,
                               font=(w.FACE, 9), anchor="w", justify="left")
        self.status.grid(row=0, column=1, sticky="w", padx=(12, 0))

    # --- loading -----------------------------------------------------------
    def load(self, period: str,
             candidates: tuple[HolidayCandidate, ...] = ()) -> None:
        """Show `period`, with the candidate days from the run that produced them."""
        self.period = period
        year, month = self._year_month()
        self.candidates = {c.date: c for c in candidates
                           if (c.date.year, c.date.month) == (year, month)}

        blocks = takvim_file.read(self._path())
        self.marks = {}
        self._other = {name: {} for name in takvim_file.BLOCKS}
        self._labels = {}
        for name, entries in blocks.items():
            for day, label in entries.items():
                if (day.year, day.month) == (year, month):
                    self.marks[day] = name
                    self._labels[day] = label
                else:
                    self._other[name][day] = label
        self._dirty = False
        self._paint()

    def _path(self) -> Path:
        return takvim_file.path_for(self.config_dir, self._year_month()[0])

    def _year_month(self) -> tuple[int, int]:
        year, month = self.period.split("-")
        return int(year), int(month)

    def _step(self, months: int) -> None:
        if self._dirty and not self._confirm_discard():
            return
        year, month = self._year_month()
        total = year * 12 + (month - 1) + months
        self.load(f"{total // 12:04d}-{total % 12 + 1:02d}")

    def _confirm_discard(self) -> bool:
        from tkinter import messagebox
        return messagebox.askyesno(
            "Kaydedilmemiş değişiklik",
            "Bu aydaki işaretlemeler kaydedilmedi. Yine de aya geçilsin mi?",
            parent=self.root)

    # --- painting ----------------------------------------------------------
    def _paint(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self._cells = {}

        for column, name in enumerate(_DAY_NAMES):
            tk.Label(self.grid_frame, text=name, background=w.CARD,
                     foreground=w.MUTED, font=(w.FACE, 8, "bold")).grid(
                row=0, column=column, sticky="ew", pady=(6, 2))

        year, month = self._year_month()
        for index, week in enumerate(_calendar.Calendar().monthdatescalendar(
                year, month), start=1):
            for column, day in enumerate(week):
                if day.month != month:
                    tk.Label(self.grid_frame, text="", background=w.CARD,
                             width=_CELL_WIDTH).grid(row=index, column=column)
                    continue
                self._cells[day] = self._cell(day, index, column)

        self.month_label.configure(text=period_label(self.period))
        self._describe()

    def _cell(self, day: date, row: int, column: int) -> tk.Label:
        weekend = day.weekday() >= 5
        kind = self.marks.get(day)
        text = str(day.day)
        if day in self.candidates and kind is None:
            text += " ?"
        cell = tk.Label(
            self.grid_frame, text=text, width=_CELL_WIDTH,
            font=(w.FACE, 10, "bold" if kind else "normal"),
            background=_MARK.get(kind, w.CARD),
            foreground=w.MUTED if weekend else (
                w.WARN if day in self.candidates and kind is None else w.INK),
            highlightthickness=1,
            highlightbackground=w.LINE if kind or day in self.candidates else w.CARD,
            pady=6, cursor="arrow" if weekend else "hand2")
        cell.grid(row=row, column=column, sticky="ew", padx=1, pady=1)
        if not weekend:
            # A weekend is already a rest day; letting it be marked would invite an
            # entry that changes nothing and reads as though it does.
            cell.bind("<Button-1>", lambda _event, d=day: self._cycle(d))
        return cell

    def _cycle(self, day: date) -> None:
        current = self.marks.get(day)
        nxt = _CYCLE[(_CYCLE.index(current) + 1) % len(_CYCLE)]
        if nxt is WORKDAY:
            self.marks.pop(day, None)
        else:
            self.marks[day] = nxt
        self._dirty = True
        self._paint()

    def _describe(self) -> None:
        counts = {kind: sum(1 for k in self.marks.values() if k == kind)
                  for kind in (STATUTORY, ADMIN)}
        parts = [f"{counts[STATUTORY]} resmi tatil",
                 f"{counts[ADMIN]} idari tatil"]
        self.note.configure(
            text=f"{self._path().name} · " + " · ".join(parts)
                 + "\nBir güne tıklamak sırayla: iş günü → resmi tatil → idari tatil.",
            foreground=w.MUTED)

        if self.candidates:
            unmarked = [c for day, c in sorted(self.candidates.items())
                        if day not in self.marks]
            if unmarked:
                lines = [f"{c.date.strftime('%d.%m')} — {c.people} kişi "
                         f"(normal gün {c.median})" for c in unmarked]
                self.candidate_note.configure(
                    text="Bu günlerde neredeyse kimse yoktu: "
                         + ",  ".join(lines) + "\nTatil miydi? İşaretlemek size ait — "
                         "program hiçbir günü kendisi işaretlemez.",
                    foreground=w.WARN)
            else:
                self.candidate_note.configure(
                    text="Boş görünen günlerin hepsi işaretlendi.",
                    foreground=w.MUTED)
        else:
            self.candidate_note.configure(
                text="Rapor üretildikten sonra, neredeyse kimsenin gelmediği günler "
                     "burada işaretlenir.", foreground=w.MUTED)
        self.status.configure(
            text="Kaydedilmemiş değişiklik var." if self._dirty else "",
            foreground=w.WARN if self._dirty else w.MUTED)
        w.set_enabled(self.save_button, self._dirty)

    # --- saving ------------------------------------------------------------
    def _save(self) -> None:
        blocks = {name: dict(self._other[name]) for name in takvim_file.BLOCKS}
        for day, kind in self.marks.items():
            # A label the file already had is kept — "Emek ve Dayanışma Günü" is worth
            # more than "Resmi tatil", and re-marking a day must not flatten it.
            previous = self._labels.get(day)
            keep = previous if previous and self.marks.get(day) == kind else None
            blocks[kind][day] = keep or _DEFAULT_LABEL[kind]
        try:
            takvim_file.write(self._path(), blocks)
        except (OSError, takvim_file.CalendarFileError, ConfigError) as exc:
            self.status.configure(text=f"Kaydedilemedi: {exc}", foreground=w.BAD)
            return
        self._labels = {day: blocks[kind][day] for day, kind in self.marks.items()}
        self._dirty = False
        self._describe()
        self.status.configure(
            text=f"Kaydedildi: {self._path().name}. Raporu yeniden üretin — "
                 f"saatler bu takvimle hesaplanır.", foreground=w.OK)
