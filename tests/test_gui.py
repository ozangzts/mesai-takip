"""What the window decides, not how it draws.

The window is a thin shell over `pipeline.run()` by design, so the parts worth testing
are the ones that decide what it tells the user: which files it found, which month it
understood, and what it remembers between runs. No test asserts a colour or a
geometry — that would be testing tkinter.

`inspect_sources` is the one that earns its keep. The user picks a folder by hand, and
what they need to know — before pressing anything — is which of the three exports were
found. Reporting only the first failure would hide the other two, and it is the
per-source answer that lets the window offer to go and find a missing one.

The last group does build a real `Tk`, because "a fresh window pre-selects nothing" is
only true if the constructor really runs. It skips itself when there is no display.
"""

import json
import time
from pathlib import Path

import tkinter as tk_module

import pytest

from mesai import gui
from mesai import snapshot as snapshot_module
from mesai.gui import app as app_module, places, rapor, widgets
from mesai.mail import recipients
from mesai import gui as _gui_pkg  # noqa: F401  (gui.rapor attribute access)


# Test windows are parked far off the visible desktop. A full run builds and destroys
# well over a hundred real windows, and they flashed in front of whatever the developer
# was doing for the whole thirty seconds. Position only — every geometry assertion here
# is about size, and `wm geometry WxH` leaves the position alone, so nothing measured
# changes. Not `withdraw()`: an unmapped window reports a size of 1x1 and the window
# tests would stop testing anything.
_OFFSCREEN = "+6000+6000"


def _tk_root(tk):
    """A Tk root, skipping only when there is genuinely no display.

    Both window fixtures used to read any `TclError` as "headless" and skip. That is
    wrong for a *transient* failure, and transient failures happen: a full run
    occasionally lost one window test this way, at a different test each time, and it
    did so before any of these tests existed. A test that silently skips has stopped
    protecting anything, which is the same objection as ADR-020's — a check that
    quietly does not run is worse than no check.

    So whether a display exists is decided once, by probe. After that, creating a
    window is retried a couple of times and then allowed to fail: a red run is the
    correct outcome for something that should have worked.
    """
    global _HAS_DISPLAY
    if _HAS_DISPLAY is None:
        try:
            probe = tk.Tk()
        except tk.TclError:
            _HAS_DISPLAY = False
        else:
            probe.destroy()
            _HAS_DISPLAY = True
    if not _HAS_DISPLAY:
        pytest.skip("no display")
    for remaining in (2, 1, 0):
        try:
            root = tk.Tk()
        except tk.TclError:
            if not remaining:
                raise
            time.sleep(0.2)
        else:
            root.geometry(_OFFSCREEN)
            return root


