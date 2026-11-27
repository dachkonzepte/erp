"""Kopien der freigegebenen Unterlagen für das Kundenportal (seit 1.11.33, Stufe P2b; Bauplan P2, B2 „Weg B“, B5, B6 und Nachtrag 3–4).

Das Portal liest nie eine Datei des ERP. Zu jeder Freigabe, die der Kunde sehen soll, legt der Postbote (Benutzer des ERP, app/portal_postbote.py) eine
Kopie in den Ordner PORTAL_DATEIEN (auf dem Server /srv/dk-portal/dateien, tobias:www-data 2750); nginx liefert sie aus, wenn das Portal es für eine
gültige Sitzung erlaubt (X-Accel-Redirect, ab 1.11.34). Hier:

- **abgleich()** (auf den Weckruf portal_freigabe und alle 15 Minuten): eine Kopie, die nicht mehr sein soll, geht (Zeile zuerst, dann die Datei); zu jeder
  Freigabe, die sein soll, ohne Kopie und ohne Fehler, entsteht eine; im vollen Lauf dazu: eine Zeile, deren Datei fehlt, verliert ihre Kopie (sie entsteht
  neu), und eine Datei ohne Zeile wird gelöscht. „Soll sein“: nicht zurückgenommen, Kunde nicht im Archiv, die Kette der Quelle führt heute zu diesem
  Kunden (portal_quelle(), dieselbe Funktion wie im Portal). Eine Rücknahme wirkt im Portal sofort (die Funktionen prüfen sie selbst), die Datei ist im
  nächsten Lauf weg.
- **Kopie**: ein PDF byte-gleich aus der Ablage (Prüfsumme der Ablage) bzw. aus dem Ordner der Art, die Kopie gegen die Quelle geprüft; ein Rasterbild
  (JPEG, PNG, WebP, GIF -- am Inhalt erkannt) neu kodiert in einem Kindprozess mit Grenzen für Speicher und Zeit (app/portal_foto_kind.py); alles andere
  „falscher_typ“. Name zufällig (32 Byte, hexadezimal) mit Endung .pdf bzw. .jpg, Datei 0640. Höchstens 25 MB je Quelle.
- **Fehler**: ein festes Wort an der Zeile (app/portal/werte.py::KOPIE_FEHLER), sonst nichts -- auch nicht im Protokoll (nur Nummer der Freigabe und
  Wort, Regel 18). Der Postbote versucht eine Zeile mit Fehler nicht von selbst noch einmal (das ERP setzt ihn ab P2c zurück).
- **Ein Ordner, eine Datenbank**: die Datei .datenbank im Ordner nennt Datenbank und Schema; passt sie nicht (oder liegen Kopien ohne sie da), legt und
  löscht der Postbote dort nichts (OrdnerFremd) -- ein zweiter Postbote mit demselben Ordner (etwa für die Spielwiese) löschte sonst die Kopien des ersten.

Nur PostgreSQL (portal_quelle(), portal_jetzt()). Zeit nur aus der Datenbank, wie in den Funktionen des Portals.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from .dateiauslieferung import typ_aus_inhalt
from .models import (ChecklistVersion, CustomerDocument, DefectFile, NoticeLetter, OrderAcceptanceFile, PortalFreigabe, ProjectDocument, PropertyDocument,
                     SentDocument, ServiceReport, ServiceReportPhoto)

logger = logging.getLogger(__name__)

UMGEBUNG = "PORTAL_DATEIEN"
KANAL = "portal_freigabe"          # NOTIFY des Auslösers an portal_freigaben (app/portal/weckruf.py)
HOECHSTENS_BYTES = 25 * 1024 * 1024  # je Quelle (Entscheidung P2-14)
ENDUNG = {"application/pdf": ".pdf", "image/jpeg": ".jpg"}
NAME = re.compile(r"^[0-9a-f]{64}\.(pdf|jpg)$")
BESITZER = ".datenbank"
TEIL = ".teil"
TEIL_ALT_SEKUNDEN = 3600           # ein Rest eines abgebrochenen Schreibens
JE_DURCHGANG = 50                  # Kopien je Abfrage; danach wieder Codes (der Postbote schickt auch die Anmeldecodes)
RASTER = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

# Kindprozess für Fotos (Nachtrag 4): Speicher (RLIMIT_AS bzw. Job-Objekt), Zeit, Bildpunkte, Kante und Qualität wie die Fotos des ERP (B5)
KIND = Path(__file__).with_name("portal_foto_kind.py")
# Grenze des Kinds (seit 1.11.35, bis 1.11.34 1 GiB -- mehr als die ganze Einheit): MemoryHigh der Einheit erp-portalpost (640M) minus POSTBOTE_RAUM. So
# scheitert das Kind an seiner eigenen Grenze, bevor die Einheit eng wird (über MemoryHigh bremst der Kernel jeden Prozess der Einheit, auch den Postboten
# beim Versand der Codes). tests/test_v826_portal_foto_vorrang.py hält beides gegen die Einheit; ändert sich MemoryHigh, ändert sich FOTO_SPEICHER mit.
POSTBOTE_RAUM = 192 * 1024 * 1024  # der Postbote selbst (auf dem Server rund 100 MB, S6) und eine PDF-Kopie bis 25 MB, zweimal im Speicher, mit Puffer
FOTO_SPEICHER = 448 * 1024 * 1024
FOTO_SEKUNDEN = 60
FOTO_PIXEL = 64_000_000
FOTO_KANTE = 1600
FOTO_QUALITAET = 82
KIND_WORT = {10: "nicht_lesbar", 11: "zu_gross"}  # jede andere Rückgabe (12 Speicher, 13 ohne Vorrang, Absturz, Zeit) ist „abbruch“

# „Soll eine Kopie haben“ -- dieselbe Kette wie portal_sichtbar() ohne die Kopie selbst; dazu der Kunde nicht im Archiv
_SOLL = ("f.zurueckgenommen_am IS NULL AND c.archiviert_am IS NULL "
         "AND EXISTS (SELECT 1 FROM portal_quelle(f.quelle, f.quelle_id) q WHERE q.kunde = f.customer_id)")


class OrdnerFremd(RuntimeError):
    """Der Ordner gehört einer anderen Datenbank (oder trägt Kopien ohne Kennung) -- hier wird nichts angelegt oder gelöscht."""


class QuelleFehlt(Exception):
    def __init__(self, wort: str):
        super().__init__(wort)
        self.wort = wort


@dataclass
class Stand:
    angelegt: int = 0
    fehler: dict = field(default_factory=dict)
    entfernt: int = 0
    nachgeholt: int = 0     # Zeile mit fehlender Datei, Kopie neu
    waisen: int = 0
    fremd: int = 0          # unbekannte Dateien im Ordner (nicht angefasst)
    mehr: bool = False      # es wartet noch Arbeit -- der Postbote kommt gleich wieder


def ordner_aus_umgebung(umgebung=os.environ) -> Path | None:
    wert = (umgebung.get(UMGEBUNG) or "").strip()
    return Path(wert) if wert else None


# --- Fotos -------------------------------------------------------------------------------------------------------------------------------------------

def _kind_umgebung() -> dict:
    """Nur, was ein Prozess zum Starten braucht -- keine Geheimnisse aus .env (DATABASE_URL, Schlüssel) in einen Prozess, der fremde Bilder liest."""
    umgebung = {"PATH": os.environ.get("PATH", "")}
    if sys.platform == "win32":
        umgebung["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return umgebung


def kind_befehl(speicher: int = FOTO_SPEICHER, pixel: int = FOTO_PIXEL) -> list[str]:
    """Der Aufruf des Kinds -- für foto_neu_kodieren() und das Prüfskript des Servers (scripts/pruefe_portal_foto.py) derselbe."""
    return [sys.executable, "-I", str(KIND), str(speicher), str(pixel), str(FOTO_KANTE), str(FOTO_QUALITAET)]


def foto_neu_kodieren(daten: bytes, *, speicher: int = FOTO_SPEICHER, sekunden: float = FOTO_SEKUNDEN, pixel: int = FOTO_PIXEL,
                      befehl: list[str] | None = None) -> bytes | str:
    """Das Foto als neues JPEG (bytes) oder ein Wort aus KOPIE_FEHLER. Der Kindprozess setzt seine Grenze für Speicher selbst; nach `sekunden` beendet
    ihn subprocess (kill). Ein Absturz oder die Zeitgrenze sind „abbruch“ -- der Aufrufer läuft weiter. `befehl` nur für Tests."""
    befehl = befehl or kind_befehl(speicher, pixel)
    try:
        lauf = subprocess.run(befehl, input=daten, capture_output=True, timeout=sekunden, env=_kind_umgebung(), check=False)
    except subprocess.TimeoutExpired:
        return "abbruch"
    except OSError:
        return "abbruch"
    if lauf.returncode != 0:
        return KIND_WORT.get(lauf.returncode, "abbruch")
    if typ_aus_inhalt(lauf.stdout) != "image/jpeg":
        return "abbruch"
    return lauf.stdout


# --- Quelle lesen --------------------------------------------------------------------------------------------------------------------------------------

def _ablage(db: Session, doc_id: int | None) -> bytes:
    from .sent_documents import ArchiveFileError, read_sent_document

    doc = db.get(SentDocument, doc_id) if doc_id is not None else None
    if doc is None:
        raise QuelleFehlt("fehlt")
    if (doc.size_bytes or 0) > HOECHSTENS_BYTES:
        raise QuelleFehlt("zu_gross")
    try:
        return read_sent_document(doc)
    except ArchiveFileError as e:
        raise QuelleFehlt("pruefsumme" if e.status == "abweichend" else "fehlt")


def _datei(wurzel: Path, pfad: Path) -> bytes:
    """Eine Datei unter `wurzel` -- ein Pfad, der hinauszeigt, gilt als fehlend."""
    try:
        echt = pfad.resolve(strict=True)
        if wurzel.resolve() not in echt.parents:
            raise QuelleFehlt("fehlt")
        if echt.stat().st_size > HOECHSTENS_BYTES:
            raise QuelleFehlt("zu_gross")
        return echt.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        raise QuelleFehlt("fehlt")


def _beleg(row) -> bytes:
    from .acceptances import AcceptanceFileError, read_acceptance_file

    if (row.size_bytes or 0) > HOECHSTENS_BYTES:
        raise QuelleFehlt("zu_gross")
    try:
        return read_acceptance_file(row)
    except AcceptanceFileError as e:
        raise QuelleFehlt("pruefsumme" if e.status == "abweichend" else "fehlt")


def quelle_lesen(db: Session, quelle: str, quelle_id: int) -> bytes:
    """Die Bytes der Quelle -- für die Dokumente aus der Ablage die feste Fassung (nie neu erzeugt), sonst die gespeicherte Datei. QuelleFehlt mit Wort."""
    from .sent_documents import frozen_version

    if quelle == "sent_documents":
        return _ablage(db, quelle_id)
    if quelle in ("invoices", "reminders"):
        doc = frozen_version(db, "rechnung" if quelle == "invoices" else "mahnung", quelle_id)
        return _ablage(db, doc.id if doc is not None else None)
    if quelle == "service_reports":
        bericht = db.get(ServiceReport, quelle_id)
        return _ablage(db, bericht.pdf_document_id if bericht is not None else None)
    if quelle == "checklist_versions":
        fassung = db.get(ChecklistVersion, quelle_id)
        return _ablage(db, fassung.sent_document_id if fassung is not None else None)
    if quelle == "notice_letters":
        brief = db.get(NoticeLetter, quelle_id)
        return _ablage(db, brief.sent_document_id if brief is not None else None)
    if quelle == "service_report_photos":
        from .service_report_photos import PHOTO_ROOT, photo_path
        foto = db.get(ServiceReportPhoto, quelle_id)
        if foto is None:
            raise QuelleFehlt("fehlt")
        return _datei(PHOTO_ROOT, photo_path(foto.file_path))
    if quelle == "customer_documents":
        from .customer_documents import CUSTOMER_ROOT, document_path
        row = db.get(CustomerDocument, quelle_id)
        if row is None:
            raise QuelleFehlt("fehlt")
        return _datei(CUSTOMER_ROOT, document_path(row))
    if quelle == "project_documents":
        from .project_documents import PROJECT_ROOT, document_path
        row = db.get(ProjectDocument, quelle_id)
        if row is None:
            raise QuelleFehlt("fehlt")
        return _datei(PROJECT_ROOT, document_path(row))
    if quelle == "property_documents":
        from .property_documents import PROPERTY_ROOT, document_path
        row = db.get(PropertyDocument, quelle_id)
        if row is None:
            raise QuelleFehlt("fehlt")
        return _datei(PROPERTY_ROOT, document_path(row))
    if quelle in ("defect_files", "order_acceptance_files"):
        row = db.get(DefectFile if quelle == "defect_files" else OrderAcceptanceFile, quelle_id)
        if row is None:
            raise QuelleFehlt("fehlt")
        return _beleg(row)
    raise QuelleFehlt("falscher_typ")  # eine Quelle ohne Zweig hier -- der Wächter in tests/test_v823 verlangt jede aus FREIGABE_QUELLEN


def kopie_inhalt(daten: bytes, *, foto=foto_neu_kodieren) -> tuple[bytes, str] | str:
    """(Inhalt, Typ) der Kopie oder ein Wort aus KOPIE_FEHLER. Den Typ bestimmt der Inhalt, nie ein Name oder eine gespeicherte Angabe."""
    typ = typ_aus_inhalt(daten)
    if typ == "application/pdf":
        return daten, typ
    if typ in RASTER:
        ergebnis = foto(daten)
        return (ergebnis, "image/jpeg") if isinstance(ergebnis, bytes) else ergebnis
    return "falscher_typ"


# --- Ordner ----------------------------------------------------------------------------------------------------------------------------------------

def kennung(db: Session) -> str:
    return db.scalar(text("SELECT current_database() || '/' || current_schema()"))


def besitzer_pruefen(db: Session, ordner: Path) -> None:
    """Der Ordner gehört dieser Datenbank (Datei .datenbank) -- ohne Kennung und ohne Kopien wird sie angelegt; sonst OrdnerFremd."""
    soll = kennung(db)
    datei = ordner / BESITZER
    try:
        ist = datei.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        if any(NAME.match(p.name) for p in ordner.iterdir()):
            raise OrdnerFremd("Kopien ohne Kennung im Ordner")
        fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(soll + "\n")
        return
    if ist != soll:
        raise OrdnerFremd("Der Ordner gehört einer anderen Datenbank")


def _schreiben(ordner: Path, inhalt: bytes, typ: str) -> tuple[str, str]:
    """Exklusiv in eine Teil-Datei, dann umbenannt; gegengelesen. (Name, SHA-256)."""
    name = secrets.token_hex(32) + ENDUNG[typ]
    teil = ordner / f".{name}{TEIL}"
    ziel = ordner / name
    sha = hashlib.sha256(inhalt).hexdigest()
    fd = os.open(teil, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o640)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(inhalt)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(teil, 0o640)
        os.replace(teil, ziel)
    except BaseException:
        teil.unlink(missing_ok=True)
        raise
    if hashlib.sha256(ziel.read_bytes()).hexdigest() != sha:
        ziel.unlink(missing_ok=True)
        raise OSError("Die Kopie stimmt nicht mit der Quelle überein.")
    return name, sha


def _loeschen(ordner: Path, name: str) -> None:
    if NAME.match(name or ""):
        (ordner / name).unlink(missing_ok=True)


# --- Abgleich ------------------------------------------------------------------------------------------------------------------------------------------

def _entfernen(db: Session, ordner: Path, ids: list[int]) -> int:
    """Kopie weg: zuerst die Zeile (committet), dann die Datei -- bricht es dazwischen ab, ist die Datei eine Waise (voller Lauf)."""
    if not ids:
        return 0
    # die Namen vor dem Ändern lesen (unter Sperre): RETURNING gäbe den neuen Wert zurück, also keinen
    zeilen = db.execute(select(PortalFreigabe.id, PortalFreigabe.kopie_name)
                        .where(PortalFreigabe.id.in_(ids), PortalFreigabe.kopie_name.is_not(None)).order_by(PortalFreigabe.id).with_for_update()).all()
    if not zeilen:
        db.rollback()
        return 0
    db.execute(update(PortalFreigabe).where(PortalFreigabe.id.in_([z.id for z in zeilen]))
               .values(kopie_name=None, kopie_typ=None, kopie_groesse=None, kopie_sha256=None, kopie_bereit_am=None)
               .execution_options(synchronize_session=False))
    db.commit()
    namen = [z.kopie_name for z in zeilen]
    for name in namen:
        _loeschen(ordner, name)
    return len(namen)


def _anlegen(db: Session, ordner: Path, freigabe_id: int, stand: Stand, foto) -> None:
    f = db.get(PortalFreigabe, freigabe_id)
    quelle, quelle_id = f.quelle, f.quelle_id
    try:
        daten = quelle_lesen(db, quelle, quelle_id)
    except QuelleFehlt as e:
        daten = e.wort
    except OSError as e:  # etwa keine Rechte an der Datei: fest „nicht_lesbar“, sonst bliebe jeder Lauf an dieser Zeile hängen
        logger.warning("Quelle der Freigabe %s nicht lesbar (%s)", freigabe_id, type(e).__name__)
        daten = "nicht_lesbar"
    db.rollback()  # keine Transaktion offen, während ein Foto neu kodiert wird (bis zu einer Minute)
    ergebnis = daten if isinstance(daten, str) else kopie_inhalt(daten, foto=foto)
    del daten
    bedingung = (PortalFreigabe.id == freigabe_id, PortalFreigabe.zurueckgenommen_am.is_(None), PortalFreigabe.kopie_name.is_(None),
                 PortalFreigabe.kopie_fehler.is_(None))
    if isinstance(ergebnis, str):
        db.execute(update(PortalFreigabe).where(*bedingung).values(kopie_fehler=ergebnis).execution_options(synchronize_session=False))
        db.commit()
        stand.fehler[ergebnis] = stand.fehler.get(ergebnis, 0) + 1
        logger.warning("Kopie der Freigabe %s nicht angelegt (%s)", freigabe_id, ergebnis)
        return
    inhalt, typ = ergebnis
    name, sha = _schreiben(ordner, inhalt, typ)
    geaendert = db.execute(update(PortalFreigabe).where(*bedingung)
                           .values(kopie_name=name, kopie_typ=typ, kopie_groesse=len(inhalt), kopie_sha256=sha, kopie_bereit_am=func.portal_jetzt())
                           .execution_options(synchronize_session=False)).rowcount
    if geaendert != 1:  # inzwischen zurückgenommen oder schon erledigt
        db.rollback()
        _loeschen(ordner, name)
        return
    db.commit()
    stand.angelegt += 1


def abgleich(db: Session, ordner: Path, *, voll: bool = False, sekunden: float = 5.0, foto=foto_neu_kodieren) -> Stand:
    """Ein Durchgang (siehe oben). Höchstens `sekunden` Arbeit an neuen Kopien -- bleibt etwas übrig, Stand.mehr. Committet je Schritt."""
    stand = Stand()
    besitzer_pruefen(db, ordner)
    db.rollback()
    weg = db.execute(text(f"SELECT f.id FROM portal_freigaben f JOIN customers c ON c.id = f.customer_id "
                          f"WHERE f.kopie_name IS NOT NULL AND NOT ({_SOLL}) ORDER BY f.id")).scalars().all()
    db.rollback()
    stand.entfernt = _entfernen(db, ordner, list(weg))
    if voll:
        fehlend = [i for i, name in db.execute(select(PortalFreigabe.id, PortalFreigabe.kopie_name)
                                               .where(PortalFreigabe.kopie_name.is_not(None)).order_by(PortalFreigabe.id)).all()
                   if not (ordner / name).is_file()]
        db.rollback()
        stand.nachgeholt = _entfernen(db, ordner, fehlend)
    ende = time.monotonic() + sekunden
    while True:
        ids = db.execute(text(f"SELECT f.id FROM portal_freigaben f JOIN customers c ON c.id = f.customer_id "
                              f"WHERE f.kopie_name IS NULL AND f.kopie_fehler IS NULL AND {_SOLL} ORDER BY f.id LIMIT :n"),
                         {"n": JE_DURCHGANG}).scalars().all()
        db.rollback()
        if not ids:
            break
        for freigabe_id in ids:
            if time.monotonic() >= ende:
                stand.mehr = True
                break
            _anlegen(db, ordner, freigabe_id, stand, foto)
        if stand.mehr:
            break
    if voll:
        bekannt = set(db.scalars(select(PortalFreigabe.kopie_name).where(PortalFreigabe.kopie_name.is_not(None))
                                 .order_by(PortalFreigabe.id)).all())  # Menge: Reihenfolge egal
        db.rollback()
        jetzt = time.time()
        for p in ordner.iterdir():
            if p.name == BESITZER:
                continue
            if NAME.match(p.name):
                if p.name not in bekannt:
                    p.unlink(missing_ok=True)
                    stand.waisen += 1
            elif p.name.startswith(".") and p.name.endswith(TEIL):
                if jetzt - p.stat().st_mtime > TEIL_ALT_SEKUNDEN:
                    p.unlink(missing_ok=True)
                    stand.waisen += 1
            else:
                stand.fremd += 1
        if stand.fremd:
            logger.warning("Im Ordner der Kopien liegen %s fremde Dateien (nicht angefasst)", stand.fremd)
    return stand

