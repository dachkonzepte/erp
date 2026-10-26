"""Version 1.9.92 (Stufe 4, R5a, Punkt 5, Entscheidung Tobias): der DATEV-Export nur für abgeschlossene Zeiträume, nur vollständig, mit den
gespeicherten Stunden.

    Zeitraum      Ende nach dem Abschluss -> 409 („nur für abgeschlossene Zeiträume“), keine Datei
    Stunden       die gespeicherten, über tagessumme() summiert -- je Mitarbeiter dieselbe Summe wie Stundenzettel (PDF) und Übersicht; keine
                  zweite Rundung (bis 1.9.91 wurde jede Buchung nach den Zeitregeln erneut gerundet: 2,33 + 0,42 + 7,17 = 9,92 h wurden 10,00 h)
    vollständig   fehlt eine Lohnart (je gebuchter Zeitart, kein stiller Rückfall auf „Sonstige“), eine Personalnummer oder Berater-/
                  Mandantennummer -> 409 mit Liste, keine Datei (bis 1.9.91 fehlten die Stunden still, nur als Zahl in X-DATEV-Warnings)
    LODAS         Kopf [Allgemein] mit BeraterNr und MandantenNr, [Satzbeschreibung], je Personalnummer, Monat und Lohnart eine Zeile
    Nummern       Berater- und Mandantennummer nur der Admin (PUT /api/time-backoffice/datev-nummern), Format nach DATEV (422); das allgemeine
                  Formular der Zeitregeln lässt sie stehen
"""

import csv
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest

from app.models import Employee, EmployeePayrollSettings, TimeEntry, TimeTrackingSettings
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v133_invoices import make_order_with_item
from tests.test_v213_inspection_items import _extract_pdf_text

