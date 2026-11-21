"""Version 1.10.15 (Antwort F4 vom 21.11.2026): die Büro-Suche zeigt das Archiv in einer eigenen Gruppe „im Archiv“.

    Gruppe       Kunden, Objekte eines Kunden im Archiv, Anfragen, Projekte ohne Auftrag und deren Angebote im Archiv -- zuletzt, zusammen höchstens
                 `limit`, die Zahl über alle; die übrigen Gruppen bleiben ohne Archiv
    Treffer      Art, „im Archiv seit TT.MM.JJJJ“ (Tag in Berlin), was zurückgeholt wird (Objekt -> Kunde, Angebot -> Projekt)
    Seite        kein Link, nur „Zurückholen und öffnen“ (POST …/zurueckholen, danach die Seite des Treffers); Filter „im Archiv“
    Kopfzeile    keine Treffer aus dem Archiv, eine Zeile „n Treffer im Archiv“ in die Suche (types=archiv)
    nicht        die Suche der Monteurin, der Kalender (types=projects,quotes), „Beteiligten hinzufügen“ (office_source("customers"))
"""

import json
from datetime import datetime

import pytest

from app.models import Property, Quote
from app.routers import aufbewahrung as aufbewahrung_router
from app.routers import pages as pages_router
from app.routers import search as search_router
from app.search import office_source, search_office, search_properties_for_field
from tests.gerenderte_seite import gerenderte_seite
from tests.node_lauf import node_ausfuehren
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v782_archiv import Welt

IM_ARCHIV = datetime(2026, 11, 20, 23, 30)  # UTC -- in Berlin schon der 21.11.


@pytest.fixture
def welt(threaded_db_session):
    w = Welt(threaded_db_session)
    db = w.db
    # vorweg ein anderer Kunde mit zwei Objekten und einem Projekt: Objekt und Kunde, Angebot und Projekt haben danach verschiedene IDs (sonst bliebe
    # „Objekt holt seinen Kunden zurück“ zufällig grün -- Gegenprobe 1.10.15-2a/2b)
    otto = w.kunde(name="Otto Anders")
    db.add(Property(customer_id=otto.id, name="Lager", city="Musterstadt"))
    w.projekt(otto)
    alt = w.kunde(name="Zacharias Archiv")
    alt.archiviert_am = IM_ARCHIV
    w.anfrage_archiv = w.anfrage(alt, archiviert_am=IM_ARCHIV)
    w.projekt_archiv = w.projekt(alt, archived=True, archiviert_am=IM_ARCHIV)
    db.add(Quote(project_id=w.projekt_archiv.id, quote_number="A-ZACH-1", title="Zacharias Angebot", status="versendet"))
    aktiv = w.kunde(name="Zacharias Aktiv")
    w.anfrage(aktiv)
    db.commit()
    w.alt, w.aktiv = alt, aktiv
    w.objekt_alt = db.query(Property).filter(Property.customer_id == alt.id).one()
    w.angebot = db.query(Quote).filter(Quote.quote_number == "A-ZACH-1").one()
    assert w.objekt_alt.id != alt.id and w.angebot.id != w.projekt_archiv.id  # verschiedene IDs, siehe oben
    return w


def _gruppen(db, text="Zacharias", **mehr):
    return {g["key"]: g for g in search_office(db, "buero_auftrag", text, **mehr)}


def test_gruppe_im_archiv_zuletzt_mit_allen_arten(welt):
    gruppen = list(_gruppen(welt.db))
    assert gruppen[-1] == "archiv"
    g = _gruppen(welt.db)["archiv"]
    assert g["label"] == "im Archiv" and g["total"] == 5
    arten = [(h["subtitle"].split(" · ")[0], h["zurueckholen_art"], h["zurueckholen_id"]) for h in g["hits"]]
    assert arten == [("Kunde", "kunde", welt.alt.id), ("Objekt", "kunde", welt.alt.id), ("Anfrage", "anfrage", welt.anfrage_archiv.id),
                     ("Projekt", "projekt", welt.projekt_archiv.id), ("Angebot", "projekt", welt.projekt_archiv.id)]


