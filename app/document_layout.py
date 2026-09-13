"""PDF-Layout-Editor: Geschäftslogik (seit 1.0.58).

Verwaltet DocumentLayoutBlock-Zeilen -- Position/Größe/Sichtbarkeit der
Bausteine, aus denen sich ein PDF zusammensetzt, plus frei hinzufügbare
eigene Textblöcke. Siehe models.py für die ausführliche Begründung des
Datenmodells.

WICHTIGE, BEWUSSTE EINSCHRÄNKUNG DER ERSTEN VERSION: die hier hinterlegten
Positionen gehen von einem einseitigen Dokument aus (ein typisches, nicht zu
langes Angebot). Bei sehr vielen Positionen wächst items_table über die
geplante Höhe hinaus und kann nachfolgende Bausteine (Summen,
Zahlungsbedingungen) überlappen -- die bestehende, fließende PDF-Erzeugung
bricht dagegen automatisch um. Das freie Positionieren ist also ein
bewusster Kompromiss: mehr Gestaltungsfreiheit auf typischen, kürzeren
Dokumenten, keine automatische Serienbrief-artige Serienumbruch-Logik für
Ausreißer nach oben. Sollte sich das in der Praxis als zu einschränkend
zeigen, ist eine Mehrseiten-Behandlung ein guter, aber deutlich größerer
nächster Ausbauschritt.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .document_type_fallback import SHARED_DOCUMENT_TYPE, resolve_shared_document_type
from .models import DocumentLayoutBlock, DocumentLayoutBackground

DOCUMENT_TYPES = {"quote", "order", "invoice", "reminder", "service_report"}

# Seit 1.3.1 (app/document_frame.py, CLAUDE.md "PDF-Rahmen"): die vier gezeichneten Bausteine, die
# als optionaler Rückfall neben Briefpapier-Hintergrund + Rändern zur Verfügung stehen.
# x_mm/y_mm/width_mm/height_mm sind für
# 'footer_text' in diesem Modell NICHT die tatsächliche Zeichenposition (die Seitenzahl sitzt
# immer fest, siehe app/document_frame.py) -- nur `visible` wird dort gelesen.
#
# company_header UND logo starten standardmäßig UNSICHTBAR (seit 1.3.2, echter Fehler aus dem
# ersten Smoke-Test behoben): der Fließtext-Bereich beginnt bei der Mahnung -- anders als beim
# Angebot, wo fünf weitere, fest positionierte Bausteine dazwischenliegen -- direkt am oberen
# Rand (DocumentPageMargins.top_mm). company_header stand mit y_mm=17 exakt auf demselben Wert
# wie der damalige Standardrand (ebenfalls 17mm) -- gezeichneter Block und fließender Inhalt
# überlappten sich sichtbar. Wer Briefpapier hinterlegt, braucht den Baustein ohnehin nicht; wer
# keins hat, kann ihn einschalten, muss dann aber den oberen Rand für Seite 1 (und Folgeseiten,
# da beide denselben Baustein zeigen) entsprechend vergrößern -- seit 1.3.2 ist der damalige
# Mahnung-spezifische, seit 1.3.6 GEMEINSAME Standardrand dafür bereits groß genug bemessen
# (DOCUMENT_TYPE_MARGIN_OVERRIDES in app/document_page_margins.py, 42mm statt generisch 17mm),
# ein zusätzliches manuelles Vergrößern ist bei unveränderten Standardwerten nicht mehr nötig.
#
# Seit 1.3.6 (Zusammenführung der Layout-Einstellungen, CLAUDE.md "Gemeinsamer Dokumenttyp"):
# umbenannt von DEFAULT_REMINDER_LAYOUT -- gilt nicht mehr nur für die Mahnung, sondern (seit
# 1.3.20 auch das Angebot) für jeden Dokumenttyp (siehe SHARED_DOCUMENT_TYPE/
# resolve_shared_document_type in app/document_type_fallback.py). Migration 8567f75a5266
# überführt die bereits erprobten, 1.3.1/1.3.2 angepassten Mahnung-Zeilen unverändert in den
# geteilten Satz -- diese Konstante wird also nur noch für eine KOMPLETT frische Installation
# ohne jede bestehende Zeile gebraucht.
# continuation_header (seit 1.3.7, CLAUDE.md "PDF-Rahmen"): Wiederholungszeile auf Folgeseiten
# (Belegnummer/Kunden-Nr./Datum/Seite o. ä., dokumenttyp-spezifisch -- der Aufrufer übergibt die
# Beschriftung/Wert-Paare selbst an render_framed_pdf(), siehe app/document_frame.py). Erscheint
# NIE auf Seite 1 (dort steht der volle Kopfbereich als Inhalt). x_mm/width_mm sind weiterhin NICHT
# die tatsächliche Zeichenposition (links/rechts kommt aus den Rändern, damit die Zeile immer auf
# derselben Fluchtlinie wie der übrige Inhalt endet, siehe frame_content_width()) -- ABER `y_mm`
# UND `height_mm` sind seit 1.3.12 echt: document_frame.py liest sie tatsächlich (vorher fest bei
# 8mm/6mm, unabhängig vom Feldwert). Grund: ein echter, hochgeladener Briefbogen kann seine
# Dekorfläche an jeder beliebigen Stelle haben -- bei der 1.3.11-Verifikation gegen die echte
# Datenbank überlagerte die feste 8mm-Position sichtbar die obere Dekorfläche des tatsächlich
# hochgeladenen Briefpapiers (CLAUDE.md, Abschnitt "Einstellbare Position der Wiederholungszeile").
# Standardwert 12mm/4mm (Höhe: eine realistische einzeilige 8pt-Textzeile, keine willkürliche
# Abschätzung mehr) ist für eine Installation OHNE eigene Kopfgrafik gewählt -- bleibt damit knapp
# UNTERHALB von Logo/Firmenkopf (die bei y_mm=17 beginnen, 1mm Abstand zur Unterkante bei
# 12+4=16mm), unabhängig vom konfigurierten Rand. Ein Briefbogen mit einer tieferen Kopfgrafik
# (wie im konkreten Fund) braucht einen größeren, selbst eingestellten Wert -- dafür jetzt ein
# eigenes Eingabefeld in Einstellungen → Dokumente & Layout, keine Codeänderung mehr nötig.
# Default AN (anders als footer_text, siehe unten) -- eine reine Text-Zeile ohne Flächenbedarf,
# die Belegnummer/Kunden-Nr./Datum trägt, liefert Informationen, die ein Briefbogen von sich aus
# nicht haben kann, und läuft dabei nicht in dessen eigenen, aufgedruckten Fußbereich (siehe
# direkt darunter).
#
# footer_text (Seitenzahl) steht seit 1.3.8 standardmäßig auf visible=False (vorher, seit 1.3.1,
# `True`) -- echter Fehler, gefunden bei der 1.3.7-Verifikation gegen die echte,  migrierte
# Datenbank: die feste Zeichenposition (20mm/12mm von links/unten) überlagerte sichtbar den
# eigenen, aufgedruckten Fußbereich des tatsächlich hochgeladenen Briefpapiers (Anschrift,
# Kontakt, Registergericht, Bankverbindung stehen dort bereits). Anders als beim 1.3.2-Fehler
# (company_header/logo, dort ging es um eine Kollision mit dem FLIESSENDEN INHALT) hier eine
# Kollision mit dem Briefbogen selbst -- und die Seitenangabe wird an dieser Stelle inzwischen
# ohnehin nicht mehr gebraucht: sie steht seit 1.3.4 im Meta-Block auf Seite 1 und seit 1.3.7 in
# der Wiederholungszeile auf Folgeseiten. Bleibt abschaltbar bestehen für Installationen ohne
# eigenen Briefbogen, die trotzdem eine Seitenzahl unten auf jeder Seite wollen.
DEFAULT_SHARED_LAYOUT = [
    ("logo", "Firmenlogo", 155, 10, 35, 20, 9.5, "normal", "left", False),
    ("company_header", "Firmenkopf", 18, 17, 176, 22, 9.5, "normal", "left", False),
    ("footer_text", "Fußzeile (Seitenzahl)", 18, 282, 176, 8, 8, "normal", "left", False),
    ("continuation_header", "Wiederholungszeile (Folgeseiten)", 18, 12, 176, 4, 8, "normal", "left", True),
]


def ensure_default_layout(db: Session, document_type: str) -> list[DocumentLayoutBlock]:
    """Legt beim ersten Aufruf für diesen Dokumenttyp die Standardbelegung an. Rührt eine bereits
    bestehende Belegung nicht an -- ruft man das erneut auf, nachdem jemand schon etwas
    verschoben hat, bleibt die Bearbeitung erhalten.

    Jeder Dokumenttyp -- seit 1.3.20 auch "quote", siehe CLAUDE.md "Gemeinsamer Dokumenttyp"/
    Aufräumen nach dem PDF-Umbau -- landet über resolve_shared_document_type() beim geteilten Satz
    (SHARED_DOCUMENT_TYPE), sofern für ihn nicht ausnahmsweise eine eigene Zeile existiert -- das
    ist bewusst dieselbe Regel wie in app/document_page_margins.py, hier zentral aus
    app/document_type_fallback.py importiert statt ein zweites Mal nachgebaut.

    document_type darf hier zusätzlich SHARED_DOCUMENT_TYPE selbst sein (seit 1.3.6) -- die
    Oberfläche unter Einstellungen → Dokumente & Layout fragt/schreibt bewusst direkt "default",
    nicht über einen echten Dokumenttyp."""
    if document_type not in DOCUMENT_TYPES and document_type != SHARED_DOCUMENT_TYPE:
        raise ValueError(f"Unbekannter Dokumenttyp: {document_type}")
    effective_type = resolve_shared_document_type(db, DocumentLayoutBlock, document_type)
    existing = db.scalar(select(DocumentLayoutBlock.id).where(DocumentLayoutBlock.document_type == effective_type).limit(1))
    if existing is not None:
        return list_layout_blocks(db, effective_type)
    for i, (block_type, label, x, y, w, h, fs, fw, align, visible) in enumerate(DEFAULT_SHARED_LAYOUT):
        db.add(DocumentLayoutBlock(
            document_type=effective_type, block_type=block_type, label=label,
            x_mm=Decimal(x), y_mm=Decimal(y), width_mm=Decimal(w), height_mm=Decimal(h),
            font_size=Decimal(str(fs)), font_weight=fw, text_align=align, visible=visible,
            sort_order=(i + 1) * 10,
        ))
    db.commit()
    return list_layout_blocks(db, effective_type)


def list_layout_blocks(db: Session, document_type: str) -> list[DocumentLayoutBlock]:
    return db.scalars(
        select(DocumentLayoutBlock)
        .where(DocumentLayoutBlock.document_type == document_type)
        .order_by(DocumentLayoutBlock.sort_order, DocumentLayoutBlock.id)
    ).all()


def update_layout_block(
    db: Session, block: DocumentLayoutBlock, *, x_mm: Decimal, y_mm: Decimal, width_mm: Decimal,
    height_mm: Decimal, content: str | None, font_size: Decimal, font_weight: str, text_align: str, visible: bool,
) -> DocumentLayoutBlock:
    block.x_mm = x_mm
    block.y_mm = y_mm
    block.width_mm = width_mm
    block.height_mm = height_mm
    block.font_size = font_size
    block.font_weight = font_weight
    block.text_align = text_align
    block.visible = visible
    db.commit()
    db.refresh(block)
    return block


def reset_layout_to_default(db: Session, document_type: str) -> list[DocumentLayoutBlock]:
    """Löscht die komplette aktuelle Belegung und legt die Standardbelegung neu an -- bewusst
    destruktiv, im Frontend mit einer deutlichen Sicherheitsabfrage abzusichern."""
    for block in list_layout_blocks(db, document_type):
        db.delete(block)
    db.commit()
    return ensure_default_layout(db, document_type)


def get_background(db: Session, document_type: str, page_type: str = "first") -> DocumentLayoutBackground | None:
    """page_type ist seit 1.3.1 optional (Default "first") -- jeder bestehende Aufruf ohne
    page_type (Angebot: quote_layout_pdf.py, der alte Bild-Upload-Endpunkt) trifft nach der
    Migration exakt dieselbe Zeile wie vorher, jetzt mit page_type='first' getaggt.

    LITERALER Zugriff, bewusst OHNE den seit 1.3.6 bestehenden Rückfall auf den geteilten Satz
    (siehe get_effective_background() dafür) -- set_background()/set_background_repeat()/
    remove_background() suchen darüber die Zeile, die sie tatsächlich verändern/löschen wollen.
    Würde diese Funktion selbst zurückfallen, könnte ein Schreibzugriff mit einem echten
    Dokumenttyp (z.B. versehentlich "invoice") die GETEILTE Zeile finden und verändern, statt
    (wie beabsichtigt) eine eigene, neue Zeile für "invoice" anzulegen -- genau das lautlose
    Fehlverhalten, vor dem app/document_type_fallback.py warnt."""
    return db.scalar(select(DocumentLayoutBackground).where(
        DocumentLayoutBackground.document_type == document_type,
        DocumentLayoutBackground.page_type == page_type,
    ))


def get_effective_background(db: Session, document_type: str, page_type: str = "first") -> DocumentLayoutBackground | None:
    """Wie get_background(), aber MIT Rückfall auf den geteilten Satz (SHARED_DOCUMENT_TYPE),
    falls für document_type selbst keine eigene Zeile existiert -- für lesende, darstellende
    Zwecke (app/document_frame.py beim tatsächlichen Rendern; die Admin-Oberfläche, wenn sie
    anzeigen will, was für einen Dokumenttyp aktuell WIRKT). Seit 1.3.20 gilt das ausnahmslos für
    jeden Dokumenttyp, auch "quote" (siehe CLAUDE.md "Gemeinsamer Dokumenttyp"/Aufräumen nach dem
    PDF-Umbau).

    Zweiter Rückfall (seit 1.3.13, gefunden beim Vergleich des damals neuen, parallelen Angebots-
    Renderers gegen ein echtes, mehrseitiges Angebot -- zu dem Zeitpunkt trug "quote" noch eine
    eigene, nie um eine eigene Folgeseiten-Zeile ergänzte "first"-Zeile): existiert für
    page_type="continuation" KEINE eigene Zeile, aber die "first"-Zeile trägt
    repeat_on_every_page=True, wird die "first"-Zeile stattdessen zurückgegeben.
    document_frame.py::_draw_background() ist erst seit 1.3.1 seitentypbewusst --
    repeat_on_every_page ist ein älteres Feld aus der Zeit VOR der page_type-Aufteilung
    (Altbestandsfall, siehe DocumentLayoutBackground-Docstring), bleibt als genereller
    Mechanismus bestehen, auch wenn "quote" seit 1.3.20 (eigene Zeile per Migration gelöscht)
    kein praktischer Auslöser mehr dafür ist."""
    effective_type = resolve_shared_document_type(db, DocumentLayoutBackground, document_type, DocumentLayoutBackground.page_type == page_type)
    row = get_background(db, effective_type, page_type)
    if row is None and page_type != "first":
        first_row = get_background(db, effective_type, "first")
        if first_row is not None and first_row.repeat_on_every_page:
            return first_row
    return row


def set_background(db: Session, document_type: str, stored_filename: str, page_type: str = "first") -> DocumentLayoutBackground:
    """Legt den Datenbankeintrag für einen neu hochgeladenen Hintergrund an
    oder aktualisiert ihn -- das Austauschen der eigentlichen Datei
    (inkl. Löschen der alten) übernimmt bereits replace_background() in
    app/document_layout_background.py, bevor diese Funktion aufgerufen
    wird. Ein bereits gesetztes repeat_on_every_page bleibt beim erneuten
    Hochladen erhalten (nur stored_filename wird ausgetauscht)."""
    row = get_background(db, document_type, page_type)
    if row is None:
        row = DocumentLayoutBackground(document_type=document_type, page_type=page_type, stored_filename=stored_filename)
        db.add(row)
    else:
        row.stored_filename = stored_filename
    db.commit()
    db.refresh(row)
    return row


def set_background_repeat(db: Session, document_type: str, repeat: bool, page_type: str = "first") -> DocumentLayoutBackground | None:
    """Ändert nur, ob der bereits hinterlegte Hintergrund bei mehrseitigen
    Dokumenten auf jeder Seite wiederholt wird -- ohne die Datei selbst
    anzufassen. Gibt None zurück, wenn (noch) kein Hintergrund existiert.
    Nur für den Altbestandsfall (ein einzelner Hintergrund, Angebot) relevant -- bei getrennten
    Seitentyp-Hintergründen (page_type != "first") übernimmt die bloße Existenz der jeweiligen
    Zeile dieselbe Rolle, siehe DocumentLayoutBackground-Docstring."""
    row = get_background(db, document_type, page_type)
    if row is None:
        return None
    row.repeat_on_every_page = repeat
    db.commit()
    db.refresh(row)
    return row


def remove_background(db: Session, document_type: str, page_type: str = "first") -> None:
    row = get_background(db, document_type, page_type)
    if row is not None:
        db.delete(row)
        db.commit()
