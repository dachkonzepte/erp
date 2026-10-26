"""Router: pages

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 22 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

import logging
import os
from urllib.parse import quote

from fastapi import APIRouter
from pathlib import Path
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from sqlalchemy.orm import Session

from ..checklist_purposes import DEFAULT_PURPOSE, PURPOSES
from ..meldungen import KEIN_MITARBEITER
from ..concern_notices import OPEN_CONCERNS_TEXT
from ..database import get_db
from ..deps import require_admin
from ..models import AppUser
from ..permissions import ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ZEITEN_NUR_LESEN, darf_lohndaten, darf_zeit_buchen, darf_zeit_fuer_andere_buchen, default_home_page_for_role, has_min_role, has_role, require_min_role, zeit_nur_mit_von_bis
from .. import seitendaten
from ..design_dateien import pruefsumme as ds_pruefsumme
from ..version import APP_VERSION
from ..weiterleitung import ist_lokal, sicheres_ziel

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.globals["app_version"] = APP_VERSION
# Seit 1.9.2: Zusatz ?v= an ds.css und ds-basis.css aus dem Inhalt (_ds_kopf.html), beim Start gebildet -- einfache Werte statt einer
# Funktion, damit Tests mit einer schlanken Jinja-Umgebung die Seiten weiter rendern (ein fehlender Wert ergibt dort leeren Text)
templates.env.globals["ds_css_pruefsumme"] = ds_pruefsumme("ds.css")
templates.env.globals["ds_basis_pruefsumme"] = ds_pruefsumme("ds-basis.css")
# seit 1.9.5: die alten Farbnamen der Seiten (--bg, --card, --accent …) zeigen zentral auf --ds-*
templates.env.globals["ds_alte_namen_pruefsumme"] = ds_pruefsumme("ds-alte-namen.css")
templates.env.globals["kein_mitarbeiter"] = KEIN_MITARBEITER  # seit 1.8.159: eine Meldung für Server und Vorlagen

# Die fuenf Jinja-Globals unten laufen bei JEDER Seitenanfrage (jede Seite bindet _sidebar.html
# UND seit 1.3.45 _topbar.html ein, die get_theme()/is_module_enabled()/sidebar_logo_url()/
# sidebar_logo_height_px()/account_display() aufrufen). Seit 1.8.114 (Vorgabe vom 16.10.2026,
# Punkt 1c) oeffnen sie keine eigene Sitzung mehr: sie lesen die Seitendaten der Anfrage, die
# die Anmeldeschranke in ihrer einen Sitzung mitgeladen hat (app/seitendaten.py) -- bis 1.8.113
# holte jeder Aufruf eine eigene Verbindung, eine Seite mit Seitenleiste so 37 (/tasks 41). Ein
# DB-Zustand, der beim Laden einen Teil scheitern laesst (z. B. eine durch eine uebersprungene
# Migration fehlende Spalte, oder ein general_settings.logo_filename, das auf eine kaputte
# Datei zeigt), darf NIE als Ausnahme durchschlagen -- sonst antwortet JEDE Seite mit 500,
# einschliesslich der Anmeldeseite, und niemand kommt mehr ins System, um es zu reparieren
# (realer Vorfall, siehe CLAUDE.md). app/seitendaten.py::laden() faellt deshalb je Teil auf
# einen sicheren, immer darstellbaren Wert zurueck. pass_context: Jinja reicht den Kontext der
# Vorlage (mit request) als erstes Argument herein; ohne Kontext (direkter Aufruf) laden sie
# selbst, mit einer Sitzung.


def _seitendaten(context) -> seitendaten.Seitendaten:
    return seitendaten.fuer_anfrage(context.get("request") if context is not None else None)


@pass_context
def _current_theme(context=None) -> dict:
    """Jinja-Global (Aufruf als Funktion, kein statischer Wert): die Akzentfarbe aus
    general_settings, je Anfrage frisch -- Aenderungen sind ohne Neustart auf der naechsten
    Seitenanfrage sichtbar."""
    return {"accent_color": _seitendaten(context).akzentfarbe}


templates.env.globals["get_theme"] = _current_theme


@pass_context
def _is_module_enabled(context, module_key: str) -> bool:
    """Jinja-Global (seit 1.0.103): der Modul-Zustand, je Anfrage frisch -- ein Admin schaltet
    ein Modul in den Einstellungen um, ohne den Server neu zu starten. Verwendung z. B. in
    _sidebar.html: {% if is_module_enabled('aufgabenmanagement') %}. Ohne Zeile oder bei einem
    Lesefehler aktiv (Opt-out-Default, app/modules.py)."""
    return _seitendaten(context).modul_aktiv(module_key)


templates.env.globals["is_module_enabled"] = _is_module_enabled


@pass_context
def _sidebar_logo_url(context=None) -> str | None:
    """Jinja-Global: die URL des Logos, das _sidebar.html oben links statt des Schriftzugs
    "DACHKONZEPTE" zeigen soll, oder None, wenn keins hinterlegt ist (dann der Schriftzug --
    eine leere Stelle waere schlechter als Text). Welches Logo, entscheidet
    company_logo.py::sidebar_logo_filename(); die URL baut app/seitendaten.py::_logo_url()."""
    return _seitendaten(context).logo_url


@pass_context
def _sidebar_logo_height_px(context=None) -> int:
    """Jinja-Global (seit 1.3.39): die eingestellte Anzeigehoehe des Sidebar-Logos in Pixeln
    (Einstellungen -> Erscheinungsbild). Wird nur ausgewertet, wenn sidebar_logo_url() bereits
    eine URL liefert -- ohne Logo bleibt es beim Schriftzug, dessen Groesse ueber CSS laeuft."""
    return _seitendaten(context).logo_hoehe


templates.env.globals["sidebar_logo_url"] = _sidebar_logo_url
templates.env.globals["sidebar_logo_height_px"] = _sidebar_logo_height_px


@pass_context
def _account_display(context, current_user) -> dict:
    """Jinja-Global (seit 1.3.45): voller Name + Initialen fuer den Kontoknopf der Topbar
    (_topbar.html) -- current_user ist request.state.erp_user (None, falls nicht angemeldet),
    von der aufrufenden Vorlage bereits als current_user gesetzt (Muster _sidebar.html). Woher
    der Name kommt, entscheidet auth.py::resolve_account_display(). Gilt ein anderer Benutzer als
    der der Seitendaten (nur in Tests denkbar), laedt es fuer ihn mit eigener Sitzung."""
    if current_user is None:
        return seitendaten.konto_rueckfall(None)
    daten = _seitendaten(context)
    if daten.konto is not None and daten.konto_von == getattr(current_user, "id", None):
        return daten.konto
    return seitendaten.laden_mit_eigener_sitzung(current_user).konto or seitendaten.konto_rueckfall(current_user)


templates.env.globals["account_display"] = _account_display


def _can(current_user, *roles: str) -> bool:
    """Jinja-Global (seit "Rechtekonzept", siehe CLAUDE.md): DIE eine Stelle für Rollenprüfung
    in Vorlagen -- kein current_user.role-Vergleich soll je an zwei Stellen leicht
    unterschiedlich geschrieben werden, exakt das Muster, das bei
    build_din5008_header_block()s Vorgängern (drei divergierende Varianten, siehe CLAUDE.md
    "Kopfbereich") bereits einmal zum Problem wurde. Verwendung:
    {% if can(current_user, 'admin', 'buero_finanzen', 'buero_auftrag') %}...{% endif %}. current_user ist
    request.state.erp_user (None, falls nicht angemeldet) -- wie bei account_display() von der
    aufrufenden Vorlage bereits als current_user gesetzt, kein DB-Zugriff nötig, deshalb auch
    keine try/except-Absicherung wie bei den DB-gestützten Globals oben. Delegiert seit der
    Aufgaben-Sichtbarkeitsänderung an has_role() (app/permissions.py) -- dieselbe eine Quelle,
    die auch require_role() und list_tasks_for_user() (app/tasks.py) nutzen."""
    return has_role(current_user, *roles)


templates.env.globals["can"] = _can


# Seit "Rechtekonzept" (Seiten-Klassifizierung, siehe CLAUDE.md): dieselbe Standardverweigerung
# wie bei /api/-Endpunkten -- eine Seite ohne einen dieser beiden Depends() ist admin-only,
# nicht "für jeden Angemeldeten offen" (tests/test_v260_role_audit.py::
# test_all_page_routes_have_an_explicit_role_check() erzwingt das). _any_role_dep ist die
# Ausnahme für die sechs Seiten, die ein Monteur tatsächlich braucht (/account, /mobil,
# /mobil/stundenzettel (seit 1.9.59 Weiterleitung auf /mobil/zeiten), /mobil/objekt/{property_id}, /time-tracking,
# /orders/{id}/service-reports -- seit "Dateiablage je Objekt" sechs, vorher fünf seit 1.3.61,
# vorher vier; /mobil hieß bis 1.3.60 /vor-ort) -- jede andere Seite ist Büro/Admin, exakt gespiegelt an der
# API-Klassifizierung der jeweiligen Fachdomäne (siehe dort). Ein 403 aus diesen Dependencies
# wird von app/main.py's Exception-Handler zu access_denied.html statt einer rohen JSON-Antwort.
#
# Sonderfall "/" (seit 1.3.61, Punkt 2 "Startseite für Monteure", siehe CLAUDE.md): trägt seither
# ebenfalls _any_role_dep statt _role_dep, zeigt einem Monteur aber NIE das Dashboard -- die Route
# selbst leitet ihn sofort auf default_home_page_for_role() weiter (siehe dashboard_page() unten).
# Das ist bewusst kein drittes Verhalten neben "gesperrt"/"offen", sondern dieselbe Weiche wie
# login_page()/der 403-Exception-Handler: die Rolle entscheidet das Ziel, nicht der aufgerufene Weg.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
_any_role_dep = Depends(require_min_role(ROLE_FIELD))
# Betriebskosten-Übersicht ist Teil der Finanzen-Achse (Rechtekonzept Etappe 2, 1.4.8) -- ein
# buero_auftrag-Konto darf diese Seite an keiner Stelle öffnen, nicht nur die API dahinter.
_finanzen_role_dep = Depends(require_min_role(ROLE_OFFICE_FINANZEN))


# Seit 1.8.130 ohne Ersteinrichtungs-Ausnahme (bis dahin öffnete sich /users ohne Konto für jeden, Gegenstück zu POST /api/users).
# Seit 1.8.134 nur Administratoren, wie Liste (GET /api/users) und Anlegen (POST /api/users): das Büro sah bis dahin die Fehlermeldung der
# Liste und trotzdem das Formular „Benutzer hinzufügen“ -- jetzt die Sperrseite.
_users_page_dep = Depends(require_admin("Die Benutzerverwaltung ist nur für Administratoren verfügbar."))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Seit 1.3.47: zeigt die Anmeldemaske nicht noch einmal, wenn schon jemand angemeldet ist
    (vorher: die Maske erschien unverändert erneut, unabhängig vom Anmeldestatus). Seit 1.3.48
    (echter Fund, siehe CLAUDE.md): die Weiterleitung ignorierte next bisher vollständig und
    ging immer aufs Dashboard -- jetzt landet eine bereits vollständig angemeldete Person
    (zweiter Faktor bestätigt, falls nötig) auf next, wenn vorhanden, sonst aufs Dashboard. Ein
    Administrator mit noch unbestätigtem zweitem Faktor geht weiterhin direkt nach "Mein
    Konto" (dort ist ohnehin nichts anderes nutzbar) -- next wird dabei als Query-Parameter
    mitgegeben, damit account.html nach der Bestätigung selbst noch weiß, wohin es
    anschließend gehen soll (siehe dort).

    Seit 1.8.98 prüft next app/weiterleitung.py::sicheres_ziel() (vorher _safe_next_target() hier, ohne Rückstrich, Tab und
    kodierte Varianten): nur ein lokaler Pfad, sonst die Startseite der Rolle."""
    current_user = getattr(request.state, "erp_user", None)
    if current_user is not None:
        otp_ok = getattr(request.state, "otp_ok", True)
        wert = request.query_params.get("next")
        if current_user.role == "admin" and not otp_ok:
            url = f"/account?next={quote(wert, safe='')}" if ist_lokal(wert) else "/account"
            return RedirectResponse(url=url, status_code=302)
        return RedirectResponse(url=sicheres_ziel(wert, default_home_page_for_role(current_user.role)), status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={})