def _touch(folder: Path, *names: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")


_HAS_DISPLAY: bool | None = None

COMPLETE = (
    "Macunköy Temmuz Mesai giriş-çıkış.xls",
    "Teknopark - Temmuz Mesai Takip Exceli.xlsx",
    "HCMT34_TEMMUZ_IZIN.xlsx",
)


# --- folder validation ------------------------------------------------------

def _states(folder, settings, chosen=None):
    return gui.inspect_sources(folder, settings, chosen)


def test_a_complete_folder_is_usable(tmp_path, settings):
    _touch(tmp_path, *COMPLETE)
    states = _states(tmp_path, settings)

    assert len(states) == 3
    assert all(state.ready for state in states)
    assert all(not state.chosen for state in states)


def test_mixed_containers_are_all_accepted(tmp_path, settings):
    """July arrived as .xls, May as .xlsx — the window must accept either."""
    _touch(tmp_path, "Macunkoy Mayis Mesai giris-cikis.xlsx",
           "Teknopark - Mayis Mesai Takip Exceli.xls", "HCMT34_MAYIS_IZIN.xlsm")
    assert all(state.ready for state in _states(tmp_path, settings))


def test_every_missing_source_is_named_not_just_the_first(tmp_path, settings):
    _touch(tmp_path, "Teknopark - Temmuz Mesai Takip Exceli.xlsx")
    missing = [state for state in _states(tmp_path, settings) if not state.ready]

    assert len(missing) == 2, "both absent files must be listed"
    assert {state.label for state in missing} == {"Macunköy", "İzin"}
    assert all("bulunamadı" in state.note for state in missing)


def test_two_files_for_one_source_is_refused(tmp_path, settings):
    """Two months in one folder is the ADR-014 mistake; catch it before the run."""
    _touch(tmp_path, *COMPLETE, "Macunköy Haziran Mesai giriş-çıkış.xlsx")
    states = {state.key: state for state in _states(tmp_path, settings)}

    assert not states["macunkoy"].ready
    assert "2 dosya eşleşti" in states["macunkoy"].note
    assert states["teknopark"].ready, "the other two are unaffected"


def test_an_unset_or_missing_folder_leaves_every_source_unresolved(tmp_path, settings):
    assert all(not state.ready for state in _states(None, settings))
    assert all(not state.ready for state in _states(tmp_path / "olmayan", settings))


def test_the_folder_report_never_leaks_a_full_path(tmp_path, settings):
    """Only file names — a folder note showing full paths gets unreadable fast."""
    _touch(tmp_path, *COMPLETE)
    assert not any(str(tmp_path) in state.note for state in _states(tmp_path, settings))


# --- naming one export outright ---------------------------------------------
#
# The three exports do not always arrive in the same place. Rather than make someone
# copy files into one folder before every run — a step that eventually gets done wrong —
# a source that is not where the others are can be named on its own.

def test_a_hand_picked_file_resolves_a_source_the_folder_lacks(tmp_path, settings):
    folder = tmp_path / "07 - 2026"
    _touch(folder, "Macunköy Temmuz Mesai giriş-çıkış.xls",
           "Teknopark - Temmuz Mesai Takip Exceli.xlsx")
    elsewhere = tmp_path / "posta"
    _touch(elsewhere, "HCMT34_TEMMUZ_IZIN.xlsx")

    states = {s.key: s for s in _states(folder, settings,
                                        {"izin": elsewhere / "HCMT34_TEMMUZ_IZIN.xlsx"})}

    assert all(state.ready for state in states.values())
    assert states["izin"].chosen and not states["izin"].mismatch
    assert states["izin"].path.parent == elsewhere
    assert not states["macunkoy"].chosen, "the folder still answers for the others"


def test_a_hand_picked_file_also_settles_an_ambiguous_folder(tmp_path, settings):
    """Two months in one folder: naming one is a legitimate answer, not only an error."""
    _touch(tmp_path, *COMPLETE, "Macunköy Haziran Mesai giriş-çıkış.xlsx")
    chosen = {"macunkoy": tmp_path / "Macunköy Temmuz Mesai giriş-çıkış.xls"}
    states = {s.key: s for s in _states(tmp_path, settings, chosen)}

    assert states["macunkoy"].ready and states["macunkoy"].chosen


def test_a_hand_picked_file_that_vanished_is_reported_not_used(tmp_path, settings):
    states = {s.key: s for s in _states(tmp_path, settings,
                                        {"izin": tmp_path / "yok.xlsx"})}

    assert not states["izin"].ready
    assert "artık yok" in states["izin"].note


def test_an_odd_name_is_flagged_but_still_used(tmp_path, settings):
    """The patterns are a convention, not a rule — a renamed export is still that export.

    Refusing it would make the escape hatch useless in the one case it is for. The
    reader validates the layout, so a genuinely wrong file still fails loudly.
    """
    odd = tmp_path / "gecen ay.xlsx"
    odd.write_bytes(b"")
    states = {s.key: s for s in _states(tmp_path, settings, {"izin": odd})}

    assert states["izin"].ready, "it must still be usable"
    assert states["izin"].mismatch, "and it must say the name looks wrong"


# --- period parsing ---------------------------------------------------------
#
# Real folders are not named the way the tool would prefer. `06-2026` turned up in use
# and was rejected outright, which meant the period field could not be filled at all.

@pytest.mark.parametrize("text", [
    "2026-07", "2026-7", "2026_07", "2026.07", "2026/07", "2026 07", "202607",
    "07-2026", "7-2026", "07_2026", "07.2026", "07/2026", "07 2026", "072026",
    "Temmuz 2026", "2026 Temmuz", "TEMMUZ-2026", "temmuz2026",
    "Mesai 2026-07 Girdi", "IK 07-2026 dosyalar", "Temmuz 2026 puantaj",
])
def test_every_plausible_spelling_of_july_2026_is_understood(text):
    assert gui.parse_period(text) == "2026-07"


def test_turkish_month_names_fold_correctly(tmp_path):
    """`MAYIS` and `Mayıs` must both resolve — bare .upper() gets this wrong."""
    assert gui.parse_period("Mayıs 2026") == "2026-05"
    assert gui.parse_period("MAYIS 2026") == "2026-05"
    assert gui.parse_period("mayis 2026") == "2026-05"
    assert gui.parse_period("Ağustos 2026") == "2026-08"


@pytest.mark.parametrize("text, why", [
    ("03-04", "no four-digit year: March 2004 or April 2003?"),
    ("2026", "no month"),
    ("Temmuz", "no year"),
    ("2026-13", "month out of range"),
    ("2026-00", "month out of range"),
    ("13-2026", "month out of range"),
    ("1999-07", "year below the plausible range"),
    ("2100-07", "year above the plausible range"),
    ("2026-2027", "two years, no month"),
    ("Mesai", "nothing numeric"),
    ("", "empty"),
])
def test_an_ambiguous_or_impossible_period_is_refused(text, why):
    """Refusing is the point: a silent wrong guess is the failure mode to avoid."""
    assert gui.parse_period(text) is None, why


def test_the_period_is_read_off_the_folder_name(tmp_path):
    assert gui.guess_period(Path("data/raw/2026-07")) == "2026-07"
    assert gui.guess_period(Path("G:/IK/Mesai/06-2026")) == "2026-06"
    assert gui.guess_period(Path("G:/IK/Mesai/Temmuz 2026")) == "2026-07"


def test_the_parent_folder_is_the_fallback(tmp_path):
    assert gui.guess_period(Path("data/raw/2026-05/girdi")) == "2026-05"


def test_an_unrecognisable_folder_yields_no_guess(tmp_path):
    """Better to leave the field empty than to guess wrong — the user cannot tell."""
    assert gui.guess_period(Path("C:/Temp/Mesai")) is None
    assert gui.guess_period(Path("data/raw/2026-13")) is None, "month out of range"
    assert gui.guess_period(Path("data/raw/26-07")) is None, "year not four digits"


def test_a_canonical_period_survives_reparsing(tmp_path):
    """The field is rewritten with the parsed value, so parsing must be idempotent."""
    for text in ("06-2026", "Temmuz 2026", "202612", "2026-1"):
        once = gui.parse_period(text)
        assert once is not None
        assert gui.parse_period(once) == once


# --- labels -----------------------------------------------------------------

def test_the_period_label_is_turkish(tmp_path):
    assert gui.period_label("2026-07") == "Temmuz 2026"
    assert gui.period_label("2026-01") == "Ocak 2026"
    assert gui.period_label("2026-12") == "Aralık 2026"


# --- what is remembered between runs ----------------------------------------
#
# The window used to restore the last chosen folder. That was wrong for a specific
# reason: the input folder is month-specific (`07 - 2026`), so from the second month
# onwards the restored value pointed at a month already done — and filled the period
# field with it, ready to run. Only the browse starting point is kept now.

@pytest.fixture
def screen(tmp_path):
    """A real report screen inside a real window, rooted in tmp_path.

    `base` is what decides where `arayuz-ayarlari.json` is read from and written to,
    so pointing it at tmp_path is what keeps the developer's own settings file out of
    the test. The whole `App` is built rather than the screen alone: the constructor
    is the thing under test as much as the screen is.
    """
    tk = pytest.importorskip("tkinter")
    root = _tk_root(tk)

    def build(settings_payload=None):
        if settings_payload is not None:
            (tmp_path / "arayuz-ayarlari.json").write_text(
                json.dumps(settings_payload), encoding="utf-8")
        return gui.App(root, config_dir=Path("config"),
                       roster_dir=Path("data/personel"), base=tmp_path).report

    yield build
    try:
        root.destroy()
    except tk_module.TclError:   # a test closed the window itself
        pass


def test_a_fresh_window_selects_nothing(screen):
    window = screen()

    assert window.folder is None
    assert window.folder_var.get() == ""
    assert window.period_var.get() == ""
    assert str(window.run_button.cget("state")) == "disabled"
    assert "Gözat" in " ".join(window.note_lines)


def test_the_empty_period_field_says_what_may_be_typed(screen):
    """The hint is written for the empty state, so it must show in the empty state.

    It did not: the caption was only ever written by the field's write trace, which
    never fires on a fresh window. The field sat empty next to an empty caption.
    """
    window = screen()

    assert "2026-07" in window.period_note.cget("text")


def test_the_browse_location_is_remembered_but_nothing_is_selected(screen, tmp_path):
    share = tmp_path / "MESAI TAKIP"
    (share / "07 - 2026").mkdir(parents=True)
    window = screen({"browse_dir": str(share)})

    assert window.browse_dir == share, "browsing should start where it left off"
    assert window.folder is None, "but nothing may be pre-selected"
    assert window.period_var.get() == ""


def test_the_old_settings_format_is_migrated_to_its_parent(screen, tmp_path):
    """Upgrading must not resurrect the stale behaviour, nor lose the location."""
    share = tmp_path / "MESAI TAKIP"
    month = share / "07 - 2026"
    month.mkdir(parents=True)
    window = screen({"folder": str(month)})

    assert window.browse_dir == share
    assert window.folder is None
    assert window.period_var.get() == "", "the stale month must not be pre-filled"


def test_a_vanished_browse_location_is_simply_ignored(screen, tmp_path):
    """An unmounted network drive must not break startup."""
    window = screen({"browse_dir": str(tmp_path / "Z-yok")})

    assert window.browse_dir is None
    assert window.folder is None


def test_remembering_stores_the_parent_not_the_selection(screen, tmp_path):
    share = tmp_path / "MESAI TAKIP"
    month = share / "07 - 2026"
    month.mkdir(parents=True)
    window = screen()
    window.folder = month
    window._remember()

    saved = json.loads((tmp_path / "arayuz-ayarlari.json").read_text(encoding="utf-8"))
    assert saved["browse_dir"] == str(share)
    assert "07 - 2026" not in saved["browse_dir"], "month must not be stored"


# --- navigation -------------------------------------------------------------
#
# The rail exists so that a second work face — mail, then choosing people — is an
# entry in `SCREENS` and nothing else. These tests are the claim: they register a
# fake screen the way a real one would be registered, and assert the shell handles it
# without the shell or the report screen knowing anything about it.

@pytest.fixture
def shell(tmp_path):
    """Builds an `App` on a real Tk, optionally with extra screens registered."""
    tk = pytest.importorskip("tkinter")
    root = _tk_root(tk)

    built: list[str] = []

    def build(extra=()):
        return gui.App(root, config_dir=Path("config"),
                       roster_dir=Path("data/personel"), base=tmp_path,
                       screens=app_module.SCREENS + tuple(extra))

    def fake(key, label="Sahte"):
        def make(parent, _shell):
            built.append(key)
            return type("FakeScreen", (), {"frame": tk.Frame(parent)})()
        return app_module.Screen(key, label, make)

    build.fake = fake
    build.built = built
    yield build
    try:
        root.destroy()
    except tk_module.TclError:   # a test closed the window itself
        pass


def test_the_registered_screen_keys_are_unique():
    """A duplicate key would make `show()` reach a screen nobody can navigate to."""
    keys = [entry.key for entry in app_module.SCREENS]
    assert len(keys) == len(set(keys))


def test_the_first_registered_screen_is_the_one_shown(shell):
    window = shell()

    assert window._showing == app_module.SCREENS[0].key
    assert window.report.frame.winfo_manager() == "grid"


def test_a_second_screen_is_built_only_when_first_opened(shell):
    """Lazy on purpose: the mail screen needs a snapshot it should not load unasked."""
    window = shell(extra=[shell.fake("sahte")])
    assert shell.built == [], "registering must not build"

    window.show("sahte")
    assert shell.built == ["sahte"]

    window.show(app_module.SCREENS[0].key)
    window.show("sahte")
    assert shell.built == ["sahte"], "a screen is built at most once"


def test_switching_away_and_back_keeps_what_was_typed(shell):
    """grid_remove, not grid_forget — losing a chosen folder on a tab switch is a bug."""
    window = shell(extra=[shell.fake("sahte")])
    window.report.period_var.set("2026-07")

    window.show("sahte")
    assert window.report.frame.winfo_manager() == "", "the report must be hidden"

    window.show("rapor")
    assert window.report.period_var.get() == "2026-07"
    assert window.report.frame.winfo_manager() == "grid"


def test_an_unregistered_screen_key_fails_loudly(shell):
    window = shell()
    with pytest.raises(KeyError):
        window.show("yok-boyle-bir-ekran")


# --- what the untouched window looks like -----------------------------------
#
# A window nobody has touched yet must not look like something already went wrong,
# and must not look like a job already part-done. Both were true at one point.

def test_nothing_chosen_yet_is_not_painted_as_a_problem(screen):
    """Red is for problems. 'You have not picked a folder' is where every run starts."""
    window = screen()
    labels = window.folder_note.winfo_children()

    assert labels, "the starting instruction must be shown"
    assert all(str(label.cget("foreground")) != widgets.BAD for label in labels)


def test_found_and_missing_sources_are_coloured_separately(screen, tmp_path, settings):
    """Two of three found: the two that were found must not be painted as failures."""
    folder = tmp_path / "07 - 2026"
    _touch(folder, "Teknopark - Temmuz Mesai Takip Exceli.xlsx",
           "HCMT34_TEMMUZ_IZIN.xlsx")
    window = screen()
    window._write_sources(gui.inspect_sources(folder, settings))

    marks = [child for child in window.folder_note.winfo_children()
             if str(child.cget("text")) in ("✓", "✗")]
    colours = [str(child.cget("foreground")) for child in marks]
    assert colours.count(widgets.OK) == 2, "both found files keep the found colour"
    assert colours.count(widgets.BAD) == 1, "only the missing one is a problem"


def test_only_an_unresolved_source_is_offered_a_button(screen, tmp_path, settings):
    """A file found where it was expected needs nothing; a missing one needs a way out."""
    folder = tmp_path / "07 - 2026"
    _touch(folder, "Teknopark - Temmuz Mesai Takip Exceli.xlsx",
           "HCMT34_TEMMUZ_IZIN.xlsx")
    window = screen()
    window._write_sources(gui.inspect_sources(folder, settings))

    buttons = [child for child in window.folder_note.winfo_children()
               if isinstance(child, tk_module.Button)]
    assert len(buttons) == 1, "one missing source, one button"
    assert str(buttons[0].cget("text")) == "Seç…"


def test_a_hand_picked_source_is_offered_a_way_back(screen, tmp_path, settings):
    _touch(tmp_path, *COMPLETE)
    window = screen()
    window._write_sources(gui.inspect_sources(
        tmp_path, settings, {"izin": tmp_path / "HCMT34_TEMMUZ_IZIN.xlsx"}))

    labels = [str(child.cget("text")) for child in window.folder_note.winfo_children()]
    assert any("Geri al" in text for text in labels)
    assert any("elle seçildi" in text for text in labels)


def test_changing_the_folder_forgets_hand_picked_files(screen, tmp_path):
    """They belonged to the old month. Carrying them over would mix two periods."""
    first = tmp_path / "06 - 2026"
    second = tmp_path / "07 - 2026"
    first.mkdir()
    second.mkdir()
    window = screen()
    window._set_folder(first)
    window.chosen["izin"] = tmp_path / "haziran-izin.xlsx"

    window._set_folder(second)
    assert window.chosen == {}


def test_the_activity_bar_shows_nothing_before_a_run(screen):
    """It used to draw a stub of filled bar, reading as 'a little bit done already'."""
    window = screen()
    bar = window.progress

    assert bar.canvas.coords(bar._bar) == [0.0, 0.0, 0.0, 0.0]


def test_the_result_card_says_what_to_do_instead_of_sitting_empty(screen):
    window = screen()
    shown = window.result.get("1.0", "end")

    assert "Gözat" in shown and "Rapor Oluştur" in shown
    assert "RAPOR DOSYASI" not in shown, "no output path before a run has produced one"


def test_starting_a_run_shows_the_activity_bar(screen, tmp_path):
    """Covers the call site, not just the widget.

    The bar was swapped for one with a different `start()` signature and nothing
    noticed, because no test had ever pressed the button. The run itself fails here —
    no folder is chosen — but it fails on the worker thread, after the bar is up.
    """
    window = screen()
    window.period_var.set("2026-07")
    window._start()

    left, _top, right, _bottom = window.progress.canvas.coords(window.progress._bar)
    assert right > left, "the bar must be drawn once a run has started"

    window.progress.stop()
    assert window.progress.canvas.coords(window.progress._bar) == [0.0, 0.0, 0.0, 0.0]


def test_the_summary_figures_are_drawn_in_a_fixed_width_font(screen):
    """They are aligned with spaces, so a proportional font leaves the colons ragged."""
    window = screen()
    window._render(rapor.Result(
        True, "Mayıs 2026 raporu yazıldı", (), widgets.OK,
        figures=("Raporda yer alan kişi : 171", "Kişi-gün kaydı        : 1823")))

    assert window.result.tag_ranges("figure"), "the figures must carry the mono tag"
    assert str(window.result.tag_cget("figure", "font")).startswith(widgets.MONO)


def test_a_long_result_can_be_scrolled_to_the_end(screen, tmp_path):
    """The snapshot path is the last thing written and used to be clipped away."""
    window = screen()
    window._render(rapor.Result(
        True, "Temmuz 2026 raporu yazıldı — EKSİK",
        tuple(f"satır {n}" for n in range(40)), widgets.WARN,
        output=tmp_path / "rapor.xlsx", snapshot=tmp_path / "veri.json"))
    window.root.update()

    assert window.result.yview()[1] < 1.0, "this much text must not fit"
    assert window._scroll.winfo_manager() == "grid", "so the scrollbar must appear"

    window.result.yview_moveto(1.0)
    assert window.result.yview()[1] == 1.0, "the end must be reachable"


def test_a_short_result_hides_the_scrollbar(screen):
    window = screen()
    window.root.update()

    assert window._scroll.winfo_manager() == "", "nothing out of view, nothing to show"


# --- naming a file from another month (ADR-023) -----------------------------
#
# The hard guard is in the pipeline: a source whose every record falls outside the
# month fails the run, because a report 72 % short that looks normal is worse than no
# report. What the window adds is noticing earlier, from the file NAME, so the warning
# arrives before the button rather than after it. It decides nothing.

@pytest.mark.parametrize("name, expected", [
    ("Macunköy Mayıs Mesai giriş-çıkış.xlsx", "Mayıs"),
    ("Teknopark - Haziran Mesai Takip Exceli.xlsx", "Haziran"),
    ("HCMT34_TEMMUZ_IZIN.xlsx", "Temmuz"),
    ("hcmt34_mayis_izin.xlsx", "Mayıs"),
    ("rapor.xlsx", ""),
    ("Mayıs ve Haziran birlesik.xlsx", ""),
])
def test_the_month_named_in_a_file_name_is_read_or_left_alone(name, expected):
    """Two months named means neither can be trusted, so it says nothing."""
    assert gui.rapor.month_in_name(name) == expected


def test_a_file_naming_another_month_is_flagged_but_still_usable(tmp_path, settings):
    _touch(tmp_path, "Macunköy Mayıs Mesai giriş-çıkış.xlsx",
           "Teknopark - Haziran Mesai Takip Exceli.xlsx",
           "HCMT34_MAYIS_IZIN.xlsx")
    states = {s.key: s for s in gui.inspect_sources(tmp_path, settings,
                                                    period="2026-05")}

    assert states["teknopark"].other_month == "Haziran"
    assert states["teknopark"].suspect, "worth a second look"
    assert states["teknopark"].ready, "but the dates inside decide, not the name"
    assert not states["macunkoy"].other_month
    assert not states["macunkoy"].suspect


def test_without_a_period_no_month_warning_is_possible(tmp_path, settings):
    """Nothing to compare against — it must not invent one."""
    _touch(tmp_path, "Teknopark - Haziran Mesai Takip Exceli.xlsx")
    states = {s.key: s for s in gui.inspect_sources(tmp_path, settings)}

    assert states["teknopark"].other_month == ""


def test_the_month_warning_is_painted_as_a_caution_not_a_failure(screen, tmp_path,
                                                                 settings):
    """It is still usable, so it must not wear the colour of a missing file."""
    _touch(tmp_path, "Macunköy Mayıs Mesai giriş-çıkış.xlsx",
           "Teknopark - Haziran Mesai Takip Exceli.xlsx",
           "HCMT34_MAYIS_IZIN.xlsx")
    window = screen()
    window._write_sources(gui.inspect_sources(tmp_path, settings, period="2026-05"))

    colours = [str(child.cget("foreground"))
               for child in window.folder_note.winfo_children()
               if str(child.cget("text")) in ("✓", "✗")]
    assert colours.count(widgets.WARN) == 1
    assert colours.count(widgets.OK) == 2
    assert widgets.BAD not in colours, "nothing here is missing"

    notes = [str(child.cget("text")) for child in window.folder_note.winfo_children()]
    assert any("adında Haziran geçiyor" in text for text in notes), "and it says why"


# --- where the report is written (ADR-024) ----------------------------------
#
# The output folder is remembered outright while the INPUT folder deliberately is not,
# and the difference is the whole point: the month lives in the subfolder this makes,
# so last month's output choice is still right this month. Restoring the input folder
# offers a stale month ready to run; restoring this one offers the place reports go.

def test_the_output_folder_defaults_to_the_desktop(screen):
    window = screen()

    assert window.output_dir == places.desktop_dir()
    assert window.output_var.get() == str(places.desktop_dir())


def test_a_remembered_output_folder_is_restored(screen, tmp_path):
    kept = tmp_path / "Raporlar"
    kept.mkdir()
    window = screen({"output_dir": str(kept)})

    assert window.output_dir == kept


def test_a_vanished_output_folder_falls_back_to_the_desktop(screen, tmp_path):
    """An unmounted drive must not stop the run — and the field shows the fallback."""
    window = screen({"output_dir": str(tmp_path / "Z-yok")})

    assert window.output_dir == places.desktop_dir()
    assert window.output_var.get() == str(places.desktop_dir())


def test_changing_the_output_folder_is_saved_without_losing_the_browse_location(
        screen, tmp_path):
    """Two keys, one file. Writing one used to mean writing the whole object."""
    share = tmp_path / "MESAI TAKIP"
    month = share / "07 - 2026"
    month.mkdir(parents=True)
    kept = tmp_path / "Raporlar"
    kept.mkdir()

    window = screen()
    window.folder = month
    window._remember()
    window.output_dir = kept
    window._save()

    saved = json.loads((tmp_path / "arayuz-ayarlari.json").read_text(encoding="utf-8"))
    assert saved == {"output_dir": str(kept), "browse_dir": str(share)}


def test_the_folder_name_puts_the_month_first_and_says_what_it_is():
    assert places.report_folder_name("2026-06") == "2026-06 Rapor"
    assert places.report_folder_name("2026-12") == "2026-12 Rapor"


def test_the_workbook_and_its_snapshot_land_in_the_same_folder(tmp_path):
    """One run, one folder. They used to be written to two unrelated places."""
    workbook, data = places.report_paths(tmp_path, "2026-06")

    assert workbook.parent == data.parent == tmp_path / "2026-06 Rapor"
    assert workbook.name == "mesai-raporu-2026-06.xlsx"
    assert data.name == "gonderim-2026-06.json"


def test_the_snapshot_default_follows_its_workbook(tmp_path):
    """Wherever the workbook was pointed, including a path the CLI was handed."""
    workbook = tmp_path / "baska" / "yer" / "rapor.xlsx"
    assert snapshot_module.default_path("2026-06", workbook) == \
        workbook.parent / "gonderim-2026-06.json"


def test_the_window_names_the_folder_it_will_create(screen):
    """It creates a subfolder rather than writing into the chosen one; say so."""
    window = screen()
    window.period_var.set("2026-06")

    assert "2026-06 Rapor" in window.output_note.cget("text")


def test_before_a_period_is_known_no_folder_name_is_invented(screen):
    window = screen()

    assert "Rapor" not in window.output_note.cget("text").split("klasör")[0]
    assert "Dönem" in window.output_note.cget("text")


def test_the_snapshot_caption_no_longer_speaks_for_hr(screen, tmp_path):
    """Whether HR needs to open it is not this line's business — it says what it is."""
    window = screen()
    window._render(rapor.Result(
        True, "bitti", (), widgets.OK,
        output=tmp_path / "r.xlsx", snapshot=tmp_path / "v.json"))
    shown = window.result.get("1.0", "end")

    assert "e-posta adımı bunu okuyacak" in shown
    assert "İK" not in shown


def test_an_existing_report_for_the_month_is_announced_before_the_button(screen,
                                                                        tmp_path):
    """A rerun overwrites in place, so it is said beforehand rather than discovered."""
    window = screen()
    window.output_dir = tmp_path
    window.period_var.set("2026-06")
    assert "oluşturacak" in window.output_note.cget("text")
    assert str(window.output_note.cget("foreground")) != widgets.WARN

    workbook, _data = places.report_paths(tmp_path, "2026-06")
    workbook.parent.mkdir(parents=True)
    workbook.write_bytes(b"gecen kosu")
    window._show_output()

    assert "üzerine yazılacak" in window.output_note.cget("text")
    assert str(window.output_note.cget("foreground")) == widgets.WARN


def test_the_month_folders_sort_into_date_order(tmp_path):
    """Year first. Month first put January 2027 above May 2026."""
    names = sorted(places.report_folder_name(p)
                   for p in ("2026-05", "2026-12", "2027-01"))
    assert names == ["2026-05 Rapor", "2026-12 Rapor", "2027-01 Rapor"]


# --- the people screen (ADR-028) --------------------------------------------
#
# The rule lives in mail/recipients.py and is tested there. What is tested here is the
# wiring: that a run hands its data file over, that the dropdown reflects the file, and
# that a tick actually removes somebody.

def _snapshot_file(tmp_path, people, *, partial=False):
    import json
    payload = {
        "format_version": snapshot_module.FORMAT_VERSION,
        "period": "2026-05",
        "generated_at": "2026-08-19T10:00:00",
        "rules": {},
        "coverage": {"macunkoy": {"partial": partial,
                                  "missing_from": "2026-05-20" if partial else None}},
        "people": people,
    }
    path = tmp_path / "gonderim-2026-05.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _person(name, problems=(), expected=(), email="a@b.c"):
    return {"name": name, "email": email, "personnel_no": None, "department": None,
            "facility": None, "in_roster": True, "has_attendance": True,
            "worked_days": 20, "minutes": 480, "remote_days": 0.0, "leave_days": 0.0,
            "problems": list(problems), "expected": list(expected), "notes": []}


@pytest.fixture
def people_screen(shell, tmp_path):
    window = shell()
    window.show("kisiler")
    return window


def test_the_people_screen_starts_empty_and_says_what_to_do(people_screen):
    screen = people_screen._screens["kisiler"]

    assert screen.snapshot is None
    assert recipients.choices(None) == ()
    assert "Rapor oluşturduktan sonra" in str(screen.empty_note.cget("text"))
    assert screen.empty_note.winfo_manager() == "grid", "and it must be showing"
    assert screen.tree.winfo_manager() == "", "with the list out of the way"


def test_a_finished_run_hands_its_data_file_over(shell, tmp_path):
    """The usual path involves choosing nothing — the report screen passes the path."""
    path = _snapshot_file(tmp_path, [_person("AYŞE DENEME", ["Çıkış yok"])])
    window = shell()
    window.snapshot_ready(path)
    window.show("kisiler")
    screen = window._screens["kisiler"]

    assert screen.source == path
    assert [p.name for p in recipients.matching(screen.snapshot, recipients.ALL)] == \
        ["AYŞE DENEME"]


def test_the_dropdown_is_built_from_the_loaded_file(people_screen, tmp_path):
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME", ["Çıkış yok"]),
        _person("BERK NUMUNE", ["Çıkış yok"]),
        _person("CEM ÖRNEK", [], ["Uzaktan + sistem kaydı"]),
    ]))

    shown = list(screen.filter_box.cget("values"))
    assert any("Herkes  (3)" == s for s in shown)
    assert any("Çıkış yok  (2)" == s for s in shown)
    assert any(s.startswith("Uzaktan + sistem kaydı  (1)") for s in shown)
    assert any("beklenen durum" in s for s in shown), "and it says it is not a problem"


