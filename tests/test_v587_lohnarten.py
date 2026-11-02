"""Version 1.9.169 (Lohn L1a, Punkt 4, Entscheidungen Tobias E7 und Nachtrag 02.11.2026): Zuordnung für den DATEV-Export, Kategorie
Freizeitausgleich.

    vorbelegt     Arbeit 1/1000, Feiertag F/1012, Urlaub U/8000, Krankheit K/1650, Art Weiterbildung 1/1000 (Sollzeit), Schlechtwetter Winter
                  8110 als Monatszeile; alles andere leer = nicht exportiert, sichtbar in der Liste (auch Berufsschule, Schlechtwetter Sommer)
    Vorrang       eine Art mit eigener Zuordnung vor ihrer Kategorie
    Kategorie     Freizeitausgleich ist eine eigene Kategorie; die Migration d8f2a6c4e913 stellt den Bestand um (Art Freizeitausgleich in
                  Kategorie Urlaub)
    Rechte        ändern nur Admin und Büro – Finanzen (E10)
"""

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app.grunddaten import anlegen
from app.lohnarten import fest, liste, speichern, zuordnung
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v380_nummern_eindeutig import _alembic, _ok

MIGRATION = "d8f2a6c4e913"
VORHER = "c5a9e3f71d28"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _zeilen(db):
    return {z["schluessel"]: (z["kennzeichen"], z["lohnart"], z["monatszeile"], z["wirkt"]) for z in liste(db)}


def test_vorbelegt_nach_e7(db_session):
    z = _zeilen(db_session)
    assert z["arbeit"] == ("1", "1000", False, "1 / 1000")
    assert z["feiertag"] == ("F", "1012", False, "F / 1012")
    assert z["kategorie:urlaub"] == ("U", "8000", False, "U / 8000")
    assert z["kategorie:krankheit"] == ("K", "1650", False, "K / 1650")
    assert z["schlechtwetter:winter"] == (None, "8110", True, "Monatszeile 8110")
    assert z["art:weiterbildung"] == ("1", "1000", False, "1 / 1000")
    for leer in ("kategorie:fortbildung", "kategorie:unbezahlt", "kategorie:freizeitausgleich", "schlechtwetter:sommer"):
        assert z[leer] == (None, None, False, "nicht exportiert"), leer
    assert z["art:berufsschule"][:3] == (None, None, False) and z["art:berufsschule"][3] == "wie die Kategorie – Fortbildung: nicht exportiert"
    assert z["art:freizeitausgleich"][3] == "wie die Kategorie – Freizeitausgleich: nicht exportiert"


@pytest.mark.parametrize("kategorie, art, erwartet", [
    ("fortbildung", "Weiterbildung", ("1", "1000")),   # Art vor Kategorie
    ("fortbildung", "Berufsschule", None),             # offen beim Lohnbüro
    ("fortbildung", "Fortbildung", None),
    ("urlaub", "Sonstiges", ("U", "8000")),            # ohne eigene Zuordnung die Kategorie
    ("krankheit", "Kind krank", ("K", "1650")),        # selbst angelegte Art
    ("freizeitausgleich", "Freizeitausgleich", None),
    ("unbezahlt", "Unbezahlt", None),
])
def test_art_vor_kategorie(db_session, kategorie, art, erwartet):
    w = zuordnung(db_session, kategorie, art, date(2026, 12, 7))
    assert (None if w is None else (w["kennzeichen"], w["lohnart"])) == erwartet


def test_schlechtwetter_nach_datum(db_session):
    """Winter 01.12.–31.03. (Monatszeile 8110), Sommer leer (bis der Juni-Export da ist)."""
    for tag in (date(2026, 12, 1), date(2027, 3, 31), date(2027, 1, 15)):
        assert zuordnung(db_session, "schlechtwetter", "Schlechtwetter", tag)["lohnart"] == "8110", tag
    for tag in (date(2026, 11, 30), date(2027, 4, 1), date(2027, 6, 15)):
        assert zuordnung(db_session, "schlechtwetter", "Schlechtwetter", tag) is None, tag


def test_eigene_zuordnung_einer_art_und_leeren(db_session):
    db = db_session
    speichern(db, "art:berufsschule", "BS", "1100", False)
    assert zuordnung(db, "fortbildung", "Berufsschule", date(2026, 12, 7))["lohnart"] == "1100"
    speichern(db, "arbeit", None, None, False)
    assert fest(db, "arbeit") is None
    anlegen(db)  # ein Neustart füllt einen geleerten Eintrag nicht wieder
    assert fest(db, "arbeit") is None and _zeilen(db)["arbeit"][3] == "nicht exportiert"


@pytest.mark.parametrize("schluessel, kennzeichen, lohnart, monatszeile, teil", [
    ("arbeit", "UU1", "1000", False, "ein oder zwei Zeichen"),
    ("arbeit", "1", "10000", False, "1 bis 4 Ziffern"),
    ("arbeit", "1", "10a", False, "1 bis 4 Ziffern"),
    ("arbeit", None, "1000", True, "nur für Schlechtwetter"),
    ("schlechtwetter:winter", "S", "8110", True, "kein Kennzeichen"),
    ("feiertag", "F", None, False, "gehört eine Lohnart"),
    ("feiertag", None, "1012", False, "gehört ein Kennzeichen"),
    ("lohn:irgendwas", "1", "1000", False, "Unbekannter Eintrag"),
    ("art:", "1", "1000", False, "Unbekannter Eintrag"),
])
def test_pruefungen(db_session, schluessel, kennzeichen, lohnart, monatszeile, teil):
    with pytest.raises(ValueError, match=teil):
        speichern(db_session, schluessel, kennzeichen, lohnart, monatszeile)


