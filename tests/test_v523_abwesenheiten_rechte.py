"""Version 1.9.101 (Stufe 4, R5b Nachrunde, Punkt 1, Entscheidung Tobias): Abwesenheiten und Anträge.

    Büro – Finanzen   sieht alle Anträge (GET /api/absence-requests; „Zeiten“: Prüfen, Abwesenheiten, Zahl am Reiter) und stellt sie auch für
                      andere (bis 1.9.100 nur die eigenen); entscheidet nicht (403)
    Admin             sieht und entscheidet alle; zieht seit 1.9.101 nur zurück, was er selbst gestellt hat
    zurückziehen      wer den Antrag gestellt hat (requested_by_user_id, app/permissions.py::darf_antrag_zurueckziehen()); ein Antrag ohne
                      diese Angabe die Person, für die er gilt -- „Meine Zeiten“ und „Zeiten“ zeigen „Zurückziehen“ nur danach
    Büro – Auftrag    nur die eigenen; für andere 403
    Vor dem Abschluss die offenen Anträge, die das Konto sieht; „Anträge entschieden“ nur, wenn wirklich keiner offen ist
Im Browser: scripts/klicktest_zeiten.py (Abwesenheiten), scripts/klicktest_meine_zeiten.py.
"""

import json
import re
from datetime import timedelta

import pytest

from app.models import AppUser, EmployeeAbsenceRequest
from app.permissions import darf_abwesenheiten_aller
from app.routers import absence_requests as absence_router
from app.routers import zeiten as zeiten_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)
from tests.test_v518_zeiten_seite import _funktion, _node, _skript, _text


@pytest.fixture
def konten(welt):  # noqa: F811
    """Konten mit ID (requested_by_user_id ist ein Fremdschlüssel): Fin (Büro – Finanzen, ohne Mitarbeiter), Anna (Admin), Tom (Monteurin-Rolle
    mit seinem Mitarbeiter), Bea (Büro – Auftrag mit Mias Mitarbeiter)."""
    db = welt["db"]
    k = {"fin": AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", active=True, password_hash="x"),
         "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", active=True, password_hash="x"),
         "tom": AppUser(username="tom", display_name="Tom Monteur", role="field", employee_id=welt["tom"].id, active=True, password_hash="x"),
         "bea": AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=welt["mia"].id, active=True, password_hash="x")}
    db.add_all(k.values()); db.commit()
    return k


def _als(w, konto):
    return w["client"](w["db"], zeiten_router.router, absence_router.router, role=konto.role, employee_id=konto.employee_id, user_id=konto.id,
                       display_name=konto.display_name)


def _antrag(w, wer, von=None, kategorie="urlaub", tage=0, status="pending"):
    tag = w["heute"] + timedelta(days=7)
    row = EmployeeAbsenceRequest(employee_id=w["tom"].id, absence_type=kategorie.capitalize(), absence_category=kategorie, start_date=tag,
                                 end_date=tag + timedelta(days=tage), status=status, requested_by_user_id=von.id if von else None)
    w["db"].add(row); w["db"].commit()
    return row


def _neu(client, w, kategorie="krankheit"):
    tag = (w["heute"] + timedelta(days=14)).isoformat()
    return client.post("/api/absence-requests", json={"employee_id": w["tom"].id, "absence_category": kategorie,
                                                      "absence_type": kategorie.capitalize(), "start_date": tag, "end_date": tag})


@pytest.mark.parametrize("rolle, alle", [("admin", True), ("buero_finanzen", True), ("buero_auftrag", False), ("field", False)])
def test_regel_je_rolle(rolle, alle):
    assert darf_abwesenheiten_aller(AppUser(username="x", role=rolle)) is alle


