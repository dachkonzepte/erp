"""Freigaben fürs Kundenportal im ERP (seit 1.11.36, Stufe P2c; Bauplan P2, B4 und B9; Antworten des Betriebs vom 26. und 27.11.2026).

Was der Kunde sieht, steht als Zeile in portal_freigaben (app/models.py::PortalFreigabe). Die Funktionen der Datenbank zeigen sie nur, wenn die Kette ihrer
Quelle heute zu genau diesem Kunden führt (app/portal/unterlagen.py::portal_quelle()), sie nicht zurückgenommen ist und ihre Kopie bereit liegt. Dieses
Modul ist die Seite des ERP dazu:

- kette(): dieselbe Kette in Python -- unter SQLite gibt es die Funktion der Datenbank nicht, und das ERP nennt den Grund, warum eine Freigabe ruht.
  tests/test_v827_portal_freigaben_kette.py prüft in jeder Zelle der Matrix aus 1.11.32 (tests/test_v822_portal_unterlagen_matrix.py), dass Python und SQL
  dasselbe sagen. Eine Änderung an einer Kette gehört in beide (SQL über eine neue Migration).
- freigeben(): eine oder mehrere Unterlagen einer Quelle für den Kunden aus dem Pfad -- nur, wenn die Kette heute zu ihm führt (sonst außen wie
  unbekannt, Regel 25), sie gilt (sonst 409 mit Grund), nur PDF und Rasterbilder bis 25 MB (P2-12, P2-14; endgültig prüft der Postbote am Inhalt). Steht
  dieselbe Quelle noch bei einem anderen Kunden (dort ruht sie, Index „höchstens eine je Quelle“), sagt die Meldung, wo -- erst dort zurücknehmen
  (vorgemerkt am 26.11.2026). Mehrere auf einmal (Nachtrag 6): alles oder nichts; schon freigegebene desselben Kunden zählen als „schon“.
- zuruecknehmen(): sofort unsichtbar, die Kopie entfernt der Postbote; auch im Archiv (wie Sperren). Die Zeile bleibt (Nachweis).
- erneut(): eine gescheiterte Kopie noch einmal -- der Postbote versucht es von selbst nicht (Festlegung 1.11.33-5).
- stand(): je Freigabe des Kunden Art, Titel, Zustand (sichtbar, wird vorbereitet, gescheitert, ruht mit Grund, zurückgenommen).

Nichts hier zeigt dem Kunden etwas an -- das tun nur die Funktionen der Datenbank. Wer freigibt und zurücknimmt, steht in der Änderungshistorie
(PortalFreigabe in app/audit.py, ohne die Felder der Kopie).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today, to_berlin, utc_jetzt
from .models import (
    ChecklistAttachment, ChecklistTemplateVersion, ChecklistVersion, Checklist, Customer, CustomerDocument, Defect, DefectFile, DocumentCategory, Invoice,
    NoticeLetter, Order, OrderAcceptance, OrderAcceptanceFile, OrderContract, PortalFreigabe, Project, ProjectDocument, Property, PropertyDocument, Quote,
    Reminder, SentDocument, ServiceReport, ServiceReportPhoto, WebAnfrage,
)
from .portal import werte

HOECHSTENS_BYTES = 25 * 1024 * 1024  # wie der Postbote (app/portal_kopien.py, Entscheidung P2-14)
FREIGEBBAR_TYPEN = ("application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif")  # P2-12: nur PDF und Rasterbilder
HOECHSTENS_JE_AUFRUF = 200  # mehrere auf einmal (Nachtrag 6)
KANAL = "portal_freigabe"  # Weckruf des Postboten (app/portal/weckruf.py)

ART_TEXT = {
    "angebot": "Angebot", "auftrag": "Auftragsbestätigung", "vertrag": "Vertrag", "rechnung": "Rechnung", "mahnung": "Mahnung",
    "abnahmeprotokoll": "Abnahmeprotokoll", "einsatzbericht": "Einsatzbericht", "brief": "Brief", "checkliste": "Checkliste", "foto": "Foto",
    "dokument": "Dokument",
}
ZUSTAND_TEXT = {
    "sichtbar": "im Portal sichtbar", "wird_vorbereitet": "wird vorbereitet", "gescheitert": "Kopie gescheitert", "ruht": "ruht",
    "zurueckgenommen": "zurückgenommen",
}
FEHLER_TEXT = {  # app/portal/werte.py::KOPIE_FEHLER in Worten
    "zu_gross": "zu groß (mehr als 25 MB oder zu viele Bildpunkte)", "nicht_lesbar": "Datei nicht lesbar",
    "falscher_typ": "kein PDF und kein Bild", "pruefsumme": "Datei in der Ablage beschädigt (Prüfsumme)", "abbruch": "Bild ließ sich nicht umwandeln",
    "fehlt": "Datei fehlt",
}
MELDUNG_FREMD = "Unterlage nicht gefunden."
MELDUNG_TYP = "Nur PDF und Bilder (JPEG, PNG, WebP, GIF) lassen sich freigeben – bitte vorher als PDF speichern."
MELDUNG_GROESSE = "Größer als 25 MB – zu groß fürs Kundenportal."
MELDUNG_SCHON = "Schon im Portal freigegeben."


class UnterlageFehlt(Exception):
    """Unbekannt oder gehört (heute) nicht zu diesem Kunden -- außen dasselbe (Router 404)."""


class FreigabeNicht(Exception):
    """Geht im jetzigen Zustand nicht (Router 409) -- der Text sagt, warum und was zu tun ist."""


# --- Kette in Python (Spiegel von portal_quelle()) ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Kette:
    """kunde: wohin die Kette heute führt, ohne die Bedingungen der Gültigkeit (None: die Unterlage gibt es nicht bzw. keine Kette zu einem Kunden);
    grund: warum sie heute nicht gilt (None: gilt). Sichtbar wäre sie genau dann, wenn gilt und kunde der Kunde der Freigabe ist -- wie portal_quelle()."""
    kunde: int | None
    grund: str | None = None
    art: str = "dokument"
    titel: str = ""
    datum: date | None = None
    auftrag: str | None = None
    objekt_id: int | None = None
    typ: str | None = None      # gespeicherter Typ einer hochgeladenen Datei; None = PDF aus der Ablage bzw. Foto des Berichts (immer JPEG)
    groesse: int | None = None

    @property
    def gilt(self) -> bool:
        return self.kunde is not None and self.grund is None


FEHLT = Kette(None)


def _tag(wert: date | datetime | None) -> date | None:
    if isinstance(wert, datetime):
        return to_berlin(wert).date()
    return wert


def _datum_text(tag: date | None) -> str:
    return tag.strftime("%d.%m.%Y") if tag else ""


def _projekt_grund(p: Project | None) -> str | None:
    """portal_projekt_offen(): kein Mustervorgang, nicht archiviert (von Hand oder Aufbewahrung)."""
    if p is None:
        return "Projekt gibt es nicht mehr"
    if p.is_template:
        return "Projekt ist ein Mustervorgang"
    if p.archived or p.archiviert_am is not None:
        return "Projekt im Archiv"
    return None


def _auftrag(db: Session, order_id: int | None) -> tuple[Order | None, Project | None]:
    o = db.get(Order, order_id) if order_id is not None else None
    return o, (db.get(Project, o.project_id) if o is not None else None)


def _datei_art(typ: str | None) -> str:
    return "foto" if (typ or "").startswith("image/") else "dokument"


def _kategorie(db: Session, category_id: int | None, name: str | None = None) -> str:
    if name:
        return name
    k = db.get(DocumentCategory, category_id) if category_id is not None else None
    return k.label if k is not None else "Dokument"


def _fassung_gilt(db: Session, v: ChecklistVersion) -> bool:
    """portal_fassung_gilt(): keine Unterschrift der Fassung ist verworfen."""
    try:
        ids = [int(x) for x in json.loads(v.signature_ids or "[]")]
    except (ValueError, TypeError):
        ids = []
    if not ids:
        return True
    return db.scalar(select(ChecklistAttachment.id).where(ChecklistAttachment.checklist_id == v.checklist_id, ChecklistAttachment.discarded_at.is_not(None),
                                                          ChecklistAttachment.id.in_(ids)).limit(1)) is None


def _mit_projekt(kunde, p: Project | None, grund: str | None = None, **rest) -> Kette:
    return Kette(kunde, grund or _projekt_grund(p), objekt_id=p.property_id if p is not None else None, **rest)


def kette(db: Session, quelle: str, quelle_id: int) -> Kette:
    """Je Quelle derselbe Weg wie in portal_quelle() (app/portal/unterlagen.py)."""
    if quelle == "invoices":
        from .invoices import rechnungsart_text
        i = db.get(Invoice, quelle_id)
        if i is None:
            return FEHLT
        o, p = _auftrag(db, i.order_id)
        if i.status == "entwurf":  # der Kunde steht erst ab dem Festschreiben an der Rechnung; bis dahin der des Auftrags
            return _mit_projekt(o.customer_id, p, "Rechnung im Entwurf", art="rechnung", titel="Rechnung (Entwurf)", datum=i.invoice_date,
                                auftrag=o.order_number)
        return _mit_projekt(i.customer_id, p, art="rechnung", titel=f"{rechnungsart_text(i)} {i.invoice_number or ''}".strip(), datum=i.invoice_date,
                            auftrag=o.order_number)
    if quelle == "reminders":
        r = db.get(Reminder, quelle_id)
        if r is None:
            return FEHLT
        i = db.get(Invoice, r.invoice_id)
        o, p = _auftrag(db, i.order_id)
        grund = "Mahnung nicht festgeschrieben" if r.status != "versendet" else ("Mahnung ersetzt" if r.replaced_by_id is not None else None)
        return _mit_projekt(i.customer_id, p, grund, art="mahnung", titel=f"{r.level}. Mahnung {r.reminder_number or ''}".strip(), datum=r.reminder_date,
                            auftrag=o.order_number)
    if quelle == "sent_documents":
        s = db.get(SentDocument, quelle_id)
        if s is None:
            return FEHLT
        tag = _tag(s.created_at)
        if s.document_type == "angebot":
            q = db.get(Quote, s.document_id)
            p = db.get(Project, q.project_id) if q is not None else None
            if p is None:
                return FEHLT
            return _mit_projekt(p.customer_id, p, art="angebot", titel=f"Angebot {s.document_number or ''}".strip(), datum=tag)
        if s.document_type == "auftrag":
            o, p = _auftrag(db, s.document_id)
            if o is None:
                return FEHLT
            return _mit_projekt(o.customer_id, p, art="auftrag", titel=f"Auftragsbestätigung {o.order_number}", datum=tag, auftrag=o.order_number)
        if s.document_type == "vertrag":
            c = db.get(OrderContract, s.document_id)
            o, p = _auftrag(db, c.order_id if c is not None else None)
            if o is None:
                return FEHLT
            return _mit_projekt(o.customer_id, p, art="vertrag", titel=f"Vertrag zum Auftrag {o.order_number}", datum=tag, auftrag=o.order_number)
        return FEHLT  # andere Arten der Ablage haben keine Kette ins Portal
    if quelle == "service_reports":
        from .service_reports import REPORT_TYPE_LABELS
        sr = db.get(ServiceReport, quelle_id)
        if sr is None:
            return FEHLT
        o, p = _auftrag(db, sr.order_id)
        grund = ("Bericht nicht unterschrieben" if sr.status != "unterschrieben"
                 else ("Bericht ohne feste Fassung (vor 1.11.29 unterschrieben)" if sr.pdf_document_id is None else None))
        return _mit_projekt(o.customer_id, p, grund, art="einsatzbericht", auftrag=o.order_number, datum=sr.performed_at,
                            titel=f"{REPORT_TYPE_LABELS.get(sr.report_type, 'Einsatzbericht')} vom {_datum_text(sr.performed_at)}")
    if quelle == "checklist_versions":
        v = db.get(ChecklistVersion, quelle_id)
        if v is None:
            return FEHLT
        c = db.get(Checklist, v.checklist_id)
        fassung = db.get(ChecklistTemplateVersion, c.template_version_id)
        art = "abnahmeprotokoll" if fassung is not None and fassung.purpose == "abnahme" else "checkliste"
        grund = None if _fassung_gilt(db, v) else "Fassung überholt (Unterschrift verworfen)"
        titel = f"{c.template_label_snapshot} (Fassung {v.version_no})"
        if c.order_id is not None:
            o, p = _auftrag(db, c.order_id)
            return _mit_projekt(o.customer_id, p, grund, art=art, titel=titel, datum=_tag(v.created_at), auftrag=o.order_number)
        if c.property_id is not None:
            pr = db.get(Property, c.property_id)
            return Kette(pr.customer_id, grund, art=art, titel=titel, datum=_tag(v.created_at), objekt_id=pr.id)
        return FEHLT  # Checkliste am Betriebsmittel oder am Betrieb: keine Kette zu einem Kunden
    if quelle == "notice_letters":
        from .notice_letters import LETTER_KINDS
        n = db.get(NoticeLetter, quelle_id)
        if n is None:
            return FEHLT
        c = db.get(Checklist, n.checklist_id)
        if c.order_id is None:
            return FEHLT
        o, p = _auftrag(db, c.order_id)
        unterschrift = db.get(ChecklistAttachment, n.signature_id)
        grund = "Unterschrift verworfen" if unterschrift is not None and unterschrift.discarded_at is not None else None
        art_ = LETTER_KINDS[n.kind].label if n.kind in LETTER_KINDS else "Brief"
        return _mit_projekt(o.customer_id, p, grund, art="brief", titel=f"{art_} vom {_datum_text(_tag(n.created_at))}", datum=_tag(n.created_at),
                            auftrag=o.order_number)
    if quelle == "service_report_photos":
        f = db.get(ServiceReportPhoto, quelle_id)
        if f is None:
            return FEHLT
        sr = db.get(ServiceReport, f.service_report_id)
        o, p = _auftrag(db, sr.order_id)
        tag = _tag(f.created_at)
        return _mit_projekt(o.customer_id, p, art="foto", titel=f"Foto vom {_datum_text(tag)}", datum=tag, auftrag=o.order_number)
    if quelle == "customer_documents":
        d = db.get(CustomerDocument, quelle_id)
        if d is None:
            return FEHLT
        tag = d.document_date or _tag(d.uploaded_at)
        return Kette(d.customer_id, art=_datei_art(d.content_type), titel=f"{_kategorie(db, d.category_id, d.category)} vom {_datum_text(tag)}", datum=tag,
                     typ=d.content_type, groesse=d.file_size)
    if quelle == "project_documents":
        d = db.get(ProjectDocument, quelle_id)
        if d is None:
            return FEHLT
        p = db.get(Project, d.project_id)
        tag = d.document_date or _tag(d.uploaded_at)
        return _mit_projekt(p.customer_id, p, art=_datei_art(d.content_type), titel=f"{_kategorie(db, d.category_id, d.category)} vom {_datum_text(tag)}",
                            datum=tag, typ=d.content_type, groesse=d.file_size)
    if quelle == "property_documents":
        d = db.get(PropertyDocument, quelle_id)
        if d is None:
            return FEHLT
        pr = db.get(Property, d.property_id)
        w = db.get(WebAnfrage, d.webanfrage_id) if d.webanfrage_id is not None else None
        grund = "Eingang der Webseite im Archiv" if w is not None and w.archiviert_am is not None else None
        tag = _tag(d.uploaded_at)
        return Kette(pr.customer_id, grund, art=_datei_art(d.content_type), titel=f"{_kategorie(db, d.category_id)} vom {_datum_text(tag)}", datum=tag,
                     objekt_id=pr.id, typ=d.content_type, groesse=d.file_size)
    if quelle == "defect_files":
        f = db.get(DefectFile, quelle_id)
        if f is None:
            return FEHLT
        d = db.get(Defect, f.defect_id)
        o, p = _auftrag(db, d.order_id)
        tag = _tag(f.created_at)
        art = _datei_art(f.content_type)
        return _mit_projekt(o.customer_id, p, "Mangel verworfen" if d.discarded_at is not None else None, art=art, datum=tag, auftrag=o.order_number,
                            titel=f"{'Foto' if art == 'foto' else 'Beleg'} zum Mangel vom {_datum_text(tag)}", typ=f.content_type, groesse=f.size_bytes)
    if quelle == "order_acceptance_files":
        f = db.get(OrderAcceptanceFile, quelle_id)
        if f is None:
            return FEHLT
        a = db.get(OrderAcceptance, f.acceptance_id)
        o, p = _auftrag(db, a.order_id)
        return _mit_projekt(o.customer_id, p, "Abnahme verworfen" if a.discarded_at is not None else None, art=_datei_art(f.content_type),
                            titel=f"Beleg zur Abnahme vom {_datum_text(a.accepted_on)}", datum=a.accepted_on, auftrag=o.order_number, typ=f.content_type,
                            groesse=f.size_bytes)
    return FEHLT  # eine Quelle ohne Zweig hier -- der Wächter in tests/test_v827 verlangt jede aus FREIGABE_QUELLEN


# --- Freigeben, zurücknehmen, erneut --------------------------------------------------------------------------------------------------------------------

def _kunde_text(db: Session, kunde_id: int) -> str:
    k = db.get(Customer, kunde_id)
    if k is None:
        return "einem anderen Kunden"
    nummer = k.customer_number
    return f"Kunde {nummer} ({k.name})" if nummer else f"Kunde {k.name}"


def _bestehend(db: Session, quelle: str, quelle_id: int) -> PortalFreigabe | None:
    return db.scalar(select(PortalFreigabe).where(PortalFreigabe.quelle == quelle, PortalFreigabe.quelle_id == quelle_id,
                                                  PortalFreigabe.zurueckgenommen_am.is_(None)))


def _anderswo(db: Session, f: PortalFreigabe) -> str:
    return (f"Diese Unterlage ist noch bei {_kunde_text(db, f.customer_id)} freigegeben (dort ruht sie) – erst beim bisherigen Kunden zurücknehmen.")


def pruefen(db: Session, kunde_id: int, quelle: str, quelle_id: int) -> Kette:
    """Lässt sich die Unterlage für diesen Kunden freigeben? Die Kette (UnterlageFehlt, FreigabeNicht mit Grund) -- ohne Blick auf bestehende Freigaben."""
    if quelle not in werte.FREIGABE_QUELLEN:
        raise UnterlageFehlt(MELDUNG_FREMD)
    k = kette(db, quelle, quelle_id)
    if k.kunde != kunde_id:  # unbekannt oder (heute) bei einem anderen Kunden -- außen gleich (Regel 25)
        raise UnterlageFehlt(MELDUNG_FREMD)
    if k.grund:
        raise FreigabeNicht(f"Lässt sich nicht freigeben: {k.grund}.")
    if k.typ is not None and k.typ not in FREIGEBBAR_TYPEN:
        raise FreigabeNicht(MELDUNG_TYP)
    if k.groesse is not None and k.groesse > HOECHSTENS_BYTES:
        raise FreigabeNicht(MELDUNG_GROESSE)
    return k


@dataclass
class Ergebnis:
    neu: list[int]
    schon: int


def freigeben(db: Session, kunde_id: int, quelle: str, quelle_ids: list[int], titel: str | None, *, user_id: int | None,
              user_name: str | None) -> Ergebnis:
    """Alles oder nichts: jede Unterlage wird geprüft, bevor eine Zeile entsteht. Schon für diesen Kunden freigegeben: zählt als „schon“ (nichts Neues);
    ist keine neu, FreigabeNicht. Noch bei einem anderen Kunden freigegeben: FreigabeNicht mit dem Kunden. titel leer = je Unterlage der Vorschlag."""
    ids = list(dict.fromkeys(quelle_ids))
    if not ids or len(ids) > HOECHSTENS_JE_AUFRUF:
        raise FreigabeNicht(f"Eine bis {HOECHSTENS_JE_AUFRUF} Unterlagen auf einmal.")
    neu: list[tuple[int, Kette]] = []
    schon = 0
    for qid in ids:
        k = pruefen(db, kunde_id, quelle, qid)
        b = _bestehend(db, quelle, qid)
        if b is not None:
            if b.customer_id != kunde_id:
                raise FreigabeNicht(_anderswo(db, b))
            schon += 1
            continue
        neu.append((qid, k))
    if not neu:
        raise FreigabeNicht(MELDUNG_SCHON)
    jetzt_ = utc_jetzt()
    zeilen = [PortalFreigabe(customer_id=kunde_id, art=k.art, quelle=quelle, quelle_id=qid, titel=(titel or k.titel or ART_TEXT[k.art])[:120],
                             datum=k.datum or berlin_today(), regel=None, freigegeben_am=jetzt_, freigegeben_von_user_id=user_id,
                             freigegeben_von_name=user_name or "System") for qid, k in neu]
    db.add_all(zeilen)
    try:
        db.commit()  # der Auslöser an portal_freigaben weckt den Postboten (app/portal/weckruf.py)
    except IntegrityError:  # gleichzeitig freigegeben: höchstens eine je Quelle
        db.rollback()
        for qid, _k in neu:
            b = _bestehend(db, quelle, qid)
            if b is not None and b.customer_id != kunde_id:
                raise FreigabeNicht(_anderswo(db, b))
        raise FreigabeNicht("Eben schon freigegeben – bitte neu laden.")
    return Ergebnis(neu=[z.id for z in zeilen], schon=schon)


def _freigabe_des_kunden(db: Session, kunde_id: int, freigabe_id: int) -> PortalFreigabe:
    f = db.scalar(select(PortalFreigabe).where(PortalFreigabe.id == freigabe_id).with_for_update())
    if f is None or f.customer_id != kunde_id:  # Regel 25: die Freigabe gehört zum Kunden im Pfad
        raise UnterlageFehlt("Freigabe nicht gefunden.")
    return f


def zuruecknehmen(db: Session, kunde_id: int, freigabe_id: int, grund: str | None, *, user_id: int | None, user_name: str | None) -> None:
    """Sofort unsichtbar (die Funktionen prüfen zurueckgenommen_am); die Kopie entfernt der Postbote, geweckt vom Auslöser. Auch im Archiv."""
    f = _freigabe_des_kunden(db, kunde_id, freigabe_id)
    if f.zurueckgenommen_am is not None:
        raise FreigabeNicht("Schon zurückgenommen.")
    f.zurueckgenommen_am = utc_jetzt()
    f.zurueckgenommen_von_user_id = user_id
    f.zurueckgenommen_von_name = user_name or "System"
    f.zurueckgenommen_grund = grund or None
    db.commit()


def _wecken(db: Session) -> None:
    """Den Postboten wecken, wo kein Auslöser greift (ein Zurücksetzen von kopie_fehler) -- nur unter PostgreSQL; die Nachricht geht mit dem Commit."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_notify(:k, '')"), {"k": KANAL})


