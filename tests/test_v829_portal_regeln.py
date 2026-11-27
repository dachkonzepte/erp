"""Version 1.11.37 (Stufe P2c, Teil 2): die automatischen Regeln (Bauplan P2, B4.3; Entscheidungen P2-3 bis P2-5) -- app/portal_freigaben.py.

    Rechnung        festgeschrieben, Kunde der Rechnung, mindestens einmal beim Kunden angekommen (Versand oder Zustellung)
    Mahnung         festgeschrieben, hinausgegangen, nicht ersetzt
    Angebot, AB,    je Dokument die zuletzt versendete Fassung -- an die Adresse des Kunden (bzw. nachgetragen an den Auftraggeber) automatisch, sonst nur
    Vertrag         Vorschlag; eine ältere automatische nimmt das System als überholt zurück
    Abnahmeprot.    die jüngste gültige Fassung mit der Unterschrift des Auftraggebers (protocol_version()); eine ältere überholt
    Einsatzbericht  unterschrieben mit fester Fassung (Rapport wie Wartung, P2-5)
    Brief           beim Auftraggeber angekommen
    Dazu            von einer Person zurückgenommen: nie wieder; vom System überholt: wieder, wenn sie wieder die jüngste ist; kein stilles Umhängen; zweimal
                    angewandt ändert nichts; Portal an wendet sie gleich an (auch für Älteres); der Postbote im vollen Lauf für jeden Kunden mit Portal an,
                    ein Fehler darin hält ihn nicht an.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import portal_freigaben as pf
from app import portal_postbote as postbote
from app.models import (
    ChecklistAttachment, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Checklist, ChecklistVersion, EmailDispatch, EnabledModule,
    Invoice, NoticeLetter, Order, OrderContract, PortalFreigabe, Quote, Reminder, SentDocument, ServiceReport,
)
from app.routers import kundenportal, portal_freigaben
from tests.quellangebot import quell_angebot
from tests.test_v828_portal_freigaben import Welt
from tests.portal_webseite import webseite_setzen

EMAIL = "kunde@example.invalid"


class Regeln(Welt):
    def __init__(self, db, client):
        super().__init__(db, client)
        self.a.email = EMAIL
        self.db.commit()
        self.p = self.projekt(self.a)
        nr = f"A-{self.p.id}"
        self.o = Order(order_number=nr, project_id=self.p.id, source_quote_id=quell_angebot(self.db, self.p.id, nr), quote_number_snapshot=f"Q-{nr}",
                       title="Dach", customer_name="x", customer_id=self.a.id)
        self.db.add(self.o)
        self.db.commit()

    def ablage(self, art, dok_id):
        s = SentDocument(document_type=art, document_id=dok_id, filename="x.pdf", stored_filename=f"2026/11/{uuid.uuid4().hex}.pdf", size_bytes=10,
                         sha256="0" * 64, created_by_name="Test")
        self.db.add(s)
        self.db.flush()
        return s

    def versand(self, art, dok_id, *, an=EMAIL, ablage=None, kanal="smtp", an_den_auftraggeber=None, status="gesendet", am=None):
        d = EmailDispatch(dispatch_key=uuid.uuid4().hex, message_ref=uuid.uuid4().hex, status=status, channel=kanal, document_type=art, document_id=dok_id,
                          to_recipients=an, subject="Test", created_by_name="Büro", sent_document_id=ablage.id if ablage is not None else None,
                          delivered_to_client=an_den_auftraggeber, created_at=am or datetime.utcnow(), finished_at=am or datetime.utcnow())
        self.db.add(d)
        self.db.commit()
        return d

    def rechnung(self, *, status="versendet"):
        i = Invoice(order_id=self.o.id, invoice_type="abschlag", customer_name="x", status=status, customer_id=self.a.id if status != "entwurf" else None,
                    invoice_number=None if status == "entwurf" else f"R-{uuid.uuid4().hex[:8]}")
        self.db.add(i)
        self.db.commit()
        return i

    def anwenden(self, kunde=None):
        return pf.regeln_anwenden(self.db, kunde or self.a)

    def aktiv(self, kunde=None):
        self.db.expire_all()
        return {(f.quelle, f.quelle_id, f.regel) for f in self.db.scalars(select(PortalFreigabe).where(
            PortalFreigabe.customer_id == (kunde or self.a).id, PortalFreigabe.zurueckgenommen_am.is_(None)))}

    def checkliste(self, zweck="allgemein"):
        vorlage = ChecklistTemplate(label="Protokoll")
        self.db.add(vorlage)
        self.db.flush()
        fassung = ChecklistTemplateVersion(template_id=vorlage.id, version_no=1, purpose=zweck)
        self.db.add(fassung)
        self.db.flush()
        feld = ChecklistTemplateField(version_id=fassung.id, field_key=f"u{uuid.uuid4().hex[:6]}", field_type="unterschrift", label="Unterschrift")
        self.db.add(feld)
        self.db.flush()
        c = Checklist(template_id=vorlage.id, template_version_id=fassung.id, template_label_snapshot="Protokoll", context_type="auftrag", order_id=self.o.id)
        self.db.add(c)
        self.db.flush()
        u = ChecklistAttachment(checklist_id=c.id, template_field_id=feld.id, kind="unterschrift", stored_filename=uuid.uuid4().hex)
        self.db.add(u)
        self.db.commit()
        return c, u


@pytest.fixture
def r(threaded_db_session, router_test_client):
    db = threaded_db_session
    webseite_setzen(db)  # seit 1.11.47: ohne Webseite kein Portal (Impressum und Datenschutz sind Pflicht)
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    db.commit()
    return Regeln(db, router_test_client(db, portal_freigaben.router, kundenportal.router, role="buero_auftrag", user_id=11, display_name="Auri Auftrag"))


def test_rechnung_nur_wenn_angekommen(r):
    angekommen, nie, entwurf = r.rechnung(), r.rechnung(), r.rechnung(status="entwurf")
    r.versand("rechnung", angekommen.id)
    r.versand("rechnung", nie.id, status="fehlgeschlagen")
    r.versand("rechnung", entwurf.id)
    assert r.anwenden().neu == 1 and r.aktiv() == {("invoices", angekommen.id, "rechnung")}
    f = r.db.scalar(select(PortalFreigabe))
    assert (f.freigegeben_von_name, f.freigegeben_von_user_id, f.art) == ("automatisch", None, "rechnung")


def test_nichts_dessen_kette_nicht_gilt(r):
    """Angekommen, aber das Projekt ist heute im Archiv (bzw. ein Mustervorgang): die Kette gilt nicht, die Regel gibt nichts frei."""
    i = r.rechnung()
    r.versand("rechnung", i.id)
    r.p.archived = True
    r.db.commit()
    assert r.anwenden().neu == 0 and r.aktiv() == set()
    r.p.archived, r.p.is_template = False, True
    r.db.commit()
    assert r.anwenden().neu == 0
    r.p.is_template = False
    r.db.commit()
    assert r.anwenden().neu == 1


def test_mahnung_hinausgegangen_und_nicht_ersetzt(r):
    i = r.rechnung()
    alt, neu = Reminder(invoice_id=i.id, level=1, status="versendet"), Reminder(invoice_id=i.id, level=1, status="versendet")
    entwurf = Reminder(invoice_id=i.id, level=2, status="entwurf")
    r.db.add_all([alt, neu, entwurf])
    r.db.flush()
    alt.replaced_by_id = neu.id
    r.db.commit()
    for m in (alt, neu, entwurf):
        r.versand("mahnung", m.id)
    r.anwenden()
    assert {(q, i_) for q, i_, _r in r.aktiv()} == {("reminders", neu.id)}  # die Rechnung selbst ging nie hinaus


def test_angebot_juengste_fassung_an_den_kunden_sonst_vorschlag(r):
    q = r.db.scalar(select(Quote).where(Quote.project_id == r.p.id))
    s1 = r.ablage("angebot", q.id)
    r.versand("angebot", q.id, ablage=s1, an=f"Kunde <{EMAIL.upper()}>, buero@example.invalid", am=datetime(2026, 11, 20, 9))
    assert r.anwenden().neu == 1 and r.aktiv() == {("sent_documents", s1.id, "angebot")}
    s2 = r.ablage("angebot", q.id)
    r.versand("angebot", q.id, ablage=s2, an="architekt@example.invalid", am=datetime(2026, 11, 21, 9))
    stand = r.anwenden()
    assert (stand.neu, stand.ueberholt) == (0, 1) and r.aktiv() == set()
    alt = r.db.scalar(select(PortalFreigabe).where(PortalFreigabe.quelle_id == s1.id))
    assert (alt.zurueckgenommen_von_name, alt.zurueckgenommen_grund, alt.zurueckgenommen_von_user_id) == ("System", pf.UEBERHOLT, None)
    vorschlaege = r.client.get(r.url(r.a)).json()["vorschlaege"]
    assert [(v["quelle_id"], v["art"], v["an"]) for v in vorschlaege] == [(s2.id, "angebot", "architekt@example.invalid")]
    assert r.freigeben(r.a, "sent_documents", [s2.id]).status_code == 200  # ein Vorschlag geht nur von Hand
    assert r.client.get(r.url(r.a)).json()["vorschlaege"] == [] and r.anwenden().neu == 0


def test_auftragsbestaetigung_und_vertrag_nachgetragen_an_den_auftraggeber(r):
    s = r.ablage("auftrag", r.o.id)
    r.versand("auftrag", r.o.id, ablage=s, kanal="einschreiben", an="", an_den_auftraggeber=True)
    vertrag = OrderContract(order_id=r.o.id)
    r.db.add(vertrag)
    r.db.flush()
    v = r.ablage("vertrag", vertrag.id)
    r.versand("vertrag", vertrag.id, ablage=v, kanal="bote", an="", an_den_auftraggeber=False)  # an einen Beteiligten: nur Vorschlag
    r.anwenden()
    assert r.aktiv() == {("sent_documents", s.id, "auftrag")}
    assert [(x["quelle_id"], x["an"]) for x in pf.vorschlaege(r.db, r.a)] == [(v.id, None)]


def test_einsatzbericht_nur_mit_fester_fassung(r):
    fest = ServiceReport(order_id=r.o.id, report_type="rapport", status="unterschrieben")
    ohne = ServiceReport(order_id=r.o.id, report_type="wartung", status="unterschrieben")
    entwurf = ServiceReport(order_id=r.o.id, report_type="wartung")
    r.db.add_all([fest, ohne, entwurf])
    r.db.flush()
    fest.pdf_document_id = r.ablage("einsatzbericht", fest.id).id
    entwurf.pdf_document_id = r.ablage("einsatzbericht", entwurf.id).id
    r.db.commit()
    r.anwenden()
    assert r.aktiv() == {("service_reports", fest.id, "einsatzbericht")}


def test_brief_nur_beim_auftraggeber_angekommen(r):
    c, u = r.checkliste()
    u2 = ChecklistAttachment(checklist_id=c.id, template_field_id=u.template_field_id, kind="unterschrift", stored_filename=uuid.uuid4().hex)
    r.db.add(u2)
    r.db.commit()
    briefe = []
    for unterschrift in (u, u2):  # je Unterschrift ein Brief
        s = r.ablage("behinderungsanzeige", c.id)
        n = NoticeLetter(checklist_id=c.id, kind="behinderungsanzeige", version_no=len(briefe) + 1, signature_id=unterschrift.id, signature_sha256="0" * 64,
                         content="{}", content_sha256="0" * 64, sent_document_id=s.id)
        r.db.add(n)
        r.db.commit()
        briefe.append((n, s))
    r.versand("behinderungsanzeige", c.id, ablage=briefe[0][1])
    r.versand("behinderungsanzeige", c.id, ablage=briefe[1][1], kanal="fax", an="", an_den_auftraggeber=False)
    r.anwenden()
    assert r.aktiv() == {("notice_letters", briefe[0][0].id, "brief")}


def _fassung(r, c, u, nr):
    v = ChecklistVersion(checklist_id=c.id, version_no=nr, kind="unterschrift", signature_ids=f"[{u.id}]", sent_document_id=r.ablage("checkliste", c.id).id)
    r.db.add(v)
    r.db.commit()
    return v


def test_abnahmeprotokoll_juengste_gueltige_und_ueberholt_kommt_wieder(r, monkeypatch):
    """protocol_version() selbst prüfen die Tests des Versands (test_v367); hier, was die Regel daraus macht."""
    import app.protocol_dispatch as versand

    c, u = r.checkliste("abnahme")
    v1, v2 = _fassung(r, c, u, 1), _fassung(r, c, u, 2)
    jetzt = {"fassung": v1}
    monkeypatch.setattr(versand, "protocol_version", lambda db, checkliste: jetzt["fassung"] if checkliste.id == c.id else None)
    r.anwenden()
    assert r.aktiv() == {("checklist_versions", v1.id, "abnahmeprotokoll")}
    jetzt["fassung"] = v2
    stand = r.anwenden()
    assert (stand.neu, stand.ueberholt) == (1, 1) and r.aktiv() == {("checklist_versions", v2.id, "abnahmeprotokoll")}
    jetzt["fassung"] = v1  # die neuere gilt nicht mehr: die ältere ist wieder die jüngste gültige -- vom System überholt, sie kommt wieder
    r.anwenden()
    assert ("checklist_versions", v1.id, "abnahmeprotokoll") in r.aktiv()
    assert r.db.scalar(select(PortalFreigabe).where(PortalFreigabe.quelle_id == v1.id, PortalFreigabe.zurueckgenommen_am.is_not(None))) is not None


def test_von_einer_person_zurueckgenommen_nie_wieder(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)
    r.anwenden()
    fid = r.db.scalar(select(PortalFreigabe.id))
    assert r.client.post(r.url(r.a, f"/{fid}/zuruecknehmen"), json={"grund": "nicht fürs Portal"}).status_code == 200
    assert r.anwenden().neu == 0 and r.aktiv() == set()
    assert r.freigeben(r.a, "invoices", [i.id]).status_code == 200  # von Hand geht es weiter


def test_kein_stilles_umhaengen(r):
    """Die Kette führt heute zu B: die Regel von B legt nichts an, solange die Zeile bei A steht (dort ruht sie)."""
    b = ServiceReport(order_id=r.o.id, report_type="wartung", status="unterschrieben")
    r.db.add(b)
    r.db.flush()
    b.pdf_document_id = r.ablage("einsatzbericht", b.id).id
    r.db.commit()
    r.anwenden()
    r.o.customer_id = r.b.id
    r.p.customer_id = r.b.id
    r.db.commit()
    assert r.anwenden(r.b).neu == 0 and r.aktiv(r.b) == set()
    assert r.client.get(r.url(r.a)).json()["eintraege"][0]["zustand"] == "ruht"


def test_zweimal_angewandt_aendert_nichts(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)
    assert r.anwenden().neu == 1
    stand = r.anwenden()
    assert (stand.neu, stand.ueberholt) == (0, 0) and len(r.zeilen()) == 1


def test_portal_an_wendet_die_regeln_gleich_an(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)  # vor der Einladung versendet (P2-3)
    assert r.zeilen() == []
    assert r.client.post(f"/api/customers/{r.a.id}/portal/schalter", json={"an": True}).status_code == 200
    assert r.aktiv() == {("invoices", i.id, "rechnung")}
    assert r.client.post(f"/api/customers/{r.a.id}/portal/schalter", json={"an": False}).status_code == 200
    assert r.aktiv() == {("invoices", i.id, "rechnung")}  # aus nimmt nichts zurück -- das Portal zeigt ohnehin nichts


def test_regeln_alle_nur_portal_an_nicht_archiv_und_mit_modul(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)
    assert pf.regeln_alle(r.db).neu == 0  # Portal aus
    r.a.portal_aktiv = True
    r.a.archiviert_am = datetime(2026, 11, 26)
    r.db.commit()
    assert pf.regeln_alle(r.db).neu == 0  # im Archiv
    r.a.archiviert_am = None
    r.db.query(EnabledModule).update({"enabled": False})
    r.db.commit()
    assert pf.regeln_alle(r.db).neu == 0  # Modul aus
    r.db.query(EnabledModule).update({"enabled": True})
    r.db.commit()
    assert pf.regeln_alle(r.db).neu == 1


def test_jede_regel_hat_einen_namen_der_passt():
    assert set(pf.REGELN) <= set(pf.ART_TEXT) and max(len(x) for x in pf.REGELN) <= PortalFreigabe.__table__.c.regel.type.length


def test_ein_fehler_in_den_regeln_haelt_den_postboten_nicht_an(r, monkeypatch, caplog):
    def kaputt(_db):
        raise RuntimeError("geheimer Inhalt")

    monkeypatch.setattr(pf, "regeln_alle", kaputt)
    with caplog.at_level(logging.ERROR, logger="app.portal_postbote"):
        postbote.regeln(r.db)
    assert "Regeln nicht angewandt (RuntimeError)" in caplog.text and "geheimer Inhalt" not in caplog.text


# --- PostgreSQL: der Postbote im vollen Lauf ------------------------------------------------------------------------------------------------------------

from tests.test_v823_portal_kopien import _bis, _kunde, _laeuft, echte_quelle, w, welt  # noqa: E402,F401 -- w und welt: Fixtures der Kopien


def test_pg_postbote_wendet_die_regeln_im_vollen_lauf_an(w):
    kunde, _sitz = _kunde(w, "Regel")
    q, _ = echte_quelle(w, "invoices", kunde)
    w.erp("UPDATE customers SET portal_aktiv = true WHERE id = :k", k=kunde)
    w.erp("INSERT INTO email_dispatches (dispatch_key, message_ref, status, channel, document_type, document_id, to_recipients, subject, created_at, "
          "created_by_name) VALUES (:s, :m, 'gesendet', 'smtp', 'rechnung', :i, 'x@example.invalid', 'Rechnung', now(), 'Büro')",
          s=uuid.uuid4().hex, m=uuid.uuid4().hex, i=q.id)
    halt, faden, fehler = _laeuft(w, w.ordner)
    try:
        _bis(lambda: w.erp("SELECT count(*) FROM portal_freigaben WHERE quelle_id = :i AND regel = 'rechnung' AND kopie_bereit_am IS NOT NULL",
                           i=q.id)[0][0] == 1, "Regel angewandt und Kopie angelegt")
    finally:
        halt.set()
        w.erp("SELECT pg_notify('portal_post', '')")
        faden.join(30)
    assert fehler == [] and not faden.is_alive()
    with Session(w.engine) as db:
        assert db.execute(text("SELECT freigegeben_von_name FROM portal_freigaben WHERE quelle_id = :i"), {"i": q.id}).scalar() == "automatisch"
