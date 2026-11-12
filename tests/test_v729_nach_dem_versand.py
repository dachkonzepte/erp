"""Version 1.9.329 (Lohn L2c-2, Punkt 2): Liste „Nach dem Versand geändert“ in „Monat & Lohn“.

    Bezug        die als gesendet vermerkte Datei des Monats; gibt es danach eine Abgleich-Zeile, die jüngste davon -- ohne gesendete Datei keine Liste,
                 sondern „noch nichts versendet“ (auch wenn Dateien abgelegt sind)
    Vergleich    je Person und Tag die Zeilen der Datei gegen berechnen() von heute: vorher und jetzt („1/1000 8,00 h“), Monatszeilen für sich; eine
                 Person über die Personalnummer, auch über eine frühere (Nummernwechsel: eine eigene Zeile „Personalnummer alt -> neu“)
    Grund        die Einträge der Änderungshistorie seit dem Erzeugen des Bezugs: je Tag Zeitbuchung und Abwesenheit der Person, je Person die
                 Lohnstammdaten, für viele zugleich (Zuordnung, Kalender, Modell, Feiertage, Bundesland) ein Satz oben; sonst „kein Eintrag …“
    Rechte       GET /api/zeiten/nach-dem-versand -- nur Admin und Büro – Finanzen
    Seite        „Monat & Lohn“: die Karte mit Stand, Bezug, je Zeile Person, Tag, vorher -> jetzt und Grund
"""

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.audit import reset_audit_context, set_audit_context
from app.lohndatei import ablegen, berechnen, datei, versendet_setzen
from app.lohndatei_abgleich import KEIN_VERSAND, OHNE_GRUND, datei_lesen, eintrag_text, nach_dem_versand
from app.models import EmployeeAbsence, EmployeePayrollSettings, LohnartZuordnung, Lohndatei, PersonalnummerVergabe, TimeEntry, TimeTrackingSettings
from app.routers import zeiten as zeiten_router
from app.time_backoffice import lohndatei_erzeugen
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v224_field_view import make_employee
from tests.test_v325_contract_basis import beauftragen, make_quote

DEZ = date(2026, 12, 1)
URL = "/api/zeiten/nach-dem-versand"


@contextmanager
def als(name="Anna Admin", uid=1):
    token = set_audit_context(SimpleNamespace(id=uid, display_name=name), None)
    try:
        yield
    finally:
        reset_audit_context(token)


@pytest.fixture
def w(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    order = beauftragen(db, make_quote(db, is_consumer=False, number="0729"))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "1234567", "12345", date(2026, 12, 31)
    ada = make_employee(db, "M-1", "Ada", "Arbeit")
    bo = make_employee(db, "M-2", "Bo", "Bau")
    for e, nr in ((ada, "00094"), (bo, "00095")):
        db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=nr, export_umfang="alles", payroll_export_enabled=True))
    for e, tag in ((ada, 7), (ada, 8), (bo, 7)):
        db.add(TimeEntry(employee_id=e.id, project_id=order.project_id, order_id=order.id, work_date=date(2026, 12, tag), entry_type="site",
                         hours=Decimal("8"), break_minutes=0, status="booked", started_at=datetime(2026, 12, tag, 7), ended_at=datetime(2026, 12, tag, 15)))
    db.commit()

    def gesendet():
        row = lohndatei_erzeugen(db, DEZ, user_id=7, user_name="Fin Finanzen")
        versendet_setzen(db, row.id, user_id=7, user_name="Fin Finanzen")
        return row

    return {"db": db, "ada": ada, "bo": bo, "order": order, "gesendet": gesendet,
            "client": lambda rolle="buero_finanzen": router_test_client(db, zeiten_router.router, role=rolle, user_id=7, display_name="Fin Finanzen")}


def _buchung(db, emp, tag):
    return db.query(TimeEntry).filter_by(employee_id=emp.id, work_date=date(2026, 12, tag)).one()