def test_uebrige_gruppen_ohne_archiv(welt):
    g = _gruppen(welt.db)
    assert [h["id"] for h in g["customers"]["hits"]] == [welt.aktiv.id]
    assert all(h["id"] != welt.anfrage_archiv.id for h in g["inquiries"]["hits"])
    assert "projects" not in g and "quotes" not in g  # nur im Archiv
    assert all(h.get("zurueckholen_art") is None for k, x in g.items() if k != "archiv" for h in x["hits"])


def test_im_archiv_seit_als_tag_in_berlin(welt):
    kunde = _gruppen(welt.db)["archiv"]["hits"][0]
    assert kunde["subtitle"] == f"Kunde · {welt.alt.customer_number} · Musterstadt · im Archiv seit 21.11.2026"
    objekt = _gruppen(welt.db)["archiv"]["hits"][1]
    assert objekt["subtitle"].endswith("Kunde im Archiv seit 21.11.2026")
    angebot = _gruppen(welt.db)["archiv"]["hits"][4]
    assert angebot["subtitle"].endswith("Projekt im Archiv seit 21.11.2026") and angebot["url"] == f"/quotes/{welt.angebot.id}/edit"


def test_ohne_zeitpunkt_nur_im_archiv(welt):
    welt.projekt_archiv.archiviert_am = None  # vor 1.10.11 von Hand archiviert
    welt.db.commit()
    projekt = [h for h in _gruppen(welt.db)["archiv"]["hits"] if h["subtitle"].startswith("Projekt")][0]
    assert projekt["subtitle"].endswith(" · im Archiv")


def test_ein_projekt_mit_auftrag_bleibt_in_den_projekten(welt):
    welt.auftrag(welt.projekt_archiv)
    welt.db.commit()
    g = _gruppen(welt.db)
    assert [h["id"] for h in g["projects"]["hits"]] == [welt.projekt_archiv.id]
    assert not any(h["subtitle"].startswith(("Projekt", "Angebot")) for h in g["archiv"]["hits"])


def test_limit_ueber_alle_arten_zahl_ueber_alle(welt):
    g = _gruppen(welt.db, limit_per_type=2)["archiv"]
    assert g["total"] == 5 and len(g["hits"]) == 2


def test_typen_filter_und_andere_suchen_ohne_archiv(welt):
    db = welt.db
    assert set(_gruppen(db, types=frozenset({"projects", "quotes"}))) == set()  # Kalender (Verknüpfung)
    assert set(_gruppen(db, types=frozenset({"archiv"}))) == {"archiv"}
    assert [x["customer_name"] for x in search_properties_for_field(db, "Zacharias")] == ["Zacharias Aktiv"]  # Monteurin: nur Objekte aktiver Kunden
    musterweg = db.query(Property).filter(Property.street == "Musterweg 1").all()
    assert sorted(x["id"] for x in search_properties_for_field(db, "Musterweg")) == sorted(p.id for p in musterweg if p.customer_id != welt.alt.id)
    kunden = office_source("customers").query_fn(db, "Zacharias", 10)
    assert [k.id for k in kunden[1]] == [welt.aktiv.id]  # „Beteiligten hinzufügen“


def test_api_und_zurueckholen(welt, router_test_client):
    db = welt.db
    c = router_test_client(db, search_router.router, aufbewahrung_router.router, role="buero_auftrag")
    g = {x["key"]: x for x in c.get("/api/search?q=Zacharias").json()}
    objekt = g["archiv"]["hits"][1]
    assert set(objekt) == {"id", "title", "subtitle", "url", "zurueckholen_art", "zurueckholen_id"}
    r = c.post(f"/api/aufbewahrung/{objekt['zurueckholen_art']}/{objekt['zurueckholen_id']}/zurueckholen")
    assert r.status_code == 200
    g = {x["key"]: x for x in c.get("/api/search?q=Zacharias").json()}
    assert welt.alt.id in [h["id"] for h in g["customers"]["hits"]]
    assert [h["subtitle"].split(" · ")[0] for h in g["archiv"]["hits"]] == ["Anfrage", "Projekt", "Angebot"]  # die Vorgänge bleiben im Archiv


