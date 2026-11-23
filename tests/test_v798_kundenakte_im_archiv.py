"""Version 1.10.27 (Antwort zum Bericht F10, 23.11.2026): die Kundenakte nennt ein Projekt im Archiv unter „Laufende Projekte“ „Im Archiv“, nicht
„Abgeschlossen“.

Bis 1.10.26 stand jedes Projekt, das nicht läuft, in der Zeile „Abgeschlossen: …“ unter den laufenden -- auch ein Projekt im Archiv, das nie einen Auftrag
hatte (im Klicktest P-2026-0902). Jetzt nennt der Server je Projekt „im_archiv“ (archiviert und ohne Auftrag, dieselbe Regel wie
app/projects.py::_projekt_im_archiv()), und die Übersicht zeigt zwei Zeilen: „Abgeschlossen: …“ (abgeschlossen, storniert, archiviert mit Auftrag) und
„Im Archiv: …“. Gemessen im Browser: scripts/klicktest_nur_lesen.py (Kundenakte im Archiv und nach dem Zurückholen).
"""

import pytest

from app.kundenakte import projekte
from app.models import Order, Project
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v555_kundenakte_zahlen import _projekt_ohne_auftrag, welt  # noqa: F401  (Fixture)
from tests.test_v557_kundenakte_seite import _lauf, akte_welt  # noqa: F401  (Fixture)

UEBERSICHT = ("await kundenakteStarten(); return {zeile: _element('uAbgeschlossen').innerHTML, versteckt: _element('uAbgeschlossen').hidden,"
              "laufend: _element('uProjekteListe').innerHTML};")


def _archivieren(db, projekt_id):
    """Erst anlegen, dann ins Archiv -- wie „⋮ → Archivieren“ (nur die Spalte des Archivs)."""
    db.get(Project, projekt_id).archived = True
    db.commit()


@pytest.fixture
def mit_archiv(welt):
    """Kessler bekommt Projekt E ohne Auftrag im Archiv; das Projekt von D (storniert, mit Auftrag) wird archiviert -- es ist nicht im Archiv der Aufbewahrung."""
    db = welt["db"]
    e, _ = _projekt_ohne_auftrag(db, welt["kessler"], "P-E")
    _archivieren(db, e.id)
    d_projekt = db.get(Order, welt["d"].id).project_id
    _archivieren(db, d_projekt)
    return {**welt, "e": e, "d_projekt": db.get(Project, d_projekt)}


def test_server_nennt_im_archiv_nur_ohne_auftrag(mit_archiv):
    db = mit_archiv["db"]
    je = {p["project_number"]: p for p in projekte(db, mit_archiv["kessler"].id)}
    e, d = je["P-E"], je[mit_archiv["d_projekt"].project_number]
    assert (e["archived"], e["im_archiv"], e["laufend"], e["auftraege"]) == (True, True, False, [])
    assert (d["archived"], d["im_archiv"], d["laufend"]) == (True, False, False)  # archiviert, aber mit Auftrag: nicht im Archiv der Aufbewahrung
    c = je[mit_archiv["c"].project_number]
    assert (c["archived"], c["im_archiv"], c["laufend"]) == (False, False, True)  # ohne Auftrag, nicht archiviert: läuft
    assert not any(p["im_archiv"] for p in je.values() if p["auftraege"] or not p["archived"])


@nur_mit_node
def test_uebersicht_trennt_abgeschlossen_und_im_archiv(mit_archiv, router_test_client):
    welt_ = {**mit_archiv, "client": router_test_client}
    e = _lauf(welt_, UEBERSICHT)["ergebnis"]
    nummer_e, nummer_d = mit_archiv["e"].project_number, mit_archiv["d_projekt"].project_number
    abgeschlossen, archiv = e["zeile"].split('</span><span class="projekt-kurzliste" style="display:block">Im Archiv: ')
    assert e["versteckt"] is False
    assert abgeschlossen.startswith('<span class="projekt-kurzliste" style="display:block">Abgeschlossen: ')
    assert nummer_d in abgeschlossen and nummer_e not in abgeschlossen  # das stornierte Projekt (archiviert mit Auftrag) bleibt „Abgeschlossen“
    assert archiv == f'<a href="/projects/{mit_archiv["e"].id}">{nummer_e}</a> Garage</span>'
    assert nummer_e not in e["laufend"]


@nur_mit_node
def test_nur_ein_projekt_im_archiv_ohne_zeile_abgeschlossen(welt, router_test_client):
    """Kunde mit einem einzigen Projekt, im Archiv: nur die Zeile „Im Archiv“, kein „Abgeschlossen“ (der Fall aus dem Klicktest)."""
    from tests.test_v381_zahlungen import _kunde
    db = welt["db"]
    nora = _kunde(db, "Nora")
    p, _ = _projekt_ohne_auftrag(db, nora, "P-N")
    _archivieren(db, p.id)
    e = _lauf({**welt, "nora": nora, "client": router_test_client}, UEBERSICHT, kunde="nora")["ergebnis"]
    assert e["versteckt"] is False
    assert e["zeile"] == f'<span class="projekt-kurzliste" style="display:block">Im Archiv: <a href="/projects/{p.id}">P-N</a> Garage</span>'
    assert "Kein laufendes Projekt." in e["laufend"]


@nur_mit_node
def test_ohne_abgeschlossene_und_archiv_keine_zeile(welt, router_test_client):
    from tests.test_v381_zahlungen import _kunde
    db = welt["db"]
    olga = _kunde(db, "Olga")
    _projekt_ohne_auftrag(db, olga, "P-O")
    e = _lauf({**welt, "olga": olga, "client": router_test_client}, UEBERSICHT, kunde="olga")["ergebnis"]
    assert (e["versteckt"], e["zeile"]) == (True, "")
