"""The window itself: the shell that holds a work face, and nothing more.

Kept separate from the screen it currently shows because a second one is coming. The
e-mail step needs its own widgets, its own state and its own idea of what "finished"
means, and folding that into the report screen's class would produce one object with
two jobs. The shell owns the toplevel, the header band and the area a screen is built
into; a screen owns everything inside it.

Only one screen exists today, so there is no navigation yet — adding a left-hand panel
is a matter of putting items beside `self.content` and swapping which screen is
gridded into it, not of restructuring anything.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from ..cli import program_dir
from . import widgets as w
from .rapor import ReportScreen

WINDOW_TITLE = "Mesai Raporu"
WINDOW_SUBTITLE = "Aylık çalışma süresi raporu"


class App:
    def __init__(self, root: tk.Tk, config_dir: Path | None = None,
                 roster_dir: Path | None = None, base: Path | None = None) -> None:
        self.root = root
        self.base = base or program_dir()
        self.config_dir = config_dir or (self.base / "config")
        self.roster_dir = roster_dir or (self.base / "data" / "personel")

        root.title(WINDOW_TITLE)
        root.minsize(720, 600)
        self._build()

    def _build(self) -> None:
        w.use_native_theme()
        self.root.configure(background=w.BG)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._header()

        # Where a screen goes. The padding lives here rather than in the screen so
        # every future work face is inset identically without having to remember to.
        self.content = tk.Frame(self.root, background=w.BG)
        self.content.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.report = ReportScreen(self.content, root=self.root, base=self.base,
                                   config_dir=self.config_dir,
                                   roster_dir=self.roster_dir)
        self.report.frame.grid(row=0, column=0, sticky="nsew")

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
