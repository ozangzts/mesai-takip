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
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, ttk

from .. import snapshot as snapshot_module
from ..anomalies import DESCRIPTIONS
from ..mail import message, recipients, sender, template as mail_template
from . import settings as settings_file
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
# Checkbox columns in the note panel. Three since every note became selectable: the
# panel doubled in entries and its height is the day panel's height.
_NOTE_COLUMNS = 3


class MailPreview:
    """The message, on screen, before anything leaves — and editable there.

    Why a preview at all: a send is the one action in this program that cannot be
    undone. Everything else writes a file the operator can look at and regenerate. So
    the last thing between the composed text and somebody's inbox is a person reading
    it.

    Why editable: the composed body is a starting point. The operator knows things the
    snapshot does not, and a preview that can only be accepted or cancelled makes them
    choose between sending the wrong words and not writing at all.

    **What is on screen is what is sent.** The text widget is read back at send time,
    not the draft that opened the window. A preview showing one thing while another
    goes out would be worse than no preview.
    """

    def __init__(self, parent: tk.Misc, draft, send) -> None:
        self._parent = parent
        self._draft = draft
        self._send = send
        self.window: tk.Toplevel | None = None
        self.status: tk.Label | None = None
        self.sent = False

    def show(self) -> tk.Toplevel:
        top = self.window = tk.Toplevel(self._parent)
        top.title("E-posta önizleme")
        top.configure(background=w.BG)
        top.transient(self._parent)
        top.geometry("640x560")
        top.minsize(520, 420)
        top.columnconfigure(0, weight=1)
        top.rowconfigure(3, weight=1)

        head = tk.Frame(top, background=w.BG)
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        head.columnconfigure(1, weight=1)
        tk.Label(head, text="Kime", background=w.BG, foreground=w.MUTED,
                 font=(w.FACE, 9)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.to_var = tk.StringVar(value=self._draft.to)
        tk.Entry(head, textvariable=self.to_var, font=(w.FACE, 9), relief="flat",
                 background=w.CARD, foreground=w.INK, highlightthickness=1,
                 highlightbackground=w.LINE, highlightcolor=w.ACCENT).grid(
            row=0, column=1, sticky="ew", ipady=4)

        tk.Label(head, text="Konu", background=w.BG, foreground=w.MUTED,
                 font=(w.FACE, 9)).grid(row=1, column=0, sticky="w", padx=(0, 8),
                                        pady=(8, 0))
        self.subject_var = tk.StringVar(value=self._draft.subject)
        tk.Entry(head, textvariable=self.subject_var, font=(w.FACE, 9), relief="flat",
                 background=w.CARD, foreground=w.INK, highlightthickness=1,
                 highlightbackground=w.LINE, highlightcolor=w.ACCENT).grid(
            row=1, column=1, sticky="ew", ipady=4, pady=(8, 0))

        # What this window can and cannot show. It renders the PLAIN part — tkinter has
        # no HTML engine — and the message also carries an HTML part with the table,
        # which is what most people will actually see. Saying "gönderilecek olan bu
        # pencerede gördüğünüzün aynısıdır" while a whole second version went out
        # unseen was the gap: the operator opened the window, saw text they recognised,
        # and concluded the template had not changed.
        note_row = tk.Frame(top, background=w.BG)
        note_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(10, 4))
        note_row.columnconfigure(0, weight=1)
        self.note = tk.Label(note_row, background=w.BG, foreground=w.MUTED,
                             font=(w.FACE, 8), anchor="w", justify="left",
                             wraplength=470)
        self.note.grid(row=0, column=0, sticky="ew")
        if self._draft.html.strip():
            self.note.configure(
                text="Aşağıdaki DÜZ METİN düzenlenebilir. Mail ayrıca tablolu bir "
                     "HTML biçimi taşıyor ve çoğu kişi onu görecek — sağdaki düğme "
                     "onu tarayıcıda açar. Düz metni düzenlerseniz HTML biçimi "
                     "gönderilmez.")
            w.button(note_row, "HTML'i tarayıcıda gör", self._show_html,
                     primary=False).grid(row=0, column=1, sticky="e", padx=(10, 0))
        else:
            self.note.configure(
                text="Aşağıdaki metin düzenlenebilir. Gönderilecek olan, bu "
                     "pencerede gördüğünüzün aynısıdır — bu mail yalnızca düz "
                     "metin taşıyor.")

        body_card = tk.Frame(top, background=w.LINE)
        body_card.grid(row=3, column=0, sticky="nsew", padx=14)
        body_card.columnconfigure(0, weight=1)
        body_card.rowconfigure(0, weight=1)
        self.body = tk.Text(body_card, font=(w.FACE, 10), wrap="word", relief="flat",
                            background=w.CARD, foreground=w.INK, padx=12, pady=10,
                            undo=True)
        self.body.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.body.insert("1.0", self._draft.body)
        scroll = ttk.Scrollbar(body_card, orient="vertical",
                               command=self.body.yview)
        self.body.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns", pady=1)

        self.status = tk.Label(top, background=w.BG, foreground=w.MUTED,
                               font=(w.FACE, 9), anchor="w", justify="left",
                               wraplength=600)
        self.status.grid(row=4, column=0, sticky="ew", padx=14, pady=(8, 0))

        actions = tk.Frame(top, background=w.BG)
        actions.grid(row=5, column=0, sticky="ew", padx=14, pady=14)
        actions.columnconfigure(0, weight=1)
        w.button(actions, "Vazgeç", self.close, primary=False).grid(
            row=0, column=1, padx=(0, 8))
        self.send_button = w.button(actions, "Gönder", self.confirm, primary=True)
        self.send_button.grid(row=0, column=2)

        top.bind("<Escape>", lambda _e: self.close())
        return top

    def current(self):
        """The draft as it stands in the window — the thing that will be sent.

        **The HTML part is dropped once the body is edited.** The window shows and edits
        the plain text; an HTML alternative that still carried the original wording would
        mean the recipient reads something the operator never saw, and most mail clients
        would show them exactly that part. Editing here is therefore a decision to send
        the plain version. Changing the table itself is an edit to
        `config/mail-taslagi.yaml`, which is where the HTML lives.
        """
        body = self.body.get("1.0", "end-1c")
        html = self._draft.html if body.strip() == self._draft.body.strip() else ""
        return replace(self._draft, to=self.to_var.get().strip(),
                       subject=self.subject_var.get().strip(),
                       body=body, html=html)

    def _show_html(self) -> None:
        """Open the HTML part in the default browser.

        A temporary file rather than anything clever: the point is to let a person look
        at the thing that will be sent, and a browser is the only renderer on the machine
        that shows it the way a mail client will. Written fresh each time, so it follows
        an edit to `config/mail-taslagi.yaml` without restarting.
        """
        import tempfile
        import webbrowser

        html = self.current().html or self._draft.html
        if not html.strip():
            return
        path = Path(tempfile.gettempdir()) / "mesai-mail-onizleme.html"
        path.write_text(html, encoding="utf-8")
        webbrowser.open(path.as_uri())

    def confirm(self) -> None:
        draft = self.current()
        if not draft.is_sendable:
            self._say("Alıcı adresi ya da mesaj gövdesi boş.", w.BAD)
            return
        w.set_enabled(self.send_button, False)
        self._say("Gönderiliyor…", w.MUTED)
        if self.window is not None:
            self.window.update_idletasks()
        ok, note = self._send(draft)
        self.sent = ok
        if ok:
            self._say(note, w.OK)
            # Left open for a moment rather than vanishing: the one thing the operator
            # wants to see after an irreversible action is confirmation that it
            # happened, and a window that disappears looks the same as one that crashed.
            if self.window is not None:
                self.window.after(1200, self.close)
        else:
            self._say(note, w.BAD)
            w.set_enabled(self.send_button, True)

    def _say(self, text: str, colour: str) -> None:
        if self.status is not None:
            self.status.configure(text=text, foreground=colour)

    def close(self) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class PeopleScreen:
    def __init__(self, parent: tk.Misc, *, root: tk.Misc, base: Path,
                 config_dir: Path | None = None) -> None:
        self.root = root
        self.base = base
        # Taken from the shell, which already owns it and already allows an override.
        # This used to be computed here as `base / "config"`, which quietly ignored that
        # override — so the window read its rules from one place and its mail template
        # from another. Two answers to "where is config" is the same defect ADR-077 is
        # about, one layer down.
        self._config_dir = config_dir or (base / "config")
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
        # The counted days the operator has deliberately ticked ON. They start off
        # (`_off_for`), so an off-set alone could not express "yes, ask about this one".
        self._days_on: set[tuple[str, str]] = set()
        self._day_rows: list[tuple[str, str]] = []      # (ISO date, row id)
        # Whose address is currently in the mail field. Tracked so the field is refilled
        # when the person changes and left alone otherwise: a typed address must survive
        # ticking a day, and must NOT follow the operator onto the next person.
        self._mail_filled_for: str | None = None

        self._build(parent)
        self._repaint()

    @property
    def config_dir(self) -> Path:
        """Where `gmail.yaml` and `mail-taslagi.yaml` are looked for.

        Beside the program, never inside it: `config/` has to stay writable and
        hand-editable (`HANDOVER.md` §3, ADR-042), a credential compiled into an exe
        could not be rotated, and the mail wording has to be changeable without a
        rebuild (ADR-078).
        """
        return self._config_dir

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

        # Headings on. They were off while the list had one obvious column; with five,
        # `9:39` and `+2` beside each other were guesswork (ADR-066).
        style.configure("Kisiler.Treeview.Heading", background=w.BG, foreground=w.MUTED,
                        font=(w.FACE, 8, "bold"), relief="flat", borderwidth=0)
        self.tree = ttk.Treeview(
            card, style="Kisiler.Treeview", show="headings", selectmode="none",
            columns=("tik", "ad", "saat", "gun", "eposta"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for column, title, width, anchor, stretch in (
                ("tik", "", 34, "center", False),
                ("ad", "Ad Soyad", 210, "w", False),
                # Right-aligned rather than set in the fixed-width face: a Treeview
                # takes one font for the whole widget, and lining up the ends of the
                # figures is what made this column readable without one.
                ("saat", "Süre", 66, "e", False),
                # The count of days this person has outstanding — the number of rows the
                # panel on the right will show. It used to be `+2`, a count of the
                # person's OTHER notes, which answered "how many filters is this person
                # in" — a question nobody asks, and one more number in a screen that had
                # four of them for the same person. ADR-066.
                # "Gün" alone read as a plain day count next to a duration. It is the
                # count of the person's problem days — the rows the panel on the right
                # will show — so the heading says that.
                ("gun", "Sorunlu gün", 86, "e", False),
                ("eposta", "E-posta", 240, "w", True)):
            self.tree.column(column, width=width, anchor=anchor, stretch=stretch)
            self.tree.heading(column, text=title, anchor=anchor)
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

        style.configure("Gunler.Treeview.Heading", background=w.BG, foreground=w.MUTED,
                        font=(w.FACE, 8, "bold"), relief="flat", borderwidth=0)
        self.day_tree = ttk.Treeview(
            day_card, style="Gunler.Treeview", show="headings", selectmode="none",
            columns=("tik", "tarih", "gun", "giris", "cikis", "sure", "not"))
        self.day_tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        for column, title, width, anchor, stretch in (
                ("tik", "", 34, "center", False),
                ("tarih", "Tarih", 74, "w", False),
                ("gun", "Gün", 38, "w", False),
                ("giris", "Giriş", 50, "e", False),
                ("cikis", "Çıkış", 50, "e", False),
                ("sure", "Süre", 52, "e", False),
                ("not", "Sorun", 150, "w", True)):
            self.day_tree.column(column, width=width, anchor=anchor, stretch=stretch)
            self.day_tree.heading(column, text=title, anchor=anchor)

        # The note has to fit the panel it sits in, at any window size. A fixed
        # `wraplength` was cut off until the window was maximised, which is how the
        # loudest message on the screen came to be the one nobody could read (ADR-070).
        day_card.bind("<Configure>", self._day_card_resized)

        self._day_scroll = ttk.Scrollbar(day_card, orient="vertical",
                                         command=self.day_tree.yview)
        self.day_tree.configure(yscrollcommand=self._day_scrolled)
        self.day_tree.tag_configure("baslik", foreground=w.MUTED)
        self.day_tree.bind("<Button-1>", self._day_clicked)
        self.day_tree.bind("<Enter>", self._grab_wheel)
        self.day_tree.bind("<Leave>", self._release_wheel)
        self.day_tree.bind("<MouseWheel>", self._day_wheel)

        # --- the mail row, under the day list ---------------------------
        #
        # One person at a time, deliberately: no bulk send exists and none is offered
        # (`mail/sender.py`). The address is prefilled from the snapshot and stays
        # editable, because the eight people a month who have none are exactly the ones
        # somebody has to type in by hand, and a read-only field would send them
        # nowhere. Editing it does not write anything back — the snapshot is the record
        # of what the report said, and a typed address is this send only.
        mail_row = self.mail_row = tk.Frame(day_card, background=w.CARD)
        mail_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=1, pady=(0, 1))
        mail_row.columnconfigure(1, weight=1)
        tk.Label(mail_row, text="E-posta", background=w.CARD, foreground=w.MUTED,
                 font=(w.FACE, 9)).grid(row=0, column=0, sticky="w", padx=(10, 6),
                                        pady=8)
        self.mail_var = tk.StringVar(value="")
        self.mail_entry = tk.Entry(
            mail_row, textvariable=self.mail_var, font=(w.FACE, 9), relief="flat",
            background=w.CARD, foreground=w.INK, highlightthickness=1,
            highlightbackground=w.LINE, highlightcolor=w.ACCENT)
        self.mail_entry.grid(row=0, column=1, sticky="ew", ipady=4)
        self.mail_button = w.button(mail_row, "E-posta gönder…", self._preview_mail,
                                   primary=True)
        self.mail_button.grid(row=0, column=2, sticky="e", padx=(8, 10))
        self.mail_row.grid_remove()

        # Shown in the day list's place until somebody picks a person. A Treeview
        # cannot hold a paragraph and a row saying "pick someone" is still a row.
        self.day_note = tk.Label(
            day_card, background=w.CARD, foreground=w.MUTED, font=(w.FACE, 9),
            justify="left", anchor="nw", padx=14, pady=12, wraplength=380,
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
    def _off_for(self, person) -> set[tuple[str, str]]:
        """`_days_off` for this person, with the counted days seeded off.

        The off-set's rule everywhere else is *a day nobody has decided about is IN*, so
        a new note cannot quietly drop somebody (ADR-061). It is inverted for the days
        that cost nothing, and for the same underlying reason: including them by default
        would tell a person "eksik durum tespit edilmiştir" about a day that was counted
        in full. Silence is the expensive mistake when a day was LOST; a false statement
        is the expensive one when it was not.

        Seeded rather than stored, so ticking one on is remembered (it goes into
        `_days_on`) and nothing has to be written when a person is merely looked at.
        """
        _lost, kept = recipients.days_by_cost(person)
        off = {(person.name, day.date.isoformat()) for day in kept
               if (person.name, day.date.isoformat()) not in self._days_on}
        return off | self._days_off

    def _person_days(self) -> tuple[tuple, tuple]:
        """`(lost, kept)` for the person on show — every problem day they have.

        **Not the ticked set.** The panel and the count used to be `days_for(person,
        counted())`, so unticking a note walked them down: a person with 24 uncounted
        days showed 21 with only `Çıkış yok` ticked. A number that moves with a control
        is not a fact about the person (ADR-074). The ticks decide who is in the LIST;
        what a person's days are is not up for selection.
        """
        person = self._selected_person()
        if person is None:
            return (), ()
        return recipients.days_by_cost(person)

    def day_selection(self) -> tuple[tuple[str, str], ...]:
        """`(name, ISO date)` for every day still selected, across every person.

        The mail step's input, and the reason the off-set is keyed on the date rather
        than on a row: this survives re-sorting, re-filtering and switching person —
        the mistake `excluded` already avoids.
        """
        if self.snapshot is None:
            return ()
        return tuple(
            (person.name, day.date.isoformat())
            for person in recipients.selected(self.snapshot, self.filter_key,
                                              self.excluded, self.counted())
            for day in sum(recipients.days_by_cost(person), ())
            if (person.name, day.date.isoformat()) not in self._off_for(person))

    def _month_level_notes(self) -> list[str]:
        """This person's notes that are about the month rather than a day.

        `Kart bilgisi yok` has no dated day, so the day list has nothing to show for it
        and an empty panel read as "nothing wrong with this person" — the opposite of
        what the note says. The period is spelled out, because "which days" is the
        question the panel is there to answer and for this note the answer is all of
        them.
        """
        if self.snapshot is None or self._person is None:
            return []
        person = next((p for p in self.snapshot.people
                       if p.name == self._person), None)
        if person is None:
            return []
        dated = {label for day in person.days for label in day.problems}
        satirlar = []
        for label in person.problems:
            if label in dated:
                continue
            aciklama = next((e for l, _s, e, _g in DESCRIPTIONS.values()
                             if l == label), "")
            satirlar.append(f"{label}" + chr(10) + f"    {aciklama}")
        if satirlar:
            satirlar.append("")
            satirlar.append(f"Dönem: {period_label(self.snapshot.period)}")
        return satirlar

    def _day_headline(self, lost: tuple, kept: tuple) -> str:
        """Two counts, because the panel now holds two kinds of day.

        Lumping them would put the `Sorunlu gün` column and this line in disagreement
        for a reader who can see both at once — the column counts only what was lost.
        """
        person = self._selected_person()
        off = self._off_for(person) if person is not None else set()
        chosen = sum(1 for d in lost + kept
                     if (self._person, d.date.isoformat()) not in off)
        text = f"{self._person} — {len(lost)} sayılmayan gün"
        if kept:
            # `sayılan`, not `sayılan/izinli`: leave days left this panel in ADR-075 and
            # the heading below dropped the word, but this line kept it — so the one
            # number a reader could check against the block said it held something the
            # block does not. A stale word in a count is a false statement.
            text += f", {len(kept)} sayılan"
        return f"{text}, {chosen} seçili"

    def _paint_days(self) -> None:
        self.day_tree.delete(*self.day_tree.get_children())
        self._day_rows = []
        lost, kept = self._person_days()
        days = lost + kept

        if self._person is None or not days:
            self.day_tree.grid_remove()
            self._day_scroll.grid_remove()
            self.day_note.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
            if self._person is None:
                self.day_title.configure(text="GÜNLER", foreground=w.INK)
                self.day_note.configure(foreground=w.MUTED, font=(w.FACE, 9))
                self._paint_mail_row()
                return
            # A person can have nothing to list for two very different reasons, and
            # saying "sorunlu gün yok" to both made somebody with no card record at all
            # look fine. A month-level note has no day to show, so the panel shows the
            # note. ADR-069.
            aylik = self._month_level_notes()
            if aylik:
                # Red and bold. It carried the same muted grey as "nothing wrong here",
                # so the one message that means the opposite looked like it (ADR-070).
                self.day_title.configure(
                    text=f"⚠  {self._person} — GÜN BAZLI KAYIT YOK",
                    foreground=w.BAD)
                self.day_note.configure(text=chr(10).join(aylik),
                                        foreground=w.BAD, font=(w.FACE, 9, "bold"))
            else:
                self.day_title.configure(text=f"{self._person} — sorunlu gün yok",
                                         foreground=w.INK)
                self.day_note.configure(
                    text="Bu kişinin, işaretli notlara ait ve hiçbir yerde "
                         "sayılmamış bir günü yok." + chr(10) * 2 +
                         "Notlardan seçimi değiştirirseniz bu liste de değişir.",
                    foreground=w.MUTED, font=(w.FACE, 9))
            # Still offered: a month-level note (`Kart bilgisi yok`) is a real thing to
            # write to somebody about, and it is the note with no day to tick.
            self._paint_mail_row()
            return

        self.day_note.grid_remove()
        self.day_tree.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        self.day_title.configure(text=self._day_headline(lost, kept),
                                 foreground=w.INK)

        off = self._off_for(self._selected_person())
        for day in lost:
            self._insert_day(day, off)
        if kept:
            # A heading row rather than a word on each line. The distinction is about
            # the whole block, so saying it once is enough, and the `Sorun` column has
            # the note in it — a second phrase per row competes with the thing the row
            # is actually about. It said "sayılan ya da izinli" while leave days were
            # here too; they are not here any more (ADR-075), so it says one thing.
            heading = self.day_tree.insert(
                "", "end", tags=("baslik",),
                values=("", "SAYILAN GÜNLER", "", "", "", "",
                        "süre sayıldı — istenirse tek tek seçilir"))
            self._day_rows.append((None, heading))
            for day in kept:
                self._insert_day(day, off)
        self._day_scrolled(*self.day_tree.yview())
        self._paint_mail_row()

    def _insert_day(self, day, off: set) -> None:
        key = (self._person, day.date.isoformat())
        row = self.day_tree.insert(
            "", "end",
            values=("☐" if key in off else "☑",
                    day.date.strftime("%d.%m.%Y"),
                    _GUN_KISA[day.date.weekday()],
                    day.entry_text or "—", day.exit_text or "—",
                    day.hours_text or "—",
                    ", ".join(recipients.day_notes(day))))
        self._day_rows.append((day.date.isoformat(), row))

    # --- writing to one person ---------------------------------------------
    #
    # Person by person, and never a loop. `mail/sender.py` says why at length: 162
    # e-mails cannot be recalled, and a bulk send is a decision nobody has taken yet.
    # The window offers no control that would send more than one.

    def _selected_person(self):
        if self.snapshot is None or self._person is None:
            return None
        return next((p for p in self.snapshot.people
                     if p.name == self._person), None)

    def _paint_mail_row(self) -> None:
        """Show the address and the button for whoever is on the right, or hide both.

        The field is refilled from the snapshot whenever the person changes and left
        alone otherwise, so a typed address survives ticking a day off — but does not
        silently follow the operator onto the next person, which would send one
        person's mail to another's address.
        """
        person = self._selected_person()
        if person is None:
            self.mail_row.grid_remove()
            self._mail_filled_for = None
            return
        self.mail_row.grid()
        if self._mail_filled_for != person.name:
            self.mail_var.set(person.email or "")
            self._mail_filled_for = person.name
        w.set_enabled(self.mail_button, True)

    def _draft(self):
        """The draft for the person on show, with the address as it stands in the field.

        Composed by `mail.message.compose` and nowhere else, so the preview and the
        send cannot differ — a preview produced by different code is a preview of
        nothing.
        """
        person = self._selected_person()
        if person is None:
            return None
        # Whatever is ticked in the panel, of both kinds. A counted day is here only
        # if somebody ticked it on deliberately (`_off_for` starts them off), so the
        # message never tells a person "eksik durum tespit edilmiştir" about a day that
        # was counted in full unless that was asked for.
        off = self._off_for(person)
        chosen = [d for d in sum(self._person_days(), ())
                  if (person.name, d.date.isoformat()) not in off]
        # The template is read from `config/` on every draft, not cached: the operator
        # edits that file to change the wording and must see the change without
        # restarting. It is one small YAML file per preview.
        tpl = mail_template.load(self.config_dir)
        draft = message.compose(person, chosen, self.snapshot.period, self.counted(),
                                template=tpl)
        return replace(draft, to=self.mail_var.get().strip())

    def _preview_mail(self) -> None:
        """Show the message before anything leaves, and let it be edited.

        Editable on purpose: the composed text is a starting point, not a rule. What
        the operator approves in this window is byte-for-byte what is sent — the
        editor's contents are read back at send time, not the draft that opened it.
        """
        try:
            draft = self._draft()
        except mail_template.TemplateError as exc:
            # A broken template must not open a preview of nothing. The message names the
            # file and the field, because whoever edited it is the one who can fix it.
            self.day_title.configure(text=f"⚠  MAİL TASLAĞI KULLANILAMIYOR",
                                     foreground=w.BAD)
            self.day_note.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
            self.day_tree.grid_remove()
            self.day_note.configure(text=str(exc), foreground=w.BAD,
                                    font=(w.FACE, 9, "bold"))
            return
        if draft is None:
            return
        MailPreview(self.root, draft, self._send).show()

    def _send(self, draft) -> tuple[bool, str]:
        """Send one message. Returns `(ok, what to tell the operator)`.

        Every failure is reported in words rather than raised into the window: a missing
        `config/gmail.yaml` and a rejected app password are both fixed by a person, and
        a traceback tells them nothing about which it was.
        """
        try:
            account = sender.load_account(self.config_dir)
            sender.send(draft, account)
        except sender.MailError as exc:
            return False, str(exc)
        return True, f"Gönderildi: {draft.to}"

    def _day_clicked(self, event: tk.Event) -> str | None:
        """A click anywhere on a day row takes that day in or out.

        The whole row here, unlike the person list above: a day row does one thing.
        """
        item = self.day_tree.identify_row(event.y)
        person = self._selected_person()
        if not item or person is None:
            return None
        for iso, row in self._day_rows:
            if row != item:
                continue
            if iso is None:
                break               # the `SAYILAN…` heading row does nothing
            key = (person.name, iso)
            # Two stores, because the default differs by what the day cost: a lost day
            # starts in and comes out through `_days_off`, a counted one starts out and
            # goes in through `_days_on`. One set could not express both.
            if key in self._off_for(person):
                self._days_off.discard(key)
                self._days_on.add(key)
            else:
                self._days_on.discard(key)
                self._days_off.add(key)
            self.day_tree.set(row, "tik",
                              "☐" if key in self._off_for(person) else "☑")
            lost, kept = self._person_days()
            self.day_title.configure(text=self._day_headline(lost, kept))
            break
        return "break"

    def _day_scrolled(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._day_scroll.grid_remove()
        else:
            self._day_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 1))
        self.day_tree.yview_moveto(first)

    def _day_card_resized(self, event: tk.Event) -> None:
        self.day_note.configure(wraplength=max(240, event.width - 40))

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
        header.grid(row=0, column=0, columnspan=_NOTE_COLUMNS, sticky="ew",
                    padx=10, pady=(8, 2))
        header.columnconfigure(0, weight=1)
        w.button(header, "Hepsi", self._count_all, primary=False).grid(
            row=0, column=1, padx=(8, 0))
        w.button(header, "Temizle", self._count_none, primary=False).grid(
            row=0, column=2, padx=(6, 0))

        # EVERY note gets a checkbox. The `KEPT` ones were text-only because ticking
        # them selected nobody (ADR-069) — that was the filter's bug, not a property of
        # the notes, and `counted_only_labels` fixed it: `Gece geçişi (6)` now returns
        # its 6 people. A note that can be acted on belongs on a control.
        families = {group: [(label, count) for g, label, count in offered
                            if g == group]
                    for group in (recipients.LOST, recipients.KEPT)}
        families = {k: v for k, v in families.items() if v}

        # Three columns, and the labels FLOW across them under a heading that spans the
        # full width. Dealing whole families to columns instead — one family per column
        # — left the third column empty and let the taller family set the height on its
        # own: measured at the 880x620 floor, the panel took 267 px and the day panel
        # was left with 11. The day panel is where the mail step lives, so that height
        # is not the note panel's to take. Flowing is 6 rows instead of 11.
        row = _NOTES_TOP
        for family, labels in families.items():
            tk.Label(self.notes_frame, text=family, background=w.CARD,
                     foreground=w.INK, font=(w.FACE, 9, "bold"), anchor="w").grid(
                row=row, column=0, columnspan=_NOTE_COLUMNS, sticky="w",
                padx=(10, 24), pady=(6 if row > _NOTES_TOP else 2, 1))
            row += 1
            for index, (label, count) in enumerate(labels):
                if index and index % _NOTE_COLUMNS == 0:
                    row += 1
                var = tk.BooleanVar(value=label not in self._off)
                self._note_vars[label] = var
                tk.Checkbutton(
                    self.notes_frame, text=f"{label}  ({count})", variable=var,
                    background=w.CARD, activebackground=w.CARD, foreground=w.INK,
                    font=(w.FACE, 9), highlightthickness=0, borderwidth=0, anchor="w",
                    command=lambda lbl=label: self._toggle_note(lbl)).grid(
                    row=row, column=index % _NOTE_COLUMNS, sticky="w", padx=(8, 16))
            row += 1
        rows = [row]

        for column in range(_NOTE_COLUMNS):
            self.notes_frame.columnconfigure(column, weight=1)

        # The `Bu ay ayrıca: …` line that used to sit here is gone: every note it named
        # is now a checkbox above it, so it would be describing the panel it is in.
        tk.Frame(self.notes_frame, background=w.CARD, height=8).grid(
            row=max(rows), column=0, columnspan=_NOTE_COLUMNS, sticky="ew")

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
            # No address is a fact about the row, not a reason to hide it. Eleven of
            # May's people are leavers the roster no longer carries an address for.
            # The person's days that lost time. NOT the ticked set and not the filter:
            # *"bir insanın kaç günü sayılmamışsa o kadar sorunlu günü görünmeli
            # filtreden bağımsız"* (ADR-074). It was 446 across July with the default
            # ticks — 27 of them days that were counted in full — and 127 with one note
            # ticked. The truth is 419 and it does not move.
            gun = len(recipients.days_by_cost(person)[0])
            row = self.tree.insert(
                "", "end", tags=() if person.email else ("adres-yok",),
                values=(self._glyph(person.name), person.name, person.hours_text,
                        gun or "",
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
