"""Version 1.9.136 (Stufe 5, R3, Punkt 1) -- Verlauf des Kunden (app/kunde_verlauf.py, GET /api/customers/{id}/verlauf) und Stammdaten als
Teil-Update (PUT /api/customers/{id}, Regel 22).

Verlauf: Änderungen am Kunden (samt Profil), an „Kontakte & Kundenwissen“ (auch gelöschte Einträge), an seinen Objekten und Dachflächen, an
seinen Anfragen; seine Zahlungen; der Versand seiner Dokumente -- eine Zeile je Aktion wie in der Akte, Filter nach Art, Seiten über `vor`; nichts
von einem anderen Kunden; Büro – Auftrag liest, die Monteurin 403.

Stammdaten: der Handler übernimmt nur gesendete Felder -- „phone“ allein ändert nur das Telefon (Kategorie, Land, Nummer, Zahlungsbedingung,
„Verbraucher“ bleiben, im Änderungsprotokoll steht nur das Telefon); Name, Kategorie, Land, „Verbraucher“ ausdrücklich leer 422.
"""

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import select

import app.akte_verlauf as akte_verlauf
from app.crm import ensure_customer_profile
from app.grunddaten import anlegen
from app.models import AuditLog, Customer, CustomerExtraInfo, EmailDispatch, PaymentTerm, Property, RoofArea
from app.routers import customers as customers_router
from tests.test_v381_zahlungen import _abschlag, _auftrag, _buchen, _kunde
from tests.test_v547_akte_verlauf import _Anfrage


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    anlegen(db)
    db.commit()
    kessler = _kunde(db, "Kessler")
    ensure_customer_profile(db, kessler, "Privatkunde", "K-1")
    db.commit()
    with _Anfrage(7, "Olga Office", "PUT", f"/api/customers/{kessler.id}"):
        k = db.get(Customer, kessler.id)
        k.phone = "02451 55 01 20"
        ensure_customer_profile(db, k, "Gewerbekunde", None)
        db.commit()
    with _Anfrage(7, "Olga Office", "POST", f"/api/customers/{kessler.id}/extra-infos"):
        bleibt = CustomerExtraInfo(customer_id=kessler.id, info_type="phone", label="Sabine Kessler", value="0151 23 45 67 80")
        weg = CustomerExtraInfo(customer_id=kessler.id, info_type="info", label="Wissen", value="Schlüssel beim Hausmeister")
        db.add_all([bleibt, weg])
        db.commit()
    with _Anfrage(7, "Olga Office", "DELETE", f"/api/customers/{kessler.id}/extra-infos/{weg.id}"):
        db.delete(db.get(CustomerExtraInfo, weg.id))
        db.commit()
    with _Anfrage(9, "Bert Büro", "POST", "/api/properties"):
        objekt = Property(customer_id=kessler.id, name="Am Wasserturm 4", street="Am Wasserturm 4", city="Übach-Palenberg")
        db.add(objekt)
        db.commit()
    with _Anfrage(9, "Bert Büro", "POST", "/api/roof-areas"):
        flaeche = RoofArea(property_id=objekt.id, name="Hauptdach Süd")
        db.add(flaeche)
        db.commit()
    order = _auftrag(db, kessler)
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/invoices/x/send"):
        rechnung = _abschlag(db, order)
    jetzt = db.scalar(select(AuditLog.occurred_at).where(AuditLog.entity_type == "Rechnung").order_by(AuditLog.id.desc()))
    db.add(EmailDispatch(dispatch_key="kunde-verlauf-1", message_ref="m-kv-1", status="gesendet", channel="smtp", document_type="rechnung",
                         document_id=rechnung.id, document_number=rechnung.invoice_number, to_recipients="buchhaltung@kessler.example",
                         subject="Rechnung", created_at=jetzt + timedelta(seconds=2), created_by_user_id=8, created_by_name="Fin Finanzen"))
    db.commit()
    with _Anfrage(8, "Fin Finanzen", "POST", "/api/payments"):
        _buchen(db, rechnung, "100")
    lorenz = _kunde(db, "Lorenz")
    with _Anfrage(7, "Olga Office", "PUT", f"/api/customers/{lorenz.id}"):
        db.get(Customer, lorenz.id).phone = "0999"
        fremd = CustomerExtraInfo(customer_id=lorenz.id, info_type="info", label="Lorenz", value="nicht bei Kessler")
        db.add(fremd)
        db.commit()
    return {"db": db, "kessler": kessler, "lorenz": lorenz, "fremd": fremd, "objekt": objekt, "flaeche": flaeche, "weg": weg, "rechnung": rechnung,
            "client": lambda rolle="buero_auftrag": router_test_client(db, customers_router.router, role=rolle)}


