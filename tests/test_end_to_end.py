"""One whole month, from four synthetic workbooks to a report and a snapshot.

**Why this file exists.** Until it was written, nothing in the suite called
`pipeline.run()`. Every stage was unit-tested and every reader had fixture tests, but
the assembled pipeline was only ever verified by a human running it against the real
`data/` folder — which is git-ignored, so no automated run could ever do it. That made
the one question that matters ("does the whole thing still work?") depend on somebody
remembering to check.

The figures below are hand-computed, and the input is deliberately unpleasant: a
missing punch, a night shift crossing midnight, a person in both sites on the same day,
a remote-work day that collides with the nominal timesheet placeholder, and a short day.
Those are the five shapes that produced real bugs.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import openpyxl
import pytest

from mesai import config, snapshot
from mesai.pipeline import run
from mesai.rules.worktime import hhmm
from tests.builders import (
    izin_row, mac_row, roster_row, tek_block, tek_day, write_izin, write_macunkoy,
    write_roster, write_teknopark,
)

PERIOD = "2026-06"


@pytest.fixture
def month(tmp_path):
    """Build a complete month of input and return the folders to run against."""
    raw = tmp_path / "raw"
    roster_dir = tmp_path / "personel"
    raw.mkdir()
    roster_dir.mkdir()

    write_roster(roster_dir / "calisan_listesi.xlsx", [
        roster_row("adeneme", "1001", "AYŞE", "DENEME", "ayse@example.com"),
        roster_row("vornek", "1002", "VELİ", "ÖRNEK", "veli@example.com",
                   facility="MACUNKÖY TESİSİ"),
        roster_row("ztaslak", "1003", "ZEYNEP", "TASLAK", "zeynep@example.com"),
    ])

    # AYŞE: a clean Teknopark day, plus a Macunköy site visit inside it (ADR-001).
    # VELİ: a night shift the source records with a negative duration (D2), and a
    #       day whose exit is missing and cannot be repaired (ADR-003).
    # ZEYNEP: a two-hour day, under the short-day threshold (ADR-019).
    write_macunkoy(raw / "Macunköy Haziran Mesai giriş-çıkış.xlsx", [
        mac_row("AYŞE", "DENEME", "1001", "2026-06-01", "13:20", "14:05", "0:45"),
        mac_row("VELİ", "ÖRNEK", "1002", "2026-06-02", "23:00", "02:00", "-21:00"),
        mac_row("VELİ", "ÖRNEK", "1002", "2026-06-03", "08:00", None, None),
        mac_row("ZEYNEP", "TASLAK", "1003", "2026-06-04", "09:00", "11:00", "2:00"),
        mac_row("ZİYARETÇİ7", "ZİYARETÇİ7", "SN9001", "2026-06-01",
                "08:00", "17:00", "9:00"),          # excluded, not an employee
    ])

    # AYŞE 08:00-17:00 on the 1st; her Macunköy visit falls inside it, so the union is
    # one interval. On the 5th she has the nominal 09:00-18:00 placeholder, the same
    # day she declared remote work (ADR-017, ADR-018).
    write_teknopark(raw / "Teknopark - Haziran Mesai Takip Exceli.xlsx", [
        tek_block("AYŞE DENEME", [
            tek_day("2026-06-01", "08:00", "17:00", "9:00"),
            tek_day("2026-06-05", "09:00", "18:00", "9:00"),
        ], row=3, col=1, total="18:00"),
    ])

    write_izin(raw / "HCMT34_HAZIRAN_IZIN.xlsx", [
        izin_row("1001", "AYŞE DENEME", None, None, None, None, None, 1.0),
        izin_row("1001", "AYŞE DENEME", "Uzaktan Çalışma", "05.06.2026", "07:30",
                 "05.06.2026", "16:30", 1.0),
        izin_row("1003", "ZEYNEP TASLAK", None, None, None, None, None, 1.0),
        izin_row("1003", "ZEYNEP TASLAK", "Yıllık İzin", "08.06.2026", "07:30",
                 "08.06.2026", "16:30", 1.0),
    ])
    return raw, roster_dir


@pytest.fixture
def result(month, tmp_path, settings):
    raw, roster_dir = month
    return run(raw, tmp_path / "out" / f"mesai-raporu-{PERIOD}.xlsx", PERIOD, settings,
               generated_at=__import__("datetime").datetime(2026, 7, 1, 9, 0),
               roster_dir=roster_dir,
               snapshot_path=tmp_path / "veri" / f"gonderim-{PERIOD}.json")


# --- the run produces both artifacts ---------------------------------------

def test_both_the_workbook_and_the_snapshot_are_written(result):
    assert result["output"].exists()
    assert result["snapshot"].exists()

    book = openpyxl.load_workbook(result["output"], read_only=True)
    assert book.sheetnames == ["Aylık Özet", "Günlük Detay", "Sorulacaklar",
                               "Şüpheli Kayıtlar", "İzin Özeti", "Kontrol"]


def test_the_reconciliation_invariant_holds(result):
    """The guard from AGENTS.md §3. If this fails, hours were lost or doubled."""
    book = openpyxl.load_workbook(result["output"], read_only=True)
    control = "\n".join(
        " | ".join(str(c) for c in row if c is not None)
        for row in book["Kontrol"].iter_rows(values_only=True))

    assert "Mutabakat | TAMAM" in control


# --- the five shapes that produced real bugs -------------------------------

def test_a_cross_site_day_is_counted_once(result):
    """AYŞE: Teknopark 08:00-17:00 with a Macunköy visit inside it. Nine hours, not
    nine plus forty-five minutes."""
    day = next(w for w in _workdays(result) if w[1] == "01.06.2026")
    assert day[6] == "9:00", f"got {day[6]}"


def test_a_midnight_crossing_is_repaired(result):
    """VELİ, 2nd: the source says -21:00 for a 23:00 -> 02:00 night shift."""
    day = next(w for w in _workdays(result) if w[1] == "02.06.2026")
    assert day[6] == "3:00"
    assert "gece-geçişi" in (day[9] or "")


def test_an_unrepairable_missing_punch_contributes_nothing(result):
    """VELİ, 3rd: entry only, no other site to reconcile against. ADR-003."""
    assert not [w for w in _workdays(result) if w[1] == "03.06.2026"]

    book = openpyxl.load_workbook(result["output"], read_only=True)
    anomalies = "\n".join(
        " | ".join(str(c) for c in row if c is not None)
        for row in book["Şüpheli Kayıtlar"].iter_rows(values_only=True))
    assert "Çıkış yok" in anomalies


def test_a_remote_day_overrides_the_nominal_placeholder(result):
    """AYŞE, 5th: declared 07:30-16:30, timesheet holds the 09:00-18:00 placeholder.

    ADR-018 — the declaration wins, so nine hours rather than 07:30->18:00 = 10:30.
    """
    day = next(w for w in _workdays(result) if w[1] == "05.06.2026")
    assert day[6] == "9:00", f"got {day[6]} — placeholder was not set aside"


def test_a_short_day_is_flagged_but_still_counted(result):
    """ZEYNEP, 4th: two hours exactly is NOT under the threshold, so no flag."""
    day = next(w for w in _workdays(result) if w[1] == "04.06.2026")
    assert day[6] == "2:00"
    assert "kısa-gün" not in (day[9] or ""), "exactly 2:00 must not flag"


def test_a_visitor_badge_never_reaches_the_summary(result):
    book = openpyxl.load_workbook(result["output"], read_only=True)
    names = [row[0] for row in book["Aylık Özet"].iter_rows(values_only=True)
             if row[0]]
    assert not any("ZİYARETÇİ" in str(name) for name in names)


# --- the monthly total, computed by hand -----------------------------------

def test_the_monthly_total_is_the_hand_computed_figure(result):
    """9:00 + 3:00 + 2:00 + 9:00 = 23:00.

    AYŞE 1st 9:00 and 5th 9:00; VELİ 2nd 3:00 (3rd contributes nothing);
    ZEYNEP 4th 2:00. No break deduction (ADR-016), no in-day gaps.
    """
    assert hhmm(result["gross"]) == "23:00"


def test_the_snapshot_agrees_with_the_workbook(result):
    """Both artifacts come from one run; a divergence here means they can disagree."""
    loaded = snapshot.load(result["snapshot"])
    total = sum((p.minutes for p in loaded.people), 0)

    assert total == int(result["gross"].total_seconds() // 60)
    assert loaded.period == PERIOD


def test_a_month_holding_only_its_first_week_is_reported_incomplete(result):
    """ADR-020, end to end.

    This fixture deliberately stops on the 5th while June has 22 expected working
    days, which is the July 2026 situation in miniature: internally consistent files
    describing part of a month. The first version of this test asserted the opposite
    and failed — the guard was right and the assumption was wrong.
    """
    loaded = snapshot.load(result["snapshot"])
    assert not loaded.is_complete

    partial = result["partial_sources"]
    assert partial, "a source stopping mid-month must be reported"
    assert {c.source for c in partial} == {"macunkoy", "teknopark"}
    assert all(c.trailing_missing for c in partial)

    book = openpyxl.load_workbook(result["output"], read_only=True)
    summary = "\n".join(
        " ".join(str(c) for c in row if c is not None)
        for row in book["Aylık Özet"].iter_rows(values_only=True))
    assert "BU RAPOR EKSİK" in summary, "the deliverable sheet must say so"


def test_the_snapshot_carries_emails_the_workbook_omits(result):
    """The mail step's whole reason for reading the snapshot instead. ADR-021."""
    loaded = snapshot.load(result["snapshot"])
    ayse = next(p for p in loaded.people if p.name == "AYŞE DENEME")
    assert ayse.email == "ayse@example.com"

    book = openpyxl.load_workbook(result["output"], read_only=True)
    everything = "\n".join(
        " ".join(str(c) for c in row if c is not None)
        for sheet in book.worksheets for row in sheet.iter_rows(values_only=True))
    assert "ayse@example.com" not in everything


