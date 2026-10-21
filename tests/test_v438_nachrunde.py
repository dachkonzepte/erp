"""Nachrunde zur Fehlerrunde (1.8.143 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

Die Punkte 1–3 (Zeit buchen, Gruppenzeit stoppen, Kennzeichen entziehen) stehen in tests/test_v437_befund_zeit_fuer_andere.py.

    4  users.html: Zurück-Link mit echtem Ziel statt history.back() (1.8.146)
    5  Stammdaten-Formular: nach dem Speichern in den Bereich der Liste, auch für Ressourcen (1.8.147)
    6  Auftrag: Menge und Einheitspreis mit Tausenderpunkt über zahlText() (1.8.148)
    7  Links nach /users nur für Administratoren -- Wächter, der Stand war schon richtig (1.8.149)
    8  /api/audit-logs: offset negativ oder keine Zahl 422, sehr groß leere Seite, nie 500; Namen der Historie lesbar (1.8.150)
"""

import html
import json
import re

import pytest

from tests.test_v334_auswahl_restfaelle import TEMPLATES, im_browser, nur_mit_node, seite
from tests.test_v414_zahleneingaben import _js


# ---------------------------------------------------------------------------
# 4. users.html: Zurück-Link mit echtem Ziel
# ---------------------------------------------------------------------------

def test_benutzerseite_zurueck_in_die_einstellungen(threaded_db_session, router_test_client):
    """Bis 1.8.145 ging „← Einstellungen“ per history.back() zurück -- nach direktem Aufruf ins Leere."""
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role="admin").get("/users")
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    # seit 1.9.21 (Stufe 2, Runde 8) als Pfad im Seitenkopf statt „← Einstellungen“
    assert 'class="back' not in markup and "history.back" not in antwort.text
    nav = re.search(r'<nav class="ds-kopf-pfad"[^>]*>(.*?)</nav>', markup, flags=re.S).group(1)
    assert re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav) == [("/settings", "Einstellungen")]
    assert html.unescape(re.search(r'class="ds-kopf-pfadende" aria-current="page">([^<]*)<', nav).group(1)) == "Benutzer und Zugriff"
    assert router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").status_code == 200


# ---------------------------------------------------------------------------
# 5. Stammdaten-Formular: nach dem Speichern in den richtigen Bereich
# ---------------------------------------------------------------------------

SPEICHERN_FETCH = r"""
  globalThis.fetch = async (url, opt = {}) => ({ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'},
                                                json: async () => ({id: 7})});
  _element('name').value = 'Kran';
  await save();
  return {ziel: location.href, meldung: _element('msg').textContent || ''};
"""


@nur_mit_node
@pytest.mark.parametrize("adresse,ziel", [
    ("/master-data/resources/new", "/master-data#assets"),
    ("/master-data/resources/3/edit", "/master-data#assets"),
    ("/master-data/teams/5/edit", "/master-data#teams"),
])
def test_stammdaten_formular_springt_in_den_bereich_der_liste(threaded_db_session, router_test_client, adresse, ziel):
    """Bis 1.8.146 sprang das Formular nach dem Speichern auf '/master-data#'+Art -- für Ressourcen „#resources“, den Bereich gibt es
    nicht, die Liste zeigte Kunden. Das Skript der vom Server gezeichneten Seite in node."""
    from app.routers.pages import router as pages_router
    from tests.gerenderte_seite import gerenderte_seite

    html_text = router_test_client(threaded_db_session, pages_router, role="buero_finanzen").get(adresse).text
    ergebnis = im_browser(gerenderte_seite(html_text, "init()"), SPEICHERN_FETCH)["ergebnis"]
    assert ergebnis == {"ziel": ziel, "meldung": ""}


def test_jeder_stammdatenbereich_hat_einen_bereich_der_liste():
    """Jedes Ziel nach dem Speichern (und jeder Zurück-Link) ist ein Bereich, den die Liste kennt (viewFromHash in master_data.html)."""
    from app.routers.pages import STAMMDATEN_BEREICHE

    quelle = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    bekannt = set(re.findall(r"'(\w+)'", re.search(r"function viewFromHash\(\)\{.*?\[(.*?)\]", quelle, flags=re.S).group(1)))
    assert {bereich for bereich, _ in STAMMDATEN_BEREICHE.values()} <= bekannt
    assert "resources" not in bekannt  # der Bereich, auf den das Formular bis 1.8.146 sprang


