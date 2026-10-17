"""Version 1.8.113 -- Vorgabe vom 16.10.2026, Punkte 4-6 (docs/archiv/stammdaten-und-sidebar.md, "Umsetzung 1.8.113").

4. Das Versandprotokoll steht seit 1.8.112 nicht mehr in der Seitenleiste -- dafür in der Projektmappe (Reiter "Versand") und in der
   Kundenakte (Karte "Versand"), gefiltert: GET /api/email-dispatches?project_id= bzw. ?customer_id= (app/dispatch_documents.py::
   document_filter()). Je Dokumentart über dieselbe Kette wie project_id_of(); beim Kunden zusätzlich Checklisten an seinen Objekten;
   Aufgaben-Mails nie. Der Link einer Mahnung führt in ihre Rechnung zur Mahnung (invoice_id am Eintrag, ?mahnung=).
5. Mobile Kopfzeile mit "Mein Konto".
6. Das Leistungsformular lädt für "Büro – Auftrag" wieder (die Kalkulationsvorgaben liest seit 1.4.8 nur Büro – Finanzen/Admin)."""

import json
import re
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.email_dispatch import list_dispatches
from app.models import Checklist, EmailDispatch, Order, OrderContract, Project, Property, Quote
from app.project_pipeline_columns import default_pipeline_column_id
from app.reminders import create_reminder
from app.routers.email_dispatches import router as dispatch_router
from tests.test_v153_mahnwesen import make_sent_overdue_invoice
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def _versand(db, art: str, dokument_id: int) -> None:
    db.add(EmailDispatch(dispatch_key=f"test-{uuid.uuid4()}", message_ref=str(uuid.uuid4()), status="gesendet", channel="smtp",
                         document_type=art, document_id=dokument_id, document_number=f"{art}-{dokument_id}",
                         to_recipients="kunde@example.com", subject=art, finished_at=datetime.utcnow()))


def _checkliste(db, *, order_id=None, property_id=None) -> Checklist:
    # Nur die Bezüge zählen (SQLite prüft die Fremdschlüssel auf Vorlage und Fassung hier nicht).
    c = Checklist(template_id=1, template_version_id=1, template_label_snapshot="Test", status="abgeschlossen",
                  context_type="auftrag" if order_id else "objekt", order_id=order_id, property_id=property_id)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    r1, r2 = make_sent_overdue_invoice(db, suffix="0001"), make_sent_overdue_invoice(db, suffix="0002")
    auftrag1, auftrag2 = r1.order, r2.order
    projekt1 = db.get(Project, auftrag1.project_id)
    kunde1, kunde2 = projekt1.customer_id, db.get(Project, auftrag2.project_id).customer_id
    # Zweites Projekt desselben Kunden mit Auftrag, Objekt des Kunden mit einer Checkliste ohne Auftrag.
    projekt1b = Project(project_number="P-TEST-0003", name="Zweites Projekt", customer_id=kunde1,
                        pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt1b); db.flush()
    auftrag1b = Order(order_number="AUF-TEST-0003", project_id=projekt1b.id, source_quote_id=3, quote_number_snapshot="A-TEST-0003",
                      title="Zweiter Auftrag", vat_rate=Decimal("19.00"), customer_name="Test Kunde", customer_number="K-0003")
    objekt = Property(customer_id=kunde1, name="Halle", street="Weg 1", postal_code="11111", city="Ort")
    db.add_all([auftrag1b, objekt]); db.flush()
    angebot1 = Quote(quote_number="A-TEST-0001", project_id=projekt1.id, title="Angebot", vat_rate=Decimal("19.00"))
    vertrag1 = OrderContract(order_id=auftrag1.id)
    db.add_all([angebot1, vertrag1]); db.flush()
    mahnung1 = create_reminder(db, r1)
    cl_auftrag1, cl_auftrag2 = _checkliste(db, order_id=auftrag1.id), _checkliste(db, order_id=auftrag2.id)
    cl_objekt = _checkliste(db, property_id=objekt.id)
    projekt1_dokumente = {("angebot", angebot1.id), ("auftrag", auftrag1.id), ("rechnung", r1.id), ("mahnung", mahnung1.id),
                          ("vertrag", vertrag1.id), ("checkliste", cl_auftrag1.id), ("behinderungsanzeige", cl_auftrag1.id),
                          ("bedenkenanzeige", cl_auftrag1.id), ("wiederaufnahme", cl_auftrag1.id)}
    andere = {("auftrag", auftrag2.id), ("rechnung", r2.id), ("checkliste", cl_auftrag2.id)}
    projekt1b_dokumente = {("auftrag", auftrag1b.id)}
    objekt_dokumente = {("checkliste", cl_objekt.id)}
    for art, nr in projekt1_dokumente | andere | projekt1b_dokumente | objekt_dokumente | {("aufgabe", 1)}:
        _versand(db, art, nr)
    db.commit()
    return {"db": db, "projekt1": projekt1.id, "projekt1b": projekt1b.id, "kunde1": kunde1, "kunde2": kunde2,
            "p1": projekt1_dokumente, "p1b": projekt1b_dokumente, "objekt": objekt_dokumente, "andere": andere,
            "mahnung1": mahnung1.id, "rechnung1": r1.id}


