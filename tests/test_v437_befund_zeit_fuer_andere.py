"""Befund 1.8.142 (Fehlerrunde vor Stufe 2, Punkt 11, nur Befund): kann eine Monteurin für andere Zeit buchen?

Anlass: der Einsatzbericht zeigt einer Monteurin bei „Zeit buchen“ die Auswahl „Mitarbeiter“ mit allen aktiven Mitarbeitern.
Entscheidung des Betreibers (19.10.2026): Monteure buchen nur für sich und ihre Kolonne -- umgesetzt wird in der nächsten Runde.

Ergebnis (Ist-Stand 1.8.142, über die echte Anmeldeschranke):

- Einzelbuchung (`POST /api/time-entries`, `/start`, `PUT/DELETE /api/time-entries/{id}`, `/stop`, `GET …/active?employee_id=`):
  für jede Rolle außer Admin nur die eigene Person (`app/routers/time_tracking.py::_time_entry_employee_for_request()` -- fremde
  `employee_id` 403 „Sie dürfen nur eigene Zeiten erfassen.“; `_time_entry_can_edit()` -- fremde Buchung 403). Auch für die Kolonne
  nicht: eine Einzelbuchung für einen Kollegen derselben Kolonne lehnt der Server ebenso ab.
- Gruppenbuchung (`POST /api/time-entry-groups`, `/start`): nur als Kolonnenführerin eines aktiven Teams (`_require_crew_leader()`,
  `TeamEmployee.is_crew_leader`), nur Mitglieder dieses Teams, sie selbst dabei (`app/time_tracking.py::validate_group_members()`),
  Auftrag ihr zugeordnet. Ändern/Löschen nur, solange sie Kolonnenführerin ist (`_require_group_owner()`).
- Die Oberfläche bot mehr an, als der Server annimmt: `service_reports.html` füllte `#teEmployee` mit allen aktiven Mitarbeitern
  aus `/api/employees` (`employeeOptionsHtml(null)`), vorgewählt „— nicht zugeordnet —“; wer einen Kollegen wählte, bekam 403.
  Seit 1.8.143 behoben (Nachrunde, Punkt 1): eine Monteurin sieht keine Auswahl, sie bucht für sich; das xfail ist ein grüner Test.
- Nebenbefund: eine laufende Gruppenzeit stoppte die Initiatorin auch dann für alle, wenn sie nicht mehr Kolonnenführerin war
  (`POST /api/time-entry-groups/{id}/stop` und `POST /api/time-entries/{id}/stop` prüften nur „hat sie angelegt“; Ändern derselben
  Gruppe 403). Seit 1.8.144 gesperrt wie Ändern (Nachrunde, Punkt 2); seit 1.8.145 fragt das Speichern des Teams nach, bevor es
  jemandem das Kennzeichen nimmt, während für das Team eine Gruppenzeit läuft (Punkt 3).

Gegenprobe (Regel 24): `_time_entry_employee_for_request()` ohne die Prüfung „nur eigene“ und `_require_crew_leader()` ohne Wirkung
-- die Angriffstests wurden rot; Datei danach byte-genau zurück (Prüfsumme), siehe docs/archiv/rechtekonzept.md, "Befund 1.8.142".
"""

import re
from datetime import timedelta

import pytest

from app.berlin_time import berlin_now, berlin_today
from tests.test_v334_auswahl_restfaelle import FAKE_DOM, TEMPLATES, im_browser, nur_mit_node, seite
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order

HEUTE = berlin_today()