def test_a_person_with_leave_but_no_attendance_is_reported_as_such(result):
    """ZEYNEP has leave on the 8th and worked the 4th; nobody here is data-less, so the
    snapshot must not invent a 'no data' person."""
    loaded = snapshot.load(result["snapshot"])
    assert {p.name for p in loaded.people} == {
        "AYŞE DENEME", "VELİ ÖRNEK", "ZEYNEP TASLAK"}
    assert all(p.has_attendance for p in loaded.people)


# --- determinism ------------------------------------------------------------

def test_two_runs_produce_identical_figures(month, tmp_path, settings):
    """ADR-005. The generation timestamp is the only thing allowed to differ."""
    raw, roster_dir = month
    import datetime as _dt

    def once(tag):
        out = run(raw, tmp_path / tag / f"r-{PERIOD}.xlsx", PERIOD, settings,
                  generated_at=_dt.datetime(2026, 7, 1, 9, 0), roster_dir=roster_dir,
                  snapshot_path=tmp_path / tag / "s.json")
        payload = json.loads(out["snapshot"].read_text(encoding="utf-8"))
        return out["gross"], payload

    first_gross, first_snap = once("a")
    second_gross, second_snap = once("b")

    assert first_gross == second_gross
    assert first_snap == second_snap


# --- helpers ----------------------------------------------------------------

def _workdays(result) -> list[tuple]:
    """Data rows of the Günlük Detay sheet."""
    book = openpyxl.load_workbook(result["output"], read_only=True)
    rows = list(book["Günlük Detay"].iter_rows(values_only=True))
    header = next(i for i, row in enumerate(rows) if row[0] == "Ad Soyad")
    return [row for row in rows[header + 1:]
            if row[0] and not str(row[0]).startswith(("Oluşturulma", "Kaynak", "Bu "))]
