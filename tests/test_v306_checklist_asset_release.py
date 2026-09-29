"""Version 1.8.2 -- "nicht einsatzbereit" verschwindet wieder: auf zwei Wegen (spätere Checkliste
mit "einsatzbereit: ja" ODER Büro markiert als repariert, mit Wer und Wann), eine erneute Meldung
"nein" gilt wieder. Dazu: Betriebsmittel mit Checklisten sind nicht löschbar.

Nutzt den Aufbau aus tests/test_v305_checklist_filling.py (Monteur C ist keinem Auftrag
zugeordnet -- Geräte-Checklisten gehen über die ID, siehe Betreiberentscheidung A)."""

import pytest

from app.models import ChecklistAssetRelease, EnabledModule
from app.operational_assets import delete_asset
from app.routers.checklists import router as checklists_router
from tests.test_v305_checklist_filling import _client, _fields, world  # noqa: F401 -- Fixture


def _report(world, client, value):
    """Abgeschlossene Geräte-Checkliste mit einsatzbereit = value."""
    c = client.post("/api/checklists", json={"template_id": world["asset_tpl"]["id"], "context_type": "betriebsmittel",
                                             "operational_asset_id": world["asset"].id}).json()
    assert client.put(f"/api/checklists/{c['id']}/answers/{_fields(c)['einsatzbereit']}",
                      json={"value": value}).status_code == 200
    assert client.post(f"/api/checklists/{c['id']}/complete").status_code == 200
    return c["id"]


def _state(client, world):
    return client.get(f"/api/checklists/asset-readiness/{world['asset'].id}").json()


def test_later_checklist_with_ja_clears_warning_and_new_nein_restores_it(world, router_test_client):
    """Weg 1: eine spätere Checkliste am selben Gerät mit "ja" hebt die Warnung auf -- sichtbar
    für Monteur und Büro gleichermaßen. Eine danach erneut gemeldete "nein" gilt wieder."""
    field = _client(world, router_test_client, "c")
    office = _client(world, router_test_client, "office")
    first = _report(world, field, "nein")
    assert _state(field, world)["ready"] is False and _state(office, world)["checklist_id"] == first

    second = _report(world, field, "ja")
    for client in (field, office):
        state = _state(client, world)
        assert state["ready"] is True and state["checklist_id"] == second and state["released_at"] is None

    third = _report(world, field, "nein")
    state = _state(office, world)
    assert state["ready"] is False and state["checklist_id"] == third


def test_office_marks_repaired_with_who_and_when(world, router_test_client):
    """Weg 2: das Büro markiert als repariert -- Wer (Anzeigename) und Wann stehen im Ergebnis
    und in der Datenbank, die Checkliste selbst bleibt unverändert (abgeschlossen, "nein")."""
    field = _client(world, router_test_client, "c")
    office = _client(world, router_test_client, "office")
    reported = _report(world, field, "nein")

    resp = office.post(f"/api/checklists/asset-readiness/{world['asset'].id}/repaired",
                       json={"note": "  Kabel getauscht  "})
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["ready"] is True and state["reported_ready"] is False and state["checklist_id"] == reported
    assert state["released_by_name"] == "Buero_auftrag" and state["release_note"] == "Kabel getauscht"
    assert state["released_at"]

    release = world["db"].query(ChecklistAssetRelease).one()
    assert release.checklist_id == reported and release.released_by_employee_id == world["emps"]["office"].id
    assert release.released_at is not None

    assert _state(field, world)["ready"] is True  # auch der Monteur sieht keine Warnung mehr
    checklist = office.get(f"/api/checklists/{reported}").json()
    assert checklist["status"] == "abgeschlossen"
    assert checklist["answers"][str(_fields(checklist)["einsatzbereit"])]["value"] == "nein"

    # Zweiter Klick: derselbe Stand, keine zweite Zeile.
    again = office.post(f"/api/checklists/asset-readiness/{world['asset'].id}/repaired", json={"note": "anders"})
    assert again.status_code == 200 and again.json()["release_note"] == "Kabel getauscht"
    assert world["db"].query(ChecklistAssetRelease).count() == 1

    # Eine neue Meldung "nein" nach der Reparatur gilt wieder -- die Freigabe hing an der alten.
    newer = _report(world, field, "nein")
    state = _state(office, world)
    assert state["ready"] is False and state["checklist_id"] == newer and state["released_at"] is None


def test_mark_repaired_requires_a_current_nein(world, router_test_client):
    office = _client(world, router_test_client, "office")
    url = f"/api/checklists/asset-readiness/{world['asset'].id}/repaired"
    assert office.post(url, json={}).status_code == 400  # noch gar keine Meldung
    _report(world, _client(world, router_test_client, "c"), "ja")
    assert office.post(url, json={}).status_code == 400  # einsatzbereit -- nichts aufzuheben
    assert office.post("/api/checklists/asset-readiness/9999/repaired", json={}).status_code == 404


def test_field_cannot_mark_repaired(world, router_test_client):
    """Monteure heben eine Meldung nur über eine neue Checkliste auf, nie per Knopf."""
    field = _client(world, router_test_client, "c")
    _report(world, field, "nein")
    resp = field.post(f"/api/checklists/asset-readiness/{world['asset'].id}/repaired", json={})
    assert resp.status_code == 403
    assert _state(field, world)["ready"] is False


@pytest.mark.parametrize("module_key", ["checklisten", "betriebsmittel"])
def test_mark_repaired_respects_disabled_modules(world, router_test_client, module_key):
    field = _client(world, router_test_client, "c")
    _report(world, field, "nein")
    world["db"].add(EnabledModule(module_key=module_key, enabled=False))
    world["db"].commit()
    admin = router_test_client(world["db"], checklists_router)
    assert admin.post(f"/api/checklists/asset-readiness/{world['asset'].id}/repaired", json={}).status_code == 403


def test_asset_with_checklists_cannot_be_deleted(world, router_test_client):
    _report(world, _client(world, router_test_client, "c"), "nein")
    with pytest.raises(ValueError, match="Checklisten"):
        delete_asset(world["db"], world["asset"].id)