def _welt():
    """Kolonne Nord: Lea (Kolonnenführerin), Mia, Max. Kolonne Süd: Otto (Kolonnenführer). Ein Auftrag, Lea, Mia und Max
    zugeordnet. Eine Buchung von Max. Konten für Mia und Lea (Monteurinnen) über die echte Anmeldeschranke."""
    from app.models import AppUser, Team, TeamEmployee
    from app.routers.resource_planning import router as teams_router
    from app.routers.time_tracking import router as time_router
    from app.sitzungen import neue_sitzung
    from app.time_tracking import create_manual_entry
    from tests.anmeldung import app_mit_schranke, browser_client, neue_datenbank

    engine, make_session = neue_datenbank()
    with make_session() as db:
        emp = {name: _employee(db, f"B-{i}", name, "Test") for i, name in enumerate(("Lea", "Mia", "Max", "Otto"), 1)}
        nord, sued = Team(name="Kolonne Nord"), Team(name="Kolonne Süd")
        db.add_all([nord, sued])
        db.flush()
        for name, leiter in (("Lea", True), ("Mia", False), ("Max", False)):
            db.add(TeamEmployee(team_id=nord.id, employee_id=emp[name].id, is_crew_leader=leiter))
        db.add(TeamEmployee(team_id=sued.id, employee_id=emp["Otto"].id, is_crew_leader=True))
        db.commit()
        order, _ = _order(db, "AUF-437-0001", "P-437-0001")
        for name in ("Lea", "Mia", "Max"):
            _assign_via_team(db, order, emp[name])
        fremd = create_manual_entry(db, employee_id=emp["Max"].id, order_id=order.id, work_date=HEUTE, hours=2)
        cookies = {}
        for name in ("Mia", "Lea"):
            konto = AppUser(username=name.lower(), display_name=name, role="field", employee_id=emp[name].id, password_hash="x")
            db.add(konto)
            db.flush()
            cookies[name] = neue_sitzung(db, konto, zweiter_faktor=True)
        ada = AppUser(username="ada", display_name="Ada", role="admin", password_hash="x")  # seit 1.8.144: stoppt die Gruppe
        db.add(ada)
        db.flush()
        cookies["Ada"] = neue_sitzung(db, ada, zweiter_faktor=True)
        db.commit()
        welt = {"ids": {n: e.id for n, e in emp.items()}, "nord": nord.id, "sued": sued.id, "auftrag": order.id,
                "fremde_buchung": fremd.id, "cookies": cookies}
    welt["client"] = browser_client(app_mit_schranke(make_session, time_router, teams_router))
    welt["engine"], welt["sitzung"] = engine, make_session
    return welt


@pytest.fixture
def welt():
    w = _welt()
    yield w
    w["engine"].dispose()


def _als(welt, name):
    from app.auth import COOKIE_NAME

    welt["client"].cookies.set(COOKIE_NAME, welt["cookies"][name], domain="testserver.local")
    return welt["client"]


def _buchungen(welt):
    from app.models import TimeEntry

    with welt["sitzung"]() as db:
        return sorted((e.employee_id, float(e.hours or 0)) for e in db.query(TimeEntry).all())


def _manuell(welt, mitarbeiter, **mehr):
    return {"employee_id": mitarbeiter, "order_id": welt["auftrag"], "work_date": HEUTE.isoformat(), "hours": "3", **mehr}


# --- Angriffstest: Einzelbuchung für andere ----------------------------------------------------------------------------------

def test_monteurin_bucht_einzeln_nur_fuer_sich(welt):
    ids, vorher = welt["ids"], _buchungen(welt)
    mia = _als(welt, "Mia")
    for fremd in (ids["Max"], ids["Lea"], ids["Otto"]):  # Kolonne (Mitglied, Kolonnenführerin) und fremdes Team
        antwort = mia.post("/api/time-entries", json=_manuell(welt, fremd))
        assert antwort.status_code == 403, antwort.text
        assert antwort.json()["detail"] == "Sie dürfen nur eigene Zeiten erfassen."
        start = {"employee_id": fremd, "order_id": welt["auftrag"]}
        assert mia.post("/api/time-entries/start", json=start).status_code == 403
        assert mia.get(f"/api/time-entries/active?employee_id={fremd}").status_code == 403
    assert _buchungen(welt) == vorher

    eigen = mia.post("/api/time-entries", json=_manuell(welt, ids["Mia"]))  # Kontrolle: für sich selbst geht es
    assert eigen.status_code == 200 and eigen.json()["employee_id"] == ids["Mia"]
    # die eigene Buchung einem anderen zuschieben, fremde ändern, stoppen, löschen
    assert mia.put(f"/api/time-entries/{eigen.json()['id']}", json={"employee_id": ids["Max"]}).status_code == 403
    fremde = welt["fremde_buchung"]
    assert mia.put(f"/api/time-entries/{fremde}", json={"hours": "8"}).status_code == 403
    assert mia.post(f"/api/time-entries/{fremde}/stop", json={}).status_code == 403
    assert mia.delete(f"/api/time-entries/{fremde}").status_code == 403
    assert _buchungen(welt) == sorted(vorher + [(ids["Mia"], 3.0)])
    # sie sieht auch nur ihre eigenen Buchungen
    assert {z["employee_id"] for z in mia.get(f"/api/time-entries?employee_id={ids['Max']}").json()} == {ids["Mia"]}