# Seit 1.8.120: wann eine Seitenroute umleitet, statt eine Vorlage zu zeichnen -- dann lädt die Anmeldeschranke keine Seitendaten
# (app/seitendaten.py::wird_gezeichnet(); tests/test_v425_seitendaten_nur_fuer_seiten.py prüft jede Route je Rolle).
login_page.dk_ohne_seite = lambda user, request: user is not None


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request, _role: AppUser = _any_role_dep):
    return templates.TemplateResponse(request=request, name="account.html", context={})


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, _role: AppUser = _users_page_dep):
    return templates.TemplateResponse(request=request, name="users.html", context={})


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="history.html", context={})


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, _role: AppUser = _any_role_dep):
    """Seit 1.3.61 (Punkt 2 "Startseite für Monteure", siehe CLAUDE.md "Zeiterfassung für
    Monteure"): ein Monteur landet nach dem Anmelden direkt auf /mobil, nicht auf einer Seite
    ohne Zugriffsrechte -- die Weiche hängt an der Rolle (default_home_page_for_role()), nicht
    am Weg, deckt also auch den Fall ab, dass ein Monteur "/" von Hand aufruft. Büro/Admin
    sehen unverändert das Dashboard."""
    if _role.role == ROLE_FIELD:
        return RedirectResponse(url=default_home_page_for_role(_role.role), status_code=302)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})


