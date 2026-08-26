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
    assert saved["output_dir"] == str(kept)
    assert saved["browse_dir"] == str(share)


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
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "gonderim-2026-05.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _person(name, problems=(), expected=(), email="a@b.c", days=()):
    return {"name": name, "email": email, "personnel_no": None, "department": None,
            "facility": None, "in_roster": True, "has_attendance": True,
            "worked_days": 20, "minutes": 480, "remote_days": 0.0, "leave_days": 0.0,
            "problems": list(problems), "expected": list(expected), "notes": [],
            "days": list(days)}


def _pday(day, problems=("Çıkış yok",), entry="07:41", exit="", minutes=None,
          covered_by=""):
    """One problem day, as the snapshot file writes it.

    `minutes=None` and no `covered_by` means nothing was counted and no leave explains
    it — the shape `days_for` returns, which is what the day panel lists (ADR-061).
    """
    return {"date": f"2026-05-{day:02d}", "problems": list(problems),
            "entry": entry, "exit": exit, "minutes": minutes,
            "covered_by": covered_by}


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
    """What matters is that a fresh window does not bring it back.

    Asserted through `_restore` rather than by looking for an absent key: since the
    settings file is written read-modify-write (so screens cannot clobber each other),
    *omitting* a key would leave the old value in the file. Clearing is therefore
    written as an explicit `null`, and the assertion has to be about the behaviour.
    """
    _touch(tmp_path / "personel", "calisan_listesi.xlsx")
    window = screen()
    window.roster_file = tmp_path / "personel" / "calisan_listesi.xlsx"
    window._save()

    window._forget_source("roster")

    reopened = screen()
    assert reopened.roster_file is None, "a forgotten roster came back"


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


def _click(screen, row, *, on_tick: bool):
    """A click on one row, in the tick column or outside it.

    The x has to be real: the row does two things now and which one depends on the
    column the pointer is over (ADR-064).
    """
    box = screen.tree.bbox(row)
    x = box[0] + 8 if on_tick else box[0] + 120
    return screen._clicked(type("Click", (), {"x": x, "y": box[1] + 2})())


def test_clicking_the_tick_takes_that_person_out_and_back(people):
    """The tick column is the target for in-or-out, since the rest of the row now
    shows the person's days (ADR-064)."""
    window, screen = people()
    name, row = screen._rows[0]
    window.root.update()

    _click(screen, row, on_tick=True)
    assert name in screen.excluded
    assert screen.tree.set(row, "tik") == "☐"

    _click(screen, row, on_tick=True)
    assert name not in screen.excluded


def test_clicking_the_name_shows_that_persons_days_and_leaves_them_in(people):
    """The two targets must not bleed into each other: opening somebody's days is not
    a decision about whether to write to them."""
    window, screen = people()
    name, row = screen._rows[0]
    window.root.update()

    _click(screen, row, on_tick=False)
    assert screen._person == name
    assert name not in screen.excluded, "showing the days must not remove the person"
    assert name in screen.day_title.cget("text")


def test_clicking_below_the_last_row_changes_nothing(people):
    """There is no nearest person to guess at down there."""
    window, screen = people()
    screen.filter_key = "Çıkış yok"
    screen._repaint()
    window.root.update()

    screen._clicked(type("Click", (), {"x": 8,
                                      "y": screen.tree.winfo_height() - 4})())
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


# --- picking which notes count as a problem (ADR-048) -----------------------
#
# The workflow: filter to the people whose records need chasing, tick who stays, copy
# the list — and later, mail them. Which notes make somebody one of those people is a
# decision that will change, so it is ticked in the window rather than fixed in code.
# What must not happen is a silent one: an empty tick list meaning "everybody", or a
# remembered selection quietly dropping a note that appeared this month.

def _boxes(screen) -> dict:
    """The note checkboxes, by the label they carry."""
    import tkinter as tk_local

    found = {}
    for child in screen.notes_frame.winfo_children():
        if isinstance(child, tk_local.Checkbutton):
            text = str(child.cget("text"))
            found[text.rsplit("  (", 1)[0]] = child
    return found


@pytest.fixture
def problem_screen(people_screen, tmp_path):
    """The people screen showing `Sorunu olanlar` over a synthetic month."""
    def build():
        screen = people_screen._screens["kisiler"]
        screen.load(_snapshot_file(tmp_path, [
            _person("AYŞE DENEME", ["Çıkış yok"]),
            _person("BERK NUMUNE", ["Çıkış yok", "Gece geçişi"]),
            _person("CEM ÖRNEK", ["Tesis birleştirme"]),
            _person("DENİZ TASLAK", ["Kart bilgisi yok"]),
            _person("EDA MİSAL", []),
        ]))
        screen.filter_key = recipients.PROBLEM
        screen._repaint()
        people_screen.root.update()
        return screen
    return build


