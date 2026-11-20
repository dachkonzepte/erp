"""Version 1.10.10 (Stufe W1c): Kontakt vermerken an Anfrage, Projekt und Kunde -- nur Tag und Weg, nie ein Inhalt.

    Vermerken   je Bezug GET/POST …/kontakte, ab Büro – Auftrag; Liste der jüngste Kontakt zuerst; Konto und Zeitpunkt aus der Anmeldung
    Prüfung     Tag nicht in der Zukunft (Berlin), nicht vor 2000; Weg nur aus der festen Liste; jedes weitere Feld 422 (kein Inhalt); unbekannter
                Bezug 404; die Monteurin 403
    Datenbank   genau ein Bezug (CHECK), kein Inhalt (keine Spalte dafür)
    Historie    „Kontakt“ mit Weg und Tag, am Projekt bzw. an der Anfrage eines Projekts im Verlauf der Akte
    Löschen     ein Projekt ohne Auftrag nimmt seine Vermerke mit (Regel 6); die der Anfrage bleiben an ihr
    Seite       Dialog in Anfragen, Akte und Kundenakte; die Liste über textContent; gesendet werden nur Tag und Weg
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.berlin_time import berlin_today
from app.models import AuditLog, Customer, Inquiry, Kontaktvermerk
from app.routers import kontaktvermerke as kv_router
from app.routers import projects as projekte_router
from tests.test_v192_project_templates import make_full_project
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.vorlagen_js import bindet_ein

BOESE = '<img src=x onerror="alert(1)">'


def _welt(db):
    project = make_full_project(db)
    kunde = db.get(Customer, project.customer_id)
    anfrage = Inquiry(inquiry_number="AN-TEST-1", customer_id=kunde.id, title="Dachrinne")
    mit_projekt = Inquiry(inquiry_number="AN-TEST-2", customer_id=kunde.id, title="Sanierung", project_id=project.id)
    db.add_all([anfrage, mit_projekt])
    db.commit()
    return project, kunde, anfrage, mit_projekt


def _c(db, router_test_client, rolle="buero_auftrag"):
    return router_test_client(db, kv_router.router, projekte_router.router, role=rolle, user_id=7, display_name="Anna Büro")


def test_vermerken_je_bezug(threaded_db_session, router_test_client):
    db = threaded_db_session
    project, kunde, anfrage, _ = _welt(db)
    c = _c(db, router_test_client)
    heute = berlin_today()
    for adresse in (f"/api/inquiries/{anfrage.id}/kontakte", f"/api/projects/{project.id}/kontakte", f"/api/customers/{kunde.id}/kontakte"):
        assert c.get(adresse).json() == []
        r = c.post(adresse, json={"kontakt_am": (heute - timedelta(days=10)).isoformat(), "weg": "brief"})
        assert r.status_code == 200, r.text
        r = c.post(adresse, json={"kontakt_am": heute.isoformat(), "weg": "telefon"})
        liste = r.json()
        assert [(v["kontakt_am"], v["weg"], v["weg_text"], v["von"]) for v in liste] == [
            (heute.isoformat(), "telefon", "Telefon", "Anna Büro"), ((heute - timedelta(days=10)).isoformat(), "brief", "Brief", "Anna Büro")]
        assert c.get(adresse).json() == liste
    zeilen = db.scalars(select(Kontaktvermerk).order_by(Kontaktvermerk.id)).all()
    assert [(z.inquiry_id, z.project_id, z.customer_id, z.created_by_user_id) for z in zeilen] == [
        (anfrage.id, None, None, 7)] * 2 + [(None, project.id, None, 7)] * 2 + [(None, None, kunde.id, 7)] * 2


@pytest.mark.parametrize("koerper, grund", [
    ({"kontakt_am": "TAG+1", "weg": "telefon"}, "Zukunft"),
    ({"kontakt_am": "1999-12-31", "weg": "telefon"}, "2000"),
    ({"kontakt_am": "HEUTE", "weg": "fax"}, None),
    ({"kontakt_am": "HEUTE"}, None),
    ({"weg": "telefon"}, None),
    ({"kontakt_am": "HEUTE", "weg": "telefon", "notiz": "Kunde will Angebot"}, None),  # kein Inhalt, auch nicht versehentlich
])
def test_tag_und_weg_geprueft(koerper, grund, threaded_db_session, router_test_client):
    db = threaded_db_session
    project, *_ = _welt(db)
    werte = {"TAG+1": (berlin_today() + timedelta(days=1)).isoformat(), "HEUTE": berlin_today().isoformat()}
    koerper = {k: werte.get(v, v) for k, v in koerper.items()}
    r = _c(db, router_test_client).post(f"/api/projects/{project.id}/kontakte", json=koerper)
    assert r.status_code == 422, r.text
    if grund:
        assert grund in r.text
    assert db.scalar(select(Kontaktvermerk.id)) is None


def test_heute_und_der_erste_januar_2000_gehen(threaded_db_session, router_test_client):
    db = threaded_db_session
    project, *_ = _welt(db)
    c = _c(db, router_test_client)
    for tag in (berlin_today().isoformat(), "2000-01-01"):
        assert c.post(f"/api/projects/{project.id}/kontakte", json={"kontakt_am": tag, "weg": "sonstiges"}).status_code == 200


@pytest.mark.parametrize("pfad", ["/api/inquiries/{}/kontakte", "/api/projects/{}/kontakte", "/api/customers/{}/kontakte"])
@pytest.mark.parametrize("kennung", [999999, 2_147_483_648])
def test_unbekannter_bezug_404(pfad, kennung, threaded_db_session, router_test_client):
    db = threaded_db_session
    _welt(db)
    c = _c(db, router_test_client)
    assert c.get(pfad.format(kennung)).status_code == 404
    assert c.post(pfad.format(kennung), json={"kontakt_am": berlin_today().isoformat(), "weg": "telefon"}).status_code == 404
    assert db.scalar(select(Kontaktvermerk.id)) is None


def test_monteurin_nirgends(threaded_db_session, router_test_client):
    db = threaded_db_session
    project, kunde, anfrage, _ = _welt(db)
    c = _c(db, router_test_client, rolle="field")
    for adresse in (f"/api/inquiries/{anfrage.id}/kontakte", f"/api/projects/{project.id}/kontakte", f"/api/customers/{kunde.id}/kontakte"):
        assert c.get(adresse).status_code == 403
        assert c.post(adresse, json={"kontakt_am": berlin_today().isoformat(), "weg": "telefon"}).status_code == 403
    assert db.scalar(select(Kontaktvermerk.id)) is None


def test_genau_ein_bezug_in_der_datenbank(threaded_db_session):
    db = threaded_db_session
    project, kunde, anfrage, _ = _welt(db)
    for bezug in ({}, {"project_id": project.id, "customer_id": kunde.id}, {"inquiry_id": anfrage.id, "project_id": project.id}):
        db.add(Kontaktvermerk(**bezug, kontakt_am=date(2026, 1, 1), weg="telefon"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_keine_spalte_fuer_einen_inhalt():
    spalten = {c.key for c in inspect(Kontaktvermerk).columns}
    assert spalten == {"id", "inquiry_id", "project_id", "customer_id", "kontakt_am", "weg", "created_at", "created_by_user_id"}


def test_historie_mit_weg_und_tag(threaded_db_session, router_test_client):
    db = threaded_db_session
    project, kunde, anfrage, mit_projekt = _welt(db)
    c = _c(db, router_test_client)
    for adresse, pid in ((f"/api/projects/{project.id}/kontakte", project.id), (f"/api/inquiries/{mit_projekt.id}/kontakte", project.id),
                         (f"/api/inquiries/{anfrage.id}/kontakte", None), (f"/api/customers/{kunde.id}/kontakte", None)):
        before = db.scalar(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)) or 0
        c.post(adresse, json={"kontakt_am": "2026-03-04", "weg": "gespraech"})
        neu = db.scalars(select(AuditLog).where(AuditLog.id > before, AuditLog.entity_type == "Kontakt")).all()
        assert neu and all(z.entity_label == "Gespräch am 04.03.2026" and z.project_id == pid for z in neu), [(z.entity_label, z.project_id) for z in neu]


def test_verlauf_des_kunden_nennt_seinen_kontakt(threaded_db_session, router_test_client):
    from app.routers import customers as kunden_router
    db = threaded_db_session
    project, kunde, anfrage, _ = _welt(db)
    c = router_test_client(db, kv_router.router, kunden_router.router, role="buero_auftrag", user_id=7, display_name="Anna Büro")
    c.post(f"/api/customers/{kunde.id}/kontakte", json={"kontakt_am": "2026-03-04", "weg": "brief"})
    verlauf = c.get(f"/api/customers/{kunde.id}/verlauf").json()
    assert "Brief am 04.03.2026" in str(verlauf), str(verlauf)[:400]


def test_projekt_loeschen_nimmt_seine_vermerke_mit(threaded_db_session, router_test_client):
    db = threaded_db_session
    project, kunde, anfrage, mit_projekt = _welt(db)
    c = _c(db, router_test_client, rolle="admin")
    for adresse in (f"/api/projects/{project.id}/kontakte", f"/api/inquiries/{mit_projekt.id}/kontakte"):
        c.post(adresse, json={"kontakt_am": "2026-03-04", "weg": "email"})
    assert c.delete(f"/api/projects/{project.id}").status_code == 200
    db.expire_all()
    assert [(z.inquiry_id, z.project_id) for z in db.scalars(select(Kontaktvermerk))] == [(mit_projekt.id, None)]


# --- Seiten ------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage, aktion", [("akte.html", "kontakt-projekt"), ("customer.html", "kontakt-kunde"), ("inquiries.html", "kontakt-anfrage")])
def test_dialog_in_den_drei_seiten(vorlage, aktion):
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / vorlage).read_text(encoding="utf-8")
    assert bindet_ein(vorlage, "_kontaktvermerk.html") and bindet_ein(vorlage, "_aktionen.html")
    assert f'data-klick="{aktion}"' in text and f"aktion('{aktion}'" in text and "kontaktDialogOeffnen(" in text


LISTE = [{"id": 2, "kontakt_am": "2026-11-12", "weg": "telefon", "weg_text": BOESE, "created_at": "2026-11-12T09:30:00", "von": BOESE},
         {"id": 1, "kontakt_am": "2026-10-01", "weg": "brief", "weg_text": "Brief", "created_at": "2026-10-01T08:00:00", "von": None}]


@nur_mit_node
def test_dialog_liste_ueber_textcontent():
    ablauf = ("await kontaktDialogOeffnen('projekt', 5, 'P-1 · Dach');"
              "const k = _element('kontaktListe').kinder;"
              "return [k.length, k[0].kinder.map(x => x.textContent), k[1].kinder.map(x => x.textContent), _element('kontaktBezug').textContent,"
              " _element('kontaktTag').value === berlinToday(), _element('kontaktTag').max === berlinToday()];")
    erg = im_browser(seite("akte.html", "\nakteStarten()"), ablauf, {"/api/projects/5/kontakte": LISTE})["ergebnis"]
    assert erg[0] == 2
    assert erg[1] == ["12.11.2026 · " + BOESE, " · vermerkt am 12.11.2026 10:30 von " + BOESE]  # Text, kein HTML
    assert erg[2] == ["01.10.2026 · Brief", " · vermerkt am 01.10.2026 10:00"]
    assert erg[3:] == ["P-1 · Dach", True, True]


@nur_mit_node
def test_dialog_sendet_nur_tag_und_weg():
    ablauf = ("const _alt = globalThis.fetch; globalThis.fetch = async (u, o = {}) => {"  # die Antwort auf POST ist die Liste des Bezugs
              " const r = await _alt(u, o); return (o.method || 'GET') === 'POST' ? {...r, json: async () => []} : r; };"
              "await kontaktDialogOeffnen('kunde', 3, 'K-1');"
              "await _dkAktionen.click['kontakt-vermerken']();"  # ohne Weg: nichts gesendet
              "const ohne = _element('kontaktStatus').textContent;"
              "_element('kontaktWeg').innerHTML = _element('kontaktWeg').innerHTML || '<option value=\"\">-</option><option value=\"email\">E-Mail</option>';"
              "_element('kontaktWeg').value = 'email'; _element('kontaktTag').value = '2026-11-01';"
              "await _dkAktionen.click['kontakt-vermerken']();"
              "const gesendet = _element('kontaktStatus').textContent;"
              "_element('kontaktTag').value = '2999-01-01'; await _dkAktionen.click['kontakt-vermerken']();"  # Zukunft: nichts gesendet
              "const zukunft = _element('kontaktStatus').textContent;"
              "_element('kontaktTag').value = '1999-12-31'; await _dkAktionen.click['kontakt-vermerken']();"
              "return [ohne, gesendet, zukunft, _element('kontaktStatus').textContent];")
    lauf = im_browser(seite("customer.html", "\nkundenakteStarten()"), ablauf, {"/api/customers/3/kontakte": []})
    assert lauf["ergebnis"] == ["Bitte den Weg wählen.", "Vermerkt.", "Der Kontakt darf nicht in der Zukunft liegen.",
                                "Der Kontakt darf nicht vor dem 01.01.2000 liegen."]
    posts = [a for a in lauf["aufrufe"] if a["methode"] == "POST"]
    assert posts == [{"url": "/api/customers/3/kontakte", "methode": "POST", "body": {"kontakt_am": "2026-11-01", "weg": "email"}}]