dashboard_page.dk_ohne_seite = lambda user, request: user is not None and user.role == ROLE_FIELD  # seit 1.8.120, siehe login_page


@router.get("/leistungskatalog", response_class=HTMLResponse)
def service_catalog_page(request: Request, _role: AppUser = _role_dep):
    # seit 1.9.21 (Stufe 2, Runde 8) der Pfad Stammdaten / Leistungskataloge fest im Seitenkopf (bis dahin „zurueck“ aus
    # zurueck_stammdaten("catalogs"))
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="tasks.html", context={})


@router.get("/mobil", response_class=HTMLResponse)
def field_view_page(request: Request, _role: AppUser = _any_role_dep):
    """Monteursansicht (seit 1.3.0, bis 1.3.60 unter /vor-ort -- reine Umbenennung, siehe
    CLAUDE.md "Monteursansicht: Umbenennung zu /mobil", keine Verhaltensänderung) -- eigene,
    schlanke Seite statt der vollen Sidebar (siehe _mobile_header.html). Rendert nur das
    statische Gerüst (Projektkonvention, siehe test_v218_template_rendering.py) -- die
    Feierabend-Prüfung sitzt bewusst NUR in GET /api/field-view/today (einzige Quelle der
    Wahrheit statt zweier Prüfstellen), dessen 401 das Frontend (mobil.html) zu /login
    weiterleitet. Ein serverseitiger Redirect hier hätte denselben Effekt gehabt, wäre aber
    zusätzlich wanduhrzeit-abhängig und damit gegen den generischen Seiten-Rendertest geflackert. Seit 1.8.43 mit
    dem Text des Hinweises "Offene Bedenken" (app/concern_notices.py, eine Quelle für Seite und Auftrag)."""
    return templates.TemplateResponse(request=request, name="mobil.html",
                                      context={"open_concerns_text": OPEN_CONCERNS_TEXT})


@router.get("/mobil/offen", response_class=HTMLResponse)
def field_open_page(request: Request, _role: AppUser = _any_role_dep):
    """„Heute / Offen“ (seit 1.9.49, Stufe 4, R2 Nachrunde): offene Berichte, Mängel zur Beseitigung, offene Checklisten und
    Wartungen an meinen Objekten -- bis 1.9.48 unter „Heute“ (/mobil). Im Monteursrahmen für jede Rolle wie das Objekt; rendert nur
    das Gerüst, die Daten kommen je Abschnitt aus den Schnittstellen der Monteursansicht."""
    return templates.TemplateResponse(request=request, name="mobil_offen.html", context={})