# ---------------------------------------------------------------------------
# 6. Auftrag: Menge und Einheitspreis mit Tausenderpunkt
# ---------------------------------------------------------------------------

@nur_mit_node
def test_zahltext_mit_tausenderpunkt_und_zurueck():
    """Seit 1.8.148 setzt zahlText(wert, stellen, {tausender: true}) den Tausenderpunkt; zahlLesen() liest ihn unverändert zurück.
    Ohne die Option wie bisher ohne Punkt (tests/test_v414_zahleneingaben.py)."""
    faelle = [[12345.678, None], [1234.56, None], [-1234.5, 2], [999, None], [1250, None], [1234567.891, None], [0.5, None],
              ["12345.678", None], [None, None]]
    ergebnis = _js(f"process.stdout.write(JSON.stringify({json.dumps(faelle)}.map(([w,s])=>zahlText(w,s===null?undefined:s,{{tausender:true}}))));")
    assert ergebnis == ["12.345,678", "1.234,56", "-1.234,50", "999", "1.250", "1.234.567,891", "0,5", "12.345,678", ""]
    werte = [0, 7.5, 1250, 1250.5, 999999.99, -3.75, 1234567.891, 12345.678, 100000]
    assert _js(f"process.stdout.write(JSON.stringify({json.dumps(werte)}.map(w=>zahlLesen(zahlText(w,undefined,{{tausender:true}})))));") == werte
    assert _js("process.stdout.write(JSON.stringify(zahlText(12345.678)));") == "12345,678"


@nur_mit_node
def test_auftrag_zeigt_menge_und_ep_mit_tausenderpunkt():
    """Bis 1.8.147 standen Menge und Einheitspreis im LV des Auftrags ohne Tausenderpunkt („12345,678“, „1234,56“)."""
    position = {"id": 4, "position_number": "1", "short_text": "Dach", "quantity": "12345.678", "unit": "m²", "unit_price": "1234.56",
                "line_total": "15241480.23", "include_in_total": True}
    lauf = im_browser(seite("order.html", "load().catch(e=>document.querySelector('main')"), f"""
      order = {{order_lock: null, items: [{json.dumps(position)}]}}; units = [];
      const zeile = rowHtml({json.dumps(position)});
      openItem(4);
      return {{menge: /data-feld="Menge" value="([^"]*)"/.exec(zeile)[1], ep: /data-feld="Einheitspreis" value="([^"]*)"/.exec(zeile)[1],
               dialogMenge: _element('iQty').value, dialogEp: _element('iPrice').value}};""")
    assert lauf["ergebnis"] == {"menge": "12.345,678", "ep": "1.234,56", "dialogMenge": "12.345,678", "dialogEp": "1.234,56"}


# ---------------------------------------------------------------------------
# 7. Links nach /users nur für Administratoren (Wächter)
# ---------------------------------------------------------------------------

def _links_nach_users(text):
    """Jeder Verweis auf die Seite /users (nicht /api/users): href, Navigation und Zeichenketten in Skripten."""
    return re.findall(r"""(?:href=|location\.href\s*=\s*|location\.assign\(|window\.open\()["'`]/users(?:[?#"'`])""", text) + \
        re.findall(r"""["'`]/users["'`]""", text)


def test_links_nach_users_nur_fuer_admins(threaded_db_session, router_test_client):
    """Seit 1.8.134 ist /users nur für Administratoren (Festlegung 1.8.134 Nr. 1, bestätigt 19.10.2026). Jede Seite, gezeichnet in jeder
    anderen Rolle, verweist nicht dorthin; als Admin führen die Einstellungen hin. Der Stand war schon so (der einzige Link steht seit
    1.8.112 in den Einstellungen unter „nur Admin“) -- der Test hält ihn fest."""
    from app.routers.pages import router as pages_router
    from tests.test_v218_template_rendering import _dummy_path

    pfade = [_dummy_path(r.path) for r in pages_router.routes
             if "GET" in getattr(r, "methods", set()) and r.path not in ("/health", "/users")]
    gefunden, gezeichnet = {}, 0
    for rolle in ("buero_finanzen", "buero_auftrag", "field"):
        client = router_test_client(threaded_db_session, pages_router, role=rolle)
        for pfad in pfade:
            antwort = client.get(pfad, follow_redirects=False)
            if antwort.status_code != 200:
                continue
            gezeichnet += 1
            if _links_nach_users(antwort.text):
                gefunden.setdefault(rolle, []).append(pfad)
    assert gezeichnet > 100 and gefunden == {}
    einstellungen = router_test_client(threaded_db_session, pages_router, role="admin").get("/settings").text
    assert 'href="/users"' in einstellungen  # Kontrolle: als Admin da


