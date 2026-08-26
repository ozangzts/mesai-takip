"""The message wording, loaded from `config/mail-taslagi.yaml` rather than written here.

**Why it is not in the code.** It is going to change — a table for the person to fill in
was asked for the day the first version shipped — and this program is going to be handed
over as a frozen `.exe`. Wording compiled into an executable can only be changed by
rebuilding it, on a machine with Python, by somebody who can. That is the whole reason
AGENTS.md §6 puts thresholds, holidays and facility labels in `config/`: *a rule change
must be a YAML edit, never a code edit.* The message text is the same kind of thing.

**What stays in the code**, and must: which days are listed, which note is written beside
each one (only the ticked one — see `message.compose`), and how a reading with a missing
half is described. Those are decisions with a right answer, not wording.

Two rules this loader enforces, both because the failure is a mail that has already gone:

* **An unknown placeholder fails loudly.** A typo has to stop the send, not produce a
  message with a literal `{isim}` in it.
* **A missing required key fails loudly.** A template file that predates a change must
  not silently fall back to something else — the same reasoning as the required
  `daily_hours` / `break.deduct` config keys (AGENTS.md §6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_NAME = "mail-taslagi.yaml"

# Every key the file must carry. The HTML ones are optional: an empty `html_govde` means
# plain text only, which is what shipped first and is still a correct message.
REQUIRED = ("konu", "govde", "gun_satiri", "gunsuz_govde")
OPTIONAL = ("html_govde", "html_gun_satiri", "html_gunsuz_govde")

# What each field may refer to. Checked at load time against the actual template, so a
# typo is caught before anything is sent rather than appearing in somebody's inbox.
FIELDS: dict[str, frozenset[str]] = {
    "konu": frozenset({"ad", "donem"}),
    "govde": frozenset({"ad", "donem", "gunler"}),
    "gunsuz_govde": frozenset({"ad", "donem"}),
    "gun_satiri": frozenset({"tarih", "gun", "sorun", "okuma", "giris", "cikis",
                             "sure"}),
    "html_govde": frozenset({"ad", "donem", "gunler_html"}),
    "html_gunsuz_govde": frozenset({"ad", "donem"}),
    "html_gun_satiri": frozenset({"tarih", "gun", "sorun", "okuma", "giris", "cikis",
                                  "sure"}),
}

_PLACEHOLDER = re.compile(r"\{([a-z_]*)\}")


class TemplateError(Exception):
    """The template cannot be used, in words for whoever edits the file."""


@dataclass(frozen=True)
class Template:
    konu: str
    govde: str
    gun_satiri: str
    gunsuz_govde: str
    html_govde: str = ""
    html_gun_satiri: str = ""
    html_gunsuz_govde: str = ""

    @property
    def has_html(self) -> bool:
        """Whether to send a second, HTML part.

        Both the body and the row template are needed: an HTML body with no row template
        would render a table with no rows, which looks like a bug to the reader and is
        one.
        """
        return bool(self.html_govde.strip() and self.html_gun_satiri.strip())


def _check(field: str, text: str) -> None:
    allowed = FIELDS[field]
    for name in _PLACEHOLDER.findall(text):
        if name not in allowed:
            bilinen = ", ".join(f"{{{n}}}" for n in sorted(allowed))
            raise TemplateError(
                f"{CONFIG_NAME}: '{field}' içinde tanınmayan bir alan var: "
                f"{{{name}}}.\n\nBu alanda kullanılabilecekler: {bilinen}")


def load(config_dir: Path) -> Template:
    """Read the template, or say exactly what is wrong with it.

    Falls back to nothing. A missing file is an error rather than a built-in default,
    because a built-in default is invisible: the operator would edit the file, see no
    change, and have no way to tell that the file they edited is not the one being used.
    """
    path = config_dir / CONFIG_NAME
    if not path.exists():
        raise TemplateError(
            f"{CONFIG_NAME} bulunamadı ({path}). Mail metni bu dosyada tutuluyor; "
            "depodaki kopyayı config klasörüne koyun.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TemplateError(f"{CONFIG_NAME} okunamadı: {exc}") from exc
    if not isinstance(raw, dict):
        raise TemplateError(f"{CONFIG_NAME} bir eşleme olmalı.")

    missing = [key for key in REQUIRED if not str(raw.get(key) or "").strip()]
    if missing:
        raise TemplateError(
            f"{CONFIG_NAME} eksik ya da boş: {', '.join(missing)}. "
            "Bu alanlar zorunlu.")

    values = {key: str(raw.get(key) or "") for key in REQUIRED + OPTIONAL}
    for field, text in values.items():
        if text.strip():
            _check(field, text)

    tpl = Template(**values)
    # An HTML body with no rows renders an empty table. Say so here rather than letting
    # somebody discover it in a sent message.
    if tpl.html_govde.strip() and not tpl.html_gun_satiri.strip():
        raise TemplateError(
            f"{CONFIG_NAME}: 'html_govde' doldurulmuş ama 'html_gun_satiri' boş. "
            "Tablonun satırları nereden gelecek? İkisi birlikte doldurulmalı ya da "
            "ikisi birlikte boş bırakılmalı.")
    return tpl


def fill(field: str, text: str, **values: str) -> str:
    """Substitute into one template field.

    `str.format` is not used: the HTML body is full of CSS braces
    (`style="...;font-size:13px"` is fine, but `{border-collapse}` would not be) and a
    stray brace in hand-edited text must not raise a `KeyError` at send time. This
    replaces only the names the field is allowed to carry and leaves everything else
    exactly as written.
    """
    for name in FIELDS[field]:
        text = text.replace(f"{{{name}}}", values.get(name, ""))
    return text
