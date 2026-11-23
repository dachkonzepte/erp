"""Archivschutz: ein Vorgang im Archiv ist nur lesbar (seit 1.10.23, Antwort F10 vom 23.11.2026; docs/archiv/webseite-und-kundenportal.md, „Umsetzung 1.10.23“).

Im Archiv (app/aufbewahrung.py) ist ein Kunde oder eine Anfrage mit archiviert_am und ein Projekt, das archiviert ist und keinen Auftrag hat -- wie die Suche
(app/search.py::_projekt_nicht_im_archiv()) und die Hinweise seit 1.10.18; ein archiviertes Projekt mit Auftrag ist nicht im Archiv der Aufbewahrung. Der
Eingang der Webseite ist seit 1.10.11 geschützt (jede Aktion ein bedingtes UPDATE mit archiviert_am IS NULL, app/webanfragen.py::_aendern()) und steht hier
nicht.

Der Server lehnt jede Änderung an einem Vorgang im Archiv mit 409 ab -- in zwei Stufen:

    vorab     die Router der Vorgänge prüfen vor dem Endpunkt jede schreibende Anfrage, deren Pfad einen Teil eines Vorgangs im Archiv nennt (archiv_vorab(),
              je Router die Zuordnung Pfadparameter -> Tabelle) -- 409, bevor eine Datei geschrieben oder gelöscht oder eine Mail gesendet ist
    Sitzung   jeder Flush (before_flush, vor dem Änderungsprotokoll): jede neue, geänderte oder gelöschte Zeile eines Teils (TEILE) eines Vorgangs im Archiv;
              jeder neu gesetzte Verweis einer anderen Tabelle auf einen Teil eines Vorgangs im Archiv (Aufgabe, Termin, Auftrag, Zahlung, Adressbuch …) -- 409.
              Wer schon auf ihn zeigt, bleibt änderbar (eine Aufgabe, ein Termin im Kalender, eine Eingangsrechnung).

Erlaubt bleibt einzig das Zurückholen: an der Wurzel (Kunde, Projekt, Anfrage) ändern sich dabei nur die Spalten des Archivs (ARCHIV_SPALTEN) -- auch das
Archivieren und Entarchivieren von Hand im „⋮“ der Akte (app/projects.py::set_project_archived()); die Aufbewahrung selbst schreibt mit Core-UPDATEs, die nicht
über den Flush laufen.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import event, exists, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session
from sqlalchemy.orm.interfaces import MANYTOONE

from .database import get_db

# Die Wurzeln eines Vorgangs und ihre Art
WURZELN = {"customers": "kunde", "projects": "projekt", "inquiries": "anfrage"}

# Die Teile eines Vorgangs: die Wurzeln und was an ihnen hängt (Fremdschlüssel NOT NULL). Jede andere Tabelle mit einem Fremdschlüssel NOT NULL auf einen
# Teil steht in tests/test_v793_archivschutz.py::KEIN_TEIL mit Grund (z. B. ein Auftrag: ein Projekt mit Auftrag ist nicht im Archiv).
TEILE = frozenset({
    "customers", "customer_profiles", "customer_extra_infos", "customer_documents",
    "properties", "property_documents", "roof_areas", "roof_layers", "roof_components",
    "projects", "project_profiles", "project_documents", "project_participants",
    "quotes", "quote_items", "quote_sections", "quote_document_meta", "quote_employee_assignments", "quote_item_calculations", "quote_item_layouts",
    "quote_item_material_calculations",
    "inquiries", "kontaktvermerke",
})

# An der Wurzel ändert das Archivieren und Zurückholen nur diese Spalten
ARCHIV_SPALTEN = frozenset({"archived", "archiviert_am", "archiviert_von_user_id", "zurueckgeholt_am", "updated_at"})

MELDUNGEN = {
    "projekt": "Das Projekt ist im Archiv – nur zum Ansehen. Zum Ändern erst zurückholen.",
    "anfrage": "Die Anfrage ist im Archiv – nur zum Ansehen. Zum Ändern erst zurückholen.",
    "kunde": "Der Kunde ist im Archiv – nur zum Ansehen. Zum Ändern erst zurückholen.",
}
REIHENFOLGE = ("projekt", "anfrage", "kunde")  # welche Meldung, wenn mehrere Wurzeln im Archiv sind

# Schreibende Routen der Router mit archiv_vorab(), die trotzdem durchgehen: das Zurückholen (Entarchivieren im „⋮“ der Akte)
ZURUECKHOLEN = frozenset({"/api/projects/{project_id}/unarchive"})

INT4_MAX = 2_147_483_647


class ImArchiv(HTTPException):
    """409 mit der Meldung der Art -- als HTTPException, damit jede App (auch eine Test-App) sie ohne eigenen Handler als 409 beantwortet, auch aus dem
    Flush heraus."""

    def __init__(self, art: str):
        super().__init__(status_code=409, detail=MELDUNGEN[art])
        self.art = art


def _tabellen():
    from .database import Base
    return Base.metadata.tables


@lru_cache(maxsize=1)
def verweise() -> dict[str, tuple[tuple[str, str], ...]]:
    """Je Tabelle die Spalten mit Fremdschlüssel auf einen Teil: ((spalte, zieltabelle), …) -- aus den Fremdschlüsseln des Modells."""
    aus = {}
    for name, tabelle in _tabellen().items():
        paare = tuple(sorted({(fk.parent.name, fk.column.table.name) for fk in tabelle.foreign_keys if fk.column.table.name in TEILE}))
        if paare:
            aus[name] = paare
    return aus


class Pruefer:
    """Löst Zeilen zu den Wurzeln ihres Vorgangs auf und prüft, ob eine im Archiv ist -- je Flush bzw. Anfrage ein Pruefer, jede Zeile einmal gelesen."""

    def __init__(self, db: Session):
        self.db = db
        self._wurzeln: dict[tuple[str, int], frozenset] = {}
        self._archiv: dict[tuple[str, int], bool] = {}

    def wurzeln(self, tabelle: str, kennung: int) -> frozenset:
        schluessel = (tabelle, kennung)
        if schluessel in self._wurzeln:
            return self._wurzeln[schluessel]
        self._wurzeln[schluessel] = frozenset()  # gegen Kreise (quote_sections.parent_id)
        aus = {(WURZELN[tabelle], kennung)} if tabelle in WURZELN else set()
        spalten = verweise().get(tabelle, ())
        if spalten and 0 < kennung <= INT4_MAX:
            t = _tabellen()[tabelle]
            with self.db.no_autoflush:
                zeile = self.db.execute(select(*[t.c[s] for s, _ in spalten]).where(t.c.id == kennung)).first()
            if zeile is not None:
                for (_, ziel), wert in zip(spalten, zeile):
                    if wert is not None:
                        aus |= self.wurzeln(ziel, wert)
        self._wurzeln[schluessel] = frozenset(aus)
        return self._wurzeln[schluessel]

    def im_archiv(self, art: str, kennung: int) -> bool:
        schluessel = (art, kennung)
        if schluessel not in self._archiv:
            t = _tabellen()
            with self.db.no_autoflush:
                if art == "projekt":
                    p, o = t["projects"], t["orders"]
                    zeile = self.db.execute(select(p.c.archived, exists().where(o.c.project_id == p.c.id)).where(p.c.id == kennung)).first()
                    self._archiv[schluessel] = bool(zeile and zeile[0] and not zeile[1])
                else:
                    w = t["customers" if art == "kunde" else "inquiries"]
                    self._archiv[schluessel] = self.db.execute(select(w.c.archiviert_am).where(w.c.id == kennung)).scalar() is not None
        return self._archiv[schluessel]

    def pruefen(self, wurzeln) -> None:
        """ImArchiv (409), wenn eine der Wurzeln im Archiv ist."""
        arten = {art for art, kennung in wurzeln if self.im_archiv(art, kennung)}
        for art in REIHENFOLGE:
            if art in arten:
                raise ImArchiv(art)


def pruefen(db: Session, tabelle: str, kennung: int) -> None:
    """Für Wege, die vor dem Flush etwas tun, das sich nicht zurückrollen lässt (Datei, Mail): ImArchiv, wenn die Zeile zu einem Vorgang im Archiv gehört."""
    p = Pruefer(db)
    p.pruefen(p.wurzeln(tabelle, kennung))


def pruefen_dokument(db: Session, document_type: str, document_id: int) -> None:
    """Versandprotokoll (Zustellung nachtragen, Empfang bzw. unzustellbar, Klären): ein Dokument eines Vorgangs im Archiv -- ImArchiv, bevor ein Beleg in
    die Ablage geht. Heute ist das nur ein Angebot; jede andere Art hängt an einem Auftrag (ein Projekt mit Auftrag ist nie im Archiv)."""
    from .dispatch_documents import document_row
    zeile = document_row(db, document_type, document_id) if 0 < document_id <= INT4_MAX else None
    if zeile is None:
        return
    tabelle = zeile.__table__.name
    if tabelle in TEILE:
        pruefen(db, tabelle, zeile.id)
    elif getattr(zeile, "project_id", None) is not None:
        pruefen(db, "projects", zeile.project_id)


def archiv_vorab(*, monteurin: bool = False, **zuordnung: str):
    """Für APIRouter(dependencies=[archiv_vorab(customer_id="customers", …)]): jede schreibende Anfrage, deren Pfadparameter (Name -> Tabelle eines Teils)
    eine Zeile eines Vorgangs im Archiv nennt, endet vor dem Endpunkt mit 409 -- außer dem Zurückholen (ZURUECKHOLEN). Die Abhängigkeit des Routers läuft
    vor der Rollenprüfung des Endpunkts: auf Routen des Büros prüft sie die Monteurin nicht (sie bekommt dort weiter 403 und erfährt nicht, was im Archiv
    ist); monteurin=True für Routen, die die Monteurin selbst nutzt (Dokument am Objekt in /mobil)."""
    for tabelle in zuordnung.values():
        assert tabelle in TEILE, tabelle

    def _archiv_vorab(request: Request, db: Session = Depends(get_db, scope="function")):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        if getattr(request.scope.get("route"), "path", None) in ZURUECKHOLEN:
            return
        konto = getattr(request.state, "erp_user", None)
        if not monteurin and konto is not None and getattr(konto, "role", None) == "field":
            return
        p = Pruefer(db)
        wurzeln = set()
        for name, tabelle in zuordnung.items():
            wert = request.path_params.get(name)
            if wert is None:
                continue
            try:
                kennung = int(wert)
            except (TypeError, ValueError):
                continue
            if 0 < kennung <= INT4_MAX:  # sonst antwortet der Endpunkt 404 (app/ids.py)
                wurzeln |= p.wurzeln(tabelle, kennung)
        p.pruefen(wurzeln)

    _archiv_vorab.zuordnung = dict(zuordnung)  # für tests/test_v793_archivschutz.py
    _archiv_vorab.monteurin = monteurin
    return Depends(_archiv_vorab)


# --- Sitzung ----------------------------------------------------------------------------------------------------------------------------------------

def _werte(state, spalte: str, ziel: str, nur_neu: bool) -> list:
    """Die Werte einer Verweisspalte eines Objekts im Flush: nur_neu -- nur, was neu gesetzt ist (Anlegen, geänderter Verweis); sonst auch der alte Wert.
    Ein Verweis, der nur über die Beziehung gesetzt ist (Fremdschlüssel erst im Flush), kommt als Kennung bzw. als neues Objekt dazu."""
    mapper = state.mapper
    spalte_obj = mapper.local_table.c[spalte]
    try:
        schluessel = mapper.get_property_by_column(spalte_obj).key
    except Exception:  # Spalte ohne Attribut
        return []
    hist = state.attrs[schluessel].history
    if state.pending:
        werte = [getattr(state.obj(), schluessel)]
    elif nur_neu:
        werte = list(hist.added)
    else:
        werte = list(hist.added) + list(hist.deleted) + list(hist.unchanged)
        if not werte:
            werte = [getattr(state.obj(), schluessel)]  # abgelaufen: nachladen
    for rel in mapper.relationships:
        if rel.direction is not MANYTOONE or spalte_obj not in rel.local_columns or rel.mapper.local_table.name != ziel:
            continue
        rhist = state.attrs[rel.key].history
        objekte = list(rhist.added) + ([] if nur_neu and not state.pending else list(rhist.deleted) + list(rhist.unchanged))
        for o in objekte:
            if o is None:
                continue
            ostate = sa_inspect(o)
            werte.append(ostate.identity[0] if ostate.identity else o)
    return [w for w in werte if w is not None]


def _wurzeln_des_objekts(p: Pruefer, obj, nur_neu: bool) -> set:
    state = sa_inspect(obj)
    tabelle = state.mapper.local_table.name
    aus = set()
    if tabelle in WURZELN and state.identity and not nur_neu:
        aus.add((WURZELN[tabelle], state.identity[0]))
    for spalte, ziel in verweise().get(tabelle, ()):
        for wert in _werte(state, spalte, ziel, nur_neu):
            if isinstance(wert, int):
                aus |= p.wurzeln(ziel, wert)
            elif wert is not obj:
                aus |= _wurzeln_des_objekts(p, wert, nur_neu=False)  # ein neues Objekt im selben Flush: seine Verweise
    return aus


def _nur_archivspalten(state) -> bool:
    geaendert = {a.key for a in state.mapper.column_attrs if state.attrs[a.key].history.has_changes()}
    return bool(geaendert) and geaendert <= ARCHIV_SPALTEN


ARCHIV_IN_DER_DATENBANK = (("customers", "archiviert_am"), ("inquiries", "archiviert_am"), ("projects", "archiviert_am"))


def _archivspalten_da(session: Session) -> bool:
    """Der Schutz braucht die Spalten des Archivs (Migration der Version 1.10.11). Auf einem älteren Stand -- eine Migration der Kette auf einer frischen
    Datenbank, eine Migrationsprobe (tests/test_v380_nummern_eindeutig.py) -- gibt es sie noch nicht; dann prüft er nichts, sonst bräche jeder Flush mit
    einer fehlenden Spalte ab. Einmal je Datenbankverbindung nachgesehen (Connection.info bleibt an der Verbindung des Pools)."""
    verbindung = session.connection()
    if "archivschutz" not in verbindung.info:
        try:
            pruefer = sa_inspect(verbindung)
            verbindung.info["archivschutz"] = all(spalte in {s["name"] for s in pruefer.get_columns(tabelle)}
                                                  for tabelle, spalte in ARCHIV_IN_DER_DATENBANK)
        except NoSuchTableError:
            verbindung.info["archivschutz"] = False
    return verbindung.info["archivschutz"]


def _vor_dem_flush(session: Session, flush_context, instances) -> None:
    if not (session.new or session.dirty or session.deleted):
        return
    tabellen = verweise()
    p = None
    wurzeln = set()
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        state = sa_inspect(obj)
        tabelle = state.mapper.local_table.name
        teil = tabelle in TEILE
        if not teil and tabelle not in tabellen:
            continue
        if p is None:
            if not _archivspalten_da(session):
                return
            p = Pruefer(session)
        if obj in session.new:
            wurzeln |= _wurzeln_des_objekts(p, obj, nur_neu=not teil)
        elif obj in session.deleted:
            if teil:
                wurzeln |= _wurzeln_des_objekts(p, obj, nur_neu=False)
        elif session.is_modified(obj, include_collections=False):
            if teil:
                if tabelle in WURZELN and _nur_archivspalten(state):
                    continue
                wurzeln |= _wurzeln_des_objekts(p, obj, nur_neu=False)
            else:
                wurzeln |= _wurzeln_des_objekts(p, obj, nur_neu=True)
    if wurzeln:
        p.pruefen(wurzeln)


# Vor dem Änderungsprotokoll (app/audit.py::collect_audit): eine abgelehnte Änderung merkt dort nichts vor
event.listen(Session, "before_flush", _vor_dem_flush, insert=True)
