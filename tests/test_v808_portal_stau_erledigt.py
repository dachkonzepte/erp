"""Stau-Hinweis des Postboten auf „Start“, überarbeitet (seit 1.11.9, Antwort 1.11.7-1/-3): Gestaltung wie die übrigen Warnhinweise, Link „Versandprotokoll
öffnen“ (gefiltert auf die Anmeldecodes), Text je Rolle (den Dienst erp-portalpost nennt nur der Text für den Admin), „Erledigt“ für den Admin an einem
gescheiterten Versand -- Name und Zeit in der Änderungshistorie, ein neuer Fehler zeigt den Hinweis wieder. Klicktest: scripts/klicktest_portal_stau.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AuditLog, Customer, EnabledModule, PortalPost, PortalSitzung, PortalZugang
from app.portal_postbote import ERLEDIGT_AKTION, STAU_TEXTE, STAU_TEXTE_ADMIN, StauVeraltet, erledigen, stau, stau_stand
from app.routers import kundenportal
from tests.portal_webseite import webseite_setzen
from tests.vorlagen_js import zusammensetzen

JETZT = datetime(2026, 11, 24, 9, 0)


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    webseite_setzen(db)  # seit 1.11.47: sonst stünde der Hinweis auf fehlende Pflichtangaben in jeder Antwort
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", portal_aktiv=True)
    db.add(kunde)
    db.flush()
    zugang = PortalZugang(customer_id=kunde.id, email="max@example.invalid", email_anzeige="m***@example.invalid")
    db.add(zugang)
    db.flush()
    sitzung = PortalSitzung(zugang_id=zugang.id, wert_sha256="c" * 64, angelegt_am=JETZT, laeuft_ab=JETZT + timedelta(minutes=15))
    db.add(sitzung)
    db.commit()

    def auftrag(status, minuten):
        post = PortalPost(art="code", zugang_id=zugang.id, sitzung_id=sitzung.id, angefordert_am=JETZT - timedelta(minutes=minuten + 1),
                          status=status, erledigt_am=None if status == "wartet" else JETZT - timedelta(minutes=minuten))
        db.add(post)
        db.commit()
        return post.id

    return db, auftrag


def test_texte_je_rolle():
    assert STAU_TEXTE["wartet"] == ("Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte den Administrator "
                                    "informieren.")
    assert STAU_TEXTE_ADMIN["wartet"] == ("Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte prüfen, ob der Postbote "
                                          "läuft (Dienst erp-portalpost).")
    assert STAU_TEXTE["fehler"] == STAU_TEXTE_ADMIN["fehler"] == ("Kundenportal: Der letzte Anmeldecode ging nicht hinaus – bitte im Versandprotokoll "
                                                                   "nachsehen.")
    assert all("erp-portalpost" not in t for t in STAU_TEXTE.values())


def test_erledigt_beendet_den_hinweis_ein_neuer_fehler_zeigt_ihn_wieder(welt):
    db, auftrag = welt
    erster = auftrag("fehler", 10)
    assert stau_stand(db, JETZT) == ("fehler", erster)
    erledigen(db, erster, jetzt_=JETZT, user_id=None, user_name="Admin Muster")
    assert stau_stand(db, JETZT) == (None, None) and stau(db, JETZT) is None
    post = db.get(PortalPost, erster)
    assert (post.quittiert_am, post.quittiert_von_name) == (JETZT, "Admin Muster")
    zweiter = auftrag("fehler", 5)
    assert stau_stand(db, JETZT) == ("fehler", zweiter)  # ein neuer Fehler zeigt den Hinweis wieder
    auftrag("gesendet", 3)
    assert stau_stand(db, JETZT) == (None, None)  # ein späterer Versand beendet ihn wie bisher


def test_erledigt_nur_am_aktuellen_fehler(welt):
    db, auftrag = welt
    erster = auftrag("fehler", 10)
    zweiter = auftrag("fehler", 5)
    with pytest.raises(StauVeraltet):  # der Admin sah den ersten; inzwischen scheiterte der zweite
        erledigen(db, erster, jetzt_=JETZT, user_id=None, user_name="Admin Muster")
    erledigen(db, zweiter, jetzt_=JETZT, user_id=None, user_name="Admin Muster")
    with pytest.raises(StauVeraltet):  # nicht zweimal
        erledigen(db, zweiter, jetzt_=JETZT, user_id=None, user_name="Admin Muster")
    with pytest.raises(StauVeraltet):  # unbekannt
        erledigen(db, 999999, jetzt_=JETZT, user_id=None, user_name="Admin Muster")
    gesendet = auftrag("gesendet", 1)
    with pytest.raises(StauVeraltet):  # ein gesendeter ist kein Fehler
        erledigen(db, gesendet, jetzt_=JETZT, user_id=None, user_name="Admin Muster")


def test_wartet_laesst_sich_nicht_erledigen(welt):
    db, auftrag = welt
    auftrag("fehler", 10)
    wartet = auftrag("wartet", 5)
    assert stau_stand(db, JETZT) == ("wartet", None)  # „wartet“ geht vor
    with pytest.raises(StauVeraltet):
        erledigen(db, wartet, jetzt_=JETZT, user_id=None, user_name="Admin Muster")


def test_schnittstelle_je_rolle(welt, router_test_client):
    db, auftrag = welt
    fehler = auftrag("fehler", 10)
    buero = router_test_client(db, kundenportal.router, role="buero_auftrag")
    admin = router_test_client(db, kundenportal.router, role="admin", user_id=7, display_name="Admin Muster")
    assert buero.get("/api/kundenportal/postbote").json() == {"stau": "fehler", "text": STAU_TEXTE["fehler"], "post_id": fehler, "erledigen": False,
                                                              "pflicht": None}
    assert admin.get("/api/kundenportal/postbote").json() == {"stau": "fehler", "text": STAU_TEXTE["fehler"], "post_id": fehler, "erledigen": True,
                                                              "pflicht": None}
    for rolle in ("buero_auftrag", "buero_finanzen"):
        r = router_test_client(db, kundenportal.router, role=rolle).post("/api/kundenportal/postbote/erledigt", json={"post_id": fehler})
        assert r.status_code == 403
    assert admin.post("/api/kundenportal/postbote/erledigt", json={"post_id": fehler + 1}).status_code == 409
    r = admin.post("/api/kundenportal/postbote/erledigt", json={"post_id": fehler})
    assert r.status_code == 200 and r.json() == {"stau": None, "text": None, "post_id": None, "erledigen": False, "pflicht": None}
    [eintrag] = db.scalars(select(AuditLog).where(AuditLog.action == ERLEDIGT_AKTION)).all()
    assert (eintrag.entity_id, eintrag.actor_name, eintrag.actor_user_id) == (str(fehler), "Admin Muster", 7)
    assert admin.post("/api/kundenportal/postbote/erledigt", json={"post_id": fehler}).status_code == 409  # schon erledigt
    auftrag("wartet", 5)
    assert buero.get("/api/kundenportal/postbote").json()["text"] == STAU_TEXTE["wartet"]
    assert admin.get("/api/kundenportal/postbote").json() == {"stau": "wartet", "text": STAU_TEXTE_ADMIN["wartet"], "post_id": None,
                                                              "erledigen": False, "pflicht": None}


def test_erledigt_nur_mit_modul(welt, router_test_client):
    db, auftrag = welt
    fehler = auftrag("fehler", 10)
    db.query(EnabledModule).filter_by(module_key="kundenportal").update({"enabled": False})
    db.commit()
    admin = router_test_client(db, kundenportal.router, role="admin")
    assert admin.post("/api/kundenportal/postbote/erledigt", json={"post_id": fehler}).status_code == 403
    assert db.get(PortalPost, fehler).quittiert_am is None


def test_startseite_warnhinweis_mit_link_und_erledigt():
    seite = zusammensetzen("dashboard.html")[0]
    assert 'href="/versandprotokoll?typ=portal_code"' in seite and ">Versandprotokoll öffnen</a>" in seite
    assert 'data-klick="portal-stau-erledigt"' in seite and "abschliessen('portal-stau'" in seite
    assert "api('/api/kundenportal/postbote/erledigt'" in seite
    assert "getElementById('portalStauErledigt').hidden=!d.erledigen" in seite
    assert ".portal-stau{" in seite and "border-left:4px solid var(--ds-warn-text)" in seite and "background:var(--ds-warn-hell)" in seite


def test_versandprotokoll_filtert_die_arten_des_portals():
    seite = zusammensetzen("email_dispatches.html")[0]
    assert "{% if is_module_enabled('kundenportal') %}" in seite
    assert '<option value="portal_link">Link zum Kundenportal</option>' in seite
    assert '<option value="portal_code">Anmeldecode des Kundenportals</option>' in seite


def test_migration_legt_genau_die_spalten_des_modells_an():
    """Migration c8e2f5a1d394 auf einer Tabelle portal_post ohne die drei Spalten: danach wie das Modell, rückwärts wieder ohne."""
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Column, MetaData, Table, create_engine, inspect

    datei = next((Path(__file__).resolve().parents[1] / "alembic" / "versions").glob("*_portal_post_erledigt.py"))
    spec = importlib.util.spec_from_file_location("mig_portal_post_erledigt", datei)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    neu = {"quittiert_am", "quittiert_von_user_id", "quittiert_von_name"}
    modell = PortalPost.__table__
    meta = MetaData()
    Table("portal_post", meta, *[Column(c.name, c.type, nullable=c.nullable, primary_key=c.primary_key) for c in modell.columns if c.name not in neu])
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            meta.create_all(conn)
            ops = Operations(MigrationContext.configure(conn))
            mig.op = ops
            mig.upgrade()
            spalten = {s["name"]: s for s in inspect(conn).get_columns("portal_post")}
            for name in neu:
                assert spalten[name]["nullable"] is True
                assert str(spalten[name]["type"]) == str(modell.c[name].type.compile(engine.dialect)), name
            assert set(spalten) == {c.name for c in modell.columns}
            mig.downgrade()
            assert not neu & {s["name"] for s in inspect(conn).get_columns("portal_post")}
    finally:
        engine.dispose()
