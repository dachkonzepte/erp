"""Freigaben und Lese-Funktionen der Unterlagen im Kundenportal (seit 1.11.31, Stufe P2a; Bauplan P2, B1, B4, B7 mit Nachtrag vom 26.11.2026).

Festlegungen 1.11.31 (Gegenproben in docs/archiv/gegenproben-portal.md, „1.11.31“):
1. Sichtbar ist nur, was als Freigabe für den Kunden der Sitzung steht, nicht zurückgenommen ist und eine bereite Kopie hat.
2. Zusätzlich muss die Kette der Quelle heute zu genau diesem Kunden führen -- sonst ruht die Freigabe (Kunde der Rechnung gewechselt, Objekt umgehängt,
   Quelle gelöscht).
3. Nie sichtbar: Rechnung im Entwurf, ersetzte oder nicht versendete Mahnung, Einsatzbericht ohne feste Fassung, Projekt als Mustervorgang oder im Archiv.
4. Jede Quelle hat genau einen Zweig in der Kette (fest im SQL, ohne dynamisches SQL); jeder Zweig läuft fehlerfrei.
5. Die Gruppe im Portal ist Auftragsnummer und Adresse des Objekts, nie der Projekttitel.
6. Eine Datei gibt es nur nach einer Anforderung derselben Sitzung für diese Freigabe in den letzten 30 Minuten; portal_datei() schreibt nichts.
7. Liste und Anforderung schreiben das Zugriffsprotokoll (Aktion, Ergebnis, Freigabe -- kein Inhalt) und zählen die Bremsen (Liste 120 je Sitzung und
   Stunde; Anforderung 300 je Zugang und Stunde, 1500 je Tag, 300 je Anschluss und Stunde, 5000 gesamt je Stunde).
8. Der Benutzer des Portals liest portal_freigaben nicht und ruft keinen Helfer auf; er darf genau die drei Funktionen.
9. Höchstens eine nicht zurückgenommene Freigabe je Quelle; eine Freigabe hält den Rückweg eines Adressimports auf wie ein Zugang.
"""

import importlib.util
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Customer, CustomerDocument, DocumentCategory, ImportRun, Invoice, Order, PortalFreigabe, Project, Property, PropertyDocument, Reminder, SentDocument,
    ServiceReport,
)
from app.portal import pruefwerte, unterlagen, werte
from app.portal.rechte import FUNKTIONEN
from app.project_pipeline_columns import default_pipeline_column_id
from tests.quellangebot import quell_angebot
from tests.test_v800_portal_funktionen import HIER, TESTROLLE, pg  # noqa: F401  (Fixture)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "e5c8a1f3b9d2"


def _migration():
    pfad = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_unterlagen", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# --- ohne Datenbank -----------------------------------------------------------------------------------------------------------------------------------

def test_jede_quelle_hat_genau_einen_zweig():
    """Festlegung 4."""
    assert sorted(unterlagen.ZWEIGE) == sorted(werte.FREIGABE_QUELLEN) and len(unterlagen.ZWEIGE) == len(set(unterlagen.ZWEIGE))


def test_funktionen_fester_pfad_ohne_dynamisches_sql_und_rechte():
    """Festlegungen 4 und 8: fester search_path, kein EXECUTE/format(); SECURITY DEFINER genau die drei für das Portal, jede für alle entzogen."""
    erzeugen = [a for a in unterlagen.ANWEISUNGEN if a.startswith("CREATE OR REPLACE FUNCTION")]
    for a in erzeugen:
        assert "SET search_path = pg_catalog, @SCHEMA@, pg_temp" in a
        assert not re.search(r"\bEXECUTE\b|\bformat\s*\(", a, re.I), a[:80]
    definer = {re.match(r"CREATE OR REPLACE FUNCTION (\w+)\(", a).group(1) for a in erzeugen if "SECURITY DEFINER" in a}
    assert definer == set(unterlagen.FUER_DAS_PORTAL) == {"portal_unterlagen", "portal_datei_anfordern", "portal_datei"}
    assert set(unterlagen.FUER_DAS_PORTAL) <= set(FUNKTIONEN)
    erzeugt = {re.match(r"CREATE OR REPLACE FUNCTION (\w+)\(", a).group(1) for a in erzeugen}
    entzogen = {re.match(r"REVOKE ALL ON FUNCTION (\w+)\(", a).group(1) for a in unterlagen.ANWEISUNGEN if a.startswith("REVOKE")}
    assert erzeugt == entzogen