def test_finanzen_sieht_toms_antrag_stellt_krank_fuer_tom_und_entscheidet_nicht(welt, konten):  # noqa: F811
    """Angriff: Büro – Finanzen entscheidet Toms Antrag -> 403, zieht ihn zurück -> 403 (es hat ihn nicht gestellt). Gegenprobe: es sieht ihn
    (auch auf „Zeiten“, ohne eigenen Mitarbeiter), stellt „Krank“ für Tom und zieht genau diesen zurück. Bis 1.9.100: 403 für Tom, nur eigene."""
    tom = _antrag(welt, "tom", von=konten["tom"])
    fin = _als(welt, konten["fin"])
    assert [a["id"] for a in fin.get("/api/absence-requests").json()] == [tom.id]
    seite = fin.get("/api/zeiten/abwesenheiten").json()
    assert [(a["employee_name"], a["darf_entscheiden"], a["darf_zurueckziehen"]) for a in seite["antraege"]] == [("Tom Monteur", False, False)]
    assert (seite["hinweis"], seite["darf_beantragen"], seite["fuer_andere"], seite["offen"]) == (None, True, True, 1)
    assert "Tom Monteur" in {m["name"] for m in seite["mitarbeiter"]}
    krank = _neu(fin, welt)
    assert krank.status_code == 200, krank.text
    assert (krank.json()["requested_by_user_id"], krank.json()["darf_zurueckziehen"], krank.json()["beantragt_von"]) == (konten["fin"].id, True, "Fin Finanzen")
    assert fin.post(f"/api/absence-requests/{krank.json()['id']}/review", json={"decision": "approved"}).status_code == 403
    abgelehnt = fin.delete(f"/api/absence-requests/{tom.id}")
    assert (abgelehnt.status_code, abgelehnt.json()["detail"]) == (403, absence_router.NUR_WER_GESTELLT)
    assert fin.delete(f"/api/absence-requests/{krank.json()['id']}").status_code == 200
    welt["db"].expire_all()
    assert (welt["db"].get(EmployeeAbsenceRequest, tom.id).status, welt["db"].get(EmployeeAbsenceRequest, krank.json()["id"]).status) == \
        ("pending", "cancelled")


def test_buero_auftrag_nur_die_eigenen(welt, konten):  # noqa: F811
    """Angriff: Büro – Auftrag stellt einen Antrag für Tom -> 403, nichts angelegt; Toms Antrag sieht es nicht. Gegenprobe: für sich 200."""
    _antrag(welt, "tom", von=konten["tom"])
    bea = _als(welt, konten["bea"])
    vorher = welt["db"].query(EmployeeAbsenceRequest).count()
    antwort = _neu(bea, welt)
    assert (antwort.status_code, antwort.json()["detail"]) == (403, absence_router.NUR_EIGENE_ABWESENHEIT)
    assert welt["db"].query(EmployeeAbsenceRequest).count() == vorher
    assert bea.get("/api/absence-requests").json() == []
    seite = bea.get("/api/zeiten/abwesenheiten").json()
    assert (seite["antraege"], seite["hinweis"], seite["fuer_andere"], seite["mitarbeiter"]) == ([], zeiten_router.NUR_EIGENE_ANTRAEGE, False, [])
    tag = (welt["heute"] + timedelta(days=21)).isoformat()
    eigen = bea.post("/api/absence-requests", json={"employee_id": welt["mia"].id, "absence_category": "urlaub", "absence_type": "Urlaub",
                                                    "start_date": tag, "end_date": tag})
    assert eigen.status_code == 200 and eigen.json()["darf_zurueckziehen"] is True and eigen.json()["beantragt_von"] is None


def test_monteurin_zieht_den_antrag_des_bueros_nicht_zurueck(welt, konten):  # noqa: F811
    """Angriff: Tom zieht den Antrag zurück, den Büro – Finanzen für ihn gestellt hat -> 403. Gegenprobe: seinen eigenen -> 200; „Meine
    Zeiten“ bekommt darf_zurueckziehen und „beantragt von“."""
    vom_buero = _antrag(welt, "tom", von=konten["fin"], kategorie="krankheit")
    eigen = _antrag(welt, "tom", von=konten["tom"])
    tom = welt["client"](welt["db"], absence_router.router, role="field", employee_id=welt["tom"].id, user_id=konten["tom"].id)
    liste = {a["id"]: (a["darf_zurueckziehen"], a["beantragt_von"]) for a in tom.get("/api/absence-requests").json()}
    assert liste == {vom_buero.id: (False, "Fin Finanzen"), eigen.id: (True, None)}
    assert tom.delete(f"/api/absence-requests/{vom_buero.id}").status_code == 403
    assert tom.delete(f"/api/absence-requests/{eigen.id}").status_code == 200


