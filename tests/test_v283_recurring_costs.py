"""Version 1.5.0 -- Betriebskosten-Übersicht, Schicht 1 (siehe CLAUDE.md
"Betriebskosten-Übersicht" für die volle Herleitung). Deckt ab: normalize_to_annual() für alle
Rhythmen inkl. "einmalig" (Punkt 4 der Anfrage -- das Modell nimmt einmalige Kosten bereits auf,
ohne Umbau), die Kündigungsfrist-Ableitung, den vollständigen CRUD-Zyklus samt Dokumentenablage,
die Doppelzählungs-Exklusion in overview_summary() samt Transparenz-Hinweisen
(has_linked_recurring_cost/asset_quick_cost_hint), die allgemeine Task.min_visible_role-
Erweiterung (Sichtbarkeit UND das claim()-Rollen-Gate), die On-Demand-Erinnerung mit
min_visible_role=ROLE_OFFICE_FINANZEN (nicht unassigned -- eine Kündigungsfrist geht nur
Finanzen/Admin etwas an), und den abschließend verlangten Angriffstest: buero_auftrag und field
kommen über KEINEN Weg an die Betriebskosten -- Liste, Endpunkte, Summen, Dokumente, die
finanz-adressierten Aufgaben. Rekursiver Schlüssel-Scan, je ein Testkonto pro Rolle."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AppUser, EnabledModule, OperationalAsset
from app.operational_assets import create_asset
from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.recurring_costs import (
    BILLING_INTERVALS, cancellation_deadline, check_due_cancellations_and_create_reminders,
    create_cost, create_cost_document, delete_cost, delete_cost_document, get_cost,
    is_cancellation_due, is_cancellation_overdue, list_costs, normalize_to_annual, overview_summary,
    update_cost,
)
from app.routers.recurring_costs import router as recurring_costs_router
from app.routers.tasks import router as tasks_router
from app.tasks import claim_task, create_task, list_tasks_for_user

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
FORBIDDEN_KEYS = {"label", "net_amount", "billing_interval", "annual_amount", "vendor"}


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _recursive_keys(value, keys=None):
    if keys is None:
        keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            _recursive_keys(v, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _recursive_keys(item, keys)
    elif isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                parsed = json.loads(s)
            except (TypeError, ValueError):
                return keys
            _recursive_keys(parsed, keys)
    return keys


def _base_payload(**overrides):
    payload = {
        "label": "Bürolokal Übach-Palenberg", "category": "Miete", "net_amount": "1200.00",
        "billing_interval": "monatlich", "vendor": None, "contract_end_date": None,
        "notice_period_months": None, "asset_id": None, "active": True, "notes": None,
    }
    payload.update(overrides)
    return payload


# --- normalize_to_annual() für alle Rhythmen ---

def test_normalize_to_annual_covers_every_billing_interval():
    assert normalize_to_annual(Decimal("100"), "monatlich") == Decimal("1200.00")
    assert normalize_to_annual(Decimal("100"), "vierteljaehrlich") == Decimal("400.00")
    assert normalize_to_annual(Decimal("100"), "halbjaehrlich") == Decimal("200.00")
    assert normalize_to_annual(Decimal("100"), "jaehrlich") == Decimal("100.00")


def test_normalize_to_annual_einmalig_is_zero_but_model_accepts_the_value():
    """Punkt 4 der Anfrage: 'einmalig' ist bereits ein gültiger Rhythmus-Wert -- der
    normierte Jahresbetrag ist 0 (kein laufender Beitrag zur Summe), der Posten selbst bleibt
    aber speicherbar und sichtbar, ohne Modellumbau."""
    assert "einmalig" in BILLING_INTERVALS
    assert normalize_to_annual(Decimal("500"), "einmalig") == Decimal("0.00")
    db = db_session()
    cost = create_cost(db, _base_payload(label="Einmalige Anschlusskosten", net_amount="500", billing_interval="einmalig"))
    assert cost["annual_amount"] == Decimal("0.00")
    assert cost["billing_interval"] == "einmalig"
    # Bleibt in der normalen Liste sichtbar -- kein Sonderfall, der ihn ausblendet.
    assert cost["id"] in [c["id"] for c in list_costs(db)]


# --- Kündigungsfrist-Ableitung ---

def test_cancellation_deadline_is_contract_end_minus_notice_period():
    assert cancellation_deadline(date(2026, 12, 31), 3) == date(2026, 9, 30)


def test_cancellation_deadline_none_without_both_fields():
    assert cancellation_deadline(None, 3) is None
    assert cancellation_deadline(date(2026, 12, 31), None) is None


def test_is_cancellation_due_and_overdue():
    today = date(2026, 9, 18)
    deadline = date(2026, 9, 30)
    assert is_cancellation_due(deadline, 30, today=today) is True
    assert is_cancellation_due(deadline, 5, today=today) is False
    assert is_cancellation_overdue(deadline, today=today) is False
    assert is_cancellation_overdue(date(2026, 9, 1), today=today) is True


# --- CRUD ---

def test_create_get_update_delete_cost():
    db = db_session()
    created = create_cost(db, _base_payload())
    assert created["label"] == "Bürolokal Übach-Palenberg"
    assert created["annual_amount"] == Decimal("14400.00")

    fetched = get_cost(db, created["id"])
    assert fetched["id"] == created["id"]

    updated = update_cost(db, created["id"], _base_payload(label="Bürolokal (neu)", net_amount="1300.00"))
    assert updated["label"] == "Bürolokal (neu)"
    assert updated["annual_amount"] == Decimal("15600.00")

    assert delete_cost(db, created["id"]) is True
    assert get_cost(db, created["id"]) is None
    assert delete_cost(db, 99999) is False


def test_create_cost_rejects_unknown_billing_interval():
    db = db_session()
    with pytest.raises(ValueError):
        create_cost(db, _base_payload(billing_interval="woechentlich"))


def test_create_cost_rejects_unknown_asset_id():
    db = db_session()
    with pytest.raises(ValueError):
        create_cost(db, _base_payload(asset_id=99999))


# --- Doppelzählungs-Exklusion (das Kernstück der ersten Nutzerentscheidung) ---

def test_overview_summary_excludes_asset_quick_cost_when_a_recurring_cost_is_linked():
    db = db_session()
    asset = create_asset(db, {"name": "Transporter", "recurring_cost_per_month": "300.00"})

    # Ohne verknüpften Kostenposten fließt die monatliche Notiz der Ressource ein.
    summary = overview_summary(db)
    assert summary["annual_total"] == Decimal("3600.00")
    assert summary["asset_quick_cost_count"] == 1
    assert summary["cost_count"] == 0

    # Ein verknüpfter Kostenposten ERSETZT die Notiz, statt sie zu ergänzen -- keine Doppelzählung.
    cost = create_cost(db, _base_payload(
        label="Leasingrate Transporter", category="Leasing", net_amount="450.00",
        billing_interval="monatlich", asset_id=asset["id"],
    ))
    summary = overview_summary(db)
    assert summary["annual_total"] == Decimal("5400.00")  # NUR die Leasingrate, nicht 3600+5400
    assert summary["asset_quick_cost_count"] == 0
    assert summary["cost_count"] == 1

    # Transparenz-Hinweise auf beiden Seiten der Frage.
    fetched_cost = get_cost(db, cost["id"])
    assert fetched_cost["asset_quick_cost_hint"] is not None
    assert "Transporter" in fetched_cost["asset_quick_cost_hint"]

    from app.operational_assets import get_asset
    fetched_asset = get_asset(db, asset["id"])
    assert fetched_asset["has_linked_recurring_cost"] is True

    # Deaktiviert man den Kostenposten, greift die Ersetzung nicht mehr -- die Notiz zählt wieder.
    update_cost(db, cost["id"], _base_payload(
        label="Leasingrate Transporter", net_amount="450.00", billing_interval="monatlich",
        asset_id=asset["id"], active=False,
    ))
    summary = overview_summary(db)
    assert summary["annual_total"] == Decimal("3600.00")
    assert summary["asset_quick_cost_count"] == 1
    fetched_asset = get_asset(db, asset["id"])
    assert fetched_asset["has_linked_recurring_cost"] is False


def test_overview_summary_sums_multiple_active_costs():
    db = db_session()
    create_cost(db, _base_payload(label="Miete", net_amount="1000", billing_interval="monatlich"))
    create_cost(db, _base_payload(label="Versicherung", net_amount="600", billing_interval="jaehrlich"))
    summary = overview_summary(db)
    assert summary["annual_total"] == Decimal("12600.00")
    assert summary["cost_count"] == 2


def test_overview_summary_highlights_due_and_overdue_cancellations():
    db = db_session()
    today = date.today()
    create_cost(db, _base_payload(
        label="Läuft bald ab", contract_end_date=today + timedelta(days=40), notice_period_months=1,
    ))  # Kündigungsfrist in 10 Tagen -- innerhalb der Standard-Vorlaufzeit (30 Tage)
    create_cost(db, _base_payload(
        label="Bereits überfällig", contract_end_date=today - timedelta(days=10), notice_period_months=1,
    ))  # Kündigungsfrist längst verstrichen
    create_cost(db, _base_payload(label="Läuft noch lange", contract_end_date=today + timedelta(days=400), notice_period_months=1))
    summary = overview_summary(db)
    assert [c["label"] for c in summary["cancellations_due"]] == ["Läuft bald ab"]
    assert [c["label"] for c in summary["cancellations_overdue"]] == ["Bereits überfällig"]


# --- Dokumentenablage ---

def test_document_upload_and_delete_removes_file_from_disk(tmp_path, monkeypatch):
    from app import recurring_cost_documents as docs_module

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    cost = create_cost(db, _base_payload())
    stored = docs_module.save_document("mietvertrag.pdf", b"dummy-inhalt")
    assert docs_module.document_path(stored).is_file()

    document = create_cost_document(
        db, cost["id"], document_type="Vertrag", notes=None,
        stored_filename=stored, original_filename="mietvertrag.pdf",
    )
    assert document["document_type"] == "Vertrag"
    fetched = get_cost(db, cost["id"])
    assert len(fetched["documents"]) == 1

    assert delete_cost_document(db, document["id"]) is True
    assert not docs_module.document_path(stored).is_file()
    assert delete_cost_document(db, document["id"]) is False


def test_deleting_cost_removes_its_document_files(tmp_path, monkeypatch):
    """Cascade: löscht man den Kostenposten selbst, muss auch die zugehörige Datei
    verschwinden -- Muster app/operational_assets.py::delete_asset()."""
    from app import recurring_cost_documents as docs_module

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    cost = create_cost(db, _base_payload())
    stored = docs_module.save_document("kuendigung.pdf", b"dummy")
    create_cost_document(db, cost["id"], document_type="Kündigungsschreiben", notes=None,
                          stored_filename=stored, original_filename="kuendigung.pdf")
    assert delete_cost(db, cost["id"]) is True
    assert not docs_module.document_path(stored).is_file()


# --- Task.min_visible_role: die allgemeine Erweiterung (nicht nur für Betriebskosten) ---

def test_create_task_stores_min_visible_role():
    db = db_session()
    task = create_task(db, title="Kündigungsfrist beachten", min_visible_role=ROLE_OFFICE_FINANZEN)
    assert task["min_visible_role"] == ROLE_OFFICE_FINANZEN


def test_create_task_rejects_unknown_role():
    db = db_session()
    with pytest.raises(ValueError):
        create_task(db, title="X", min_visible_role="buchhaltung")


def test_finance_addressed_unassigned_task_visible_only_to_finanzen_and_admin():
    """Kernanforderung: 'ohne Angabe geht sie an alle Bürorollen; mit buero_finanzen nur an
    Finanzen und Admin.' -- geprüft über die EINE Sichtbarkeitsfunktion, list_tasks_for_user()."""
    db = db_session()
    create_task(db, title="Allgemeine Büroaufgabe")  # kein min_visible_role
    create_task(db, title="Kündigungsfrist beachten", min_visible_role=ROLE_OFFICE_FINANZEN)

    for role, expected_titles in (
        (ROLE_OFFICE_AUFTRAG, {"Allgemeine Büroaufgabe"}),
        (ROLE_OFFICE_FINANZEN, {"Allgemeine Büroaufgabe", "Kündigungsfrist beachten"}),
        (ROLE_ADMIN, {"Allgemeine Büroaufgabe", "Kündigungsfrist beachten"}),
    ):
        user = AppUser(username=f"{role}-x", display_name=role, role=role, active=True)
        rows = list_tasks_for_user(db, user, unassigned_only=True)
        assert {r["title"] for r in rows} == expected_titles, role

    # field sieht -- unverändert seit dem Rechtekonzept -- ohnehin gar keine Aufgabe.
    field_user = AppUser(username="field-x", display_name="field", role=ROLE_FIELD, active=True)
    assert list_tasks_for_user(db, field_user, unassigned_only=True) == []