@router.get("/mobil/zeiten", response_class=HTMLResponse)
def field_times_page(request: Request, _role: AppUser = _any_role_dep):
    """„Meine Zeiten“ (seit 1.9.59, Stufe 4, R3): Kacheln, Buchungen des Monats, Nachtragen und Ändern nach der Tagesregel,
    Abwesenheit, Stundenzettel als PDF -- ersetzt die Zeiterfassung der Monteurin (/time-tracking) und den Stundenzettel
    (/mobil/stundenzettel), beide leiten hierher. Im Monteursrahmen für jede Rolle wie „Heute / Offen“; rendert nur das Gerüst, die
    Daten kommen aus GET /api/field-view/meine-zeiten (immer die eigenen)."""
    return templates.TemplateResponse(request=request, name="mobil_zeiten.html", context={})


@router.get("/mobil/stundenzettel", response_class=HTMLResponse)
def field_timesheet_page(request: Request, _role: AppUser = _any_role_dep):
    """Frühere Adresse des Stundenzettels (1.3.61–1.9.58, field_timesheet.html) -- seit 1.9.59 steht er auf „Meine Zeiten“ (Karte
    „Monat“: Monat, Summe, PDF); ein Lesezeichen landet dort."""
    return RedirectResponse(url="/mobil/zeiten", status_code=302)


field_timesheet_page.dk_ohne_seite = lambda user, request: True  # seit 1.9.59, siehe login_page


@router.get("/mobil/objekt/{property_id}", response_class=HTMLResponse)
def field_property_page(request: Request, property_id: int, _role: AppUser = _any_role_dep):
    """Mobile Objektansicht (seit "Dateiablage je Objekt", siehe CLAUDE.md) -- in dieser Runde
    noch ohne Suche erreichbar, nur über eine bekannte Objekt-ID (die Suche als Einstieg folgt
    als eigener, späterer Schritt). Rendert nur das statische Gerüst, alle Daten kommen per
    fetch() gegen die eigenständig gesicherten /api/field-view/properties/{property_id}/...-
    Endpunkte (app/routers/field_view.py) -- dort, nicht hier, sitzt die inhaltliche Sperre."""
    return templates.TemplateResponse(request=request, name="mobil_objekt.html", context={"property_id": property_id})


@router.get("/maintenance-contracts", response_class=HTMLResponse)
def maintenance_contracts_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="maintenance_contracts.html", context={})


@router.get("/maintenance-contracts/{contract_id}", response_class=HTMLResponse)
def maintenance_contract_page(request: Request, contract_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(
        request=request, name="maintenance_contract.html", context={"contract_id": contract_id}
    )


@router.get("/betriebskosten", response_class=HTMLResponse)
def recurring_costs_page(request: Request, _role: AppUser = _finanzen_role_dep):
    """Betriebskosten-Übersicht (seit 1.5.0) -- buero_finanzen-only (siehe _finanzen_role_dep
    oben), kein Modul-Check auf der Seitenroute selbst (etablierte Konvention, siehe
    maintenance_contracts_page()), der API-Endpunkt dahinter prüft is_module_enabled()
    unabhängig davon."""
    return templates.TemplateResponse(request=request, name="recurring_costs.html", context={})


@router.get("/eingangsrechnungen", response_class=HTMLResponse)
def incoming_invoices_page(request: Request, _role: AppUser = _finanzen_role_dep):
    """Eingangsrechnungen (Buchhaltung Stufe 1) -- buero_finanzen-only (siehe
    _finanzen_role_dep oben, dieselbe Finanzen-Achse wie Betriebskosten/Kalkulationsgrundlagen),
    kein Modul-Check auf der Seitenroute selbst (etablierte Konvention, siehe
    recurring_costs_page()), der API-Endpunkt dahinter prüft is_module_enabled() unabhängig
    davon."""
    return templates.TemplateResponse(request=request, name="incoming_invoices.html", context={})


@router.get("/kalender", response_class=HTMLResponse)
def calendar_page(request: Request, _role: AppUser = _role_dep):
    """Kalender (Büro-Termine, seit 1.7.0) -- buero_auftrag/buero_finanzen/admin (_role_dep
    oben, dieselbe Schwelle wie Projekte/Angebote/Aufträge), GETRENNT von /planning (Plantafel,
    bleibt für Einsatz-/Feldplanung). Kein Modul-Check auf der Seitenroute selbst (etablierte
    Konvention, siehe recurring_costs_page()), der API-Endpunkt dahinter (app/routers/
    calendar_events.py) prüft is_module_enabled() unabhängig davon."""
    return templates.TemplateResponse(request=request, name="calendar.html", context={})


@router.get("/betriebsmittel/{asset_id}", response_class=HTMLResponse)
def operational_asset_page(request: Request, asset_id: int, _role: AppUser = _any_role_dep):
    """Seit Betriebsmittelverwaltung Stufe 2 (siehe CLAUDE.md) rollenbewusst wie
    time_tracking_page(): dieselbe URL (Ziel des QR-Codes auf dem Etikett, siehe
    routers/operational_assets.py) rendert für `field` die reduzierte
    operational_asset_field.html statt der vollen, Büro-getragenen operational_asset.html --
    die Weiche hängt an der Rolle, nicht am Weg (QR-Code oder von Hand eingetippte URL). Kein
    Modul-Check auf der Seitenroute selbst -- etablierte Konvention (siehe tasks_page()/
    maintenance_contract_page()), der API-Endpunkt dahinter prüft is_module_enabled()
    unabhängig davon."""
    template_name = "operational_asset_field.html" if _role.role == ROLE_FIELD else "operational_asset.html"
    return templates.TemplateResponse(request=request, name=template_name, context={"asset_id": asset_id})


@router.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="projects.html", context={})