def erneut(db: Session, kunde_id: int, freigabe_id: int) -> None:
    """Eine gescheiterte Kopie noch einmal versuchen: kopie_fehler leer, der Postbote legt sie im nächsten Durchgang an."""
    f = _freigabe_des_kunden(db, kunde_id, freigabe_id)
    if f.zurueckgenommen_am is not None:
        raise FreigabeNicht("Zurückgenommen – erst neu freigeben.")
    if f.kopie_fehler is None:
        raise FreigabeNicht("Die Kopie ist nicht gescheitert.")
    f.kopie_fehler = None
    db.flush()
    _wecken(db)
    db.commit()


# --- Stand für die Karte ---------------------------------------------------------------------------------------------------------------------------------

def zustand(db: Session, f: PortalFreigabe, k: Kette | None = None) -> tuple[str, str | None]:
    """(Zustand, Grund) -- in derselben Reihenfolge, in der die Funktionen der Datenbank prüfen."""
    if f.zurueckgenommen_am is not None:
        return "zurueckgenommen", f.zurueckgenommen_grund
    k = k or kette(db, f.quelle, f.quelle_id)
    if k.kunde is None:
        return "ruht", "die Unterlage gibt es nicht mehr"
    if k.kunde != f.customer_id:
        return "ruht", "gehört heute zu einem anderen Kunden"
    if k.grund:
        return "ruht", k.grund
    if f.kopie_fehler:
        return "gescheitert", FEHLER_TEXT.get(f.kopie_fehler, f.kopie_fehler)
    if f.kopie_bereit_am is None or f.kopie_name is None:
        return "wird_vorbereitet", None
    return "sichtbar", None


