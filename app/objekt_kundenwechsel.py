"""Ein Objekt wechselt den Kunden (seit 1.11.30, Nebenbefund N1 aus dem Bauplan P2, Entscheidung des Betriebs vom 26.11.2026).

Bis 1.11.29 setzte PUT /api/properties/{id} den Kunden eines Objekts ohne jede Prüfung um: Objektdokumente, Checklisten, Dachflächen und
Wartungsverträge gehörten danach still dem neuen Kunden, die Projekte darauf weiter dem alten. Seitdem:

- Hängt am Objekt ein Vorgang (SPERREN: Projekt -- auch eines anderen Kunden --, Anfrage, Wartungsvertrag, Dokument, Checkliste, Abnahme, Mangel) oder ist
  es die Hauptadresse seines Kunden, wechselt es den Kunden nicht: 409 mit den Bereichen und dem Rat, beim neuen Kunden ein neues Objekt anzulegen.
- Sonst nur mit Begründung (fehlt sie, 422) und einem Eintrag in der Änderungshistorie mit der Begründung; was zum Gebäude selbst gehört, wechselt mit
  (WANDERT_MIT: Dachflächen mit Bauteilen und Schichten).

Jeder Fremdschlüssel auf properties steht in genau einer der beiden Listen (Wächter tests/test_v820_objekt_kundenwechsel.py); ein neuer kommt dort hinein.
Rollenlos; die Rolle prüft der Router.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import record_audit_entry
from .database import Base
from .models import Customer, Property

# (Tabelle, Spalte) -> (Einzahl, Mehrzahl) für die Meldung
SPERREN = {
    ("projects", "property_id"): ("Projekt", "Projekte"),
    ("inquiries", "property_id"): ("Anfrage", "Anfragen"),
    ("maintenance_contracts", "property_id"): ("Wartungsvertrag", "Wartungsverträge"),
    ("property_documents", "property_id"): ("Dokument", "Dokumente"),
    ("checklists", "property_id"): ("Checkliste", "Checklisten"),
    ("order_acceptances", "property_id"): ("Abnahme", "Abnahmen"),
    ("defects", "property_id"): ("Mangel", "Mängel"),
}

# (Tabelle, Spalte) -> warum sie mit dem Objekt wechselt
WANDERT_MIT = {
    ("roof_areas", "property_id"): "Dachflächen gehören zum Gebäude (mit Bauteilen und Schichten)",
    ("imported_addresses", "created_property_id"): "nur die Herkunft aus dem Adressimport",
}

GRUND_FEHLT = "Bitte eine Begründung für den Kundenwechsel angeben – sie steht danach in der Änderungshistorie."
GRUND_HOECHSTENS = 500


class KundenwechselGesperrt(ValueError):
    """Am Objekt hängt ein Vorgang oder es ist die Hauptadresse -- 409."""


class GrundFehlt(ValueError):
    """Kundenwechsel ohne Begründung -- 422."""


def fremdschluessel_auf_objekte() -> list[tuple[str, str]]:
    """Jede Spalte mit Fremdschlüssel auf properties.id als (Tabelle, Spalte)."""
    return sorted((t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns
                  for fk in c.foreign_keys if fk.column.table.name == "properties")


def _und(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


def sperrgrund(db: Session, prop: Property) -> str | None:
    """Warum das Objekt den Kunden nicht wechselt, oder None. Gezählt je Bereich in fester Reihenfolge (SPERREN)."""
    teile, gesamt = [], 0
    for (tabelle, spalte), (einzahl, mehrzahl) in SPERREN.items():
        t = Base.metadata.tables[tabelle]
        n = db.scalar(select(func.count()).select_from(t).where(t.c[spalte] == prop.id))
        if n:
            teile.append(f"{n} {einzahl if n == 1 else mehrzahl}")
            gesamt += n
    saetze = []
    if prop.is_primary_address:
        saetze.append("Das Objekt ist die Hauptadresse des Kunden – sie wechselt den Kunden nicht.")
    if teile:
        verb = "hängt" if gesamt == 1 else "hängen"
        saetze.append(f"Am Objekt {verb} noch {_und(teile)} – ein Objekt mit Vorgängen wechselt den Kunden nicht.")
    if not saetze:
        return None
    return " ".join(saetze) + " Lege beim neuen Kunden ein neues Objekt an."


def kunde_wechseln(db: Session, prop: Property, neuer_kunde: Customer, grund: str | None) -> None:
    """Setzt den Kunden des Objekts um (ohne Commit; der Aufrufer committet). Gleicher Kunde: nichts. Sperrt vorher die Zeile des Objekts (FOR UPDATE;
    SQLite ignoriert es), damit zwischen Zählen und Umsetzen kein Vorgang dazukommt, der das Objekt schon nutzt."""
    if neuer_kunde.id == prop.customer_id:
        return
    db.execute(select(Property.id).where(Property.id == prop.id).with_for_update())
    if (sperre := sperrgrund(db, prop)) is not None:
        raise KundenwechselGesperrt(sperre)
    grund = (grund or "").strip()
    if not grund:
        raise GrundFehlt(GRUND_FEHLT)
    alter_kunde = db.get(Customer, prop.customer_id)
    record_audit_entry(
        db, action="Kunde gewechselt", entity_type="Objekt", entity_id=prop.id, entity_label=prop.name,
        field_name="kundenwechsel_grund", field_label="Begründung des Kundenwechsels",
        old_value=alter_kunde.name if alter_kunde else None, new_value=f"{neuer_kunde.name} – {grund}",
    )
    prop.customer_id = neuer_kunde.id
