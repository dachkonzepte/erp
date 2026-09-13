"""Router: imports

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 1 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ImportSummary
from ..service import persist_project
from ..importers.leistungen_dach import LeistungenDachImportError, parse_leistungen_dach_xml

router = APIRouter()

@router.post("/api/imports/leistungen-dach", response_model=ImportSummary)
async def import_leistungen_dach(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="Bitte eine XML-Datei auswählen.")

    xml_bytes = await file.read()
    try:
        project = parse_leistungen_dach_xml(xml_bytes)
    except LeistungenDachImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    inserted, replaced = persist_project(db, project, file.filename)
    return ImportSummary(
        filename=file.filename,
        source_name=project.source_name,
        source_version=project.source_version,
        title_count=project.title_count,
        position_count=len(project.services),
        material_item_count=project.material_item_count,
        inserted_services=inserted,
        replaced_services=replaced,
    )
