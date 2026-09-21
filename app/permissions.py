"""Rechtekonzept: vier Rollen statt zwei -- Ergänzung zu app/deps.py::require_admin() (seit
"Rechtekonzept", siehe CLAUDE.md für die volle Begründung und den Etappenplan).

require_admin() selbst bleibt UNVERÄNDERT und wird an den Dateien, die es heute schon nutzt,
nicht angefasst -- es deckt sich exakt mit require_min_role(ROLE_ADMIN) unten, kein Grund,
etwas zu ändern, das bereits funktioniert (Bestandsschutz, siehe CLAUDE.md).

**Standardverweigerung, nicht Positivliste (das ist der wichtigste Teil dieses Moduls -- siehe
CLAUDE.md "Rechtekonzept" für die volle Begründung, hier nur die Kurzfassung als Code-Kommentar):**
jeder /api/-Endpunkt MUSS eine ausdrückliche Rollenangabe tragen (Depends(require_role(...)),
Depends(require_min_role(...)) oder Depends(require_admin(...))) -- fehlt sie, ist der Endpunkt
NICHT "für jeden Angemeldeten offen" (das bisherige, real aufgetretene Fehlerbild, siehe /users
seit 1.3.28 und die Suche-Bestandsaufnahme), sondern gilt als admin-only. tests/test_v260_role_audit.py
erzwingt das mechanisch: er geht jede registrierte Route durch und schlägt fehl, wenn eine ohne
erkennbare Rollenprüfung registriert ist -- ein vergessener Depends(...) fällt dadurch beim
nächsten vollständigen Testlauf auf, nicht erst, wenn jemand es zufällig bemerkt.

**Vier Rollen statt drei (seit der Aufteilung von "office" -- CLAUDE.md "Rechtekonzept" ->
"Vier Rollen"):** admin bleibt alles inklusive Systemverwaltung. Die ehemals einzelne Rolle
"office" ist in zwei getrennte Rollen aufgeteilt -- buero_finanzen (alles Fachliche/Kaufmännische
PLUS Betriebskosten-Übersicht/Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung/
Mitarbeitervergütung, Schnittstelle zum Steuerberater, keine Systemverwaltung) und buero_auftrag
(der komplette produktive und kaufmännische Betrieb -- Projekte, Angebote mit voller Kalkulation,
Aufträge, Rechnungen, Mahnwesen, Planung, Wartung, Anfragen, Aufgaben, Betriebsmittel-Bestand --
OHNE Betriebskosten-Übersicht/Kalkulationsgrundlagen-Herleitung/Mitarbeitervergütung). field bleibt
unverändert die Monteursrolle.

**Hierarchie statt vier unabhängiger Mengen (ROLE_RANK, require_min_role() unten):** admin ⊇
buero_finanzen ⊇ buero_auftrag ⊇ field -- buero_finanzen kann alles, was buero_auftrag kann, PLUS
mehr; admin kann alles, was buero_finanzen kann, PLUS Systemverwaltung. Praktisch bedeutet das: die
überwältigende Mehrheit der ehemaligen require_role(ROLE_ADMIN, ROLE_OFFICE)-Stellen braucht keine
Einzelentscheidung, sondern genau EINE mechanische Übersetzung auf require_min_role(ROLE_OFFICE_AUFTRAG)
(lässt beide Bürorollen + admin durch, exakt wie vorher "office" + admin) -- nur eine kleine,
bewusst einzeln entschiedene Teilmenge (Kalkulationsgrundlagen, künftige Betriebskosten-Übersicht,
Mitarbeitervergütung) verengt sich auf require_min_role(ROLE_OFFICE_FINANZEN). has_role()/
require_role() bleiben daneben als reine Mengenzugehörigkeits-Prüfung bestehen -- für admin-only
(via require_admin()) und die "für jede Rolle offen"-Fälle (require_role(ROLE_ADMIN,
ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG, ROLE_FIELD), äquivalent zu require_min_role(ROLE_FIELD)).
"""

