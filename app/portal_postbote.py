"""Der Postbote des Kundenportals (seit 1.11.6, Stufe P1c; Bauplan P1, Abschnitt 1.1 und 3.2) -- ein Dienst unter dem Benutzer des ERP (erp-portalpost).

Das Portal fordert einen Anmeldecode nur an: portal_code_anfordern() legt einen Auftrag in portal_post und weckt mit NOTIFY portal_post (ohne Inhalt).
Der Postbote
1. hört mit LISTEN auf den Kanal (nur ein Weckruf -- er liest die Aufträge selbst) und schaut ohne Weckruf jede Minute nach;
2. nimmt je Auftrag die Zeile mit FOR UPDATE SKIP LOCKED, sperrt Zugang und Sitzung in der Reihenfolge der Funktionen (Zugang -> Sitzung -> Code) und
   prüft ein zweites Mal: Auftrag höchstens 10 Minuten alt, Zugang gilt (portal_zugang_grund()), Sitzung unbestätigt und gültig, Grenzen an den
   gesendeten Codes -- je Zugang 3 je 15 Minuten und 10 je Tag, gesamt 200 je Stunde. Sonst „verworfen“ mit festem Text;
3. erzeugt den Code, speichert nur den Prüfwert (frühere Codes der Sitzung gelten nicht mehr), schickt ihn über app/portal_mails.py::senden()
   (Microsoft 365, ohne „Gesendete Elemente“) und hält das Ergebnis am Auftrag und im Zugriffsprotokoll fest. Scheitert der Versand, gilt der Code nicht;
4. räumt auf (beim Start, danach stündlich): Codes 24 Stunden nach dem Anlegen, Sitzungen 30 Tage nach ihrem Ende (mit ihnen ihre Codes und Aufträge),
   Bremsen 48 Stunden nach ihrem Fenster, das Zugriffsprotokoll nach 24 Monaten (P1-2);
5. seit 1.11.33 (Stufe P2b): gleicht die Kopien der freigegebenen Unterlagen ab (app/portal_kopien.py) -- auf den Weckruf portal_freigabe (LISTEN, der
   Auslöser an portal_freigaben, app/portal/weckruf.py), beim Start und danach alle 15 Minuten voll. Je Durchgang höchstens wenige Sekunden an neuen
   Kopien, dann wieder die Codes; bleibt etwas übrig, kommt er ohne Warten wieder. Ohne Ordner (PORTAL_DATEIEN nicht gesetzt) keine Kopien, die Codes gehen
   weiter. Ein Fehler am Ordner (fehlt, keine Rechte, gehört einer anderen Datenbank) beendet den Postboten nicht: protokolliert (nur die Klasse), nächster
   Versuch im nächsten vollen Lauf.
6. seit 1.11.37 (Stufe P2c): wendet im vollen Lauf (beim Start, danach alle 15 Minuten) die automatischen Regeln an (app/portal_freigaben.py::regeln_alle(),
   Bauplan P2, B4.3) -- für jeden Kunden mit Portal an; neue Zeilen wecken über den Auslöser die Kopien. Ein Fehler darin beendet den Postboten nicht (die
   Codes gehen vor): nur die Klasse ins Protokoll, nächster Versuch im nächsten vollen Lauf.
7. seit 1.11.41 (Stufe P2d): rechnet das Schaufenster (Zahlstand, Termine) jedes Kunden mit Portal neu (app/portal_schaufenster.py::alle()) -- auf den
   Weckruf portal_schaufenster (LISTEN; Auslöser an den Tabellen aus app/portal/weckruf.py::TABELLEN_SCHAUFENSTER) und den der Freigaben, beim Start und
   alle 15 Minuten. Ein
   Fehler darin beendet den Postboten nicht (nur die Klasse ins Protokoll).

Genau ein Postbote: er hält eine Sperre der Datenbank (pg_try_advisory_lock je Schema -- auf dem Server eines, in Tests jedes Wegwerf-Schema für
sich) -- ein zweiter bricht ab. Ein Auftrag geht nie zweimal hinaus: der
Versandschlüssel ist „portal-code-<Auftrag>“; findet der Postbote ihn schon im Versandprotokoll (Abbruch mitten im Versand), übernimmt er dessen
Ergebnis und erzeugt keinen neuen Code. Nur PostgreSQL (LISTEN, SKIP LOCKED, die Funktionen des Portals). Zeit nur aus der Datenbank (portal_jetzt()),
wie in den Funktionen. Der Code steht nur in der Mail und kurz in einer Variablen -- nie in einer Tabelle, einem Protokoll oder einer Ausnahme; das
Protokoll nennt nur die Nummer des Auftrags und den Namen einer Ausnahme (Regel 18).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import delete, func, literal_column, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import portal_kopien, portal_mails
from .audit import record_audit_entry
from .email_dispatch import DispatchConflict
from .models import Customer, EmailDispatch, PortalBremse, PortalCode, PortalPost, PortalSitzung, PortalZugang, PortalZugriff
from .portal import pruefwerte, weckruf

logger = logging.getLogger(__name__)

KANAL = "portal_post"            # wie pg_notify() in portal_code_anfordern()
SPERRE = 7311250                 # pg_try_advisory_lock(SPERRE, hashtext(Schema)): genau ein Postbote je Datenbank und Schema
NAME = "Postbote"                # „erstellt von“ im Versandprotokoll
AUFTRAG_HOECHSTENS = timedelta(minutes=10)
CODE_GUELTIG = timedelta(minutes=portal_mails.CODE_MINUTEN)
# (Fenster, Grenze, je Zugang) -- gezählt an den gesendeten Codes; dieselben Zahlen prüft portal_code_anfordern() an den Anforderungen
GRENZEN = ((timedelta(minutes=15), 3, True), (timedelta(days=1), 10, True), (timedelta(hours=1), 200, False))
NACHSEHEN_SEKUNDEN = 60
KOPIEN_VOLL_SEKUNDEN = 15 * 60    # seit 1.11.33: voller Abgleich der Kopien (Bauplan P2, B2.1)
KOPIEN_DURCHGANG_SEKUNDEN = 5.0   # Arbeit an neuen Kopien je Durchgang, dann wieder die Codes
STAU_NACH = timedelta(minutes=2)  # Hinweis auf „Start“ (seit 1.11.7)
AUFRAEUMEN_SEKUNDEN = 3600

# Fester Text am Auftrag (portal_post.fehler, höchstens 60 Zeichen) -> Ergebnis im Zugriffsprotokoll
ZU_ALT, SITZUNG_UNGUELTIG, GRENZE, ZUGANG = "Auftrag zu alt", "Sitzung gilt nicht mehr", "Grenze erreicht", "Zugang gilt nicht"
VERSAND, HAENGT = "Versand gescheitert", "Versand hängt -- im Versandprotokoll klären"


class AndererPostbote(RuntimeError):
    """Es läuft schon ein Postbote (die Sperre der Datenbank ist belegt)."""


def jetzt(db: Session) -> datetime:
    """Die Zeit der Datenbank (naiv UTC) -- dieselbe, mit der die Funktionen des Portals Codes prüfen."""
    return db.scalar(select(func.portal_jetzt()))


def _protokoll(db: Session, zugang_id: int, sitzung_id: int, aktion: str, ergebnis: str) -> None:
    db.execute(select(func.portal_protokoll(zugang_id, sitzung_id, aktion, ergebnis)))


def _abschliessen(db: Session, post_id: int, zugang_id: int, sitzung_id: int, status: str, fehler: str | None, dispatch_id: int | None,
                  ergebnis: str) -> None:
    """Auftrag erledigt (nur aus „wartet“), Eintrag im Zugriffsprotokoll, commit."""
    db.execute(update(PortalPost).where(PortalPost.id == post_id, PortalPost.status == "wartet")
               .values(status=status, fehler=fehler, email_dispatch_id=dispatch_id, erledigt_am=func.portal_jetzt())
               .execution_options(synchronize_session=False))
    _protokoll(db, zugang_id, sitzung_id, "code_gesendet" if status == "gesendet" else "code_fehler", ergebnis)
    db.commit()


def _grund(db: Session, post: PortalPost, sitzung: PortalSitzung | None, jetzt_: datetime) -> tuple[str, str] | None:
    """Die zweite Prüfung: (Ergebnis fürs Zugriffsprotokoll, fester Text am Auftrag) oder None, wenn der Code hinausgehen darf."""
    if post.angefordert_am < jetzt_ - AUFTRAG_HOECHSTENS:
        return "ungueltig", ZU_ALT
    grund = db.scalar(select(func.portal_zugang_grund(post.zugang_id)))
    if grund is not None:
        return grund, ZUGANG
    if (sitzung is None or sitzung.zugang_id != post.zugang_id or sitzung.beendet_am is not None or sitzung.bestaetigt_am is not None
            or sitzung.laeuft_ab <= jetzt_):
        return "ungueltig", SITZUNG_UNGUELTIG
    for fenster, grenze, je_zugang in GRENZEN:
        anzahl = select(func.count(PortalPost.id)).where(PortalPost.status == "gesendet", PortalPost.erledigt_am > jetzt_ - fenster)
        if je_zugang:
            anzahl = anzahl.where(PortalPost.zugang_id == post.zugang_id)
        if db.scalar(anzahl) >= grenze:
            return "bremse", GRENZE
    return None


def naechster(db: Session) -> int | None:
    """Einen wartenden Auftrag erledigen (der älteste, den kein anderer gerade hält); seine Nummer, None ohne wartenden Auftrag. Committet."""
    post = db.scalars(select(PortalPost).where(PortalPost.status == "wartet").order_by(PortalPost.id).limit(1)
                      .with_for_update(skip_locked=True)).first()
    if post is None:
        db.rollback()
        return None
    post_id, zugang_id, sitzung_id = post.id, post.zugang_id, post.sitzung_id
    schluessel = f"portal-code-{post_id}"
    vorhanden = db.scalars(select(EmailDispatch).where(EmailDispatch.dispatch_key == schluessel)).first()
    if vorhanden is not None:  # Abbruch mitten im Versand: dessen Ergebnis übernehmen -- nie ein zweiter Code, nie eine zweite Mail
        gesendet = vorhanden.status == "gesendet"
        _abschliessen(db, post_id, zugang_id, sitzung_id, "gesendet" if gesendet else "fehler", None if gesendet else HAENGT, vorhanden.id,
                      "ok" if gesendet else "ungueltig")
        return post_id
    db.execute(select(PortalZugang.id).where(PortalZugang.id == zugang_id).with_for_update(key_share=True))   # FOR NO KEY UPDATE
    sitzung = db.scalars(select(PortalSitzung).where(PortalSitzung.id == sitzung_id).with_for_update()).first()
    jetzt_ = jetzt(db)
    grund = _grund(db, post, sitzung, jetzt_)
    if grund is not None:
        _abschliessen(db, post_id, zugang_id, sitzung_id, "verworfen", grund[1], None, grund[0])
        return post_id

    zugang = db.get(PortalZugang, zugang_id)
    kunde = db.get(Customer, zugang.customer_id)
    code = pruefwerte.neuer_code()
    db.execute(update(PortalCode).where(PortalCode.sitzung_id == sitzung_id, PortalCode.verbraucht_am.is_(None), PortalCode.ersetzt_am.is_(None))
               .values(ersetzt_am=jetzt_).execution_options(synchronize_session=False))
    neu = PortalCode(sitzung_id=sitzung_id, pruefwert=pruefwerte.code(sitzung.wert_sha256, code), angelegt_am=jetzt_, gueltig_bis=jetzt_ + CODE_GUELTIG)
    db.add(neu)
    db.flush()
    code_id, an = neu.id, zugang.email
    html_ = portal_mails.code_html(db, kunde, code)
    del code
    try:
        # senden() committet den Code zusammen mit dem Eintrag „in Arbeit“ im Versandprotokoll -- vor dem Senden
        ergebnis = portal_mails.senden(db, art="portal_code", dokument_id=post_id, an=an, html_=html_, dispatch_key=schluessel, user_name=NAME)
    except (ValueError, DispatchConflict) as e:
        db.rollback()
        logger.warning("Postbote: Auftrag %s nicht gesendet (%s)", post_id, type(e).__name__)
        db.execute(update(PortalCode).where(PortalCode.id == code_id, PortalCode.ersetzt_am.is_(None)).values(ersetzt_am=func.portal_jetzt())
                   .execution_options(synchronize_session=False))  # nie hinausgegangen: der Code gilt nicht
        dispatch_id = db.scalar(select(EmailDispatch.id).where(EmailDispatch.dispatch_key == schluessel))
        _abschliessen(db, post_id, zugang_id, sitzung_id, "fehler", VERSAND, dispatch_id, "ungueltig")
        return post_id
    finally:
        del html_
    _abschliessen(db, post_id, zugang_id, sitzung_id, "gesendet", None, ergebnis.dispatch.id, "ok")
    logger.info("Postbote: Auftrag %s gesendet", post_id)
    return post_id


def alle(db: Session) -> int:
    """Alle wartenden Aufträge erledigen; ihre Zahl."""
    n = 0
    while naechster(db) is not None:
        n += 1
    return n


def aufraeumen(db: Session) -> dict[str, int]:
    """Löschen nach den Fristen (Bauplan P1, Abschnitt 6). Sitzungen gehen samt ihren Codes und Aufträgen (ON DELETE CASCADE); im Zugriffsprotokoll bleibt
    der Eintrag ohne Sitzung (SET NULL). Das Versandprotokoll bleibt (Regel 21). Committet."""
    j = jetzt(db)
    zahlen = {
        "codes": db.execute(delete(PortalCode).where(PortalCode.angelegt_am < j - timedelta(hours=24))).rowcount,
        "sitzungen": db.execute(delete(PortalSitzung).where(
            func.coalesce(PortalSitzung.beendet_am, PortalSitzung.laeuft_ab) < j - timedelta(days=30))).rowcount,
        "bremsen": db.execute(delete(PortalBremse).where(PortalBremse.fenster_beginn < j - timedelta(hours=48))).rowcount,
        "zugriffe": db.execute(delete(PortalZugriff).where(
            PortalZugriff.zeitpunkt < func.portal_jetzt() - literal_column("interval '24 months'"))).rowcount,
    }
    db.commit()
    return zahlen


def kopien(db: Session, ordner, *, voll: bool, sekunden: float = KOPIEN_DURCHGANG_SEKUNDEN, foto=None) -> bool:
    """Ein Abgleich der Kopien (seit 1.11.33); True, wenn noch Arbeit wartet. Ein Fehler am Ordner beendet den Postboten nicht (die Codes gehen vor):
    nur die Klasse ins Protokoll, False -- der nächste volle Lauf versucht es wieder. Ein Fehler der Datenbank geht weiter (Schleife endet, systemd)."""
    try:
        stand = portal_kopien.abgleich(db, ordner, voll=voll, sekunden=sekunden, **({"foto": foto} if foto else {}))
    except (OSError, portal_kopien.OrdnerFremd) as e:
        db.rollback()
        logger.error("Postbote: Kopien nicht abgeglichen (%s)", type(e).__name__)
        return False
    if stand.angelegt or stand.entfernt or stand.nachgeholt or stand.waisen or stand.fehler:
        logger.info("Postbote: Kopien angelegt %s, entfernt %s, nachgeholt %s, Waisen %s, Fehler %s", stand.angelegt, stand.entfernt, stand.nachgeholt,
                    stand.waisen, dict(sorted(stand.fehler.items())))
    return stand.mehr


def regeln(db: Session) -> None:
    """Die automatischen Regeln für jeden Kunden mit Portal an (seit 1.11.37). Ein Fehler darin beendet den Postboten nicht: nur die Klasse ins Protokoll."""
    from . import portal_freigaben

    try:
        stand = portal_freigaben.regeln_alle(db)
    except Exception as e:  # noqa: BLE001 -- die Codes gehen vor; der nächste volle Lauf versucht es wieder
        db.rollback()
        logger.error("Postbote: Regeln nicht angewandt (%s)", type(e).__name__)
        return
    if stand.neu or stand.ueberholt:
        logger.info("Postbote: Regeln -- %s neu freigegeben, %s überholt", stand.neu, stand.ueberholt)


def schaufenster(db: Session) -> None:
    """Das Schaufenster jedes Kunden mit Portal neu (seit 1.11.41). Ein Fehler darin beendet den Postboten nicht: nur die Klasse ins Protokoll."""
    from . import portal_schaufenster

    try:
        lauf = portal_schaufenster.alle(db)
    except Exception as e:  # noqa: BLE001 -- die Codes gehen vor; der nächste Weckruf bzw. volle Lauf versucht es wieder
        db.rollback()
        logger.error("Postbote: Schaufenster nicht gerechnet (%s)", type(e).__name__)
        return
    logger.debug("Postbote: Schaufenster -- %s Kunden, %s Zeilen geleert", lauf.kunden, lauf.geleert)


def laufen(engine: Engine, *, halt: Callable[[], bool] = lambda: False, nachsehen: float = NACHSEHEN_SEKUNDEN,
           aufraeumen_alle: float = AUFRAEUMEN_SEKUNDEN, ordner=None, kopien_voll_alle: float = KOPIEN_VOLL_SEKUNDEN, foto=None) -> None:
    """Die Schleife des Dienstes: Sperre nehmen (sonst AndererPostbote), LISTEN, dann je Weckruf oder spätestens nach `nachsehen` Sekunden alle
    wartenden Aufträge, dazu das Aufräumen und (seit 1.11.33, mit `ordner`) die Kopien: auf den Weckruf portal_freigabe, solange Arbeit wartet, und alle
    `kopien_voll_alle` Sekunden voll. Ein Fehler der Datenbank beendet die Schleife (systemd startet neu, Restart=always)."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as hoerer:
        if not hoerer.scalar(text("SELECT pg_try_advisory_lock(:k, hashtext(current_schema()))"), {"k": SPERRE}):
            raise AndererPostbote("Es läuft schon ein Postbote.")
        hoerer.exec_driver_sql(f"LISTEN {KANAL}")
        hoerer.exec_driver_sql(f"LISTEN {portal_kopien.KANAL}")
        hoerer.exec_driver_sql(f"LISTEN {weckruf.KANAL_SCHAUFENSTER}")  # seit 1.11.41
        roh = hoerer.connection.driver_connection
        logger.info("Postbote bereit (LISTEN %s, %s, %s)", KANAL, portal_kopien.KANAL, weckruf.KANAL_SCHAUFENSTER)
        if ordner is None:
            logger.warning("Postbote: PORTAL_DATEIEN nicht gesetzt -- keine Kopien für das Kundenportal")
        try:
            _schleife(engine, roh, halt=halt, nachsehen=nachsehen, aufraeumen_alle=aufraeumen_alle, ordner=ordner, kopien_voll_alle=kopien_voll_alle,
                      foto=foto)
        finally:  # seit 1.11.33: die Verbindung geht in den Pool zurück -- ohne Sperre und ohne LISTEN (sonst hielte sie beides weiter)
            try:
                hoerer.exec_driver_sql("UNLISTEN *")
                hoerer.execute(text("SELECT pg_advisory_unlock(:k, hashtext(current_schema()))"), {"k": SPERRE})
            except Exception:  # noqa: BLE001 -- eine abgerissene Verbindung hält ohnehin nichts mehr
                pass


