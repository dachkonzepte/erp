"""Router: document_layout (seit 1.0.58).

Endpunkte für den PDF-Layout-Editor -- Geschäftslogik liegt vollständig in
app/document_layout.py.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..document_frame import RENDERERS_USING_SHARED_FRAME
from ..document_layout import (
    DOCUMENT_TYPES, ensure_default_layout, get_background, get_effective_background,
    remove_background, reset_layout_to_default, set_background, update_layout_block,
)
from ..document_layout_background import (
    MAX_UPLOAD_BYTES, background_path, delete_background_file, prepare_background_upload, replace_background,
)
from ..document_page_margins import PAGE_TYPES, get_margins, reset_margins_to_default, update_margins
from ..document_type_fallback import SHARED_DOCUMENT_TYPE
from ..models import AppUser, DocumentLayoutBlock
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import (
    DocumentLayoutBackgroundOut, DocumentLayoutBlockOut, DocumentLayoutBlockUpdate,
    DocumentPageMarginsOut, DocumentPageMarginsUpdate,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): ausschließlich von settings.html genutzt (geprüft),
# Büro-/Admin-Konfiguration, für keinen Monteur relevant.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

# Nur dieser eine document_type-Wert darf tatsächlich BESCHRIEBEN werden -- SHARED_DOCUMENT_TYPE
# ("default", der geteilte Satz für jeden Dokumenttyp, siehe app/document_type_fallback.py). Ein
# echter Dokumenttyp wie "invoice"/"order"/"reminder"/"quote" darf hier NICHT ankommen: bekäme er
# versehentlich eine eigene Zeile, würde der Lese-Rückfall auf den geteilten Satz für genau diesen
# Typ ab sofort lautlos nicht mehr greifen -- niemandem fiele das auf, bis jemand die geteilten
# Einstellungen ändert und sich fragt, warum sie für diesen einen Dokumenttyp wirkungslos bleiben.
# Lesend gilt weiterhin der volle DOCUMENT_TYPES-Satz (siehe _validate_document_type), damit z.B.
# "reminder" weiterhin über den Rückfall gelesen werden kann.
#
# Seit 1.3.20 (Aufräumen nach dem PDF-Umbau): "quote" stand hier bis dahin zusätzlich, weil der
# alte, positionsbasierte Angebots-Renderer eigene, produktiv angepasste Werte brauchte und dafür
# über app/templates/document_layout_editor.html beschreibbar sein musste. Mit dessen Entfernung
# verhält sich "quote" wie jeder andere Dokumenttyp -- nur noch lesbar über den Rückfall, nicht
# mehr eigenständig beschreibbar. Ein Schreibversuch auf "quote" würde sonst eine neue, eigene
# Zeile anlegen und "quote" damit lautlos aus dem geteilten Satz herausfallen lassen -- genau der
# Zustand, den die Zusammenführung gerade erst aufgelöst hat.
WRITABLE_DOCUMENT_TYPES = {SHARED_DOCUMENT_TYPE}


def _validate_readable_document_type(document_type: str) -> None:
    """Wie eine reine DOCUMENT_TYPES-Prüfung, aber zusätzlich SHARED_DOCUMENT_TYPE ("default")
    selbst zulässig -- für Briefpapier/Ränder/Bausteine-GETs, da Einstellungen → Dokumente &
    Layout bewusst direkt "default" abfragt, nicht über einen echten Dokumenttyp."""
    if document_type not in DOCUMENT_TYPES and document_type != SHARED_DOCUMENT_TYPE:
        raise HTTPException(status_code=404, detail=f"Unbekannter Dokumenttyp: {document_type}")


def _validate_writable_document_type(document_type: str) -> None:
    if document_type not in WRITABLE_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{document_type}' kann nicht beschrieben werden -- nur "
                f"'{SHARED_DOCUMENT_TYPE}' ist zulässiges Ziel für Briefpapier/Ränder/Bausteine."
            ),
        )


def _get_block_or_404(db: Session, block_id: int) -> DocumentLayoutBlock:
    block = db.get(DocumentLayoutBlock, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Layout-Baustein nicht gefunden.")
    return block


# Muss VOR "/api/document-layout/{document_type}" registriert sein: Starlette matcht Routen in
# Registrierungsreihenfolge, nicht nach Spezifität -- "rollout-status" würde sonst als
# document_type-Wert verschluckt und liefe sofort in _validate_readable_document_type() ins 404,
# das exakte Literal-vs-Platzhalter-Muster, vor dem tests/test_v167_pagination.py bereits warnt.
@router.get("/api/document-layout/rollout-status")
def get_shared_frame_rollout_status(_role: AppUser = _role_dep):
    """Welche Dokumenttypen nutzen den geteilten Satz (Briefpapier/Ränder/Bausteine) bereits
    tatsächlich beim Rendern, welche noch nicht? Liest RENDERERS_USING_SHARED_FRAME direkt aus
    app/document_frame.py -- also von genau der Stelle, die ein künftiger Renderer beim Umstellen
    zwangsläufig anfassen muss (render_framed_pdf() lehnt einen unbekannten Typ ab), damit diese
    Vorschau nie veraltet, weil jemand eine separate Liste zu aktualisieren vergisst.

    "quote" stand hier bis 1.3.13 hartkodiert unter "excluded" (eigener, positionsbasierter
    Layout-Designer, nie am gemeinsamen Rahmen teilnehmend) -- seit 1.3.20 (Aufräumen nach dem
    PDF-Umbau, CLAUDE.md "Gemeinsamer Dokumenttyp") ist dieser Renderer entfernt, "quote" nutzt
    wie jeder andere Dokumenttyp ausschließlich den gemeinsamen Rahmen und den geteilten Satz.
    "excluded" ist deshalb nicht mehr hartkodiert, sondern (aktuell leer, da kein Dokumenttyp
    mehr dauerhaft ausgeschlossen ist) für einen künftigen, tatsächlich dauerhaft
    ausgeschlossenen Typ vorgesehen."""
    return {
        "using_shared_settings": [
            {"document_type": key, "label": label} for key, label in RENDERERS_USING_SHARED_FRAME.items()
        ],
        "not_yet_migrated": [
            {"document_type": t, "label": {"order": "Auftrag", "invoice": "Rechnung"}.get(t, t)}
            for t in sorted(DOCUMENT_TYPES - set(RENDERERS_USING_SHARED_FRAME))
        ],
        "excluded": [],
    }


@router.get("/api/document-layout/{document_type}", response_model=list[DocumentLayoutBlockOut])
def get_document_layout(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    return ensure_default_layout(db, document_type)


@router.put("/api/document-layout/blocks/{block_id}", response_model=DocumentLayoutBlockOut)
def put_layout_block(block_id: int, payload: DocumentLayoutBlockUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    block = _get_block_or_404(db, block_id)
    return update_layout_block(
        db, block, x_mm=payload.x_mm, y_mm=payload.y_mm, width_mm=payload.width_mm, height_mm=payload.height_mm,
        content=payload.content, font_size=payload.font_size, font_weight=payload.font_weight,
        text_align=payload.text_align, visible=payload.visible,
    )


@router.post("/api/document-layout/{document_type}/reset", response_model=list[DocumentLayoutBlockOut])
def post_reset_document_layout(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    return reset_layout_to_default(db, document_type)


@router.get("/api/document-layout/{document_type}/background", response_model=DocumentLayoutBackgroundOut)
def get_document_layout_background_status(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    row = get_effective_background(db, document_type)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=row is not None, repeat_on_every_page=row.repeat_on_every_page if row else True)


@router.get("/api/document-layout/{document_type}/background/file")
def get_document_layout_background_file(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    row = get_effective_background(db, document_type)
    if row is None:
        raise HTTPException(status_code=404, detail="Kein Hintergrund hinterlegt.")
    path = background_path(row.stored_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Hintergrunddatei nicht gefunden.")
    return FileResponse(path)


@router.post("/api/document-layout/{document_type}/background", response_model=DocumentLayoutBackgroundOut)
async def upload_document_layout_background(document_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(status_code=422, detail="Bitte PNG, JPEG oder WebP verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    existing = get_background(db, document_type)
    stored = replace_background(existing.stored_filename if existing else None, file.filename, data)
    row = set_background(db, document_type, stored)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=True, repeat_on_every_page=row.repeat_on_every_page)


@router.delete("/api/document-layout/{document_type}/background", response_model=DocumentLayoutBackgroundOut)
def delete_document_layout_background(document_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    existing = get_background(db, document_type)
    if existing is not None:
        delete_background_file(existing.stored_filename)
        remove_background(db, document_type)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=False)


# --- Seitentypbewusste Hintergründe (seit 1.3.1, app/document_frame.py) -- bewusst ein anderes
# Pfadsegment ("backgrounds", Plural) statt page_type in die bestehenden "background"-Routen
# einzufügen: die bestehenden Routen kennen bereits die Literale "file"/"repeat" an genau dieser
# Segmentposition, ein "/{page_type}" dort hätte eine Literal-vs-Platzhalter-Kollision riskiert
# (siehe tests/test_v167_pagination.py-Kommentar zu genau diesem Fallstrick in diesem Projekt).
# Akzeptiert zusätzlich application/pdf (nur Seite 0 wird gerastert) und normalisiert JEDE Quelle
# auf JPEG mit Seitenverhältnis-Prüfung (siehe app/document_layout_background.py) -- anders als
# die obigen, unveränderten Bild-Only-Routen des Angebots. Kein page_type-bewusster
# repeat-Endpunkt: das Feld bleibt nur für den Altbestandsfall (ein einzelner Hintergrund)
# relevant, siehe DocumentLayoutBackground-Docstring.

@router.get("/api/document-layout/{document_type}/backgrounds/{page_type}", response_model=DocumentLayoutBackgroundOut)
def get_document_layout_background_status_for_page_type(document_type: str, page_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    _validate_page_type(page_type)
    row = get_effective_background(db, document_type, page_type)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=row is not None, repeat_on_every_page=row.repeat_on_every_page if row else True)


@router.get("/api/document-layout/{document_type}/backgrounds/{page_type}/file")
def get_document_layout_background_file_for_page_type(document_type: str, page_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    _validate_page_type(page_type)
    row = get_effective_background(db, document_type, page_type)
    if row is None:
        raise HTTPException(status_code=404, detail="Kein Hintergrund hinterlegt.")
    path = background_path(row.stored_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Hintergrunddatei nicht gefunden.")
    return FileResponse(path)


@router.post("/api/document-layout/{document_type}/backgrounds/{page_type}", response_model=DocumentLayoutBackgroundOut)
async def upload_document_layout_background_for_page_type(document_type: str, page_type: str, file: UploadFile = File(...), db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    _validate_page_type(page_type)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    content_type = (file.content_type or "").lower()
    if content_type not in ("image/png", "image/jpeg", "image/webp", "application/pdf"):
        raise HTTPException(status_code=422, detail="Bitte PNG, JPEG, WebP oder PDF verwenden.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 10 MB.")
    try:
        jpeg_bytes = prepare_background_upload(data, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = get_background(db, document_type, page_type)
    stored = replace_background(existing.stored_filename if existing else None, "briefpapier.jpg", jpeg_bytes)
    row = set_background(db, document_type, stored, page_type)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=True, repeat_on_every_page=row.repeat_on_every_page)


@router.delete("/api/document-layout/{document_type}/backgrounds/{page_type}", response_model=DocumentLayoutBackgroundOut)
def delete_document_layout_background_for_page_type(document_type: str, page_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    _validate_page_type(page_type)
    existing = get_background(db, document_type, page_type)
    if existing is not None:
        delete_background_file(existing.stored_filename)
        remove_background(db, document_type, page_type)
    return DocumentLayoutBackgroundOut(document_type=document_type, has_background=False)


def _validate_page_type(page_type: str) -> None:
    if page_type not in PAGE_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Seitentyp: {page_type}")


@router.get("/api/document-layout/{document_type}/margins/{page_type}", response_model=DocumentPageMarginsOut)
def get_document_page_margins(document_type: str, page_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_readable_document_type(document_type)
    _validate_page_type(page_type)
    return get_margins(db, document_type, page_type)


@router.put("/api/document-layout/{document_type}/margins/{page_type}", response_model=DocumentPageMarginsOut)
def put_document_page_margins(document_type: str, page_type: str, payload: DocumentPageMarginsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    _validate_page_type(page_type)
    return update_margins(db, document_type, page_type, top_mm=payload.top_mm, bottom_mm=payload.bottom_mm, left_mm=payload.left_mm, right_mm=payload.right_mm)


@router.post("/api/document-layout/{document_type}/margins/{page_type}/reset", response_model=DocumentPageMarginsOut)
def post_reset_document_page_margins(document_type: str, page_type: str, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _validate_writable_document_type(document_type)
    _validate_page_type(page_type)
    return reset_margins_to_default(db, document_type, page_type)
