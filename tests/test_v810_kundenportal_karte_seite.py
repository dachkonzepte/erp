"""Karte „Kundenportal“ in der Kundenakte (seit 1.11.11, Stufe P1d) -- die Seite; das Verhalten prüft scripts/klicktest_kundenportal_karte.py, die
Funktionen stehen in tests/test_v554_kundenakte_funktionen.py::FUNKTIONEN. Dazu der Testschalter ERP_TEST_GRAPH (nur für Test-Instanzen, nur 127.0.0.1).
"""

from __future__ import annotations

import pytest

from app.email_sending import graph_attrappe
from tests import vorlagen_js as vj
from tests.vorlagen_js import zusammensetzen


def test_karte_und_dialoge_nur_mit_modul():
    """Karte und Dialoge stehen in {% if is_module_enabled('kundenportal') %} (ohne Modul gar nicht da), die Seite fragt nur mit Modul. Gezeichnet mit
    und ohne Modul prüft es klicktest_kundenportal_karte (im Test-Client lesen die Jinja-Globals eine eigene Datenbank)."""
    seite = (vj.TEMPLATES / "customer.html").read_text(encoding="utf-8")
    for kennung in ('id="uPortal"', 'id="portalZugangDialog"', 'id="portalLinkDialog"', 'id="portalSperrenDialog"', 'id="portalProtokollDialog"'):
        stelle = seite.index(kennung)
        davor = seite.rindex("{% if is_module_enabled('kundenportal') %}", 0, stelle)
        assert "{% endif %}" not in seite[davor:stelle], kennung
    assert "const PORTAL=\"{{ 'ja' if is_module_enabled('kundenportal') else 'nein' }}\"===\"ja\";" in seite  # ungerendert: ohne Portal
    assert "async function portalLaden(){if(!PORTAL)return;" in seite


def test_texte_nur_als_text():
    """Was vom Server kommt, geht nur über textContent bzw. esc() in die Seite; das Protokoll baut seine Zeilen mit createElement."""
    seite = zusammensetzen("customer.html")[0]
    anfang = seite.index("// --- Kundenportal (seit 1.11.11")
    skript = seite[anfang:seite.index("aktion('kontakt-kunde'", anfang)]
    assert "innerHTML=zeilen.map(([k,w])=>`<dt>${esc(k)}</dt><dd>${esc(w)}</dd>`)" in skript
    assert skript.count("innerHTML") == 1 and "insertAdjacentHTML" not in skript and "outerHTML" not in skript
    assert "el('portalText').textContent=d.zustand_text" in skript and "el('portalHinweis').textContent=hinweis" in skript
    assert "document.createElement('li')" in skript


def test_link_und_sperren_abschliessend_der_rest_speichern():
    seite = zusammensetzen("customer.html")[0]
    for funktion, art in (("portalLinkSenden", "abschliessen"), ("portalSperren", "abschliessen"), ("portalSchalten", "speichern"),
                          ("portalZugangAnlegen", "speichern"), ("portalEntsperren", "speichern"), ("portalVerlaengern", "speichern")):
        rumpf = seite[seite.index(f"async function {funktion}("):]
        rumpf = rumpf[:rumpf.index("\n}\n")]
        assert f"await {art}('portal'," in rumpf, funktion


def test_rueckfrage_vor_ausschalten_entsperren_verlaengern():
    """confirm() (Ja/Nein, Regel 4) vor dem Ausschalten mit Zugang, dem Entsperren und dem Verlängern."""
    seite = zusammensetzen("customer.html")[0]
    for funktion in ("portalSchalten", "portalEntsperren", "portalVerlaengern"):
        rumpf = seite[seite.index(f"async function {funktion}("):]
        rumpf = rumpf[:rumpf.index("\n}\n")]
        assert "if(" in rumpf and "!confirm(" in rumpf, funktion
    assert "prompt(" not in seite


@pytest.mark.parametrize("umgebung, wert, erwartet", [
    ("test", "http://127.0.0.1:8765", "http://127.0.0.1:8765"),
    ("development", "http://127.0.0.1:1", "http://127.0.0.1:1"),
    ("production", "http://127.0.0.1:8765", None),
    (None, "http://127.0.0.1:8765", None),
    ("test", "http://10.0.0.1:8765", None),
    ("test", "https://127.0.0.1:8765", None),
    ("test", "http://127.0.0.1:8765/v1.0", None),
    ("test", "http://localhost:8765", None),
    ("test", "", None),
])
def test_graph_attrappe_nur_fuer_test_instanzen(monkeypatch, umgebung, wert, erwartet):
    if umgebung is None:
        monkeypatch.delenv("ERP_ENV", raising=False)
    else:
        monkeypatch.setenv("ERP_ENV", umgebung)
    monkeypatch.setenv("ERP_TEST_GRAPH", wert)
    assert graph_attrappe() == erwartet


def test_graph_attrappe_lenkt_anmeldung_und_versand_um(db_session, monkeypatch):
    """Mit dem Schalter gehen Anmeldung und sendMail an die Attrappe -- sonst an Microsoft."""
    from app.email_sending import get_graph_access_token, load_smtp_settings
    from tests.test_v321_email_dispatch import _configure_graph

    db = db_session
    _configure_graph(db)
    gesehen = []

    class Antwort:
        def __init__(self, daten):
            self.daten = daten

        def read(self):
            return self.daten

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        gesehen.append(req.full_url)
        return Antwort(b'{"access_token": "x"}')

    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", urlopen)
    monkeypatch.setenv("ERP_ENV", "test")
    monkeypatch.setenv("ERP_TEST_GRAPH", "http://127.0.0.1:8765")
    get_graph_access_token(load_smtp_settings(db))
    monkeypatch.setenv("ERP_ENV", "production")
    get_graph_access_token(load_smtp_settings(db))
    assert gesehen == ["http://127.0.0.1:8765/tenant-1/oauth2/v2.0/token", "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token"]
