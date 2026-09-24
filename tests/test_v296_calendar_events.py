"""Version 1.7.0 -- Kalender-Modul (Stufe 1), Modul "kalender": Büro-Termine (Besichtigung/
Aufmaß/Besprechung), bewusst GETRENNT von der Plantafel (siehe CLAUDE.md "Kalender" für die
volle Herleitung inkl. des Stufe-2-Befunds zur Outlook-Synchronisation, die hier NICHT gebaut
ist). Deckt ab: create/update/delete/list (echtes Teil-Update, Zeitraum-/Zuordnungsvalidierung),
die serverseitige Privatsphäre-Redaktion (eigener privater Termin voll sichtbar, fremder
privater Termin nur "Belegt" ohne Titel/Ort/Notiz/Projekt-/Angebotsbezug), list_owners() (nur
Büro-/Admin-Rollen), das Entkoppeln von Projekt/Angebot beim Löschen eines Projekts, und den
abschließend verlangten Angriffstest: field kommt an keinen Teil des Moduls, auch nicht bei
deaktiviertem Modul für Büro-Rollen."""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.calendar_events import (
    create_event, delete_event, get_event, is_redacted_for_viewer, list_events, list_owners,
    redact_for_busy, unlink_calendar_events_for_project, update_event,
)
from app.database import Base, get_db
from app.models import AppUser, Customer, EnabledModule, Project, Quote
from app.permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import delete_project
from app.routers.calendar_events import router as calendar_router
from app.routers.pages import router as pages_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
# "title" ist bewusst NICHT enthalten -- der reduzierte Schlüssel existiert (fester Platzhalter
# "Belegt"), nur der ECHTE Titel darf nicht durchsickern (separat per reduced["title"]=="Belegt"
# geprüft).
FORBIDDEN_KEYS = {"location", "notes", "project_id", "project_name", "quote_id", "quote_number"}


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def threaded_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _make_user(db, *, role="buero_auftrag", username="user"):
    user = AppUser(username=username, display_name=username.capitalize(), role=role, active=True, password_hash=hash_password("Passwort123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _client_for_real_user(db, *routers, user):
    """Wie router_test_client() (tests/conftest.py), aber mit einem ECHTEN, bereits committeten
    AppUser statt eines nur transienten Fake-Objekts -- die shared Fixture kann kein `.id`
    liefern (das Fake-Objekt wird nie zur db hinzugefügt), das reicht für Rollen-Gates, aber
    nicht für die hier geforderte Eigentümerschafts-/Privatsphäre-Prüfung, die request.state.
    erp_user.id braucht. Bewusst lokal in dieser Testdatei, keine Änderung an der shared
    Fixture."""
    app = FastAPI()
    for router in routers:
        app.include_router(router)

    @app.middleware("http")
    async def _fake_identity(request, call_next):
        request.state.erp_user = user
        request.state.otp_ok = True
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _seed_project(db):
    customer = Customer(name="Erika Musterfrau", last_name="Musterfrau")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    project = Project(
        project_number="P-TEST-0001", customer_id=customer.id, name="Testprojekt",
        pipeline_column_id=default_pipeline_column_id(db),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    quote = Quote(quote_number="A-TEST-0001", project_id=project.id, title="Testangebot")
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return project, quote


def _base_event_kwargs(**overrides):
    start = datetime(2026, 5, 4, 9, 0)
    end = datetime(2026, 5, 4, 10, 0)
    base = dict(
        title="Besichtigung", start_at=start, end_at=end, all_day=False, location="Musterstraße 1",
        notes="Interner Vermerk", project_id=None, quote_id=None, is_private=False,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Reine Geschäftslogik (app/calendar_events.py)
# ---------------------------------------------------------------------------


def test_create_event_basic_and_owner_name_resolved():
    db = db_session()
    owner = _make_user(db, username="tobias")
    data = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())
    assert data["title"] == "Besichtigung"
    assert data["owner_user_id"] == owner.id
    # Ohne Employee-Verknüpfung fällt resolve_account_display() auf den Benutzernamen zurück,
    # unverändert (keine Kapitalisierung) -- Muster app/auth.py::resolve_account_display().
    assert data["owner_name"] == "tobias"
    assert data["external_source"] == "erp"
    assert data["outlook_event_id"] is None


def test_create_event_rejects_project_and_quote_together():
    db = db_session()
    owner = _make_user(db)
    project, quote = _seed_project(db)
    with pytest.raises(ValueError):
        create_event(db, owner_user_id=owner.id, **_base_event_kwargs(project_id=project.id, quote_id=quote.id))


def test_create_event_rejects_end_before_start():
    db = db_session()
    owner = _make_user(db)
    with pytest.raises(ValueError):
        create_event(db, owner_user_id=owner.id, **_base_event_kwargs(
            start_at=datetime(2026, 5, 4, 10, 0), end_at=datetime(2026, 5, 4, 9, 0),
        ))


def test_create_event_rejects_unknown_owner_project_and_quote():
    db = db_session()
    owner = _make_user(db)
    with pytest.raises(ValueError):
        create_event(db, owner_user_id=999999, **_base_event_kwargs())
    with pytest.raises(ValueError):
        create_event(db, owner_user_id=owner.id, **_base_event_kwargs(project_id=999999))
    with pytest.raises(ValueError):
        create_event(db, owner_user_id=owner.id, **_base_event_kwargs(quote_id=999999))


def test_update_event_partial_update_does_not_touch_unset_fields():
    db = db_session()
    owner = _make_user(db)
    created = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())
    updated = update_event(db, created["id"], {"title": "Aufmaß"})
    assert updated["title"] == "Aufmaß"
    # location/notes waren nicht Teil des Teil-Updates -- müssen unverändert bleiben (dieselbe
    # Gefahrenklasse wie bei upsert_roof_layer() vor 1.2.19).
    assert updated["location"] == "Musterstraße 1"
    assert updated["notes"] == "Interner Vermerk"


def test_update_event_rejects_end_before_start_after_merge_with_existing():
    db = db_session()
    owner = _make_user(db)
    created = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())
    with pytest.raises(ValueError):
        update_event(db, created["id"], {"end_at": created["start_at"] - timedelta(hours=1)})


def test_update_event_unknown_id_returns_none():
    db = db_session()
    assert update_event(db, 999999, {"title": "x"}) is None


def test_delete_event_returns_false_for_unknown_id():
    db = db_session()
    assert delete_event(db, 999999) is False


def test_get_event_roundtrip():
    db = db_session()
    owner = _make_user(db)
    created = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())
    assert get_event(db, created["id"])["title"] == "Besichtigung"
    delete_event(db, created["id"])
    assert get_event(db, created["id"]) is None


