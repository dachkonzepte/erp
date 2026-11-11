"""Version 1.9.313 (Lohn L2b, Punkt 1; Antwort 3 des Befunds L2): die Kategorie „Sonderurlaub“.

    Kategorie     neben Urlaub, Krankheit …; anlegen wie jede andere (Antrag, Eintrag), kein halber Tag; ohne Art heißt sie „Sonderurlaub“; eine Art
                  „Sonderurlaub“ passt nur noch zu ihr, eine selbst angelegte Art („Hochzeit“) zu jeder Kategorie. Zählt nicht gegen das Urlaubskonto
                  (das Urlaubskonto zählt nur „urlaub“, Punkt 3).
    Zuordnung     eine Zeile „Kategorie Sonderurlaub“, leer (die Lohnart nennt das Steuerbüro): nicht in der Lohndatei, unter „Nicht in der Datei“
                  „ohne Kennzeichen in der Zuordnung“; mit Kennzeichen in der Datei
    Prüfen        „Vor dem Abschluss“ nennt je Kategorie ohne Zuordnung die Tage („Sonderurlaub ohne Zuordnung: 2 Tage nicht in der Lohndatei“, ohne Namen) --
                  nicht Unbezahlt und Freizeitausgleich (bewusst leer), nicht bei Export-Umfang „nichts“; sperrt nichts (Entscheidung 11.11.2026)
    Seiten        jede Auswahl der Kategorie und jede Liste ihrer Namen kennt jede Kategorie (Wächter gegen eine vergessene Stelle); Einstellungen →
                  Abwesenheitsarten nennt je Art die Kategorie vom Server
Stehende Uhr 10.11.2026 (fester_tag).
"""

import re
from datetime import date
from decimal import Decimal

import pytest

from app.absence_requests import ABSENCE_CATEGORIES, ABSENCE_CATEGORY_LABELS, art_kategorien, ist_widerspruch, kategorien_text
from app.lohnarten import liste, speichern
from app.lohndatei import OHNE_KENNZEICHEN, berechnen, ohne_zuordnung
from app.models import EmployeeAbsence, EmployeePayrollSettings, TimeTrackingSettings
from app.option_settings import get_option_group
from app.routers import absence_requests as antraege_router
from app.routers import zeiten as zeiten_router
from app.zeiten import vor_dem_abschluss
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee

NOV = date(2026, 11, 1)


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    tom = make_employee(db, "M-2", "Tom", "Monteur")
    for e, pnr in ((mia, "00091"), (tom, "00092")):
        e.employee_group = "gewerblich"
        db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=pnr, export_umfang="alles", payroll_export_enabled=True))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer = "1234567", "12345"
    db.commit()
    return {"db": db, "mia": mia, "tom": tom, "client": router_test_client}


def abwesend(w, e, von, bis, kategorie, art):
    w["db"].add(EmployeeAbsence(employee_id=e.id, absence_type=art, absence_category=kategorie, start_date=von, end_date=bis))
    w["db"].commit()


# --- Kategorie und Art --------------------------------------------------------------------------------------------------------------------

def test_kategorie_und_art():
    assert ABSENCE_CATEGORIES.index("sonderurlaub") == ABSENCE_CATEGORIES.index("urlaub") + 1 and ABSENCE_CATEGORY_LABELS["sonderurlaub"] == "Sonderurlaub"
    assert art_kategorien("Sonderurlaub") == ("sonderurlaub",)
    assert ist_widerspruch("urlaub", "Sonderurlaub") and not ist_widerspruch("sonderurlaub", "Sonderurlaub")
    assert not ist_widerspruch("sonderurlaub", "Hochzeit") and not ist_widerspruch("sonderurlaub", "Sonstiges")  # selbst angelegt: jede Kategorie
    assert ist_widerspruch("sonderurlaub", "Urlaub")
    assert (kategorien_text(art_kategorien("Hochzeit")), kategorien_text(art_kategorien("Urlaub")), kategorien_text(art_kategorien("Berufsschule"))) == (
        "jede Kategorie", "Urlaub", "Fortbildung")