def _dokumente(antwort: dict) -> set[tuple[str, int]]:
    return {(d["document_type"], d["document_id"]) for d in antwort["items"]}


def test_versand_eines_projekts_nur_seine_dokumente(welt):
    db = welt["db"]
    assert _dokumente(list_dispatches(db, project_id=welt["projekt1"], include_task_mails=True)) == welt["p1"]
    assert _dokumente(list_dispatches(db, project_id=welt["projekt1b"], include_task_mails=True)) == welt["p1b"]


def test_versand_eines_kunden_seine_projekte_und_objekte(welt):
    db = welt["db"]
    kunde1 = _dokumente(list_dispatches(db, customer_id=welt["kunde1"], include_task_mails=True))
    assert kunde1 == welt["p1"] | welt["p1b"] | welt["objekt"]  # keine Aufgaben-Mail, nichts vom anderen Kunden
    assert _dokumente(list_dispatches(db, customer_id=welt["kunde2"])) == welt["andere"]


def test_mahnung_traegt_ihre_rechnung(welt):
    eintraege = list_dispatches(welt["db"], project_id=welt["projekt1"])["items"]
    mahnung = next(d for d in eintraege if d["document_type"] == "mahnung")
    assert (mahnung["document_id"], mahnung["invoice_id"]) == (welt["mahnung1"], welt["rechnung1"])


def test_api_filtert_und_lehnt_beides_zugleich_ab(welt, router_test_client):
    client = router_test_client(welt["db"], dispatch_router, role="buero_auftrag")
    antwort = client.get(f"/api/email-dispatches?project_id={welt['projekt1']}")
    assert antwort.status_code == 200 and _dokumente(antwort.json()) == welt["p1"]
    antwort = client.get(f"/api/email-dispatches?customer_id={welt['kunde2']}")
    assert antwort.status_code == 200 and _dokumente(antwort.json()) == welt["andere"]
    beides = client.get(f"/api/email-dispatches?project_id={welt['projekt1']}&customer_id={welt['kunde1']}")
    assert beides.status_code == 400


def test_projektmappe_und_kundenakte_zeigen_ihren_versand():
    mappe = (TEMPLATES / "project_folder.html").read_text(encoding="utf-8")
    akte = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    baustein = (TEMPLATES / "_email_dispatch.html").read_text(encoding="utf-8")
    protokoll = (TEMPLATES / "email_dispatches.html").read_text(encoding="utf-8")
    assert 'data-tab="sec-dispatch"' in mappe and "renderDispatchList('projectDispatches',{project_id:projectId})" in mappe
    assert "renderDispatchList('customerDispatches',{customer_id:customerId})" in akte
    from tests import vorlagen_js

    assert all(vorlagen_js.bindet_ein(n, "_email_dispatch.html", TEMPLATES) for n in ("project_folder.html", "customer.html"))
    assert "`/api/email-dispatches?${anfrage}&limit=100`" in baustein
    # Die Mahnung führt in ihre Rechnung zur Mahnung -- im Versandprotokoll und in den neuen Listen derselbe Link.
    assert "mahnung: d.invoice_id ? `/invoices/${Number(d.invoice_id)}?mahnung=${id}` : '/mahnwesen'" in baustein
    assert "${dispatchDocLink(d)}" in protokoll and "function docLink" not in protokoll and "mahnung:'/mahnwesen'" not in protokoll
    assert "q.set('project_id',projektId)" in protokoll and "q.set('customer_id',kundeId)" in protokoll
    rechnung = (TEMPLATES / "invoice_detail.html").read_text(encoding="utf-8")
    assert 'data-mahnung="${r.id}"' in rechnung and "renderReminders(status,list);markiereMahnung()" in rechnung


