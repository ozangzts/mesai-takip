"""The report writer actually writes.

This file exists because of a real bug: the report kept its own copy of the
severity -> impact-text mapping, so adding the `info` severity in `anomalies.py`
(ADR-017) made every month-end run die with `KeyError: 'info'` — while all 112 unit
tests stayed green, because none of them built a workbook.

These tests are deliberately shallow. They do not check business figures; the merge
and worktime suites do that. They check that a workbook can be produced from every
severity and every anomaly kind, so a change to that vocabulary cannot pass CI and
fail on real data.
"""

from datetime import date, datetime, timedelta

import openpyxl
import pytest

from mesai.anomalies import IMPACT_TEXT, Anomaly, AnomalyKind, Collector, DESCRIPTIONS
from mesai.models import (
    Employee, Interval, LeaveRecord, MonthSummary, RunStats, WorkDay,
)
from mesai.report import workbook

KEY = ("AYSE", "DENEME")
DAY = date(2026, 5, 21)


def _employee() -> Employee:
    return Employee(
        key=KEY, display_name="AYŞE DENEME", personnel_no="8801",
        department="TEST EKİBİ", job_title="TEST MÜHENDİSİ",
        facility="DEICO TESİS", in_roster=True, sources=frozenset({"teknopark"}),
    )


def _workday() -> WorkDay:
    intervals = (
        Interval(datetime(2026, 5, 21, 8, 21), datetime(2026, 5, 21, 13, 48),
                 frozenset({"teknopark"})),
        Interval(datetime(2026, 5, 21, 14, 30), datetime(2026, 5, 21, 18, 0),
                 frozenset({"teknopark"})),
    )
    return WorkDay(
        key=KEY, date=DAY, intervals=intervals,
        gross=timedelta(hours=9, minutes=39), break_deduction=timedelta(),
        net=timedelta(hours=9, minutes=39), tags=frozenset({"uzaktan"}),
    )


def _summary() -> MonthSummary:
    return MonthSummary(
        employee=_employee(), period="2026-05",
        gross=timedelta(hours=9, minutes=39), net=timedelta(hours=9, minutes=39),
        worked_days=1, remote_days=1.0, leave_days=0.5, anomaly_count=0,
        has_attendance=True,
    )


def _all_kinds() -> Collector:
    """One anomaly of every kind — so no kind can be unrenderable."""
    collector = Collector()
    for row, kind in enumerate(AnomalyKind, start=1):
        collector.add(Anomaly(
            kind=kind, source="teknopark", source_row=row, key=KEY,
            raw_name="AYŞE DENEME", date=DAY, raw_entry="08:00", raw_exit="17:00",
            detail="test",
        ))
    return collector


def _build(tmp_path, settings, anomalies=None, summaries=None, name="rapor.xlsx"):
    path = tmp_path / name
    workbook.build(
        path=path, period="2026-05",
        summaries=summaries if summaries is not None else [_summary()],
        workdays=[_workday()], employees={KEY: _employee()},
        leave=[LeaveRecord(
            key=KEY, raw_name="AYŞE DENEME", personnel_no="8801",
            leave_type="Yıllık İzin", status="Kullanıldı",
            start=datetime(2026, 5, 20, 7, 30), end=datetime(2026, 5, 20, 12, 0),
            days=0.5, department="TEST EKİBİ", source_row=3)],
        anomalies=anomalies if anomalies is not None else _all_kinds(),
        stats=RunStats(
            rows_read={"teknopark": 1}, records_built={"teknopark": 1},
            intervals_accepted=2, union_total=timedelta(hours=8, minutes=57),
            accepted_total=timedelta(hours=9, minutes=39),
            files={"teknopark": "test.xlsx"}, roster_date=date(2026, 7, 28)),
        settings=settings, generated_at=datetime(2026, 8, 17, 12, 0),
    )
    return path


def test_every_anomaly_kind_can_be_written(tmp_path, settings):
    """The KeyError this file was written for. Covers all kinds and all severities."""
    path = _build(tmp_path, settings)
    assert path.exists()

    book = openpyxl.load_workbook(path, read_only=True)
    assert book.sheetnames == ["Aylık Özet", "Günlük Detay", "Sorulacaklar",
                               "Şüpheli Kayıtlar", "İzin Özeti", "Kontrol"]


def test_every_severity_has_impact_text():
    """A kind whose severity has no impact text kills the run at report time."""
    for kind, (_, severity, _explanation, _group) in DESCRIPTIONS.items():
        assert severity in IMPACT_TEXT, f"{kind} has severity {severity!r}"


def test_every_anomaly_kind_is_described():
    for kind in AnomalyKind:
        assert kind in DESCRIPTIONS, f"{kind} would raise KeyError on .label"


