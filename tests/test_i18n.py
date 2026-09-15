import pytest

def test_dynamic_i18n_translation():
    from doremi.utils.i18n import _, set_language
    
    # Set to Spanish
    set_language("es")
    assert _("Inicio") == "Inicio"
    assert _("Apariencia") == "Apariencia"
    
    # Set to English
    set_language("en")
    assert _("Inicio") == "Home"
    assert _("Apariencia") == "Appearance"
    
    # Fallback to key when translation is missing
    assert _("Texto No Traducido") == "Texto No Traducido"


def test_i18n_format_and_plural_helpers():
    from doremi.utils.i18n import _f, ngettext, set_language

    set_language("es")
    assert _f("Hola {name}", name="Doremi") == "Hola Doremi"
    assert ngettext("{count} canción", "{count} canciones", 1) == "1 canción"
    assert ngettext("{count} canción", "{count} canciones", 3) == "3 canciones"

    set_language("en")
    assert _f("Hola {name}", name="Doremi") == "Hola Doremi"