def test_claim_task_rejects_role_below_min_visible_role():
    """buero_auftrag darf eine finanz-adressierte Aufgabe nicht übernehmen -- auch nicht mit
    korrekt verknüpfter employee_id -- claim_task() wirft dafür ein eigenes PermissionError,
    getrennt von den ValueError-Geschäftsregelfällen."""
    db = db_session()
    task = create_task(db, title="Kündigungsfrist beachten", min_visible_role=ROLE_OFFICE_FINANZEN)
    auftrag_user = AppUser(username="a", display_name="a", role=ROLE_OFFICE_AUFTRAG, active=True, employee_id=1)
    with pytest.raises(PermissionError):
        claim_task(db, task["id"], auftrag_user)

    finanzen_user = AppUser(username="f", display_name="f", role=ROLE_OFFICE_FINANZEN, active=True, employee_id=1)
    claimed = claim_task(db, task["id"], finanzen_user)
    assert claimed["assigned_employee_id"] == 1


def test_claim_task_without_min_visible_role_works_for_any_office_role():
    db = db_session()
    task = create_task(db, title="Allgemeine Büroaufgabe")
    auftrag_user = AppUser(username="a", display_name="a", role=ROLE_OFFICE_AUFTRAG, active=True, employee_id=1)
    claimed = claim_task(db, task["id"], auftrag_user)
    assert claimed["assigned_employee_id"] == 1


