"""Desktop window over the same `pipeline.run()` the CLI calls.

The person who runs this monthly does not use a terminal, so "open a console and pass
--ay" is not a deliverable. This package exists to remove that requirement and nothing
else: **it contains no business logic.** `ARCHITECTURE.md` §3 anticipated this —
`pipeline.py` was split out from `cli.py` precisely so a second front end could drive
the same run.

It was a single 662-line module until the e-mail step came into view. Split now rather
than later because the growth is all in one direction — a second work face, a list of
people, a selection state — and adding that to the class that already owns the report
run would have produced one object with two jobs.

| Module | What lives there |
| --- | --- |
| `app.py` | the toplevel window, the header band, `main()` |
| `rapor.py` | the report screen: folder, per-source files, period, the run, result |
| `period.py` | reading and writing a month (`07-2026` → `2026-07` → `Temmuz 2026`) |
| `widgets.py` | palette, buttons, captions — the vocabulary every screen shares |

`rapor.py` keeps the Turkish name the handover gave it; `report.py` would have read as
a sibling of `mesai.report`, the package that writes the workbook, which it is not.

Nothing here should ever start computing on its own. When the selection logic for
e-mail arrives it belongs in its own module outside this package — "who falls into
this category, minus these people" is a business rule, and the same convention that
keeps `cli.py` to argument parsing applies to the window.
"""

from .app import App, main
from .period import guess_period, parse_period, period_label
from .rapor import ReportScreen, SourceState, inspect_sources

__all__ = ["App", "ReportScreen", "SourceState", "guess_period", "inspect_sources",
           "main", "parse_period", "period_label"]