def test_hours_columns_follow_the_break_switch(tmp_path, settings, settings_break):
    """ADR-016: one hours column pair with the deduction off, two with it on."""
    rows = openpyxl.load_workbook(_build(tmp_path, settings), read_only=True)
    headers = [c for c in list(rows["Aylık Özet"].iter_rows(values_only=True))[3]
               if c is not None]
    assert "Çalışma Süresi" in headers
    assert "Net Süre" not in headers

    book = openpyxl.load_workbook(
        _build(tmp_path, settings_break, name="eski-kural.xlsx"), read_only=True)
    headers = [c for c in list(book["Aylık Özet"].iter_rows(values_only=True))[3]
               if c is not None]
    assert "Brüt Süre" in headers and "Net Süre" in headers


def test_daily_sheet_shows_the_gap_that_the_envelope_pays(tmp_path, settings):
    book = openpyxl.load_workbook(_build(tmp_path, settings), read_only=True)
    rows = list(book["Günlük Detay"].iter_rows(values_only=True))
    headers = [c for c in rows[3] if c is not None]
    assert headers[6:8] == ["Çalışma Süresi", "Gün İçi Boşluk"]
    assert rows[4][6] == "9:39" and rows[4][7] == "0:42"


def test_the_rule_banner_names_the_active_rule(tmp_path, settings, settings_break):
    book = openpyxl.load_workbook(_build(tmp_path, settings), read_only=True)
    banner = list(book["Aylık Özet"].iter_rows(values_only=True))[2][0]
    assert "kesinti UYGULANMAZ" in banner
    assert "son çıkışına" in banner

    book = openpyxl.load_workbook(
        _build(tmp_path, settings_break, name="eski-kural.xlsx"), read_only=True)
    banner = list(book["Aylık Özet"].iter_rows(values_only=True))[2][0]
    assert "45 dk kesinti uygulanır" in banner


def test_locked_output_file_reports_a_readable_error(tmp_path, settings, monkeypatch):
    """It happens every month: HR leaves the workbook open in Excel."""
    def boom(*_args):
        raise PermissionError

    monkeypatch.setattr(workbook.os, "replace", boom)
    with pytest.raises(workbook.ReportLocked, match="kilitli"):
        _build(tmp_path, settings)


# --- partial-export banner (ADR-020) ---------------------------------------

def test_partial_coverage_puts_a_warning_above_the_table(tmp_path, settings):
    """The deliverable sheet must say so — a mid-month report looks normal otherwise."""
    from mesai.models import SourceCoverage
    stats = RunStats(
        rows_read={"teknopark": 1}, records_built={"teknopark": 1},
        intervals_accepted=2, union_total=timedelta(hours=8, minutes=57),
        accepted_total=timedelta(hours=9, minutes=39),
        files={"teknopark": "test.xlsx"}, roster_date=date(2026, 7, 28),
        coverage={"teknopark": SourceCoverage(
            source="teknopark", present=13, expected=23,
            trailing_missing=tuple(date(2026, 7, d) for d in (20, 21, 22)))},
    )
    path = tmp_path / "kismi.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=Collector(), stats=stats,
        settings=settings, generated_at=datetime(2026, 8, 18, 12, 0),
    )

    book = openpyxl.load_workbook(path, read_only=True)
    rows = list(book["Aylık Özet"].iter_rows(values_only=True))
    assert "BU RAPOR EKSİK" in str(rows[3][0])
    assert "20.07" in str(rows[3][0])
    # The table must have shifted down rather than been overwritten.
    assert rows[4][0] == "Ad Soyad"

    control = "\n".join(
        " ".join(str(c) for c in r if c is not None)
        for r in book["Kontrol"].iter_rows(values_only=True))
    assert "KISMİ DIŞA AKTARIM" in control
    assert "13 / 23" in control


def test_full_coverage_leaves_the_table_where_it_was(tmp_path, settings):
    from mesai.models import SourceCoverage
    stats = RunStats(
        files={"teknopark": "test.xlsx"},
        coverage={"teknopark": SourceCoverage("teknopark", 23, 23, ())},
    )
    path = tmp_path / "tam.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=Collector(), stats=stats,
        settings=settings, generated_at=datetime(2026, 8, 18, 12, 0),
    )

    book = openpyxl.load_workbook(path, read_only=True)
    rows = list(book["Aylık Özet"].iter_rows(values_only=True))
    assert rows[3][0] == "Ad Soyad", "no banner, header stays on row 4"
    control = "\n".join(
        " ".join(str(c) for c in r if c is not None)
        for r in book["Kontrol"].iter_rows(values_only=True))
    assert "Dönemin tamamı kapsanıyor" in control




