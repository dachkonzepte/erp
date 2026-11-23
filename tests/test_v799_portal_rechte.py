"""Version 1.11.0 (Stufe P1a, Kundenportal): Tabellen des Portals und die Rechte seines Datenbank-Benutzers.

    eingeordnet   jede Tabelle des Modells steht in app/portal/rechte.py (LESEN) oder in KEIN_ZUGRIFF -- eine neue Tabelle macht den Test rot
    verboten      Personal, Lohn, Zeiten, Konten, Sitzungen, Geheimnisse, Protokolle, Kundendaten und die Tabellen des Portals nie in LESEN; LESEN genau
                  die Firmendaten und die Revision (Bauplan P1, Nachtrag N1: alles an Link und Sitzung über Funktionen der Datenbank, ab 1.11.1)
    Spalten       jede Spalte aus LESEN gibt es im Modell
    Werte         die CHECK der Spalten = app/portal/werte.py = die Migration wörtlich
    Abschottung   app/portal importiert aus dem ERP nur die Positivliste (kein app.models, kein app.database)
    Modul         „Kundenportal“ ist ab Werk aus (ohne Zeile), lässt sich einschalten
    Adressimport  ein Zugang zum Portal ist eine Verwendung des Kunden -- Rückgängigmachen lehnt ab
    Skript        scripts/portal_rechte.py ohne DATABASE_URL oder ohne PostgreSQL: Rückgabe 2
    PostgreSQL    (Testrolle dkportal_test, Wegwerf-Schema) setzen und prüfen; unter SET ROLE nur die erlaubten Spalten, sonst keine Berechtigung (42501);
                  pruefen() meldet jede Abweichung; Migration auf einem Bestand (SQLite und PostgreSQL), Downgrade bricht mit Zugang ab
"""

import ast
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, create_engine, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.database import Base
from app.models import Customer, EnabledModule, ImportRun, PortalZugang
from app.modules import AB_WERK_AUS, OPTIONAL_MODULES, is_module_enabled, module_enabled_in, set_module_enabled
from app.portal import rechte, werte
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
TESTROLLE = "dkportal_test"
MIGRATION, VORHER = "4f8a2c6e1b97", "9a4c2e7b1d56"

