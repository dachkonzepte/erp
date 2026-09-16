"""Router: field_view (seit 1.3.0) -- Monteursansicht /mobil (bis 1.3.60 /vor-ort, reine
Umbenennung, siehe CLAUDE.md "Monteursansicht: Umbenennung zu /mobil") auf dem Fahrzeug-Tablet:
heutige Einsätze (Plantafel, über list_todays_assignments_for_employee()), offene Entwurfsberichte
(über list_draft_reports_for_employee(), nur bei aktivem Modul "wartungen") und, seit 1.3.61,
eigene kommende Plantafel-Termine sowie ein eigener Stundenzettel (PDF). Kein eigener
OPTIONAL_MODULES-Eintrag (siehe CLAUDE.md) -- eine neue Oberfläche über bereits bestehenden
bzw. bereits eigenständig geschalteten Daten, kein neues fachliches Modul.

Trägt außerdem das Web-App-Manifest und die PWA-Icons (GET /manifest.json,
GET /api/mobile-icon/{size}.png) -- dieselbe Datei, da beides ausschließlich der
Monteursansicht dient.

Seit "Dateiablage je Objekt" (siehe CLAUDE.md) zusätzlich die mobile Objektansicht
(properties/{property_id}/...) -- hier gilt ausdrücklich EINE ANDERE Zugriffsregel als der Rest
dieser Datei: ein Monteur erreicht JEDES Objekt über seine ID, nicht nur die eigenen
(list_field_relevant_property_ids() aus dem Wartungsfinder wird hier bewusst NICHT geprüft).
Die Grenze sitzt stattdessen ausschließlich im INHALT -- harmlose Objektfelder
(PropertyAccessOut), nur für Monteure freigegebene, nicht gesperrte Dokumentkategorien
(field_may_see_category(), beide Schlösser aus 1.3.62) und das bereits etablierte reduzierte
Wartungshistorie-Schema (ServiceReportHistoryOut) -- nie Preise, Beträge, Kalkulationen oder
Kundennotizen. Jeder dieser Endpunkte prüft das eigenständig, nicht nur die Auflistung: ein
Datei-Abruf über eine geratene ID prüft field_may_see_category() ERNEUT am Ausliefer-Zeitpunkt.

Die Wartungshistorie (.../maintenance-history) hat seither eine Detail-Variante
(.../maintenance-history/{report_id}/pdf) -- bewusst OHNE die sonst überall geltende
Ersteller-Prüfung require_field_report_ownership() (app/routers/orders.py): ein Monteur darf
hier auch den Bericht eines längst ausgeschiedenen Kollegen lesen, solange er zu diesem Objekt
gehört und bereits unterschrieben ist. Reines Lesen -- kein PUT/DELETE/sign existiert unter
diesem Pfad, siehe resolve_property_history_report_for_field() (app/service_reports.py)."""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import COOKIE_NAME
from ..database import get_db
from ..deps import require_admin
from ..document_categories import ensure_default_categories, field_may_see_category
from ..field_timesheet_pdf import build_field_timesheet_pdf
from ..maintenance_contracts import list_relevant_contracts_for_employee
from ..mobile_manifest import build_icon_png, build_manifest
from ..mobile_settings import get_or_create_mobile_settings, is_past_shift_end, mobile_settings_to_dict, update_mobile_settings
from ..models import AppUser, DocumentCategory, Order, Property
from ..modules import is_module_enabled
from ..permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE, require_role
from ..planning import list_field_bookable_order_ids, list_todays_assignments_for_employee, list_upcoming_assignments_for_employee
from ..property_documents import (
    MAX_UPLOAD_BYTES, can_preview_type, create_property_document, is_image_type,
    list_merged_documents_for_property, resolve_property_document_for_field,
)
from ..schemas import (
    FieldDocumentCategoryOut, FieldMaintenancePropertyGroupOut, MobileSettingsOut, MobileSettingsUpdate,
    PropertyAccessOut, PropertyDocumentListItemOut, PropertySearchHitOut, ServiceReportHistoryOut,
)
from ..search import search_properties_for_field
from ..service_report_pdf import build_service_report_pdf_for_field
from ..service_reports import (
    list_draft_reports_for_employee, list_maintenance_history_for_property_field,
    resolve_property_history_report_for_field,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): reiner Lesezugriff auf eine nicht-sensible
