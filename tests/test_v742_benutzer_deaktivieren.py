"""Version 1.9.342 (Nachrunde V1, Punkt 2): „Deaktivieren“ statt „Löschen“ bei einem verwendeten Konto.

Entscheidung Tobias (14.11.2026): bei einem verwendeten Konto bietet die Seite „Benutzer“ gleich „Deaktivieren“ an, „Löschen“ nur für ein nie verwendetes.
Der Server sagt, wo ein Konto steht (`verwendet_in` in GET /api/users, aus app/konto_loeschen.py::verwendungen()), und deaktiviert über einen eigenen
Endpunkt -- PUT /api/users/{id} ist ein volles Update, ein „Deaktivieren“ dort schickte Rolle und Mitarbeiter mit oder setzte sie zurück (Regel 22).
"""

import re
from pathlib import Path

from sqlalchemy import func, select

from app import sitzungen
from app.models import AppUser, Employee, Task, UserSession
from app.routers.users import router as users_router

ROOT = Path(__file__).resolve().parents[1]


def _welt(db):
    ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add(ma)
    db.flush()
    bea = AppUser(username="bea", display_name="Bea", role="buero_finanzen", employee_id=ma.id, active=True, password_hash="x")
    carl = AppUser(username="carl", display_name="Carl", role="buero_auftrag", active=True, password_hash="x")
    db.add_all([bea, carl])
    db.flush()
    db.add(Task(title="Rückruf", created_by_user_id=bea.id))
    db.commit()
    return bea, carl, ma


def test_liste_sagt_wo_ein_konto_steht(threaded_db_session, router_test_client):
    db = threaded_db_session
    bea, carl, _ma = _welt(db)
    liste = {u["username"]: u["verwendet_in"] for u in router_test_client(db, users_router, user_id=900).get("/api/users").json()}
    assert liste["bea"] == ["Aufgaben"] and liste["carl"] == []


def test_deaktivieren_laesst_den_rest_und_beendet_die_sitzungen(threaded_db_session, router_test_client):
    db = threaded_db_session
    bea, _carl, ma = _welt(db)
    sitzungen.neue_sitzung(db, bea, zweiter_faktor=True)
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == bea.id)) == 1
    r = router_test_client(db, users_router, user_id=900).post(f"/api/users/{bea.id}/deaktivieren")
    assert r.status_code == 200, r.text
    assert (r.json()["active"], r.json()["role"], r.json()["employee_id"], r.json()["verwendet_in"]) == (False, "buero_finanzen", ma.id, ["Aufgaben"])
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == bea.id)) == 0
    nochmal = router_test_client(db, users_router, user_id=900).post(f"/api/users/{bea.id}/deaktivieren")  # schon inaktiv: bleibt, wie es ist
    assert (nochmal.status_code, nochmal.json()["active"]) == (200, False)


def test_deaktivieren_nicht_sich_selbst_nicht_den_letzten_admin_nur_admin(threaded_db_session, router_test_client):
    db = threaded_db_session
    bea, _carl, _ma = _welt(db)
    selbst = router_test_client(db, users_router, user_id=900).post("/api/users/900/deaktivieren")
    assert selbst.status_code == 409 and "selbst" in selbst.json()["detail"]
    admin = AppUser(username="ada", display_name="Ada", role="admin", active=True, password_hash="x")
    db.add(admin)
    db.commit()
    db.get(AppUser, 900).active = False  # das angemeldete Testkonto zählt nicht mit: Ada ist die letzte aktive Administratorin
    db.commit()
    letzte = router_test_client(db, users_router, user_id=900).post(f"/api/users/{admin.id}/deaktivieren")
    assert letzte.status_code == 409 and "letzte aktive Administrator" in letzte.json()["detail"]
    assert router_test_client(db, users_router, role="buero_finanzen").post(f"/api/users/{bea.id}/deaktivieren").status_code == 403
    assert router_test_client(db, users_router, user_id=900).post("/api/users/99999/deaktivieren").status_code == 404


def test_seite_bietet_loeschen_nur_ohne_verwendung():
    html = (ROOT / "app" / "templates" / "users.html").read_text(encoding="utf-8")
    knopf = re.search(r"function kontoKnopf\(u\)\{(.*?)\n\}", html, re.S).group(1)
    assert "if(!wo.length)return `<button class=\"danger\" data-klick=\"loeschen\" data-id=\"${u.id}\">Löschen</button>`;" in knopf
    assert "if(!u.active)return '';" in knopf and 'data-klick="deaktivieren"' in knopf
    assert "api(`/api/users/${id}/deaktivieren`,{method:'POST'})" in html
    assert "kontoKnopf(u)" in html and html.count(">Löschen</button>") == 1
    assert "aktion('loeschen',el=>deleteUser(Number(el.dataset.id)));" in html
