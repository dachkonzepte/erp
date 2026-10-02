"""Router: Briefe an den Auftraggeber zur Behinderungsanzeige und Vorbehalte (seit 1.8.40, Stufe 2b, Runde 2b-3
Teil 2; app/notice_letters.py, app/notice_reservations.py).

Alles nur fürs Büro (buero_auftrag aufwärts), Monteure 403 -- der Monteur meldet die Behinderung, versendet
wird im Büro. Die Briefe hängen an Checklisten, das Modul "checklisten" muss an sein. Vorbehalte lesen Büro und
Admin, speichern nur Administratoren: die Prüfangabe entscheidet, ob ein Rechtstext in den Brief kommt (wie die
Klauseln der Vertragsgrundlage).

Gewöhnliche def-Routen: Rendern und Fotos verkleinern sind CPU-gebunden (Befund 1.3.62).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_dispatch import DispatchConflict, dispatch_to_dict
from ..models import AppUser
from ..modules import is_module_enabled
from ..notice_letters import NoticeStateError, ensure_letter, notice_state, preview_pdf, send_notice_letter
from ..notice_reservations import list_reservations, update_reservation
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import NoticeLetterSend, NoticeReservationOut, NoticeReservationUpdate

router = APIRouter()

_office_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Anzeigen an den Auftraggeber versendet das Büro."))
_admin_dep = Depends(require_min_role(ROLE_ADMIN, message="Vorbehalte und ihre rechtliche Prüfung pflegen nur Administratoren."))


def _require_module(db: Session) -> None:
    if not is_module_enabled(db, "checklisten"):
        raise HTTPException(status_code=403, detail="Das Modul Checklisten & Formulare ist deaktiviert.")


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (NoticeStateError, DispatchConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _actor(user: AppUser) -> tuple[int | None, str]:
    return getattr(user, "id", None), (getattr(user, "display_name", None) or getattr(user, "username", None) or "System")


@router.get("/api/checklists/{checklist_id}/notice-letters")
def get_notice_letters(checklist_id: int, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Stand beider Briefe (Behinderungsanzeige, Anzeige der Wiederaufnahme) samt Empfänger, Vorbelegung CC,
    Vorbehalt und Fassungen -- für die Karte auf der Ausfüllseite."""
    _require_module(db)
    return _call(notice_state, db, checklist_id)


@router.get("/api/checklists/{checklist_id}/notice-letters/{kind}/preview")
def get_notice_letter_preview(checklist_id: int, kind: str, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Vorschau mit dem Stand von jetzt (quer "Vorschau – nicht versendet"), nichts wird abgelegt."""
    _require_module(db)
    pdf = _call(preview_pdf, db, checklist_id, kind, user_name=_actor(_role)[1])
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Vorschau-{kind}-{checklist_id}.pdf"',
                             "Cache-Control": "private, no-store"})


@router.post("/api/checklists/{checklist_id}/notice-letters/{kind}/freeze")
def post_notice_letter_freeze(checklist_id: int, kind: str, db: Session = Depends(get_db), _role: AppUser = _office_dep):
    """Brief erstellen (für Post oder Fax): die Fassung zur aktuellen Unterschrift einfrieren und ablegen --
    vorhanden bleibt vorhanden."""
    _require_module(db)
    user_id, user_name = _actor(_role)
    _call(ensure_letter, db, checklist_id, kind, user_id=user_id, user_name=user_name)
    return _call(notice_state, db, checklist_id)


@router.post("/api/checklists/{checklist_id}/notice-letters/{kind}/send-email")
def post_notice_letter_send(checklist_id: int, kind: str, payload: NoticeLetterSend, db: Session = Depends(get_db),
                            _role: AppUser = _office_dep):
    """Per E-Mail an den Auftraggeber (An fest, nicht wählbar), CC frei -- immer die abgelegte Fassung."""
    _require_module(db)
    result = _call(send_notice_letter, db, checklist_id, kind, cc_email=payload.cc_email,
                   dispatch_key=payload.dispatch_key, user=_role)
    return dispatch_to_dict(result.dispatch)


@router.get("/api/settings/notice-reservations", response_model=list[NoticeReservationOut])
def get_notice_reservations(db: Session = Depends(get_db), _role: AppUser = _office_dep):
    return list_reservations(db)


@router.put("/api/settings/notice-reservations/{letter_kind}/{basis_group}", response_model=NoticeReservationOut)
def put_notice_reservation(letter_kind: str, basis_group: str, payload: NoticeReservationUpdate, request: Request,
                           db: Session = Depends(get_db), _role: AppUser = _admin_dep):
    actor = getattr(request.state, "erp_user", None)
    actor_name = getattr(actor, "display_name", None) or getattr(actor, "username", None) or "System"
    try:
        reservation, review_reset = update_reservation(
            db, letter_kind, basis_group, reservation_text=payload.reservation_text, reviewed_on=payload.reviewed_on,
            reviewed_by=payload.reviewed_by, actor_name=actor_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**reservation, "review_reset": review_reset}