def test_verweise_nach_users_nur_in_den_einstellungen_fuer_admins():
    """Auch Verweise, die erst ein Skript baut: in den Vorlagen steht /users nur in settings.html (hinter „nur Admin“) und in
    users.html selbst (Rücksprung nach dem Abmelden)."""
    from tests.vorlagen_js import alle_vorlagen

    stellen = {name for name in alle_vorlagen() if _links_nach_users((TEMPLATES / name).read_text(encoding="utf-8"))
               or "next=/users" in (TEMPLATES / name).read_text(encoding="utf-8")}
    assert stellen == {"settings.html", "users.html"}
    quelle = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    link = quelle.index('href="/users"')
    davor = quelle[:link]
    assert davor.rfind("{% if ist_admin %}") > davor.rfind("{% endif %}")  # innerhalb des Blocks „nur Admin“


# ---------------------------------------------------------------------------
# 8. /api/audit-logs: Versatz geprüft, nie 500; Namen der Historie lesbar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("abfrage,status,leer", [
    ("offset=-1", 422, None),               # bis 1.8.149: 200, still als 0 gelesen
    ("offset=x", 422, None),
    ("offset=1.5", 422, None),
    ("offset=1000000", 200, True),          # über dem Ende: leere Seite (aus der Datenbank)
    (f"offset={2**62}", 200, True),
    (f"offset={2**63}", 200, True),         # bis 1.8.149: OverflowError, 500
    (f"offset={10**30}", 200, True),        # ebenso
    (f"project_id={10**30}", 200, True),    # ebenso
    (f"limit={10**30}", 200, False),
    ("limit=-5", 200, False),
    ("offset=0", 200, False),
])
def test_audit_logs_versatz_nie_500(threaded_db_session, router_test_client, abfrage, status, leer):
    from app.routers import audit

    client = router_test_client(threaded_db_session, audit.router)  # Grunddaten schreiben Einträge, die Liste ist nicht leer
    antwort = client.get("/api/audit-logs?" + abfrage)
    assert antwort.status_code == status, antwort.text
    if status == 200:
        assert (antwort.json() == []) is leer
        if leer:
            assert antwort.headers["x-dk-weitere"] == "0"


def test_namen_der_historie_sind_lesbar():
    """Seit 1.8.138 (tests/test_v436_fehlerrunde_vor_stufe_2.py) hat jede protokollierte Art und jedes protokollierte Feld einen Namen.
    Seit 1.8.150 dazu: der Name ist lesbar -- nicht leer, nicht der technische Name selbst, kein Unterstrich, keine Klassenschreibweise."""
    from sqlalchemy import inspect as sa_inspect

    from app.audit import AUDITED_TYPES, EXCLUDED_FIELDS, FIELD_LABELS, TYPE_LABELS

    technisch = re.compile(r"[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+")
    arten = {cls.__name__: TYPE_LABELS.get(cls, "") for cls in AUDITED_TYPES}
    felder = {a.key: FIELD_LABELS.get(a.key, "") for cls in AUDITED_TYPES for a in sa_inspect(cls).column_attrs
              if a.key not in EXCLUDED_FIELDS and a.key != "id"}
    assert len(arten) > 50 and len(felder) > 300
    assert {k: v for k, v in arten.items() if not v.strip() or v == k or technisch.fullmatch(v) or "_" in v} == {}
    assert {k: v for k, v in felder.items() if not v.strip() or v == k or "_" in v or technisch.fullmatch(v)} == {}
