"""Version 1.9.325 (Lohn L2c-1, Nachrunde, Punkt B): Hinweis beim Deaktivieren einer Person ohne Austritt.

    wann      das Speichern (PUT /api/employees/{id}) setzt die Person von aktiv auf inaktiv, und in den Lohnstammdaten steht kein Austritt (oder es gibt keine)
    was       „austritt_hinweis“ in der Antwort: „Austritt eintragen – sonst läuft die Sollzeit weiter“ -- nur ein Hinweis, gespeichert ist trotzdem, nichts
              gesperrt; sonst leer (mit Austritt, schon inaktiv, aktiv bleiben, wieder aktivieren)
    Seiten    das Formular bleibt nach dem Speichern stehen und zeigt den Hinweis mit „Zu den Lohnstammdaten“ (/settings?mitarbeiter=<id>#time-rules) und
              „Zur Liste“; die Lohnstammdaten zeigen die Person dann auch bei „Inaktive ausblenden“, der Cursor steht in ihrem Feld „Austritt“
"""

from datetime import date
from decimal import Decimal

from app.employees import AUSTRITT_HINWEIS
from app.models import Employee, EmployeePayrollSettings
from app.routers.employees import router as employees_router
from tests import vorlagen_js as vj

D = Decimal


def person(db, vorname, *, aktiv=True, austritt=None, lohn=True):
    e = Employee(first_name=vorname, last_name="Test", employee_group="gewerblich", hourly_wage=D("20"), weekly_hours=D("40"), active=aktiv)
    db.add(e)
    db.commit()
    if lohn:
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", austritt=austritt))
        db.commit()
    return e


def speichern(client, e, aktiv):
    return client.put(f"/api/employees/{e.id}", json={"first_name": e.first_name, "last_name": "Test", "employee_group": "gewerblich",
                                                      "compensation_type": "hourly", "hourly_wage": 20, "weekly_hours": 40, "active": aktiv})


def test_hinweis_nur_beim_deaktivieren_ohne_austritt(threaded_db_session, router_test_client):
    db = threaded_db_session
    c = router_test_client(db, employees_router)
    ohne, keine_lohnstammdaten = person(db, "Ada"), person(db, "Bo", lohn=False)
    mit = person(db, "Cem", austritt=date(2027, 3, 31))
    schon, bleibt, wieder = person(db, "Dan", aktiv=False), person(db, "Eli"), person(db, "Fe", aktiv=False)
    erwartet = {ohne: (False, AUSTRITT_HINWEIS), keine_lohnstammdaten: (False, AUSTRITT_HINWEIS), mit: (False, None), schon: (False, None),
                bleibt: (True, None), wieder: (True, None)}
    for e, (aktiv, hinweis) in erwartet.items():
        r = speichern(c, e, aktiv)
        assert r.status_code == 200, (e.first_name, r.text)
        assert (r.json()["active"], r.json()["austritt_hinweis"]) == (aktiv, hinweis), e.first_name
    db.expire_all()
    assert db.get(Employee, ohne.id).active is False  # gespeichert ist trotzdem -- nur ein Hinweis
    assert AUSTRITT_HINWEIS == "Austritt eintragen – sonst läuft die Sollzeit weiter"
    assert all(x.get("austritt_hinweis") is None for x in c.get("/api/employees").json())  # nur in der Antwort auf das Speichern


def test_seiten():
    form = vj.seitentext("master_data_form.html")[0]
    assert ("if(type==='employees'&&editing&&saved&&saved.austritt_hinweis){el('msg').textContent='Gespeichert.';"
            "austrittHinweisZeigen(saved.austritt_hinweis);return}") in form
    assert "href=\"/settings?mitarbeiter='+Number(recordId)+'#time-rules\">Zu den Lohnstammdaten</a>" in form
    einst = vj.seitentext("settings.html")[0]
    assert "x.active!==false||(ziel!=null&&x.employee_id===ziel)" in einst and "lohnDerListe(payroll,LOHN_ZIEL).map(" in einst and "lohnregelnNurLesen();lohnZielZeigen()}" in einst
