"""Version 1.9.230 (Stufe 6, R3a, Punkt 0a, Vorweg aus Lohn L1b): in der Lohndatei nur Personalnummern mit genau 5 Ziffern, „DATEV-Nr. = ERP-Nr.“
entfällt.

    Format     eine gespeicherte Personalnummer ohne genau 5 Ziffern (vor 1.9.212 gespeichert, z. B. „1001“) sperrt die Lohndatei wie eine fehlende:
               datev_fehlt() nennt sie (art „personalnummer_format“), „Prüfen“ zeigt sie unter „Vor dem Abschluss“, der Export lehnt ab (409), die
               Datei selbst lehnt sie ab (ValueError) -- bis 1.9.229 ging „1001“ so hinein (Bild 01 des Berichts L1b)
    Schalter   „DATEV-Nr. = ERP-Nr.“ gibt es nicht mehr: weder in den Zeitregeln noch auf der Seite; die alte Spalte liest niemand
    Migration  b6d14e8a2f73: war der Schalter an, wird die Mitarbeiternummer mit genau 5 Ziffern Personalnummer, wenn sie frei ist
"""

import importlib.util
import os
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.lohndatei import Person, Zeile, berechnen, datei
from app.models import TimeBackofficeAdvancedSettings
from app.time_backoffice import DatevExportGesperrt, build_datev_export, datev_fehlt, time_settings_dict, load_time_settings
from app.zeiten import datev_text, monat, pruefen
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v627_lohndatei_vollstaendig import DEZ, LETZTER, buchen, person, tag, w  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = "b6d14e8a2f73"
VORHER = "d5a8e3c71b42"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


# --- Format ---------------------------------------------------------------------------------------------------------------------------------

def test_vier_ziffern_sperren_die_datei(w):
    """Mia „1001“ (alt gespeichert), Tom „00102“, Ole „M-17“ -- zwei Einträge mit der Nummer und dem Namen, keine Datei, die Zeile „Fehlt“ zählt sie."""
    mia = person(w, "M-1", "Mia", "Monteurin", "1001")
    tom = person(w, "M-2", "Tom", "Teich", "00102")
    ole = person(w, "M-3", "Ole", "Offen", "M-17")
    for e in (mia, tom, ole):
        buchen(w, e, "8", tag(1))
    fehlt = datev_fehlt(w["db"], DEZ, LETZTER)
    assert [(x["art"], x["text"]) for x in fehlt] == [
        ("personalnummer_format", "Personalnummer „1001“ hat nicht genau 5 Ziffern: Mia Monteurin"),
        ("personalnummer_format", "Personalnummer „M-17“ hat nicht genau 5 Ziffern: Ole Offen")]
    assert datev_text(fehlt) == "2 Personalnummern"
    with pytest.raises(DatevExportGesperrt) as fehler:
        build_datev_export(w["db"], DEZ, LETZTER)
    assert "Personalnummer „1001“ hat nicht genau 5 Ziffern: Mia Monteurin" in str(fehler.value)


def test_fehlend_und_falsch_zusammen(w):
    ada = person(w, "M-1", "Ada", "Adler")
    ben = person(w, "M-2", "Ben", "Berg", "101")
    for e in (ada, ben):
        buchen(w, e, "8", tag(2))
    assert [x["text"] for x in datev_fehlt(w["db"], DEZ, LETZTER)] == ["Personalnummer fehlt: Ada Adler",
                                                                       "Personalnummer „101“ hat nicht genau 5 Ziffern: Ben Berg"]
    assert datev_text(datev_fehlt(w["db"], DEZ, LETZTER)) == "2 Personalnummern"


def test_ohne_zeile_kein_eintrag(w):
    """Umfang „nichts“: keine Zeile, keine Forderung an die Nummer -- auch nicht an ihr Format."""
    e = person(w, "M-1", "Mia", "Monteurin", "1001", umfang="nichts")
    buchen(w, e, "8", tag(1))
    assert datev_fehlt(w["db"], DEZ, LETZTER) == []


def test_pruefen_nennt_sie_unter_vor_dem_abschluss(w):
    """„ein Eintrag unter ‚Prüfen‘“: der Monat von „Prüfen“ ist der Dezember (abgeschlossen bis zum 31.12.) -- der Eintrag steht in „Vor dem Abschluss“."""
    e = person(w, "M-1", "Mia", "Monteurin", "1001")
    buchen(w, e, "8", tag(1))
    stand = pruefen(w["db"], date(2026, 12, 15))
    assert {"art": "personalnummer_format", "text": "Personalnummer „1001“ hat nicht genau 5 Ziffern: Mia Monteurin"} in stand["vor_dem_abschluss"]