@router.get("/planning", response_class=HTMLResponse)
def planning_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="planning.html", context={})


@router.get("/time-tracking", response_class=HTMLResponse)
def time_tracking_page(request: Request, _role: AppUser = _any_role_dep):
    """Seit 1.3.60 rollenbewusst statt einer festen Vorlage (siehe CLAUDE.md „Zeiterfassung für
    Monteure"): dieselbe URL rendert für `field` die reduzierte time_tracking_field.html
    (Muster _mobile_header.html/mobil.html) statt der vollen, Sidebar-getragenen
    time_tracking.html -- bewusst KEINE zweite Route (z. B. /mobil/zeit), damit die Weiche an
    der Rolle hängt, nicht am Weg: _sidebar.html/_mobile_header.html/service_reports.html
    verlinken alle unverändert auf /time-tracking, ein Büro-Konto, das testweise als `field`
    unterwegs ist (oder umgekehrt), sieht bei JEDEM Aufruf -- Sidebar-Link, altes Lesezeichen,
    eingetippte Adresse, ?order_id=-Link von service_reports.html -- exakt das, was die aktuelle
    Sitzungsrolle vorsieht. `_role` ist das AppUser-Objekt aus require_role() (siehe
    app/permissions.py), keine zweite Anfrage an request.state nötig.

    Seit 1.9.59 (Stufe 4, R3): für `field` eine Weiterleitung auf „Meine Zeiten“ (/mobil/zeiten) statt time_tracking_field.html --
    Starten und Stoppen stehen auf „Heute“, alles andere auf „Meine Zeiten“; ein ?order_id= (Link „Zeiterfassung (Auftrag)“ im
    Einsatzbericht) geht als Zahl mit und wählt den Auftrag im Dialog „Zeit nachtragen“ vor."""
    if _role.role == ROLE_FIELD:
        auftrag = request.query_params.get("order_id") or ""
        return RedirectResponse(url=f"/mobil/zeiten?order_id={int(auftrag)}" if auftrag.isdigit() else "/mobil/zeiten", status_code=302)
    # seit 1.9.89 (Stufe 4, R5a): wer nur liest (Büro – Auftrag), bekommt die Seite ohne Buchen und Ändern
    return templates.TemplateResponse(request=request, name="time_tracking.html",
                                      context={"zeit_buchen": darf_zeit_buchen(_role), "zeiten_nur_lesen": ZEITEN_NUR_LESEN})


time_tracking_page.dk_ohne_seite = lambda user, request: user is not None and user.role == ROLE_FIELD  # seit 1.9.59, siehe login_page


@router.get("/zeiten", response_class=HTMLResponse)
def zeiten_page(request: Request, _role: AppUser = _any_role_dep):
    """Seit 1.9.96 (Stufe 4, R5b): die Büroseite „Zeiten“ (Prüfen, Buchungen) -- die Daten aus app/zeiten.py. Was das Konto darf
    (app/permissions.py), entscheidet hier, was die Seite zeigt: „+ Buchung“ nur, wer bucht; die Knöpfe je Zeile nach den Angaben des Servers.
    Die Monteurin hat „Meine Zeiten“ (/mobil/zeiten)."""
    if _role.role == ROLE_FIELD:
        return RedirectResponse(url="/mobil/zeiten", status_code=302)
    return templates.TemplateResponse(request=request, name="zeiten.html",
                                      context={"zeit_buchen": darf_zeit_buchen(_role), "zeit_fuer_andere": darf_zeit_fuer_andere_buchen(_role),
                                               "lohndaten": darf_lohndaten(_role), "admin": _role.role == "admin"})


zeiten_page.dk_ohne_seite = lambda user, request: user is not None and user.role == ROLE_FIELD  # die Monteurin: Weiterleitung


@router.get("/time-backoffice", response_class=HTMLResponse)
def time_backoffice_page(request: Request, _role: AppUser = _role_dep):
    # seit 1.9.89 (Stufe 4, R5a): was das Konto an Zeiten und Lohndaten darf (app/permissions.py) -- die Seite bietet nur das an
    return templates.TemplateResponse(request=request, name="time_backoffice.html",
                                      context={"zeit_buchen": darf_zeit_buchen(_role), "zeit_fuer_andere": darf_zeit_fuer_andere_buchen(_role),
                                               "lohndaten": darf_lohndaten(_role), "zeiten_nur_lesen": ZEITEN_NUR_LESEN})


# Seit 1.8.135: Zurück-Links der Formularseiten mit echtem Ziel und Namen (bis dahin history.back(), nach direktem Aufruf ins Leere, und
# Namen wie „← Projekte & Belege“). Werte aus der Adresse nur als Zahl -- sonst das allgemeine Ziel.
def _zahl(wert: str | None) -> int | None:
    return int(wert) if wert and wert.isdigit() else None


