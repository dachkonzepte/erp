"""Version 1.9.172 (Lohn L1a, Punkt 7): scripts/pruefe_zeitregeln.py -- wie stehen Zeitregeln, Modelle, Personalnummern und Feiertage?

    Grunddaten   Rundung, Tarif (KW 18–48 8,00 h, KW 49–17 7,50 h), Pausen 6 h -> 30 min und 9 h -> 45 min, Standardmodell, Zuordnung -> Rückgabe 0
    zu klären    alte Grundwerte, Kalenderwochen ohne aktives Modell, Personalnummer fehlt (außer Export „nichts“), falsch, doppelt -> Rückgabe 1
    Hinweise     abweichende Pausenregeln, mehrere Modelle in einer Woche, kein Standardmodell -> Rückgabe bleibt
    Feiertage    Bundesland, gesetzliche Feiertage dieses und des nächsten Jahres, von Hand eingetragene Tage
    Datenschutz  kein Name in der Ausgabe
    nur lesen    die eigene Sitzung schreibt nicht (SQLite und PostgreSQL); ohne DATABASE_URL Rückgabe 2
"""

import importlib.util
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (Employee, EmployeePayrollSettings, EmployeeTargetHours, EmployeeWorkTimeModel, PlanningHoliday, PlanningRegionSettings,
                        TimeBackofficeAdvancedSettings, TimeTrackingSettings, WorkTimeBreakRule, WorkTimeModel, WorkTimeModelValidity)
from tests.befund_vor_echtbetrieb import pg_sitzung
from tests.pg_schutz import pg_url_pruefen
from tests.test_v133_invoices import db_session

ROOT = Path(__file__).resolve().parent.parent
HEUTE = date(2026, 11, 10)
NAME = "Geheimnachname"


