"""Das Angebot, aus dem ein Auftrag der Testdaten stammt (seit 1.9.338, Runde V1 „Fremdschlüssel in der Test-SQLite“).

orders.source_quote_id ist Pflicht, eindeutig und ein Fremdschlüssel auf quotes. Bis 1.9.337 legten viele Testhelfer einen Auftrag mit einer
erfundenen Nummer an (source_quote_id=1, 2, 9101 …) -- SQLite prüfte keine Fremdschlüssel, PostgreSQL lehnt jeden solchen Auftrag ab, und mit
PRAGMA foreign_keys=ON (seit 1.9.339) die Suite ebenso. Ein Helfer, der einen Auftrag von Hand baut, legt sein Angebot deshalb hiermit an:

    order = Order(order_number="AUF-TEST-0001", project_id=project.id,
                  source_quote_id=quell_angebot(db, project.id, "AUF-TEST-0001"), ...)

Die Angebotsnummer ist „Q-<Auftragsnummer>“: eindeutig je Datenbank wie die Auftragsnummer (uq_quote_number, uq_order_number), und sie gleicht keinem
Nummernkreis des ERP. Status „beauftragt“ wie bei einem Angebot, aus dem ein Auftrag entstanden ist.
"""

from app.models import Quote


def quell_angebot(db, project_id: int, order_number: str) -> int:
    """Legt das Quell-Angebot des Auftrags order_number im Projekt project_id an und gibt seine ID zurück (flush, kein commit)."""
    quote = Quote(quote_number=f"Q-{order_number}", project_id=project_id, title=f"Quelle von {order_number}", status="beauftragt")
    db.add(quote)
    db.flush()
    return quote.id