# Jede Tabelle des Modells, auf die der Benutzer des Portals kein Recht hat. Eine neue Tabelle kommt hierher -- oder, nach Entscheidung des Betriebs, mit
# genau ihren Spalten nach app/portal/rechte.py::LESEN (nur, was öffentlich oder ohne Bezug zu Personen ist; Kundendaten nur über Funktionen).
KEIN_ZUGRIFF = frozenset({
    'accounts', 'ai_call_log', 'ai_settings', 'app_users', 'arbeitszeit_kalendertage', 'audit_logs', 'base_interest_rates', 'calculation_settings',
    'calendar_events', 'catalogs', 'checklist_answer_selections', 'checklist_answers', 'checklist_asset_releases', 'checklist_attachments',
    'checklist_follow_ups', 'checklist_rule_executions', 'checklist_template_field_options', 'checklist_template_fields', 'checklist_template_rules',
    'checklist_template_versions', 'checklist_templates', 'checklist_versions', 'checklists', 'contacts', 'contract_basis_clauses',
    'contract_template_sections', 'contract_templates', 'customer_documents', 'customer_extra_infos', 'customer_profiles', 'customers',
    'defect_events', 'defect_files', 'defects', 'dispatch_authorizations', 'dispatch_copies', 'dispatch_outcomes', 'document_categories',
    'document_email_templates', 'document_layout_backgrounds', 'document_layout_blocks', 'document_page_margins', 'dunning_legal_texts',
    'email_dispatches', 'employee_absence_requests', 'employee_absences', 'employee_compensation_settings', 'employee_cost_allocation_settings',
    'employee_functions', 'employee_payroll_settings', 'employee_planning_settings', 'employee_profiles', 'employee_role_settings',
    'employee_target_hours', 'employee_work_time_models', 'employees', 'enabled_modules', 'failed_login_attempts', 'findings', 'import_batches',
    'import_runs', 'imported_addresses', 'incoming_invoice_items', 'incoming_invoice_settings', 'incoming_invoices', 'inquiries', 'inspection_items',
    'inspection_template_items', 'inspection_templates', 'invoice_charges', 'invoice_deductions', 'invoice_default_starts', 'invoice_items',
    'invoices', 'kontaktvermerke', 'labor_rate_overhead_settings', 'labor_rate_settings', 'lohn_startwerte', 'lohnart_zuordnungen', 'lohndateien',
    'maintenance_contract_items', 'maintenance_contracts', 'maintenance_settings', 'maintenance_windows', 'material_calculation_overrides',
    'material_groups', 'materials', 'mobile_settings', 'notice_letters', 'notice_reservations', 'number_sequences', 'operational_asset_documents',
    'operational_asset_inspections', 'operational_asset_settings', 'operational_assets', 'operational_resources', 'order_acceptance_files',
    'order_acceptance_roof_areas', 'order_acceptances', 'order_contract_basis_changes', 'order_contract_signatures', 'order_contract_versions',
    'order_contracts', 'order_customer_changes', 'order_item_calculation_snapshots', 'order_item_material_snapshots', 'order_items',
    'order_revisions', 'order_sections', 'order_status_changes', 'order_warranty_changes', 'orders', 'outlook_calendar_sync_state',
    'outlook_delete_orders', 'outlook_series_occurrences', 'outlook_sync_settings', 'payment_allocations', 'payment_refund_sources', 'payment_terms',
    'payments', 'personalnummern_vergeben', 'planning_holidays', 'planning_region_settings', 'planning_school_holiday_sync',
    'planning_school_holidays', 'planning_settings', 'planning_slot_capacity', 'planning_slot_employees', 'planning_slot_resources',
    'planning_slots', 'portal_bremsen', 'portal_codes', 'portal_post', 'portal_sitzungen', 'portal_zugaenge', 'portal_zugriffe',
    'productive_hours_settings', 'project_documents', 'project_participants', 'project_pipeline_columns', 'project_profiles', 'projects',
    'properties', 'property_documents', 'quote_document_meta', 'quote_employee_assignments', 'quote_item_calculations', 'quote_item_layouts',
    'quote_item_material_calculations', 'quote_items', 'quote_sections', 'quotes', 'recurring_cost_documents', 'recurring_cost_settings',
    'recurring_costs', 'reminder_levels', 'reminders', 'roof_areas', 'roof_component_types', 'roof_components', 'roof_layer_types', 'roof_layers',
    'roof_type_inspection_template_defaults', 'sent_documents', 'service_calculations', 'service_materials', 'service_report_assets',
    'service_report_materials', 'service_report_photos', 'service_report_roof_areas', 'service_reports', 'services', 'setting_option_groups',
    'setting_options', 'smtp_settings', 'suppliers', 'task_checklist_items', 'task_columns', 'task_settings', 'tasks', 'tax_keys', 'team_employees',
    'team_resources', 'teams', 'time_backoffice_advanced_settings', 'time_entries', 'time_entry_group_members', 'time_entry_groups',
    'time_tracking_settings', 'trusted_devices', 'two_factor_recovery_codes', 'urlaubsansprueche', 'user_dashboard_widgets', 'user_sessions',
    'webanfrage_dateien', 'webanfragen', 'webanfragen_abholung', 'work_preparation_delivery_notes', 'work_preparation_employees',
    'work_preparation_material_delivery_notes', 'work_preparation_material_suppliers', 'work_preparation_materials', 'work_preparation_tasks',
    'work_preparation_team_assignments', 'work_preparation_team_employees', 'work_preparation_team_resources', 'work_preparations',
    'work_time_break_rules', 'work_time_model_validities', 'work_time_models',
})

