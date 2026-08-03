"""Turkish casing, identity keys, and collation — the traps that fail silently."""

from mesai.normalize import (
    display_name, fold, is_excluded, name_key, sort_key, tr_upper,
)


def test_dotted_i_survives_uppercasing():
    # Python's own str.lower() on "İ" yields two codepoints; nothing in this project
    # may depend on it. tr_upper is the only casing path.
    assert tr_upper("irem") == "İREM"
    assert tr_upper("ışık") == "IŞIK"
    assert len("İ".lower()) == 2, "stdlib behaviour changed; revisit normalize.py"


def test_display_name_collapses_whitespace():
    assert display_name("  ahmet   can  sınama ") == "AHMET CAN SINAMA"
    assert display_name(None) == ""


def test_fold_maps_turkish_variants_together():
    # These pairs are entered inconsistently at source and must resolve without
    # an alias entry — docs/DATA-SOURCES.md §6.1 group A.
    assert fold("AYŞE DENEMEÇİ") == fold("AYŞE DENEMECİ")
    assert fold("VELİ ÖRNEKÇİ") == fold("VELİ ÖRNEKCİ")
    assert fold("MELİK NUMUNE") == fold("MELIK NUMUNE")
    assert fold("ÜMİT TASLAK") == fold("ÜMIT TASLAK")


def test_name_key_ignores_middle_names():
    # The roster stores only the first given name — ADR-010.
    assert name_key("AHMET CAN SINAMA") == name_key("AHMET SINAMA")
    assert name_key("AYLA NUR MİSAL") == name_key("AYLA MİSAL")
    assert name_key("HANDE NUR ÖRNEK TASLAK") == name_key("HANDE ÖRNEK TASLAK")


def test_name_key_drops_initials():
    assert name_key("M. KEREM ÖRNEK") == ("KEREM", "ORNEK")


def test_name_key_edge_cases():
    assert name_key("") == ("", "")
    assert name_key("MADONNA") == ("MADONNA", "")


def test_name_key_does_not_merge_different_people():
    assert name_key("AHMET SINAMA") != name_key("TAHA SINAMA")
    assert name_key("ARDA TASLAK") != name_key("ARDA MİSAL")


def test_surname_change_is_not_bridged_by_the_key():
    # Deliberate: a changed surname alters the last token, so it needs a config
    # alias rather than a silent guess.
    assert name_key("SEDA DENEME") != name_key("BÜŞRA ÜNAL")


PREFIXES = ("ZIYARETCI", "GECICI", "STJ")


def test_excludes_shared_badges():
    assert is_excluded("ZİYARETÇİ35 ZİYARETÇİ35", "ZİYARETÇİ35", "ZİYARETÇİ35", PREFIXES)
    assert is_excluded("GEÇİCİ6 GEÇİCİ6", "GEÇİCİ6", "GEÇİCİ6", PREFIXES)
    assert is_excluded("STJ20 STJ20", "STJ20", "STJ20", PREFIXES)


def test_exclusion_requires_both_conditions():
    # A real person whose given name equals their surname must survive.
    assert not is_excluded("KEMAL KEMAL", "KEMAL", "KEMAL", PREFIXES)
    # A real person whose surname merely starts with a prefix must survive.
    assert not is_excluded("AHMET STJEPANOVIC", "AHMET", "STJEPANOVIC", PREFIXES)


# --- collation (Turkish alphabetical order) --------------------------------

def test_turkish_letters_sort_in_the_right_place():
    """Python's default sort puts Ç Ğ İ Ö Ş Ü after Z, which is wrong for a
    Turkish name list. Ordered: A B C Ç D E F G Ğ H I İ J ... O Ö P R S Ş T U Ü V Y Z
    """
    names = ["ZEYNEP", "ŞEYMANUR", "İBRAHİM", "ÜMİT", "ÖMER", "ÇAĞLA", "AHMET",
             "SALİH", "UMUTCAN", "OĞUZHAN", "IŞIK", "CAN", "GÜL", "GÖKHAN"]
    assert sorted(names, key=sort_key) == [
        "AHMET", "CAN", "ÇAĞLA", "GÖKHAN", "GÜL", "IŞIK", "İBRAHİM", "OĞUZHAN",
        "ÖMER", "SALİH", "ŞEYMANUR", "UMUTCAN", "ÜMİT", "ZEYNEP",
    ]
    # And the naive sort really does get it wrong, so the helper is not redundant.
    assert sorted(names) != sorted(names, key=sort_key)


def test_each_turkish_pair_orders_correctly():
    for earlier, later in [("CAN", "ÇAM"), ("GUL", "GÜL"), ("GAZI", "GÖZ"),
                           ("ILGIN", "İLKER"), ("OZAN", "ÖZGE"),
                           ("SAMET", "ŞAHİN"), ("UFUK", "ÜMİT")]:
        assert sort_key(earlier) < sort_key(later), f"{earlier} < {later}"


def test_space_sorts_before_letters():
    assert sort_key("AHMET CAN") < sort_key("AHMETCAN")


def test_sort_key_is_case_and_whitespace_insensitive():
    assert sort_key("  ahmet   can  ") == sort_key("AHMET CAN")


def test_sort_key_handles_empty_and_none():
    assert sort_key("") == ()
    assert sort_key(None) == ()


def test_unknown_characters_sort_last_but_deterministically():
    assert sort_key("ZEYNEP") < sort_key("(BOŞ)")
    assert sort_key("(A)") == sort_key("(A)")
