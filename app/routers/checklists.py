"""Router: checklists (seit 1.8.1) -- ausgefüllte Checklisten des Moduls "checklisten"
(siehe docs/archiv/modul-checklisten.md, Abschnitt "Rechte").

Jeder Endpunkt ist für jede Rolle registriert (require_min_role(ROLE_FIELD)) -- die eigentliche
Entscheidung fällt je Kontext und je Checkliste hier im Router, die Geschäftslogik
(app/checklists.py) ist rollenlos:

- Büro/Admin (buero_auftrag aufwärts): alles, auch Kontext "Betrieb".
- Monteur (`field`), nur mit Mitarbeiterverknüpfung:
  - Kontext Auftrag: nur über require_field_order_access() (field_may_access_order(),
    Planungsbezug ODER eigener Bericht). Eine Checkliste ist KEIN zusätzlicher Weg zum Auftrag.
  - Kontext Objekt/Betriebsmittel: jedes Objekt/Gerät über die ID (Betreiberentscheidung A,
    dieselbe Ausnahme wie die mobile Objektansicht bzw. der QR-Code), Betriebsmittel nur bei
    aktivem Modul "betriebsmittel".
  - Kontext Betrieb: kein Zugriff.
  - Schreiben (Antworten, Anhänge, Abschließen, Löschen): nur die eigene Checkliste.
  - Eine Unterschrift sperrt die Antworten und Fotos oberhalb von ihr (seit 1.8.13, seit 1.8.14
    abschnittsweise) für JEDE Rolle, auch fürs Büro; "Unterschriften verwerfen" mit Begründung
    ist dem Büro vorbehalten.
  - Fremde Checklisten: in der Liste nur Titel/Datum/Ersteller/Status; Einzelabruf und Anhänge
    nur, wenn die Vorlage field_readable trägt (Betreiberentscheidung B).
  - Die EIGENE Checkliste bleibt erreichbar, auch wenn der Monteur inzwischen nicht mehr dem
    Auftrag zugeordnet ist -- dieselbe Überlegung wie Weg 2 beim Einsatzbericht (ein begonnener
    Entwurf darf durch eine Umplanung nicht unerreichbar werden). Das öffnet nur diese eine
    Checkliste, nicht den Auftrag.

Foto-/Unterschrift-Upload ist bewusst eine gewöhnliche `def`-Route: die Pillow-Verkleinerung ist
CPU-gebunden und liefe in einer `async def`-Route auf der Event-Loop (Befund 1.3.62)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..checklist_email import get_checklist_recipient_email, send_checklist_email
from ..checklist_follow_ups import list_checklists_with_open_follow_ups, list_follow_ups, run_checklist_follow_ups
from ..checklist_pdf import build_checklist_pdf
from ..checklist_rules import list_checklists_with_open_rules, list_rule_executions, run_checklist_rules
from ..checklists import (
    ChecklistLocked, add_attachment, asset_readiness, attachment_path, complete_checklist, create_checklist,
    delete_attachment, delete_checklist, discard_signatures, get_attachment, get_checklist, get_checklist_row,
    list_checklists, list_startable_templates, mark_asset_repaired, save_answer, MAX_PHOTO_UPLOAD_BYTES,
)
from ..database import get_db
from ..email_dispatch import DispatchConflict, dispatch_to_dict
from ..models import AppUser, Checklist
from ..modules import is_module_enabled
from ..permissions import ROLE_FIELD, ROLE_OFFICE_AUFTRAG, has_min_role, require_min_role
from ..schemas import (
    ChecklistAnswerWrite, ChecklistAssetReadinessOut, ChecklistAssetReleaseWrite, ChecklistCreate,
    ChecklistDiscardSignaturesWrite, ChecklistEmailSend, ChecklistFollowUpOut, ChecklistFollowUpsRunOut,
    ChecklistRuleExecutionOut, ChecklistRulesRunOut, ChecklistOut, ChecklistStartableTemplateOut,
    ChecklistSummaryOut,
)
from .orders import require_field_order_access

router = APIRouter()

MODULE_KEY = "checklisten"
_any_role_dep = Depends(require_min_role(ROLE_FIELD))
_office_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

NOT_OWNER = "Diese Checkliste hat eine andere Person angelegt."
ANSWERS_HIDDEN = "Von dieser Checkliste sind für Sie nur Titel, Datum und Ersteller sichtbar."
COMPANY_OFFICE_ONLY = "Checklisten im Kontext Betrieb sind dem Büro vorbehalten."


def _require_module_enabled(db: Session) -> None:
    if not is_module_enabled(db, MODULE_KEY):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")


def _is_office(role: AppUser) -> bool:
    return has_min_role(role, ROLE_OFFICE_AUFTRAG)


def _require_field_employee(role: AppUser) -> int:
    if role.employee_id is None:
        raise HTTPException(status_code=403, detail="Ihr Konto ist mit keinem Mitarbeiter verknüpft.")
    return role.employee_id


def _require_context_access(db: Session, role: AppUser, context_type: str, *, order_id=None, asset_id=None) -> None:
    """Darf diese Rolle im Kontext überhaupt etwas sehen/anlegen? Büro: immer."""
    if _is_office(role):
        return
    _require_field_employee(role)
    if context_type == "betrieb":
        raise HTTPException(status_code=403, detail=COMPANY_OFFICE_ONLY)
    if context_type == "auftrag":
        if order_id is None:
            raise HTTPException(status_code=403, detail="Kein Auftrag angegeben.")
        require_field_order_access(db, role, order_id)
    elif context_type == "betriebsmittel":
        if not is_module_enabled(db, "betriebsmittel"):
            raise HTTPException(status_code=403, detail="Das Modul Betriebsmittelverwaltung ist deaktiviert.")


def _is_own(role: AppUser, checklist: Checklist) -> bool:
    return role.employee_id is not None and checklist.created_by_employee_id == role.employee_id


def _checklist_for(db: Session, role: AppUser, checklist_id: int, *, write: bool = False) -> Checklist:
    """Lädt eine Checkliste und prüft den Zugriff. write=True: Ändern/Abschließen/Löschen."""
    checklist = get_checklist_row(db, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checkliste nicht gefunden.")
    if _is_office(role):
        return checklist
    _require_field_employee(role)
    if checklist.context_type == "betrieb":
        raise HTTPException(status_code=403, detail=COMPANY_OFFICE_ONLY)
    if _is_own(role, checklist):
        if checklist.context_type == "betriebsmittel" and not is_module_enabled(db, "betriebsmittel"):
            raise HTTPException(status_code=403, detail="Das Modul Betriebsmittelverwaltung ist deaktiviert.")
        return checklist
    _require_context_access(db, role, checklist.context_type, order_id=checklist.order_id,
                            asset_id=checklist.operational_asset_id)
    if write:
        raise HTTPException(status_code=403, detail=NOT_OWNER)
    if not checklist.template.field_readable:
        raise HTTPException(status_code=403, detail=ANSWERS_HIDDEN)
    return checklist


def _with_flags(data: dict, role: AppUser, checklist: Checklist) -> dict:
    """can_edit: mindestens ein Feld ist noch offen (seit 1.8.14 abschnittsweise, welche genau
    gesperrt sind, steht in sealed_field_ids). can_delete: Entwurf ohne jede Unterschrift, auch
    ohne verworfene."""
    own = _is_own(role, checklist)
    draft = checklist.status == "entwurf"
    data["is_own"] = own
    data["can_sign"] = draft and (_is_office(role) or own)
    sealed = set(data["sealed_field_ids"])
    data["can_edit"] = data["can_sign"] and any(
        f["field_type"] not in ("hinweis", "unterschrift") and f["id"] not in sealed for f in data["fields"])
    data["can_delete"] = data["can_sign"] and not data["has_signatures"]
    data["can_discard_signatures"] = draft and data["signed"] and _is_office(role)
    return data


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ChecklistLocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _detail(db: Session, role: AppUser, checklist_id: int) -> dict:
    db.expire_all()
    checklist = get_checklist_row(db, checklist_id)
    return _with_flags(get_checklist(db, checklist_id), role, checklist)


# --- Vorlagen zum Starten, Listen -----------------------------------------------------------

@router.get("/api/checklists/startable-templates", response_model=list[ChecklistStartableTemplateOut])
def get_startable_templates(context: str, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Veröffentlichte, nicht archivierte Vorlagen für einen Kontext -- nur Bezeichnung und
    Beschreibung, keine Regeln, keine Entwürfe."""
    _require_module_enabled(db)
    if not _is_office(_role) and context == "betrieb":
        raise HTTPException(status_code=403, detail=COMPANY_OFFICE_ONLY)
    return _call(list_startable_templates, db, context)


