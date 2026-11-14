"""Version 1.9.340 (Runde V1, Punkt 3): E1–E5 aus dem Befund SQLite/PostgreSQL behoben, „Benutzer löschen“ mit Meldung statt 500.

Alle fünf scheiterten live (PostgreSQL) an einem Fremdschlüssel, weil zwischen zwei Tabellen ohne ORM-Beziehung in der falschen Reihenfolge gelöscht
wurde; seit 1.9.339 scheitern sie unter PRAGMA foreign_keys=ON auch in der Suite (bis 1.9.339 dort als erwartet rot geführt). Die bestehenden Tests
(v194 E1, v247 E2, v214 E3, v105 E4, v083 E5) laufen wieder normal; dieser Test ergänzt je Fall, was sie nicht prüfen:

- E1 über die echte Route (wie die Probe P10 des Befunds);
- E4: die Kalkulation behält ihre Werte, nur der Verweis auf das alte Quellmaterial ist leer;
- E5: auch eine Lieferanten-Zuordnung allein übersteht den Neuaufbau (F1: „die Lieferanten-Zuordnungen gleich mitprüfen“);
- „Benutzer löschen“: steht das Konto anderswo, 409 mit den Bereichen und dem Rat zu deaktivieren; sonst geht es mit allem, was zu ihm gehört;
  jeder Fremdschlüssel auf app_users ist eingeordnet.
"""

from decimal import Decimal

from sqlalchemy import func, select

from app.konto_loeschen import BEREICHE, MIT_DEM_KONTO, fremdschluessel_auf_konten
from app.models import (AppUser, Project, QuoteItemLayout, QuoteItemMaterialCalculation, QuoteSection, Task, TwoFactorRecoveryCode,
                        UserDashboardWidget)
from app.routers.projects import router as projects_router
from app.routers.users import router as users_router
from app.schemas import SupplierCreate, WorkPreparationMaterialBulkAssign
from app.work_preparation import ensure_preparation, preparation_to_dict, refresh_preparation_materials
from tests.test_v083_material_bulk_assignment import db_session as av_db, setup_order
from tests.test_v192_project_templates import make_full_project


def test_e1_projekt_mit_lv_titeln_ueber_die_route_loeschen(threaded_db_session, router_test_client):
    db = threaded_db_session
    projekt = make_full_project(db)
    projekt_id, angebot_id = projekt.id, projekt.quotes[0].id
    assert db.scalar(select(func.count()).select_from(QuoteItemLayout).where(QuoteItemLayout.section_id.is_not(None))) >= 1
    db.commit()
    r = router_test_client(db, projects_router).delete(f"/api/projects/{projekt_id}")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Project, projekt_id) is None
    assert db.scalar(select(func.count()).select_from(QuoteSection).where(QuoteSection.quote_id == angebot_id)) == 0


def test_e4_erneuter_import_loest_nur_den_verweis_der_kalkulation():
    from pathlib import Path
    from app.importers.leistungen_dach import parse_leistungen_dach_xml
    from app.service import persist_project
    db = av_db()
    setup_order(db)
    vorher = {k.id: (k.name, k.quantity, k.purchase_price) for k in db.scalars(select(QuoteItemMaterialCalculation)).all()
              if k.source_material_id is not None}
    assert vorher, "Vorbedingung: eine Kalkulation hat Material aus dem Katalog übernommen"
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    persist_project(db, parse_leistungen_dach_xml(sample.read_bytes()), "Thiefes.xml")  # erneut importieren
    db.expire_all()
    for kid, werte in vorher.items():
        k = db.get(QuoteItemMaterialCalculation, kid)
        assert k.source_material_id is None
        assert (k.name, k.quantity, k.purchase_price) == werte


def test_e5_lieferant_allein_uebersteht_den_neuaufbau():
    from app.main import bulk_assign_work_preparation_materials, create_supplier
    db = av_db()
    order = setup_order(db)
    prep = ensure_preparation(db, order.id)
    lieferant = create_supplier(SupplierCreate(name="Lieferant allein"), db)
    mid = preparation_to_dict(db, prep)["materials"][0]["id"]
    bulk_assign_work_preparation_materials(WorkPreparationMaterialBulkAssign(material_ids=[mid], supplier_id=lieferant.id), db)
    refresh_preparation_materials(db, order.id)
    db.commit()
    nachher = preparation_to_dict(db, ensure_preparation(db, order.id))["materials"]
    assert any(m["supplier_id"] == lieferant.id for m in nachher)


def _konto(db, name):
    k = AppUser(username=name, display_name=name.capitalize(), role="buero_auftrag", active=True, password_hash="x")
    db.add(k)
    db.commit()
    return k


def test_konto_mit_verwendung_wird_nicht_geloescht_sondern_erklaert(threaded_db_session, router_test_client):
    db = threaded_db_session
    bea = _konto(db, "bea")
    db.add(Task(title="Rückruf", created_by_user_id=bea.id))
    db.commit()
    r = router_test_client(db, users_router, user_id=900).delete(f"/api/users/{bea.id}")
    assert r.status_code == 409, r.text
    assert "Aufgaben" in r.json()["detail"] and "Deaktiviere" in r.json()["detail"]
    db.expire_all()
    assert db.get(AppUser, bea.id) is not None


def test_konto_ohne_verwendung_geht_mit_allem_was_zu_ihm_gehoert(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom = _konto(db, "tom")
    db.add_all([UserDashboardWidget(user_id=tom.id, widget_key="aufgaben"), TwoFactorRecoveryCode(user_id=tom.id, code_hash="h")])
    db.commit()
    r = router_test_client(db, users_router, user_id=900).delete(f"/api/users/{tom.id}")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(AppUser, tom.id) is None
    assert db.scalar(select(func.count()).select_from(UserDashboardWidget).where(UserDashboardWidget.user_id == tom.id)) == 0


def test_jeder_fremdschluessel_auf_konten_ist_eingeordnet():
    alle = fremdschluessel_auf_konten()
    eingeordnet = {(t, s) for t, s in alle if t in MIT_DEM_KONTO} | set(BEREICHE)
    assert set(alle) == eingeordnet, f"nicht eingeordnet: {sorted(set(alle) - eingeordnet)}; veraltet: {sorted(eingeordnet - set(alle))}"
    assert not {t for t, _ in BEREICHE} & set(MIT_DEM_KONTO)
