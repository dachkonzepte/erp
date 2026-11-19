"""Eine Anfrage der Webseite als Anfrage übernehmen (seit 1.10.5, Stufe W1b; docs/archiv/webseite-und-kundenportal.md).

Vorschlag (vorschlag()): nur aus den strukturierten Feldern (app/webanfrage_angaben.py), nie aus Betreff oder Nachricht --

    Eigentümer          der Melder wird Kunde (Verbraucher), die Adresse des Objekts als Vorschlag für seine Anschrift
    Hausverwaltung      die Firma wird Kunde (kein Verbraucher), der Melder ihr Ansprechpartner
    Mieter              die Hausverwaltung bzw. der Vermieter aus dem Pflichtfeld wird Kunde (Verbraucher oder nicht: das Büro wählt), der Mieter ist
                        Ansprechpartner vor Ort -- Telefon und E-Mail des Mieters gehören nie zum Kunden
    Kantservice, Dach, PV  der Kontakt wird Kunde; Dach und PV mit der Adresse des Konfigurators, PV mit „privat/gewerbe“ als Verbraucher ja/nein

dazu bestehende Kunden mit ihren Gründen (E-Mail, Telefon, Name; PLZ nur zusätzlich), je Kunde seine Objekte mit „Adresse gleich“. Angelegt wird nichts,
bevor das Büro Auftraggeber und Objekt gewählt hat (keine Vorauswahl).

Übernehmen (uebernehmen()): eine Transaktion -- zuerst die Anfrage der Webseite (bedingtes UPDATE: nie zweimal, nicht aus der Prüfliste), dann Kunde und
Objekt (neu oder gewählt; ein Objekt nur des Kunden), die Anfrage (Quelle „Website“, Nummer der Webseite), die Fotos ans Objekt (Kategorie „Bilder /
Fotos“); das PDF bleibt am Eingang und steht an der Anfrage. Danach soll der Empfangsdienst die Anfragenummer bekommen (F2). Scheitert etwas, bleibt nichts
angelegt (auch keine Datei).

Rollenlos wie jede Geschäftslogik.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from sqlalchemy import func, not_, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from .audit import record_audit_entry
from .crm import kunde_anlegen
from .document_categories import resolve_category_id
from .models import Customer, Inquiry, Property, WebAnfrage
from .property_documents import create_property_document, document_path
from .settings import issue_number
from .suchmuster import passt
from .telefonbuch import schluessel, telefonbuch
from .webanfrage_angaben import ARTEN_KONFIGURATOR, adresse_text, einzeilig, objekt_adresse, reparatur_daten, umschlag_lesen
from .webanfragen import ART_HISTORIE, ERP_ID, IN_PRUEFLISTE, STATUS_NEU, STATUS_UEBERNOMMEN, SchonErledigt, datei_pfad

QUELLE = "Website"  # wie die Auswahl „Herkunft“ der Seite „Anfragen“
KATEGORIE_FOTOS = "Bilder / Fotos"
VORSCHLAEGE_MAX = 10
OBJEKTE_MAX = 200
_TELEFON = re.compile(r"\A\+?[0-9 ()/.\-]{5,40}\Z")
_EMAIL = re.compile(r"\A[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}\Z")


class ObjektFremd(ValueError):
    """Das gewählte Objekt gehört nicht zum gewählten Kunden -- 422."""


class AuswahlFehlt(ValueError):
    """Auftraggeber oder Objekt nicht (eindeutig) gewählt -- 422."""


def _telefon(wert) -> str | None:
    t = einzeilig(wert, 40)
    return t if t and _TELEFON.match(t) and len(re.sub(r"\D", "", t)) >= 5 else None


def _email(wert) -> str | None:
    t = einzeilig(wert, 120)
    return t if t and _EMAIL.match(t) else None


def _name_teilen(name: str | None) -> tuple[str | None, str | None]:
    """„Vorname Nachname“ -> (Vorname, Nachname); ein Wort nur als Nachname. Das Büro sieht und ändert beides vor dem Übernehmen."""
    if not name:
        return None, None
    teile = name.split(" ")
    return (" ".join(teile[:-1]) or None, teile[-1]) if len(teile) > 1 else (None, teile[0])


def angaben(zeile: WebAnfrage) -> dict:
    """Die strukturierten Angaben der Anfrage für die Übernahme: rolle (eigentuemer | verwaltung | mieter | kontakt), name, firma, hausverwaltung, telefon,
    email, objekt {strasse, plz, ort} | None, vor_ort {name, telefon} | None, ort (nur Kantservice: das freie Feld), verbraucher (True | False | None)."""
    u = umschlag_lesen(zeile.umschlag) or {}
    daten = reparatur_daten(zeile.art, u)
    if daten is not None:
        m = daten.get("melder") if isinstance(daten.get("melder"), dict) else {}
        o = daten.get("objekt") if isinstance(daten.get("objekt"), dict) else {}
        vo = o.get("vor_ort") if isinstance(o.get("vor_ort"), dict) else {}
        rolle = m.get("rolle") if m.get("rolle") in ("eigentuemer", "verwaltung", "mieter") else "eigentuemer"
        vor_ort = {"name": einzeilig(vo.get("name"), 80), "telefon": _telefon(vo.get("telefon"))}
        return {"rolle": rolle, "name": einzeilig(m.get("name"), 80), "firma": einzeilig(m.get("firma"), 100) if rolle == "verwaltung" else None,
                "hausverwaltung": einzeilig(m.get("hausverwaltung"), 100) if rolle == "mieter" else None, "telefon": _telefon(m.get("telefon")),
                "email": _email(m.get("email")), "objekt": objekt_adresse(zeile.art, u), "vor_ort": vor_ort if vor_ort["name"] else None, "ort": None,
                "verbraucher": {"eigentuemer": True, "verwaltung": False}.get(rolle)}
    k = u.get("kontakt") if isinstance(u.get("kontakt"), dict) else {}
    verbraucher = None
    if zeile.art == "dach":
        verbraucher = True
    elif zeile.art == "pv" and isinstance(u.get("daten"), dict):
        verbraucher = {"privat": True, "gewerbe": False}.get(u["daten"].get("kunde"))
    return {"rolle": "kontakt", "name": einzeilig(k.get("name"), 100), "firma": None, "hausverwaltung": None, "telefon": _telefon(k.get("telefon")),
            "email": _email(k.get("email")), "objekt": objekt_adresse(zeile.art, u) if zeile.art in ARTEN_KONFIGURATOR else None, "vor_ort": None,
            "ort": einzeilig(k.get("ort"), 100) if zeile.art == "kantservice" else None, "verbraucher": verbraucher}


def _nur_ziffern(spalte):
    for zeichen in (" ", "/", "-", "(", ")", "."):
        spalte = func.replace(spalte, zeichen, "")
    return spalte


def _kunden(db: Session, a: dict) -> list[dict]:
    """Bestehende Kunden mit Gründen -- beim Mieter nur nach dem Namen der Hausverwaltung (Telefon und E-Mail sind die des Mieters)."""
    treffer: dict[int, list[str]] = {}

    def dazu(abfrage, grund):
        for kid in db.scalars(abfrage.order_by(Customer.id).limit(50)).all():
            treffer.setdefault(kid, [])
            if grund not in treffer[kid]:
                treffer[kid].append(grund)

    eigene = a["rolle"] != "mieter"
    if eigene and a["email"]:
        e = a["email"].lower()
        dazu(select(Customer.id).where(or_(func.lower(Customer.email) == e, func.lower(Customer.email_2) == e)), "E-Mail gleich")
    if eigene and a["telefon"]:
        ende = re.sub(r"\D", "", a["telefon"])[-7:]
        if len(ende) >= 6:
            dazu(select(Customer.id).where(or_(passt(_nur_ziffern(Customer.phone), ende), passt(_nur_ziffern(Customer.mobile), ende))),
                 "Telefon gleich")
    if a["rolle"] == "verwaltung" and a["firma"]:
        dazu(select(Customer.id).where(passt(Customer.name, a["firma"])), "Name ähnlich")
    elif a["rolle"] == "mieter" and a["hausverwaltung"]:
        dazu(select(Customer.id).where(passt(Customer.name, a["hausverwaltung"])), "Name ähnlich")
    elif a["name"]:
        vorname, nachname = _name_teilen(a["name"])
        bedingung = [telefonbuch(Customer.last_name) == schluessel(nachname)]
        if vorname:
            bedingung.append(telefonbuch(Customer.first_name) == schluessel(vorname))
        dazu(select(Customer.id).where(*bedingung), "Name gleich")
    plz = (a["objekt"] or {}).get("plz")
    kunden = db.scalars(select(Customer).where(Customer.id.in_(list(treffer))).order_by(Customer.id)).all() if treffer else []
    out = []
    for k in kunden:
        gruende = treffer[k.id]
        if plz and (k.postal_code == plz or any(p.postal_code == plz for p in k.properties)):
            gruende.append("PLZ gleich")
        out.append({"id": k.id, "name": k.name, "kundennummer": k.customer_number,
                    "adresse": adresse_text({"strasse": k.street, "plz": k.postal_code, "ort": k.city}), "gruende": gruende})
    out.sort(key=lambda x: (-len(x["gruende"]), schluessel(x["name"]), x["id"]))
    return out[:VORSCHLAEGE_MAX]


def vorschlag(db: Session, zeile: WebAnfrage) -> dict:
    """Was die Seite zum Übernehmen vorschlägt -- schreibt nichts (Regel 23)."""
    a = angaben(zeile)
    objekt = a["objekt"] or {}
    vorname, nachname = _name_teilen(a["name"])
    if a["rolle"] == "verwaltung":
        kunde_neu = {"first_name": None, "last_name": a["firma"], "contact_person": a["name"], "email": a["email"], "phone": a["telefon"],
                     "street": None, "postal_code": None, "city": None}
        auftraggeber = "Die Hausverwaltung bzw. Firma ist Auftraggeber, der Melder ihr Ansprechpartner."
    elif a["rolle"] == "mieter":
        kunde_neu = {"first_name": None, "last_name": a["hausverwaltung"], "contact_person": None, "email": None, "phone": None,
                     "street": None, "postal_code": None, "city": None}
        auftraggeber = "Ein Mieter meldet: Auftraggeber ist die Hausverwaltung bzw. der Vermieter (laut Mieter), der Mieter Ansprechpartner vor Ort."
    else:
        kunde_neu = {"first_name": vorname, "last_name": nachname, "contact_person": None, "email": a["email"], "phone": a["telefon"],
                     "street": objekt.get("strasse"), "postal_code": objekt.get("plz"), "city": objekt.get("ort")}
        auftraggeber = "Der Melder ist Auftraggeber." if a["rolle"] == "eigentuemer" else "Der Kontakt ist Auftraggeber."
    vor_ort = a["vor_ort"] or ({"name": a["name"], "telefon": a["telefon"]} if a["rolle"] == "mieter" and a["name"] else None)
    u = umschlag_lesen(zeile.umschlag) or {}
    beschreibung = u.get("text") if isinstance(u.get("text"), str) else None
    return {
        "rolle": a["rolle"], "auftraggeber": auftraggeber, "kunden": _kunden(db, a), "kunde_neu": {**kunde_neu, "is_consumer": a["verbraucher"]},
        "objekt_neu": {"name": objekt.get("strasse") or "Objekt laut Webseite", "street": objekt.get("strasse"), "postal_code": objekt.get("plz"),
                       "city": objekt.get("ort"), "site_contact_name": (vor_ort or {}).get("name"), "site_contact_phone": (vor_ort or {}).get("telefon")}
        if a["objekt"] else None,
        "vor_ort": vor_ort, "ort_kontakt": a["ort"],
        "anfrage": {"titel": (zeile.betreff or zeile.art_name or zeile.nummer)[:255],
                    "beschreibung": f"Anfrage der Webseite {zeile.nummer}" + (f"\n\n{beschreibung}" if beschreibung else ""),
                    "ansprechpartner": a["name"] if a["rolle"] == "verwaltung" else None},
        "uebernehmen_moeglich": zeile.status == STATUS_NEU and not _in_pruefliste(zeile),
    }


def _in_pruefliste(zeile: WebAnfrage) -> bool:
    from .webanfragen import in_pruefliste
    return in_pruefliste(zeile)


def _strasse_vergleichbar(text: str | None) -> str:
    t = unicodedata.normalize("NFKC", (text or "")).casefold().replace("ß", "ss")
    t = re.sub(r"str\.", "strasse", t)
    return re.sub(r"[\s.\-]", "", t)


def objekte(db: Session, zeile: WebAnfrage, kunde_id: int) -> list[dict]:
    """Die Objekte eines Kunden für die Auswahl -- „Adresse gleich“, wenn Straße und PLZ der Anfrage passen."""
    if db.get(Customer, kunde_id) is None:
        raise LookupError(kunde_id)
    o = angaben(zeile)["objekt"] or {}
    out = []
    for p in db.scalars(select(Property).where(Property.customer_id == kunde_id).order_by(Property.id).limit(OBJEKTE_MAX)).all():
        gleich = bool(o.get("strasse") and o.get("plz")) and p.postal_code == o["plz"] and _strasse_vergleichbar(p.street) == _strasse_vergleichbar(o["strasse"])
        out.append({"id": p.id, "name": p.name, "adresse": adresse_text({"strasse": p.street, "plz": p.postal_code, "ort": p.city}),
                    "hauptadresse": p.is_primary_address, "adresse_gleich": gleich, "site_contact_name": p.site_contact_name,
                    "site_contact_phone": p.site_contact_phone})
    out.sort(key=lambda x: (not x["adresse_gleich"], x["id"]))
    return out


def erp_id_aus(inquiry: Inquiry) -> str:
    """Die Anfragenummer als erp_id (F2) -- passt sie nicht in die Zeichen des Empfangsdienstes, anfrage-<ID>."""
    return inquiry.inquiry_number if ERP_ID.match(inquiry.inquiry_number or "") else f"anfrage-{inquiry.id}"


def uebernehmen(db: Session, webanfrage_id: int, e, user_id: int | None) -> Inquiry:
    """e: WebAnfrageUebernehmenIn (app/schemas.py). Eine Transaktion; Fehler: LookupError (404), SchonErledigt (409), ObjektFremd/AuswahlFehlt (422)."""
    zeile = db.get(WebAnfrage, webanfrage_id)
    if zeile is None:
        raise LookupError(webanfrage_id)
    geschrieben = []
    try:
        treffer = db.execute(sa_update(WebAnfrage).where(WebAnfrage.id == webanfrage_id, WebAnfrage.status == STATUS_NEU, not_(IN_PRUEFLISTE))
                             .values(status=STATUS_UEBERNOMMEN, erledigt_am=datetime.utcnow(), erledigt_von_user_id=user_id)).rowcount
        if treffer != 1:
            raise SchonErledigt()
        if (e.kunde_id is None) == (e.kunde_neu is None):
            raise AuswahlFehlt("Bitte einen Auftraggeber wählen: einen bestehenden Kunden oder einen neuen.")
        if e.kunde_id is not None:
            kunde = db.get(Customer, e.kunde_id)
            if kunde is None:
                raise LookupError(e.kunde_id)
        else:
            kunde = kunde_anlegen(db, e.kunde_neu.model_dump())
        objekt = None
        if e.objekt == "gewaehlt":
            objekt = db.get(Property, e.objekt_id) if e.objekt_id is not None else None
            if objekt is None:
                raise LookupError(e.objekt_id)
            if objekt.customer_id != kunde.id:  # Regel 25: nur ein Objekt des gewählten Kunden
                raise ObjektFremd("Das Objekt gehört nicht zum gewählten Kunden.")
            if e.vor_ort_uebernehmen:
                vor_ort = vorschlag(db, zeile)["vor_ort"]
                if vor_ort:
                    objekt.site_contact_name, objekt.site_contact_phone = vor_ort["name"], vor_ort["telefon"]
        elif e.objekt == "neu":
            if e.objekt_neu is None:
                raise AuswahlFehlt("Bitte die Angaben des neuen Objekts ausfüllen.")
            objekt = Property(customer_id=kunde.id, **e.objekt_neu.model_dump())
            db.add(objekt)
            db.flush()
        elif e.objekt == "hauptadresse":
            if e.kunde_neu is None:
                raise AuswahlFehlt("„Hauptadresse“ nur beim neuen Kunden.")
            objekt = next(p for p in kunde.properties if p.is_primary_address)
        inquiry = Inquiry(inquiry_number=issue_number(db, "inquiry"), customer_id=kunde.id, property_id=objekt.id if objekt else None, title=e.titel,
                          description=e.beschreibung, status="neu", priority=e.prioritaet, source=QUELLE, contact_person=e.ansprechpartner,
                          webseite_nummer=zeile.nummer)
        db.add(inquiry)
        db.flush()
        if objekt is not None:
            kategorie = resolve_category_id(db, KATEGORIE_FOTOS)
            for datei in zeile.dateien:
                if datei.typ != "image/jpeg":
                    continue
                doc = create_property_document(db, objekt.id, category_id=kategorie, file_data=datei_pfad(datei).read_bytes(),
                                               original_filename=f"{zeile.nummer}-{datei.name}",
                                               description=f"Foto der Anfrage der Webseite {zeile.nummer}", commit=False)
                geschrieben.append(document_path(doc))
        db.execute(sa_update(WebAnfrage).where(WebAnfrage.id == webanfrage_id).values(inquiry_id=inquiry.id, melden_soll=erp_id_aus(inquiry)))
        record_audit_entry(db, action="übernommen", entity_type=ART_HISTORIE, entity_id=webanfrage_id, entity_label=zeile.nummer, field_name="status",
                           old_value=STATUS_NEU, new_value=f"{STATUS_UEBERNOMMEN} ({inquiry.inquiry_number})")
        db.commit()
    except BaseException:
        db.rollback()
        for pfad in geschrieben:
            pfad.unlink(missing_ok=True)
        raise
    return inquiry