def _strom(client, customer_id, **abfrage):
    antwort = client.get(f"/api/customers/{customer_id}/verlauf", params=abfrage)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def test_strom_des_kunden(welt):
    strom = _strom(welt["client"](), welt["kessler"].id)["eintraege"]
    typen = {z["entity_type"] for e in strom for z in e["einzelheiten"]}
    assert {"Kunde", "Kundenwissen", "Objekt", "Dachfläche", "Zahlungseingang"} <= typen
    kunde = next(e for e in strom if any(z["entity_type"] == "Kunde" and z["field_name"] == "phone" for z in e["einzelheiten"]))
    felder = {z["field_name"] for z in kunde["einzelheiten"]}
    assert {"phone", "category"} <= felder and kunde["konto"] == "Olga Office"  # Stammdaten und Profil: eine Aktion, eine Zeile
    geloescht = [z for e in strom for z in e["einzelheiten"] if z["entity_type"] == "Kundenwissen" and z["action"] == "gelöscht"]
    assert [z["entity_id"] for z in geloescht] == [str(welt["weg"].id)]  # gelöscht -- über den Schnappschuss gefunden
    objekt = next(e for e in strom if e["einzelheiten"] and e["einzelheiten"][0]["entity_type"] == "Objekt")
    assert objekt["ziel"] == {"href": f"/properties/{welt['objekt'].id}", "text": "Öffnen"}
    flaeche = next(e for e in strom if e["einzelheiten"] and e["einzelheiten"][0]["entity_type"] == "Dachfläche")
    assert flaeche["ziel"] == {"href": f"/roof-areas/{welt['flaeche'].id}", "text": "Öffnen"}
    versand = [e for e in strom if e["art"] == "versand"]
    assert len(versand) == 1 and "buchhaltung@kessler.example" in versand[0]["titel"]
    # nichts von Lorenz -- verglichen über die Protokollzeilen selbst: unter SQLite bekommt sein Eintrag die Kennung des gelöschten von Kessler
    # (die höchste Kennung wird nach dem Löschen neu vergeben), Art und Kennung allein unterscheiden die beiden nicht
    db = welt["db"]
    lorenz = set(db.scalars(select(AuditLog.id).where(AuditLog.request_path == f"/api/customers/{welt['lorenz'].id}")))
    assert lorenz  # Lorenz hat Zeilen im Protokoll -- sonst prüfte die nächste Zeile nichts
    assert lorenz.isdisjoint({z["id"] for e in strom for z in e["einzelheiten"]})


def test_filter_nach_art(welt):
    client = welt["client"]()
    zahlungen = _strom(client, welt["kessler"].id, art="zahlung")["eintraege"]
    assert zahlungen and {e["art"] for e in zahlungen} == {"zahlung"}
    versand = _strom(client, welt["kessler"].id, art="versand")["eintraege"]
    assert [e["art"] for e in versand] == ["versand"]
    assert client.get(f"/api/customers/{welt['kessler'].id}/verlauf", params={"art": "bericht"}).status_code == 422


def _kennungen(eintraege):
    """Jede Protokollzeile und jeder Versand eines Stroms -- Überschriften können an einer Seitengrenze anders ausfallen (ein Versand hängt dann
    an einer anderen Zeile), verloren oder doppelt darf nichts sein."""
    return [("zeile", z["id"]) for e in eintraege for z in e["einzelheiten"]] + [("versand", e["versand"]["id"]) for e in eintraege if e["versand"]]


def test_seiten_ohne_doppelte_und_ohne_luecken(welt, monkeypatch):
    voll = _strom(welt["client"](), welt["kessler"].id)["eintraege"]
    monkeypatch.setattr(akte_verlauf, "ZEILEN_JE_ABRUF", 2)
    client, gesehen, vor, seiten = welt["client"](), [], None, 0
    while True:
        seite = _strom(client, welt["kessler"].id, **({"vor": vor} if vor else {}))
        assert seite["eintraege"], "eine Seite ohne Zeilen, aber mit vor -- kein Fortschritt"
        gesehen += _kennungen(seite["eintraege"])
        seiten += 1
        vor = seite["vor"]
        if not vor:
            break
        assert seiten < 50
    assert seiten > 1 and sorted(gesehen) == sorted(_kennungen(voll))  # jede Protokollzeile und jeder Versand genau einmal