def test_choosing_a_filter_narrows_the_list(people_screen, tmp_path):
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME", ["Çıkış yok"]),
        _person("BERK NUMUNE", []),
    ]))
    screen.filter_var.set("Çıkış yok  (1)")
    screen._filter_changed()

    assert screen.filter_key == "Çıkış yok"
    assert [name for name, _var in screen._rows] == ["AYŞE DENEME"]


def test_unticking_someone_removes_them_from_the_selection(people_screen, tmp_path):
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME"), _person("BERK NUMUNE")]))

    name, row = screen._rows[0]
    screen._toggle(name)

    chosen = recipients.selected(screen.snapshot, screen.filter_key, screen.excluded)
    assert [p.name for p in chosen] == ["BERK NUMUNE"]
    assert "1 / 2 kişi seçili" in screen.count_label.cget("text")
    assert screen.tree.set(row, "tik") == "☐", "and the glyph must say so"

    screen._toggle(name)
    assert screen.tree.set(row, "tik") == "☑", "clicking again puts them back"


def test_changing_the_filter_forgets_removals(people_screen, tmp_path):
    """They belonged to the group they were made in."""
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [_person("AYŞE DENEME", ["Çıkış yok"])]))
    screen.excluded.add("AYŞE DENEME")
    screen.filter_var.set("Çıkış yok  (1)")
    screen._filter_changed()

    assert screen.excluded == set()


