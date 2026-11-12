"""Version 1.9.326 (Lohn L2c-1, Nachrunde, Punkt C): „DATEV bekommt keine Arbeit – Umfang prüfen“.

    wer        jede gewerbliche Person der Lohndatei des Monats, die im Monat beschäftigt ist und deren Export-Umfang nicht „alles“ ist („nur Abwesenheiten“,
               „nichts“) -- nicht kaufmännisch, nicht „alles“, nicht wer vor dem Monat ausgetreten ist
    wo         „Vor dem Abschluss“ (Reiter „Prüfen“) und „1 Prüfen“ in „Monat & Lohn“ (mit Weg zu den Lohnstammdaten), je Person „Name: DATEV bekommt keine Arbeit –
               Umfang prüfen“
    Wirkung    nur ein Hinweis: sperrt weder Abschluss noch Lohndatei, zählt nicht in „Fehlt“
Dezember 2026 wie tests/test_v626_lohndatei.py.
"""

from datetime import date

from app.models import EmployeePayrollSettings, TimeTrackingSettings
from app.time_backoffice import abschluss_hindernisse, datev_fehlt
from app.lohndatei import berechnen
from app.zeiten import UMFANG_HINWEIS, monat, umfang_hinweise, vor_dem_abschluss
from tests import vorlagen_js as vj
from tests.test_v626_lohndatei import ERSTER, LETZTER, person, w  # noqa: F401  (w ist die Fixture)


def test_wer_einen_hinweis_bekommt(w):
    db = w["db"]
    ada = person(w, "M-1", "Ada", "00091", umfang="abwesenheiten")
    bo = person(w, "M-2", "Bo", "00092", umfang="nichts")
    person(w, "M-3", "Kai", "00093", umfang="abwesenheiten", gruppe="kaufmaennisch")
    person(w, "M-4", "Cem", "00094")  # alles
    dan = person(w, "M-5", "Dan", "00095", umfang="nichts")
    db.query(EmployeePayrollSettings).filter_by(employee_id=dan.id).one().austritt = date(2026, 11, 30)  # vor dem Monat ausgetreten
    db.commit()
    eva = person(w, "M-6", "Eva", "00096", umfang="nichts", eintritt=date(2026, 12, 15))  # tritt im Monat ein
    h = umfang_hinweise(db, ERSTER, berechnen(db, ERSTER))
    assert [(x["employee_id"], x["text"]) for x in h] == [(ada.id, "Ada Test: " + UMFANG_HINWEIS), (bo.id, "Bo Test: " + UMFANG_HINWEIS),
                                                          (eva.id, "Eva Test: " + UMFANG_HINWEIS)]
    assert UMFANG_HINWEIS == "DATEV bekommt keine Arbeit – Umfang prüfen"


def test_in_vor_dem_abschluss_und_monat_sperrt_nichts(w):
    db = w["db"]
    person(w, "M-1", "Ada", "00091", umfang="abwesenheiten")
    db.get(TimeTrackingSettings, 1).locked_until = None  # offen: dann prüft abschluss_hindernisse() den ganzen Monat
    db.commit()
    texte = [(x["art"], x["text"]) for x in vor_dem_abschluss(db, ERSTER)]
    assert ("umfang", "Ada Test: " + UMFANG_HINWEIS) in texte
    m = monat(db, ERSTER)
    assert [x["text"] for x in m["umfang_hinweise"]] == ["Ada Test: " + UMFANG_HINWEIS]
    assert "umfang" not in {x["art"] for x in datev_fehlt(db, ERSTER, LETZTER, personen=berechnen(db, ERSTER))}  # sperrt die Lohndatei nicht
    assert "Umfang" not in (m["datev_text"] or "")  # zählt nicht in „Fehlt“
    assert abschluss_hindernisse(db, LETZTER) == []  # sperrt den Abschluss nicht


def test_seite():
    text = vj.seitentext("zeiten.html")[0]
    assert "(d.umfang_hinweise||[]).forEach(function(x){z.push(['offen',x.text,'Lohnstammdaten','einstellungen'])});" in text
