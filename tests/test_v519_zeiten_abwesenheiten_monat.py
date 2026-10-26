"""Version 1.9.97 (Stufe 4, R5b, Punkte 5, 6 und 3): „Abwesenheiten“, „Monat & Lohn“, „Kolonne buchen“ und „Abschluss aufheben“ auf der Seite
„Zeiten“.

    Abwesenheiten  GET /api/zeiten/abwesenheiten -- der Admin sieht und entscheidet alle, sonst nur die eigenen (ohne Mitarbeiter keine, mit
                   Hinweis); beantragen der Admin für jeden, sonst nur für sich -- POST /api/absence-requests für eine andere Person 403
                   (bis 1.9.96 durfte das seit 1.9.89 auch Büro – Finanzen, ohne den Antrag danach zu sehen)
    Monat & Lohn   nur Admin und Büro – Finanzen (Reiter fehlt sonst); „Fehlt: …“ unter „Abschließen“ nur die Lücken der Zeiten, was DATEV
                   fehlt bei „DATEV-Export“; Abschließen über abschliessen() -- abgelehnt (409) die Liste auf der Seite; DATEV erst
                   abgeschlossen und vollständig; Stunden je Mitarbeiter und Zeitart mit Personalnummer
    Kopf „⋮“       „Kolonne buchen“ nur, wer bucht; „Abschluss aufheben“ nur der Admin
Im Browser: scripts/klicktest_zeiten.py.
"""

import json
import re

import pytest

from app.models import EmployeeAbsenceRequest
from app.routers import absence_requests as absence_router
from app.routers import pages as pages_router
from app.routers import zeiten as zeiten_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.test_v518_zeiten_seite import _baustein, _funktion, _skript, _text

ARBEITSTAGE = 5


def _als(w, rolle, employee_id=None):
    return w["client"](w["db"], zeiten_router.router, absence_router.router, role=rolle, employee_id=employee_id)


def _antraege(w):
    db = w["db"]
    tom = EmployeeAbsenceRequest(employee_id=w["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=w["heute"],
                                 end_date=w["heute"], status="pending")
    mia = EmployeeAbsenceRequest(employee_id=w["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=w["heute"],
                                 end_date=w["heute"], status="pending")
    db.add_all([tom, mia]); db.commit()
    return tom, mia


# --- Abwesenheiten -----------------------------------------------------------------------------------------------------------------

def test_abwesenheiten_admin_alle_und_entscheidet(welt):  # noqa: F811
    _antraege(welt)
    d = _als(welt, "admin").get("/api/zeiten/abwesenheiten").json()
    assert sorted(a["employee_name"] for a in d["antraege"]) == ["Mia Monteurin", "Tom Monteur"]
    assert {a["darf_entscheiden"] for a in d["antraege"]} == {True} and d["hinweis"] is None and d["fuer_andere"] is True
    assert d["offen"] == 2 and {"Mia Monteurin", "Tom Monteur"} <= {m["name"] for m in d["mitarbeiter"]}


def test_abwesenheiten_buero_nur_die_eigenen(welt):  # noqa: F811
    """Angriff: Büro – Finanzen (Konto = Mia) sieht Toms Antrag nicht und entscheidet nichts. Gegenprobe: den eigenen sieht es und zieht ihn
    zurück; ohne Mitarbeiter keine Anträge, der Hinweis und kein „beantragen“."""
    _antraege(welt)
    d = _als(welt, "buero_finanzen", welt["mia"].id).get("/api/zeiten/abwesenheiten").json()
    assert [(a["employee_name"], a["darf_entscheiden"], a["darf_zurueckziehen"]) for a in d["antraege"]] == [("Mia Monteurin", False, True)]
    assert d["hinweis"] == zeiten_router.NUR_EIGENE_ANTRAEGE and d["mitarbeiter"] == [] and d["darf_beantragen"] is True and d["offen"] == 1
    ohne = _als(welt, "buero_finanzen").get("/api/zeiten/abwesenheiten").json()
    assert (ohne["antraege"], ohne["darf_beantragen"], ohne["hinweis"]) == ([], False,
                                                                            "Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → Benutzer und Zugriff ändern.")


def test_abwesenheiten_status_und_rechte(welt):  # noqa: F811
    tom, _ = _antraege(welt)
    tom.status = "approved"; welt["db"].commit()
    admin = _als(welt, "admin")
    assert [a["employee_name"] for a in admin.get("/api/zeiten/abwesenheiten", params={"status": "approved"}).json()["antraege"]] == ["Tom Monteur"]
    assert admin.get("/api/zeiten/abwesenheiten", params={"status": "erledigt"}).status_code == 422
    assert _als(welt, "field", welt["tom"].id).get("/api/zeiten/abwesenheiten").status_code == 403


@pytest.mark.parametrize("rolle, eigen, fuer, erwartet", [
    ("buero_finanzen", "mia", "tom", 403), ("buero_finanzen", "mia", "mia", 200), ("buero_auftrag", "mia", "mia", 200),
    ("buero_finanzen", None, "tom", 403), ("admin", None, "tom", 200)])
def test_antrag_fuer_andere_nur_der_admin(welt, rolle, eigen, fuer, erwartet):  # noqa: F811
    """Angriff: Büro – Finanzen beantragt für Tom (bis 1.9.96 angenommen) -> 403. Gegenprobe: für sich 200, der Admin für Tom 200."""
    client = _als(welt, rolle, welt[eigen].id if eigen else None)
    antwort = client.post("/api/absence-requests", json={"employee_id": welt[fuer].id, "absence_category": "urlaub", "absence_type": "Urlaub",
                                                         "start_date": welt["heute"].isoformat(), "end_date": welt["heute"].isoformat()})
    assert antwort.status_code == erwartet, antwort.text
    if erwartet == 403:
        assert welt["db"].query(EmployeeAbsenceRequest).count() == 0


# --- Seite: Reiter und Menü je Rolle ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle, monat, kolonne, aufheben", [
    ("buero_auftrag", False, False, False), ("buero_finanzen", True, True, False), ("admin", True, True, True)])