def _skript():
    spec = importlib.util.spec_from_file_location("pruefe_zeitregeln", ROOT / "scripts" / "pruefe_zeitregeln.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lauf(db):
    zeilen = []
    rc = _skript().main([], sitzung=db, ausgabe=zeilen.append, heute=HEUTE)
    return rc, zeilen


def _modell(db, code):
    return db.scalar(select(WorkTimeModel).where(WorkTimeModel.code == code))


def _person(db, nr, *, datev=None, umfang="alles", eintritt=None, austritt=None, aktiv=True):
    emp = Employee(employee_number=nr, first_name="Mia", last_name=NAME, employee_group="gewerblich", weekly_hours=Decimal("40"), active=aktiv)
    db.add(emp)
    db.flush()
    db.add(EmployeePayrollSettings(employee_id=emp.id, datev_personnel_number=datev, export_umfang=umfang, payroll_export_enabled=umfang != "nichts",
                                   eintritt=eintritt, austritt=austritt))
    db.commit()
    return emp


def test_grunddaten_nichts_zu_klaeren():
    db = db_session()
    sommer, winter = _modell(db, "summer"), _modell(db, "winter")
    rc, zeilen = _lauf(db)
    assert rc == 0, zeilen
    assert zeilen[0] == "Rundung: keine; abgeschlossen bis: –"
    assert zeilen[1:4] == [
        "Arbeitszeitmodelle: 2",
        f"  Modell {sommer.id} „Sommermodell“ (Kürzel summer): KW 18–48, Soll Mo–Fr 8,00 h, über 6,00 h -> 30 min · über 9,00 h -> 45 min, aktiv, "
        "Standardmodell, 0 Person(en) zugeordnet",
        f"  Modell {winter.id} „Wintermodell“ (Kürzel winter): KW 49–17, Soll Mo–Fr 7,50 h, über 6,00 h -> 30 min · über 9,00 h -> 45 min, aktiv, "
        "0 Person(en) zugeordnet",
    ]
    assert "Personen (aktiv): 0; DATEV-Nr. = ERP-Nr.: nein" in zeilen
    assert "Bundesland NW, Feiertage automatisch: an" in zeilen
    assert "Von Hand eingetragene Tage: 0 (zählen nicht als Feiertag F)" in zeilen
    assert zeilen[-1] == "Nichts zu klären."
    assert not any("Hinweis" in z for z in zeilen)


def test_rundung_und_abschluss():
    db = db_session()
    zeit = db.get(TimeTrackingSettings, 1)
    zeit.rounding_minutes, zeit.locked_until = 15, date(2026, 10, 31)
    db.commit()
    assert _lauf(db)[1][0] == "Rundung: 15 Minuten; abgeschlossen bis: 31.10.2026"


def test_feiertage_dieses_und_naechsten_jahres():
    db = db_session()
    _, zeilen = _lauf(db)
    jahr26 = next(z for z in zeilen if z.startswith("  Gesetzliche Feiertage 2026: "))
    assert jahr26.startswith("  Gesetzliche Feiertage 2026: 01.01.2026 Neujahr, ") and "25.12.2026 1. Weihnachtstag, 26.12.2026 2. Weihnachtstag" in jahr26
    assert "01.11.2026 Allerheiligen" in jahr26  # NW
    assert any(z.startswith("  Gesetzliche Feiertage 2027: 01.01.2027 Neujahr") for z in zeilen)


def test_anderes_bundesland_und_von_hand_eingetragene_tage():
    db = db_session()
    region = db.get(PlanningRegionSettings, 1) or PlanningRegionSettings(id=1)
    region.federal_state_code, region.auto_public_holidays = "BE", False
    db.add(region)
    db.add_all([PlanningHoliday(holiday_date=date(2026, 12, 24), name="Betriebsruhe", active=True),
                PlanningHoliday(holiday_date=date(2026, 12, 31), name="Silvester", active=False)])
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 0
    assert "Bundesland BE, Feiertage automatisch: aus" in zeilen
    assert not any("Allerheiligen" in z for z in zeilen)  # nicht in Berlin
    i = zeilen.index("Von Hand eingetragene Tage: 2 (zählen nicht als Feiertag F)")
    assert zeilen[i + 1:i + 3] == ["  24.12.2026 Betriebsruhe", "  31.12.2026 Silvester (inaktiv)"]


def test_alte_grundwerte_sind_zu_klaeren():
    """Vor der Migration b7e3c91d4a52 (oder wenn sie die Modelle wegen einer Änderung von Hand nicht umgestellt hat)."""
    db = db_session()
    sommer, winter = _modell(db, "summer"), _modell(db, "winter")
    for m, (von, bis) in ((sommer, (13, 43)), (winter, (44, 12))):
        g = db.scalar(select(WorkTimeModelValidity).where(WorkTimeModelValidity.model_id == m.id))
        g.valid_from_week, g.valid_to_week = von, bis
        m.daily_target_hours = Decimal("8.00")
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert f"  ! Modell {sommer.id} trägt noch die alten Grundwerte (KW 13–43, 8,00 h), nicht den Tarif (KW 18–48 8,00 h, KW 49–17 7,50 h)." in zeilen
    assert f"  ! Modell {winter.id} trägt noch die alten Grundwerte (KW 44–12, 8,00 h), nicht den Tarif (KW 18–48 8,00 h, KW 49–17 7,50 h)." in zeilen
    assert zeilen[-1] == "Zu klären: 2"


def test_kalenderwochen_ohne_aktives_modell():
    db = db_session()
    _modell(db, "winter").active = False
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert "  ! Kalenderwochen ohne aktives Modell: 1–17, 49–53 -- dort keine Sollzeit nach Tarif." in zeilen


def test_hinweise_aendern_die_rueckgabe_nicht():
    db = db_session()
    sommer = _modell(db, "summer")
    db.get(TimeBackofficeAdvancedSettings, 1).default_work_time_model_id = None
    for r in db.scalars(select(WorkTimeBreakRule).where(WorkTimeBreakRule.model_id == sommer.id)):
        if r.threshold_hours == Decimal("9"):
            r.break_minutes = 30
    db.scalar(select(WorkTimeModelValidity).where(WorkTimeModelValidity.model_id == sommer.id)).valid_to_week = 50
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 0, zeilen
    assert "    Hinweis: Pausenregeln weichen von 6 h -> 30 min und 9 h -> 45 min ab." in zeilen
    assert "  Hinweis: kein Standardmodell -- wer kein Modell zugeordnet hat, bekommt das erste für die Woche gültige." in zeilen
    assert ("  Hinweis: Kalenderwochen mit mehreren aktiven Modellen: 49–50 -- es gilt das zugeordnete, sonst das Standardmodell, sonst das erste."
            in zeilen)


def test_personalnummern_fehlend_falsch_doppelt():
    db = db_session()
    gut = _person(db, "E-1", datev="91001")
    fehlt = _person(db, "E-2")
    _person(db, "E-3", umfang="nichts")                          # nichts exportiert: ohne Nummer in Ordnung
    nur_abw = _person(db, "E-4", umfang="abwesenheiten")         # Abwesenheiten gehen in die Datei: Nummer nötig
    null = _person(db, "E-5", datev="091001")
    doppelt = _person(db, "E-6", datev=" 91001")                 # in der Datenbank verschieden, für DATEV dieselbe
    _person(db, "E-7", aktiv=False)                              # inaktiv: nicht geprüft
    rc, zeilen = _lauf(db)
    assert rc == 1
    befunde = [z for z in zeilen if z.startswith("  ! ")]
    assert befunde == [
        f"  ! Person {fehlt.id}: keine Personalnummer, Export „alles“.",
        f"  ! Person {nur_abw.id}: keine Personalnummer, Export „nur Abwesenheiten“.",
        f"  ! Person {null.id}: Personalnummer „091001“ hat nicht genau 5 Ziffern.",  # seit 1.9.212
        f"  ! Personalnummer 91001 tragen 2 Personen ({gut.id}, {doppelt.id}).",
    ]
    assert "Personen (aktiv): 6; DATEV-Nr. = ERP-Nr.: nein" in zeilen
    assert "  Export-Umfang: alles 4, nur Abwesenheiten 1, nichts 1" in zeilen


def test_gleichsetzung_prueft_die_erp_nummer():
    db = db_session()
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    db.commit()
    ziffern = _person(db, "09005")  # seit 1.9.212 fünfstellig (bis 1.9.211 „9005“)
    buchstaben = _person(db, "M-17")
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert "Personen (aktiv): 2; DATEV-Nr. = ERP-Nr.: ja" in zeilen
    assert f"  ! Person {buchstaben.id}: Personalnummer „M-17“ hat nicht genau 5 Ziffern." in zeilen  # seit 1.9.212
    assert not any(f"Person {ziffern.id}:" in z for z in zeilen)


def test_eintritt_austritt_eigene_sollzeit_und_zuordnung_der_modelle():
    db = db_session()
    a = _person(db, "E-1", datev="00001", eintritt=date(2020, 4, 1))  # seit 1.9.212 fünfstellig (bis 1.9.211 „1“, „2“, „3“)
    b = _person(db, "E-2", datev="00002", eintritt=date(2021, 1, 1), austritt=date(2026, 10, 31))
    _person(db, "E-3", datev="00003", austritt=date(2027, 3, 31))     # Austritt erst später
    db.add(EmployeeTargetHours(employee_id=a.id, valid_from=date(2026, 1, 1), dienstag=Decimal("8"), mittwoch=Decimal("8")))
    db.add(EmployeeWorkTimeModel(employee_id=a.id, model_id=_modell(db, "winter").id))
    db.commit()
    rc, zeilen = _lauf(db)
    assert rc == 0, zeilen
    assert f"  Eintritt eingetragen: 2 von 3; aktiv, aber ausgetreten: {b.id}" in zeilen
    assert "  Personen mit eigener Sollzeit: 1" in zeilen
    assert any(z.startswith(f"  Modell {_modell(db, 'winter').id} „Wintermodell“") and z.endswith(", 1 Person(en) zugeordnet") for z in zeilen)


def test_zuordnung_fuer_den_export():
    db = db_session()
    _, zeilen = _lauf(db)
    i = next(n for n, z in enumerate(zeilen) if z.startswith("Zuordnung für den DATEV-Export: "))
    zuordnung = zeilen[i + 1:-1]
    assert "  arbeit: 1 / 1000" in zuordnung
    assert "  kategorie:urlaub: U / 8000" in zuordnung
    assert "  schlechtwetter:winter: WA / 8195" in zuordnung  # seit 1.9.214 (bis 1.9.213 Monatszeile 8110)
    assert "  schlechtwetter:sommer: nicht exportiert" in zuordnung
    assert "  art:weiterbildung: 1 / 1000" in zuordnung


def test_kein_name_in_der_ausgabe():
    db = db_session()
    _person(db, "E-1")
    _person(db, "E-2", datev="091001")
    _, zeilen = _lauf(db)
    ausgabe = "\n".join(zeilen)
    assert NAME not in ausgabe and "Mia" not in ausgabe


def test_ohne_database_url_rueckgabe_2():
    zeilen = []
    assert _skript().main([], umgebung={}, ausgabe=zeilen.append) == 2
    assert zeilen == ["DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a"]


def test_aufruf_steht_im_kopf_der_datei():
    kopf = _skript().__doc__
    assert ".venv/bin/python scripts/pruefe_zeitregeln.py" in kopf and "Rückgabe: 0 nichts zu klären, 1 etwas zu klären" in kopf


def test_die_eigene_sitzung_schreibt_nicht(tmp_path):
    from app.grunddaten import anlegen

    url = pg_url_pruefen(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")  # Regel 27: wer DATABASE_URL weitergibt, prüft sie
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        anlegen(db)
        db.commit()
        _person(db, "E-1")
        db.close()
        zeilen = []
        assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 1
        sitzung = _skript().nur_lesende_sitzung(url)
        try:
            with pytest.raises(DBAPIError):
                sitzung.execute(text("UPDATE work_time_models SET daily_target_hours = 1"))
                sitzung.commit()
            sitzung.rollback()
        finally:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    finally:
        engine.dispose()


@pytest.fixture
def pg():
    with pg_sitzung("pruefe_zeitr") as db:
        yield db


def test_unter_postgresql_lesen_und_nicht_schreiben(pg):
    """Regel 27: im Wegwerf-Schema, über die eigene Sitzung des Skripts wie auf dem Server."""
    from app.grunddaten import anlegen

    anlegen(pg)
    pg.commit()
    fehlt = _person(pg, "E-1")
    schema = pg.scalar(text("SELECT current_schema()"))
    url = pg_url_pruefen(f"{os.environ['ERP_TEST_POSTGRES_URL']}?options=-csearch_path={schema}")
    zeilen = []
    assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 1
    assert f"  ! Person {fehlt.id}: keine Personalnummer, Export „alles“." in zeilen
    sitzung = _skript().nur_lesende_sitzung(url)
    try:
        with pytest.raises(DBAPIError):
            sitzung.execute(text("UPDATE work_time_models SET daily_target_hours = 1"))
        sitzung.rollback()
    finally:
        bind = sitzung.get_bind()
        sitzung.close()
        bind.dispose()