def test_the_problem_filter_is_offered_next_to_the_clean_one(problem_screen):
    """They are each other's counterpart; a list with only one of them reads oddly."""
    screen = problem_screen()
    shown = list(screen.filter_box.cget("values"))

    assert any(s.startswith("Sorunu olmayanlar  (1)") for s in shown)
    # 4, not 3: the count is everybody with something outstanding under any note, and
    # it no longer follows the tick panel. `Tesis birleştirme` is unticked by default,
    # so the LIST still shows three — the number answers "how big is this group", the
    # rows answer "who is selected right now", and they are different questions.
    assert any(s.startswith("Sorunu olanlar  (4)") for s in shown), shown


def test_the_two_defaults_off_are_unticked_and_their_people_absent(problem_screen):
    """`CEM` has only `Tesis birleştirme` — a punch the program already repaired."""
    screen = problem_screen()

    assert screen._off == set(recipients.DEFAULT_OFF)
    assert [name for name, _row in screen._rows] == [
        "AYŞE DENEME", "BERK NUMUNE", "DENİZ TASLAK"]
    assert _boxes(screen)["Tesis birleştirme"].cget("variable")


def test_ticking_a_note_back_on_brings_its_people_in(problem_screen):
    screen = problem_screen()

    _boxes(screen)["Tesis birleştirme"].invoke()
    assert "CEM ÖRNEK" in [name for name, _row in screen._rows]

    _boxes(screen)["Tesis birleştirme"].invoke()
    assert "CEM ÖRNEK" not in [name for name, _row in screen._rows]


def test_unticking_a_note_removes_only_the_people_it_alone_explains(problem_screen):
    """`BERK` has `Çıkış yok` too, so dropping `Gece geçişi` must not drop him."""
    screen = problem_screen()

    _boxes(screen)["Gece geçişi"].invoke()

    assert "BERK NUMUNE" in [name for name, _row in screen._rows]


def test_clearing_every_note_shows_nobody_rather_than_everybody(problem_screen):
    """The dangerous direction: an empty tick list must not fall back to "all"."""
    screen = problem_screen()

    screen._count_none()

    assert screen._rows == []
    assert "0 / 0 kişi seçili" in screen.count_label.cget("text")


def test_hepsi_counts_every_note_including_the_two(problem_screen):
    screen = problem_screen()

    screen._count_all()

    assert screen._off == set()
    assert len(screen._rows) == 4, "everyone with any note at all"


def test_the_filter_count_does_not_move_with_the_ticks(problem_screen):
    """*"o sayı değişmesin total sayı kalsın."*

    It used to be the row count, which meant unticking notes walked it down towards
    zero — and the panel that does the unticking is only reachable from inside this
    filter, so the number described a state you had to enter it to see. The row count
    is on the screen anyway, under the list.
    """
    screen = problem_screen()
    seen = set()

    for action in (lambda: _boxes(screen)["Çıkış yok"].invoke(),
                   screen._count_all,
                   screen._count_none):
        action()
        entry = next(c for c in screen._choices if c.key == recipients.PROBLEM)
        seen.add(entry.count)
    assert len(seen) == 1, f"the count moved with the ticks: {seen}"


def test_the_selection_is_remembered_between_runs(problem_screen, people_screen,
                                                  tmp_path):
    """A setup decision, not a monthly one."""
    screen = problem_screen()
    _boxes(screen)["Gece geçişi"].invoke()

    stored = json.loads(
        (tmp_path / "arayuz-ayarlari.json").read_text(encoding="utf-8"))
    assert "Gece geçişi" in stored["problem_notes_off"]


def test_a_remembered_selection_is_applied_on_the_next_window(shell, tmp_path):
    (tmp_path / "arayuz-ayarlari.json").write_text(
        json.dumps({"problem_notes_off": ["Çıkış yok"]}), encoding="utf-8")

    window = shell()
    window.show("kisiler")
    screen = window._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME", ["Çıkış yok"]),
        _person("DENİZ TASLAK", ["Kart bilgisi yok"])]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    window.root.update()

    assert [name for name, _row in screen._rows] == ["DENİZ TASLAK"]


def test_a_note_that_is_new_this_month_counts_without_being_asked(shell, tmp_path):
    """The off-set is stored, not the on-set — so a note nobody has seen counts.

    For a list that decides who gets contacted, including somebody who should not have
    been is a correction; leaving somebody out is silence.
    """
    (tmp_path / "arayuz-ayarlari.json").write_text(
        json.dumps({"problem_notes_off": ["Tesis birleştirme"]}), encoding="utf-8")

    window = shell()
    window.show("kisiler")
    screen = window._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("YENİ SINAMA", ["Giriş-çıkış tutarsız"])]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    window.root.update()

    assert [name for name, _row in screen._rows] == ["YENİ SINAMA"]


def test_the_panel_is_shown_only_under_the_problem_filter(problem_screen):
    """Under any other filter it has nothing to change, so it is not in the way."""
    screen = problem_screen()
    assert screen.notes_frame.winfo_manager() == "grid"

    screen.filter_key = recipients.ALL
    screen._repaint()
    assert screen.notes_frame.winfo_manager() == ""

    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    assert screen.notes_frame.winfo_manager() == "grid"