# --- On-Demand-Erinnerung: min_visible_role statt unassigned ---

def test_check_due_cancellations_creates_finanzen_addressed_task_idempotently():
    db = db_session()
    today = date.today()
    cost = create_cost(db, _base_payload(
        label="Bürolokal", contract_end_date=today + timedelta(days=20), notice_period_months=1,
    ))
    reminded = check_due_cancellations_and_create_reminders(db)
    assert reminded == [cost["id"]]

    finanzen_user = AppUser(username="f", display_name="f", role=ROLE_OFFICE_FINANZEN, active=True)
    auftrag_user = AppUser(username="a", display_name="a", role=ROLE_OFFICE_AUFTRAG, active=True)
    finanzen_titles = {t["title"] for t in list_tasks_for_user(db, finanzen_user, unassigned_only=True)}
    auftrag_titles = {t["title"] for t in list_tasks_for_user(db, auftrag_user, unassigned_only=True)}
    assert any("Bürolokal" in t for t in finanzen_titles)
    assert not any("Bürolokal" in t for t in auftrag_titles)

    # Idempotent -- ein zweiter Aufruf ohne Änderung erinnert nicht erneut.
    assert check_due_cancellations_and_create_reminders(db) == []


def test_check_due_cancellations_noop_when_task_module_disabled():
    db = db_session()
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    today = date.today()
    create_cost(db, _base_payload(contract_end_date=today + timedelta(days=5), notice_period_months=1))
    assert check_due_cancellations_and_create_reminders(db) == []


