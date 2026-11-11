"""Version 1.9.316 (Lohn L2b, Punkt 4): das Urlaubskonto auf den Seiten.

    danach Rest   beim Stellen und beim Genehmigen dieselbe Rechnung: Rest des Kontos minus die Tage dieses Urlaubs (andere offene Anträge zählen nicht
                  mit) -- „5 Urlaubstage · danach Rest 24,5 Tage“; über den Jahreswechsel je Jahr; vor 2027 nichts. GET /api/absence-requests/rest-danach
                  für die eigene Person, Admin und Büro – Finanzen für jede; an jedem offenen Antrag auf Urlaub in „Prüfen“ und „Abwesenheiten“
    Zeiten        Abwesenheiten: Karte „Urlaubskonto“ mit Jahr (Jahre vom Server) und „Inaktive ausblenden“ (Vorgabe an, eigener Schlüssel)
    Meine Zeiten  nur das eigene Konto (Schlüssel „urlaub“ -- „urlaubskonto“ enthielte „skonto“, verboten in der Datengrenze)
    Einstellungen Block „Urlaub und Startwerte“: Spalte „Rest 2027“
Stehende Uhr 10.11.2026 (fester_tag): das laufende Jahr der Konten ist 2027.
"""

import json
import re
from datetime import date
from decimal import Decimal

import pytest

from app.models import EmployeeAbsence, EmployeeAbsenceRequest, LohnStartwert
from app.routers import absence_requests as antraege_router
from app.routers import time_backoffice as backoffice_router
from app.routers import zeiten as zeiten_router
from app.urlaubskonto import rest_danach
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee

D = Decimal
R = "/api/absence-requests/rest-danach"


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    ada, bo = make_employee(db, "M-1", "Ada", "Monteurin"), make_employee(db, "M-2", "Bo", "Monteur")
    db.add(LohnStartwert(employee_id=ada.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.add(EmployeeAbsence(employee_id=ada.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 1, 4), end_date=date(2027, 1, 8)))
    db.commit()
    return {"db": db, "ada": ada, "bo": bo, "client": router_test_client}


def test_rest_danach(w):
    db, ada = w["db"], w["ada"]
    d = rest_danach(db, ada.id, date(2027, 4, 12), date(2027, 4, 16))  # Rest 30 + 4,5 − 5 = 29,5; minus 5
    assert (d["tage"], d["tage_text"], d["text"], d["jahre"]) == (D("5"), "5 Urlaubstage", "danach Rest 24,5 Tage",
                                                                   [{"jahr": 2027, "tage": D("5"), "rest_danach": D("24.5")}])
    assert rest_danach(db, ada.id, date(2027, 4, 12), date(2027, 4, 12), halber_tag=True)["tage_text"] == "0,5 Urlaubstage"
    assert rest_danach(db, ada.id, date(2027, 4, 12), date(2027, 4, 12))["tage_text"] == "1 Urlaubstag"
    # über den Jahreswechsel: Mo 27.–Do 30.12. und Silvester (Vorschlag ganzer Urlaubstag) = 5; Mo 03.–Fr 07.01.2028 = 5 (Neujahr Feiertag)
    d = rest_danach(db, ada.id, date(2027, 12, 27), date(2028, 1, 7))
    assert d["text"] == "danach Rest 2027: 24,5 Tage · 2028: 25 Tage" and d["tage"] == D("10")
    assert rest_danach(db, ada.id, date(2026, 12, 1), date(2026, 12, 4)) is None  # vor 2027 kein Konto
    # andere offene Anträge zählen nicht mit
    db.add(EmployeeAbsenceRequest(employee_id=ada.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 5, 3),
                                  end_date=date(2027, 5, 7), status="pending"))
    db.commit()
    assert rest_danach(db, ada.id, date(2027, 4, 12), date(2027, 4, 16))["text"] == "danach Rest 24,5 Tage"


