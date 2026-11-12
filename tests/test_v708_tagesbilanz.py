"""Version 1.9.308 (Lohn L2a, Punkt 1): die Tagesbilanz je Person und Tag (app/tagesbilanz.py::bilanz()).

    je Tag      Soll, beschäftigt, Arbeit (alle Zeitarten, 0,25 h), Fahrzeit getrennt (minutengenau) und die Arbeit ohne Fahrzeit (0,25 h), Feiertag,
                Posten: Feiertag mit Sollzeit, Kalendertag (nicht an einem Feiertag, nicht wo ein Urlaub ihn nimmt), Abwesenheit mit Kategorie, Art und
                Anteil, Schlechtwetter (Soll − Arbeit, nie unter 0)
    unabhängig  von Export-Umfang und Zuordnung (die gelten erst in der Lohndatei)
    Abfragen    eine feste Zahl, unabhängig von der Zahl der Personen, Buchungen und Abwesenheiten
    eine Regel  Abwesenheitstage und Kalendertage wie app/sollzeit.py::abwesenheit_tage() und app/arbeitszeitkalender.py::abwesenheiten()
    Lohndatei   rechnet darüber -- keine eigene Abfrage nach Buchungen oder Abwesenheiten mehr; die Dateien bleiben gleich (tests/test_v626_lohndatei.py
                und die Vorprobe September und Oktober, Bericht)
Dezember 2026 wie tests/test_v626_lohndatei.py: Tarif 7,50 h, Fr 25.12. und Sa 26.12. Feiertag, Do 24.12. Heiligabend 7,00 h, Do 31.12. Silvester.
"""

import ast
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event

from app.arbeitszeitkalender import abwesenheiten
from app.models import EmployeeAbsence
from app.sollzeit import abwesenheit_tage
from app.tagesbilanz import bilanz
from tests.test_v626_lohndatei import ERSTER, LETZTER, abwesend, buchen, person, tag, w  # noqa: F401  (w ist die Fixture)

ROOT = Path(__file__).resolve().parent.parent
D = Decimal


def _posten(t) -> list[tuple]:
    return [(x.quelle, x.stunden, x.kategorie, x.art, x.anteil) for x in t.posten]


