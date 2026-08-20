"""Editing the holiday list must not cost the file's own explanation of itself.

`config/takvim-<yıl>.yaml` is the one config file the window writes back to, and it
carries the note saying what depends on it. That note has already been wrong once
(ADR-040), which is exactly why a round-trip may not delete it.

The file is a **list of dates**. It used to be a `{date: name}` map, and briefly had a
second map for the company's own closures; both shapes are still read so that an
existing calendar is not silently emptied (ADR-045).
"""

from datetime import date

import pytest

from mesai import takvim_file

SAMPLE = '''# Bir yorum, dosyanın kendisi hakkında.
#
# İkinci satır.

weekly_rest_days: [saturday, sunday]

holidays:
  # Blok hakkında bir yorum.
  - 2026-05-01
  - 2026-07-15
'''


@pytest.fixture
def calendar(tmp_path):
    path = tmp_path / "takvim-2026.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


# --- reading ----------------------------------------------------------------

def test_the_dates_are_read(calendar):
    assert takvim_file.read(calendar) == {date(2026, 5, 1), date(2026, 7, 15)}


def test_a_missing_file_reads_as_empty(tmp_path):
    assert takvim_file.read(tmp_path / "yok.yaml") == set()


def test_the_older_named_shape_is_still_read(tmp_path):
    """`2026-05-01: "Emek ve Dayanışma Günü"` — what the file looked like before.

    A calendar written by an earlier version must not read as empty, which would
    silently turn every holiday back into a working day.
    """
    path = tmp_path / "takvim-2026.yaml"
    path.write_text('''weekly_rest_days: [saturday, sunday]

holidays:
  2026-05-01: "Emek ve Dayanışma Günü"
  2026-07-15: "Demokrasi ve Millî Birlik Günü"    # INFERRED
''', encoding="utf-8")

    assert takvim_file.read(path) == {date(2026, 5, 1), date(2026, 7, 15)}


def test_the_retired_second_block_is_folded_in(tmp_path):
    """`admin_holidays` existed for one commit (ADR-042, undone by ADR-043)."""
    path = tmp_path / "takvim-2026.yaml"
    path.write_text(SAMPLE + '''
admin_holidays:
  2026-08-10: "İdari tatil"
''', encoding="utf-8")

    assert date(2026, 8, 10) in takvim_file.read(path)


def test_a_retired_block_is_removed_on_the_next_save(tmp_path):
    """Left standing, the same day would sit in two places — and un-marking it would
    bring it back from the one nothing writes any more."""
    path = tmp_path / "takvim-2026.yaml"
    path.write_text(SAMPLE + '''
admin_holidays:
  2026-08-10: "İdari tatil"
''', encoding="utf-8")

    takvim_file.write(path, takvim_file.read(path))

    assert "admin_holidays" not in path.read_text(encoding="utf-8")
    assert date(2026, 8, 10) in takvim_file.read(path), "folded in, not dropped"


# --- writing ----------------------------------------------------------------

def test_every_comment_survives_a_round_trip(calendar):
    takvim_file.write(calendar, takvim_file.read(calendar) | {date(2026, 8, 30)})

    text = calendar.read_text(encoding="utf-8")
    assert "# Bir yorum, dosyanın kendisi hakkında." in text
    assert "# İkinci satır." in text
    assert "# Blok hakkında bir yorum." in text
    assert "weekly_rest_days: [saturday, sunday]" in text


def test_what_was_written_is_what_reads_back(calendar):
    days = takvim_file.read(calendar) | {date(2026, 8, 30), date(2026, 8, 10)}
    takvim_file.write(calendar, days)

    assert takvim_file.read(calendar) == days


def test_a_file_without_the_block_gets_one(tmp_path):
    path = tmp_path / "takvim-2026.yaml"
    path.write_text("weekly_rest_days: [saturday, sunday]\n", encoding="utf-8")

    takvim_file.write(path, {date(2026, 8, 10)})

    text = path.read_text(encoding="utf-8")
    assert "holidays:" in text
    assert "weekly_rest_days: [saturday, sunday]" in text
    assert takvim_file.read(path) == {date(2026, 8, 10)}


def test_a_removed_day_is_gone_from_the_file(calendar):
    takvim_file.write(calendar, takvim_file.read(calendar) - {date(2026, 5, 1)})

    text = calendar.read_text(encoding="utf-8")
    assert "2026-05-01" not in text
    assert "2026-07-15" in text, "the others stay"
    assert "# Blok hakkında bir yorum." in text, "and so does the comment"


def test_the_dates_come_out_in_order(calendar):
    takvim_file.write(calendar, takvim_file.read(calendar)
                      | {date(2026, 1, 1), date(2026, 10, 29), date(2026, 4, 23)})

    written = [line.strip("- ").strip()
               for line in calendar.read_text(encoding="utf-8").splitlines()
               if line.strip().startswith("- 2026-")]
    assert written == sorted(written)
    assert len(written) == 5


def test_emptying_the_list_leaves_the_heading_and_the_comments(calendar):
    takvim_file.write(calendar, set())

    text = calendar.read_text(encoding="utf-8")
    assert "holidays:" in text
    assert "# Blok hakkında bir yorum." in text
    assert "2026-05-01" not in text
    assert takvim_file.read(calendar) == set()


def test_a_comment_above_one_date_stays_above_that_date(tmp_path):
    """A note explaining a single day travels with it, and goes when it goes."""
    path = tmp_path / "takvim-2026.yaml"
    path.write_text('''holidays:
  # blok notu
  - 2026-05-01
  # bu gun veriden cikarildi
  - 2026-05-25
''', encoding="utf-8")

    takvim_file.write(path, takvim_file.read(path) | {date(2026, 12, 1)})
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines.index("# bu gun veriden cikarildi") == lines.index("- 2026-05-25") - 1
    assert lines.index("# blok notu") < lines.index("- 2026-05-01")

    takvim_file.write(path, takvim_file.read(path) - {date(2026, 5, 25)})
    text = path.read_text(encoding="utf-8")
    assert "# bu gun veriden cikarildi" not in text, "the note went with its day"
    assert "# blok notu" in text, "the block's own note did not"


def test_something_other_than_a_date_set_is_refused(calendar):
    before = calendar.read_text(encoding="utf-8")
    with pytest.raises(takvim_file.CalendarFileError):
        takvim_file.write(calendar, {date(2026, 8, 10): "Tatil"})
    assert calendar.read_text(encoding="utf-8") == before


def test_the_real_config_survives_a_round_trip_unchanged():
    """The shipped file, rewritten with what it already contains, must not move.

    The strongest available check: it is the file with the most comments and the most
    structure, and a rewrite that changes nothing is the definition of a safe editor.
    """
    import shutil
    import tempfile
    from pathlib import Path

    real = Path("config/takvim-2026.yaml")
    if not real.is_file():                       # pragma: no cover - fresh clone
        pytest.skip("config/takvim-2026.yaml yok")
    before = real.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "takvim-2026.yaml"
        shutil.copy(real, copy)
        takvim_file.write(copy, takvim_file.read(copy))
        after = copy.read_text(encoding="utf-8")

    assert after == before, "kendi icerigiyle yeniden yazmak dosyayi degistirmemeli"