# ---------------------------------------------------------------------------
# Angriffstest: buero_auftrag und field kommen über KEINEN Weg an die Betriebskosten --
# Liste, Endpunkte, Summen, Dokumente, die finanz-adressierten Aufgaben. Null durchgelassen.
# ---------------------------------------------------------------------------

def _seed_cost_and_finance_task(threaded_db_session, router_test_client):
    """Legt über einen echten buero_finanzen-Router-Aufruf einen Kostenposten samt fälliger
    Kündigungsfrist an und löst die Erinnerung aus -- Testgrundlage für den Angriffstest."""
    db = threaded_db_session
    client = router_test_client(db, recurring_costs_router, role="buero_finanzen")
    resp = client.post("/api/recurring-costs", json=_base_payload(
        label="Angriffstest-Kostenposten", contract_end_date=str(date.today() + timedelta(days=10)),
        notice_period_months=1,
    ))
    assert resp.status_code == 200, resp.text
    cost_id = resp.json()["id"]
    check_due_cancellations_and_create_reminders(db)
    return cost_id


def test_recurring_costs_list_and_detail_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    cost_id = _seed_cost_and_finance_task(threaded_db_session, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, recurring_costs_router, role=role)
        list_resp = client.get("/api/recurring-costs")
        detail_resp = client.get(f"/api/recurring-costs/{cost_id}")
        if role in ("buero_finanzen", "admin"):
            assert list_resp.status_code == 200, (role, list_resp.text)
            assert detail_resp.status_code == 200, (role, detail_resp.text)
            assert _recursive_keys(list_resp.json()) & FORBIDDEN_KEYS
        else:
            assert list_resp.status_code == 403, (role, list_resp.text)
            assert detail_resp.status_code == 403, (role, detail_resp.text)
            assert not (_recursive_keys(list_resp.json()) & FORBIDDEN_KEYS)
            assert not (_recursive_keys(detail_resp.json()) & FORBIDDEN_KEYS)


