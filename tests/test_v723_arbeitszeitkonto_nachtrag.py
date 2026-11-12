"""Version 1.9.323 (Nachtrag L2c-1, Punkt 1): die Regel des Arbeitszeitkontos nach den Antworten von Betrieb und Steuerbüro (12.11.2026).

    wie DATEV     gutgeschrieben wird, was in der Lohndatei eine Zeile hat; ein Tag ohne Zeile ist ein Minus -- Freizeitausgleich, Unbezahlt, Schlechtwetter
                  Sommer. Geprüft an der ausgelieferten Zuordnung, dazu Sonderurlaub U/8000 (trägt der Betrieb ein): je Tag mit Posten „gutgeschrieben“
                  genau dann, wenn die Lohndatei an dem Tag eine Zeile (außer Arbeit) schreibt
    Winter        Schlechtwetter Winter (WA) neutral, mit Vermerk „DATEV löst ein Guthaben selbst auf“ am Posten und als Hinweis am Konto
    Azubis        die Mehrarbeit (AA/1900) geht aufs Konto
    Sollzeit      wie bisher aus der Tagesbilanz, nach Kalenderwoche (KW 17 7,50 h, KW 18 8,00 h -- wie DATEV)
    vorläufig     die Schnittstelle sagt „vorläufig – maßgeblich ist die Lohnabrechnung“
"""

from datetime import date
from decimal import Decimal

from app.arbeitszeitkonto import VORLAEUFIG, WINTER_HINWEIS, WINTER_VERMERK, konten
from app.lohnarten import speichern
from app.lohndatei import berechnen, monat_ende
from app.routers import zeiten as zeiten_router
from tests.test_v626_lohndatei import abwesend, buchen, person, w  # noqa: F401  (w ist die Fixture)

D = Decimal


def tage(w, e, erster, heute):
    k = next(k for k in konten(w["db"], erster, monat_ende(erster), [e.id], heute=heute))
    return {t.tag: t for t in k.tage}, k


def test_gutgeschrieben_genau_mit_einer_zeile_in_der_lohndatei(w):
    db = w["db"]
    speichern(db, "kategorie:sonderurlaub", "U", "8000", False)  # die Antwort des Steuerbüros, eingetragen wie vom Betrieb
    a = person(w, "M-1", "Ada", "00095")
    for tag, kategorie, art in [(date(2027, 2, 1), "urlaub", "Urlaub"), (date(2027, 2, 2), "krankheit", "Krankheit"),
                                (date(2027, 2, 3), "sonderurlaub", "Sonderurlaub"), (date(2027, 2, 4), "fortbildung", "Weiterbildung"),
                                (date(2027, 2, 5), "fortbildung", "Berufsschule"), (date(2027, 2, 8), "unbezahlt", "Unbezahlt"),
                                (date(2027, 2, 9), "freizeitausgleich", "Freizeitausgleich"), (date(2027, 2, 10), "schlechtwetter", "Schlechtwetter"),
                                (date(2027, 5, 10), "schlechtwetter", "Schlechtwetter"), (date(2027, 5, 11), "unbezahlt", "Unbezahlt")]:
        abwesend(w, a, tag, kategorie=kategorie, art=art)
    buchen(w, a, "2.00", date(2027, 2, 10))  # Ausfall Winter 5,50
    buchen(w, a, "2.00", date(2027, 5, 10))  # Ausfall Sommer 6,00
    geprueft, abweichend = 0, []
    for erster in (date(2027, 2, 1), date(2027, 5, 1), date(2027, 12, 1)):  # dazu Himmelfahrt 06.05. (F), Heiligabend (FR) und Silvester (UU) 2027
        zeilen = {z.tag for p in berechnen(db, erster) if p.employee_id == a.id for z in p.zeilen if z.quelle not in ("arbeit", "mehrarbeit")}
        konto, _k = tage(w, a, erster, heute=date(2028, 1, 10))
        for tag, t in konto.items():
            if not t.posten:
                continue
            geprueft += 1
            gut = any(p["gutgeschrieben"] for p in t.posten)
            if gut != (tag in zeilen):
                abweichend.append((tag, [p["bezeichnung"] for p in t.posten], gut, tag in zeilen))
    assert abweichend == []
    # Februar 8 Abwesenheiten; Mai 2 Abwesenheiten und 3 Feiertage (Himmelfahrt, Pfingstmontag, Fronleichnam -- der 01.05. ist ein Samstag); Dezember
    # Heiligabend und Silvester
    assert geprueft == 15