def test_a_person_without_an_address_is_shown_and_counted(people_screen, tmp_path):
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME", email=None), _person("BERK NUMUNE")]))

    assert "1 kişinin e-postası yok" in screen.count_label.cget("text")
    rows = {screen.tree.set(row, "ad"): row for _name, row in screen._rows}
    assert screen.tree.set(rows["AYŞE DENEME"], "eposta") == "e-posta yok"
    assert screen.tree.item(rows["AYŞE DENEME"], "tags") == ("adres-yok",), \
        "an address that is missing is the one thing on a row worth colouring"
    assert screen.tree.item(rows["BERK NUMUNE"], "tags") == ""


def test_an_incomplete_month_is_called_out_before_anyone_acts_on_it(people_screen,
                                                                   tmp_path):
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [_person("AYŞE DENEME")], partial=True))

    assert "BU AY EKSİK" in screen.source_note.cget("text")
    assert str(screen.source_note.cget("foreground")) == widgets.BAD


def test_a_data_file_from_an_older_version_is_refused_not_parsed(people_screen,
                                                                tmp_path):
    import json
    path = tmp_path / "gonderim-2026-05.json"
    path.write_text(json.dumps({"format_version": 1, "people": []}), encoding="utf-8")
    screen = people_screen._screens["kisiler"]
    screen.load(path)

    assert screen.snapshot is None
    assert str(screen.source_note.cget("foreground")) == widgets.BAD


