"""The message text and the send path. Nothing here opens a socket.

`sender.send` takes a `transport` for exactly this: the wiring — credentials read, MIME
built, headers set — is covered without a live connection and without an account, so
the suite can never mail a real person by accident.
"""

from datetime import date
from pathlib import Path

import pytest

from mesai.mail import message, sender, template as mail_template
from mesai.snapshot import Person, ProblemDay


@pytest.fixture(scope="module")
def tpl():
    """The template that actually ships, read from `config/`.

    Not a copy written here: the wording left the code (ADR-078) so it could be edited
    without a rebuild, and a test against a private copy would stop testing the thing
    that gets sent. Break the shipped file and these go red.
    """
    return mail_template.load(Path("config"))


def person(name="AYŞE DENEME", email="ayse@example.com"):
    return Person(
        name=name, email=email, personnel_no=None, department=None, facility=None,
        in_roster=True, has_attendance=True, worked_days=20, minutes=9000,
        remote_days=0.0, leave_days=0.0, problems=(), expected=(), notes=())


def day(d, problems=("Çıkış yok",), entry="07:41", exit=""):
    return ProblemDay(date=date(2026, 7, d), problems=tuple(problems),
                      entry=entry, exit=exit)


# --- the text --------------------------------------------------------------

def test_the_month_is_written_in_words(tpl):
    """`2026-07` is not what the reader thinks in."""
    assert message.period_text("2026-07") == "Temmuz 2026"
    assert message.period_text("2026-01") == "Ocak 2026"


def test_the_body_lists_the_days_with_their_reason(tpl):
    draft = message.compose(person(), [day(14), day(3)], "2026-07", {"Çıkış yok"}, template=tpl)

    assert draft.to == "ayse@example.com"
    # The month and nothing else. It carried the day count, which put a number in the
    # one line read before anything is opened.
    assert draft.subject == "Temmuz 2026 mesai kayıtları"
    assert draft.body.startswith("Sayın AYŞE DENEME,")
    # Sorted, and each line says which day of the week — a bare date makes the reader
    # go and look it up before they can remember anything about it — and what was read.
    assert "03.07.2026 Cum — Çıkış yok (giriş 07:41, çıkış kaydı yok)" in draft.body
    assert "14.07.2026 Sal — Çıkış yok (giriş 07:41, çıkış kaydı yok)" in draft.body
    assert draft.body.index("03.07") < draft.body.index("14.07")
    assert draft.is_sendable


def test_only_the_ticked_note_is_written(tpl):
    """The trap `HANDOVER.md` §1 names: a day can carry more than one note.

    July has two days that are both `Çıkış yok` and `Günlük süre çok kısa`. Writing the
    second one asks about something nobody selected.
    """
    ikili = day(9, problems=("Çıkış yok", "Günlük süre çok kısa (<2 saat)"))
    draft = message.compose(person(), [ikili], "2026-07", {"Çıkış yok"}, template=tpl)

    assert "Çıkış yok" in draft.body
    assert "Günlük süre çok kısa" not in draft.body


def test_with_no_note_ticked_the_day_still_says_why_it_is_listed(tpl):
    """A dated line with no reason is a date the reader cannot answer."""
    draft = message.compose(person(), [day(9)], "2026-07", set(), template=tpl)
    assert "09.07.2026 Per — Çıkış yok" in draft.body


def test_each_line_says_what_was_actually_read_that_day(tpl):
    """*"giriş çıkış saatlerini de ekleyebilir miyiz o günler için?"* — and it is the
    difference between answering and having to go and ask somebody.

    The missing half is named, never dashed: a dash beside a time reads as a formatting
    artefact to somebody reading this once on a phone.
    """
    tam = day(2, entry="07:41", exit="18:26")
    girissiz = day(3, problems=("Giriş yok",), entry="", exit="18:26")
    bossuz = day(4, problems=("Hem giriş hem çıkış yok",), entry="", exit="")
    body = message.compose(person(), [tam, girissiz, bossuz, day(5)],
                           "2026-07", set(), template=tpl).body

    assert "(giriş 07:41, çıkış 18:26)" in body
    assert "(giriş kaydı yok, çıkış 18:26)" in body
    assert "(giriş ve çıkış kaydı yok)" in body
    assert "(giriş 07:41, çıkış kaydı yok)" in body
    assert "—," not in body and ", —" not in body, "eksik yarım tire ile yazılmamalı"


