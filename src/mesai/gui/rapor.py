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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath
from tkinter import filedialog, ttk

from .. import config, snapshot
from ..pipeline import InputError, period_bounds, run
from ..readers import LayoutError, find_sources
from ..report.workbook import ReportLocked
from ..normalize import fold
from ..rules.worktime import hhmm
from . import places
from . import widgets as w
from .period import MONTHS, guess_period, parse_period, period_label

# Remembered between runs so the folder is chosen once, not every month. Plain JSON
# next to the program; it holds a path, never employee data.
SETTINGS_FILE = "arayuz-ayarlari.json"

# The three monthly exports, in the order a reader expects to see them listed. The
# labels are the site names and nothing else: "giriş-çıkış" and "puantaj" described how
# each site happens to record attendance, which is a distinction the reader of this
# window never has to make.
SOURCES = (("macunkoy", "Macunköy"),
           ("teknopark", "Teknopark"),
           ("izin", "İzin"))


@dataclass
class Result:
    """What a finished run produced, in the form the screen needs to render it.

    `figures` is kept apart from `lines` because the two want different type. The
    summary is a column of labels and numbers aligned with spaces, which only lines up
    in a fixed-width font; `lines` is prose, which reads worse in one. They used to
    share a field and the summary's colons drifted out of line.
    """
    ok: bool
    heading: str
    lines: tuple[str, ...]
    colour: str
    output: Path | None = None
    snapshot: Path | None = None
    figures: tuple[str, ...] = ()


# The result card is the largest thing on the screen and it is empty until a run
# finishes. An empty box says nothing about what to do next, so it starts by saying it:
# the same three steps, in the order the controls above it appear.
WELCOME = Result(
    True, "Hazır",
    ("1.  'Gözat…' ile üç mesai dosyasının bulunduğu klasörü seçin.",
     "2.  Dönemi doğrulayın — klasör adından okunabiliyorsa kendiliğinden dolar.",
     "3.  'Rapor Oluştur'a basın.",
     "",
     "Hesaplama birkaç saniye sürer. Bittiğinde özet ve dosya yolları burada yazar."),
    "")                              # no status colour: this is not an outcome


@dataclass(frozen=True)
class SourceState:
    """Where one of the three monthly exports stands, before anything is read."""
    key: str
    label: str
    path: Path | None       # None means this source cannot be read yet
    note: str               # the file name, or why there isn't one
    chosen: bool = False    # named by hand rather than found in the folder
    mismatch: bool = False  # named by hand, but the name does not look like this source
    other_month: str = ""   # a month named in the file name that is not the period's

    @property
    def ready(self) -> bool:
        return self.path is not None

    @property
    def suspect(self) -> bool:
        """Usable, but worth a second look before pressing anything."""
        return self.ready and (self.mismatch or bool(self.other_month))


def _looks_like(name: str, patterns: tuple[str, ...]) -> bool:
    """Does this file name match the source's own globs?

    Used only to *say something* about a hand-picked file, never to refuse one. The
    patterns are a convention, not a rule — a renamed export is still that export, and
    the reader validates the layout anyway. `PurePath.match` is used rather than a
    hand-rolled comparison so this agrees with the globbing exactly, Windows'
    case-insensitivity included.
    """
    return any(PurePath(name).match(pattern) for pattern in patterns)


def month_in_name(name: str) -> str:
    """The Turkish month named in a file name, if exactly one is, else "".

    A weak signal used for a warning and never for a decision: `Macunköy Mayıs Mesai
    giriş-çıkış.xlsx` says which month it is meant to be, and most exports are named
    this way. The authority on which month a file actually holds is the period filter,
    which reads the dates inside it and fails the run when they are all wrong
    (ADR-023). This only moves that discovery earlier, to before the button is pressed.

    Two month names in one file name means neither can be trusted, so it says nothing.
    """
    folded = fold(name)
    found = [month for month in MONTHS if fold(month) in folded]
    return found[0] if len(found) == 1 else ""