def test_migration_traegt_anweisungen_und_checks_woertlich():
    from app.models import portal_in
    modul = _migration()
    assert modul.ANWEISUNGEN == unterlagen.ANWEISUNGEN
    assert modul.CHECKS == {
        "ck_portal_freigabe_art": portal_in("art", werte.FREIGABE_ARTEN),
        "ck_portal_freigabe_quelle": portal_in("quelle", werte.FREIGABE_QUELLEN),
        "ck_portal_freigabe_kopie_typ": portal_in("kopie_typ", werte.KOPIE_TYPEN, leer=True),
        "ck_portal_freigabe_kopie_fehler": portal_in("kopie_fehler", werte.KOPIE_FEHLER, leer=True),
        "ck_portal_zugriff_aktion": portal_in("aktion", werte.AKTIONEN),
    }


def _freigabe(db, kunde_id, quelle, quelle_id, *, art="dokument", bereit=True, titel="Unterlage", datum=date(2026, 11, 20)):
    f = PortalFreigabe(customer_id=kunde_id, art=art, quelle=quelle, quelle_id=quelle_id, titel=titel, datum=datum, freigegeben_am=datetime.utcnow(),
                       freigegeben_von_name="Büro", kopie_name=(uuid.uuid4().hex + ".pdf") if bereit else None,
                       kopie_typ="application/pdf" if bereit else None, kopie_groesse=1234 if bereit else None,
                       kopie_bereit_am=datetime.utcnow() if bereit else None)
    db.add(f)
    db.flush()
    return f


def test_hoechstens_eine_aktive_freigabe_je_quelle(db_session):
    """Festlegung 9 (SQLite): eine zweite aktive Freigabe derselben Quelle scheitert; nach der Rücknahme geht eine neue."""
    db = db_session
    k = Customer(name="Kundin", last_name="Kundin")
    db.add(k); db.flush()
    erste = _freigabe(db, k.id, "customer_documents", 7)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            _freigabe(db, k.id, "customer_documents", 7)
    erste.zurueckgenommen_am = datetime.utcnow()
    db.flush()
    _freigabe(db, k.id, "customer_documents", 7)
    db.commit()


def test_freigabe_haelt_den_rueckweg_eines_adressimports_auf(db_session):
    """Festlegung 9: wie ein Zugang -- ihr Fremdschlüssel ließe das Löschen des Kunden sonst scheitern."""
    from app.address_import import _run_is_untouched
    db = db_session
    lauf = ImportRun(source_filename="adressen.csv")
    db.add(lauf); db.flush()
    k = Customer(name="Import Muster", last_name="Muster", import_run_id=lauf.id)
    db.add(k); db.commit()
    assert _run_is_untouched(db, lauf) is True
    _freigabe(db, k.id, "customer_documents", 1)
    db.commit()
    assert _run_is_untouched(db, lauf) is False


