"""Anfragen der Webseite (seit 1.10.0, Stufe W1a; docs/archiv/webseite-und-kundenportal.md).

Abholen (abholen()): über die ERP-Schnittstelle des Empfangsdienstes der Webseite (dk-anfrage/1, nur auf diesem Server). Je neue Anfrage: den Umschlag
holen und prüfen, jede Datei holen, Größe, Prüfsumme und Typ am Inhalt prüfen, unter eigenem Namen ablegen, dann EINE Transaktion für den Eingang
(WebAnfrage mit Dateien) -- und erst danach beim Empfangsdienst „übernommen“ melden. Was der Empfangsdienst liefert, gilt als Fremddaten wie von einem
Angreifer:

- Verbindung nur zu einer Adresse auf diesem Server (DK_ANFRAGE_URL, Vorgabe http://127.0.0.1:8095), ohne Proxy und ohne Umleitung (eine Umleitung
  nähme sonst den Schlüssel mit). Der Schlüssel (DK_ANFRAGE_SCHLUESSEL) steht nie in einem Protokoll, einer Fehlermeldung, einer Antwort oder dem Stand.
- Grenzen für jede Antwort (Liste, Umschlag, Datei, Summe je Anfrage, Zahl der Dateien, Teile eines JSON, Seiten, neue Anfragen je Lauf, Zeit).
- Der Name einer Datei wird nur gegen eine feste Liste geprüft (anfrage.pdf, foto-N.jpg) und nie als Pfad benutzt; die Angabe „pfad“ des Umschlags wird
  nie gelesen. Abgelegt wird unter einem zufälligen Namen.
- Stimmt eine Datei nicht (Prüfsumme, Größe, Typ am Inhalt, fehlt): nichts ablegen, nichts melden -- die Anfrage steht im Stand unter „nicht abgeholt“
  und kommt im nächsten Lauf wieder.
- Unbekannte Art, unbekannte Fassung, ungültige Angaben: in den Eingang mit Grund (Prüfliste) -- nie ein Fehler 500.
- Fällt der Empfangsdienst mitten in einer Anfrage aus, bleibt nichts halb angelegt (Dateien weg, keine Zeile); der Lauf endet mit dem Fehler.
- Ein Lauf belegt den Stand (bedingtes UPDATE wie beim Outlook-Abgleich, SPERRE_GILT); ein zweiter Lauf zugleich tut nichts.

Rollenlos wie jede Geschäftslogik; wer abholen und lesen darf, entscheidet app/routers/webanfragen.py.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .dateiauslieferung import typ_aus_inhalt
from .grunddaten import einzelzeile
from .models import WebAnfrage, WebAnfrageDatei, WebanfragenAbholung
from .webanfrage_angaben import objekt_adresse
from .paths import data_dir

logger = logging.getLogger(__name__)

SCHLUESSEL_VARIABLE = "DK_ANFRAGE_SCHLUESSEL"
ADRESSE_VARIABLE = "DK_ANFRAGE_URL"
ADRESSE_VORGABE = "http://127.0.0.1:8095"
LOKALE_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

FASSUNG = "dk-anfrage/1"
ARTEN = {"kantservice": "Kantservice", "dach": "Dachsanierung", "pv": "Photovoltaik", "reparatur": "Reparatur", "wartung": "Wartung"}
STATUS_NEU = "neu"
STATUS = (STATUS_NEU,)  # W1b ergänzt übernommen und verworfen

NUMMER = re.compile(r"\A[A-Z]{1,3}-\d{8}-\d{4}-[0-9A-F]{4,8}\Z")
DATEINAME = re.compile(r"\A(?:anfrage\.pdf|foto-[1-9][0-9]?\.jpg)\Z")
ABLAGENAME = re.compile(r"\A[0-9a-f]{32}\.(?:pdf|jpg)\Z")
SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
ART_ZEICHEN = re.compile(r"\A[a-z_]{1,20}\Z")
FASSUNG_ZEICHEN = re.compile(r"\A[a-z0-9./_-]{1,40}\Z")
SCHLUESSEL_ZEICHEN = re.compile(r"\A[\x21-\x7e]{32,256}\Z")  # sichtbares ASCII ohne Leerzeichen: nie ein Zeilenumbruch in der Kopfzeile

# Grenzen (Fremddaten)
LISTE_MAX = 2_000_000          # Bytes einer Seite der Liste
UMSCHLAG_MAX = 512_000         # Bytes eines Umschlags (der Empfangsdienst nimmt höchstens 12 MiB an, der Text darin ist klein)
DATEI_MAX = 16 * 1024 * 1024   # Bytes je Datei (Empfangsdienst: PDF höchstens 8 MiB, Fotos höchstens 2048 px)
DATEIEN_MAX = 12               # Dateien je Anfrage (heute: PDF und bis zu 6 Fotos)
SUMME_MAX = 48 * 1024 * 1024   # Bytes aller Dateien einer Anfrage
TEILE_MAX = 20_000             # Teile eines JSON (Listen, Objekte, Werte)
SEITEN_MAX = 20                # Seiten der Liste je Lauf
SEITE = 100                    # Einträge je Seite
NEU_JE_LAUF = 50               # neue Anfragen je Lauf (Skript); der Knopf holt weniger
KNOPF_HOECHSTENS = 20          # „Jetzt abholen“ (seit 1.10.1): höchstens so viele neue …
KNOPF_FRIST = 40               # … und nach so vielen Sekunden keine neue mehr (die Seite wartet höchstens 60 s)
EINGANG_MAX = 500              # Zeilen der Liste des Eingangs (die neuesten)
ZEITLIMIT = 15                 # Sekunden je Aufruf
SPERRE_GILT = timedelta(minutes=10)

# Feste Texte -- nie mit Inhalten der Antwort oder dem Schlüssel
NICHT_EINGERICHTET = "Schnittstelle nicht eingerichtet"
NICHT_LOKAL = "Adresse der Schnittstelle nicht auf diesem Server -- nicht abgeholt"
NICHT_ERREICHBAR = "Empfangsdienst nicht erreichbar"
ABGELEHNT = "Empfangsdienst lehnt ab – Schlüssel prüfen"
UNLESBAR = "Antwort des Empfangsdienstes unlesbar"
UMLEITUNG = "Empfangsdienst leitet um – nicht gefolgt"

G_PRUEFSUMME = "Prüfsumme einer Datei stimmt nicht"
G_GROESSE = "Größe einer Datei stimmt nicht"
G_UNVOLLSTAENDIG = "Datei unvollständig übertragen"
G_ZU_GROSS = "Datei zu groß"
G_TYP = "Dateityp passt nicht zum Namen"
G_DATEI_FEHLT = "Datei fehlt beim Empfangsdienst"
G_NUMMER = "Nummer ungültig"
G_NUMMER_ANDERS = "Umschlag mit anderer Nummer"
G_UNLESBAR = "Umschlag unlesbar"
G_WEG = "Anfrage beim Empfangsdienst nicht mehr da"
G_ABLAGE = "Ablage gescheitert"

P_ART = "unbekannte Art"
P_FASSUNG = "unbekannte Fassung"
P_DATEIEN = "Angaben zu den Dateien ungültig"
P_EINGANG = "Eingang ungültig"
P_BETREFF = "Betreff zu lang oder ungültig"
P_NAME = "Name zu lang oder ungültig"
P_ART_NAME = "Name der Art zu lang oder ungültig"


class SchnittstellenFehler(Exception):
    """Der Lauf endet: der Text ist einer der festen Texte oben."""


class _Unlesbar(Exception):
    pass


class _DateiFehler(Exception):
    """Eine Datei stimmt nicht: die Anfrage wird nicht abgelegt und nicht gemeldet."""


class _KeineUmleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 -- urllib-Schnittstelle
        raise SchnittstellenFehler(UMLEITUNG)


def _oeffner() -> urllib.request.OpenerDirector:
    """Ohne Proxy (http_proxy aus der Umgebung bekäme sonst jeden Aufruf samt Schlüssel) und ohne Umleitung -- je Aufruf neu gebaut, damit kein
    früher gelesener Stand der Umgebung gilt."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _KeineUmleitung())


