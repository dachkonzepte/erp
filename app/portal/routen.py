"""Die Wege des Portal-Dienstes (seit 1.11.2). Jede Antwort über ein eigenes Schema (Positivliste, extra verboten) -- ein neues Feld im ERP kommt nie von
selbst ins Portal. Jeder Weg steht in genau einer Liste: OEFFENTLICH (ohne Sitzung), VORSTUFE (mit unbestätigter Sitzung), SITZUNG (bestätigt); ein Wächter
(tests/test_v801_portal_dienst.py) verlangt das. Jeder Endpunkt ist ein gewöhnliches def (Threadpool).

Kein GET schreibt (wie Regel 23 im ERP): Lesen ruft nur Funktionen, die nichts schreiben (STABLE), oder liest die Firmendaten.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

router = APIRouter()

LESEN_METHODEN = ["GET", "HEAD"]

# Pfad -> Art; jede Route steht in genau einer (Wächter)
OEFFENTLICH = {"/health", "/api/kontakt"}
VORSTUFE: set[str] = set()
SITZUNG: set[str] = set()


class _Aus(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GesundOut(_Aus):
    ok: bool


class KontaktOut(_Aus):
    firma: str | None
    strasse: str | None
    plz: str | None
    ort: str | None
    telefon: str | None
    email: str | None
    webseite: str | None


@router.api_route("/health", methods=LESEN_METHODEN, response_model=GesundOut)
def gesund(request: Request):
    """Für systemd, update.sh und nginx: der Dienst läuft und erreicht die Datenbank. Sonst 503 ohne Grund."""
    try:
        if request.app.state.db.erreichbar():
            return {"ok": True}
    except Exception:  # noqa: BLE001 -- die Ursache gehört ins Journal des Dienstes, nicht in die Antwort
        pass
    return JSONResponse({"ok": False}, status_code=503)


@router.api_route("/api/kontakt", methods=LESEN_METHODEN, response_model=KontaktOut)
def kontakt(request: Request):
    """Die Firmendaten aus den Einstellungen (P1-14) -- öffentlich, für „Willkommen“ und die Fehlerseite."""
    k = request.app.state.db.kontakt() or {}
    return {"firma": k.get("company_name"), "strasse": k.get("street"), "plz": k.get("postal_code"), "ort": k.get("city"),
            "telefon": k.get("phone"), "email": k.get("email"), "webseite": k.get("website")}
