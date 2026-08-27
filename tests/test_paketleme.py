"""Guards on the `.exe` build recipe.

These are string tests over `MesaiTakip.spec`, `baslat.py` and `derle.cmd`, which is
weaker than exercising a build — a real one takes half a minute and needs PyInstaller
installed. They exist because every one of them encodes a mistake that actually shipped
a broken folder, and each was only visible by launching the exe:

* the entry point had a relative import and died on line one,
* `config/` went inside `_internal/` where the program does not look,
* two files that must never be distributed were excluded by a glob that happened to
  miss them.

A test that would have gone red on any of those is worth more than its shape suggests.
"""

from pathlib import Path

import pytest

SPEC = Path("MesaiTakip.spec")
BASLAT = Path("baslat.py")
DERLE = Path("derle.cmd")

# Real name spellings and a login. Neither may leave this machine inside a zip.
GIZLI = ("personel.yaml", "gmail.yaml")


@pytest.fixture(scope="module")
def spec():
    """The spec with comment lines removed.

    The comments explain each of these bugs at length and name the wrong file while
    doing it, so a substring check over the raw text tests the prose rather than the
    recipe.
    """
    return chr(10).join(
        line for line in SPEC.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))


def test_the_build_files_exist():
    for path in (SPEC, BASLAT, DERLE):
        assert path.is_file(), f"{path} yok — paketleme tarifi eksik"


def test_the_entry_point_has_no_relative_import():
    """The first build died here: `ImportError: attempted relative import with no known
    parent package`.

    PyInstaller runs its entry script as a top-level `__main__` with no package, so
    `from .app import main` cannot work. `mesai/gui/__main__.py` keeps its relative
    import because `python -m mesai.gui` gives it one; `baslat.py` exists to be the
    frozen entry and must stay absolute.
    """
    text = BASLAT.read_text(encoding="utf-8")
    kod = [line for line in text.splitlines()
           if line.strip().startswith(("import ", "from "))]

    assert kod, "baslat.py hiçbir şey import etmiyor"
    for line in kod:
        assert not line.strip().startswith("from ."), line
    assert any("from mesai.gui import main" in line for line in kod), kod


def test_the_spec_uses_the_launcher_and_not_the_module(spec):
    """Pointing it back at `__main__.py` reintroduces the first bug silently: the build
    still succeeds."""
    assert '"baslat.py"' in spec
    assert "gui/__main__.py" not in spec


def test_the_spec_carries_no_data_files(spec):
    """`config/` and `KULLANIM.txt` must NOT be in `datas`.

    PyInstaller 6 puts everything in `datas` under `_internal/`, and `cli.program_dir`
    looks for `config/` beside the executable. A copy in `_internal/` is both in the
    wrong place and somewhere the operator must never be sent. `derle.cmd` copies them.
    """
    assert "datas=[]" in spec.replace(" ", "")


def test_the_build_script_copies_config_next_to_the_exe():
    text = DERLE.read_text(encoding="utf-8", errors="replace")
    assert "dist\\MesaiTakip\\config" in text
    assert "KULLANIM.txt" in text


def test_the_build_script_excludes_the_two_files_that_must_not_ship():
    """By name, not by a glob that happens to miss them.

    An exclusion that works by accident stops working the day somebody adds a file to
    `config/`, and the failure is a zip with real employee names or a live credential
    in it — handed to somebody, over e-mail, unrecoverably.
    """
    text = DERLE.read_text(encoding="utf-8", errors="replace")
    for name in GIZLI:
        assert name in text, f"{name} derle.cmd'de dışlanmıyor"


def test_the_two_secret_files_are_git_ignored():
    """The same two files, the same reason, the other direction."""
    ignore = Path(".gitignore").read_text(encoding="utf-8")
    for name in GIZLI:
        assert f"config/{name}" in ignore, name
    assert "dist/" in ignore, "derleme çıktısı gerçek config taşıyabilir"


def test_the_window_is_built_without_a_console(spec):
    """A black terminal behind the window reads as a fault to somebody who does not know
    what a terminal is."""
    assert "console=False" in spec.replace(" ", "")


def test_upx_is_off(spec):
    """Compression is a common antivirus trigger and the saving is irrelevant here."""
    assert "upx=True" not in spec.replace(" ", "")


def test_the_lazily_imported_reader_is_a_hidden_import(spec):
    """`xlrd` is imported inside `readers/base.py` only when a `.xls` turns up.

    So the import scan can miss it and the build still looks fine — until the month the
    Macunköy export arrives as `.xls`, which has happened once already (ADR-020). On the
    operator's machine that is a failed run at month end with no way to fix it locally.
    """
    assert "xlrd" in spec


def test_the_build_script_removes_this_machines_settings():
    """`arayuz-ayarlari.json` is written next to the exe, so testing the build creates it.

    It holds this machine's paths — the Desktop, a network drive, the chosen roster file —
    and none of them exist on the target machine; `roster_file` in particular lands the
    new install straight in "seçilen dosya artık yok". It also carries
    `problem_notes_off`, which is one operator's setup choice and not a default anybody
    else should inherit silently.

    Nothing about it is secret. It is simply the wrong machine's state, and it ships by
    accident rather than by decision — which is why the assembly step deletes it rather
    than relying on nobody having launched the exe.
    """
    text = DERLE.read_text(encoding="utf-8", errors="replace")
    assert "arayuz-ayarlari.json" in text
    assert "del " in text, "silinmesi gerekiyor, sadece anilmasi degil"