def test_ohne_gesendete_datei_keine_liste(w):
    db = w["db"]
    assert nach_dem_versand(db, DEZ) == {"stand": "nichts_versendet", "text": KEIN_VERSAND, "bezug": None, "zeilen": [], "allgemein": [], "anzahl": 0}
    lohndatei_erzeugen(db, DEZ, user_id=7, user_name="Fin")  # abgelegt, nicht gesendet
    assert nach_dem_versand(db, DEZ)["stand"] == "nichts_versendet"
    assert KEIN_VERSAND == "Noch nichts versendet – vermerke an der Datei „An das Steuerbüro gesendet“."


def test_gleich_nach_dem_versand(w):
    row = w["gesendet"]()
    d = nach_dem_versand(w["db"], DEZ)
    assert (d["stand"], d["text"], d["zeilen"], d["anzahl"]) == ("gleich", "Keine Änderung nach dem Versand.", [], 0)
    assert d["bezug"]["id"] == row.id == d["bezug"]["gesendet_id"] and d["bezug"]["art"] == "datei"


def test_aenderung_je_tag_mit_grund(w):
    db = w["db"]
    w["gesendet"]()
    with als():
        e = _buchung(db, w["ada"], 8)
        e.hours, e.ended_at = Decimal("6"), datetime(2026, 12, 8, 13)
        db.add(EmployeeAbsence(employee_id=w["bo"].id, start_date=date(2026, 12, 21), end_date=date(2026, 12, 21), absence_type="Urlaub",
                               absence_category="urlaub"))
        db.delete(_buchung(db, w["bo"], 7))
        db.commit()
    d = nach_dem_versand(db, DEZ)
    assert d["stand"] == "geaendert" and d["text"] == "3 Änderungen nach dem Versand" and d["anzahl"] == 3
    zeilen = [(z["name"], z["personalnummer"], z["tag"], z["vorher"], z["jetzt"]) for z in d["zeilen"]]
    assert zeilen == [("Ada Arbeit", "00094", date(2026, 12, 8), ["1/1000 8,00 h"], ["1/1000 6,00 h"]),
                      ("Bo Bau", "00095", date(2026, 12, 7), ["1/1000 8,00 h"], []),
                      ("Bo Bau", "00095", date(2026, 12, 21), [], [zeilen[2][4][0]])]
    assert zeilen[2][4][0].startswith("U/") or zeilen[2][4][0].startswith("U ")
    g = [z["gruende"] for z in d["zeilen"]]
    assert len(g[0]) == 1 and g[0][0].startswith("Zeitbuchung geändert · ") and g[0][0].endswith(" · Anna Admin")
    assert g[1][0].startswith("Zeitbuchung gelöscht · ") and g[2][0].startswith("Abwesenheit angelegt · ")
    assert d["allgemein"] == []


def test_ohne_eintrag_und_allgemein(w):
    """Was die Historie nicht kennt, heißt „kein Eintrag …“; eine Änderung der Zuordnung steht als ein Satz oben."""
    db = w["db"]
    w["gesendet"]()
    db.execute(TimeEntry.__table__.update().where(TimeEntry.work_date == date(2026, 12, 7), TimeEntry.employee_id == w["ada"].id)
               .values(hours=Decimal("7")))  # an der Historie vorbei
    db.commit()
    with als("Fin Finanzen", 7):
        z = db.query(LohnartZuordnung).filter_by(schluessel="arbeit").one()
        z.lohnart = "1001"
        db.commit()
    d = nach_dem_versand(db, DEZ)
    ada = [z for z in d["zeilen"] if z["name"] == "Ada Arbeit"]
    assert [(z["tag"], z["vorher"], z["jetzt"], z["gruende"]) for z in ada] == [
        (date(2026, 12, 7), ["1/1000 8,00 h"], ["1/1001 7,00 h"], [OHNE_GRUND]),
        (date(2026, 12, 8), ["1/1000 8,00 h"], ["1/1001 8,00 h"], [OHNE_GRUND])]
    assert len(d["allgemein"]) == 1 and d["allgemein"][0].startswith("Zuordnung DATEV-Export geändert · ") and d["allgemein"][0].endswith(" · Fin Finanzen")


