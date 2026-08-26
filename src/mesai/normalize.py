"""Turkish-safe name normalization and identity keys.

Never use bare str.upper() / str.lower() on a Turkish name anywhere in this project.
`"İ".lower()` returns `"i̇"` — two codepoints — which silently breaks equality.
See AGENTS.md §2.4.
"""

from __future__ import annotations

import unicodedata

# Lowercase -> uppercase, Turkish rules. Applied before str.upper() so that the
# dotted/dotless i pair survives.
_TR_UPPER = str.maketrans({
    "i": "İ", "ı": "I", "ş": "Ş", "ğ": "Ğ", "ü": "Ü", "ö": "Ö", "ç": "Ç",
})

# Turkish uppercase -> ASCII, for building match keys. Note that İ, I and ı all
# fold to "I": this is what makes MELİK/MELIK and DENEMEÇİ/DENEMECİ resolve without
# an alias entry.
_FOLD = str.maketrans({
    "İ": "I", "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C", "Â": "A", "Î": "I",
})


def tr_upper(s: str) -> str:
    """Uppercase using Turkish casing rules."""
    return s.translate(_TR_UPPER).upper()


def display_name(s: object) -> str:
    """Canonical display form: NFC, collapsed whitespace, Turkish uppercase."""
    if s is None:
        return ""
    text = unicodedata.normalize("NFC", str(s))
    return tr_upper(" ".join(text.split()))


def fold(s: object) -> str:
    """ASCII-folded uppercase form, for comparison only. Never displayed."""
    folded = display_name(s).translate(_FOLD)
    return unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()


def name_tokens(s: object) -> list[str]:
    """Folded name tokens, dropping single-letter initials such as "M.".

    The IAS roster stores only the first given name, so middle names must not
    participate in the key. Initials are dropped because they carry no information
    the key can use.
    """
    return [t for t in fold(s).split() if len(t.rstrip(".")) > 1]


# Turkish alphabet order. Q, W and X are not in it but occur in foreign names, so
# they are slotted where a Turkish reader would expect them.
_ALPHABET = "AÂBCÇDEFGĞHIİJKLMNOÖPQRSŞTUÜVWXYZ"
_COLLATION = {char: index for index, char in enumerate(_ALPHABET)}


def sort_key(s: object) -> tuple[tuple[int, int], ...]:
    """Collation key for Turkish alphabetical order.

    Python's default string sort compares codepoints, which puts Ç, Ğ, İ, Ö, Ş and Ü
    after Z — so `ŞÜKRÜ` and `İBRAHİM` land at the bottom of a name list instead of
    after `S` and `I`. Every user-facing ordering must use this function.

    Each character becomes a (class, rank) pair: spaces sort before letters, letters
    by their position in the Turkish alphabet, anything else after both.
    """
    out: list[tuple[int, int]] = []
    for char in display_name(s):
        if char.isspace():
            out.append((0, 0))
        elif char in _COLLATION:
            out.append((1, _COLLATION[char]))
        else:
            out.append((2, ord(char)))
    return tuple(out)


def name_key(s: object) -> tuple[str, str]:
    """(first token, last token) — the identity key. See ADR-010.

    "AHMET CAN SINAMA" and roster "AHMET SINAMA" both yield ("AHMET", "SINAMA").
    """
    tokens = name_tokens(s)
    if not tokens:
        return ("", "")
    if len(tokens) == 1:
        return (tokens[0], "")
    return (tokens[0], tokens[-1])


def is_excluded(full_name: object, given: object, surname: object,
                prefixes: tuple[str, ...]) -> bool:
    """True for visitor/temporary badges — see docs/DATA-SOURCES.md D4.

    Requires BOTH that given name equals surname AND that the token matches a
    configured prefix. Either condition alone would drop legitimate people.
    """
    if given is None or surname is None:
        folded = fold(full_name)
        parts = folded.split()
        if len(parts) < 2 or parts[0] != parts[-1]:
            return False
        token = parts[0]
    else:
        if fold(given) != fold(surname):
            return False
        token = fold(given)
    return any(token.startswith(p) for p in prefixes)
