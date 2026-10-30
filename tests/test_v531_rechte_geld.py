"""Version 1.9.111 (Stufe 5, R1, Punkt 1, Entscheidung Tobias): mit Geld arbeiten nur Admin und Büro – Finanzen -- eine Regel in
app/permissions.py (darf_geld(), require_geld).

    Server      jeder schreibende Endpunkt an Rechnungen, Zahlungen, Mahnungen und Nebenforderungen nimmt nur Admin und Büro – Finanzen
                (Struktur über alle Routen der vier Router; einzige Ausnahme die Mahnstufen in den Einstellungen, Festlegung 1.9.111);
                „Zustellung nachtragen“, Versandergebnis und Klären an Rechnung und Mahnung ebenso, an jedem anderen Dokument wie bisher
    Angriff     Büro – Auftrag: jede Geld-Aktion 403 mit GELD_NUR_LESEN, in der Datenbank ändert sich nichts
    Gegenprobe  Büro – Finanzen und Admin: dieselbe Aktion 200
    Lesen       Büro – Auftrag liest weiter jede Rechnung, Zahlung, Mahnung und Nebenforderung (200)
    Oberfläche  Auftrag, Rechnung, Kundenakte und Mahnwesen bekommen von der Seitenroute, ob das Konto mit Geld arbeitet; Büro – Auftrag
                sieht keinen Knopf (Rechnung anlegen, Bulk-Entwürfe) und den Hinweis; die Knöpfe der Skripte prüft
                scripts/klicktest_rechte_geld.py im Browser
"""

import re
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

from app.auth import hash_password
from app.berlin_time import berlin_today
from app.database import get_db
from app.dunning_charges import discard_default_start
from app.email_sending import update_smtp_settings
from app.models import (
    AppUser, DispatchAuthorization, DispatchCopy, DispatchOutcome, EmailDispatch, Invoice, InvoiceCharge, InvoiceDeduction,
    InvoiceDefaultStart, InvoiceItem, Payment, PaymentAllocation, PaymentRefundSource, Reminder, SentDocument,
)
from app.payments import Line, book_payment, invoice_customer_id
from app.permissions import GELD_NUR_LESEN, GELD_ROLLEN, darf_geld
from app.reminders import create_reminder, finalize_and_send_reminder
from app.routers.dunning_charges import router as charges_router
from app.routers.email_dispatches import router as dispatches_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from app.routers.reminders import router as reminders_router
from tests import test_v378_rechnung_sperre_und_datum as v378
from tests.test_v382_mahnwesen import _rechnung, _welt
from tests.test_v383_nebenforderungen import _gebucht, _welt_mit_verzug
from tests.test_v393_ueberzahlung import _ueberzahlt

D = Decimal
HEUTE = berlin_today()
ROUTER = (invoices_router, payments_router, reminders_router, charges_router, dispatches_router)
# Seit 1.9.120 leer: die Mahnstufen in den Einstellungen (Fristen, Gebühren, Texte) gehören zum Geld (Festlegung 1.9.111 Nr. 1 nicht
# bestätigt, tests/test_v540_einstellungen_mit_geld.py) -- bis 1.9.119 stand hier PUT /api/reminder-levels/{level_id}.
KEIN_GELD: set = set()
STAND = (Invoice, InvoiceItem, InvoiceDeduction, Payment, PaymentAllocation, PaymentRefundSource, Reminder, InvoiceCharge,
         InvoiceDefaultStart, EmailDispatch, DispatchOutcome, DispatchAuthorization, DispatchCopy, SentDocument)


class Konto:
    """Wechselt die Rolle zwischen Vorbereitung (Admin) und Aktion -- dieselbe Test-App, dieselbe Datenbank."""
    rolle = "admin"


def _client(db, konto):
    app = FastAPI()
    for router in ROUTER:
        app.include_router(router)

    @app.middleware("http")
    async def _anmeldung(request, call_next):
        request.state.erp_user = AppUser(id=None, username=f"{konto.rolle}-test", display_name=konto.rolle.capitalize(),
                                         role=konto.rolle, active=True, password_hash=hash_password("Passwort123"))
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _stand(db):
    """Jede Zeile jeder Geld-Tabelle mit allen Spalten -- vorher und nachher gleich heißt: nichts geschrieben."""
    db.expire_all()
    stand = {}
    for model in STAND:
        spalten = [c.key for c in sa_inspect(model).mapper.column_attrs]
        stand[model.__name__] = sorted(tuple(str(getattr(o, s)) for s in spalten) for o in db.scalars(select(model)))
    return stand