# --- Angriffstest: Gruppenbuchung -----------------------------------------------------------------------------------------------

def _gruppe(welt, team, mitarbeiter):
    return {"employee_ids": mitarbeiter, "team_id": team, "order_id": welt["auftrag"], "work_date": HEUTE.isoformat(), "hours": "4"}


def test_kolonnenmitglied_ohne_kennzeichen_bucht_nicht_fuer_die_kolonne(welt):
    ids, vorher = welt["ids"], _buchungen(welt)
    mia = _als(welt, "Mia")
    antwort = mia.post("/api/time-entry-groups", json=_gruppe(welt, welt["nord"], [ids["Mia"], ids["Max"]]))
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["detail"] == "Gruppenbuchungen sind für Monteure dem Kolonnenführer des Teams vorbehalten."
    start = {"employee_ids": [ids["Mia"], ids["Max"]], "team_id": welt["nord"], "order_id": welt["auftrag"]}
    assert mia.post("/api/time-entry-groups/start", json=start).status_code == 403
    assert mia.post("/api/time-entry-groups", json=_gruppe(welt, None, [ids["Mia"], ids["Max"]])).status_code == 403
    assert _buchungen(welt) == vorher


def test_kolonnenfuehrerin_bucht_nur_fuer_ihre_kolonne(welt):
    ids, vorher = welt["ids"], _buchungen(welt)
    lea = _als(welt, "Lea")
    # außerhalb der Kolonne: fremdes Team, Nicht-Mitglied, ohne sich selbst
    assert lea.post("/api/time-entry-groups", json=_gruppe(welt, welt["sued"], [ids["Lea"], ids["Otto"]])).status_code == 403
    assert lea.post("/api/time-entry-groups", json=_gruppe(welt, welt["nord"], [ids["Lea"], ids["Otto"]])).status_code == 422
    assert lea.post("/api/time-entry-groups", json=_gruppe(welt, welt["nord"], [ids["Mia"], ids["Max"]])).status_code == 422
    assert _buchungen(welt) == vorher
    # für die eigene Kolonne geht es (Entscheidung: „für sich und ihre Kolonne“)
    antwort = lea.post("/api/time-entry-groups", json=_gruppe(welt, welt["nord"], [ids["Lea"], ids["Mia"], ids["Max"]]))
    assert antwort.status_code == 200
    assert _buchungen(welt) == sorted(vorher + [(ids["Lea"], 4.0), (ids["Mia"], 4.0), (ids["Max"], 4.0)])


def _laufend(welt):
    from app.models import TimeEntry, TimeEntryGroup

    with welt["sitzung"]() as db:
        return (sorted(e.employee_id for e in db.query(TimeEntry).filter_by(status="running")),
                sorted(g.id for g in db.query(TimeEntryGroup).filter_by(status="running")))


def _gruppe_starten(welt, stunden_her):
    ids = welt["ids"]
    start = {"employee_ids": [ids["Lea"], ids["Max"]], "team_id": welt["nord"], "order_id": welt["auftrag"],
             "started_at": (berlin_now() - timedelta(hours=stunden_her)).replace(microsecond=0).isoformat()}
    antwort = _als(welt, "Lea").post("/api/time-entry-groups/start", json=start)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["id"]