def test_the_control_sheet_lists_only_this_month_s_holidays(tmp_path, settings):
    """July's report listed May's seven holidays under "assumptions behind the figures".

    The calendar file holds the whole year, so every month's report showed every
    month's holidays. Dates outside the period being reported on are not assumptions
    behind its figures; they are noise on the one sheet whose job is to be checkable.
    """
    from dataclasses import replace
    from datetime import date

    calendar = replace(
        settings.calendar,
        holidays=frozenset({date(2026, 5, 1), date(2026, 7, 15)}))
    path = tmp_path / "tatil.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=Collector(),
        stats=RunStats(files={"teknopark": "test.xlsx"}),
        settings=replace(settings, calendar=calendar),
        generated_at=datetime(2026, 8, 20, 12, 0),
    )

    control = "\n".join(
        " ".join(str(c) for c in r if c is not None)
        for r in openpyxl.load_workbook(path, read_only=True)["Kontrol"].iter_rows(
            values_only=True))
    assert "15.07.2026" in control, "the month's own holiday must be listed"
    assert "01.05.2026" not in control, "another month's must not"


def test_a_month_with_no_holiday_defined_says_so(tmp_path, settings):
    """Silence would read as "there were none", which is the mistake to avoid.

    Ramazan and Kurban Bayramı move every year and are entered by hand, so a month
    that has nothing in the calendar is exactly the case worth naming out loud.
    """
    from dataclasses import replace

    path = tmp_path / "tatilsiz.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=Collector(),
        stats=RunStats(files={"teknopark": "test.xlsx"}),
        settings=replace(settings,
                         calendar=replace(settings.calendar,
                                          holidays=frozenset())),
        generated_at=datetime(2026, 8, 20, 12, 0),
    )

    control = "\n".join(
        " ".join(str(c) for c in r if c is not None)
        for r in openpyxl.load_workbook(path, read_only=True)["Kontrol"].iter_rows(
            values_only=True))
    assert "işaretli gün yok" in control


def test_the_control_sheet_sections_are_numbered_once_each(tmp_path, settings):
    """Two sections were both numbered 9, and a doc pointed at the wrong one.

    The numbers are how everything else refers to this sheet — "section 7 lists every
    alias in effect" is the documented way to check that the alias table loaded at all.
    A duplicate makes such a reference ambiguous, and it was invisible because nothing
    read the numbers back.
    """
    import re

    path = tmp_path / "numaralar.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=Collector(),
        stats=RunStats(files={"teknopark": "test.xlsx"}), settings=settings,
        generated_at=datetime(2026, 8, 20, 12, 0),
    )

    book = openpyxl.load_workbook(path, read_only=True)
    numbers = [int(m.group(1)) for r in book["Kontrol"].iter_rows(values_only=True)
               if r and r[0] and (m := re.match(r"^(\d+)\. ", str(r[0])))]

    assert numbers, "the sheet must have numbered sections at all"
    assert numbers == sorted(set(numbers)), f"repeated or out of order: {numbers}"
    assert numbers == list(range(1, len(numbers) + 1)), f"a gap: {numbers}"


# --- the workbook is for HR, not for developers -----------------------------

_DEVELOPER_JARGON = (
    "ADR-", "ROADMAP", "DOMAIN-RULES", "DATA-SOURCES", "OUTPUT-SPEC",
    ".md", ".py", "config/", "daily_hours", "break.deduct", "nominal_day",
    "Faz 2", "Faz 4",
)


def test_no_developer_references_reach_the_workbook(tmp_path, settings):
    """The person who reads this file will never open the repository.

    Cells used to carry things like `ROADMAP.md Q4` and `— ADR-015`: meaningful to
    whoever wrote the rule, noise to an HR reader who cannot follow them anywhere.
    48 cells in the May 2026 report were like this. Every explanation now stands on
    its own in plain Turkish.

    This test fails on the next `ADR-0NN` someone appends to a report string.
    """
    from mesai.models import SourceCoverage
    stats = RunStats(
        rows_read={"teknopark": 1}, records_built={"teknopark": 1},
        intervals_accepted=2, union_total=timedelta(hours=8, minutes=57),
        accepted_total=timedelta(hours=9, minutes=39),
        files={"teknopark": "test.xlsx"}, roster_date=date(2026, 7, 28),
        roster_duplicates=["AYŞE DENEME: iki hesap"],
        out_of_period={"teknopark": 2}, out_of_period_leave=1,
        # Both branches, so partial-coverage wording is covered too.
        coverage={"teknopark": SourceCoverage("teknopark", 13, 23,
                                             (date(2026, 7, 20), date(2026, 7, 21))),
                  "macunkoy": SourceCoverage("macunkoy", 23, 23, ())},
    )
    path = tmp_path / "jargon.xlsx"
    workbook.build(
        path=path, period="2026-07", summaries=[_summary()], workdays=[_workday()],
        employees={KEY: _employee()}, leave=[], anomalies=_all_kinds(), stats=stats,
        settings=settings, generated_at=datetime(2026, 8, 18, 12, 0),
    )

    offenders: list[str] = []
    book = openpyxl.load_workbook(path, read_only=True)
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if not isinstance(cell, str):
                    continue
                for token in _DEVELOPER_JARGON:
                    if token in cell:
                        offenders.append(f"{sheet.title}: {token!r} in {cell[:70]!r}")

    assert not offenders, "developer jargon in the workbook:\n" + "\n".join(offenders)


