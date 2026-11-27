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
Der Kunde kommt nur aus der Sitzung; die einzige Nummer, die ein Weg nimmt, ist die einer Freigabe (seit 1.11.34) -- ob sie dem Kunden der Sitzung gehört,
prüft die Funktion der Datenbank (fremd, zurückgenommen, ruhend und unbekannt sind außen dasselbe: 404).

Seit 1.11.34 (Stufe P2b; Bauplan P2, B2 „Weg B“, B6, B7) die Dateien -- das Portal fasst kein Byte an, nginx liefert die Kopie aus:
    POST /api/datei/anfordern {"freigabe": n}   prüft Sitzung, Bremsen und Sichtbarkeit und schreibt das Zugriffsprotokoll -> {"stand": "angefordert"}
    GET  /datei/{n}                              liest nur: nach einer Anforderung derselben Sitzung in den letzten 30 Minuten (auch für die Range-Abrufe
    GET  /datei/{n}/herunterladen                eines PDF-Betrachters) eine leere Antwort mit X-Accel-Redirect auf /_portal_dateien/<Name der Kopie>,
                                                 Content-Type, Content-Disposition (inline bzw. attachment, Name aus dem Titel, nie der ursprüngliche
                                                 Dateiname) und Cache-Control -- nur diese drei übernimmt nginx; alle übrigen Kopfzeilen setzt dort der
                                                 internal-Block selbst (scripts/server/nginx-kunde.conf)

Seit 1.11.14 (Stufe P1e) die Seite selbst (app/portal/seiten.py): GET / (eine Seite für A–E, mit den öffentlichen Firmendaten), /s/portal.js und
/s/portal.css (fester Typ, ein Jahr im Speicher des Browsers -- die Seite nennt sie mit ?v=<Prüfsumme>); dazu die Design-Dateien unter /static
(app/design_dateien.py, in main.py eingebunden -- kein Weg dieses Routers).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from . import pruefwerte
from .begruessung import begruessung
from .seiten import DAUERHAFT
from .werte import POST_STATUS

router = APIRouter()
logger = logging.getLogger("dk_portal")

LESEN_METHODEN = ["GET", "HEAD"]

# Pfad -> Art; jede Route steht in genau einer (Wächter)
OEFFENTLICH = {"/health", "/api/kontakt", "/api/link", "/", "/s/portal.js", "/s/portal.css"}  # die Seite seit 1.11.14
VORSTUFE = {"/api/code", "/api/code/stand", "/api/code/pruefen"}
SITZUNG = {"/api/sitzung/weiter", "/api/abmelden", "/api/willkommen", "/api/datei/anfordern", "/datei/{freigabe}", "/datei/{freigabe}/herunterladen",
           "/datei/{freigabe}/vorschau"}  # die Vorschau seit 1.11.44

# Cookies (Bauplan 3.3): nur über diese Adresse (__Host-: Secure, Path=/, ohne Domain), nie für Skripte lesbar, nie bei Anfragen von fremden Seiten
COOKIE = "__Host-dkportal"            # bestätigte Sitzung, 30 Tage gleitend
COOKIE_CODE = "__Host-dkportal-code"  # unbestätigte Sitzung bis zum richtigen Code, 15 Minuten
SITZUNG_SEKUNDEN = 30 * 24 * 3600
CODE_SEKUNDEN = 15 * 60
LINK_KOPF = "x-portal-link"
MAX_WERT = 256  # ein echter Wert hat 43 Zeichen; was länger ist, geht gar nicht erst in die Rechnung
# Seit 1.11.8: der Code darf Leerzeichen tragen („481 207“) -- entfernt werden nur diese, und nur aus einer kurzen Eingabe
CODE_LEERZEICHEN = str.maketrans("", "", " \u00a0\u2009\u202f")
CODE_EINGABE_HOECHSTENS = 20

# Was jede Funktion der Datenbank antworten kann -- und hier behandelt wird. tests/test_v802_portal_sitzung.py vergleicht mit dem Text der Funktionen;
# ein Wort, das hier fehlt, beantwortet der Dienst mit 500, statt es still als etwas anderes zu lesen.
BEHANDELT = {
    "portal_link_oeffnen": frozenset({"angemeldet", "code_noetig", "ungueltig", "bremse"}),
    "portal_code_anfordern": frozenset({"angefordert", "bremse", "ungueltig"}),
    "portal_post_stand": frozenset({"ungueltig", "keiner", *POST_STATUS}),
    "portal_code_pruefen": frozenset({"angemeldet", "falsch", "neu_anfordern", "bremse", "ungueltig"}),
    "portal_sitzung_weiter": frozenset({"gueltig", "verlaengert", "ungueltig"}),
    "portal_abmelden": frozenset({"abgemeldet", "ungueltig"}),
    "portal_datei_anfordern": frozenset({"ok", "bremse", "unbekannt", "ungueltig"}),  # seit 1.11.34
    "portal_datei": frozenset({"ok", "unbekannt", "ungueltig"}),
    "portal_vorschau": frozenset({"ok", "keine", "unbekannt", "ungueltig"}),  # seit 1.11.44
}