def _schleife(engine: Engine, roh, *, halt, nachsehen, aufraeumen_alle, ordner, kopien_voll_alle, foto) -> None:
    """Die Arbeit von laufen() zwischen LISTEN und Ende."""
    zuletzt_aufgeraeumt = zuletzt_voll = zuletzt_regeln = None
    geweckt = mehr = schaufenster_geweckt = False
    while not halt():
        with Session(engine) as db:
            n = alle(db)
            if zuletzt_aufgeraeumt is None or time.monotonic() - zuletzt_aufgeraeumt >= aufraeumen_alle:
                zahlen = aufraeumen(db)
                zuletzt_aufgeraeumt = time.monotonic()
                logger.info("Postbote: aufgeräumt %s", zahlen)
            voller_lauf = zuletzt_regeln is None or time.monotonic() - zuletzt_regeln >= kopien_voll_alle
            if voller_lauf:  # seit 1.11.37: im vollen Lauf, vor den Kopien
                regeln(db)
                zuletzt_regeln = time.monotonic()
            if voller_lauf or schaufenster_geweckt or geweckt:  # seit 1.11.41: dazu auf den Weckruf des Schaufensters und der Freigaben
                schaufenster(db)
            if ordner is not None:
                voll = zuletzt_voll is None or time.monotonic() - zuletzt_voll >= kopien_voll_alle
                if voll or geweckt or mehr:
                    mehr = kopien(db, ordner, voll=voll, foto=foto)
                    if voll:
                        zuletzt_voll = time.monotonic()
        if n:
            logger.info("Postbote: %s Aufträge erledigt", n)
        geweckt = schaufenster_geweckt = False
        for nachricht in roh.notifies(timeout=0 if mehr else nachsehen, stop_after=1):
            geweckt = geweckt or nachricht.channel == portal_kopien.KANAL
            schaufenster_geweckt = schaufenster_geweckt or nachricht.channel == weckruf.KANAL_SCHAUFENSTER
        if geweckt or schaufenster_geweckt:  # seit 1.11.41: was schon wartet, gleich mit -- ein Lauf statt einer je Transaktion
            for nachricht in roh.notifies(timeout=0):
                geweckt = geweckt or nachricht.channel == portal_kopien.KANAL
                schaufenster_geweckt = schaufenster_geweckt or nachricht.channel == weckruf.KANAL_SCHAUFENSTER


