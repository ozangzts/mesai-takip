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
from . import settings as settings_file
from ..mail.recipients import other_problems
from . import widgets as w
from .period import period_label

_ROW_HEIGHT = 22

# Day-of-week abbreviations, matching the report Gün column so the two read the
# same. Not settings.calendar.label(): this screen reads a snapshot and has no
# settings, and that label also carries Tatil, which cannot happen on a day that is
# missing a record on an expected working day.
_GUN_KISA = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
# The note panel's header occupies row 0; family blocks start below it.
_NOTES_TOP = 1


class PeopleScreen:
    def __init__(self, parent: tk.Misc, *, root: tk.Misc, base: Path) -> None:
        self.root = root
        self.base = base
        self.snapshot: snapshot_module.Snapshot | None = None
        self.source: Path | None = None
        self.filter_key = recipients.ALL
        self.excluded: set[str] = set()
        # Which notes are NOT counted towards `Sorunu olanlar`. The off-set is stored
        # rather than the on-set on purpose: a note added to `anomalies.py` later then
        # counts by default, instead of quietly leaving people out of a list that
        # decides who gets contacted. Remembered between runs — this is a setup
        # decision, not a monthly one.
        self._off: set[str] = set(self._remembered_off())
        self._choices: tuple[recipients.Choice, ...] = ()
        # (name, row id) in display order. The tick itself is not stored here —
        # `excluded` is the one place it lives, and the glyph is drawn from it.
        self._rows: list[tuple[str, str]] = []
        self._pointer_in_list = False
        # The person whose days are on show, and the days taken OUT of the selection.
        # Off-set again, and for the same reason as `_off`: a day nobody has decided
        # about is in, so a new day cannot quietly fall out of a list that decides what
        # somebody is told. Keyed on (name, ISO date) rather than a row index, because
        # the list re-sorts and re-filters underneath — the mistake `excluded` avoids.
        self._person: str | None = None
        self._days_off: set[tuple[str, str]] = set()
        self._day_rows: list[tuple[str, str]] = []      # (ISO date, row id)

        self._build(parent)
        self._repaint()

    def _remembered_off(self) -> tuple[str, ...]:
        stored = settings_file.load(self.base).get("problem_notes_off")
        if not isinstance(stored, list):
            return recipients.DEFAULT_OFF
        return tuple(str(label) for label in stored)

    def counted(self) -> frozenset[str]:
        """The notes that put somebody in `Sorunu olanlar`, for this month's snapshot."""
        present = {label for _g, label, _c
                   in recipients.problem_labels(self.snapshot)}
        return frozenset(present - self._off)

    # --- layout ------------------------------------------------------------
    def _build(self, parent: tk.Misc) -> None:
        body = self.frame = tk.Frame(parent, background=w.BG)
        # Two columns, so the day panel costs width and not height. Height is the
        # dimension that has bitten twice (ADR-038) and the window floor is 620 px;
        # width can grow and the panel shares what is there. The person list keeps the
        # larger share because its e-mail column is the one that wants room.
        body.columnconfigure(0, weight=3, minsize=430)
        body.columnconfigure(1, weight=2, minsize=430)
        body.rowconfigure(6, weight=1)

        w.caption(body, "VERİ DOSYASI", row=0)
        source_row = tk.Frame(body, background=w.BG)
        source_row.grid(row=1, column=0, columnspan=2, sticky="ew")
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
        self.source_note.grid(row=2, column=0, columnspan=2, sticky="ew",
                              pady=(8, 16))

        # --- filter ------------------------------------------------------
        w.caption(body, "FİLTRE", row=3)
        filter_row = tk.Frame(body, background=w.BG)
        filter_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        filter_row.columnconfigure(1, weight=1)
        self.filter_var = tk.StringVar(value="")
        self.filter_box = ttk.Combobox(filter_row, textvariable=self.filter_var,
                                       state="readonly", width=42,
                                       font=(w.FACE, 10))
        self.filter_box.grid(row=0, column=0, sticky="w", ipady=3)
        self.filter_box.bind("<<ComboboxSelected>>", self._filter_changed)
        self.filter_box.bind("<MouseWheel>", self._wheel_over_filter)

        self.filter_note = tk.Label(filter_row, background=w.BG, foreground=w.MUTED,
                                    font=(w.FACE, 9), anchor="w", justify="left")
        self.filter_note.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # --- which notes count as a problem ------------------------------
        #
        # Shown only under `Sorunu olanlar`, because under any other filter there is
        # nothing for it to change. One column per family so twelve checkboxes read as
        # four short lists rather than one wall (ADR-029).
        self.notes_frame = tk.Frame(body, background=w.CARD, highlightthickness=1,
                                    highlightbackground=w.LINE)
        self.notes_frame.grid(row=5, column=0, columnspan=2, sticky="ew",
                              pady=(0, 12))
        self.notes_frame.grid_remove()
        self._note_vars: dict[str, tk.BooleanVar] = {}

        # --- the list ----------------------------------------------------
        #
        # A `ttk.Treeview`, not a frame of labels inside a canvas. The frame worked and
        # was smooth enough at ten rows; at a real month's 171 it was not. Measured:
        # 856 widgets, 1 065 ms to draw the list, and 58 ms for one scroll step (worst
        # 145 ms), because tk repositions every one of those widgets on every step.
        # That is what the operator saw as rows smearing over each other while dragging
        # and settling once released. The same 171 rows in a Treeview: 20 ms to redraw,
        # 17.7 ms per step, worst 19 ms — it draws text instead of moving widgets.
        # ADR-039.
        card = tk.Frame(body, background=w.LINE)
        card.grid(row=6, column=0, sticky="nsew", padx=(0, 10))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Kisiler.Treeview", background=w.CARD, fieldbackground=w.CARD,
                        foreground=w.INK, font=(w.FACE, 9), rowheight=_ROW_HEIGHT,
                        borderwidth=0, relief="flat")
        # The vista theme draws a sunken border around a Treeview and offers no option
        # to turn it off; the card's hairline is the border here, so the element is
        # taken out of the layout instead.
        style.layout("Kisiler.Treeview",
                     [("Treeview.treearea", {"sticky": "nswe"})])

        self.tree = ttk.Treeview(
            card, style="Kisiler.Treeview", show="", selectmode="none",
            columns=("tik", "ad", "saat", "diger", "eposta"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for column, width, anchor, stretch in (
                ("tik", 34, "center", False),
                ("ad", 210, "w", False),
                # Right-aligned rather than set in the fixed-width face: a Treeview
                # takes one font for the whole widget, and lining up the ends of the
                # figures is what made this column readable without one.
                ("saat", 66, "e", False),
                ("diger", 38, "w", False),
                ("eposta", 240, "w", True)):
            self.tree.column(column, width=width, anchor=anchor, stretch=stretch)
        # A tag colours a whole row — a Treeview has no per-cell colour. Only the
        # missing address earns one, because it is the one thing on a row that stops
        # the mail step from working. The note count stays plain text.
        self.tree.tag_configure("adres-yok", foreground=w.WARN)

        self._scroll = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self._scrolled)
        self.tree.bind("<Button-1>", self._clicked)
        self.tree.bind("<Enter>", self._grab_wheel)
        self.tree.bind("<Leave>", self._release_wheel)
        # Three bindings for one gesture, because tk offers no single place that
        # catches it. `_grab_wheel` says why.
        self.tree.bind("<MouseWheel>", self._wheel)

        # Shown in the list's place when no month is loaded. A Treeview cannot hold a
        # paragraph, and a fake row saying "nothing here" is still a row.
        self.empty_note = tk.Label(
            card, background=w.CARD, foreground=w.MUTED, font=(w.FACE, 9),
            justify="left", anchor="nw", padx=14, pady=12,
            text="Rapor oluşturduktan sonra kişiler burada listelenir.\n"
                 "Daha önce üretilmiş bir ay için 'Aç…' ile veri dosyasını "
                 "seçebilirsiniz.")

        # --- the selected person's days -----------------------------------
        #
        # Master-detail beside the list rather than under it. The operator asked for a
        # person's faulty days "like Günlük Detay" and for the days to be selectable, so
        # this is the same shape as the person list: a Treeview with a tick column, the
        # tick living in an off-set keyed on the date.
        day_card = self.day_card = tk.Frame(body, background=w.LINE)
        day_card.grid(row=6, column=1, sticky="nsew")
        day_card.columnconfigure(0, weight=1)
        day_card.rowconfigure(1, weight=1)

        self.day_title = tk.Label(
            day_card, background=w.CARD, foreground=w.INK, font=(w.FACE, 9, "bold"),
            anchor="w", padx=10, pady=6)
        self.day_title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=1,
                            pady=(1, 0))

        style.configure("Gunler.Treeview", background=w.CARD, fieldbackground=w.CARD,
                        foreground=w.INK, font=(w.FACE, 9), rowheight=_ROW_HEIGHT,
                        borderwidth=0, relief="flat")
        style.layout("Gunler.Treeview",
                     [("Treeview.treearea", {"sticky": "nswe"})])

        self.day_tree = ttk.Treeview(
            day_card, style="Gunler.Treeview", show="", selectmode="none",
            columns=("tik", "tarih", "gun", "giris", "cikis", "sure", "not"))
        self.day_tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        for column, width, anchor, stretch in (
                ("tik", 34, "center", False),
                ("tarih", 74, "w", False),
                ("gun", 38, "w", False),
                ("giris", 50, "e", False),
                ("cikis", 50, "e", False),
                ("sure", 52, "e", False),
                ("not", 150, "w", True)):
            self.day_tree.column(column, width=width, anchor=anchor, stretch=stretch)

        self._day_scroll = ttk.Scrollbar(day_card, orient="vertical",
                                         command=self.day_tree.yview)
        self.day_tree.configure(yscrollcommand=self._day_scrolled)
        self.day_tree.bind("<Button-1>", self._day_clicked)
        self.day_tree.bind("<Enter>", self._grab_wheel)
        self.day_tree.bind("<Leave>", self._release_wheel)
        self.day_tree.bind("<MouseWheel>", self._day_wheel)

        # Shown in the day list's place until somebody picks a person. A Treeview
        # cannot hold a paragraph and a row saying "pick someone" is still a row.
        self.day_note = tk.Label(
            day_card, background=w.CARD, foreground=w.MUTED, font=(w.FACE, 9),
            justify="left", anchor="nw", padx=14, pady=12,
            text=("Soldaki listeden bir kişiye tıklayın; o kişinin sorunlu "
                  "günleri burada gün gün listelenir." + chr(10) * 2 +
                  "Adın solundaki kareye tıklamak kişiyi listeden çıkarır."))

        # --- actions ------------------------------------------------------
        actions = tk.Frame(body, background=w.BG)
        actions.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 0))
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
    #
    # The Treeview keeps its own scroll region, so an offset can no longer outlive the
    # rows it belonged to — which is what left a 2-person filter showing the empty
    # space below a 60-person one. What survives is the decision: a list of different
    # people starts at its top, the same people re-ticked keep their place (ADR-038,
    # ADR-039).

    _WHEEL_LINES = 3                  # what Windows itself scrolls per notch

    def _scrolled(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._scroll.grid_remove()
        else:
            self._scroll.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
        self._scroll.set(first, last)

    def _grab_wheel(self, _event: object = None) -> None:
        """Take the wheel while the pointer is over the list.

        Choosing a filter left the wheel doing nothing over the list, and which widget
        a `<MouseWheel>` reaches is not one answer: tk routes it by focus on some
        builds and by the window under the pointer on others, and the rows used to be
        labels that swallowed it either way. So the gesture is caught in three places
        and every one of them ends here:

        - **on the tree**, for when the event arrives at the widget under the pointer;
        - **on the `all` tag** while the pointer is inside, for when it arrives at
          whatever holds focus — a button, the path field, anything;
        - **on the filter box**, which needs its own handler for a second reason, in
          `_wheel_over_filter`.

        A widget binding runs before its class binding, which is what stops the list
        being scrolled twice at two speeds when the tree itself has focus: ttk's own
        Treeview binding moves one row per notch, this one moves three — the number
        Windows uses.

        `unbind_all` is safe only because nothing else in this window binds
        `<MouseWheel>` on the `all` tag. If something ever does, this has to change.
        """
        self._pointer_in_list = True
        self.tree.bind_all("<MouseWheel>", self._wheel)

    def _release_wheel(self, _event: object = None) -> None:
        self._pointer_in_list = False
        self.tree.unbind_all("<MouseWheel>")

    def _wheel_over_filter(self, event: tk.Event) -> str:
        """The wheel must never change the filter.

        ttk gives every combobox a class binding that steps its value on each notch.
        On this screen that meant a stray notch moved the filter from `Herkes` to
        `Sorunu olmayanlar` to `Çıkış yok` — measured, 43 people to 40 to 3 — and each
        change also drops the removals made by hand, because a removal belongs to the
        group it was made in. A gesture whose effect depends on where the focus
        invisibly happens to be does not belong on the screen that decides who gets an
        e-mail.

        Returning "break" is what stops the class binding from running. The list is
        still scrolled while the pointer is over it, so the wheel does exactly one
        thing.
        """
        if self._pointer_in_list:
            self._wheel(event)
        return "break"

    def _wheel(self, event: tk.Event) -> str:
        self.tree.yview_scroll(int(-event.delta / 120) * self._WHEEL_LINES, "units")
        return "break"

    # --- loading -----------------------------------------------------------
    def load(self, path: Path) -> None:
        """Show the month in `path`. Called by the shell after a run, or by `Aç…`."""
        self.source = path
        self.source_var.set(str(path))
        self.excluded.clear()
        # A new month means new days; keeping last month's ticks would carry a decision
        # about dates that are not in this file.
        self._person = None
        self._days_off.clear()
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
        parts = [f"{source} {info.get('missing_from')} sonrası"
                 for source, info in snap.coverage.items() if info.get("partial")]
        # ADR-057: the other shape of an uncovered period — a working day on which
        # nobody was recorded at either site. It may equally be a holiday that was
        # never marked, so the wording does not decide between the two.
        if snap.blank_workdays:
            gunler = ", ".join(f"{d:%d.%m}" for d in snap.blank_workdays[:6])
            if len(snap.blank_workdays) > 6:
                gunler += " ..."
            parts.append(f"{len(snap.blank_workdays)} iş gününde hiçbir tesiste "
                         f"kayıt yok ({gunler})")
        missing = ", ".join(parts)
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
        # from. Day ticks are NOT cleared: they are about one person's one date, which
        # means the same thing under every filter, and re-picking them after every
        # filter change is exactly the work this panel exists to save.
        self.excluded.clear()
        self._repaint()

    def _select_all(self) -> None:
        self.excluded.clear()
        self._redraw_ticks()

    def _clear_all(self) -> None:
        self.excluded = {p.name for p in recipients.matching(
            self.snapshot, self.filter_key, self.counted())}
        self._redraw_ticks()

    def _redraw_ticks(self) -> None:
        """Repaint every glyph without rebuilding the list.

        These two buttons change no row's contents and no row's order, so rebuilding
        would only throw the reader back to the top of a list they were halfway down.
        """
        for name, row in self._rows:
            self.tree.set(row, "tik", self._glyph(name))
        self._update_count()

    def _clicked(self, event: tk.Event) -> str | None:
        """Two targets on one row: the tick column takes the person out of the list,
        the rest of the row shows that person's days.

        It used to be the whole row for the tick, on the reasoning that in-or-out was
        the only thing a row did. A row does two things now (ADR-064), so it needs two
        targets, and the 34 px tick column is a comfortable one — the glyph is already
        there and it is what somebody aims at anyway. Clicking below the last row does
        nothing rather than acting on whoever is nearest.
        """
        item = self.tree.identify_row(event.y)
        if not item:
            return None
        on_tick = self.tree.identify_column(event.x) == "#1"
        for name, row in self._rows:
            if row == item:
                if on_tick:
                    self._toggle(name)
                else:
                    self._person = name
                    self._paint_days()
                break
        return "break"

    # --- the selected person's days ----------------------------------------
    def _person_days(self) -> tuple:
        """The days on show — the ones the ticked notes are about, for this person.

        `days_for` and nothing else, so this panel lists exactly what the mail step
        would carry: days where nothing was counted and no leave covers them (ADR-059,
        ADR-061). A day the other site's record already covered is not here, because it
        is not a problem.
        """
        if self.snapshot is None or self._person is None:
            return ()
        person = next((p for p in self.snapshot.people
                       if p.name == self._person), None)
        if person is None:
            return ()
        return recipients.days_for(person, self.counted())

    def day_selection(self) -> tuple[tuple[str, str], ...]:
        """`(name, ISO date)` for every day still selected, across every person.

        The mail step's input, and the reason the off-set is keyed on the date rather
        than on a row: this survives re-sorting, re-filtering and switching person —
        the mistake `excluded` already avoids.
        """
        if self.snapshot is None:
            return ()
        counted = self.counted()
        return tuple(
            (person.name, day.date.isoformat())
            for person in recipients.selected(self.snapshot, self.filter_key,
                                              self.excluded, counted)
            for day in recipients.days_for(person, counted)
            if (person.name, day.date.isoformat()) not in self._days_off)

    def _day_headline(self, days: tuple) -> str:
        chosen = sum(1 for d in days
                     if (self._person, d.date.isoformat()) not in self._days_off)
        return f"{self._person} — {len(days)} sorunlu gün, {chosen} seçili"

    def _paint_days(self) -> None:
        self.day_tree.delete(*self.day_tree.get_children())
        self._day_rows = []
        days = self._person_days()

        if self._person is None or not days:
            self.day_tree.grid_remove()
            self._day_scroll.grid_remove()
            self.day_note.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
            if self._person is None:
                self.day_title.configure(text="GÜNLER")
            else:
                self.day_title.configure(text=f"{self._person} — sorunlu gün yok")
                self.day_note.configure(
                    text="Bu kişinin, işaretli notlara ait ve hiçbir yerde "
                         "sayılmamış bir günü yok." + chr(10) * 2 +
                         "Notlardan seçimi değiştirirseniz bu liste de değişir.")
            return

        self.day_note.grid_remove()
        self.day_tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self.day_title.configure(text=self._day_headline(days))

        for day in days:
            key = (self._person, day.date.isoformat())
            row = self.day_tree.insert(
                "", "end",
                values=("☐" if key in self._days_off else "☑",
                        day.date.strftime("%d.%m.%Y"),
                        _GUN_KISA[day.date.weekday()],
                        day.entry_text or "—", day.exit_text or "—",
                        day.hours_text or "—",
                        ", ".join(day.problems)))
            self._day_rows.append((day.date.isoformat(), row))
        self._day_scrolled(*self.day_tree.yview())

    def _day_clicked(self, event: tk.Event) -> str | None:
        """A click anywhere on a day row takes that day in or out.

        The whole row here, unlike the person list above: a day row does one thing.
        """
        item = self.day_tree.identify_row(event.y)
        if not item or self._person is None:
            return None
        for iso, row in self._day_rows:
            if row == item:
                key = (self._person, iso)
                if key in self._days_off:
                    self._days_off.discard(key)
                else:
                    self._days_off.add(key)
                self.day_tree.set(row, "tik",
                                  "☐" if key in self._days_off else "☑")
                self.day_title.configure(
                    text=self._day_headline(self._person_days()))
                break
        return "break"

    def _day_scrolled(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._day_scroll.grid_remove()
        else:
            self._day_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 1))
        self.day_tree.yview_moveto(first)

    def _day_wheel(self, event: tk.Event) -> str:
        self.day_tree.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _toggle(self, name: str) -> None:
        if name in self.excluded:
            self.excluded.discard(name)
        else:
            self.excluded.add(name)
        self._redraw_tick(name)
        self._update_count()

    def _redraw_tick(self, name: str) -> None:
        """Repaint one row's glyph. The rest of the row has not changed."""
        for listed, row in self._rows:
            if listed == name:
                self.tree.set(row, "tik", self._glyph(name))
                return

    def _glyph(self, name: str) -> str:
        return "☐" if name in self.excluded else "☑"

    def _copy(self) -> None:
        people = recipients.selected(self.snapshot, self.filter_key, self.excluded,
                                     self.counted())
        if not people:
            return
        text = "\n".join(f"{p.name}\t{p.email or ''}\t{p.hours_text}" for p in people)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # --- which notes count -------------------------------------------------
    def _paint_notes(self) -> None:
        """Rebuild the checkbox panel, or hide it when it has nothing to say."""
        for child in self.notes_frame.winfo_children():
            child.destroy()
        self._note_vars = {}

        offered = recipients.problem_labels(self.snapshot)
        if self.filter_key != recipients.PROBLEM or not offered:
            self.notes_frame.grid_remove()
            return
        self.notes_frame.grid()

        header = tk.Frame(self.notes_frame, background=w.CARD)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 2))
        header.columnconfigure(0, weight=1)
        w.button(header, "Hepsi", self._count_all, primary=False).grid(
            row=0, column=1, padx=(8, 0))
        w.button(header, "Temizle", self._count_none, primary=False).grid(
            row=0, column=2, padx=(6, 0))

        # `Günü sayılmayan` first, always, whatever the snapshot's order — that group is
        # the reason the split exists and it may not drift below the other one.
        groups: dict[str, list[tuple[str, int]]] = {
            recipients.LOST: [], recipients.KEPT: []}
        for group, label, count in offered:
            groups[group].append((label, count))
        families = {name: rows for name, rows in groups.items() if rows}

        # Two columns, not one per family. Four columns of Turkish labels do not fit
        # the width — `Günlük süre çok uzun (>16 saat)  (4)` was clipped mid-count, and
        # a checkbox whose text is cut off is worse than a taller panel. Blocks are
        # dealt into whichever column is shorter, so the two sides stay even.
        heights = [0, 0]
        rows = [_NOTES_TOP, _NOTES_TOP]
        for family, labels in families.items():
            side = 0 if heights[0] <= heights[1] else 1
            heights[side] += len(labels) + 1
            tk.Label(self.notes_frame, text=family, background=w.CARD,
                     foreground=w.INK, font=(w.FACE, 9, "bold"), anchor="w").grid(
                row=rows[side], column=side, sticky="w", padx=(10, 24),
                pady=(6 if rows[side] > _NOTES_TOP else 2, 2))
            rows[side] += 1
            for label, count in labels:
                var = tk.BooleanVar(value=label not in self._off)
                self._note_vars[label] = var
                tk.Checkbutton(
                    self.notes_frame, text=f"{label}  ({count})", variable=var,
                    background=w.CARD, activebackground=w.CARD, foreground=w.INK,
                    font=(w.FACE, 9), highlightthickness=0, borderwidth=0, anchor="w",
                    command=lambda lbl=label: self._toggle_note(lbl)).grid(
                    row=rows[side], column=side, sticky="w", padx=(8, 24))
                rows[side] += 1

        for column in (0, 1):
            self.notes_frame.columnconfigure(column, weight=1)
        tk.Frame(self.notes_frame, background=w.CARD, height=8).grid(
            row=max(rows), column=0, columnspan=2, sticky="ew")

    def _toggle_note(self, label: str) -> None:
        if self._note_vars[label].get():
            self._off.discard(label)
        else:
            self._off.add(label)
        self._remember_off()
        self._repaint()

    def _count_all(self) -> None:
        self._off.clear()
        self._remember_off()
        self._repaint()

    def _count_none(self) -> None:
        self._off = {label for _g, label, _c
                     in recipients.problem_labels(self.snapshot)}
        self._remember_off()
        self._repaint()

    def _remember_off(self) -> None:
        settings_file.update(self.base, problem_notes_off=sorted(self._off))

    # --- painting ----------------------------------------------------------
    def _repaint(self) -> None:
        listed_before = [name for name, _ in self._rows]
        self._choices = recipients.choices(self.snapshot, self.counted())
        self.filter_box.configure(values=[c.display for c in self._choices])
        for choice in self._choices:
            if choice.key == self.filter_key:
                self.filter_var.set(choice.display)
                self.filter_note.configure(
                    text="" if choice.key in recipients.STANDING
                    else ("bu bir sorun değil, beklenen durum"
                          if not choice.is_problem else ""),
                    foreground=w.MUTED)
                break

        self.tree.delete(*self.tree.get_children())
        self._rows = []

        if self.snapshot is None:
            self.tree.grid_remove()
            self._scroll.grid_remove()
            self.empty_note.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
            self._paint_notes()
            self._paint_days()
            self._update_count()
            return
        self.empty_note.grid_remove()
        self.tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        for person in recipients.matching(self.snapshot, self.filter_key,
                                          self.counted()):
            # Only a count of the other notes, never the notes themselves. Somebody
            # filtering by one note still needs to know this person has others — "fix
            # the missing exit" is a different conversation if the same person also has
            # three short days — but printing every label on every row turns the list
            # into a wall of text and pushes the address off the edge.
            others = other_problems(person, self.filter_key)
            # No address is a fact about the row, not a reason to hide it. Eleven of
            # May's people are leavers the roster no longer carries an address for.
            row = self.tree.insert(
                "", "end", tags=() if person.email else ("adres-yok",),
                values=(self._glyph(person.name), person.name, person.hours_text,
                        f"+{others}" if others else "",
                        person.email or "e-posta yok"))
            self._rows.append((person.name, row))

        self._paint_notes()
        # A person the filter no longer admits must not stay on show beside it: the
        # panel would be describing somebody the list does not contain. Their ticks are
        # kept — `_days_off` is keyed on the name, so coming back restores what was
        # chosen, the same way a re-filter does not forget `_off`.
        if self._person is not None and self._person not in {n for n, _ in self._rows}:
            self._person = None
        self._paint_days()
        self._update_count()
        if listed_before != [name for name, _ in self._rows]:
            self.tree.yview_moveto(0.0)

    def _update_count(self) -> None:
        counted = self.counted()
        people = recipients.selected(self.snapshot, self.filter_key, self.excluded,
                                     counted)
        total = len(recipients.matching(self.snapshot, self.filter_key, counted))
        missing = recipients.without_email(people)
        text = f"{len(people)} / {total} kişi seçili"
        if missing:
            text += f"   ·   {len(missing)} kişinin e-postası yok"
        self.count_label.configure(text=text,
                                   foreground=w.WARN if missing else w.INK)
        w.set_enabled(self.copy_button, bool(people))
