"""Version 1.9.337 (Lohn L2c-3, Punkt 4): beim Antrag auf Freizeitausgleich oder Unbezahlt „Stand vorläufig x h · danach y h“.

    Rechnung   der Stand bis gestern (vorläufig) und danach: minus, was die Tage des Antrags ab heute kosten -- je Tag Sollzeit minus Gutschrift (ein Feiertag
               kostet nichts); Tage vor heute stehen schon im Stand. Unter 0 „Plusstunden reichen nicht“ -- nur ein Hinweis. Ohne Startwert nur „Stand
               vorläufig: Startwert folgt“. Ohne Konto (nicht gewerblich, ganz vor dem Kontobeginn) nichts.
    wo         beim Stellen (GET /api/zeiten/konto-danach, Dialog unter „Zeiten“ und auf der Plantafel) und an jedem offenen Antrag beim Genehmigen (Prüfen,
               Abwesenheiten: Schlüssel konto_danach) -- nur Admin und Büro – Finanzen (wie das Konto, B11)
    Monteurin  keine Zahl: die Schnittstelle 403, ihre Anträge und „Meine Zeiten“ ohne konto_danach, die Seite fragt nicht
"""

from datetime import date
from decimal import Decimal

import pytest

from app.absence_requests import create_request
from app.arbeitszeitkonto import REICHT_NICHT, stand_danach
from app.models import EmployeePayrollSettings, LohnStartwert
from app.routers import absence_requests as antraege_router
from app.routers import field_view as field_router
from app.routers import zeiten as zeiten_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee
from tests.test_v734_konto_monat import _funktion
from tests.uhr import uhr_festhalten

HEUTE = date(2027, 1, 5)  # gezählt bis 04.01.: Neujahr neutral, der 04.01. ohne Eintrag −7,50


@pytest.fixture
def w(threaded_db_session, router_test_client):
    db = threaded_db_session
    leute = {}
    for nr, vor, gruppe, start in (("M-1", "Ada", "gewerblich", Decimal("10")), ("M-2", "Bo", "gewerblich", None), ("K-1", "Kai", "kaufmaennisch", Decimal("5"))):
        e = make_employee(db, nr, vor, "Test")
        e.employee_group = gruppe
        db.add(EmployeePayrollSettings(employee_id=e.id, export_umfang="alles", payroll_export_enabled=True, eintritt=date(2020, 1, 1)))
        if start is not None:
            db.add(LohnStartwert(employee_id=e.id, stichtag=date(2026, 12, 31), saldo_stunden=start))
        leute[vor] = e
    db.commit()
    return {"db": db, "leute": leute,
            "client": lambda rolle="buero_finanzen", employee_id=None: router_test_client(db, zeiten_router.router, antraege_router.router, field_router.router,
                                                                                           role=rolle, user_id=7, employee_id=employee_id, display_name="X")}


def test_rechnung(w):
    db, ada = w["db"], w["leute"]["Ada"]
    # Stand bis 04.01.: +10,00 − 7,50 = +2,50; Do/Fr 07.–08.01. kosten je 7,50
    s = stand_danach(db, ada.id, date(2027, 1, 7), date(2027, 1, 8), heute=HEUTE)
    assert (s["stand"], s["danach"], s["reicht_nicht"]) == (Decimal("2.50"), Decimal("-12.50"), True)
    assert s["text"] == "Stand vorläufig +2,50 h · danach -12,50 h" and s["hinweis"] == REICHT_NICHT == "Plusstunden reichen nicht"
    # der 04.01. liegt vor heute (steht schon im Stand), 05.–06.01. kosten 15,00
    assert stand_danach(db, ada.id, date(2027, 1, 4), date(2027, 1, 6), heute=HEUTE)["danach"] == Decimal("-12.50")
    # ein Feiertag kostet nichts; vor dem Kontobeginn ist der Stand der Startwert
    s = stand_danach(db, ada.id, date(2027, 1, 1), date(2027, 1, 1), heute=date(2026, 12, 20))
    assert (s["stand"], s["danach"], s["reicht_nicht"], s["hinweis"]) == (Decimal("10"), Decimal("10"), False, None)
    assert s["text"] == "Stand vorläufig +10,00 h · danach +10,00 h"


def test_ohne_startwert_und_ohne_konto(w):
    db, le = w["db"], w["leute"]
    assert stand_danach(db, le["Bo"].id, date(2027, 1, 7), date(2027, 1, 7), heute=HEUTE) == {
        "stand": None, "danach": None, "reicht_nicht": False, "text": "Stand vorläufig: Startwert folgt", "hinweis": None}
    assert stand_danach(db, le["Kai"].id, date(2027, 1, 7), date(2027, 1, 7), heute=HEUTE) is None  # kaufmännisch: kein Konto
    assert stand_danach(db, le["Ada"].id, date(2026, 12, 21), date(2026, 12, 23), heute=date(2026, 12, 1)) is None  # ganz vor dem Kontobeginn


