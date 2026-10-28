"""Seit 1.9.124 (Stufe 5, R2, Punkt 1): der Auftrag hat nur noch vier Status -- läuft, pausiert, abgeschlossen, storniert -- und wechselt sie nur
über eigene Aktionen mit Rückfrage (POST /api/orders/{id}/status, app/auftragsstatus.py::status_aendern()).

    Liste       ein Status außerhalb der vier -> 422; PUT /api/orders/{id} und Beauftragen mit Status -> 422 (bis 1.9.123 freier Text)
    Begründung  Pausieren und Stornieren ohne Begründung -> 422; Abschließen ohne Schlussrechnung und ohne Begründung -> 409; „ohne Rechnung“
                nur ohne jede Rechnung (sonst 409); Fortsetzen aus „abgeschlossen“ nur mit Begründung (422)
    Übergänge   aus „storniert“ nichts mehr (409), derselbe Status noch einmal 409
    Wirkung     pausiert sperrt nichts; abgeschlossen: kein neuer Einsatz, nicht in der Plantafel, die Monteurin bucht nicht (409), Bericht geht;
                storniert: dazu kein Bericht für jede Rolle (409) -- Rechnung und Buchung des Büros gehen (200)
    Historie    OrderStatusChange mit Begründung und Person, unveränderlich, im Änderungsprotokoll
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.auftragsstatus import OHNE_RECHNUNG_TEXT, status_aendern
from app.invoices import create_abschlag_pauschal, create_schlussrechnung
from app.meldungen import AUFTRAG_ABGESCHLOSSEN_ZEITEN, AUFTRAG_STORNIERT_ZEITEN, BERICHT_STORNIERT
from app.models import ArchiveImmutableError, AuditLog, Order, OrderStatusChange, PlanningSlot, ServiceReport, TimeEntry
from app.routers import field_view as field_view_router
from app.routers import invoices as invoices_router
from app.routers import orders as orders_router
from app.routers import planning as planning_router
from app.routers import quotes as quotes_router
from app.routers import service_reports as service_reports_router
from app.routers import time_tracking as time_tracking_router
from tests.leistungszeitraum import festschreiben
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import _einsatz, _zweiter_auftrag, welt  # noqa: F401  (Fixture)

ROUTER = (orders_router.router, planning_router.router, service_reports_router.router, time_tracking_router.router, invoices_router.router,
          quotes_router.router)


def _buero(w, role="buero_auftrag", employee_id=None):
    return w["client"](w["db"], *ROUTER, role=role, employee_id=employee_id)


def _als(w, emp):
    """Die Monteurin mit allen Routern dieses Tests (Buchung, Bericht, Heute)."""
    return w["client"](w["db"], *ROUTER, field_view_router.router, role="field", employee_id=emp.id)


def _status(client, order_id, status, reason=None):
    return client.post(f"/api/orders/{order_id}/status", json={"status": status, "reason": reason})


def _frisch(w):
    w["db"].expire_all()
    return w["db"].get(Order, w["order"].id)


# --- Liste, Begründung, Übergänge -----------------------------------------------------------------------------------------------------

def test_neuer_auftrag_laeuft(welt):  # noqa: F811
    """Beauftragen setzt „läuft“; die Antwort trägt den lesbaren Status und die möglichen Übergänge."""
    assert welt["order"].status == "laeuft"
    daten = _buero(welt).get(f"/api/orders/{welt['order'].id}").json()
    assert daten["status_label"] == "läuft"
    assert [a["ziel"] for a in daten["status_info"]["aktionen"]] == ["pausiert", "abgeschlossen", "storniert"]
    assert {a["ziel"]: a["begruendung_pflicht"] for a in daten["status_info"]["aktionen"]} == {
        "pausiert": True, "abgeschlossen": False, "storniert": True}
    assert daten["status_info"]["abschluss"] == {"schlussrechnung": False, "ohne_rechnung": True, "grund": None,
                                                 "stunden_gebucht": "0.00"}


@pytest.mark.parametrize("wert", ["beauftragt", "in_ausfuehrung", "arbeitsvorbereitung", "erledigt", "", "LAEUFT"])
def test_status_ausserhalb_der_liste_422(welt, wert):  # noqa: F811
    """Angriff: ein Status außerhalb der vier Werte -> 422, nichts geändert, keine Historie."""
    antwort = _status(_buero(welt), welt["order"].id, wert, "irgendwas")
    assert antwort.status_code == 422, antwort.text
    assert _frisch(welt).status == "laeuft"
    assert welt["db"].scalar(select(OrderStatusChange.id)) is None


@pytest.mark.parametrize("ziel", ["pausiert", "storniert"])
@pytest.mark.parametrize("begruendung", [None, "", "   "])
def test_pausieren_und_stornieren_ohne_begruendung_422(welt, ziel, begruendung):  # noqa: F811
    antwort = _status(_buero(welt), welt["order"].id, ziel, begruendung)
    assert antwort.status_code == 422, antwort.text
    assert _frisch(welt).status == "laeuft"


def test_put_und_beauftragen_mit_status_422(welt):  # noqa: F811
    """Angriff: der Status über PUT (bis 1.9.123 der Weg der Auftragsseite) und beim Beauftragen -> 422 mit dem Weg; ohne Status geht beides."""
    client = _buero(welt)
    antwort = client.put(f"/api/orders/{welt['order'].id}", json={"title": "Neu", "status": "storniert"})
    assert antwort.status_code == 422 and "POST /api/orders/{id}/status" in antwort.text
    assert _frisch(welt).status == "laeuft" and _frisch(welt).title == "Wartung"
    assert client.put(f"/api/orders/{welt['order'].id}", json={"title": "Neu"}).status_code == 200
    quote = make_quote(welt["db"], is_consumer=False, number="0544q")
    abgelehnt = client.post(f"/api/quotes/{quote.id}/convert-to-order", json={"status": "arbeitsvorbereitung"})
    assert abgelehnt.status_code == 422, abgelehnt.text
    angelegt = client.post(f"/api/quotes/{quote.id}/convert-to-order", json={})
    assert angelegt.status_code == 200, angelegt.text
    assert angelegt.json()["status"] == "laeuft"


def test_pausieren_fortsetzen_mit_historie(welt):  # noqa: F811
    """Pausieren mit Begründung, Fortsetzen ohne -- je eine Zeile in der Historie mit Person, im Änderungsprotokoll unter dem Projekt."""
    client = _buero(welt)
    antwort = _status(client, welt["order"].id, "pausiert", "Wechselrichter erst ab KW 47")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["status"] == "pausiert" and [a["ziel"] for a in daten["status_info"]["aktionen"]] == ["laeuft", "abgeschlossen", "storniert"]
    assert daten["status_info"]["letzter_wechsel"]["reason"] == "Wechselrichter erst ab KW 47"
    assert _status(client, welt["order"].id, "laeuft").status_code == 200
    historie = client.get(f"/api/orders/{welt['order'].id}/status-changes").json()
    assert [(h["old_status"], h["new_status"], h["reason"], h["action"]) for h in historie] == [
        ("laeuft", "pausiert", "Wechselrichter erst ab KW 47", "Pausieren"), ("pausiert", "laeuft", None, "Fortsetzen")]
    assert all(h["changed_by_name"] for h in historie)
    zeilen = welt["db"].scalars(select(AuditLog).where(AuditLog.entity_type == "Auftragsstatus").order_by(AuditLog.id)).all()
    assert len(zeilen) == 2 and zeilen[0].project_id == welt["order"].project_id
    assert zeilen[0].entity_label.endswith("läuft → pausiert")
    statuszeilen = welt["db"].scalars(select(AuditLog).where(AuditLog.entity_type == "Auftrag", AuditLog.field_name == "status")).all()
    assert [(z.old_value, z.new_value) for z in statuszeilen] == [("laeuft", "pausiert"), ("pausiert", "laeuft")]


def test_uebergaenge_die_nicht_gehen_409(welt):  # noqa: F811
    client = _buero(welt)
    assert _status(client, welt["order"].id, "laeuft").status_code == 409  # derselbe Status
    assert _status(client, welt["order"].id, "storniert", "Kunde hat abgesagt").status_code == 200
    for ziel, grund in (("laeuft", "doch"), ("pausiert", "Pause"), ("abgeschlossen", "ohne Rechnung")):
        antwort = _status(client, welt["order"].id, ziel, grund)
        assert antwort.status_code == 409 and "storniert" in antwort.json()["detail"], antwort.text
    assert _frisch(welt).status == "storniert"


def test_abschliessen_ohne_schlussrechnung_und_ohne_begruendung_409(welt):  # noqa: F811
    """Angriff: Abschließen ohne Schlussrechnung und ohne Begründung -> 409 mit dem Weg; mit Begründung „ohne Rechnung“ geht es (ohne jede
    Rechnung) und hält „ohne Rechnung“ fest."""
    client = _buero(welt)
    antwort = _status(client, welt["order"].id, "abgeschlossen")
    assert antwort.status_code == 409 and antwort.json()["detail"] == OHNE_RECHNUNG_TEXT
    assert _frisch(welt).status == "laeuft"
    assert _status(client, welt["order"].id, "abgeschlossen", "Kulanz, keine Rechnung").status_code == 200
    zeile = welt["db"].scalar(select(OrderStatusChange))
    assert (zeile.new_status, zeile.without_invoice, zeile.reason) == ("abgeschlossen", True, "Kulanz, keine Rechnung")


def test_ohne_rechnung_nur_ohne_jede_rechnung(welt):  # noqa: F811
    """Mit einem Abschlag (auch als Entwurf) gibt es kein „ohne Rechnung“ -- 409 mit der Nummer; nach der Schlussrechnung geht Abschließen
    ohne Begründung."""
    db = welt["db"]
    abschlag = create_abschlag_pauschal(db, welt["order"], lump_sum_net=Decimal("100"))
    client = _buero(welt)
    antwort = _status(client, welt["order"].id, "abgeschlossen", "ohne Rechnung")
    assert antwort.status_code == 409 and "Entwurf" in antwort.json()["detail"], antwort.text
    festschreiben(db, abschlag)
    antwort = _status(client, welt["order"].id, "abgeschlossen", "ohne Rechnung")
    assert antwort.status_code == 409 and abschlag.invoice_number in antwort.json()["detail"], antwort.text
    info = client.get(f"/api/orders/{welt['order'].id}").json()["status_info"]["abschluss"]
    assert info["ohne_rechnung"] is False and abschlag.invoice_number in info["grund"]
    schluss = create_schlussrechnung(db, _frisch(welt))
    festschreiben(db, schluss)
    assert client.get(f"/api/orders/{welt['order'].id}").json()["status_info"]["abschluss"]["schlussrechnung"] is True
    antwort = _status(client, welt["order"].id, "abgeschlossen")
    assert antwort.status_code == 200, antwort.text
    assert db.scalar(select(OrderStatusChange)).without_invoice is False


def test_fortsetzen_aus_abgeschlossen_nur_mit_begruendung(welt):  # noqa: F811
    client = _buero(welt)
    assert _status(client, welt["order"].id, "abgeschlossen", "ohne Rechnung").status_code == 200
    assert _status(client, welt["order"].id, "laeuft").status_code == 422
    assert _status(client, welt["order"].id, "laeuft", "Nacharbeit an der Rinne").status_code == 200
    assert _frisch(welt).status == "laeuft"


def test_historie_unveraenderlich(welt):  # noqa: F811
    status_aendern(welt["db"], welt["order"].id, "pausiert", "Regen")
    zeile = welt["db"].scalar(select(OrderStatusChange))
    zeile.reason = "anders"
    with pytest.raises(ArchiveImmutableError):
        welt["db"].commit()
    welt["db"].rollback()
    with pytest.raises(ArchiveImmutableError):
        welt["db"].delete(welt["db"].scalar(select(OrderStatusChange)))
        welt["db"].commit()
    welt["db"].rollback()


# --- Wirkung --------------------------------------------------------------------------------------------------------------------------

def _plantafel(w, client):
    heute = w["heute"]
    return client.get("/api/planning", params={"start": heute.isoformat(), "end": (heute + timedelta(days=13)).isoformat()}).json()


def _einsatz_planen(w, client):
    heute = w["heute"]
    return client.post("/api/planning/slots", json={"order_id": w["order"].id, "team_id": w["team"].id,
                                                    "start_date": heute.isoformat(), "end_date": heute.isoformat()})


def _bericht(client, w, employee_id=None):
    return client.post(f"/api/orders/{w['order'].id}/service-reports", json={"report_type": "rapport", "description": "Dach geprüft",
                                                                              "created_by_employee_id": employee_id})


def _mia_bucht(w):
    return _als(w, w["mia"]).post("/api/time-entries", json={"employee_id": w["mia"].id, "order_id": w["order"].id,
                                                             "work_date": w["gestern"].isoformat(), "von": "07:00", "bis": "12:00"})


def _buero_bucht(w):
    bea = make_employee(w["db"], "B-544", "Bea", "Büro")
    return _buero(w, role="buero_finanzen", employee_id=bea.id).post("/api/time-entries", json={
        "employee_id": bea.id, "order_id": w["order"].id, "work_date": w["gestern"].isoformat(), "hours": "2"})


def _vorbereiten(w):
    """Mia eingeplant am Auftrag (ein Einsatz der letzten Woche) -- der Zugang steht, gesperrt ist nur, was am Status hängt."""
    _einsatz(w, w["order"], [(w["heute"] - timedelta(days=7), w["heute"] - timedelta(days=6))], [w["mia"], w["tom"]])


def test_pausiert_sperrt_nichts(welt):  # noqa: F811
    """pausiert: Einsatz planen, Bericht, Buchung der Monteurin gehen; die Plantafel zeigt den Hinweis mit Begründung."""
    _vorbereiten(welt)
    client = _buero(welt)
    assert _status(client, welt["order"].id, "pausiert", "Gerüst fehlt").status_code == 200
    assert _mia_bucht(welt).status_code == 200
    assert _bericht(client, welt).status_code == 200
    geplant = _einsatz_planen(welt, client)
    assert geplant.status_code == 200, geplant.text
    assert (geplant.json()["order_status"], geplant.json()["order_status_reason"]) == ("pausiert", "Gerüst fehlt")


def test_abgeschlossen_kein_einsatz_nicht_in_der_plantafel_monteurin_bucht_nicht(welt):  # noqa: F811
    _vorbereiten(welt)
    offen = _zweiter_auftrag(welt)
    client = _buero(welt)
    assert {x["order_id"] for x in _plantafel(welt, client)["backlog"]} >= {offen.id}
    assert _status(client, welt["order"].id, "abgeschlossen", "ohne Rechnung").status_code == 200
    antwort = _einsatz_planen(welt, client)
    assert antwort.status_code == 409 and "abgeschlossen" in antwort.json()["detail"], antwort.text
    rueckstand = {x["order_id"] for x in _plantafel(welt, client)["backlog"]}
    assert welt["order"].id not in rueckstand and offen.id in rueckstand
    vorher = welt["db"].query(TimeEntry).count()
    gebucht = _mia_bucht(welt)
    assert gebucht.status_code == 409 and gebucht.json()["detail"] == AUFTRAG_ABGESCHLOSSEN_ZEITEN
    assert welt["db"].query(TimeEntry).count() == vorher
    assert _buero_bucht(welt).status_code == 200
    assert _bericht(client, welt).status_code == 200  # nur storniert sperrt Berichte


def test_storniert_einsatz_bericht_buchung_der_monteurin_409_rechnung_und_buero_200(welt):  # noqa: F811
    """Die Vorgabe: storniert -- Einsatz planen, Bericht anlegen (Büro und Monteurin), Buchung der Monteurin -> 409; Rechnung anlegen
    (Büro – Finanzen) und Buchung des Büros -> 200."""
    _vorbereiten(welt)
    client = _buero(welt)
    assert _status(client, welt["order"].id, "storniert", "Kunde hat abgesagt").status_code == 200
    planen = _einsatz_planen(welt, client)
    assert planen.status_code == 409 and "storniert" in planen.json()["detail"], planen.text
    assert welt["db"].query(PlanningSlot).count() == 1  # nur der Einsatz von vorher
    for bericht in (_bericht(client, welt), _bericht(_als(welt, welt["mia"]), welt)):
        assert bericht.status_code == 409 and bericht.json()["detail"] == BERICHT_STORNIERT, bericht.text
    assert welt["db"].query(ServiceReport).count() == 0
    gebucht = _mia_bucht(welt)
    assert gebucht.status_code == 409 and gebucht.json()["detail"] == AUFTRAG_STORNIERT_ZEITEN
    rechnung = _buero(welt, role="buero_finanzen").post(f"/api/orders/{welt['order'].id}/invoices/abschlag-pauschal",
                                                         json={"lump_sum_net": "100", "progress_description": "Teilleistung"})
    assert rechnung.status_code == 200, rechnung.text
    assert _buero_bucht(welt).status_code == 200


def test_bericht_anlegen_im_geschaeftsweg_gesperrt(welt):  # noqa: F811
    """Auch ohne Router (z. B. ein künftiger Aufrufer) legt create_report() zu einem stornierten Auftrag nichts an."""
    from app.auftragsstatus import AuftragGeschlossen
    from app.service_reports import create_report
    status_aendern(welt["db"], welt["order"].id, "storniert", "abgesagt")
    with pytest.raises(AuftragGeschlossen):
        create_report(welt["db"], welt["order"].id, report_type="rapport")


def test_statusregeln_ohne_gross_und_kleinschreibung():
    """F20: jede Regel liest den Status über app/auftragsstatus.py::wert() -- „ Storniert “ ist storniert, leer ist „läuft“."""
    from app.auftragsstatus import einsatz_gesperrt, geschlossen, storniert, wert
    class A:
        status = " Storniert "
    assert storniert(A) and geschlossen(A) and einsatz_gesperrt(A)
    A.status = None
    assert wert(A.status) == "laeuft" and not geschlossen(A) and einsatz_gesperrt(A) is None


def test_auftragsseite_ohne_statusauswahl():
    """Die Auftragsseite bietet keine Auswahl „Status“ mehr und schickt beim Speichern keinen Status; die Übergänge kommen aus dem Baustein."""
    from pathlib import Path
    from tests.vorlagen_js import bindet_ein
    seite = (Path(__file__).resolve().parent.parent / "app" / "templates" / "akte.html").read_text(encoding="utf-8")
    assert 'id="status"' not in seite and "status:document.getElementById('status')" not in seite
    assert bindet_ein("akte.html", "_auftragsstatus.html")
    angebot = (Path(__file__).resolve().parent.parent / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert 'id="oStatus"' not in angebot and "status:v('oStatus')" not in angebot
