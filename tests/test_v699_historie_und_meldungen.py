"""Version 1.9.299 (Geräte-Runde, Punkt 4).

    N2  Betriebsmittel und Prüffristen stehen in der Änderungshistorie („Betriebsmittel“, „Prüffrist“) -- bis 1.9.298 nur die Ressource; jedes Feld mit
        lesbarem Namen (Wächter v436/v438), der Name des Geräts wie auf seiner Seite
    N1  DELETE /api/resources/{id} an einem Gerät mit Betriebsmittel: 409 mit Meldung, nichts gelöscht -- bis 1.9.298 unter PostgreSQL 500 am Fremdschlüssel
    N6  zwei gleichzeitige Verknüpfungen derselben Ressource: der zweite bekommt die Meldung „bereits einem anderen Betriebsmittel zugeordnet“ (422) statt 500
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.audit import reset_audit_context, set_audit_context
from app.models import AuditLog, OperationalAsset, OperationalResource
from app.routers.operational_assets import router as asset_router
from app.routers.resource_planning import router as resource_router


class _Konto:
    id = None
    role = "admin"
    display_name = "Anna Admin"
    username = "anna"


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    token = set_audit_context(_Konto(), None)
    try:
        yield {"db": db, "c": router_test_client(db, asset_router, resource_router)}
    finally:
        reset_audit_context(token)


def _historie(db, art):
    db.expire_all()
    return db.scalars(select(AuditLog).where(AuditLog.entity_type == art).order_by(AuditLog.id)).all()


def test_betriebsmittel_und_pruefung_in_der_historie(welt):
    db, c = welt["db"], welt["c"]
    a = c.post("/api/operational-assets", json={"einplanbar": True, "name": "Pritsche HS-DK 202", "asset_type": "Fahrzeug", "asset_number": "BM-7"}).json()
    c.put(f"/api/operational-assets/{a['id']}", json={"usage_notes": "Nur mit Einweisung", "selectable_in_reports": True})
    r = c.post(f"/api/operational-assets/{a['id']}/inspections", json={"inspection_type": "TÜV / Hauptuntersuchung", "interval_months": 12,
                                                                        "last_inspection_date": date(2026, 5, 1).isoformat()})
    assert r.status_code == 200, r.text
    bm = _historie(db, "Betriebsmittel")
    assert bm and {z.entity_label for z in bm} == {"BM-7 Pritsche HS-DK 202"}
    felder = {z.field_name for z in bm if z.field_name}
    assert {"usage_notes", "selectable_in_reports"} <= felder
    pr = _historie(db, "Prüffrist")
    assert pr and pr[0].entity_label == "TÜV / Hauptuntersuchung · Pritsche HS-DK 202"
    assert _historie(db, "Ressource")  # das Plantafel-Gerät wie bisher


def test_ressource_mit_betriebsmittel_nicht_loeschen(welt):
    db, c = welt["db"], welt["c"]
    a = c.post("/api/operational-assets", json={"einplanbar": True, "name": "Kran", "asset_type": "Kran"}).json()
    r = c.delete(f"/api/resources/{a['resource_id']}")
    assert r.status_code == 409 and "gehört zu einem Betriebsmittel" in r.json()["detail"]
    db.expire_all()
    assert db.get(OperationalResource, a["resource_id"]) is not None and db.get(OperationalAsset, a["id"]).resource_id == a["resource_id"]
    frei = OperationalResource(name="Alt", resource_type="Sonstiges")
    db.add(frei)
    db.commit()
    assert c.delete(f"/api/resources/{frei.id}").json() == {"deleted": True}  # ohne Betriebsmittel und unbenutzt wie bisher


def test_gleichzeitige_verknuepfung_meldung_statt_500(welt, monkeypatch):
    db, c = welt["db"], welt["c"]
    r = OperationalResource(name="Anhänger", resource_type="Anhänger")
    db.add(r)
    db.commit()
    assert c.post("/api/operational-assets", json={"resource_id": r.id}).status_code == 200
    # der zweite kommt an der Prüfung im Code vorbei (wie bei zwei gleichzeitigen Anfragen) -- die Bedingung der Datenbank hält
    monkeypatch.setattr("app.operational_assets._validate_resource_not_taken", lambda *a, **k: None)
    zweite = c.post("/api/operational-assets", json={"resource_id": r.id})
    assert zweite.status_code == 422 and "bereits einem anderen Betriebsmittel zugeordnet" in zweite.json()["detail"]
    db.expire_all()
    assert len(db.scalars(select(OperationalAsset).where(OperationalAsset.resource_id == r.id)).all()) == 1