def test_beim_stellen_nur_admin_und_finanzen(w):
    ada = w["leute"]["Ada"]
    q = {"employee_id": ada.id, "von": "2027-01-07", "bis": "2027-01-08"}
    with uhr_festhalten(tag=HEUTE):
        r = w["client"]().get("/api/zeiten/konto-danach", params=q)
        assert r.status_code == 200 and r.json()["text"] == "Stand vorläufig +2,50 h · danach -12,50 h"
        assert w["client"]("admin").get("/api/zeiten/konto-danach", params=q).status_code == 200
        assert w["client"]("buero_auftrag").get("/api/zeiten/konto-danach", params=q).status_code == 403
        assert w["client"]("field", ada.id).get("/api/zeiten/konto-danach", params=q).status_code == 403
        assert w["client"]().get("/api/zeiten/konto-danach", params={**q, "bis": "2027-01-06"}).status_code == 422


def test_beim_genehmigen_und_nie_fuer_die_monteurin(w):
    db, ada = w["db"], w["leute"]["Ada"]
    fza = create_request(db, employee_id=ada.id, absence_category="freizeitausgleich", start_date=date(2027, 1, 7), end_date=date(2027, 1, 8))
    urlaub = create_request(db, employee_id=ada.id, absence_category="urlaub", start_date=date(2027, 1, 11), end_date=date(2027, 1, 11))
    with uhr_festhalten(tag=HEUTE):
        for pfad, schluessel in (("/api/zeiten/pruefen", "antraege"), ("/api/zeiten/abwesenheiten", "antraege")):
            je = {a["id"]: a["konto_danach"] for a in w["client"]().get(pfad).json()[schluessel]}
            assert je[fza.id]["text"] == "Stand vorläufig +2,50 h · danach -12,50 h" and je[urlaub.id] is None, pfad
            bab = w["client"]("buero_auftrag", ada.id).get(pfad).json()[schluessel]  # mit Mitarbeiter: sie sieht ihre eigenen Anträge
            assert {a["id"] for a in bab} == {fza.id, urlaub.id}, pfad
            assert all(a["konto_danach"] is None for a in bab), pfad  # Büro – Auftrag sieht das Konto nicht (B11), auch nicht das eigene
        feld = w["client"]("field", ada.id)
        for pfad in ("/api/absence-requests", "/api/field-view/meine-zeiten"):
            r = feld.get(pfad)
            assert r.status_code == 200 and "konto_danach" not in r.text and "Stand vorläufig" not in r.text, pfad


def test_seite_zeiten():
    z = vj.seitentext("zeiten.html")[0]
    js = ("function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}\n" + _funktion(z, "kontoDanachZeile")
          + "\nprocess.stdout.write(JSON.stringify([kontoDanachZeile({konto_danach:null}),kontoDanachZeile({konto_danach:{text:'Stand vorläufig +2,50 h · danach -12,50 h',"
            "hinweis:'Plusstunden reichen nicht'}}),kontoDanachZeile({konto_danach:{text:'Stand vorläufig: Startwert folgt',hinweis:null}})]))")
    leer, zeile, ohne = node_ausfuehren(js)
    assert leer == "" and ohne == '<span class="zeile-unter konto-danach">Stand vorläufig: Startwert folgt</span>'
    assert zeile == ('<span class="zeile-unter konto-danach">Stand vorläufig +2,50 h · danach -12,50 h <span class="chip chip-warn">Plusstunden reichen nicht</span>'
                     '</span>')
    laden = _funktion(z, "adKontoLaden")
    assert "var geht=RECHTE.lohndaten&&!!wer&&STAND_KATEGORIEN.indexOf(el('adKategorie').value)>=0" in laden
    assert "lesen('kontodanach',()=>geht?api(url):Promise.resolve(null)" in laden
    assert "adKontoLaden();" in _funktion(z, "adRestLaden")
    assert z.count("+kontoDanachZeile(a)+") == 1 and "var konto=kontoDanachZeile(a);" in z  # in „Abwesenheiten“ und in „Prüfen“


def test_seite_plantafel_und_monteurin():
    p = vj.seitentext("planning.html")[0]
    assert "const geht=!!(board.rechte||{}).konto_stand&&!!wer&&['freizeitausgleich','unbezahlt'].indexOf(" in p
    assert "function absenceRestLaden(){absenceKontoLaden();" in p
    m = vj.seitentext("mobil_zeiten.html")[0]
    assert "konto-danach" not in m and "konto_danach" not in m and "Stand vorläufig" not in m


def test_plantafel_rechte(w):
    from types import SimpleNamespace

    from app.routers import planning as planning_router
    for rolle, erwartet in (("buero_finanzen", True), ("admin", True), ("buero_auftrag", False), ("field", False)):
        assert planning_router._tafel_rechte(w["db"], SimpleNamespace(role=rolle, employee_id=None))["konto_stand"] is erwartet, rolle
