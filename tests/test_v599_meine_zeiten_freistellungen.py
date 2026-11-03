"""Seit 1.9.187 (Lohn L1a, Stufe 2, Punkt 2): „Meine Zeiten“ zeigt die Freistellungen des Arbeitszeitkalenders.

Feste Tage: Dezember 2026 (Do 24.12. Heiligabend, Do 31.12. Silvester, Winter 7,50 h); Uhr 10.11.2026 (fester_tag).

    Server   GET /api/field-view/meine-zeiten liefert für den angezeigten Monat "freistellungen" -- je Tag Abwesenheit, Stunden (Sollzeit des
             Tags: Heiligabend 7,00 h, Silvester die des Modells), bezahlt; dieselbe Rechnung wie der Lohn (app/arbeitszeitkalender.py::
             abwesenheiten()): nur gewerbliche, nur an Tagen mit Sollzeit (Teilzeit am Donnerstag voll), Silvester fehlt, wenn ein genehmigter
             Urlaub ihn als ganzen Urlaubstag nimmt; in anderen Monaten keine
    Seite    in der Karte „Abwesenheit“ wie die Anträge: Abwesenheit, Tag mit Wochentag, Stunden, „bezahlt“/„unbezahlt“, „gilt ohne Antrag“

Im Browser: scripts/klicktest_meine_zeiten_freistellungen.py.
"""

import json
import re
from datetime import date
from decimal import Decimal

import pytest

from app.absence_requests import create_request, review_request
from app.models import Employee
from app.routers import field_view as field_view_router
from app.routers import time_tracking as time_tracking_router
from app.sollzeit import zeile_anlegen
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee

D = Decimal


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Teilzeit")
    kim = Employee(employee_number="K-1", first_name="Kim", last_name="Kauffrau", employee_group="kaufmaennisch", active=True)
    db.add(kim)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "kim": kim, "client": router_test_client}


def _frei(w, emp, monat="2026-12", role="field"):
    client = w["client"](w["db"], time_tracking_router.router, field_view_router.router, role=role, employee_id=emp.id)
    antwort = client.get("/api/field-view/meine-zeiten", params={"monat": monat})
    assert antwort.status_code == 200, antwort.text
    return [(f["tag"], f["abwesenheit"], D(str(f["stunden"])), f["bezahlt"]) for f in antwort.json()["freistellungen"]]


HEILIGABEND = ("2026-12-24", "Heiligabend – bezahlte Freistellung", D("7.00"), True)
SILVESTER = ("2026-12-31", "Silvester – unbezahlte Freistellung", D("7.50"), False)


def test_dezember_mit_heiligabend_und_silvester(welt):
    assert _frei(welt, welt["mia"]) == [HEILIGABEND, SILVESTER]


def test_andere_monate_ohne(welt):
    assert _frei(welt, welt["mia"], "2026-11") == [] and _frei(welt, welt["mia"], "2027-01") == []


def test_teilzeit_nur_an_tagen_mit_sollzeit_und_voll(welt):
    """Tom Di–Do 3,00 h: Do 24.12. voll 7,00 h, Do 31.12. 3,00 h (Sollzeit des Tags). Im Dezember 2029 (24. und 31. ein Montag): keine."""
    zeile_anlegen(welt["db"], welt["tom"].id, date(2026, 12, 1), {"dienstag": D("3"), "mittwoch": D("3"), "donnerstag": D("3")})
    assert _frei(welt, welt["tom"]) == [HEILIGABEND, ("2026-12-31", "Silvester – unbezahlte Freistellung", D("3.00"), False)]
    assert _frei(welt, welt["tom"], "2029-12") == []


def test_kaufmaennisch_ohne(welt):
    assert _frei(welt, welt["kim"], role="buero_finanzen") == []


def test_silvester_als_ganzer_urlaubstag_fehlt(welt):
    """Ein genehmigter Urlaub 28.12.–31.12. mit „ganzer Urlaubstag“ nimmt Silvester -- die Freistellung fehlt; Heiligabend bleibt."""
    antrag = create_request(welt["db"], employee_id=welt["mia"].id, absence_category="urlaub", start_date=date(2026, 12, 28),
                            end_date=date(2026, 12, 31), kalendertag_urlaub=True)
    assert _frei(welt, welt["mia"]) == [HEILIGABEND, SILVESTER]  # offen: zählt noch nicht
    review_request(welt["db"], antrag.id, decision="approved", reviewed_by_user_id=None)
    assert _frei(welt, welt["mia"]) == [HEILIGABEND]


# --- Seite --------------------------------------------------------------------------------------------------------------------------

def _funktion(text: str, kopf: str) -> str:
    i = text.index(kopf)
    tiefe, j = 0, text.index("{", i)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _zahl() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / "_zahl.html").read_text(encoding="utf-8"), flags=re.S))


def _zeichnen(liste) -> dict:
    text = vj.eigene_skripte("mobil_zeiten.html").text
    teile = [_funktion(text, k) for k in ("function esc(", "function pad2(", "function teile(", "function tagLang(", "function stunden(",
                                          "function freistellungenZeichnen(")]
    js = (_zahl() + "\nvar WOCHENTAG=['So','Mo','Di','Mi','Do','Fr','Sa'];var box={hidden:false,innerHTML:'x'};function el(id){return box}\n"
          + "\n".join(teile) + f"\nfreistellungenZeichnen({json.dumps(liste)});process.stdout.write(JSON.stringify({{hidden:box.hidden,html:box.innerHTML}}));")
    return node_ausfuehren(js)


def test_seite_wie_die_antraege_mit_stunden_und_bezahlt():
    d = _zeichnen([{"tag": "2026-12-24", "abwesenheit": "Heiligabend – bezahlte Freistellung", "stunden": "7.00", "bezahlt": True},
                   {"tag": "2026-12-31", "abwesenheit": "Silvester – <unbezahlte> Freistellung", "stunden": "7.50", "bezahlt": False}])
    assert d["hidden"] is False
    zeilen = [re.sub(r"<[^>]+>", "|", z) for z in d["html"].split('<div class="antrag"')[1:]]
    assert zeilen == [' data-freistellung="2026-12-24">||Heiligabend – bezahlte Freistellung||Do 24.12.2026 · 7,00 h · bezahlt|||gilt ohne Antrag||',
                      ' data-freistellung="2026-12-31">||Silvester – &lt;unbezahlte&gt; Freistellung||Do 31.12.2026 · 7,50 h · unbezahlt|||gilt ohne Antrag||']


def test_seite_ohne_freistellung_leer():
    assert _zeichnen([]) == {"hidden": True, "html": ""}
    assert "freistellungenZeichnen(d.freistellungen);" in _funktion(vj.eigene_skripte("mobil_zeiten.html").text, "function zeichnen(")
