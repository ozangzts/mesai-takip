"""Editing the calendar file must not cost the file's own explanation of itself.

`config/takvim-<yıl>.yaml` is the one config file the window writes back to, and it
carries the notes saying which dates were inferred, which came from law, and what
depends on the file. That last note has already been wrong once (ADR-040), which is
exactly why a round-trip may not delete it.
"""

from datetime import date

import pytest

from mesai import takvim_file

SAMPLE = '''# Public holidays and weekly rest days.
#
# STATUS: the 2026-05 entries were INFERRED from the data.

weekly_rest_days: [saturday, sunday]

holidays:
  # Fixed-date statutory holidays, listed for the whole year.
  2026-05-01: "Emek ve Dayanışma Günü"
  2026-07-15: "Demokrasi ve Millî Birlik Günü"

half_days:
  - 2026-05-26
'''


@pytest.fixture
def calendar(tmp_path):
    path = tmp_path / "takvim-2026.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


# --- reading ----------------------------------------------------------------

def test_the_dates_are_read_with_their_labels(calendar):
    blocks = takvim_file.read(calendar)

    assert blocks[takvim_file.HOLIDAYS] == {
        date(2026, 5, 1): "Emek ve Dayanışma Günü",
        date(2026, 7, 15): "Demokrasi ve Millî Birlik Günü",
    }


def test_a_missing_file_reads_as_empty(tmp_path):
    assert takvim_file.read(tmp_path / "yok.yaml") == {takvim_file.HOLIDAYS: {}}


def test_half_days_are_not_mistaken_for_a_date_block(calendar):
    """`half_days` is a list, not a mapping, and nothing here may touch it."""
    assert date(2026, 5, 26) not in takvim_file.read(calendar)[
        takvim_file.HOLIDAYS]


def test_a_retired_block_is_folded_in_rather_than_lost(tmp_path):
    """`admin_holidays` existed for one day (ADR-042, undone by ADR-043).

    A calendar written while it existed must not quietly lose those days, so the block
    is still read — and never written back.
    """
    path = tmp_path / "takvim-2026.yaml"
    path.write_text(SAMPLE + '''
admin_holidays:
  2026-08-10: "İdari tatil"
''', encoding="utf-8")

    blocks = takvim_file.read(path)
    assert date(2026, 8, 10) in blocks[takvim_file.HOLIDAYS]
    assert blocks[takvim_file.HOLIDAYS][date(2026, 8, 10)] == "İdari tatil"

    takvim_file.write(path, blocks)
    assert "admin_holidays" not in path.read_text(encoding="utf-8")
    assert date(2026, 8, 10) in takvim_file.read(path)[takvim_file.HOLIDAYS], \
        "folded into the one block, not dropped"


# --- writing ----------------------------------------------------------------

def test_every_comment_survives_a_round_trip(calendar):
    blocks = takvim_file.read(calendar)
    blocks[takvim_file.HOLIDAYS][date(2026, 8, 30)] = "Zafer Bayramı"
    takvim_file.write(calendar, blocks)

    text = calendar.read_text(encoding="utf-8")
    assert "# STATUS: the 2026-05 entries were INFERRED from the data." in text
    assert "# Public holidays and weekly rest days." in text
    assert "# Fixed-date statutory holidays, listed for the whole year." in text
    assert "weekly_rest_days: [saturday, sunday]" in text
    assert "half_days:" in text and "- 2026-05-26" in text


def test_what_was_written_is_what_reads_back(calendar):
    blocks = takvim_file.read(calendar)
    blocks[takvim_file.HOLIDAYS][date(2026, 8, 30)] = "Zafer Bayramı"
    blocks[takvim_file.HOLIDAYS][date(2026, 8, 10)] = "Tatil"
    takvim_file.write(calendar, blocks)

    assert takvim_file.read(calendar) == blocks


def test_a_block_the_file_lacks_is_appended_with_its_heading(tmp_path):
    path = tmp_path / "takvim-2026.yaml"
    path.write_text("weekly_rest_days: [saturday, sunday]\n", encoding="utf-8")

    takvim_file.write(path, {takvim_file.HOLIDAYS: {date(2026, 8, 10): "Tatil"}})

    text = path.read_text(encoding="utf-8")
    assert "holidays:" in text
    assert "weekly_rest_days: [saturday, sunday]" in text
    assert takvim_file.read(path)[takvim_file.HOLIDAYS] == {
        date(2026, 8, 10): "Tatil"}


def test_a_removed_day_is_gone_from_the_file(calendar):
    blocks = takvim_file.read(calendar)
    del blocks[takvim_file.HOLIDAYS][date(2026, 5, 1)]
    takvim_file.write(calendar, blocks)

    text = calendar.read_text(encoding="utf-8")
    assert "2026-05-01" not in text
    assert "2026-07-15" in text, "the others stay"
    assert "# Fixed-date statutory holidays" in text, "and so does the comment"


def test_the_dates_come_out_in_order(calendar):
    blocks = takvim_file.read(calendar)
    for day in (date(2026, 1, 1), date(2026, 10, 29), date(2026, 4, 23)):
        blocks[takvim_file.HOLIDAYS][day] = "Tatil"
    takvim_file.write(calendar, blocks)

    written = [line.strip().split(":")[0]
               for line in calendar.read_text(encoding="utf-8").splitlines()
               if line.startswith("  2026-")]
    assert written == sorted(written)


def test_emptying_a_block_leaves_the_heading_and_the_comments(calendar):
    blocks = takvim_file.read(calendar)
    blocks[takvim_file.HOLIDAYS] = {}
    takvim_file.write(calendar, blocks)

    text = calendar.read_text(encoding="utf-8")
    assert "holidays:" in text
    assert "# Fixed-date statutory holidays" in text
    assert "2026-05-01" not in text
    assert takvim_file.read(calendar)[takvim_file.HOLIDAYS] == {}


def test_a_quote_in_a_label_cannot_break_the_file(calendar):
    blocks = takvim_file.read(calendar)
    blocks[takvim_file.HOLIDAYS][date(2026, 8, 10)] = 'Kapalı "hafta"'
    takvim_file.write(calendar, blocks)

    assert takvim_file.read(calendar)[takvim_file.HOLIDAYS][date(2026, 8, 10)] == \
        "Kapalı 'hafta'"


def test_an_unknown_block_is_refused_before_anything_is_written(calendar):
    before = calendar.read_text(encoding="utf-8")
    with pytest.raises(takvim_file.CalendarFileError):
        takvim_file.write(calendar, {"tatiller": {date(2026, 8, 10): "x"}})
    assert calendar.read_text(encoding="utf-8") == before


def test_the_real_config_survives_a_round_trip_unchanged():
    """The shipped file, rewritten with what it already contains, must not move.

    The strongest available check: it is the file with the most comments, the most
    inline notes and the most structure, and a rewrite that changes nothing is the
    definition of a safe editor.
    """
    from pathlib import Path

    real = Path("config/takvim-2026.yaml")
    if not real.is_file():                       # pragma: no cover - fresh clone
        pytest.skip("config/takvim-2026.yaml yok")
    before = real.read_text(encoding="utf-8")

    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "takvim-2026.yaml"
        shutil.copy(real, copy)
        takvim_file.write(copy, takvim_file.read(copy))
        after = copy.read_text(encoding="utf-8")

    assert after == before, "kendi icerigiyle yeniden yazmak dosyayi degistirmemeli"
