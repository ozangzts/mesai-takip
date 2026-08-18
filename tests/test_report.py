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
    for kind, (_, severity) in DESCRIPTIONS.items():
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