def inspect_sources(folder: Path | None, settings,
                    chosen: Mapping[str, Path] | None = None,
                    period: str | None = None) -> tuple[SourceState, ...]:
    """Where each of the three exports stands, given a folder and any hand-picked files.

    Runs before any reading, so a wrong folder is caught while the user is still
    looking at the field rather than after a failed run. Reports every source, present
    or not — "two of three found" is more useful than the first error, and it is what
    lets the window offer to find the missing one on its own.

    `period` is used only to notice that a file's *name* mentions a different month.
    It decides nothing — see `month_in_name`.
    """
    chosen = chosen or {}
    wanted = MONTHS[int(period.split("-")[1]) - 1] if period else ""
    states: list[SourceState] = []

    def other_month(path: Path) -> str:
        named = month_in_name(path.name)
        return named if wanted and named and named != wanted else ""

    for key, label in SOURCES:
        picked = chosen.get(key)
        if picked is not None:
            if picked.is_file():
                states.append(SourceState(
                    key, label, picked, picked.name, chosen=True,
                    mismatch=not _looks_like(picked.name, settings.sources[key]),
                    other_month=other_month(picked)))
            else:
                states.append(SourceState(key, label, None,
                                          "seçilen dosya artık yok", chosen=True))
            continue

        matches = find_sources(folder, settings.sources[key]) \
            if folder and folder.is_dir() else []
        if len(matches) == 1:
            states.append(SourceState(key, label, matches[0], matches[0].name,
                                      other_month=other_month(matches[0])))
        elif not matches:
            states.append(SourceState(key, label, None, "bulunamadı"))
        else:
            # Two months in one folder — the ADR-014 mistake. Naming one by hand is a
            # legitimate answer to it, which is why this offers the same button as a
            # missing file rather than only an error.
            names = ", ".join(p.name for p in matches[:3])
            states.append(SourceState(
                key, label, None, f"{len(matches)} dosya eşleşti ({names})"))
    return tuple(states)