def test_a_person_with_no_dated_day_still_composes(tpl):
    """`Kart bilgisi yok` carries no date, and is the most important one to write about.

    An empty bullet list would be the wrong shape, so the body says it in words.
    """
    draft = message.compose(person(), [], "2026-07", set(), template=tpl)

    assert "ulaşılamamıştır" in draft.body
    assert "·" not in draft.body
    assert draft.is_sendable


def test_the_message_names_nobody_and_no_department(tpl):
    """AGENTS §6, and it applies to what leaves the machine most of all.

    The failure this guards is on the record: the report once said
    `45 dk kesinti İK talebiyle kapatıldı` when no such request had ever been made.
    """
    draft = message.compose(person(), [day(14)], "2026-07", {"Çıkış yok"}, template=tpl)
    text = f"{draft.subject}\n{draft.body}"

    for yasak in ("İK", "IK", "IT", "HR", "onay bekl", "talebiyle",
                  "ile kontrol", "müdür", "yönetici", "departman"):
        assert yasak not in text, yasak


def test_a_person_without_an_address_composes_but_is_not_sendable(tpl):
    """The address is typed in by hand for these eight people a month.

    Refusing to compose would mean the operator cannot even see what to send.
    """
    draft = message.compose(person(email=None), [day(14)], "2026-07", set(), template=tpl)

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


def test_the_committed_example_is_loadable_but_not_a_working_account(tpl):
    """It exists so nobody has to guess the key names; it must not look real."""
    from pathlib import Path

    import yaml
    raw = yaml.safe_load(Path("config/gmail.example.yaml").read_text(encoding="utf-8"))

    assert set(raw) == {"adres", "uygulama_sifresi", "gorunen_ad", "bilgi"}
    assert raw["uygulama_sifresi"] == "x" * 16, "the example must be obviously fake"


def test_the_display_name_is_used_when_present(tmp_path):
    (tmp_path / "gmail.yaml").write_text(
        "adres: a@gmail.com\nuygulama_sifresi: x\ngorunen_ad: Mesai Takip\n",
        encoding="utf-8")
    hesap = sender.load_account(tmp_path)

    assert hesap.sender == "Mesai Takip <a@gmail.com>"
    assert sender.Account("a@gmail.com", "x").sender == "a@gmail.com"


# --- the send path ---------------------------------------------------------

def test_send_builds_the_message_and_hands_it_to_the_transport(tpl):
    hesap = sender.Account("a@gmail.com", "x", "Mesai Takip")
    draft = message.compose(person(), [day(14)], "2026-07", {"Çıkış yok"}, template=tpl)
    gonderilen = []

    sender.send(draft, hesap, transport=lambda mail, acc: gonderilen.append(mail))

    assert len(gonderilen) == 1
    mail = gonderilen[0]
    assert mail["To"] == "ayse@example.com"
    assert mail["From"] == "Mesai Takip <a@gmail.com>"
    assert mail["Subject"] == draft.subject

    # Two parts, because the shipped template carries an HTML table. `alternative`, not
    # `mixed`: they are the same message twice, and a client shows one of them.
    assert mail.get_content_type() == "multipart/alternative"
    parts = list(mail.iter_parts())
    türler = [p.get_content_type() for p in parts]
    assert türler == ["text/plain", "text/html"], türler
    # UTF-8 on both, because the body is Turkish and the project's own lesson is that
    # encoding is never assumed (AGENTS §2.4).
    assert all(p.get_content_charset() == "utf-8" for p in parts)
    # The same information in both. A reader must not learn a different thing depending
    # on which part their mail program renders.
    for part in parts:
        icerik = part.get_content()
        assert "AYŞE DENEME" in icerik
        assert "14.07.2026" in icerik
        assert "Çıkış yok" in icerik