def test_regel_je_rolle():
    assert {r: darf_geld(AppUser(username="x", role=r)) for r in ("admin", "buero_finanzen", "buero_auftrag", "field")} == {
        "admin": True, "buero_finanzen": True, "buero_auftrag": False, "field": False}
    assert darf_geld(None) is True  # ohne Konto (Tests ohne Anmeldung) wie die anderen Regeln


def _rollen_der_route(route):
    rollen, offen = [], list(route.dependant.dependencies)
    while offen:
        dep = offen.pop()
        if getattr(dep.call, "_dk_roles", None) is not None:
            rollen.append(dep.call._dk_roles)
        offen.extend(dep.dependencies)
    return rollen


def test_jede_schreibende_geld_route_nimmt_nur_admin_und_finanzen():
    """Struktur: jede Route der vier Geld-Router mit einer anderen Methode als GET -- auch eine künftige -- lässt Büro – Auftrag nicht
    durch (Rollen der Abhängigkeit höchstens Admin und Büro – Finanzen). Seit 1.9.120 ohne Ausnahme (bis 1.9.119 die Mahnstufen)."""
    funde, gesehen = [], set()
    for router in (invoices_router, payments_router, reminders_router, charges_router):
        for route in router.routes:
            for methode in route.methods - {"GET", "HEAD"}:
                schluessel = (methode, route.path)
                gesehen.add(schluessel)
                if schluessel in KEIN_GELD:
                    continue
                rollen = _rollen_der_route(route)
                if not rollen or not all(r <= GELD_ROLLEN for r in rollen):
                    funde.append(f"{methode} {route.path}: {rollen}")
    assert funde == []
    assert KEIN_GELD <= gesehen, "KEIN_GELD nennt eine Route, die es nicht mehr gibt"
    assert len(gesehen) >= 30  # 15 Rechnung, 6 Zahlung, 8 Mahnwesen, 3 Nebenforderung -- dazu Admin-Einstellungen


# --- Rundgang: jede Geld-Aktion als Büro – Auftrag 403, als Büro – Finanzen und Admin 200 ------------------------------------------

def _rechnung_welt():
    db, order_id = v378._welt()
    return db, {"order_id": order_id}


def _sz_rechnung(route):
    """Szenario aus dem Rundgang von tests/test_v378: Vorbereitung über den Client (als Admin), die Aktion danach."""
    def bauen(c, db, w):
        return v378.SZENARIEN[route](c, w["order_id"], db)
    return bauen


def _mahn_welt():
    db = _welt()
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")
    return db, {}


def _entwurf(db):
    return create_reminder(db, _rechnung(db, "0101"))


def _eingeschaltet(db):
    from app.models import GeneralSettings
    db.get(GeneralSettings, 1).dunning_charges_enabled = True
    db.commit()
    return _entwurf(db)


def _sz(vorbereiten, aktion):
    def bauen(c, db, w):
        wert = vorbereiten(db)
        return lambda: aktion(c, wert)
    return bauen


def _zahlung_mit_rest(db):
    invoice = _rechnung(db, "0201")
    payment = book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("300.00"), note=None,
                           lines=[], user_name="Test")
    return invoice, payment


def _zuordnung(db):
    invoice = _rechnung(db, "0202")
    payment = book_payment(db, customer_id=invoice_customer_id(invoice), received_on=HEUTE, amount=D("100.00"), note=None,
                           lines=[Line(invoice.id, zahlung=D("100.00"))], user_name="Test")
    return db.scalar(select(PaymentAllocation.id).where(PaymentAllocation.payment_id == payment.id))


def _verzug_welt():
    db, invoice, second = _welt_mit_verzug()
    return db, {"invoice": invoice, "second": second}