def test_minus_ohne_zeile_und_winter_mit_vermerk(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00095", eintritt=date(2027, 2, 1))
    abwesend(w, a, date(2027, 2, 8), kategorie="unbezahlt", art="Unbezahlt")
    abwesend(w, a, date(2027, 2, 9), kategorie="freizeitausgleich", art="Freizeitausgleich")
    abwesend(w, a, date(2027, 2, 10), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "2.00", date(2027, 2, 10))
    t, k = tage(w, a, date(2027, 2, 1), heute=date(2027, 3, 1))
    assert (t[date(2027, 2, 8)].saldo, t[date(2027, 2, 9)].saldo, t[date(2027, 2, 10)].saldo) == (D("-7.50"), D("-7.50"), D("0"))
    assert t[date(2027, 2, 10)].posten == [{"bezeichnung": "Schlechtwetter Winter", "stunden": D("5.50"), "gutgeschrieben": True, "vermerk": WINTER_VERMERK}]
    assert WINTER_HINWEIS in k.hinweise
    b = person(w, "M-2", "Ben", "00096", eintritt=date(2027, 5, 3))
    abwesend(w, b, date(2027, 5, 10), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, b, "2.00", date(2027, 5, 10))
    t, k = tage(w, b, date(2027, 5, 1), heute=date(2027, 6, 1))
    assert (t[date(2027, 5, 10)].saldo, t[date(2027, 5, 10)].posten[0]["vermerk"]) == (D("-6.00"), None)  # Sommer: keine Zeile, ein Minus
    assert WINTER_HINWEIS not in k.hinweise


def test_azubi_mehrarbeit_geht_aufs_konto(w):
    db = w["db"]
    z = person(w, "M-1", "Zoe", "00097", azubi=True, eintritt=date(2027, 2, 1))
    buchen(w, z, "9.00", date(2027, 2, 1))
    zeilen = [(x.kennzeichen, x.lohnart, x.stunden) for p in berechnen(db, date(2027, 2, 1)) if p.employee_id == z.id for x in p.zeilen
              if x.tag == date(2027, 2, 1)]
    assert zeilen == [("1", "1000", D("7.50")), ("AA", "1900", D("1.50"))]
    t, _k = tage(w, z, date(2027, 2, 1), heute=date(2027, 2, 2))
    assert t[date(2027, 2, 1)].saldo == D("1.50")  # die Mehrarbeit zählt im Konto


def test_sollzeit_nach_kalenderwoche(w):
    a = person(w, "M-1", "Ada", "00095", eintritt=date(2027, 4, 26))
    t, _k = tage(w, a, date(2027, 4, 1), heute=date(2027, 5, 31))
    u, _k = tage(w, a, date(2027, 5, 1), heute=date(2027, 5, 31))
    assert (t[date(2027, 4, 30)].soll, u[date(2027, 5, 3)].soll) == (D("7.50"), D("8.00"))  # Fr 30.04. KW 17, Mo 03.05. KW 18


def test_schnittstelle_vorlaeufig(w, router_test_client):
    db = w["db"]
    person(w, "M-1", "Ada", "00095")
    d = router_test_client(db, zeiten_router.router, role="admin").get("/api/zeiten/arbeitszeitkonto").json()
    assert (d["vorlaeufig"], d["hinweis"]) == (True, "vorläufig – maßgeblich ist die Lohnabrechnung") and VORLAEUFIG == d["hinweis"]