def test_monat_und_lohn_kennzeichnet_sie(w):
    e = person(w, "M-1", "Mia", "Monteurin", "1001")
    g = person(w, "M-2", "Tom", "Teich", "00102")
    for x in (e, g):
        buchen(w, x, "8", tag(1))
    zeilen = {z["name"]: (z["personalnummer"], z["personalnummer_gueltig"]) for z in monat(w["db"], DEZ)["zeilen"]}
    assert zeilen["Mia Monteurin"] == ("1001", False) and zeilen["Tom Teich"] == ("00102", True)


def test_die_datei_lehnt_sie_selbst_ab():
    """Zweite Sicherung: datei() schreibt keine Zeile mit einer Nummer ohne genau 5 Ziffern (auch ohne Nummer nicht)."""
    zeile = Zeile(date(2026, 12, 1), "AR", "1000", 8, "arbeit")
    ok = Person(1, "Tom", "00102", "alles", False, "Teich")
    ok.zeilen.append(zeile)
    assert datei("1234567", "12345", DEZ, [ok]).startswith(b"1234567;12345;12/2026")
    for nummer in ("1001", "M-17", None, "001020"):
        p = Person(2, "Mia", nummer, "alles", False, "Monteurin")
        p.zeilen.append(zeile)
        with pytest.raises(ValueError, match="Personalnummer ohne genau 5 Ziffern"):
            datei("1234567", "12345", DEZ, [ok, p])
    leer = Person(3, "Ole", "1", "nichts", False, "Offen")  # ohne Zeilen zählt die Nummer nicht
    assert datei("1234567", "12345", DEZ, [ok, leer])


# --- Schalter -------------------------------------------------------------------------------------------------------------------------------

def test_alte_spalte_wirkt_nicht(w):
    """Die alte Spalte auf „an“: die Mitarbeiternummer 00042 ist keine Personalnummer, die Zeitregeln nennen den Schalter nicht."""
    db = w["db"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    db.commit()
    e = person(w, "00042", "Max", "Dach")
    buchen(w, e, "8", tag(1))
    assert [p.personalnummer for p in berechnen(db, DEZ) if p.employee_id == e.id] == [None]
    assert [x["text"] for x in datev_fehlt(db, DEZ, LETZTER)] == ["Personalnummer fehlt: Max Dach"]
    assert "datev_personnel_equals_erp_number" not in time_settings_dict(load_time_settings(db), db)


def test_die_seite_hat_keinen_schalter():
    seite = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")
    assert "datevSameErp" not in seite and "datev_personnel_equals_erp_number" not in seite
    assert "entspricht der ERP-Mitarbeiternummer</label>" not in seite and "Bei Aktivierung wird die ERP-Mitarbeiternummer" not in seite


def test_niemand_liest_die_alte_spalte():
    """Unter app/ und scripts/ steht der Name nur noch im Modell (Spalte) und in der Beschriftung alter Einträge des Änderungsprotokolls."""
    funde = []
    for ordner in ("app", "scripts"):
        for f in (ROOT / ordner).rglob("*"):
            if f.suffix in (".py", ".html") and "datev_personnel_equals_erp_number" in f.read_text(encoding="utf-8"):
                funde.append(f.relative_to(ROOT).as_posix())
    assert sorted(funde) == ["app/audit.py", "app/models.py"]


# --- Migration b6d14e8a2f73 -----------------------------------------------------------------------------------------------------------------

def _mig():
    datei_ = next((ROOT / "alembic" / "versions").glob("*_gleichsetzung_entfaellt.py"))
    spec = importlib.util.spec_from_file_location("mig_gleich", datei_)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PERSONEN = [  # Mitarbeiternummer, DATEV-Nummer (None = keine Zeile der Lohnstammdaten, "" = Zeile ohne Nummer)
    ("E1", "00042", None),      # ohne Lohnstammdaten -> neue Zeile mit 00042
    ("E2", " 00043 ", ""),      # Leerzeichen am Rand -> 00043
    ("E3", "MA-0042", None),    # keine 5 Ziffern -> nichts
    ("E4", "00045", "00099"),   # abweichend -> ersetzt (die Datei nahm die Mitarbeiternummer)
    ("E5", "00046", "00046"),   # schon so -> nichts
    ("E6", "00047", ""),        # E7 trägt 00047 -> nichts
    ("E7", "00070", "00047"),   # seine eigene 00070 ist frei -> ersetzt
    ("E8", "00048", ""),        # 00048 ist E7 gemerkt -> nichts
    ("E9", "00049", ""),        # 00049 eingelesen ohne Person -> nichts
    ("E10", "123456", "00101"),  # 6 Ziffern -> nichts
    # Gegenprobe 230_6c blieb grün (E6/E7: getragen UND gemerkt) -- getragen allein, ungemerkt (seit dem Nachtrag der Gegenprobe):
    ("E11", "00050", ""),       # E12 trägt 00050 (nicht gemerkt) -> nichts
    ("E12", "M-12", "00050"),
    ("E13", " 00051", ""),      # dieselbe Nummer zweimal: die erste Person (nach id) bekommt sie
    ("E14", "00051", ""),
]
GEMERKT = [("00045", "E4"), ("00048", "E7"), ("00049", None), ("00047", "E7")]


def _bestand(engine, gleich: bool) -> None:
    with engine.begin() as c:
        for kurz, erp, datev in PERSONEN:
            c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                           "VALUES (:e, 'P', :l, 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')"), {"e": erp, "l": kurz, "a": True})
            if datev is not None:
                c.execute(text("INSERT INTO employee_payroll_settings (employee_id, datev_personnel_number, payroll_export_enabled, export_umfang, azubi, "
                               "updated_at) VALUES ((SELECT id FROM employees WHERE last_name = :l), :d, :a, 'abwesenheiten', :f, '2026-09-01')"),
                          {"l": kurz, "d": datev or None, "a": True, "f": False})
        for nummer, kurz in GEMERKT:
            c.execute(text("INSERT INTO personalnummern_vergeben (nummer, employee_id, vergeben_am) VALUES "
                           "(:n, (SELECT id FROM employees WHERE last_name = :l), '2026-11-01')"), {"n": nummer, "l": kurz})
        c.execute(text("INSERT INTO time_backoffice_advanced_settings (id, datev_personnel_equals_erp_number, updated_at) VALUES (1, :g, '2026-09-01')"),
                  {"g": gleich})


