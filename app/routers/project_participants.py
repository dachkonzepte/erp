"""Router: Beteiligte am Projekt (seit 1.8.37, Stufe 2b, Runde 2b-2).

Nur Büro (buero_auftrag und höher), wie die übrige Projektmappe (app/routers/projects.py). Ein Monteur
bekommt 403 -- Beteiligte, ihre Kontaktdaten und die Vollmacht sind kaufmännisch. Geschäftslogik in
app/project_participants.py.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import actor_of
from ..models import AppUser, Contact, Project, ProjectParticipant
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..project_participants import (
    MAX_POWER_OF_ATTORNEY_BYTES, DuplicateParticipantError, add_participant, list_participants,
    participant_to_dict, power_of_attorney_path, remove_participant, remove_power_of_attorney, roles_list,
    store_power_of_attorney, update_participant,
)
from ..schemas import ParticipantRoleOut, ProjectParticipantCreate, ProjectParticipantOut, ProjectParticipantUpdate

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    return project


def _participant_or_404(db: Session, participant_id: int) -> ProjectParticipant:
    participant = db.get(ProjectParticipant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Beteiligter nicht gefunden.")
    return participant


def _errors(action):
    try:
        return action()
    except DuplicateParticipantError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/project-participant-roles", response_model=list[ParticipantRoleOut])
def get_participant_roles(_role: AppUser = _role_dep):
    return roles_list()


@router.get("/api/projects/{project_id}/participants", response_model=list[ProjectParticipantOut])
def get_project_participants(project_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    _project_or_404(db, project_id)
    return list_participants(db, project_id)


@router.post("/api/projects/{project_id}/participants", response_model=ProjectParticipantOut)
def post_project_participant(project_id: int, payload: ProjectParticipantCreate, db: Session = Depends(get_db),
                             _role: AppUser = _role_dep):
    project = _project_or_404(db, project_id)
    contact = db.get(Contact, payload.contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden.")
    participant = _errors(lambda: add_participant(
        db, project, contact, role=payload.role, copy_on_notices=payload.copy_on_notices,
        authorized_recipient=payload.authorized_recipient,
    ))
    return participant_to_dict(db, participant)


@router.put("/api/project-participants/{participant_id}", response_model=ProjectParticipantOut)
def put_project_participant(participant_id: int, payload: ProjectParticipantUpdate, db: Session = Depends(get_db),
                            _role: AppUser = _role_dep):
    participant = _participant_or_404(db, participant_id)
    values = payload.model_dump(exclude_unset=True)
    return participant_to_dict(db, _errors(lambda: update_participant(db, participant, values)))


@router.delete("/api/project-participants/{participant_id}")
def delete_project_participant(participant_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    remove_participant(db, _participant_or_404(db, participant_id))
    return {"ok": True}


@router.post("/api/project-participants/{participant_id}/power-of-attorney", response_model=ProjectParticipantOut)
def post_power_of_attorney(participant_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                           user: AppUser = _role_dep):
    participant = _participant_or_404(db, participant_id)
    data = file.file.read(MAX_POWER_OF_ATTORNEY_BYTES + 1)
    _user_id, user_name = actor_of(user)
    return participant_to_dict(db, _errors(lambda: store_power_of_attorney(
        db, participant, filename=file.filename, data=data, user_name=user_name,
    )))


@router.get("/api/project-participants/{participant_id}/power-of-attorney")
def get_power_of_attorney(participant_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    participant = _participant_or_404(db, participant_id)
    if not participant.poa_stored_filename:
        raise HTTPException(status_code=404, detail="Keine Vollmacht hinterlegt.")
    path = power_of_attorney_path(participant.poa_stored_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datei der Vollmacht nicht gefunden.")
    return FileResponse(path, media_type=participant.poa_content_type, filename=participant.poa_original_filename,
                        content_disposition_type="inline")


@router.delete("/api/project-participants/{participant_id}/power-of-attorney", response_model=ProjectParticipantOut)
def delete_power_of_attorney(participant_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return participant_to_dict(db, remove_power_of_attorney(db, _participant_or_404(db, participant_id)))
