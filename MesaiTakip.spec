import sys
from pathlib import Path

# PyInstaller build recipe. Run it with:
#
#     conda activate mesai
#     pyinstaller MesaiTakip.spec --noconfirm
#
# Output: dist/MesaiTakip/ — a folder holding MesaiTakip.exe and everything it needs.
#
# --- Why a folder and not a single file ------------------------------------
#
# `--onefile` unpacks the whole program into a temp directory on every launch. For a
# tkinter application that is a three-to-eight second wait before the window appears,
# every time, and antivirus software treats self-extracting behaviour with more
# suspicion than a plain folder. The folder starts in about a second.
#
# The cost is that MesaiTakip.exe must stay inside its folder — it needs the files
# beside it. `KULLANIM.txt` says so twice.
#
# --- What is NOT inside the executable ------------------------------------
#
# `config/` is deliberately left out and shipped next to the exe:
#
#   * a rule change must be a YAML edit, never a rebuild (AGENTS §6),
#   * the calendar screen WRITES to `config/takvim-<yıl>.yaml` (ADR-042), so it has to
#     be a real writable file rather than a read-only copy inside an archive,
#   * `gmail.yaml` holds a credential, which has to be rotatable without a rebuild,
#   * `mail-taslagi.yaml` is the message wording, which is expected to change (ADR-078).
#
# `derle.cmd` copies `config/` next to the exe as a starting point, minus the two files
# that must never be distributed: `personel.yaml` (real name spellings) and `gmail.yaml`
# (a login). The example files ship instead, and whoever installs it copies the real
# ones across by hand — the same manual step a fresh clone already needs.
#
# `data/` is never packaged. It holds personal data and it is the operator's, not the
# program's.

# `config/` and `KULLANIM.txt` are NOT listed here.
#
# PyInstaller 6 puts everything in `datas` under `_internal/`, and the program looks for
# `config/` beside the executable (`cli.program_dir`, which resolves to
# `Path(sys.executable).parent` when frozen). A copy inside `_internal/` would be both
# in the wrong place and somewhere the operator must never be told to open.
#
# So `derle.cmd` copies them next to the exe after the build. The spec builds the
# program; the script assembles the thing you hand over.

# The entry point is `baslat.py`, NOT `src/mesai/gui/__main__.py`. That module is what
# `python -m mesai.gui` runs, so its imports are relative — which PyInstaller cannot
# honour, because a frozen entry script is a top-level `__main__` with no package. The
# first build died on exactly that. See the docstring in `baslat.py`.

# --- The conda DLL problem, solved once ------------------------------------
#
# CPython's extension modules (`_tkinter.pyd`, `pyexpat.pyd`, `_ssl.pyd`, ...) link
# against native libraries. In a normal CPython install those sit in `DLLs/` and
# PyInstaller's scan finds them. In a **conda** environment they are in `Library/bin/`,
# which the scan does not look in — so the build succeeds and the exe dies on launch.
#
# It died three times, each on a different one, each only visible by actually running it:
#
#   1. `ImportError: DLL load failed while importing _tkinter`   -> tcl86t, tk86t
#   2. `ImportError: DLL load failed while importing pyexpat`    -> libexpat (openpyxl)
#   3. and `libssl` / `libcrypto` were still missing, which would NOT have shown up at
#      startup at all — SMTP over TLS needs them, so the first symptom would have been
#      a failed send, in front of somebody, after the report looked fine.
#
# So this is resolved rather than listed. Every `.pyd` the interpreter ships plus
# `python3*.dll` is read with `pefile` (which PyInstaller already depends on), its import
# table walked, and anything named that exists in `Library/bin` is carried — transitively,
# because those libraries depend on each other (`libssl` needs `libcrypto`, Tk needs the
# CRT stubs). 26 files on this environment, ~16 MB, and the list maintains itself when the
# environment changes instead of rotting into a stale hard-coded set.
#
# `zlib.dll` and `zlib1.dll` are both here and that is correct: they are different files
# with different dependents, and dropping one because the names look alike is the kind of
# tidying that produces a broken build a month later.
try:
    import pefile
except ImportError:                     # pragma: no cover - build-time only
    raise SystemExit("HATA: pefile bulunamadi. PyInstaller ile birlikte kurulur:"
                     "\n    pip install pyinstaller")


def _dll_imports(path):
    """The DLL names one binary imports. Names only — resolution is the caller's."""
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    found = {entry.dll.decode("ascii", "replace").lower()
             for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []}
    pe.close()
    return found


def _conda_binaries():
    prefix = Path(sys.prefix)
    pool = {p.name.lower(): p for p in (prefix / "Library" / "bin").glob("*.dll")}
    if not pool:
        # Not conda, or laid out differently. PyInstaller's own scan is then probably
        # enough — but say so, because a silently empty list is how this bug got here.
        print("UYARI: Library/bin altinda DLL bulunamadi. Conda ortami degilse normal;"
              " degilse uretilen exe acilmayabilir.")
        return []

    roots = list((prefix / "DLLs").glob("*.pyd")) + list(prefix.glob("python3*.dll"))
    needed, queue, seen = {}, list(roots), set()
    while queue:
        current = queue.pop()
        key = str(current).lower()
        if key in seen:
            continue
        seen.add(key)
        for name in _dll_imports(current):
            if name in pool and name not in needed:
                needed[name] = pool[name]
                queue.append(pool[name])
    print(f"conda Library/bin: {len(needed)} DLL pakete eklendi")
    return [(str(path), ".") for path in needed.values()]


binaries = _conda_binaries()

a = Analysis(
    ["baslat.py"],
    pathex=["src"],
    binaries=binaries,
    datas=[],
    # openpyxl and xlrd are pure Python and found by the import scan; yaml too. Listed
    # anyway because the failure mode is invisible until a month arrives in the other
    # container format: `xlrd` is only imported inside `readers/base.py` when a `.xls`
    # turns up, which is exactly the case that broke once already (ADR-020) and would
    # break again on a machine where the scan had dropped it.
    hiddenimports=["xlrd", "openpyxl", "yaml"],
    hookspath=[],
    runtime_hooks=[],
    # Nothing here needs them and they cost tens of megabytes. Not a guess: the project
    # has no numeric or plotting dependency at all (`pyproject.toml`), so anything the
    # scan drags in from the conda environment is an accident of what else is installed.
    excludes=["numpy", "pandas", "matplotlib", "scipy", "PIL", "IPython",
              "pytest", "PyInstaller", "setuptools", "pip"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MesaiTakip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX compression is a common antivirus trigger. Not worth it.
    # No console window. The window is the interface, and a black terminal appearing
    # behind it looks like something went wrong to somebody who does not know what a
    # terminal is. The CLI is a separate entry point and is not shipped here.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MesaiTakip",
)
