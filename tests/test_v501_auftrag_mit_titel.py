"""Seit 1.9.78 (Stufe 4, R4 Nachtrag 2, Punkt 3): jede Zeile der Liste der Monteurin nennt den Titel des Auftrags.

    Daten      list_field_bookable_orders() liefert dazu "title" und "property_name" (Schnappschuss am Auftrag)
    Anzeige    _auftrag_text.html, eine Stelle für „Heute“ und „Meine Zeiten“: im Dialog „Für welchen Auftrag?“ „AUF-2026-0102 · Attika“, darunter
               „Halle Nord · Hallenbau GmbH · Werkstr. 5, …“; in der Auswahl „Auftrag“ einzeilig, höchstens 60 Zeichen, sonst mit „…“ gekürzt
Zwei Aufträge am selben Objekt sind damit unterscheidbar. Im Browser prüft das scripts/klicktest_bericht_ohne_einsatz.py.
"""

import json
from datetime import timedelta

import pytest

from app import berlin_time
from app.planning import list_field_bookable_orders
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz

ATTIKA = {"id": 2, "order_number": "AUF-2026-0102", "title": "Attika", "property_name": "Halle Nord", "customer_name": "Hallenbau GmbH",
          "property_address": "Werkstr. 5\n52531 Übach-Palenberg"}
RINNE = {**ATTIKA, "id": 1, "order_number": "AUF-2026-0101", "title": "Notdienst Rinne"}


@pytest.fixture
def welt(threaded_db_session, feste_uhr):
    db = threaded_db_session
    heute = berlin_time.berlin_today()
    mia = make_employee(db, "M-501", "Mia", "Monteurin")
    w = {"db": db, "mia": mia, "team": make_team(db, "K-501", "Kolonne 501")}
    w["auftraege"] = []
    for nr, titel in (("05011", "Notdienst Rinne"), ("05012", "Attika")):
        order = beauftragen(db, make_quote(db, is_consumer=False, number=nr))
        order.title, order.property_name = titel, "Halle Nord"  # beide am selben Objekt
        w["auftraege"].append(order)
        _einsatz(w, order, [(heute - timedelta(days=1), heute - timedelta(days=1))], [mia])
    db.commit()
    return w


def test_liste_liefert_titel_und_objekt(welt):
    liste = list_field_bookable_orders(welt["db"], welt["mia"].id)
    assert {(o["title"], o["property_name"]) for o in liste} == {("Notdienst Rinne", "Halle Nord"), ("Attika", "Halle Nord")}


def _js(ausdruck):
    baustein = (vj.TEMPLATES / "_auftrag_text.html").read_text(encoding="utf-8")
    skript = baustein.split("<script>", 1)[1].split("</script>", 1)[0]
    return node_ausfuehren(skript + f"\nconsole.log(JSON.stringify({ausdruck}));")


def test_dialog_zweizeilig_mit_titel():
    a = json.dumps(ATTIKA, ensure_ascii=False)
    assert _js(f"[auftragTitel({a}),auftragNeben({a})]") == ["AUF-2026-0102 · Attika",
                                                             "Halle Nord · Hallenbau GmbH · Werkstr. 5, 52531 Übach-Palenberg"]


def test_auswahl_einzeilig_gekuerzt_und_unterscheidbar(welt):
    """Angriff: zwei Aufträge am selben Objekt (Daten vom Server) -- in der Auswahl verschieden, je höchstens 60 Zeichen, mit dem Titel."""
    liste = json.dumps(list_field_bookable_orders(welt["db"], welt["mia"].id), ensure_ascii=False, default=str)
    texte = _js(f"{liste}.map(auftragText)")
    assert len(texte) == 2 and len(set(texte)) == 2
    assert all(len(t) <= 60 and "\n" not in t for t in texte)
    assert any(t.startswith(o["order_number"] + " · Attika") for t in texte for o in json.loads(liste))
    lang = json.dumps(ATTIKA, ensure_ascii=False)
    assert _js(f"auftragText({lang})") == "AUF-2026-0102 · Attika · Halle Nord · Hallenbau GmbH · Werk…"
    kurz = json.dumps({"order_number": "AUF-1", "title": "Dach"}, ensure_ascii=False)
    assert _js(f"auftragText({kurz})") == "AUF-1 · Dach"


def test_eine_stelle_fuer_heute_und_meine_zeiten():
    for seite in ("mobil.html", "mobil_zeiten.html"):
        assert vj.bindet_ein(seite, "_auftrag_text.html"), seite
        assert "function auftragText(" not in vj.seitentext(seite)[0], seite  # keine eigene Fassung mehr
    heute = vj.seitentext("mobil.html")[0]
    assert "esc(auftragTitel(o)||'Auftrag')" in heute and "var neben=auftragNeben(o);" in heute
