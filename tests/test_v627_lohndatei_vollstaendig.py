"""Version 1.9.225 (Lohn L1b, Punkt 2): Vollständigkeit der Lohndatei und „Nicht in der Datei“.

    Personalnummer   „Vor dem Abschluss“ und der Export verlangen sie von jedem, der eine Zeile bekäme (app/lohndatei.py::berechnen()) -- auch nur mit
                     Abwesenheit, Ausfalltag, Heiligabend, Silvester oder Feiertag; nicht beim Umfang „nichts“ (bis 1.9.224 nur bei Buchungen und Umfang
                     „alles“)
    Nicht in der     je Person mit Grund: Arbeit, Mehrarbeit und Feiertag bei „nur Abwesenheiten“; Arbeit und Abwesenheiten bei „nichts“; jede Zeile ohne
    Datei            Kennzeichen; Arbeit vor dem Eintritt oder nach dem Austritt -- „Monat & Lohn“ über dem Knopf „DATEV-Export“

Dezember 2026 (Tarif 7,50 h, Fr 25.12. Feiertag, Do 24.12. Heiligabend, Do 31.12. Silvester); Juni 2026 für Schlechtwetter Sommer (Tarif 8,00 h).
"""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from app.lohndatei import berechnen
from app.lohnarten import speichern
from app.models import EmployeeAbsence, EmployeePayrollSettings, TimeEntry, TimeTrackingSettings
from app.routers import zeiten as zeiten_router
from app.time_backoffice import DatevExportGesperrt, build_datev_export, datev_fehlt
from app.zeiten import monat, vor_dem_abschluss
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote

D = Decimal
DEZ, LETZTER = date(2026, 12, 1), date(2026, 12, 31)


def tag(t: int, m: int = 12) -> date:
    return date(2026, m, t)


@pytest.fixture
def w(threaded_db_session, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0627"))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", LETZTER
    db.commit()
    return {"db": db, "order": order}


def person(w, nummer, vorname, nachname, pnr=None, *, umfang="alles", eintritt=None, aktiv=True):
    e = make_employee(w["db"], nummer, vorname, nachname)
    e.active = aktiv
    w["db"].add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=pnr, export_umfang=umfang, payroll_export_enabled=umfang != "nichts",
                                        eintritt=eintritt))
    w["db"].commit()
    return e


def buchen(w, e, stunden, t):
    o = w["order"]
    w["db"].add(TimeEntry(employee_id=e.id, project_id=o.project_id, order_id=o.id, work_date=t, entry_type="site", hours=D(stunden), break_minutes=0,
                          status="booked", started_at=datetime.combine(t, time(7)), ended_at=datetime.combine(t, time(8))))
    w["db"].commit()


def abwesend(w, e, von, bis=None, kategorie="urlaub", art="Urlaub"):
    w["db"].add(EmployeeAbsence(employee_id=e.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis or von))
    w["db"].commit()


def fehlt(w, erster=DEZ):
    return [x["text"] for x in datev_fehlt(w["db"], erster, LETZTER if erster == DEZ else erster.replace(day=30))]


# --- Personalnummer von jedem, der eine Zeile bekäme -------------------------------------------------------------------------------------------

def test_auch_ohne_buchung(w):
    """Ohne Buchung: Urlaub (Ada), nur Feiertag/Heiligabend/Silvester (Ben, aktiv); nach Nachnamen. Bis 1.9.224 fehlte keine der beiden."""
    ada = person(w, "M-1", "Ada", "Zander")
    person(w, "M-2", "Ben", "Adler")
    abwesend(w, ada, tag(8))
    assert fehlt(w) == ["Personalnummer fehlt: Ben Adler", "Personalnummer fehlt: Ada Zander"]


def test_ausfalltag_allein(w):
    """Nur ein Ausfalltag Schlechtwetter in einem Monat ohne Feiertag (März 2026): die Zeile WA verlangt die Nummer."""
    c = person(w, "M-3", "Cleo", "Berg", umfang="abwesenheiten")
    abwesend(w, c, tag(10, 3), kategorie="schlechtwetter", art="Schlechtwetter")
    assert [x["text"] for x in datev_fehlt(w["db"], date(2026, 3, 1), date(2026, 3, 31))] == ["Personalnummer fehlt: Cleo Berg"]


def test_ohne_zeile_keine_nummer_noetig(w):
    """Umfang „nichts“ (auch mit Buchung und Urlaub), „nur Abwesenheiten“ nur mit Buchung in einem Monat ohne Feiertag und Kalendertag (März),
    inaktiv ohne Daten. Im Dezember bekommt Emil (gewerblich, „nur Abwesenheiten“) Heiligabend und Silvester -- dort fehlt seine Nummer."""
    d = person(w, "M-4", "Dora", "Kurz", umfang="nichts")
    buchen(w, d, "8.00", tag(7))
    abwesend(w, d, tag(8))
    e = person(w, "M-5", "Emil", "Lang", umfang="abwesenheiten")
    buchen(w, e, "8.00", tag(10, 3))
    person(w, "M-6", "Fritz", "Alt", aktiv=False)
    assert fehlt(w) == ["Personalnummer fehlt: Emil Lang"]
    assert [x["text"] for x in datev_fehlt(w["db"], date(2026, 3, 1), date(2026, 3, 31))] == []


