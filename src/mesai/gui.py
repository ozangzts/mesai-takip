"""Desktop window over the same `pipeline.run()` the CLI calls.

The person who runs this monthly does not use a terminal, so "open a console and pass
--ay" is not a deliverable. This module exists to remove that requirement and nothing
else: **it contains no business logic.** Every figure it shows was computed by the
pipeline; every rule it mentions came from `Settings`. `ARCHITECTURE.md` §3 anticipated
this — `pipeline.py` was split out from `cli.py` precisely so a second front end could
drive the same run.

Three deliberate choices:

* **tkinter**, from the standard library. No new dependency, packages cleanly into a
  single executable, and keeps ADR-005 intact — no network, nothing to configure.
* **No default input folder.** The tool used to guess `data/raw/<month>`; a guess that
  is wrong is worse than an empty field, because the user cannot tell it happened. They
  pick the folder holding the three exports, and the window immediately reports what it
  found there. The choice is remembered for next month.
* **The work runs on a worker thread.** The pipeline takes a few seconds; on the UI
  thread the window would grey out and Windows would label it "not responding".

The layout is intentionally plain. It will grow — filtering people by problem before
mailing, deselecting individuals by hand — and the seams for that are `snapshot.py`
(which already answers "who has which problem") plus this module's `_Result` object.
Nothing here should ever start computing on its own.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from . import config, snapshot
from .cli import program_dir
from .pipeline import InputError, period_bounds, run
from .normalize import fold
from .readers import LayoutError, find_sources
from .report.workbook import ReportLocked
from .rules.worktime import hhmm

WINDOW_TITLE = "Mesai Raporu"

# Remembered between runs so the folder is chosen once, not every month. Plain JSON
# next to the program; it holds a path, never employee data.
_SETTINGS_FILE = "arayuz-ayarlari.json"

_MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
           "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")

# The three monthly exports, in the order a reader expects to see them listed.
_SOURCES = (("macunkoy", "Macunköy giriş-çıkış"),
            ("teknopark", "Teknopark puantaj"),
            ("izin", "İzin (HCM)"))

_OK = "#1b7f3a"
_WARN = "#a86500"
_BAD = "#b3261e"
_MUTED = "#5f6368"


@dataclass
class _Result:
    """What a finished run produced, in the form the window needs to render it."""
    ok: bool
    heading: str
    lines: tuple[str, ...]
    colour: str
    output: Path | None = None
    snapshot: Path | None = None


def period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{_MONTHS[int(month) - 1]} {year}"


def describe_folder(folder: Path, settings) -> tuple[bool, tuple[str, ...]]:
    """What the chosen folder contains, and whether it is usable.

    Runs before any reading, so a wrong folder is caught while the user is still
    looking at the field rather than after a failed run. Reports every source, present
    or not — "two of three found" is more useful than the first error.
    """
    if not folder or not folder.is_dir():
        return False, ("Klasör seçilmedi.",)

    lines: list[str] = []
    complete = True
    for key, label in _SOURCES:
        matches = find_sources(folder, settings.sources[key])
        if not matches:
            complete = False
            lines.append(f"✗ {label}: bulunamadı")
        elif len(matches) > 1:
            complete = False
            names = ", ".join(p.name for p in matches[:3])
            lines.append(f"✗ {label}: {len(matches)} dosya eşleşti ({names})")
        else:
            lines.append(f"✓ {label}: {matches[0].name}")
    return complete, tuple(lines)


# Nobody names their folders the way the tool would like. Observed in practice:
# `2026-07`, `06-2026`, `Temmuz 2026`. Rather than demand one spelling, recognise the
# ones a person would plausibly type — and refuse the genuinely ambiguous ones.
_YEAR_MIN, _YEAR_MAX = 2000, 2099

# Folded (ASCII, uppercase) Turkish month names -> number. Folding matters: `MAYIS`
# and `MAYıS` must both match, which bare .upper() gets wrong in Turkish.
_MONTH_BY_NAME = {fold(name): number for number, name in enumerate(_MONTHS, start=1)}

# Two numbers with an optional separator, or six run-together digits.
_NUMERIC = re.compile(r"(?<!\d)(\d{1,4})\s*[-_./\\ ]\s*(\d{1,4})(?!\d)")
_SIX_DIGITS = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _is_year(value: int) -> bool:
    return _YEAR_MIN <= value <= _YEAR_MAX


def _is_month(value: int) -> bool:
    return 1 <= value <= 12


def parse_period(text: str) -> str | None:
    """Normalise a human spelling of a month into `YYYY-MM`, or None if unclear.

    Accepts, in any of `- _ . / \\ space` or run together:
        2026-07   2026-7   202607   2026 Temmuz
        07-2026   7-2026   072026   Temmuz 2026
    and finds them inside a longer name (`Mesai 2026-07 Girdi`).

    **Refuses rather than guesses** when the year is not identifiable — `03-04` could
    be March 2004 or April 2003, and picking one silently is exactly the kind of
    plausible-wrong answer this project exists to avoid. The order is resolved by
    which part is a four-digit year, never by assuming a convention.
    """
    if not text:
        return None
    raw = text.strip()

    # A month NAME plus a year settles the order on its own.
    folded = fold(raw)
    for name, number in _MONTH_BY_NAME.items():
        if name in folded:
            for match in re.finditer(r"(?<!\d)(\d{4})(?!\d)", raw):
                if _is_year(int(match.group(1))):
                    return f"{int(match.group(1))}-{number:02d}"
            return None                      # month named, year missing or implausible

    for first, second in _NUMERIC.findall(raw):
        a, b = int(first), int(second)
        year_first = len(first) == 4 and _is_year(a) and _is_month(b)
        year_second = len(second) == 4 and _is_year(b) and _is_month(a)
        if year_first and not year_second:
            return f"{a}-{b:02d}"
        if year_second and not year_first:
            return f"{b}-{a:02d}"
        # Neither part is a four-digit year, or somehow both are: ambiguous, refuse.

    for (digits,) in ((m.group(1),) for m in _SIX_DIGITS.finditer(raw)):
        head, tail = int(digits[:4]), int(digits[4:])
        if _is_year(head) and _is_month(tail):
            return f"{head}-{tail:02d}"
        head2, tail2 = int(digits[:2]), int(digits[2:])
        if _is_year(tail2) and _is_month(head2):
            return f"{tail2}-{head2:02d}"
    return None


def guess_period(folder: Path) -> str | None:
    """The month this folder is for, read off its own name then its parent's."""
    for candidate in (folder.name, folder.parent.name if folder.parent else ""):
        period = parse_period(candidate)
        if period:
            return period
    return None


