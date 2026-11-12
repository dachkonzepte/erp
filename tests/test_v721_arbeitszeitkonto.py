"""Version 1.9.321 (Lohn L2c-1, Punkt 1): das Arbeitszeitkonto (app/arbeitszeitkonto.py; Befund L2c, Abschnitte 2 und 11; Antworten B1–B8, B11, B16).

    Regel       Ist = Arbeit + gutgeschriebene Posten, Saldo = Ist − Soll; gutgeschrieben alles außer Freizeitausgleich (REGEL, eine Tabelle) -- Urlaub,
                Krankheit, Feiertag, Sonderurlaub, Fortbildung, Unbezahlt, Heiligabend, Silvester, Schlechtwetter neutral; Arbeit daneben, am Samstag oder
                Sonntag ein Plus; ein betriebsfreier Tag ohne Urlaub ein Minus
    wer, wann   nur gewerbliche, nur zwischen Eintritt und Austritt, nur Tage vor heute, ab dem 01.01.2027
    Stand       Startwert (Saldo zum 31.12.2026) + Salden; „ohne Startwert“ nur, wer am Stichtag beschäftigt war
    Abfragen    eine feste Zahl
    Schnittstelle  GET /api/zeiten/arbeitszeitkonto -- nur Admin und Büro – Finanzen (auch nicht die eigene für andere Rollen), vor 2027 422
Die Beispielwoche ist die aus Abschnitt 2 des Befunds (Sommer, Sollzeit 8,00 h): −3,75 h.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import event

from app.absence_requests import ABSENCE_CATEGORIES, ABSENCE_CATEGORY_UNKNOWN
from app.arbeitszeitkonto import GUTSCHRIFT, KEINE, KONTOBEGINN, OHNE_STARTWERT, REGEL, konten
from app.models import EmployeeAbsence, EmployeePayrollSettings, LohnStartwert, PlanningHoliday
from app.routers import zeiten as zeiten_router
from app.tagesbilanz import QUELLEN
from tests.test_v626_lohndatei import abwesend, buchen, person, w  # noqa: F401  (w ist die Fixture)

D = Decimal


def konto(w, e, von, bis, heute):
    return next(k for k in konten(w["db"], von, bis, heute=heute) if k.employee_id == e.id)


def saldi(k) -> dict:
    return {t.tag: t.saldo for t in k.tage}


def test_regel_ist_eine_tabelle_fuer_jede_kategorie_und_quelle():
    erwartet = {f"abwesenheit:{k}" for k in (*ABSENCE_CATEGORIES, ABSENCE_CATEGORY_UNKNOWN) if k != "schlechtwetter"} | {q for q in QUELLEN if q != "abwesenheit"}
    assert set(REGEL) == erwartet
    assert [k for k, v in REGEL.items() if v == KEINE] == ["abwesenheit:freizeitausgleich"]  # B1, B3: nur Freizeitausgleich ist ein Minus
    assert set(REGEL.values()) == {GUTSCHRIFT, KEINE}


def test_beispielwoche(w):
    """Abschnitt 2 des Befunds: Mo +1,25, Di 0, Mi −8,00, Do 0, Fr −1,00, Sa +4,00 = −3,75 (KW 23, Sollzeit 8,00 h)."""
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091", eintritt=date(2027, 6, 7))  # vorher keine Sollzeit -- die Woche steht für sich
    buchen(w, a, "8.25", date(2027, 6, 7))
    buchen(w, a, "1.00", date(2027, 6, 7), art="travel", ab=16)  # Fahrzeit zählt wie Arbeit (Antwort 7)
    abwesend(w, a, date(2027, 6, 8))
    abwesend(w, a, date(2027, 6, 9), kategorie="freizeitausgleich", art="Freizeitausgleich")
    abwesend(w, a, date(2027, 6, 10), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "2.00", date(2027, 6, 10))
    db.add(EmployeeAbsence(employee_id=a.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 6, 11), end_date=date(2027, 6, 11),
                           halber_tag=True))
    db.commit()
    buchen(w, a, "3.00", date(2027, 6, 11))
    buchen(w, a, "4.00", date(2027, 6, 12))
    k = konto(w, a, date(2027, 6, 7), date(2027, 6, 13), heute=date(2027, 6, 14))
    assert saldi(k) == {date(2027, 6, 7): D("1.25"), date(2027, 6, 8): D("0"), date(2027, 6, 9): D("-8"), date(2027, 6, 10): D("0"),
                        date(2027, 6, 11): D("-1"), date(2027, 6, 12): D("4"), date(2027, 6, 13): D("0")}
    assert (k.stand, k.startwert, k.hinweise) == (D("-3.75"), None, [])  # Eintritt 2027: kein Startwert, kein Hinweis
    mi = next(t for t in k.tage if t.tag == date(2027, 6, 9))
    assert (mi.soll, mi.arbeit, mi.gutschrift, mi.posten) == (D("8.00"), D("0"), D("0"), [{"bezeichnung": "Freizeitausgleich", "stunden": D("8.00"),
                                                                                            "gutgeschrieben": False}])
    do = next(t for t in k.tage if t.tag == date(2027, 6, 10))
    assert (do.arbeit, do.gutschrift, do.ist) == (D("2.00"), D("6.00"), D("8.00"))  # Schlechtwetter: Ausfall 6,00 gutgeschrieben


def test_neutral_und_plus(w):
    db = w["db"]
    b = person(w, "M-2", "Ben", "00092", eintritt=date(2027, 5, 1))
    buchen(w, b, "3.00", date(2027, 5, 6))  # Christi Himmelfahrt (Do): Feiertag gutgeschrieben + Arbeit = +3
    abwesend(w, b, date(2027, 5, 18), kategorie="krankheit", art="Krankheit")
    buchen(w, b, "2.00", date(2027, 5, 18))  # Arbeit am Kranktag: +2 (B4)
    abwesend(w, b, date(2027, 5, 19), kategorie="krankheit", art="Krankheit")
    abwesend(w, b, date(2027, 5, 20), kategorie="sonderurlaub", art="Sonderurlaub")
    abwesend(w, b, date(2027, 5, 21), kategorie="fortbildung", art="Weiterbildung")
    buchen(w, b, "4.00", date(2027, 5, 23))  # Sonntag: +4
    abwesend(w, b, date(2027, 5, 24), kategorie="unbezahlt", art="Unbezahlt")  # B2: neutral
    db.add(PlanningHoliday(holiday_date=date(2027, 5, 25), name="Brückentag", active=True))  # betriebsfrei, nichts eingetragen: −8 (B5)
    db.commit()
    abwesend(w, b, date(2027, 5, 26), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, b, "9.00", date(2027, 5, 26))  # Ausfalltag mit mehr Arbeit als Sollzeit: Ausfall 0, +1
    s = saldi(konto(w, b, date(2027, 5, 6), date(2027, 5, 26), heute=date(2027, 5, 27)))
    assert {t: s[t] for t in (date(2027, 5, 6), date(2027, 5, 17), date(2027, 5, 18), date(2027, 5, 19), date(2027, 5, 20), date(2027, 5, 21),
                              date(2027, 5, 23), date(2027, 5, 24), date(2027, 5, 25), date(2027, 5, 26))} == {
        date(2027, 5, 6): D("3.00"), date(2027, 5, 17): D("0"), date(2027, 5, 18): D("2.00"), date(2027, 5, 19): D("0"), date(2027, 5, 20): D("0"),
        date(2027, 5, 21): D("0"), date(2027, 5, 23): D("4.00"), date(2027, 5, 24): D("0"), date(2027, 5, 25): D("-8.00"), date(2027, 5, 26): D("1.00")}
    # 17.05. Pfingstmontag: Feiertag neutral


def test_heiligabend_und_silvester(w):
    c = person(w, "M-3", "Cem", "00093", eintritt=date(2027, 12, 1))
    buchen(w, c, "2.00", date(2027, 12, 24))  # Heiligabend (Fr): 7,00 gutgeschrieben, Arbeit dazu
    s = saldi(konto(w, c, date(2027, 12, 24), date(2027, 12, 31), heute=date(2028, 1, 3)))
    assert (s[date(2027, 12, 24)], s[date(2027, 12, 31)]) == (D("2.00"), D("0"))  # Silvester unbezahlt frei: neutral


def test_nur_gewerbliche_und_zwischen_eintritt_und_austritt(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091", eintritt=date(2027, 3, 3))
    k = person(w, "M-2", "Kai", "00092", gruppe="kaufmaennisch", eintritt=date(2027, 3, 1))
    buchen(w, a, "8.00", date(2027, 3, 1))  # vor dem Eintritt: zählt nicht
    buchen(w, k, "8.00", date(2027, 3, 1))
    p = db.query(EmployeePayrollSettings).filter_by(employee_id=a.id).one()
    p.austritt = date(2027, 3, 4)
    db.commit()
    buchen(w, a, "8.00", date(2027, 3, 5))  # nach dem Austritt: zählt nicht
    liste = konten(db, date(2027, 3, 1), date(2027, 3, 31), heute=date(2027, 4, 1))
    assert [x.employee_id for x in liste] == [a.id]  # nur gewerbliche (B8)
    s = saldi(liste[0])
    assert (s[date(2027, 3, 1)], s[date(2027, 3, 3)], s[date(2027, 3, 4)], s[date(2027, 3, 5)]) == (D("0"), D("-7.50"), D("-7.50"), D("0"))
    assert liste[0].stand == D("-15.00")


def test_stand_ab_dem_startwert_und_nur_bis_gestern(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091", eintritt=date(2020, 1, 1))
    b = person(w, "M-2", "Bo", "00092", eintritt=date(2020, 1, 1))
    c = person(w, "M-3", "Cy", "00093", eintritt=date(2027, 2, 1))
    d = person(w, "M-4", "Dan", "00094", eintritt=date(2020, 1, 1))
    db.add(LohnStartwert(employee_id=a.id, stichtag=date(2026, 12, 31), saldo_stunden=D("12.50"), herkunft="steuerbuero"))
    db.add(LohnStartwert(employee_id=d.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("3"), saldo_stunden=None, herkunft="steuerbuero"))
    db.commit()
    # Januar 2027: Fr 01.01. Neujahr (neutral), Mo 04.–Fr 29.01. 20 Arbeitstage zu 7,50 h ohne Eintrag = −150; Februar bis gestern (Mo 01., Di 02.) −15
    ka = konto(w, a, KONTOBEGINN, date(2027, 2, 28), heute=date(2027, 2, 3))
    assert [(m.monat, m.soll, m.saldo, m.stand) for m in ka.monate] == [(date(2027, 1, 1), D("157.50"), D("-150.00"), D("-137.50")),
                                                                         (date(2027, 2, 1), D("15.00"), D("-15.00"), D("-152.50"))]
    assert (ka.startwert, ka.stand_vorher, ka.stand, ka.hinweise) == (D("12.50"), D("12.50"), D("-152.50"), [])
    assert max(t.tag for t in ka.tage) == date(2027, 2, 2)  # heute und später zählen nicht
    feb = konto(w, a, date(2027, 2, 1), date(2027, 2, 28), heute=date(2027, 2, 3))
    assert (feb.stand_vorher, feb.stand, [m.monat for m in feb.monate]) == (D("-137.50"), D("-152.50"), [date(2027, 2, 1)])
    assert konto(w, b, KONTOBEGINN, date(2027, 1, 31), heute=date(2027, 2, 3)).hinweise == [OHNE_STARTWERT]  # am Stichtag beschäftigt, kein Startwert
    assert konto(w, d, KONTOBEGINN, date(2027, 1, 31), heute=date(2027, 2, 3)).hinweise == [OHNE_STARTWERT]  # Startwert ohne Saldo
    assert konto(w, c, date(2027, 2, 1), date(2027, 2, 28), heute=date(2027, 2, 3)).hinweise == []  # Eintritt 2027 (B16)
    assert konto(w, a, date(2027, 1, 1), date(2027, 1, 31), heute=date(2026, 11, 10)).stand == D("12.50")  # vor dem Kontobeginn zählt nichts


def test_eine_feste_zahl_abfragen(w):
    db = w["db"]

    def abfragen() -> int:
        zaehler = []
        bind = db.get_bind()
        hoeren = lambda *x, **y: zaehler.append(1)  # noqa: E731
        event.listen(bind, "before_cursor_execute", hoeren)
        try:
            konten(db, date(2027, 3, 1), date(2027, 3, 31), heute=date(2027, 4, 1))
        finally:
            event.remove(bind, "before_cursor_execute", hoeren)
        return len(zaehler)

    def zwei_personen(n: int):
        for i in range(n, n + 2):
            e = person(w, f"M-{i}", f"P{i}", f"0009{i}")
            db.add(LohnStartwert(employee_id=e.id, stichtag=date(2026, 12, 31), saldo_stunden=D("1"), herkunft="steuerbuero"))
            db.commit()
            buchen(w, e, "8.00", date(2027, 3, 1))
            buchen(w, e, "1.00", date(2027, 3, 2), art="travel")
            abwesend(w, e, date(2027, 3, 3), date(2027, 3, 4))
            abwesend(w, e, date(2027, 3, 8), kategorie="freizeitausgleich", art="Freizeitausgleich")
            abwesend(w, e, date(2027, 3, 9), kategorie="schlechtwetter", art="Schlechtwetter")

    zwei_personen(1)
    db.expire_all()
    wenige = abfragen()
    zwei_personen(3)
    zwei_personen(5)
    db.expire_all()
    assert abfragen() == wenige


def test_schnittstelle(w, router_test_client):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00091")
    url = "/api/zeiten/arbeitszeitkonto"
    for rolle in ("admin", "buero_finanzen"):
        r = router_test_client(db, zeiten_router.router, role=rolle).get(url)
        assert r.status_code == 200, (rolle, r.text)
        daten = r.json()
        assert (daten["monat"], daten["kontobeginn"], [k["employee_id"] for k in daten["konten"]]) == ("2027-01", "2027-01-01", [a.id])  # Vorgabe: Januar 2027
        assert "maßgeblich" in daten["hinweis"] and "tage" in daten["konten"][0]
    for rolle in ("buero_auftrag", "field"):  # B11: nur Admin und Büro – Finanzen, auch nicht das eigene
        r = router_test_client(db, zeiten_router.router, role=rolle, employee_id=a.id).get(f"{url}?mitarbeiter={a.id}")
        assert r.status_code == 403 and r.json()["detail"] == "Das Arbeitszeitkonto sehen nur Admin und Büro – Finanzen."
    c = router_test_client(db, zeiten_router.router, role="admin")
    assert c.get(f"{url}?monat=2026-12").status_code == 422
    assert c.get(f"{url}?monat=2027-02&mitarbeiter={a.id}").json()["monat"] == "2027-02"
    assert c.get(f"{url}?monat=2027-02&mitarbeiter=999999").json()["konten"] == []