# Nie in LESEN, auch nicht mit einzelnen Spalten: Konten, Sitzungen, Geheimnisse, Personal, Lohn, Zeiten, Protokolle, Kundendaten, das Portal selbst
VERBOTEN = frozenset({
    'ai_call_log', 'ai_settings', 'app_users', 'audit_logs', 'email_dispatches', 'failed_login_attempts', 'sent_documents', 'smtp_settings',
    'trusted_devices', 'two_factor_recovery_codes', 'user_sessions', 'user_dashboard_widgets', 'outlook_calendar_sync_state', 'outlook_delete_orders',
    'outlook_series_occurrences', 'outlook_sync_settings',
    'employees', 'employee_absence_requests', 'employee_absences', 'employee_compensation_settings', 'employee_cost_allocation_settings',
    'employee_functions', 'employee_payroll_settings', 'employee_planning_settings', 'employee_profiles', 'employee_role_settings',
    'employee_target_hours', 'employee_work_time_models', 'arbeitszeit_kalendertage', 'lohn_startwerte', 'lohnart_zuordnungen', 'lohndateien',
    'personalnummern_vergeben', 'time_backoffice_advanced_settings', 'time_entries', 'time_entry_group_members', 'time_entry_groups',
    'time_tracking_settings', 'urlaubsansprueche', 'work_time_break_rules', 'work_time_model_validities', 'work_time_models',
    'customers', 'customer_profiles', 'customer_extra_infos', 'customer_documents', 'contacts', 'properties', 'property_documents', 'inquiries',
    'webanfragen', 'webanfrage_dateien', 'kontaktvermerke', 'projects', 'project_documents', 'project_participants', 'quotes', 'quote_items',
    'orders', 'order_items', 'invoices', 'invoice_items', 'payments', 'payment_allocations', 'reminders', 'defects', 'defect_events', 'defect_files',
    'service_reports', 'service_report_photos', 'calendar_events', 'tasks',
    'portal_zugaenge', 'portal_sitzungen', 'portal_codes', 'portal_post', 'portal_zugriffe', 'portal_bremsen',
})
# LESEN genau so (Bauplan P1 mit Nachtrag N1) -- eine weitere Tabelle nur nach Entscheidung des Betriebs
LESEN_GENAU = {
    "general_settings": ("id", "company_name", "street", "postal_code", "city", "phone", "email", "website"),
    "alembic_version": ("version_num",),
}
# Was das Paket app/portal aus dem ERP importieren darf (der Dienst des Portals lädt weder Modelle noch die Datenbank des ERP)
PORTAL_IMPORTE_AUS_APP = {"app.portal", "app.berlin_time", "app.design_dateien"}


# --- Wächter ohne Datenbank ---------------------------------------------------------------------------------------------------------------------------

def test_jede_tabelle_ist_eingeordnet():
    tabellen = set(Base.metadata.tables)
    lesen = set(rechte.LESEN) - {"alembic_version"}  # alembic_version gehört nicht zum Modell
    neu = sorted(tabellen - lesen - KEIN_ZUGRIFF)
    assert neu == [], f"neue Tabellen -- in app/portal/rechte.py::LESEN oder KEIN_ZUGRIFF (tests/test_v799_portal_rechte.py) eintragen: {neu}"
    assert sorted(KEIN_ZUGRIFF - tabellen) == [], "KEIN_ZUGRIFF nennt Tabellen, die es nicht mehr gibt"
    assert lesen & KEIN_ZUGRIFF == set()


def test_verboten_nie_lesbar_und_lesen_genau():
    assert set(rechte.LESEN) & VERBOTEN == set()
    assert VERBOTEN <= KEIN_ZUGRIFF
    assert rechte.LESEN == LESEN_GENAU


def test_jede_spalte_aus_lesen_gibt_es():
    for tabelle, spalten in rechte.LESEN.items():
        if tabelle == "alembic_version":
            assert spalten == ("version_num",)
            continue
        vorhanden = set(Base.metadata.tables[tabelle].columns.keys())
        assert set(spalten) <= vorhanden, (tabelle, sorted(set(spalten) - vorhanden))


def test_namen_nur_klein_ohne_sonderzeichen():
    for gut in ("dkportal", "pgtest_portal_1a2b", "public"):
        assert rechte._name(gut) == gut
    for schlecht in ("", "Public", "x; DROP TABLE y", "a-b", "a b", "x" * 64):
        with pytest.raises(ValueError):
            rechte._name(schlecht)


def _check(tabelle: str, name: str) -> str:
    return next(c for c in Base.metadata.tables[tabelle].constraints if isinstance(c, CheckConstraint) and c.name == name).sqltext.text


