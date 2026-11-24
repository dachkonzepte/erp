"""Stau-Hinweis des Postboten auf „Start“ (seit 1.11.7, Stufe P1c; Bauplan P1, Abschnitt 4): „wartet“, wenn ein Auftrag länger als 2 Minuten wartet,
„fehler“, wenn der zuletzt erledigte scheiterte -- fester Text, ab Büro – Auftrag, nur mit eingeschaltetem Modul. Klicktest: scripts/klicktest_portal_stau.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import Customer, EnabledModule, PortalPost, PortalSitzung, PortalZugang
from app.portal_postbote import STAU_TEXTE, stau
from app.routers import kundenportal
from tests.vorlagen_js import zusammensetzen

JETZT = datetime(2026, 11, 24, 9, 0)


@pytest.fixture
def welt(db_session):
    db = db_session
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", portal_aktiv=True)
    db.add(kunde)
    db.flush()
    zugang = PortalZugang(customer_id=kunde.id, email="max@example.invalid", email_anzeige="m***@example.invalid")
    db.add(zugang)
    db.flush()
    sitzung = PortalSitzung(zugang_id=zugang.id, wert_sha256="b" * 64, angelegt_am=JETZT, laeuft_ab=JETZT + timedelta(minutes=15))
    db.add(sitzung)
    db.commit()

    def auftrag(status="wartet", vor=timedelta(minutes=1), erledigt_vor=None):
        db.add(PortalPost(art="code", zugang_id=zugang.id, sitzung_id=sitzung.id, angefordert_am=JETZT - vor, status=status,
                          erledigt_am=None if erledigt_vor is None else JETZT - erledigt_vor))
        db.commit()

    return db, auftrag


def test_ohne_auftraege_kein_stau(welt):
    db, _a = welt
    assert stau(db, JETZT) is None


@pytest.mark.parametrize("vor, erwartet", [(timedelta(seconds=119), None), (timedelta(seconds=121), "wartet")])
def test_wartet_laenger_als_zwei_minuten(welt, vor, erwartet):
    db, auftrag = welt
    auftrag(vor=vor)
    assert stau(db, JETZT) == erwartet


@pytest.mark.parametrize("folge, erwartet", [
    ((("fehler", 5),), "fehler"),
    ((("fehler", 5), ("gesendet", 4)), None),          # danach ging einer hinaus
    ((("gesendet", 5), ("fehler", 4)), "fehler"),
    ((("fehler", 5), ("verworfen", 4)), "fehler"),     # verworfen ist kein Versand -- der letzte Versand scheiterte
    ((("verworfen", 5),), None),
])
def test_der_zuletzt_versuchte_versand_zaehlt(welt, folge, erwartet):
    db, auftrag = welt
    for status, minuten in folge:
        auftrag(status=status, vor=timedelta(minutes=minuten + 1), erledigt_vor=timedelta(minutes=minuten))
    assert stau(db, JETZT) == erwartet


def test_texte_fest():
    assert set(STAU_TEXTE) == {"wartet", "fehler"}
    assert all(t.startswith("Kundenportal: ") for t in STAU_TEXTE.values())


def test_schnittstelle_nur_mit_modul(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = router_test_client(db, kundenportal.router)
    assert client.get("/api/kundenportal/postbote").status_code == 403  # ab Werk aus (AB_WERK_AUS)
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    db.commit()
    # seit 1.11.9 mit Auftrag und „erledigen“ (Antwort 1.11.7-1)
    assert client.get("/api/kundenportal/postbote").json() == {"stau": None, "text": None, "post_id": None, "erledigen": False}


def test_startseite_fragt_nur_mit_modul():
    """Die Seite fragt nur, wenn das Modul an ist (Jinja), und setzt den Text nur über textContent."""
    seite = zusammensetzen("dashboard.html")[0]
    assert "is_module_enabled('kundenportal')" in seite
    assert "lesen('portal-stau'" in seite and "api('/api/kundenportal/postbote')" in seite
    assert "getElementById('portalStauText').textContent=" in seite