def test_ehemalige_kolonnenfuehrerin_stoppt_die_gruppe_nicht(welt):
    """Bis 1.8.143 (Nebenbefund 1.8.142): Stoppen prüfte nur „hat angelegt“, Ändern zusätzlich „noch Kolonnenführerin“. Seit 1.8.144
    gesperrt wie Ändern (Entscheidung vom 19.10.2026); ihre eigene Zeit stoppt sie weiter, wie ein Mitglied; ein Admin stoppt die Gruppe."""
    from app.models import TeamEmployee

    ids = welt["ids"]
    # Kontrolle: mit Kennzeichen stoppt sie ihre Gruppe für alle
    erste = _gruppe_starten(welt, 5)
    ende = (berlin_now() - timedelta(hours=4)).replace(microsecond=0).isoformat()
    assert _als(welt, "Lea").post(f"/api/time-entry-groups/{erste}/stop", json={"ended_at": ende}).status_code == 200
    assert _laufend(welt) == ([], [])

    gid = _gruppe_starten(welt, 2)
    with welt["sitzung"]() as db:  # das Büro nimmt Lea das Kennzeichen
        db.query(TeamEmployee).filter_by(team_id=welt["nord"], employee_id=ids["Lea"]).update({"is_crew_leader": False})
        db.commit()
    lea = _als(welt, "Lea")
    assert lea.put(f"/api/time-entry-groups/{gid}", json={"notes": "x"}).status_code == 403
    gestoppt = lea.post(f"/api/time-entry-groups/{gid}/stop", json={})
    assert gestoppt.status_code == 403, gestoppt.text
    assert gestoppt.json()["detail"] == "Gruppenbuchungen sind für Monteure dem Kolonnenführer des Teams vorbehalten."
    assert _laufend(welt) == (sorted([ids["Lea"], ids["Max"]]), [gid])

    # ihre eigene Zeit: nur sie, die Gruppe und die Zeit von Max laufen weiter
    eigene = lea.get("/api/time-entries/active").json()["id"]
    assert lea.post(f"/api/time-entries/{eigene}/stop", json={}).status_code == 200
    assert _laufend(welt) == ([ids["Max"]], [gid])

    # ein Admin stoppt die Gruppe
    admin = _als(welt, "Ada").post(f"/api/time-entry-groups/{gid}/stop", json={})
    assert admin.status_code == 200 and admin.json()["status"] == "booked", admin.text
    assert _laufend(welt) == ([], [])


# --- Kennzeichen entziehen, während eine Gruppenzeit läuft (seit 1.8.145) ------------------------------------------------------

def _nord(welt, lea_leitet=True, beschreibung=None):
    ids = welt["ids"]
    return {"team_number": None, "name": "Kolonne Nord", "description": beschreibung, "active": True, "resources": [],
            "employees": [{"employee_id": ids["Lea"], "role": None, "is_crew_leader": lea_leitet},
                          {"employee_id": ids["Mia"], "role": None, "is_crew_leader": False},
                          {"employee_id": ids["Max"], "role": None, "is_crew_leader": False}]}


def _leitet(welt):
    from app.models import TeamEmployee

    with welt["sitzung"]() as db:
        return sorted(m.employee_id for m in db.query(TeamEmployee).filter_by(team_id=welt["nord"], is_crew_leader=True))


