"""Entry point for the frozen `.exe`, and nothing else.

**Why this file exists rather than pointing PyInstaller at `mesai/gui/__main__.py`.**
That module is what `python -m mesai.gui` runs, so it imports with `from .app import
main` — correct there, because `-m` gives it a package context. PyInstaller runs its
entry script as a top-level `__main__` with no package, and a relative import then fails
at the first line:

    ImportError: attempted relative import with no known parent package

Which it did, on the first build. With `console=False` that surfaces as a traceback
dialog rather than a silent nothing, so it was visible — but on the operator's machine it
would have been a wall of English about relative imports, and the program would never
have opened. Hence a launcher whose imports are absolute.

Nothing else belongs here. `main()` is in `gui/app.py`; this file is a shim for the
packager and must stay small enough to have nothing to go wrong in.
"""

from mesai.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
