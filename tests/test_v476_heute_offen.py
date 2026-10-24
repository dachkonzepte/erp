"""Seit 1.9.49 (Stufe 4, R2 Nachrunde, Punkt 2; ersetzt Festlegung 1.9.45 Nr. 4): die Listen weg von „Heute“, auf die eigene Seite
„Heute / Offen“ (/mobil/offen).

    Heute          keine Listen mehr (offene Berichte, Mängel, Checklisten, Wartungen); die Seite endet mit „Nächste Tage“; die Zeilen von
                   „Offen“ springen auf /mobil/offen#<Abschnitt>, „Wartungen an meinen Objekten“ als eigene Zeile, wenn es welche gibt
    Offen          im Monteursrahmen mit Seitenkopf (Pfad Heute / Offen, Tablet-Maße) für jede Rolle; ein Abschnitt erscheint nur mit Inhalt
                   (oder mit einem Fehler beim Laden), alles leer -> „Nichts offen.“; was dort ging (Beseitigt melden, Wartung durchführen),
                   geht hier über dieselben Schnittstellen
    Berichte       GET /api/field-view/offene-berichte: nur die eigenen Entwürfe, nur die Felder, die die Seite zeigt
    Zahl           heute.offen["wartungen"] = Wartungsverträge an meinen Objekten (dieselbe Liste wie der Abschnitt)

Im Browser prüft das scripts/klicktest_heute.py (Teil „offen“).
"""

import json
import re

from app.heute import offen
from app.routers import field_view as field_view_router
from app.routers.pages import router as pages_router
from app.service_reports import create_report
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v334_auswahl_restfaelle import FAKE_DOM
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)

ABSCHNITTE = ["offene-berichte", "maengel", "offene-checklisten", "wartungen"]


def _markup(text: str) -> str:
    return re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)


# --- Heute ohne Listen ------------------------------------------------------------------------------------------------------------

def test_heute_ohne_listen_und_endet_mit_naechste_tage(threaded_db_session, router_test_client, feste_uhr):
    html = router_test_client(threaded_db_session, pages_router, role="field").get("/mobil").text
    markup = _markup(html)
    for kennung in ("draftReportsList", "defectsList", "draftChecklistsList", "maintenanceList", 'class="listen"', *ABSCHNITTE):
        assert kennung not in markup, kennung
    # die Seite endet mit „Nächste Tage“: danach schließen nur noch Spalte, Raster und main
    rest = markup.split('id="naechsteKarte"', 1)[1]
    assert re.fullmatch(r'[^<]*>\s*<span[^>]*>Nächste Tage</span>\s*<div id="naechsteZeilen"></div>\s*</section>\s*</div>\s*</div>\s*</main>.*',
                        rest, flags=re.S), rest[:300]
    skript = vj.eigene_skripte("mobil.html").text
    for adresse in ("/api/field-view/defects", "/api/checklists/mine", "/api/field-view/maintenance-contracts", "/remedied", "/perform-maintenance"):
        assert adresse not in skript, adresse


def test_offen_zeilen_springen_auf_die_eigene_seite():
    skript = vj.eigene_skripte("mobil.html").text
    teil = skript[skript.index("function renderOffen("):skript.index("function renderNaechste(")]
    ziele = re.findall(r"href=\"(/mobil/offen#[a-z-]+)\">'\+offenZeile\('([^']+)'", teil)
    assert ziele == [("/mobil/offen#offene-berichte", "Berichte"), ("/mobil/offen#offene-checklisten", "Checklisten"),
                     ("/mobil/offen#maengel", "Befunde zur Beseitigung"), ("/mobil/offen#wartungen", "Wartungen an meinen Objekten")]
    assert "if(o.wartungen>0)" in teil


# --- die Seite „Heute / Offen“ ------------------------------------------------------------------------------------------------------

def test_offen_seite_im_monteursrahmen_fuer_jede_rolle(threaded_db_session, router_test_client):
    for rolle in ("field", "buero_auftrag", "admin"):
        antwort = router_test_client(threaded_db_session, pages_router, role=rolle).get("/mobil/offen", follow_redirects=False)
        assert antwort.status_code == 200, (rolle, antwort.status_code)
        markup = _markup(antwort.text)
        assert 'id="mobileHeaderWrap"' in markup and '<header class="ds-kopf ds-kopf-tablet" id="seitenkopf">' in markup
        nav = re.search(r'<nav class="ds-kopf-pfad" id="seitenkopfPfad" aria-label="Pfad">(.*?)</nav>', markup, flags=re.S).group(1)
        assert re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav) == [("/mobil", "Heute")]
        assert re.search(r'<h1 class="ds-kopf-titel" id="seitenkopfTitel">Offen</h1>', markup)
        # der Reiter „Heute“ ist aktiv
        assert re.search(r'<a href="/mobil" class="mobile-nav-reiter active" aria-current="page">Heute</a>', markup)
        for kennung in ABSCHNITTE:
            assert re.search(rf'<section id="{kennung}" aria-labelledby="[^"]+" hidden>', markup), (rolle, kennung)