def test_expected_behaviour_notes_are_not_offered_for_ticking(people_screen, tmp_path):
    """`Uzaktan + sistem kaydı` is expected behaviour, not somebody's problem (ADR-017).

    Offering it here would invite putting 38 people on a chasing list for a note that
    says the program did the right thing.
    """
    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person("AYŞE DENEME", ["Çıkış yok"], ["Uzaktan + sistem kaydı"])]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    people_screen.root.update()

    assert "Uzaktan + sistem kaydı" not in _boxes(screen)
    assert "Çıkış yok" in _boxes(screen)


def test_the_copied_list_follows_the_ticked_notes(problem_screen):
    """The clipboard is the point of the screen; it must not copy a different list."""
    screen = problem_screen()
    captured: list[str] = []
    screen.root.clipboard_clear = lambda: None
    screen.root.clipboard_append = lambda text: captured.append(text)

    screen._copy()
    assert len(captured[0].split("\n")) == 3

    captured.clear()
    screen._count_all()
    screen._copy()
    assert len(captured[0].split("\n")) == 4


def test_the_note_panel_fits_with_every_note_present(people_screen, tmp_path):
    """The panel clipped once already, at four columns (ADR-039's neighbourhood).

    The labels are plain again — `{not} ({kişi})`, ADR-059 — and the widest of them is
    `Günlük süre çok uzun (>16 saat)`. This holds the fit against a month that carries
    every note at once, so a label added later cannot quietly start clipping. A clipped
    checkbox is worse than a tall panel: the reader cannot tell which note they tick.
    """
    import tkinter as tk

    from mesai.mail import recipients

    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        # every punch note, on days that mostly counted, so both figures are wide
        _person(f"KİŞİ{n} DENEME", ["Çıkış yok", "Giriş yok",
                                    "Hem giriş hem çıkış yok",
                                    "Günlük süre çok kısa (<2 saat)",
                                    "Günlük süre çok uzun (>16 saat)",
                                    "Gece geçişi", "Tesis birleştirme",
                                    "Kart bilgisi yok", "Ay büyük ölçüde boş"])
        for n in range(120)
    ]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    people_screen.root.update_idletasks()

    kutular = [child for child in screen.notes_frame.winfo_children()
               if isinstance(child, tk.Checkbutton)]
    assert kutular, "the panel must have rendered something to measure"

    available = screen.notes_frame.winfo_width()
    assert available > 1, "frame not mapped; the measurement would be meaningless"
    # Three columns share the width now — every note became a checkbox, so the panel
    # carries twice the entries and its height is the day panel's height. Measured
    # against `_NOTE_COLUMNS` rather than a literal, so changing the column count
    # cannot leave this test asserting the old layout.
    from mesai.gui.people import _NOTE_COLUMNS
    kolon = available / _NOTE_COLUMNS
    en_genis = max(k.winfo_reqwidth() for k in kutular)
    assert en_genis <= kolon, (
        f"kutu {en_genis}px, kolon {kolon:.0f}px — kırpılır")


# --- different window sizes (asked for directly) -----------------------------

_SIZES = [
    (880, 620),      # the floor: root.minsize
    (1024, 700),     # a small laptop
    (1366, 768),     # the commonest laptop panel
    (1920, 1080),    # a desk monitor
    (2560, 1400),    # wide, the case where a fixed layout leaves a dead right half
]


@pytest.mark.parametrize("width,height", _SIZES)
def test_the_people_screen_uses_the_window_it_is_given(people_screen, tmp_path,
                                                       width, height):
    """Asked directly: does anything break at another resolution or maximized?

    Two failures are looked for, and they are the two a grid layout actually produces:
    a list that stops growing and leaves the right half of a wide window dead, and a
    layout wider than its window, which crops from the edge.
    """
    from mesai.mail import recipients

    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person(f"KİŞİ{n} DENEME", ["Çıkış yok"]) for n in range(60)]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()

    root = people_screen.root
    root.geometry(f"{width}x{height}")
    root.update()
    root.update_idletasks()

    assert root.winfo_width() >= width - 2, "the window did not take the size"
    # nothing may be wider than the window it sits in
    assert screen.frame.winfo_width() <= root.winfo_width()

    # Two panels share the width now (ADR-064): the person list and the day list. Both
    # have to be usable at every size, and together they have to use the window rather
    # than sitting at a fixed width in a wide one. The day CARD is measured, not its
    # Treeview — with nobody picked the tree is unmapped and reports 1 px, which would
    # make this assert nothing.
    liste, gun_karti = screen.tree, screen.day_card
    assert liste.winfo_width() >= 330, (
        f"{width}x{height}: kişi listesi {liste.winfo_width()}px")
    assert gun_karti.winfo_width() >= 330, (
        f"{width}x{height}: gün paneli {gun_karti.winfo_width()}px")
    # Against the screen's own frame, not the window: the navigation rail on the left
    # takes width too, and comparing with the window made this fail at 1024 and 1366
    # for a reason that had nothing to do with the panels.
    icerik = screen.frame.winfo_width()
    assert liste.winfo_width() + gun_karti.winfo_width() >= icerik * 0.9, (
        f"{width}x{height}: iki panel {liste.winfo_width()}+"
        f"{gun_karti.winfo_width()}px / içerik {icerik}px")
    assert liste.winfo_height() > 60, "the list collapsed"

    # And with somebody picked, the day list itself has to be usable.
    if screen._rows:
        _click(screen, screen._rows[0][1], on_tick=False)
        root.update_idletasks()
        if any(screen._person_days()):
            assert screen.day_tree.winfo_width() >= 330, (
                f"{width}x{height}: gün listesi {screen.day_tree.winfo_width()}px")
            assert screen.day_tree.winfo_height() > 40, "gün listesi çöktü"