def test_feste_werte_als_check_wie_in_der_migration():
    import importlib.util
    pfad = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_portal", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    erwartet = {
        ("portal_sitzungen", "ck_portal_sitzung_ende"): "beendet_grund IS NULL OR beendet_grund IN ("
                                                         + ", ".join(f"'{w}'" for w in werte.SITZUNG_ENDE) + ")",
        ("portal_post", "ck_portal_post_art"): "art IN (" + ", ".join(f"'{w}'" for w in werte.POST_ARTEN) + ")",
        ("portal_post", "ck_portal_post_status"): "status IN (" + ", ".join(f"'{w}'" for w in werte.POST_STATUS) + ")",
        ("portal_zugriffe", "ck_portal_zugriff_aktion"): "aktion IN (" + ", ".join(f"'{w}'" for w in werte.AKTIONEN) + ")",
        ("portal_zugriffe", "ck_portal_zugriff_ergebnis"): "ergebnis IN (" + ", ".join(f"'{w}'" for w in werte.ERGEBNISSE) + ")",
    }
    for (tabelle, name), sql in erwartet.items():
        assert _check(tabelle, name) == sql, name
        assert modul.CHECKS[name] == sql, f"Migration {name}"
    assert set(modul.CHECKS) == {n for _t, n in erwartet}


def test_portal_importiert_aus_dem_erp_nur_die_positivliste():
    paket = ROOT / "app" / "portal"
    fremd = []
    for datei in sorted(paket.glob("*.py")):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.ImportFrom):
                if knoten.level:  # relativ: aus dem Paket selbst (eine Ebene) ist erlaubt, alles darüber nicht
                    ziel = "app.portal" if knoten.level == 1 else "app"
                    ziel = f"{ziel}.{knoten.module}" if knoten.module else ziel
                else:
                    ziel = knoten.module or ""
                namen = [ziel]
            elif isinstance(knoten, ast.Import):
                namen = [a.name for a in knoten.names]
            else:
                continue
            for name in namen:
                if (name == "app" or name.startswith("app.")) and not any(name == e or name.startswith(e + ".") for e in PORTAL_IMPORTE_AUS_APP):
                    fremd.append(f"{datei.name}: {name}")
    assert fremd == []


def test_modul_kundenportal_ab_werk_aus(db_session):
    db = db_session
    assert "kundenportal" in OPTIONAL_MODULES and AB_WERK_AUS == {"kundenportal"}
    assert db.scalar(select(EnabledModule).where(EnabledModule.module_key == "kundenportal")) is None
    assert is_module_enabled(db, "kundenportal") is False
    assert module_enabled_in({}, "kundenportal") is False and module_enabled_in({}, "wartungen") is True
    set_module_enabled(db, "kundenportal", True)
    assert is_module_enabled(db, "kundenportal") is True
    set_module_enabled(db, "kundenportal", False)
    assert is_module_enabled(db, "kundenportal") is False


def test_kunde_hat_portal_ab_werk_aus(db_session):
    db = db_session
    k = Customer(name="Muster", last_name="Muster")
    db.add(k)
    db.commit()
    db.refresh(k)
    assert k.portal_aktiv is False
    assert db.execute(text("SELECT portal_aktiv FROM customers WHERE id = :i"), {"i": k.id}).scalar() in (0, False)


def test_adressimport_mit_portal_zugang_nicht_rueckgaengig(db_session):
    from app.address_import import _run_is_untouched, revert_import_run
    db = db_session
    lauf = ImportRun(source_filename="adressen.csv")
    db.add(lauf)
    db.flush()
    k = Customer(name="Import Muster", last_name="Muster", import_run_id=lauf.id)
    db.add(k)
    db.commit()
    assert _run_is_untouched(db, lauf) is True
    db.add(PortalZugang(customer_id=k.id, email="kunde@example.invalid", email_anzeige="k***@example.invalid"))
    db.commit()
    assert _run_is_untouched(db, lauf) is False
    with pytest.raises(ValueError, match="nicht rückgängig"):
        revert_import_run(db, lauf.id)
    assert db.get(Customer, k.id) is not None


def test_archiv_neuer_zugang_abgelehnt_sperren_geht(db_session):
    """Der Zugang zählt nicht zum Vorgang (KEIN_TEIL in test_v793): Sperren geht auch, wenn der Kunde im Archiv ist; ein NEUER Zugang an einem Kunden im
    Archiv ist ein neuer Verweis auf ihn und wird abgelehnt (409)."""
    from datetime import datetime as dt

    from app.archivschutz import ImArchiv
    db = db_session
    k, j = Customer(name="Alt", last_name="Alt"), Customer(name="Jung", last_name="Jung")
    db.add_all([k, j])
    db.flush()
    zugang = PortalZugang(customer_id=k.id, email="alt@example.invalid", email_anzeige="a***@example.invalid")
    db.add(zugang)
    db.commit()
    k.archiviert_am = j.archiviert_am = dt(2026, 11, 20, 10, 0)
    db.commit()
    zugang.gesperrt_am, zugang.gesperrt_grund = dt(2026, 11, 23, 10, 0), "Kunde im Archiv"
    db.commit()  # Sperren geht
    db.add(PortalZugang(customer_id=j.id, email="jung@example.invalid", email_anzeige="j***@example.invalid"))
    with pytest.raises(ImArchiv):
        db.commit()
    db.rollback()