def _sz_verzug(aktion):
    def bauen(c, db, w):
        return aktion(c, db, w["invoice"], w["second"])
    return bauen


def _zustellung_rechnung(db):
    return _rechnung(db, "0301")


def _gesendet(db, art="rechnung", status="gesendet", alt=False):
    invoice = _rechnung(db, "0302")
    from datetime import datetime
    row = EmailDispatch(dispatch_key=f"geld-{art}-{status}", message_ref=f"geld-{art}-{status}", status=status, channel="smtp",
                        document_type=art, document_id=invoice.id, document_number=invoice.invoice_number,
                        to_recipients="kunde@example.com", subject="Rechnung")
    if alt:  # hängt: seit mehr als STUCK_AFTER in Arbeit
        row.created_at = datetime.utcnow() - timedelta(hours=1)
    db.add(row)
    db.commit()
    return row.id


SZENARIEN = {
    **{route: (_rechnung_welt, _sz_rechnung(route)) for route in v378.SZENARIEN},
    # Zahlungen
    ("POST", "/api/payments"): (_mahn_welt, _sz(lambda db: _rechnung(db, "0203"), lambda c, inv: c.post("/api/payments", json={
        "customer_id": invoice_customer_id(inv), "received_on": HEUTE.isoformat(), "amount": "100.00",
        "lines": [{"invoice_id": inv.id, "zahlung": "100.00"}]}))),
    ("POST", "/api/payments/{payment_id}/allocations"): (_mahn_welt, _sz(_zahlung_mit_rest, lambda c, w: c.post(
        f"/api/payments/{w[1].id}/allocations", json={"lines": [{"invoice_id": w[0].id, "zahlung": "50.00"}]}))),
    ("POST", "/api/payments/{payment_id}/reverse"): (_mahn_welt, _sz(_zahlung_mit_rest, lambda c, w: c.post(
        f"/api/payments/{w[1].id}/reverse", json={"reason": "falsch erfasst"}))),
    ("POST", "/api/payment-allocations/{allocation_id}/reverse"): (_mahn_welt, _sz(_zuordnung, lambda c, a: c.post(
        f"/api/payment-allocations/{a}/reverse", json={"reason": "falsche Rechnung"}))),
    ("POST", "/api/invoices/{invoice_id}/refunds"): (_mahn_welt, _sz(lambda db: _ueberzahlt(db)[2], lambda c, schluss: c.post(
        f"/api/invoices/{schluss.id}/refunds", json={"paid_on": HEUTE.isoformat(), "amount": "1190.00"}))),
    ("POST", "/api/customers/{customer_id}/refunds"): (_mahn_welt, _sz(_zahlung_mit_rest, lambda c, w: c.post(
        f"/api/customers/{invoice_customer_id(w[0])}/refunds",
        json={"paid_on": HEUTE.isoformat(), "lines": [{"payment_id": w[1].id, "amount": "300.00"}]}))),
    # Mahnungen
    ("POST", "/api/invoices/{invoice_id}/reminders"): (_mahn_welt, _sz(lambda db: _rechnung(db, "0101"), lambda c, inv: c.post(
        f"/api/invoices/{inv.id}/reminders", json={}))),
    ("POST", "/api/reminders/bulk"): (_mahn_welt, _sz(lambda db: _rechnung(db, "0101"), lambda c, inv: c.post(
        "/api/reminders/bulk", json={"invoice_ids": [inv.id]}))),
    ("POST", "/api/reminders/{reminder_id}/send"): (_mahn_welt, _sz(_entwurf, lambda c, r: c.post(f"/api/reminders/{r.id}/send"))),
    ("PUT", "/api/reminders/{reminder_id}"): (_mahn_welt, _sz(_entwurf, lambda c, r: c.put(
        f"/api/reminders/{r.id}", json={"text": "x", "payment_days": 9}))),
    ("PUT", "/api/reminders/{reminder_id}/charges"): (_mahn_welt, _sz(_eingeschaltet, lambda c, r: c.put(
        f"/api/reminders/{r.id}/charges",
        json={"fee_amount": "5.00", "fee_accepted": True, "flat_fee_accepted": False, "interest_accepted": False}))),
    ("DELETE", "/api/reminders/{reminder_id}"): (_mahn_welt, _sz(_entwurf, lambda c, r: c.delete(f"/api/reminders/{r.id}"))),
    ("POST", "/api/reminders/{reminder_id}/send-email"): (_mahn_welt, _sz(
        lambda db: finalize_and_send_reminder(db, _entwurf(db)),
        lambda c, r: c.post(f"/api/reminders/{r.id}/send-email", json={"dispatch_key": "geldtest-mahnung-1"}))),
    # Nebenforderungen und Verzug (Rundgang aus tests/test_v383)
    ("POST", "/api/invoices/{invoice_id}/default-start"): (_verzug_welt, _sz_verzug(lambda c, db, inv, r: (
        discard_default_start(db, db.scalar(select(InvoiceDefaultStart)), reason="neu"),
        lambda: c.post(f"/api/invoices/{inv.id}/default-start", json={"starts_on": str(HEUTE - timedelta(days=8))}))[1])),
    ("POST", "/api/invoice-default-starts/{start_id}/discard"): (_verzug_welt, _sz_verzug(lambda c, db, inv, r: (
        lambda s: lambda: c.post(f"/api/invoice-default-starts/{s}/discard", json={"reason": "falsch"}))(
        db.scalar(select(InvoiceDefaultStart.id))))),
    ("POST", "/api/invoice-charges/{charge_id}/reverse"): (_verzug_welt, _sz_verzug(lambda c, db, inv, r: (
        lambda g: lambda: c.post(f"/api/invoice-charges/{g}/reverse", json={"reason": "Kulanz"}))(_gebucht(db, r).id))),
    # Versandprotokoll an Rechnung und Mahnung
    ("POST", "/api/email-dispatches/manual"): (_mahn_welt, _sz(_zustellung_rechnung, lambda c, inv: c.post(
        "/api/email-dispatches/manual", data={"document_type": "rechnung", "document_id": str(inv.id), "channel": "einschreiben",
                                              "delivered_on": HEUTE.isoformat(), "note": "Rückschein liegt vor",
                                              "dispatch_key": "geldtest-zustellung-1", "to_client": "true"}))),
    ("POST", "/api/email-dispatches/{dispatch_id}/outcome"): (_mahn_welt, _sz(_gesendet, lambda c, d: c.post(
        f"/api/email-dispatches/{d}/outcome", data={"outcome": "empfangen", "outcome_on": HEUTE.isoformat(), "note": ""}))),
    ("POST", "/api/email-dispatches/{dispatch_id}/resolve"): (_mahn_welt, _sz(
        lambda db: _gesendet(db, status="in_arbeit", alt=True),
        lambda c, d: c.post(f"/api/email-dispatches/{d}/resolve", json={"outcome": "gesendet", "note": "im Postausgang gefunden"}))),
}


