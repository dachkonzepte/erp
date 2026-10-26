"""Version 1.8.117 -- das Zeiterfassungs-Backoffice ist für Büro – Auftrag und Büro – Finanzen nutzbar, wie Seite und Endpunkte es erlauben
(Vorgabe vom 16.10.2026, Punkt 3).

Bis 1.8.116 brach init() in time_backoffice.html für jede Rolle außer Admin ab ("nur für Administratoren verfügbar"), obwohl die Seite und
alle Endpunkte seit 1.4.8 dem Büro offenstehen. Jetzt bekommt die Seite Rolle und Mitarbeiter des Kontos vom Server (ICH) und bietet nur an,
was der Server dem Konto erlaubt. Hier: welche Regeln des Servers die Seite abbildet (fremde Buchungen, abgeschlossener Zeitraum, Anträge,
Abschluss), jede Anfrage der Seite für das Büro erlaubt, die gerenderte Rolle. Das Verhalten im Browser prüft
scripts/klicktest_backoffice_buero.py.

Seit 1.9.89 (Stufe 4, R5a, Entscheidungen Tobias): Büro – Auftrag liest die Zeiten aller und ändert nichts (auch keine eigenen), Büro –
Finanzen ändert die Buchungen aller außerhalb des abgeschlossenen Zeitraums und hat die Lohndaten (Stundenzettel, CSV, DATEV, Abschluss);
die Seite bekommt das vom Server (ICH.buchen, ICH.andere, ICH.lohn) und zeigt Büro – Auftrag die Ausgabe nicht."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import Employee, EmployeeAbsenceRequest, TimeEntry, TimeTrackingSettings
from app.routers import absence_requests, employees, pages, settings as settings_router, time_backoffice, time_tracking
from tests.test_v133_invoices import make_order_with_item

VORLAGE = Path(__file__).resolve().parent.parent / "app" / "templates" / "time_backoffice.html"
HEUTE = date(2026, 10, 16)
VON, BIS = "2026-10-01", "2026-10-31"


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    order, item = make_order_with_item(db)
    bea = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="angestellt", hourly_wage=Decimal("22"))
    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", hourly_wage=Decimal("22"))
    db.add_all([bea, mia]); db.flush()

    def te(ma, tag):
        return TimeEntry(employee_id=ma.id, project_id=order.project_id, order_id=order.id, work_date=tag, entry_type="site",
                         counts_as_productive=True, hours=Decimal("2"), status="booked", source="manual")

    eintraege = {"bea_zu": te(bea, date(2026, 10, 1)), "bea_offen": te(bea, date(2026, 10, 2)), "mia": te(mia, date(2026, 10, 2))}
    db.add_all(eintraege.values())
    for ma in (bea, mia):
        db.add(EmployeeAbsenceRequest(employee_id=ma.id, absence_type="Urlaub", start_date=HEUTE + timedelta(days=30),
                                      end_date=HEUTE + timedelta(days=31), status="pending"))
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 1)
    db.commit()
    return db, bea, mia, order, {k: v.id for k, v in eintraege.items()}


ROUTER = (time_backoffice.router, employees.router, time_tracking.router, absence_requests.router, settings_router.router, pages.router)

# Jede Anfrage, die die Seite schickt (GET, für das Büro immer erlaubt) -- test_jede_anfrage_der_seite_ist_hier_geprueft hält die Liste
# mit der Vorlage gleich. Seit 1.9.89 getrennt: GET_NUR_LOHN fragt die Seite nur mit Lohndaten (ICH.lohn), der Server gibt die Ausgaben
# nur Admin und Büro – Finanzen (die Personalnummern liest weiter jedes Büro).
GET_DER_SEITE = ["/api/employees", f"/api/time-backoffice/summary?start_date={VON}&end_date={BIS}", "/api/time-backoffice/settings",
                 "/api/settings/option-groups", f"/api/time-entries?start_date={VON}&end_date={BIS}&limit=2000"]
GET_NUR_LOHN = ["/api/time-backoffice/payroll-employees",
                f"/api/time-backoffice/timesheet.pdf?start_date={VON}&end_date={BIS}",
                f"/api/time-backoffice/timesheet.csv?start_date={VON}&end_date={BIS}",
                f"/api/time-backoffice/datev-export?start_date={VON}&end_date={BIS}"]


@pytest.mark.parametrize("rolle", ["buero_auftrag", "buero_finanzen"])
def test_jede_anfrage_der_seite_ist_dem_buero_erlaubt(welt, router_test_client, rolle):
    db, bea, *_ = welt
    for mitarbeiter in (bea.id, None):
        client = router_test_client(db, *ROUTER, role=rolle, employee_id=mitarbeiter)
        status = {pfad: client.get(pfad).status_code for pfad in GET_DER_SEITE}
        assert set(status.values()) == {200}, status
        assert client.get(GET_NUR_LOHN[0]).status_code == 200
        lohn = {pfad: client.get(pfad).status_code for pfad in GET_NUR_LOHN[1:]}
        assert set(lohn.values()) == ({200} if rolle == "buero_finanzen" else {403}), lohn  # seit 1.9.89
        # seit 1.9.89 liest jedes Büro den Kontext, auch ohne eigenen Mitarbeiter (bis dahin 403); die Seite fragt ihn, wer bucht
        assert client.get("/api/time-tracking/context").status_code == 200
        # Anträge nur mit Mitarbeiter -- die Seite fragt ohne ihn nicht (ICH.mitarbeiter === null)
        assert client.get("/api/absence-requests").status_code == (200 if mitarbeiter else 403)


def test_was_der_server_dem_buero_auftrag_nicht_erlaubt(welt, router_test_client):
    """Büro – Auftrag liest seit 1.9.89 nur: keine Buchung ändern, auch keine eigene (bis 1.9.88: eigene offene 200), nicht abschließen
    (bis 1.9.88 vorrücken 200), keinen Antrag entscheiden."""
    db, bea, mia, order, ids = welt
    buero = router_test_client(db, *ROUTER, role="buero_auftrag", employee_id=bea.id)
    assert [x["employee_name"] for x in buero.get("/api/absence-requests").json()] == ["Bea Büro"]  # nur die eigenen
    antrag = db.query(EmployeeAbsenceRequest).filter_by(employee_id=bea.id).one()
    assert buero.post(f"/api/absence-requests/{antrag.id}/review", json={"decision": "approved"}).status_code == 403
    for eintrag in ("mia", "bea_zu", "bea_offen"):
        assert buero.put(f"/api/time-entries/{ids[eintrag]}", json={"hours": 3}).status_code == 403, eintrag
    assert buero.put("/api/time-backoffice/lock", json={"locked_until": "2026-10-02"}).status_code == 403


def test_was_der_server_dem_buero_finanzen_erlaubt(welt, router_test_client):
    """Büro – Finanzen seit 1.9.89: fremde Buchungen außerhalb des abgeschlossenen Zeitraums ändern, vorrücken -- nicht im abgeschlossenen
    Zeitraum, nicht wieder öffnen oder aufheben, keinen Antrag entscheiden (das bleibt dem Admin)."""
    db, bea, mia, order, ids = welt
    buero = router_test_client(db, *ROUTER, role="buero_finanzen", employee_id=bea.id)
    antrag = db.query(EmployeeAbsenceRequest).filter_by(employee_id=bea.id).one()
    assert buero.post(f"/api/absence-requests/{antrag.id}/review", json={"decision": "approved"}).status_code == 403
    assert buero.put(f"/api/time-entries/{ids['mia']}", json={"hours": 3}).status_code == 200          # fremd, offen
    assert buero.put(f"/api/time-entries/{ids['bea_zu']}", json={"hours": 3}).status_code == 403       # abgeschlossen
    assert buero.put("/api/time-backoffice/lock", json={"locked_until": "2026-10-02"}).status_code == 200  # vorrücken
    assert buero.put("/api/time-backoffice/lock", json={"locked_until": "2026-10-01"}).status_code == 403  # wieder öffnen
    assert buero.put("/api/time-backoffice/lock", json={"locked_until": None}).status_code == 403          # aufheben


def _ich(html: str) -> str:
    return re.search(r"const ICH=\{[^}]*\};", html).group(0)


@pytest.mark.parametrize("rolle, mitarbeiter, ich, aufheben", [
    ("buero_auftrag", 7, "const ICH={admin:false,buchen:false,andere:false,lohn:false,mitarbeiter:7};", False),
    ("buero_finanzen", None, "const ICH={admin:false,buchen:true,andere:true,lohn:true,mitarbeiter:null};", False),
    ("admin", None, "const ICH={admin:true,buchen:true,andere:true,lohn:true,mitarbeiter:null};", True),
])
def test_die_seite_bekommt_rolle_und_mitarbeiter_vom_server(welt, router_test_client, rolle, mitarbeiter, ich, aufheben):
    """Seit 1.9.89 dazu buchen, andere und lohn (app/permissions.py); ohne Lohndaten fehlen die Reiter der Ausgabe und ihr Inhalt."""
    db = welt[0]
    html = router_test_client(db, pages.router, role=rolle, employee_id=mitarbeiter).get("/time-backoffice").text
    assert _ich(html) == ich
    lohn = rolle != "buero_auftrag"
    assert ('onclick="clearLock()"' in html) is aufheben and ('id="nurAdminOeffnen"' in html) is (lohn and not aufheben)
    assert ('data-tab="timesheets"' in html, 'data-tab="datev"' in html, 'id="lockDate"' in html) == (lohn, lohn, lohn)


def test_keine_rollenpruefung_mehr_im_browser():
    quelle = VORLAGE.read_text(encoding="utf-8")
    assert "nur für Administratoren verfügbar" not in quelle and "/api/auth/status" not in quelle


def test_jede_anfrage_der_seite_ist_hier_geprueft():
    """Eine neue Anfrage der Seite braucht ihren Platz in GET_DER_SEITE oder in den Regeln oben."""
    quelle = VORLAGE.read_text(encoding="utf-8")
    pfade = {re.sub(r"\$\{[^}]*\}.*", "", p).split("?")[0].rstrip(".")
             for p in re.findall(r"(?:api\(|location\.href=)[`']((?:/api/)[^`']*)", quelle)}
    geprueft = {p.split("?")[0] for p in GET_DER_SEITE + GET_NUR_LOHN} | {"/api/time-tracking/context", "/api/absence-requests",
                                                            "/api/absence-requests/", "/api/time-backoffice/lock",
                                                            "/api/time-entries/", "/api/orders/", "/api/time-backoffice/timesheet"}
    assert pfade <= geprueft, pfade - geprueft