def test_ein_tag_mit_allem(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00101")
    buchen(w, a, "5.10", tag(1))  # Baustelle
    buchen(w, a, "1.30", tag(1), art="travel", ab=13)  # Fahrzeit
    db.add(EmployeeAbsence(employee_id=a.id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(2), end_date=tag(2), halber_tag=True))
    db.commit()
    abwesend(w, a, tag(7), tag(8), kategorie="krankheit", art="Krankheit")
    abwesend(w, a, tag(9), kategorie="schlechtwetter", art="Schlechtwetter")
    buchen(w, a, "2.00", tag(9))
    abwesend(w, a, tag(30), tag(31))  # Urlaub über Silvester: ganzer Urlaubstag (leer gilt wie der Vorschlag)
    b = bilanz(db, ERSTER, LETZTER)
    t = b.tage[a.id]
    assert len(t) == 31 and a.id in {e.id for e in b.personen}
    eins = t[tag(1)]
    assert (eins.soll, eins.gebucht, eins.arbeit, eins.fahrzeit, eins.arbeit_ohne_fahrzeit) == (D("7.50"), True, D("6.50"), D("1.30"), D("5.00"))
    assert _posten(t[tag(2)]) == [("abwesenheit", D("3.75"), "urlaub", "Urlaub", D("0.5"))]
    assert _posten(t[tag(7)]) == [("abwesenheit", D("7.50"), "krankheit", "Krankheit", D("1"))]
    assert _posten(t[tag(9)]) == [("schlechtwetter", D("5.50"), "schlechtwetter", None, None)]
    assert t[tag(9)].posten[0].bezeichnung == "Schlechtwetter Winter"
    assert _posten(t[tag(24)]) == [("kalender", D("7.00"), "heiligabend", None, None)]  # Heiligabend: bezahlte Freistellung
    assert t[tag(24)].soll == D("7.00")
    assert _posten(t[tag(25)]) == [("feiertag", D("7.50"), None, None, None)] and t[tag(25)].feiertag
    assert t[tag(26)].feiertag and t[tag(26)].soll == 0 and t[tag(26)].posten == []  # Feiertag ohne Sollzeit: kein Posten
    assert _posten(t[tag(31)]) == [("abwesenheit", D("7.50"), "urlaub", "Urlaub", D("1"))]  # der Urlaub nimmt Silvester
    assert t[tag(5)].posten == [] and t[tag(5)].soll == 0 and not t[tag(5)].gebucht  # Samstag


def test_unabhaengig_von_umfang_und_zuordnung(w):
    db = w["db"]
    a = person(w, "M-1", "Ada", "00101", umfang="nichts")
    k = person(w, "M-2", "Kai", None, umfang="abwesenheiten", gruppe="kaufmaennisch")
    for e in (a, k):
        buchen(w, e, "8.00", tag(1))
        abwesend(w, e, tag(2))
    b = bilanz(db, ERSTER, LETZTER)
    for e in (a, k):
        assert (b.tage[e.id][tag(1)].arbeit, _posten(b.tage[e.id][tag(2)])) == (D("8.00"), [("abwesenheit", D("7.50"), "urlaub", "Urlaub", D("1"))])
        assert _posten(b.tage[e.id][tag(25)]) == [("feiertag", D("7.50"), None, None, None)]
    assert _posten(b.tage[a.id][tag(24)]) == [("kalender", D("7.00"), "heiligabend", None, None)]
    assert b.tage[k.id][tag(24)].posten == []  # Heiligabend gilt nur für gewerbliche Mitarbeiter (Vorgabe des Kalenders)


def test_vor_dem_eintritt_gebucht(w):
    from datetime import date
    db = w["db"]
    a = person(w, "M-1", "Ada", "00101", eintritt=date(2026, 12, 15))
    buchen(w, a, "4.00", tag(10))
    t = bilanz(db, ERSTER, LETZTER).tage[a.id][tag(10)]
    assert (t.beschaeftigt, t.soll, t.gebucht, t.arbeit) == (False, D("0.00"), True, D("4.00"))


def test_nur_genannte_personen(w):
    db = w["db"]
    a, k = person(w, "M-1", "Ada", "00101"), person(w, "M-2", "Kai", "00102")
    b = bilanz(db, ERSTER, LETZTER, [k.id])
    assert [e.id for e in b.personen] == [k.id] and set(b.tage) == {k.id}


def test_eine_feste_zahl_abfragen(w):
    db = w["db"]

    def abfragen() -> int:
        zaehler = []
        bind = db.get_bind()
        hoeren = lambda *x, **y: zaehler.append(1)  # noqa: E731
        event.listen(bind, "before_cursor_execute", hoeren)
        try:
            bilanz(db, ERSTER, LETZTER)
        finally:
            event.remove(bind, "before_cursor_execute", hoeren)
        return len(zaehler)

    def zwei_personen(n: int):
        for i in range(n, n + 2):
            e = person(w, f"M-{i}", f"P{i}", f"0009{i}")  # seit 1.9.324 erfunden (Kreis 0009x, tests/test_v724_testnummern_erfunden.py)
            buchen(w, e, "8.00", tag(1))
            buchen(w, e, "1.00", tag(2), art="travel")
            abwesend(w, e, tag(3), tag(4))
            abwesend(w, e, tag(7), kategorie="krankheit", art="Krankheit")
            abwesend(w, e, tag(9), kategorie="schlechtwetter", art="Schlechtwetter")
            abwesend(w, e, tag(30), tag(31))

    zwei_personen(1)
    db.expire_all()
    wenige = abfragen()
    zwei_personen(3)
    zwei_personen(5)
    db.expire_all()
    assert abfragen() == wenige


def test_eine_regel_fuer_abwesenheitstage_und_kalendertage(w):
    """Was die Bilanz je Abwesenheit und Kalendertag rechnet, ist genau das, was die Funktionen je Person mit eigener Abfrage liefern."""
    db = w["db"]
    a = person(w, "M-1", "Ada", "00101")
    k = person(w, "M-2", "Kai", "00102", gruppe="kaufmaennisch")
    for e in (a, k):
        abwesend(w, e, tag(21), tag(31))  # über Heiligabend, die Feiertage und Silvester
        db.add(EmployeeAbsence(employee_id=e.id, absence_type="Urlaub", absence_category="urlaub", start_date=tag(3), end_date=tag(3), halber_tag=True))
        db.commit()
    b = bilanz(db, ERSTER, LETZTER)
    for e in (a, k):
        for x in db.query(EmployeeAbsence).filter(EmployeeAbsence.employee_id == e.id):
            einzeln = abwesenheit_tage(db, e.id, x.start_date, x.end_date, kategorie=x.absence_category, halber_tag=bool(x.halber_tag),
                                       kalendertag_urlaub=x.kalendertag_urlaub)["je_tag"]
            aus_bilanz = [{"tag": t, "anteil": p.anteil, "stunden": p.stunden} for t, tg in b.tage[e.id].items() for p in tg.posten
                          if p.quelle == "abwesenheit" and x.start_date <= t <= x.end_date]
            assert aus_bilanz == einzeln
        kal = [(k_["tag"], k_["stunden"], k_["schluessel"]) for k_ in abwesenheiten(db, e.id, ERSTER, LETZTER) if k_["tag"] not in b.feiertage]
        assert [(t, p.stunden, p.kategorie) for t, tg in b.tage[e.id].items() for p in tg.posten if p.quelle == "kalender"] == kal


def test_lohndatei_fragt_nicht_selbst():
    """berechnen() liest Buchungen und Abwesenheiten nur über die Tagesbilanz."""
    baum = ast.parse((ROOT / "app/lohndatei.py").read_text(encoding="utf-8"))
    funktion = next(f for f in baum.body if isinstance(f, ast.FunctionDef) and f.name == "berechnen")
    namen = {n.id for n in ast.walk(funktion) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(funktion) if isinstance(n, ast.Attribute)}
    assert "bilanz" in namen
    assert not namen & {"TimeEntry", "EmployeeAbsence", "abwesenheit_tage", "kalender_abwesenheiten", "ausfall", "soll_fuer_personen", "arbeit_des_tags"}