def test_rundgang_deckt_jede_schreibende_geld_route():
    routen = {(m, r.path) for router in (invoices_router, payments_router, reminders_router, charges_router)
              for r in router.routes for m in r.methods - {"GET", "HEAD"}}
    routen -= KEIN_GELD
    routen -= {("PUT", "/api/reminder-levels/{level_id}")}  # seit 1.9.120 Einstellung mit Geld -- Rundgang in tests/test_v540
    routen -= {("PUT", "/api/dunning-settings"), ("POST", "/api/base-interest-rates"), ("PUT", "/api/base-interest-rates/{rate_id}"),
               ("DELETE", "/api/base-interest-rates/{rate_id}"), ("PUT", "/api/dunning-legal-texts/{text_key}")}  # nur Admin
    assert sorted(routen - set(SZENARIEN)) == []


def _lauf(route, rolle):
    welt, bauen = SZENARIEN[route]
    db, w = welt()
    konto = Konto()
    try:
        client = _client(db, konto)
        aktion = bauen(client, db, w)  # vorbereitet als Admin
        konto.rolle = rolle
        vorher = _stand(db)
        antwort = aktion()
        return antwort, vorher, _stand(db)
    finally:
        db.close()


@pytest.mark.parametrize("route", sorted(SZENARIEN), ids=lambda r: f"{r[0]} {r[1]}")
@patch("app.email_sending.smtplib.SMTP")
def test_buero_auftrag_bekommt_403_und_nichts_aendert_sich(_smtp, route):
    antwort, vorher, nachher = _lauf(route, "buero_auftrag")
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["detail"] == GELD_NUR_LESEN
    assert nachher == vorher


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
@pytest.mark.parametrize("route", sorted(SZENARIEN), ids=lambda r: f"{r[0]} {r[1]}")
@patch("app.email_sending.smtplib.SMTP")
def test_finanzen_und_admin_gegenprobe_200(_smtp, route, rolle):
    antwort, vorher, nachher = _lauf(route, rolle)
    assert antwort.status_code == 200, antwort.text
    assert nachher != vorher, "Szenario schreibt nichts -- prüft nichts"