def test_nummernwechsel_und_lohnstammdaten(w):
    db = w["db"]
    w["gesendet"]()
    with als():
        p = db.query(EmployeePayrollSettings).filter_by(employee_id=w["ada"].id).one()
        p.datev_personnel_number = "00096"
        db.add(PersonalnummerVergabe(nummer="00094", employee_id=w["ada"].id))
        db.commit()
    d = nach_dem_versand(db, DEZ)
    [z] = d["zeilen"]  # dieselbe Person über die frühere Nummer: nur die Nummer ist anders, die Tage gleich
    assert (z["name"], z["art"], z["tag"], z["vorher"], z["jetzt"]) == ("Ada Arbeit", "nummer", None, ["Personalnummer 00094"], ["Personalnummer 00096"])
    assert z["personalnummer"] == "00096" and z["gruende"][0].startswith("Lohnstammdaten geändert · ")


def test_bezug_ist_die_juengste_abgleich_zeile(w):
    db = w["db"]
    gesendet = w["gesendet"]()
    with als():
        e = _buchung(db, w["ada"], 8)
        e.hours = Decimal("6")
        db.commit()
    assert nach_dem_versand(db, DEZ)["anzahl"] == 1
    # „Besprochen“ (1.9.330) legt die Rechnung von heute als Abgleich-Zeile ab -- danach ist die Liste leer
    inhalt = datei("1234567", "12345", DEZ, berechnen(db, DEZ))
    ablegen(db, DEZ, inhalt, "abgleich.txt", user_id=7, user_name="Fin", art="abgleich", notiz="Telefonat 05.02.")
    db.commit()
    d = nach_dem_versand(db, DEZ)
    assert (d["stand"], d["bezug"]["art"], d["bezug"]["notiz"], d["bezug"]["gesendet_id"]) == ("gleich", "abgleich", "Telefonat 05.02.", gesendet.id)


def test_route_und_rechte(w):
    db = w["db"]
    w["gesendet"]()
    r = w["client"]().get(URL, params={"monat": "2026-12"})
    assert r.status_code == 200 and r.json()["stand"] == "gleich" and r.json()["bezug"]["art"] == "datei"
    for rolle in ("buero_auftrag", "field"):
        assert w["client"](rolle).get(URL, params={"monat": "2026-12"}).status_code == 403
    assert w["client"]().get(URL, params={"monat": "2026-11"}).json()["stand"] == "nichts_versendet"
    # eine abgelegte Datei, die nicht zu ihrer Prüfsumme passt: 409, nichts verglichen
    db.execute(Lohndatei.__table__.update().values(sha256="0" * 64))
    db.commit()
    r = w["client"]().get(URL, params={"monat": "2026-12"})
    assert r.status_code == 409 and "Prüfsumme" in r.json()["detail"]


# --- Seite ---

def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def test_seite_zeilen_und_bezug():
    text = vj.seitentext("zeiten.html")[0]
    js = ("function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
          "function berlinZeitpunkt(w){return 'Z['+w+']'}function tagKurz(i){return 'T['+i+']'}\n"
          + "\n".join(_funktion(text, f) for f in ("nachVersandBezug", "nachVersandZeile"))
          + "\nprocess.stdout.write(JSON.stringify(["
          "nachVersandBezug(null),"
          "nachVersandBezug({art:'datei',erzeugt_am:'e',versendet_am:'v',versendet_von_name:'Fin'}),"
          "nachVersandBezug({art:'abgleich',erzeugt_am:'e',erzeugt_von_name:'Fin',notiz:'Telefonat <05.02.>'}),"
          "nachVersandZeile({art:'tag',tag:'2026-12-08',name:'Ada <A>',personalnummer:'00094',vorher:['1/1000 8,00 h'],jetzt:[],gruende:['Zeitbuchung gelöscht · x · y']}),"
          "nachVersandZeile({art:'nummer',tag:null,name:'Bo',personalnummer:'00096',vorher:['Personalnummer 00095'],jetzt:['Personalnummer 00096'],gruende:['g']}),"
          "nachVersandZeile({art:'monat',tag:null,name:'Bo',personalnummer:'00096',vorher:[],jetzt:['Monatszeile 8195 8,00 h'],gruende:['g']})]))")
    leer, datei_, abgleich, tag, nummer, monat = node_ausfuehren(js)
    assert leer == "" and datei_ == "Bezug: Datei vom Z[e], gesendet Z[v] · Fin"
    assert abgleich == "Bezug: besprochen Z[e] · Fin – „Telefonat <05.02.>“"  # textContent: kein esc nötig
    assert tag == ('<tr><td>Ada &lt;A><br><span class="mut num">00094</span></td><td class="nv-tag">T[2026-12-08]</td><td class="num">1/1000 8,00 h</td>'
                   '<td class="num"><span class="mut">–</span></td><td>Zeitbuchung gelöscht · x · y</td></tr>')
    assert '<td class="nv-tag">Personalnummer</td>' in nummer and '<td class="nv-tag">Monatszeile</td>' in monat