@pytest.mark.parametrize("rolle,status", [("buero_auftrag", 200), ("buero_finanzen", 200), ("admin", 200), ("field", 403)])
def test_rollen(welt, rolle, status):
    client = welt["client"](rolle)
    assert client.get(f"/api/customers/{welt['kessler'].id}/verlauf").status_code == status
    assert client.get("/api/customers/987654/verlauf").status_code == (404 if status == 200 else 403)


# --- Stammdaten als Teil-Update ----------------------------------------------------------------------------------------------------------

def _kunde_mit_allem(db):
    term = PaymentTerm(label="14 Tage netto", days=14)
    db.add(term)
    db.flush()
    k = Customer(name="Wohnbau Kessler GmbH", last_name="Wohnbau Kessler GmbH", country="Österreich", is_consumer=False, email="info@k.example")
    db.add(k)
    db.flush()
    ensure_customer_profile(db, k, "Gewerbekunde", "K-10042", default_payment_term_id=term.id, set_payment_term=True)
    db.commit()
    return k, term


def test_nur_gesendete_felder(welt):
    db = welt["db"]
    k, term = _kunde_mit_allem(db)
    vorher = db.scalar(select(AuditLog.id).order_by(AuditLog.id.desc()))
    antwort = welt["client"]().put(f"/api/customers/{k.id}", json={"phone": "02451 55 01 20"})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["phone"] == "02451 55 01 20"
    assert (daten["category"], daten["country"], daten["customer_number"], daten["default_payment_term_id"], daten["is_consumer"],
            daten["last_name"], daten["email"]) == ("Gewerbekunde", "Österreich", "K-10042", term.id, False, "Wohnbau Kessler GmbH", "info@k.example")
    felder = {f for f, in db.execute(select(AuditLog.field_name).where(AuditLog.id > vorher, AuditLog.entity_type == "Kunde"))}
    assert felder == {"phone"}


def test_zahlungsbedingung_ausdruecklich_leeren(welt):
    db = welt["db"]
    k, _ = _kunde_mit_allem(db)
    antwort = welt["client"]().put(f"/api/customers/{k.id}", json={"default_payment_term_id": None})
    assert antwort.status_code == 200 and antwort.json()["default_payment_term_id"] is None and antwort.json()["category"] == "Gewerbekunde"


@pytest.mark.parametrize("feld", ["last_name", "category", "country", "is_consumer"])
def test_pflichtfelder_nicht_leer(welt, feld):
    k, _ = _kunde_mit_allem(welt["db"])
    assert welt["client"]().put(f"/api/customers/{k.id}", json={feld: None}).status_code == 422


def test_akte_seiten_mit_aktion_ueber_die_grenze(welt, router_test_client, monkeypatch):
    """Fund 1.9.136, auch im Verlauf der Akte: reicht eine einzige Aktion über ZEILEN_JE_ABRUF, warf die Seite ihre einzige Gruppe weg und `vor`
    zeigte immer wieder auf dieselbe Stelle. Jetzt wächst die Seite (akte_verlauf.zeilen_seite()), jede Zeile kommt genau einmal."""
    from app.routers import projects as projects_router
    db = welt["db"]
    project_id = db.get(Customer, welt["kessler"].id).projects[0].id
    client = router_test_client(db, projects_router.router, role="buero_auftrag")
    voll = client.get(f"/api/projects/{project_id}/verlauf").json()["eintraege"]
    monkeypatch.setattr(akte_verlauf, "ZEILEN_JE_ABRUF", 1)
    gesehen, vor, seiten = [], None, 0
    while True:
        seite = client.get(f"/api/projects/{project_id}/verlauf", params={"vor": vor} if vor else {}).json()
        assert seite["eintraege"], "eine Seite ohne Zeilen, aber mit vor -- kein Fortschritt"
        gesehen += _kennungen(seite["eintraege"])
        seiten += 1
        vor = seite["vor"]
        if not vor:
            break
        assert seiten < 50
    assert seiten > 1 and sorted(gesehen) == sorted(_kennungen(voll))


