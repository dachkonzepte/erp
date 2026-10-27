"""Version 1.9.95 (Stufe 4, R5b, Punkte 1–3 und 6, Server): die Daten der Büroseite „Zeiten“ (app/zeiten.py, app/routers/zeiten.py).

    GET /api/zeiten/pruefen     Zeiten von früher, Tage mit unpassender Pause (Vorschau von „Pausen neu rechnen“), offene Anträge, der
                                Monat mit Stunden je Mitarbeiter und „Vor dem Abschluss“, Zahlen an den Reitern -- ab Büro – Auftrag
    GET /api/zeiten/buchungen   Buchungen eines Monats nach Mitarbeiter, Auftrag, Zeitart, „Summe der Auswahl“ ohne laufende Zeit
    GET /api/zeiten/monat       Abschluss, Lücken der Zeiten, was dem DATEV-Export fehlt, Stunden je Mitarbeiter und Zeitart mit
                                Personalnummer -- nur Admin und Büro – Finanzen
Was das Konto darf (darf_schliessen, darf_buchen, darf_aendern, rechte), folgt denselben Regeln wie die schreibenden Endpunkte.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.models import EmployeeAbsenceRequest, EmployeePayrollSettings, TimeEntry, TimeTrackingSettings
from app.routers import time_backoffice as time_backoffice_router
from app.routers import time_tracking as time_tracking_router
from app.routers import zeiten as zeiten_router
from app.time_backoffice import abschluss_hindernisse, backoffice_summary, build_datev_export
from app.time_tracking import create_manual_entry, delete_entry, pausen_vorschau, start_timer, stop_timer
from app.zeiten import luecken_text, monat_lesen, pruef_monat
from tests.test_v325_contract_basis import beauftragen, make_quote
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)


def _als(w, rolle="buero_finanzen", employee_id=None):
    return w["client"](w["db"], zeiten_router.router, time_tracking_router.router, time_backoffice_router.router, role=rolle,
                       employee_id=employee_id)


def _get(w, pfad, rolle="buero_finanzen", employee_id=None, **params):
    antwort = _als(w, rolle, employee_id).get(pfad, params=params)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _zeit(w, emp, von, bis, tag, order=None, art="site"):
    row = start_timer(w["db"], employee_id=emp.id, order_id=(order or w["order"]).id, entry_type=art, started_at=datetime.combine(tag, von))
    return stop_timer(w["db"], row.id, ended_at=datetime.combine(tag, bis))


def _abschluss(w, bis):
    w["db"].get(TimeTrackingSettings, 1).locked_until = bis
    w["db"].commit()


def _pause_passt_nicht(w, emp, tag):
    """07:00–12:00 und 12:00–16:15 (45 min bei der zweiten), die erste gelöscht -- abgezogen 45, nach Zeitregel 0."""
    erste = _zeit(w, emp, time(7), time(12), tag)
    zweite = _zeit(w, emp, time(12), time(16, 15), tag)
    delete_entry(w["db"], erste.id)
    return zweite


def D(wert):
    """Zahl aus einer JSON-Antwort (Decimal wird dort zur Zahl)."""
    return Decimal(str(wert))


def _monat(tag):
    return f"{tag:%Y-%m}"


# --- Rechte -------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle, pruefen, buchungen, monat", [
    ("field", 403, 403, 403), ("buero_auftrag", 200, 200, 403), ("buero_finanzen", 200, 200, 200), ("admin", 200, 200, 200)])
def test_wer_was_liest(welt, rolle, pruefen, buchungen, monat):  # noqa: F811
    """Angriff: die Monteurin liest nichts, Büro – Auftrag nicht „Monat & Lohn“. Gegenprobe: Büro – Finanzen und Admin alles."""
    client = _als(welt, rolle, employee_id=welt["mia"].id if rolle == "field" else None)
    assert [client.get(p).status_code for p in ("/api/zeiten/pruefen", "/api/zeiten/buchungen", "/api/zeiten/monat")] == [pruefen, buchungen, monat]


@pytest.mark.parametrize("rolle, erwartet", [
    ("buero_auftrag", {"zeit_buchen": False, "zeit_fuer_andere": False, "lohndaten": False, "antraege_entscheiden": False, "admin": False}),
    ("buero_finanzen", {"zeit_buchen": True, "zeit_fuer_andere": True, "lohndaten": True, "antraege_entscheiden": False, "admin": False}),
    ("admin", {"zeit_buchen": True, "zeit_fuer_andere": True, "lohndaten": True, "antraege_entscheiden": True, "admin": True})])
def test_rechte_und_knoepfe_je_rolle(welt, rolle, erwartet):  # noqa: F811
    """Angriff: Büro – Auftrag (das Konto ist Tom) bekommt an keiner Zeit ein Recht zu schließen, zu buchen oder zu ändern -- auch nicht
    an Toms eigener laufender Zeit (die Seite zeigt keine Knöpfe). Gegenprobe: Büro – Finanzen und Admin an jeder."""
    _abschluss(welt, welt["gestern"] - timedelta(days=1))
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(6, 45)))
    _pause_passt_nicht(welt, welt["mia"], welt["gestern"])
    _zeit(welt, welt["mia"], time(7), time(9), welt["heute"])
    p = _get(welt, "/api/zeiten/pruefen", rolle, employee_id=welt["tom"].id)
    b = _get(welt, "/api/zeiten/buchungen", rolle, employee_id=welt["tom"].id, monat=_monat(welt["gestern"]))
    assert p["rechte"] == erwartet == b["rechte"]
    darf = erwartet["zeit_buchen"]
    assert [z["darf_schliessen"] for z in p["offene_zeiten"]] == [darf]
    assert [t["darf_buchen"] for t in p["pausen"]] == [darf]
    assert {e["darf_aendern"] for e in b["eintraege"] if e["status"] == "booked"} == {darf}
    assert [e["darf_schliessen"] for e in b["eintraege"] if e["status"] == "running"] == [darf]


def test_im_abgeschlossenen_zeitraum_nur_der_admin(welt):  # noqa: F811
    """Angriff: Büro – Finanzen ändert keine Buchung bis „Abgeschlossen bis“ (der Endpunkt lehnt ab). Gegenprobe: der Admin."""
    _zeit(welt, welt["mia"], time(7), time(9), welt["gestern"])
    _abschluss(welt, welt["gestern"])
    for rolle, darf in (("buero_finanzen", False), ("admin", True)):
        assert [e["darf_aendern"] for e in _get(welt, "/api/zeiten/buchungen", rolle, monat=_monat(welt["gestern"]))["eintraege"]] == [darf]


def test_monat_nur_als_jjjj_mm(welt):  # noqa: F811
    assert _als(welt).get("/api/zeiten/buchungen", params={"monat": "Oktober"}).status_code == 422
    assert monat_lesen("2026-10", date(2026, 3, 1)) == date(2026, 10, 1) and monat_lesen(None, date(2026, 3, 9)) == date(2026, 3, 1)


# --- Prüfen -----------------------------------------------------------------------------------------------------------------------------

def test_pruefen_zeiten_von_frueher(welt):  # noqa: F811
    """Angriff: Toms Zeit läuft seit gestern -- unter „Zeiten von früher“ mit Beginn, Zeitart und Auftrag; Mias Zeit von heute nicht.
    Gegenprobe: Ende eingetragen (dieselbe Zahl wie die Vorschau) -> die Liste ist leer."""
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["gestern"], time(6, 45)))
    start_timer(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, started_at=datetime.combine(welt["heute"], time(7)))
    p = _get(welt, "/api/zeiten/pruefen")
    z = p["offene_zeiten"]
    assert [(x["id"], x["name"], x["seit"], x["zeitart"], x["order_number"], x["title"], x["gruppe"]) for x in z] == [
        (row.id, "Tom Monteur", f"{welt['gestern'].isoformat()}T06:45:00", "Baustellenzeit", welt["order"].order_number, "Wartung", False)]
    assert p["zahlen"]["pruefen"] == 1
    client = _als(welt)
    ende = {"ende": f"{welt['gestern'].isoformat()}T16:00", "pause_minuten": 0}
    vorschau = client.get(f"/api/time-entries/{row.id}/ende-vorschau", params=ende).json()
    gebucht = client.post(f"/api/time-entries/{row.id}/ende-nachtragen", json=ende).json()
    assert (D(vorschau["gebucht"]), vorschau["pause"]) == (D(gebucht["hours"]), gebucht["break_minutes"]) == (Decimal("8.5"), 45)
    assert _get(welt, "/api/zeiten/pruefen")["offene_zeiten"] == []


def test_pruefen_pause_passt_nicht_mit_vorschau(welt):  # noqa: F811
    """Angriff: Mias Tag gestern passt nicht -- „Pause passt nicht zum Tag“ mit der Vorschau von „Pausen neu rechnen“ je Buchung (Zeitart,
    Von–Bis, Pause und gebucht alt -> neu). Gegenprobe: genau diese Vorschau gebucht („So buchen“) -> der Tag ist weg."""
    _abschluss(welt, welt["gestern"] - timedelta(days=1))
    zweite = _pause_passt_nicht(welt, welt["mia"], welt["gestern"])
    p = _get(welt, "/api/zeiten/pruefen")
    stand = pausen_vorschau(welt["db"], welt["mia"].id, welt["gestern"])
    assert [(t["name"], t["tag"], t["abgezogen"], t["nach_zeitregel"]) for t in p["pausen"]] == [
        ("Mia Monteurin", welt["gestern"].isoformat(), 45, 0)]
    b = p["pausen"][0]["buchungen"]
    assert [(x["id"], x["zeitart"], x["von"], x["bis"], x["pause_alt"], x["pause_neu"], D(x["gebucht_alt"]), D(x["gebucht_neu"]))
            for x in b] == [(zweite.id, "Baustellenzeit", f"{welt['gestern'].isoformat()}T12:00:00", f"{welt['gestern'].isoformat()}T16:15:00",
                             45, 0, Decimal("3.5"), Decimal("4.25"))]
    assert [(x["id"], x["pause_neu"]) for x in b] == [(x["id"], x["pause_neu"]) for x in stand["buchungen"]]
    antwort = _als(welt).post("/api/time-entries/pausen-neu-rechnen", json={
        "work_date": welt["gestern"].isoformat(), "employee_id": welt["mia"].id, "buchungen": [{"id": x["id"], "pause": x["pause_neu"]} for x in b]})
    assert antwort.status_code == 200, antwort.text
    welt["db"].expire_all()
    assert (welt["db"].get(TimeEntry, zweite.id).break_minutes, welt["db"].get(TimeEntry, zweite.id).hours) == (0, Decimal("4.25"))
    assert _get(welt, "/api/zeiten/pruefen")["pausen"] == []


def test_pruefen_pausen_erst_nach_dem_abschluss(welt):  # noqa: F811
    """Angriff: ein Tag bis „Abgeschlossen bis“ erscheint nicht (er ist abgerechnet). Gegenprobe: der Tag danach."""
    _pause_passt_nicht(welt, welt["mia"], welt["gestern"])
    _abschluss(welt, welt["gestern"])
    assert _get(welt, "/api/zeiten/pruefen")["pausen"] == []
    _abschluss(welt, welt["gestern"] - timedelta(days=1))
    assert len(_get(welt, "/api/zeiten/pruefen")["pausen"]) == 1


def test_pruefen_antraege_je_konto(welt):  # noqa: F811
    """Angriff: Büro – Auftrag sieht die Anträge anderer nicht (wie GET /api/absence-requests). Gegenprobe: der Admin und seit 1.9.101 Büro –
    Finanzen alle offenen, mit Arbeitstagen; Zahl am Reiter „Abwesenheiten“ (bis 1.9.100 sah Büro – Finanzen nur die eigenen)."""
    db = welt["db"]
    montag = welt["heute"] + timedelta(days=7 - welt["heute"].weekday())
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=montag,
                                  end_date=montag + timedelta(days=4), status="pending"))
    db.add(EmployeeAbsenceRequest(employee_id=welt["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=montag,
                                  end_date=montag, status="approved"))
    db.commit()
    admin = _get(welt, "/api/zeiten/pruefen", "admin")
    assert [(a["employee_name"], a["arbeitstage"]) for a in admin["antraege"]] == [("Tom Monteur", 5)]
    assert admin["zahlen"]["abwesenheiten"] == 1
    fin = _als(welt, "buero_finanzen", employee_id=welt["mia"].id).get("/api/zeiten/pruefen").json()
    assert [a["employee_name"] for a in fin["antraege"]] == ["Tom Monteur"] and fin["zahlen"]["abwesenheiten"] == 1
    bea = _als(welt, "buero_auftrag", employee_id=welt["mia"].id).get("/api/zeiten/pruefen").json()
    assert bea["antraege"] == [] and bea["zahlen"]["abwesenheiten"] == 0


def test_pruefen_monat_und_vor_dem_abschluss(welt):  # noqa: F811
    """Der Monat rechts: Gebucht und Fahrzeit, Stunden je Mitarbeiter (eine laufende Zeit zählt nicht) -- dieselbe Summe wie die
    Übersicht; „Vor dem Abschluss“ mit den Lücken als Zahl und was dem DATEV-Export fehlt."""
    tag = welt["gestern"]
    _abschluss(welt, tag.replace(day=1) - timedelta(days=1))  # der Monat rechts ist dann der von gestern
    _zeit(welt, welt["mia"], time(7), time(12), tag)
    _zeit(welt, welt["tom"], time(6), time(7), tag, art="travel")
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(tag, time(7, 30)))
    p = _get(welt, "/api/zeiten/pruefen")
    m = p["monat"]
    assert m["monat"] == _monat(tag) == _monat(pruef_monat(welt["db"], welt["heute"]))
    uebersicht = backoffice_summary(welt["db"], tag.replace(day=1), date.fromisoformat(m["ende"]))
    assert (D(m["gebucht"]), D(m["fahrzeit"])) == (uebersicht["total_hours"], uebersicht["travel_hours"]) == (Decimal("6"), Decimal("1"))
    assert [(x["name"], x["tage"], D(x["stunden"])) for x in m["mitarbeiter"]] == [
        ("Mia Monteurin", 1, Decimal("5")), ("Tom Monteur", 1, Decimal("1"))]
    assert [x["text"] for x in p["vor_dem_abschluss"]] == [
        "1 Zeit läuft noch", "Personalnummer fehlt: Tom Monteur", "Personalnummer fehlt: Mia Monteurin", "Lohnart fehlt: Baustellenzeit",
        "Lohnart fehlt: Fahrzeit", "Beraternummer und Mandantennummer fehlen"]


def test_pruef_monat_ist_der_erste_offene(welt):  # noqa: F811
    db = welt["db"]
    _abschluss(welt, date(2026, 9, 30))
    assert pruef_monat(db, date(2026, 11, 3)) == date(2026, 10, 1)
    _abschluss(welt, date(2026, 10, 31))
    assert pruef_monat(db, date(2026, 11, 3)) == date(2026, 11, 1)
    _abschluss(welt, None)
    assert pruef_monat(db, date(2026, 11, 3)) == date(2026, 11, 1)


# --- Buchungen --------------------------------------------------------------------------------------------------------------------------

def test_filter_aendern_liste_und_summe_laufende_zaehlt_nicht(welt):  # noqa: F811
    """Angriff: eine laufende Zeit steht in der Liste, zählt aber nicht zur „Summe der Auswahl“. Gegenprobe: jeder Filter (Mitarbeiter,
    Auftrag, Zeitart) ändert Liste und Summe gleich."""
    tag = welt["gestern"]
    zweiter = beauftragen(welt["db"], make_quote(welt["db"], is_consumer=False, number="0517b"))
    _zeit(welt, welt["mia"], time(7), time(12), tag)                       # 5,00 h Baustelle A
    _zeit(welt, welt["tom"], time(6), time(7), tag, art="travel")          # 1,00 h Fahrzeit A
    _zeit(welt, welt["tom"], time(7), time(10), tag, order=zweiter)        # 3,00 h Baustelle B
    laeuft = start_timer(welt["db"], employee_id=welt["mia"].id, order_id=zweiter.id, started_at=datetime.combine(tag, time(13)))
    laeuft.hours = Decimal("2")  # selbst mit Stunden zählt eine laufende Zeit nicht (tagessumme())
    welt["db"].commit()

    def summe(**f):
        d = _get(welt, "/api/zeiten/buchungen", monat=_monat(tag), **f)
        return D(d["summe"]), len(d["eintraege"]), d["laufend"]

    assert summe() == (Decimal("9"), 4, 1)
    assert summe(mitarbeiter=welt["mia"].id) == (Decimal("5"), 2, 1)
    assert summe(mitarbeiter=welt["tom"].id) == (Decimal("4"), 2, 0)
    assert summe(auftrag=zweiter.id) == (Decimal("3"), 2, 1)
    assert summe(zeitart="travel") == (Decimal("1"), 1, 0)
    assert summe(mitarbeiter=welt["tom"].id, auftrag=welt["order"].id, zeitart="site") == (Decimal("0"), 0, 0)
    d = _get(welt, "/api/zeiten/buchungen", monat=_monat(tag))
    assert {a["id"] for a in d["filter"]["auftraege"]} == {welt["order"].id, zweiter.id}
    assert {"Mia Monteurin", "Tom Monteur"} <= {m["name"] for m in d["filter"]["mitarbeiter"]}
    assert {"site", "travel", "workshop"} <= {z["value"] for z in d["filter"]["zeitarten"]}


def test_buchungen_kennzeichen(welt):  # noqa: F811
    """Abgeschlossener Auftrag gekennzeichnet, Zeitart mit Namen, laufende Zeit von früher, Dauer ohne Uhrzeiten; ein Monat ohne Buchungen
    leer, mit Summe 0."""
    tag = welt["gestern"]
    welt["order"].status = "abgeschlossen"
    welt["db"].commit()
    create_manual_entry(welt["db"], employee_id=welt["mia"].id, order_id=welt["order"].id, work_date=tag, entry_type="workshop", hours=Decimal("6"),
                        break_minutes=30)
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(tag, time(6, 45)))
    d = _get(welt, "/api/zeiten/buchungen", monat=_monat(tag))
    zeilen = {e["employee_name"]: e for e in d["eintraege"]}
    assert (zeilen["Mia Monteurin"]["zeitart"], zeilen["Mia Monteurin"]["started_at"], zeilen["Mia Monteurin"]["auftrag_geschlossen"]) == (
        "Werkstattzeit", None, "abgeschlossen")
    assert (zeilen["Tom Monteur"]["status"], zeilen["Tom Monteur"]["laeuft_seit_frueher"]) == ("running", True)
    leer = _get(welt, "/api/zeiten/buchungen", monat="2020-01")
    assert (leer["eintraege"], D(leer["summe"]), leer["titel"], leer["vorher"], leer["nachher"]) == ([], Decimal("0"), "Januar 2020",
                                                                                                           "2019-12", "2020-02")


# --- Monat & Lohn -----------------------------------------------------------------------------------------------------------------------

def test_monat_luecken_und_datev(welt):  # noqa: F811
    """Angriff: mit laufender Zeit und unpassender Pause nennt „Monat & Lohn“ beides (dieselbe Liste wie die Ablehnung des Abschlusses),
    die Zeile „Fehlt: …“ nur diese; was DATEV fehlt, steht getrennt. Gegenprobe: ohne Lücken leer, abgeschlossen ohne Lücken."""
    tag = welt["gestern"]
    _abschluss(welt, tag.replace(day=1) - timedelta(days=1))
    row = start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(tag, time(6, 45)))
    _pause_passt_nicht(welt, welt["mia"], tag)
    m = _get(welt, "/api/zeiten/monat", monat=_monat(tag))
    ende = date.fromisoformat(m["ende"])
    assert [x["text"] for x in m["luecken"]] == [x["text"] for x in abschluss_hindernisse(welt["db"], ende)]
    assert m["luecken_text"] == "1 laufende Zeit, 1 Pause" == luecken_text(abschluss_hindernisse(welt["db"], ende))
    assert m["status"] == "offen" and "Personalnummer" not in m["luecken_text"]
    assert m["datev_text"] == "1 Personalnummer, 1 Lohnart, DATEV-Nummern"
    assert [x["art"] for x in m["datev_fehlt"]] == ["personalnummer", "lohnart", "datev_nummern"]
    _als(welt, "admin").post(f"/api/time-entries/{row.id}/ende-nachtragen", json={"ende": f"{tag.isoformat()}T07:45", "pause_minuten": 0})
    welt["db"].query(TimeEntry).filter(TimeEntry.employee_id == welt["mia"].id).delete()
    welt["db"].commit()
    m = _get(welt, "/api/zeiten/monat", monat=_monat(tag))
    assert (m["luecken"], m["luecken_text"]) == ([], "")
    _abschluss(welt, ende)
    m = _get(welt, "/api/zeiten/monat", monat=_monat(tag))
    assert (m["status"], m["luecken"], m["abgeschlossen_bis"]) == ("abgeschlossen", [], ende.isoformat())


def test_monat_tabelle_eine_rechnung_mit_dem_datev_export(welt):  # noqa: F811
    """Stunden je Mitarbeiter und Zeitart mit Personalnummer -- dieselben Zahlen wie der DATEV-Export (eine Rechnung); „Sonstige“ nur mit
    Stunden; eine Personalnummer, die fehlt, ist leer (die Seite zeigt „fehlt“)."""
    db, tag = welt["db"], welt["gestern"]
    s = db.get(TimeTrackingSettings, 1)
    s.datev_target = "lohn_gehalt"
    s.datev_wage_type_site, s.datev_wage_type_travel, s.datev_wage_type_workshop = "100", "200", "300"
    s.datev_beraternummer, s.datev_mandantennummer = "1234", "56"
    db.add_all([EmployeePayrollSettings(employee_id=welt["mia"].id, datev_personnel_number="1001", payroll_export_enabled=True),
                EmployeePayrollSettings(employee_id=welt["tom"].id, datev_personnel_number=None, payroll_export_enabled=True)])
    db.commit()
    _zeit(welt, welt["mia"], time(7), time(9, 20), tag)                    # 2,33 h
    _zeit(welt, welt["mia"], time(9, 20), time(9, 45), tag, art="travel")  # 0,42 h
    _zeit(welt, welt["tom"], time(7), time(10), tag, art="workshop")       # 3,00 h
    m = _get(welt, "/api/zeiten/monat", monat=_monat(tag))
    assert [s["label"] for s in m["spalten"]] == ["Baustelle", "Fahrzeit", "Werkstatt", "Schlechtwetter"]
    zeilen = {z["name"]: z for z in m["zeilen"]}
    mia, tom = zeilen["Mia Monteurin"], zeilen["Tom Monteur"]
    assert (mia["personalnummer"], mia["tage"], D(mia["stunden"]["site"]), D(mia["stunden"]["travel"]), D(mia["zusammen"])) == (
        "1001", 1, Decimal("2.33"), Decimal("0.42"), Decimal("2.75"))
    assert (tom["personalnummer"], D(tom["stunden"]["workshop"])) == (None, Decimal("3"))
    assert m["datev_text"] == "1 Personalnummer"
    db.get(EmployeePayrollSettings, db.query(EmployeePayrollSettings).filter_by(employee_id=welt["tom"].id).one().id).datev_personnel_number = "1002"
    db.commit()
    _abschluss(welt, date.fromisoformat(m["ende"]))
    daten, _ = build_datev_export(db, date.fromisoformat(m["start"]), date.fromisoformat(m["ende"]))
    zeilen_datei = daten.decode("utf-8-sig").splitlines()[1:]
    assert sorted(z.split(";")[3] for z in zeilen_datei) == sorted(["2,33", "0,42", "3,00"])
    create_manual_entry(db, employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=tag, entry_type="other", hours=Decimal("1"),
                        break_minutes=0)
    m = _get(welt, "/api/zeiten/monat", monat=_monat(tag))
    assert [s["label"] for s in m["spalten"]][-1] == "Sonstige"
    assert D(m["summe"]["zusammen"]) == Decimal("6.75")


def test_nur_laufende_zeit_ohne_zeile_im_monat(welt):  # noqa: F811
    """Angriff: Tom hat im Monat nur eine laufende Zeit -- er steht weder rechts auf „Prüfen“ noch in „Stunden je Mitarbeiter“ (keine Zeile
    „0 Tage, 0,00“, gefunden im Klicktest 1.9.96). Gegenprobe: Mia mit gebuchter Zeit steht in beiden."""
    tag = welt["gestern"]
    _abschluss(welt, tag.replace(day=1) - timedelta(days=1))
    _zeit(welt, welt["mia"], time(7), time(9), tag)
    start_timer(welt["db"], employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(tag, time(7)))
    assert [x["name"] for x in _get(welt, "/api/zeiten/pruefen")["monat"]["mitarbeiter"]] == ["Mia Monteurin"]
    assert [z["name"] for z in _get(welt, "/api/zeiten/monat", monat=_monat(tag))["zeilen"]] == ["Mia Monteurin"]
