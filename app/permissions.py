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

_DEFAULT_MESSAGE = "Für deine Rolle nicht verfügbar."
ROLLE_NICHT_VERFUEGBAR = _DEFAULT_MESSAGE  # seit 1.9.27: die Sperrseite zeigt diese allgemeine Meldung nicht (app/main.py)


def has_role(user: AppUser | None, *roles: str) -> bool:
    """Die EINE Quelle für "hat diese Person eine dieser Rollen" (flache Mengenzugehörigkeit,
    keine Hierarchie -- für Hierarchie siehe has_min_role() unten) -- genutzt von require_role()
    unten, vom Jinja-Global can() (app/routers/pages.py) UND von list_tasks_for_user()
    (app/tasks.py). Ein zweiter, eigener Weg zur Rollenbestimmung wäre genau das Muster, das bei
    build_din5008_header_block() zu drei divergierenden Varianten geführt hat (siehe CLAUDE.md
    "Kopfbereich") -- hier bewusst vermieden."""
    return user is not None and user.role in roles


# Seit 1.9.33 (Stufe 4, R1): die Rollen der Monteursansicht -- wer /mobil als Arbeitsplatz hat (Startseite /mobil,
# default_home_page_for_role() oben). Nur sie bekommen die heutigen Einsätze (GET /api/field-view/today) und den Feierabend (POST
# /api/field-view/feierabend). Die Seite /mobil öffnet weiter jede Rolle -- das Büro wird dort aber nach Feierabend nicht mehr abgemeldet
# (bis 1.9.32 meldete der GET jeder Rolle ab 19 Uhr "feierabend", /mobil beendete dann die Sitzung).
MOBIL_ROLLEN = frozenset({ROLE_FIELD})
NUR_MONTEURSANSICHT = "„Heute“ gibt es nur in der Monteursansicht."  # seit 1.9.93 (bis dahin „Die Einsätze …“, der Reiter heißt „Heute“)


def hat_monteursansicht(user: AppUser | None) -> bool:
    """Seit 1.9.33: gehört die Person zu den Rollen der Monteursansicht (MOBIL_ROLLEN)?"""
    return has_role(user, *MOBIL_ROLLEN)


# Seit 1.9.89 (Stufe 4, R5a, Entscheidungen Tobias): die Rechte an den Zeiten, je Recht eine Regel an dieser Stelle -- Server
# (app/routers/time_tracking.py, app/routers/time_backoffice.py) und Oberfläche fragen nur diese Funktionen bzw. Abhängigkeiten.
# - Zeiten anderer buchen, ändern, löschen, „Ende nachtragen“, „Pausen neu rechnen“: Admin und Büro – Finanzen (bis 1.9.88 nur Admin);
#   im abgeschlossenen Zeitraum weiter nur der Admin (time_tracking._require_open_period()), Anträge entscheiden der Admin.
# - Überhaupt Zeiten buchen oder ändern: die Monteurin (nur ihre eigenen) und wer für andere bucht. Büro – Auftrag liest die Zeiten
#   aller und ändert nichts -- auch keine eigenen (Entscheidung: das Büro erfasst keine eigene Zeit).
# - Lohndaten -- Stundenzettel aller, Stundendaten als CSV, DATEV-Export, Abschließen: Admin und Büro – Finanzen; einen Abschluss
#   zurücknehmen oder aufheben nur der Admin.
ZEIT_FUER_ANDERE_ROLLEN = frozenset({ROLE_ADMIN, ROLE_OFFICE_FINANZEN})
ZEIT_BUCHEN_ROLLEN = ZEIT_FUER_ANDERE_ROLLEN | {ROLE_FIELD}
LOHNDATEN_ROLLEN = frozenset({ROLE_ADMIN, ROLE_OFFICE_FINANZEN})
ZEITEN_NUR_LESEN = "Zeiten buchen und ändern Admin und Büro – Finanzen – du kannst sie lesen."
NUR_LOHNDATEN = "Stundenzettel, Exporte und den Abschluss gibt es nur für Admin und Büro – Finanzen."


def darf_zeit_fuer_andere_buchen(user: AppUser | None) -> bool:
    """Seit 1.8.152: wer Zeit für andere bucht oder deren Buchungen ändert -- die eine Stelle für den Server
    (app/routers/time_tracking.py) und die Oberfläche (Auswahl "Mitarbeiter" im Einsatzbericht, über /api/auth/status und die
    Seitenroute). Seit 1.9.89 Admin und Büro – Finanzen (bis dahin nur Admin); ohne Konto (Tests ohne Anmeldung) wie bisher ohne
    Einschränkung."""
    return user is None or has_role(user, *ZEIT_FUER_ANDERE_ROLLEN)


def darf_zeit_buchen(user: AppUser | None) -> bool:
    """Seit 1.9.89: wer überhaupt Zeiten bucht, startet, stoppt, ändert oder löscht -- die Monteurin ihre eigenen, nach
    darf_zeit_fuer_andere_buchen() auch die anderer. Büro – Auftrag liest nur (bis 1.9.88 buchte es eigene Zeiten). Die Endpunkte prüfen
    es über require_zeit_buchen, die Oberfläche blendet danach aus."""
    return user is None or has_role(user, *ZEIT_BUCHEN_ROLLEN)


def darf_lohndaten(user: AppUser | None) -> bool:
    """Seit 1.9.89: Stundenzettel aller, Stundendaten als CSV, DATEV-Export und Abschließen -- Admin und Büro – Finanzen (bis 1.9.88
    jedes Büro). Die Endpunkte prüfen es über require_lohndaten, die Oberfläche blendet danach aus."""
    return user is None or has_role(user, *LOHNDATEN_ROLLEN)


def zeit_nur_mit_von_bis(user: AppUser | None) -> bool:
    """Seit 1.9.60 (Stufe 4, R3, Punkt 3): wer eine Zeit nur mit Von und Bis nachträgt oder ändert, nie als reine Dauer -- heute die
    Monteurin (field), damit die Pausenregel des Tages gilt; das Büro trägt weiter Dauern ein. Die eine Stelle für den Server
    (POST/PUT /api/time-entries) und die Oberfläche (Einsatzbericht, Seitenroute); ohne Konto (Tests ohne Anmeldung) ohne Einschränkung."""
    return user is not None and has_role(user, ROLE_FIELD)


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


# Seit 1.9.89: die Abhängigkeiten zu darf_zeit_buchen() und darf_lohndaten() oben -- dieselben Rollenmengen, eine Stelle.
require_zeit_buchen = require_role(*ZEIT_BUCHEN_ROLLEN, message=ZEITEN_NUR_LESEN)
require_lohndaten = require_role(*LOHNDATEN_ROLLEN, message=NUR_LOHNDATEN)


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
    # PWA-Icon der Monteursansicht -- liefert nur ein aus dem Firmenlogo abgeleitetes
    # Platzhalterbild, keine Kunden-/Geschäftsdaten. Seit 1.8.130 auch ohne Anmeldung erreichbar
    # (app/anmeldeschranke.py::OEFFENTLICH, GET und HEAD), wie /manifest.json, das darauf verweist.
    ("GET", "/api/mobile-icon/{size}.png"),
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
})