@pytest.mark.parametrize("width,height", _SIZES)
def test_the_report_screen_uses_the_window_it_is_given(people_screen, width, height):
    """Same question for the screen that is on display when the window first opens."""
    people_screen.show("rapor")
    root = people_screen.root
    root.geometry(f"{width}x{height}")
    root.update()
    root.update_idletasks()

    screen = people_screen._screens["rapor"]
    assert screen.frame.winfo_width() <= root.winfo_width()
    assert screen.frame.winfo_width() >= root.winfo_width() * 0.5


def test_maximizing_is_left_alone(people_screen):
    """`_fit` grows the window on a screen change; maximized, the size is the user's.

    Without the early return, switching screens while maximized re-asserted a smaller
    geometry and un-maximized the window.
    """
    root = people_screen.root
    try:
        root.state("zoomed")
        root.update_idletasks()
    except Exception:                       # pragma: no cover - platform without it
        pytest.skip("this platform has no zoomed state")

    people_screen.show("kisiler")
    root.update_idletasks()
    assert root.state() == "zoomed", "switching screens must not un-maximize"

    people_screen.show("rapor")
    root.update_idletasks()
    assert root.state() == "zoomed"


# --- the selected person's days (ADR-064) ------------------------------------

def _day_click(screen, row):
    box = screen.day_tree.bbox(row)
    return screen._day_clicked(type("Click", (), {"x": box[0] + 8,
                                                  "y": box[1] + 2})())


@pytest.fixture
def day_screen(people_screen, tmp_path):
    """The people screen over a month whose people carry problem DAYS, not just labels.

    The other fixtures give people note labels and no days, which was enough while the
    screen only listed people. The day panel needs the days themselves.
    """
    def build():
        screen = people_screen._screens["kisiler"]
        screen.load(_snapshot_file(tmp_path, [
            _person("AYŞE DENEME", ["Çıkış yok"],
                    days=[_pday(4), _pday(11), _pday(18)]),
            _person("BERK NUMUNE", ["Giriş yok"],
                    days=[_pday(5, ["Giriş yok"], entry="", exit="18:26")]),
            # days that ARE explained: counted elsewhere, and covered by leave. Neither
            # may reach the panel (ADR-061).
            _person("CEM ÖRNEK", ["Çıkış yok"],
                    days=[_pday(6, minutes=523),
                          _pday(7, covered_by="Yıllık İzin")]),
            # A note nobody has anything outstanding under: it happened, and every day
            # of it counted. It belongs in the `also_happened` line, not on a checkbox.
            _person("DENİZ TASLAK", ["Tesis birleştirme"],
                    days=[_pday(8, ["Tesis birleştirme"], minutes=540)]),
            _person("EDA MİSAL", []),
        ]))
        screen.filter_key = recipients.PROBLEM
        screen._repaint()
        people_screen.root.update()
        return screen
    return build


def _person_with_days(screen):
    """The first listed person who actually has days to show."""
    for name, row in screen._rows:
        screen._person = name
        if any(screen._person_days()):
            return name, row
    screen._person = None
    return None, None


def test_the_day_panel_lists_every_problem_day_whatever_is_ticked(day_screen):
    """The panel is a fact about the person, not a view of the tick panel (ADR-074).

    It used to be `days_for(person, counted())`, so unticking a note walked it down: a
    person with 24 uncounted days showed 21 with only `Çıkış yok` ticked. *"bir insanın
    kaç günü sayılmamışsa o kadar sorunlu günü görünmeli filtreden bağımsız."*
    """
    from mesai.mail import recipients

    screen = day_screen()
    name, row = _person_with_days(screen)
    assert name, "sentetik ayda gösterilecek gün olan kimse yok"
    _click(screen, row, on_tick=False)

    person = next(p for p in screen.snapshot.people if p.name == name)
    lost, kept = recipients.days_by_cost(person)
    assert screen._person_days() == (lost, kept)

    # Untick every note: the panel must not move.
    screen._count_none()
    screen._person = name
    screen._paint_days()
    assert screen._person_days() == (lost, kept), "panel işaretlere bağlı kalmış"