class ReportScreen:
    """Builds itself into `parent` and owns everything the report run needs.

    It takes `root` separately because `after()` — the only way a worker thread's
    result can reach the UI thread — belongs to the toplevel, not to the frame this
    screen happens to sit in.
    """

    def __init__(self, parent: tk.Misc, *, root: tk.Misc, base: Path,
                 config_dir: Path, roster_dir: Path,
                 on_snapshot: Callable[[Path], None] | None = None) -> None:
        self.root = root
        # Called with the data file after a successful run. The shell passes the path
        # on to the people screen; this screen does not know that screen exists.
        self.on_snapshot = on_snapshot
        self.base = base
        self.config_dir = config_dir
        self.roster_dir = roster_dir
        self.folder: Path | None = None
        # Files named outright, one per source key, when the folder did not hold them.
        self.chosen: dict[str, Path] = {}
        self.states: tuple[SourceState, ...] = ()
        self._queue: queue.Queue[Result] = queue.Queue()
        self._running = False
        self._last_output: Path | None = None

        self._build(parent)
        self._render(WELCOME)
        self._restore()
        # The period note is otherwise only written by the trace, which never fires on
        # a fresh window — nothing has typed into the field yet. That left the empty
        # field with an empty caption beside it, so the one line explaining what may be
        # typed there was unreachable in exactly the state it was written for.
        self._period_changed()

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

        # One label per line rather than one multi-line label, so a folder with two of
        # the three exports can show the two that were found in the colour of a found
        # file and the missing one in the colour of a problem. A single label has one
        # colour, which meant a partial match painted the good news red too.
        self.folder_note = tk.Frame(body, background=w.BG)
        self.folder_note.grid(row=2, column=0, sticky="ew", pady=(8, 16))
        # Column 2 holds the file name and takes the slack, so the mark and the site
        # name stay in a narrow column against the left edge. Giving column 0 the
        # weight instead left the tick stranded a third of the way from the label.
        self.folder_note.columnconfigure(2, weight=1)
        self.note_lines: tuple[str, ...] = ()

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

        # --- where the report goes ---------------------------------------
        w.caption(body, "RAPOR KLASÖRÜ", row=5)

        out_row = tk.Frame(body, background=w.BG)
        out_row.grid(row=6, column=0, sticky="ew")
        out_row.columnconfigure(0, weight=1)
        self.output_var = tk.StringVar(value="")
        tk.Entry(out_row, textvariable=self.output_var, state="readonly",
                 font=(w.FACE, 9), relief="flat", readonlybackground=w.CARD,
                 foreground=w.INK, highlightthickness=1, highlightbackground=w.LINE,
                 highlightcolor=w.ACCENT).grid(row=0, column=0, sticky="ew", ipady=5)
        w.button(out_row, "Değiştir…", self._choose_output, primary=False).grid(
            row=0, column=1, sticky="e", padx=(8, 0))

        self.output_note = tk.Label(body, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), anchor="w")
        self.output_note.grid(row=7, column=0, sticky="ew", pady=(8, 18))

        self.run_button = w.button(body, "Rapor Oluştur", self._start, primary=True)
        self.run_button.grid(row=8, column=0, sticky="ew", ipady=4)
        w.set_enabled(self.run_button, False)

        self.progress = w.Progress(body)
        self.progress.grid(row=9, column=0, sticky="ew", pady=(10, 0))

        # --- result card -------------------------------------------------
        card = tk.Frame(body, background=w.LINE)      # hairline border via padding
        card.grid(row=10, column=0, sticky="nsew", pady=(12, 12))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        body.rowconfigure(10, weight=1)
        self.result = tk.Text(card, height=12, relief="flat", wrap="word",
                              font=(w.FACE, 9), padx=14, pady=12, background=w.CARD,
                              foreground=w.INK, borderwidth=0, highlightthickness=0,
                              spacing1=1, spacing3=2, cursor="arrow")
        self.result.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.result.configure(state="disabled")

        # A run that hits a partial source writes four extra lines per source, so the
        # card overflows on some months and not others. It used to simply clip, which
        # cost the reader the snapshot path — printed in full, and then unreachable.
        self._scroll = ttk.Scrollbar(card, orient="vertical",
                                     command=self.result.yview)
        self.result.configure(yscrollcommand=self._scrolled)
        self.result.bind("<MouseWheel>", self._wheel)

        self.result.tag_configure("heading", font=(w.FACE, 10, "bold"))
        self.result.tag_configure("path", font=(w.MONO, 9))
        # Aligned with spaces, so it only aligns in a fixed-width font.
        self.result.tag_configure("figure", font=(w.MONO, 9))
        for name, colour in (("ok", w.OK), ("warn", w.WARN), ("bad", w.BAD),
                             ("muted", w.MUTED)):
            self.result.tag_configure(name, foreground=colour)

        buttons = tk.Frame(body, background=w.BG)
        buttons.grid(row=11, column=0, sticky="e")
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
    #
    # The OUTPUT folder is remembered outright, and the difference is the point: it is
    # not month-specific. The month lives in the subfolder this makes (`06-2026
    # Rapor`), so last month's choice is still exactly right this month. Restoring the
    # input folder offers a stale month ready to run; restoring the output folder
    # offers the place reports go. Same mechanism, opposite consequence.

    def _settings_path(self) -> Path:
        return self.base / SETTINGS_FILE

    def _restore(self) -> None:
        """Load the browse starting point and the output folder. Selects no input."""
        self.browse_dir: Path | None = None
        self.output_dir: Path = places.desktop_dir()
        saved: dict[str, object] = {}
        try:
            saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

        candidate = saved.get("browse_dir")
        if candidate is None and saved.get("folder"):
            # Written by the version that remembered the selection itself. Its parent
            # is exactly the browse location we want, so upgrade rather than discard.
            candidate = str(Path(saved["folder"]).parent)
        if candidate and Path(str(candidate)).is_dir():
            self.browse_dir = Path(str(candidate))

        # A vanished output folder falls back to the Desktop rather than failing. It
        # is visible in the field either way, so a silent substitution is not possible.
        stored_output = saved.get("output_dir")
        if stored_output and Path(str(stored_output)).is_dir():
            self.output_dir = Path(str(stored_output))

        self._show_output()
        self._describe()

    def _save(self) -> None:
        """Write both remembered paths. Always both, so neither can drop the other."""
        payload: dict[str, str] = {"output_dir": str(self.output_dir)}
        if self.browse_dir is not None:
            payload["browse_dir"] = str(self.browse_dir)
        try:
            self._settings_path().write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass        # a read-only install is not worth failing a run over

    def _remember(self) -> None:
        if self.folder is None:
            return
        self.browse_dir = self.folder.parent
        self._save()

    # --- actions -----------------------------------------------------------
    def _choose(self) -> None:
        start = self.folder or self.browse_dir or self.base
        chosen = filedialog.askdirectory(
            title="Üç mesai dosyasının bulunduğu klasörü seçin",
            initialdir=str(start))
        if chosen:
            self._set_folder(Path(chosen))
            self._remember()

    def _choose_source(self, key: str) -> None:
        """Name one export outright, for when it is not where the others are."""
        label = dict(SOURCES)[key]
        start = self.folder or self.browse_dir or self.base
        picked = filedialog.askopenfilename(
            title=f"{label} dosyasını seçin",
            initialdir=str(start),
            filetypes=[("Excel dosyaları", "*.xlsx *.xlsm *.xls"),
                       ("Tüm dosyalar", "*.*")])
        if picked:
            self.chosen[key] = Path(picked)
            self._describe()

    def _forget_source(self, key: str) -> None:
        """Undo a hand-picked file and look in the folder again."""
        self.chosen.pop(key, None)
        self._describe()

    def _choose_output(self) -> None:
        picked = filedialog.askdirectory(
            title="Raporun yazılacağı klasörü seçin",
            initialdir=str(self.output_dir))
        if picked:
            self.output_dir = Path(picked)
            self._show_output()
            self._save()

    def _show_output(self) -> None:
        """Say where the report goes, and name the folder that will be made for it.

        The folder is the part worth showing: the run creates `06-2026 Rapor` inside
        the chosen directory rather than writing into it, and somebody who expects the
        workbook to land where they pointed would otherwise go looking in the wrong
        place.
        """
        self.output_var.set(str(self.output_dir))
        period = parse_period(self.period_var.get().strip())
        if not period:
            self.output_note.configure(
                text="Dönem girildiğinde kullanılacak klasörün adı burada yazacak.",
                foreground=w.MUTED)
            return

        folder = places.report_folder_name(period)
        if places.existing_report(self.output_dir, period) is not None:
            # Overwriting last run's report is usually the intent, and it happens
            # either way — so it is said before the button rather than discovered
            # after it.
            self.output_note.configure(
                text=f"⚠ {folder} klasöründe zaten bir rapor var — üzerine yazılacak.",
                foreground=w.WARN)
        else:
            self.output_note.configure(
                text=f"Bu koşu şu klasörü oluşturacak:  {folder}   "
                     f"(rapor ve veri dosyası birlikte)",
                foreground=w.MUTED)

    def _set_folder(self, folder: Path) -> None:
        self.folder = folder
        self.folder_var.set(str(folder))
        # Hand-picked files belonged to the folder they were picked alongside. Carrying
        # them into a different month would quietly mix two periods — the one mistake
        # the period filter exists to catch, and it should not be made in the first
        # place.
        self.chosen.clear()
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
        # Both the per-source warning ("this file's name says Haziran") and the name
        # of the folder about to be created depend on the period, so editing it has to
        # repaint them.
        self._show_output()
        if self.folder and not self._running:
            self._describe()

    def _describe(self) -> None:
        try:
            settings = config.load(self.config_dir, self.period_var.get() or "2026-01")
        except Exception as exc:                       # noqa: BLE001
            self._write_message(f"Config okunamadı: {exc}", problem=True)
            w.set_enabled(self.run_button, False)
            return

        if not self.folder:
            # A folder comes first and the per-source buttons appear underneath it, so
            # there is no state where a file has been named but no folder chosen — and
            # the pipeline still needs the folder for the sources nobody named.
            #
            # Not a problem, and it must not be painted as one. Nothing chosen yet is
            # simply where every run starts; a red line here made an untouched window
            # look like something had already gone wrong.
            self._write_message("Başlamak için 'Gözat…' ile klasörü seçin.",
                                problem=False)
            w.set_enabled(self.run_button, False)
            return

        self.states = inspect_sources(self.folder, settings, self.chosen,
                                      parse_period(self.period_var.get().strip()))
        self._write_sources(self.states)
        w.set_enabled(self.run_button,
                      all(s.ready for s in self.states) and not self._running)

    def _clear_note(self) -> None:
        for child in self.folder_note.winfo_children():
            child.destroy()

    def _write_message(self, text: str, problem: bool) -> None:
        self._clear_note()
        self.states = ()
        self.note_lines = (text,)
        tk.Label(self.folder_note, text=text, background=w.BG,
                 foreground=w.BAD if problem else w.MUTED,
                 font=(w.FACE, 9), anchor="w").grid(row=0, column=0, columnspan=3,
                                                    sticky="ew")

    def _write_sources(self, states: tuple[SourceState, ...]) -> None:
        """One row per source: a mark, the site name, the file, and a way to fix it.

        Each row carries its own colour. When two of the three are found and one is
        not, the two that were found must not be painted in the colour of the one that
        was not — they were the same label once, and one label has one colour.
        """
        self._clear_note()
        self.note_lines = tuple(f"{s.label}: {s.note}" for s in states)

        for row, state in enumerate(states):
            if not state.ready:
                mark, colour = "✗", w.BAD
            elif state.suspect:
                mark, colour = "✓", w.WARN
            else:
                mark, colour = "✓", w.OK
            tk.Label(self.folder_note, text=mark, background=w.BG, foreground=colour,
                     font=(w.FACE, 9)).grid(row=row, column=0, sticky="w")
            tk.Label(self.folder_note, text=state.label, background=w.BG,
                     foreground=w.INK, font=(w.FACE, 9), anchor="w", width=11).grid(
                row=row, column=1, sticky="w", padx=(6, 8))

            note = state.note
            if state.chosen and state.ready:
                note += "   (elle seçildi)"
            if state.mismatch:
                note += "   — adı bu kaynağa benzemiyor, yine de kullanılacak"
            if state.other_month:
                note += f"   ⚠ adında {state.other_month} geçiyor"
            tk.Label(self.folder_note, text=note, background=w.BG, foreground=colour,
                     font=(w.FACE, 9), anchor="w").grid(row=row, column=2, sticky="w")

            # A row only gets a button when it has something to offer: find the file
            # the folder did not hold, or undo a hand-picked one. A source that was
            # found where it was expected needs nothing.
            if not state.ready:
                w.button(self.folder_note, "Seç…",
                         lambda k=state.key: self._choose_source(k),
                         primary=False).grid(row=row, column=3, sticky="e",
                                             padx=(10, 0), pady=1)
            elif state.chosen:
                w.button(self.folder_note, "Geri al",
                         lambda k=state.key: self._forget_source(k),
                         primary=False).grid(row=row, column=3, sticky="e",
                                             padx=(10, 0), pady=1)

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
        self.progress.start()
        self._render(Result(True, f"{period_label(period)} hesaplanıyor…", (),
                            w.MUTED))
        threading.Thread(target=self._work,
                         args=(period, self.folder, dict(self.chosen),
                               self.output_dir),
                         daemon=True).start()
        self.root.after(120, self._poll)

    def _work(self, period: str, folder: Path | None,
              chosen: dict[str, Path], output_dir: Path) -> None:
        """Runs OFF the UI thread. Puts a Result on the queue; never touches widgets.

        `chosen` is copied by the caller rather than read off `self`: the user can go
        on clicking while this runs, and a run must report on the files it was started
        with.
        """
        try:
            settings = config.load(self.config_dir, period)
            output, snapshot_path = places.report_paths(output_dir, period)
            result = run(folder, output, period, settings, datetime.now(),
                         roster_dir=self.roster_dir,
                         snapshot_path=snapshot_path,
                         chosen=chosen)
            self._queue.put(self._summarise(period, result))
        except ReportLocked as exc:
            self._queue.put(Result(False, "Rapor yazılamadı", (str(exc),), w.BAD))
        except LayoutError as exc:
            self._queue.put(Result(False, "Dosyalar okunamadı", (str(exc),), w.BAD))
        except InputError as exc:
            # Not the same failure as an unreadable file, and it used to share its
            # heading. A wrong-month export (ADR-023) reads perfectly; what is wrong is
            # which file was handed over, and the heading has to leave room for that.
            self._queue.put(Result(False, "Rapor oluşturulmadı", (str(exc),), w.BAD))
        except Exception as exc:                       # noqa: BLE001
            # Last resort: an unexpected failure must reach the window, not vanish
            # into a thread nobody is watching.
            self._queue.put(Result(
                False, "Beklenmeyen hata",
                (f"{type(exc).__name__}: {exc}",), w.BAD))

    def _summarise(self, period: str, result: dict) -> Result:
        partial = result.get("partial_sources") or []
        figures = (
            f"Raporda yer alan kişi : {result['people']}",
            f"  mesai verisi olan   : {result['with_attendance']}",
            f"  mesai verisi olmayan: {result['without_attendance']}",
            f"Kişi-gün kaydı        : {result['workdays']}",
            f"Toplam çalışma süresi : {hhmm(result['gross'])}",
            f"Şüpheli kayıt         : {result['anomalies']}"
            f" ({result['excluded_anomalies']} tanesi toplama dahil edilmedi)",
        )
        lines: list[str] = []
        for cov in partial:
            first = cov.trailing_missing[0].strftime("%d.%m.%Y")
            lines += [
                "",
                f"⚠ EKSİK VERİ — {cov.source} dosyası dönemin tamamını içermiyor.",
                f"   {first} ve sonrası yok ({cov.present}/{cov.expected} iş günü).",
                "   Bu rapordaki saatler bordro için kullanılamaz.",
            ]
        heading = f"{period_label(period)} raporu yazıldı"
        if partial:
            return Result(True, f"{heading} — EKSİK", tuple(lines), w.WARN,
                          result["output"], result.get("snapshot"), figures)
        return Result(True, heading, (), w.OK, result["output"],
                      result.get("snapshot"), figures)

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
        if result.snapshot is not None and self.on_snapshot is not None:
            self.on_snapshot(result.snapshot)
        have_file = bool(result.output and result.output.exists())
        w.set_enabled(self.open_report, have_file)
        w.set_enabled(self.open_folder, have_file)
        self._describe()
        self._period_changed()

    def _scrolled(self, first: str, last: str) -> None:
        """Show the scrollbar only when there is something out of view."""
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scroll.grid_remove()
        else:
            self._scroll.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
        self._scroll.set(first, last)

    def _wheel(self, event: tk.Event) -> str:
        self.result.yview_scroll(-event.delta // 120, "units")
        return "break"

    def _render(self, result: Result) -> None:
        tag = {w.OK: "ok", w.WARN: "warn", w.BAD: "bad"}.get(result.colour, "muted")
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", result.heading + "\n", ("heading", tag))
        if result.figures:
            self.result.insert("end", "\n".join(result.figures) + "\n", "figure")
        if result.lines:
            self.result.insert("end", "\n".join(result.lines) + "\n")
        # Full paths, not just file names. "Veri dosyası oluşturuldu" with no path is
        # not actionable — the reader has to go hunting for it.
        if result.output:
            self.result.insert("end", "\nRAPOR DOSYASI\n", ("heading", "ok"))
            self.result.insert("end", f"{result.output.resolve()}\n", "path")
        if result.snapshot:
            self.result.insert("end", "\nVERİ DOSYASI", "heading")
            self.result.insert("end", "  (e-posta adımı bunu okuyacak)\n",
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