# Seit 1.11.7: der Hinweis auf „Start“ (fester Text, die Oberfläche setzt ihn nur als Text)
STAU_TEXTE = {  # seit 1.11.9 (Antwort 1.11.7-3) für das Büro: den Dienst nennt nur der Text für den Admin
    "wartet": "Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte den Administrator informieren.",
    "fehler": "Kundenportal: Der letzte Anmeldecode ging nicht hinaus – bitte im Versandprotokoll nachsehen.",
}
STAU_TEXTE_ADMIN = {
    **STAU_TEXTE,
    "wartet": "Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte prüfen, ob der Postbote läuft (Dienst erp-portalpost).",
}
# „Erledigt“ in der Änderungshistorie (seit 1.11.9; erledigen() schreibt die Aktion wörtlich -- test_v732 prüft ihre Länge)
ERLEDIGT_AKTION = "Versandfehler erledigt"
ERLEDIGT_ART = "Kundenportal-Versand"
VERALTET = "Der Hinweis ist nicht mehr aktuell -- bitte die Seite neu laden."


class StauVeraltet(Exception):
    """„Erledigt“ an einem Auftrag, der nicht (mehr) der gezeigte Fehler ist (Router 409)."""


def stau_stand(db: Session, jetzt_: datetime) -> tuple[str | None, int | None]:
    """Für den Hinweis auf „Start“ (seit 1.11.7, Bauplan P1, Abschnitt 4): („wartet“, None), wenn ein Auftrag länger als 2 Minuten wartet; („fehler“,
    Auftrag), wenn der zuletzt versuchte Versand scheiterte und (seit 1.11.9) noch nicht erledigt ist -- ein verworfener Auftrag ist kein Versand und
    ändert daran nichts; sonst (None, None). jetzt_ in naivem UTC (app/berlin_time.py::utc_jetzt()). Liest nur."""
    wartet = db.scalar(select(PortalPost.id).where(PortalPost.status == "wartet", PortalPost.angefordert_am < jetzt_ - STAU_NACH)
                       .order_by(PortalPost.id).limit(1))
    if wartet is not None:
        return "wartet", None
    letzter = db.execute(select(PortalPost.id, PortalPost.status, PortalPost.quittiert_am)
                         .where(PortalPost.status.in_(("gesendet", "fehler")), PortalPost.erledigt_am.is_not(None))
                         .order_by(PortalPost.erledigt_am.desc().nulls_last(), PortalPost.id.desc()).limit(1)).first()
    if letzter is not None and letzter.status == "fehler" and letzter.quittiert_am is None:
        return "fehler", letzter.id
    return None, None


