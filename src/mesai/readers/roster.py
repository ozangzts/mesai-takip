"""IAS employee registry reader — `SYST03_TEMPIASUSERS.xlsx`.

This reader is different from the others. It returns no PunchRecords; it builds the
Employee index that everything else resolves against, and it runs first.

It is also the one reader that MUST raise, because its two invariants protect
payroll correctness rather than a single row. See ADR-010.
"""

from __future__ import annotations

from pathlib import Path

from ..models import NameKey, RosterEntry
from ..normalize import display_name, name_key
from .base import LayoutError, as_text, open_sheets

EXPECTED_HEADERS = ("Kullanıcı", "Kontak No", "İsim", "Soyad", "E-posta")
OPTIONAL_HEADERS = ("Bölüm", "Tesis", "Görev")
PREFERRED_SHEET = "TEMPIASUSERS"

# Columns are located by HEADER TEXT, not by position — see _find_sheet. Note that
# `İsim` holds only the first given name, so the roster's display form is abbreviated
# (ADR-010).


def _find_sheet(sheets, path: Path):
    """Locate the roster sheet by its COLUMNS, not its name.

    The file gets renamed by whoever exports it (`SYST03_TEMPIASUSERS.xlsx` became
    `calisan_listesi.xlsx`), so the sheet name may change too. The columns are the
    real contract. `TEMPIASUSERS` is tried first only as a fast path; the workbook
    also holds a `Sayfa1` with just name and e-mail, which must not be picked.
    """
    ordered = ([s for s in sheets if s.name == PREFERRED_SHEET]
               + [s for s in sheets if s.name != PREFERRED_SHEET])

    seen: list[str] = []
    for sheet in ordered:
        header = [as_text(sheet.value(1, c)) for c in range(1, sheet.ncols + 1)]
        missing = [h for h in EXPECTED_HEADERS if h not in header]
        if not missing:
            return sheet, header
        seen.append(f"  '{sheet.name}': eksik kolonlar {missing}")

    raise LayoutError(
        f"{path.name}: beklenen kolonları taşıyan sayfa bulunamadı.\n"
        f"Aranan kolonlar: {list(EXPECTED_HEADERS)}\n"
        + "\n".join(seen)
        + "\n\n'E-posta' kolonu Faz 4 (otomatik mail) için zorunludur."
    )


def read(path: Path) -> tuple[dict[NameKey, RosterEntry], list[str]]:
    """Load the registry, keyed by (first token, last token).

    Returns (entries, duplicate_notes).

    Raises LayoutError if the sheet or the expected columns are missing, or if two
    *different* employees share a key — that would silently merge two people's
    payroll hours, so it fails the run instead.

    A key repeat is NOT automatically a collision. The registry contains stale
    duplicate accounts: one person can hold two logins (a surname change where the
    old account was never closed) with identical contact number, e-mail, department
    and title. Same person, two rows — deduplicated, not fatal.
    """
    sheet, header = _find_sheet(open_sheets(path), path)
    col = {name: header.index(name) for name in EXPECTED_HEADERS}
    col.update({name: header.index(name)
                for name in OPTIONAL_HEADERS if name in header})

    def cell(row: tuple, name: str) -> str | None:
        index = col.get(name)
        if index is None or index >= len(row):
            return None
        return as_text(row[index])

    entries: dict[NameKey, RosterEntry] = {}
    identity: dict[NameKey, tuple[str, str]] = {}     # key -> (contact, email)
    logins: dict[NameKey, list[str]] = {}
    collisions: list[str] = []
    duplicates: list[str] = []

    for row_no, row in enumerate(sheet.rows(2), start=2):
        given = cell(row, "İsim")
        if not given:
            continue
        surname = cell(row, "Soyad") or ""
        full = f"{given} {surname}".strip()
        key = name_key(full)

        contact = (cell(row, "Kontak No") or "").lstrip("0")
        email = (cell(row, "E-posta") or "").lower()
        login = cell(row, "Kullanıcı") or f"satır {row_no}"

        entry = RosterEntry(
            key=key,
            display_name=display_name(full),
            email=cell(row, "E-posta"),
            facility=cell(row, "Tesis"),
            department=cell(row, "Bölüm"),
            job_title=cell(row, "Görev"),
            row=row_no,
        )

        if key in entries:
            previous_contact, previous_email = identity[key]
            same_person = (
                (contact and contact == previous_contact)
                or (email and email == previous_email)
            )
            if same_person:
                logins[key].append(login)
                duplicates.append(
                    f"{entry.display_name}: {' / '.join(logins[key])} "
                    f"(satır {entries[key].row} ve {row_no})"
                )
                continue
            collisions.append(
                f"  {entries[key].display_name} (satır {entries[key].row}, "
                f"kontak {previous_contact or '-'}, {previous_email or '-'})\n"
                f"  {entry.display_name} (satır {row_no}, kontak {contact or '-'}, "
                f"{email or '-'})\n"
                f"  => aynı anahtar: {key}"
            )
            continue

        entries[key] = entry
        identity[key] = (contact, email)
        logins[key] = [login]

    if collisions:
        raise LayoutError(
            f"{path.name}: aynı (ad, soyad) anahtarına sahip ama FARKLI kişi olan "
            f"{len(collisions)} kayıt var. Bu kişilerin bordro saatleri birleşeceği "
            "için çalışma durduruldu.\n\n" + "\n\n".join(collisions) +
            "\n\nÇözüm: config/personel.yaml içine bu kişiler için ayırt edici "
            "kayıt ekleyin ve docs/DECISIONS.md ADR-010'u güncelleyin."
        )
    if not entries:
        raise LayoutError(f"{path.name}: hiç personel kaydı okunamadı")

    return entries, duplicates
