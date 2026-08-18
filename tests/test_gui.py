"""The window's pure helpers.

Only the logic is tested here, not the widgets: the window is a thin shell over
`pipeline.run()` by design, so the parts worth testing are the ones that decide what
it tells the user. Building a real `Tk` needs a display and would test tkinter rather
than this project.

`describe_folder` is the one that earns its keep. The user picks a folder by hand, and
what they need to know — before pressing anything — is which of the three exports were
found. Reporting only the first failure would hide the other two.
"""

from pathlib import Path

from mesai import gui


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


# --- period detection -------------------------------------------------------

def test_the_period_is_read_off_the_folder_name(tmp_path):
    assert gui.guess_period(Path("data/raw/2026-07")) == "2026-07"
    assert gui.guess_period(Path("G:/IK/Mesai/2026-7")) == "2026-07", "pads the month"


def test_the_parent_folder_is_the_fallback(tmp_path):
    assert gui.guess_period(Path("data/raw/2026-05/girdi")) == "2026-05"


def test_an_unrecognisable_folder_yields_no_guess(tmp_path):
    """Better to leave the field empty than to guess wrong — the user cannot tell."""
    assert gui.guess_period(Path("C:/Temp/Mesai")) is None
    assert gui.guess_period(Path("data/raw/2026-13")) is None, "month out of range"
    assert gui.guess_period(Path("data/raw/26-07")) is None, "year not four digits"


# --- labels -----------------------------------------------------------------

def test_the_period_label_is_turkish(tmp_path):
    assert gui.period_label("2026-07") == "Temmuz 2026"
    assert gui.period_label("2026-01") == "Ocak 2026"
    assert gui.period_label("2026-12") == "Aralık 2026"
