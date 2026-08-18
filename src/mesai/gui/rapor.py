"""The report work face: pick a folder, name the month, produce the workbook.

This is one screen of the window, not the window itself. It owns every widget between
the header band and the bottom of the frame, plus the worker thread that runs the
pipeline — and **no business logic at all.** Every figure it shows was computed by
`pipeline.run()`; every rule it mentions came from `Settings`.

Three deliberate choices, all older than this file:

* **tkinter**, from the standard library. No new dependency, packages cleanly into a
  single executable, and keeps ADR-005 intact — no network, nothing to configure.
* **No default input folder, and none is restored.** A guess that is wrong is worse
  than an empty field, because the user cannot tell it happened. They pick the folder
  holding the three exports and the screen immediately reports what it found there.
  Only the *browse starting location* is remembered — the input folder is
  month-specific, so restoring last month's selection would offer a stale month
  pre-filled and ready to run.
* **The work runs on a worker thread.** The pipeline takes a few seconds; on the UI
  thread the window would grey out and Windows would label it "not responding".
"""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from .. import config, snapshot
from ..pipeline import InputError, period_bounds, run
from ..readers import LayoutError, find_sources
from ..report.workbook import ReportLocked
from ..rules.worktime import hhmm
from . import widgets as w
from .period import guess_period, parse_period, period_label

# Remembered between runs so the folder is chosen once, not every month. Plain JSON
# next to the program; it holds a path, never employee data.
SETTINGS_FILE = "arayuz-ayarlari.json"

# The three monthly exports, in the order a reader expects to see them listed.
SOURCES = (("macunkoy", "Macunköy giriş-çıkış"),
           ("teknopark", "Teknopark puantaj"),
           ("izin", "İzin (HCM)"))


@dataclass
class Result:
    """What a finished run produced, in the form the screen needs to render it."""
    ok: bool
    heading: str
    lines: tuple[str, ...]
    colour: str
    output: Path | None = None
    snapshot: Path | None = None


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
    for key, label in SOURCES:
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