def test_karte_nennt_die_neuen_aktionen(db_session):
    """Festlegung 11: im Protokoll der Karte „Kundenportal“ heißen die neuen Aktionen „Unterlagen geöffnet“ und „Unterlage angefordert“; eine Anforderung,
    die nichts fand, „– nicht verfügbar“ (nicht „unbekannter Link“)."""
    from app import kundenportal as kp
    from app.models import PortalZugang, PortalZugriff
    db = db_session
    k = Customer(name="Kundin", last_name="Kundin")
    db.add(k); db.flush()
    z = PortalZugang(customer_id=k.id, email="k@example.invalid", email_anzeige="k***@example.invalid")
    db.add(z); db.flush()
    for i, (aktion, ergebnis) in enumerate((("unterlagen", "ok"), ("datei_angefordert", "ok"), ("datei_angefordert", "unbekannt"))):
        db.add(PortalZugriff(zeitpunkt=datetime(2026, 11, 26, 10, i), zugang_id=z.id, aktion=aktion, ergebnis=ergebnis,
                             objekt_art="freigabe" if aktion == "datei_angefordert" else None, objekt_id=7 if aktion == "datei_angefordert" else None))
    db.commit()
    texte = [e["text"] for e in kp.protokoll(db, k)["eintraege"] if e["art"] == "portal"]
    assert texte == ["Unterlage angefordert – nicht verfügbar", "Unterlage angefordert", "Unterlagen geöffnet"]


# --- PostgreSQL ----------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def w(pg):  # noqa: F811
    from app.grunddaten import anlegen
    db = sessionmaker(bind=pg.engine)()
    anlegen(db)
    db.commit()
    kunde, _zugang, link = pg.kunde()
    anderer, _z2, link2 = pg.kunde(nachname="Fremd", link="F")
    welt = SimpleNamespace(pg=pg, db=db, kunde=kunde, anderer=anderer, sitz=pg.angemeldet(link), sitz2=pg.angemeldet(link2),
                           sitz_b=pg.angemeldet(link),  # zweites Gerät desselben Kunden
                           zugang=_zugang, kategorie=db.scalar(select(DocumentCategory.id).order_by(DocumentCategory.id).limit(1)))
    try:
        yield welt
    finally:
        db.close()


def _liste(w, sitz=None):
    return [tuple(r) for r in w.pg.als_portal("SELECT * FROM portal_unterlagen(:s)", s=pruefwerte.sitzung(sitz or w.sitz))]


def _ids(w, sitz=None):
    zeilen = _liste(w, sitz)
    if zeilen[0][0] == "leer":
        assert len(zeilen) == 1
        return []
    assert {z[0] for z in zeilen} == {"ok"}, zeilen
    return [z[2] for z in zeilen]


def _objekt(w, kunde=None, strasse="Hafenweg 3"):
    o = Property(customer_id=kunde or w.kunde, name="Halle", street=strasse, postal_code="12345", city="Musterstadt")
    w.db.add(o); w.db.flush()
    return o


def _projekt(w, kunde=None, objekt=None, nr="P-1"):
    p = Project(project_number=f"{nr}-{uuid.uuid4().hex[:6]}", name="Interner Titel", customer_id=kunde or w.kunde,
                property_id=objekt.id if objekt else None, status="anfrage", pipeline_column_id=default_pipeline_column_id(w.db))
    w.db.add(p); w.db.flush()
    return p


def _auftrag(w, projekt, kunde=None, nr=None):
    nr = nr or f"A-{uuid.uuid4().hex[:6]}"
    o = Order(order_number=nr, project_id=projekt.id, source_quote_id=quell_angebot(w.db, projekt.id, nr), quote_number_snapshot=f"Q-{nr}",
              title="Dach", customer_name="x",
              customer_id=kunde or projekt.customer_id)
    w.db.add(o); w.db.flush()
    return o


def _rechnung(w, auftrag, *, status="versendet", kunde=None):
    i = Invoice(order_id=auftrag.id, invoice_type="abschlag", customer_name="x", status=status, customer_id=kunde or auftrag.customer_id,
                invoice_number=f"R-{uuid.uuid4().hex[:6]}" if status != "entwurf" else None)
    w.db.add(i); w.db.flush()
    return i


def _ablage(w, art, dok_id):
    s = SentDocument(document_type=art, document_id=dok_id, filename="x.pdf", stored_filename=f"2026/11/{uuid.uuid4().hex}.pdf", size_bytes=10,
                     sha256="0" * 64, created_by_name="Test")
    w.db.add(s); w.db.flush()
    return s


def _kundendokument(w, kunde=None):
    d = CustomerDocument(customer_id=kunde or w.kunde, category_id=w.kategorie, original_filename="plan.pdf", stored_filename=uuid.uuid4().hex)
    w.db.add(d); w.db.flush()
    return d