# Bereich der Stammdaten-Liste (Hash von /master-data) und sein Name je Datentyp des Formulars
STAMMDATEN_BEREICHE = {
    "customers": ("customers", "Kunden"), "properties": ("properties", "Objekte"), "employees": ("employees", "Mitarbeiter"),
    "teams": ("teams", "Kolonnen / Teams"), "assets": ("assets", "Betriebsmittel"),
    "resources": ("assets", "Fuhrpark & Maschinen"),  # nur bei abgeschaltetem Modul Betriebsmittel, Bereich heißt dann so
    # (seit 1.8.147 auch das Ziel des Formulars nach dem Speichern: "listenbereich" -- bis dahin "#resources", den Bereich gibt es nicht)
    "suppliers": ("suppliers", "Lieferanten"), "contacts": ("contacts", "Adressbuch"), "catalogs": ("catalogs", "Leistungskataloge"),
    "materials": ("materials", "Materialkataloge"), "materialGroups": ("materialGroups", "Materialkataloge"),
}


def zurueck_stammdaten(data_type: str, record_id: int | None = None, projekt: int | None = None) -> dict:
    if data_type == "contacts" and projekt:
        return {"href": f"/projects/{projekt}#sec-participants", "text": "Projektmappe"}
    if data_type == "properties" and record_id:
        return {"href": f"/properties/{record_id}", "text": "Objekt"}
    bereich, name = STAMMDATEN_BEREICHE[data_type]
    return {"href": f"/master-data#{bereich}", "text": f"Stammdaten: {name}"}


def pfad_stammdaten(data_type: str, record_id: int | None = None, projekt: int | None = None) -> list[dict]:
    """Seit 1.9.22 (Stufe 2, Runde 8): die Glieder des Pfads im Stammdaten-Formular vor der Seite selbst -- der Bereich der Leiste (aus der
    Projektmappe kommend: Projekte), dann der bisherige Rückweg (dasselbe Ziel wie zurueck_stammdaten(), das „Abbrechen“ nimmt)."""
    if data_type == "contacts" and projekt:
        return [{"href": "/projects", "text": "Projekte"}, {"href": f"/projects/{projekt}#sec-participants", "text": "Projektmappe"}]
    if data_type == "properties" and record_id:
        return [{"href": "/master-data", "text": "Stammdaten"}, {"href": f"/properties/{record_id}", "text": "Objekt"}]
    bereich, name = STAMMDATEN_BEREICHE[data_type]
    return [{"href": "/master-data", "text": "Stammdaten"}, {"href": f"/master-data#{bereich}", "text": name}]


@router.get("/projects/new", response_class=HTMLResponse)
def project_create_page(request: Request, customer_id: str | None = None, _role: AppUser = _role_dep):
    kunde = _zahl(customer_id)
    zurueck = {"href": f"/customers/{kunde}", "text": "Kundenakte"} if kunde else {"href": "/projects", "text": "Projekte"}
    return templates.TemplateResponse(request=request, name="project_form.html", context={"zurueck": zurueck})


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_folder_page(request: Request, project_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="project_folder.html", context={"project_id": project_id})


@router.get("/quotes/new", response_class=HTMLResponse)
def quote_create_page(request: Request, project_id: str | None = None, _role: AppUser = _role_dep):
    projekt = _zahl(project_id)
    zurueck = {"href": f"/projects/{projekt}", "text": "Projektmappe"} if projekt else {"href": "/projects", "text": "Projekte"}
    return templates.TemplateResponse(request=request, name="quote_form.html", context={"zurueck": zurueck})


@router.get("/services/new", response_class=HTMLResponse)
def service_create_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="service_form.html",
                                      context={"service_id": None, "zurueck": {"href": "/leistungskatalog", "text": "Leistungskatalog"}})


@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
def service_edit_page(request: Request, service_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="service_form.html",
                                      context={"service_id": service_id, "zurueck": {"href": "/leistungskatalog", "text": "Leistungskatalog"}})


@router.get("/master-data", response_class=HTMLResponse)
def master_data_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="master_data.html", context={})


def _require_finanzen_for_employees(data_type: str, role: AppUser) -> None:
    """Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8, siehe CLAUDE.md): Mitarbeiter anlegen/
    bearbeiten läuft über EIN kombiniertes Formular mit den Vergütungsfeldern direkt darin
    (master_data_form.html::employeeForm()) -- die Seite selbst muss deshalb buero_finanzen-only
    sein, nicht nur die API dahinter, sonst würde buero_auftrag ein Formular sehen, dessen
    Speichern serverseitig ohnehin abgelehnt wird. Jeder andere Stammdatenbereich bleibt bei
    buero_auftrag (_role_dep)."""
    if data_type == "employees" and not has_min_role(role, ROLE_OFFICE_FINANZEN):
        raise HTTPException(status_code=403, detail="Mitarbeiter anlegen/bearbeiten ist nur für Büro – Finanzen und Administratoren verfügbar.")


@router.get("/master-data/{data_type}/new", response_class=HTMLResponse)
def master_data_create_page(request: Request, data_type: str, projekt: str | None = None, _role: AppUser = _role_dep):
    if data_type not in {"customers", "properties", "employees", "suppliers", "contacts", "resources", "teams", "catalogs", "materials", "materialGroups", "assets"}:
        raise HTTPException(status_code=404, detail="Stammdatenbereich nicht gefunden.")
    _require_finanzen_for_employees(data_type, _role)
    return templates.TemplateResponse(request=request, name="master_data_form.html",
                                      context={"data_type": data_type, "zurueck": zurueck_stammdaten(data_type, projekt=_zahl(projekt)),
                                               "pfad": pfad_stammdaten(data_type, projekt=_zahl(projekt)),
                                               "listenbereich": STAMMDATEN_BEREICHE[data_type][0]})


