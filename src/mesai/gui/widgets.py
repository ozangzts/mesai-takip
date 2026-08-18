"""Palette and the widget primitives every screen in the window shares.

Split out of the single `gui.py` when a second work face (e-mail) became a near-term
certainty: a button that looks like the report screen's button must *be* the report
screen's button, not a second copy that drifts. Nothing here knows what the program
computes — it is appearance and affordance only.

Coloured controls are `tk` rather than `ttk` on purpose: the vista theme ignores
background/foreground on ttk widgets, which is why a ttk.Button cannot be given an
accent colour at all.

The first version of this window was fairly called "Windows XP". The theme was already
`vista` and the font already Segoe UI; what dated it was everything sharing one flat
grey, sunken `relief="solid"` borders, and a scaling override that rendered text
SMALLER than the system setting. Hence: a light body with white cards, hairline
borders, one accent-coloured primary action, and no scaling override.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# Palette. Deliberately restrained: a light body, white cards, one accent colour for
# the single primary action, and status colours chosen to stay readable on white.
FACE = "Segoe UI"
MONO = "Consolas"
BG = "#f4f5f7"            # window body
CARD = "#ffffff"          # input fields, result card, header band
LINE = "#dfe3e8"          # hairline borders
INK = "#1f2328"           # body text
MUTED = "#656d76"         # captions, secondary text
HOVER = "#f0f2f4"         # secondary button hover
ACCENT = "#0b5cad"
ACCENT_HOVER = "#094e93"
DISABLED_BG = "#e8eaed"

OK = "#1a7f37"
WARN = "#9a6700"
BAD = "#cf222e"


def use_native_theme() -> None:
    """Adopt the platform ttk theme and thin down the one ttk widget in use."""
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("Thin.Horizontal.TProgressbar", thickness=3,
                    background=ACCENT, troughcolor=BG, borderwidth=0)


def caption(parent: tk.Misc, text: str, row: int, *, background: str = BG) -> None:
    """Small upper-case section label - the only type hierarchy this needs."""
    tk.Label(parent, text=text, background=background, foreground=MUTED,
             font=(FACE, 8, "bold"), anchor="w").grid(
        row=row, column=0, sticky="w", pady=(0, 6))


def button(parent: tk.Misc, text: str, command, *, primary: bool) -> tk.Button:
    """Flat button with a hover state, since ttk cannot be recoloured here."""
    bg, fg = (ACCENT, "#ffffff") if primary else (CARD, INK)
    hover = ACCENT_HOVER if primary else HOVER
    widget = tk.Button(
        parent, text=text, command=command, relief="flat", cursor="hand2",
        font=(FACE, 10 if primary else 9, "bold" if primary else "normal"),
        background=bg, foreground=fg, activebackground=hover,
        activeforeground=fg, borderwidth=0, padx=16, pady=6,
        highlightthickness=0 if primary else 1,
        highlightbackground=LINE, disabledforeground=MUTED)
    widget._idle_bg = bg                         # type: ignore[attr-defined]
    widget._hover_bg = hover                     # type: ignore[attr-defined]

    def enter(_event: object) -> None:
        if str(widget.cget("state")) != "disabled":
            widget.configure(background=hover)

    def leave(_event: object) -> None:
        if str(widget.cget("state")) != "disabled":
            widget.configure(background=bg)

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)
    return widget


def set_enabled(widget: tk.Button, enabled: bool) -> None:
    """Enable/disable and repaint. A flat button gives no affordance otherwise."""
    widget.configure(
        state="normal" if enabled else "disabled",
        cursor="hand2" if enabled else "arrow",
        background=widget._idle_bg if enabled else DISABLED_BG,  # type: ignore[attr-defined]
    )


def reveal(path: Path) -> None:
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


def dpi_aware() -> None:
    """Tell Windows this process scales itself, so text is crisp on a HiDPI screen.

    Without it Windows bitmap-stretches the whole window and everything looks soft —
    a large part of what read as "dated". Silently ignored anywhere else.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware
    except (ImportError, AttributeError, OSError):
        pass