def test_admin_entscheidet_und_zieht_nur_eigene_zurueck(welt, konten):  # noqa: F811
    """Angriff: der Admin zieht Toms Antrag zurück -> 403 (bis 1.9.100 erlaubt; er entscheidet ihn). Gegenprobe: seinen für Tom gestellten
    zieht er zurück, Toms entscheidet er."""
    tom = _antrag(welt, "tom", von=konten["tom"])
    admin = _als(welt, konten["anna"])
    assert admin.delete(f"/api/absence-requests/{tom.id}").status_code == 403
    eigen = _neu(admin, welt).json()
    assert eigen["darf_zurueckziehen"] is True and admin.delete(f"/api/absence-requests/{eigen['id']}").status_code == 200
    assert admin.post(f"/api/absence-requests/{tom.id}/review", json={"decision": "approved"}).status_code == 200


def test_antrag_ohne_antragsteller_zieht_die_person_zurueck(welt, konten):  # noqa: F811
    alt = _antrag(welt, "tom", von=None)
    assert _als(welt, konten["fin"]).delete(f"/api/absence-requests/{alt.id}").status_code == 403
    tom = welt["client"](welt["db"], absence_router.router, role="field", employee_id=welt["tom"].id, user_id=konten["tom"].id)
    assert tom.delete(f"/api/absence-requests/{alt.id}").status_code == 200


def test_zahl_antraege_und_vor_dem_abschluss_je_konto(welt, konten):  # noqa: F811
    """Toms offener Antrag: Büro – Finanzen sieht ihn auf „Prüfen“ (Zahl am Reiter, „1 Antrag offen“ vor dem Abschluss), Büro – Auftrag nicht
    -- aber auch nicht „Anträge entschieden“ (es ist einer offen). Nach der Entscheidung bei beiden „entschieden“."""
    tom = _antrag(welt, "tom", von=konten["tom"])
    fin = _als(welt, konten["fin"]).get("/api/zeiten/pruefen").json()
    assert ([a["id"] for a in fin["antraege"]], fin["zahlen"]["abwesenheiten"], fin["antraege_entschieden"]) == ([tom.id], 1, False)
    assert {"art": "antraege", "text": "1 Antrag offen"} in fin["vor_dem_abschluss"]
    bea = _als(welt, konten["bea"]).get("/api/zeiten/pruefen").json()
    assert (bea["antraege"], bea["zahlen"]["abwesenheiten"], bea["antraege_entschieden"]) == ([], 0, False)
    assert all(x["art"] != "antraege" for x in bea["vor_dem_abschluss"])
    assert _als(welt, konten["anna"]).post(f"/api/absence-requests/{tom.id}/review", json={"decision": "rejected"}).status_code == 200
    for konto in ("fin", "bea"):
        d = _als(welt, konten[konto]).get("/api/zeiten/pruefen").json()
        assert d["antraege_entschieden"] is True and all(x["art"] != "antraege" for x in d["vor_dem_abschluss"]), konto


@pytest.mark.parametrize("liste, entschieden, erwartet", [
    ([{"art": "laeuft", "text": "1 Zeit läuft noch"}, {"art": "antraege", "text": "1 Antrag offen"}], False, ["1 Zeit läuft noch", "1 Antrag offen"]),
    ([{"art": "laeuft", "text": "1 Zeit läuft noch"}], True, ["1 Zeit läuft noch", "✓ Anträge entschieden"]),
    ([], True, ["✓ Nichts offen – der Monat lässt sich abschließen."]),
    ([], False, ["✓ Der Monat lässt sich abschließen."])])