@router.get("/api/checklists", response_model=list[ChecklistSummaryOut])
def get_checklists(context: str | None = None, order_id: int | None = None, property_id: int | None = None,
                   operational_asset_id: int | None = None, status: str | None = None, template_id: int | None = None,
                   open_rules: bool = False, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Büro: frei filterbar. Monteur: genau EIN Bezug (Auftrag, Objekt oder Betriebsmittel) mit
    Zugriffsprüfung -- keine auftragsübergreifende Liste."""
    _require_module_enabled(db)
    if not _is_office(_role):
        given = [(k, v) for k, v in (("auftrag", order_id), ("objekt", property_id),
                                     ("betriebsmittel", operational_asset_id)) if v is not None]
        if len(given) != 1:
            raise HTTPException(status_code=403, detail="Bitte genau einen Auftrag, ein Objekt oder ein Betriebsmittel angeben.")
        context_type, _ = given[0]
        _require_context_access(db, _role, context_type, order_id=order_id, asset_id=operational_asset_id)
        context = context_type
    ids = None
    if open_rules:  # Büro: nur Checklisten mit nicht angelegten Aufgaben (seit 1.8.3)
        if not _is_office(_role):
            raise HTTPException(status_code=403, detail="Nur für das Büro.")
        ids = list_checklists_with_open_rules(db)
    rows = list_checklists(db, context_type=context, order_id=order_id, property_id=property_id,
                           asset_id=operational_asset_id, status=status, template_id=template_id, ids=ids)
    office = _is_office(_role)
    for row in rows:
        row["is_own"] = _role.employee_id is not None and row["created_by_employee_id"] == _role.employee_id
        row["can_open"] = office or row["is_own"] or row["field_readable"]
    return rows


@router.get("/api/checklists/mine", response_model=list[ChecklistSummaryOut])
def get_my_checklists(status: str | None = "entwurf", db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Eigene Checklisten (Standard: offene Entwürfe) -- für /mobil. Ohne Mitarbeiterverknüpfung
    eine leere Liste, kein Fehler (Muster GET /api/field-view/maintenance-contracts)."""
    _require_module_enabled(db)
    if _role.employee_id is None:
        return []
    rows = list_checklists(db, created_by_employee_id=_role.employee_id, status=status or None)
    if not _is_office(_role):
        rows = [r for r in rows if r["context_type"] != "betrieb"]
    for row in rows:
        row["is_own"] = True
        row["can_open"] = True
    return rows


@router.get("/api/checklists/asset-readiness/{asset_id}", response_model=ChecklistAssetReadinessOut)
def get_asset_readiness(asset_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Letzte Meldung zur Einsatzbereitschaft (Entscheidung B, Zusatz) -- bewusst für jede Rolle,
    unabhängig von field_readable: der Hinweis "nicht einsatzbereit" ist eine Sicherheitsangabe."""
    _require_module_enabled(db)
    _require_context_access(db, _role, "betriebsmittel", asset_id=asset_id)
    return asset_readiness(db, asset_id)


@router.post("/api/checklists/asset-readiness/{asset_id}/repaired", response_model=ChecklistAssetReadinessOut)
def post_asset_repaired(asset_id: int, payload: ChecklistAssetReleaseWrite, db: Session = Depends(get_db),
                        _role: AppUser = _office_dep):
    """Büro markiert ein als "nicht einsatzbereit" gemeldetes Gerät als repariert (seit 1.8.2) --
    mit Wer (Anzeigename des Kontos) und Wann. Monteure heben eine Meldung nur über eine neue
    Checkliste mit "einsatzbereit: ja" auf."""
    _require_module_enabled(db)
    if not is_module_enabled(db, "betriebsmittel"):
        raise HTTPException(status_code=403, detail="Das Modul Betriebsmittelverwaltung ist deaktiviert.")
    by_name = getattr(_role, "display_name", None) or getattr(_role, "username", None)
    return _call(mark_asset_repaired, db, asset_id, note=payload.note, user_id=getattr(_role, "id", None),
                 employee_id=_role.employee_id, by_name=by_name)


# --- Anlegen, Lesen, Ausfüllen --------------------------------------------------------------

@router.post("/api/checklists", response_model=ChecklistOut)
def post_checklist(payload: ChecklistCreate, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _require_context_access(db, _role, payload.context_type, order_id=payload.order_id,
                            asset_id=payload.operational_asset_id)
    data = _call(
        create_checklist, db, template_id=payload.template_id, context_type=payload.context_type,
        order_id=payload.order_id, property_id=payload.property_id, asset_id=payload.operational_asset_id,
        created_by_employee_id=_role.employee_id, created_by_user_id=getattr(_role, "id", None),
        client_uuid=payload.client_uuid,
    )
    return _detail(db, _role, data["id"])


@router.get("/api/checklists/{checklist_id}", response_model=ChecklistOut)
def get_checklist_endpoint(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id)
    return _detail(db, _role, checklist_id)


@router.put("/api/checklists/{checklist_id}/answers/{field_id}", response_model=ChecklistOut)
def put_checklist_answer(checklist_id: int, field_id: int, payload: ChecklistAnswerWrite,
                         db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id, write=True)
    _call(save_answer, db, checklist_id, field_id, payload.value, recorded_by_employee_id=_role.employee_id,
          client_uuid=payload.client_uuid, client_recorded_at=payload.client_recorded_at)
    return _detail(db, _role, checklist_id)


@router.post("/api/checklists/{checklist_id}/attachments", response_model=ChecklistOut)
def post_checklist_attachment(checklist_id: int, field_id: int = Form(...), file: UploadFile = File(...),
                              signer_name: str | None = Form(None), client_uuid: str | None = Form(None),
                              db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id, write=True)
    data = file.file.read(MAX_PHOTO_UPLOAD_BYTES + 1)
    _call(add_attachment, db, checklist_id, field_id, data, signer_name=signer_name,
          created_by_employee_id=_role.employee_id, client_uuid=client_uuid)
    return _detail(db, _role, checklist_id)


@router.get("/api/checklist-attachments/{attachment_id}/file")
def get_checklist_attachment_file(attachment_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    attachment = get_attachment(db, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden.")
    _checklist_for(db, _role, attachment.checklist_id)
    path = attachment_path(attachment)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/api/checklist-attachments/{attachment_id}", response_model=ChecklistOut)
def delete_checklist_attachment(attachment_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    attachment = get_attachment(db, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden.")
    checklist_id = attachment.checklist_id
    _checklist_for(db, _role, checklist_id, write=True)
    _call(delete_attachment, db, attachment_id)
    return _detail(db, _role, checklist_id)


@router.post("/api/checklists/{checklist_id}/complete", response_model=ChecklistOut)
def post_complete_checklist(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id, write=True)
    _call(complete_checklist, db, checklist_id, completed_by_employee_id=_role.employee_id)
    return _detail(db, _role, checklist_id)


@router.post("/api/checklists/{checklist_id}/discard-signatures", response_model=ChecklistOut)
def post_discard_signatures(checklist_id: int, payload: ChecklistDiscardSignaturesWrite,
                            db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """"Unterschrift verwerfen" (seit 1.8.13): nur Büro, Begründung Pflicht. Seit 1.8.15 mit
    gewählter Unterschrift (signature_id): sie und die Unterschriften in Feldern darunter fallen,
    die übrigen bleiben. Verworfene bleiben als markiert stehen (Nachweis)."""
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id, write=True)
    by_name = getattr(_role, "display_name", None) or getattr(_role, "username", None)
    _call(discard_signatures, db, checklist_id, signature_id=payload.signature_id, reason=payload.reason,
          user_id=getattr(_role, "id", None), by_name=by_name)
    return _detail(db, _role, checklist_id)


@router.get("/api/checklists/{checklist_id}/pdf")
def get_checklist_pdf(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """PDF einer abgeschlossenen Checkliste (seit 1.8.4) -- dieselbe Leseprüfung wie der
    Einzelabruf: Büro alles, Monteur die eigene und fremde nur bei field_readable, Betrieb nie.
    Gewöhnliche def-Route: das Rendern ist CPU-gebunden (Befund 1.3.62)."""
    _require_module_enabled(db)
    checklist = _checklist_for(db, _role, checklist_id)
    pdf = _call(build_checklist_pdf, db, checklist)
    filename = f"Checkliste-{checklist.id}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"})


@router.get("/api/checklists/{checklist_id}/email-recipient")
def get_checklist_email_recipient(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Vorbelegung für das Feld "An" (seit 1.8.20) -- nur fürs Büro, der Monteur sieht keine
    Kundenadresse über die Checkliste."""
    _require_module_enabled(db)
    checklist = _checklist_for(db, _role, checklist_id)
    return {"recipient_email": get_checklist_recipient_email(db, checklist)}


@router.post("/api/checklists/{checklist_id}/send-email")
def post_send_checklist_email(checklist_id: int, payload: ChecklistEmailSend, db: Session = Depends(get_db),
                              _role: AppUser = _office_dep):
    """Abgeschlossene Checkliste per E-Mail (seit 1.8.20) -- nur Büro/Admin, Versand-PDF mit
    verkleinerten Fotos unter 3 MB, über Protokoll und Ablage. Gewöhnliche def-Route: das Rendern
    (ggf. mehrere Stufen) ist CPU-gebunden (Befund 1.3.62)."""
    _require_module_enabled(db)
    checklist = _checklist_for(db, _role, checklist_id)
    try:
        result = send_checklist_email(db, checklist, to_email=payload.to_email, cc_email=payload.cc_email,
                                      dispatch_key=payload.dispatch_key, user=_role)
    except DispatchConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return dispatch_to_dict(result.dispatch)


@router.delete("/api/checklists/{checklist_id}")
def delete_checklist_endpoint(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id, write=True)
    _call(delete_checklist, db, checklist_id)
    return {"ok": True}


# --- Regeln → Aufgaben (seit 1.8.3, nur Büro) ------------------------------------------------

@router.get("/api/checklists/{checklist_id}/rule-executions", response_model=list[ChecklistRuleExecutionOut])
def get_rule_executions(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Ausgelöste Regeln und angelegte Aufgaben -- Büro-intern, Monteure sehen das nie."""
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id)
    return list_rule_executions(db, checklist_id)


@router.post("/api/checklists/{checklist_id}/run-rules", response_model=ChecklistRulesRunOut)
def post_run_rules(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """"Aufgaben nachholen" für eine Checkliste -- idempotent, legt nur Fehlendes an."""
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id)
    return _call(run_checklist_rules, db, checklist_id)


@router.post("/api/checklists/run-open-rules", response_model=ChecklistRulesRunOut)
def post_run_open_rules(db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """"Alle nachholen": jede Checkliste mit nicht angelegten Aufgaben erneut auswerten."""
    _require_module_enabled(db)
    total = {"created": 0, "module_off": 0}
    for checklist_id in list_checklists_with_open_rules(db):
        result = _call(run_checklist_rules, db, checklist_id)
        for key in total:
            total[key] += result[key]
    return total


# --- Folgen des Zwecks (seit 1.8.16, nur Büro) -----------------------------------------------

@router.get("/api/checklists/{checklist_id}/follow-ups", response_model=list[ChecklistFollowUpOut])
def get_follow_ups(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Folgen des Abschlusses mit ihrem Ziel -- Büro-intern wie die Regeln, Monteure sehen das nie."""
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id)
    return list_follow_ups(db, checklist_id)


@router.post("/api/checklists/{checklist_id}/run-follow-ups", response_model=ChecklistFollowUpsRunOut)
def post_run_follow_ups(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """"Folgen nachholen" für eine Checkliste -- idempotent, führt nur Offenes aus."""
    _require_module_enabled(db)
    _checklist_for(db, _role, checklist_id)
    return _call(run_checklist_follow_ups, db, checklist_id)


@router.post("/api/checklists/run-open-follow-ups", response_model=ChecklistFollowUpsRunOut)
def post_run_open_follow_ups(db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """"Alle nachholen" für Folgen: jede Checkliste mit offenen Folgen erneut auswerten."""
    _require_module_enabled(db)
    total = {"done": 0, "module_off": 0, "failed": 0}
    for checklist_id in list_checklists_with_open_follow_ups(db):
        result = _call(run_checklist_follow_ups, db, checklist_id)
        for key in total:
            total[key] += result[key]
    return total
