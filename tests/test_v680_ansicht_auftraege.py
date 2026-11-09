"""Version 1.9.280 (Stufe 6, R5c, Punkt 2): Ansicht „Aufträge“, Kurzname am Gerät, Kran mit eigenem Zeichen.

    Kurzname   operational_resources.kurzname (Migration c3e9f1a7b285, höchstens 30 Zeichen, leer = der Name); im Stammdaten-Formular; PUT /api/resources/{id}
               ist ein Teil-Update (Regel 22, bis 1.9.279 ein Altfall in BEKANNT)
    Kran       am Typ erkannt („Kran“, auch „Autokran“): eigenes Zeichen am Chip
    Ansicht    vierter Reiter „Aufträge“: eine Zeile je offenem Auftrag (Auftragsliste, nur in dieser Ansicht geladen), je Einsatz eine Karte in der Zelle des Tags
               (fest, vorläufig, Kran; zwei Einsätze zwei Karten), Chips der Personen und Geräte an diesem Tag, „niemand“ an einem Tag ohne jemanden; ⚠ bzw. der
               Punkt nur am betroffenen Chip und Tag; ab 2 Wochen schmalere Chips (Name im title); links „Zum Einplanen“ mit Wochenleiste (eingeplant, frei,
               beantragt, abwesend ohne Art, doppelt)
Der Klicktest scripts/klicktest_plantafel_auftraege.py prüft die Ansicht im Browser mit Daten wie die Zeichnung.
"""

import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.models import OperationalResource
from app.planning import ist_kran
from app.routers.resource_planning import router as resource_router
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT

VORHER, MIGRATION = "b6e4d2a9c731", "c3e9f1a7b285"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
SEITE = ROOT / "app/templates/planning.html"


# --- Kurzname und Kran ---------------------------------------------------------------------------------------------------------------------

def test_kurzname_anlegen_und_aendern_als_teil_update(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, resource_router)
    r = client.post("/api/resources", json={"resource_type": "Fahrzeug", "name": "Pritsche HS-DK 202", "identifier": "HS-DK 202", "kurzname": " HS-DK 202 "})
    assert r.status_code == 200 and r.json()["kurzname"] == "HS-DK 202", r.text
    rid = r.json()["id"]
    assert client.put(f"/api/resources/{rid}", json={"kurzname": "202"}).json()["kurzname"] == "202"
    nur_name = client.put(f"/api/resources/{rid}", json={"name": "Pritsche 202"}).json()
    assert (nur_name["name"], nur_name["kurzname"], nur_name["identifier"], nur_name["resource_type"]) == ("Pritsche 202", "202", "HS-DK 202", "Fahrzeug")
    assert client.put(f"/api/resources/{rid}", json={"kurzname": ""}).json()["kurzname"] is None  # leer = der Name
    assert client.put(f"/api/resources/{rid}", json={"kurzname": "x" * 31}).status_code == 422
    assert client.put(f"/api/resources/{rid}", json={"name": None}).status_code == 422
    assert client.post("/api/resources", json={"name": "Kran", "kurzname": "y" * 31}).status_code == 422


@pytest.mark.parametrize("typ, kran", [("Kran", True), ("Autokran", True), ("kran", True), ("Fahrzeug", False), (None, False)])
def test_kran_am_typ(typ, kran):
    assert ist_kran(OperationalResource(name="x", resource_type=typ)) is kran


def test_tafel_liefert_kurzname_und_kran(threaded_db_session, router_test_client):
    from datetime import date

    from app.routers.planning import router as planning_router
    db = threaded_db_session
    db.add_all([OperationalResource(resource_type="Kran", name="Liebherr", kurzname="Kran", active=True),
                OperationalResource(resource_type="Fahrzeug", name="Pritsche", active=True)])
    db.commit()
    r = router_test_client(db, planning_router).get("/api/planning", params={"start": date(2026, 11, 2).isoformat(), "end": date(2026, 11, 8).isoformat()})
    assert {(x["name"], x["kurzname"], x["kran"]) for x in r.json()["resources"]} == {("Liebherr", "Kran", True), ("Pritsche", None, False)}


def test_stammdaten_formular_mit_kurzname():
    text_ = (ROOT / "app/templates/master_data_form.html").read_text(encoding="utf-8")
    assert '<label for="kurzname">Kurzname auf der Plantafel</label><input id="kurzname" maxlength="30"' in text_
    assert "el('kurzname').value=record.kurzname||'';" in text_ and "kurzname:n(v('kurzname'))," in text_


