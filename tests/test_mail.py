"""The message text and the send path. Nothing here opens a socket.

`sender.send` takes a `transport` for exactly this: the wiring — credentials read, MIME
built, headers set — is covered without a live connection and without an account, so
the suite can never mail a real person by accident.
"""

from datetime import date

import pytest

from mesai.mail import message, sender
from mesai.snapshot import Person, ProblemDay


def person(name="AYŞE DENEME", email="ayse@example.com"):
    return Person(
        name=name, email=email, personnel_no=None, department=None, facility=None,
        in_roster=True, has_attendance=True, worked_days=20, minutes=9000,
        remote_days=0.0, leave_days=0.0, problems=(), expected=(), notes=())


def day(d, problems=("Çıkış yok",), entry="07:41", exit=""):
    return ProblemDay(date=date(2026, 7, d), problems=tuple(problems),
                      entry=entry, exit=exit)


# --- the text --------------------------------------------------------------

def test_the_month_is_written_in_words():
    """`2026-07` is not what the reader thinks in."""
    assert message.period_text("2026-07") == "Temmuz 2026"
    assert message.period_text("2026-01") == "Ocak 2026"


def test_the_body_lists_the_days_with_their_reason():
    draft = message.compose(person(), [day(14), day(3)], "2026-07", {"Çıkış yok"})

    assert draft.to == "ayse@example.com"
    assert "Temmuz 2026" in draft.subject and "2 gün" in draft.subject
    assert draft.body.startswith("Sayın AYŞE DENEME,")
    # Sorted, and each line says which day of the week — a bare date makes the reader
    # go and look it up before they can remember anything about it.
    assert "03.07.2026 Cum — Çıkış yok" in draft.body
    assert "14.07.2026 Sal — Çıkış yok" in draft.body
    assert draft.body.index("03.07") < draft.body.index("14.07")
    assert draft.is_sendable


def test_only_the_ticked_note_is_written():
    """The trap `HANDOVER.md` §1 names: a day can carry more than one note.

    July has two days that are both `Çıkış yok` and `Günlük süre çok kısa`. Writing the
    second one asks about something nobody selected.
    """
    ikili = day(9, problems=("Çıkış yok", "Günlük süre çok kısa (<2 saat)"))
    draft = message.compose(person(), [ikili], "2026-07", {"Çıkış yok"})

    assert "Çıkış yok" in draft.body
    assert "Günlük süre çok kısa" not in draft.body


def test_with_no_note_ticked_the_day_still_says_why_it_is_listed():
    """A dated line with no reason is a date the reader cannot answer."""
    draft = message.compose(person(), [day(9)], "2026-07", set())
    assert "09.07.2026 Per — Çıkış yok" in draft.body


def test_a_person_with_no_dated_day_still_composes():
    """`Kart bilgisi yok` carries no date, and is the most important one to write about.

    An empty bullet list would be the wrong shape, so the body says it in words.
    """
    draft = message.compose(person(), [], "2026-07", set())

    assert "ulaşılamamıştır" in draft.body
    assert "·" not in draft.body
    assert draft.is_sendable


def test_the_message_names_nobody_and_no_department():
    """AGENTS §6, and it applies to what leaves the machine most of all.

    The failure this guards is on the record: the report once said
    `45 dk kesinti İK talebiyle kapatıldı` when no such request had ever been made.
    """
    draft = message.compose(person(), [day(14)], "2026-07", {"Çıkış yok"})
    text = f"{draft.subject}\n{draft.body}"

    for yasak in ("İK", "IK", "IT", "HR", "onay bekl", "talebiyle",
                  "ile kontrol", "müdür", "yönetici", "departman"):
        assert yasak not in text, yasak


def test_a_person_without_an_address_composes_but_is_not_sendable():
    """The address is typed in by hand for these eight people a month.

    Refusing to compose would mean the operator cannot even see what to send.
    """
    draft = message.compose(person(email=None), [day(14)], "2026-07", set())

    assert draft.to == ""
    assert not draft.is_sendable
    assert "Sayın" in draft.body


# --- credentials -----------------------------------------------------------

