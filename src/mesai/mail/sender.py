"""Sending one message through Gmail's SMTP, and where the credentials live.

**One at a time, on purpose.** There is no bulk send here and the window offers none:
the operator picks a person, reads the draft, and sends it. 162 e-mails cannot be
recalled, and every rule in this project about lists that decide who gets contacted
(ADR-017, ADR-048, ADR-061) exists because the expensive mistake is the silent one. A
loop over the whole list is a decision that has not been taken yet (`HANDOVER.md` §1),
not a feature that was forgotten.

**Credentials never enter the repository.** They live in `config/gmail.yaml`, which
`.gitignore` keeps out the same way it keeps out `personel.yaml` — the file holds an
account and an app password, which is a login, and AGENTS.md §2.3 puts logins in the
same class as names. An app password is not the account password: Gmail issues a
16-character one per application once 2FA is on, and it can be revoked on its own.

Nothing here retries. A failed send is reported to the operator with what the server
said, because the two failures this will actually produce — a wrong app password and a
blocked sign-in — are both fixed by a person, not by trying again.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

import yaml

from .message import Draft

HOST = "smtp.gmail.com"
PORT = 587

CONFIG_NAME = "gmail.yaml"

SETUP_HELP = (
    "Gmail hesabı ayarlanmamış. config/gmail.yaml dosyasını şu şekilde oluşturun:\n\n"
    "    adres: hesap@gmail.com\n"
    "    uygulama_sifresi: xxxxxxxxxxxxxxxx\n"
    "    gorunen_ad: Mesai Takip\n\n"
    "Uygulama şifresi hesabın kendi şifresi değildir: Google hesabında iki adımlı "
    "doğrulama açıkken 'uygulama şifreleri' bölümünden 16 haneli bir şifre üretilir. "
    "Bu dosya git'e girmez."
)


class MailError(Exception):
    """Anything that stopped a message from leaving, in words for the operator."""


@dataclass(frozen=True)
class Account:
    address: str
    app_password: str
    display_name: str = ""

    @property
    def sender(self) -> str:
        return f"{self.display_name} <{self.address}>" if self.display_name \
            else self.address


def load_account(config_dir: Path) -> Account:
    """Read `config/gmail.yaml`, or say exactly what to put in it.

    Keys are Turkish because a human edits this file by hand, unlike the rest of
    `config/` which the program's own rules live in. Missing keys fail here rather
    than at the SMTP handshake, where the error would be about authentication and the
    cause would be a typo.
    """
    path = config_dir / CONFIG_NAME
    if not path.exists():
        raise MailError(SETUP_HELP)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise MailError(f"{path.name} okunamadı: {exc}") from exc
    if not isinstance(raw, dict):
        raise MailError(f"{path.name} bir eşleme olmalı.\n\n{SETUP_HELP}")

    address = str(raw.get("adres") or "").strip()
    password = str(raw.get("uygulama_sifresi") or "").strip()
    missing = [name for name, value in (("adres", address),
                                        ("uygulama_sifresi", password)) if not value]
    if missing:
        raise MailError(f"{path.name} eksik: {', '.join(missing)}.\n\n{SETUP_HELP}")
    return Account(address=address,
                   app_password=password.replace(" ", ""),
                   display_name=str(raw.get("gorunen_ad") or "").strip())


def build(draft: Draft, account: Account) -> EmailMessage:
    """The MIME message. UTF-8 throughout — the body is Turkish.

    Plain text always, and an HTML alternative when the template carries one
    (`config/mail-taslagi.yaml`). `multipart/alternative` rather than HTML alone: a mail
    program that will not render HTML shows the plain part, and the two carry the same
    information — a reader must not learn a different thing depending on which one they
    see. The plain part is first, which is what the standard asks for; the client shows
    the last part it can render.
    """
    mail = EmailMessage()
    mail["From"] = account.sender
    mail["To"] = draft.to
    mail["Subject"] = draft.subject
    mail.set_content(draft.body, subtype="plain", charset="utf-8")
    if draft.html.strip():
        mail.add_alternative(draft.html, subtype="html", charset="utf-8")
    return mail


def send(draft: Draft, account: Account, transport=None) -> None:
    """Send one message. Raises `MailError` with something the operator can act on.

    `transport` exists for the tests: a fake that records what it was handed, so the
    wiring is covered without a live connection and without an account. Nothing in the
    suite ever opens a socket.
    """
    if not draft.to.strip():
        raise MailError("Alıcı adresi boş.")
    if not draft.body.strip():
        raise MailError("Mesaj gövdesi boş.")

    mail = build(draft, account)
    if transport is not None:
        transport(mail, account)
        return

    try:
        with smtplib.SMTP(HOST, PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(account.address, account.app_password)
            smtp.send_message(mail)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError(
            "Gmail girişi reddedildi. Uygulama şifresi yanlış ya da iptal edilmiş "
            f"olabilir.\n\nSunucunun yanıtı: {exc.smtp_code} "
            f"{exc.smtp_error.decode('utf-8', 'replace') if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"Gönderilemedi: {exc}") from exc
