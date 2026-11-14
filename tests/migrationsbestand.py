"""Echte Eltern für den Bestand einer Migrationsprobe (seit 1.9.338, Runde V1 „Fremdschlüssel in der Test-SQLite“).

Eine Migrationsprobe legt mit create_all() den Stand von heute an, schreibt einen Bestand mit rohem SQL und ruft downgrade()/upgrade() einer
Migration. Bis 1.9.337 zeigten diese Zeilen oft auf Eltern, die es nicht gab (order_id=1, contract_id=1, document_id=1 …) -- SQLite prüfte
keine Fremdschlüssel. Unter PostgreSQL und mit PRAGMA foreign_keys=ON (seit 1.9.339) scheitert so ein INSERT; deshalb legen die Proben ihre
Eltern hiermit an und setzen die IDs als Parameter ein. Jede Funktion legt genau einen Datensatz (bzw. eine Kette) an und gibt die ID(s)
zurück -- so ändert sich keine Zählung, die eine Probe prüft.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import (Checklist, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Contact, Customer, Defect, Order,
                        OrderAcceptance, OrderContract, OrderContractVersion, Project, SentDocument)
from app.project_pipeline_columns import default_pipeline_column_id
from tests.quellangebot import quell_angebot


def auftrag(engine, nummer: str = "AUF-BESTAND-1") -> dict:
    """Kunde, Projekt, Angebot und Auftrag; Rückgabe {"customer", "project", "quote", "order"}."""
    with Session(engine) as db:
        kunde = Customer(name="Bestand", last_name="Bestand")
        db.add(kunde)
        db.flush()
        projekt = Project(project_number=f"P-{nummer}", name="Bestand", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt)
        db.flush()
        order = Order(order_number=nummer, project_id=projekt.id, source_quote_id=quell_angebot(db, projekt.id, nummer), quote_number_snapshot=f"Q-{nummer}",
                      title="Bestand", customer_name="Bestand", customer_id=kunde.id)
        db.add(order)
        db.commit()
        return {"customer": kunde.id, "project": projekt.id, "quote": order.source_quote_id, "order": order.id}


def dokument(engine, name: str = "bestand") -> int:
    """Ein Eintrag der Ablage (sent_documents) ohne Datei; Rückgabe seine ID."""
    with Session(engine) as db:
        d = SentDocument(document_type="contract", document_id=1, filename=f"{name}.pdf", stored_filename=f"{name}-ablage.pdf", size_bytes=1,
                         sha256="0" * 64)
        db.add(d)
        db.commit()
        return d.id


def vertrag(engine, order_id: int, status: str = "entwurf") -> int:
    """Ein Vertrag am Auftrag; Rückgabe seine ID."""
    with Session(engine) as db:
        v = OrderContract(order_id=order_id, status=status, created_by_name="Bestand")
        db.add(v)
        db.commit()
        return v.id


def fassung(engine, contract_id: int, sent_document_id: int) -> int:
    """Fassung 1 eines Vertrags; Rückgabe ihre ID."""
    with Session(engine) as db:
        f = OrderContractVersion(contract_id=contract_id, version_no=1, basis_key="bgb", is_consumer=False, frozen_content="{}",
                                 content_sha256="x", sent_document_id=sent_document_id, attachment_kind="aktuell")
        db.add(f)
        db.commit()
        return f.id


def abnahme(engine, order_id: int) -> int:
    """Eine förmliche Abnahme am Auftrag (verweigert); Rückgabe ihre ID."""
    with Session(engine) as db:
        a = OrderAcceptance(order_id=order_id, kind="foermlich", accepted_on=date(2026, 9, 15), scope="gesamt", result="verweigert",
                            declared_by="auftraggeber", declared_by_name="K", content_sha256="x", created_by_name="Bestand")
        db.add(a)
        db.commit()
        return a.id


def mangel(engine, order_id: int) -> int:
    """Ein Mangel am Auftrag (ohne Abnahme); Rückgabe seine ID."""
    with Session(engine) as db:
        m = Defect(order_id=order_id, source="abnahme", description="Bestand", content_sha256="x", created_by_name="Bestand")
        db.add(m)
        db.commit()
        return m.id


def checkliste(engine) -> dict:
    """Vorlage mit Fassung 1, ein Feld „Unterschrift“ und eine Checkliste im Kontext Betrieb; Rückgabe {"checklist", "field"}."""
    with Session(engine) as db:
        vorlage = ChecklistTemplate(label="Bestand")
        db.add(vorlage)
        db.flush()
        fassung = ChecklistTemplateVersion(template_id=vorlage.id, version_no=1)
        db.add(fassung)
        db.flush()
        feld = ChecklistTemplateField(version_id=fassung.id, field_key="unterschrift", field_type="unterschrift", label="Unterschrift")
        db.add(feld)
        db.flush()
        liste = Checklist(template_id=vorlage.id, template_version_id=fassung.id, template_label_snapshot="Bestand", context_type="betrieb")
        db.add(liste)
        db.commit()
        return {"checklist": liste.id, "field": feld.id}


def kontakt(engine) -> int:
    """Ein Eintrag im Adressbuch; Rückgabe seine ID."""
    with Session(engine) as db:
        k = Contact(last_name="Bestand")
        db.add(k)
        db.commit()
        return k.id
