"""Version 1.9.301 (Nachrunde der Geräte-Runde, Punkt 1): „Ressource“ heißt überall „Gerät“.

    Oberfläche     keine Vorlage zeigt „Ressource“ (ohne Kommentare), keine Meldung des Servers nennt es (Zeichenketten unter app/ ohne Docstrings) -- übrig
                   sind nur die gespeicherten alten Namen der Historie, die app/verlauf_namen.py beim Anzeigen übersetzt
    Einstellungen  Auswahlliste „Gerätetypen · Fuhrpark & Maschinen“ (bis 1.9.300 „Ressourcentypen“); im Bestand stellt die Migration c990522c34ff um, nur
                   wo noch genau die bisherige Bezeichnung steht
    AV, Kolonne    Reiter „Kolonnen / Geräte“, „Noch keine Geräte angelegt.“
    Modul aus      „N planbare Geräte“, Spalte „Gerät“, „Gerät anlegen“ / „Gerät bearbeiten“, „Gerätenummer“, „Gerätetyp“
    Meldungen      „Gerät nicht gefunden.“, „Gerätenummer ist bereits vergeben.“
    Historie       gespeichert bleibt die Art wie bisher („Ressource“, „Plantafel-Gerät“, „Team-Ressource“, „AV-Team-Ressource“ -- Filter, Verlauf der Akte,
                   Schwärzung hängen daran), angezeigt „Gerät“, „Gerät am Einsatz“, „Gerät der Kolonne“, „Gerät der Kolonne (AV)“, für alte und neue
                   Einträge gleich; Felder „Gerät“, „Gerätetyp“, „Gerätenummer“ -- auch ein älterer Eintrag mit gespeicherter alter Bezeichnung
"""

import ast
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

from app.audit import FIELD_LABELS, TYPE_LABELS, reset_audit_context, set_audit_context
from app.models import AuditLog, SettingOptionGroup
from app.option_settings import DEFAULT_OPTION_GROUPS
from app.routers.audit import router as audit_router
from app.routers.resource_planning import router as resource_router
from app.verlauf_namen import ALTE_FELDNAMEN, ANGEZEIGTE_ARTEN, art_lesbar, feld_lesbar
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.vorlagen_js import alle_vorlagen

ROOT = Path(__file__).resolve().parent.parent
VORLAGEN = ROOT / "app" / "templates"
MIGRATION = "c990522c34ff"
VORHER = "c3e9f1a7b285"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
ALT = "Ressourcentypen · Fuhrpark & Maschinen"
NEU = "Gerätetypen · Fuhrpark & Maschinen"


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?<![:'\"\\])//[^\n]*", "", text)
    text = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _vorlage(name: str) -> str:
    return (VORLAGEN / name).read_text(encoding="utf-8")


# --- Oberfläche ------------------------------------------------------------------------------------------------------------------------------

def test_keine_vorlage_zeigt_ressource():
    treffer = []
    for name in alle_vorlagen():
        text = _ohne_kommentare(_vorlage(name))
        for m in re.finditer("Ressource", text):
            treffer.append(f"{name}: …{text[max(0, m.start() - 40):m.end() + 30]}…")
    assert treffer == []


def _zeichenketten(pfad: Path):
    """Jede Zeichenkette einer Python-Datei außer Docstrings (auch die festen Teile eines f-Strings)."""
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    docstrings = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and knoten.body:
            erstes = knoten.body[0]
            if isinstance(erstes, ast.Expr) and isinstance(erstes.value, ast.Constant) and isinstance(erstes.value.value, str):
                docstrings.add(id(erstes.value))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str) and id(knoten) not in docstrings:
            yield knoten.value


def test_keine_meldung_nennt_ressource():
    """Übrig darf nur ein gespeicherter alter Name sein, den die Historie beim Anzeigen übersetzt."""
    alte_namen = set(ANGEZEIGTE_ARTEN) | set(ALTE_FELDNAMEN)
    treffer = []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        for wert in _zeichenketten(pfad):
            if "Ressource" in wert and wert not in alte_namen:
                treffer.append(f"{pfad.relative_to(ROOT).as_posix()}: {wert[:90]!r}")
    assert treffer == []


def test_neue_texte_stehen():
    assert ">Kolonnen / Geräte</button>" in _vorlage("work_preparation.html")
    form = _vorlage("master_data_form.html")
    assert "titel(editing?'Gerät bearbeiten':'Gerät anlegen')" in form
    assert "<label>Gerätenummer</label>" in form and "<label>Gerätetyp *</label>" in form
    assert "Noch keine Geräte angelegt." in form
    liste = _vorlage("master_data.html")
    assert "sub.textContent=`${resources.length} planbare Geräte`" in liste and "table(['Nr.','Typ','Gerät','Hersteller / Modell'" in liste


def test_auswahlliste_heisst_geraetetypen(db_session):
    assert DEFAULT_OPTION_GROUPS["resource_types"]["label"] == NEU
    gruppe = db_session.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == "resource_types"))
    assert gruppe.label == NEU  # eine neue Installation (Grunddaten beim Start)