# --- the fourth file (ADR-035) ----------------------------------------------
#
# The window listed three sources and enabled the button on them, but the run needs
# four. A missing roster surfaced only after pressing — the exact thing the pre-flight
# check exists to prevent.

def test_the_roster_is_checked_before_the_button_is_pressed(tmp_path, settings):
    empty = tmp_path / "personel"
    empty.mkdir()
    state = rapor.roster_state(empty, tmp_path / "07 - 2026", settings)

    assert not state.ready
    assert "bulunamadı" in state.note
    assert len(state.note) < 60, "the row sits beside three others; keep it short"


def test_a_roster_found_in_its_own_folder_is_reported(tmp_path, settings):
    home = tmp_path / "personel"
    _touch(home, "calisan_listesi.xlsx")
    state = rapor.roster_state(home, tmp_path / "07 - 2026", settings)

    assert state.ready and state.path.name == "calisan_listesi.xlsx"
    assert not state.chosen


def test_a_hand_picked_roster_wins(tmp_path, settings):
    """It is not month-specific, and a packaged program may have no data/personel/."""
    home = tmp_path / "personel"
    _touch(home, "calisan_listesi.xlsx")
    elsewhere = tmp_path / "masaustu"
    _touch(elsewhere, "IK listesi.xlsx")

    state = rapor.roster_state(home, None, settings,
                               elsewhere / "IK listesi.xlsx")
    assert state.ready and state.chosen
    assert state.path.parent == elsewhere


def test_the_run_button_stays_disabled_without_a_roster(screen, tmp_path):
    window = screen()
    window.roster_dir = tmp_path / "yok"
    _touch(tmp_path / "07 - 2026", *COMPLETE)
    window._set_folder(tmp_path / "07 - 2026")

    assert str(window.run_button.cget("state")) == "disabled"
    assert any("Personel listesi" in line for line in window.note_lines)