@dataclass(frozen=True)
class Verbindung:
    basis: str
    schluessel: str = field(repr=False)


def adresse_pruefen(adresse: str) -> str | None:
    """Die Adresse der Schnittstelle, wenn sie auf diesem Server liegt (http, 127.0.0.1/localhost/::1, ohne Benutzer, Pfad, Abfrage) -- sonst None."""
    try:
        teile = urllib.parse.urlsplit(adresse.strip())
        port = teile.port
    except ValueError:
        return None
    if teile.scheme != "http" or teile.hostname not in LOKALE_HOSTS or teile.username or teile.password:
        return None
    if teile.path not in ("", "/") or teile.query or teile.fragment:
        return None
    host = f"[{teile.hostname}]" if ":" in teile.hostname else teile.hostname
    return f"http://{host}" + (f":{port}" if port else "")


def verbindung() -> tuple[Verbindung | None, str | None]:
    """(Verbindung, None) oder (None, Grund) -- der Grund ist ein fester Text."""
    schluessel = os.environ.get(SCHLUESSEL_VARIABLE, "").strip()
    if not schluessel or not SCHLUESSEL_ZEICHEN.match(schluessel):
        return None, NICHT_EINGERICHTET
    basis = adresse_pruefen(os.environ.get(ADRESSE_VARIABLE) or ADRESSE_VORGABE)
    if basis is None:
        return None, NICHT_LOKAL
    return Verbindung(basis, schluessel), None