# Konfigurationszeile (Feierabend-Uhrzeit) -- für jede Rolle offen, Muster wie GET /api/modules.
_any_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD))


def _now() -> datetime:
    """Eigene, ersetzbare Bruchstelle für den aktuellen Zeitpunkt (seit 1.3.71) -- ausschließlich
    für tests/test_v224_field_view.py, das zwei bereits vor dieser Korrektur bestehende Tests
    hatte, die nach 19 Uhr (dem Standard-Feierabend, siehe unten) IMMER fehlschlugen, unabhängig
    von jeder Codeänderung: is_past_shift_end() erwartet zwar bereits ein optionales `now`,
    get_field_view_today() reichte es aber nirgends durch, sondern verließ sich stillschweigend
    auf dessen eigenen datetime.now()-Rückfall.

    BEWUSST NICHT als Query-/Body-Parameter auf der Route selbst -- das würde einem Monteur
    erlauben, die Feierabend-Abmeldung per `?now=...` zu umgehen, ein echtes Sicherheitsrisiko.
    Diese Funktion ist stattdessen eine reine Python-Ebene: die Tests rufen get_field_view_today()
    ohnehin schon direkt als Funktion auf (nicht über HTTP), monkeypatchen hier `_now` genauso,
    wie sie `db=`/`request=` bereits direkt statt über FastAPIs Depends()-Mechanismus setzen --
    kein Weg, der über eine echte HTTP-Anfrage erreichbar wäre."""
    return datetime.now()