def _adresse(db: Session, objekt_id: int | None) -> str | None:
    pr = db.get(Property, objekt_id) if objekt_id is not None else None
    if pr is None:
        return None
    ort = " ".join(x for x in (pr.postal_code, pr.city) if x)
    return ", ".join(x for x in (pr.street, ort) if x) or None


def eintrag(db: Session, f: PortalFreigabe) -> dict:
    k = kette(db, f.quelle, f.quelle_id)
    z, grund = zustand(db, f, k)
    return {
        "id": f.id, "art": f.art, "art_text": ART_TEXT.get(f.art, f.art), "quelle": f.quelle, "quelle_id": f.quelle_id, "titel": f.titel, "datum": f.datum,
        "automatisch": f.regel is not None, "freigegeben_am": f.freigegeben_am, "freigegeben_von": f.freigegeben_von_name, "zustand": z,
        "zustand_text": ZUSTAND_TEXT[z], "grund": grund, "zurueckgenommen_am": f.zurueckgenommen_am, "zurueckgenommen_von": f.zurueckgenommen_von_name,
        "auftrag": k.auftrag, "objekt": _adresse(db, k.objekt_id),
    }


def stand(db: Session, kunde: Customer, *, modul_an: bool = True) -> dict:
    """Was die Karte „Im Portal“ zeigt: je Freigabe des Kunden ein Eintrag, die jüngste zuerst; dazu, ob der Kunde das Portal sieht."""
    zeilen = db.scalars(select(PortalFreigabe).where(PortalFreigabe.customer_id == kunde.id)
                        .order_by(PortalFreigabe.freigegeben_am.desc(), PortalFreigabe.id.desc())).all()
    return {"portal_aktiv": bool(kunde.portal_aktiv), "kunde_archiv": kunde.archiviert_am is not None, "eintraege": [eintrag(db, f) for f in zeilen],
            "vorschlaege": vorschlaege(db, kunde)}  # seit 1.11.37