def test_vor_dem_abschluss_haken_nur_wenn_keiner_offen(liste, entschieden, erwartet):
    """„Anträge entschieden“ und „Nichts offen“ nur mit antraege_entschieden -- Büro – Auftrag sieht fremde Anträge nicht, bekommt dann
    „Der Monat lässt sich abschließen“ (offene Anträge sperren den Abschluss nicht)."""
    html = _node(("abschlussHtml",), f"return abschlussHtml({json.dumps({'vor_dem_abschluss': liste, 'antraege_entschieden': entschieden})})",
                 vorweg="var HAKEN='';")
    zeilen = [("✓ " if 'class="haken"' in li else "") + _text(li) for li in re.findall(r"<li.*?</li>", html)]
    assert zeilen == erwartet


def test_beantragt_von_in_der_zeile():
    vorweg = ("var KATEGORIE={krankheit:'Krankheit'};var STATUS={pending:['offen','chip-info']};function berlinZeitpunkt(w,a){return '20.10.2026'};"
              "var ZURUECK=null;var RECHTE={admin:false};var P=null;")
    antrag = {"id": 4, "employee_name": "Tom Monteur", "absence_type": "Krankheit", "absence_category": "krankheit", "start_date": "2026-11-02",
              "end_date": "2026-11-02", "arbeitstage": 1, "created_at": "2026-10-20T08:00:00", "notes": None, "review_notes": None,
              "status": "pending", "darf_entscheiden": False, "darf_zurueckziehen": True, "beantragt_von": "Fin Finanzen"}
    html = _node(("beantragtText", "abwesenheitHtml", "antragHtml"),
                 f"return [abwesenheitHtml({json.dumps(antrag)}),antragHtml({json.dumps(antrag)})]", vorweg=vorweg)
    assert all("Mo 02.11.–Mo 02.11.2026 · 1 Arbeitstag · beantragt von Fin Finanzen am 20.10." in _text(h) for h in html)


def test_meine_zeiten_zurueckziehen_nur_mit_darf_zurueckziehen():
    """„Meine Zeiten“ zeigt „Zurückziehen“ nur nach darf_zurueckziehen vom Server (bis 1.9.100 an jedem offenen Antrag) und nennt, wer ihn
    gestellt hat."""
    text = vj.eigene_skripte("mobil_zeiten.html").text
    rumpf = _funktion(text, "antraegeZeichnen")
    assert "var knoepfe=!r.darf_zurueckziehen?'':rueckfrage" in rumpf and "r.status!=='pending'" not in rumpf
    assert "'<span>beantragt von '+esc(r.beantragt_von)+'</span>'" in rumpf
    vorweg = ("var KATEGORIE={urlaub:'Urlaub'};var STATUS={pending:'Offen'};var ZURUECKZIEHEN=null;var EL={};"
              "function el(id){return EL[id]||(EL[id]={textContent:'',innerHTML:''})}"
              "function tagLang(t){return t}function esc(s){return String(s==null?'':s)}")
    zeilen = [{"id": 1, "absence_category": "urlaub", "absence_type": "Urlaub", "start_date": "2026-11-02", "end_date": "2026-11-02",
               "status": "pending", "darf_zurueckziehen": False, "beantragt_von": "Fin Finanzen"},
              {"id": 2, "absence_category": "urlaub", "absence_type": "Urlaub", "start_date": "2026-11-09", "end_date": "2026-11-09",
               "status": "pending", "darf_zurueckziehen": True, "beantragt_von": None}]
    html = node_ausfuehren(vorweg + f"var ANTRAEGE={json.dumps(zeilen)};\n" + rumpf
                           + "\nantraegeZeichnen();process.stdout.write(JSON.stringify(el('adAntraege').innerHTML));")
    erste, zweite = re.findall(r'<div class="antrag" data-antrag-zeile="\d+">.*?</div>', html)
    assert "beantragt von Fin Finanzen" in erste and "data-antrag=" not in erste
    assert 'data-antrag="fragen" data-id="2"' in zweite and "beantragt von" not in zweite