def test_antrag_ohne_art_und_ohne_halben_tag(w):
    c = w["client"](w["db"], antraege_router.router, role="admin", employee_id=w["mia"].id)
    r = c.post("/api/absence-requests", json={"employee_id": w["mia"].id, "absence_category": "sonderurlaub", "start_date": "2026-11-16",
                                              "end_date": "2026-11-17"})
    assert r.status_code == 200, r.text
    assert (r.json()["absence_category"], r.json()["absence_type"]) == ("sonderurlaub", "Sonderurlaub")
    r = c.post("/api/absence-requests", json={"employee_id": w["mia"].id, "absence_category": "sonderurlaub", "start_date": "2026-11-23",
                                              "end_date": "2026-11-23", "halber_tag": True})
    assert r.status_code == 422 and "nur bei Urlaub" in r.text
    r = c.post("/api/absence-requests", json={"employee_id": w["mia"].id, "absence_category": "urlaub", "absence_type": "Sonderurlaub",
                                              "start_date": "2026-11-24", "end_date": "2026-11-24"})
    assert r.status_code == 422 and "passt nicht zur Kategorie" in r.text


def test_arten_mit_kategorie_auch_inaktive(w):
    db = w["db"]
    gruppe = get_option_group(db, "absence_types")
    from app.models import SettingOption
    db.add(SettingOption(group_id=gruppe.id, value="Hochzeit", label="Hochzeit", sort_order=900, active=False))
    db.commit()
    c = w["client"](db, antraege_router.router, role="buero_finanzen")
    aktiv = {a["value"]: a["kategorien_text"] for a in c.get("/api/absence-requests/arten").json()}
    alle = {a["value"]: a["kategorien_text"] for a in c.get("/api/absence-requests/arten?alle=true").json()}
    assert "Hochzeit" not in aktiv and alle["Hochzeit"] == "jede Kategorie"


# --- Lohndatei und „Vor dem Abschluss“ ----------------------------------------------------------------------------------------------------

def test_ohne_zuordnung_nicht_in_der_datei_und_vor_dem_abschluss(w):
    db, mia, tom = w["db"], w["mia"], w["tom"]
    zeile = next(z for z in liste(db) if z["schluessel"] == "kategorie:sonderurlaub")
    assert (zeile["bezeichnung"], zeile["kennzeichen"], zeile["wirkt"]) == ("Kategorie Sonderurlaub", None, "nicht exportiert")
    abwesend(w, mia, date(2026, 11, 16), date(2026, 11, 17), "sonderurlaub", "Hochzeit")  # Mo, Di
    abwesend(w, tom, date(2026, 11, 18), date(2026, 11, 18), "sonderurlaub", "Sonderurlaub")
    abwesend(w, tom, date(2026, 11, 19), date(2026, 11, 20), "unbezahlt", "Unbezahlt")  # bewusst leer: nicht genannt
    personen = {p.employee_id: p for p in berechnen(db, NOV)}
    assert not personen[mia.id].zeilen  # nichts in der Datei
    assert [(n["was"], n["grund"], len(n["tage"])) for n in personen[mia.id].nicht] == [("Sonderurlaub (Hochzeit)", OHNE_KENNZEICHEN, 2)]
    assert ohne_zuordnung(list(personen.values())) == [
        {"art": "zuordnung", "kategorie": "sonderurlaub", "text": "Sonderurlaub ohne Zuordnung: 3 Tage nicht in der Lohndatei"}]
    assert [x for x in vor_dem_abschluss(db, NOV) if x["art"] == "zuordnung"] == [
        {"art": "zuordnung", "text": "Sonderurlaub ohne Zuordnung: 3 Tage nicht in der Lohndatei"}]
    # „Prüfen“ (auch Büro – Auftrag): ohne Namen
    daten = w["client"](db, zeiten_router.router, role="buero_auftrag").get("/api/zeiten/pruefen").json()
    zuordnung = [x for x in daten["vor_dem_abschluss"] if x["art"] == "zuordnung"]
    assert [x["text"] for x in zuordnung] == ["Sonderurlaub ohne Zuordnung: 3 Tage nicht in der Lohndatei"]
    assert "Mia" not in zuordnung[0]["text"] and "Tom" not in zuordnung[0]["text"]
    # mit Kennzeichen: in der Datei, keine Meldung mehr
    speichern(db, "kategorie:sonderurlaub", "SU", None, False)
    personen = {p.employee_id: p for p in berechnen(db, NOV)}
    assert [(z.tag, z.kennzeichen, z.lohnart, z.stunden) for z in personen[mia.id].zeilen] == [
        (date(2026, 11, 16), "SU", None, Decimal("8.00")), (date(2026, 11, 17), "SU", None, Decimal("8.00"))]
    assert ohne_zuordnung(list(personen.values())) == []
    assert [x for x in vor_dem_abschluss(db, NOV) if x["art"] == "zuordnung"] == []