class ReportScreen:
    """Builds itself into `parent` and owns everything the report run needs.

    It takes `root` separately because `after()` — the only way a worker thread's
    result can reach the UI thread — belongs to the toplevel, not to the frame this
    screen happens to sit in.
    """

    def __init__(self, parent: tk.Misc, *, root: tk.Misc, base: Path,
                 config_dir: Path, roster_dir: Path) -> None:
        self.root = root
        self.base = base
        self.config_dir = config_dir
        self.roster_dir = roster_dir
        self.folder: Path | None = None
        self._queue: queue.Queue[Result] = queue.Queue()
        self._running = False
        self._last_output: Path | None = None

        self._build(parent)
        self._restore()

    # --- layout ------------------------------------------------------------
    def _build(self, parent: tk.Misc) -> None:
        body = self.frame = tk.Frame(parent, background=w.BG)
        body.columnconfigure(0, weight=1)

        # --- source folder -----------------------------------------------
        w.caption(body, "KAYNAK KLASÖR", row=0)

        picker = tk.Frame(body, background=w.BG)
        picker.grid(row=1, column=0, sticky="ew")
        picker.columnconfigure(0, weight=1)
        self.folder_var = tk.StringVar(value="")
        tk.Entry(picker, textvariable=self.folder_var, state="readonly",
                 font=(w.FACE, 9), relief="flat", readonlybackground=w.CARD,
                 foreground=w.INK, highlightthickness=1, highlightbackground=w.LINE,
                 highlightcolor=w.ACCENT).grid(row=0, column=0, sticky="ew", ipady=5)
        w.button(picker, "Gözat…", self._choose, primary=False).grid(
            row=0, column=1, sticky="e", padx=(8, 0))

        self.folder_note = tk.Label(body, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), justify="left", anchor="w")
        self.folder_note.grid(row=2, column=0, sticky="ew", pady=(8, 16))

        # --- period ------------------------------------------------------
        w.caption(body, "DÖNEM", row=3)

        period_row = tk.Frame(body, background=w.BG)
        period_row.grid(row=4, column=0, sticky="ew", pady=(0, 18))
        self.period_var = tk.StringVar(value="")
        self.period_box = tk.Entry(period_row, textvariable=self.period_var, width=12,
                                   font=(w.FACE, 10), relief="flat",
                                   background=w.CARD, foreground=w.INK,
                                   highlightthickness=1, highlightbackground=w.LINE,
                                   highlightcolor=w.ACCENT)
        self.period_box.grid(row=0, column=0, sticky="w", ipady=5, ipadx=4)
        self.period_note = tk.Label(period_row, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), anchor="w")
        self.period_note.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.period_var.trace_add("write", lambda *_: self._period_changed())

        self.run_button = w.button(body, "Rapor Oluştur", self._start, primary=True)
        self.run_button.grid(row=5, column=0, sticky="ew", ipady=4)
        w.set_enabled(self.run_button, False)

        self.progress = ttk.Progressbar(body, mode="indeterminate",
                                        style="Thin.Horizontal.TProgressbar")
        self.progress.grid(row=6, column=0, sticky="ew", pady=(10, 0))

        # --- result card -------------------------------------------------
        card = tk.Frame(body, background=w.LINE)      # hairline border via padding
        card.grid(row=7, column=0, sticky="nsew", pady=(12, 12))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        body.rowconfigure(7, weight=1)
        self.result = tk.Text(card, height=12, relief="flat", wrap="word",
                              font=(w.FACE, 9), padx=14, pady=12, background=w.CARD,
                              foreground=w.INK, borderwidth=0, highlightthickness=0,
                              spacing1=1, spacing3=2, cursor="arrow")
        self.result.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.result.configure(state="disabled")
        self.result.tag_configure("heading", font=(w.FACE, 10, "bold"))
        self.result.tag_configure("path", font=(w.MONO, 9))
        for name, colour in (("ok", w.OK), ("warn", w.WARN), ("bad", w.BAD),
                             ("muted", w.MUTED)):
            self.result.tag_configure(name, foreground=colour)

        buttons = tk.Frame(body, background=w.BG)
        buttons.grid(row=8, column=0, sticky="e")
        self.open_report = w.button(buttons, "Raporu Aç", self._open_report,
                                    primary=False)
        self.open_report.grid(row=0, column=0, padx=(0, 8))
        w.set_enabled(self.open_report, False)
        self.open_folder = w.button(buttons, "Klasörü Aç", self._open_folder,
                                    primary=False)
        self.open_folder.grid(row=0, column=1)
        w.set_enabled(self.open_folder, False)

    # There used to be a dropdown here listing every month found NEXT TO the chosen
    # folder. It was removed: it appeared with no explanation of where the entries came
    # from, and it invited the one mistake worth preventing — picking `07 - 2026` as the
    # folder and then `2026-05` from the list, i.e. running one month's period against
    # another month's files. The period now comes from the folder, and typing something
    # that disagrees with the folder produces a visible warning rather than a silent
    # mismatch.

    # --- persistence -------------------------------------------------------
    #
    # Only the folder to START BROWSING FROM is remembered — never a pre-selected
    # folder. An earlier version restored the last chosen folder, which was wrong for
    # a specific reason: the input folder is month-specific (`07 - 2026`), so from the
    # second month onwards the restored value always points at a month already done,
    # and it filled the period field with that month too. Opening the window in August
    # and being shown July, ready to run, is precisely the plausible-looking wrong
    # default this project avoids everywhere else.
    #
    # Remembering the PARENT keeps the convenience — the browse dialog opens on the
    # right share instead of Documents — while the selection itself stays deliberate.

    def _settings_path(self) -> Path:
        return self.base / SETTINGS_FILE

    def _restore(self) -> None:
        """Load the browse starting point. Never selects anything."""
        self.browse_dir: Path | None = None
        try:
            saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._describe()
            return

        candidate = saved.get("browse_dir")
        if candidate is None and saved.get("folder"):
            # Written by the version that remembered the selection itself. Its parent
            # is exactly the browse location we want, so upgrade rather than discard.
            candidate = str(Path(saved["folder"]).parent)
        if candidate and Path(candidate).is_dir():
            self.browse_dir = Path(candidate)
        self._describe()

    def _remember(self) -> None:
        if self.folder is None:
            return
        self.browse_dir = self.folder.parent
        try:
            self._settings_path().write_text(
                json.dumps({"browse_dir": str(self.browse_dir)}, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass        # a read-only install is not worth failing a run over

    # --- actions -----------------------------------------------------------
    def _choose(self) -> None:
        start = self.folder or self.browse_dir or self.base
        chosen = filedialog.askdirectory(
            title="Üç mesai dosyasının bulunduğu klasörü seçin",
            initialdir=str(start))
        if chosen:
            self._set_folder(Path(chosen))
            self._remember()

    def _set_folder(self, folder: Path) -> None:
        self.folder = folder
        self.folder_var.set(str(folder))
        guessed = guess_period(folder)
        if guessed:
            self.period_var.set(guessed)
        self._describe()
        self._period_changed()

    def _period_changed(self) -> None:
        """Say what the period field will actually be used as, and flag a mismatch.

        Typing a month that disagrees with the chosen folder is the one mistake worth
        catching here. The run would read one month's files under another month's
        period, the period filter would drop everything, and the failure would surface
        seconds later looking like a file problem instead of a typo.
        """
        typed = self.period_var.get().strip()
        parsed = parse_period(typed)
        folder_period = guess_period(self.folder) if self.folder else None

        if not typed:
            text, colour = "Örn. 2026-07 · 07-2026 · Temmuz 2026", w.MUTED
        elif parsed is None:
            text, colour = "anlaşılamadı — yıl dört haneli olmalı", w.BAD
        elif folder_period and parsed != folder_period:
            text, colour = f"⚠ klasör {folder_period} dönemine ait görünüyor", w.WARN
        elif parsed != typed:
            text, colour = f"= {parsed} · {period_label(parsed)}", w.MUTED
        else:
            text, colour = period_label(parsed), w.MUTED
        self.period_note.configure(text=text, foreground=colour)

    def _describe(self, extra: tuple[str, ...] = ()) -> None:
        try:
            settings = config.load(self.config_dir, self.period_var.get() or "2026-01")
        except Exception as exc:                       # noqa: BLE001
            self._write_note((f"Config okunamadı: {exc}",), ok=False)
            w.set_enabled(self.run_button, False)
            return

        ok, lines = describe_folder(self.folder, settings) if self.folder \
            else (False, ("Başlamak için 'Gözat…' ile klasörü seçin.",))
        self._write_note(extra + lines, ok=ok)
        w.set_enabled(self.run_button, ok and not self._running)

    def _write_note(self, lines: tuple[str, ...], ok: bool) -> None:
        self.folder_note.configure(text="\n".join(lines),
                                   foreground=w.MUTED if ok else w.BAD)

    def _start(self) -> None:
        # Whatever the user typed goes through the same parser as a folder name, so
        # `06-2026` and `Temmuz 2026` work in the field too. Only the canonical form
        # reaches the pipeline — `--ay` stays strict there (ADR-014).
        typed = self.period_var.get().strip()
        period = parse_period(typed)
        if period is None:
            self._render(Result(
                False, "Dönem anlaşılamadı",
                (f"Girilen: {typed!r}" if typed else "Dönem boş.",
                 "",
                 "Şu yazımlar kabul edilir:",
                 "   2026-07   ·   07-2026   ·   202607   ·   Temmuz 2026",
                 "",
                 "Yıl dört haneli olmalı. '03-04' gibi bir yazım kabul edilmez,",
                 "çünkü hangisinin ay hangisinin yıl olduğu belli değil.",
                 ), w.BAD))
            return
        if period != typed:
            self.period_var.set(period)          # show what will actually be used
        try:
            period_bounds(period)
        except (ValueError, IndexError):          # pragma: no cover - parser precedes
            self._render(Result(False, "Dönem hatalı", (f"{period!r} okunamadı.",),
                                w.BAD))
            return

        self._running = True
        w.set_enabled(self.run_button, False)
        w.set_enabled(self.open_report, False)
        w.set_enabled(self.open_folder, False)
        self.progress.start(12)
        self._render(Result(True, f"{period_label(period)} hesaplanıyor…", (),
                            w.MUTED))
        threading.Thread(target=self._work, args=(period, self.folder),
                         daemon=True).start()
        self.root.after(120, self._poll)

    def _work(self, period: str, folder: Path) -> None:
        """Runs OFF the UI thread. Puts a Result on the queue; never touches widgets."""
        try:
            settings = config.load(self.config_dir, period)
            output = (self.base / "data" / "out" / period
                      / f"mesai-raporu-{period}.xlsx")
            result = run(folder, output, period, settings, datetime.now(),
                         roster_dir=self.roster_dir,
                         snapshot_path=snapshot.default_path(period, self.base))
            self._queue.put(self._summarise(period, result))
        except ReportLocked as exc:
            self._queue.put(Result(False, "Rapor yazılamadı", (str(exc),), w.BAD))
        except (LayoutError, InputError) as exc:
            self._queue.put(Result(False, "Dosyalar okunamadı", (str(exc),), w.BAD))
        except Exception as exc:                       # noqa: BLE001
            # Last resort: an unexpected failure must reach the window, not vanish
            # into a thread nobody is watching.
            self._queue.put(Result(
                False, "Beklenmeyen hata",
                (f"{type(exc).__name__}: {exc}",), w.BAD))

    def _summarise(self, period: str, result: dict) -> Result:
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
            return Result(True, f"{period_label(period)} raporu yazıldı — EKSİK",
                          tuple(lines), w.WARN, result["output"],
                          result.get("snapshot"))
        return Result(True, f"{period_label(period)} raporu yazıldı",
                      tuple(lines), w.OK, result["output"], result.get("snapshot"))

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
        have_file = bool(result.output and result.output.exists())
        w.set_enabled(self.open_report, have_file)
        w.set_enabled(self.open_folder, have_file)
        self._describe()
        self._period_changed()

    def _render(self, result: Result) -> None:
        tag = {w.OK: "ok", w.WARN: "warn", w.BAD: "bad"}.get(result.colour, "muted")
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", result.heading + "\n", ("heading", tag))
        if result.lines:
            self.result.insert("end", "\n".join(result.lines) + "\n")
        # Full paths, not just file names. "Veri dosyası oluşturuldu" with no path is
        # not actionable — the reader has to go hunting for it.
        if result.output:
            self.result.insert("end", "\nRAPOR DOSYASI\n", ("heading", "ok"))
            self.result.insert("end", f"{result.output.resolve()}\n", "path")
        if result.snapshot:
            self.result.insert("end", "\nVERİ DOSYASI", "heading")
            self.result.insert(
                "end", "  (e-posta adımı bunu okuyacak; İK'nın açması gerekmez)\n",
                "muted")
            self.result.insert("end", f"{result.snapshot.resolve()}\n",
                               ("path", "muted"))
        self.result.configure(state="disabled")

    def _open_report(self) -> None:
        if self._last_output:
            w.reveal(self._last_output)

    def _open_folder(self) -> None:
        if self._last_output:
            w.reveal(self._last_output.parent)
