"""Rechtekonzept: drei Rollen statt zwei -- Ergänzung zu app/deps.py::require_admin() (seit
"Rechtekonzept", siehe CLAUDE.md für die volle Begründung und den Etappenplan).

require_admin() selbst bleibt UNVERÄNDERT und wird an den zwölf Dateien, die es heute schon
nutzen, nicht angefasst -- es deckt sich exakt mit require_role("admin") unten, kein Grund,
etwas zu ändern, das bereits funktioniert (Bestandsschutz, siehe CLAUDE.md).

**Standardverweigerung, nicht Positivliste (das ist der wichtigste Teil dieses Moduls -- siehe
CLAUDE.md "Rechtekonzept" für die volle Begründung, hier nur die Kurzfassung als Code-Kommentar):**
jeder /api/-Endpunkt MUSS eine ausdrückliche Rollenangabe tragen (Depends(require_role(...))
oder Depends(require_admin(...))) -- fehlt sie, ist der Endpunkt NICHT "für jeden Angemeldeten
offen" (das bisherige, real aufgetretene Fehlerbild, siehe /users seit 1.3.28 und die Suche-
Bestandsaufnahme), sondern gilt als admin-only. tests/test_v260_role_audit.py erzwingt das
mechanisch: er geht jede registrierte Route durch und schlägt fehl, wenn eine ohne erkennbare
Rollenprüfung registriert ist -- ein vergessener Depends(...) fällt dadurch beim nächsten
vollständigen Testlauf auf, nicht erst, wenn jemand es zufällig bemerkt.
"""

from fastapi import HTTPException, Request

from .models import AppUser

ROLE_ADMIN = "admin"
ROLE_OFFICE = "office"
ROLE_FIELD = "field"

# Reihenfolge = geringste zu höchste Berechtigung -- u. a. für die Rollenauswahl in users.html
# (dort bewusst als Standardauswahl der am wenigsten privilegierte Wert, siehe CLAUDE.md).
ROLES = (ROLE_FIELD, ROLE_OFFICE, ROLE_ADMIN)

ROLE_LABELS = {
    ROLE_ADMIN: "Administrator",
    ROLE_OFFICE: "Büro",
    ROLE_FIELD: "Monteur",
}


def default_home_page_for_role(role: str | None) -> str:
    """Landing-Seite ohne ein mitgegebenes `next` -- ein Monteur landet auf /mobil (seit 1.3.61,
    bis dahin /vor-ort -- reine Umbenennung, siehe CLAUDE.md "Monteursansicht: Umbenennung zu
    /mobil"; seine einzige freigegebene Desktop-Startseite -- die übrigen für ihn offenen Seiten
    -- /account, /mobil/stundenzettel, /time-tracking, /orders/{id}/service-reports -- sind keine
    sinnvollen Einstiegspunkte ohne Kontext), jede andere Rolle unverändert auf dem Dashboard.
    Genutzt von app/routers/pages.py::login_page() (bereits angemeldeter Aufruf von /login),
    app/routers/pages.py::dashboard_page() (seit 1.3.61: ein Monteur, der / von Hand aufruft,
    wird direkt weitergeleitet statt access_denied.html zu sehen -- CLAUDE.md, dort auch die
    Begründung, warum NUR / diesen Redirect bekommt, keine andere Büro-Seite) UND vom
    403-Handler in app/main.py (Ziel des "Zur Startseite"-Links auf access_denied.html) --
    alle drei kennen die Rolle bereits aus request.state.erp_user."""
    return "/mobil" if role == ROLE_FIELD else "/"

_DEFAULT_MESSAGE = "Für Ihre Rolle nicht verfügbar."


def require_role(*allowed_roles: str, message: str = _DEFAULT_MESSAGE):
    """Fabrik für eine FastAPI-Dependency, die 403 auslöst, wenn die angemeldete Person keine
    der übergebenen Rollen trägt (sonst den AppUser zurückgibt) -- Verallgemeinerung von
    app/deps.py::require_admin() auf drei statt zwei Rollen.

    Verwendung: _role: AppUser = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, message="..."))

    Trägt eine _dk_roles-Markierung auf der zurückgegebenen Funktion, an der
    tests/test_v260_role_audit.py eine tatsächlich vorgenommene Klassifizierung erkennt (nicht
    nur irgendeine beliebige Dependency)."""
    allowed = frozenset(allowed_roles)

    def _dependency(request: Request) -> AppUser:
        user = getattr(request.state, "erp_user", None)
        if user is None or user.role not in allowed:
            raise HTTPException(status_code=403, detail=message)
        return user

    _dependency._dk_roles = allowed
    return _dependency