def test_pg_sichtbarkeit_grundregeln(w):
    """Festlegung 1: eigene Sitzung sieht die Freigabe; die Sitzung eines anderen Kunden nicht; ohne gültige Sitzung „ungueltig“; ohne bereite Kopie
    und nach der Rücknahme nicht."""
    a = _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id)
    _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id, bereit=False)
    w.db.commit()
    assert _ids(w) == [a.id]
    assert _ids(w, w.sitz2) == []
    assert _liste(w, "keine-sitzung")[0][0] == "ungueltig"
    w.db.execute(text("UPDATE portal_freigaben SET zurueckgenommen_am = now() WHERE id = :f"), {"f": a.id})
    w.db.commit()
    assert _ids(w) == []


def test_pg_kette_fuehrt_nicht_mehr_zum_kunden_ruht(w):
    """Festlegung 2: Rechnung mit anderem Kunden, Objekt (an der Prüfung vorbei) umgehängt, Kundendokument gelöscht -- jede ruht, auch der neue Kunde
    sieht nichts; die Freigabe bleibt als Zeile."""
    a = _auftrag(w, _projekt(w, objekt=_objekt(w)))
    rechnung = _rechnung(w, a)
    fr = _freigabe(w.db, w.kunde, "invoices", rechnung.id, art="rechnung")
    o = _objekt(w)
    d = PropertyDocument(property_id=o.id, category_id=w.kategorie, original_filename="foto.jpg", stored_filename=uuid.uuid4().hex)
    w.db.add(d); w.db.flush()
    fo = _freigabe(w.db, w.kunde, "property_documents", d.id, art="foto")
    kd = _kundendokument(w)
    fk = _freigabe(w.db, w.kunde, "customer_documents", kd.id)
    w.db.commit()
    assert sorted(_ids(w)) == sorted([fr.id, fo.id, fk.id])
    w.db.execute(text("UPDATE invoices SET customer_id = :k WHERE id = :i"), {"k": w.anderer, "i": rechnung.id})
    w.db.commit()
    assert sorted(_ids(w)) == sorted([fo.id, fk.id]), "Rechnung mit anderem Kunden"
    w.db.execute(text("UPDATE properties SET customer_id = :k WHERE id = :o"), {"k": w.anderer, "o": o.id})
    w.db.commit()
    assert _ids(w) == [fk.id], "Objekt umgehängt"
    w.db.execute(text("DELETE FROM customer_documents WHERE id = :d"), {"d": kd.id})
    w.db.commit()
    assert _ids(w) == [], "Quelle gelöscht"
    assert _ids(w, w.sitz2) == []
    assert w.db.get(PortalFreigabe, fk.id) is not None


def test_pg_nie_sichtbar(w):
    """Festlegung 3: Rechnung im Entwurf; ersetzte Mahnung; Einsatzbericht ohne feste Fassung; Projekt als Mustervorgang oder im Archiv."""
    p = _projekt(w)
    a = _auftrag(w, p)
    entwurf, rechnung = _rechnung(w, a, status="entwurf"), _rechnung(w, a)
    fe = _freigabe(w.db, w.kunde, "invoices", entwurf.id, art="rechnung")
    m = Reminder(invoice_id=rechnung.id, level=1, status="versendet")
    w.db.add(m); w.db.flush()
    fm = _freigabe(w.db, w.kunde, "reminders", m.id, art="mahnung")
    b = ServiceReport(order_id=a.id, report_type="wartung", status="unterschrieben")
    w.db.add(b); w.db.flush()
    fb = _freigabe(w.db, w.kunde, "service_reports", b.id, art="einsatzbericht")
    s = _ablage(w, "angebot", quell_angebot(w.db, p.id, "X1"))
    fa = _freigabe(w.db, w.kunde, "sent_documents", s.id, art="angebot")
    w.db.commit()
    sichtbar = _ids(w)
    assert sorted(sichtbar) == sorted([fm.id, fa.id]) and fe.id not in sichtbar and fb.id not in sichtbar, "Entwurf, Bericht ohne Fassung"
    w.db.execute(text("UPDATE service_reports SET pdf_document_id = :d WHERE id = :b"), {"d": _ablage(w, "einsatzbericht", b.id).id, "b": b.id})
    w.db.commit()
    assert fb.id in _ids(w), "Bericht mit Fassung"
    m2 = Reminder(invoice_id=rechnung.id, level=1, status="versendet")
    w.db.add(m2); w.db.flush()
    w.db.execute(text("UPDATE reminders SET replaced_by_id = :n WHERE id = :m"), {"n": m2.id, "m": m.id})
    w.db.commit()
    assert fm.id not in _ids(w), "Mahnung ersetzt"
    for spalte in ("is_template", "archived"):
        w.db.execute(text(f"UPDATE projects SET {spalte} = true WHERE id = :p"), {"p": p.id})
        w.db.commit()
        assert _ids(w) == [], spalte
        w.db.execute(text(f"UPDATE projects SET {spalte} = false WHERE id = :p"), {"p": p.id})
        w.db.commit()
    assert sorted(_ids(w)) == sorted([fa.id, fb.id])