def test_skript_ohne_datenbank_oder_ohne_postgresql(monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("portal_rechte_skript", ROOT / "scripts" / "portal_rechte.py")
    skript = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skript)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert skript.main(["--pruefen"]) == 2
    assert "DATABASE_URL fehlt" in capsys.readouterr().out
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    assert skript.main(["--setzen"]) == 2
    assert "nur unter PostgreSQL" in capsys.readouterr().out


# --- PostgreSQL mit der Testrolle ----------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def pg_portal():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_portal_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (einmalig als Superuser: CREATE ROLE {TESTROLLE} NOLOGIN NOINHERIT; "
                            f"GRANT {TESTROLLE} TO erp WITH INHERIT FALSE, SET TRUE)")
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            c.execute(text("INSERT INTO alembic_version VALUES ('4f8a2c6e1b97')"))
        yield engine, schema
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _setzen(engine, schema):
    with engine.begin() as c:
        return rechte.setzen(c, rolle=TESTROLLE, schema=schema)


def _pruefen(engine, schema):
    with engine.connect() as c:
        return rechte.pruefen(c, rolle=TESTROLLE, schema=schema)


def test_pg_setzen_und_pruefen_ohne_abweichung(pg_portal):
    engine, schema = pg_portal
    anweisungen = _setzen(engine, schema)
    assert f"GRANT SELECT (id, company_name, street, postal_code, city, phone, email, website) ON {schema}.general_settings TO {TESTROLLE}" in anweisungen
    assert f"REVOKE ALL ON FUNCTION {schema}.telefonbuch(t text) FROM PUBLIC" in anweisungen
    assert _pruefen(engine, schema) == []
    _setzen(engine, schema)  # zweimal hintereinander: dasselbe Ergebnis
    assert _pruefen(engine, schema) == []


def _als_rolle(engine, anweisung: str):
    """Führt die Anweisung als Testrolle aus: None bei Erfolg, sonst der SQLSTATE (42501 = keine Berechtigung; die Meldung ist je nach Sprache des
    Servers deutsch oder englisch)."""
    with engine.connect() as c:
        c.execute(text(f"SET ROLE {TESTROLLE}"))
        try:
            c.execute(text(anweisung)).fetchall() if anweisung.lstrip().upper().startswith("SELECT") else c.execute(text(anweisung))
            return None
        except ProgrammingError as exc:
            return exc.orig.sqlstate
        finally:
            c.rollback()
            c.execute(text("RESET ROLE"))
            c.rollback()


def test_pg_als_rolle_nur_die_erlaubten_spalten(pg_portal):
    engine, schema = pg_portal
    _setzen(engine, schema)
    assert _als_rolle(engine, "SELECT id, company_name, street, postal_code, city, phone, email, website FROM general_settings") is None
    assert _als_rolle(engine, "SELECT version_num FROM alembic_version") is None
    verweigert = "42501"  # insufficient_privilege
    assert _als_rolle(engine, "SELECT iban FROM general_settings") == verweigert
    assert _als_rolle(engine, "SELECT * FROM general_settings") == verweigert
    # jede Tabelle des Modells: SELECT * verweigert (general_settings nur einzelne Spalten)
    offen = [t for t in sorted(Base.metadata.tables) if _als_rolle(engine, f"SELECT * FROM {t} LIMIT 0") != verweigert]
    assert offen == []
    for anweisung in ("INSERT INTO portal_bremsen (schluessel, fenster_beginn) VALUES ('x', now())",
                      "UPDATE general_settings SET company_name = 'x'", "DELETE FROM alembic_version",
                      "INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab) VALUES (1, 'x', now(), now())",
                      "SELECT telefonbuch('Müller')", "SELECT nextval('portal_zugriffe_id_seq')", "CREATE TABLE eigen (i integer)"):
        assert _als_rolle(engine, anweisung) == verweigert, anweisung