def test_a_missing_account_file_says_what_to_write(tmp_path):
    with pytest.raises(sender.MailError) as hata:
        sender.load_account(tmp_path)

    metin = str(hata.value)
    assert "gmail.yaml" in metin
    assert "uygulama_sifresi" in metin
    # It must say the app password is not the account password: getting that wrong is
    # the failure that looks like "Gmail is broken".
    assert "hesabın kendi şifresi değildir" in metin


def test_a_half_filled_account_file_names_the_missing_key(tmp_path):
    (tmp_path / "gmail.yaml").write_text("adres: a@gmail.com\n", encoding="utf-8")

    with pytest.raises(sender.MailError) as hata:
        sender.load_account(tmp_path)
    assert "uygulama_sifresi" in str(hata.value)
    assert "adres" not in str(hata.value).split("\n")[0]


def test_the_app_password_loses_the_spaces_google_shows_it_with(tmp_path):
    """Google prints it as four groups of four. Pasted as shown, login fails."""
    (tmp_path / "gmail.yaml").write_text(
        "adres: a@gmail.com\nuygulama_sifresi: abcd efgh ijkl mnop\n", encoding="utf-8")

    assert sender.load_account(tmp_path).app_password == "abcdefghijklmnop"


def test_the_committed_example_is_loadable_but_not_a_working_account():
    """It exists so nobody has to guess the key names; it must not look real."""
    from pathlib import Path

    import yaml
    raw = yaml.safe_load(Path("config/gmail.example.yaml").read_text(encoding="utf-8"))

    assert set(raw) == {"adres", "uygulama_sifresi", "gorunen_ad"}
    assert raw["uygulama_sifresi"] == "x" * 16, "the example must be obviously fake"


def test_the_display_name_is_used_when_present(tmp_path):
    (tmp_path / "gmail.yaml").write_text(
        "adres: a@gmail.com\nuygulama_sifresi: x\ngorunen_ad: Mesai Takip\n",
        encoding="utf-8")
    hesap = sender.load_account(tmp_path)

    assert hesap.sender == "Mesai Takip <a@gmail.com>"
    assert sender.Account("a@gmail.com", "x").sender == "a@gmail.com"


# --- the send path ---------------------------------------------------------

def test_send_builds_the_message_and_hands_it_to_the_transport():
    hesap = sender.Account("a@gmail.com", "x", "Mesai Takip")
    draft = message.compose(person(), [day(14)], "2026-07", {"Çıkış yok"})
    gonderilen = []

    sender.send(draft, hesap, transport=lambda mail, acc: gonderilen.append(mail))

    assert len(gonderilen) == 1
    mail = gonderilen[0]
    assert mail["To"] == "ayse@example.com"
    assert mail["From"] == "Mesai Takip <a@gmail.com>"
    assert mail["Subject"] == draft.subject
    # UTF-8, because the body is Turkish and the report's own lesson is that encoding
    # is never assumed (AGENTS §2.4).
    assert mail.get_content_charset() == "utf-8"
    assert "Sayın AYŞE DENEME" in mail.get_content()


def test_send_refuses_an_empty_address_before_touching_the_network():
    hesap = sender.Account("a@gmail.com", "x")
    draft = message.compose(person(email=None), [day(14)], "2026-07", set())
    tasindi = []

    with pytest.raises(sender.MailError):
        sender.send(draft, hesap, transport=lambda mail, acc: tasindi.append(mail))
    assert not tasindi


def test_send_refuses_an_empty_body():
    from dataclasses import replace

    hesap = sender.Account("a@gmail.com", "x")
    draft = replace(message.compose(person(), [day(14)], "2026-07", set()), body="  ")

    with pytest.raises(sender.MailError):
        sender.send(draft, hesap, transport=lambda mail, acc: None)


def test_there_is_no_bulk_send():
    """One at a time is a decision, not an omission (HANDOVER §1 has the three open
    questions). A helper that loops would be the whole risk in one call."""
    isimler = dir(sender)

    assert not [n for n in isimler
                if any(k in n.lower() for k in ("all", "bulk", "many", "each",
                                                "batch", "broadcast"))]
