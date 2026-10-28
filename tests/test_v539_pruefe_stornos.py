"""Version 1.9.119 (Stufe 5, R1 Nachrunde, Punkt 1): scripts/pruefe_stornos.py -- hebt jeder festgeschriebene Storno sein Original genau
auf?

    genau        Abschlag nach Leistungsstand, pauschaler Abschlag (auch ohne Position, vor 1.3.24), Rechnung vor 1.8.11 (ungerundet, krummer
                 Preis), Schlussrechnung mit Abzug -> kein Treffer, „Alle n Stornos heben ihr Original genau auf.“, Rückgabe 0
    Altbestand   Storno mit geänderter Menge (Zustand vor 1.9.114, direkt in der Datenbank) -> Treffer mit Netto/USt/Brutto und der Position
                 Soll / Ist, Rückgabe 1; ergänzte und entfernte Position; ein Entwurf zählt nicht
    nur lesen    die eigene Sitzung schreibt nicht (SQLite und PostgreSQL): ein UPDATE scheitert, das Änderungsprotokoll bleibt gleich;
                 ohne DATABASE_URL Rückgabe 2
"""

import importlib.util
import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.invoices import (create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft,
                          update_invoice_item)
from app.models import AuditLog, Invoice, InvoiceItem
from tests.leistungszeitraum import festschreiben
from tests.pg_schutz import pg_url_pruefen
from tests.test_v133_invoices import db_session, make_order_with_item

ROOT = Path(__file__).resolve().parent.parent


def _skript():
    spec = importlib.util.spec_from_file_location("pruefe_stornos", ROOT / "scripts" / "pruefe_stornos.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _lauf(db):
    zeilen = []
    rc = _skript().main([], sitzung=db, ausgabe=zeilen.append)
    return rc, zeilen


def _abschlag_mit_storno(db, ist="40", preis="50", order=None):
    """Abschlag nach Leistungsstand (Ist von 100 m² zu preis), festgeschrieben. Der Preis steht im Auftrag (seit 1.8.85 nimmt der
    Entwurf ihn nur von dort)."""
    if order is None:
        order, _ = make_order_with_item(db, unit_price=Decimal(preis))
    invoice = create_abschlag_leistungsstand(db, order)
    update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal(ist))
    original = festschreiben(db, invoice)
    return order, original


def test_genauer_storno_kein_treffer():
    db = db_session()
    _, original = _abschlag_mit_storno(db)
    storno = festschreiben(db, create_storno_draft(db, original))
    anzahl, treffer = _skript().pruefen(db)
    assert (anzahl, treffer) == (1, [])
    rc, zeilen = _lauf(db)
    assert (rc, zeilen) == (0, ["Alle 1 Stornos heben ihr Original genau auf."])
    assert storno.status != "entwurf"


def test_storno_mit_geaenderter_menge_vor_1_9_114_ist_ein_treffer():
    """Der Beleg aus 1.9.114 (F8): Ist 7 am Storno-Entwurf -> −33 m², −1.650,00 € statt −40 m², −2.000,00 €. Seit 1.9.114 lässt die
    Anwendung das nicht mehr zu -- hier direkt in der Datenbank, wie es ein Storno von vor 1.9.114 sein kann."""
    db = db_session()
    _, original = _abschlag_mit_storno(db)
    storno = festschreiben(db, create_storno_draft(db, original))
    db.execute(update(InvoiceItem).where(InvoiceItem.invoice_id == storno.id)
               .values(ist_quantity=Decimal("7"), billed_quantity=Decimal("-33"), billed_total=Decimal("-1650")))
    db.commit()
    db.expire_all()
    anzahl, treffer = _skript().pruefen(db)
    assert anzahl == 1 and len(treffer) == 1
    t = treffer[0]
    assert t.storno == f"{storno.invoice_number} (ID {storno.id})" and t.original == f"{original.invoice_number} (ID {original.id})"
    assert t.abweichungen == [
        "Netto: Soll −2.000,00 €, Ist −1.650,00 €",
        "USt: Soll −380,00 €, Ist −313,50 €",
        "Brutto: Soll −2.380,00 €, Ist −1.963,50 €",
        "Position 1 Dacheindeckung: Menge Soll −40, Ist −33; Betrag Soll −2.000,00 €, Ist −1.650,00 €",
    ]
    rc, zeilen = _lauf(db)
    assert rc == 1
    assert zeilen[0] == "1 von 1 Stornos heben ihr Original nicht genau auf:"
    assert zeilen[1] == f"Storno {t.storno} zu {t.original}:"
    assert zeilen[2:] == [f"  {a}" for a in t.abweichungen]


def test_ergaenzte_und_entfernte_position():
    db = db_session()
    _, original = _abschlag_mit_storno(db)
    storno = festschreiben(db, create_storno_draft(db, original))
    position = storno.items[0]
    db.execute(insert(InvoiceItem.__table__).values(
        invoice_id=storno.id, sort_order=20, position_number="2", short_text="Zusatz", long_text="", unit="Stk",
        unit_price=Decimal("10"), soll_quantity=None, ist_quantity=Decimal("1"), billed_quantity=Decimal("1"), billed_total=Decimal("10")))
    db.execute(delete(InvoiceItem).where(InvoiceItem.id == position.id))
    db.commit()
    db.expire_all()
    [t] = _skript().pruefen(db)[1]
    assert "Position 1 Dacheindeckung: fehlt im Storno (Soll Menge −40, Betrag −2.000,00 €)" in t.abweichungen
    assert "Position 2 Zusatz: nur im Storno (Menge 1, Betrag 10,00 €)" in t.abweichungen
    assert t.abweichungen[0].startswith("Netto: Soll −2.000,00 €, Ist 10,00 €")