def test_umfang_nichts_und_ein_tag(w):
    db, mia, tom = w["db"], w["mia"], w["tom"]
    db.query(EmployeePayrollSettings).filter_by(employee_id=tom.id).one().export_umfang = "nichts"
    db.commit()
    abwesend(w, tom, date(2026, 11, 16), date(2026, 11, 17), "sonderurlaub", "Sonderurlaub")
    assert ohne_zuordnung(berechnen(db, NOV)) == []  # wer nicht exportiert wird, zählt nicht
    abwesend(w, mia, date(2026, 11, 18), date(2026, 11, 18), "sonderurlaub", "Sonderurlaub")
    assert [x["text"] for x in ohne_zuordnung(berechnen(db, NOV))] == ["Sonderurlaub ohne Zuordnung: 1 Tag nicht in der Lohndatei"]


def test_auch_eine_andere_kategorie_ohne_zuordnung(w):
    """Die Meldung gilt jeder Kategorie ohne Kennzeichen (außer Unbezahlt und Freizeitausgleich) -- z. B. Fortbildung, wenn die Zuordnung leer ist."""
    db, mia = w["db"], w["mia"]
    abwesend(w, mia, date(2026, 11, 16), date(2026, 11, 16), "fortbildung", "Seminar")
    abwesend(w, mia, date(2026, 11, 17), date(2026, 11, 17), "freizeitausgleich", "Freizeitausgleich")
    assert [x["text"] for x in ohne_zuordnung(berechnen(db, NOV))] == ["Fortbildung ohne Zuordnung: 1 Tag nicht in der Lohndatei"]


# --- Seiten --------------------------------------------------------------------------------------------------------------------------------

AUSWAHL = {"mobil_zeiten.html": r'<select id="adKategorie">(.*?)</select>', "zeiten.html": r'<select id="adKategorie">(.*?)</select>',
           "planning.html": r'<select id="absenceCategory">(.*?)</select>'}
NAMEN = {"mobil_zeiten.html": r"var KATEGORIE=\{(.*?)\}", "zeiten.html": r"var KATEGORIE=\{(.*?)\}",
         "planning.html": r"const ABSENCE_CATEGORY_LABELS=\{(.*?)\}"}


@pytest.mark.parametrize("vorlage", sorted(AUSWAHL))
def test_jede_seite_kennt_jede_kategorie(vorlage):
    """Wächter: eine neue Kategorie in app/absence_requests.py fehlt in keiner Auswahl und keiner Liste der Namen (Schlechtwetter wählt man dort nicht --
    es hat einen eigenen Weg)."""
    text = (vj.TEMPLATES / vorlage).read_text(encoding="utf-8")
    optionen = re.findall(r'<option value="(\w+)">([^<]+)</option>', re.search(AUSWAHL[vorlage], text, re.S)[1])
    assert optionen == [(k, ABSENCE_CATEGORY_LABELS[k]) for k in ABSENCE_CATEGORIES if k != "schlechtwetter"]
    namen = dict(re.findall(r"(\w+):'([^']+)'", re.search(NAMEN[vorlage], text)[1]))
    assert {k: namen.get(k) for k in ABSENCE_CATEGORIES} == {k: ABSENCE_CATEGORY_LABELS[k] for k in ABSENCE_CATEGORIES}


def test_einstellungen_nennen_die_kategorie_vom_server():
    text = vj.seitentext("settings.html")[0]
    assert "lade('Abwesenheitsarten','abwesenheitsarten','/api/absence-requests/arten?alle=true',[],d=>{artenKategorien=d;renderTimeList()})" in text
    assert "<div class=\"muted small\" data-art-kategorie>Kategorie: ${esc(artKategorieText(o))}</div>" in text
    assert "if(g.group_key==='absence_types')await ladeArtenKategorien();" in text


def test_sperrt_nichts(w):
    """Eine Kategorie ohne Zuordnung sperrt weder den Abschluss noch die Lohndatei -- sie geht nur nicht hinein (Entscheidung 11.11.2026)."""
    from app.time_backoffice import abschluss_hindernisse, build_datev_export, datev_fehlt
    db, mia = w["db"], w["mia"]
    abwesend(w, mia, date(2026, 11, 16), date(2026, 11, 17), "sonderurlaub", "Sonderurlaub")
    ende = date(2026, 11, 30)
    assert abschluss_hindernisse(db, ende) == [] and datev_fehlt(db, NOV, ende) == []
    db.get(TimeTrackingSettings, 1).locked_until = ende
    db.commit()
    inhalt, _name = build_datev_export(db, NOV, ende)
    assert b";16;" not in inhalt and inhalt.startswith(b"1234567;12345;11/2026\r\n")