def test_privacy_redaction_own_vs_colleague():
    db = db_session()
    owner = _make_user(db, username="owner")
    colleague = _make_user(db, username="colleague")
    private = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(is_private=True))
    public = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(title="Teamrunde", is_private=False))

    # Der Besitzer selbst sieht seinen eigenen privaten Termin immer voll.
    assert is_redacted_for_viewer(private, owner.id) is False
    # Ein Kollege sieht denselben Termin nur reduziert.
    assert is_redacted_for_viewer(private, colleague.id) is True
    reduced = redact_for_busy(private)
    assert reduced["title"] == "Belegt"
    assert set(reduced.keys()) & FORBIDDEN_KEYS == set()
    assert reduced["owner_user_id"] == owner.id
    assert reduced["start_at"] == private["start_at"]

    # Ein NICHT privater Termin eines Kollegen bleibt für jeden voll sichtbar.
    assert is_redacted_for_viewer(public, colleague.id) is False


def test_list_events_filters_by_overlapping_range():
    db = db_session()
    owner = _make_user(db)
    inside = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(
        title="innerhalb", start_at=datetime(2026, 5, 10, 8, 0), end_at=datetime(2026, 5, 10, 9, 0),
    ))
    spanning = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(
        title="mehrtaegig", start_at=datetime(2026, 5, 9, 8, 0), end_at=datetime(2026, 5, 11, 9, 0),
    ))
    outside = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(
        title="ausserhalb", start_at=datetime(2026, 6, 1, 8, 0), end_at=datetime(2026, 6, 1, 9, 0),
    ))
    rows = list_events(db, start=datetime(2026, 5, 10, 0, 0), end=datetime(2026, 5, 10, 23, 59))
    ids = {r["id"] for r in rows}
    assert inside["id"] in ids
    assert spanning["id"] in ids
    assert outside["id"] not in ids