def test_naming_a_roster_completes_the_set(screen, tmp_path):
    window = screen()
    window.roster_dir = tmp_path / "yok"
    _touch(tmp_path / "07 - 2026", *COMPLETE)
    _touch(tmp_path / "ik", "calisan_listesi.xlsx")
    window._set_folder(tmp_path / "07 - 2026")

    window.roster_file = tmp_path / "ik" / "calisan_listesi.xlsx"
    window._describe()

    assert str(window.run_button.cget("state")) == "normal"


def test_changing_the_month_folder_keeps_the_roster(screen, tmp_path):
    """The three monthly picks belong to a month; this one belongs to the company."""
    window = screen()
    _touch(tmp_path / "ik", "calisan_listesi.xlsx")
    window.roster_file = tmp_path / "ik" / "calisan_listesi.xlsx"
    window.chosen["izin"] = tmp_path / "bir-yer" / "izin.xlsx"

    (tmp_path / "07 - 2026").mkdir()
    window._set_folder(tmp_path / "07 - 2026")

    assert window.chosen == {}, "monthly picks belong to the month they were made in"
    assert window.roster_file is not None, "the roster does not"


def test_the_run_is_handed_the_roster_it_was_shown(screen, tmp_path):
    window = screen()
    window.roster_file = tmp_path / "ik" / "calisan_listesi.xlsx"
    window.chosen["izin"] = tmp_path / "posta" / "izin.xlsx"

    assert window._run_sources() == {
        "izin": tmp_path / "posta" / "izin.xlsx",
        "roster": tmp_path / "ik" / "calisan_listesi.xlsx",
    }


def test_a_chosen_roster_is_remembered_between_sessions(screen, tmp_path):
    """Same reason the output folder is remembered and the input folder is not: this
    file is not month-specific. The same list serves every period."""
    _touch(tmp_path / "ik", "calisan_listesi.xlsx")
    chosen = tmp_path / "ik" / "calisan_listesi.xlsx"

    window = screen()
    window.roster_file = chosen
    window._save()

    saved = json.loads((tmp_path / "arayuz-ayarlari.json").read_text(encoding="utf-8"))
    assert saved["roster_file"] == str(chosen)

    reopened = screen()
    assert reopened.roster_file == chosen, "no need to pick it again"


def test_a_roster_that_moved_is_forgotten_rather_than_blocking(screen, tmp_path):
    """A remembered path that no longer exists must not lock the button forever."""
    window = screen({"roster_file": str(tmp_path / "gitti" / "liste.xlsx")})

    assert window.roster_file is None, "the normal lookup takes over"


def test_forgetting_a_roster_also_survives_a_restart(screen, tmp_path):
    _touch(tmp_path / "ik", "calisan_listesi.xlsx")
    window = screen()
    window.roster_file = tmp_path / "ik" / "calisan_listesi.xlsx"
    window._save()

    window._forget_source("roster")

    saved = json.loads((tmp_path / "arayuz-ayarlari.json").read_text(encoding="utf-8"))
    assert "roster_file" not in saved


def test_a_found_roster_can_still_be_changed(screen, tmp_path, settings):
    """It has no folder picker of its own, so "change the folder" is not an escape.

    Without this the only reachable roster is whichever one the lookup found, and a
    newer list sitting anywhere else could not be used at all.
    """
    home = tmp_path / "personel"
    _touch(home, "calisan_listesi.xlsx")
    window = screen()
    window.roster_dir = home
    window._describe()

    labels = [str(c.cget("text")) for c in window.folder_note.winfo_children()]
    assert "Değiştir…" in labels
    assert "Seç…" not in labels, "it was found; nothing is missing"


def test_a_found_monthly_source_still_offers_nothing(screen, tmp_path, settings):
    """The rule is unchanged for the three that do have a folder picker."""
    folder = tmp_path / "07 - 2026"
    _touch(folder, *COMPLETE)
    _touch(tmp_path / "personel", "calisan_listesi.xlsx")
    window = screen()
    window.roster_dir = tmp_path / "personel"
    window._set_folder(folder)

    buttons = [str(c.cget("text")) for c in window.folder_note.winfo_children()
               if isinstance(c, tk_module.Button)]
    assert buttons == ["Değiştir…"], "only the roster offers one when all four are found"


def test_the_roster_can_be_set_before_a_folder_is_chosen(screen, tmp_path):
    """It is not month-specific, so waiting for a month to be picked is an odd gate."""
    _touch(tmp_path / "personel", "calisan_listesi.xlsx")
    window = screen()
    window.roster_dir = tmp_path / "personel"
    window._describe()

    assert [s.key for s in window.states] == ["roster"]
    labels = [str(c.cget("text")) for c in window.folder_note.winfo_children()]
    assert "Değiştir…" in labels
    assert any("Gözat" in text for text in labels), "and the instruction still shows"
    assert str(window.run_button.cget("state")) == "disabled", "no folder, no run"


def test_settings_written_with_a_byte_order_mark_are_still_read(screen, tmp_path):
    """Notepad and PowerShell both add one, and the strict decoder rejects the file.

    The failure was silent and total: the output folder reverted to the Desktop, the
    remembered roster vanished, and nothing said why.
    """
    kept = tmp_path / "Raporlar"
    kept.mkdir()
    (tmp_path / "arayuz-ayarlari.json").write_text(
        json.dumps({"output_dir": str(kept)}), encoding="utf-8-sig")

    window = screen()
    assert window.output_dir == kept


# --- the window's size, and the list's scroll position ----------------------
#
# This file opens by saying no test asserts a geometry, because that would be testing
# tkinter. These do, and they are the exception that proves the rule: both were real
# bugs the operator hit, both are about state the window keeps rather than how it
# draws, and neither can be caught any other way. What is asserted is a relationship
# (the window did not get shorter; the first row is at the top of its viewport), never
# a pixel count.

@pytest.fixture
def people(shell):
    """The people screen of a real window, holding a synthetic month.

    Synthetic on purpose. A screenshot or a failure dump from this screen loaded with
    a real data file would carry employee names and e-mail addresses.
    """
    from datetime import datetime

    from mesai.snapshot import Person, Snapshot

    surnames = ("DENEME", "ÖRNEK", "NUMUNE", "TASLAK", "MİSAL", "SINAMA")

    def person(index, problems=()):
        return Person(
            name=f"KİŞİ{index:03d} {surnames[index % len(surnames)]}",
            email=f"k{index}@ornek.test", personnel_no=None, department=None,
            facility=None, in_roster=True, has_attendance=True, worked_days=20,
            minutes=9000 + index, remote_days=0.0, leave_days=0.0,
            problems=tuple(problems), expected=(), notes=())

    def build(clean=60, flagged=2):
        window = shell()
        window.show("kisiler")
        screen = window._screens["kisiler"]
        screen.snapshot = Snapshot(
            period="2026-07", generated_at=datetime(2026, 8, 20, 9, 0), rules={},
            coverage={"macunkoy": {"partial": False}},
            people=tuple([person(i) for i in range(clean)]
                         + [person(500 + i, ["Çıkış yok"]) for i in range(flagged)]))
        screen.filter_key = recipients.NO_PROBLEM
        screen._repaint()
        window.root.update()
        return window, screen

    return build


def _at_top(screen) -> bool:
    """Is the list showing its first row?

    Asked of the widget rather than of pixels now that the rows are a Treeview: it
    keeps its own scroll region, so "the top" is a fraction it reports itself.
    """
    return screen.tree.yview()[0] == 0.0


