"""Gemeinsamer Rückfall "eigener Dokumenttyp zuerst, sonst der geteilte Satz" (seit 1.3.6).

Hintergrund: der Betreiber hat entschieden, dass Briefpapier, Ränder und die vier gezeichneten
Bausteine (Logo/Firmenkopf/Fußzeile/Wiederholungszeile) für ALLE Dokumenttypen gemeinsam gelten
sollen, statt separat je Typ gepflegt zu werden. Damit ein späterer, echter Sonderfall je
Dokumenttyp trotzdem möglich bleibt, OHNE das Datenmodell erneut anzufassen, gibt es keine neue
Spalte -- nur einen weiteren, reservierten Wert für die bestehende document_type-Spalte:
SHARED_DOCUMENT_TYPE ("default").

Die Regel: existiert für den tatsächlich angefragten Dokumenttyp (z.B. "reminder") bereits eine
eigene Zeile, gilt diese unverändert (Escape-Hatch für einen künftigen Sonderfall). Existiert
keine, wird stattdessen die unter SHARED_DOCUMENT_TYPE abgelegte, geteilte Zeile verwendet.

Seit 1.3.20 (Aufräumen nach dem PDF-Umbau, CLAUDE.md "Gemeinsamer Dokumenttyp"): "quote" ist KEIN
Sonderfall mehr -- der alte, positionsbasierte Angebots-Renderer (der eigene, produktiv angepasste
Werte brauchte) ist entfernt, der neue Renderer (app/quote_framed_pdf.py) liest seither wie jeder
andere Dokumenttyp über genau diese Regel. Eine Migration hat die zuvor eigenständigen "quote"-
Zeilen gelöscht, seither verhält sich "quote" wie "reminder"/"order"/"invoice"/"service_report":
eigene Zeile falls vorhanden, sonst der geteilte Satz.

Diese Regel wird von drei Stellen gebraucht (app/document_layout.py für Bausteine/Briefpapier,
app/document_page_margins.py für Ränder, app/document_frame.py als Nutzer beider beim Rendern) --
deshalb genau EINMAL hier implementiert, statt dreimal parallel. Build_customer_and_meta_block()
mit seinen inzwischen drei auseinandergelaufenen Varianten (siehe CLAUDE.md "Kopfbereich") ist die
Warnung, die diese Zentralisierung begründet.

WICHTIG: dies ist nur die LESE-Regel. Schreibende Zugriffe (ein neuer Hintergrund, geänderte
Ränder, ein verschobener Baustein) validieren an der jeweiligen Endpunkt-Schicht separat, dass NUR
SHARED_DOCUMENT_TYPE tatsächlich beschrieben werden darf (seit 1.3.20, vorher zusätzlich "quote" --
siehe _validate_writable_document_type() in app/routers/document_layout.py) -- sonst könnte eine
versehentlich mit einem echten Dokumenttyp (z.B. "invoice") beschriebene Zeile den Rückfall für
diesen Typ lautlos abschalten, ohne dass es jemandem auffällt."""

from sqlalchemy import select
from sqlalchemy.orm import Session

SHARED_DOCUMENT_TYPE = "default"


def resolve_shared_document_type(db: Session, model, document_type: str, *extra_filters) -> str:
    """Liefert den tatsächlich zu lesenden document_type: jeder Typ bleibt bei sich selbst, WENN
    dafür schon eine eigene Zeile existiert, sonst wird SHARED_DOCUMENT_TYPE geliefert. Seit 1.3.20
    gilt das ausnahmslos für jeden Dokumenttyp, auch "quote" (siehe Moduldocstring) -- vorher war
    "quote" hier ein fest verdrahteter Sonderfall, der nie zurückfiel.

    model ist die Tabelle (z.B. DocumentLayoutBlock), extra_filters engt die Existenzprüfung
    zusätzlich ein (z.B. auf einen bestimmten page_type) -- jede Tabelle prüft dabei mit ihrer
    eigenen, passenden Bedingung, nur die Entscheidung selbst ist hier zentral."""
    has_own_row = db.scalar(
        select(model.id).where(model.document_type == document_type, *extra_filters).limit(1)
    ) is not None
    return document_type if has_own_row else SHARED_DOCUMENT_TYPE