@router.get("/master-data/{data_type}/{record_id}/edit", response_class=HTMLResponse)
def master_data_edit_page(request: Request, data_type: str, record_id: int, _role: AppUser = _role_dep):
    if data_type not in {"properties", "employees", "suppliers", "contacts", "resources", "teams", "materials"}:
        raise HTTPException(status_code=404, detail="Stammdatenbereich nicht gefunden.")
    _require_finanzen_for_employees(data_type, _role)
    return templates.TemplateResponse(
        request=request, name="master_data_form.html",
        context={"data_type": data_type, "record_id": record_id, "zurueck": zurueck_stammdaten(data_type, record_id=record_id),
                 "pfad": pfad_stammdaten(data_type, record_id=record_id), "listenbereich": STAMMDATEN_BEREICHE[data_type][0]},
    )


@router.get("/quotes/{quote_id}/edit", response_class=HTMLResponse)
def quote_editor_page(request: Request, quote_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="quote_editor.html", context={"quote_id": quote_id})


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_page(request: Request, order_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="order.html", context={"order_id": order_id})


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def invoice_page(request: Request, invoice_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="invoice_detail.html", context={"invoice_id": invoice_id})


@router.get("/finanzen", response_class=HTMLResponse)
def finanzen_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="finanzen.html", context={})


@router.get("/suche", response_class=HTMLResponse)
def office_search_page(request: Request, _role: AppUser = _role_dep):
    """Ergebnisseite der Büro-Suche (Etappe 2, seit 1.3.67, siehe CLAUDE.md "Büro-Suche") --
    trägt bewusst dieselbe _role_dep-Absicherung wie jede andere Büro-Seite, NICHT nur der
    API-Endpunkt dahinter (GET /api/search): ein Monteur, der /suche über die Adresse aufruft,
    bekommt 403 -> access_denied.html, bevor die Seite überhaupt rendert, unabhängig davon, was
    die API täte. Die Seite selbst rendert nur das Gerüst -- q/types kommen als Query-Parameter
    und werden client-seitig aus location.search gelesen (Muster: jede andere Seite in diesem
    Projekt lädt ihre Daten per fetch() nach)."""
    return templates.TemplateResponse(request=request, name="search_results.html", context={})


@router.get("/mahnwesen", response_class=HTMLResponse)
def mahnwesen_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="mahnwesen.html", context={})


@router.get("/versandprotokoll", response_class=HTMLResponse)
def email_dispatches_page(request: Request, _role: AppUser = _role_dep):
    """Versandprotokoll mit Ablage (seit 1.8.17) -- buero_auftrag aufwärts, wie die API dahinter."""
    return templates.TemplateResponse(request=request, name="email_dispatches.html", context={})


@router.get("/changelog", response_class=HTMLResponse)
def changelog_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="changelog.html", context={})


@router.get("/orders/{order_id}/work-preparation", response_class=HTMLResponse)
def work_preparation_page(request: Request, order_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="work_preparation.html", context={"order_id": order_id})


def _bericht_aus_adresse(request: Request) -> int | None:
    """?report=<id> auf der Auftragsseite (frühere Eingänge, Lesezeichen) -- nur eine Zahl, sonst None."""
    wert = request.query_params.get("report") or ""
    return int(wert) if wert.isdigit() else None


@router.get("/orders/{order_id}/service-reports", response_class=HTMLResponse)
def service_reports_page(request: Request, order_id: int, _role: AppUser = _any_role_dep):
    """Die Seite des Auftrags: Objekt & Zugang, Bedenken, die Berichte mit „+ Bericht“, frühere Berichte, Zeiten. Seit 1.9.67 (Stufe 4,
    R4, Entscheidung D) steht der Bericht selbst auf /service-reports/{id}; ?report=<id> leitet dorthin."""
    bericht = _bericht_aus_adresse(request)
    if bericht is not None:
        return RedirectResponse(url=f"/service-reports/{bericht}", status_code=302)
    return templates.TemplateResponse(request=request, name="service_reports.html",
                                      context={"order_id": order_id, "zeit_fuer_andere_buchen": darf_zeit_fuer_andere_buchen(_role),
                                               "zeit_nur_mit_von_bis": zeit_nur_mit_von_bis(_role),  # seit 1.9.60
                                               "zeit_buchen": darf_zeit_buchen(_role), "zeiten_nur_lesen": ZEITEN_NUR_LESEN})  # seit 1.9.89


service_reports_page.dk_ohne_seite = lambda user, request: _bericht_aus_adresse(request) is not None  # seit 1.9.67, siehe login_page


@router.get("/service-reports/{report_id}", response_class=HTMLResponse)
def service_report_page(request: Request, report_id: int, _role: AppUser = _any_role_dep):
    """Seit 1.9.67 (Stufe 4, R4): ein Einsatzbericht in fünf Schritten (service_report.html) -- die Daten lädt die Seite über
    GET /api/service-reports/{id}, der prüft, ob die Monteurin den Bericht öffnen darf (nur ihren eigenen)."""
    return templates.TemplateResponse(request=request, name="service_report.html", context={"report_id": report_id})


@router.get("/roof-areas/{roof_area_id}", response_class=HTMLResponse)
def roof_area_page(request: Request, roof_area_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="roof_area.html", context={"roof_area_id": roof_area_id})


@router.get("/properties/{property_id}", response_class=HTMLResponse)
def property_page(request: Request, property_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="property.html", context={"property_id": property_id})


@router.get("/findings", response_class=HTMLResponse)
def findings_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="findings.html", context={})


