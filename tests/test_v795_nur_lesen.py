"""Version 1.10.24 (Antwort F10 vom 23.11.2026, Teil 2): die Seiten eines Vorgangs im Archiv sind nur lesbar, einzig „Zurückholen“ bleibt.

    Baustein     _nur_lesen.html: nurLesen(an) setzt am <body> die Klasse ds-nur-lesen -- jeder Knopf in Inhalt, Dialogen und Fenstern fehlt außer data-lesen,
                 jedes Feld ist gesperrt (auch was die Seite danach zeichnet), nichts lässt sich ziehen oder ablegen, data-schreiben fehlt; nurLesen(false)
                 nimmt es zurück
    Seiten       Kundenakte, Akte, Objekt, Dachfläche, Angebot und Eingang der Webseite binden ihn ein und rufen nurLesen() genau einmal mit dem Stand des
                 Vorgangs; welche Knöpfe lesend sind (data-lesen), steht hier je Seite -- ein neuer Knopf ist im Archiv von selbst weg
    Server       GET /api/roof-areas/{id} nennt kunde_im_archiv (Hinweis und nur lesen auf der Seite der Dachfläche)
    gemessen     im Browser: scripts/klicktest_nur_lesen.py
"""

import re
from pathlib import Path

import pytest

from tests.vorlagen_js import bindet_ein

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"

# je Seite: der Aufruf von nurLesen() mit dem Stand des Vorgangs
SEITEN = {
    "customer.html": "nurLesen(!!customer.archiviert_am)",
    "akte.html": "nurLesen(project.archived&&!(project.order_count>0))",
    "property.html": "nurLesen(!!geladen.kunde_im_archiv)",
    "roof_area.html": "nurLesen(!!a.kunde_im_archiv)",
    "quote_editor.html": "nurLesen(!!quote.projekt_im_archiv)",
    "webanfrage.html": "nurLesen(!!d.archiviert_am)",
}
# je Seite die lesenden Knöpfe (data-lesen): ihr data-klick, onclick oder id -- nur Zurückholen, Filter, „Ältere laden“, Wege zum Lesen
LESEN = {
    "customer.html": {"kunde-zurueckholen", "verlauf-art", "verlauf-weiter", "dokumentkategorie", "dokumentunterordner", "href=/properties/${p.id}",
                      "portal-protokoll", "portal-protokoll-mehr", "dialog-zu",  # seit 1.11.11: Protokoll des Kundenportals lesen, auch im Archiv
                      "portal-sperren-dialog", "portal-sperren",  # seit 1.11.13: Sperren nimmt nur Zugang weg und geht auch im Archiv (Festlegung 1.11.0)
                      "portalSiehtLink", "ip-zuruecknehmen"},  # seit 1.11.38: Reiter „Im Portal“ ansehen, Zurücknehmen auch im Archiv (die Knöpfe der Liste baut das Skript)
    "akte.html": {"projekt-zurueckholen", "verlauf-art", "verlauf-weiter", "dateikategorie", "dateiunterordner", "filterCategory('')",
                  "filterSubfolder('')"},
    "property.html": set(),
    "roof_area.html": set(),
    "quote_editor.html": {"pdf-vorschau", "tabCatalog", "tabDetails", "tabEdit"},
    "webanfrage.html": {"eingang-zurueckholen"},
}
# was nur zum Schreiben da ist und im Archiv ganz fehlt (data-schreiben)
SCHREIBEN = {
    "customer.html": {"docUploadZone"},
    "akte.html": {"uploadZone", "newCalendarEvent"},
    "property.html": {"(Upload-Felder der Objektdateien)"},
    "roof_area.html": set(),
    "quote_editor.html": {"newCalendarEvent"},
    "webanfrage.html": set(),
}