def test_mobile_kopfzeile_mit_mein_konto():
    kopf = (TEMPLATES / "_mobile_header.html").read_text(encoding="utf-8")
    rechts = kopf[kopf.index('<div class="mobile-header-right">'):kopf.index('<div class="mobile-search-bar">')]
    assert '<a class="mobile-header-account" href="/account">Mein Konto</a>' in rechts


@pytest.mark.parametrize("pfad, erwartet", [("/services/new", "const serviceId = null;"), ("/services/7/edit", "const serviceId = 7;")])
def test_leistungsformular_rendert_eine_gueltige_kennung(threaded_db_session, router_test_client, monkeypatch, pfad, erwartet):
    """Bis 1.8.112 rendert /services/new "const serviceId = None;" (default() greift bei None nicht) -- das Skript brach ab, "Leistung
    anlegen" ging für keine Rolle (gefunden im Klicktest zu 1.8.113)."""
    from app.routers.pages import router as pages_router, templates
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)
    html = router_test_client(threaded_db_session, pages_router, role="buero_auftrag").get(pfad).text
    assert erwartet in html


def _leistungsformular(*, darf_vorgaben: bool, bearbeiten: bool) -> str:
    skript = seite("service_form.html", "init().catch(")
    skript = skript.replace("const kannVorgabenLesen = 1;", f"const kannVorgabenLesen = {'true' if darf_vorgaben else 'false'};")
    if not bearbeiten:
        skript = skript.replace("const serviceId = 1;", "const serviceId = null;")
    assert "const kannVorgabenLesen = " + ("true" if darf_vorgaben else "false") in skript
    return skript


ANTWORTEN = {
    "/api/settings/option-groups/service_types": {"options": []},
    "/api/calculation-settings": {"labor_rate": "90", "material_markup_pct": "10", "overhead_pct": "0", "risk_profit_pct": "0"},
    "/api/services/1": {"id": 1, "external_id": "L-1", "short_text": "Rinne reinigen", "long_text": None, "quantity": "1",
                        "unit": "Stk", "source_type": "manual", "materials": [], "service_type": None, "catalog_id": None},
    "/api/services/1/calculation": {"site_time_minutes": "60", "workshop_time_minutes": "0", "labor_rate": "82.50",
                                    "labor_rate_override": None, "material_markup_pct": "10", "material_markup_pct_override": None,
                                    "overhead_pct": "5", "overhead_pct_override": "5", "risk_profit_pct": "3",
                                    "risk_profit_pct_override": None, "subcontractor_cost": "0", "equipment_cost": "0",
                                    "other_cost": "0", "manual_sale_price": None},
}
ABLAUF = """await init();
  return {lohn: _element('laborRateDefault').textContent, gk: _element('overheadDefault').textContent,
          vorschau: _element('calcPreview').innerHTML};"""


@nur_mit_node
def test_leistungsformular_laedt_fuer_buero_auftrag_mit_den_werten_der_leistung():
    lauf = im_browser(_leistungsformular(darf_vorgaben=False, bearbeiten=True), ABLAUF, ANTWORTEN)
    assert "/api/calculation-settings" not in [a["url"] for a in lauf["aufrufe"]]
    e = lauf["ergebnis"]
    assert "82,50" in e["lohn"] and e["gk"] == "(Standard laut Kalkulationsvorgaben)"  # GK hat einen eigenen Wert
    # 1 h × 82,50 € = 82,50 €, GK 5 % eigener Wert, W&G 3 % aus der Kalkulation: alle Werte bekannt, kein Hinweis.
    assert "82,50" in e["vorschau"] and "data-vorschau-hinweis" not in e["vorschau"]


@nur_mit_node
def test_neue_leistung_fuer_buero_auftrag_rechnet_ohne_angenommene_standardwerte():
    lauf = im_browser(_leistungsformular(darf_vorgaben=False, bearbeiten=False), ABLAUF, ANTWORTEN)
    assert [a["url"] for a in lauf["aufrufe"]] == ["/api/settings/option-groups/service_types"]
    e = lauf["ergebnis"]
    assert e["lohn"] == "(Standard laut Kalkulationsvorgaben)"
    assert "—" in e["vorschau"] and "data-vorschau-hinweis" in e["vorschau"]  # bis 1.8.112 rechnete die Vorschau mit 82 €/h


@nur_mit_node
def test_buero_finanzen_liest_die_kalkulationsvorgaben_wie_bisher():
    lauf = im_browser(_leistungsformular(darf_vorgaben=True, bearbeiten=False), ABLAUF, ANTWORTEN)
    assert "/api/calculation-settings" in [a["url"] for a in lauf["aufrufe"]]
    assert "90,00" in lauf["ergebnis"]["lohn"]