def _lauf(client, antworten: dict) -> dict:
    html = client.get("/mobil/offen").text
    skripte = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
    abschnitte = json.dumps(ABSCHNITTE)
    js = (FAKE_DOM + f"\nANTWORTEN = {json.dumps(antworten)};\n"
          f"document.querySelectorAll = sel => sel === 'main section' ? {abschnitte}.map(_element) : [];\n"
          f"{abschnitte}.concat(['nichtsOffen']).forEach(id => {{ _element(id).hidden = true; }});\n"
          + "\n".join(skripte)
          + "\n(async () => { for (let i = 0; i < 50; i++) await new Promise(r => setTimeout(r, 0));\n"
          f"  process.stdout.write(JSON.stringify({{sichtbar: {abschnitte}.filter(id => !_element(id).hidden),"
          " nichts: !_element('nichtsOffen').hidden, laedt: !_element('offenLaedt').hidden})); })();")
    return node_ausfuehren(js, "Europe/Berlin")


ALLES_LEER = {"/api/field-view/offene-berichte": [], "/api/field-view/defects": [], "/api/checklists/mine": [],
              "/api/field-view/maintenance-contracts": []}


def test_offen_nur_die_nicht_leeren_abschnitte(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field")
    antworten = dict(ALLES_LEER)
    antworten["/api/field-view/offene-berichte"] = [{"id": 1, "order_id": 2, "order_number": "AU-1", "report_type_label": "Wartungsbericht"}]
    antworten["/api/checklists/mine"] = [{"id": 5, "template_label": "Sicherheitscheck", "context_label": "AU-1"}]
    assert _lauf(client, antworten) == {"sichtbar": ["offene-berichte", "offene-checklisten"], "nichts": False, "laedt": False}


def test_offen_alles_leer_nichts_offen(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field")
    assert _lauf(client, ALLES_LEER) == {"sichtbar": [], "nichts": True, "laedt": False}


def test_offen_fehler_beim_laden_bleibt_sichtbar(threaded_db_session, router_test_client):
    """Ein Abschnitt, dessen Laden scheitert, erscheint mit der Meldung -- ein Fehler bleibt nie unsichtbar."""
    client = router_test_client(threaded_db_session, pages_router, role="field")
    antworten = {k: v for k, v in ALLES_LEER.items() if k != "/api/field-view/defects"}  # 404
    assert _lauf(client, antworten) == {"sichtbar": ["maengel"], "nichts": False, "laedt": False}


# --- Schnittstelle und Zahl -------------------------------------------------------------------------------------------------------

def test_offene_berichte_nur_eigene_und_nur_die_felder_der_seite(welt):  # noqa: F811
    db, order = welt["db"], welt["order"]
    eigener = create_report(db, order.id, "rapport", created_by_employee_id=welt["mia"].id)
    create_report(db, order.id, "rapport", created_by_employee_id=welt["tom"].id)
    db.commit()
    client = welt["client"](db, field_view_router.router, role="field", employee_id=welt["mia"].id)
    antwort = client.get("/api/field-view/offene-berichte")
    assert antwort.status_code == 200
    assert antwort.json() == [{"id": eigener["id"], "order_id": order.id, "order_number": order.order_number,
                               "report_type_label": "Rapportbericht"}]
    assert offen(db, welt["mia"].id)["berichte"] == 1


def test_offen_zaehlt_die_wartungsvertraege_an_meinen_objekten(welt):  # noqa: F811
    """„Wartungen an meinen Objekten“ in „Offen“ zählt die Verträge an den Objekten meiner Einsätze (dieselbe Liste wie der Abschnitt auf
    „Heute / Offen“, list_relevant_contracts_for_employee()); ohne Einsatz keine."""
    from datetime import timedelta

    from app.maintenance_contracts import create_contract
    from app.models import Property
    from tests.test_v471_heute_server import _einsatz

    db, order = welt["db"], welt["order"]
    halle = Property(customer_id=order.customer_id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle)
    db.flush()
    order.project.property_id = halle.id
    db.commit()
    for titel in ("Jahreswartung Flachdach", "Rinnenreinigung"):
        create_contract(db, order.customer_id, halle.id, titel, 12, welt["heute"] + timedelta(days=30))
    assert offen(db, welt["mia"].id)["wartungen"] == 0  # noch kein Einsatz an der Halle
    _einsatz(welt, order, [(welt["heute"], welt["heute"])], [welt["mia"]])
    assert offen(db, welt["mia"].id)["wartungen"] == 2 and offen(db, welt["tom"].id)["wartungen"] == 0