def test_vor_dem_abschluss_und_export(w):
    ada = person(w, "M-1", "Ada", "Zander")
    abwesend(w, ada, tag(8))
    assert "Personalnummer fehlt: Ada Zander" in [x["text"] for x in vor_dem_abschluss(w["db"], DEZ)]
    with pytest.raises(DatevExportGesperrt) as fehler:
        build_datev_export(w["db"], DEZ, LETZTER)
    assert [(x["art"], x["name"]) for x in fehler.value.liste] == [("personalnummer", "Ada Zander")]
    assert monat(w["db"], DEZ)["datev_text"] == "1 Personalnummer"


# --- Nicht in der Datei ---------------------------------------------------------------------------------------------------------------------

def _nicht(w, erster=DEZ):
    return {x.name: x.nicht_texte() for x in berechnen(w["db"], erster) if x.nicht}


def test_umfang_nur_abwesenheiten_und_nichts(w):
    c = person(w, "M-3", "Cleo", "Berg", "00193", umfang="abwesenheiten")
    buchen(w, c, "8.00", tag(7))
    buchen(w, c, "6.10", tag(8))
    d = person(w, "M-4", "Dora", "Kurz", umfang="nichts")
    buchen(w, d, "8.00", tag(7))
    abwesend(w, d, tag(9), tag(10))
    person(w, "M-6", "Fritz", "Alt", umfang="nichts")  # aktiv, nichts eingetragen: nicht in der Liste
    assert _nicht(w) == {
        "Cleo Berg": ["Arbeit: 2 Tage, 14,00 h – Export-Umfang „nur Abwesenheiten“", "Feiertag: 1 Tag, 7,50 h – Export-Umfang „nur Abwesenheiten“"],
        "Dora Kurz": ["Arbeit: 1 Tag, 8,00 h – Export-Umfang „nichts“", "Urlaub: 2 Tage, 15,00 h – Export-Umfang „nichts“"]}


def test_ohne_kennzeichen(w):
    """Unbezahlt (Kategorie leer), Fortbildung mit Art „Sonstiges“ (Kategorie leer), Silvester mit geleerter Zuordnung."""
    a = person(w, "M-1", "Ada", "Zander", "00101")
    abwesend(w, a, tag(2), tag(3), kategorie="unbezahlt", art="Unbezahlt")
    abwesend(w, a, tag(4), kategorie="fortbildung", art="Sonstiges")
    speichern(w["db"], "kalender:silvester", None, None, False)
    assert _nicht(w) == {"Ada Zander": ["Unbezahlt: 2 Tage, 15,00 h – ohne Kennzeichen in der Zuordnung",
                                        "Fortbildung (Sonstiges): 1 Tag, 7,50 h – ohne Kennzeichen in der Zuordnung",
                                        "Silvester – unbezahlte Freistellung: 1 Tag, 7,50 h – ohne Kennzeichen in der Zuordnung"]}


def test_schlechtwetter_sommer_und_vor_dem_eintritt(w):
    a = person(w, "M-1", "Ada", "Zander", "00101", eintritt=tag(15, 6))
    abwesend(w, a, tag(16, 6), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "8.00", tag(12, 6))
    assert _nicht(w, date(2026, 6, 1)) == {"Ada Zander": ["Arbeit: 1 Tag, 8,00 h – vor dem Eintritt oder nach dem Austritt",
                                                          "Schlechtwetter Sommer: 1 Tag, 8,00 h – ohne Kennzeichen in der Zuordnung"]}


def test_nichts_fehlt_bei_vollstaendiger_zuordnung(w):
    a = person(w, "M-1", "Ada", "Zander", "00101")
    buchen(w, a, "8.00", tag(7))
    abwesend(w, a, tag(8))
    assert _nicht(w) == {}


def test_monat_und_lohn_liefert_die_liste(w, router_test_client):
    c = person(w, "M-3", "Cleo", "Berg", "00193", umfang="abwesenheiten")
    buchen(w, c, "8.00", tag(7))
    a = person(w, "M-1", "Ada", "Zander", "00101")
    abwesend(w, a, tag(2), kategorie="unbezahlt", art="Unbezahlt")
    d = router_test_client(w["db"], zeiten_router.router).get("/api/zeiten/monat", params={"monat": "2026-12"}).json()
    assert d["nicht_in_der_datei"] == [
        {"employee_id": c.id, "name": "Cleo Berg", "eintraege": ["Arbeit: 1 Tag, 8,00 h – Export-Umfang „nur Abwesenheiten“",
                                                                  "Feiertag: 1 Tag, 7,50 h – Export-Umfang „nur Abwesenheiten“"]},
        {"employee_id": a.id, "name": "Ada Zander", "eintraege": ["Unbezahlt: 1 Tag, 7,50 h – ohne Kennzeichen in der Zuordnung"]}]


def test_seite_direkt_ueber_dem_knopf():
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "zeiten.html").read_text(encoding="utf-8")
    liste, knopf = text.index('id="lohnNicht"'), text.index('id="lohnDatev"')
    assert text.index('id="lohnCsv"') < liste < knopf and text[liste:knopf].count("</div>") == 1
    assert "esc(x.name)" in text and "esc(t)" in text and "Nichts – alles aus dem Monat geht in die Datei." in text
