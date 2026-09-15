"""Router: field_view (seit 1.3.0) -- Monteursansicht /vor-ort auf dem Fahrzeug-Tablet: heutige
Einsätze (Plantafel, über list_todays_assignments_for_employee()) und offene Entwurfsberichte
(über list_draft_reports_for_employee(), nur bei aktivem Modul "wartungen"). Kein eigener
OPTIONAL_MODULES-Eintrag (siehe CLAUDE.md) -- eine neue Oberfläche über bereits bestehenden
bzw. bereits eigenständig geschalteten Daten, kein neues fachliches Modul.

Trägt außerdem das Web-App-Manifest und die PWA-Icons (GET /manifest.json,
GET /api/mobile-icon/{size}.png) -- dieselbe Datei, da beides ausschließlich der
Monteursansicht dient."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..auth import COOKIE_NAME
from ..database import get_db
from ..deps import require_admin
from ..maintenance_contracts import list_relevant_contracts_for_employee
from ..mobile_manifest import build_icon_png, build_manifest
from ..mobile_settings import get_or_create_mobile_settings, is_past_shift_end, mobile_settings_to_dict, update_mobile_settings
from ..models import AppUser
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..planning import list_todays_assignments_for_employee
from ..schemas import FieldMaintenancePropertyGroupOut, MobileSettingsOut, MobileSettingsUpdate
from ..service_reports import list_draft_reports_for_employee

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): reiner Lesezugriff auf eine nicht-sensible
# Konfigurationszeile (Feierabend-Uhrzeit) -- für jede Rolle offen, Muster wie GET /api/modules.
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


@router.get("/api/field-view/today")
def get_field_view_today(request: Request, db: Session = Depends(get_db)):
    """Löst den Mitarbeiter ausschließlich über request.state.erp_user.employee_id auf, nie
    über einen Client-Parameter -- jeder sieht ausschließlich seine eigenen Einsätze. Prüft
    zusätzlich die Feierabend-Grenze (MobileSettings.shift_end_time) und meldet bei
    Überschreitung ab (Cookie löschen, 401) -- bewusst nur an diesem und dem GET /vor-ort-
    Einstiegspunkt, nicht in der globalen Middleware (siehe CLAUDE.md)."""
    user = getattr(request.state, "erp_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Bitte zuerst anmelden.")
    if is_past_shift_end(get_or_create_mobile_settings(db)):
        response = JSONResponse(status_code=401, content={"detail": "Feierabend -- bitte erneut anmelden."})
        response.delete_cookie(COOKIE_NAME)
        return response
    if user.employee_id is None:
        raise HTTPException(
            status_code=422,
            detail="Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte einen Administrator kontaktieren.",
        )
    draft_reports = list_draft_reports_for_employee(db, user.employee_id) if is_module_enabled(db, "wartungen") else []
    return {
        "assignments": list_todays_assignments_for_employee(db, user.employee_id),
        "draft_reports": draft_reports,
    }


@router.get("/api/field-view/maintenance-contracts", response_model=list[FieldMaintenancePropertyGroupOut])
def get_field_view_maintenance_contracts(request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """"Wartungen an meinen Objekten" (siehe CLAUDE.md) -- Objekte, an denen der angemeldete
    Mitarbeiter aktuell oder in Kürze zu tun hat, samt ihren Wartungsverträgen, damit ein Monteur
    ohne die volle Vertragsliste zu durchsuchen eine ungeplante Wartung starten kann. Löst den
    Mitarbeiter wie GET /api/field-view/today ausschließlich über request.state.erp_user auf --
    fehlt die Verknüpfung oder ist das Modul "wartungen" aus, bewusst eine leere Liste statt
    eines Fehlers (die Karte blendet dann leise aus, siehe vor_ort.html), da diese Karte anders
    als die Tagesliste kein Kernbestandteil der Seite ist."""
    if not is_module_enabled(db, "wartungen"):
        return []
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        return []
    return list_relevant_contracts_for_employee(db, user.employee_id)


@router.get("/api/mobile-settings", response_model=MobileSettingsOut)
def get_mobile_settings(db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    return mobile_settings_to_dict(get_or_create_mobile_settings(db))


@router.put("/api/mobile-settings", response_model=MobileSettingsOut)
def put_mobile_settings(
    payload: MobileSettingsUpdate, db: Session = Depends(get_db),
    _admin=Depends(require_admin("Nur Administratoren dürfen die Monteursansicht-Einstellungen ändern.")),
):
    shift_end_time = datetime.strptime(payload.shift_end_time, "%H:%M").time()
    return update_mobile_settings(db, shift_end_time)


@router.get("/manifest.json")
def get_manifest(db: Session = Depends(get_db)):
    return JSONResponse(build_manifest(db), media_type="application/manifest+json")


@router.get("/api/mobile-icon/{size}.png")
def get_mobile_icon(size: int, db: Session = Depends(get_db)):
    if size < 16 or size > 1024:
        raise HTTPException(status_code=404, detail="Ungültige Icon-Größe.")
    return Response(content=build_icon_png(db, size), media_type="image/png")
