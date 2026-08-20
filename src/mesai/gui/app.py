"""The window itself: a header, a rail of work faces, and whichever one is showing.

Kept separate from the screens it shows because a second one is coming. The e-mail
step needs its own widgets, its own state and its own idea of what "finished" means,
and folding that into the report screen's class would produce one object with two
jobs. The shell owns the toplevel, the header band, the navigation rail and the area
a screen is built into; a screen owns everything inside it.

**Adding a work face is one entry in `SCREENS`.** The rail is generated from it, the
frame is created the first time the item is clicked, and nothing else here changes.
Screens never learn about each other — only the shell knows there is more than one.

Only the report screen is registered today. An item for a screen that does not exist
yet is not registered either: `ARCHITECTURE.md` §3b keeps placeholders out of the
window, because an entry HR cannot press is a promise, and the modularity that matters
lives in the module boundaries rather than in something visible to ignore.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..cli import program_dir
from . import widgets as w
from .nav import NavPanel
from .people import PeopleScreen
from .rapor import ReportScreen
from .takvim import CalendarScreen

WINDOW_TITLE = "Mesai Raporu"
WINDOW_SUBTITLE = "Aylık çalışma süresi raporu"

NAV_WIDTH = 168

# The smallest window the report screen is usable in. Also the floor `_fit` never
# goes below, so a screen can never be shown in a window too short to hold it.
MIN_WIDTH, MIN_HEIGHT = 880, 620


@dataclass(frozen=True)
class Screen:
    """A work face the rail can switch to.

    `build` is called with the frame to build into and the shell, and must return an
    object exposing a `.frame`. It is called at most once — the first time the item is
    selected — so a screen that has setup work to do does not pay for it until it is
    actually opened.
    """
    key: str
    label: str
    build: Callable[[tk.Misc, "App"], object]


def _report(parent: tk.Misc, app: "App") -> ReportScreen:
    return ReportScreen(parent, root=app.root, base=app.base,
                        config_dir=app.config_dir, roster_dir=app.roster_dir,
                        on_snapshot=app.snapshot_ready,
                        on_finished=app.run_finished)


def _people(parent: tk.Misc, app: "App") -> PeopleScreen:
    screen = PeopleScreen(parent, root=app.root, base=app.base)
    # Built on first opening, which is usually after a run has already finished — so
    # it picks up that run's data file rather than making the user find it.
    if app.last_snapshot is not None:
        screen.load(app.last_snapshot)
    return screen


def _calendar(parent: tk.Misc, app: "App") -> CalendarScreen:
    return CalendarScreen(parent, root=app.root, config_dir=app.config_dir,
                          period=app.last_period,
                          candidates=app.last_candidates)


SCREENS: tuple[Screen, ...] = (
    Screen("rapor", "Rapor", _report),
    Screen("kisiler", "Kişiler", _people),
    Screen("takvim", "Takvim", _calendar),
)


class App:
    def __init__(self, root: tk.Tk, config_dir: Path | None = None,
                 roster_dir: Path | None = None, base: Path | None = None,
                 screens: Sequence[Screen] = SCREENS) -> None:
        self.root = root
        self.base = base or program_dir()
        self.config_dir = config_dir or (self.base / "config")
        self.roster_dir = roster_dir or (self.base / "data" / "personel")
        # Held, not read from the module on every call: a window navigates the set of
        # screens it was built with, so what the rail shows and what `show()` accepts
        # can never drift apart.
        self.screens = tuple(screens)
        self._screens: dict[str, object] = {}
        self._showing: str | None = None
        # The last data file a run produced. The people screen reads it; the report
        # screen writes it. Neither knows the other exists — the shell is the only
        # thing that knows there is more than one screen.
        self.last_snapshot: Path | None = None
        # The last run's period and the days it found almost empty. Held in memory
        # rather than put in the data file: they are a question about the calendar, not
        # part of what the report says, and the calendar screen is the only reader.
        self.last_period: str | None = None
        self.last_candidates: tuple = ()

        root.title(WINDOW_TITLE)
        root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self._build()
        self.show(self.screens[0].key)

    # --- the screen on display ---------------------------------------------
    def show(self, key: str) -> None:
        """Bring `key` to the front, building it if this is its first showing."""
        if key == self._showing:
            return
        screen = self._screens.get(key)
        if screen is None:
            screen = self._screens[key] = self._definition(key).build(self.content,
                                                                     self)
        if self._showing is not None:
            # grid_remove, not grid_forget: the hidden screen keeps its position and
            # its state, so switching away and back does not reset what was typed.
            self._screens[self._showing].frame.grid_remove()   # type: ignore[attr-defined]
        screen.frame.grid(row=0, column=0, sticky="nsew")      # type: ignore[attr-defined]
        self._showing = key
        self.nav.select(key)
        self._fit()

    def _fit(self) -> None:
        """Size the window to the screen being shown — growing only, never shrinking.

        Tk shrink-wraps a toplevel to its requested size for as long as no explicit
        geometry has been set, and the two screens do not request the same height: the
        report screen asks for 791 px, the people screen 597. Switching to `Kişiler`
        therefore snapped the window down to the 620 px floor, and switching back threw
        it up again — measured on this machine, and reported as the window being
        cropped from the bottom.

        Setting a geometry once ends the shrink-wrap. Taking the maximum of what the
        screen needs and what the window already is means a taller screen can still
        grow the window, but no screen can take space away from another — and a window
        the user has enlarged, or maximized, is left alone because the maximum is
        already what it is.
        """
        if self.root.state() == "zoomed":
            return                      # maximized — the size is the user's, not ours
        self.root.update_idletasks()
        width = max(self.root.winfo_reqwidth(), self.root.winfo_width(), MIN_WIDTH)
        height = max(self.root.winfo_reqheight(), self.root.winfo_height(),
                     MIN_HEIGHT)
        # Set every time, not only when the number changes. A geometry set before the
        # window has been mapped does not end the shrink-wrap — measured: pinning the
        # size while the window was still unmapped left it shrinking on the first
        # switch exactly as before. Re-asserting the same size on each switch is what
        # makes the pin stick, and costs nothing when it is already that size.
        self.root.geometry(f"{width}x{height}")

    def _definition(self, key: str) -> Screen:
        for screen in self.screens:
            if screen.key == key:
                return screen
        raise KeyError(f"no screen registered under {key!r}")

    @property
    def report(self) -> ReportScreen:
        """The report screen. Built at startup, so this never triggers a build."""
        return self._screens["rapor"]                          # type: ignore[return-value]

    def snapshot_ready(self, path: Path) -> None:
        """A run finished and wrote `path`. Hand it to the people screen if it exists.

        Not built on demand here: constructing a screen nobody has opened, to show it
        data nobody asked for, is work done on spec. It is loaded either now or when
        the screen is first opened, and the two paths agree.
        """
        self.last_snapshot = path
        screen = self._screens.get("kisiler")
        if screen is not None:
            screen.load(path)                                  # type: ignore[attr-defined]

    def run_finished(self, period: str, candidates: tuple) -> None:
        """A run finished. Hand the calendar screen what it needs to ask about."""
        self.last_period = period
        self.last_candidates = candidates
        screen = self._screens.get("takvim")
        if screen is not None:
            screen.load(period, candidates)                    # type: ignore[attr-defined]

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        w.use_native_theme()
        self.root.configure(background=w.BG)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._header()

        main = tk.Frame(self.root, background=w.BG)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self.nav = NavPanel(main, [(s.key, s.label) for s in self.screens],
                            self.show)
        self.nav.frame.grid(row=0, column=0, sticky="ns")
        self.nav.frame.configure(width=NAV_WIDTH)
        self.nav.frame.grid_propagate(False)

        # Where a screen goes. The padding lives here rather than in the screen so
        # every future work face is inset identically without having to remember to.
        self.content = tk.Frame(main, background=w.BG)
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=16)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

    def _header(self) -> None:
        header = tk.Frame(self.root, background=w.CARD)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text=WINDOW_TITLE, background=w.CARD, foreground=w.INK,
                 font=(w.FACE, 15, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 0))
        tk.Label(header, text=WINDOW_SUBTITLE, background=w.CARD,
                 foreground=w.MUTED, font=(w.FACE, 9), anchor="w").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 14))
        tk.Frame(header, background=w.LINE, height=1).grid(
            row=2, column=0, sticky="ew")


def main(argv: list[str] | None = None) -> int:
    w.dpi_aware()
    root = tk.Tk()
    # No scaling override here. An earlier version forced 1.25 while Windows had
    # already reported 1.333, which made every label smaller than the user asked for.
    App(root)
    root.mainloop()
    return 0