def stau(db: Session, jetzt_: datetime) -> str | None:
    """Nur der Grund aus stau_stand()."""
    return stau_stand(db, jetzt_)[0]


def erledigen(db: Session, post_id: int, *, jetzt_: datetime, user_id: int | None, user_name: str | None) -> None:
    """„Erledigt“ an dem gescheiterten Versand, den der Hinweis gerade zeigt (seit 1.11.9, Antwort 1.11.7-1): der Hinweis endet, bis ein neuer Fehler
    kommt. Nur dieser eine Auftrag -- ist inzwischen ein anderer der letzte Versand (oder wartet einer), StauVeraltet (die Seite zeigte einen alten
    Stand). Name und Zeit am Auftrag und in der Änderungshistorie, in einer Transaktion; committet."""
    grund, fehler_id = stau_stand(db, jetzt_)
    if grund != "fehler" or fehler_id != post_id:
        raise StauVeraltet(VERALTET)
    geaendert = db.execute(update(PortalPost).where(PortalPost.id == post_id, PortalPost.status == "fehler", PortalPost.quittiert_am.is_(None))
                           .values(quittiert_am=jetzt_, quittiert_von_user_id=user_id, quittiert_von_name=user_name or "System")
                           .execution_options(synchronize_session=False)).rowcount
    if geaendert != 1:  # zwei Klicks zugleich: nur einer erledigt
        db.rollback()
        raise StauVeraltet(VERALTET)
    record_audit_entry(db, action="Versandfehler erledigt", entity_type=ERLEDIGT_ART, entity_id=post_id, entity_label=f"Anmeldecode (Auftrag {post_id})",
                       actor_user_id=user_id, actor_name=user_name)
    db.commit()
