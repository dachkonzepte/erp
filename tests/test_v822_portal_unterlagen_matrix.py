"""Matrix der Unterlagen im Kundenportal: jede Quelle × jeder Fall gegen PostgreSQL mit der Testrolle (seit 1.11.32, Vorgabe des Betriebs vom 26.11.2026).

Zeilen: die zwölf Quellen aus app/portal/werte.py::FREIGABE_QUELLEN, die Ablage nach Art (Angebot, Auftragsbestätigung, Vertrag) und die Fassung einer Checkliste
nach Kontext (Auftrag, Objekt) aufgeteilt -- 15 Zeilen. Spalten (FAELLE): positiv; fremder Kunde (die Freigabe nennt einen anderen Kunden als die Kette);
Objekt eines anderen Kunden; Kundenwechsel (die Kette führt danach zu einem anderen Kunden -- ruht); Mustervorgang; Projekt im Archiv; Kunde im Archiv;
zurückgenommen; Quelle ungültig (je Quelle UNGUELTIG); Kopie nicht bereit. Jede Zelle ist ein eigener Test (test_matrix[zeile-fall]) oder steht in ENTFAELLT
mit Grund; ein Wächter verlangt, dass jede Zelle genau eins von beiden ist. Jeder Fall prüft zuerst, dass die Unterlage vor der Änderung sichtbar war.

Gegenproben je Zweig von portal_quelle(): die Kette durch den Kunden der Freigabe selbst ersetzt -> die Zelle „fremder Kunde“ wird rot (Tabelle in
docs/archiv/gegenproben-portal.md, „1.11.32“).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    ChecklistAttachment, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Checklist, ChecklistVersion, CustomerDocument, Defect, DefectFile,
    DocumentCategory, Invoice, NoticeLetter, Order, OrderAcceptance, OrderAcceptanceFile, OrderContract, Project, ProjectDocument, Property,
    PropertyDocument, Reminder, SentDocument, ServiceReport, ServiceReportPhoto, WebAnfrage,
)
from app.portal import pruefwerte, rechte, werte
from app.project_pipeline_columns import default_pipeline_column_id
from tests.quellangebot import quell_angebot
from tests.test_v800_portal_funktionen import PG_URL, TESTROLLE, Welt

FAELLE = ("positiv", "fremder_kunde", "objekt_anderer_kunde", "kundenwechsel", "mustervorgang", "projekt_archiv", "kunde_archiv", "zurueckgenommen",
          "quelle_ungueltig", "kopie_nicht_bereit")
ZEILEN = ("invoices", "reminders", "sent_documents:angebot", "sent_documents:auftrag", "sent_documents:vertrag", "service_reports",
          "checklist_versions:auftrag", "checklist_versions:objekt", "notice_letters", "service_report_photos", "customer_documents", "project_documents",
          "property_documents", "defect_files", "order_acceptance_files")
OHNE_PROJEKT = "keine Kette über ein Projekt"
ENTFAELLT = {
    ("customer_documents", "objekt_anderer_kunde"): "kein Objekt -- das Dokument hängt am Kunden",
    ("customer_documents", "mustervorgang"): OHNE_PROJEKT,
    ("customer_documents", "projekt_archiv"): OHNE_PROJEKT,
    ("property_documents", "mustervorgang"): OHNE_PROJEKT + " (am Objekt)",
    ("property_documents", "projekt_archiv"): OHNE_PROJEKT + " (am Objekt)",
    ("checklist_versions:objekt", "mustervorgang"): OHNE_PROJEKT + " (Checkliste am Objekt)",
    ("checklist_versions:objekt", "projekt_archiv"): OHNE_PROJEKT + " (Checkliste am Objekt)",
}
# Was „Quelle ungültig“ je Zeile heißt
UNGUELTIG = {
    "invoices": "Rechnung im Entwurf", "reminders": "Mahnung ersetzt", "sent_documents:angebot": "Zeile der Ablage gelöscht",
    "sent_documents:auftrag": "Zeile der Ablage gelöscht", "sent_documents:vertrag": "Zeile der Ablage gelöscht",
    "service_reports": "ohne feste Fassung", "checklist_versions:auftrag": "überholt (Unterschrift verworfen)",
    "checklist_versions:objekt": "überholt (Unterschrift verworfen)", "notice_letters": "überholt (Unterschrift verworfen)",
    "service_report_photos": "gelöscht", "customer_documents": "gelöscht", "project_documents": "gelöscht", "property_documents": "Anfrage im Archiv",
    "defect_files": "Mangel verworfen", "order_acceptance_files": "Abnahme verworfen",
}
# Objekt eines anderen Kunden: über Projekt/Auftrag bleibt die Unterlage beim Kunden des Projekts sichtbar; am Objekt selbst gehört sie dem anderen
OBJEKT_SICHTBAR = {z: z not in ("property_documents", "checklist_versions:objekt") for z in ZEILEN}

ZELLEN = [(z, f) for z in ZEILEN for f in FAELLE if (z, f) not in ENTFAELLT]


def test_jede_zelle_getestet_oder_entfaellt():
    """Jede Zeile × jeder Fall ist genau eins: Test oder „entfällt (Grund)“; jede Quelle hat ihre Zeile."""
    alle = {(z, f) for z in ZEILEN for f in FAELLE}
    assert set(ZELLEN) | set(ENTFAELLT) == alle and not set(ZELLEN) & set(ENTFAELLT)
    assert {z.split(":")[0] for z in ZEILEN} == set(werte.FREIGABE_QUELLEN)
    assert set(UNGUELTIG) == set(ZEILEN) and all(ENTFAELLT.values())


# --- Welt: ein Schema für das ganze Modul, je Test eigene Kunden ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def welt():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from app.grunddaten import anlegen
    schema = f"pgtest_matrix_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)
            c.execute(text("INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', true, now())"))
        db = sessionmaker(bind=engine)()
        anlegen(db)
        db.commit()
        db.close()
        yield Welt(engine, schema)
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@dataclass
class Quelle:
    quelle: str
    id: int
    kette: tuple[str, str, int]          # (Tabelle, Spalte, ID): wo die Kette den Kunden nimmt -- für den Kundenwechsel
    projekt: int | None
    ungueltig: Callable[[], None] = field(repr=False)


class Bau:
    """Legt eine Quelle mit echten Eltern an (ORM, ein Commit); Zustandswechsel per SQL (die Modelle sperren Ändern und Löschen)."""

    def __init__(self, w):
        self.w = w
        self.db = sessionmaker(bind=w.engine, expire_on_commit=False)()  # IDs bleiben nach dem Commit lesbar
        self.kategorie = self.db.scalar(select(DocumentCategory.id).order_by(DocumentCategory.id).limit(1))

    def sql(self, anweisung, **werte_):
        self.w.erp(anweisung, **werte_)

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def objekt(self, kunde):
        return self.add(Property(customer_id=kunde, name="Halle", street="Hafenweg 3", postal_code="12345", city="Musterstadt"))

    def projekt(self, kunde, objekt):
        return self.add(Project(project_number=f"P-{uuid.uuid4().hex[:8]}", name="Interner Titel", customer_id=kunde, property_id=objekt.id,
                                status="anfrage", pipeline_column_id=default_pipeline_column_id(self.db)))

    def auftrag(self, p):
        nr = f"A-{uuid.uuid4().hex[:8]}"
        return self.add(Order(order_number=nr, project_id=p.id, source_quote_id=quell_angebot(self.db, p.id, nr), quote_number_snapshot=f"Q-{nr}",
                              title="Dach", customer_name="x", customer_id=p.customer_id))

    def ablage(self, art, dok_id):
        return self.add(SentDocument(document_type=art, document_id=dok_id, filename="x.pdf", stored_filename=f"2026/11/{uuid.uuid4().hex}.pdf",
                                     size_bytes=10, sha256="0" * 64, created_by_name="Test"))

    def checkliste(self, *, order_id=None, property_id=None):
        vorlage = self.add(ChecklistTemplate(label="Prüfliste"))
        fassung = self.add(ChecklistTemplateVersion(template_id=vorlage.id, version_no=1))
        feld = self.add(ChecklistTemplateField(version_id=fassung.id, field_key=f"u{uuid.uuid4().hex[:6]}", field_type="unterschrift", label="Unterschrift"))
        c = self.add(Checklist(template_id=vorlage.id, template_version_id=fassung.id, template_label_snapshot="Prüfliste",
                               context_type="auftrag" if order_id else "objekt", order_id=order_id, property_id=property_id))
        u = self.add(ChecklistAttachment(checklist_id=c.id, template_field_id=feld.id, kind="unterschrift", stored_filename=uuid.uuid4().hex))
        return c, u

    def verwerfen(self, tabelle, zeile):
        return lambda: self.sql(f"UPDATE {tabelle} SET discarded_at = now() WHERE id = :i", i=zeile)

    def loeschen(self, tabelle, zeile):
        return lambda: self.sql(f"DELETE FROM {tabelle} WHERE id = :i", i=zeile)

    def bauen(self, zeile, kunde, objekt_kunde) -> Quelle:
        o = self.objekt(objekt_kunde)
        p = self.projekt(kunde, o)
        a = self.auftrag(p)
        art = zeile.split(":")[1] if ":" in zeile else None
        if zeile == "invoices":
            i = self.add(Invoice(order_id=a.id, invoice_type="abschlag", customer_name="x", status="versendet", customer_id=kunde,
                                 invoice_number=f"R-{uuid.uuid4().hex[:8]}"))
            q = Quelle("invoices", i.id, ("invoices", "customer_id", i.id), p.id,
                       lambda: self.sql("UPDATE invoices SET status = 'entwurf', invoice_number = NULL WHERE id = :i", i=i.id))
        elif zeile == "reminders":
            i = self.add(Invoice(order_id=a.id, invoice_type="abschlag", customer_name="x", status="versendet", customer_id=kunde,
                                 invoice_number=f"R-{uuid.uuid4().hex[:8]}"))
            m = self.add(Reminder(invoice_id=i.id, level=1, status="versendet"))

            def ersetzen():
                s = sessionmaker(bind=self.w.engine)()
                try:
                    neu = Reminder(invoice_id=i.id, level=1, status="versendet")
                    s.add(neu)
                    s.commit()
                    neu_id = neu.id
                finally:
                    s.close()
                self.sql("UPDATE reminders SET replaced_by_id = :n WHERE id = :m", n=neu_id, m=m.id)
            q = Quelle("reminders", m.id, ("invoices", "customer_id", i.id), p.id, ersetzen)
        elif zeile.startswith("sent_documents"):
            if art == "angebot":
                s, kette = self.ablage("angebot", quell_angebot(self.db, p.id, f"X{uuid.uuid4().hex[:6]}")), ("projects", "customer_id", p.id)
            elif art == "auftrag":
                s, kette = self.ablage("auftrag", a.id), ("orders", "customer_id", a.id)
            else:
                s, kette = self.ablage("vertrag", self.add(OrderContract(order_id=a.id)).id), ("orders", "customer_id", a.id)
            q = Quelle("sent_documents", s.id, kette, p.id, self.loeschen("sent_documents", s.id))
        elif zeile == "service_reports":
            b = self.add(ServiceReport(order_id=a.id, report_type="wartung", status="unterschrieben"))
            b.pdf_document_id = self.ablage("einsatzbericht", b.id).id
            self.db.flush()
            q = Quelle("service_reports", b.id, ("orders", "customer_id", a.id), p.id,
                       lambda: self.sql("UPDATE service_reports SET pdf_document_id = NULL WHERE id = :i", i=b.id))
        elif zeile.startswith("checklist_versions"):
            if art == "auftrag":
                c, u = self.checkliste(order_id=a.id)
                kette = ("orders", "customer_id", a.id)
            else:
                c, u = self.checkliste(property_id=o.id)
                kette = ("properties", "customer_id", o.id)
            v = self.add(ChecklistVersion(checklist_id=c.id, version_no=1, kind="unterschrift", signature_ids=f"[{u.id}]",
                                          sent_document_id=self.ablage("checkliste", c.id).id))
            q = Quelle("checklist_versions", v.id, kette, p.id if art == "auftrag" else None, self.verwerfen("checklist_attachments", u.id))
        elif zeile == "notice_letters":
            c, u = self.checkliste(order_id=a.id)
            n = self.add(NoticeLetter(checklist_id=c.id, kind="behinderungsanzeige", version_no=1, signature_id=u.id, signature_sha256="0" * 64,
                                      content="{}", content_sha256="0" * 64, sent_document_id=self.ablage("behinderungsanzeige", c.id).id))
            q = Quelle("notice_letters", n.id, ("orders", "customer_id", a.id), p.id, self.verwerfen("checklist_attachments", u.id))
        elif zeile == "service_report_photos":
            b = self.add(ServiceReport(order_id=a.id, report_type="wartung"))
            f = self.add(ServiceReportPhoto(service_report_id=b.id, kind="allgemein", file_path=uuid.uuid4().hex))
            q = Quelle("service_report_photos", f.id, ("orders", "customer_id", a.id), p.id, self.loeschen("service_report_photos", f.id))
        elif zeile == "customer_documents":
            d = self.add(CustomerDocument(customer_id=kunde, category_id=self.kategorie, original_filename="plan.pdf", stored_filename=uuid.uuid4().hex))
            q = Quelle("customer_documents", d.id, ("customer_documents", "customer_id", d.id), None, self.loeschen("customer_documents", d.id))
        elif zeile == "project_documents":
            d = self.add(ProjectDocument(project_id=p.id, category_id=self.kategorie, original_filename="plan.pdf", stored_filename=uuid.uuid4().hex))
            q = Quelle("project_documents", d.id, ("projects", "customer_id", p.id), p.id, self.loeschen("project_documents", d.id))
        elif zeile == "property_documents":
            anfrage = self.add(WebAnfrage(nummer=f"W-{uuid.uuid4().hex[:8]}", fassung="dk-anfrage/1", umschlag="{}", umschlag_sha256="0" * 64))
            d = self.add(PropertyDocument(property_id=o.id, category_id=self.kategorie, original_filename="foto.jpg", stored_filename=uuid.uuid4().hex,
                                          webanfrage_id=anfrage.id))
            q = Quelle("property_documents", d.id, ("properties", "customer_id", o.id), None,
                       lambda: self.sql("UPDATE webanfragen SET archiviert_am = now() WHERE id = :i", i=anfrage.id))
        elif zeile == "defect_files":
            m = self.add(Defect(order_id=a.id, source="abnahme", description="Riss", content_sha256="0" * 64))
            f = self.add(DefectFile(defect_id=m.id, kind="foto", stored_filename=uuid.uuid4().hex, content_type="image/jpeg", size_bytes=10, sha256="0" * 64))
            q = Quelle("defect_files", f.id, ("orders", "customer_id", a.id), p.id, self.verwerfen("defects", m.id))
        elif zeile == "order_acceptance_files":
            ab = self.add(OrderAcceptance(order_id=a.id, kind="foermlich", accepted_on=date(2026, 11, 20), scope="ganz", result="abgenommen",
                                          declared_by="auftraggeber", declared_by_name="Max Muster", content_sha256="0" * 64))
            f = self.add(OrderAcceptanceFile(acceptance_id=ab.id, kind="beleg", stored_filename=uuid.uuid4().hex, content_type="application/pdf",
                                             size_bytes=10, sha256="0" * 64))
            q = Quelle("order_acceptance_files", f.id, ("orders", "customer_id", a.id), p.id, self.verwerfen("order_acceptances", ab.id))
        else:
            raise AssertionError(zeile)
        self.db.commit()
        self.db.close()
        return q


def _kunde(w, name):
    """Kunde mit Zugang und angemeldetem Gerät -- je Aufruf ein eigener Anschluss (die Bremsen aus P1 zählen je Anschluss)."""
    kid, _zugang, link = w.kunde(nachname=name, link=f"{name}-{uuid.uuid4().hex[:8]}")
    anschluss = uuid.uuid4().hex + uuid.uuid4().hex
    (erg, _anzeige, _m), vorlaeufig = w.oeffnen(link, anschluss=anschluss)
    assert erg == "code_noetig"
    assert w.anfordern(vorlaeufig, anschluss=anschluss) == ("angefordert", None)
    w.code_anlegen(vorlaeufig)
    (erg, _z), wert = w.pruefen(vorlaeufig, "123456", anschluss=anschluss)
    assert erg == "angemeldet"
    return kid, wert


def _freigabe(w, kunde, q: Quelle, *, bereit=True):
    return w.erp("INSERT INTO portal_freigaben (customer_id, art, quelle, quelle_id, titel, datum, freigegeben_am, freigegeben_von_name, kopie_name, "
                 "kopie_typ, kopie_groesse, kopie_bereit_am) VALUES (:k, 'dokument', :q, :i, 'Unterlage', DATE '2026-11-20', now(), 'Büro', :n, :t, :g, :b) "
                 "RETURNING id", k=kunde, q=q.quelle, i=q.id, n=(uuid.uuid4().hex + ".pdf") if bereit else None,
                 t="application/pdf" if bereit else None, g=1234 if bereit else None, b=datetime.utcnow() if bereit else None)[0][0]


def _liste(w, sitz):
    return [tuple(r) for r in w.als_portal("SELECT * FROM portal_unterlagen(:s)", s=pruefwerte.sitzung(sitz))]


def _ids(w, sitz):
    zeilen = _liste(w, sitz)
    if zeilen[0][0] in ("leer", "ungueltig"):
        return []
    return [z[2] for z in zeilen]


@pytest.mark.parametrize("zeile, fall", ZELLEN, ids=[f"{z}-{f}" for z, f in ZELLEN])
def test_matrix(welt, zeile, fall):
    w = welt
    w.erp("DELETE FROM portal_bremsen")  # die Bremse „Code gesamt 200 je Stunde“ gilt für das ganze Schema -- je Test neu
    kunde, sitz = _kunde(w, "Kundin")
    anderer, sitz2 = _kunde(w, "Fremd")
    bau = Bau(w)
    q = bau.bauen(zeile, kunde, anderer if fall == "objekt_anderer_kunde" else kunde)

    if fall == "positiv":
        f = _freigabe(w, kunde, q)
        assert f in _ids(w, sitz) and f not in _ids(w, sitz2)
    elif fall == "fremder_kunde":
        f = _freigabe(w, anderer, q)
        assert f not in _ids(w, sitz2), "fremde Freigabe sichtbar"
        assert f not in _ids(w, sitz)
    elif fall == "objekt_anderer_kunde":
        f = _freigabe(w, kunde, q)
        assert (f in _ids(w, sitz)) is OBJEKT_SICHTBAR[zeile]
        assert f not in _ids(w, sitz2)
    elif fall == "kopie_nicht_bereit":
        f = _freigabe(w, kunde, q, bereit=False)
        assert f not in _ids(w, sitz)
    else:
        f = _freigabe(w, kunde, q)
        assert f in _ids(w, sitz), "vor der Änderung nicht sichtbar"
        if fall == "kundenwechsel":
            tabelle, spalte, zid = q.kette
            w.erp(f"UPDATE {tabelle} SET {spalte} = :k WHERE id = :i", k=anderer, i=zid)
            assert f not in _ids(w, sitz2), "nach dem Kundenwechsel beim neuen Kunden sichtbar"
        elif fall in ("mustervorgang", "projekt_archiv"):
            w.erp(f"UPDATE projects SET {'is_template' if fall == 'mustervorgang' else 'archived'} = true WHERE id = :p", p=q.projekt)
        elif fall == "kunde_archiv":
            w.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kunde)
            assert _liste(w, sitz)[0][0] == "ungueltig"
        elif fall == "zurueckgenommen":
            w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now() WHERE id = :f", f=f)
        elif fall == "quelle_ungueltig":
            q.ungueltig()
        assert f not in _ids(w, sitz), f"nach „{fall}“ noch sichtbar"