def test_kennzeichen_entziehen_bei_laufender_gruppenzeit_fragt_nach(welt):
    """Bis 1.8.144 nahm das Speichern des Teams Lea das Kennzeichen ohne Rückfrage -- ihre laufende Gruppenzeit stoppte danach nur
    noch ein Admin (1.8.144). Seit 1.8.145: 409 mit der Rückfrage, mit Bestätigung gespeichert, gestoppt wird nichts."""
    ids, nord = welt["ids"], welt["nord"]
    gid = _gruppe_starten(welt, 2)
    ada = _als(welt, "Ada")
    # ohne Wegnahme keine Rückfrage, auch während die Gruppe läuft
    assert ada.put(f"/api/teams/{nord}", json=_nord(welt, beschreibung="Dach")).status_code == 200

    antwort = ada.put(f"/api/teams/{nord}", json=_nord(welt, lea_leitet=False))
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == {"code": "laufende_gruppenzeit", "message": "Gruppenzeit läuft noch – trotzdem entziehen?"}
    assert _leitet(welt) == [ids["Lea"]]

    bestaetigt = ada.put(f"/api/teams/{nord}?trotz_laufender_gruppenzeit=true", json=_nord(welt, lea_leitet=False))
    assert bestaetigt.status_code == 200, bestaetigt.text
    assert _leitet(welt) == []
    assert _laufend(welt) == (sorted([ids["Lea"], ids["Max"]]), [gid])  # nichts gestoppt

    # ohne laufende Gruppenzeit keine Rückfrage
    assert ada.post(f"/api/time-entry-groups/{gid}/stop", json={}).status_code == 200
    assert ada.put(f"/api/teams/{nord}", json=_nord(welt, lea_leitet=True)).status_code == 200
    assert ada.put(f"/api/teams/{nord}", json=_nord(welt, lea_leitet=False)).status_code == 200


TEAM_FETCH = r"""
  const fragen = [], puts = [];
  confirm = m => { fragen.push(m); return ANTWORT; };
  globalThis.fetch = async (url, opt = {}) => {
    puts.push((opt.method || 'GET') + ' ' + url);
    const frage = !url.includes('trotz_laufender_gruppenzeit=true');
    const status = frage ? 409 : 200;
    const body = frage ? {detail: {code: 'laufende_gruppenzeit', message: 'Gruppenzeit läuft noch – trotzdem entziehen?'}} : {id: 5};
    return {ok: !frage, status, statusText: '', headers: {get: () => 'application/json'}, json: async () => body};
  };
  _element('name').value = 'Kolonne Nord';  // Pflichtfeld (das Formular selbst zeichnet teamForm(), hier nicht gelaufen)
  await save();
  return {fragen, puts, ziel: location.href, meldung: _element('msg').textContent};
"""


@pytest.mark.parametrize("antwort", [True, False])
@nur_mit_node
def test_teamformular_fragt_vor_dem_entziehen_nach(threaded_db_session, router_test_client, antwort):
    """Das Stammdaten-Formular (vom Server gezeichnet, echtes Skript in node) fragt bei der 409 nach und speichert nur mit „OK“ erneut,
    dann mit Bestätigung; bei „Abbrechen“ bleibt es bei einer Anfrage."""
    from app.routers.pages import router as pages_router
    from tests.gerenderte_seite import gerenderte_seite

    html = router_test_client(threaded_db_session, pages_router, role="buero_auftrag").get("/master-data/teams/5/edit").text
    lauf = im_browser(gerenderte_seite(html, "init()"), f"const ANTWORT = {str(antwort).lower()};" + TEAM_FETCH)
    ergebnis = lauf["ergebnis"]
    assert ergebnis["fragen"] == ["Gruppenzeit läuft noch – trotzdem entziehen?"]
    if antwort:
        assert ergebnis["puts"] == ["PUT /api/teams/5", "PUT /api/teams/5?trotz_laufender_gruppenzeit=true"]
        assert ergebnis["ziel"] == "/master-data#teams"
    else:
        assert ergebnis["puts"] == ["PUT /api/teams/5"]
        assert (ergebnis["ziel"], ergebnis["meldung"]) == ("", "Nicht gespeichert – das Kennzeichen bleibt.")


# --- Oberfläche: Einsatzbericht als Monteurin (seit 1.8.143 umgesetzt) --------------------------------------------------------