# --- Migration c3e9f1a7b285 -------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO operational_resources (resource_type, name, active, created_at, updated_at) "
                       "VALUES ('Fahrzeug', 'Pritsche', :wahr, '2026-11-01', '2026-11-01')"), {"wahr": True})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:
        assert c.execute(text("SELECT kurzname FROM operational_resources")).scalar() is None  # bestehende Geräte ohne Kurznamen
        c.execute(text("UPDATE operational_resources SET kurzname = 'HS-DK 202'"))
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        spalten = [z[1] if engine.dialect.name == "sqlite" else z[0] for z in (
            c.execute(text("PRAGMA table_info(operational_resources)")) if engine.dialect.name == "sqlite" else
            c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'operational_resources' AND table_schema = current_schema()")))]
        assert "kurzname" not in spalten and c.execute(text("SELECT name FROM operational_resources")).scalar() == "Pritsche"
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'kurzname.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_kurzname_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


# --- die Ansicht (in node mit dem Code der Seite) ------------------------------------------------------------------------------------------

FUNKTIONEN = ["chipName", "chipHtml", "konflikteAm", "imStueck", "personenAm", "geraeteAm", "karteHtml", "personTageIn", "geraetTageIn", "einsatzTage",
              "addDays", "iso", "fmt", "istWochenende", "geraetInfo", "geraetName", "aufGeschlossen", "personZustand", "geraetZustand", "einsatzTitel",
              "slotHinweis", "tageAnzahl", "wochentag"]
BOARD = {
    "resources": [{"id": 7, "name": "Pritsche HS-DK 202", "kurzname": "HS-DK 202", "kran": False}, {"id": 9, "name": "Liebherr", "kurzname": None, "kran": True}],
    "abwesenheiten": [{"employee_id": 3, "stand": "beantragt", "von": "2026-11-12", "bis": "2026-11-12"},
                      {"employee_id": 4, "stand": "genehmigt", "art": "Krank", "von": "2026-11-13", "bis": "2026-11-13"}],
    "slots": [
        {"id": 1, "order_id": 10, "status": "fest", "art": "baustelle", "order_status": "laeuft", "start_date": "2026-11-09", "end_date": "2026-11-13",
         "project_number": "P-1", "project_name": "Wasserturm", "customer_name": "K", "art_label": "Baustelle", "status_label": "fest",
         "employees": [{"id": 1, "name": "Tom Monteur", "vorname": "Tom", "tage": ["2026-11-09", "2026-11-10", "2026-11-12", "2026-11-13"]},
                       {"id": 2, "name": "Kai Kolb", "vorname": "Kai", "tage": ["2026-11-12", "2026-11-13"]}],
         "resources": [{"id": 7, "name": "Pritsche HS-DK 202", "tage": ["2026-11-09", "2026-11-10", "2026-11-12", "2026-11-13"]},
                       {"id": 9, "name": "Liebherr", "tage": ["2026-11-13"]}],
         "conflicts": [{"type": "resource", "stufe": "warnung", "label": "Liebherr", "resource_id": 9, "tage": ["2026-11-13"]},
                       {"type": "resource", "stufe": "warnung", "label": "Pritsche", "resource_id": 7, "tage": ["2026-11-12"]}]},
        {"id": 2, "order_id": 11, "status": "vorlaeufig", "art": "kranvermietung", "order_status": "laeuft", "start_date": "2026-11-13", "end_date": "2026-11-13",
         "project_number": "P-2", "project_name": "Kran", "customer_name": "K", "art_label": "Kranvermietung", "status_label": "vorläufig",
         "employees": [{"id": 2, "name": "Kai Kolb", "vorname": "Kai", "tage": None}, {"id": 3, "name": "Nele Neu", "vorname": "Nele", "tage": None}],
         "resources": [{"id": 9, "name": "Liebherr", "tage": None}],
         "conflicts": [{"type": "antrag_offen", "stufe": "hinweis", "label": "Nele", "employee_id": 3, "tage": ["2026-11-13"]}]},
    ],
}


def _lauf(ablauf: str, tage: int = 7) -> list:
    vorbereitung = (f"var board = {json.dumps(BOARD)}; var AUFRUFE = AUFRUFE || []; const KONFLIKT_ART = {{resource: 'Gerät doppelt: ', antrag_offen: 'Antrag offen: '}};"
                    "const WOCHENTAGE=['So','Mo','Di','Mi','Do','Fr','Sa'];"
                    "const WARNZEICHEN='<svg class=\"warnzeichen\"></svg>'; const GERAETZEICHEN='<svg class=\"auto\"></svg>'; const KRANZEICHEN='<svg class=\"kranzeichen\"></svg>';"
                    f"document.getElementById('rangeDays').value = '{tage}';"
                    "function esc(s){return String(s??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]))}"
                    "function localDateIso(d){const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`}")
    return im_browser("planning.html", FUNKTIONEN, vorbereitung, ablauf)


def _chips(html: str) -> list[str]:
    import re
    return [re.sub(r"<[^>]+>", "", c) for c in re.findall(r'<span class="chip[^"]*"[^>]*>(.*?)</span>', html)]


@nur_mit_node
def test_karte_mit_chips_am_tag():
    [mo, mi, fr] = _lauf("for (const d of ['2026-11-09','2026-11-11','2026-11-13']) AUFRUFE.push(karteHtml(board.slots[0], d));")
    assert mo.startswith('<div class="a-einsatz" ') and _chips(mo) == ["Tom", "HS-DK 202"]  # Kai erst ab Do, der Kran nur am Fr; Kurzname am Gerät
    assert "chip warn" not in mo  # die Warnung der Pritsche gilt nur am Do
    assert mi.startswith('<div class="a-einsatz niemand"') and ">niemand<" in mi  # am Mi niemand
    assert _chips(fr) == ["Tom", "Kai", "HS-DK 202", "Liebherr"] and "kranzeichen" in fr
    assert fr.count('class="chip warn"') == 1 and fr.count("warnzeichen") == 1  # ⚠ nur am Kran, nur am Fr


@nur_mit_node
def test_karte_vorlaeufig_kran_und_hinweis():
    [k] = _lauf("AUFRUFE.push(karteHtml(board.slots[1], '2026-11-13'));")
    assert 'class="a-einsatz vorlaeufig kran"' in k and 'hinweis-punkt' in k and k.count("hinweis-punkt") == 1


@nur_mit_node
def test_ab_zwei_wochen_schmale_chips_mit_name_im_title():
    assert _lauf("AUFRUFE.push(chipName('Tom'));", tage=7) == ["Tom"]
    assert _lauf("AUFRUFE.push(chipName('Tom'));", tage=14) == ["To"]
    [k] = _lauf("AUFRUFE.push(karteHtml(board.slots[0], '2026-11-09'));", tage=14)
    assert 'title="Tom Monteur"' in k and ">To<" in k


@nur_mit_node
def test_wochenleiste():
    [z] = _lauf("AUFRUFE.push(['2026-11-09','2026-11-12','2026-11-13'].map(d=>[personZustand(2,d)[0],personZustand(3,d)[0],personZustand(4,d)[0],geraetZustand(9,d)[0]]));")
    assert z == [["frei", "frei", "frei", "frei"], ["eingeplant", "beantragt", "frei", "frei"], ["doppelt", "eingeplant", "abwesend", "doppelt"]]
    [t] = _lauf("AUFRUFE.push(personZustand(4,'2026-11-13')[1]);")
    assert t == "abwesend" and "Krank" not in t  # ohne Art (Antwort 13)


def test_reiter_legende_und_laden_nur_in_auftraege():
    seite = SEITE.read_text(encoding="utf-8")
    assert '<button type="button" data-view="auftraege" aria-pressed="false">Aufträge</button>' in seite
    assert '<div class="legende legende-auftraege" aria-label="Legende der Aufträge">' in seite
    assert "if(view==='auftraege')await ladeAuftragsliste()" in seite  # die übrigen Ansichten laden die Liste nicht
    # seit 1.9.281 öffnet die Karte nach dem Antippen eines Chips nicht (dann das Menü des Chips)
    assert "aktion('auftragKarte',el=>{if(chipTipp){chipTipp=false;return}openEdit(Number(el.dataset.id))});" in seite
    # seit 1.9.281 danach das Ziehen und die Leiste des letzten Zugs
    assert ("if(view==='auftraege'){document.getElementById('planner').innerHTML=auftraegeHtml();renderBacklog();renderFilter();chipZiehenEinrichten();"
            "zugNachZeigen();return}") in seite