def test_a_template_with_no_html_sends_one_part(tpl):
    """The HTML block is optional and empty is a correct message — it is what shipped
    first. A single-part mail must stay single-part."""
    from dataclasses import replace as _replace

    hesap = sender.Account("a@gmail.com", "x")
    duz = _replace(tpl, html_govde="", html_gun_satiri="")
    draft = message.compose(person(), [day(14)], "2026-07", set(), template=duz)

    assert not draft.html
    mail = sender.build(draft, hesap)
    assert mail.get_content_type() == "text/plain"
    assert mail.get_content_charset() == "utf-8"


def test_send_refuses_an_empty_address_before_touching_the_network(tpl):
    hesap = sender.Account("a@gmail.com", "x")
    draft = message.compose(person(email=None), [day(14)], "2026-07", set(), template=tpl)
    tasindi = []

    with pytest.raises(sender.MailError):
        sender.send(draft, hesap, transport=lambda mail, acc: tasindi.append(mail))
    assert not tasindi


def test_send_refuses_an_empty_body(tpl):
    from dataclasses import replace

    hesap = sender.Account("a@gmail.com", "x")
    draft = replace(message.compose(person(), [day(14)], "2026-07", set(), template=tpl), body="  ")

    with pytest.raises(sender.MailError):
        sender.send(draft, hesap, transport=lambda mail, acc: None)


def test_there_is_no_bulk_send(tpl):
    """One at a time is a decision, not an omission (HANDOVER §1 has the three open
    questions). A helper that loops would be the whole risk in one call."""
    isimler = dir(sender)

    assert not [n for n in isimler
                if any(k in n.lower() for k in ("all", "bulk", "many", "each",
                                                "batch", "broadcast"))]


# --- the template file itself ----------------------------------------------

