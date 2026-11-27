"""Version 1.11.41 (Stufe P2d, Teil 1): das Schaufenster des Kundenportals -- app/portal_schaufenster.py, Bauplan P2, B3; Entscheidungen P2-7, P2-8, P2-11.

    Zahlstand       Wächter B3: für eine Welt mit Abschlag, Teilzahlung, Skonto, Einbehalt, Storno, Schlussrechnung mit Abzügen und Erstattung ist jede Zeile
                    gleich dem, was das ERP zeigt (dunning_state() bzw. invoice_to_dict()); P2-7: ein Einbehalt oder ein genutztes Skonto ist nie offen,
                    nie überfällig
    Sichtbar        nur Rechnungen mit Freigabe für den Kunden, nicht zurückgenommen, deren Kette heute gilt (B7); kein Entwurf
    Termine         P2-8: feste Baustellentage je laufendem Auftrag, Tage je Person, leere Tage trennen; vorläufig, Kranvermietung, ohne Besetzung,
                    storniert, abgeschlossen, Projekt im Archiv nie; die Tabelle hat keine Spalte für Namen
    Lauf            alle(): nur Kunden mit Portal an und nicht im Archiv, das Schaufenster der übrigen leer, Modul aus -> alles leer; abgleichen() ersetzt und
                    setzt den Stand; ein Fehler hält den Postboten nicht an
    Weckruf         die Liste der Tabellen ist genau die erwartete; jede Tabelle, die das Schaufenster liest, steht darin oder mit Grund in OHNE_WECKRUF; die
                    Migration trägt die Anweisungen wörtlich
    PostgreSQL      jede Tabelle der Liste weckt je Anweisung einmal, eine andere nicht; der Postbote rechnet auf den Weckruf des Schaufensters und der
                    Freigaben neu
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session

from app import portal_postbote as postbote
from app import portal_schaufenster as sf
from app.berlin_time import berlin_today
from app.final_dunning import dunning_state
from app.grunddaten import anlegen
from app.invoices import (
    create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft, invoice_to_dict, update_invoice_item,
)
from app.models import (
    Base, Customer, Employee, EnabledModule, Invoice, Order, OrderItem, PlanningSlot, PlanningSlotEmployee, PortalFreigabe, PortalRechnung,
    PortalSchaufenster, PortalTermin, Project, WorkPreparation, portal_in,
)
from app.payments import Line, book_payment
from app.portal import weckruf, werte
from app.project_pipeline_columns import default_pipeline_column_id
from tests.leistungszeitraum import festschreiben
from tests.quellangebot import quell_angebot
from tests.test_v133_invoices import db_session

ROOT = Path(__file__).resolve().parents[1]
D = Decimal
HEUTE = berlin_today()
_N = itertools.count(1)


class Welt:
    def __init__(self):
        self.db = db_session()
        anlegen(self.db)
        self.db.add(EnabledModule(module_key="kundenportal", enabled=True))
        self.db.commit()
        self.kunde = self.neuer_kunde("Muster")

    def neuer_kunde(self, name: str, *, portal=True) -> Customer:
        k = Customer(name=f"Herr {name}", last_name=name, portal_aktiv=portal)
        self.db.add(k)
        self.db.commit()
        return k

    def auftrag(self, kunde: Customer | None = None, *, menge="100", preis="50") -> Order:
        kunde = kunde or self.kunde
        n = next(_N)
        p = Project(project_number=f"P-SF-{n:04d}", name="Interner Titel", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(self.db))
        self.db.add(p)
        self.db.flush()
        o = Order(order_number=f"A-SF-{n:04d}", project_id=p.id, source_quote_id=quell_angebot(self.db, p.id, f"A-SF-{n:04d}"), quote_number_snapshot=f"Q-{n}",
                  title="Dach", vat_rate=D("19.00"), customer_name=kunde.name, customer_id=kunde.id)
        self.db.add(o)
        self.db.flush()
        self.db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=D(menge), unit="m²", unit_price=D(preis)))
        self.db.commit()
        return o

    def pauschal(self, o: Order, netto="2000", faellig: date | None = None) -> Invoice:
        """2.000 € netto = 2.380,00 € brutto."""
        return festschreiben(self.db, create_abschlag_pauschal(self.db, self.db.get(Order, o.id), lump_sum_net=D(netto), due_date=faellig))

    def leistungsstand(self, o: Order, ist: str, faellig: date | None = None) -> Invoice:
        i = create_abschlag_leistungsstand(self.db, self.db.get(Order, o.id), due_date=faellig)
        update_invoice_item(self.db, i, i.items[0], ist_quantity=D(ist))
        self.db.refresh(i)
        return festschreiben(self.db, i)

    def schluss(self, o: Order, ist: str) -> Invoice:
        i = create_schlussrechnung(self.db, self.db.get(Order, o.id))
        update_invoice_item(self.db, i, i.items[0], ist_quantity=D(ist))
        self.db.refresh(i)
        return festschreiben(self.db, i)

    def storno(self, i: Invoice) -> Invoice:
        return festschreiben(self.db, create_storno_draft(self.db, self.db.get(Invoice, i.id)))

    def zahlen(self, i: Invoice, betrag: str, *, skonto="0", einbehalt="0"):
        book_payment(self.db, customer_id=i.customer_id, received_on=HEUTE, amount=D(betrag), note=None,
                     lines=[Line(i.id, zahlung=D(betrag), skonto=D(skonto), einbehalt=D(einbehalt))], user_name="Test")

    def freigeben(self, i: Invoice, kunde: Customer | None = None, *, zurueck=False) -> PortalFreigabe:
        f = PortalFreigabe(customer_id=(kunde or self.kunde).id, art="rechnung", quelle="invoices", quelle_id=i.id, titel="Rechnung", datum=i.invoice_date,
                           freigegeben_am=datetime.utcnow(), freigegeben_von_name="Büro", zurueckgenommen_am=datetime.utcnow() if zurueck else None)
        self.db.add(f)
        self.db.commit()
        return f

    def zeilen(self, kunde: Customer | None = None) -> dict[int, dict]:
        return {z["invoice_id"]: z for z in sf.rechnungen(self.db, kunde or self.kunde)}


@pytest.fixture
def w():
    welt = Welt()
    yield welt
    welt.db.close()


# --- Zahlstand: Wächter B3 und P2-7 ---------------------------------------------------------------------------------------------------------------

def _welt_mit_allem(w: Welt) -> dict[str, Invoice]:
    o = w.auftrag()
    r = {
        "offen": w.pauschal(o, faellig=HEUTE - timedelta(days=10)),
        "teil": w.pauschal(o, faellig=HEUTE + timedelta(days=14)),
        "bezahlt": w.pauschal(o),
        "skonto": w.pauschal(o, faellig=HEUTE - timedelta(days=10)),
        "einbehalt": w.pauschal(o, faellig=HEUTE - timedelta(days=10)),
        "teil_einbehalt": w.pauschal(o, faellig=HEUTE - timedelta(days=10)),
        "storniert": w.pauschal(o),
    }
    w.zahlen(r["teil"], "1000")
    w.zahlen(r["bezahlt"], "2380")
    w.zahlen(r["skonto"], "2332.40", skonto="47.60")
    w.zahlen(r["einbehalt"], "2261", einbehalt="119")
    w.zahlen(r["teil_einbehalt"], "1000", einbehalt="119")
    r["storno"] = w.storno(r["storniert"])
    # Schlussrechnung mit Abzug: Abschlag 40 m² (2.380,00 €) unbezahlt, Schlussrechnung 100 m² (5.950,00 € − 2.380,00 €) -- Zahlbetrag 5.950,00 €
    o2 = w.auftrag()
    r["abgezogen"] = w.leistungsstand(o2, "40")
    r["endrechnung"] = w.schluss(o2, "100")
    # Erstattung: Abschlag 100 m² (5.950,00 €) bezahlt, Schlussrechnung 80 m² -- Guthaben 1.190,00 €
    o3 = w.auftrag()
    r["voll_bezahlt"] = w.leistungsstand(o3, "100")
    w.zahlen(r["voll_bezahlt"], "5950")
    r["guthaben"] = w.schluss(o3, "80")
    for i in r.values():
        w.freigeben(i)
    return {k: w.db.get(Invoice, i.id) for k, i in r.items()}


ERWARTET = {  # Zustand, offener Betrag (beim Guthaben das Guthaben), überfällig, Bezug
    "offen": ("offen", "2380.00", True, None),
    "teil": ("teilweise_bezahlt", "1380.00", False, None),
    "bezahlt": ("bezahlt", "0.00", False, None),
    "skonto": ("bezahlt", "0.00", False, None),             # P2-7: ein genutztes Skonto ist nie offen
    "einbehalt": ("bezahlt", "0.00", False, None),          # P2-7: ein offener Einbehalt ist nie offen, nie überfällig
    "teil_einbehalt": ("teilweise_bezahlt", "1261.00", True, None),  # offen nur, was das ERP mahnt: 1.380,00 € − Einbehalt 119,00 €
    "storniert": ("storniert", "0.00", False, None),
    "storno": ("storno", "0.00", False, "storniert"),
    "abgezogen": ("enthalten", "0.00", False, "endrechnung"),
    "endrechnung": ("offen", "5950.00", False, None),
    "voll_bezahlt": ("bezahlt", "0.00", False, None),
    "guthaben": ("guthaben", "1190.00", False, None),
}


def test_zustaende_wie_erwartet_und_wie_das_erp(w):
    r = _welt_mit_allem(w)
    zeilen = w.zeilen()
    assert set(zeilen) == {i.id for i in r.values()}
    for name, (zustand, offen, ueber, bezug) in ERWARTET.items():
        i, z = r[name], zeilen[r[name].id]
        assert (z["zustand"], z["offen"], z["ueberfaellig"], z["bezug_nummer"]) == (
            zustand, D(offen), ueber, r[bezug].invoice_number if bezug else None), name
        assert z["zustand"] in werte.RECHNUNG_ZUSTAENDE
        # ... und gleich dem, was das ERP zeigt -- über einen anderen Weg als invoice_overview_rows()
        erp = invoice_to_dict(i)
        assert z["ueberfaellig"] == erp["is_overdue"], name
        assert (z["nummer"], z["datum"], z["faellig"], z["order_id"]) == (i.invoice_number, i.invoice_date, i.due_date, i.order_id), name
        st = dunning_state(w.db, i) if i.status != "storniert" and i.invoice_type != "storno" else None
        if zustand in ("offen", "teilweise_bezahlt"):
            assert st is not None and z["offen"] == st.dunnable > 0, name
        elif zustand == "guthaben":
            assert st is not None and z["offen"] == st.credit > 0, name
        else:
            assert z["offen"] == 0 and (st is None or st.dunnable == 0), name


def test_einbehalt_und_skonto_nie_offen_nie_ueberfaellig(w):
    """P2-7 einzeln: dieselbe überfällige Rechnung -- offen und überfällig, mit Skonto bezahlt bzw. mit Einbehalt bis auf ihn bezahlt nicht mehr."""
    o = w.auftrag()
    a, b = w.pauschal(o, faellig=HEUTE - timedelta(days=3)), w.pauschal(o, faellig=HEUTE - timedelta(days=3))
    w.freigeben(a)
    w.freigeben(b)
    assert [(z["zustand"], z["ueberfaellig"]) for z in w.zeilen().values()] == [("offen", True), ("offen", True)]
    w.zahlen(a, "2332.40", skonto="47.60")
    w.zahlen(b, "2261", einbehalt="119")
    assert [(z["zustand"], z["offen"], z["ueberfaellig"]) for z in w.zeilen().values()] == [("bezahlt", D("0.00"), False)] * 2


# --- Nur sichtbare Rechnungen (B7) ------------------------------------------------------------------------------------------------------------------

def test_nur_rechnungen_mit_gueltiger_freigabe_fuer_den_kunden(w):
    o = w.auftrag()
    ohne, zurueck, fremd, sichtbar = (w.pauschal(o) for _ in range(4))
    entwurf = create_abschlag_pauschal(w.db, w.db.get(Order, o.id), lump_sum_net=D("100"))
    w.freigeben(zurueck, zurueck=True)
    w.freigeben(fremd, w.neuer_kunde("Beispiel"))
    w.freigeben(sichtbar)
    w.freigeben(entwurf)
    assert set(w.zeilen()) == {sichtbar.id}
    p = w.db.get(Project, o.project_id)
    p.archived = True  # P2-11: Projekt im Archiv -- im Portal nichts davon
    w.db.commit()
    assert w.zeilen() == {}
    p.archived, p.is_template = False, True
    w.db.commit()
    assert w.zeilen() == {}
    p.is_template = False
    w.db.commit()
    assert set(w.zeilen()) == {sichtbar.id}


def test_kein_stilles_umhaengen_an_einen_anderen_kunden(w):
    """Die Freigabe gilt dem Kunden der Rechnung; trägt sie heute einen anderen (Kundenwechsel), fehlt sie bei beiden."""
    o = w.auftrag()
    i = w.pauschal(o)
    w.freigeben(i)
    andere = w.neuer_kunde("Beispiel")
    w.db.execute(update(Invoice).where(Invoice.id == i.id).values(customer_id=andere.id))
    w.db.commit()
    assert w.zeilen() == {} and w.zeilen(andere) == {}


# --- Termine (P2-8) ---------------------------------------------------------------------------------------------------------------------------------

def _einsatz(w: Welt, o: Order, von: date, bis: date, tage: list[date] | None = None, *, status="fest", art="baustelle", personen=1) -> PlanningSlot:
    av = w.db.scalar(select(WorkPreparation).where(WorkPreparation.order_id == o.id))
    if av is None:
        av = WorkPreparation(order_id=o.id)
        w.db.add(av)
        w.db.flush()
    s = PlanningSlot(preparation_id=av.id, start_date=von, end_date=bis, status=status, art=art)
    w.db.add(s)
    w.db.flush()
    for _ in range(personen):
        m = Employee(first_name="Erfunden", last_name=f"Monteur{next(_N)}")
        w.db.add(m)
        w.db.flush()
        w.db.add(PlanningSlotEmployee(slot_id=s.id, employee_id=m.id, tage=json.dumps([t.isoformat() for t in tage]) if tage is not None else None))
    w.db.commit()
    return s


T = date(2026, 12, 7)  # ein Montag


def test_termine_feste_baustellentage_je_auftrag_mit_unterbrechung(w):
    o = w.auftrag()
    _einsatz(w, o, T, T + timedelta(days=4))                                                       # Mo–Fr, alle Tage
    _einsatz(w, o, T + timedelta(days=7), T + timedelta(days=9), [T + timedelta(days=7), T + timedelta(days=9)])  # Mitte leer
    _einsatz(w, o, T + timedelta(days=14), T + timedelta(days=15), status="vorlaeufig")            # nie
    _einsatz(w, o, T + timedelta(days=21), T + timedelta(days=21), art="kranvermietung")           # nie
    _einsatz(w, o, T + timedelta(days=28), T + timedelta(days=28), personen=0)                     # niemand eingeplant: nie
    assert sf.termine(w.db, w.kunde) == [
        {"order_id": o.id, "von": T, "bis": T + timedelta(days=4)},
        {"order_id": o.id, "von": T + timedelta(days=7), "bis": T + timedelta(days=7)},
        {"order_id": o.id, "von": T + timedelta(days=9), "bis": T + timedelta(days=9)},
    ]


@pytest.mark.parametrize("fall", ["storniert", "abgeschlossen", "archiv", "muster", "anderer_kunde"])
def test_termine_nie(w, fall):
    o = w.auftrag(w.neuer_kunde("Beispiel") if fall == "anderer_kunde" else None)
    _einsatz(w, o, T, T)
    if fall in ("storniert", "abgeschlossen"):
        w.db.execute(update(Order).where(Order.id == o.id).values(status=fall))
    elif fall in ("archiv", "muster"):
        w.db.execute(update(Project).where(Project.id == o.project_id).values(**({"archived": True} if fall == "archiv" else {"is_template": True})))
    w.db.commit()
    assert sf.termine(w.db, w.kunde) == []


def test_pausiert_bleibt_und_die_tabelle_hat_keine_namen(w):
    o = w.auftrag()
    _einsatz(w, o, T, T)
    w.db.execute(update(Order).where(Order.id == o.id).values(status="pausiert"))
    w.db.commit()
    assert sf.termine(w.db, w.kunde) == [{"order_id": o.id, "von": T, "bis": T}]
    assert set(PortalTermin.__table__.c.keys()) == {"id", "customer_id", "order_id", "von", "bis", "stand_am"}


# --- Lauf --------------------------------------------------------------------------------------------------------------------------------------------

def test_abgleichen_ersetzt_die_zeilen_und_setzt_den_stand(w):
    o = w.auftrag()
    i = w.pauschal(o)
    w.freigeben(i)
    _einsatz(w, o, T, T)
    sf.abgleichen(w.db, w.kunde, datetime(2026, 11, 27, 10, 0))
    assert [(z.zustand, z.offen) for z in w.db.scalars(select(PortalRechnung))] == [("offen", D("2380.00"))]
    w.zahlen(i, "2380")
    sf.abgleichen(w.db, w.kunde, datetime(2026, 11, 27, 10, 5))
    assert [(z.zustand, z.offen, z.stand_am) for z in w.db.scalars(select(PortalRechnung))] == [("bezahlt", D("0.00"), datetime(2026, 11, 27, 10, 5))]
    assert w.db.scalar(select(PortalTermin.stand_am)) == datetime(2026, 11, 27, 10, 5)
    assert w.db.get(PortalSchaufenster, w.kunde.id).stand_am == datetime(2026, 11, 27, 10, 5)


def test_stand_auch_ohne_eine_zeile(w):
    sf.abgleichen(w.db, w.kunde)
    assert w.db.get(PortalSchaufenster, w.kunde.id) is not None and w.db.scalars(select(PortalRechnung)).all() == []


def test_alle_nur_portal_an_nicht_archiv_und_modul_aus_leert(w):
    aus, archiv = w.neuer_kunde("Aus", portal=False), w.neuer_kunde("Archiv")
    for k in (w.kunde, aus, archiv):
        i = w.pauschal(w.auftrag(k))
        w.freigeben(i, k)
        sf.abgleichen(w.db, k)  # ein Stand von früher: jeder hatte schon Zeilen
    w.db.execute(update(Customer).where(Customer.id == archiv.id).values(archiviert_am=datetime(2026, 11, 26)))
    w.db.commit()
    lauf = sf.alle(w.db)
    assert lauf.kunden == 1 and lauf.geleert == 4  # je Rechnung und Stand von „Aus“ und „Archiv“
    assert {z.customer_id for z in w.db.scalars(select(PortalRechnung))} == {w.kunde.id}
    assert {z.customer_id for z in w.db.scalars(select(PortalSchaufenster))} == {w.kunde.id}
    w.db.execute(update(EnabledModule).where(EnabledModule.module_key == "kundenportal").values(enabled=False))
    w.db.commit()
    assert sf.alle(w.db).kunden == 0
    assert w.db.scalars(select(PortalRechnung)).all() == [] and w.db.scalars(select(PortalSchaufenster)).all() == []


def test_ein_fehler_im_schaufenster_haelt_den_postboten_nicht_an(w, monkeypatch, caplog):
    def kaputt(_db):
        raise RuntimeError("geheimer Inhalt")

    monkeypatch.setattr(sf, "alle", kaputt)
    with caplog.at_level(logging.ERROR, logger="app.portal_postbote"):
        postbote.schaufenster(w.db)
    assert "Schaufenster nicht gerechnet (RuntimeError)" in caplog.text and "geheimer Inhalt" not in caplog.text


# --- Weckruf: Liste, Lesen, Migration --------------------------------------------------------------------------------------------------------------

ERWARTETE_TABELLEN = {  # jede mit dem, was eine Änderung dort am Schaufenster ändert
    "invoices": "Festschreiben, Storno, Kunde der Rechnung",
    "invoice_items": "Beträge (Entwurf; Endrechnung)",
    "invoice_deductions": "Abzüge der Endrechnung",
    "payments": "Zahlungseingang und -ausgang",
    "payment_allocations": "Zuordnung, Skonto, Einbehalt, Erstattung, Gegenbuchung",
    "orders": "Auftragsstatus, Kunde des Auftrags",
    "projects": "Archiv und Mustervorgang (P2-11)",
    "customers": "Portal an/aus, Archiv des Kunden",
    "planning_slots": "Einsatz anlegen, ändern, verschieben, Status",
    "planning_slot_employees": "Besetzung je Tag",
}
OHNE_WECKRUF = {  # gelesen, aber ohne eigenen Auslöser -- mit Grund
    "portal_freigaben": "eigener Weckruf portal_post (app/portal/weckruf.py, seit 1.11.33); der Postbote rechnet das Schaufenster auch darauf",
    "work_preparations": "verbindet Einsatz und Auftrag; der Auftrag einer Arbeitsvorbereitung ändert sich nie, ein neuer Einsatz weckt über planning_slots",
    "enabled_modules": "Modul an/aus: der volle Lauf alle 15 Minuten (das Portal selbst prüft das Modul)",
}


def test_die_liste_der_tabellen_ist_die_erwartete():
    assert set(weckruf.TABELLEN_SCHAUFENSTER) == set(ERWARTETE_TABELLEN), set(weckruf.TABELLEN_SCHAUFENSTER) ^ set(ERWARTETE_TABELLEN)
    assert len(weckruf.TABELLEN_SCHAUFENSTER) == len(set(weckruf.TABELLEN_SCHAUFENSTER))
    assert set(weckruf.TABELLEN_SCHAUFENSTER) <= set(Base.metadata.tables)


def test_jede_gelesene_tabelle_weckt_oder_hat_einen_grund(w):
    """Was das Schaufenster liest, ändert es -- jede Tabelle davon steht in der Liste des Weckrufs oder mit Grund in OHNE_WECKRUF; umgekehrt liest es jede
    Tabelle der Liste (kein Auslöser ohne Grund) und jeden Eintrag von OHNE_WECKRUF (keine Ausnahme ohne Anlass)."""
    _welt_mit_allem(w)
    o = w.auftrag()
    _einsatz(w, o, T, T + timedelta(days=2), [T, T + timedelta(days=2)])
    gelesen: set[str] = set()

    def mitlesen(_conn, _cursor, statement, *_rest):
        gelesen.update(re.findall(r'\b(?:FROM|JOIN)\s+"?([a-z_]+)"?', statement))

    bind = w.db.get_bind()
    event.listen(bind, "before_cursor_execute", mitlesen)
    try:
        w.db.expire_all()
        sf.alle(w.db)
    finally:
        event.remove(bind, "before_cursor_execute", mitlesen)
    gelesen -= {"portal_rechnungen", "portal_termine", "portal_schaufenster"}  # schreibt es selbst
    assert gelesen, "nichts mitgelesen"
    fehlt = gelesen - set(weckruf.TABELLEN_SCHAUFENSTER) - set(OHNE_WECKRUF)
    assert not fehlt, f"gelesen, aber ohne Weckruf und ohne Grund: {sorted(fehlt)}"
    assert not set(weckruf.TABELLEN_SCHAUFENSTER) - gelesen, f"Weckruf ohne Anlass: {sorted(set(weckruf.TABELLEN_SCHAUFENSTER) - gelesen)}"
    assert not set(OHNE_WECKRUF) - gelesen, f"Ausnahme ohne Anlass: {sorted(set(OHNE_WECKRUF) - gelesen)}"


def test_migration_traegt_die_anweisungen_woertlich():
    pfad = next((ROOT / "alembic" / "versions").glob("c4e8a2f6b1d3_*.py"))
    spec = importlib.util.spec_from_file_location("migration_schaufenster", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.ANWEISUNGEN == weckruf.ANWEISUNGEN_SCHAUFENSTER and modul.TABELLEN == weckruf.TABELLEN_SCHAUFENSTER
    assert modul.down_revision == "a7c3e9f1d2b4"
    assert repr(portal_in("zustand", werte.RECHNUNG_ZUSTAENDE)) in pfad.read_text(encoding="utf-8")
    assert len(weckruf.ANWEISUNGEN_SCHAUFENSTER) == len(weckruf.TABELLEN_SCHAUFENSTER) + 2
    assert "SET search_path = pg_catalog, @SCHEMA@, pg_temp" in weckruf.ANWEISUNGEN_SCHAUFENSTER[0]
    assert all("FOR EACH STATEMENT" in a for a in weckruf.ANWEISUNGEN_SCHAUFENSTER[1:-1])
    assert weckruf.ANWEISUNGEN_SCHAUFENSTER[-1] == "REVOKE ALL ON FUNCTION portal_schaufenster_geweckt() FROM PUBLIC"


def test_kein_inhalt_im_weckruf():
    """Der Weckruf trägt nichts -- keine ID, keinen Betrag (wie der Weckruf der Freigaben)."""
    assert f"pg_notify('{weckruf.KANAL_SCHAUFENSTER}', '')" in weckruf.ANWEISUNGEN_SCHAUFENSTER[0]
    assert "NEW." not in weckruf.ANWEISUNGEN_SCHAUFENSTER[0] and "OLD." not in weckruf.ANWEISUNGEN_SCHAUFENSTER[0]


# --- PostgreSQL --------------------------------------------------------------------------------------------------------------------------------------

from tests.test_v822_portal_unterlagen_matrix import Bau, _freigabe, _kunde, welt  # noqa: E402,F401  (welt ist eine Fixture)
from tests.test_v823_portal_kopien import _bis, _laeuft  # noqa: E402


def _weckrufe(welt, anweisung: str) -> int:
    """Wie oft die eigene Verbindung (pg_backend_pid) über eine Transaktion mit genau dieser Anweisung weckt."""
    with welt.engine.connect() as hoerer:
        hoerer.exec_driver_sql(f"LISTEN {weckruf.KANAL_SCHAUFENSTER}")
        hoerer.commit()
        roh = hoerer.connection.driver_connection
        with welt.engine.connect() as sender:
            pid = sender.execute(text("SELECT pg_backend_pid()")).scalar()
            sender.exec_driver_sql(anweisung)
            sender.commit()
        return sum(1 for n in roh.notifies(timeout=1.0) if n.pid == pid and n.channel == weckruf.KANAL_SCHAUFENSTER)


@pytest.mark.parametrize("tabelle", weckruf.TABELLEN_SCHAUFENSTER)
def test_pg_jede_tabelle_weckt_je_anweisung_einmal(welt, tabelle):
    assert _weckrufe(welt, f"UPDATE {tabelle} SET id = id WHERE false") == 1
    assert _weckrufe(welt, f"DELETE FROM {tabelle} WHERE false") == 1


def test_pg_eine_andere_tabelle_weckt_nicht(welt):
    assert _weckrufe(welt, "UPDATE reminders SET id = id WHERE false") == 0


def test_pg_der_postbote_rechnet_auf_beide_weckrufe_neu(welt):
    wk = welt
    kunde, _sitz = _kunde(wk, "Schaufenster")
    q = Bau(wk).bauen("invoices", kunde, kunde)
    fid = _freigabe(wk, kunde, q)
    wk.erp("UPDATE customers SET portal_aktiv = true WHERE id = :k", k=kunde)

    def zeilen():
        return wk.erp("SELECT count(*) FROM portal_rechnungen WHERE invoice_id = :i", i=q.id)[0][0]

    halt, faden, fehler = _laeuft(wk, None)  # ohne Ordner: keine Kopien, nur Codes, Regeln und Schaufenster
    try:
        _bis(lambda: zeilen() == 1, "beim Start gerechnet")
        wk.erp("UPDATE customers SET portal_aktiv = false WHERE id = :k", k=kunde)    # Weckruf des Schaufensters
        _bis(lambda: zeilen() == 0, "Portal aus: Zeile weg")
        wk.erp("UPDATE customers SET portal_aktiv = true WHERE id = :k", k=kunde)
        _bis(lambda: zeilen() == 1, "Portal an: Zeile wieder da")
        wk.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :f", f=fid)  # Weckruf der Freigaben
        _bis(lambda: zeilen() == 0, "zurückgenommen: Zeile weg")
    finally:
        halt.set()
        wk.erp(f"SELECT pg_notify('{postbote.KANAL}', '')")
        faden.join(30)
    assert fehler == [] and not faden.is_alive()
    assert wk.erp("SELECT count(*) FROM portal_schaufenster WHERE customer_id = :k", k=kunde)[0][0] == 1