VON, BIS = "2026-09-01", "2026-09-30"
ZEITRAUM = {"start_date": VON, "end_date": BIS}


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    tom = Employee(employee_number="M-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add_all([mia, tom]); db.flush()
    db.add_all([EmployeePayrollSettings(employee_id=mia.id, datev_personnel_number="1001", payroll_export_enabled=True),
                EmployeePayrollSettings(employee_id=tom.id, datev_personnel_number="1002", payroll_export_enabled=True)])

    def te(ma, tag, typ, stunden):
        return TimeEntry(employee_id=ma.id, project_id=order.project_id, order_id=order.id, work_date=tag, entry_type=typ,
                         counts_as_productive=typ != "travel", hours=Decimal(stunden), status="booked", source="manual")

    # Stunden nicht auf Viertelstunden: die frühere zweite Rundung (Zeitregel 15 min) hätte sie verändert
    db.add_all([te(mia, date(2026, 9, 1), "site", "2.33"), te(mia, date(2026, 9, 1), "travel", "0.42"),
                te(mia, date(2026, 9, 2), "site", "7.17"), te(tom, date(2026, 9, 2), "site", "8.08")])
    s = db.get(TimeTrackingSettings, 1)
    s.datev_wage_type_site, s.datev_wage_type_travel, s.datev_wage_type_other = "100", "200", "900"
    s.datev_beraternummer, s.datev_mandantennummer = "1234567", "12345"
    s.rounding_minutes = 15
    s.locked_until = date(2026, 9, 30)
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def _als(w, rolle="buero_finanzen"):
    return w["client"](w["db"], time_backoffice_router.router, role=rolle)


def _export(w):
    return _als(w).get("/api/time-backoffice/datev-export", params=ZEITRAUM)


def _csv(antwort):
    return list(csv.reader(StringIO(antwort.content.decode("utf-8-sig")), delimiter=";"))


# --- Zeitraum --------------------------------------------------------------------------------------------------------------------

def test_offener_zeitraum_kein_export(welt):
    """Angriff: abgeschlossen bis 15.09., Export bis 30.09. -> 409 mit Meldung, keine Datei. Gegenprobe: bis 30.09. abgeschlossen -> Datei."""
    welt["db"].get(TimeTrackingSettings, 1).locked_until = date(2026, 9, 15)
    welt["db"].commit()
    antwort = _export(welt)
    assert antwort.status_code == 409
    assert antwort.json() == {"detail": "Der DATEV-Export geht nur für abgeschlossene Zeiträume – abgeschlossen ist bis 15.09.2026.",
                              "liste": []}
    welt["db"].get(TimeTrackingSettings, 1).locked_until = None
    welt["db"].commit()
    assert "noch ist nichts abgeschlossen" in _export(welt).json()["detail"]
    welt["db"].get(TimeTrackingSettings, 1).locked_until = date(2026, 9, 30)
    welt["db"].commit()
    datei = _export(welt)
    assert datei.status_code == 200 and "attachment" in datei.headers["content-disposition"]
    assert "x-datev-warnings" not in datei.headers


# --- eine Summe --------------------------------------------------------------------------------------------------------------------

def test_datev_summe_gleich_stundenzettel_und_uebersicht(welt):
    """Je Mitarbeiter: DATEV (Lohn und Gehalt, je Tag und Zeitart) = Stundenzettel als PDF (Summenzeile) = Übersicht -- Mia 9,92 h, Tom
    8,08 h, keine zweite Rundung."""
    zeilen = _csv(_export(welt))
    assert zeilen[0] == ["Personalnummer", "Name", "Kalendertag", "Stundenanzahl", "Lohnart", "Zeitart"]
    datev: dict[str, Decimal] = {}
    for pnr, _, _, stunden, _, _ in zeilen[1:]:
        datev[pnr] = datev.get(pnr, Decimal("0")) + Decimal(stunden.replace(",", "."))
    assert datev == {"1001": Decimal("9.92"), "1002": Decimal("8.08")}
    client = _als(welt)
    uebersicht = {e["employee_name"]: Decimal(str(e["hours"])) for e in client.get("/api/time-backoffice/summary", params=ZEITRAUM).json()["employees"]}
    assert uebersicht == {"Mia Monteurin": Decimal("9.92"), "Tom Monteur": Decimal("8.08")}
    for ma, summe in ((welt["mia"], b"9,92"), (welt["tom"], b"8,08")):  # die Summenzeile des Stundenzettels (die Zeilen: 2,33 0,42 7,17)
        text = _extract_pdf_text(client.get("/api/time-backoffice/timesheet.pdf", params={**ZEITRAUM, "employee_id": ma.id}).content)
        assert b"Summe" in text and summe in text, text[-300:]


def test_laufende_zeit_zaehlt_in_keiner_summe(welt):
    """Gegenprobe zur einen Funktion: eine laufende Zeit (Stunden 0, Tag im Zeitraum) zählt weder in der Übersicht noch im Stundenzettel."""
    from datetime import datetime
    db = welt["db"]
    db.add(TimeEntry(employee_id=welt["tom"].id, project_id=db.query(TimeEntry).first().project_id, order_id=db.query(TimeEntry).first().order_id,
                     work_date=date(2026, 9, 3), entry_type="site", counts_as_productive=True, hours=Decimal("3"), status="running",
                     started_at=datetime(2026, 9, 3, 7), source="timer"))
    db.commit()
    uebersicht = {e["employee_name"]: Decimal(str(e["hours"])) for e in _als(welt).get("/api/time-backoffice/summary", params=ZEITRAUM).json()["employees"]}
    assert uebersicht["Tom Monteur"] == Decimal("8.08")


# --- vollständig oder kein Export --------------------------------------------------------------------------------------------------

def test_fehlende_lohnart_kein_export_auch_nicht_unter_sonstige(welt):
    """Angriff: Fahrzeit ohne Lohnart -- bis 1.9.91 still unter „Sonstige“ (900); jetzt 409 mit Liste, keine Datei."""
    welt["db"].get(TimeTrackingSettings, 1).datev_wage_type_travel = None
    welt["db"].commit()
    antwort = _export(welt)
    assert antwort.status_code == 409
    assert antwort.json()["liste"] == [{"art": "lohnart", "zeitart": "travel", "text": "Lohnart fehlt: Fahrzeit"}]
    assert antwort.json()["detail"] == "Kein DATEV-Export: Lohnart fehlt: Fahrzeit."


def test_fehlende_personalnummer_kein_export(welt):
    welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["tom"].id).one().datev_personnel_number = None
    welt["db"].commit()
    antwort = _export(welt)
    assert antwort.status_code == 409
    assert antwort.json()["liste"] == [{"art": "personalnummer", "employee_id": welt["tom"].id, "name": "Tom Monteur",
                                        "text": "Personalnummer fehlt: Tom Monteur"}]


def test_ohne_lohnexport_keine_personalnummer_noetig(welt):
    """Gegenprobe: Tom ohne Lohnexport -- seine Personalnummer fehlt nicht, die Datei hat nur Mia."""
    p = welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["tom"].id).one()
    p.datev_personnel_number, p.payroll_export_enabled = None, False
    welt["db"].commit()
    assert {z[0] for z in _csv(_export(welt))[1:]} == {"1001"}


