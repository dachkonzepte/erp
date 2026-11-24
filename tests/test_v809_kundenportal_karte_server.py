"""Kundenportal am Kunden -- Schalter, Zugang, Link senden, sperren, entsperren, verlängern, Protokoll (seit 1.11.10, Stufe P1d; Bauplan P1, Abschnitt 4).

Über router_test_client mit der Graph-Attrappe aus tests/test_v804_portal_mails.py; der Link steht nur in der Mail, gespeichert ist sein Prüfwert.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import kundenportal as kp
from app.berlin_time import utc_jetzt
from app.email_sending import set_send_method
from app.models import AuditLog, Customer, EmailDispatch, EnabledModule, PortalSitzung, PortalZugang, PortalZugriff
from app.portal import pruefwerte
from app.routers import kundenportal
from tests.test_v321_email_dispatch import _configure_graph, _configure_smtp
from tests.test_v804_portal_mails import GraphMitAnfrage

LINK_IM_TEXT = re.compile(r'href="(https://kunde\.dachkonzepte\.gmbh/#z=([A-Za-z0-9_-]{43}))"')


@pytest.fixture
def graph(monkeypatch):
    fake = GraphMitAnfrage()
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", fake)
    return fake


@pytest.fixture
def welt(threaded_db_session, router_test_client, graph):
    db = threaded_db_session
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", email="max@example.invalid")
    db.add(kunde)
    db.commit()
    _configure_graph(db)
    client = router_test_client(db, kundenportal.router, role="buero_auftrag", user_id=11, display_name="Auri Auftrag")
    return db, kunde, client, graph


def _url(kunde, rest=""):
    return f"/api/customers/{kunde.id}/portal{rest}"


def _an_mit_zugang(client, kunde, email="max@example.invalid"):
    assert client.post(_url(kunde, "/schalter"), json={"an": True}).status_code == 200
    r = client.post(_url(kunde, "/zugang"), json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()


def _senden(client, kunde, schluessel, email="max@example.invalid"):
    return client.post(_url(kunde, "/link"), json={"email": email, "dispatch_key": schluessel})


def test_zustaende_der_reihe_nach(welt):
    db, kunde, client, graph = welt
    assert client.get(_url(kunde)).json()["zustand"] == "aus"
    client.post(_url(kunde, "/schalter"), json={"an": True})
    assert client.get(_url(kunde)).json()["zustand"] == "kein_zugang"
    stand = client.post(_url(kunde, "/zugang"), json={"email": "max@example.invalid"}).json()
    assert stand["zustand"] == "ohne_link" and stand["zugang"]["email"] == "max@example.invalid" and not stand["zugang"]["hat_link"]
    zugang = db.scalar(select(PortalZugang))
    assert zugang.email_anzeige == "m***@example.invalid" and zugang.angelegt_von_name == "Auri Auftrag"
    stand = _senden(client, kunde, "portal-link-test-0001").json()
    assert stand["zustand"] == "aktiv" and stand["versand"]["status"] == "gesendet"
    db.expire_all()
    zugang = db.scalar(select(PortalZugang))
    zugang.gueltig_bis = utc_jetzt() + timedelta(days=20)
    db.commit()
    assert client.get(_url(kunde)).json()["zustand"] == "laeuft_ab"
    zugang.gueltig_bis = utc_jetzt() - timedelta(minutes=1)
    db.commit()
    assert client.get(_url(kunde)).json()["zustand"] == "abgelaufen"
    assert client.post(_url(kunde, "/verlaengern")).json()["zustand"] == "aktiv"
    stand = client.post(_url(kunde, "/sperren"), json={"grund": "Kunde hat das Handy verloren"}).json()
    assert stand["zustand"] == "gesperrt" and stand["zugang"]["gesperrt_grund"] == "Kunde hat das Handy verloren"
    assert stand["zugang"]["gesperrt_von"] == "Auri Auftrag"
    assert client.post(_url(kunde, "/entsperren")).json()["zustand"] == "aktiv"
    assert client.post(_url(kunde, "/schalter"), json={"an": False}).json()["zustand"] == "aus"


def test_ohne_email_am_kunden_kein_zugang(welt):
    db, kunde, client, _g = welt
    kunde.email = None
    db.commit()
    client.post(_url(kunde, "/schalter"), json={"an": True})
    assert client.get(_url(kunde)).json()["zustand"] == "ohne_email"
    r = client.post(_url(kunde, "/zugang"), json={"email": "max@example.invalid"})
    assert r.status_code == 409 and r.json()["detail"] == "Erst eine E-Mail-Adresse beim Kunden eintragen."


def test_zugang_nur_mit_portal_an_und_nur_einer(welt):
    db, kunde, client, _g = welt
    assert client.post(_url(kunde, "/zugang"), json={"email": "max@example.invalid"}).status_code == 409  # Portal aus
    _an_mit_zugang(client, kunde)
    assert client.post(_url(kunde, "/zugang"), json={"email": "max@example.invalid"}).status_code == 409
    for falsch in ("", "keine-adresse", "a@example.invalid, b@example.invalid"):
        assert client.post(_url(kunde, "/zugang"), json={"email": falsch}).status_code in (400, 409, 422)


def test_link_nur_als_pruefwert_und_mail_mit_genau_diesem_link(welt):
    db, kunde, client, graph = welt
    _an_mit_zugang(client, kunde)
    assert _senden(client, kunde, "portal-link-test-0002").status_code == 200
    [anfrage] = graph.anfragen
    assert anfrage["saveToSentItems"] == "false" and anfrage["message"]["subject"] == "Ihr Zugang zum Kundenportal"
    [(adresse, wert)] = LINK_IM_TEXT.findall(anfrage["message"]["body"]["content"])
    db.expire_all()
    zugang = db.scalar(select(PortalZugang))
    assert zugang.link_sha256 == pruefwerte.link(wert)
    gespeichert = " ".join(str(v) for t in (PortalZugang, EmailDispatch, AuditLog) for row in db.scalars(select(t)).all() for v in row.__dict__.values())
    assert wert not in gespeichert and zugang.link_sha256 not in gespeichert.replace(zugang.link_sha256, "", 1)  # Prüfwert nicht in der Historie
    [zeile] = db.scalars(select(EmailDispatch)).all()
    assert (zeile.document_type, zeile.document_id, zeile.created_by_name) == ("portal_link", zugang.id, "Auri Auftrag")


def test_zweiter_link_macht_den_ersten_ungueltig_und_meldet_alle_geraete_ab(welt):
    db, kunde, client, graph = welt
    _an_mit_zugang(client, kunde)
    _senden(client, kunde, "portal-link-test-0003")
    db.expire_all()
    zugang = db.scalar(select(PortalZugang))
    erster = zugang.link_sha256
    jetzt = utc_jetzt()
    db.add(PortalSitzung(zugang_id=zugang.id, wert_sha256="d" * 64, angelegt_am=jetzt, bestaetigt_am=jetzt, laeuft_ab=jetzt + timedelta(days=30)))
    db.commit()
    _senden(client, kunde, "portal-link-test-0004", email="neu@example.invalid")
    db.expire_all()
    zugang = db.scalar(select(PortalZugang))
    assert zugang.link_sha256 != erster and zugang.email == "neu@example.invalid" and zugang.email_anzeige == "n***@example.invalid"
    sitzung = db.scalar(select(PortalSitzung))
    assert sitzung.beendet_am is not None and sitzung.beendet_grund == "neu_erzeugt"
    assert [r["emailAddress"]["address"] for r in graph.anfragen[-1]["message"]["toRecipients"]] == ["neu@example.invalid"]


def test_derselbe_klick_erzeugt_nichts_neues(welt):
    db, kunde, client, graph = welt
    _an_mit_zugang(client, kunde)
    _senden(client, kunde, "portal-link-test-0005")
    db.expire_all()
    erster = db.scalar(select(PortalZugang)).link_sha256
    assert _senden(client, kunde, "portal-link-test-0005").status_code == 200
    db.expire_all()
    assert db.scalar(select(PortalZugang)).link_sha256 == erster and len(graph.anfragen) == 1


def test_smtp_lehnt_ab_und_nichts_aendert_sich(welt, monkeypatch):
    db, kunde, client, graph = welt
    _an_mit_zugang(client, kunde)
    _configure_smtp(db)
    set_send_method(db, "smtp")
    r = _senden(client, kunde, "portal-link-test-0006")
    assert r.status_code == 400 and "nur über Microsoft 365" in r.json()["detail"]
    db.expire_all()
    assert db.scalar(select(PortalZugang)).link_sha256 is None and db.scalars(select(EmailDispatch)).all() == []


def test_versand_gescheitert(welt, monkeypatch):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    monkeypatch.setattr("app.email_sending.urllib.request.urlopen", GraphMitAnfrage(fail_status=403, fail_detail="Access is denied."))
    r = _senden(client, kunde, "portal-link-test-0007")
    assert r.status_code == 400
    stand = client.get(_url(kunde)).json()
    assert stand["versand"]["status"] == "fehlgeschlagen" and stand["zustand"] == "aktiv"  # der neue Link gilt, die Mail ging nicht hinaus


def test_sperren_beendet_sitzungen_und_sperrt_weitere_aktionen(welt):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    _senden(client, kunde, "portal-link-test-0008")
    db.expire_all()
    zugang = db.scalar(select(PortalZugang))
    jetzt = utc_jetzt()
    db.add(PortalSitzung(zugang_id=zugang.id, wert_sha256="e" * 64, angelegt_am=jetzt, bestaetigt_am=jetzt, laeuft_ab=jetzt + timedelta(days=30)))
    db.commit()
    assert client.post(_url(kunde, "/sperren"), json={"grund": "   "}).status_code == 422  # Grund Pflicht
    client.post(_url(kunde, "/sperren"), json={"grund": "Verdacht"})
    db.expire_all()
    assert db.scalar(select(PortalSitzung)).beendet_grund == "gesperrt"
    for weg, koerper in (("/link", {"email": "max@example.invalid", "dispatch_key": "portal-link-test-0009"}), ("/verlaengern", None),
                         ("/sperren", {"grund": "noch mal"})):
        assert client.post(_url(kunde, weg), json=koerper).status_code == 409, weg
    client.post(_url(kunde, "/entsperren"))
    assert client.post(_url(kunde, "/entsperren")).status_code == 409


def test_portal_aus_beendet_sitzungen(welt):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    zugang = db.scalar(select(PortalZugang))
    jetzt = utc_jetzt()
    db.add(PortalSitzung(zugang_id=zugang.id, wert_sha256="f" * 64, angelegt_am=jetzt, laeuft_ab=jetzt + timedelta(minutes=15)))
    db.commit()
    client.post(_url(kunde, "/schalter"), json={"an": False})
    db.expire_all()
    assert db.scalar(select(PortalSitzung)).beendet_grund == "portal_aus"


def test_kunde_im_archiv_nur_lesen(welt):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    kunde.archiviert_am = utc_jetzt()
    db.commit()
    stand = client.get(_url(kunde)).json()
    assert stand["nur_lesen"] is True and stand["zustand"] == "archiv"  # im Archiv wirkt kein Zugang -- die Karte sagt es
    for weg, koerper in (("/schalter", {"an": False}), ("/link", {"email": "max@example.invalid", "dispatch_key": "portal-link-test-0010"}),
                         ("/sperren", {"grund": "x"}), ("/entsperren", None), ("/verlaengern", None), ("/zugang", {"email": "max@example.invalid"})):
        assert client.post(_url(kunde, weg), json=koerper).status_code == 409, weg


def test_rollen_und_modul(welt, router_test_client):
    db, kunde, _client, _g = welt
    monteurin = router_test_client(db, kundenportal.router, role="field")
    assert monteurin.get(_url(kunde)).status_code == 403
    assert monteurin.post(_url(kunde, "/schalter"), json={"an": True}).status_code == 403
    db.query(EnabledModule).filter_by(module_key="kundenportal").update({"enabled": False})
    db.commit()
    admin = router_test_client(db, kundenportal.router, role="admin")
    assert admin.get(_url(kunde)).status_code == 403 and admin.post(_url(kunde, "/schalter"), json={"an": True}).status_code == 403
    assert admin.get("/api/customers/999999/portal").status_code == 403  # Modul aus vor allem anderen


def test_unbekannter_kunde_404(welt):
    _db, _k, client, _g = welt
    assert client.get("/api/customers/999999/portal").status_code == 404
    assert client.post("/api/customers/999999/portal/schalter", json={"an": True}).status_code == 404


def test_protokoll_portal_und_historie_zusammen(welt):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    _senden(client, kunde, "portal-link-test-0011")
    zugang = db.scalar(select(PortalZugang))
    db.add(PortalZugriff(zeitpunkt=utc_jetzt(), zugang_id=zugang.id, aktion="link_geoeffnet", ergebnis="code_noetig"))
    db.commit()
    client.post(_url(kunde, "/sperren"), json={"grund": "Test"})
    eintraege = client.get(_url(kunde, "/protokoll")).json()["eintraege"]
    texte = [e["text"] for e in eintraege]
    assert "Link geöffnet – neues Gerät, Code nötig" in texte
    # das Konto setzt im Betrieb die Middleware (der Test-Client hat sie nicht) -- Name im Klicktest klicktest_kundenportal_karte
    assert any(e["art"] == "buero" and e["text"] == "Grund der Sperre: Test" for e in eintraege)  # seit 1.11.11 als Satz
    assert "Zugang gesperrt" in texte and "Zugang angelegt" in texte and "Neuer Link erzeugt" in texte
    assert "Link gesendet an max@example.invalid" in texte  # aus dem Versandprotokoll
    assert not any("Konto" in t or "verdeckt" in t for t in texte)  # keine Buchhaltung des Zugangs
    assert "Kundenportal eingeschaltet" in texte
    assert all(zugang.link_sha256 not in t for t in texte)


def test_protokoll_seitenweise(welt):
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    zugang = db.scalar(select(PortalZugang))
    beginn = datetime(2026, 11, 1, 8, 0)
    db.add_all([PortalZugriff(zeitpunkt=beginn + timedelta(minutes=i), zugang_id=zugang.id, aktion="verlaengert", ergebnis="ok")
                for i in range(55)])  # 50 je Seite (fest -- nicht kp.SEITE, sonst prüft der Test sich selbst)
    db.commit()
    erste = client.get(_url(kunde, "/protokoll")).json()
    zweite = client.get(_url(kunde, "/protokoll?seite=2")).json()
    assert len(erste["eintraege"]) == 50 and erste["weiter"] is True
    assert zweite["weiter"] is False and len(zweite["eintraege"]) >= 5
    zeiten = [e["zeitpunkt"] for e in erste["eintraege"] + zweite["eintraege"]]
    assert zeiten == sorted(zeiten, reverse=True)


def test_texte_fuer_jede_aktion_und_jedes_ergebnis():
    from app.portal.werte import AKTIONEN, ERGEBNISSE
    assert set(kp.AKTION_TEXT) == set(AKTIONEN) and set(kp.ERGEBNIS_TEXT) == set(ERGEBNISSE)


@pytest.mark.parametrize("adresse, anzeige", [("max@example.invalid", "m***@example.invalid"), ("a@b.invalid", "a***@b.invalid"),
                                              ("Ärger.x@beispiel.invalid", "Ä***@beispiel.invalid")])
def test_verdeckte_anzeige(adresse, anzeige):
    assert kp.email_anzeige(adresse) == anzeige


def test_gueltig_zwoelf_monate():
    assert kp.gueltig_bis_ab(datetime(2026, 11, 24, 9, 30)) == datetime(2027, 11, 24, 9, 30)
    assert kp.gueltig_bis_ab(datetime(2028, 2, 29, 12, 0)) == datetime(2029, 2, 28, 12, 0)


def test_verlaengern_nur_mit_link(welt):
    _db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    r = client.post(_url(kunde, "/verlaengern"))
    assert r.status_code == 409 and r.json()["detail"] == "Es gibt noch keinen Link -- erst einen Link senden."


def test_archiv_auch_in_der_geschaeftslogik(welt):
    """Zweite Sicherung neben archiv_vorab() am Router: jede Aktion lehnt einen Kunden im Archiv selbst ab."""
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    kunde.archiviert_am = utc_jetzt()
    db.commit()
    jetzt = utc_jetzt()
    for aktion in (lambda: kp.schalten(db, kunde, False, jetzt), lambda: kp.sperren(db, kunde, "x", jetzt, user_id=None, user_name=None),
                   lambda: kp.entsperren(db, kunde), lambda: kp.verlaengern(db, kunde, jetzt),
                   lambda: kp.link_senden(db, kunde, "max@example.invalid", "portal-link-test-0012", jetzt, user_id=None, user_name=None)):
        with pytest.raises(kp.PortalNicht, match="im Archiv"):
            aktion()


def test_buchhaltung_des_zugangs_verdraengt_im_protokoll_nichts(welt):
    """Seit 1.11.11: Felder, die das Protokoll nicht zeigt (Konto-Kennungen, verdeckte Anzeige), zählen schon in der Abfrage nicht mit -- sonst drängten
    viele neuere solche Einträge die sichtbaren aus der Seite."""
    db, kunde, client, _g = welt
    _an_mit_zugang(client, kunde)
    zugang = db.scalar(select(PortalZugang))
    spaeter = utc_jetzt() + timedelta(hours=1)
    db.add_all([AuditLog(occurred_at=spaeter + timedelta(seconds=i), actor_name="System", action="geändert", entity_type=kp.ZUGANG_ART,
                         entity_id=str(zugang.id), field_name="gesperrt_von_user_id", field_label="Gesperrt von (Konto)", new_value=str(i))
                for i in range(kp.SEITE + 10)])
    db.commit()
    seite = client.get(_url(kunde, "/protokoll")).json()
    texte = [e["text"] for e in seite["eintraege"]]
    assert "Zugang angelegt" in texte and "Kundenportal eingeschaltet" in texte and seite["weiter"] is False
