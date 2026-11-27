"""Version 1.11.42 (Stufe P2d, Teil 2): die Funktionen der Datenbank für Rechnungen und Termine des Kundenportals -- app/portal/schaufenster.py.

    Ohne Datenbank  fester search_path, kein dynamisches SQL, SECURITY DEFINER genau die zwei, jede für alle entzogen; die Ausgabe genau die Felder der
                    Positivliste; die Migration trägt Text und Prüfung wörtlich; die Karte nennt die neuen Aktionen
    PostgreSQL      Rechnungen: nur sichtbare (Freigabe, Kopie bereit, Kette zum Kunden) mit dem Zahlstand aus dem Schaufenster, ohne ihn ohne Zustand;
                    die Mahnung heißt wie ihre Stufe und hängt an der Freigabe ihrer Rechnung; Stand in jeder Zeile; ein anderer Kunde sieht nichts
                    Termine: aus dem Schaufenster, live dazu Auftrag des Kunden, läuft oder pausiert, Projekt offen
                    beide: ohne Sitzung „ungueltig“, ohne Zeile „leer“ mit Stand, Bremse der Listen, Protokoll; die Rolle des Portals liest die Tabellen nicht
"""

import importlib.util
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.berlin_time import berlin_today
from app.models import Reminder, portal_in
from app.portal import pruefwerte, schaufenster, werte
from app.portal.rechte import FUNKTIONEN
from tests.test_v800_portal_funktionen import TESTROLLE, pg  # noqa: F401  (Fixture)
from tests.test_v821_portal_unterlagen import (  # noqa: F401  (w ist eine Fixture)
    _auftrag, _bremse_voll, _freigabe, _kundendokument, _objekt, _projekt, _rechnung, w,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = "d7a3f9c2e5b1"
D = Decimal

AUSGABE = {  # Positivliste je Funktion: genau diese Felder
    "portal_rechnungen": ["ergebnis", "minuten", "stand", "freigabe", "art", "titel", "nummer", "datum", "faellig", "betrag", "zustand", "offen",
                          "ueberfaellig", "bezug", "zu_freigabe", "auftrag", "objekt"],
    "portal_termine": ["ergebnis", "minuten", "stand", "auftrag", "objekt", "von", "bis"],
    "portal_uebersicht": ["ergebnis", "minuten", "stand", "offen_anzahl", "offen_summe", "faellig_titel", "faellig_nummer", "faellig_am", "einsatz_von",
                          "einsatz_bis", "einsatz_auftrag", "einsatz_objekt", "unterlagen", "unterlage_titel", "unterlage_datum", "fotos", "foto_am"],
}


def _migration():
    pfad = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_schaufenster_funktionen", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# --- ohne Datenbank -----------------------------------------------------------------------------------------------------------------------------------

def test_funktionen_fester_pfad_ohne_dynamisches_sql_und_rechte():
    erzeugen = [a for a in schaufenster.ANWEISUNGEN if a.startswith("CREATE OR REPLACE FUNCTION")]
    for a in erzeugen:
        assert "SET search_path = pg_catalog, @SCHEMA@, pg_temp" in a and "SECURITY DEFINER" in a
        assert not re.search(r"\bEXECUTE\b|\bformat\s*\(", a, re.I), a[:80]
    erzeugt = {re.match(r"CREATE OR REPLACE FUNCTION (\w+)\(", a).group(1) for a in erzeugen}
    entzogen = {re.match(r"REVOKE ALL ON FUNCTION (\w+)\(", a).group(1) for a in schaufenster.ANWEISUNGEN if a.startswith("REVOKE")}
    assert erzeugt == entzogen == set(schaufenster.FUER_DAS_PORTAL) == {"portal_rechnungen", "portal_termine", "portal_uebersicht"}
    assert set(schaufenster.FUER_DAS_PORTAL) <= set(FUNKTIONEN)


def test_ausgabe_genau_die_felder_der_positivliste():
    for a in schaufenster.ANWEISUNGEN:
        if a.startswith("CREATE"):
            name = re.match(r"CREATE OR REPLACE FUNCTION (\w+)\(", a).group(1)
            felder = re.search(r"RETURNS TABLE \((.*?)\)\s*\nLANGUAGE", a, re.S).group(1)
            assert [f.split()[0] for f in felder.replace("\n", " ").split(",")] == AUSGABE[name], name


def test_kein_feld_mit_namen_oder_inhalt():
    """Was das Portal nie bekommt: Namen von Personen, Kolonne, Gerät, Notiz, der Projekttitel."""
    for a in schaufenster.ANWEISUNGEN:
        for verboten in ("planning_slot_employees", "employees", "teams", "notes", "p.name", "first_name", "last_name"):
            assert verboten not in a, (verboten, a[:60])


def test_migration_traegt_text_und_pruefung_woertlich():
    modul = _migration()
    assert modul.ANWEISUNGEN == schaufenster.ANWEISUNGEN and schaufenster.MIGRATIONEN == (MIGRATION,)
    assert modul.down_revision == "c4e8a2f6b1d3"
    assert modul.CHECKS == {"ck_portal_zugriff_aktion": portal_in("aktion", werte.AKTIONEN)}
    assert modul.AKTION_VORHER == portal_in("aktion", tuple(a for a in werte.AKTIONEN if a not in ("rechnungen", "termine", "uebersicht")))


def test_karte_nennt_die_neuen_aktionen(db_session):
    from app import kundenportal as kp
    from app.models import Customer, PortalZugang, PortalZugriff
    db = db_session
    k = Customer(name="Kundin", last_name="Kundin")
    db.add(k); db.flush()
    z = PortalZugang(customer_id=k.id, email="k@example.invalid", email_anzeige="k***@example.invalid")
    db.add(z); db.flush()
    for i, aktion in enumerate(("rechnungen", "termine", "uebersicht")):
        db.add(PortalZugriff(zeitpunkt=datetime(2026, 11, 27, 10, i), zugang_id=z.id, aktion=aktion, ergebnis="ok"))
    db.commit()
    assert [e["text"] for e in kp.protokoll(db, k)["eintraege"] if e["art"] == "portal"] == ["Übersicht geöffnet", "Termine geöffnet", "Rechnungen geöffnet"]


# --- PostgreSQL ----------------------------------------------------------------------------------------------------------------------------------------

def _rechnungen(w, sitz=None):
    return [dict(r._mapping) for r in w.pg.als_portal("SELECT * FROM portal_rechnungen(:s)", s=pruefwerte.sitzung(sitz or w.sitz))]


def _termine(w, sitz=None):
    return [dict(r._mapping) for r in w.pg.als_portal("SELECT * FROM portal_termine(:s)", s=pruefwerte.sitzung(sitz or w.sitz))]


def _zahlstand(w, rechnung, kunde=None, **werte_):
    zeile = {"nummer": rechnung.invoice_number, "art_text": "Abschlagsrechnung", "datum": date(2026, 11, 20), "faellig": date(2026, 12, 4),
             "brutto": D("2380.00"), "zustand": "teilweise_bezahlt", "offen": D("1380.00"), "ueberfaellig": False, "bezug_nummer": None, **werte_}
    w.pg.erp("INSERT INTO portal_rechnungen (customer_id, invoice_id, order_id, nummer, art_text, datum, faellig, brutto, zustand, offen, ueberfaellig, "
             "bezug_nummer, stand_am) VALUES (:k, :i, :o, :nummer, :art_text, :datum, :faellig, :brutto, :zustand, :offen, :ueberfaellig, :bezug_nummer, "
             "TIMESTAMP '2026-11-27 09:00')", k=kunde or w.kunde, i=rechnung.id, o=rechnung.order_id, **zeile)


def _stand(w, kunde=None, am="2026-11-27 09:00"):
    w.pg.erp("INSERT INTO portal_schaufenster (customer_id, stand_am) VALUES (:k, CAST(:a AS timestamp)) "
             "ON CONFLICT (customer_id) DO UPDATE SET stand_am = EXCLUDED.stand_am", k=kunde or w.kunde, a=am)


def test_pg_rechnungen_mit_zahlstand_mahnung_und_stand(w):
    a = _auftrag(w, _projekt(w, objekt=_objekt(w)), nr="A-2026-0118")
    mit, ohne_stand, nicht_frei, nicht_bereit = (_rechnung(w, a) for _ in range(4))
    f_mit = _freigabe(w.db, w.kunde, "invoices", mit.id, art="rechnung", titel=f"Abschlagsrechnung {mit.invoice_number}")
    f_ohne = _freigabe(w.db, w.kunde, "invoices", ohne_stand.id, art="rechnung", titel=f"Rechnung {ohne_stand.invoice_number}")
    _freigabe(w.db, w.kunde, "invoices", nicht_bereit.id, art="rechnung", bereit=False)
    m1 = Reminder(invoice_id=mit.id, level=1, status="versendet", reminder_number="M-1", reminder_date=date(2026, 12, 10))
    m2 = Reminder(invoice_id=nicht_bereit.id, level=2, status="versendet", reminder_number="M-2", reminder_date=date(2026, 12, 11))
    w.db.add_all([m1, m2]); w.db.flush()
    f_m1 = _freigabe(w.db, w.kunde, "reminders", m1.id, art="mahnung", titel="1. Mahnung M-1", datum=date(2026, 12, 10))
    f_m2 = _freigabe(w.db, w.kunde, "reminders", m2.id, art="mahnung", titel="2. Mahnung M-2", datum=date(2026, 12, 11))
    w.db.commit()
    w.pg.erp("UPDATE reminder_levels SET label = 'Zahlungserinnerung' WHERE level = 1")
    _zahlstand(w, mit)
    _stand(w)
    zeilen = _rechnungen(w)
    assert {z["ergebnis"] for z in zeilen} == {"ok"} and {z["stand"] for z in zeilen} == {datetime(2026, 11, 27, 9, 0)}
    je = {z["freigabe"]: z for z in zeilen}
    assert set(je) == {f_mit.id, f_ohne.id, f_m1.id, f_m2.id}
    z = je[f_mit.id]
    assert (z["art"], z["titel"], z["nummer"], z["faellig"], z["betrag"], z["zustand"], z["offen"], z["ueberfaellig"], z["auftrag"], z["objekt"]) == (
        "rechnung", "Abschlagsrechnung", mit.invoice_number, date(2026, 12, 4), D("2380.00"), "teilweise_bezahlt", D("1380.00"), False, "A-2026-0118",
        "Hafenweg 3, 12345 Musterstadt")
    z = je[f_ohne.id]  # sichtbar, der Postbote hat sie noch nicht gerechnet: ohne Zustand, der Titel der Freigabe
    assert (z["titel"], z["zustand"], z["betrag"], z["offen"]) == (f"Rechnung {ohne_stand.invoice_number}", None, None, None)
    z = je[f_m1.id]  # heißt wie die Stufe im ERP, hängt an seiner Rechnung
    assert (z["art"], z["titel"], z["nummer"], z["zu_freigabe"], z["datum"], z["zustand"]) == ("mahnung", "Zahlungserinnerung", "M-1", f_mit.id,
                                                                                            date(2026, 12, 10), None)
    z = je[f_m2.id]  # ihre Rechnung hat eine Freigabe, ist aber nicht sichtbar (Kopie nicht bereit)
    assert (z["titel"], z["zu_freigabe"]) == ("2. Mahnung", None)
    assert [z["ergebnis"] for z in _rechnungen(w, w.sitz2)] == ["leer"]


def test_pg_zahlstand_eines_anderen_kunden_zaehlt_nicht(w):
    """Die Zeile des Schaufensters gilt nur für ihren Kunden (wechselt die Rechnung den Kunden, ruht ohnehin die Freigabe)."""
    r = _rechnung(w, _auftrag(w, _projekt(w)))
    f = _freigabe(w.db, w.kunde, "invoices", r.id, art="rechnung")
    w.db.commit()
    _zahlstand(w, r, kunde=w.anderer)
    (z,) = _rechnungen(w)
    assert (z["freigabe"], z["zustand"]) == (f.id, None)


def _termin(w, auftrag, von, bis, kunde=None):
    w.pg.erp("INSERT INTO portal_termine (customer_id, order_id, von, bis, stand_am) VALUES (:k, :o, :v, :b, TIMESTAMP '2026-11-27 09:00')",
             k=kunde or w.kunde, o=auftrag.id, v=von, b=bis)


def test_pg_termine_mit_auftrag_und_adresse_live_geprueft(w):
    a = _auftrag(w, _projekt(w, objekt=_objekt(w)), nr="A-2026-0120")
    b = _auftrag(w, _projekt(w, objekt=_objekt(w, strasse="Musterweg 12")), nr="A-2026-0121")
    w.db.commit()
    _termin(w, a, date(2026, 12, 7), date(2026, 12, 11))
    _termin(w, b, date(2026, 12, 1), date(2026, 12, 1))
    _termin(w, a, date(2026, 12, 14), date(2026, 12, 14))
    _stand(w)
    assert [(z["auftrag"], z["objekt"], z["von"], z["bis"]) for z in _termine(w)] == [
        ("A-2026-0121", "Musterweg 12, 12345 Musterstadt", date(2026, 12, 1), date(2026, 12, 1)),
        ("A-2026-0120", "Hafenweg 3, 12345 Musterstadt", date(2026, 12, 7), date(2026, 12, 11)),
        ("A-2026-0120", "Hafenweg 3, 12345 Musterstadt", date(2026, 12, 14), date(2026, 12, 14)),
    ]
    assert [z["ergebnis"] for z in _termine(w, w.sitz2)] == ["leer"]
    for aenderung, zurueck in (
            ("UPDATE orders SET status = 'storniert' WHERE id = :o", "UPDATE orders SET status = 'laeuft' WHERE id = :o"),
            ("UPDATE orders SET status = 'abgeschlossen' WHERE id = :o", "UPDATE orders SET status = 'laeuft' WHERE id = :o"),
            ("UPDATE projects SET archived = true WHERE id = (SELECT project_id FROM orders WHERE id = :o)",
             "UPDATE projects SET archived = false WHERE id = (SELECT project_id FROM orders WHERE id = :o)"),
            (f"UPDATE orders SET customer_id = {w.anderer} WHERE id = :o", f"UPDATE orders SET customer_id = {w.kunde} WHERE id = :o")):
        w.pg.erp(aenderung, o=b.id)
        assert [z["auftrag"] for z in _termine(w)] == ["A-2026-0120", "A-2026-0120"], aenderung
        w.pg.erp(zurueck, o=b.id)
    w.pg.erp("UPDATE orders SET status = 'pausiert' WHERE id = :o", o=b.id)
    assert len(_termine(w)) == 3


def test_pg_ungueltig_leer_mit_stand_bremse_und_protokoll(w):
    for fn in ("portal_rechnungen", "portal_termine", "portal_uebersicht"):
        (z,) = [dict(r._mapping) for r in w.pg.als_portal(f"SELECT * FROM {fn}(:s)", s=pruefwerte.sitzung("keine-sitzung"))]
        assert z["ergebnis"] == "ungueltig", fn
    (r,), (t,) = _rechnungen(w), _termine(w)
    assert (r["ergebnis"], r["stand"], t["ergebnis"], t["stand"]) == ("leer", None, "leer", None)  # noch nie gerechnet: ohne Stand
    _stand(w, am="2026-11-27 10:30")
    assert _rechnungen(w)[0]["stand"] == _termine(w)[0]["stand"] == datetime(2026, 11, 27, 10, 30)
    zeilen = w.pg.erp("SELECT aktion, ergebnis FROM portal_zugriffe WHERE aktion IN ('rechnungen', 'termine') ORDER BY id")
    assert [tuple(z) for z in zeilen] == [("rechnungen", "ok"), ("termine", "ok"), ("rechnungen", "ok"), ("termine", "ok")]
    sitzung_id = w.pg.erp("SELECT id FROM portal_sitzungen WHERE wert_sha256 = :s", s=pruefwerte.sitzung(w.sitz))[0][0]
    _bremse_voll(w, f"liste:s:{sitzung_id}", 120, 3600)  # dieselbe Bremse wie die Unterlagen
    for fn in (_rechnungen, _termine):
        z = fn(w)[0]
        assert z["ergebnis"] == "bremse" and z["minuten"] >= 1, z
    assert w.pg.erp("SELECT count(*) FROM portal_zugriffe WHERE aktion IN ('rechnungen', 'termine') AND ergebnis = 'bremse'")[0][0] == 2


def test_pg_rolle_des_portals_liest_die_tabellen_nicht(w):
    for sql in ("SELECT * FROM portal_rechnungen", "SELECT * FROM portal_termine", "SELECT * FROM portal_schaufenster", "SELECT * FROM reminder_levels"):
        with pytest.raises(ProgrammingError) as fehler:
            w.pg.als_portal(sql)
        assert fehler.value.orig.sqlstate == "42501", sql
    for name, argumente in schaufenster.FUER_DAS_PORTAL.items():
        signatur = f"{name}({', '.join(a.split()[-1] for a in argumente.split(', '))})"
        assert w.pg.erp("SELECT has_function_privilege(:r, :f, 'EXECUTE')", r=TESTROLLE, f=signatur)[0][0], signatur
        assert not w.pg.erp("SELECT has_function_privilege('public', :f, 'EXECUTE')", f=signatur)[0][0], signatur
    assert text  # (Import für Typprüfer)


def _uebersicht(w, sitz=None):
    (z,) = [dict(r._mapping) for r in w.pg.als_portal("SELECT * FROM portal_uebersicht(:s)", s=pruefwerte.sitzung(sitz or w.sitz))]
    return z


def test_pg_uebersicht_in_einer_zeile(w):
    heute = berlin_today()
    leer = _uebersicht(w)
    assert (leer["ergebnis"], leer["offen_anzahl"], leer["offen_summe"], leer["faellig_nummer"], leer["einsatz_von"], leer["unterlagen"], leer["fotos"],
            leer["foto_am"]) == ("ok", 0, D("0"), None, None, 0, 0, None)
    a = _auftrag(w, _projekt(w, objekt=_objekt(w)), nr="A-2026-0118")
    spaet, frueh, bezahlt, einbehalt = (_rechnung(w, a) for _ in range(4))
    for r in (spaet, frueh, bezahlt, einbehalt):
        _freigabe(w.db, w.kunde, "invoices", r.id, art="rechnung")
    _freigabe(w.db, w.kunde, "property_documents", _dokument(w, a), art="foto")
    _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id, art="dokument", titel="Datenblatt", datum=date(2026, 10, 28))
    _freigabe(w.db, w.kunde, "customer_documents", _kundendokument(w).id, art="dokument", titel="Abnahmeprotokoll", datum=date(2026, 11, 18))
    w.db.commit()
    _zahlstand(w, spaet, zustand="offen", offen=D("2380.00"), faellig=date(2026, 12, 20), art_text="Abschlagsrechnung")
    _zahlstand(w, frueh, zustand="teilweise_bezahlt", offen=D("1000.00"), faellig=date(2026, 12, 4), art_text="Schlussrechnung")
    _zahlstand(w, bezahlt, zustand="bezahlt", offen=D("0.00"))
    _zahlstand(w, einbehalt, zustand="bezahlt", offen=D("0.00"), faellig=date(2026, 11, 1))
    _termin(w, a, heute - timedelta(days=5), heute - timedelta(days=1))       # vorbei
    _termin(w, a, heute + timedelta(days=10), heute + timedelta(days=12))
    _termin(w, a, heute, heute + timedelta(days=2))                           # läuft heute: der nächste
    _stand(w)
    z = _uebersicht(w)
    assert (z["offen_anzahl"], z["offen_summe"], z["faellig_titel"], z["faellig_nummer"], z["faellig_am"]) == (
        2, D("3380.00"), "Schlussrechnung", frueh.invoice_number, date(2026, 12, 4))
    assert (z["einsatz_von"], z["einsatz_bis"], z["einsatz_auftrag"], z["einsatz_objekt"]) == (
        heute, heute + timedelta(days=2), "A-2026-0118", "Hafenweg 3, 12345 Musterstadt")
    assert (z["unterlagen"], z["unterlage_titel"], z["unterlage_datum"], z["fotos"], z["foto_am"]) == (2, "Abnahmeprotokoll", date(2026, 11, 18), 1, heute)
    assert z["stand"] == datetime(2026, 11, 27, 9, 0)
    assert _uebersicht(w, w.sitz2)["offen_anzahl"] == 0
    assert [tuple(r) for r in w.pg.erp("SELECT aktion, ergebnis FROM portal_zugriffe WHERE aktion = 'uebersicht' ORDER BY id")] == [("uebersicht", "ok")] * 3


def _dokument(w, auftrag):
    from app.models import Order, PropertyDocument
    o = w.db.get(Order, auftrag.id)
    d = PropertyDocument(property_id=o.project.property_id, category_id=w.kategorie, original_filename="foto.jpg", stored_filename=uuid.uuid4().hex)
    w.db.add(d); w.db.flush()
    return d.id