def test_monteurin_403(welt, router_test_client):
    assert router_test_client(welt.db, search_router.router, role="field").get("/api/search?q=Zacharias").status_code == 403


# --- Oberfläche -----------------------------------------------------------------------------------------------------------------------------------

TREFFER = {"key": "archiv", "label": "im Archiv", "total": 2, "hits": [
    {"id": 4, "title": '<img src=x onerror="alert(1)">', "subtitle": "Objekt · X · Kunde im Archiv seit 21.11.2026", "url": "/properties/4",
     "zurueckholen_art": "kunde", "zurueckholen_id": 9},
    {"id": 3, "title": "AN-3 · Dachrinne", "subtitle": "Anfrage · X · im Archiv seit 21.11.2026", "url": "/inquiries?inquiry=3",
     "zurueckholen_art": "anfrage", "zurueckholen_id": 3}]}
KUNDEN = {"key": "customers", "label": "Kunden", "total": 1, "hits": [{"id": 1, "title": "Aktiv", "subtitle": None, "url": "/customers/1"}]}


def _ergebnisseite(threaded_db_session, router_test_client):
    return router_test_client(threaded_db_session, pages_router.router, role="buero_auftrag").get("/suche?q=Zacharias").text


def _lauf(html, ablauf, antworten=None):
    js = (gerenderte_seite(html, "\n(function init(){") + f"\nANTWORTEN = {json.dumps(antworten or {})};\n"
          f"(async () => {{ const ergebnis = await (async () => {{ {ablauf} }})();"
          " process.stdout.write(JSON.stringify({ergebnis, aufrufe: AUFRUFE})); })().catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return node_ausfuehren(js, "Europe/Berlin")


@nur_mit_node
def test_ergebnisseite_ohne_link_mit_zurueckholen(threaded_db_session, router_test_client):
    html = _ergebnisseite(threaded_db_session, router_test_client)
    ablauf = f"query = 'Zacharias'; groups = {json.dumps([KUNDEN, TREFFER])}; renderGroups(); return _element('resultGroups').innerHTML;"
    inhalt = _lauf(html, ablauf)["ergebnis"]
    archiv = inhalt[inhalt.index('id="archiv"'):]
    assert 'href="/properties/4"' not in archiv and 'href="/inquiries' not in archiv and 'href="/customers/1"' in inhalt
    assert archiv.count('data-klick="archiv-zurueckholen"') == 2 and 'data-art="kunde" data-id="9" data-ziel="/properties/4"' in archiv
    assert "<img" not in archiv and "&lt;img" in archiv and "Öffnen nur über „Zurückholen und öffnen“" in archiv
    assert "['archiv','im Archiv']" in html  # Filter


@nur_mit_node
def test_zurueckholen_und_oeffnen(threaded_db_session, router_test_client):
    html = _ergebnisseite(threaded_db_session, router_test_client)
    ablauf = (f"query = 'Zacharias'; groups = {json.dumps([TREFFER])}; renderGroups();"
              "await _dkAktionen.click['archiv-zurueckholen']({dataset: {art: 'kunde', id: '9', ziel: '/properties/4'}});"
              "return location.href;")
    lauf = _lauf(html, ablauf)
    assert [(a["url"], a["methode"]) for a in lauf["aufrufe"] if a["methode"] == "POST"] == [("/api/aufbewahrung/kunde/9/zurueckholen", "POST")]
    assert lauf["ergebnis"].endswith("/properties/4")


def test_kopfzeile_zeigt_eine_zeile_ins_archiv():
    from pathlib import Path
    kopf = (Path(__file__).resolve().parent.parent / "app" / "templates" / "_topbar.html").read_text(encoding="utf-8")
    assert "if(g.key==='archiv'){archiv=g;return}" in kopf
    assert "href=\"/suche?q='+escHtml(encodeURIComponent(q))+'&amp;types=archiv\"" in kopf and " Treffer im Archiv</div>" in kopf