def test_ein_entwurf_zaehlt_nicht():
    db = db_session()
    _, original = _abschlag_mit_storno(db)
    entwurf = create_storno_draft(db, original)
    db.execute(update(InvoiceItem).where(InvoiceItem.invoice_id == entwurf.id).values(billed_total=Decimal("-1")))
    db.commit()
    assert _lauf(db) == (0, ["Kein festgeschriebener Storno -- nichts zu prüfen."])


def test_pauschaler_abschlag_auch_ohne_position():
    db = db_session()
    order, _ = make_order_with_item(db)
    mit_position = festschreiben(db, create_abschlag_pauschal(db, order, lump_sum_net=Decimal("1234.565")))
    festschreiben(db, create_storno_draft(db, mit_position))
    # ohne Position wie vor 1.3.24: der Storno bekommt seit 1.8.83 die Projektionsposition -- Soll ist genau sie
    ohne = festschreiben(db, create_abschlag_pauschal(db, db.get(type(order), order.id), lump_sum_net=Decimal("500")))
    db.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id == ohne.id))
    db.commit()
    db.expire_all()
    festschreiben(db, create_storno_draft(db, db.get(Invoice, ohne.id)))
    assert _skript().pruefen(db) == (2, [])


def test_rechnung_vor_1_8_11_ungerundet():
    db = db_session()
    _, original = _abschlag_mit_storno(db, ist="3", preis="10.0042")
    db.execute(update(Invoice).where(Invoice.id == original.id).values(rounding_rule=None))
    db.commit()
    db.expire_all()
    storno = festschreiben(db, create_storno_draft(db, db.get(Invoice, original.id)))
    assert storno.rounding_rule is None
    assert _skript().pruefen(db) == (1, [])
    # um 0,0042 € daneben bleibt sichtbar (ungerundete Beträge mit ihrer ganzen Genauigkeit)
    db.execute(update(InvoiceItem).where(InvoiceItem.invoice_id == storno.id).values(billed_total=Decimal("-30.0084")))
    db.commit()
    db.expire_all()
    [t] = _skript().pruefen(db)[1]
    assert t.abweichungen[0] == "Netto: Soll −30,0126 €, Ist −30,0084 €"


def test_schlussrechnung_mit_abzug():
    db = db_session()
    order, _ = _abschlag_mit_storno(db)
    schluss = festschreiben(db, create_schlussrechnung(db, order))
    assert schluss.deductions
    festschreiben(db, create_storno_draft(db, schluss))
    assert _skript().pruefen(db) == (1, [])


def test_ohne_database_url_rueckgabe_2():
    zeilen = []
    assert _skript().main([], umgebung={}, ausgabe=zeilen.append) == 2
    assert zeilen == ["DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a"]


def _echter_auftrag(db):
    """Auftrag über Angebot und Beauftragen -- make_order_with_item() verweist auf ein Angebot 1, das es nicht gibt (unter
    PostgreSQL ein Fremdschlüsselfehler)."""
    from datetime import date

    from app.models import Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    kunde = Customer(name="Bauherr Storno", last_name="Storno")
    db.add(kunde)
    db.flush()
    projekt = Project(project_number="P-ST-1", name="Dach", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    angebot = Quote(quote_number="A-ST-1", project_id=projekt.id, title="Sanierung", vat_rate=Decimal("19"))
    db.add(angebot)
    db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Dacheindeckung", quantity=Decimal("100"), unit="m²",
                     unit_price=Decimal("50")))
    db.commit()
    order = create_order_from_quote(db, angebot.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    return load_order(db, order.id)


def _bestand(engine):
    import app.models  # noqa: F401
    from app.database import Base

    Base.metadata.create_all(engine)  # die Grunddaten legt conftest dazu an
    db = sessionmaker(bind=engine)()
    try:
        _, original = _abschlag_mit_storno(db, order=_echter_auftrag(db))
        festschreiben(db, create_storno_draft(db, original))
        return db.scalar(select(func.count()).select_from(AuditLog))
    finally:
        db.close()


def _nur_lesend_pruefen(url, zaehlen):
    url = pg_url_pruefen(url)  # Regel 27: unter PostgreSQL nur mit eigenem Schema
    vorher = zaehlen()
    zeilen = []
    assert _skript().main([], umgebung={"DATABASE_URL": url}, ausgabe=zeilen.append) == 0
    assert zeilen == ["Alle 1 Stornos heben ihr Original genau auf."]
    sitzung = _skript().nur_lesende_sitzung(url)
    try:
        with pytest.raises(DBAPIError):
            sitzung.execute(text("UPDATE invoices SET status = 'storniert' WHERE invoice_type = 'storno'"))
            sitzung.commit()
        sitzung.rollback()
    finally:
        bind = sitzung.get_bind()
        sitzung.close()
        bind.dispose()
    assert zaehlen() == vorher


def test_die_eigene_sitzung_schreibt_nicht_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}"
    engine = create_engine(url)
    try:
        _bestand(engine)

        def zaehlen():
            with engine.connect() as conn:
                return (conn.scalar(select(func.count()).select_from(AuditLog)),
                        conn.execute(text("SELECT group_concat(status) FROM invoices")).scalar())
        _nur_lesend_pruefen(url, zaehlen)
    finally:
        engine.dispose()


PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def test_die_eigene_sitzung_schreibt_nicht_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_stornos_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path%3D{schema}&application_name={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _bestand(engine)

        def zaehlen():
            with engine.connect() as conn:
                return (conn.scalar(select(func.count()).select_from(AuditLog)),
                        conn.execute(text("SELECT string_agg(status, ',' ORDER BY id) FROM invoices")).scalar())
        _nur_lesend_pruefen(url, zaehlen)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
