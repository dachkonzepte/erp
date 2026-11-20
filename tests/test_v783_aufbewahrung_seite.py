"""Version 1.10.12 (Stufe W1c): Seite „Aufbewahrung“, Kachel auf „Start“, Hinweis „im Archiv“ in Kundenakte und Eingang der Webseite.

    Seite      Büro ab Auftrag; „Alle fälligen archivieren“ und „Archivieren“ nur Admin und Büro – Finanzen (sonst der Hinweis); die Monteurin 403
    Fällig     Eingänge für sich, je Kunde seine Vorgänge mit letztem Kontakt und Herkunft, fällig ab, was mitgeht, Sperren, „unbearbeitet“; Knopf
               nur an Fälligem; „Kunde mit n Vorgängen archivieren“; jeder Text über esc()
    Archiv     Kunden und Vorgänge mit „im Archiv seit“ und „Zurückholen“ (jedes Büro)
    Aktionen   einzeln über die feste Liste der Arten, gesammelt nur mit der Prüfsumme der Vorschau
    Start      Kachel „Aufbewahrung“ unter den Anfragen der Webseite: Zahl, seit wann, unbearbeitete Eingänge; ohne Fälliges der Weg ins Archiv
    Hinweise   Kundenakte und Eingang der Webseite sagen „im Archiv seit …“; der Eingang zeigt dann keine Aktion
"""

import json

import pytest

from app.dashboard import DEFAULT_WIDGETS
from app.routers import pages as pages_router
from tests.gerenderte_seite import gerenderte_seite
from tests.node_lauf import node_ausfuehren
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.vorlagen_js import bindet_ein

BOESE = '<img src=x onerror="alert(1)">'
KONTAKT = {"tag": "2026-04-01", "herkunft": BOESE}


def _v(art, id_, **mehr):
    d = {"art": art, "id": id_, "nummer": f"N-{id_}", "titel": BOESE, "kunde_id": None, "letzter_kontakt": KONTAKT, "faellig_ab": "2026-10-01",
         "faellig": True, "sperren": [], "hinweise": [], "mit": {}, "unbearbeitet": False, "archiviert_am": None}
    d.update(mehr)
    return d


VORSCHAU = {"heute": "2026-11-20", "nach_monaten": 6, "zahl": 3, "unbearbeitet": 1, "seit": "2026-05-01", "stand": "0123456789abcdef",
            "eingaenge": [_v("eingang", 5, unbearbeitet=True, mit={"fotos": 2})],
            "kunden": [{"id": 7, "name": BOESE, "kundennummer": "K-7", "ort": "Musterstadt", "letzter_kontakt": KONTAKT, "faellig_ab": "2026-10-01",
                        "faellig": True, "gruende": [], "archiviert_am": None,
                        "vorgaenge": [_v("projekt", 9, kunde_id=7, mit={"angebote": 1}),
                                      _v("anfrage", 3, kunde_id=7, faellig=False, sperren=["offene Aufgabe am Projekt"])]}]}
ARCHIV = {"kunden": [{"id": 7, "name": BOESE, "kundennummer": "K-7", "ort": None, "letzter_kontakt": None, "faellig_ab": None, "faellig": False,
                      "gruende": [], "archiviert_am": "2026-11-20T09:30:00", "vorgaenge": []}],
          "vorgaenge": [_v("anfrage", 3, archiviert_am="2026-11-20T09:30:00")]}


def _seite(rolle, threaded_db_session, router_test_client):
    return router_test_client(threaded_db_session, pages_router.router, role=rolle).get("/aufbewahrung")


@pytest.mark.parametrize("rolle, darf", [("admin", True), ("buero_finanzen", True), ("buero_auftrag", False)])
def test_seite_je_rolle(rolle, darf, threaded_db_session, router_test_client):
    r = _seite(rolle, threaded_db_session, router_test_client)
    assert r.status_code == 200
    assert ('id="alleKnopf"' in r.text) == darf and ('id="nurLesen"' in r.text) == (not darf)
    assert f"const DARF={'true' if darf else 'false'};" in r.text


def test_monteurin_bekommt_die_seite_nicht(threaded_db_session, router_test_client):
    assert _seite("field", threaded_db_session, router_test_client).status_code == 403