def test_every_day_starts_selected(day_screen):
    """Off-set, not on-set: a day nobody has decided about is in. A list that decides
    what somebody is told errs towards one day too many, never one too few."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    assert all(screen.day_tree.set(r, "tik") == "☑" for _iso, r in screen._day_rows)
    assert screen._days_off == set()
    assert len(screen.day_selection()) >= len(screen._day_rows)


def test_clicking_a_day_takes_it_out_and_back(day_screen):
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    iso, day_row = screen._day_rows[0]

    _day_click(screen, day_row)
    assert (name, iso) in screen._days_off
    assert screen.day_tree.set(day_row, "tik") == "☐"
    assert (name, iso) not in screen.day_selection()

    _day_click(screen, day_row)
    assert (name, iso) not in screen._days_off
    assert (name, iso) in screen.day_selection()


def test_a_day_taken_out_stays_out_across_a_filter_change(day_screen):
    """Keyed on the date, not on a row: the list re-sorts and re-filters underneath.
    An index would come to mean a different day, which is the mistake `excluded`
    already avoids."""
    from mesai.mail import recipients

    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    iso, day_row = screen._day_rows[0]
    _day_click(screen, day_row)

    screen.filter_key = recipients.ALL
    screen._repaint()
    _click(screen, next(r for n, r in screen._rows if n == name), on_tick=False)

    assert (name, iso) in screen._days_off
    tikler = {i: screen.day_tree.set(r, "tik") for i, r in screen._day_rows}
    assert tikler.get(iso) == "☐", tikler


def test_a_person_the_filter_drops_leaves_the_panel(day_screen):
    """The panel must not describe somebody the list beside it does not contain."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    assert screen._person == name

    screen.filter_key = "Kart bilgisi yok"
    screen._repaint()

    if name not in {n for n, _ in screen._rows}:
        assert screen._person is None
        assert screen.day_title.cget("text") == "GÜNLER"


def test_loading_a_month_forgets_last_months_day_ticks(day_screen, tmp_path):
    """New month, new dates. Keeping the ticks would carry a decision about days that
    are not in the file."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    _day_click(screen, screen._day_rows[0][1])
    assert screen._days_off

    screen.load(_snapshot_file(tmp_path / "sonraki",
                               [_person("AYŞE DENEME", ["Çıkış yok"])]))

    assert screen._days_off == set()
    assert screen._person is None


def test_an_explained_day_never_reaches_the_panel(day_screen):
    """CEM's two days are both accounted for — one counted 523 minutes from another
    record, the other is annual leave. Neither is a problem (ADR-061), so two things
    must hold and both are asserted rather than skipped past: he is not in the problem
    list at all, and picking him from a list that does show him gives an empty panel.
    """
    from mesai.mail import recipients

    screen = day_screen()
    assert "CEM ÖRNEK" not in {n for n, _ in screen._rows},         "her günü açıklanan kişi Sorunu olanlar listesinde durmamalı"

    screen.filter_key = recipients.ALL
    screen._repaint()
    row = next(r for n, r in screen._rows if n == "CEM ÖRNEK")
    _click(screen, row, on_tick=False)

    # Nothing at all. One of his days was counted from another record and the other is
    # leave, and neither is a question for anybody (ADR-075, ADR-076).
    assert screen._person_days() == ((), ())
    assert screen._day_rows == []
    assert "sorunlu gün yok" in screen.day_title.cget("text")


def test_the_panel_shows_the_times_and_the_note_for_each_day(day_screen):
    """`Günlük Detay` beside the list, which is what was asked for: the date, the day,
    what was read, and the note. An empty reading prints as a dash, never 00:00."""
    screen = day_screen()
    row = next(r for n, r in screen._rows if n == "BERK NUMUNE")
    _click(screen, row, on_tick=False)

    _iso, day_row = screen._day_rows[0]
    values = [screen.day_tree.set(day_row, c)
              for c in ("tarih", "gun", "giris", "cikis", "sure", "not")]
    assert values == ["05.05.2026", "Sal", "—", "18:26", "—", "Giriş yok"]


def test_both_lists_name_their_columns(day_screen):
    """Five columns of bare figures were guesswork: `9:39` beside `+2` beside an
    address, with nothing saying which was which (ADR-066)."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    # `Sorunlu gün`, not `Gün`: on the person list the number is a count of problem
    # days, and beside a duration a bare "Gün" read as days worked. The day panel's own
    # `Gün` column really is the day of the week and keeps the short name.
    assert [screen.tree.heading(c, "text")
            for c in ("ad", "saat", "gun", "eposta")] == [
        "Ad Soyad", "Süre", "Sorunlu gün", "E-posta"]
    assert [screen.day_tree.heading(c, "text")
            for c in ("tarih", "gun", "giris", "cikis", "sure", "not")] == [
        "Tarih", "Gün", "Giriş", "Çıkış", "Süre", "Sorun"]
    # The tick columns stay unlabelled: a heading over a 34 px glyph column is noise.
    assert screen.tree.heading("tik", "text") == ""
    assert screen.day_tree.heading("tik", "text") == ""


