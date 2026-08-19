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
from pathlib import Path

import tkinter as tk_module

import pytest

from mesai import gui
from mesai import snapshot as snapshot_module
from mesai.gui import app as app_module, places, rapor, widgets
from mesai.mail import recipients
from mesai import gui as _gui_pkg  # noqa: F401  (gui.rapor attribute access)


def _touch(folder: Path, *names: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"")


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

    try:
        root = tk.Tk()
    except tk.TclError:                          # pragma: no cover - headless
        pytest.skip("no display")

    def build(settings_payload=None):
        if settings_payload is not None:
            (tmp_path / "arayuz-ayarlari.json").write_text(
                json.dumps(settings_payload), encoding="utf-8")
        return gui.App(root, config_dir=Path("config"),
                       roster_dir=Path("data/personel"), base=tmp_path).report

    yield build
    root.destroy()


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

    try:
        root = tk.Tk()
    except tk.TclError:                          # pragma: no cover - headless
        pytest.skip("no display")

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
    root.destroy()


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
    shown = [c.cget("text") for c in screen.list_frame.winfo_children()]
    assert any("Rapor oluşturduktan sonra" in str(t) for t in shown)


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

    name, var = screen._rows[0]
    var.set(False)
    screen._toggle(name, var)

    chosen = recipients.selected(screen.snapshot, screen.filter_key, screen.excluded)
    assert [p.name for p in chosen] == ["BERK NUMUNE"]
    assert "1 / 2 kişi seçili" in screen.count_label.cget("text")


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
    labels = [str(c.cget("text")) for c in screen.list_frame.winfo_children()]
    assert "e-posta yok" in labels


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
