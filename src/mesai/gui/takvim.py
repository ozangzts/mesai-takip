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

The screen suggests nothing. It briefly marked the days on which almost nobody was
present, taken from the last run in the session — which meant it had nothing to say
until a report had been produced, and that is a strange thing for a calendar to depend
on. The check still exists where the data is: the report's `Kontrol` sheet names those
days for the month it just computed (ADR-041, ADR-044). Marking a day is a click and
takes no help.

One state, not two kinds. A day is a holiday or it is not — statutory, a closure, a
bridge day, all the same to the calculation, which was the argument for merging the two
categories the day they shipped (ADR-043). A click toggles. Whether a particular day was
the law's or the company's is still written beside it in the file, as a name, for
whoever is asked to confirm the list.
"""

from __future__ import annotations

import calendar as _calendar
import tkinter as tk
from datetime import date
from pathlib import Path

from .. import takvim_file
from ..config import ConfigError
from . import widgets as w
from .period import period_label

HOLIDAY = takvim_file.HOLIDAYS
# What a day is called when the operator marks one and the file had no name for it.
# Deliberately plain: the program does not know whether the day was the law's or the
# company's, and writing a guess into the file would be inventing a fact.
_DEFAULT_LABEL = "Tatil"
_DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

_CELL_WIDTH = 5
_MARK = w.ACCENT_SOFT


class CalendarScreen:
    def __init__(self, parent: tk.Misc, *, root: tk.Misc, config_dir: Path,
                 period: str | None = None) -> None:
        self.root = root
        self.config_dir = config_dir
        self.period = period or date.today().strftime("%Y-%m")
        # {date: kind}, only for days in the month on display. The rest of the file is
        # held separately and written back untouched — a year's other months are not
        # this screen's business and must survive a save.
        # {date: label} for the month on display. Other months are held apart and
        # written back untouched — a year's other months are not this screen's business.
        self.marks: dict[date, str] = {}
        self._other: dict[date, str] = {}
        self._cells: dict[date, tk.Label] = {}
        self._dirty = False

        self._build(parent)
        self.load(self.period)

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
        tk.Label(legend, text="  ", background=_MARK, highlightthickness=1,
                 highlightbackground=w.LINE).grid(row=0, column=0, sticky="w", pady=1)
        tk.Label(legend, text=" Tatil — çalışılmayan gün", background=w.BG,
                 foreground=w.MUTED, font=(w.FACE, 9)).grid(
            row=0, column=1, sticky="w")

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
    def load(self, period: str) -> None:
        """Show `period`, as the calendar file has it."""
        self.period = period
        year, month = self._year_month()
        entries = takvim_file.read(self._path())[HOLIDAY]
        self.marks = {}
        self._other = {}
        for day, label in entries.items():
            if (day.year, day.month) == (year, month):
                self.marks[day] = label
            else:
                self._other[day] = label
        self._dirty = False
        self._paint()

    def unsaved(self) -> str | None:
        """What would be lost by closing now, or None. Read by the shell.

        The month switch already asks, and closing the window is the same loss by a
        different route — measured: marks that were never saved are simply gone, which
        is correct behaviour and a bad surprise.
        """
        if not self._dirty:
            return None
        return (f"{period_label(self.period)} takviminde kaydedilmemiş işaretleme "
                f"var.")

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
        marked = day in self.marks
        cell = tk.Label(
            self.grid_frame, text=str(day.day), width=_CELL_WIDTH,
            font=(w.FACE, 10, "bold" if marked else "normal"),
            background=_MARK if marked else w.CARD,
            foreground=w.MUTED if weekend else w.INK,
            highlightthickness=1,
            highlightbackground=w.LINE if marked else w.CARD,
            pady=6, cursor="arrow" if weekend else "hand2")
        cell.grid(row=row, column=column, sticky="ew", padx=1, pady=1)
        if not weekend:
            # A weekend is already a rest day; letting it be marked would invite an
            # entry that changes nothing and reads as though it does.
            cell.bind("<Button-1>", lambda _event, d=day: self.toggle(d))
        return cell

    def toggle(self, day: date) -> None:
        """Holiday or not. A name the file already had is kept when it comes back."""
        if day in self.marks:
            self._forgotten = (day, self.marks.pop(day))
        else:
            previous = getattr(self, "_forgotten", (None, None))
            self.marks[day] = (previous[1] if previous[0] == day
                               else _DEFAULT_LABEL)
        self._dirty = True
        self._paint()

    def _describe(self) -> None:
        self.note.configure(
            text=f"{self._path().name} · bu ayda {len(self.marks)} tatil günü"
                 "\nBir güne tıklamak onu tatil yapar, tekrar tıklamak iş gününe "
                 "döndürür. Hafta sonları zaten tatil.",
            foreground=w.MUTED)
        self.status.configure(
            text="Kaydedilmemiş değişiklik var." if self._dirty else "",
            foreground=w.WARN if self._dirty else w.MUTED)
        w.set_enabled(self.save_button, self._dirty)

    # --- saving ------------------------------------------------------------
    def _save(self) -> None:
        # The month on display, plus every other month exactly as it was read.
        entries = dict(self._other)
        entries.update(self.marks)
        blocks = {HOLIDAY: entries}
        try:
            takvim_file.write(self._path(), blocks)
        except PermissionError:
            # The likely shape of this once the program is a single .exe: the config
            # folder sitting somewhere the user cannot write to. Naming the folder and
            # the remedy beats naming the Windows error code.
            self.status.configure(
                text=f"Kaydedilemedi — bu klasöre yazma izni yok:\n"
                     f"{self._path().parent}\nProgramı ve config klasörünü "
                     f"yazılabilir bir yere (Masaüstü, Belgeler) taşıyın.",
                foreground=w.BAD)
            return
        except (OSError, takvim_file.CalendarFileError, ConfigError) as exc:
            self.status.configure(text=f"Kaydedilemedi: {exc}", foreground=w.BAD)
            return
        self._dirty = False
        self._describe()
        self.status.configure(
            text=f"Kaydedildi: {self._path().name}. Raporu yeniden üretin — "
                 f"saatler bu takvimle hesaplanır.", foreground=w.OK)