def test_list_events_filters_by_project_and_quote():
    db = db_session()
    owner = _make_user(db)
    project, quote = _seed_project(db)
    on_project = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(project_id=project.id))
    on_quote = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(quote_id=quote.id))
    unrelated = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())

    project_rows = {r["id"] for r in list_events(db, project_id=project.id)}
    assert project_rows == {on_project["id"]}
    quote_rows = {r["id"] for r in list_events(db, quote_id=quote.id)}
    assert quote_rows == {on_quote["id"]}
    assert unrelated["id"] not in project_rows and unrelated["id"] not in quote_rows


def test_list_owners_only_returns_requested_roles():
    db = db_session()
    _make_user(db, role="field", username="monteur")
    auftrag = _make_user(db, role="buero_auftrag", username="bauleiter")
    admin = _make_user(db, role="admin", username="admin")
    inactive = _make_user(db, role="buero_finanzen", username="ausgeschieden")
    inactive.active = False
    db.commit()

    rows = list_owners(db, role_keys=(ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN))
    ids = {r["id"] for r in rows}
    assert auftrag.id in ids
    assert admin.id in ids
    assert inactive.id not in ids
    assert not any("monteur" in r["display_name"].lower() for r in rows)


def test_unlink_calendar_events_for_project_nulls_project_and_quote_ids():
    db = db_session()
    owner = _make_user(db)
    project, quote = _seed_project(db)
    on_project = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(project_id=project.id))
    on_quote = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(quote_id=quote.id))

    unlink_calendar_events_for_project(db, project.id)
    db.commit()

    assert get_event(db, on_project["id"])["project_id"] is None
    assert get_event(db, on_quote["id"])["quote_id"] is None


def test_delete_project_with_linked_calendar_event_keeps_event_but_unlinks_it():
    db = db_session()
    owner = _make_user(db)
    project, quote = _seed_project(db)
    linked = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(quote_id=quote.id))

    project_obj = db.get(Project, project.id)
    delete_project(db, project_obj)

    survivor = get_event(db, linked["id"])
    assert survivor is not None, "Ein Termin darf beim Löschen des Projekts nicht mitgelöscht werden."
    assert survivor["project_id"] is None
    assert survivor["quote_id"] is None
    assert db.get(Project, project.id) is None


# ---------------------------------------------------------------------------
# Router: Rollen-/Modul-Gate (bewusst OHNE Eigentümerschafts-Prüfung beim Schreiben)
# ---------------------------------------------------------------------------


def test_field_role_is_rejected_on_every_calendar_endpoint(threaded_db_session, router_test_client):
    db = threaded_db_session
    owner = _make_user(db, username="owner2")
    event = create_event(db, owner_user_id=owner.id, **_base_event_kwargs())
    client = router_test_client(db, calendar_router, role="field")
    assert client.get("/api/calendar-events").status_code == 403
    assert client.get("/api/calendar-events/owners").status_code == 403
    assert client.get(f"/api/calendar-events/{event['id']}").status_code == 403
    assert client.get("/api/calendar-events/99999").status_code == 403
    assert client.post("/api/calendar-events", json={**_json_payload(_base_event_kwargs()), "owner_user_id": owner.id}).status_code == 403
    assert client.put(f"/api/calendar-events/{event['id']}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/api/calendar-events/{event['id']}").status_code == 403


def _json_payload(kwargs):
    return {
        "title": kwargs["title"], "start_at": kwargs["start_at"].isoformat(), "end_at": kwargs["end_at"].isoformat(),
        "all_day": kwargs["all_day"], "location": kwargs["location"], "notes": kwargs["notes"],
        "project_id": kwargs["project_id"], "quote_id": kwargs["quote_id"], "is_private": kwargs["is_private"],
    }