def _text(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _lesende(text: str) -> set:
    aus = set()
    for tag in re.findall(r"<(?:button|a)\b[^>]*\bdata-lesen\b[^>]*>", text):
        m = (re.search(r'data-klick="([^"]+)"', tag) or re.search(r'onclick="([^"(]+\(\'\'\))"', tag) or re.search(r'\bid="([^"]+)"', tag)
             or re.search(r'href="(/properties/\$\{p\.id\})"', tag))
        assert m, tag
        aus.add(("href=" + m.group(1)) if m.group(1).startswith("/") else m.group(1))
    return aus


def _schreibende(text: str) -> set:
    aus = set()
    for tag in re.findall(r"<\w+\b[^>]*\bdata-schreiben\b[^>]*>", text):
        m = re.search(r'\bid="([^"]+)"', tag)
        aus.add(m.group(1) if m else "(Upload-Felder der Objektdateien)")
    return aus


@pytest.mark.parametrize("seite", sorted(SEITEN))
def test_seite_bindet_ein_und_ruft_nur_lesen(seite):
    text = _text(seite)
    assert bindet_ein(seite, "_nur_lesen.html")
    assert text.count("nurLesen(") == 1 and SEITEN[seite] in text


@pytest.mark.parametrize("seite", sorted(SEITEN))
def test_lesende_knoepfe_je_seite(seite):
    """Ein Knopf bleibt im Archiv nur mit data-lesen -- genau diese; ein neuer Knopf zum Schreiben ist von selbst weg."""
    assert _lesende(_text(seite)) == LESEN[seite]
    assert _schreibende(_text(seite)) == SCHREIBEN[seite]


def test_nur_die_seiten_eines_vorgangs():
    from tests.vorlagen_js import alle_vorlagen
    mit = {name for name in alle_vorlagen() if name != "_nur_lesen.html" and "nurLesen(" in _text(name)}
    assert mit == set(SEITEN)


def test_baustein():
    text = _text("_nur_lesen.html")
    css = text[text.index("<style>"):text.index("</style>")].replace("\n", "")
    assert 'body.ds-nur-lesen :is(main, dialog, .modal-backdrop) :is(button, a.ds-knopf, a.btn, input[type="file"]):not([data-lesen]){display:none!important}' in css
    assert "body.ds-nur-lesen [data-schreiben]{display:none!important}" in css
    skript = text[text.index("<script>"):]
    for teil in ("f.disabled = true", "MutationObserver", "attributeFilter: ['disabled', 'draggable']", "setAttribute('draggable', 'false')",
                 "addEventListener('drop', _nurLesenSperren, true)", "f.disabled = false", "classList.remove('ds-nur-lesen')"):
        assert teil in skript, teil
    # gesperrte Felder sehen aus wie überall (ds-gesperrt.css, Regel 37) -- keine eigene Regel für disabled
    assert ":disabled" not in css and "[disabled]" not in css


def test_baustein_in_node_schaltet_und_ist_ohne_dom_still():
    """nurLesen() schaltet die Klasse, merkt sich den Stand (zweimal derselbe Aufruf tut nichts) und hängt die Sperren für Ziehen und Ablegen an bzw. ab."""
    from tests.node_lauf import node_ausfuehren
    skript = re.findall(r"<script>(.*?)</script>", _text("_nur_lesen.html"), flags=re.S)[0]
    js = """
var klassen = new Set(), hoerer = [];
var document = {body: {classList: {add: k => klassen.add(k), remove: k => klassen.delete(k), contains: k => klassen.has(k)},
                       querySelectorAll: () => [], matches: () => false},
                addEventListener: (art, f, c) => hoerer.push(art), removeEventListener: (art) => { hoerer = hoerer.filter(h => h !== art); }};
""" + skript + """
nurLesen(true); nurLesen(true);
const an = [klassen.has('ds-nur-lesen'), hoerer.slice().sort()];
nurLesen(false); nurLesen(false);
process.stdout.write(JSON.stringify({an, aus: [klassen.has('ds-nur-lesen'), hoerer]}));
"""
    ergebnis = node_ausfuehren(js)
    assert ergebnis == {"an": [True, ["dragover", "dragstart", "drop"]], "aus": [False, []]}


def test_dachflaeche_nennt_kunde_im_archiv(threaded_db_session, router_test_client):
    from datetime import datetime
    from app.models import Customer, Property, RoofArea
    from app.routers import roof_areas as flaechen_router
    db = threaded_db_session
    k = Customer(name="Zacharias Archiv", last_name="Archiv")
    db.add(k)
    db.flush()
    objekt = Property(customer_id=k.id, name="Hauptadresse")
    db.add(objekt)
    db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Nordseite")
    db.add(flaeche)
    db.commit()
    c = router_test_client(db, flaechen_router.router)
    assert c.get(f"/api/roof-areas/{flaeche.id}").json()["kunde_im_archiv"] is False
    k.archiviert_am = datetime(2026, 11, 20, 9)
    db.commit()
    assert c.get(f"/api/roof-areas/{flaeche.id}").json()["kunde_im_archiv"] is True