# Seit 1.11.34: die Kopien (app/portal_kopien.py) -- nginx liefert sie aus dem internal-Block unter diesem Weg aus
INTERN = "/_portal_dateien/"
KOPIE_NAME = re.compile(r"^[0-9a-f]{64}\.(pdf|jpg)$")
KOPIE_ENDUNG = {"application/pdf": "pdf", "image/jpeg": "jpg"}
FREIGABE_HOECHSTENS = 2147483647  # int4 wie die Spalte
DATEINAME_HOECHSTENS = 100


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
    """Seit 1.11.8 auch mit Leerzeichen: die Mail zeigt den Code in Gruppen („481 207“, app/portal_mails.py::code_gruppen()). Entfernt werden nur
    Leerzeichen (auch geschützte und schmale, wie sie beim Kopieren aus einer Mail entstehen), danach genau 6 Ziffern 0–9."""

    code: str = Field(pattern=r"^[0-9]{6}$")

    @field_validator("code", mode="before")
    @classmethod
    def _ohne_leerzeichen(cls, wert):
        if isinstance(wert, str) and len(wert) <= CODE_EINGABE_HOECHSTENS:
            return wert.translate(CODE_LEERZEICHEN)
        return wert


class AbmeldenIn(_Ein):
    ueberall: StrictBool


class AnfordernIn(_Ein):
    freigabe: StrictInt = Field(ge=1, le=FREIGABE_HOECHSTENS)


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


# --- Die Seite (seit 1.11.14, Stufe P1e) ---------------------------------------------------------------------------------------------------------

def seite_antwort(request: Request, fall: str = "", status: int = 200) -> HTMLResponse:
    """Die Seite mit den öffentlichen Firmendaten; liest sie die Datenbank nicht, die Fehlerseite „technisch“ ohne Kontakt (500). Nie im Speicher
    des Browsers (no-store, setzt die Schranke)."""
    seiten = request.app.state.seiten
    try:
        kontakt = _db(request).kontakt()
    except Exception as exc:  # noqa: BLE001 -- die Ursache gehört ins Journal (nur die Klasse), nicht in die Seite
        logger.error("Seite ohne Firmendaten: %s", type(exc).__name__)
        return HTMLResponse(seiten.seite(None, "technisch"), status_code=500, headers={"X-Robots-Tag": "noindex"})
    return HTMLResponse(seiten.seite(kontakt, fall), status_code=status, headers={"X-Robots-Tag": "noindex"})


@router.api_route("/", methods=LESEN_METHODEN, response_class=HTMLResponse)
def startseite(request: Request):
    """Die Seite des Portals (Bauplan P1, Abschnitt 5) -- A bis E wählt das Skript; der Link kommt im #-Fragment und nie zum Server."""
    return seite_antwort(request)


@router.api_route("/s/portal.js", methods=LESEN_METHODEN, response_class=Response)
def skript(request: Request):
    """Das Skript der Seite -- Typ fest (tests/test_v406_dateien_nie_aktiv.py), ein Jahr im Speicher (die Seite nennt es mit ?v=)."""
    return Response(request.app.state.seiten.datei("portal.js"), media_type="text/javascript; charset=utf-8", headers={"Cache-Control": DAUERHAFT})


@router.api_route("/s/portal.css", methods=LESEN_METHODEN, response_class=Response)
def stil(request: Request):
    """Der Stil der Seite -- Typ fest, ein Jahr im Speicher."""
    return Response(request.app.state.seiten.datei("portal.css"), media_type="text/css; charset=utf-8", headers={"Cache-Control": DAUERHAFT})


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


# --- Dateien (seit 1.11.34, Stufe P2b) -------------------------------------------------------------------------------------------------------------

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def dateiname(titel: str | None, typ: str) -> tuple[str, str]:
    """(ASCII-Name, Name für filename*) aus dem Titel der Freigabe -- nie der ursprüngliche Dateiname. Steuerzeichen, Anführungszeichen, Schrägstriche und
    Backslash fallen weg; der ASCII-Name ersetzt Umlaute und alles außer Buchstaben, Ziffern, Leerzeichen, Punkt, Bindestrich und Unterstrich; beide
    höchstens DATEINAME_HOECHSTENS Zeichen vor der Endung, leer -> „Unterlage“."""
    endung = KOPIE_ENDUNG[typ]
    sauber = "".join(" " if unicodedata.category(z)[0] == "C" or z in "\"\\/" else z for z in (titel or ""))
    sauber = re.sub(r"\s+", " ", sauber).strip(" .")[:DATEINAME_HOECHSTENS].strip(" .") or "Unterlage"
    ascii_ = unicodedata.normalize("NFKD", sauber.translate(UMLAUTE)).encode("ascii", "ignore").decode("ascii")
    ascii_ = re.sub(r"[^A-Za-z0-9 ._-]", "_", ascii_)
    ascii_ = re.sub(r"\s+", " ", ascii_).strip(" .") or "Unterlage"
    return f"{ascii_}.{endung}", f"{sauber}.{endung}"