def _aktion_mit_gleicher_zeit(db, customer_id, n=5):
    """n Protokollzeilen einer Aktion mit genau demselben Zeitpunkt (eine Anfrage, ein Flush) -- älter als alles andere."""
    zeit = db.scalar(select(AuditLog.occurred_at).order_by(AuditLog.occurred_at)) - timedelta(hours=1)
    zeilen = [AuditLog(occurred_at=zeit, actor_user_id=7, actor_name="Olga Office", action="geändert", entity_type="Kunde",
                       entity_id=str(customer_id), field_name=f"feld_{i}", old_value="a", new_value="b", request_method="PUT",
                       request_path=f"/api/customers/{customer_id}") for i in range(n)]
    db.add_all(zeilen)
    db.commit()
    return {z.id for z in zeilen}


def _alle_seiten(client, customer_id, *, leere_letzte=False):
    gesehen, vor, seiten = [], None, 0
    while True:
        seite = _strom(client, customer_id, **({"vor": vor} if vor else {}))
        assert seite["eintraege"] or (leere_letzte and not seite["vor"]), "eine Seite ohne Zeilen, aber mit vor -- kein Fortschritt"
        gesehen += _kennungen(seite["eintraege"])
        seiten += 1
        vor = seite["vor"]
        if not vor:
            return gesehen, seiten
        assert seiten < 50


def test_eine_aktion_ueber_die_grenze_kommt_ganz(welt, monkeypatch):
    """Fünf Zeilen einer Aktion mit demselben Zeitpunkt bei einer Grenze von 2: die Seite wächst (zeilen_seite()), keine Zeile geht verloren --
    eine Seitengrenze nach der Zeit allein ließe die mit demselben Zeitpunkt aus."""
    ids = _aktion_mit_gleicher_zeit(welt["db"], welt["kessler"].id)
    monkeypatch.setattr(akte_verlauf, "ZEILEN_JE_ABRUF", 2)
    gesehen, _ = _alle_seiten(welt["client"](), welt["kessler"].id)
    assert sorted(i for art, i in gesehen if art == "zeile" and i in ids) == sorted(ids)


def test_hoechstgrenze_erreicht_trotzdem_fortschritt(welt, monkeypatch):
    """Wächst die Seite nicht weiter (GRENZE_HOECHSTENS), bleibt die eine Gruppe stehen und `vor` geht zu älteren Zeilen -- das Blättern endet
    (bis 1.9.135 zeigte `vor` immer wieder auf dieselbe Stelle). Die übrigen Zeilen derselben Aktion mit genau demselben Zeitpunkt fehlen dann; das
    ist die Grenze (eine Aktion mit mehr als GRENZE_HOECHSTENS Zeilen), die letzte Seite darf leer sein."""
    _aktion_mit_gleicher_zeit(welt["db"], welt["kessler"].id)
    monkeypatch.setattr(akte_verlauf, "ZEILEN_JE_ABRUF", 2)
    monkeypatch.setattr(akte_verlauf, "GRENZE_HOECHSTENS", 2)
    _, seiten = _alle_seiten(welt["client"](), welt["kessler"].id, leere_letzte=True)
    assert seiten > 1


def test_kundenwissen_heisst_nach_seiner_bezeichnung(threaded_db_session, router_test_client):
    """Seit 1.9.137: „Kundenwissen Sabine Kessler angelegt“, ohne Bezeichnung nur „Kundenwissen angelegt“ -- nicht „Kundenwissen Kundenwissen angelegt“
    (so auch ältere Zeilen, deren Name nur die Art ist)."""
    from app.akte_verlauf import Gruppe, ueberschrift
    from app.audit import _entity_label
    from app.models import CustomerExtraInfo

    assert _entity_label(CustomerExtraInfo(info_type="phone", label="Sabine Kessler", value="1")) == "Sabine Kessler"
    assert _entity_label(CustomerExtraInfo(info_type="phone", label=None, value="1")) == "Kundenwissen"

    class Zeile:
        entity_type = "Kundenwissen"
        entity_type_label = "Kundenwissen"
        action = "angelegt"
        entity_label = "Kundenwissen"
        new_value = None

    assert ueberschrift(Gruppe(zeilen=[Zeile()]))[0] == "Kundenwissen angelegt"
    Zeile.entity_label = "Sabine Kessler"
    assert ueberschrift(Gruppe(zeilen=[Zeile()]))[0] == "Kundenwissen Sabine Kessler angelegt"