def test_switching_to_another_screen_never_shrinks_the_window(shell):
    """Tk shrink-wraps a toplevel to the requested size of whatever is showing.

    The two screens do not ask for the same height, so switching to `Kişiler` snapped
    the window down and switching back threw it up again — reported as the window
    being cropped from the bottom.
    """
    window = shell()
    window.root.update()
    tall = window.root.winfo_height()

    window.show("kisiler")
    window.root.update()
    assert window.root.winfo_height() >= tall, "the window got shorter"

    window.show("rapor")
    window.root.update()
    assert window.root.winfo_height() >= tall, "and it must not bounce back either"


def test_a_shorter_filter_starts_at_the_top_of_its_list(people):
    """The bug: 60 people, scrolled to the bottom, then a filter with 2.

    The canvas kept the old offset against a scrollregion 30 times shorter, leaving
    the view 972 px below the only two rows — an apparently empty list, with the
    scrollbar already hidden because the content now fits.
    """
    window, screen = people()
    screen.tree.yview_moveto(1.0)
    window.root.update()
    assert not _at_top(screen), "the setup must really be scrolled down"

    screen.filter_key = "Çıkış yok"
    screen._repaint()
    window.root.update()

    assert _at_top(screen), "the two rows must be at the top"
    assert screen.tree.yview() == (0.0, 1.0), "and nothing is out of view"
    assert screen._scroll.winfo_manager() == "", "so no scrollbar, which is right"


def test_a_longer_filter_also_starts_at_the_top(people):
    """The other direction: a list that no longer fits must still begin at its top."""
    window, screen = people()
    screen.filter_key = "Çıkış yok"
    screen._repaint()
    window.root.update()

    screen.filter_key = recipients.NO_PROBLEM
    screen._repaint()
    window.root.update()

    assert _at_top(screen)
    assert screen.tree.yview()[1] < 1.0, "60 rows must not fit"
    assert screen._scroll.winfo_manager() == "grid", "so the scrollbar comes back"


def test_the_list_keeps_its_place_when_only_the_ticks_change(people):
    """`Temizle` halfway down a long list must not throw the reader back to the top.

    This is why the reset is tied to the set of names shown rather than to repainting:
    the same people, re-ticked, is not a new list.
    """
    window, screen = people()
    screen.tree.yview_moveto(0.5)
    window.root.update()
    before = screen.tree.yview()

    screen._clear_all()
    window.root.update()

    assert screen.tree.yview() == before, "the view moved"
    assert all(screen.tree.set(row, "tik") == "☐" for _name, row in screen._rows), \
        "and it did clear them"


def test_an_emptied_list_cannot_stay_scrolled_into_nothing(people):
    """Loading a file whose filter matches nobody leaves no rows at all."""
    window, screen = people()
    screen.tree.yview_moveto(1.0)
    window.root.update()

    screen.snapshot = None
    screen._repaint()
    window.root.update()

    assert screen._rows == []
    assert screen.tree.winfo_manager() == "", "the list gives way to the note"
    assert screen.empty_note.winfo_manager() == "grid"


@pytest.mark.parametrize("focus_on", ["filter_box", "tree", "copy_button"])
def test_the_wheel_scrolls_the_list_wherever_the_focus_is(people, focus_on):
    """The reported bug: after choosing a filter the wheel did nothing over the list.

    Which widget a `<MouseWheel>` reaches depends on the tk build — focus on some, the
    window under the pointer on others — and the rows used to be labels that swallowed
    it either way. Parametrised over the three places the focus realistically sits, so
    the answer cannot be right for one of them and wrong for the others.
    """
    window, screen = people()
    target = getattr(screen, focus_on)
    screen._grab_wheel()                       # what entering the list does
    target.focus_set()
    window.root.update()
    assert _at_top(screen)

    target.event_generate("<MouseWheel>", delta=-120)
    window.root.update()

    assert not _at_top(screen), f"the wheel did nothing with the focus on {focus_on}"


def test_the_wheel_never_changes_the_filter(people):
    """ttk steps a combobox's value on every notch, and this box decides who is listed.

    Measured before the guard: two notches moved the filter from `Herkes` (43 people)
    to `Çıkış yok` (3), and each change drops the removals made by hand. A gesture
    whose effect depends on where the focus invisibly is does not belong here.
    """
    window, screen = people()
    screen._grab_wheel()
    screen.filter_box.focus_set()
    window.root.update()
    before = screen.filter_var.get()

    for _ in range(3):
        screen.filter_box.event_generate("<MouseWheel>", delta=-120)
        window.root.update()

    assert screen.filter_var.get() == before, "the filter moved under the wheel"
    assert not _at_top(screen), "and the list still scrolled"


def test_the_wheel_does_nothing_once_the_pointer_has_left_the_list(people):
    window, screen = people()
    screen._release_wheel()                    # what leaving the list does
    screen.filter_box.focus_set()
    window.root.update()
    before = screen.filter_var.get()

    screen.filter_box.event_generate("<MouseWheel>", delta=-120)
    window.root.update()

    assert _at_top(screen), "nothing outside the list may scroll it"
    assert screen.filter_var.get() == before


def test_the_wheel_binding_is_dropped_on_the_way_out(people):
    """It is bound on the `all` tag, so leaving the list has to undo it."""
    window, screen = people()
    screen._grab_wheel()
    assert screen.tree.bind_all("<MouseWheel>"), "bound while inside"

    screen._release_wheel()
    assert not screen.tree.bind_all("<MouseWheel>"), "and gone on the way out"


def test_one_wheel_notch_scrolls_more_than_one_row(people):
    """A row per notch is what made a 171-person list feel like it was not moving."""
    window, screen = people()
    window.root.update()
    screen._wheel(type("Wheel", (), {"delta": -120})())
    window.root.update()

    first_row_height = 1 / max(len(screen._rows), 1)
    assert screen.tree.yview()[0] > first_row_height, "one notch, one row"


def test_clicking_a_row_takes_that_person_out_and_back(people):
    """The whole row is the target, not a glyph a few pixels wide."""
    window, screen = people()
    name, row = screen._rows[0]
    window.root.update()

    y = screen.tree.bbox(row)[1] + 2
    screen._clicked(type("Click", (), {"y": y})())
    assert name in screen.excluded
    assert screen.tree.set(row, "tik") == "☐"

    screen._clicked(type("Click", (), {"y": y})())
    assert name not in screen.excluded


def test_clicking_below_the_last_row_changes_nothing(people):
    """There is no nearest person to guess at down there."""
    window, screen = people()
    screen.filter_key = "Çıkış yok"
    screen._repaint()
    window.root.update()

    screen._clicked(type("Click", (), {"y": screen.tree.winfo_height() - 4})())
    assert screen.excluded == set()


# --- the calendar screen (ADR-041) ------------------------------------------
#
# The screen is an editor for `config/takvim-<yıl>.yaml` and nothing else. That is the
# load-bearing part: a report whose figures depend on what was clicked in a dialog is
# not reproducible, so the answer has to reach a file before it reaches a calculation
# (AGENTS §2.1). Everything below is about the file, or about not marking a day nobody
# asked to mark.

CALENDAR_FILE = '''# Bir yorum, dosyanın kendisi hakkında.

weekly_rest_days: [saturday, sunday]

holidays:
  # Blok hakkında bir yorum.
  - 2026-05-01
  - 2026-08-30
'''