def _einsatzbericht(threaded_db_session, router_test_client, rolle, ablauf):
    """Das echte Seitenskript in node (init()), /api/employees vom echten Dienst in der Rolle."""
    from app.routers.employees import router as employees_router

    db = threaded_db_session
    emp = {name: _employee(db, f"E-{i}", name, "Test") for i, name in enumerate(("Mia", "Max", "Otto"), 1)}
    mitarbeiter = router_test_client(db, employees_router, role=rolle).get("/api/employees").json()
    antworten = {"/api/auth/status": {"authenticated": True, "user": {"employee_id": emp["Mia"].id, "role": rolle}},
                 "/api/employees": mitarbeiter}
    bausteine = ["_debounce.html", "_time_entries_list.html", "_berlin_date.html", "_offene_bedenken.html"]  # dazu die aus seite()
    extra = "\n".join(s for d in bausteine for s in re.findall(r"<script>(.*?)</script>", (TEMPLATES / d).read_text(encoding="utf-8"), flags=re.S))
    skript = seite("service_reports.html", "\ninit();")
    skript = FAKE_DOM + re.sub(r"\{\{.*?\}\}", "1", extra) + skript[len(FAKE_DOM):]
    return im_browser(skript, ablauf, antworten)["ergebnis"], emp


AUSWAHL = "{optionen: _element('teEmployee').options.map(o => o.text), verborgen: !!_element('teEmployeeField').hidden}"


@nur_mit_node
def test_einsatzbericht_buero_behaelt_die_auswahl(threaded_db_session, router_test_client):
    """Das Büro wählt weiter aus allen aktiven Mitarbeitern (bis 1.8.142 sah die Monteurin dieselbe Auswahl)."""
    ergebnis, _ = _einsatzbericht(threaded_db_session, router_test_client, "buero_finanzen", f"await init(); return {AUSWAHL};")
    assert ergebnis == {"optionen": ["— nicht zugeordnet —", "Max Test", "Mia Test", "Otto Test"], "verborgen": False}


@nur_mit_node
def test_einsatzbericht_bietet_der_monteurin_nur_an_was_der_server_annimmt(threaded_db_session, router_test_client):
    """Bis 1.8.142 (dort xfail): alle aktiven Mitarbeiter zur Auswahl, Kollegen lehnte erst der Server ab. Seit 1.8.143 keine
    Auswahl -- fest die eigene Person, das Feld verborgen, gebucht wird für sie."""
    ergebnis, emp = _einsatzbericht(threaded_db_session, router_test_client, "field", f"""
      await init();
      const auswahl = {AUSWAHL};
      _element('teHours').value = '2';
      await saveReportTimeEntry();
      return {{...auswahl, gebucht: AUFRUFE.filter(a => a.methode === 'POST').map(a => a.body.employee_id)}};""")
    assert ergebnis == {"optionen": ["Mia Test"], "verborgen": True, "gebucht": [emp["Mia"].id]}


def test_einsatzbericht_mitarbeiterfeld_im_markup_nur_fuers_buero(threaded_db_session, router_test_client):
    """Schon das gezeichnete Markup verbirgt das Feld für die Monteurin (kein Aufblitzen, bevor das Skript läuft)."""
    from app.routers.pages import router as pages_router
    from tests.test_v264_field_time_tracking import _assign_via_team, _employee as mitarbeiter, _order

    db = threaded_db_session
    order, _ = _order(db, "AUF-437-0002", "P-437-0002")
    mia = mitarbeiter(db, "E-9", "Mia", "Test")
    _assign_via_team(db, order, mia)
    felder = {}
    for rolle in ("buero_finanzen", "field"):
        client = router_test_client(db, pages_router, role=rolle, employee_id=mia.id) if rolle == "field" else router_test_client(db, pages_router, role=rolle)
        antwort = client.get(f"/orders/{order.id}/service-reports")
        assert antwort.status_code == 200, (rolle, antwort.status_code)
        felder[rolle] = re.search(r'<div class="field" id="teEmployeeField"[^>]*>', antwort.text).group(0)
    assert "hidden" not in felder["buero_finanzen"] and felder["field"].endswith(" hidden>")
