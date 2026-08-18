"""The left-hand rail: one item per work face, and which one is showing.

It knows nothing about what a screen does. It is handed labels and hands back the key
of whatever was clicked, which is what keeps adding a work face to a one-line change
in `app.py` rather than an edit here.

A rail rather than tabs. Tabs across the top compete with the header band for the same
line of sight and get cramped past three; a rail has room for a label that says what
the screen is for, and the growth this window expects is downwards — mail, then
choosing people — not sideways.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence

from . import widgets as w

_BAR = 3            # width of the accent bar marking the selected item


class NavPanel:
    """`items` is a sequence of `(key, label)`; `on_select` is given the key."""

    def __init__(self, parent: tk.Misc, items: Sequence[tuple[str, str]],
                 on_select: Callable[[str], None]) -> None:
        self.frame = tk.Frame(parent, background=w.CARD)
        self.frame.columnconfigure(0, weight=1)
        self._on_select = on_select
        self._rows: dict[str, tuple[tk.Frame, tk.Frame, tk.Label]] = {}
        self._selected: str | None = None

        for row, (key, label) in enumerate(items):
            self._rows[key] = self._item(row, key, label)

        # The rail is a fixed column; the filler below it keeps its background running
        # to the bottom of the window instead of stopping under the last item.
        self.frame.rowconfigure(len(items), weight=1)
        tk.Frame(self.frame, background=w.CARD).grid(row=len(items), column=0,
                                                     sticky="nsew")
        tk.Frame(self.frame, background=w.LINE, width=1).grid(
            row=0, column=1, rowspan=len(items) + 1, sticky="ns")

    def _item(self, row: int, key: str,
              label: str) -> tuple[tk.Frame, tk.Frame, tk.Label]:
        holder = tk.Frame(self.frame, background=w.CARD)
        holder.grid(row=row, column=0, sticky="ew")
        holder.columnconfigure(1, weight=1)

        bar = tk.Frame(holder, background=w.CARD, width=_BAR)
        bar.grid(row=0, column=0, sticky="ns")
        bar.grid_propagate(False)

        text = tk.Label(holder, text=label, background=w.CARD, foreground=w.INK,
                        font=(w.FACE, 10), anchor="w", padx=13, pady=10)
        text.grid(row=0, column=1, sticky="ew")

        for widget in (holder, bar, text):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _e, k=key: self._on_select(k))
            widget.bind("<Enter>", lambda _e, k=key: self._hover(k, True))
            widget.bind("<Leave>", lambda _e, k=key: self._hover(k, False))
        return holder, bar, text

    def _hover(self, key: str, entering: bool) -> None:
        if key == self._selected:
            return                       # the selected item already has its own fill
        holder, _bar, text = self._rows[key]
        fill = w.HOVER if entering else w.CARD
        holder.configure(background=fill)
        text.configure(background=fill)

    def select(self, key: str) -> None:
        """Paint `key` as the current screen. Called by the shell, not by a click."""
        self._selected = key
        for other, (holder, bar, text) in self._rows.items():
            chosen = other == key
            fill = w.ACCENT_SOFT if chosen else w.CARD
            holder.configure(background=fill)
            bar.configure(background=w.ACCENT if chosen else fill)
            text.configure(background=fill,
                           foreground=w.ACCENT if chosen else w.INK,
                           font=(w.FACE, 10, "bold" if chosen else "normal"))