@patch("app.email_sending.smtplib.SMTP")
def test_zustellung_an_einem_anderen_dokument_bleibt_buero_auftrag(_smtp):
    """Gegenprobe der Grenze: die Regel gilt nur für Rechnung und Mahnung -- Zustellung eines Auftrags trägt Büro – Auftrag weiter nach."""
    db, w = _mahn_welt()
    konto = Konto()
    try:
        invoice = _rechnung(db, "0401")
        konto.rolle = "buero_auftrag"
        antwort = _client(db, konto).post("/api/email-dispatches/manual", data={
            "document_type": "auftrag", "document_id": str(invoice.order_id), "channel": "persoenlich",
            "delivered_on": HEUTE.isoformat(), "note": "übergeben", "dispatch_key": "geldtest-auftrag-1", "to_client": "true"})
        assert antwort.status_code == 200, antwort.text
    finally:
        db.close()


def test_buero_auftrag_liest_alles_und_die_liste_sagt_was_es_darf():
    db, w = _mahn_welt()
    konto = Konto()
    try:
        invoice = _rechnung(db, "0501")
        reminder = finalize_and_send_reminder(db, create_reminder(db, invoice))
        rechnung_d = _gesendet(db)
        auftrag = EmailDispatch(dispatch_key="geld-auftrag-lesen", message_ref="geld-auftrag-lesen", status="gesendet",
                                channel="smtp", document_type="auftrag", document_id=invoice.order_id, document_number="AUF",
                                to_recipients="kunde@example.com", subject="Auftrag")
        db.add(auftrag)
        db.commit()
        konto.rolle = "buero_auftrag"
        client = _client(db, konto)
        kunde = invoice_customer_id(db.get(Invoice, invoice.id))
        for url in (f"/api/invoices/{invoice.id}", f"/api/orders/{invoice.order_id}/invoices", "/api/invoices",
                    f"/api/invoices/{invoice.id}/reminders", f"/api/invoices/{invoice.id}/reminder-status", "/api/reminders",
                    "/api/reminders/overdue", f"/api/invoices/{invoice.id}/charges", f"/api/customers/{kunde}/payments",
                    f"/api/customers/{kunde}/open-invoices", "/api/payments/customer-balances", f"/api/reminders/{reminder.id}/pdf",
                    "/api/email-dispatches"):
            assert client.get(url).status_code == 200, url
        zeilen = {d["id"]: d for d in client.get("/api/email-dispatches").json()["items"]}
        assert (zeilen[rechnung_d]["can_resolve"], zeilen[rechnung_d]["can_record_outcome"]) == (False, False)
        assert (zeilen[auftrag.id]["can_resolve"], zeilen[auftrag.id]["can_record_outcome"]) == (True, True)
        konto.rolle = "buero_finanzen"
        zeilen = {d["id"]: d for d in client.get("/api/email-dispatches").json()["items"]}
        assert (zeilen[rechnung_d]["can_resolve"], zeilen[rechnung_d]["can_record_outcome"]) == (True, True)
    finally:
        db.close()


