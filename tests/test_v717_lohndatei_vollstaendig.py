"""Version 1.9.317 (Nachrunde L2b, Punkt A): die Lohndatei nur vollständig -- eine Kategorie ohne Zuordnung sperrt sie wie eine fehlende Personalnummer.

    Sperre        Tage einer Kategorie ohne Kennzeichen in der Zuordnung (außer Unbezahlt und Freizeitausgleich) stehen in datev_fehlt() -- keine Lohndatei;
                  eine Art mit eigener Zuordnung (Weiterbildung, Berufsschule) geht vor; Export-Umfang „nichts“ zählt nicht; den Abschluss sperrt es nicht
    Meldung       „Vor dem Abschluss“ behält „Sonderurlaub ohne Zuordnung: n Tage nicht in der Lohndatei“, dazu „– keine Lohndatei, bis die Zuordnung steht“
                  (einmal, nicht doppelt); „Monat & Lohn“: „Fehlt: 1 Zuordnung“
    Auslieferung  ohne Zuordnung sind heute Sonderurlaub und Fortbildung (Unbezahlt und Freizeitausgleich bewusst leer)
Stehende Uhr 10.11.2026 (fester_tag).
"""

from datetime import date

import pytest

from app.absence_requests import ABSENCE_CATEGORIES
from app.lohnarten import FEST, START, speichern
from app.lohndatei import BEWUSST_LEER
from app.models import EmployeeAbsence, EmployeePayrollSettings, TimeTrackingSettings
from app.time_backoffice import DatevExportGesperrt, abschluss_hindernisse, build_datev_export, datev_fehlt
from app.zeiten import datev_text, monat, vor_dem_abschluss
from tests.test_v224_field_view import make_employee

OKT, ENDE = date(2026, 10, 1), date(2026, 10, 31)
K = " – keine Lohndatei, bis die Zuordnung steht"


@pytest.fixture
def w(threaded_db_session, fester_tag):
    db = threaded_db_session
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    for e, pnr in ((mia, "00091"), (tom, "00092")):
        e.employee_group = "gewerblich"
        db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=pnr, export_umfang="alles", payroll_export_enabled=True))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", ENDE
    db.commit()
    return {"db": db, "mia": mia, "tom": tom}


def abwesend(w, e, von, bis, kategorie, art):
    w["db"].add(EmployeeAbsence(employee_id=e.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis))
    w["db"].commit()


def zuordnungen(w):
    return [x["text"] for x in datev_fehlt(w["db"], OKT, ENDE) if x["art"] == "zuordnung"]


def test_in_der_auslieferung_ohne_zuordnung():
    """Für den Bericht: welche Kategorien heute ohne Zuordnung ausgeliefert werden (START in app/lohnarten.py)."""
    leer = [k for k in ABSENCE_CATEGORIES if k != "schlechtwetter" and f"kategorie:{k}" not in START]
    assert leer == ["sonderurlaub", "fortbildung", "unbezahlt", "freizeitausgleich"]
    assert [k for k in leer if k not in BEWUSST_LEER] == ["sonderurlaub", "fortbildung"]
    assert {s for s, _b, _h in FEST} >= {f"kategorie:{k}" for k in leer}  # jede steht in den Einstellungen


def test_sperrt_wie_eine_fehlende_personalnummer(w):
    db, mia, tom = w["db"], w["mia"], w["tom"]
    abwesend(w, mia, date(2026, 10, 12), date(2026, 10, 13), "fortbildung", "Seminar")  # Fortbildung ohne eigene Zuordnung der Art
    abwesend(w, mia, date(2026, 10, 14), date(2026, 10, 14), "fortbildung", "Weiterbildung")  # eigene Zuordnung 1 / 1000: zählt nicht
    abwesend(w, tom, date(2026, 10, 15), date(2026, 10, 15), "sonderurlaub", "Sonderurlaub")
    abwesend(w, tom, date(2026, 10, 19), date(2026, 10, 20), "unbezahlt", "Unbezahlt")  # bewusst leer
    abwesend(w, tom, date(2026, 10, 21), date(2026, 10, 21), "freizeitausgleich", "Freizeitausgleich")
    assert zuordnungen(w) == ["Sonderurlaub ohne Zuordnung: 1 Tag nicht in der Lohndatei" + K, "Fortbildung ohne Zuordnung: 2 Tage nicht in der Lohndatei" + K]
    with pytest.raises(DatevExportGesperrt) as fehler:
        build_datev_export(db, OKT, ENDE)
    assert "Fortbildung ohne Zuordnung" in str(fehler.value) and "Sonderurlaub ohne Zuordnung" in str(fehler.value)
    assert abschluss_hindernisse(db, ENDE) == []  # den Abschluss sperrt es nicht
    # „Vor dem Abschluss“ einmal je Kategorie (bis 1.9.316 kam die Zeile getrennt dazu), „Monat & Lohn“ zählt die Zuordnungen
    vda = [x["text"] for x in vor_dem_abschluss(db, OKT) if "Zuordnung" in x["text"]]
    assert vda == zuordnungen(w)
    m = monat(db, OKT)
    assert m["datev_text"] == "2 Zuordnungen" and [x["art"] for x in m["datev_fehlt"]] == ["zuordnung", "zuordnung"]
    assert datev_text([{"art": "zuordnung"}, {"art": "personalnummer"}]) == "1 Personalnummer, 1 Zuordnung"
    # mit Zuordnung geht die Datei
    speichern(db, "kategorie:sonderurlaub", "SU", None, False)
    speichern(db, "kategorie:fortbildung", "1", "1000", False)
    assert zuordnungen(w) == []
    inhalt, _name = build_datev_export(db, OKT, ENDE)
    assert b"00092;15;SU;;" in inhalt and b"00091;12;1;1000;" in inhalt


def test_export_umfang_nichts_sperrt_nicht(w):
    db, tom = w["db"], w["tom"]
    db.query(EmployeePayrollSettings).filter_by(employee_id=tom.id).one().export_umfang = "nichts"
    db.commit()
    abwesend(w, tom, date(2026, 10, 15), date(2026, 10, 15), "sonderurlaub", "Sonderurlaub")
    assert zuordnungen(w) == [] and build_datev_export(db, OKT, ENDE)[0].startswith(b"1234567;12345;10/2026")