def test_pg_gruppe_und_jeder_zweig(w):
    """Festlegungen 4 und 5: Auftragsnummer und Adresse des Objekts, nie der Projekttitel („Interner Titel“); jeder Zweig der Kette läuft fehlerfrei
    (plpgsql prüft einen Zweig erst beim Ausführen) und liefert für eine unbekannte ID nichts."""
    a = _auftrag(w, _projekt(w, objekt=_objekt(w)), nr="A-2026-0042")
    s = _ablage(w, "auftrag", a.id)
    _freigabe(w.db, w.kunde, "sent_documents", s.id, art="auftrag", titel="Auftragsbestätigung")
    w.db.commit()
    (zeile,) = _liste(w)
    assert zeile[3:] == ("auftrag", "Auftragsbestätigung", date(2026, 11, 20), "application/pdf", 1234, "A-2026-0042", "Hafenweg 3, 12345 Musterstadt")
    assert "Interner Titel" not in repr(zeile)
    for quelle in werte.FREIGABE_QUELLEN:
        assert w.pg.erp("SELECT * FROM portal_quelle(:q, 0)", q=quelle) == [], quelle


def test_pg_datei_nur_nach_anforderung_derselben_sitzung(w):
    """Festlegung 6: vorher „unbekannt“; nach der Anforderung Name, Typ, Größe, Titel; eine andere Sitzung, eine fremde Freigabe und eine Anforderung
    älter als 30 Minuten nicht; portal_datei() schreibt nichts."""
    f = _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id, titel="Plan")
    fremd = _freigabe(w.db, w.anderer, "customer_documents", _kundendokument(w, w.anderer).id)
    w.db.commit()

    def datei(sitz, freigabe):
        return tuple(w.pg.als_portal("SELECT * FROM portal_datei(:s, :f)", s=pruefwerte.sitzung(sitz), f=freigabe)[0])

    def anfordern(sitz, freigabe, anschluss=HIER):
        return tuple(w.pg.als_portal("SELECT * FROM portal_datei_anfordern(:s, :f, :a)", s=pruefwerte.sitzung(sitz), f=freigabe, a=anschluss)[0])

    vorher = w.pg.erp("SELECT count(*) FROM portal_zugriffe")[0][0]
    assert datei(w.sitz, f.id)[0] == "unbekannt"
    assert w.pg.erp("SELECT count(*) FROM portal_zugriffe")[0][0] == vorher
    assert anfordern(w.sitz, f.id) == ("ok", None)
    assert datei(w.sitz, f.id) == ("ok", f.kopie_name, "application/pdf", 1234, "Plan")
    assert datei(w.sitz2, f.id)[0] == "unbekannt"
    assert datei(w.sitz_b, f.id)[0] == "unbekannt"  # derselbe Kunde, anderes Gerät: eigene Anforderung nötig
    assert anfordern(w.sitz, fremd.id) == ("unbekannt", None) and datei(w.sitz, fremd.id)[0] == "unbekannt"
    assert anfordern(w.sitz, f.id, anschluss="kein-pruefwert") == ("ungueltig", None)
    w.pg.erp("UPDATE portal_zugriffe SET zeitpunkt = zeitpunkt - interval '31 minutes' WHERE aktion = 'datei_angefordert'")
    assert datei(w.sitz, f.id)[0] == "unbekannt"