# --- Oberfläche: was die Seitenroute zeichnet -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "buero_auftrag"])
def test_seiten_zeichnen_knoepfe_nur_mit_geld(threaded_db_session, router_test_client, rolle):
    from app.routers.pages import router as pages_router
    db = threaded_db_session
    invoice = _rechnung(db, "0601")
    client = router_test_client(db, pages_router, role=rolle)
    geld = rolle != "buero_auftrag"
    seiten = {
        "auftrag": client.get(f"/orders/{invoice.order_id}"),
        "rechnung": client.get(f"/invoices/{invoice.id}"),
        "kunde": client.get(f"/customers/{invoice_customer_id(db.get(Invoice, invoice.id))}"),
        "mahnwesen": client.get("/mahnwesen"),
    }
    for name, antwort in seiten.items():
        assert antwort.status_code == 200, name
        assert re.search(r'const GELD="(ja|nein)"!=="nein";', antwort.text).group(1) == ("ja" if geld else "nein"), name
        assert ("data-geld-nur-lesen" in antwort.text) is (not geld), name
        if not geld:
            assert GELD_NUR_LESEN in antwort.text, name
    assert ('id="newInvoiceButton"' in seiten["auftrag"].text) is geld
    assert ('id="newInvoiceType"' in seiten["auftrag"].text) is geld
    assert ('id="bulkCreateBtn"' in seiten["mahnwesen"].text) is geld
    assert ('id="dueSelectAll"' in seiten["mahnwesen"].text) is geld


def test_skripte_fragen_geld_vor_jedem_knopf():
    """Die Knöpfe zeichnen die Skripte -- jede Stelle, die eine Geld-Aktion anbietet, fragt GELD (bzw. bearbeitbar()). Geprüft am Text
    der Vorlagen; das Verhalten im Browser prüft scripts/klicktest_rechte_geld.py."""
    from pathlib import Path
    vorlagen = Path(__file__).resolve().parent.parent / "app" / "templates"
    rechnung = (vorlagen / "invoice_detail.html").read_text(encoding="utf-8")
    assert "const bearbeitbar=()=>GELD&&invoice.is_editable;" in rechnung
    assert re.findall(r"invoice\.is_editable", rechnung) == ["invoice.is_editable", "invoice.is_editable"]  # Regel und Sperrhinweis
    for stelle in ("el.innerHTML=GELD?html:''", "GELD&&p&&(Number(p.open)>0", "${GELD?`<div class=\"alloc-reverse\">",
                   "${draft&&GELD?", "innerHTML=!GELD?'':status.next_level", "(GELD?`<div class=\"fields\" style=\"margin-top:8px\" data-erstattung>",
                   "GELD?{}:{manual:false,outcomes:false}", "${GELD&&(frei||invoice.closes_order)?'':'disabled'}"):
        assert stelle in rechnung, stelle
    kunde = (vorlagen / "customer.html").read_text(encoding="utf-8")
    # seit 1.9.137 (Stufe 5, R3): „⋮“ je Eingang, Knöpfe der Vorschläge und die Dialoge nur mit Geld (bis 1.9.136 Karte je Zahlung)
    assert "if(GELD&&!p.reversed){" in kunde and "let knoepfe='';\n  if(GELD){" in kunde
    assert '{% if geld %}\n<dialog id="zuordnenDialog"' in kunde
    mahn = (vorlagen / "mahnwesen.html").read_text(encoding="utf-8")
    for stelle in ("${!GELD?blocked:blocked||`<button class=\"primary\" onclick=\"sendReminder(${r.draft.id})\">",
                   "${GELD?`<button onclick=\"editReminder(${r.draft.id})\">", "${GELD?`<button class=\"danger\" onclick=\"deleteReminder(${r.id})\">",
                   "GELD&&!r.create_block&&r.next_level", "const emailAction = !GELD ?",
                   "GELD ? {} : {manual: false, outcomes: false}", "${GELD?`<button onclick=\"createReminder("):
        assert stelle in mahn, stelle
    auftrag = (vorlagen / "akte.html").read_text(encoding="utf-8")
    # seit 1.9.129 die Akte: kein „Löschen“ eines Entwurfs in der Rechnungsliste mehr (Befund D17, auf der Rechnungsseite); „Mahnen“ nur mit GELD
    assert "const knopf=a.geld&&!GELD?''" in auftrag
    assert '{% if geld %}<div class="hinweis-zeile" id="uNaechste" hidden>' in auftrag
