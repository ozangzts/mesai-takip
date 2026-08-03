"""The report workbook — see docs/OUTPUT-SPEC.md.

Sheet modules write cells. They never compute anything: every figure arrives
already calculated.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from ..anomalies import Collector
from ..config import Settings
from ..models import Employee, LeaveRecord, MonthSummary, NameKey, RunStats, WorkDay
from ..normalize import sort_key
from ..rules.worktime import decimal_hours, hhmm
from . import styles

class ReportLocked(Exception):
    """The output file could not be replaced — typically open in Excel."""


_DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

# How an interval's origin is shown to the reader.
_SOURCE_LABEL = {"macunkoy": "Macunköy", "teknopark": "Teknopark", "izin": "Uzaktan"}
# How an input file is named on the Kontrol sheet. Deliberately different: the leave
# file is "İzin", even though the intervals it contributes are labelled "Uzaktan".
_FILE_LABEL = {
    "roster": "Personel listesi", "macunkoy": "Macunköy giriş-çıkış",
    "teknopark": "Teknopark puantaj", "izin": "İzin (HCM)",
}


def build(
    path: Path,
    period: str,
    summaries: list[MonthSummary],
    workdays: list[WorkDay],
    employees: dict[NameKey, Employee],
    leave: list[LeaveRecord],
    anomalies: Collector,
    stats: RunStats,
    settings: Settings,
    generated_at: datetime,
) -> None:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)

    footer = _footer_lines(period, stats, generated_at)

    _sheet_summary(workbook.create_sheet("Aylık Özet"), period, summaries,
                   anomalies, footer)
    _sheet_daily(workbook.create_sheet("Günlük Detay"), workdays, employees,
                 settings, footer)
    _sheet_worklist(workbook.create_sheet("Sorulacaklar"), period, anomalies,
                    employees, footer)
    _sheet_anomalies(workbook.create_sheet("Şüpheli Kayıtlar"), anomalies,
                     employees, footer)
    _sheet_leave(workbook.create_sheet("İzin Özeti"), leave, employees,
                 summaries, settings, footer)
    _sheet_control(workbook.create_sheet("Kontrol"), period, stats, summaries,
                   anomalies, settings, generated_at)

    # Write to a temporary file and move it into place, so a crash mid-write cannot
    # leave HR with a half-written workbook that still opens.
    target = path.with_suffix(".tmp.xlsx")
    workbook.save(target)
    workbook.close()
    try:
        os.replace(target, path)
    except PermissionError as exc:
        target.unlink(missing_ok=True)
        raise ReportLocked(
            f"Rapor yazılamadı, dosya kilitli:\n  {path}\n\n"
            "Dosya Excel'de açıksa kapatıp tekrar deneyin."
        ) from exc


# ---------------------------------------------------------------------------
# Sheet 1 — Aylık Özet
# ---------------------------------------------------------------------------

_SUMMARY_HEADERS = [
    "Ad Soyad", "Sicil No", "Departman", "Görev", "Tesis", "Kayıt Kaynağı",
    "Çalışılan Gün", "Brüt Süre", "Brüt (Saat)", "Net Süre", "Net (Saat)",
    "Uzaktan Çalışma (Gün)", "İzin Günü", "Şüpheli Kayıt", "Not",
]
_SUMMARY_WIDTHS = [28, 10, 30, 32, 17, 20, 13, 11, 11, 11, 11, 14, 11, 12, 34]


def _sheet_summary(sheet: Worksheet, period: str, summaries: list[MonthSummary],
                   anomalies: Collector, footer: list[str]) -> None:
    span = len(_SUMMARY_HEADERS)
    styles.write_title(sheet, 1, f"AYLIK ÇALIŞMA ÖZETİ — {_period_label(period)}", span)
    styles.write_banner(
        sheet, 2,
        "DİKKAT: Şüpheli olarak işaretlenen kayıtlar 0 saat sayılmıştır — "
        "'Şüpheli Kayıtlar' sayfasına bakın. Bu rapor bir DOĞRULAMA koşusudur, "
        "bordro için nihai değildir.", span)
    styles.write_header(sheet, 4, _SUMMARY_HEADERS, _SUMMARY_WIDTHS)

    row = 5
    total_gross = timedelta()
    total_net = timedelta()

    for summary in sorted(summaries, key=lambda s: sort_key(s.employee.display_name)):
        employee = summary.employee
        fill = None
        if not summary.has_attendance:
            fill = styles.RED_FILL
        elif summary.anomaly_count:
            fill = styles.AMBER_FILL

        values: list[object] = [
            employee.display_name,
            employee.personnel_no or "",
            employee.department or "",
            employee.job_title or "",
            employee.facility or "",
            _sources_label(employee.sources),
        ]
        if summary.has_attendance:
            values += [
                summary.worked_days,
                hhmm(summary.gross), decimal_hours(summary.gross),
                hhmm(summary.net), decimal_hours(summary.net),
            ]
            total_gross += summary.gross
            total_net += summary.net
        else:
            values += ["", "", "", "", ""]
        values += [
            summary.remote_days or "",
            summary.leave_days or "",
            summary.anomaly_count or "",
            "; ".join(summary.notes),
        ]

        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            if index in (8, 9, 10, 11, 7, 12, 13, 14):
                cell.alignment = styles.RIGHT
            if index in (9, 11):
                cell.number_format = "0.00"
            if index in (12, 13):
                cell.number_format = "0.0#"
        styles.style_row(sheet, row, span, fill)
        row += 1

    with_attendance = sum(1 for s in summaries if s.has_attendance)
    sheet.cell(row=row, column=1, value=f"TOPLAM ({with_attendance} kişi)")
    sheet.cell(row=row, column=8, value=hhmm(total_gross)).alignment = styles.RIGHT
    sheet.cell(row=row, column=9, value=decimal_hours(total_gross)).alignment = styles.RIGHT
    sheet.cell(row=row, column=10, value=hhmm(total_net)).alignment = styles.RIGHT
    sheet.cell(row=row, column=11, value=decimal_hours(total_net)).alignment = styles.RIGHT
    for index in range(1, span + 1):
        cell = sheet.cell(row=row, column=index)
        cell.font = styles.TOTAL_FONT
        cell.fill = styles.TOTAL_FILL
        cell.border = styles.BORDER
    sheet.cell(row=row, column=9).number_format = "0.00"
    sheet.cell(row=row, column=11).number_format = "0.00"

    styles.write_footer(sheet, row + 2, footer, span)


# ---------------------------------------------------------------------------
# Sheet 2 — Günlük Detay
# ---------------------------------------------------------------------------

_DAILY_HEADERS = [
    "Ad Soyad", "Tarih", "Gün", "İlk Giriş", "Son Çıkış", "Aralık Sayısı",
    "Brüt", "Öğle Kesintisi", "Net", "Kaynak", "Etiket",
]
_DAILY_WIDTHS = [28, 12, 13, 10, 10, 13, 10, 14, 10, 24, 26]


def _sheet_daily(sheet: Worksheet, workdays: list[WorkDay],
                 employees: dict[NameKey, Employee], settings: Settings,
                 footer: list[str]) -> None:
    span = len(_DAILY_HEADERS)
    styles.write_title(sheet, 1, "GÜNLÜK DETAY — özetin denetim izi", span)
    styles.write_banner(
        sheet, 2,
        "Her satır bir kişi-gün. 'Aralık Sayısı' 1'den büyükse gün bölünmüş "
        "(ara giriş-çıkış) demektir. Kaynak birden fazlaysa iki tesisin kaydı "
        "birleştirilmiştir; çakışan süre bir kez sayılır.", span)
    styles.write_header(sheet, 4, _DAILY_HEADERS, _DAILY_WIDTHS)

    row = 5
    for workday in sorted(
        workdays,
        key=lambda w: (sort_key(employees[w.key].display_name
                                if w.key in employees else ""), w.date),
    ):
        employee = employees.get(workday.key)
        label = settings.calendar.holidays.get(workday.date)
        day_label = "Resmi Tatil" if label else _DAY_NAMES[workday.date.weekday()]

        values = [
            employee.display_name if employee else "",
            workday.date.strftime("%d.%m.%Y"),
            day_label,
            workday.first_entry.strftime("%H:%M") if workday.first_entry else "",
            workday.last_exit.strftime("%H:%M") if workday.last_exit else "",
            len(workday.intervals),
            hhmm(workday.gross),
            hhmm(workday.break_deduction),
            hhmm(workday.net),
            _sources_label(workday.sources),
            ", ".join(sorted(workday.tags)),
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            if index in (4, 5, 6, 7, 8, 9):
                cell.alignment = styles.RIGHT

        fill = None
        if workday.tags:
            fill = styles.AMBER_FILL
        if label:
            fill = styles.GREY_FILL
        styles.style_row(sheet, row, span, fill)
        row += 1

    styles.write_footer(sheet, row + 1, footer, span)


# ---------------------------------------------------------------------------
# Sheet 3 — Sorulacaklar (per-person worklist)
# ---------------------------------------------------------------------------

_WORKLIST_HEADERS = [
    "Ad Soyad", "Sicil No", "Tesis", "Departman", "Sorun", "Gün Sayısı",
    "Günler", "Etki",
]
_WORKLIST_WIDTHS = [28, 10, 17, 30, 34, 11, 46, 24]


def _sheet_worklist(sheet: Worksheet, period: str, anomalies: Collector,
                    employees: dict[NameKey, Employee], footer: list[str]) -> None:
    """One row per (person, problem), with the exact dates listed.

    The Şüpheli Kayıtlar sheet is the audit trail — one row per defective record,
    216 of them. This sheet is the thing you take to HR or IT and ask about: it
    collapses those rows into a per-person question with the days named.
    """
    span = len(_WORKLIST_HEADERS)
    styles.write_title(sheet, 1,
                       f"SORULACAKLAR — kişi bazlı eksik kayıt listesi "
                       f"({_period_label(period)})", span)
    styles.write_banner(
        sheet, 2,
        "Bu sayfa İK'ya / IT'ye sormak için hazırlanmıştır: her satır bir kişi ve "
        "bir sorun türü, hangi günlerde olduğu yazılı. Kırmızı satırlardaki günler "
        "0 saat sayıldı. Satır bazlı denetim izi için 'Şüpheli Kayıtlar' sayfasına "
        "bakın.", span)
    styles.write_header(sheet, 4, _WORKLIST_HEADERS, _WORKLIST_WIDTHS)

    # (employee key, problem label) -> dates
    grouped: dict[tuple[NameKey | None, str], list[date]] = defaultdict(list)
    severity: dict[tuple[NameKey | None, str], str] = {}
    names: dict[NameKey | None, str] = {}

    for anomaly in anomalies.items:
        bucket = (anomaly.key, anomaly.label)
        if anomaly.date is not None:
            grouped[bucket].append(anomaly.date)
        else:
            grouped[bucket]          # touch, so a dateless problem still gets a row
        severity[bucket] = anomaly.severity
        employee = employees.get(anomaly.key) if anomaly.key else None
        names[anomaly.key] = employee.display_name if employee else anomaly.raw_name

    def order(item):
        (key, label), dates = item
        return (severity[(key, label)] != "excluded", -len(dates),
                sort_key(names.get(key, "")), label)

    row = 5
    for (key, label), dates in sorted(grouped.items(), key=order):
        employee = employees.get(key) if key else None
        unique_days = sorted({d.day for d in dates})

        values = [
            names.get(key, ""),
            employee.personnel_no if employee and employee.personnel_no else "",
            employee.facility if employee else "",
            employee.department if employee else "",
            label,
            len(unique_days) or "",
            _day_list(unique_days, period),
            _IMPACT_TEXT[severity[(key, label)]],
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            if index == 6:
                cell.alignment = styles.RIGHT
            if index == 7:
                cell.alignment = styles.LEFT
        fill = (styles.RED_FILL if severity[(key, label)] == "excluded"
                else styles.AMBER_FILL)
        styles.style_row(sheet, row, span, fill)
        row += 1

    styles.write_footer(sheet, row + 1, footer, span)


_IMPACT_TEXT = {
    "excluded": "Bu günler 0 saat sayıldı",
    "included": "Toplama dahil edildi",
}

_MONTHS_LOWER = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                 "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def _day_list(days: list[int], period: str) -> str:
    """`4, 5, 11, 12 Mayıs` — compact enough to read, precise enough to ask about."""
    if not days:
        return "tüm ay"
    month = _MONTHS_LOWER[int(period.split("-")[1]) - 1]
    return ", ".join(str(d) for d in days) + f" {month}"


# ---------------------------------------------------------------------------
# Sheet 4 — Şüpheli Kayıtlar
# ---------------------------------------------------------------------------

_ANOMALY_HEADERS = [
    "Ad Soyad", "Tarih", "Sorun", "Kaynak Dosya", "Kaynak Satır",
    "Ham Giriş", "Ham Çıkış", "Etki", "Açıklama",
]
_ANOMALY_WIDTHS = [28, 12, 34, 14, 13, 22, 22, 24, 52]


def _sheet_anomalies(sheet: Worksheet, anomalies: Collector,
                     employees: dict[NameKey, Employee], footer: list[str]) -> None:
    span = len(_ANOMALY_HEADERS)
    styles.write_title(sheet, 1, "ŞÜPHELİ KAYITLAR", span)
    styles.write_banner(
        sheet, 2,
        "Kırmızı satırlar toplama DAHİL EDİLMEDİ (o gün 0 saat). Sarı satırlar "
        "toplama dahil edildi ama kontrol edilmeli. 'Kaynak Satır' orijinal "
        "dosyadaki satır numarasıdır — açıp bakabilirsiniz.", span)
    styles.write_header(sheet, 4, _ANOMALY_HEADERS, _ANOMALY_WIDTHS)

    row = 5
    ordered = sorted(
        anomalies.items,
        key=lambda a: (
            a.severity != "excluded",
            sort_key(employees[a.key].display_name
                     if a.key in employees else a.raw_name),
            a.date or date.min,
        ),
    )
    for anomaly in ordered:
        employee = employees.get(anomaly.key) if anomaly.key else None
        name = employee.display_name if employee else anomaly.raw_name
        values = [
            name,
            anomaly.date.strftime("%d.%m.%Y") if anomaly.date else "",
            anomaly.label,
            _SOURCE_LABEL.get(anomaly.source, anomaly.source),
            anomaly.source_row,
            anomaly.raw_entry,
            anomaly.raw_exit,
            anomaly.impact,
            anomaly.detail,
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            if index == 5:
                cell.alignment = styles.RIGHT
        fill = styles.RED_FILL if anomaly.severity == "excluded" else styles.AMBER_FILL
        styles.style_row(sheet, row, span, fill)
        row += 1

    styles.write_footer(sheet, row + 1, footer, span)


# ---------------------------------------------------------------------------
# Sheet 5 — İzin Özeti
# ---------------------------------------------------------------------------

_LEAVE_TYPES = [
    "Yıllık İzin", "Mazeret", "Uzaktan Çalışma", "İstirahat (Raporlu)",
    "Eğitim İzni", "Doğum Günü İzni",
]
_LEAVE_HEADERS = (["Ad Soyad", "Sicil No"] + _LEAVE_TYPES
                  + ["Diğer", "Toplam Gün", "Not"])
_LEAVE_WIDTHS = [28, 10] + [15] * len(_LEAVE_TYPES) + [10, 12, 40]


def _sheet_leave(sheet: Worksheet, leave: list[LeaveRecord],
                 employees: dict[NameKey, Employee], summaries: list[MonthSummary],
                 settings: Settings, footer: list[str]) -> None:
    span = len(_LEAVE_HEADERS)
    styles.write_title(sheet, 1, "İZİN ÖZETİ", span)
    styles.write_banner(
        sheet, 2,
        "'Uzaktan Çalışma' izin değil, ÇALIŞMA olarak sayılmıştır — Aylık Özet'teki "
        "saatlerin içindedir. İzin dosyasındaki serbest metin gerekçeler (sağlık, "
        "kişisel) kişisel veri olduğu için bu rapora yazılmamıştır.", span)
    styles.write_header(sheet, 4, _LEAVE_HEADERS, _LEAVE_WIDTHS)

    by_person: dict[NameKey, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for record in leave:
        by_person[record.key][record.leave_type] += record.days

    has_attendance = {s.employee.key for s in summaries if s.has_attendance}

    row = 5
    for key, types in sorted(
        by_person.items(),
        key=lambda item: sort_key(employees[item[0]].display_name
                                  if item[0] in employees else ""),
    ):
        employee = employees.get(key)
        other = sum(days for name, days in types.items() if name not in _LEAVE_TYPES)
        total = sum(types.values())
        note = "" if key in has_attendance else "Mesai verisi yok"

        values: list[object] = [
            employee.display_name if employee else "",
            employee.personnel_no if employee and employee.personnel_no else "",
        ]
        values += [round(types.get(name, 0.0), 2) or "" for name in _LEAVE_TYPES]
        values += [round(other, 2) or "", round(total, 2), note]

        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            if 3 <= index <= span - 1:
                cell.alignment = styles.RIGHT
                cell.number_format = "0.0#"
        styles.style_row(sheet, row, span,
                         styles.RED_FILL if note else None)
        row += 1

    styles.write_footer(sheet, row + 1, footer, span)


# ---------------------------------------------------------------------------
# Sheet 6 — Kontrol
# ---------------------------------------------------------------------------

def _sheet_control(sheet: Worksheet, period: str, stats: RunStats,
                   summaries: list[MonthSummary], anomalies: Collector,
                   settings: Settings, generated_at: datetime) -> None:
    span = 4
    styles.write_title(sheet, 1, "KONTROL — mutabakat ve varsayımlar", span)
    for index, width in enumerate([46, 22, 22, 60], start=1):
        from openpyxl.utils import get_column_letter
        sheet.column_dimensions[get_column_letter(index)].width = width

    row = 3

    def section(title: str) -> None:
        nonlocal row
        cell = sheet.cell(row=row, column=1, value=title)
        cell.font = styles.HEADER_FONT
        cell.fill = styles.HEADER_FILL
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        row += 1

    def line(label: str, value: object = "", note: str = "",
             fill=None) -> None:
        nonlocal row
        sheet.cell(row=row, column=1, value=label)
        cell = sheet.cell(row=row, column=2, value=value)
        cell.alignment = styles.RIGHT
        sheet.cell(row=row, column=4, value=note)
        if fill is not None:
            styles.style_row(sheet, row, span, fill)
        row += 1

    section("1. Okunan dosyalar")
    for name, filename in stats.files.items():
        line(_FILE_LABEL.get(name, name), filename)
    row += 1

    section("2. Satır mutabakatı")
    for name in ("roster", "macunkoy", "teknopark", "izin"):
        if name not in stats.rows_read:
            continue
        built = stats.records_built.get(name, 0)
        line(f"{_FILE_LABEL.get(name, name)} — okunan satır",
             stats.rows_read[name], f"kayda dönüşen: {built}")
    line("  İzin dosyasında atlanan ara toplam satırı",
         stats.rows_read.get("izin_ara_toplam_atlanan", 0),
         "Kişi başı ara toplam satırı — sayılsa izinler ikiye katlanırdı")
    line("  İzin dosyasından gelen uzaktan çalışma aralığı",
         stats.records_built.get("izin_uzaktan", 0),
         "Çalışma olarak sayıldı — ADR-007")
    line("Ayıklanan ziyaretçi/geçici/stajyer kaydı", stats.excluded_badges,
         "config/personel.yaml:exclude_prefixes")
    outside = sum(stats.out_of_period.values())
    if outside or stats.out_of_period_leave:
        detail = ", ".join(f"{_FILE_LABEL.get(k, k)}: {v}"
                           for k, v in sorted(stats.out_of_period.items()))
        line(f"{period} dönemi dışında kalıp atılan kayıt", outside,
             detail or "—", styles.AMBER_FILL)
        line("  dönem dışı izin kaydı", stats.out_of_period_leave)
    else:
        line(f"{period} dönemi dışında kayıt", 0,
             "Tüm kayıtlar rapor dönemine ait", styles.GREEN_FILL)
    row += 1

    section("3. Hesaplama mutabakatı")
    computed = timedelta()
    for summary in summaries:
        computed += summary.gross
    line("Kabul edilen aralık sayısı", stats.intervals_accepted)
    line("Kabul edilen aralıkların toplamı", hhmm(stats.accepted_total))
    line("Kişi toplamlarının toplamı", hhmm(computed))
    matches = abs((computed - stats.accepted_total).total_seconds()) < 1
    line("Mutabakat", "TAMAM" if matches else "HATA",
         "Σ kişi brüt == Σ kabul edilen aralık" if matches
         else "Kayıt çift sayılmış veya kaybolmuş — inceleyin",
         styles.GREEN_FILL if matches else styles.RED_FILL)
    row += 1

    section("4. Kapsam")
    line("Raporda yer alan kişi", len(summaries))
    line("Mesai verisi olan", sum(1 for s in summaries if s.has_attendance))
    line("Mesai verisi olmayan", sum(1 for s in summaries if not s.has_attendance),
         "İzin kaydı var, kart kaydı yok — ROADMAP.md Q4", styles.RED_FILL)
    line("Personel listesinde olmayan",
         sum(1 for s in summaries if not s.employee.in_roster),
         "Dönemde çalışıp personel listesi alınana kadar ayrılmış olabilir "
         "— ADR-011")
    line("Şüpheli kayıt (toplam)", len(anomalies))
    line("  toplama dahil edilmeyen",
         sum(1 for a in anomalies.items if a.severity == "excluded"))
    row += 1

    section("5. Personel listesinde tekrarlanan kayıtlar")
    if stats.roster_duplicates:
        line("Aynı kişi için birden fazla hesap bulundu ve tekilleştirildi", "",
             "Aynı kontak no / e-posta, farklı kullanıcı adı. Eski hesap "
             "kapatılmamış olabilir.", styles.GREY_FILL)
        for note in stats.roster_duplicates:
            line(f"  {note}")
    else:
        line("Yok")
    row += 1

    section("6. Onay bekleyen isim eşleştirmeleri")
    if settings.personnel.alias_pairs:
        line("Aşağıdaki eşleştirmeler UYGULANDI ama İK onayı bekliyor", "",
             "Yanlışsa iki kişinin saatleri birleşmiş olur — ROADMAP.md Q4a",
             styles.AMBER_FILL)
        for variant, canonical in settings.personnel.alias_pairs:
            line(f"  {variant}", "->", canonical, styles.AMBER_FILL)
    else:
        line("Yok")
    row += 1

    section("7. Doğrulanmamış varsayımlar")
    line("Resmi tatil takvimi", f"{len(settings.calendar.holidays)} gün",
         "Veriden ÇIKARILDI, İK onaylamadı — ROADMAP.md Q16", styles.AMBER_FILL)
    for day, label in sorted(settings.calendar.holidays.items()):
        line(f"  {day.strftime('%d.%m.%Y')}", _DAY_NAMES[day.weekday()], label)
    line("Öğle arası", f"{settings.brk.minutes} dk",
         f"kalan mola kuralı, pencere {settings.brk.window_from:%H:%M}-"
         f"{settings.brk.window_to:%H:%M} — ADR-008")
    _roster_age_line(line, stats, period)
    row += 1

    section("8. Bu raporun kapsamadıkları")
    for text in (
        "Fazla mesai, eksik çalışma, haftalık FM — Faz 2 (Q5, Q6)",
        "Vardiya tespiti — Faz 2 (Q7)",
        "Multinet hakedişi — Faz 2 (Q6)",
        "Resmi tatil / hafta tatili ücret-izin karşılığı — Faz 2 (Q8)",
        "Otomatik personel maili — Faz 4 (Q18)",
    ):
        line("  " + text)

    styles.write_footer(sheet, row + 1,
                        _footer_lines(period, stats, generated_at), span)


# ---------------------------------------------------------------------------

def _roster_age_line(line, stats: RunStats, period: str) -> None:
    """Report how stale the roster is relative to the reporting period.

    A roster newer than the period is why leavers and new hires appear (ADR-011).
    The date comes from the file's own timestamp — never hard-coded, or it silently
    lies the first time HR re-exports.
    """
    if stats.roster_date is None:
        line("Personel listesi tarihi", "bilinmiyor", "", styles.AMBER_FILL)
        return

    roster_month = stats.roster_date.year * 12 + stats.roster_date.month
    year, month = (int(part) for part in period.split("-"))
    gap = roster_month - (year * 12 + month)
    stamp = stats.roster_date.strftime("%d.%m.%Y")

    if gap == 0:
        line("Personel listesi tarihi", stamp,
             "Rapor dönemiyle aynı ay — ideal", styles.GREEN_FILL)
    elif gap > 0:
        line("Personel listesi tarihi", stamp,
             f"Rapor döneminden {gap} ay SONRA alınmış. Ayrılanlar listede "
             f"görünmez, sonradan girenler mesai verisinde yoktur — ADR-011",
             styles.AMBER_FILL)
    else:
        line("Personel listesi tarihi", stamp,
             f"Rapor döneminden {-gap} ay ÖNCE alınmış. O tarihten sonra işe "
             f"girenler listede yok — ADR-011", styles.AMBER_FILL)


def _sources_label(sources: frozenset[str]) -> str:
    real = sorted(_SOURCE_LABEL.get(s, s) for s in sources if s != "uzaktan")
    if "uzaktan" in sources or "izin" in sources:
        if "Uzaktan" not in real:
            real.append("Uzaktan")
    if len(real) > 1:
        return " + ".join(real)
    return real[0] if real else ""


def _period_label(period: str) -> str:
    months = ("OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ",
              "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK")
    year, month = period.split("-")
    return f"{months[int(month) - 1]} {year}"


def _footer_lines(period: str, stats: RunStats, generated_at: datetime) -> list[str]:
    files = ", ".join(stats.files.values())
    return [
        f"Oluşturulma: {generated_at:%d.%m.%Y %H:%M} · Dönem: {period} · "
        f"mesai-takip v0.1.0",
        f"Kaynak dosyalar: {files}",
        "Bu rapor otomatik üretilmiştir. Hesaplama kuralları: docs/DOMAIN-RULES.md",
    ]
