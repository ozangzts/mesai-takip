"""The text of one person's message. No SMTP, no widget, no clock.

Separate from `sender.py` on purpose: the wording is the part that gets argued about
and the part a test can pin, and it must be reviewable without anything being sent.
`compose()` is pure, so the preview the operator approves and the body that leaves the
machine are produced by the same call — a preview built by different code than the send
is a preview of nothing.

Two rules the wording follows, both from AGENTS.md §6:

* **it names nobody and no department.** No "İK talebiyle", no "onay bekliyor", no
  "IT ile kontrol edin". The message says what the records show and asks the person to
  say what happened. Who chases it is not the message's business.
* **only the ticked notes are written.** The same day can carry more than one note —
  July has two days that are both `Çıkış yok` and `Günlük süre çok kısa` — and writing
  a note nobody selected asks a question nobody meant to ask (`HANDOVER.md` §1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..snapshot import Person, ProblemDay

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

    @property
    def is_sendable(self) -> bool:
        return bool(self.to.strip()) and bool(self.body.strip())


def _reading(day: ProblemDay) -> str:
    """What the badge system actually recorded that day, in parentheses.

    Asked for after the first version shipped without it, and it is the difference
    between a person being able to answer and having to go and ask somebody. `Çıkış yok`
    tells them what is wrong; `giriş 07:41, çıkış kaydı yok` tells them which day of
    their life it was.

    The missing half is named rather than dashed. A dash beside a time reads as a
    formatting artefact, and this message is read once, probably on a phone, by somebody
    who does not have the sheet in front of them.
    """
    entry, exit = day.entry_text, day.exit_text
    if entry and exit:
        return f"giriş {entry}, çıkış {exit}"
    if entry:
        return f"giriş {entry}, çıkış kaydı yok"
    if exit:
        return f"giriş kaydı yok, çıkış {exit}"
    return "giriş ve çıkış kaydı yok"


def _day_line(day: ProblemDay, counted: frozenset[str]) -> str:
    """The date, the weekday, why it is listed, and what was read that day.

    The reason is the **ticked** note and only that. Without the reason the reader gets
    a list of dates and no idea what to answer; with every note on the day, they get
    asked about something nobody selected.
    """
    shown = [label for label in day.problems if label in counted] or list(day.problems)
    stamp = f"{day.date:%d.%m.%Y}"
    return (f"  · {stamp} {_DAYS[day.date.weekday()]} — {', '.join(shown)}"
            f" ({_reading(day)})")


def compose(person: Person, days: Iterable[ProblemDay], period: str,
            counted: Iterable[str] = ()) -> Draft:
    """The message for one person about the days that were selected for them.

    Deliberately short. It states the month, lists the days with their reason, asks for
    a correction, and stops. Everything a longer version would add — how the figure was
    computed, what happens next, who decided — is either not the person's question or
    is something this program does not know.

    A person with no listed day still composes: the operator may be writing to somebody
    whose whole month is missing (`Kart bilgisi yok` carries no date at all), and an
    empty day list is not a reason to refuse to write. The body says so in words rather
    than showing an empty bullet list.
    """
    counted = frozenset(counted)
    dated = sorted(days, key=lambda d: d.date)
    ay = period_text(period)

    lines = [f"Sayın {person.name},", "",
             f"{ay} dönemi giriş-çıkış kayıtları incelenmiştir."]
    if dated:
        lines += ["", "Aşağıdaki günlerde kayıtlarınızda eksik ya da tutarsız bir "
                      "durum tespit edilmiştir:", ""]
        lines += [_day_line(day, counted) for day in dated]
    else:
        lines += ["", "Söz konusu dönem için tarafınıza ait giriş-çıkış kaydına "
                      "ulaşılamamıştır."]
    lines += ["", "Yukarıdaki günlere ilişkin durumu bu e-postayı yanıtlayarak "
                  "bildirmenizi rica ederiz.", "", "İyi çalışmalar."]

    # The subject is the month and nothing else. It carried the day count, which put a
    # number in the one line the reader sees before opening anything — and a number in a
    # subject line invites being read as the point of the message. The point is inside.
    return Draft(to=(person.email or "").strip(),
                 subject=f"{ay} mesai kayıtları",
                 body="\n".join(lines))
