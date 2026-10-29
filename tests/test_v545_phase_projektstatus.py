"""Seit 1.9.125 (Stufe 5, R2, Punkt 1): die Phase je Auftrag aus den Daten und der abgeleitete Projektstatus (app/akte.py).

    Phase       Angebot (immer, „angenommen“ mit dem Tag der Beauftragung) · Auftrag (immer) · Ausführung (erste Zeitbuchung, erster begonnener
                Einsatz oder erster Bericht; ein Einsatz in der Zukunft nur „geplant ab“) · Abnahme (gültig und abgenommen; verweigert und
                verworfen nicht) · Schlussrechnung (gültige Schlussrechnung oder abschließende Rechnung aus Aufwand); die letzte erreichte ist
                „jetzt“
    Projekt     ohne Angebot Anfrage, mit Angebot ohne Auftrag Angebot, sonst die früheste Phase der laufenden und pausierten Aufträge;
                alle geschlossen: Abgeschlossen (mindestens einer) bzw. Storniert -- kein Feld von Hand (422), Listen und Dashboard lesen ihn
    Prüfung     scripts/pruefe_projektstatus.py nennt Projekte, deren gespeicherter Status nicht passt (z. B. „beauftragt“ ohne Auftrag)
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app import berlin_time
from app.akte import phasen, phasen_ohne_auftrag, projekt_status, projekt_status_alle, signale
from app.auftragsstatus import status_aendern
from app.invoices import create_schlussrechnung
from app.models import (
    Customer, OrderAcceptance, PlanningSlot, Project, Quote, ServiceReport, TimeEntry, WorkPreparation, WorkPreparationTeamAssignment,
)
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers import projects as projects_router
from app.routers import orders as orders_router
from tests.leistungszeitraum import festschreiben
from tests.test_v224_field_view import make_employee, make_team
from tests.test_v325_contract_basis import beauftragen, make_quote

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def welt(threaded_db_session, router_test_client, feste_uhr):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0545a"))
    return {"db": db, "order": order, "heute": berlin_time.berlin_today(), "client": router_test_client,
            "mia": make_employee(db, "M-545", "Mia", "Monteurin"), "team": make_team(db, "K-545", "Kolonne")}


def _schritte(w, order=None):
    order = order or w["order"]
    w["db"].expire_all()
    info = phasen(order, signale(w["db"], [order.id])[order.id], w["heute"])
    return info["phase"], {s["key"]: (s["erreicht"], s["jetzt"], s["text"]) for s in info["schritte"]}


def _buchung(w, tag, hours="7.5"):
    w["db"].add(TimeEntry(employee_id=w["mia"].id, project_id=w["order"].project_id, order_id=w["order"].id, work_date=tag,
                          hours=Decimal(hours), status="booked", entry_type="site", counts_as_productive=True, source="manual"))
    w["db"].commit()


def _einsatz(w, beginn):
    db = w["db"]
    prep = db.query(WorkPreparation).filter_by(order_id=w["order"].id).one_or_none()
    if prep is None:
        prep = WorkPreparation(order_id=w["order"].id, status="offen")
        db.add(prep); db.flush()
    zuordnung = db.query(WorkPreparationTeamAssignment).filter_by(preparation_id=prep.id).one_or_none()
    if zuordnung is None:
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=w["team"].id, team_name_snapshot="Kolonne")
        db.add(zuordnung); db.flush()
    db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=beginn, end_date=beginn + timedelta(days=2)))
    db.commit()


def _abnahme(w, tag, *, result="abgenommen", discarded=False):
    w["db"].add(OrderAcceptance(order_id=w["order"].id, kind="formlos", accepted_on=tag, scope="gesamt", result=result,
                                declared_by="auftraggeber", declared_by_name="Herr Klar", content_sha256="0" * 64, checksum_format=1,
                                discarded_at=datetime(2026, 10, 1) if discarded else None))
    w["db"].commit()


# --- Phase je Fall --------------------------------------------------------------------------------------------------------------------

def test_phase_ohne_auftrag_und_mit_angebot():
    """Vor dem ersten Auftrag: ohne Angebot nichts erreicht; mit Angebot die Phase des Angebots mit Nummer und Stand."""
    leer = phasen_ohne_auftrag([])
    assert leer["phase"] is None and not any(s["erreicht"] for s in leer["schritte"])
    angebot = phasen_ohne_auftrag([Quote(id=1, quote_number="A-1", status="entwurf"), Quote(id=2, quote_number="A-2", status="versendet")])
    assert angebot["phase"] == "angebot" and angebot["schritte"][0]["text"] == "A-2 · versendet" and angebot["schritte"][0]["jetzt"]


def test_phase_auftrag_ohne_ausfuehrung(welt):
    phase, s = _schritte(welt)
    assert phase == "auftrag"
    assert s["angebot"] == (True, False, "A-0545a · angenommen 30.09.")
    assert s["auftrag"] == (True, True, "30.09. · VOB/B")
    assert s["ausfuehrung"] == (False, False, "noch nicht begonnen")
    assert s["abnahme"] == (False, False, "noch nicht erfasst") and s["schlussrechnung"] == (False, False, "nach der Abnahme")


def test_phase_ausfuehrung_ab_der_ersten_buchung(welt):
    _buchung(welt, welt["heute"] - timedelta(days=3))
    _buchung(welt, welt["heute"] - timedelta(days=1), "2")
    phase, s = _schritte(welt)
    assert phase == "ausfuehrung" and s["ausfuehrung"][:2] == (True, True)
    assert s["ausfuehrung"][2].startswith("seit ") and s["ausfuehrung"][2].endswith("9,50 h gebucht")  # seit 1.9.132 zwei Stellen


def test_einsatz_in_der_zukunft_nur_geplant_begonnener_zaehlt(welt):
    _einsatz(welt, welt["heute"] + timedelta(days=5))
    phase, s = _schritte(welt)
    assert phase == "auftrag" and s["ausfuehrung"][2].startswith("geplant ab ")
    _einsatz(welt, welt["heute"] - timedelta(days=1))
    assert _schritte(welt)[0] == "ausfuehrung"


def test_ein_bericht_beginnt_die_ausfuehrung(welt):
    welt["db"].add(ServiceReport(order_id=welt["order"].id, report_type="rapport", performed_at=welt["heute"], status="entwurf"))
    welt["db"].commit()
    assert _schritte(welt)[0] == "ausfuehrung"


def test_abnahme_nur_gueltig_und_abgenommen(welt):
    _buchung(welt, welt["heute"] - timedelta(days=3))
    _abnahme(welt, welt["heute"] - timedelta(days=1), result="verweigert")
    _abnahme(welt, welt["heute"], discarded=True)
    phase, s = _schritte(welt)
    assert phase == "ausfuehrung" and s["abnahme"][0] is False and s["abnahme"][2].startswith("verweigert ")
    _abnahme(welt, welt["heute"])
    phase, s = _schritte(welt)
    assert phase == "abnahme" and s["abnahme"][:2] == (True, True) and s["abnahme"][2].startswith("abgenommen ")


def test_schlussrechnung_erst_festgeschrieben(welt):
    _buchung(welt, welt["heute"] - timedelta(days=3))
    _abnahme(welt, welt["heute"] - timedelta(days=1))
    schluss = create_schlussrechnung(welt["db"], welt["order"])
    assert _schritte(welt)[0] == "abnahme"  # der Entwurf zählt nicht
    festschreiben(welt["db"], schluss)
    phase, s = _schritte(welt)
    assert phase == "schlussrechnung" and s["schlussrechnung"][:2] == (True, True) and schluss.invoice_number in s["schlussrechnung"][2]


def test_phase_in_der_antwort_des_auftrags(welt):
    daten = welt["client"](welt["db"], orders_router.router).get(f"/api/orders/{welt['order'].id}").json()
    assert (daten["phase"], daten["phase_label"]) == ("auftrag", "Auftrag")
    assert [s["key"] for s in daten["phasen"]["schritte"]] == ["angebot", "auftrag", "ausfuehrung", "abnahme", "schlussrechnung"]


# --- Projektstatus --------------------------------------------------------------------------------------------------------------------

def _projekt(db, number, *, angebot=False):
    kunde = Customer(name=f"K {number}", last_name=f"K {number}")
    db.add(kunde); db.flush()
    p = Project(project_number=f"P-{number}", name="Dach", customer_id=kunde.id, status="beauftragt",
                pipeline_column_id=default_pipeline_column_id(db))
    db.add(p); db.flush()
    if angebot:
        db.add(Quote(quote_number=f"A-{number}", project_id=p.id, title="Dach", vat_rate=Decimal("19")))
    db.commit()
    return p


def test_projektstatus_anfrage_angebot_auftrag(welt):
    """„beauftragt“ gespeichert, aber kein Auftrag: abgeleitet Anfrage bzw. Angebot -- der gespeicherte Wert zählt nicht."""
    db = welt["db"]
    ohne, mit_angebot = _projekt(db, "545b"), _projekt(db, "545c", angebot=True)
    alle = projekt_status_alle(db, [ohne.id, mit_angebot.id, welt["order"].project_id])
    assert alle == {ohne.id: "anfrage", mit_angebot.id: "angebot", welt["order"].project_id: "auftrag"}


def test_projektstatus_frueheste_phase_der_laufenden_auftraege(welt):
    """Zwei Aufträge: einer in Ausführung, einer pausiert ohne Ausführung -> Auftrag; der zweite storniert -> Ausführung; beide geschlossen
    -> Abgeschlossen; nur stornierte -> Storniert."""
    db = welt["db"]
    zweiter = make_quote(db, is_consumer=False, number="0545d")
    zweiter.project_id = welt["order"].project_id
    db.commit()
    order2 = beauftragen(db, zweiter)
    _buchung(welt, welt["heute"] - timedelta(days=1))
    status_aendern(db, order2.id, "pausiert", "Material fehlt")
    pid = welt["order"].project_id
    assert projekt_status(db, db.get(Project, pid)) == "auftrag"
    status_aendern(db, order2.id, "storniert", "abgesagt")
    assert projekt_status(db, db.get(Project, pid)) == "ausfuehrung"
    status_aendern(db, welt["order"].id, "abgeschlossen", "ohne Rechnung")
    assert projekt_status(db, db.get(Project, pid)) == "abgeschlossen"
    nur_storno = beauftragen(db, make_quote(db, is_consumer=False, number="0545e"))
    status_aendern(db, nur_storno.id, "storniert", "abgesagt")
    assert projekt_status(db, db.get(Project, nur_storno.project_id)) == "storniert"


def test_kein_status_von_hand(welt):
    """Angriff: Status beim Anlegen und Ändern eines Projekts -> 422; ohne Status gehen beide, die Liste liefert den abgeleiteten mit Namen."""
    db = welt["db"]
    client = welt["client"](db, projects_router.router)
    kunde = db.get(Customer, db.get(Project, welt["order"].project_id).customer_id)
    angelegt = client.post("/api/projects", json={"customer_id": kunde.id, "name": "Neu", "status": "beauftragt"})
    assert angelegt.status_code == 422, angelegt.text
    angelegt = client.post("/api/projects", json={"customer_id": kunde.id, "name": "Neu"})
    assert angelegt.status_code == 200 and (angelegt.json()["status"], angelegt.json()["status_label"]) == ("anfrage", "Anfrage")
    pid = welt["order"].project_id
    geaendert = client.put(f"/api/projects/{pid}", json={"customer_id": kunde.id, "name": "Dach", "status": "abgeschlossen"})
    assert geaendert.status_code == 422, geaendert.text
    geaendert = client.put(f"/api/projects/{pid}", json={"customer_id": kunde.id, "name": "Dach neu"})
    assert geaendert.status_code == 200 and geaendert.json()["status"] == "auftrag"
    liste = {p["id"]: (p["status"], p["status_label"]) for p in client.get("/api/projects").json()}
    assert liste[pid] == ("auftrag", "Auftrag") and liste[angelegt.json()["id"]] == ("anfrage", "Anfrage")


def test_beauftragen_schreibt_den_projektstatus_nicht_mehr(welt):
    """Seit 1.9.125 setzt die Beauftragung den gespeicherten Status nicht mehr (bis 1.9.124 „beauftragt“, auch aus „abgeschlossen“)."""
    db = welt["db"]
    quote = make_quote(db, is_consumer=False, number="0545f")
    project = db.get(Project, quote.project_id)
    project.status = "abgeschlossen"
    db.commit()
    beauftragen(db, quote)
    db.expire_all()
    assert db.get(Project, quote.project_id).status == "abgeschlossen"
    assert projekt_status(db, db.get(Project, quote.project_id)) == "auftrag"


def test_listen_und_dashboard_lesen_den_abgeleiteten():
    """Projektliste, Projektmappe und Dashboard zeigen den Namen vom Server und zählen nach den abgeleiteten Werten; keine Seite bietet
    den Status zur Auswahl an."""
    t = ROOT / "app" / "templates"
    liste, mappe, form, dash = (t / n for n in ("projects.html", "akte.html", "project_form.html", "dashboard.html"))
    assert "esc(p.status_label||p.status)" in liste.read_text(encoding="utf-8")
    assert "statusKennzeichen('projekt',project.status)" in mappe.read_text(encoding="utf-8")  # seit 1.9.129 die Akte (Projektmappe und Auftragsseite in einer Seite): Status im Seitenkopf
    for seite in (mappe, form):
        text = seite.read_text(encoding="utf-8")
        assert "editProjectStatus" not in text and 'id="status"' not in text and "status:document.getElementById" not in text
    d = dash.read_text(encoding="utf-8")
    assert "PROJEKT_AKTIV.includes(p.status)" in d and "'planung','beauftragt','ausfuehrung'" not in d


def test_pruefskript_nennt_unpassende_projekte(welt):
    """scripts/pruefe_projektstatus.py: „beauftragt“ ohne Auftrag -> Treffer mit Projektnummer; der beauftragte Auftrag passt (Rückgabe 1);
    nur passende -> „Alle n Projekte passen.“ (0)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pruefe_projektstatus", ROOT / "scripts" / "pruefe_projektstatus.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    db = welt["db"]
    db.get(Project, welt["order"].project_id).status = "beauftragt"
    db.commit()
    zeilen = []
    assert modul.main([], sitzung=db, ausgabe=zeilen.append) == 0
    assert zeilen == ["Alle 1 Projekte passen."]
    _projekt(db, "545g")  # „beauftragt“ gespeichert, ohne Angebot und Auftrag
    zeilen = []
    assert modul.main([], sitzung=db, ausgabe=zeilen.append) == 1
    assert zeilen[0] == "1 von 2 Projekten passen nicht zur Ableitung:"
    assert zeilen[1] == "  P-545g Dach: gespeichert „beauftragt“, abgeleitet „Anfrage“ (0 Angebot(e), 0 Auftrag/Aufträge)"