@pytest.fixture
def calendar_screen(shell, tmp_path):
    """The calendar screen, pointed at a throwaway config folder.

    A copy, never `config/`: a test that writes to the repository's own calendar would
    change which days the program treats as working days.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "takvim-2026.yaml").write_text(CALENDAR_FILE, encoding="utf-8")

    def build(period="2026-08"):
        window = shell()
        # Pointed at the copy after construction rather than through the
        # constructor: `config_dir` is also what the report screen validates
        # against, and this test has no business moving that.
        window.config_dir = config_dir
        window.run_finished(period)
        window.show("takvim")
        screen = window._screens["takvim"]
        screen.config_dir = config_dir
        screen.load(period)
        window.root.update()
        return window, screen

    build.config_dir = config_dir
    return build


def test_the_calendar_screen_opens_on_the_month_that_was_just_reported(
        calendar_screen):
    """Not today's month: the month whose figures the operator is looking at."""
    _window, screen = calendar_screen(period="2026-05")
    assert screen.period == "2026-05"
    assert "Mayıs 2026" in str(screen.month_label.cget("text"))


def test_the_days_already_in_the_file_are_shown_as_marked(calendar_screen):
    from datetime import date

    _window, screen = calendar_screen()
    assert screen.marks == {date(2026, 8, 30)}, "what the file says, and nothing else"


def test_a_click_makes_a_day_a_holiday_and_another_click_undoes_it(calendar_screen):
    """Two states, not three. There were briefly two kinds of holiday and nothing
    calculated them differently, so the second one cost a decision per click and bought
    a label (ADR-043)."""
    from datetime import date

    _window, screen = calendar_screen()
    day = date(2026, 8, 12)

    screen.toggle(day)
    assert day in screen.marks
    screen.toggle(day)
    assert day not in screen.marks, "and back to an ordinary working day"


def test_a_weekend_cannot_be_marked(calendar_screen):
    """It is already a rest day. An entry that changes nothing reads as though it does."""
    from datetime import date

    _window, screen = calendar_screen()
    saturday = date(2026, 8, 8)
    assert saturday.weekday() == 5

    assert saturday in screen._cells
    assert not screen._cells[saturday].bind("<Button-1>"), "no click handler"


def test_saving_writes_the_file_and_leaves_the_other_months_alone(calendar_screen):
    from datetime import date

    from mesai import takvim_file

    _window, screen = calendar_screen()
    for day in (date(2026, 8, 10), date(2026, 8, 11)):
        screen.toggle(day)
    screen._save()

    written = takvim_file.read(calendar_screen.config_dir / "takvim-2026.yaml")
    assert {date(2026, 8, 10), date(2026, 8, 11)} <= written
    assert date(2026, 5, 1) in written, \
        "May is not this screen's business and must survive"
    assert date(2026, 8, 30) in written



def test_the_file_keeps_its_comments_through_a_save(calendar_screen):
    """The notes saying which dates were inferred are the point of the file."""
    from datetime import date

    _window, screen = calendar_screen()
    screen.toggle(date(2026, 8, 12))
    screen._save()

    text = (calendar_screen.config_dir / "takvim-2026.yaml").read_text(
        encoding="utf-8")
    assert "# Bir yorum, dosyanın kendisi hakkında." in text
    assert "# Blok hakkında bir yorum." in text
    assert "weekly_rest_days: [saturday, sunday]" in text


def test_nothing_can_be_saved_until_something_changes(calendar_screen):
    _window, screen = calendar_screen()
    assert str(screen.save_button.cget("state")) == "disabled"

    from datetime import date
    screen.toggle(date(2026, 8, 12))
    assert str(screen.save_button.cget("state")) == "normal"

    screen._save()
    assert str(screen.save_button.cget("state")) == "disabled", "saved, so nothing to do"





def test_a_marked_day_is_simply_a_holiday(calendar_screen):
    """A date in a list. No name, no category, no provenance.

    There were briefly two kinds and a name each; nothing in the program ever read
    either, so both went (ADR-043, ADR-045). What is left is what the calculation
    actually uses.
    """
    from datetime import date

    from mesai import config as config_module
    from mesai import takvim_file

    _window, screen = calendar_screen()
    screen.toggle(date(2026, 8, 12))
    screen._save()

    # The throwaway config folder has no settings.yaml, so the calendar is read on its
    # own terms rather than through `config.load`.
    days = takvim_file.read(calendar_screen.config_dir / "takvim-2026.yaml")
    assert date(2026, 8, 12) in days

    calendar = config_module.Calendar(holidays=frozenset(days),
                                      rest_weekdays=frozenset({5, 6}))
    assert calendar.is_holiday(date(2026, 8, 12))
    assert date(2026, 8, 12) not in calendar.expected_workdays(2026, 8)
    assert calendar.label(date(2026, 8, 12)) == "Tatil"


def test_the_screen_suggests_nothing_and_marks_nothing(calendar_screen):
    """It briefly proposed the days almost nobody attended, from the last run.

    Removed on the operator's call, and the reason is worth keeping: the screen had
    nothing to say until a report had been produced, which is a strange thing for a
    calendar to depend on. The check lives where the data is — the report's `Kontrol`
    sheet, for the month it just computed (ADR-044). Marking a day is a click.
    """
    from datetime import date

    _window, screen = calendar_screen()

    assert not hasattr(screen, "candidates")
    assert screen.marks == {date(2026, 8, 30)}, \
        "only what the file says, never a guess"
    cell_text = {str(screen._cells[day].cget("text")) for day in screen._cells}
    assert not any("?" in text for text in cell_text), "no day is questioned"


def test_marks_survive_the_window_being_closed_and_reopened(calendar_screen):
    """They are in a file, so they must. Asked directly, so it is checked directly."""
    from datetime import date

    _window, screen = calendar_screen()
    screen.toggle(date(2026, 8, 12))
    screen._save()

    _again, reopened = calendar_screen()          # a fresh window, same config folder
    assert date(2026, 8, 12) in reopened.marks


def test_marks_that_were_never_saved_do_not_come_back(calendar_screen):
    """The other half of the same answer: unsaved is unsaved."""
    from datetime import date

    _window, screen = calendar_screen()
    screen.toggle(date(2026, 8, 12))              # no save

    _again, reopened = calendar_screen()
    assert date(2026, 8, 12) not in reopened.marks


def test_closing_the_window_with_unsaved_marks_asks_first(calendar_screen,
                                                          monkeypatch):
    """The month switch asked and the X did not — the same loss by a quieter route."""
    from datetime import date
    from tkinter import messagebox

    window, screen = calendar_screen()
    screen.toggle(date(2026, 8, 12))
    asked: list[str] = []
    monkeypatch.setattr(messagebox, "askokcancel",
                        lambda *a, **k: asked.append(a[1]) or False)

    window.close()

    assert asked, "closing must ask"
    assert "kaydedilmemiş" in asked[0].lower()
    assert window.root.winfo_exists(), "and cancelling must keep the window"


def test_closing_with_nothing_pending_does_not_ask(calendar_screen, monkeypatch):
    from tkinter import messagebox

    window, _screen = calendar_screen()
    asked: list[object] = []
    monkeypatch.setattr(messagebox, "askokcancel",
                        lambda *a, **k: asked.append(a) or False)

    window.close()
    assert not asked, "nothing to lose, nothing to ask"


def test_a_screen_without_unsaved_work_is_not_consulted(shell, monkeypatch):
    """The shell knows nothing about screens beyond the optional `unsaved()` hook."""
    from tkinter import messagebox

    window = shell(extra=[shell.fake("sahte")])
    window.show("sahte")
    monkeypatch.setattr(messagebox, "askokcancel",
                        lambda *a, **k: pytest.fail("asked about a screen with no hook"))

    window.close()
