"""Version 1.8.122 -- Baujahr eines Bauteils ab 1000 (Korrektur 119-6 vom 16.10.2026).

1.8.119 setzte das Baujahr auf 1900–2100, wie es der Browser schon hatte. Kirchen und Altbauten sind älter: ab 1000, die Obergrenze 2100
bleibt -- auf dem Server (RoofComponentCreate/Update.year_built) und im Browser (editComponentYear auf der Dachflächen-Seite) gleich; der
Abgleich von 1.8.119 (tests/test_v424_zahlgrenzen.py) prüft weiter, dass der Browser nicht strenger ist."""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from app.models import Customer, Property, RoofArea, RoofComponent
from app.routers.roof_areas import router as roof_areas_router
from app.schemas import RoofComponentCreate, RoofComponentUpdate
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v334_auswahl_restfaelle import im_browser, seite
from tests.zahlgrenzen import TEMPLATES, grenzen_im_markup, grenzen_im_schema, zahl_tags

ANGENOMMEN = (1000, 1250, 1899, 2026, 2100)
ABGELEHNT = (999, 1, 0, -1250, 2101)


@pytest.mark.parametrize("schema", [RoofComponentCreate, RoofComponentUpdate])
def test_der_server_nimmt_ab_1000_bis_2100(schema):
    for jahr in ANGENOMMEN:
        assert schema(name="Glockenturm", year_built=jahr).year_built == jahr
    assert schema(name="Glockenturm", year_built=None).year_built is None
    for jahr in ABGELEHNT:
        with pytest.raises(ValidationError):
            schema(name="Glockenturm", year_built=jahr)


def test_ueber_die_routen(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde = Customer(name="Kirchengemeinde", last_name="Kirchengemeinde")
    db.add(kunde)
    db.flush()
    objekt = Property(customer_id=kunde.id, name="Kirche St. Marien")
    db.add(objekt)
    db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Kirchenschiff")
    db.add(flaeche)
    db.commit()
    client = router_test_client(db, roof_areas_router)
    antwort = client.post(f"/api/roof-areas/{flaeche.id}/components", json={"name": "Dachstuhl", "year_built": 1250})
    assert antwort.status_code == 200, antwort.text
    bauteil = antwort.json()["id"]
    assert client.put(f"/api/roof-components/{bauteil}", json={"name": "Dachstuhl", "year_built": 1000}).status_code == 200
    assert db.get(RoofComponent, bauteil).year_built == 1000
    for jahr in (999, 2101):
        assert client.put(f"/api/roof-components/{bauteil}", json={"name": "Dachstuhl", "year_built": jahr}).status_code == 422
        assert client.post(f"/api/roof-areas/{flaeche.id}/components", json={"name": "Turm", "year_built": jahr}).status_code == 422
    db.expire_all()
    assert db.get(RoofComponent, bauteil).year_built == 1000


def _feld() -> str:
    tags = [tag for _, tag in zahl_tags((TEMPLATES / "roof_area.html").read_text(encoding="utf-8")) if 'id="editComponentYear"' in tag]
    assert len(tags) == 1
    return tags[0]


def test_browser_und_server_haben_dieselben_grenzen():
    from decimal import Decimal

    browser = grenzen_im_markup(_feld())
    for ref in ("RoofComponentCreate.year_built", "RoofComponentUpdate.year_built"):
        server = grenzen_im_schema(ref)
        assert (server.min, server.max, server.ganz) == ((Decimal("1000"), True), (Decimal("2100"), True), True), ref
        assert (browser.min, browser.max, browser.ganz) == (server.min, server.max, server.ganz), ref


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_die_dachflaechen_seite_liest_ab_1000():
    """zahlFeld('editComponentYear') mit den data-Attributen aus der Vorlage: angenommen, was der Server annimmt, sonst eine Meldung."""
    dataset = {re.sub(r"-(\w)", lambda m: m.group(1).upper(), name): wert
               for name, wert in re.findall(r'\sdata-([a-z][a-z-]*)(?:="([^"]*)")?', _feld())}
    lauf = im_browser(seite("roof_area.html", "\ninit();"), f"""
      const feld = _element('editComponentYear'); Object.assign(feld.dataset, {json.dumps(dataset)});
      const ergebnis = {{}};
      for (const text of {json.dumps([str(j) for j in ANGENOMMEN + ABGELEHNT])}) {{
        feld.value = text;
        try {{ ergebnis[text] = zahlFeld('editComponentYear'); }} catch (e) {{ ergebnis[text] = 'abgelehnt'; }}
      }}
      return ergebnis;""")
    ergebnis = lauf["ergebnis"]
    assert {text: wert for text, wert in ergebnis.items() if wert != "abgelehnt"} == {str(j): j for j in ANGENOMMEN}
    assert sorted(text for text, wert in ergebnis.items() if wert == "abgelehnt") == sorted(str(j) for j in ABGELEHNT)