def test_rest_danach_schnittstelle_rechte(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    q = f"&von=2027-04-12&bis=2027-04-16"
    eigen = w["client"](db, antraege_router.router, role="field", employee_id=ada.id)
    assert eigen.get(f"{R}?employee_id={ada.id}{q}").json()["text"] == "danach Rest 24,5 Tage"
    assert eigen.get(f"{R}?employee_id={bo.id}{q}").status_code == 403
    fin = w["client"](db, antraege_router.router, role="buero_finanzen")
    assert fin.get(f"{R}?employee_id={bo.id}{q}").json()["text"] == "danach Rest 25 Tage"
    assert fin.get(f"{R}?employee_id={bo.id}&von=2027-04-16&bis=2027-04-12").status_code == 422
    assert fin.get(f"{R}?employee_id=999999{q}").status_code == 404
    assert fin.get(f"{R}?employee_id={bo.id}&von=2026-12-01&bis=2026-12-04").json() is None


def test_an_offenen_antraegen(w):
    db, ada, bo = w["db"], w["ada"], w["bo"]
    for e, kat, von, bis, status in ((bo, "urlaub", date(2027, 4, 12), date(2027, 4, 16), "pending"), (bo, "krankheit", date(2027, 5, 3), date(2027, 5, 3), "pending"),
                                     (ada, "urlaub", date(2027, 6, 7), date(2027, 6, 7), "approved")):
        db.add(EmployeeAbsenceRequest(employee_id=e.id, absence_type=kat.capitalize(), absence_category=kat, start_date=von, end_date=bis, status=status))
    db.commit()
    c = w["client"](db, zeiten_router.router, role="admin")
    abw = {(a["employee_id"], a["absence_category"], a["status"]): a["rest_danach"] for a in c.get("/api/zeiten/abwesenheiten").json()["antraege"]}
    assert abw == {(bo.id, "urlaub", "pending"): "danach Rest 25 Tage", (bo.id, "krankheit", "pending"): None, (ada.id, "urlaub", "approved"): None}
    assert {(a["absence_category"], a["rest_danach"]) for a in c.get("/api/zeiten/pruefen").json()["antraege"]} == {
        ("urlaub", "danach Rest 25 Tage"), ("krankheit", None)}


def test_jahre_meine_zeiten_und_rest_2027(w):
    db, ada = w["db"], w["ada"]
    assert w["client"](db, zeiten_router.router, role="admin").get("/api/zeiten/urlaubskonto").json()["jahre"] == [2027, 2028]
    from app.meine_zeiten import meine_zeiten
    eigen = meine_zeiten(db, ada.id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))
    assert "urlaubskonto" not in eigen and (eigen["urlaub"]["jahr"], eigen["urlaub"]["rest"], eigen["urlaub"]["employee_id"]) == (2027, D("29.5"), ada.id)
    bo_eigen = meine_zeiten(db, w["bo"].id, monat=date(2026, 11, 1), heute=date(2026, 11, 10))["urlaub"]  # nur das eigene, auch für die zweite Person
    assert (bo_eigen["employee_id"], bo_eigen["rest"]) == (w["bo"].id, D("30.0"))
    k = w["client"](db, backoffice_router.router, role="buero_finanzen").get("/api/time-backoffice/konten").json()
    assert {p["employee_name"]: p["rest_erstes_jahr"] for p in k["personen"]} == {"Ada Monteurin": "29.5", "Bo Monteur": "30.0"}


# --- Seiten ---------------------------------------------------------------------------------------------------------------------------------