# Vollständigkeits-Ausnahmen für tests/test_v260_role_audit.py -- bewusst kurz und einzeln
# begründet, nicht als bequemer Sammelplatz für "kommt später dran". Jeder Eintrag hier ist ein
# Endpunkt, der aus einem strukturellen Grund KEINE Depends(require_role(...))/require_admin()-
# Prüfung tragen kann, nicht einer, der nur noch nicht klassifiziert wurde (das listet der Test
# selbst als Fehlschlag auf -- genau die gewollte "Standardverweigerung fällt sofort auf").
ROLE_AUDIT_EXEMPT = frozenset({
    # Anmeldung selbst -- muss vor jeder Rollenprüfung erreichbar sein, sonst könnte sich
    # niemand mehr anmelden.
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/status"),
    # Zwei-Faktor-Ersteinrichtung/-Bestätigung -- muss für einen Administrator erreichbar sein,
    # der den zweiten Faktor DIESER Sitzung noch nicht bestätigt hat (otp_ok=False); eine
    # Rollenprüfung träfe hier dieselbe Person, die sie gerade erst erfüllen will. Bereits über
    # app/main.py::_TWO_FACTOR_SETUP_PATHS eigens offengehalten, kein neuer Fund.
    ("POST", "/api/account/2fa/setup/start"),
    ("POST", "/api/account/2fa/setup/confirm"),
    ("POST", "/api/account/2fa/verify"),
    # Eigenes Passwort ändern -- ausdrücklich für jede angemeldete Person unabhängig von der
    # Rolle gedacht (Monteur/Büro/Admin gleichermaßen), siehe CLAUDE.md "Anmeldesicherheit für
    # den Onlinebetrieb". Kein Positivliste-Versehen, sondern absichtlich rollenlos -- bleibt
    # trotzdem hier und nicht ungeprüft, damit das für jeden erkennbar dokumentiert ist.
    ("POST", "/api/account/change-password"),
    # Heutige Einsätze der Monteursansicht -- prüft stattdessen, ob request.state.erp_user.
    # employee_id gesetzt ist (app/routers/field_view.py), eine feinere, personenbezogene
    # Prüfung als eine reine Rollenzugehörigkeit. Objekt-Filterung, nicht Rollen-Gate.
    ("GET", "/api/field-view/today"),
    # PWA-Icon der Monteursansicht -- liefert nur ein aus dem Firmenlogo abgeleitetes
    # Platzhalterbild, keine Kunden-/Geschäftsdaten; muss vor dem ersten Login (Installation
    # "Zum Startbildschirm hinzufügen") erreichbar sein.
    ("GET", "/api/mobile-icon/{size}.png"),
    # Bootstrap-Fall beim Anlegen des allerersten ERP-Benutzers (app/routers/users.py) -- dort
    # existiert per Definition noch KEIN angemeldeter Benutzer, jede Rollenprüfung würde also
    # immer scheitern. create_app_user() prüft die Admin-Pflicht bereits selbst, aber nur
    # NACHDEM festgestellt wurde, dass das System schon konfiguriert ist (users_exist(db)) --
    # exakt dieselbe, bereits an anderer Stelle etablierte Bootstrap-Ausnahme (siehe
    # app/main.py::_request_requires_login()).
    ("POST", "/api/users"),
})

# Dasselbe Prinzip wie ROLE_AUDIT_EXEMPT, aber für SEITENROUTEN (app/routers/pages.py,
# app/routers/field_view.py) statt /api/-Endpunkte -- siehe tests/test_v260_role_audit.py::
# test_all_page_routes_have_an_explicit_role_check(). Eine Seite ohne Depends(require_role(...))
# gilt als admin-only, exakt dieselbe Standardverweigerung wie bei der API; eine Seite, die ein
# Monteur nicht öffnen darf, muss serverseitig sperren (403 -> access_denied.html), nicht nur im
# Sidebar-Menü ausgeblendet sein (siehe CLAUDE.md "Rechtekonzept" -> "Sichtbarkeit in der
# Oberfläche").
PAGE_AUDIT_EXEMPT = frozenset({
    # Anmeldung selbst -- dieselbe Begründung wie bei den /api/auth/*-Endpunkten oben.
    ("GET", "/login"),
    # Externe Überwachung, bereits vor jeder Anmeldepflicht ungated.
    ("GET", "/health"),
    # PWA-Ressource der Monteursansicht (app/routers/field_view.py) -- wird ohnehin nur von der
    # bereits angemeldeten Seite /mobil aus verlinkt, muss aber vor dem ersten Login
    # ("Zum Startbildschirm hinzufügen") erreichbar bleiben, dieselbe Begründung wie beim
    # gleichnamigen API-Icon-Endpunkt oben.
    ("GET", "/manifest.json"),
    # Bootstrap-Fall beim Anlegen des allerersten ERP-Benutzers (app/routers/pages.py::
    # users_page(), Gegenstück zu POST /api/users oben) -- dort existiert per Definition noch
    # kein angemeldeter Benutzer, jede Depends(require_role(...))-Prüfung würde also immer
    # scheitern. Die Seite prüft die Büro-/Admin-Pflicht deshalb selbst
    # (_require_users_page_access()), aber erst NACHDEM festgestellt wurde, dass das System
    # schon konfiguriert ist -- ohne require_role(...)-Depends trägt sie keine _dk_roles-Markierung
    # und muss deshalb hier einzeln stehen, wie POST /api/users.
    ("GET", "/users"),
})