def _lauf(html: str, ablauf: str, antworten: dict | None = None):
    js = (gerenderte_seite(html, "\nladen().catch(") + f"\nANTWORTEN = {json.dumps(antworten or {})};\n"
          f"(async () => {{ const ergebnis = await (async () => {{ {ablauf} }})();"
          " process.stdout.write(JSON.stringify({ergebnis, aufrufe: AUFRUFE})); })().catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return node_ausfuehren(js, "Europe/Berlin")


@nur_mit_node
@pytest.mark.parametrize("rolle, knoepfe", [("buero_finanzen", True), ("buero_auftrag", False)])
def test_faellig_ueber_esc_und_knoepfe_nur_mit_recht(rolle, knoepfe, threaded_db_session, router_test_client):
    html = _seite(rolle, threaded_db_session, router_test_client).text
    ablauf = (f"vorschau = {json.dumps(VORSCHAU)}; standZeichnen(); faelligZeichnen();"
              "return [_element('inhalt').innerHTML, _element('standText').innerHTML];")
    inhalt, stand = _lauf(html, ablauf)["ergebnis"]
    assert "<img" not in inhalt and "&lt;img" in inhalt
    assert ('data-klick="archivieren" data-art="eingang" data-id="5"' in inhalt) == knoepfe
    assert ('data-art="projekt" data-id="9"' in inhalt) == knoepfe and ("Kunde mit 1 Vorgang archivieren" in inhalt) == knoepfe
    assert 'data-id="3"' not in inhalt and "gesperrt: offene Aufgabe am Projekt" in inhalt  # gesperrt: kein Knopf
    assert "unbearbeitet" in inhalt and "2 Fotos am Objekt" in inhalt and "1 Angebot" in inhalt and "01.04.2026" in inhalt
    assert "<b>3</b> fällig fürs Archiv seit 01.05.2026" in stand and "davon <b>1</b> unbearbeiteter Eingang" in stand


@nur_mit_node
def test_archiv_mit_zurueckholen(threaded_db_session, router_test_client):
    html = _seite("buero_auftrag", threaded_db_session, router_test_client).text
    ablauf = (f"vorschau = {json.dumps(VORSCHAU)}; archivDaten = {json.dumps(ARCHIV)}; archivZeichnen(); return _element('inhalt').innerHTML;")
    inhalt = _lauf(html, ablauf)["ergebnis"]
    assert inhalt.count('data-klick="zurueckholen"') == 2 and 'data-art="kunde" data-id="7"' in inhalt and 'data-art="anfrage" data-id="3"' in inhalt
    assert "20.11.2026" in inhalt and "<img" not in inhalt


@nur_mit_node
def test_aktionen_nur_feste_arten_und_gesammelt_mit_pruefsumme(threaded_db_session, router_test_client):
    html = _seite("buero_finanzen", threaded_db_session, router_test_client).text
    ablauf = ("const _alt = globalThis.fetch; globalThis.fetch = async (u, o = {}) => { const r = await _alt(u, o);"
              " return (o.method || 'GET') === 'POST' ? {...r, json: async () => ({archiviert: [{art: 'eingang', id: 5}], uebersprungen: [], art: 'kunde', id: 7, kunde_mit: false})} : r; };"
              f"vorschau = {json.dumps(VORSCHAU)};"
              "await _dkAktionen.click['archivieren']({dataset: {art: 'eingang', id: '5'}});"
              "await _dkAktionen.click['archivieren']({dataset: {art: '../../users', id: '1'}});"  # keine feste Art: nichts gesendet
              "await _dkAktionen.click['alle-archivieren']();"
              "await _dkAktionen.click['zurueckholen']({dataset: {art: 'kunde', id: '7'}});"
              "return _element('aktionStatus').textContent;")
    lauf = _lauf(html, ablauf, {"/api/aufbewahrung": VORSCHAU})
    posts = [(a["url"], a["body"]) for a in lauf["aufrufe"] if a["methode"] == "POST"]
    assert posts == [("/api/aufbewahrung/eingang/5/archivieren", None), ("/api/aufbewahrung/archivieren", {"stand": "0123456789abcdef"}),
                     ("/api/aufbewahrung/kunde/7/zurueckholen", None)]
    assert lauf["ergebnis"].startswith("Kunde zurückgeholt")


def test_kachel_auf_start_unter_den_anfragen():
    assert {"widget_key": "aufbewahrung", "sort_order": 13, "visible": True} in DEFAULT_WIDGETS
    keys = [w["widget_key"] for w in sorted(DEFAULT_WIDGETS, key=lambda w: w["sort_order"])]
    assert keys.index("aufbewahrung") == keys.index("webanfragen") + 1


@nur_mit_node
@pytest.mark.parametrize("zahl, erwartet", [(3, ["3 fällig fürs Archiv</a> seit 01.05.2026", "davon 1 unbearbeiteter Eingang"]),
                                            (0, ["Nichts fällig fürs Archiv.", 'href="/aufbewahrung#archiv"'])])
def test_kachel(zahl, erwartet):
    ablauf = ("authStatus = {authenticated: true, user: {role: 'buero_auftrag'}}; const c = _element('w');"
              "await renderAufbewahrungWidget(c); return c.innerHTML;")
    html = im_browser(seite("dashboard.html", "\ninit();"), ablauf, {"/api/aufbewahrung": {**VORSCHAU, "zahl": zahl}})["ergebnis"]
    assert all(e in html for e in erwartet), html


def test_kundenakte_hinweis_und_zurueckholen():
    from pathlib import Path
    vorlage = (Path(__file__).resolve().parent.parent / "app" / "templates" / "customer.html").read_text(encoding="utf-8")
    assert 'id="archivHinweis"' in vorlage and "el('archivHinweis').hidden=!customer.archiviert_am" in vorlage
    assert "api(`/api/aufbewahrung/${art}/${customerId}/zurueckholen`,{method:'POST'})" in vorlage and "const art='kunde'" in vorlage
    assert bindet_ein("aufbewahrung.html", "_speichern.html")


@nur_mit_node
def test_eingang_im_archiv_ohne_aktion():
    from tests.test_v776_webanfragen_pruefliste import _detail, _seite as wa_seite
    erg = wa_seite(_detail(archiviert_am="2026-11-20T09:30:00"))
    assert erg["stand"].startswith("Im Archiv seit 20.11.2026 – zurückholen unter „Aufbewahrung → Archiv“.")
    assert (erg["ein"], erg["weg"], erg["zurueck"]) == (True, True, True)
    normal = wa_seite(_detail())
    assert not normal["stand"].startswith("Im Archiv") and normal["weg"] is False