def test_the_person_row_counts_the_days_the_panel_will_show(day_screen):
    """One number for one person. It printed a count of the person's other notes before,
    which answered a question nobody asks and disagreed with every other figure."""
    screen = day_screen()
    for name, row in screen._rows:
        screen._person = name
        beklenen = len(screen._person_days()[0])       # the days that LOST time
        yazan = screen.tree.set(row, "gun")
        assert yazan == (str(beklenen) if beklenen else ""), (
            f"{name}: satır {yazan!r}, panel {beklenen}")


def test_every_note_that_selects_somebody_is_a_checkbox(day_screen):
    """The reverse of what ADR-069 held, and for the reason ADR-069 gave.

    Those notes were text because ticking them selected nobody. That was the filter's
    bug — `counted_only_labels` — not a property of the notes: `Gece geçişi (6)` now
    returns its six people, and a note that can be acted on belongs on a control.
    The `Bu ay ayrıca: …` line is gone; it would be describing the panel it sits in.
    """
    import tkinter as tk

    from mesai.mail import recipients

    screen = day_screen()
    offered = recipients.problem_labels(screen.snapshot)
    assert offered, "sentetik ayda hiç not yok — test bir şey ölçmüyor"

    for _group, label, count in offered:
        assert label in screen._note_vars, f"{label} kutu değil"
        assert count == len(recipients.matching(screen.snapshot, label)), label
    metin = " ".join(
        c.cget("text") for c in screen.notes_frame.winfo_children()
        if isinstance(c, tk.Label))
    assert "Bu ay ayrıca" not in metin, metin


