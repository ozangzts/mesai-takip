"""The people work face: load a month's data file, filter it, pick who is in the list.

It decides nothing. Which people a filter admits is `mail/recipients.py`; this module
turns that answer into rows and turns clicks back into a filter key and a set of
removed names. Keeping the rule outside the widget is what makes "everyone missing an
exit punch, except these two" testable without a display.

It reads the **data file**, never the workbook — `snapshot.py` says why at length. The
report screen hands over the path as soon as a run finishes, so the usual path through
this screen involves choosing nothing.

Removal is by **name**, not by row number: the list re-sorts when the filter changes,
and a remembered index would quietly come to mean somebody else.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .. import snapshot as snapshot_module
from ..mail import recipients
from ..mail.recipients import other_problems
from . import widgets as w
from .period import period_label

_ROW_HEIGHT = 22


class PeopleScreen:
    def __init__(self, parent: tk.Misc, *, root: tk.Misc, base: Path) -> None:
        self.root = root
        self.base = base
        self.snapshot: snapshot_module.Snapshot | None = None
        self.source: Path | None = None
        self.filter_key = recipients.ALL
        self.excluded: set[str] = set()
        self._choices: tuple[recipients.Choice, ...] = ()
        self._rows: list[tuple[str, tk.BooleanVar]] = []

        self._build(parent)
        self._repaint()

    # --- layout ------------------------------------------------------------
    def _build(self, parent: tk.Misc) -> None:
        body = self.frame = tk.Frame(parent, background=w.BG)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)

        w.caption(body, "VERİ DOSYASI", row=0)
        source_row = tk.Frame(body, background=w.BG)
        source_row.grid(row=1, column=0, sticky="ew")
        source_row.columnconfigure(0, weight=1)
        self.source_var = tk.StringVar(value="")
        tk.Entry(source_row, textvariable=self.source_var, state="readonly",
                 font=(w.FACE, 9), relief="flat", readonlybackground=w.CARD,
                 foreground=w.INK, highlightthickness=1, highlightbackground=w.LINE,
                 highlightcolor=w.ACCENT).grid(row=0, column=0, sticky="ew", ipady=5)
        w.button(source_row, "Aç…", self._choose_file, primary=False).grid(
            row=0, column=1, sticky="e", padx=(8, 0))

        self.source_note = tk.Label(body, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), anchor="w", justify="left")
        self.source_note.grid(row=2, column=0, sticky="ew", pady=(8, 16))

        # --- filter ------------------------------------------------------
        w.caption(body, "FİLTRE", row=3)
        filter_row = tk.Frame(body, background=w.BG)
        filter_row.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        filter_row.columnconfigure(1, weight=1)
        self.filter_var = tk.StringVar(value="")
        self.filter_box = ttk.Combobox(filter_row, textvariable=self.filter_var,
                                       state="readonly", width=42,
                                       font=(w.FACE, 10))
        self.filter_box.grid(row=0, column=0, sticky="w", ipady=3)
        self.filter_box.bind("<<ComboboxSelected>>", self._filter_changed)

        self.filter_note = tk.Label(filter_row, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), anchor="w", justify="left")
        self.filter_note.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # --- the list ----------------------------------------------------
        card = tk.Frame(body, background=w.LINE)
        card.grid(row=5, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(card, background=w.CARD, highlightthickness=0,
                                borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._scroll = ttk.Scrollbar(card, orient="vertical",
                                     command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._scrolled)
        self.canvas.bind("<MouseWheel>", self._wheel)

        self.list_frame = tk.Frame(self.canvas, background=w.CARD)
        self._window = self.canvas.create_window((0, 0), window=self.list_frame,
                                                 anchor="nw")
        self.list_frame.bind("<Configure>", self._resized)
        self.canvas.bind("<Configure>", self._canvas_resized)

        # --- actions ------------------------------------------------------
        actions = tk.Frame(body, background=w.BG)
        actions.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(1, weight=1)
        left = tk.Frame(actions, background=w.BG)
        left.grid(row=0, column=0, sticky="w")
        w.button(left, "Tümünü seç", self._select_all, primary=False).grid(
            row=0, column=0, padx=(0, 8))
        w.button(left, "Temizle", self._clear_all, primary=False).grid(row=0, column=1)

        self.count_label = tk.Label(actions, background=w.BG, foreground=w.INK,
                                    font=(w.FACE, 10, "bold"), anchor="e")
        self.count_label.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.copy_button = w.button(actions, "Listeyi kopyala", self._copy,
                                    primary=False)
        self.copy_button.grid(row=0, column=2, sticky="e")

    # --- scrolling ---------------------------------------------------------
    def _scrolled(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scroll.grid_remove()
        else:
            self._scroll.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
        self._scroll.set(first, last)

    def _wheel(self, event: tk.Event) -> str:
        self.canvas.yview_scroll(-event.delta // 120, "units")
        return "break"

    def _resized(self, _event: object) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_resized(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    # --- loading -----------------------------------------------------------
    def load(self, path: Path) -> None:
        """Show the month in `path`. Called by the shell after a run, or by `Aç…`."""
        self.source = path
        self.source_var.set(str(path))
        self.excluded.clear()
        try:
            self.snapshot = snapshot_module.load(path)
        except snapshot_module.SnapshotError as exc:
            self.snapshot = None
            self.source_note.configure(text=str(exc), foreground=w.BAD)
            self._repaint()
            return
        except OSError as exc:                          # pragma: no cover - rare
            self.snapshot = None
            self.source_note.configure(text=f"Dosya açılamadı: {exc}",
                                       foreground=w.BAD)
            self._repaint()
            return

        self.filter_key = recipients.ALL
        self._describe_source()
        self._repaint()

    def _describe_source(self) -> None:
        assert self.snapshot is not None
        snap = self.snapshot
        line = (f"{period_label(snap.period)} · {len(snap.people)} kişi · "
                f"{snap.generated_at:%d.%m.%Y %H:%M} tarihinde üretildi")
        if snap.is_complete:
            self.source_note.configure(text=line, foreground=w.MUTED)
            return
        # ADR-020: a month whose sources stop mid-period. The figures are real but the
        # month is not, and this screen is the last place before somebody acts on them.
        missing = ", ".join(
            f"{source} {info.get('missing_from')} sonrası"
            for source, info in snap.coverage.items() if info.get("partial"))
        self.source_note.configure(
            text=f"{line}\n⚠ BU AY EKSİK — {missing}. Saatler bordro için "
                 f"kullanılamaz.", foreground=w.BAD)

    def _choose_file(self) -> None:
        start = self.source.parent if self.source else self.base
        picked = filedialog.askopenfilename(
            title="Rapor veri dosyasını seçin",
            initialdir=str(start),
            filetypes=[("Veri dosyası", "gonderim-*.json"),
                       ("JSON", "*.json"), ("Tüm dosyalar", "*.*")])
        if picked:
            self.load(Path(picked))

    # --- filtering ---------------------------------------------------------
    def _filter_changed(self, _event: object = None) -> None:
        chosen = self.filter_var.get()
        for choice in self._choices:
            if choice.display == chosen:
                self.filter_key = choice.key
                break
        # Removals belong to the group they were made in. Carrying them across a filter
        # change would silently keep somebody out of a list they were never removed
        # from.
        self.excluded.clear()
        self._repaint()

    def _select_all(self) -> None:
        self.excluded.clear()
        self._repaint()

    def _clear_all(self) -> None:
        self.excluded = {p.name for p in recipients.matching(self.snapshot,
                                                             self.filter_key)}
        self._repaint()

    def _toggle(self, name: str, var: tk.BooleanVar) -> None:
        if var.get():
            self.excluded.discard(name)
        else:
            self.excluded.add(name)
        self._update_count()

    def _copy(self) -> None:
        people = recipients.selected(self.snapshot, self.filter_key, self.excluded)
        if not people:
            return
        text = "\n".join(f"{p.name}\t{p.email or ''}\t{p.hours_text}" for p in people)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # --- painting ----------------------------------------------------------
    def _repaint(self) -> None:
        self._choices = recipients.choices(self.snapshot)
        self.filter_box.configure(values=[c.display for c in self._choices])
        for choice in self._choices:
            if choice.key == self.filter_key:
                self.filter_var.set(choice.display)
                self.filter_note.configure(
                    text="" if choice.key in (recipients.ALL, recipients.NO_PROBLEM)
                    else ("bu bir sorun değil, beklenen durum"
                          if not choice.is_problem else ""),
                    foreground=w.MUTED)
                break

        for child in self.list_frame.winfo_children():
            child.destroy()
        self._rows = []
        # The address column takes the slack, not the name column. Names are short and
        # of a known length; an address is the thing that runs out of room, and it was
        # being clipped mid-word with no indication that anything had been cut.
        self.list_frame.columnconfigure(1, weight=0)
        self.list_frame.columnconfigure(4, weight=1)

        if self.snapshot is None:
            tk.Label(self.list_frame,
                     text="Rapor oluşturduktan sonra kişiler burada listelenir.\n"
                          "Daha önce üretilmiş bir ay için 'Aç…' ile veri dosyasını "
                          "seçebilirsiniz.",
                     background=w.CARD, foreground=w.MUTED, font=(w.FACE, 9),
                     justify="left", anchor="w", padx=14, pady=12).grid(
                row=0, column=0, columnspan=4, sticky="w")
            self._update_count()
            return

        people = recipients.matching(self.snapshot, self.filter_key)
        for row, person in enumerate(people):
            var = tk.BooleanVar(value=person.name not in self.excluded)
            box = tk.Checkbutton(
                self.list_frame, variable=var, background=w.CARD,
                activebackground=w.CARD, highlightthickness=0, borderwidth=0,
                command=lambda n=person.name, v=var: self._toggle(n, v))
            box.grid(row=row, column=0, sticky="w", padx=(10, 4))
            self._rows.append((person.name, var))

            tk.Label(self.list_frame, text=person.name, background=w.CARD,
                     foreground=w.INK, font=(w.FACE, 9), anchor="w").grid(
                row=row, column=1, sticky="ew")
            tk.Label(self.list_frame, text=person.hours_text, background=w.CARD,
                     foreground=w.MUTED, font=(w.MONO, 9), anchor="e", width=8).grid(
                row=row, column=2, sticky="e", padx=(8, 8))

            # Only a count, never the notes themselves. Somebody filtering by one note
            # still needs to know this person has others — "fix the missing exit" is a
            # different conversation if the same person also has three short days —
            # but printing every label on every row turns the list into a wall of text
            # and pushes the address off the edge.
            others = other_problems(person, self.filter_key)
            tk.Label(self.list_frame, text=f"+{others}" if others else "",
                     background=w.CARD, foreground=w.WARN if others else w.MUTED,
                     font=(w.FACE, 9), anchor="w", width=3).grid(
                row=row, column=3, sticky="w", padx=(0, 8))
            # No address is a fact about the row, not a reason to hide it. Eleven of
            # May's people are leavers the roster no longer carries an address for.
            trailing = person.email or "e-posta yok"
            tk.Label(self.list_frame, text=trailing, background=w.CARD,
                     foreground=w.MUTED if person.email else w.WARN,
                     font=(w.FACE, 9), anchor="w").grid(
                row=row, column=4, sticky="ew", padx=(0, 12))

        self._update_count()

    def _update_count(self) -> None:
        people = recipients.selected(self.snapshot, self.filter_key, self.excluded)
        total = len(recipients.matching(self.snapshot, self.filter_key))
        missing = recipients.without_email(people)
        text = f"{len(people)} / {total} kişi seçili"
        if missing:
            text += f"   ·   {len(missing)} kişinin e-postası yok"
        self.count_label.configure(text=text,
                                   foreground=w.WARN if missing else w.INK)
        w.set_enabled(self.copy_button, bool(people))