def test_seite_laedt_mit_dem_monat():
    text = vj.seitentext("zeiten.html")[0]
    assert (".then(function(){return lesen('nachVersand',()=>api('/api/zeiten/nach-dem-versand?monat='+encodeURIComponent(LOHN_MONAT)),"
            "nachVersandZeichnen)})") in _funktion(text, "monatLaden")
    zeichnen = _funktion(text, "nachVersandZeichnen")
    for teil in ("el('nvBezug').textContent=nachVersandBezug(d.bezug);", "el('nvText').textContent=d.text;", "el('nvTabelle').hidden=!d.zeilen.length;",
                 "el('nvAllgemeinKopf').hidden=!(d.allgemein||[]).length;"):
        assert teil in zeichnen


def test_abgleich_vor_der_gesendeten_zaehlt_nicht(w):
    """Bezug ist nur eine Abgleich-Zeile, die nach der gesendeten Datei erzeugt wurde -- eine ältere nicht."""
    db = w["db"]
    ablegen(db, DEZ, datei("1234567", "12345", DEZ, berechnen(db, DEZ)), "alt.txt", user_id=7, user_name="Fin", art="abgleich", notiz="früher")
    db.commit()
    gesendet = w["gesendet"]()
    d = nach_dem_versand(db, DEZ)
    assert (d["bezug"]["id"], d["bezug"]["art"]) == (gesendet.id, "datei")


def test_verschobene_buchung_alter_und_neuer_tag(w):
    db = w["db"]
    w["gesendet"]()
    with als():
        e = _buchung(db, w["ada"], 7)
        e.work_date, e.started_at, e.ended_at = date(2026, 12, 9), datetime(2026, 12, 9, 7), datetime(2026, 12, 9, 15)
        db.commit()
    zeilen = {z["tag"]: z for z in nach_dem_versand(db, DEZ)["zeilen"] if z["name"] == "Ada Arbeit"}
    assert sorted(zeilen) == [date(2026, 12, 7), date(2026, 12, 9)]
    assert (zeilen[date(2026, 12, 7)]["jetzt"], zeilen[date(2026, 12, 9)]["vorher"]) == ([], [])
    for z in zeilen.values():
        assert len(z["gruende"]) == 1 and z["gruende"][0].startswith("Zeitbuchung geändert · ")


def test_monatszeilen_fuer_sich():
    from app.lohndatei import Person, Zeile
    from app.lohndatei_abgleich import heute_lesen
    roh = b"1234567;12345;12/2026\r\n00094;7;WA;8195;8,00;;;;;;\r\n00094;;;8195;;;16,00;;;;\r\n00094;;;8195;;;1,00;;;;\r\n"
    s = datei_lesen(roh, DEZ, lambda n: 5)
    assert dict(s.zeilen) == {(5, date(2026, 12, 7)): {("WA", "8195"): Decimal("8.00")}, (5, None): {(None, "8195"): Decimal("17.00")}}
    p = Person(5, "Ada", "00094", "alles", False, zeilen=[Zeile(None, None, "8195", Decimal("17"), "schlechtwetter")])
    assert dict(heute_lesen([p]).zeilen) == {(5, None): {(None, "8195"): Decimal("17")}}
    assert eintrag_text((None, "8195"), Decimal("17")) == "Monatszeile 8195 17,00 h"
    assert eintrag_text(("FE", None), Decimal("8")) == "FE 8,00 h" and eintrag_text(("1", "1000"), Decimal("7.5")) == "1/1000 7,50 h"