def unterlagen(db: Session, quelle: str, quelle_ids: list[int]) -> list[dict]:
    """Für „Im Portal zeigen“ an einer Datei: je Unterlage der Kunde der Kette, ob sie sich freigeben lässt (sonst warum), der Vorschlag für den Titel
    und eine bestehende Freigabe. Liest nur."""
    aus = []
    for qid in dict.fromkeys(quelle_ids):
        k = kette(db, quelle, qid) if quelle in werte.FREIGABE_QUELLEN else FEHLT
        grund = None
        if k.kunde is None:
            grund = MELDUNG_FREMD
        elif k.grund:
            grund = k.grund
        elif k.typ is not None and k.typ not in FREIGEBBAR_TYPEN:
            grund = MELDUNG_TYP
        elif k.groesse is not None and k.groesse > HOECHSTENS_BYTES:
            grund = MELDUNG_GROESSE
        b = _bestehend(db, quelle, qid) if k.kunde is not None else None
        bestehend = None
        if b is not None:
            z, zgrund = zustand(db, b, k)
            bestehend = {"id": b.id, "customer_id": b.customer_id, "zustand": z, "zustand_text": ZUSTAND_TEXT[z], "grund": zgrund,
                         "anderer_kunde": b.customer_id != k.kunde}
        aus.append({"quelle_id": qid, "customer_id": k.kunde, "freigebbar": grund is None and (b is None), "grund": grund,
                    "art": k.art if k.kunde is not None else None, "titel_vorschlag": k.titel or None, "bestehend": bestehend})
    return aus