def test_pg_pruefen_meldet_jede_abweichung(pg_portal):
    engine, schema = pg_portal
    _setzen(engine, schema)
    with engine.begin() as c:
        for a in (f"GRANT SELECT ON customers TO {TESTROLLE}", f"GRANT SELECT (iban) ON general_settings TO {TESTROLLE}",
                  f"REVOKE SELECT (phone) ON general_settings FROM {TESTROLLE}", "GRANT EXECUTE ON FUNCTION telefonbuch(text) TO PUBLIC",
                  f"GRANT UPDATE (company_name) ON general_settings TO {TESTROLLE}", f"GRANT USAGE ON SEQUENCE portal_post_id_seq TO {TESTROLLE}",
                  f"GRANT CREATE ON SCHEMA {schema} TO {TESTROLLE}", f"GRANT INSERT ON portal_zugriffe TO {TESTROLLE}"):
            c.execute(text(a))
    abw = _pruefen(engine, schema)
    for erwartet in ("Tabelle customers: SELECT auf die ganze Tabelle", "Spalte general_settings.iban: SELECT zu viel",
                     "Spalte general_settings.phone: SELECT fehlt", "Funktion telefonbuch(t text): für alle ausführbar (PUBLIC)",
                     "Spalte general_settings.company_name: UPDATE zu viel", "Sequenz portal_post_id_seq: USAGE",
                     f"Schema {schema}: darf Objekte anlegen (CREATE)", "Tabelle portal_zugriffe: INSERT auf die ganze Tabelle"):
        assert erwartet in abw, (erwartet, abw)
    _setzen(engine, schema)  # setzen räumt jede Abweichung ab
    assert _pruefen(engine, schema) == []


def test_pg_pruefen_rolle_und_benutzer_des_erp(pg_portal):
    engine, schema = pg_portal
    _setzen(engine, schema)
    with engine.connect() as c:
        assert rechte.pruefen(c, rolle="gibt_es_nicht", schema=schema) == ["Rolle gibt_es_nicht fehlt"]
        erp = c.execute(text("SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    assert tuple(erp) == (False, False, False)  # der Benutzer des ERP der Tests ist kein Superuser -- sonst meldete pruefen() es
    with engine.begin() as c:
        with pytest.raises(ValueError, match="Rolle gibt_es_nicht fehlt"):
            rechte.setzen(c, rolle="gibt_es_nicht", schema=schema)


def test_pg_setzen_bricht_ab_wenn_eine_tabelle_fehlt(pg_portal):
    engine, schema = pg_portal
    with engine.begin() as c:
        c.execute(text("DROP TABLE alembic_version"))
    with engine.begin() as c:
        with pytest.raises(ValueError, match="Erst die Migration: Tabelle alembic_version fehlt"):
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)


# --- Migration auf einem Bestand -----------------------------------------------------------------------------------------------------------------------

def _probe_migration(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO customers (name, last_name, created_at) VALUES ('Bestand', 'Bestand', '2026-11-01 10:00:00')"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT portal_aktiv FROM customers")).scalar() in (0, False)  # der Bestand: Portal aus
        kid = c.execute(text("SELECT id FROM customers")).scalar()
        c.execute(text("INSERT INTO portal_zugaenge (customer_id, email, email_anzeige, angelegt_am) VALUES (:k, 'a@example.invalid', "
                       "'a***@example.invalid', '2026-11-23 10:00:00')"), {"k": kid})
    with pytest.raises(IntegrityError):
        with engine.begin() as c:  # ein Status außerhalb der festen Werte
            zid = c.execute(text("SELECT id FROM portal_zugaenge")).scalar()
            c.execute(text("INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab, beendet_grund) VALUES "
                           "(:z, :w, '2026-11-23 10:00:00', '2026-11-23 10:15:00', 'erfunden')"), {"z": zid, "w": "a" * 64})
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "gingen mit dem Downgrade verloren" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("DELETE FROM portal_zugaenge"))
        c.execute(text("UPDATE customers SET portal_aktiv = :w"), {"w": True})
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "1 Kunden mit Portal an" in (nein.stdout + nein.stderr)
    with engine.begin() as c:
        c.execute(text("UPDATE customers SET portal_aktiv = :w"), {"w": False})
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT name FROM customers")).scalar() == "Bestand"
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'portal.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe_migration(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_portal_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe_migration(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