def test_office_roles_can_use_the_full_crud_cycle(threaded_db_session, router_test_client):
    db = threaded_db_session
    owner = _make_user(db, username="owner3")
    for role in ("buero_auftrag", "buero_finanzen", "admin"):
        client = router_test_client(db, calendar_router, role=role)
        payload = {**_json_payload(_base_event_kwargs(title=f"Termin-{role}")), "owner_user_id": owner.id}
        created = client.post("/api/calendar-events", json=payload)
        assert created.status_code == 200, created.text
        event_id = created.json()["id"]
        assert client.get(f"/api/calendar-events/{event_id}").status_code == 200
        updated = client.put(f"/api/calendar-events/{event_id}", json={"title": "geändert"})
        assert updated.status_code == 200 and updated.json()["title"] == "geändert"
        assert client.delete(f"/api/calendar-events/{event_id}").status_code == 200
        assert client.get(f"/api/calendar-events/{event_id}").status_code == 404


def test_owners_endpoint_returns_office_roles_only(threaded_db_session, router_test_client):
    db = threaded_db_session
    _make_user(db, role="buero_auftrag", username="office1")
    _make_user(db, role="field", username="field1")
    client = router_test_client(db, calendar_router, role="admin")
    resp = client.get("/api/calendar-events/owners")
    assert resp.status_code == 200
    names = [o["display_name"].lower() for o in resp.json()]
    assert any("office1" in n for n in names)
    assert not any("field1" in n for n in names)


def test_module_disabled_blocks_calendar_for_every_role_including_admin(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="kalender", enabled=False))
    db.commit()
    for role in ALL_ROLES:
        client = router_test_client(db, calendar_router, role=role)
        assert client.get("/api/calendar-events").status_code == 403, role
        assert client.get("/api/calendar-events/owners").status_code == 403, role


def test_calendar_page_route_rejects_field(threaded_db_session, router_test_client):
    db = threaded_db_session
    field_client = router_test_client(db, pages_router, role="field")
    assert field_client.get("/kalender").status_code == 403
    office_client = router_test_client(db, pages_router, role="buero_auftrag")
    assert office_client.get("/kalender").status_code == 200


# ---------------------------------------------------------------------------
# Router: Privatsphäre-Redaktion mit einer ECHTEN, id-tragenden Identität
# ---------------------------------------------------------------------------


def test_router_redacts_a_colleagues_private_event_but_not_the_owners_own():
    db = threaded_db_session()
    owner = _make_user(db, username="ownerreal")
    colleague = _make_user(db, role="buero_finanzen", username="colleaguereal")
    private = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(title="Vertrauliches Gespräch", is_private=True))

    owner_client = _client_for_real_user(db, calendar_router, user=owner)
    resp_owner = owner_client.get(f"/api/calendar-events/{private['id']}")
    assert resp_owner.status_code == 200
    assert resp_owner.json()["title"] == "Vertrauliches Gespräch"
    assert resp_owner.json()["location"] == "Musterstraße 1"

    colleague_client = _client_for_real_user(db, calendar_router, user=colleague)
    resp_colleague = colleague_client.get(f"/api/calendar-events/{private['id']}")
    assert resp_colleague.status_code == 200
    body = resp_colleague.json()
    assert body["title"] == "Belegt"
    assert set(body.keys()) & FORBIDDEN_KEYS == set()

    list_resp = colleague_client.get("/api/calendar-events", params={
        "start": "2026-05-01T00:00:00", "end": "2026-05-31T23:59:59",
    })
    assert list_resp.status_code == 200
    assert all(set(row.keys()) & FORBIDDEN_KEYS == set() for row in list_resp.json() if row["title"] == "Belegt")


def test_router_never_redacts_a_non_private_colleague_event():
    db = threaded_db_session()
    owner = _make_user(db, username="ownerpublic")
    colleague = _make_user(db, role="admin", username="colleaguepublic")
    public = create_event(db, owner_user_id=owner.id, **_base_event_kwargs(title="Teammeeting", is_private=False))

    colleague_client = _client_for_real_user(db, calendar_router, user=colleague)
    resp = colleague_client.get(f"/api/calendar-events/{public['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Teammeeting"
    assert resp.json()["location"] == "Musterstraße 1"