def test_somebody_with_no_card_record_does_not_look_clean(day_screen, tmp_path):
    """The panel said `sorunlu gün yok` to somebody whose whole month has no badge
    record, because a month-level note has no day to list. That is the opposite of what
    the note says (ADR-069)."""
    from mesai.mail import recipients

    screen = day_screen()
    screen.load(_snapshot_file(tmp_path / "kartsiz", [
        _person("KEREM DENEME", ["Kart bilgisi yok"]),
        _person("AYŞE DENEME", ["Çıkış yok"], days=[_pday(4)]),
    ]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()

    row = next(r for n, r in screen._rows if n == "KEREM DENEME")
    _click(screen, row, on_tick=False)

    assert screen._person_days() == ((), ())
    baslik = screen.day_title.cget("text")
    metin = screen.day_note.cget("text")
    assert "sorunlu gün yok" not in baslik, baslik
    assert "Kart bilgisi yok" in metin, metin
    assert "Dönem:" in metin, "hangi dönem olduğu yazmalı"


def test_the_no_card_record_message_is_loud_and_fits(day_screen, tmp_path):
    """It carried the same muted grey and font as "nothing wrong here", and a fixed wrap
    length cut it off until the window was maximised — so the one message that means the
    opposite of "fine" looked like it and could not be read (ADR-070)."""
    from mesai.gui import widgets as w
    from mesai.mail import recipients

    screen = day_screen()
    screen.load(_snapshot_file(tmp_path / "kartsiz2", [
        _person("KEREM DENEME", ["Kart bilgisi yok"]),
        _person("AYŞE DENEME", ["Çıkış yok"], days=[_pday(4)]),
    ]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    root = screen.frame.winfo_toplevel()

    kartsiz = next(r for n, r in screen._rows if n == "KEREM DENEME")
    _click(screen, kartsiz, on_tick=False)
    assert screen.day_note.cget("foreground") == w.BAD
    assert "bold" in str(screen.day_note.cget("font"))
    assert screen.day_title.cget("foreground") == w.BAD

    # and the ordinary empty state must not shout
    temiz = next(r for n, r in screen._rows if n == "AYŞE DENEME")
    _click(screen, temiz, on_tick=False)
    assert screen.day_title.cget("foreground") == w.INK

    # the note wraps to whatever the panel is, at the window floor and above
    for width, height in ((880, 620), (1366, 768)):
        root.geometry(f"{width}x{height}")
        root.update()
        _click(screen, kartsiz, on_tick=False)
        root.update_idletasks()
        pay = screen.day_card.winfo_width() - screen.day_note.winfo_width()
        assert pay >= 0, (f"{width}x{height}: yazı {screen.day_note.winfo_width()}px, "
                          f"panel {screen.day_card.winfo_width()}px")


# --- writing to one person -------------------------------------------------

def test_the_mail_row_appears_only_with_a_person_selected(day_screen):
    """It belongs to the person on the right, and there is no bulk send to belong to."""
    screen = day_screen()
    assert not screen.mail_row.winfo_ismapped() or screen._person is None

    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    screen.frame.update_idletasks()

    assert screen._person == name
    assert screen.mail_row.winfo_ismapped()
    assert screen.mail_var.get(), "adres snapshot'tan doldurulmalı"


def test_the_address_is_editable_and_survives_ticking_a_day(day_screen):
    """The eight people a month with no address are typed in by hand.

    A field that reset on every repaint would lose what was typed the moment a day was
    ticked off, which is the same click the operator makes next.
    """
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    screen.mail_var.set("elle@yazildi.com")
    iso, day_row = screen._day_rows[0]
    screen._day_clicked(type("Click", (), {"y": screen.day_tree.bbox(day_row)[1] + 2})())

    assert screen.mail_var.get() == "elle@yazildi.com"


def test_switching_person_refills_the_address(day_screen):
    """A typed address must NOT follow the operator onto the next person: that would
    send one person's mail to another's address."""
    screen = day_screen()
    first, first_row = _person_with_days(screen)
    _click(screen, first_row, on_tick=False)
    screen.mail_var.set("elle@yazildi.com")

    other = next(r for n, r in screen._rows if n != first)
    _click(screen, other, on_tick=False)

    assert screen.mail_var.get() != "elle@yazildi.com"


def test_the_draft_carries_only_the_days_still_ticked(day_screen):
    """The panel's ticks are the message's day list — that is what they are for."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)
    before = screen._draft()
    assert before is not None

    iso, day_row = screen._day_rows[0]
    screen._day_clicked(type("Click", (), {"y": screen.day_tree.bbox(day_row)[1] + 2})())
    after = screen._draft()

    from datetime import date
    dropped = date.fromisoformat(iso).strftime("%d.%m.%Y")
    assert dropped in before.body
    assert dropped not in after.body


def test_the_preview_sends_what_is_on_screen_not_what_was_composed(day_screen):
    """A preview showing one thing while another goes out is worse than no preview."""
    from mesai.gui.people import MailPreview

    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    sent = []
    preview = MailPreview(screen.root, screen._draft(),
                          lambda d: (sent.append(d), (True, "Gönderildi"))[1])
    preview.show()
    preview.body.insert("end", "\n\nElle eklenen satır.")
    preview.to_var.set("baska@adres.com")
    preview.confirm()

    assert len(sent) == 1
    assert sent[0].to == "baska@adres.com"
    assert sent[0].body.endswith("Elle eklenen satır.")
    assert preview.sent
    preview.close()


def test_the_preview_refuses_to_send_with_an_empty_address(day_screen):
    from mesai.gui.people import MailPreview

    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    sent = []
    preview = MailPreview(screen.root, screen._draft(),
                          lambda d: (sent.append(d), (True, ""))[1])
    preview.show()
    preview.to_var.set("   ")
    preview.confirm()

    assert not sent
    assert not preview.sent
    assert "boş" in preview.status.cget("text")
    preview.close()


def test_a_failed_send_says_why_and_leaves_the_window_open(day_screen):
    """The two failures this will actually produce — a wrong app password and a missing
    account file — are both fixed by a person. Closing the window loses the message."""
    from mesai.gui.people import MailPreview

    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    preview = MailPreview(screen.root, screen._draft(),
                          lambda d: (False, "Gmail girişi reddedildi."))
    preview.show()
    preview.confirm()

    assert not preview.sent
    assert "reddedildi" in preview.status.cget("text")
    assert preview.window is not None, "pencere kapanmamalı"
    preview.close()


def test_the_screen_reports_a_missing_account_file_instead_of_raising(day_screen,
                                                                     tmp_path):
    """`config/gmail.yaml` is absent on a fresh clone, which is the common case."""
    screen = day_screen()
    name, row = _person_with_days(screen)
    _click(screen, row, on_tick=False)

    ok, note = screen._send(screen._draft())

    assert not ok
    assert "gmail.yaml" in note


def test_the_note_panel_leaves_the_day_panel_room_at_the_floor(people_screen,
                                                               tmp_path):
    """The panel's height is height the day panel does not get, and the mail step is
    down there.

    Measured when every note became a checkbox: dealing whole families to columns left
    the third column empty and the taller family set the height alone — 267 px of panel
    and **11 px** of day panel at the 880x620 floor. Flowing the labels across the
    columns instead gives 152 and 126. This holds the ratio at the floor, which is the
    size that has bitten twice (ADR-038).
    """
    from mesai.mail import recipients

    screen = people_screen._screens["kisiler"]
    screen.load(_snapshot_file(tmp_path, [
        _person(f"KİŞİ{n} DENEME",
                ["Çıkış yok", "Giriş yok", "Hem giriş hem çıkış yok",
                 "Günlük süre çok kısa (<2 saat)", "Günlük süre çok uzun (>16 saat)",
                 "Gece geçişi", "Tesis birleştirme", "Uzaktan + kart kaydı",
                 "Giriş-çıkış tutarsız (>20 saat)", "Kart bilgisi yok"],
                days=[_pday(4), _pday(11)])
        for n in range(40)]))
    screen.filter_key = recipients.PROBLEM
    screen._repaint()
    people_screen.root.geometry("880x620")
    people_screen.root.update_idletasks()
    people_screen.root.update()

    panel = screen.notes_frame.winfo_height()
    gun = screen.day_card.winfo_height()
    assert panel <= 190, f"not paneli {panel}px — gün paneline yer kalmıyor"
    assert gun >= 100, f"gün paneli {gun}px; not paneli {panel}px"


def test_the_counted_days_sit_under_a_heading_and_start_unticked(day_screen):
    """*"sayılan günler diye bir başlıktan sonra o günler görünsün ... sadece isteğe
    bağlı seçilir, ilk başta seçilmemiş gelir."*

    They are offered because a repaired night crossing is a real thing to ask about
    (ADR-072). They start off because telling somebody "eksik durum tespit edilmiştir"
    about a day that was counted in full is a false statement — 27 of July's days were in
    that position while the ticked set drove the panel.
    """
    from mesai.mail import recipients

    screen = day_screen()
    screen.filter_key = recipients.ALL
    screen._repaint()
    row = next(r for n, r in screen._rows if n == "DENİZ TASLAK")
    _click(screen, row, on_tick=False)

    lost, kept = screen._person_days()
    assert not lost and kept, "bu kişi yalnızca sayılan gün taşıyor"

    values = [screen.day_tree.item(r, "values") for _iso, r in screen._day_rows]
    baslik = [v for v in values if "SAYILAN" in str(v[1])]
    assert len(baslik) == 1, values
    # every counted day is below the heading and unticked
    for v in values[values.index(baslik[0]) + 1:]:
        assert v[0] == "☐", v


def test_a_counted_day_can_be_ticked_on_and_reaches_the_message(day_screen):
    """Off by default is not off for good — the whole point of offering them."""
    from mesai.mail import recipients

    screen = day_screen()
    screen.filter_key = recipients.ALL
    screen._repaint()
    row = next(r for n, r in screen._rows if n == "DENİZ TASLAK")
    _click(screen, row, on_tick=False)
    screen.mail_var.set("deniz@example.com")

    assert "·" not in screen._draft().body, "hiçbiri seçili olmamalı"

    screen.frame.update_idletasks()
    iso, day_row = next((i, r) for i, r in screen._day_rows if i is not None)
    screen._day_clicked(type("Click", (), {"y": screen.day_tree.bbox(day_row)[1] + 2})())

    from datetime import date
    assert date.fromisoformat(iso).strftime("%d.%m.%Y") in screen._draft().body


def test_clicking_the_heading_row_does_nothing(day_screen):
    """It is not a day, and a tick appearing on it would mean nothing."""
    from mesai.mail import recipients

    screen = day_screen()
    screen.filter_key = recipients.ALL
    screen._repaint()
    row = next(r for n, r in screen._rows if n == "DENİZ TASLAK")
    _click(screen, row, on_tick=False)

    screen.frame.update_idletasks()
    heading = next(r for iso, r in screen._day_rows if iso is None)
    before = screen.day_tree.item(heading, "values")
    screen._day_clicked(type("Click", (), {"y": screen.day_tree.bbox(heading)[1] + 2})())

    assert screen.day_tree.item(heading, "values") == before
    assert not screen._days_on and not screen._days_off


def test_the_problem_day_column_does_not_move_with_the_ticks(day_screen):
    """The number is a fact about the person. It read 446 across July with the default
    ticks and 127 with one note ticked; the truth is 419 (ADR-074).

    Measured under `Herkes`, because the ticks legitimately decide **who** is in
    `Sorunu olanlar` — untick everything there and the list is empty, which is the
    ticks doing their job. What they may not change is a person's own number.
    """
    from mesai.mail import recipients

    screen = day_screen()
    screen.filter_key = recipients.ALL
    screen._repaint()
    before = {n: screen.tree.set(r, "gun") for n, r in screen._rows}
    assert any(before.values()), "ölçülecek bir sayı yok"

    screen._count_none()

    after = {n: screen.tree.set(r, "gun") for n, r in screen._rows}
    assert after == before, f"{before} -> {after}"


def test_the_day_headline_counts_only_what_the_panel_holds(day_screen):
    """It said `2 sayılan/izinli` after leave days had already left the panel.

    ADR-075 took them out and the block heading dropped the word; this line kept it, so
    the one number a reader can check against the block claimed it held something the
    block does not. A stale word inside a count is a false statement, which is the class
    of defect ADR-055, ADR-068 and ADR-070 were each about.
    """
    from mesai.mail import recipients

    screen = day_screen()
    screen.filter_key = recipients.ALL
    screen._repaint()

    for name, row in screen._rows:
        _click(screen, row, on_tick=False)
        baslik = screen.day_title.cget("text")
        assert "izinli" not in baslik, baslik
        lost, kept = screen._person_days()
        if kept:
            assert f"{len(kept)} sayılan" in baslik, baslik
        if lost or kept:
            assert f"{len(lost)} sayılmayan gün" in baslik, baslik