@pytest.mark.parametrize("berater, mandant, text", [(None, "12345", "Beraternummer fehlt"), ("1234567", None, "Mandantennummer fehlt"),
                                                    (None, None, "Beraternummer und Mandantennummer fehlen")])
def test_fehlende_datev_nummern_kein_export(welt, berater, mandant, text):
    s = welt["db"].get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer = berater, mandant
    welt["db"].commit()
    antwort = _export(welt)
    assert antwort.status_code == 409 and antwort.json()["liste"] == [{"art": "datev_nummern", "text": text}]


def test_mehreres_fehlt_alles_in_der_liste(welt):
    s = welt["db"].get(TimeTrackingSettings, 1)
    s.datev_wage_type_site = s.datev_beraternummer = None
    welt["db"].query(EmployeePayrollSettings).filter_by(employee_id=welt["mia"].id).one().datev_personnel_number = None
    welt["db"].commit()
    assert [x["art"] for x in _export(welt).json()["liste"]] == ["personalnummer", "lohnart", "datev_nummern"]


# --- LODAS ---------------------------------------------------------------------------------------------------------------------------

def test_lodas_mit_kopf_und_einer_zeile_je_monat_und_lohnart(welt):
    welt["db"].get(TimeTrackingSettings, 1).datev_target = "lodas"
    welt["db"].commit()
    antwort = _export(welt)
    assert antwort.status_code == 200
    zeilen = antwort.content.decode("cp1252").split("\r\n")
    assert zeilen == [
        "[Allgemein]", "Ziel=LODAS", "Version_SST=1.0", "BeraterNr=1234567", "MandantenNr=12345", "Datumsformat=TT/MM/JJJJ",
        "Feldtrennzeichen=;", "Zahlenkomma=,", "",
        "[Satzbeschreibung]", "3;u_lod_bwd_buchung_standard;abrechnung_zeitraum#bwd;bs_wert_butab#bwd;bs_nr#bwd;la_eigene#bwd;pnr#bwd;", "",
        "[Bewegungsdaten]", "3;01/09/2026;9,50;01;100;1001", "3;01/09/2026;0,42;01;200;1001", "3;01/09/2026;8,08;01;100;1002", ""]


# --- Berater- und Mandantennummer --------------------------------------------------------------------------------------------------

def test_datev_nummern_nur_admin(welt):
    antwort = _als(welt, "buero_finanzen").put("/api/time-backoffice/datev-nummern", json={"beraternummer": "1001", "mandantennummer": "1"})
    assert antwort.status_code == 403
    assert welt["db"].get(TimeTrackingSettings, 1).datev_beraternummer == "1234567"


@pytest.mark.parametrize("berater, mandant", [("123", "1"), ("12345678", "1"), ("1000", "1"), ("12a45", "1"), ("1001", "123456"),
                                              ("1001", "0"), ("1001", "-1")])
def test_datev_nummern_im_falschen_format_422(welt, berater, mandant):
    antwort = _als(welt, "admin").put("/api/time-backoffice/datev-nummern", json={"beraternummer": berater, "mandantennummer": mandant})
    assert antwort.status_code == 422, antwort.text
    welt["db"].expire_all()
    s = welt["db"].get(TimeTrackingSettings, 1)
    assert (s.datev_beraternummer, s.datev_mandantennummer) == ("1234567", "12345")


def test_datev_nummern_speichern_und_leeren(welt):
    client = _als(welt, "admin")
    d = client.put("/api/time-backoffice/datev-nummern", json={"beraternummer": " 1001 ", "mandantennummer": "99999"}).json()
    assert (d["datev_beraternummer"], d["datev_mandantennummer"]) == ("1001", "99999")
    assert client.put("/api/time-backoffice/datev-nummern", json={"beraternummer": "", "mandantennummer": None}).json()["datev_beraternummer"] is None
    assert client.put("/api/time-backoffice/datev-nummern", json={"beraternummer": "1001"}).status_code == 422  # beide Pflicht (Regel 22)


def test_formular_der_zeitregeln_laesst_die_nummern_stehen(welt):
    """Das Büro speichert die Zeitregeln (volles Formular) -- Berater- und Mandantennummer bleiben."""
    client = _als(welt, "buero_auftrag")
    form = client.get("/api/time-backoffice/settings").json()
    form.update({"datev_beraternummer": "9999", "datev_mandantennummer": "9"})
    assert client.put("/api/time-backoffice/settings", json=form).status_code == 200
    welt["db"].expire_all()
    s = welt["db"].get(TimeTrackingSettings, 1)
    assert (s.datev_beraternummer, s.datev_mandantennummer) == ("1234567", "12345")