def test_reiter_und_menue_je_rolle(threaded_db_session, router_test_client, rolle, monat, kolonne, aufheben):
    """Angriff: Büro – Auftrag hat keinen Reiter „Monat & Lohn“ (und keinen Inhalt dazu), kein „Kolonne buchen“; „Abschluss aufheben“ nur
    der Admin. Gegenprobe: Büro – Finanzen und Admin."""
    html = router_test_client(threaded_db_session, pages_router.router, role=rolle).get("/zeiten").text
    assert ('data-reiter="monat"' in html, 'id="reiter-monat"' in html) == (monat, monat)
    assert 'data-reiter="abwesenheiten"' in html
    assert ('id="kolonneBuchen"' in html, 'id="abschlussAufheben"' in html) == (kolonne, aufheben)


# --- Seite: Monat & Lohn ---------------------------------------------------------------------------------------------------------

MONAT = {"monat": "2026-10", "titel": "Oktober 2026", "start": "2026-10-01", "ende": "2026-10-31", "status": "offen", "abgeschlossen_bis": "2026-09-30",
         "luecken": [{"art": "laeuft", "text": "Ole Offen: Zeit läuft seit 16.10.2026, 15:30"}, {"art": "pause", "text": "Mia, 10.10.2026: …"}],
         "luecken_text": "1 laufende Zeit, 1 Pause", "antraege_offen": 0,
         "datev_fehlt": [{"art": "personalnummer", "text": "Personalnummer fehlt: Ole Offen"}, {"art": "lohnart", "text": "Lohnart fehlt: Fahrzeit"},
                         {"art": "datev_nummern", "text": "Beraternummer und Mandantennummer fehlen"}],
         "datev_text": "1 Personalnummer, 1 Lohnart, DATEV-Nummern",
         "spalten": [{"key": "site", "label": "Baustelle"}, {"key": "travel", "label": "Fahrzeit"}, {"key": "workshop", "label": "Werkstatt"},
                     {"key": "weather", "label": "Schlechtwetter"}],
         "zeilen": [{"employee_id": 1, "name": "Mia Monteurin", "personalnummer": "1001", "lohnexport": True, "tage": 20,
                     "stunden": {"site": 142.75, "travel": 14.25, "workshop": 11.5, "weather": 0, "other": 0}, "zusammen": 168.5},
                    {"employee_id": 3, "name": "Ole Offen", "personalnummer": None, "lohnexport": True, "tage": 10,
                     "stunden": {"site": 73.5, "travel": 8.5, "workshop": 0, "weather": 0, "other": 0}, "zusammen": 82}],
         "summe": {"stunden": {"site": 216.25, "travel": 22.75, "workshop": 11.5, "weather": 0, "other": 0}, "zusammen": 250.5}}