def _bremse_voll(w, schluessel, grenze, fenster_sekunden):
    w.pg.erp("INSERT INTO portal_bremsen AS b (schluessel, fenster_beginn, zaehler) VALUES "
             "(:k, to_timestamp(floor(extract(epoch FROM portal_jetzt()) / :f) * :f) AT TIME ZONE 'utc', :g) "
             "ON CONFLICT (schluessel, fenster_beginn) DO UPDATE SET zaehler = EXCLUDED.zaehler", k=schluessel, f=fenster_sekunden, g=grenze)


def test_pg_protokoll_bremsen_und_rechte(w):
    """Festlegungen 7 und 8: das Protokoll nennt Aktion, Ergebnis und Freigabe; Liste je Sitzung 120 je Stunde, Anforderung je Zugang 300 je Stunde;
    die Rolle des Portals liest portal_freigaben nicht und ruft keinen Helfer auf (SQLSTATE 42501)."""
    f = _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id)
    w.db.commit()
    _ids(w)
    w.pg.als_portal("SELECT * FROM portal_datei_anfordern(:s, :f, :a)", s=pruefwerte.sitzung(w.sitz), f=f.id, a=HIER)
    zeilen = w.pg.erp("SELECT aktion, ergebnis, objekt_art, objekt_id FROM portal_zugriffe WHERE aktion IN ('unterlagen', 'datei_angefordert') "
                      "ORDER BY id")
    assert [tuple(z) for z in zeilen] == [("unterlagen", "ok", None, None), ("datei_angefordert", "ok", "freigabe", f.id)]
    sitzung_id = w.pg.erp("SELECT id FROM portal_sitzungen WHERE wert_sha256 = :s", s=pruefwerte.sitzung(w.sitz))[0][0]
    _bremse_voll(w, f"liste:s:{sitzung_id}", 120, 3600)
    erg = _liste(w)[0]
    assert erg[0] == "bremse" and erg[1] >= 1, erg
    _bremse_voll(w, f"datei:z:{w.zugang}", 300, 3600)
    erg = tuple(w.pg.als_portal("SELECT * FROM portal_datei_anfordern(:s, :f, :a)", s=pruefwerte.sitzung(w.sitz), f=f.id, a=HIER)[0])
    assert erg[0] == "bremse" and erg[1] >= 1, erg
    for sql in ("SELECT * FROM portal_freigaben", "SELECT * FROM portal_quelle('customer_documents', 1)", "SELECT portal_sichtbar(1, 1)"):
        with pytest.raises(ProgrammingError) as fehler:
            w.pg.als_portal(sql)
        assert fehler.value.orig.sqlstate == "42501", sql
    # das Recht selbst, nicht nur der Fehler (ein Helfer ohne SECURITY DEFINER scheiterte sonst auch an den Tabellen): kein EXECUTE auf einen Helfer,
    # EXECUTE auf genau die drei Funktionen
    for signatur, _sql in unterlagen._HELFER:
        assert not w.pg.erp("SELECT has_function_privilege(:r, :f, 'EXECUTE')", r=TESTROLLE, f=signatur)[0][0], f"Helfer ausführbar: {signatur}"
    for name, argumente in unterlagen.FUER_DAS_PORTAL.items():
        signatur = f"{name}({', '.join(a.split()[-1] for a in argumente.split(', '))})"
        assert w.pg.erp("SELECT has_function_privilege(:r, :f, 'EXECUTE')", r=TESTROLLE, f=signatur)[0][0], signatur