def test_kennzeichen_gross(db_session):
    assert speichern(db_session, "kategorie:unbezahlt", "u", "9000", False).kennzeichen == "U"


def test_schnittstelle_und_rechte(threaded_db_session, router_test_client):
    db = threaded_db_session
    auftrag = router_test_client(db, time_backoffice_router.router, role="buero_auftrag")
    assert auftrag.get("/api/time-backoffice/lohnarten").status_code == 200
    koerper = {"schluessel": "kategorie:freizeitausgleich", "kennzeichen": "Z", "lohnart": "1500", "monatszeile": False}
    r = auftrag.put("/api/time-backoffice/lohnarten", json=koerper)
    assert r.status_code == 403 and "du kannst sie lesen" in r.json()["detail"]
    finanzen = router_test_client(db, time_backoffice_router.router, role="buero_finanzen")
    r = finanzen.put("/api/time-backoffice/lohnarten", json=koerper)
    assert r.status_code == 200, r.text
    assert {z["schluessel"]: z["wirkt"] for z in r.json()}["kategorie:freizeitausgleich"] == "Z / 1500"
    falsch = finanzen.put("/api/time-backoffice/lohnarten", json={**koerper, "lohnart": "abc"})
    assert falsch.status_code == 422 and "1 bis 4 Ziffern" in falsch.json()["detail"]
    assert finanzen.put("/api/time-backoffice/lohnarten", json={"schluessel": "arbeit"}).status_code == 422  # kein Feld mit Vorgabewert


def test_freizeitausgleich_eigene_kategorie(db_session):
    from app.absence_requests import create_request
    from tests.test_v224_field_view import make_employee
    mia = make_employee(db_session, "M-1", "Mia", "Monteurin")
    db_session.commit()
    antrag = create_request(db_session, employee_id=mia.id, absence_category="freizeitausgleich", absence_type="Freizeitausgleich",
                            start_date=date(2026, 12, 7), end_date=date(2026, 12, 7))
    assert (antrag.absence_category, antrag.absence_type) == ("freizeitausgleich", "Freizeitausgleich")
    ohne = create_request(db_session, employee_id=mia.id, absence_category="freizeitausgleich", start_date=date(2026, 12, 8),
                          end_date=date(2026, 12, 8))
    assert ohne.absence_type == "Freizeitausgleich"
    with pytest.raises(ValueError, match="passt nicht zur Kategorie"):
        create_request(db_session, employee_id=mia.id, absence_category="urlaub", absence_type="Freizeitausgleich",
                       start_date=date(2026, 12, 9), end_date=date(2026, 12, 9))


def test_seiten_bieten_die_kategorie_an():
    from tests import vorlagen_js as vj
    for vorlage in ("zeiten.html", "mobil_zeiten.html", "planning.html"):
        html = (vj.TEMPLATES / vorlage).read_text(encoding="utf-8")
        assert '<option value="freizeitausgleich">Freizeitausgleich</option>' in html, vorlage
        assert "freizeitausgleich:'Freizeitausgleich'" in html, vorlage


# --- Migration d8f2a6c4e913 ---------------------------------------------------------------------------------------------------------------

def _bestand(engine) -> None:
    with engine.begin() as c:
        c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                       "VALUES ('M-1', 'Mia', 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"a": True})
        mia = c.execute(text("SELECT id FROM employees")).scalar()
        for i, (kategorie, art) in enumerate((("urlaub", "Freizeitausgleich"), ("urlaub", " freizeitausgleich "), ("urlaub", "Urlaub"),
                                              ("unbezahlt", "Freizeitausgleich"))):
            tag = f"2026-10-{i + 5:02d}"
            c.execute(text("INSERT INTO employee_absences (employee_id, absence_type, absence_category, start_date, end_date, created_at, updated_at) "
                           "VALUES (:e, :a, :k, :t, :t, '2026-09-01', '2026-09-01')"), {"e": mia, "a": art, "k": kategorie, "t": tag})
            c.execute(text("INSERT INTO employee_absence_requests (employee_id, absence_type, absence_category, start_date, end_date, status, created_at, updated_at) "
                           "VALUES (:e, :a, :k, :t, :t, 'pending', '2026-09-01', '2026-09-01')"), {"e": mia, "a": art, "k": kategorie, "t": tag})


def _kategorien(engine) -> list[list[str]]:
    with engine.connect() as c:
        return [[z[0] for z in c.execute(text(f"SELECT absence_category FROM {t} ORDER BY start_date"))]
                for t in ("employee_absences", "employee_absence_requests")]


def _probe(url: str, engine) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    neu = ["freizeitausgleich", "freizeitausgleich", "urlaub", "unbezahlt"]
    assert _kategorien(engine) == [neu, neu]
    _ok(_alembic(url, "downgrade", VORHER))
    alt = ["urlaub", "urlaub", "urlaub", "unbezahlt"]
    assert _kategorien(engine) == [alt, alt]
    _ok(_alembic(url, "upgrade", "head"))
    assert _kategorien(engine) == [neu, neu]


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'lohnarten.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_lohnart_{uuid.uuid4().hex[:8]}"
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