class App:
    def __init__(self, root: tk.Tk, config_dir: Path | None = None,
                 roster_dir: Path | None = None) -> None:
        self.root = root
        self.base = program_dir()
        self.config_dir = config_dir or (self.base / "config")
        self.roster_dir = roster_dir or (self.base / "data" / "personel")
        self.folder: Path | None = None
        self._queue: queue.Queue[_Result] = queue.Queue()
        self._running = False

        root.title(WINDOW_TITLE)
        root.minsize(660, 430)
        self._build()
        self._restore()

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}
        frame = ttk.Frame(self.root, padding=14)
        frame.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text="Kaynak klasör", font=("Segoe UI", 9, "bold")) \
            .grid(row=0, column=0, sticky="w", **pad)
        self.folder_var = tk.StringVar(value="")
        entry = ttk.Entry(frame, textvariable=self.folder_var, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frame, text="Gözat…", command=self._choose) \
            .grid(row=0, column=2, sticky="e", **pad)

        self.folder_note = tk.Text(frame, height=4, relief="flat", wrap="word",
                                   background=self.root.cget("background"),
                                   font=("Segoe UI", 9), borderwidth=0)
        self.folder_note.grid(row=1, column=0, columnspan=3, sticky="ew",
                              padx=12, pady=(0, 4))
        self.folder_note.configure(state="disabled")

        ttk.Label(frame, text="Dönem", font=("Segoe UI", 9, "bold")) \
            .grid(row=2, column=0, sticky="w", **pad)
        self.period_var = tk.StringVar(value="")
        period_row = ttk.Frame(frame)
        period_row.grid(row=2, column=1, columnspan=2, sticky="ew", **pad)
        self.period_box = ttk.Combobox(period_row, textvariable=self.period_var,
                                       width=14, values=self._period_choices())
        self.period_box.grid(row=0, column=0, sticky="w")
        ttk.Label(period_row, foreground=_MUTED, font=("Segoe UI", 8),
                  text="klasör adından okunur · elle de yazılabilir: "
                       "2026-07 · 07-2026 · Temmuz 2026")             .grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.run_button = ttk.Button(frame, text="Rapor Oluştur",
                                     command=self._start, state="disabled")
        self.run_button.grid(row=3, column=0, columnspan=3, sticky="ew", padx=12,
                             pady=(10, 4))

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", padx=12)

        self.result = tk.Text(frame, height=11, relief="solid", borderwidth=1,
                              wrap="word", font=("Segoe UI", 9), padx=10, pady=8)
        self.result.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=12,
                         pady=(10, 6))
        self.result.configure(state="disabled")
        self.result.tag_configure("heading", font=("Segoe UI", 10, "bold"))
        for name, colour in (("ok", _OK), ("warn", _WARN), ("bad", _BAD),
                             ("muted", _MUTED)):
            self.result.tag_configure(name, foreground=colour)

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="e", padx=12, pady=(0, 4))
        self.open_report = ttk.Button(buttons, text="Raporu Aç", state="disabled",
                                      command=self._open_report)
        self.open_report.grid(row=0, column=0, padx=4)
        self.open_folder = ttk.Button(buttons, text="Klasörü Aç", state="disabled",
                                      command=self._open_folder)
        self.open_folder.grid(row=0, column=1, padx=4)

        self._last_output: Path | None = None

    def _period_choices(self) -> list[str]:
        """Months already present under the chosen folder's parent, newest first.

        Only a convenience — the field stays editable, because a folder holding one
        month's files need not be named after it.
        """
        if self.folder is None:
            return []
        found = {guess_period(self.folder)} if guess_period(self.folder) else set()
        parent = self.folder.parent
        if parent.is_dir():
            for child in parent.iterdir():
                if child.is_dir():
                    period = guess_period(child)
                    if period:
                        found.add(period)
        return sorted((p for p in found if p), reverse=True)

    # --- persistence -------------------------------------------------------
    def _settings_path(self) -> Path:
        return self.base / _SETTINGS_FILE

    def _restore(self) -> None:
        try:
            saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
            folder = Path(saved["folder"])
        except (OSError, ValueError, KeyError):
            self._describe()
            return
        if folder.is_dir():
            self._set_folder(folder)
        else:
            # The remembered folder is gone — a Drive letter that did not mount, a
            # renamed share. Say so rather than silently starting empty.
            self._describe(extra=(f"Son kullanılan klasör bulunamadı: {folder}",))

    def _remember(self) -> None:
        if self.folder is None:
            return
        try:
            self._settings_path().write_text(
                json.dumps({"folder": str(self.folder)}, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass        # a read-only install is not worth failing a run over

    # --- actions -----------------------------------------------------------
    def _choose(self) -> None:
        chosen = filedialog.askdirectory(
            title="Üç mesai dosyasının bulunduğu klasörü seçin",
            initialdir=str(self.folder) if self.folder else str(self.base))
        if chosen:
            self._set_folder(Path(chosen))
            self._remember()

    def _set_folder(self, folder: Path) -> None:
        self.folder = folder
        self.folder_var.set(str(folder))
        self.period_box.configure(values=self._period_choices())
        guessed = guess_period(folder)
        if guessed:
            self.period_var.set(guessed)
        self._describe()

    def _describe(self, extra: tuple[str, ...] = ()) -> None:
        try:
            settings = config.load(self.config_dir, self.period_var.get() or "2026-01")
        except Exception as exc:                       # noqa: BLE001
            self._write_note((f"Config okunamadı: {exc}",), ok=False)
            self.run_button.configure(state="disabled")
            return

        ok, lines = describe_folder(self.folder, settings) if self.folder \
            else (False, ("Başlamak için 'Gözat…' ile klasörü seçin.",))
        self._write_note(extra + lines, ok=ok)
        self.run_button.configure(
            state="normal" if ok and not self._running else "disabled")

    def _write_note(self, lines: tuple[str, ...], ok: bool) -> None:
        self.folder_note.configure(state="normal")
        self.folder_note.delete("1.0", "end")
        self.folder_note.insert("end", "\n".join(lines))
        self.folder_note.configure(state="disabled",
                                   foreground=_MUTED if ok else _BAD)

    def _start(self) -> None:
        # Whatever the user typed goes through the same parser as a folder name, so
        # `06-2026` and `Temmuz 2026` work in the field too. Only the canonical form
        # reaches the pipeline — `--ay` stays strict there (ADR-014).
        typed = self.period_var.get().strip()
        period = parse_period(typed)
        if period is None:
            self._render(_Result(
                False, "Dönem anlaşılamadı",
                (f"Girilen: {typed!r}" if typed else "Dönem boş.",
                 "",
                 "Şu yazımlar kabul edilir:",
                 "   2026-07   ·   07-2026   ·   202607   ·   Temmuz 2026",
                 "",
                 "Yıl dört haneli olmalı. '03-04' gibi bir yazım kabul edilmez,",
                 "çünkü hangisinin ay hangisinin yıl olduğu belli değil.",
                 ), _BAD))
            return
        if period != typed:
            self.period_var.set(period)          # show what will actually be used
        try:
            period_bounds(period)
        except (ValueError, IndexError):          # pragma: no cover - parser precedes
            self._render(_Result(False, "Dönem hatalı", (f"{period!r} okunamadı.",),
                                 _BAD))
            return

        self._running = True
        self.run_button.configure(state="disabled")
        self.open_report.configure(state="disabled")
        self.open_folder.configure(state="disabled")
        self.progress.start(12)
        self._render(_Result(True, f"{period_label(period)} hesaplanıyor…", (), _MUTED))
        threading.Thread(target=self._work, args=(period, self.folder),
                         daemon=True).start()
        self.root.after(120, self._poll)

    def _work(self, period: str, folder: Path) -> None:
        """Runs OFF the UI thread. Puts a _Result on the queue; never touches widgets."""
        try:
            settings = config.load(self.config_dir, period)
            output = (self.base / "data" / "out" / period
                      / f"mesai-raporu-{period}.xlsx")
            result = run(folder, output, period, settings, datetime.now(),
                         roster_dir=self.roster_dir,
                         snapshot_path=snapshot.default_path(period, self.base))
            self._queue.put(self._summarise(period, result))
        except ReportLocked as exc:
            self._queue.put(_Result(False, "Rapor yazılamadı", (str(exc),), _BAD))
        except (LayoutError, InputError) as exc:
            self._queue.put(_Result(False, "Dosyalar okunamadı", (str(exc),), _BAD))
        except Exception as exc:                       # noqa: BLE001
            # Last resort: an unexpected failure must reach the window, not vanish
            # into a thread nobody is watching.
            self._queue.put(_Result(
                False, "Beklenmeyen hata",
                (f"{type(exc).__name__}: {exc}",), _BAD))

    def _summarise(self, period: str, result: dict) -> _Result:
        partial = result.get("partial_sources") or []
        lines = [
            f"Raporda yer alan kişi : {result['people']}",
            f"  mesai verisi olan   : {result['with_attendance']}",
            f"  mesai verisi olmayan: {result['without_attendance']}",
            f"Kişi-gün kaydı        : {result['workdays']}",
            f"Toplam çalışma süresi : {hhmm(result['gross'])}",
            f"Şüpheli kayıt         : {result['anomalies']}"
            f" ({result['excluded_anomalies']} tanesi toplama dahil edilmedi)",
        ]
        if partial:
            for cov in partial:
                first = cov.trailing_missing[0].strftime("%d.%m.%Y")
                lines += [
                    "",
                    f"⚠ EKSİK VERİ — {cov.source} dosyası dönemin tamamını içermiyor.",
                    f"   {first} ve sonrası yok ({cov.present}/{cov.expected} iş günü).",
                    "   Bu rapordaki saatler bordro için kullanılamaz.",
                ]
            return _Result(True, f"{period_label(period)} raporu yazıldı — EKSİK",
                           tuple(lines), _WARN, result["output"],
                           result.get("snapshot"))
        return _Result(True, f"{period_label(period)} raporu yazıldı",
                       tuple(lines), _OK, result["output"], result.get("snapshot"))

    def _poll(self) -> None:
        try:
            result = self._queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll)
            return
        self.progress.stop()
        self._running = False
        self._render(result)
        self._last_output = result.output
        state = "normal" if result.output and result.output.exists() else "disabled"
        self.open_report.configure(state=state)
        self.open_folder.configure(state=state)
        self._describe()

    def _render(self, result: _Result) -> None:
        tag = {_OK: "ok", _WARN: "warn", _BAD: "bad"}.get(result.colour, "muted")
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", result.heading + "\n", ("heading", tag))
        if result.lines:
            self.result.insert("end", "\n".join(result.lines) + "\n")
        if result.snapshot:
            self.result.insert(
                "end", f"\nVeri dosyası: {result.snapshot.name}\n", "muted")
        self.result.configure(state="disabled")

    def _open_report(self) -> None:
        if self._last_output:
            _reveal(self._last_output)

    def _open_folder(self) -> None:
        if self._last_output:
            _reveal(self._last_output.parent)


def _reveal(path: Path) -> None:
    """Open a file or folder with whatever the OS uses. Never raises at the user."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))                    # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.25)               # readable on a 1080p laptop
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