def eingerichtet() -> bool:
    return verbindung()[0] is not None


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Aufrufe
# ---------------------------------------------------------------------------------------------------------------------------------------------

def _anfrage(v: Verbindung, methode: str, pfad: str, koerper: dict | None = None) -> urllib.request.Request:
    kopf = {"Authorization": "Bearer " + v.schluessel, "Accept": "application/json"}
    daten = None
    if koerper is not None:
        daten = json.dumps(koerper).encode("utf-8")
        kopf["Content-Type"] = "application/json"
    return urllib.request.Request(v.basis + pfad, data=daten, method=methode, headers=kopf)


def _lesen(antwort, hoechstens: int) -> bytes:
    laenge = antwort.headers.get("Content-Length")
    if laenge is not None and (not laenge.strip().isdigit() or int(laenge) > hoechstens):
        raise _Unlesbar()
    daten = antwort.read(hoechstens + 1)
    if len(daten) > hoechstens:
        raise _Unlesbar()
    return daten


def _aufruf(v: Verbindung, methode: str, pfad: str, hoechstens: int, koerper: dict | None = None) -> tuple[int, bytes]:
    """(Status, Inhalt). Ein HTTP-Fehler ist ein Status (Inhalt leer); nicht erreichbar oder abgebrochen: SchnittstellenFehler. Zu groß: _Unlesbar."""
    try:
        with _oeffner().open(_anfrage(v, methode, pfad, koerper), timeout=ZEITLIMIT) as antwort:
            return antwort.status, _lesen(antwort, hoechstens)
    except SchnittstellenFehler:
        raise
    except urllib.error.HTTPError as fehler:
        fehler.close()
        return fehler.code, b""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        raise SchnittstellenFehler(NICHT_ERREICHBAR) from None