# --- Automatische Regeln (seit 1.11.37, Bauplan P2, B4.3; Entscheidungen P2-3 bis P2-5) -------------------------------------------------------------
#
# „Automatisch“ heißt: eine Zeile mit Regel entsteht ohne Klick -- beim Einschalten des Portals am Kunden (app/kundenportal.py::schalten()) und danach im
# vollen Lauf des Postboten (alle 15 Minuten, app/portal_postbote.py), auch für alles, was vor der Einladung entstand (P2-3). Sie steht im ERP wie eine
# einzelne und lässt sich zurücknehmen. Von einer Person zurückgenommen legt die Regel sie nie wieder an; vom System als überholt zurückgenommen (eine neuere
# Fassung derselben Unterlage ist die jüngste) schon, wenn sie wieder die jüngste ist. Kein stilles Umhängen: steht die Quelle noch beim bisherigen Kunden,
# legt die Regel nichts an (die Karte zeigt dort „ruht“).

REGELN = ("rechnung", "mahnung", "angebot", "auftrag", "vertrag", "abnahmeprotokoll", "einsatzbericht", "brief")
REGEL_VON = "automatisch"       # freigegeben_von_name einer Zeile der Regel (ohne Konto)
SYSTEM = "System"               # zurueckgenommen_von_name, wenn die Regel eine überholte Fassung zurücknimmt
UEBERHOLT = "neuere Fassung versendet"


