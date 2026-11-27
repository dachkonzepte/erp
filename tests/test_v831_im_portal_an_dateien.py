"""Version 1.11.39 (Stufe P2c, Teil 4): „Im Portal zeigen“ an den Dateien -- Wächter über die Vorlagen (die Abläufe prüft
scripts/klicktest_kundenportal_an_dateien.py).

    Plätze      jede Seite setzt je Datei einen Platz <span data-ip-quelle="…" data-ip-id="…">; jede genannte Quelle ist eine aus FREIGABE_QUELLEN; die Seiten
                mit Dateien haben genau ihre Quellen (Kundenakte, Akte, Objekt, Mängel, Abnahme) und rufen danach imPortalAnDateien(); der Einsatzbericht
                öffnet für seine Fotos die Auswahl (imPortalFotos)
    Baustein    jede dieser Seiten bindet _im_portal.html ein (die Mängel und Abnahme über die Akte); der Dialog steht nur mit Modul und ab Büro – Auftrag
                im HTML, ungerendert ist IM_PORTAL_DARF aus
    Belege      an Belegen der Abnahme und Dateien am Mangel nur, solange die Datei unverändert ist
"""

import re

from app.portal import werte
from tests import vorlagen_js as vj

SEITEN = {
    "customer.html": {"customer_documents"},
    "akte.html": {"project_documents"},
    "property.html": {"property_documents", "project_documents"},
    "_maengel.html": {"defect_files"},
    "_abnahme.html": {"order_acceptance_files"},
}
EINBINDEN = {"customer.html": "customer.html", "akte.html": "akte.html", "property.html": "property.html", "_maengel.html": "akte.html",
             "_abnahme.html": "akte.html", "service_report.html": "service_report.html"}


def _text(name):
    return vj.TEMPLATES.joinpath(name).read_text(encoding="utf-8")


def _quellen(text):
    """Die Quellen der Plätze -- auch in einem bedingten Ausdruck (Objekt: Datei des Objekts oder des Projekts)."""
    aus = set()
    for wert in re.findall(r'data-ip-quelle="([^"]+)"', text):
        aus |= set(re.findall(r"[a-z_]+", wert)) & set(werte.FREIGABE_QUELLEN) if "${" in wert else {wert}
    return aus


def test_jede_quelle_eines_platzes_ist_bekannt():
    for name in vj.alle_vorlagen():
        if name == "_im_portal.html":
            continue  # der Baustein nennt den Platz nur in seinem Kopfkommentar („…“)
        for wert in re.findall(r'data-ip-quelle="([^"$]+)"', _text(name)):
            assert wert in werte.FREIGABE_QUELLEN, (name, wert)


def test_seiten_mit_dateien_haben_ihre_plaetze_und_rufen_den_baustein():
    for name, quellen in SEITEN.items():
        text = _text(name)
        assert _quellen(text) == quellen, name
        assert "imPortalAnDateien(" in text, name
    gefunden = {name for name in vj.alle_vorlagen() if name != "_im_portal.html" and "data-ip-quelle=" in _text(name)}
    assert gefunden == set(SEITEN), gefunden  # eine neue Seite mit Plätzen kommt in SEITEN


def test_einsatzbericht_oeffnet_die_auswahl_nur_fuers_buero():
    text = _text("service_report.html")
    assert "imPortalFotos({quelle:'service_report_photos'" in text
    assert "if(IM_PORTAL_DARF&&DARF_BUERO&&FOTOS.length)" in text


def test_jede_seite_bindet_den_baustein_ein():
    for seite in set(EINBINDEN.values()):
        assert vj.bindet_ein(seite, "_im_portal.html"), seite


def test_dialog_nur_mit_modul_und_buero():
    text = _text("_im_portal.html")
    assert ("{% set im_portal_darf = is_module_enabled('kundenportal') and can(request.state.erp_user, 'admin', 'buero_finanzen', 'buero_auftrag') %}"
            in text)
    assert text.index("{% if im_portal_darf %}") < text.index('<dialog id="imPortalDialog"') < text.index("{% endif %}")
    assert 'const IM_PORTAL_DARF = "{{ \'ja\' if im_portal_darf else \'nein\' }}" === "ja";' in text


def test_belege_nur_unveraendert():
    for name in ("_maengel.html", "_abnahme.html"):
        assert "${f.status==='unveraendert'?` <span data-ip-quelle=" in _text(name), name