@router.post("/api/datei/anfordern", response_model=CodeOut)
def datei_anfordern(request: Request, eingabe: AnfordernIn):
    """„Ansehen“ (Bauplan P2, B7): die Funktion prüft Sitzung, Bremsen und ob die Freigabe dem Kunden der Sitzung sichtbar ist, und schreibt das
    Zugriffsprotokoll. Fremd, zurückgenommen, ruhend und unbekannt: 404 -- außen dasselbe."""
    wert = _wert(request, COOKIE)
    if wert is None:
        return _ohne_sitzung(COOKIE)
    ergebnis, minuten = _db(request).datei_anfordern(pruefwerte.sitzung(wert), eingabe.freigabe, _anschluss(request))
    if _behandelt("portal_datei_anfordern", ergebnis) == "bremse":
        return _bremse(minuten)
    if ergebnis == "ungueltig":
        return _ohne_sitzung(COOKIE)
    if ergebnis == "unbekannt":
        return JSONResponse({"fehler": "nicht_gefunden"}, status_code=404)
    return {"stand": "angefordert"}


def _datei(request: Request, freigabe: int, art: str):
    """Liest nur: die Kopie für nginx (X-Accel-Redirect) -- nach einer Anforderung derselben Sitzung in den letzten 30 Minuten. Ein GET setzt und löscht
    kein Cookie. Name und Typ der Kopie prüft der Dienst noch einmal, bevor er sie nginx nennt (nie ein Pfad aus der Datenbank ohne Prüfung)."""
    wert = _wert(request, COOKIE)
    if wert is None:
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    ergebnis, name, typ, _groesse, titel = _db(request).datei(pruefwerte.sitzung(wert), freigabe)
    if _behandelt("portal_datei", ergebnis) == "ungueltig":
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    if ergebnis == "unbekannt":
        return JSONResponse({"fehler": "nicht_gefunden"}, status_code=404)
    if typ not in KOPIE_ENDUNG or not KOPIE_NAME.match(name or "") or not name.endswith("." + KOPIE_ENDUNG[typ]):
        raise UnbekanntesErgebnis("portal_datei")
    ascii_, voll = dateiname(titel, typ)
    medientyp = "application/pdf" if typ == "application/pdf" else "image/jpeg"  # fester Typ (Regel 31); typ ist oben geprüft
    return Response(b"", media_type=medientyp, headers={
        "X-Accel-Redirect": INTERN + name,
        "Content-Disposition": f'{art}; filename="{ascii_}"; filename*=UTF-8\'\'{quote(voll, safe="")}',
        "Cache-Control": "private, no-store",
    })


@router.api_route("/datei/{freigabe}", methods=LESEN_METHODEN, response_class=Response)
def datei_ansehen(request: Request, freigabe: int = Path(ge=1, le=FREIGABE_HOECHSTENS)):
    """„Ansehen“ im selben Tab (P2-16): inline."""
    return _datei(request, freigabe, "inline")


@router.api_route("/datei/{freigabe}/vorschau", methods=LESEN_METHODEN, response_class=Response)
def datei_vorschau(request: Request, freigabe: int = Path(ge=1, le=FREIGABE_HOECHSTENS)):
    """Seit 1.11.44: die Vorschau eines Fotos (400 px) für die Bildreihe -- liest nur, ohne Anforderung (die Liste steht schon im Protokoll); sichtbar wie
    die Datei. Ohne Vorschau, fremd, zurückgenommen, ruhend, unbekannt: 404 -- außen dasselbe."""
    wert = _wert(request, COOKIE)
    if wert is None:
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    ergebnis, name = _db(request).vorschau(pruefwerte.sitzung(wert), freigabe)
    if _behandelt("portal_vorschau", ergebnis) == "ungueltig":
        return JSONResponse({"fehler": "sitzung"}, status_code=401)
    if ergebnis != "ok":
        return JSONResponse({"fehler": "nicht_gefunden"}, status_code=404)
    if not KOPIE_NAME.match(name or "") or not name.endswith(".jpg"):
        raise UnbekanntesErgebnis("portal_vorschau")
    return Response(b"", media_type="image/jpeg", headers={
        "X-Accel-Redirect": INTERN + name,
        "Content-Disposition": 'inline; filename="Vorschau.jpg"',
        "Cache-Control": "private, no-store",
    })


@router.api_route("/datei/{freigabe}/herunterladen", methods=LESEN_METHODEN, response_class=Response)
def datei_herunterladen(request: Request, freigabe: int = Path(ge=1, le=FREIGABE_HOECHSTENS)):
    """„Herunterladen“: attachment."""
    return _datei(request, freigabe, "attachment")