def _write(dizin, **degistir):
    """The shipped template with some fields replaced, in a temp config dir."""
    import yaml
    raw = yaml.safe_load((Path("config") / "mail-taslagi.yaml").read_text("utf-8"))
    raw.update(degistir)
    (dizin / "mail-taslagi.yaml").write_text(
        yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return dizin


def test_the_shipped_template_loads_and_carries_html(tpl):
    """If the committed file is broken, everything about the mail step is broken."""
    assert tpl.konu and tpl.govde and tpl.gun_satiri and tpl.gunsuz_govde
    assert tpl.has_html, "sevk edilen taslakta tablo var"


def test_the_shipped_template_names_nobody_and_no_department(tpl):
    """AGENTS §6, and the wording is hand-editable now — the rule did not move out of
    the code just because the words did.

    The failure this guards is on the record: the report once said
    `45 dk kesinti İK talebiyle kapatıldı` when no such request had ever been made.
    """
    from dataclasses import asdict

    metin = "\n".join(str(v) for v in asdict(tpl).values())
    for yasak in ("İK", "IK", " IT ", "HR", "onay bekl", "talebiyle",
                  "ile kontrol", "müdür", "yönetici", "departman"):
        assert yasak not in metin, yasak


def test_a_missing_template_file_says_where_it_should_be(tmp_path):
    """No built-in fallback: a fallback is invisible, and the operator would edit the
    file, see no change, and have no way to tell which copy is in use."""
    with pytest.raises(mail_template.TemplateError) as hata:
        mail_template.load(tmp_path)
    assert "mail-taslagi.yaml" in str(hata.value)


def test_an_empty_required_field_fails_rather_than_sending_nothing(tmp_path):
    with pytest.raises(mail_template.TemplateError) as hata:
        mail_template.load(_write(tmp_path, govde=""))
    assert "govde" in str(hata.value)


def test_an_unknown_placeholder_fails_before_anything_is_sent(tmp_path):
    """A typo has to stop the send, not produce a message with a literal `{isim}` in it.

    This is the whole risk of moving wording into a hand-edited file, so it is the first
    thing the loader checks and the error names both the field and the alternatives.
    """
    with pytest.raises(mail_template.TemplateError) as hata:
        mail_template.load(_write(tmp_path, govde="Sayın {isim},\n{gunler}"))

    metin = str(hata.value)
    assert "{isim}" in metin
    assert "{ad}" in metin, "ne yazması gerektiğini de söylemeli"


def test_a_day_field_cannot_be_used_in_the_body(tmp_path):
    """`{tarih}` in the body would silently render empty — the body is about the month."""
    with pytest.raises(mail_template.TemplateError) as hata:
        mail_template.load(_write(tmp_path, govde="Sayın {ad}, {tarih}\n{gunler}"))
    assert "{tarih}" in str(hata.value)


def test_an_html_body_with_no_row_template_fails(tmp_path):
    """It would render a table with no rows, which looks like a bug and is one."""
    with pytest.raises(mail_template.TemplateError) as hata:
        mail_template.load(_write(tmp_path, html_gun_satiri=""))
    assert "html_gun_satiri" in str(hata.value)


def test_both_html_fields_empty_is_allowed(tmp_path):
    """Plain text only is a correct message and must stay possible."""
    tpl = mail_template.load(_write(tmp_path, html_govde="", html_gun_satiri="",
                                    html_gunsuz_govde=""))
    assert not tpl.has_html


def test_the_wording_really_comes_from_the_file(tmp_path):
    """The point of the whole change: edit the file, the message changes. No rebuild."""
    tpl = mail_template.load(_write(
        tmp_path, konu="{donem} icin bilgi", govde="Merhaba {ad}.\n{gunler}",
        gun_satiri="- {tarih}: {sorun}"))
    draft = message.compose(person(), [day(14)], "2026-07", {"Çıkış yok"},
                            template=tpl)

    assert draft.subject == "Temmuz 2026 icin bilgi"
    assert draft.body.startswith("Merhaba AYŞE DENEME.")
    assert "- 14.07.2026: Çıkış yok" in draft.body


def test_a_name_reaching_the_html_part_is_escaped(tmp_path):
    """A name comes from a source file and goes into markup.

    Not because a badge export is expected to contain `<`, but because "this value cannot
    contain markup" is an assumption about somebody else's system, and this project makes
    no such assumption anywhere else either.
    """
    draft = message.compose(person(name='AYŞE <b>DENEME</b>'), [day(14)], "2026-07",
                            set(), template=mail_template.load(Path("config")))

    assert "&lt;b&gt;" in draft.html
    assert "<b>DENEME" not in draft.html
    assert "<b>DENEME</b>" in draft.body, "düz metin kısmı olduğu gibi kalır"


def test_cc_comes_from_the_account_file_and_reaches_the_header(tmp_path, tpl):
    """Default, not rule: typed once in `gmail.yaml`, editable before every send."""
    (tmp_path / "gmail.yaml").write_text(
        "adres: a@gmail.com\nuygulama_sifresi: x\nbilgi: bir@deico.com.tr, iki@deico.com.tr\n",
        encoding="utf-8")
    hesap = sender.load_account(tmp_path)
    assert hesap.cc == ("bir@deico.com.tr", "iki@deico.com.tr")

    from dataclasses import replace
    draft = replace(message.compose(person(), [day(14)], "2026-07", set(), template=tpl),
                    cc=", ".join(hesap.cc))
    gonderilen = []
    sender.send(draft, hesap, transport=lambda mail, acc: gonderilen.append(mail))

    assert gonderilen[0]["Cc"] == "bir@deico.com.tr, iki@deico.com.tr"


def test_cc_accepts_a_yaml_list_too(tmp_path):
    """A hand-edited file gets written both ways; refusing one would be a config that
    is right and rejected."""
    (tmp_path / "gmail.yaml").write_text(
        "adres: a@gmail.com\nuygulama_sifresi: x\nbilgi:\n  - bir@deico.com.tr\n  - iki@deico.com.tr\n",
        encoding="utf-8")
    assert sender.load_account(tmp_path).cc == ("bir@deico.com.tr", "iki@deico.com.tr")


def test_no_cc_means_no_header(tmp_path, tpl):
    """An empty `Cc:` header is worse than none — some clients show it as a blank row."""
    hesap = sender.Account("a@gmail.com", "x")
    draft = message.compose(person(), [day(14)], "2026-07", set(), template=tpl)
    gonderilen = []
    sender.send(draft, hesap, transport=lambda mail, acc: gonderilen.append(mail))

    assert gonderilen[0]["Cc"] is None