# --- Meldungen und Historie über die Schnittstelle --------------------------------------------------------------------------------------------

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
        yield {"db": db, "c": router_test_client(db, resource_router, audit_router)}
    finally:
        reset_audit_context(token)


def test_meldungen_nennen_das_geraet(welt):
    c = welt["c"]
    assert c.get("/api/resources/999999").json()["detail"] == "Gerät nicht gefunden."
    assert c.post("/api/resources", json={"name": "Kran", "resource_type": "Kran", "resource_number": "K-1"}).status_code == 200
    doppelt = c.post("/api/resources", json={"name": "Kran 2", "resource_type": "Kran", "resource_number": "K-1"})
    assert doppelt.status_code == 409 and doppelt.json()["detail"] == "Gerätenummer ist bereits vergeben."


def test_historie_zeigt_geraet_gespeichert_bleibt_ressource(welt):
    db, c = welt["db"], welt["c"]
    r = c.post("/api/resources", json={"name": "Pritsche", "resource_type": "Fahrzeug", "resource_number": "F-1"}).json()
    assert c.put(f"/api/resources/{r['id']}", json={"resource_type": "Anhänger"}).status_code == 200
    # ein älterer Eintrag: Art als Klassenname (vor 1.8.138), Feld mit der damals gespeicherten Bezeichnung
    db.add(AuditLog(occurred_at=datetime(2026, 9, 1, 8), actor_name="Alt", action="geändert", entity_type="OperationalResource", entity_id=str(r["id"]),
                    entity_label="F-1 Pritsche", field_name="resource_number", field_label="Ressourcennummer", old_value="F-0", new_value="F-1"))
    db.commit()
    zeilen = c.get("/api/audit-logs?entity_type=Ressource").json()  # der Filter nimmt die gespeicherte Art
    assert zeilen and {z["entity_type"] for z in zeilen} == {"Ressource"} and {z["entity_type_label"] for z in zeilen} == {"Gerät"}
    typ = [z for z in zeilen if z["field_name"] == "resource_type"]
    assert typ and typ[0]["field_label"] == "Gerätetyp" and typ[0]["new_value"] == "Anhänger"
    alt = [z for z in c.get("/api/audit-logs?entity_type=OperationalResource").json()]
    assert [(z["entity_type_label"], z["field_label"]) for z in alt] == [("Gerät", "Gerätenummer")]


def test_angezeigte_arten_und_felder():
    assert art_lesbar("Ressource") == "Gerät"
    assert art_lesbar("Plantafel-Gerät") == "Gerät am Einsatz"
    assert art_lesbar("Team-Ressource") == "Gerät der Kolonne"
    assert art_lesbar("AV-Team-Ressource") == "Gerät der Kolonne (AV)"
    assert art_lesbar("OperationalResource") == "Gerät" and art_lesbar("TeamResource") == "Gerät der Kolonne"
    # gespeichert bleiben die bisherigen Namen -- an ihnen hängen Filter, Verlauf der Akte und Schwärzung
    gespeichert = {cls.__name__: name for cls, name in TYPE_LABELS.items()}
    assert (gespeichert["OperationalResource"], gespeichert["PlanningSlotResource"], gespeichert["TeamResource"],
            gespeichert["WorkPreparationTeamResource"]) == ("Ressource", "Plantafel-Gerät", "Team-Ressource", "AV-Team-Ressource")
    assert not [n for n in TYPE_LABELS.values() if "Ressource" in (art_lesbar(n) or "")]
    assert not [n for n in FIELD_LABELS.values() if "Ressource" in n]
    assert (FIELD_LABELS["resource_id"], FIELD_LABELS["resource_type"], FIELD_LABELS["resource_number"]) == ("Gerät", "Gerätetyp", "Gerätenummer")
    assert [feld_lesbar("resource_id", alt) for alt in ("Ressource", "Ressource (Name)", "Ressourcentyp", "Ressourcentyp (Stand)", "Ressourcennummer")] == [
        "Gerät", "Gerät (Name)", "Gerätetyp", "Gerätetyp (Stand)", "Gerätenummer"]


# --- Migration c990522c34ff ------------------------------------------------------------------------------------------------------------------

def _labels(engine) -> dict:
    with engine.connect() as c:
        return dict(c.execute(text("SELECT group_key, label FROM setting_option_groups")).all())


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        for key, label in (("resource_types", ALT), ("units", "Mengeneinheiten")):
            c.execute(text("INSERT INTO setting_option_groups (group_key, label, sort_order, created_at, updated_at) VALUES (:k, :l, 10, '2026-11-01', '2026-11-01')"),
                      {"k": key, "l": label})
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _labels(engine) == {"resource_types": NEU, "units": "Mengeneinheiten"}
    _ok(_alembic(url, "downgrade", VORHER))
    assert _labels(engine) == {"resource_types": ALT, "units": "Mengeneinheiten"}
    with engine.begin() as c:  # eine andere Bezeichnung bleibt (in den Einstellungen nicht änderbar -- nur der Vollständigkeit halber)
        c.execute(text("UPDATE setting_option_groups SET label = 'Fahrzeugarten' WHERE group_key = 'resource_types'"))
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _labels(engine)["resource_types"] == "Fahrzeugarten"
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'geraetetypen.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_geraetetypen_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
