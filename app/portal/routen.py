"""Die Wege des Portal-Dienstes (seit 1.11.2; Link, Code und Sitzung seit 1.11.3). Jede Antwort über ein eigenes Schema (Positivliste, extra verboten) --
ein neues Feld im ERP kommt nie von selbst ins Portal. Jeder Weg steht in genau einer Liste: OEFFENTLICH (ohne Sitzung), VORSTUFE (mit unbestätigter
Sitzung), SITZUNG (bestätigt); ein Wächter (tests/test_v801_portal_dienst.py) verlangt das. Jeder Endpunkt ist ein gewöhnliches def (Threadpool).

Kein GET schreibt (wie Regel 23 im ERP): Lesen ruft nur Funktionen, die nichts schreiben (STABLE, ohne Commit), oder liest die Firmendaten; ein GET setzt
auch kein Cookie.

Ablauf (Bauplan P1, 3.1–3.3; alles Prüfen in den Funktionen der Datenbank, app/portal/funktionen.py):
    POST /api/link            Link aus der Kopfzeile X-Portal-Link (die Seite liest ihn aus dem #-Fragment) -> angemeldet | code_noetig | ungueltig;
                              bei code_noetig das Cookie der unbestätigten Sitzung (15 Minuten) und die verdeckte Adresse
    POST /api/code            Code anfordern (Auftrag an den Postboten)
    GET  /api/code/stand      Stand des Versands (wartet, gesendet, fehler, verworfen, keiner)
    POST /api/code/pruefen    {"code": "123456"} -> angemeldet (neues Cookie der bestätigten Sitzung) | falsch (mit Rest) | neu_anfordern
    POST /api/sitzung/weiter  beim Laden jeder Seite mit Sitzung: prüft und verlängert höchstens einmal je Stunde um 30 Tage
    POST /api/abmelden        {"ueberall": false | true}
    GET  /api/willkommen      Begrüßung des Kunden der Sitzung
Ohne gültige Sitzung 401 {"fehler": "sitzung"} (ein POST löscht dabei das Cookie), eine Bremse 429 {"fehler": "bremse", "minuten": n} mit Retry-After.
Kein Weg nimmt eine ID: der Kunde kommt nur aus der Sitzung.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from . import pruefwerte
from .begruessung import begruessung
from .werte import POST_STATUS

router = APIRouter()

LESEN_METHODEN = ["GET", "HEAD"]

# Pfad -> Art; jede Route steht in genau einer (Wächter)
OEFFENTLICH = {"/health", "/api/kontakt", "/api/link"}
VORSTUFE = {"/api/code", "/api/code/stand", "/api/code/pruefen"}
SITZUNG = {"/api/sitzung/weiter", "/api/abmelden", "/api/willkommen"}

# Cookies (Bauplan 3.3): nur über diese Adresse (__Host-: Secure, Path=/, ohne Domain), nie für Skripte lesbar, nie bei Anfragen von fremden Seiten
COOKIE = "__Host-dkportal"            # bestätigte Sitzung, 30 Tage gleitend
COOKIE_CODE = "__Host-dkportal-code"  # unbestätigte Sitzung bis zum richtigen Code, 15 Minuten
SITZUNG_SEKUNDEN = 30 * 24 * 3600
CODE_SEKUNDEN = 15 * 60
LINK_KOPF = "x-portal-link"
MAX_WERT = 256  # ein echter Wert hat 43 Zeichen; was länger ist, geht gar nicht erst in die Rechnung

# Was jede Funktion der Datenbank antworten kann -- und hier behandelt wird. tests/test_v802_portal_sitzung.py vergleicht mit dem Text der Funktionen;
# ein Wort, das hier fehlt, beantwortet der Dienst mit 500, statt es still als etwas anderes zu lesen.
BEHANDELT = {
    "portal_link_oeffnen": frozenset({"angemeldet", "code_noetig", "ungueltig", "bremse"}),
    "portal_code_anfordern": frozenset({"angefordert", "bremse", "ungueltig"}),
    "portal_post_stand": frozenset({"ungueltig", "keiner", *POST_STATUS}),
    "portal_code_pruefen": frozenset({"angemeldet", "falsch", "neu_anfordern", "bremse", "ungueltig"}),
    "portal_sitzung_weiter": frozenset({"gueltig", "verlaengert", "ungueltig"}),
    "portal_abmelden": frozenset({"abgemeldet", "ungueltig"}),
}


class UnbekanntesErgebnis(RuntimeError):
    """Eine Funktion der Datenbank antwortete mit einem Wort, das der Dienst nicht kennt (Code und Migration auseinander) -- 500, im Journal die Klasse."""


def _behandelt(funktion: str, wort: str) -> str:
    if wort not in BEHANDELT[funktion]:
        raise UnbekanntesErgebnis(funktion)
    return wort


class _Aus(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Ein(BaseModel):
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


class LinkOut(_Aus):
    stand: str
    email_anzeige: str | None


class CodeOut(_Aus):
    stand: str


class PruefenOut(_Aus):
    stand: str
    rest: int | None


class StandOut(_Aus):
    stand: str


class WillkommenOut(_Aus):
    begruessung: str


class CodeIn(_Ein):
    code: str = Field(pattern=r"^[0-9]{6}$")


class AbmeldenIn(_Ein):
    ueberall: StrictBool


# --- Hilfen ----------------------------------------------------------------------------------------------------------------------------------------

def _db(request: Request):
    return request.app.state.db


def _anschluss(request: Request) -> str:
    """Der Anschluss als HMAC (F14). request.client ist hinter nginx die rechteste fremde Adresse aus X-Forwarded-For -- gunicorn/uvicorn vertrauen der
    Kopfzeile nur von 127.0.0.1 und ::1 (E4); eine vom Besucher vorangestellte Adresse ändert nichts."""
    adresse = request.client.host if request.client else ""
    return pruefwerte.anschluss(adresse, request.app.state.einstellungen.bremse_schluessel)


def _wert(request: Request, name: str) -> str | None:
    wert = request.cookies.get(name)
    return wert if wert and len(wert) <= MAX_WERT else None


def _setzen(antwort: JSONResponse, name: str, wert: str, sekunden: int) -> None:
    antwort.set_cookie(name, wert, max_age=sekunden, path="/", secure=True, httponly=True, samesite="strict")


def _loeschen(antwort: JSONResponse, *namen: str) -> None:
    for name in namen:
        antwort.delete_cookie(name, path="/", secure=True, httponly=True, samesite="strict")


def _ohne_sitzung(*loeschen: str) -> JSONResponse:
    antwort = JSONResponse({"fehler": "sitzung"}, status_code=401)
    _loeschen(antwort, *loeschen)
    return antwort


def _bremse(minuten: int | None) -> JSONResponse:
    minuten = max(1, int(minuten or 1))
    return JSONResponse({"fehler": "bremse", "minuten": minuten}, status_code=429, headers={"Retry-After": str(minuten * 60)})


# --- Öffentlich ------------------------------------------------------------------------------------------------------------------------------------

@router.api_route("/health", methods=LESEN_METHODEN, response_model=GesundOut)
def gesund(request: Request):
    """Für systemd, update.sh und nginx: der Dienst läuft und erreicht die Datenbank. Sonst 503 ohne Grund."""
    try:
        if _db(request).erreichbar():
            return {"ok": True}
    except Exception:  # noqa: BLE001 -- die Ursache gehört ins Journal des Dienstes, nicht in die Antwort
        pass
    return JSONResponse({"ok": False}, status_code=503)


@router.api_route("/api/kontakt", methods=LESEN_METHODEN, response_model=KontaktOut)
def kontakt(request: Request):
    """Die Firmendaten aus den Einstellungen (P1-14) -- öffentlich, für „Willkommen“ und die Fehlerseite."""
    k = _db(request).kontakt() or {}
    return {"firma": k.get("company_name"), "strasse": k.get("street"), "plz": k.get("postal_code"), "ort": k.get("city"),
            "telefon": k.get("phone"), "email": k.get("email"), "webseite": k.get("website")}


@router.post("/api/link", response_model=LinkOut)
def link(request: Request):
    """Link prüfen (Seite A). Jeder Grund, aus dem ein Link nicht gilt, ist außen dieselbe Antwort (die Funktion unterscheidet nur im Protokoll)."""
    wert = request.headers.get(LINK_KOPF)
    if not wert or len(wert) > MAX_WERT:
        return JSONResponse({"fehler": "eingabe"}, status_code=422)
    alt, neu = _wert(request, COOKIE), pruefwerte.neuer_wert()
    ergebnis, anzeige, minuten = _db(request).link_oeffnen(pruefwerte.link(wert), _anschluss(request),
                                                           pruefwerte.sitzung(alt) if alt else None, pruefwerte.sitzung(neu))
    if _behandelt("portal_link_oeffnen", ergebnis) == "bremse":
        return _bremse(minuten)
    if ergebnis == "code_noetig":
        antwort = JSONResponse({"stand": "code_noetig", "email_anzeige": anzeige})
        _setzen(antwort, COOKIE_CODE, neu, CODE_SEKUNDEN)
        return antwort
    return {"stand": ergebnis, "email_anzeige": None}


# --- Vorstufe (unbestätigte Sitzung) ---------------------------------------------------------------------------------------------------------------

@router.post("/api/code", response_model=CodeOut)
def code_anfordern(request: Request):
    """Code anfordern (Seite B): ein Auftrag an den Postboten (P1c), der die Mail an die Adresse des Zugangs schickt -- nie an eine aus der Anfrage."""
    wert = _wert(request, COOKIE_CODE)
    if wert is None:
        return _ohne_sitzung(COOKIE_CODE)
    ergebnis, minuten = _db(request).code_anfordern(pruefwerte.sitzung(wert), _anschluss(request))
    if _behandelt("portal_code_anfordern", ergebnis) == "bremse":
        return _bremse(minuten)
    if ergebnis == "ungueltig":
        return _ohne_sitzung(COOKIE_CODE)
    return {"stand": "angefordert"}


@router.api_route("/api/code/stand", methods=LESEN_METHODEN, response_model=StandOut)
def code_stand(request: Request):
    """Stand des Versands (Seite B: wird gesendet …, gesendet, gescheitert). Liest nur."""
    wert = _wert(request, COOKIE_CODE)
    if wert is None:
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    stand = _behandelt("portal_post_stand", _db(request).post_stand(pruefwerte.sitzung(wert)))
    if stand == "ungueltig":
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    return {"stand": stand}


@router.post("/api/code/pruefen", response_model=PruefenOut)
def code_pruefen(request: Request, eingabe: CodeIn):
    """Code eingeben (Seite C). Richtig: die Sitzung ist bestätigt und bekommt einen NEUEN Wert -- ein vorher bekannter Wert nützt danach nichts; eine
    frühere Sitzung dieses Browsers endet (ein Browser, eine Sitzung)."""
    wert = _wert(request, COOKIE_CODE)
    if wert is None:
        return _ohne_sitzung(COOKIE_CODE)
    sitzung, neu = pruefwerte.sitzung(wert), pruefwerte.neuer_wert()
    db = _db(request)
    ergebnis, zahl = db.code_pruefen(sitzung, pruefwerte.code(sitzung, eingabe.code), pruefwerte.sitzung(neu), _anschluss(request))
    if _behandelt("portal_code_pruefen", ergebnis) == "bremse":
        return _bremse(zahl)
    if ergebnis == "ungueltig":
        return _ohne_sitzung(COOKIE_CODE)
    if ergebnis == "falsch":
        return {"stand": "falsch", "rest": max(0, int(zahl or 0))}
    if ergebnis == "neu_anfordern":
        return {"stand": "neu_anfordern", "rest": None}
    alt = _wert(request, COOKIE)
    if alt:
        db.abmelden(pruefwerte.sitzung(alt), False)  # die frühere Sitzung dieses Browsers -- ihr Ergebnis ändert nichts
    antwort = JSONResponse({"stand": "angemeldet", "rest": None})
    _setzen(antwort, COOKIE, neu, SITZUNG_SEKUNDEN)
    _loeschen(antwort, COOKIE_CODE)
    return antwort


# --- Sitzung (bestätigt) ---------------------------------------------------------------------------------------------------------------------------

@router.post("/api/sitzung/weiter", response_model=StandOut)
def sitzung_weiter(request: Request):
    """Beim Laden jeder Seite mit Sitzung (Seite D): prüft und verlängert höchstens einmal je Stunde um 30 Tage ab jetzt -- dann auch das Cookie."""
    wert = _wert(request, COOKIE)
    if wert is None:
        return _ohne_sitzung(COOKIE)
    ergebnis = _behandelt("portal_sitzung_weiter", _db(request).sitzung_weiter(pruefwerte.sitzung(wert)))
    if ergebnis == "ungueltig":
        return _ohne_sitzung(COOKIE)
    antwort = JSONResponse({"stand": "angemeldet"})
    if ergebnis == "verlaengert":
        _setzen(antwort, COOKIE, wert, SITZUNG_SEKUNDEN)
    return antwort


@router.post("/api/abmelden", response_model=StandOut)
def abmelden(request: Request, eingabe: AbmeldenIn):
    """Abmelden (dieses Gerät) oder auf allen Geräten (P1-6). Eine noch unbestätigte Sitzung dieses Browsers endet mit."""
    wert, code_wert = _wert(request, COOKIE), _wert(request, COOKIE_CODE)
    if wert is None:
        return _ohne_sitzung(COOKIE, COOKIE_CODE)
    db = _db(request)
    ergebnis = _behandelt("portal_abmelden", db.abmelden(pruefwerte.sitzung(wert), eingabe.ueberall))
    if code_wert:
        db.abmelden(pruefwerte.sitzung(code_wert), False)
    if ergebnis == "ungueltig":
        return _ohne_sitzung(COOKIE, COOKIE_CODE)
    antwort = JSONResponse({"stand": "abgemeldet"})
    _loeschen(antwort, COOKIE, COOKIE_CODE)
    return antwort


@router.api_route("/api/willkommen", methods=LESEN_METHODEN, response_model=WillkommenOut)
def willkommen(request: Request):
    """Die Begrüßung des Kunden der Sitzung (Seite D) -- gesiezt, aus Anrede, Titel und Namen (begruessung.py). Liest nur."""
    wert = _wert(request, COOKIE)
    zeile = _db(request).willkommen(pruefwerte.sitzung(wert)) if wert else None
    if zeile is None:
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    return {"begruessung": begruessung(zeile["anrede"], zeile["titel"], zeile["vorname"], zeile["nachname"], zeile["name"])}