# --- the window must say where it put things --------------------------------

def test_the_result_panel_names_both_output_paths(tmp_path, settings, monkeypatch):
    """"Veri dosyası oluşturuldu" with no path is not actionable.

    The user could not find the snapshot, and the report path was not shown at all.
    Both are now printed in full, resolved.
    """
    import tkinter as tk
    from mesai import gui
    from mesai.gui import rapor, widgets

    try:
        root = tk.Tk()
    except tk.TclError:                       # pragma: no cover - headless CI
        pytest.skip("no display")

    try:
        app = gui.App(root, config_dir=tmp_path, roster_dir=tmp_path, base=tmp_path)
        report = tmp_path / "out" / "mesai-raporu-2026-07.xlsx"
        data = tmp_path / "veri" / "gonderim-2026-07.json"
        app.report._render(rapor.Result(
            True, "Temmuz 2026 raporu yazıldı", ("Toplam: 1:00",), widgets.OK,
            output=report, snapshot=data))
        shown = app.report.result.get("1.0", "end")
    finally:
        root.destroy()

    assert str(report.resolve()) in shown, "report path missing"
    assert str(data.resolve()) in shown, "snapshot path missing"
    assert "RAPOR DOSYASI" in shown and "VERİ DOSYASI" in shown


# --- the labels are filter keys now (ADR-027) -------------------------------

def test_no_two_kinds_share_a_label():
    """The people screen filters on the label, so a duplicate would merge two groups."""
    labels = [label for label, _s, _e, _g in DESCRIPTIONS.values()]
    assert len(labels) == len(set(labels))


def test_every_label_is_short_enough_to_scan_in_a_dropdown():
    """They used to be sentences. A dropdown of sentences cannot be read at a glance."""
    for kind, (label, _severity, _explanation, _group) in DESCRIPTIONS.items():
        assert len(label) <= 38, f"{kind}: {label!r}"


def test_every_kind_explains_itself():
    """The short label drops the meaning; the explanation has to carry it."""
    for kind, (label, _severity, explanation, _group) in DESCRIPTIONS.items():
        assert explanation, f"{kind} has no explanation"
        assert explanation != label, kind


def test_the_two_ambiguous_pairs_stay_distinct():
    """Both pairs caused a real misreading, and both are filter targets.

    "sadece giriş" reads equally as "only the entry exists" and "only the entry is
    missing" — opposite people. And one reading under 5 minutes is a different question
    from a whole day under 2 hours; they shared the words "Süre çok kısa".
    """
    label = {kind: value[0] for kind, value in DESCRIPTIONS.items()}
    assert label[AnomalyKind.MISSING_ENTRY] == "Giriş yok"
    assert label[AnomalyKind.MISSING_EXIT] == "Çıkış yok"
    assert label[AnomalyKind.SHORT_DAY] == "Günlük süre çok kısa (<2 saat)"


def test_the_remote_pair_names_the_kind_that_actually_fires():
    """Measured on May 2026: REMOTE_REPLACED_NOMINAL 35 days, REMOTE_OVERLAP 0.

    ADR-018 removes the system's default day, so nothing is left to overlap with. The
    plain name therefore belongs to the kind the shipped config produces — it was on
    the unreachable one, which would have made the filter look empty.
    """
    label = {kind: value[0] for kind, value in DESCRIPTIONS.items()}
    assert label[AnomalyKind.REMOTE_REPLACED_NOMINAL] == "Uzaktan + sistem kaydı"
    assert label[AnomalyKind.REMOTE_OVERLAP_REAL] == "Uzaktan + kart kaydı"


def test_the_worklist_prints_the_explanation_beside_the_keyword(tmp_path, settings):
    book = openpyxl.load_workbook(_build(tmp_path, settings), read_only=True)
    rows = list(book["Sorulacaklar"].iter_rows(values_only=True))
    header = [c for c in rows[3] if c is not None]

    assert header[4] == "Sorun" and header[5] == "Açıklama"
    explanations = {row[4]: row[5] for row in rows[4:] if row and row[4]}
    assert explanations["Çıkış yok"] == "Giriş basılmış, çıkış kaydı yok"