def test_recurring_costs_overview_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_cost_and_finance_task(threaded_db_session, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, recurring_costs_router, role=role)
        resp = client.get("/api/recurring-costs/overview")
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert resp.status_code == expected, (role, resp.text)
        if expected == 403:
            assert not (_recursive_keys(resp.json()) & {"monthly_total", "annual_total"})


def test_recurring_costs_write_and_settings_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, recurring_costs_router, role=role)
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert client.post("/api/recurring-costs", json=_base_payload(label=f"neu-{role}")).status_code == expected, role
        assert client.get("/api/recurring-cost-settings").status_code == expected, role
        assert client.put("/api/recurring-cost-settings", json={"reminder_lead_days": 14}).status_code == expected, role
        assert client.post("/api/recurring-costs/check-due").status_code == expected, role


def test_recurring_cost_documents_never_reachable_for_buero_auftrag_or_field_even_with_guessed_id(
    threaded_db_session, router_test_client, tmp_path, monkeypatch,
):
    from app import recurring_cost_documents as docs_module
    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)

    db = threaded_db_session
    cost_id = _seed_cost_and_finance_task(threaded_db_session, router_test_client)
    finanzen_client = router_test_client(db, recurring_costs_router, role="buero_finanzen")
    upload_resp = finanzen_client.post(
        f"/api/recurring-costs/{cost_id}/documents",
        data={"document_type": "Vertrag"},
        files={"file": ("vertrag.pdf", b"dummy", "application/pdf")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    document_id = upload_resp.json()["id"]

    for role in ("buero_auftrag", "field"):
        client = router_test_client(db, recurring_costs_router, role=role)
        assert client.get(f"/api/recurring-cost-documents/{document_id}/file").status_code == 403, role
        assert client.delete(f"/api/recurring-cost-documents/{document_id}").status_code == 403, role
        # Auch mit einer geratenen, gar nicht existierenden ID -- dieselbe 403, bevor die
        # Geschäftslogik (die sonst ein 404 liefern würde) überhaupt läuft.
        assert client.get("/api/recurring-cost-documents/99999/file").status_code == 403, role
        assert client.post(
            f"/api/recurring-costs/{cost_id}/documents", data={"document_type": "Vertrag"},
            files={"file": ("x.pdf", b"x", "application/pdf")},
        ).status_code == 403, role


def test_finance_addressed_task_never_visible_or_claimable_for_buero_auftrag_or_field(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    _seed_cost_and_finance_task(threaded_db_session, router_test_client)

    finanzen_list = router_test_client(db, tasks_router, role="buero_finanzen").get("/api/tasks?unassigned_only=true")
    assert finanzen_list.status_code == 200
    finance_task_ids = [t["id"] for t in finanzen_list.json() if t.get("min_visible_role") == ROLE_OFFICE_FINANZEN]
    assert finance_task_ids, "Vorbedingung: die Erinnerungs-Aufgabe muss existieren"
    task_id = finance_task_ids[0]

    auftrag_client = router_test_client(db, tasks_router, role="buero_auftrag", employee_id=1)
    auftrag_list = auftrag_client.get("/api/tasks?unassigned_only=true")
    assert auftrag_list.status_code == 200
    assert task_id not in [t["id"] for t in auftrag_list.json()]
    assert not any("Kündigungsfrist" in (t.get("title") or "") for t in auftrag_list.json())

    # Auch ein direkter Übernahme-Versuch mit geratener/bekannter ID -- 403, kein 400/200.
    claim_resp = auftrag_client.post(f"/api/tasks/{task_id}/claim")
    assert claim_resp.status_code == 403, claim_resp.text

    field_client = router_test_client(db, tasks_router, role="field")
    field_list = field_client.get("/api/tasks?unassigned_only=true")
    assert field_list.status_code == 403
    field_claim = field_client.post(f"/api/tasks/{task_id}/claim")
    assert field_claim.status_code == 403

    finanzen_claim = router_test_client(db, tasks_router, role="buero_finanzen", employee_id=1).post(
        f"/api/tasks/{task_id}/claim"
    )
    assert finanzen_claim.status_code == 200, finanzen_claim.text


def test_module_disabled_blocks_every_role_including_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="betriebskosten", enabled=False))
    db.commit()
    for role in ALL_ROLES:
        client = router_test_client(db, recurring_costs_router, role=role)
        resp = client.get("/api/recurring-costs")
        assert resp.status_code == 403, (role, resp.text)
