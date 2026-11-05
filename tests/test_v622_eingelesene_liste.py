"""Version 1.9.218 (L1a Stufe 7, Punkt 1): eingelesene Personalnummern ohne Person in einer eigenen Liste -- Festlegung 1.9.213 Nr. 6 neu gefasst.

    Liste     unter „Zeitregeln und DATEV“, nur für den Admin (Block nur im Markup des Admins, GET .../personalnummern/eingelesen nur Admin);
              je Zeile Nummer, eingelesen am (Tag in Berlin), „freigeben“ mit derselben Warnung wie bei einer früheren Nummer -- oder, wenn
              jemand sie trägt, wer (wie 1.9.191)
    Büro – Finanzen sieht die Liste nicht (403, kein Block)

Alle Nummern sind erfunden.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import EmployeePayrollSettings, PersonalnummerVergabe
from app.routers import pages as pages_router
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v224_field_view import make_employee

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    db.add_all([PersonalnummerVergabe(nummer="00205", employee_id=None, vergeben_am=datetime(2026, 11, 4, 23, 30)),  # Berlin: 05.11.
                PersonalnummerVergabe(nummer="00011", employee_id=None, vergeben_am=datetime(2026, 11, 5, 8, 0)),
                PersonalnummerVergabe(nummer="00123", employee_id=mia.id, vergeben_am=datetime(2026, 11, 1, 8, 0))])
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _client(w, rolle):
    w["db"].commit()
    return w["client"](w["db"], time_backoffice_router.router, pages_router.router, role=rolle)


def test_liste_nur_ohne_person_sortiert(welt):
    r = _client(welt, "admin").get("/api/time-backoffice/personalnummern/eingelesen")
    assert r.status_code == 200, r.text
    assert r.json() == [{"nummer": "00011", "eingelesen_am": "2026-11-05", "traegt": None},
                        {"nummer": "00205", "eingelesen_am": "2026-11-05", "traegt": None}]


@pytest.mark.parametrize("rolle", ["buero_finanzen", "buero_auftrag", "field"])
def test_nur_der_admin(welt, rolle):
    assert _client(welt, rolle).get("/api/time-backoffice/personalnummern/eingelesen").status_code == 403


def test_wer_sie_traegt_statt_freigeben(welt):
    """An der Sperre vorbei (wie aus einem alten Bestand): Tom trägt 00011 -- die Liste nennt ihn, freigeben lehnt der Server ab."""
    db = welt["db"]
    db.add(EmployeePayrollSettings(employee_id=welt["tom"].id, datev_personnel_number="00011", export_umfang="alles"))
    client = _client(welt, "admin")
    zeilen = client.get("/api/time-backoffice/personalnummern/eingelesen").json()
    assert [(z["nummer"], z["traegt"]) for z in zeilen] == [("00011", "Tom Monteur"), ("00205", None)]
    assert client.post("/api/time-backoffice/personalnummern/freigeben", json={"nummer": "00011"}).status_code == 409


def test_freigegeben_verschwindet(welt):
    client = _client(welt, "admin")
    assert client.post("/api/time-backoffice/personalnummern/freigeben", json={"nummer": "00205"}).status_code == 200
    assert [z["nummer"] for z in client.get("/api/time-backoffice/personalnummern/eingelesen").json()] == ["00011"]


def test_block_nur_im_markup_des_admins(welt):
    admin = _client(welt, "admin").get("/settings")
    finanzen = _client(welt, "buero_finanzen").get("/settings")
    assert admin.status_code == finanzen.status_code == 200
    assert 'id="eingeleseneBlock"' in admin.text and 'id="eingeleseneZeilen"' in admin.text
    assert "eingeleseneBlock" not in finanzen.text and "Eingelesene Personalnummern" not in finanzen.text


def test_dieselbe_warnung_ohne_namen():
    """pnrFreigabeOeffnen() ohne Namen (data-name="" der eingelesenen Zeile): derselbe Text ab „Gibst du sie frei“, vorn die eingelesene Liste."""
    from tests.node_lauf import node_ausfuehren
    from tests.vorlagen_js import eigene_skripte
    from tests.test_v518_zeiten_seite import _funktion
    text = eigene_skripte("settings.html").text
    skript = ("var EL={};var document={getElementById(id){return EL[id]||(EL[id]={textContent:'',showModal(){}})}};var pnrNummer=null,pnrStatus='';"
              + _funktion(text, "pnrFreigabeOeffnen")
              + "\nvar aus=[];pnrFreigabeOeffnen('00205','');aus.push(EL.pnrFreigabeWarnung.textContent,pnrStatus);"
              + "pnrFreigabeOeffnen('91008','Mia Monteurin');aus.push(EL.pnrFreigabeWarnung.textContent,pnrStatus);"
              + "process.stdout.write(JSON.stringify(aus));")
    eingelesen, status_e, person, status_p = node_ausfuehren(skript)
    assert eingelesen.startswith("Die Personalnummer 00205 steht in der eingelesenen Liste vergebener Nummern und ist für alle gesperrt. Gibst du sie frei")
    assert person.startswith("Die Personalnummer 91008 gehörte Mia Monteurin und ist für alle anderen gesperrt. Gibst du sie frei")
    assert eingelesen.split(". Gibst du sie frei", 1)[1] == person.split(". Gibst du sie frei", 1)[1]
    assert (status_e, status_p) == ("eingeleseneStatus", "payrollStatus")


def test_liste_gezeichnet_leer_und_mit_traeger():
    """renderEingelesene(): ohne Nummern der Satz, mit Trägerin statt „freigeben“ ihr Name, sonst „freigeben“ mit leerem data-name."""
    from tests.node_lauf import node_ausfuehren
    from tests.test_v518_zeiten_seite import _funktion
    from tests.vorlagen_js import eigene_skripte
    text = eigene_skripte("settings.html").text
    vorweg = ("var EL={};var document={getElementById(id){return EL[id]||(EL[id]={innerHTML:''})}};"
              "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
              "function szDatum(s){return s?s.slice(8,10)+'.'+s.slice(5,7)+'.'+s.slice(0,4):''}")
    skript = (vorweg + _funktion(text, "renderEingelesene")
              + "\nvar aus=[];var eingelesen=[];renderEingelesene();aus.push(EL.eingeleseneZeilen.innerHTML);"
              + "eingelesen=[{nummer:'00011',eingelesen_am:'2026-11-05',traegt:'Tom Monteur'},{nummer:'00012',eingelesen_am:'2026-11-05',traegt:null}];"
              + "renderEingelesene();aus.push(EL.eingeleseneZeilen.innerHTML);process.stdout.write(JSON.stringify(aus));")
    leer, voll = node_ausfuehren(skript)
    assert "Keine eingelesenen Nummern ohne Person." in leer
    assert '<span data-traegt="00011">trägt heute Tom Monteur</span>' in voll and 'data-nummer="00011"' not in voll
    assert 'data-klick="pnr-freigeben" data-nummer="00012" data-name=""' in voll and "05.11.2026" in voll