ELEMENTE = ("lohnMonat lohnStatus lohnAbgeschlossen lohnPruefen lohnAbschlussText lohnAbschliessen lohnFehlt lohnAbgelehnt lohnPdf lohnCsv "
            "lohnDatev lohnDatevGesperrt lohnDatevFehlt lohnKopf lohnZeilen lohnLeer").split()


def _monat_zeichnen(daten: dict) -> dict:
    text = _skript()
    kopf = (re.search(r"var WOCHENTAG=.*?;\n", text)[0] + re.search(r"var HAKEN='.*?';\n", text)[0])
    stubs = ("const _el={};function el(id){return _el[id]||(_el[id]={id,textContent:'',innerHTML:'',hidden:false,disabled:false,className:'',"
             "_a:{},setAttribute(k,v){this._a[k]=v},getAttribute(k){return this._a[k]}})}")
    js = (_baustein("_zahl.html") + "\n" + kopf + stubs + "\n"
          + "\n".join(_funktion(text, f) for f in ("esc", "pad2", "teile", "tagLang", "zeitraum", "monatZeichnen"))
          + f"\nmonatZeichnen({json.dumps(daten)});"
          + "process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(_el).map(([k,v])=>[k,{t:v.textContent,h:v.innerHTML,"
            "hidden:v.hidden,disabled:v.disabled,href:v._a.href||null}]))));")
    return node_ausfuehren(js)


def test_monat_fehlt_nur_luecken_der_zeiten_datev_getrennt():
    """Abweichung von der Vorlage (Vorgabe R5b, Punkt 6): „Fehlt: …“ unter „Abschließen“ nennt nur die Lücken der Zeiten; Personal-, DATEV-
    Nummern und Lohnarten stehen bei „DATEV-Export“. Mit Lücken ist „Abschließen“ gesperrt, DATEV vor dem Abschluss gesperrt."""
    e = _monat_zeichnen(MONAT)
    assert e["lohnFehlt"]["t"] == "Fehlt: 1 laufende Zeit, 1 Pause" and "Personalnummer" not in e["lohnFehlt"]["t"]
    assert e["lohnDatevFehlt"]["t"] == "Fehlt: 1 Personalnummer, 1 Lohnart, DATEV-Nummern"
    assert (e["lohnAbschliessen"]["t"], e["lohnAbschliessen"]["disabled"]) == ("Oktober 2026 abschließen", True)
    assert (e["lohnDatev"]["hidden"], e["lohnDatevGesperrt"]["hidden"]) == (True, False)
    pruefen = _text(e["lohnPruefen"]["h"])
    assert pruefen.startswith("1 Zeit läuft noch Prüfen 1 Tag mit unpassender Pause Prüfen Personalnummer fehlt: Ole Offen Personal")
    assert pruefen.endswith("Anträge entschieden")
    assert e["lohnPdf"]["href"] == "/api/time-backoffice/timesheet.pdf?start_date=2026-10-01&end_date=2026-10-31"


def test_monat_ohne_luecken_abschliessen_frei_datev_erst_abgeschlossen_und_vollstaendig():
    frei = _monat_zeichnen({**MONAT, "luecken": [], "luecken_text": ""})
    assert (frei["lohnAbschliessen"]["disabled"], frei["lohnFehlt"]["t"], frei["lohnDatev"]["hidden"]) == (False, "", True)
    zu = _monat_zeichnen({**MONAT, "luecken": [], "luecken_text": "", "status": "abgeschlossen", "abgeschlossen_bis": "2026-10-31"})
    assert zu["lohnAbschliessen"]["hidden"] is True and zu["lohnDatev"]["hidden"] is True  # DATEV fehlt noch etwas
    fertig = _monat_zeichnen({**MONAT, "luecken": [], "luecken_text": "", "status": "abgeschlossen", "abgeschlossen_bis": "2026-10-31",
                              "datev_fehlt": [], "datev_text": ""})
    assert (fertig["lohnDatev"]["hidden"], fertig["lohnDatevGesperrt"]["hidden"]) == (False, True)
    assert fertig["lohnDatev"]["href"] == "/api/time-backoffice/datev-export?start_date=2026-10-01&end_date=2026-10-31"


