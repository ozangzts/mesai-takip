"""IAS employee registry reader — `SYST03_TEMPIASUSERS.xlsx`.

This reader is different from the others. It returns no PunchRecords; it builds the
Employee index that everything else resolves against, and it runs first.

It is also the one reader that MUST raise, because its two invariants protect
payroll correctness rather than a single row. See ADR-010.
"""

from __future__ import annotations

from pathlib import Path

from ..models import NameKey, RosterEntry
from ..normalize import display_name, fold, name_key
from .base import LayoutError, as_text, open_sheets

PREFERRED_SHEET = "TEMPIASUSERS"

# How many rows to search for the header. Same budget as `base.find_header_row`.
HEADER_SEARCH_ROWS = 10

# Each field, and the header spellings accepted for it. Compared **folded** — upper
# case, ASCII, whitespace-collapsed — so `E-Posta`, `e-posta` and `E-POSTA` are one
# thing and a Turkish character cannot split a match (`İsim` vs `Isim`).
#
# Aliases exist because this file is exported by somebody else's system and has
# already been renamed once (`SYST03_TEMPIASUSERS.xlsx` -> `calisan_listesi.xlsx`).
# A column called `Ad` instead of `İsim` is the same column; refusing to read it
# would be this program being fussy about a synonym, at month end, on a machine
# where nobody can change the code.
#
# What is NOT here is a fuzzy matcher. The list is closed and explicit: an
# unanticipated header stops the run and the message says what is accepted. That is
# the AGENTS §2.1 rule — the program never guesses at payroll input, it says what it
# found.
#
# ASCII spellings are NOT listed: folding already makes `Kullanici` and `Unvan`
# the same as their Turkish forms, and the assertion below refuses a duplicate
# rather than letting two entries quietly claim one spelling. It caught exactly
# that on the first run.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "Kullanıcı": ("Kullanıcı", "Kullanıcı Adı", "Login"),
    "Kontak No": ("Kontak No", "Kontak Numarası", "Sicil No", "Personel No"),
    "İsim": ("İsim", "Ad", "Adı"),
    "Soyad": ("Soyad", "Soyadı", "Soy Ad", "Soyisim"),
    "E-posta": ("E-posta", "Eposta", "E-posta Adresi", "E-mail", "Email", "Mail"),
    "Bölüm": ("Bölüm", "Departman", "Birim"),
    "Tesis": ("Tesis", "Lokasyon", "Şube"),
    "Görev": ("Görev", "Ünvan", "Pozisyon"),
}

EXPECTED_HEADERS = ("Kullanıcı", "Kontak No", "İsim", "Soyad", "E-posta")
OPTIONAL_HEADERS = ("Bölüm", "Tesis", "Görev")

# folded spelling -> canonical field. Built once; a spelling claimed by two fields
# would be a bug in the table above, so it is asserted rather than resolved quietly.
_BY_SPELLING: dict[str, str] = {}
for _field, _spellings in HEADER_ALIASES.items():
    for _spelling in _spellings:
        _folded = fold(_spelling)
        assert _folded not in _BY_SPELLING, f"iki alan aynı yazımı istiyor: {_spelling}"
        _BY_SPELLING[_folded] = _field

# Columns are located by HEADER TEXT, not by position, and the header is SEARCHED FOR
# rather than assumed to be row 1 — see `_find_sheet`. Note that `İsim` holds only
# the first given name, so the display form is abbreviated (ADR-010).


def _row_fields(sheet, row_no: int) -> dict[str, int]:
    """`{canonical field: 0-based column}` for one candidate header row.

    First spelling wins if a sheet somehow carries two accepted names for one
    field, so the result does not depend on column order.
    """
    found: dict[str, int] = {}
    for col in range(1, sheet.ncols + 1):
        field = _BY_SPELLING.get(fold(as_text(sheet.value(row_no, col))))
        if field is not None:
            found.setdefault(field, col - 1)
    return found


def _find_sheet(sheets, path: Path):
    """Locate the roster sheet AND its header row, by the columns rather than names.

    Three things about this file are not stable, and all three have changed or will:

    * **the file name** — it arrived as `SYST03_TEMPIASUSERS.xlsx` and became
      `calisan_listesi.xlsx`, so `sources.roster` matches by pattern;
    * **the sheet name** — hence the search here. `TEMPIASUSERS` is tried first only
      as a fast path, and the workbook also holds a `Sayfa1` carrying just name and
      e-mail, which must not be picked;
    * **which row the header is on.** This used to read row 1 and nothing else. The
      Macunköy export gained a title line above its header in July 2026 (ADR-020,
      `DATA-SOURCES.md` D10) and its reader was fixed to search for the header; this
      one was not, and would have failed the same way. It searches now.

    `base.find_header_row` is not reused because it matches header text exactly, and
    this file needs the folded alias table: `Ad` for `İsim` is the same column.
    """
    ordered = ([s for s in sheets if s.name == PREFERRED_SHEET]
               + [s for s in sheets if s.name != PREFERRED_SHEET])

    seen: list[str] = []
    for sheet in ordered:
        best: list[str] | None = None
        for row_no in range(1, min(HEADER_SEARCH_ROWS, sheet.nrows) + 1):
            found = _row_fields(sheet, row_no)
            missing = [name for name in EXPECTED_HEADERS if name not in found]
            if not missing:
                return sheet, row_no, found
            if best is None or len(missing) < len(best):
                best = missing
        seen.append(
            f"  '{sheet.name}': eksik kolonlar {best or list(EXPECTED_HEADERS)}")

    kabul = "\n".join(f"    {field}: {', '.join(HEADER_ALIASES[field])}"
                      for field in EXPECTED_HEADERS)
    raise LayoutError(
        f"{path.name}: beklenen kolonları taşıyan sayfa bulunamadı.\n"
        f"İlk {HEADER_SEARCH_ROWS} satırda başlık arandı.\n\n"
        f"Kabul edilen kolon adları:\n{kabul}\n\n"
        "Bakılan sayfalar:\n" + "\n".join(seen)
        + "\n\n'E-posta' kolonu otomatik mail için zorunludur. "
        "Büyük/küçük harf ve Türkçe karakter farkı sorun değildir; yukarıdaki "
        "adlardan biri yeterli."
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
    sheet, header_row, col = _find_sheet(open_sheets(path), path)

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

    # Data starts after the header, wherever the header turned out to be.
    first = header_row + 1
    for row_no, row in enumerate(sheet.rows(first), start=first):
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