def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _baustein(name: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


DOM = ("var EL={};function feld(id){return EL[id]||(EL[id]={id:id,value:'',checked:false,hidden:false,textContent:'',innerHTML:''})}"
       "var el=feld,document={getElementById:feld};var SPEICHER={};var localStorage={getItem(k){return k in SPEICHER?SPEICHER[k]:null},setItem(k,v){SPEICHER[k]=v}};"
       "function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}")
KONTO = {"employee_id": 1, "name": "Ada Monteurin", "active": True, "jahr": 2027, "anspruch": 30.0, "anspruch_vorgabe": True, "uebertrag": 4.5,
         "genehmigt": 5.0, "vorbei": 0.0, "kuenftig": 5.0, "beantragt": 5.0, "rest": 29.5, "rest_nach_antraegen": 24.5, "hinweise": ["Anspruch prüfen"]}


def _zeiten(ablauf: str, vorweg: str = ""):
    text = vj.eigene_skripte("zeiten.html").text
    konst = re.search(r"var UK=null,UK_JAHR=null,UK_INAKTIVE='[^']+';", text)[0]
    js = (_baustein("_zahl.html") + "\n" + _baustein("_auswahl.html") + "\n" + DOM + "\n" + konst + vorweg + "\n"
          + "\n".join(_funktion(text, f) for f in ("ukInaktiveVersteckt", "urlaubskontoZeichnen", "ukZeile"))
          + f"\nprocess.stdout.write(JSON.stringify((()=>{{{ablauf}}})()));")
    return node_ausfuehren(js)


def test_zeiten_karte_mit_inaktiven():
    alt = dict(KONTO, employee_id=2, name="Ute Ehemalig", active=False, hinweise=[])
    d = {"jahr": 2027, "jahre": [2027, 2028], "konten": [KONTO, alt]}
    ablauf = (f"var d={json.dumps(d)};urlaubskontoZeichnen(d);var a=[EL.ukZeilen.innerHTML,EL.ukInaktivZahl.textContent,EL.ukInaktive.checked,EL.ukJahr.innerHTML];"
              "SPEICHER[UK_INAKTIVE]='zeigen';urlaubskontoZeichnen(d);a.push(EL.ukZeilen.innerHTML);return a")
    html, zahl, haken, jahre, alle = _zeiten(ablauf)
    assert (zahl, haken) == ("1 inaktiv", True) and "Ute" not in html and 'value="2027" selected' in jahre and 'value="2028"' in jahre
    assert ('<td><span>Ada Monteurin</span><span class="uk-hinweis">Anspruch prüfen</span></td><td class="r num">30 <span class="mut">(Vorgabe)</span></td>'
            '<td class="r num">4,5</td><td class="r num">5</td><td class="r num">0</td><td class="r num">5</td><td class="r num">5</td>'
            '<td class="r num"><b>29,5</b></td><td class="r num">24,5</td>') in html
    assert '<tr class="uk-zeile inaktiv" data-uk="2"><td><span>Ute Ehemalig</span>' in alle


def test_meine_zeiten_eigenes_konto():
    text = vj.eigene_skripte("mobil_zeiten.html").text
    js = (_baustein("_zahl.html") + "\n" + DOM + "\n" + _funktion(text, "ukEigenZeichnen")
          + f"\nukEigenZeichnen({json.dumps(KONTO)});var a=[EL.ukEigen.hidden,EL.ukEigen.innerHTML];ukEigenZeichnen(null);a.push(EL.ukEigen.hidden);"
            "process.stdout.write(JSON.stringify(a));")
    sichtbar, html, ohne = node_ausfuehren(js)
    assert (sichtbar, ohne) == (False, True)
    assert html.startswith('<span class="uk-titel">Urlaub 2027</span><span>Rest</span><span class="r"><b>29,5</b></span>')
    assert '<span>Rest nach den offenen Anträgen</span><span class="r">24,5</span><span class="uk-hinweis">Anspruch prüfen</span>' in html


def test_seiten_aufbau():
    zeiten = vj.seitentext("zeiten.html")[0]
    assert '<section class="tabelle-karte" aria-labelledby="ukTitel" id="ukKarte" hidden>' in zeiten
    assert "var UK=null,UK_JAHR=null,UK_INAKTIVE='erp_urlaubskonto_inaktive';" in zeiten  # eigener Schlüssel
    assert "lesen('urlaubrest',()=>geht?api(url):Promise.resolve(null)" in zeiten  # „danach Rest“ beim Stellen, ohne Anfrage ein Lesen
    assert "(a.rest_danach?' · '+a.rest_danach:'')" in zeiten and zeiten.count("(a.rest_danach?' · '+a.rest_danach:'')") == 2  # Prüfen und Abwesenheiten
    planung = vj.seitentext("planning.html")[0]
    assert "absenceRestLaden();absenceDialog.showModal()" in planung and '<p class="feld breit klein" id="absenceRest" role="status" hidden></p>' in planung
    mobil = vj.seitentext("mobil_zeiten.html")[0]
    assert "ukEigenZeichnen(d.urlaub);" in mobil and "lesen('urlaubrest',()=>geht?api(url):Promise.resolve(null)" in mobil
    einstellungen = vj.seitentext("settings.html")[0]
    assert "<th id=\"kontenRestKopf\">Rest</th>" in einstellungen and "document.getElementById('kontenRestKopf').textContent='Rest '+konten.erstes_jahr;" in einstellungen
    assert '<td class="nw" data-rest>${esc(kontenTage(p.rest_erstes_jahr))}</td>' in einstellungen