@router.get("/api/field-view/today")
def get_field_view_today(request: Request, db: Session = Depends(get_db)):
    """Löst den Mitarbeiter ausschließlich über request.state.erp_user.employee_id auf, nie
    über einen Client-Parameter -- jeder sieht ausschließlich seine eigenen Einsätze. Prüft
    zusätzlich die Feierabend-Grenze (MobileSettings.shift_end_time) und meldet bei
    Überschreitung ab (Cookie löschen, 401) -- bewusst nur an diesem und dem GET /mobil-
    Einstiegspunkt, nicht in der globalen Middleware (siehe CLAUDE.md)."""
    user = getattr(request.state, "erp_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Bitte zuerst anmelden.")
    if is_past_shift_end(get_or_create_mobile_settings(db), _now()):
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
    eines Fehlers (die Karte blendet dann leise aus, siehe mobil.html), da diese Karte anders
    als die Tagesliste kein Kernbestandteil der Seite ist."""
    if not is_module_enabled(db, "wartungen"):
        return []
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        return []
    return list_relevant_contracts_for_employee(db, user.employee_id)


@router.get("/api/field-view/time-tracking/orders")
def get_field_view_time_tracking_orders(request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Auftragsauswahl für die reduzierte Zeiterfassung auf /mobil (seit 1.3.60, siehe
    CLAUDE.md „Zeiterfassung für Monteure"). Löst den Mitarbeiter wie GET /api/field-view/today
    ausschließlich über request.state.erp_user auf -- kein employee_id-Parameter, ein Monteur
    kann hierüber nie die Auftragsliste eines Kollegen abrufen. Reines Anzeige-Dict statt eines
    Pydantic-response_model (Muster list_relevant_contracts_for_employee() oben) -- die drei
    Felder entsprechen exakt dem, was time_tracking_context() (app/time_tracking.py) für die
    volle Seite ohnehin schon liefert, kein neues Anzeigeformat."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        return []
    order_ids = list_field_bookable_order_ids(db, user.employee_id)
    if not order_ids:
        return []
    rows = db.scalars(
        select(Order)
        .where(
            Order.id.in_(order_ids),
            or_(Order.status.is_(None), func.lower(func.coalesce(Order.status, "")).not_in(["abgeschlossen", "storniert"])),
        )
        .order_by(Order.order_number.desc())
    ).all()
    return [
        {"id": o.id, "order_number": o.order_number, "customer_name": o.customer_name, "property_address": o.property_address}
        for o in rows
    ]


@router.get("/api/field-view/upcoming")
def get_field_view_upcoming(request: Request, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """"Eigene Plantafel-Einträge" auf /mobil (seit 1.3.61, siehe CLAUDE.md "Zeiterfassung für
    Monteure" -> "Eigene Plantafel-Einträge") -- eine reine Leseansicht der eigenen KOMMENDEN
    Termine, kein Zugriff auf die Plantafel selbst: kein Verschieben, keine fremden
    Kolonnen/Aufträge. Löst den Mitarbeiter wie GET /api/field-view/today ausschließlich über
    request.state.erp_user auf, bewusst eine leere Liste statt eines Fehlers ohne
    Mitarbeiterverknüpfung (dieselbe Kartenlogik wie die Wartungen-Karte, kein Kernbestandteil
    der Seite). GET /planning (die volle Plantafel) bleibt für `field` weiterhin gesperrt --
    dieser Endpunkt zeigt nur die eigene, bereits stark eingegrenzte Sicht, siehe
    list_upcoming_assignments_for_employee() (app/planning.py)."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        return []
    return list_upcoming_assignments_for_employee(db, user.employee_id)


@router.get("/api/field-view/timesheet.pdf")
def get_field_view_timesheet_pdf(
    request: Request, year: int | None = None, month: int | None = None,
    db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    """Eigener Stundenzettel als PDF (seit 1.3.61, siehe CLAUDE.md "Zeiterfassung für Monteure"
    -> "Stundenzettel") -- ausschließlich die eigenen Buchungen, wie der Bildschirm-Stundenzettel
    ausschließlich über request.state.erp_user aufgelöst, kein employee_id-Parameter. Baut auf
    demselben gemeinsamen PDF-Rahmen wie Mahnung/Rechnung/Auftrag/Einsatzbericht/Angebot
    (render_framed_pdf(), siehe app/field_timesheet_pdf.py) -- mit Briefkopf, NICHT die alte,
    landscape-eigene Büro-Vorlage aus app/time_backoffice.py (admin-only, mehrere Mitarbeiter
    gleichzeitig, nutzt selbst bewusst NICHT den gemeinsamen Rahmen -- kein Vorbild für den
    Rahmen, nur für die Spaltenauswahl)."""
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        raise HTTPException(status_code=422, detail="Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet.")
    today = date.today()
    year = year or today.year
    month = month or today.month
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="Ungültiger Monat.")
    try:
        data = build_field_timesheet_pdf(db, user.employee_id, year, month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = f"Stundenzettel_{year:04d}-{month:02d}.pdf"
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/field-view/properties/search", response_model=list[PropertySearchHitOut])
def get_field_view_property_search(q: str = "", db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Die Monteurs-Objektsuche (Kernfunktion in app/search.py, siehe dort für die Begründung,
    warum eine künftige Büro-Suche sie erweitert statt ersetzt). MUSS vor
    GET /api/field-view/properties/{property_id} registriert sein: Starlette matcht Routen in
    Registrierungsreihenfolge, nicht nach Spezifität -- ein Aufruf von .../properties/search
    würde sonst am {property_id}:int-Platzhalter scheitern (422, "search" ist keine gültige
    Ganzzahl), das bereits mehrfach dokumentierte Literal-vs-Platzhalter-Muster (siehe CLAUDE.md).

    Liefert UNABHÄNGIG vom Aufrufer IMMER das feldsichere Ergebnis von
    search_properties_for_field() -- dieser Endpunkt IST die Monteurs-Suche, kein gemeinsamer,
    rollenabhängig antwortender Endpunkt (eine künftige, reichhaltigere Büro-Suche bekommt einen
    EIGENEN Endpunkt auf search_properties()). `q` ist der einzige Client-Parameter; ein
    zusätzlicher, erfundener Parameter (z. B. ?type=customer) wird von FastAPI ignoriert, kein
    Weg, mehr als Objekte zu bekommen. `limit` ist bewusst NICHT client-steuerbar (fest auf
    SEARCH_RESULT_LIMIT) -- ein ?limit=10000 kann nie mehr als die vorgesehenen zehn Treffer
    erzwingen. response_model=list[PropertySearchHitOut] kappt zusätzlich strukturell auf
    id/name/city/customer_name, selbst falls die Funktion künftig versehentlich mehr zurückgäbe."""
    return search_properties_for_field(db, q)


@router.get("/api/field-view/properties/{property_id}", response_model=PropertyAccessOut)
def get_field_view_property(property_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Mobile Objektansicht (siehe Moduldocstring oben, "Dateiablage je Objekt") -- BEWUSST ohne
    jede Zugriffsbeschränkung auf property_id: ein Monteur erreicht jedes Objekt über seine ID,
    nicht nur die eigenen. Die Sperre sitzt ausschließlich im Inhalt: PropertyAccessOut ist
    dieselbe feldsichere Teilmenge wie bei GET /api/orders/{order_id}/property -- kein `notes`,
    keine `customer_id`/`is_primary_address`."""
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return prop


@router.get("/api/field-view/document-categories", response_model=list[FieldDocumentCategoryOut])
def get_field_view_document_categories(db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Kategorie-Auswahl für den Monteur-Upload -- nur für Monteure freigegebene Kategorien
    (field_may_see_category(), beide Schlösser aus 1.3.62), damit die Oberfläche gar nicht erst
    eine gesperrte Kategorie zur Wahl anbietet. Der eigentliche Schutz sitzt trotzdem serverseitig
    im Upload-Endpunkt selbst (siehe unten) -- diese Liste ist nur die Komfort-Vorauswahl, kein
    zusätzliches Schloss."""
    ensure_default_categories(db)
    categories = db.scalars(
        select(DocumentCategory).where(DocumentCategory.active == True)  # noqa: E712
        .order_by(DocumentCategory.sort_order, DocumentCategory.id)
    ).all()
    return [
        FieldDocumentCategoryOut(id=c.id, key=c.key, label=c.label)
        for c in categories if field_may_see_category(c)
    ]


@router.get("/api/field-view/properties/{property_id}/documents", response_model=list[PropertyDocumentListItemOut])
def get_field_view_property_documents(property_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Zusammengeführte, nur für Monteure freigegebene Dokumentliste des Objekts (eigene
    Objekt-Uploads PLUS die Dokumente aller nicht archivierten Projekte des Objekts, siehe
    list_merged_documents_for_property() in app/property_documents.py) -- field_visible_only=True
    ist hier fest verdrahtet, nicht optional."""
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return list_merged_documents_for_property(db, property_id, field_visible_only=True)


def _resolve_or_404(db: Session, property_id: int, source: str, document_id: int):
    resolved = resolve_property_document_for_field(db, property_id, source, document_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    doc, path = resolved
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return doc, path


@router.get("/api/field-view/properties/{property_id}/documents/{source}/{document_id}/view")
def view_field_view_property_document(
    property_id: int, source: Literal["property", "project"], document_id: int,
    db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    """Der kritischste Endpunkt dieser Ansicht (zusammen mit .../download unten):
    resolve_property_document_for_field() prüft field_may_see_category() ERNEUT am
    Ausliefer-Zeitpunkt, nicht nur bei der Auflistung oben -- eine über die Liste nie gezeigte,
    aber per geratener {source}/{document_id} angefragte Datei aus einer gesperrten Kategorie
    liefert denselben 404 wie eine tatsächlich nicht existierende, damit eine Anfrage nicht
    einmal bestätigt, dass die Datei existiert."""
    doc, path = _resolve_or_404(db, property_id, source, document_id)
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename, content_disposition_type="inline")


@router.get("/api/field-view/properties/{property_id}/documents/{source}/{document_id}/download")
def download_field_view_property_document(
    property_id: int, source: Literal["property", "project"], document_id: int,
    db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    """Siehe view_field_view_property_document() oben -- identische Prüfung, nur ohne
    content_disposition_type='inline'."""
    doc, path = _resolve_or_404(db, property_id, source, document_id)
    return FileResponse(path, media_type=doc.content_type or "application/octet-stream", filename=doc.original_filename)


@router.post("/api/field-view/properties/{property_id}/documents", response_model=PropertyDocumentListItemOut)
async def upload_field_view_property_document(
    property_id: int, request: Request, file: UploadFile = File(...), category_id: int = Form(...),
    description: str | None = Form(None), db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    """Eigener, objektgebundener Upload eines Monteurs (siehe CLAUDE.md "Dateiablage je Objekt"
    für die Objekt-statt-Sammelprojekt-Entscheidung -- ein spontaner Einsatz hat oft gar kein
    Projekt). category_id wird HIER serverseitig gegen field_may_see_category() geprüft,
    unabhängig davon, was GET .../document-categories der Oberfläche zur Auswahl anbietet -- ein
    direkter API-Aufruf mit einer gesperrten Kategorie schlägt ebenso fehl wie über die UI.
    Bilder werden wie Berichtsfotos verkleinert, Dokumente bleiben im Original
    (create_property_document()/_store_uploaded_file(), app/property_documents.py)."""
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    user = getattr(request.state, "erp_user", None)
    if user is None or user.employee_id is None:
        raise HTTPException(status_code=422, detail="Für den Upload wird eine Mitarbeiterverknüpfung benötigt.")
    category = db.get(DocumentCategory, category_id)
    if category is None or not field_may_see_category(category):
        raise HTTPException(status_code=422, detail="Diese Kategorie ist für Monteure nicht freigegeben.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 50 MB.")
    doc = create_property_document(
        db, property_id, category_id=category_id, file_data=data, original_filename=file.filename,
        content_type=file.content_type, description=description, uploaded_by_employee_id=user.employee_id,
    )
    return {
        "source": "property", "id": doc.id, "property_id": doc.property_id, "project_id": None,
        "category_key": category.key, "category_label": category.label,
        "original_filename": doc.original_filename, "content_type": doc.content_type,
        "file_size": doc.file_size, "description": doc.description, "uploaded_at": doc.uploaded_at,
        "is_image": is_image_type(doc.content_type), "can_preview": can_preview_type(doc.content_type),
    }


@router.get(
    "/api/field-view/properties/{property_id}/maintenance-history",
    response_model=list[ServiceReportHistoryOut],
)
def get_field_view_property_maintenance_history(property_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep):
    """Alte Wartungsberichte des Objekts im bereits etablierten, reduzierten Schema
    (ServiceReportHistoryOut/_history_report_to_field_dict(), Rechtekonzept -> "Berichts-
    Eigentümerschaft") -- anders als list_property_history_for_field() (Auftrag-scoped, schließt
    den eigenen Auftrag aus) objektbezogen und ohne Ausschluss, siehe
    list_maintenance_history_for_property_field() in app/service_reports.py."""
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return list_maintenance_history_for_property_field(db, property_id)


@router.get("/api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf")
def get_field_view_property_maintenance_history_report_pdf(
    property_id: int, report_id: int, db: Session = Depends(get_db), _role: AppUser = _any_role_dep,
):
    """Detailansicht EINES früheren Berichts, ausschließlich über das Objekt erreichbar (Anlass:
    ein Monteur will vor einer erneuten Wartung nachvollziehen, was beim letzten Einsatz gemacht
    wurde, auch von einem inzwischen ausgeschiedenen Kollegen) -- die Liste oben zeigt dafür
    bereits `id` je Eintrag, dieser Endpunkt löst genau EINEN davon in ein vollständiges PDF auf.

    Anders als require_field_report_ownership() (app/routers/orders.py, für den EIGENEN Auftrag/
    Bericht gedacht) prüft resolve_property_history_report_for_field() KEINE Ersteller-Zuordnung
    -- nur, dass der Bericht tatsächlich zu DIESEM Objekt gehört und bereits unterschrieben ist.
    Eine geratene report_id oder eine, die zu einem ANDEREN Objekt gehört, liefert denselben 404
    wie ein nicht existierender Bericht (Muster resolve_property_document_for_field() oben).
    Reines Lesen: unter diesem Pfad existiert kein PUT/DELETE/sign -- die schreibenden
    Berichts-Endpunkte in app/routers/service_reports.py bleiben unverändert über
    require_field_report_ownership() auf den eigenen Bericht beschränkt.

    Das PDF entspricht dem Kundendokument bis auf einen einzigen Unterschied: keine Zeitbuchungen
    der Kollegen (build_service_report_pdf_for_field(), siehe app/service_report_pdf.py) -- kein
    Preis wird dadurch entfernt, ServiceReportMaterial/TimeEntry tragen ohnehin nirgends eine
    Preisspalte."""
    if db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    report = resolve_property_history_report_for_field(db, property_id, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Bericht nicht gefunden.")
    pdf = build_service_report_pdf_for_field(db, report)
    filename = f"Einsatzbericht_{report.order.order_number}_{report.id}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


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
