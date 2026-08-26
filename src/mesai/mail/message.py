"""One person's message: which days it lists, and what is said about each.

The **wording** is not here any more — it is `config/mail-taslagi.yaml`, loaded by
`template.py`, because it will change and this program ships frozen (see that module).
What stays here is everything with a right answer rather than a preference:

* **only the ticked note is written.** The same day can carry more than one — July has
  two that are both `Çıkış yok` and `Günlük süre çok kısa` — and writing a note nobody
  selected asks a question nobody meant to ask.
* **a counted day never carries a missing-punch note** (`recipients.day_notes`, ADR-076).
  `Hem giriş hem çıkış yok` beside the times the day was counted from is a contradiction,
  not a fact.
* **the missing half of a reading is named, not dashed.** A dash beside a time reads as a
  formatting artefact to somebody reading this once, probably on a phone.
* **no person and no department is named** beyond the recipient (AGENTS.md §6). A test
  holds the shipped template to it, because the words are hand-editable now — the rule
  did not move out of the code just because the wording did.

`compose()` stays pure and takes the template as an argument, so the preview the operator
approves and the body that leaves the machine come from one call. A preview produced by
different code than the send is a preview of nothing.
"""

from __future__ import annotations

import html as _html
from collections.abc import Iterable
from dataclasses import dataclass

from ..snapshot import Person, ProblemDay
from .recipients import day_notes
from .template import Template, TemplateError, fill

_MONTHS = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
           "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")

_DAYS = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def period_text(period: str) -> str:
    """`2026-07` -> `Temmuz 2026`. The reader does not think in ISO."""
    year, month = (int(part) for part in period.split("-"))
    return f"{_MONTHS[month - 1]} {year}"


@dataclass(frozen=True)
class Draft:
    """A composed message, before anybody has agreed to send it."""
    to: str
    subject: str
    body: str
    html: str = ""

    @property
    def is_sendable(self) -> bool:
        return bool(self.to.strip()) and bool(self.body.strip())


def reading(day: ProblemDay) -> str:
    """What the badge system actually recorded that day.

    It is the difference between the person being able to answer and having to go and ask
    somebody: `Çıkış yok` tells them what is wrong, `giriş 07:41, çıkış kaydı yok` tells
    them which day of their life it was.
    """
    entry, exit = day.entry_text, day.exit_text
    if entry and exit:
        return f"giriş {entry}, çıkış {exit}"
    if entry:
        return f"giriş {entry}, çıkış kaydı yok"
    if exit:
        return f"giriş kaydı yok, çıkış {exit}"
    return "giriş ve çıkış kaydı yok"


def _values(day: ProblemDay, counted: frozenset[str]) -> dict[str, str]:
    """The fields one day's row may refer to.

    `sorun` is the **ticked** note and only that, falling back to what the day carries
    when nothing is ticked — a dated line with no reason is a date the reader cannot
    answer.
    """
    notes = day_notes(day)
    shown = [label for label in notes if label in counted] or list(notes)
    return {
        "tarih": f"{day.date:%d.%m.%Y}",
        "gun": _DAYS[day.date.weekday()],
        "sorun": ", ".join(shown),
        "okuma": reading(day),
        "giris": day.entry_text,
        "cikis": day.exit_text,
        "sure": day.hours_text,
    }


def _escaped(values: dict[str, str]) -> dict[str, str]:
    """Every substituted value, escaped for the HTML part.

    A name comes from a source file and goes into markup, so it is escaped — not because
    a badge export is expected to contain `<`, but because "this value cannot contain
    markup" is an assumption about somebody else's system, and this project does not make
    those anywhere else either (the container sniffing, the header search, the alias
    table). The template itself is never escaped: its markup is the point.
    """
    return {key: _html.escape(value, quote=True) for key, value in values.items()}


def compose(person: Person, days: Iterable[ProblemDay], period: str,
            counted: Iterable[str] = (), template: Template | None = None) -> Draft:
    """The message for one person about the days selected for them.

    A person with no listed day still composes: the operator may be writing to somebody
    whose whole month is missing (`Kart bilgisi yok` carries no date at all), and an empty
    day list is not a reason to refuse to write. The template carries a separate body for
    that case, so it says so in words rather than showing an empty list.
    """
    if template is None:
        raise TemplateError(
            "Mail taslağı yüklenmedi. Metin config/mail-taslagi.yaml dosyasında "
            "tutuluyor ve programın içine gömülmemiştir.")

    counted = frozenset(counted)
    dated = sorted(days, key=lambda d: d.date)
    ay = period_text(period)
    common = {"ad": person.name, "donem": ay}

    if dated:
        rows = [fill("gun_satiri", template.gun_satiri, **_values(day, counted))
                for day in dated]
        body = fill("govde", template.govde, gunler="\n".join(rows), **common)
    else:
        body = fill("gunsuz_govde", template.gunsuz_govde, **common)

    html = ""
    if template.has_html:
        if dated:
            rows = [fill("html_gun_satiri", template.html_gun_satiri,
                         **_escaped(_values(day, counted)))
                    for day in dated]
            html = fill("html_govde", template.html_govde,
                        gunler_html="".join(rows), **_escaped(common))
        elif template.html_gunsuz_govde.strip():
            html = fill("html_gunsuz_govde", template.html_gunsuz_govde,
                        **_escaped(common))

    return Draft(to=(person.email or "").strip(),
                 subject=fill("konu", template.konu, **common).strip(),
                 body=body.strip() + "\n", html=html.strip())
