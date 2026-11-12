"""Version 1.9.315 (Lohn L2b, Punkt 3; Antworten 1, 3, 4 und 5 des Befunds L2): das Urlaubskonto je Person und Jahr (app/urlaubskonto.py).

    Spalten       Anspruch (Vorgabe oder je Person), Übertrag (2027 der Startwert; ab 2028 nach der Vorgabe), genehmigt davon vorbei/künftig,
                  beantragt (offene Anträge), Rest = Anspruch + Übertrag − genehmigt, Rest nach den offenen Anträgen
    Zählen        nur Urlaub (nicht Sonderurlaub), nur Tage mit Sollzeit der eigenen Woche, halber Tag mit Anteil, ohne gesetzliche Feiertage und
                  Heiligabend, Silvester nur als ganzer Urlaubstag; ein betriebsfreier Tag zählt
    Hinweise      „ohne Übertrag – Startwert folgt“, „Übertrag doppelt – prüfen“, „Anspruch prüfen“ (Eintritt/Austritt im Jahr), vorgemerkter Verfall
                  (nichts verfällt), „Rest unter 0“ -- keine Sperre
    Abfragen      eine feste Zahl, unabhängig von Personen, Tagen und Anträgen
    Schnittstelle GET /api/zeiten/urlaubskonto?jahr= -- Admin und Büro – Finanzen alle, Büro – Auftrag das eigene, vor 2027 422
Stehende Uhr 10.11.2026 (fester_tag); vorbei/künftig über heute=.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.models import (EmployeeAbsence, EmployeeAbsenceRequest, EmployeePayrollSettings, EmployeeTargetHours, LohnStartwert, PlanningHoliday,
                        TimeTrackingSettings, Urlaubsanspruch)
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import ANSPRUCH_PRUEFEN, DOPPELT, OHNE_STARTWERT, konten
from tests.test_v224_field_view import make_employee

D = Decimal


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada = make_employee(db, "M-1", "Ada", "Monteurin")
    bo = make_employee(db, "M-2", "Bo", "Teilzeit")
    for e in (ada, bo):
        e.employee_group = "gewerblich"
    db.add(EmployeeTargetHours(employee_id=bo.id, valid_from=date(2026, 1, 1), montag=D("8"), dienstag=D("8"), mittwoch=D("8"), donnerstag=D("0"),
                               freitag=D("0"), samstag=D("0"), sonntag=D("0")))
    db.add(LohnStartwert(employee_id=ada.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.commit()
    return {"db": db, "ada": ada, "bo": bo, "client": router_test_client}


def urlaub(w, e, von, bis, *, kategorie="urlaub", halber_tag=False, kalendertag_urlaub=None):
    w["db"].add(EmployeeAbsence(employee_id=e.id, absence_type=kategorie.capitalize(), absence_category=kategorie, start_date=von, end_date=bis,
                                halber_tag=halber_tag, kalendertag_urlaub=kalendertag_urlaub))
    w["db"].commit()


def antrag(w, e, von, bis, kategorie="urlaub", status="pending"):
    w["db"].add(EmployeeAbsenceRequest(employee_id=e.id, absence_type=kategorie.capitalize(), absence_category=kategorie, start_date=von, end_date=bis,
                                       status=status))
    w["db"].commit()


def konto(w, e, jahr=2027, heute=date(2027, 2, 1)):
    return next(k for k in konten(w["db"], jahr, heute=heute) if k.employee_id == e.id)


def test_zaehlt_nur_urlaub_an_tagen_mit_sollzeit(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    db.add(PlanningHoliday(holiday_date=date(2027, 1, 8), name="Brückentag", active=True))  # betriebsfrei: zählt (Antwort 4)
    db.commit()
    urlaub(w, ada, date(2027, 1, 1), date(2027, 1, 8))  # Fr 01.01. Neujahr zählt nicht -> Mo 04.–Fr 08.01. = 5
    urlaub(w, ada, date(2027, 2, 5), date(2027, 2, 5), halber_tag=True)  # 0,5
    urlaub(w, ada, date(2027, 3, 1), date(2027, 3, 2), kategorie="sonderurlaub")  # zählt nicht (Antwort 3)
    urlaub(w, ada, date(2027, 12, 23), date(2027, 12, 31), kalendertag_urlaub=True)  # Do 23., (Fr 24. Heiligabend nein, Sa/So, Mo 27.–Do 30.) Fr 31. ja = 6
    urlaub(w, bo, date(2027, 1, 4), date(2027, 1, 8))  # Bo: nur Mo–Mi Sollzeit = 3
    k = konto(w, ada)
    assert (k.anspruch, k.anspruch_vorgabe, k.uebertrag, k.uebertrag_quelle) == (D("30.0"), True, D("4.5"), "startwert")
    assert (k.genehmigt, k.vorbei, k.kuenftig, k.beantragt) == (D("11.5"), D("5"), D("6.5"), D("0"))
    assert (k.rest, k.rest_nach_antraegen, k.hinweise) == (D("23.0"), D("23.0"), [])
    assert konto(w, ada, heute=date(2027, 2, 5)).vorbei == D("5.5")  # heute zählt als vorbei
    b = konto(w, bo)
    assert (b.genehmigt, b.uebertrag, b.hinweise) == (D("3"), D("0"), [OHNE_STARTWERT])


def test_silvester_frei_zaehlt_nicht(w):
    urlaub(w, w["ada"], date(2027, 12, 31), date(2027, 12, 31), kalendertag_urlaub=False)
    assert konto(w, w["ada"]).genehmigt == D("0")


def test_offene_antraege(w):
    ada = w["ada"]
    antrag(w, ada, date(2027, 4, 12), date(2027, 4, 16))
    antrag(w, ada, date(2027, 4, 19), date(2027, 4, 20), kategorie="sonderurlaub")  # zählt nicht
    antrag(w, ada, date(2026, 12, 28), date(2027, 1, 5))  # nur der Teil im Jahr: Mo 04., Di 05.
    antrag(w, ada, date(2027, 6, 7), date(2027, 6, 11), status="approved")  # entschieden: kein offener Antrag
    antrag(w, ada, date(2027, 6, 14), date(2027, 6, 18), status="rejected")
    k = konto(w, ada)
    assert (k.beantragt, k.rest, k.rest_nach_antraegen) == (D("7"), D("34.5"), D("27.5"))


def test_hinweise(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    db.add(EmployeePayrollSettings(employee_id=bo.id, eintritt=date(2027, 3, 1), export_umfang="alles", payroll_export_enabled=True))
    db.add(Urlaubsanspruch(employee_id=ada.id, jahr=2027, urlaubstage=D("2"), uebertrag=D("3")))  # Bestand: doppelt
    s = db.get(TimeTrackingSettings, 1)
    s.urlaub_verfall = "31.03."
    db.commit()
    urlaub(w, ada, date(2027, 1, 4), date(2027, 1, 15))  # 10 Tage
    k = konto(w, ada)
    assert (k.anspruch, k.anspruch_vorgabe, k.uebertrag, k.rest) == (D("2.0"), False, D("4.5"), D("-3.5"))  # der doppelte zählt nicht
    assert k.hinweise == [DOPPELT, "Verfall des Übertrags vorgemerkt am 31.03.2027 – nichts verfällt von selbst", "Rest unter 0 (-3,5 Tage)"]
    assert konto(w, bo).hinweise == [ANSPRUCH_PRUEFEN]  # seit 1.9.320 ohne „Startwert folgt“: Eintritt 2027, kein Startwert (Antwort B16)


def test_ab_2028_von_hand_und_automatisch(w):
    db, ada = w["db"], w["ada"]
    urlaub(w, ada, date(2027, 1, 4), date(2027, 1, 8))  # Rest 2027 = 30 + 4,5 − 5 = 29,5
    db.add(Urlaubsanspruch(employee_id=ada.id, jahr=2028, uebertrag=D("2")))
    db.commit()
    k = konto(w, ada, 2028, heute=date(2028, 1, 1))
    assert (k.uebertrag_quelle, k.uebertrag, k.hinweise) == ("von_hand", D("2"), [])
    db.get(TimeTrackingSettings, 1).urlaub_uebertrag = "automatisch"
    db.commit()
    k = konto(w, ada, 2028, heute=date(2028, 1, 1))
    assert (k.uebertrag_quelle, k.uebertrag, k.rest, k.hinweise) == ("automatisch", D("29.5"), D("59.5"), [DOPPELT])


def test_personen_aktiv_oder_mit_urlaub_im_jahr(w):
    db = w["db"]
    alt = make_employee(db, "M-8", "Alt", "Ehemalig")
    weg = make_employee(db, "M-9", "Weg", "Ehemalig")
    alt.active = weg.active = False
    db.commit()
    urlaub(w, alt, date(2027, 1, 4), date(2027, 1, 4))
    namen = {k.name for k in konten(db, 2027, heute=date(2027, 2, 1))}
    assert namen == {"Ada Monteurin", "Bo Teilzeit", "Alt Ehemalig"}  # „Weg“: inaktiv ohne etwas im Jahr
    # „automatisch“: die Tagesbilanz läuft ab 2027 -- 2028 steht „Alt“ trotzdem nicht da (inaktiv, nichts im Jahr 2028)
    db.get(TimeTrackingSettings, 1).urlaub_uebertrag = "automatisch"
    db.commit()
    assert {k.name for k in konten(db, 2028, heute=date(2028, 2, 1))} == {"Ada Monteurin", "Bo Teilzeit"}


def test_vor_2027_nicht(w):
    with pytest.raises(ValueError, match="beginnt 2027"):
        konten(w["db"], 2026)


def _abfragen(db, aufruf) -> int:
    import gc
    zaehler = []
    bind = db.get_bind()
    gc.collect()

    def mitzaehlen(*_a, **_k):
        zaehler.append(1)
    event.listen(bind, "before_cursor_execute", mitzaehlen)
    try:
        aufruf()
    finally:
        event.remove(bind, "before_cursor_execute", mitzaehlen)
    return len(zaehler)


def test_eine_feste_zahl_abfragen(w):
    db = w["db"]
    urlaub(w, w["ada"], date(2027, 1, 4), date(2027, 1, 8))
    eins = _abfragen(db, lambda: konten(db, 2027, heute=date(2027, 2, 1)))
    for i in range(4):
        e = make_employee(db, f"X-{i}", f"X{i}", "Mehr")
        urlaub(w, e, date(2027, 1, 4 + i), date(2027, 2, 4 + i))
        antrag(w, e, date(2027, 5, 3), date(2027, 5, 7))
        db.add(Urlaubsanspruch(employee_id=e.id, jahr=2027, urlaubstage=D("26")))
    db.commit()
    assert _abfragen(db, lambda: konten(db, 2027, heute=date(2027, 2, 1))) == eins


def test_schnittstelle_mit_rechten(w):
    db, ada = w["db"], w["ada"]
    urlaub(w, ada, date(2027, 1, 4), date(2027, 1, 8))
    r = w["client"](db, zeiten_router.router, role="buero_finanzen").get("/api/zeiten/urlaubskonto?jahr=2027").json()
    assert r["jahr"] == 2027 and {k["name"] for k in r["konten"]} == {"Ada Monteurin", "Bo Teilzeit"}
    zeile = next(k for k in r["konten"] if k["name"] == "Ada Monteurin")
    assert (zeile["anspruch"], zeile["uebertrag"], zeile["genehmigt"], zeile["rest"], zeile["rest_nach_antraegen"]) == (30.0, 4.5, 5.0, 29.5, 29.5)  # JSON-Zahlen wie die übrigen Endpunkte unter /api/zeiten
    eigen = w["client"](db, zeiten_router.router, role="buero_auftrag", employee_id=ada.id).get("/api/zeiten/urlaubskonto?jahr=2027").json()
    assert [k["name"] for k in eigen["konten"]] == ["Ada Monteurin"]
    ohne = w["client"](db, zeiten_router.router, role="buero_auftrag").get("/api/zeiten/urlaubskonto?jahr=2027").json()
    assert ohne["konten"] == []
    assert w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/urlaubskonto?jahr=2026").status_code == 422
    assert w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/urlaubskonto").json()["jahr"] == 2027  # Vorgabe: frühestens 2027