from fastapi import HTTPException, Request

from .models import AppUser

ROLE_ADMIN = "admin"
ROLE_OFFICE_FINANZEN = "buero_finanzen"
ROLE_OFFICE_AUFTRAG = "buero_auftrag"
ROLE_FIELD = "field"

# Reihenfolge = geringste zu höchste Berechtigung -- u. a. für die Rollenauswahl in users.html
# (dort bewusst als Standardauswahl der am wenigsten privilegierte Wert, siehe CLAUDE.md).
# Deckt sich exakt mit der Rangfolge in ROLE_RANK unten.
ROLES = (ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN)

ROLE_LABELS = {
    ROLE_ADMIN: "Administrator",
    ROLE_OFFICE_FINANZEN: "Büro – Finanzen",
    ROLE_OFFICE_AUFTRAG: "Büro – Auftrag",
    ROLE_FIELD: "Monteur",
}

# Die EINE Rangfolge für die Hierarchie-Prüfung (has_min_role()/require_min_role() unten) --
# admin > buero_finanzen > buero_auftrag > field, jede Stufe umfasst alle darunterliegenden.
# Bewusst ein einfacher int-Rang statt einer Graphstruktur -- die Hierarchie dieses Projekts ist
# eine reine Kette (Total Order), kein Baum/keine unabhängigen Zweige, ein Rang bildet das
# verlustfrei ab.
ROLE_RANK = {
    ROLE_FIELD: 0,
    ROLE_OFFICE_AUFTRAG: 1,
    ROLE_OFFICE_FINANZEN: 2,
    ROLE_ADMIN: 3,
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


def has_role(user: AppUser | None, *roles: str) -> bool:
    """Die EINE Quelle für "hat diese Person eine dieser Rollen" (flache Mengenzugehörigkeit,
    keine Hierarchie -- für Hierarchie siehe has_min_role() unten) -- genutzt von require_role()
    unten, vom Jinja-Global can() (app/routers/pages.py) UND von list_tasks_for_user()
    (app/tasks.py). Ein zweiter, eigener Weg zur Rollenbestimmung wäre genau das Muster, das bei
    build_din5008_header_block() zu drei divergierenden Varianten geführt hat (siehe CLAUDE.md
    "Kopfbereich") -- hier bewusst vermieden."""
    return user is not None and user.role in roles


def has_min_role(user: AppUser | None, min_role: str) -> bool:
    """Hierarchie-Prüfung: hat diese Person MINDESTENS den Rang von min_role (ROLE_RANK)? Anders
    als has_role() keine Mengenzugehörigkeit, sondern eine Rang-Schwelle -- admin erfüllt jede
    Schwelle, buero_finanzen jede Schwelle bis einschließlich buero_auftrag, usw. Ein unbekannter
    oder fehlender user.role-Wert (z. B. ein nicht mehr existierender Altwert) erfüllt keine
    Schwelle -- Standardverweigerung greift auch hier, kein stiller Rückfall auf "irgendwie
    erlaubt". Siehe require_min_role() unten für die FastAPI-Dependency-Fabrik, die darauf
    aufbaut."""
    if user is None or user.role not in ROLE_RANK:
        return False
    return ROLE_RANK[user.role] >= ROLE_RANK[min_role]


def require_role(*allowed_roles: str, message: str = _DEFAULT_MESSAGE):
    """Fabrik für eine FastAPI-Dependency, die 403 auslöst, wenn die angemeldete Person keine
    der übergebenen Rollen trägt (sonst den AppUser zurückgibt) -- Verallgemeinerung von
    app/deps.py::require_admin() auf eine beliebige, explizit aufgezählte Rollenmenge. Für die
    weitaus häufigere "Mindestrang genügt"-Prüfung siehe require_min_role() unten -- require_role()
    bleibt für die Fälle, in denen eine echte, nicht-hierarchische Menge gemeint ist (z. B. eine
    für jede Rolle offene Stelle, siehe ROLES oben).

    Verwendung: _role: AppUser = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE_FINANZEN, message="..."))

    Trägt eine _dk_roles-Markierung auf der zurückgegebenen Funktion, an der
    tests/test_v260_role_audit.py eine tatsächlich vorgenommene Klassifizierung erkennt (nicht
    nur irgendeine beliebige Dependency)."""
    allowed = frozenset(allowed_roles)

    def _dependency(request: Request) -> AppUser:
        user = getattr(request.state, "erp_user", None)
        if not has_role(user, *allowed):
            raise HTTPException(status_code=403, detail=message)
        return user

    _dependency._dk_roles = allowed
    return _dependency


def require_min_role(min_role: str, *, message: str = _DEFAULT_MESSAGE):
    """Fabrik für eine FastAPI-Dependency nach MINDESTRANG statt einer fest aufgezählten
    Rollenliste -- seit der Aufteilung von "office" in buero_finanzen/buero_auftrag (siehe
    CLAUDE.md "Rechtekonzept" -> "Vier Rollen") die PRIMÄRE Prüfart für die überwältigende
    Mehrheit der Endpunkte: require_min_role(ROLE_OFFICE_AUFTRAG) lässt automatisch auch
    buero_finanzen UND admin durch (admin ⊇ buero_finanzen ⊇ buero_auftrag ⊇ field, ROLE_RANK
    oben) -- exakt das, was vorher require_role(ROLE_ADMIN, ROLE_OFFICE) für die einzelne Rolle
    "office" leistete, jetzt ohne jede der beiden Bürorollen einzeln aufzuzählen. Eine künftige,
    fünfte Rolle bräuchte dadurch an den meisten Stellen keine einzige Änderung -- nur ROLE_RANK
    oben müsste sie einsortieren.

    Verwendung: _role: AppUser = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="..."))

    Trägt wie require_role() eine _dk_roles-Markierung -- hier die vollständige, aus ROLE_RANK
    abgeleitete Menge aller Rollen ab diesem Mindestrang (nicht nur min_role selbst), damit
    tests/test_v260_role_audit.py dieselbe Vollständigkeitsprüfung ohne jede Sonderbehandlung für
    diese neue Fabrik fortführen kann -- der Test liest ausschließlich, OB eine Markierung
    existiert, nicht, über welche der beiden Fabriken sie gesetzt wurde."""
    threshold = ROLE_RANK[min_role]
    allowed = frozenset(role for role, rank in ROLE_RANK.items() if rank >= threshold)

    def _dependency(request: Request) -> AppUser:
        user = getattr(request.state, "erp_user", None)
        if not has_min_role(user, min_role):
            raise HTTPException(status_code=403, detail=message)
        return user

    _dependency._dk_roles = allowed
    return _dependency


# Vollständigkeits-Ausnahmen für tests/test_v260_role_audit.py -- bewusst kurz und einzeln
# begründet, nicht als bequemer Sammelplatz für "kommt später dran". Jeder Eintrag hier ist ein
# Endpunkt, der aus einem strukturellen Grund KEINE Depends(require_role(...))/require_min_role(...)/
# require_admin()-Prüfung tragen kann, nicht einer, der nur noch nicht klassifiziert wurde (das
# listet der Test selbst als Fehlschlag auf -- genau die gewollte "Standardverweigerung fällt
# sofort auf").
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
    # "Alle vertrauten Geräte abmelden" -- dieselbe Selbstbedienungs-Begründung wie
    # change-password direkt darüber: für jede angemeldete Person gedacht (nur Administratoren
    # haben heute je ein vertrautes Gerät, aber der Endpunkt wirkt ausschließlich auf das eigene
    # Konto), siehe CLAUDE.md "Zwei-Faktor-Authentifizierung".
    ("POST", "/api/account/trusted-devices/revoke-all"),
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