@dataclass(frozen=True)
class Kandidat:
    quelle: str
    quelle_id: int
    regel: str
    gruppe: tuple | None = None  # nur die jüngste Fassung einer Gruppe gilt (Angebot, Auftragsbestätigung, Vertrag je Dokument; Abnahmeprotokoll je Checkliste)


def _an_den_kunden(d, email: str | None) -> bool:
    """Ging dieser Versand an den Kunden? Nachgetragen: an den Auftraggeber (delivered_to_client); per Mail: seine Adresse steht unter An (P2-4)."""
    from .email_dispatch import MANUAL_CHANNELS, parse_recipients

    if d.channel in MANUAL_CHANNELS:
        return d.delivered_to_client is True
    if not email:
        return False
    try:
        an = {a.lower() for a in parse_recipients(d.to_recipients, label="An")}
    except ValueError:
        return False
    return email.strip().lower() in an


def _ablage(db: Session, kunde: Customer) -> tuple[list[Kandidat], list[dict], dict[tuple, int]]:
    """Angebot, Auftragsbestätigung, Vertrag: je Dokument die zuletzt versendete Fassung (P2-4) -- an den Kunden: Kandidat, sonst Vorschlag. Dazu je Gruppe
    die jüngste Fassung (für „überholt“)."""
    from sqlalchemy import and_, or_

    from .email_dispatch import MANUAL_CHANNELS, dispatch_outcomes
    from .models import EmailDispatch

    angebote = select(Quote.id).join(Project, Project.id == Quote.project_id).where(Project.customer_id == kunde.id)
    auftraege = select(Order.id).where(Order.customer_id == kunde.id)
    vertraege = select(OrderContract.id).where(OrderContract.order_id.in_(auftraege))
    zeilen = db.execute(
        select(EmailDispatch, SentDocument).join(SentDocument, SentDocument.id == EmailDispatch.sent_document_id)
        .where(EmailDispatch.status == "gesendet", or_(
            and_(SentDocument.document_type == "angebot", SentDocument.document_id.in_(angebote)),
            and_(SentDocument.document_type == "auftrag", SentDocument.document_id.in_(auftraege)),
            and_(SentDocument.document_type == "vertrag", SentDocument.document_id.in_(vertraege))))
        .order_by(EmailDispatch.created_at, EmailDispatch.id)).all()
    ergebnisse = dispatch_outcomes(db, [d.id for d, _s in zeilen])
    juengste: dict[tuple, tuple] = {}
    for d, s in zeilen:
        e = ergebnisse.get(d.id)
        if e is not None and e.outcome == "unzustellbar":
            continue
        juengste[(s.document_type, s.document_id)] = (d, s)  # aufsteigend sortiert: die letzte gewinnt
    liste, vorschlaege_ = [], []
    for gruppe, (d, s) in juengste.items():
        if _an_den_kunden(d, kunde.email):
            liste.append(Kandidat("sent_documents", s.id, s.document_type, gruppe))
        else:
            vorschlaege_.append({"quelle": "sent_documents", "quelle_id": s.id, "art": s.document_type, "am": _tag(d.finished_at or d.created_at),
                                 "an": None if d.channel in MANUAL_CHANNELS else d.to_recipients})
    return liste, vorschlaege_, {g: s.id for g, (_d, s) in juengste.items()}


