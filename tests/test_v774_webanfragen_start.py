"""Version 1.10.2 (Stufe W1a): neue Anfragen der Webseite fallen dem Büro auf der Startseite auf -- Standard-Widget „Anfragen der Webseite“.

    Ort         die Startseite des Büros („Start“, Dashboard) -- „Heute“ ist die Seite der Monteurin; ein Standard-Widget direkt unter „Meine Aufgaben“
                (sort_order 12), das nach der Regel von 1.8.18 auch gespeicherte Layouts erreicht; bewusst entfernt bleibt entfernt
    Inhalt      Zahl im Eingang (davon Spamverdacht, zu prüfen) mit Weg zum Eingang, die fünf neuesten mit Weg zur Anfrage, Fehler des letzten Laufs,
                ohne Schlüssel „noch nicht eingerichtet“; jeder Wert über esc()
    Liste       GET /api/webanfragen?anzahl=1…500
"""

import json
from datetime import datetime

import pytest

from app.dashboard import DEFAULT_WIDGETS, get_widget_layout, save_widget_layout
from app.models import AppUser, WebAnfrage
from app.routers import webanfragen as router_modul
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

BOESE = '<img src=x onerror="window.__boese=1">'


def test_standard_widget_unter_meine_aufgaben(db_session):
    assert [w["widget_key"] for w in DEFAULT_WIDGETS][:2] == ["my_tasks", "webanfragen"]
    assert next(w for w in DEFAULT_WIDGETS if w["widget_key"] == "webanfragen") == {"widget_key": "webanfragen", "sort_order": 12, "visible": True}
    db = db_session
    alt = AppUser(username="alt", display_name="Alt", role="buero_auftrag", password_hash="-")
    weg = AppUser(username="weg", display_name="Weg", role="buero_auftrag", password_hash="-")
    db.add_all([alt, weg])
    db.commit()
    save_widget_layout(db, alt.id, [{"widget_key": "my_tasks", "sort_order": 10, "visible": True},
                                    {"widget_key": "kpis", "sort_order": 20, "visible": True}])  # gespeichert vor 1.10.2
    assert [w["widget_key"] for w in get_widget_layout(db, alt.id)][:2] == ["my_tasks", "webanfragen"]
    save_widget_layout(db, weg.id, [{"widget_key": "webanfragen", "sort_order": 12, "visible": False}])
    assert next(w for w in get_widget_layout(db, weg.id) if w["widget_key"] == "webanfragen")["visible"] is False


def test_liste_mit_anzahl(threaded_db_session, router_test_client):
    db = threaded_db_session
    for i in range(7):
        db.add(WebAnfrage(nummer=f"R-20261119-09{i:02d}-0A0{i}", fassung="dk-anfrage/1", eingang_am=datetime(2026, 11, 19, 8, i), umschlag="{}",
                          umschlag_sha256="0" * 64, status="neu"))
    db.commit()
    c = router_test_client(db, router_modul.router, role="buero_auftrag")
    assert [z["nummer"][-4:] for z in c.get("/api/webanfragen?anzahl=5").json()] == ["0A06", "0A05", "0A04", "0A03", "0A02"]
    assert len(c.get("/api/webanfragen").json()) == 7
    assert c.get("/api/webanfragen?anzahl=0").status_code == 422 and c.get("/api/webanfragen?anzahl=501").status_code == 422


def _widget(stand: dict, liste: list) -> str:
    ablauf = ("authStatus = {authenticated: true, user: {role: 'buero_auftrag'}}; const c = _element('w');"
              "await renderWebanfragenWidget(c); return c.innerHTML;")
    return im_browser(seite("dashboard.html", "\ninit();"), ablauf, {"/api/webanfragen/stand": stand, "/api/webanfragen?anzahl=5": liste})["ergebnis"]


STAND = {"eingerichtet": True, "laeuft": False, "letzter_lauf_am": "2026-11-19T08:11:00", "letzter_erfolg_am": "2026-11-19T08:11:00",
         "letzter_fehler": None, "letzte_neu": 2, "nicht_abgeholt": [], "neu": 2, "pruefliste": 3, "spamverdacht": 1, "pruefen": 1}
ZEILE = {"id": 9, "nummer": "W-20261119-0912-0E3F", "art": "wartung", "art_name": BOESE, "fassung": "dk-anfrage/1", "eingang_am": "2026-11-19T08:12:00",
         "betreff": BOESE, "kontakt_name": BOESE, "spamverdacht": True, "pruefen_grund": "unbekannte Art", "status": "neu",
         "abgeholt_am": "2026-11-19T08:13:00", "gemeldet_am": None, "dateien": 0}


@nur_mit_node
def test_widget_zeigt_zahl_und_die_neuesten():
    html = _widget(STAND, [ZEILE])
    # seit 1.10.4: Spamverdacht und „zu prüfen“ zählen in der Prüfliste, mit Weg dorthin
    assert '<a href="/anfragen/webseite" ' in html and '2 im Eingang</a> · <a href="/anfragen/webseite#pruefliste"' in html and "3 in der Prüfliste</a>" in html
    assert 'href="/anfragen/webseite/9"' in html and "W-20261119-0912-0E3F · Spamverdacht · zu prüfen" in html and "19.11.2026" in html
    assert "<img" not in html and "&lt;img src=x" in html


@nur_mit_node
def test_widget_leer_ohne_schluessel_und_mit_fehler():
    leer = _widget(dict(STAND, eingerichtet=False, neu=0, spamverdacht=0, pruefen=0), [])
    assert "Keine Anfragen der Webseite im Eingang." in leer and "noch nicht eingerichtet" in leer
    fehler = _widget(dict(STAND, letzter_fehler=BOESE), [])
    assert "Letzter Lauf: &lt;img" in fehler and "<img" not in fehler


@nur_mit_node
def test_widget_nur_fuer_buero():
    ablauf = ("authStatus = {authenticated: true, user: {role: 'field'}}; const c = _element('w'); await renderWebanfragenWidget(c);"
              "return [c.innerHTML, AUFRUFE.length];")
    assert im_browser(seite("dashboard.html", "\ninit();"), ablauf)["ergebnis"] == ['<div class="muted small">Nur für Büro und Admin verfügbar.</div>', 0]
