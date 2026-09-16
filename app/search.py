"""Geteilte Suchkernfunktion (siehe CLAUDE.md "Dateiablage je Objekt" -> "Suche als Einstieg").
Heute nur Objekte (Property) -- die Büro-Suche existiert noch nicht (bisher nur Befund, nie
gebaut). Diese Datei ist trotzdem bereits als geteilter KERN angelegt, den eine künftige
Büro-Suche um weitere Datensatzarten (Kunden, Aufträge, ...) ERWEITERT, nicht ersetzt -- Muster:
die Lehre aus build_customer_and_meta_block()s historischer Divergenz in drei Varianten (siehe
CLAUDE.md "Kopfbereich"), hier von Anfang an vermieden.

Zwei Schichten, bewusst getrennt:

1. search_properties() -- reine Datenbeschaffung, KEINE Rollenprüfung/-reduktion. Sucht Property
   nach Name/Straße/PLZ/Ort sowie dem Namen des zugehörigen Kunden (Join), unabhängig davon, wer
   aufruft. Gibt volle Property-ORM-Objekte zurück -- eine künftige, reichhaltigere Büro-Suche
   liest daraus, welche Felder sie zusätzlich zeigen will, ohne diese Funktion anzufassen.
2. field_safe_property_search_results() -- reduziert JEDES Ergebnis auf die für `field`
   zulässigen, harmlosen Felder (id, name, city).

search_properties_for_field() kombiniert beide zu der EINEN Funktion, die ein Monteurs-Endpunkt
aufrufen darf. WICHTIG für jeden künftigen, auch für `field` erreichbaren Such-Endpunkt (auch
einen gemeinsamen Büro+Monteur-Endpunkt): bei role==ROLE_FIELD MUSS er
search_properties_for_field() aufrufen, NIE search_properties() direkt zurückgeben -- die
Feldbegrenzung sitzt serverseitig, an der Rolle, nicht an der URL/dem Aufrufer. Das ist die
konkrete Umsetzung von Regel 11 (Standardverweigerung) für dieses Konzept: ein Monteur, der einen
künftigen, gemeinsamen Büro-Such-Endpunkt direkt aufruft, muss über DIESELBE Funktion trotzdem
nur Objekte und nur die harmlosen Felder bekommen, nicht die vollen Ergebnisse.

Index-Frage geprüft, nicht nur angenommen (siehe CLAUDE.md für die empirische Belegung): ein
gewöhnlicher B-Baum-Index hilft einem präfixlosen `ILIKE('%term%')` weder unter SQLite noch unter
PostgreSQL (Customer.name trägt bereits einen Index UND SQLite ignoriert ihn nachweislich bei
diesem Abfragemuster, EXPLAIN QUERY PLAN zeigt "SCAN"). Bei der aktuellen Datenmenge (163 Objekte,
162 Kunden) ist ein voller Tabellenscan je Suchanfrage ohnehin irrelevant (< 1ms) -- ein neuer
Index wäre hier reine Dekoration ohne messbaren Nutzen. Die tatsächlich wirksamen Hebel gegen zu
teure Anfragen sind MIN_QUERY_LENGTH (verhindert eine sehr breite Anfrage bei nur einem Zeichen)
und der client-seitige 300ms-Debounce (verhindert eine Anfrage je Tastendruck) -- siehe
app/templates/mobil.html."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Customer, Property

MIN_QUERY_LENGTH = 2
SEARCH_RESULT_LIMIT = 10


def search_properties(db: Session, query: str, *, limit: int = SEARCH_RESULT_LIMIT) -> list[Property]:
    """Kernfunktion (siehe Moduldocstring) -- sucht Objekte nach Name, Straße, PLZ, Ort und dem
    Namen des zugehörigen Kunden. Eine zu kurze Anfrage (< MIN_QUERY_LENGTH) liefert bewusst
    keine Treffer statt der ersten N Objekte der Datenbank -- eine Vorschlagsliste ohne
    brauchbaren Suchbegriff wäre irreführend, nicht hilfreich."""
    term = (query or "").strip()
    if len(term) < MIN_QUERY_LENGTH:
        return []
    pattern = f"%{term}%"
    stmt = (
        select(Property)
        .join(Customer, Property.customer_id == Customer.id)
        .where(or_(
            Property.name.ilike(pattern),
            Property.street.ilike(pattern),
            Property.postal_code.ilike(pattern),
            Property.city.ilike(pattern),
            Customer.name.ilike(pattern),
        ))
        .order_by(Property.name)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def field_safe_property_search_results(properties: list[Property]) -> list[dict]:
    """Schicht 2 (siehe Moduldocstring) -- reduziert auf id/name/city, die einzigen Felder, die
    die Vorschlagsliste laut Anfrage zeigen darf (Objektname und Ort zur Identifikation, kein
    Kunde, keine volle Adresse, keine Kundennummer)."""
    return [{"id": p.id, "name": p.name, "city": p.city} for p in properties]


def search_properties_for_field(db: Session, query: str, *, limit: int = SEARCH_RESULT_LIMIT) -> list[dict]:
    """Die EINE Funktion, die ein für `field` erreichbarer Such-Endpunkt aufrufen darf --
    kombiniert Schicht 1 (Objektbegrenzung: ausschließlich Property, nie Kunde/Auftrag/Rechnung/
    Angebot) mit Schicht 2 (Feldbegrenzung). Siehe Moduldocstring, warum künftiger Code diese
    Reduktion nicht selbst nachbauen darf."""
    return field_safe_property_search_results(search_properties(db, query, limit=limit))