def kandidaten(db: Session, kunde: Customer) -> tuple[list[Kandidat], list[dict], dict[tuple, int]]:
    """Was die Regeln für diesen Kunden freigeben würden (B4.3), was nur Vorschlag ist (an eine andere Adresse versendet), und je Gruppe die jüngste Fassung.
    Jeder Kandidat führt heute über seine Kette zu genau diesem Kunden und gilt (kette()). Liest nur."""
    from .email_dispatch import document_reached_on
    from .notice_letters import delivered_dispatches
    from .protocol_dispatch import protocol_version
    from .reminders import reached_map

    liste: list[Kandidat] = []
    rechnungen = db.scalars(select(Invoice).where(Invoice.customer_id == kunde.id, Invoice.status != "entwurf").order_by(Invoice.id)).all()
    erreicht = document_reached_on(db, "rechnung", rechnungen)
    liste += [Kandidat("invoices", i.id, "rechnung") for i in rechnungen if i.id in erreicht]
    mahnungen = db.scalars(select(Reminder).join(Invoice, Invoice.id == Reminder.invoice_id)
                           .where(Invoice.customer_id == kunde.id, Reminder.status == "versendet", Reminder.replaced_by_id.is_(None))
                           .order_by(Reminder.id)).all()
    erreicht = reached_map(db, mahnungen)
    liste += [Kandidat("reminders", r.id, "mahnung") for r in mahnungen if r.id in erreicht]
    ablage, vorschlaege_, juengste = _ablage(db, kunde)
    liste += ablage
    protokolle = db.scalars(select(Checklist).join(Order, Order.id == Checklist.order_id)
                            .join(ChecklistTemplateVersion, ChecklistTemplateVersion.id == Checklist.template_version_id)
                            .where(Order.customer_id == kunde.id, ChecklistTemplateVersion.purpose == "abnahme").order_by(Checklist.id)).all()
    for c in protokolle:
        v = protocol_version(db, c)  # die jüngste gültige Fassung mit der Unterschrift des Auftraggebers -- sonst None
        if v is not None:
            liste.append(Kandidat("checklist_versions", v.id, "abnahmeprotokoll", ("abnahmeprotokoll", c.id)))
            juengste[("abnahmeprotokoll", c.id)] = v.id
    berichte = db.scalars(select(ServiceReport.id).join(Order, Order.id == ServiceReport.order_id)
                          .where(Order.customer_id == kunde.id, ServiceReport.status == "unterschrieben", ServiceReport.pdf_document_id.is_not(None))
                          .order_by(ServiceReport.id)).all()
    liste += [Kandidat("service_reports", i, "einsatzbericht") for i in berichte]
    briefe = db.scalars(select(NoticeLetter).join(Checklist, Checklist.id == NoticeLetter.checklist_id).join(Order, Order.id == Checklist.order_id)
                        .where(Order.customer_id == kunde.id).order_by(NoticeLetter.id)).all()
    angekommen: dict[tuple, set] = {}
    for n in briefe:
        schluessel = (n.kind, n.checklist_id)
        if schluessel not in angekommen:
            angekommen[schluessel] = {d.sent_document_id for d in delivered_dispatches(db, n.kind, n.checklist_id)}
        if n.sent_document_id in angekommen[schluessel]:
            liste.append(Kandidat("notice_letters", n.id, "brief"))
    gueltig = []
    for k in liste:
        kt = kette(db, k.quelle, k.quelle_id)
        if kt.gilt and kt.kunde == kunde.id:
            gueltig.append(k)
    return gueltig, vorschlaege_, juengste