def _stand(engine):
    with engine.connect() as c:
        lohn = sorted((l, d, u) for l, d, u in c.execute(text(
            "SELECT e.last_name, p.datev_personnel_number, p.export_umfang FROM employee_payroll_settings p JOIN employees e ON e.id = p.employee_id")))
        gemerkt = sorted([(n, l) for n, l in c.execute(text(
            "SELECT v.nummer, e.last_name FROM personalnummern_vergeben v LEFT JOIN employees e ON e.id = v.employee_id"))], key=lambda x: x[0])
        schalter = c.execute(text("SELECT datev_personnel_equals_erp_number FROM time_backoffice_advanced_settings")).scalar()
        return lohn, gemerkt, bool(schalter)


def _probe(url, engine):
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, gleich=True)
    vorher = _stand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    lohn, gemerkt, schalter = _stand(engine)
    assert lohn == sorted([
        ("E1", "00042", "alles"), ("E2", "00043", "abwesenheiten"), ("E4", "00045", "abwesenheiten"), ("E5", "00046", "abwesenheiten"),
        ("E6", None, "abwesenheiten"), ("E7", "00070", "abwesenheiten"), ("E8", None, "abwesenheiten"), ("E9", None, "abwesenheiten"),
        ("E10", "00101", "abwesenheiten"), ("E11", None, "abwesenheiten"), ("E12", "00050", "abwesenheiten"), ("E13", "00051", "abwesenheiten"),
        ("E14", None, "abwesenheiten")])
    assert gemerkt == sorted(vorher[1] + [("00042", "E1"), ("00043", "E2"), ("00051", "E13"), ("00070", "E7")], key=lambda x: x[0])
    assert schalter is True  # die Spalte bleibt, wie sie war -- nichts liest sie
    _ok(_alembic(url, "downgrade", VORHER))
    assert _stand(engine) == (lohn, gemerkt, schalter)  # downgrade() ändert keine Daten
    _ok(_alembic(url, "upgrade", "head"))


def _ohne_schalter(url, engine):
    _ok(_alembic(url, "upgrade", VORHER))
    _bestand(engine, gleich=False)
    vorher = _stand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert _stand(engine) == vorher


def _sqlite(tmp_path, name, ablauf):
    url = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = create_engine(url)
    try:
        ablauf(url, engine)
    finally:
        engine.dispose()


def _postgresql(ablauf):
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_gleich_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        ablauf(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    _sqlite(tmp_path, "gleich.db", _probe)


def test_migration_ohne_schalter_aendert_nichts_sqlite(tmp_path):
    _sqlite(tmp_path, "gleich_aus.db", _ohne_schalter)


def test_migration_auf_einem_bestand_postgresql():
    _postgresql(_probe)


def test_migration_ohne_schalter_aendert_nichts_postgresql():
    _postgresql(_ohne_schalter)


def test_uebernahmen_ohne_einstellungszeile(tmp_path):
    """Ohne Zeile der Einstellungen (nie gespeichert): nichts zu übernehmen."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'leer.db').as_posix()}")
    try:
        with engine.begin() as c:
            c.execute(text("CREATE TABLE time_backoffice_advanced_settings (id INTEGER, datev_personnel_equals_erp_number BOOLEAN)"))
            assert _mig().uebernahmen(c) == []
    finally:
        engine.dispose()
