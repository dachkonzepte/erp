"""Gemeinsame FastAPI-Dependencies für Zugriffsprüfungen (seit 1.0.9).

Ersetzt die zuvor verstreuten "nur Administratoren dürfen das"-Prüfungen
(teils als eigenes _require_admin() nur in time_backoffice.py, teils als
Inline-Checks in mehreren anderen Routern) durch eine einzige,
wiederverwendbare Dependency-Fabrik.

require_admin() ist bewusst parametrisierbar (message=...), damit jeder
Endpunkt weiterhin seine bisherige, spezifische Fehlermeldung zeigt --
konsolidiert wird nur die Prüf-LOGIK, nicht der Wortlaut.

Gilt bewusst NUR für reine "nur Administratoren"-Fälle ohne Ausnahmen.
Nicht dafür geeignet (bleiben unverändert als spezifische Logik in den
jeweiligen Routern):
- Der Bootstrap-Fall beim Anlegen des allerersten ERP-Benutzers
  (routers/users.py, create_app_user) -- dort darf es noch KEINEN
  Administrator geben.
- Selbstbedienungs-/Eigentümer-Logik wie "eigene Zeitbuchungen und
  Abwesenheitsanträge sehen/bearbeiten, fremde nur als Admin"
  (routers/time_tracking.py, routers/absence_requests.py) -- das ist
  Filterlogik, kein binäres Ja/Nein-Gate.
"""

from fastapi import HTTPException, Request

from .models import AppUser

_DEFAULT_MESSAGE = "Diese Aktion ist nur für Administratoren verfügbar."


def require_admin(message: str = _DEFAULT_MESSAGE):
    """Fabrik für eine FastAPI-Dependency, die 403 auslöst, wenn kein
    angemeldeter Administrator vorliegt, und sonst den AppUser zurückgibt.

    Verwendung: current: AppUser = Depends(require_admin("eigene Meldung"))
    """

    def _dependency(request: Request) -> AppUser:
        user = getattr(request.state, "erp_user", None)
        if user is None or user.role != "admin":
            raise HTTPException(status_code=403, detail=message)
        return user

    # Seit "Rechtekonzept" (siehe CLAUDE.md, app/permissions.py::require_role()): reine
    # Markierung für tests/test_v260_role_audit.py, damit dieser require_admin() als bereits
    # klassifiziert erkennt -- ändert das Verhalten dieser Funktion an keiner Stelle.
    _dependency._dk_roles = frozenset({"admin"})
    return _dependency