def test_monat_tabelle_mit_personalnummer():
    e = _monat_zeichnen(MONAT)
    assert _text(e["lohnKopf"]["h"]) == "Mitarbeiter Personalnr. Tage Baustelle Fahrzeit Werkstatt Schlechtwetter Zusammen"
    zeilen = [_text(z) for z in re.findall(r"<tr[^>]*>(.*?)</tr>", e["lohnZeilen"]["h"])]
    assert zeilen == ["Mia Monteurin 1001 20 142,75 14,25 11,50 0,00 168,50", "Ole Offen fehlt 10 73,50 8,50 0,00 0,00 82,00",
                      "Zusammen 216,25 22,75 11,50 0,00 250,50"]
    assert "timesheet.pdf?start_date=2026-10-01&amp;end_date=2026-10-31&amp;employee_id=1" in e["lohnZeilen"]["h"] or \
        "timesheet.pdf?start_date=2026-10-01&end_date=2026-10-31&employee_id=1" in e["lohnZeilen"]["h"]


def test_abschliessen_ueber_abschliessen_mit_liste():
    rumpf = _funktion(_skript(), "monatAbschliessen")
    assert "abschliessen('monat',()=>api('/api/time-backoffice/lock',{method:'PUT'" in rumpf and "speichern(" not in rumpf
    assert "(e.liste||[]).map(" in rumpf
    from tests.test_v399_abschliessen import ABSCHLIESSEND
    assert ABSCHLIESSEND[("zeiten.html", "monatAbschliessen")] == "Monat der Zeiterfassung abschließen"


# --- Seite: Abwesenheiten --------------------------------------------------------------------------------------------------------

ANTRAG = {"id": 4, "employee_name": "Tom Monteur", "absence_type": "Urlaub", "absence_category": "urlaub", "start_date": "2026-11-02",
          "end_date": "2026-11-06", "arbeitstage": 5, "created_at": "2026-10-20T08:00:00", "notes": None, "review_notes": None, "status": "pending",
          "darf_entscheiden": False, "darf_zurueckziehen": False}


def _abwesenheit(zurueck=None, **anders):
    vorweg = ("var KATEGORIE={urlaub:'Urlaub'};var STATUS={pending:['offen','chip-info']};function berlinZeitpunkt(w,a){return '20.10.2026'};"
              f"var ZURUECK={json.dumps(zurueck)};")
    text = _skript()
    js = (re.search(r"var WOCHENTAG=.*?;\n", text)[0] + vorweg + "\n"
          + "\n".join(_funktion(text, f) for f in ("esc", "pad2", "teile", "tagLang", "abwesenheitHtml"))
          + f"\nprocess.stdout.write(JSON.stringify(abwesenheitHtml({json.dumps({**ANTRAG, **anders})})));")
    return node_ausfuehren(js)


def test_antrag_knoepfe_nach_dem_server():
    """Ohne Recht keine Knöpfe; Entscheiden mit Notiz nur mit darf_entscheiden; Zurückziehen mit Rückfrage in der Zeile (kein confirm())."""
    ohne = _abwesenheit()
    assert "Tom Monteur · Urlaub Mo 02.11.–Fr 06.11.2026 · 5 Arbeitstage · beantragt am 20.10. offen" == _text(ohne) and "<button" not in ohne
    admin = _abwesenheit(darf_entscheiden=True)
    assert 'id="notiz-4"' in admin and 'data-entscheidung="approved"' in admin and 'data-entscheidung="rejected"' in admin
    eigen = _abwesenheit(darf_zurueckziehen=True)
    assert 'data-aktion="abw-fragen"' in eigen and "Antrag zurückziehen?" not in eigen
    frage = _abwesenheit(zurueck="4", darf_zurueckziehen=True)
    assert "Antrag zurückziehen?" in frage and 'data-aktion="abw-ja"' in frage and 'data-aktion="abw-nein"' in frage