def _teile(wert) -> int:
    """Zahl der Teile eines JSON, ohne Rekursion."""
    zahl, offen = 0, [wert]
    while offen:
        x = offen.pop()
        zahl += 1
        if zahl > TEILE_MAX:
            return zahl
        if isinstance(x, dict):
            offen.extend(x.values())
        elif isinstance(x, list):
            offen.extend(x)
    return zahl


def _json(daten: bytes):
    try:
        wert = json.loads(daten.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise _Unlesbar() from None
    if _teile(wert) > TEILE_MAX:
        raise _Unlesbar()
    return wert


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Sperre und Stand
# ---------------------------------------------------------------------------------------------------------------------------------------------

def _sperre_nehmen(db: Session, jetzt: datetime) -> str | None:
    kennung = uuid.uuid4().hex
    treffer = db.execute(sa_update(WebanfragenAbholung).where(
        WebanfragenAbholung.id == 1,
        or_(WebanfragenAbholung.lauf_seit.is_(None), WebanfragenAbholung.lauf_seit < jetzt - SPERRE_GILT),
    ).values(lauf_kennung=kennung, lauf_seit=jetzt)).rowcount
    db.commit()
    return kennung if treffer == 1 else None


def _sperre_freigeben(db: Session, kennung: str, werte: dict) -> None:
    db.execute(sa_update(WebanfragenAbholung).where(WebanfragenAbholung.id == 1, WebanfragenAbholung.lauf_kennung == kennung)
               .values(lauf_kennung=None, lauf_seit=None, **werte))
    db.commit()


def stand(db: Session, jetzt: datetime | None = None) -> dict:
    """Stand des Abholens für die Seite -- ohne Schlüssel und ohne Adresse."""
    jetzt = jetzt or datetime.utcnow()
    zeile = einzelzeile(db, WebanfragenAbholung)
    try:
        nicht = json.loads(zeile.nicht_abgeholt) if zeile.nicht_abgeholt else []
    except ValueError:
        nicht = []
    zaehler = dict(db.execute(select(WebAnfrage.status, func.count(WebAnfrage.id)).group_by(WebAnfrage.status)).all())
    return {
        "eingerichtet": eingerichtet(),
        "laeuft": zeile.lauf_seit is not None and zeile.lauf_seit >= jetzt - SPERRE_GILT,
        "letzter_lauf_am": zeile.letzter_lauf_am,
        "letzter_erfolg_am": zeile.letzter_erfolg_am,
        "letzter_fehler": zeile.letzter_fehler,
        "letzte_neu": zeile.letzte_neu,
        "nicht_abgeholt": nicht,
        "neu": zaehler.get(STATUS_NEU, 0),
        "spamverdacht": db.scalar(select(func.count(WebAnfrage.id)).where(WebAnfrage.status == STATUS_NEU, WebAnfrage.spamverdacht.is_(True))),
        "pruefen": db.scalar(select(func.count(WebAnfrage.id)).where(WebAnfrage.status == STATUS_NEU, WebAnfrage.pruefen_grund.is_not(None))),
    }


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Ablage
# ---------------------------------------------------------------------------------------------------------------------------------------------

def ablage_ordner() -> Path:
    ordner = data_dir() / "webanfragen"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def datei_pfad(datei: WebAnfrageDatei) -> Path:
    """Pfad einer abgelegten Datei -- nur für einen Namen, den abholen() vergeben hat."""
    if not ABLAGENAME.match(datei.gespeichert_als or ""):
        raise ValueError("ungültiger Ablagename")
    return ablage_ordner() / datei.gespeichert_als


def _datei_holen(v: Verbindung, nummer: str, angabe: dict, ordner: Path, geschrieben: list[Path]) -> dict:
    """Holt eine Datei, prüft Größe, Prüfsumme und Typ am Inhalt und legt sie unter einem zufälligen Namen ab. _DateiFehler, wenn sie nicht stimmt."""
    name = angabe["name"]
    erwartet = "application/pdf" if name.endswith(".pdf") else "image/jpeg"
    endung = "pdf" if name.endswith(".pdf") else "jpg"
    ablagename = f"{secrets.token_hex(16)}.{endung}"
    teil = ordner / (ablagename + ".teil")
    geschrieben.append(teil)
    pfad = f"/erp/v1/anfragen/{urllib.parse.quote(nummer, safe='')}/dateien/{urllib.parse.quote(name, safe='')}"
    pruef, groesse, kopf, angekuendigt = hashlib.sha256(), 0, b"", None
    try:
        with _oeffner().open(_anfrage(v, "GET", pfad), timeout=ZEITLIMIT) as antwort:
            laenge = antwort.headers.get("Content-Length")
            if laenge is not None and (not laenge.strip().isdigit() or int(laenge) > DATEI_MAX):
                raise _DateiFehler(G_ZU_GROSS)
            angekuendigt = int(laenge) if laenge is not None else None
            with open(teil, "wb") as ziel:
                while True:
                    stueck = antwort.read(65536)
                    if not stueck:
                        break
                    groesse += len(stueck)
                    if groesse > DATEI_MAX:
                        raise _DateiFehler(G_ZU_GROSS)
                    if len(kopf) < 64:
                        kopf += stueck[:64]
                    pruef.update(stueck)
                    ziel.write(stueck)
    except (_DateiFehler, SchnittstellenFehler):
        raise
    except urllib.error.HTTPError as fehler:
        fehler.close()
        raise _DateiFehler(G_DATEI_FEHLT) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        raise SchnittstellenFehler(NICHT_ERREICHBAR) from None
    if angekuendigt is not None and groesse < angekuendigt:
        raise _DateiFehler(G_UNVOLLSTAENDIG)  # Verbindung mitten in der Datei abgebrochen
    if groesse != angabe["bytes"]:
        raise _DateiFehler(G_GROESSE)
    if not secrets.compare_digest(pruef.hexdigest(), angabe["sha256"]):
        raise _DateiFehler(G_PRUEFSUMME)
    if typ_aus_inhalt(kopf) != erwartet:
        raise _DateiFehler(G_TYP)
    endgueltig = ordner / ablagename
    os.replace(teil, endgueltig)
    geschrieben.append(endgueltig)
    return {"name": name, "typ": erwartet, "groesse": groesse, "sha256": pruef.hexdigest(), "gespeichert_als": ablagename}


def _dateien_angaben(wert) -> list[dict] | None:
    """Die Dateien des Umschlags, geprüft -- None, wenn die Angaben nicht stimmen (dann in die Prüfliste, ohne Dateien)."""
    if wert is None:
        return []
    if not isinstance(wert, list) or len(wert) > DATEIEN_MAX:
        return None
    angaben, namen, summe = [], set(), 0
    for d in wert:
        if not isinstance(d, dict):
            return None
        name, sha, groesse = d.get("name"), d.get("sha256"), d.get("bytes")
        if not isinstance(name, str) or not DATEINAME.match(name) or name in namen:
            return None
        if not isinstance(sha, str) or not SHA256.match(sha):
            return None
        if isinstance(groesse, bool) or not isinstance(groesse, int) or not 0 < groesse <= DATEI_MAX:
            return None
        summe += groesse
        if summe > SUMME_MAX:
            return None
        namen.add(name)
        angaben.append({"name": name, "sha256": sha, "bytes": groesse})
    return angaben


def _text(wert, laenge: int) -> tuple[str | None, bool]:
    """(Text, gut): leer ist gut; zu lang, kein Text oder mit Steuerzeichen nicht."""
    if wert is None or wert == "":
        return None, True
    if not isinstance(wert, str) or len(wert) > laenge or any(ord(z) < 32 for z in wert):
        return None, False
    return wert.strip() or None, True


def _eingang(wert) -> datetime | None:
    if isinstance(wert, bool) or not isinstance(wert, int):
        return None
    if not 1_577_836_800 <= wert <= time.time() + 86_400:  # 2020 bis morgen
        return None
    return datetime.fromtimestamp(wert, tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------------------------------------------------------------------------

@dataclass
class Ergebnis:
    neu: int = 0
    gemeldet: int = 0
    pruefen: int = 0
    nicht_abgeholt: list[dict] = field(default_factory=list)
    fehler: str | None = None
    laeuft_schon: bool = False
    weitere: bool = False

    def als_dict(self) -> dict:
        return {"neu": self.neu, "gemeldet": self.gemeldet, "pruefen": self.pruefen, "nicht_abgeholt": self.nicht_abgeholt,
                "fehler": self.fehler, "laeuft_schon": self.laeuft_schon, "weitere": self.weitere}


def _melden(db: Session, v: Verbindung, zeile: WebAnfrage, erg: Ergebnis) -> None:
    pfad = f"/erp/v1/anfragen/{urllib.parse.quote(zeile.nummer, safe='')}/uebernommen"
    try:
        status, daten = _aufruf(v, "POST", pfad, 64_000, {"erp_id": f"eingang-{zeile.id}"})
        antwort = _json(daten) if status == 200 else None
        gut = isinstance(antwort, dict) and antwort.get("ok") is True
    except _Unlesbar:
        gut = False
    if gut:
        zeile.gemeldet_am = datetime.utcnow()
        db.commit()
        erg.gemeldet += 1


def _eine_holen(db: Session, v: Verbindung, nummer: str, erg: Ergebnis) -> WebAnfrage | None:
    """Holt eine Anfrage in den Eingang -- None, wenn sie nicht abgelegt wurde (Grund in erg.nicht_abgeholt)."""
    def nicht(grund: str) -> None:
        erg.nicht_abgeholt.append({"nummer": nummer, "grund": grund})

    try:
        status, daten = _aufruf(v, "GET", f"/erp/v1/anfragen/{urllib.parse.quote(nummer, safe='')}", UMSCHLAG_MAX)
        if status == 404:
            nicht(G_WEG)
            return None
        if status != 200:
            nicht(f"Empfangsdienst antwortet {int(status)}")
            return None
        umschlag = _json(daten)
    except _Unlesbar:
        nicht(G_UNLESBAR)
        return None
    if not isinstance(umschlag, dict):
        nicht(G_UNLESBAR)
        return None
    if umschlag.get("nr") != nummer:
        nicht(G_NUMMER_ANDERS)
        return None

    gruende: list[str] = []
    fassung = umschlag.get("schema")
    angaben: list[dict] = []
    if fassung != FASSUNG:
        gruende.append(P_FASSUNG)
    else:
        if umschlag.get("art") not in ARTEN:
            gruende.append(P_ART)
        geprueft = _dateien_angaben(umschlag.get("dateien"))
        if geprueft is None:
            gruende.append(P_DATEIEN)
        else:
            angaben = geprueft
    art = umschlag.get("art") if isinstance(umschlag.get("art"), str) and ART_ZEICHEN.match(umschlag.get("art")) else None
    art_name, gut = _text(umschlag.get("art_name"), 80)
    if not gut:
        gruende.append(P_ART_NAME)
    betreff, gut = _text(umschlag.get("betreff"), 255)
    if not gut:
        gruende.append(P_BETREFF)
    kontakt = umschlag.get("kontakt") if isinstance(umschlag.get("kontakt"), dict) else {}
    name, gut = _text(kontakt.get("name"), 255)
    if not gut:
        gruende.append(P_NAME)
    eingang_am = _eingang(umschlag.get("zeit"))
    if eingang_am is None:
        gruende.append(P_EINGANG)

    ordner = ablage_ordner()
    geschrieben: list[Path] = []
    try:
        dateien = [_datei_holen(v, nummer, a, ordner, geschrieben) for a in angaben]
        zeile = WebAnfrage(
            nummer=nummer, art=art, art_name=art_name,
            fassung=fassung if isinstance(fassung, str) and FASSUNG_ZEICHEN.match(fassung) else "unbekannt",
            eingang_am=eingang_am, betreff=betreff, kontakt_name=name, spamverdacht=umschlag.get("spamverdacht") is True,
            **_adresse_spalten(art if art in ARTEN else None, umschlag),
            pruefen_grund="; ".join(gruende) or None, umschlag=daten.decode("utf-8"), umschlag_sha256=hashlib.sha256(daten).hexdigest(),
            status=STATUS_NEU, dateien=[WebAnfrageDatei(**d) for d in dateien],
        )
        db.add(zeile)
        db.commit()
    except _DateiFehler as fehler:
        _wegraeumen(geschrieben)
        nicht(str(fehler))
        return None
    except IntegrityError:  # die Nummer ist schon da (ein anderer Weg war schneller)
        db.rollback()
        _wegraeumen(geschrieben)
        return db.scalar(select(WebAnfrage).where(WebAnfrage.nummer == nummer))
    except SchnittstellenFehler:
        db.rollback()
        _wegraeumen(geschrieben)
        raise
    except Exception:
        db.rollback()
        _wegraeumen(geschrieben)
        logger.exception("Webanfrage %s: Ablage gescheitert.", nummer)
        nicht(G_ABLAGE)
        return None
    erg.neu += 1
    if zeile.pruefen_grund:
        erg.pruefen += 1
    return zeile


def _adresse_spalten(art: str | None, umschlag: dict) -> dict:
    """Die Adresse des Objekts für die Spalten des Eingangs (seit 1.10.3) -- nur aus den strukturierten Angaben."""
    adresse = objekt_adresse(art, umschlag) or {}
    return {"objekt_strasse": adresse.get("strasse"), "objekt_plz": adresse.get("plz"), "objekt_ort": adresse.get("ort")}


def _wegraeumen(pfade: list[Path]) -> None:
    for pfad in pfade:
        try:
            pfad.unlink(missing_ok=True)
        except OSError:
            logger.warning("Webanfrage: Datei ließ sich nicht wegräumen.")


def _liste(wert) -> tuple[list, bool, str | None]:
    if not isinstance(wert, dict) or wert.get("ok") is not True or not isinstance(wert.get("anfragen"), list):
        raise _Unlesbar()
    naechste = wert.get("naechste")
    return wert["anfragen"], wert.get("weitere") is True, naechste if isinstance(naechste, str) and NUMMER.match(naechste) else None


def abholen(db: Session, *, hoechstens: int = NEU_JE_LAUF, frist_sekunden: float | None = None) -> Ergebnis:
    """Ein Lauf: Liste seitenweise, je neue Anfrage holen und ablegen, jede gelistete Anfrage, die schon im Eingang ist, (wieder) als übernommen melden.
    hoechstens: neue Anfragen je Lauf; frist_sekunden: danach keine neue mehr (der Knopf, damit die Seite nicht wartet)."""
    erg = Ergebnis()
    jetzt = datetime.utcnow()
    v, grund = verbindung()
    if v is None:
        erg.fehler = grund
        db.execute(sa_update(WebanfragenAbholung).where(WebanfragenAbholung.id == 1).values(letzter_lauf_am=jetzt, letzter_fehler=grund))
        db.commit()
        return erg
    kennung = _sperre_nehmen(db, jetzt)
    if kennung is None:
        erg.laeuft_schon = True
        return erg
    ende = time.monotonic() + frist_sekunden if frist_sekunden else None
    try:
        nach, gesehen = None, set()
        for _ in range(SEITEN_MAX):
            pfad = f"/erp/v1/anfragen?anzahl={SEITE}" + (f"&nach={urllib.parse.quote(nach, safe='')}" if nach else "")
            try:
                status, daten = _aufruf(v, "GET", pfad, LISTE_MAX)
                if status == 404:
                    raise SchnittstellenFehler(ABGELEHNT)
                if status != 200:
                    raise SchnittstellenFehler(f"Empfangsdienst antwortet {int(status)}")
                anfragen, weitere, nach = _liste(_json(daten))
            except _Unlesbar:
                raise SchnittstellenFehler(UNLESBAR) from None
            for eintrag in anfragen:
                nummer = eintrag.get("nr") if isinstance(eintrag, dict) else None
                if not isinstance(nummer, str) or not NUMMER.match(nummer):
                    erg.nicht_abgeholt.append({"nummer": None, "grund": G_NUMMER})
                    continue
                if nummer in gesehen:
                    continue
                gesehen.add(nummer)
                zeile = db.scalar(select(WebAnfrage).where(WebAnfrage.nummer == nummer))
                if zeile is None:
                    if erg.neu >= hoechstens or (ende is not None and time.monotonic() > ende):
                        erg.weitere = True
                        continue
                    zeile = _eine_holen(db, v, nummer, erg)
                if zeile is not None:
                    _melden(db, v, zeile, erg)
            if not weitere or nach is None:
                break
        else:
            erg.weitere = True
    except SchnittstellenFehler as fehler:
        erg.fehler = str(fehler)
    finally:
        db.rollback()
        _sperre_freigeben(db, kennung, {
            "letzter_lauf_am": datetime.utcnow(), "letzter_fehler": erg.fehler, "letzte_neu": erg.neu,
            "nicht_abgeholt": json.dumps(erg.nicht_abgeholt[:50], ensure_ascii=False) if erg.nicht_abgeholt else None,
            **({"letzter_erfolg_am": datetime.utcnow()} if erg.fehler is None else {}),
        })
    if erg.fehler:
        logger.warning("Anfragen der Webseite: %s (%s neu, %s gemeldet).", erg.fehler, erg.neu, erg.gemeldet)
    else:
        logger.info("Anfragen der Webseite: %s neu, %s davon zu prüfen, %s gemeldet, %s nicht abgeholt%s.", erg.neu, erg.pruefen, erg.gemeldet,
                    len(erg.nicht_abgeholt), ", weitere offen" if erg.weitere else "")
    return erg


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Lesen (Eingang)
# ---------------------------------------------------------------------------------------------------------------------------------------------

def eingang(db: Session, anzahl: int = EINGANG_MAX) -> list[WebAnfrage]:
    """Die Liste des Eingangs (seit 1.10.1): die neuesten zuerst (Eingang, ohne Eingang am Ende), höchstens anzahl (bis EINGANG_MAX; die
    Startseite nimmt seit 1.10.2 die fünf neuesten)."""
    from sqlalchemy.orm import selectinload
    return list(db.scalars(select(WebAnfrage).options(selectinload(WebAnfrage.dateien))
                           .order_by(WebAnfrage.eingang_am.desc().nulls_last(), WebAnfrage.id.desc()).limit(min(anzahl, EINGANG_MAX))))


def zeile_zu_dict(zeile: WebAnfrage) -> dict:
    return {
        "id": zeile.id, "nummer": zeile.nummer, "art": zeile.art, "art_name": zeile.art_name or ARTEN.get(zeile.art or ""),
        "fassung": zeile.fassung, "eingang_am": zeile.eingang_am, "betreff": zeile.betreff, "kontakt_name": zeile.kontakt_name,
        "objekt_strasse": zeile.objekt_strasse, "objekt_plz": zeile.objekt_plz, "objekt_ort": zeile.objekt_ort,
        "spamverdacht": zeile.spamverdacht, "pruefen_grund": zeile.pruefen_grund, "status": zeile.status, "abgeholt_am": zeile.abgeholt_am,
        "gemeldet_am": zeile.gemeldet_am, "dateien": len(zeile.dateien),
    }