@router.get("/inspection-templates", response_class=HTMLResponse)
def inspection_templates_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="inspection_templates.html", context={})


@router.get("/inspection-templates/{template_id}", response_class=HTMLResponse)
def inspection_template_page(request: Request, template_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="inspection_template.html", context={"template_id": template_id})


@router.get("/checklisten/vorlagen", response_class=HTMLResponse)
def checklist_templates_page(request: Request, _role: AppUser = _role_dep):
    """Checklisten-Vorlagen (seit 1.8.0, Modul "checklisten") -- Liste zuerst, Bearbeiten auf
    eigener Seite (Regel 10). buero_auftrag aufwärts (_role_dep). Kein Modul-Check auf der
    Seitenroute selbst (etablierte Konvention, siehe calendar_page()), die API dahinter prüft
    is_module_enabled() unabhängig davon."""
    return templates.TemplateResponse(request=request, name="checklist_templates.html", context={})


@router.get("/checklisten/vorlagen/{template_id}", response_class=HTMLResponse)
def checklist_template_page(request: Request, template_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="checklist_template.html", context={"template_id": template_id})


@router.get("/checklisten", response_class=HTMLResponse)
def checklists_page(request: Request, _role: AppUser = _role_dep):
    """Büro-Übersicht aller Checklisten (seit 1.8.1) plus Starten im Kontext "Betrieb" --
    buero_auftrag aufwärts. Monteure erreichen Checklisten nur über /mobil und die Kontextseiten."""
    return templates.TemplateResponse(request=request, name="checklists.html", context={})


@router.get("/checklisten/{checklist_id:int}", response_class=HTMLResponse)
def checklist_page(request: Request, checklist_id: int, _role: AppUser = _any_role_dep):
    """Eine Checkliste ausfüllen/ansehen (seit 1.8.1) -- für jede Rolle dieselbe URL, die Vorlage
    bindet für `field` die mobile Kopfzeile statt der Sidebar ein (Weiche an der Rolle, Muster
    time_tracking_page()). Der `:int`-Konverter hält /checklisten/vorlagen frei. Was sichtbar
    ist, entscheidet GET /api/checklists/{id} (403 für fremde, nicht lesbare Checklisten)."""
    return templates.TemplateResponse(request=request, name="checklist.html", context={
        "checklist_id": checklist_id, "is_field": _role.role == ROLE_FIELD,
    })


@router.get("/checklisten/auftrag/{order_id:int}", response_class=HTMLResponse)
def checklist_order_page(request: Request, order_id: int, zweck: str | None = None, _role: AppUser = _any_role_dep):
    """Checklisten eines Auftrags (seit 1.8.1), Einstieg für Monteure aus /mobil. Der
    Auftragszugriff wird von der API geprüft (require_field_order_access()), die Seite rendert
    nur das Gerüst. ?zweck= (seit 1.8.38, Link einer Regel-Aufgabe) hebt das Anlegen einer
    Checkliste dieses Zwecks hervor; ein unbekannter Zweck wird ignoriert."""
    purpose = PURPOSES.get(zweck or "")
    if purpose is None or purpose.key == DEFAULT_PURPOSE:
        purpose = None
    return templates.TemplateResponse(request=request, name="checklist_order.html", context={
        "order_id": order_id, "is_field": _role.role == ROLE_FIELD,
        "zweck": purpose.key if purpose else None, "zweck_label": purpose.label if purpose else None,
    })


@router.get("/inquiries", response_class=HTMLResponse)
def inquiries_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="inquiries.html", context={})


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_record_page(request: Request, customer_id: int, _role: AppUser = _role_dep):
    return templates.TemplateResponse(
        request=request, name="customer.html", context={"customer_id": customer_id}
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, _role: AppUser = _role_dep):
    return templates.TemplateResponse(request=request, name="settings.html", context={})


@router.get("/address-import", response_class=HTMLResponse)
def address_import_page(
    request: Request, _admin=Depends(require_admin("Der Adressimport ist nur für Administratoren verfügbar.")),
):
    return templates.TemplateResponse(request=request, name="address_import.html", context={})


INSTANZ_ENV = "ERP_INSTANZ"  # seit 1.9.85, siehe health()


@router.get("/health")
@router.head("/health", include_in_schema=False)
def health():
    """Ohne Anmeldung (app/anmeldeschranke.py::OEFFENTLICH). Seit 1.8.129 auch HEAD -- eine Überwachung, die nur die Kopfzeilen holt,
    bekam bis dahin 405 (FastAPI ergänzt bei einer GET-Route kein HEAD). Seit 1.8.130 als eigene HEAD-Route ohne Eintrag in der
    Schnittstellenbeschreibung (eine Route mit GET und HEAD ergab dort zweimal dieselbe Operation-ID).

    Seit 1.9.85: eine Klicktest-Instanz nennt ihre Kennung (ERP_INSTANZ, nur mit ERP_ENV=development oder test) -- scripts/cdp_klicktest.py
    prüft damit, dass unter dem Port die eigene Instanz antwortet und kein gleichzeitig gestarteter fremder Server (Port-Wettlauf,
    Befund vom 24.10.2026). Im Betrieb ist die Variable nie gesetzt."""
    antwort = {"status": "ok", "version": APP_VERSION}
    kennung = os.environ.get(INSTANZ_ENV)
    if kennung and os.environ.get("ERP_ENV") in ("development", "test"):
        antwort["instanz"] = kennung
    return antwort