def _gruppe(db: Session, f: PortalFreigabe) -> tuple | None:
    if f.quelle == "sent_documents":
        s = db.get(SentDocument, f.quelle_id)
        return (s.document_type, s.document_id) if s is not None else None
    if f.quelle == "checklist_versions" and f.regel == "abnahmeprotokoll":
        v = db.get(ChecklistVersion, f.quelle_id)
        return ("abnahmeprotokoll", v.checklist_id) if v is not None else None
    return None


@dataclass
class Angewandt:
    neu: int = 0
    ueberholt: int = 0


def regeln_anwenden(db: Session, kunde: Customer) -> Angewandt:
    """Legt fehlende Zeilen der Regeln an und nimmt überholte Fassungen zurück (ein Commit). Ein gleichzeitiges Freigeben (Index „höchstens eine je
    Quelle“) überspringt die eine Zeile, nicht den Rest."""
    stand = Angewandt()
    liste, _vorschlaege, juengste = kandidaten(db, kunde)
    jetzt_ = utc_jetzt()
    for k in liste:
        zeilen = db.scalars(select(PortalFreigabe).where(PortalFreigabe.quelle == k.quelle, PortalFreigabe.quelle_id == k.quelle_id)
                            .order_by(PortalFreigabe.id)).all()
        if any(z.zurueckgenommen_am is None for z in zeilen):
            continue  # schon freigegeben -- hier oder (ruhend) bei einem anderen Kunden
        if any(z.zurueckgenommen_von_user_id is not None for z in zeilen):
            continue  # von einer Person zurückgenommen: die Regel legt sie nie wieder an
        kt = kette(db, k.quelle, k.quelle_id)
        try:
            with db.begin_nested():
                db.add(PortalFreigabe(customer_id=kunde.id, art=kt.art, quelle=k.quelle, quelle_id=k.quelle_id, titel=(kt.titel or ART_TEXT[kt.art])[:120],
                                      datum=kt.datum or berlin_today(), regel=k.regel, freigegeben_am=jetzt_, freigegeben_von_user_id=None,
                                      freigegeben_von_name=REGEL_VON))
            stand.neu += 1
        except IntegrityError:
            pass  # eben von Hand freigegeben (gleichzeitig)
    for f in db.scalars(select(PortalFreigabe).where(PortalFreigabe.customer_id == kunde.id, PortalFreigabe.regel.is_not(None),
                                                    PortalFreigabe.zurueckgenommen_am.is_(None)).order_by(PortalFreigabe.id)).all():
        g = _gruppe(db, f)
        if g is not None and g in juengste and juengste[g] != f.quelle_id:
            f.zurueckgenommen_am, f.zurueckgenommen_von_user_id, f.zurueckgenommen_von_name, f.zurueckgenommen_grund = jetzt_, None, SYSTEM, UEBERHOLT
            stand.ueberholt += 1
    db.commit()
    return stand


def regeln_alle(db: Session) -> Angewandt:
    """Für den Postboten: jeder Kunde mit Portal an und nicht im Archiv -- nur mit eingeschaltetem Modul."""
    from .modules import is_module_enabled

    gesamt = Angewandt()
    if not is_module_enabled(db, "kundenportal"):
        return gesamt
    for kunde in db.scalars(select(Customer).where(Customer.portal_aktiv.is_(True), Customer.archiviert_am.is_(None)).order_by(Customer.id)).all():
        stand = regeln_anwenden(db, kunde)
        gesamt.neu += stand.neu
        gesamt.ueberholt += stand.ueberholt
    return gesamt


def vorschlaege(db: Session, kunde: Customer) -> list[dict]:
    """An eine andere Adresse versendete jüngste Fassungen (Angebot, Auftragsbestätigung, Vertrag): nur von Hand freigeben (P2-4). Ohne die schon
    freigegebenen und ohne die, deren Kette heute nicht gilt. Liest nur."""
    _liste, liste, _j = kandidaten(db, kunde)
    aus = []
    for v in liste:
        if _bestehend(db, v["quelle"], v["quelle_id"]) is not None:
            continue
        kt = kette(db, v["quelle"], v["quelle_id"])
        if not (kt.gilt and kt.kunde == kunde.id):
            continue
        aus.append({**v, "titel": kt.titel, "art_text": ART_TEXT[v["art"]]})
    return aus
