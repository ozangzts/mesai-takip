"""What the window decides, not how it draws.

The window is a thin shell over `pipeline.run()` by design, so the parts worth testing
are the ones that decide what it tells the user: which files it found, which month it
understood, and what it remembers between runs. No test asserts a colour or a
geometry — that would be testing tkinter.

`describe_folder` is the one that earns its keep. The user picks a folder by hand, and
what they need to know — before pressing anything — is which of the three exports were
found. Reporting only the first failure would hide the other two.

The last group does build a real `Tk`, because "a fresh window pre-selects nothing" is
only true if the constructor really runs. It skips itself when there is no display.
"""

import json
from pathlib import Path

import pytest

from mesai import gui
from mesai.gui import app as app_module, rapor, widgets


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

def test_a_complete_folder_is_usable(tmp_path, settings):
    _touch(tmp_path, *COMPLETE)
    ok, lines = gui.describe_folder(tmp_path, settings)

    assert ok
    assert len(lines) == 3
    assert all(line.startswith("✓") for line in lines)


def test_mixed_containers_are_all_accepted(tmp_path, settings):
    """July arrived as .xls, May as .xlsx — the window must accept either."""
    _touch(tmp_path, "Macunkoy Mayis Mesai giris-cikis.xlsx",
           "Teknopark - Mayis Mesai Takip Exceli.xls", "HCMT34_MAYIS_IZIN.xlsm")
    ok, _ = gui.describe_folder(tmp_path, settings)
    assert ok


def test_every_missing_source_is_named_not_just_the_first(tmp_path, settings):
    _touch(tmp_path, "Teknopark - Temmuz Mesai Takip Exceli.xlsx")
    ok, lines = gui.describe_folder(tmp_path, settings)

    assert not ok
    missing = [line for line in lines if line.startswith("✗")]
    assert len(missing) == 2, "both absent files must be listed"
    assert any("Macunköy" in line for line in missing)
    assert any("İzin" in line for line in missing)


def test_two_files_for_one_source_is_refused(tmp_path, settings):
    """Two months in one folder is the ADR-014 mistake; catch it before the run."""
    _touch(tmp_path, *COMPLETE, "Macunköy Haziran Mesai giriş-çıkış.xlsx")
    ok, lines = gui.describe_folder(tmp_path, settings)

    assert not ok
    assert any("2 dosya eşleşti" in line for line in lines)


def test_an_unset_or_missing_folder_is_not_usable(tmp_path, settings):
    ok, lines = gui.describe_folder(None, settings)
    assert not ok and "seçilmedi" in lines[0]

    ok, _ = gui.describe_folder(tmp_path / "olmayan", settings)
    assert not ok


def test_the_folder_report_never_leaks_a_full_path(tmp_path, settings):
    """Only file names — a folder note showing full paths gets unreadable fast."""
    _touch(tmp_path, *COMPLETE)
    _, lines = gui.describe_folder(tmp_path, settings)
    assert not any(str(tmp_path) in line for line in lines)


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
    assert saved == {"browse_dir": str(share)}
    assert "07 - 2026" not in saved.get("browse_dir", ""), "month must not be stored"


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
    window._write_note(describe_folder_lines(folder, settings), problem=True)

    colours = [str(label.cget("foreground"))
               for label in window.folder_note.winfo_children()]
    assert colours.count(widgets.OK) == 2, "both found files keep the found colour"
    assert colours.count(widgets.BAD) == 1, "only the missing one is a problem"


def describe_folder_lines(folder, settings):
    _ok, lines = gui.describe_folder(folder, settings)
    return lines


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
