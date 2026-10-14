"""Version 1.8.99 -- Vorweg zur Vorgabe vom 14.10.2026 (Korrekturen der Festlegungen 1.8.96/1.8.97).

- 96-13: window.__dkZeitlimit steht nur im Baustein (app/templates/_speichern.html) und unter scripts/ -- die Versand-Teilvorlage las es
  bis 1.8.98 selbst (jetzt zeitlimitSekunden() aus dem Baustein).
- moveItemBefore (Angebots-Editor, Drag-and-drop auf eine Position) als Teil-Update: POST /api/quotes/{id}/items/{item_id}/move schickt
  nur before_item_id, die Reihenfolge rechnet der Server -- bis 1.8.98 Titel und Reihenfolge aller Positionen des Zieltitels aus dem Stand
  beim Laden (Nebenbefund 5 aus 1.8.96). Angriffstest Regel 25 (fremde Positionen).
- 97-7: das Speichern der Kalkulation lädt das LV in seinem Bereich 'angebot' neu; Formular und Kalkulation nur, wenn noch dieselbe
  Position gewählt ist (Nebenbefund 10 aus 1.8.97).
- 96-19: Zeilensperre überall, wo ein gespeicherter Wert aus mehreren Feldern abgeleitet wird -- Angriffstests mit zwei gleichzeitigen
  Teil-Updates verschiedener Felder gegen PostgreSQL (opt-in, Wegwerf-Schema): Verkaufspreis einer Leistung, Nummerierung im Angebot
  (Verschieben), Auftrag und LV-Position einer Zeit- und einer Gruppenbuchung, Materialbedarf der Arbeitsvorbereitung nach einer
  Auftragsposition (im selben Commit), Art und Name eines Kontakts. Die Sperre belegt _run(): die zweite Aktion wartet auf die erste.

96-1 (Zeitlimit beim Hochladen) steht in tests/test_v404_hochladen_zeitlimit.py, 96-7 und 96-6 in tests/test_v399_abschliessen.py, 97-1 in
tests/test_v400_lesen_ueber_baustein.py, 96-24 in tests/test_v399_teil_updates_rest.py."""

from __future__ import annotations

import subprocess
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Contact, Employee, ImportBatch, Order, OrderItem, OrderItemCalculationSnapshot, OrderItemMaterialSnapshot, Quote, QuoteItem,
    QuoteItemLayout, Service, ServiceCalculation, ServiceMaterial, TimeEntry, WorkPreparationMaterial,
)
from app.projects import auto_number_quote, create_quote_section, load_quote, quote_to_dict
from app.routers import quotes as quotes_router
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v375_rechnungen_sperren import _run, _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v400_lesen_ueber_baustein import _ausfuehren

ROOT = Path(__file__).resolve().parent.parent
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")


# ---------------------------------------------------------------------------
# 96-13: __dkZeitlimit nur im Baustein und unter scripts/
# ---------------------------------------------------------------------------

def _dateien_mit(text: str) -> list[str]:
    dateien = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8").stdout.split("\n")
    return sorted(f for f in dateien if f and (ROOT / f).is_file() and text.encode() in (ROOT / f).read_bytes())


def test_das_zeitlimit_setzt_nur_der_baustein_und_ein_klicktest():
    """Festlegung 1.8.96 Nr. 13 (korrigiert 14.10.2026): window.__dkZeitlimit steht im Code nur im Baustein und unter scripts/ (dort
    kürzen es Klicktests). Tests und Dokumentation zählen nicht als Code."""
    erlaubt = lambda f: f == "app/templates/_speichern.html" or f.startswith(("scripts/", "tests/")) or f.endswith(".md")  # noqa: E731
    assert [f for f in _dateien_mit("__dkZeitlimit") if not erlaubt(f)] == []
    assert "app/templates/_speichern.html" in _dateien_mit("__dkZeitlimit")  # sonst prüfte der Test nichts


# ---------------------------------------------------------------------------
# moveItemBefore: Teil-Update
# ---------------------------------------------------------------------------

@nur_mit_node
def test_verschieben_auf_eine_position_schickt_nur_das_ziel():
    """Bis 1.8.98 schickte moveItemBefore sections:[] und items:[alle Positionen des Zieltitels mit Titel und Reihenfolge aus dem Stand
    beim Laden] an /reorder. Jetzt nur, vor welche Position."""
    log = _ausfuehren("quote_editor.html", ["moveItemBefore"], """
        const quoteId=3; let quote={items:[{id:1,section_id:null,layout_sort_order:10},{id:2,section_id:null,layout_sort_order:20}]};
        async function reloadQuote(){LOG.push('LV neu geladen')}
        const _f=globalThis.fetch; globalThis.fetch=(u,o={})=>{LOG.push((o.method||'GET')+' '+u+' '+(o.body||''));return _f(u,o)};
    """, """
        const a=moveItemBefore(2,1); await ruhe();
        await antworte('/api/quotes/3/items/2/move',{});
        await a;
        await moveItemBefore(1,1);
    """)
    assert [x for x in log if not x.startswith("fetch")] == [
        'POST /api/quotes/3/items/2/move {"before_item_id":1}', "LV neu geladen"]


def _angebot(db, number="0001"):
    """Angebot mit Titel T1 (Positionen a, b, c) und T2 (d), nummeriert."""
    from tests.test_v325_contract_basis import make_quote
    quote = make_quote(db, is_consumer=False, number=number)
    a = quote.items[0]
    t1 = create_quote_section(db, quote.id, "T1", None, None)
    t2 = create_quote_section(db, quote.id, "T2", None, None)
    positionen = {"a": a}
    for name in ("b", "c", "d"):
        item = QuoteItem(quote_id=quote.id, position_number=name, short_text=name, quantity=D("1"), unit="Stk", unit_price=D("10"))
        db.add(item)
        db.flush()
        positionen[name] = item
    for n, (name, titel) in enumerate((("a", t1), ("b", t1), ("c", t1), ("d", t2)), 1):
        layout = db.scalar(select(QuoteItemLayout).where(QuoteItemLayout.quote_item_id == positionen[name].id))
        if layout is None:
            db.add(QuoteItemLayout(quote_item_id=positionen[name].id, section_id=titel.id, sort_order=n * 10))
        else:
            layout.section_id, layout.sort_order = titel.id, n * 10
    db.commit()
    auto_number_quote(db, quote.id)
    return quote.id, {k: v.id for k, v in positionen.items()}, (t1.id, t2.id)


def _reihe(db, quote_id) -> list[tuple]:
    db.expire_all()
    q = quote_to_dict(load_quote(db, quote_id))
    return sorted(((i["section_id"], i["position_number"], i["short_text"]) for i in q["items"]), key=lambda x: x[1])


def test_verschieben_rechnet_titel_und_reihenfolge_auf_dem_server(threaded_db_session, router_test_client):
    db = threaded_db_session
    qid, p, (t1, t2) = _angebot(db)
    client = router_test_client(db, quotes_router.router)
    # Inzwischen anderswo: eine neue Position e im Titel T1 -- der Editor kennt sie nicht, sie bleibt trotzdem in der Reihe.
    e = QuoteItem(quote_id=qid, position_number="e", short_text="e", quantity=D("1"), unit="Stk", unit_price=D("10"))
    db.add(e); db.flush()
    db.add(QuoteItemLayout(quote_item_id=e.id, section_id=t1, sort_order=35))
    db.commit()
    assert client.post(f"/api/quotes/{qid}/items/{p['d']}/move", json={"before_item_id": p["b"]}).status_code == 200
    assert [x[2] for x in _reihe(db, qid) if x[0] == t1] == ["Eindecken", "d", "b", "c", "e"]
    assert [x[1] for x in _reihe(db, qid)] == ["01.0010", "01.0020", "01.0030", "01.0040", "01.0050"]
    assert client.post(f"/api/quotes/{qid}/items/{p['c']}/move", json={"before_item_id": p["a"]}).status_code == 200
    assert [x[2] for x in _reihe(db, qid) if x[0] == t1] == ["c", "Eindecken", "d", "b", "e"]


def test_verschieben_mit_fremden_positionen_ist_404(threaded_db_session, router_test_client):
    """Regel 25: beide Positionen gehören zum Angebot der Adresse -- fremd wie unbekannt 404, nichts geändert."""
    db = threaded_db_session
    qid, p, _ = _angebot(db, "0001")
    qid2, p2, _ = _angebot(db, "0002")
    client = router_test_client(db, quotes_router.router)
    vorher = (_reihe(db, qid), _reihe(db, qid2))
    for item_id, ziel in ((p2["a"], p["b"]), (p["a"], p2["b"]), (999999, p["b"]), (p["a"], 999999)):
        antwort = client.post(f"/api/quotes/{qid}/items/{item_id}/move", json={"before_item_id": ziel})
        assert antwort.status_code == 404, (item_id, ziel, antwort.text)
    assert client.post(f"/api/quotes/{qid}/items/{p['a']}/move", json={"before_item_id": p["a"]}).status_code == 422
    assert client.post(f"/api/quotes/{qid}/items/{p['a']}/move", json={}).status_code == 422
    assert (_reihe(db, qid), _reihe(db, qid2)) == vorher


# ---------------------------------------------------------------------------
# 97-7: Kalkulation speichern lädt das LV in seinem Bereich neu
# ---------------------------------------------------------------------------

_KALKULATION = """
    const quoteId=3; let quote={items:[{id:1,unit_price:50},{id:2,unit_price:70}]}, currentItem=quote.items[0], currentCalc=null;
    const v=id=>document.getElementById(id).value; function cn(id){return Number(v(id)||0)}
    function fillItemEditor(){LOG.push('Formular '+currentItem.id+' EP '+currentItem.unit_price)}
    function fillCalc(){LOG.push('Kalkulation '+currentItem.id)}
    function renderAll(){LOG.push('LV EP '+quote.items.map(i=>i.unit_price).join('/'))}
"""


@nur_mit_node
def test_kalkulation_speichern_laedt_das_lv_im_bereich_angebot_neu():
    log = _ausfuehren("quote_editor.html", ["saveCalc"], _KALKULATION, """
        const s=saveCalc(); await ruhe();
        await antworte('/api/quotes/3/items/1/calculation',{effective_sale_price:61});
        await antworte('/api/quotes/3',{items:[{id:1,unit_price:61},{id:2,unit_price:70}]});
        await s;
        LOG.push(document.getElementById('calcStatus').textContent);
    """)
    assert log == ["fetch /api/quotes/3/items/1/calculation", "fetch /api/quotes/3", "Formular 1 EP 61", "Kalkulation 1", "LV EP 61/70",
                   "Kalkulation gespeichert. EP wurde übernommen."]


@nur_mit_node
def test_kalkulation_speichern_laesst_eine_inzwischen_gewaehlte_position_stehen():
    """Während des Speicherns wird Position 2 gewählt: das LV lädt neu, Formular und Kalkulation bleiben bei Position 2 (bis 1.8.98
    zeichnete das Neuladen die Kalkulation der ersten in das Formular der zweiten)."""
    log = _ausfuehren("quote_editor.html", ["saveCalc"], _KALKULATION, """
        const s=saveCalc(); await ruhe();
        currentItem=quote.items[1];
        await antworte('/api/quotes/3/items/1/calculation',{effective_sale_price:61});
        await antworte('/api/quotes/3',{items:[{id:1,unit_price:61},{id:2,unit_price:70}]});
        await s;
        LOG.push('gewählt '+currentItem.id+' EP '+currentItem.unit_price);
    """)
    assert log == ["fetch /api/quotes/3/items/1/calculation", "fetch /api/quotes/3", "LV EP 61/70", "gewählt 2 EP 70"]


# ---------------------------------------------------------------------------
# 96-19: zwei gleichzeitige Teil-Updates verschiedener Felder gegen PostgreSQL
# ---------------------------------------------------------------------------

ADMIN = SimpleNamespace(state=SimpleNamespace(erp_user=SimpleNamespace(role="admin", id=None, employee_id=None, username="admin")))


def _leistung(s) -> int:
    batch = ImportBatch(source_type="manual", source_name="Test", filename="-")
    s.add(batch); s.flush()
    service = Service(import_batch_id=batch.id, source_type="manual", external_id="L-1", short_text="Eindecken", quantity=D("1"),
                      unit="m²", site_time_raw=D("30"), workshop_time_raw=D("0"), time_unit="min", sale_price=D("50"))
    s.add(service); s.flush()
    s.add(ServiceCalculation(service_id=service.id, site_time_minutes=D("30"), labor_rate_override=D("60")))
    s.add(ServiceMaterial(service_id=service.id, name="Ziegel", quantity=D("10"), unit="Stk", waste_raw=D("0"),
                          purchase_price=D("2"), price_basis=D("1")))
    s.commit()
    return service.id


def test_postgresql_leistung_zwei_kalkulationsfelder_gleichzeitig_preis_passt(pg):
    """Stundensatz hier, Einkaufspreis eines Materials dort (eine andere Zeile): der Verkaufspreis folgt aus der ganzen Kalkulation. Ohne
    die Sperre der Leistung rechnete die zweite Anfrage mit dem Stundensatz von vor der ersten und schrieb diesen Preis zuletzt."""
    from app.calculation import build_calculation, get_service_for_calculation, get_settings_for_catalog
    from app.routers.services import update_service_calculation
    from app.schemas import MaterialOverrideIn, ServiceCalculationUpdate
    Session, _ = pg
    sid = _vorbereiten(Session, _leistung)
    mid = _vorbereiten(Session, lambda s: s.scalar(select(ServiceMaterial.id).where(ServiceMaterial.service_id == sid)))
    erste, zweite = _run(
        Session,
        lambda s: update_service_calculation(sid, ServiceCalculationUpdate(labor_rate_override=D("80")), db=s, _role=None),
        lambda s: update_service_calculation(sid, ServiceCalculationUpdate(material_overrides=[
            MaterialOverrideIn(material_id=mid, purchase_price_override=D("9"))]), db=s, _role=None))
    assert not isinstance(zweite, Exception), zweite

    def pruefen(s):
        service = get_service_for_calculation(s, sid)
        ergebnis = build_calculation(service, get_settings_for_catalog(s, service.catalog_id))
        return (service.calculation.labor_rate_override, [o.purchase_price_override for o in service.material_overrides],
                service.sale_price, ergebnis["effective_sale_price"])
    satz, abweichung, gespeichert, gerechnet = _vorbereiten(Session, pruefen)
    assert (satz, abweichung) == (D("80"), [D("9")])
    assert gespeichert == gerechnet


def test_postgresql_zwei_positionen_gleichzeitig_verschoben_nummerierung_passt(pg):
    Session, _ = pg
    qid, p, (t1, _t2) = _vorbereiten(Session, lambda s: _angebot(s, "0101"))
    from app.routers.quotes import move_quote_item_api
    from app.schemas import QuoteItemMove
    erste, zweite = _run(Session,
                         lambda s: move_quote_item_api(qid, p["d"], QuoteItemMove(before_item_id=p["a"]), db=s, _role=None),
                         lambda s: move_quote_item_api(qid, p["c"], QuoteItemMove(before_item_id=p["b"]), db=s, _role=None))
    assert not isinstance(zweite, Exception), zweite

    def pruefen(s):
        vorher = _reihe(s, qid)
        auto_number_quote(s, qid)  # neu gerechnet aus dem gespeicherten Stand: ändert nichts mehr
        return vorher, _reihe(s, qid)
    gespeichert, neu_gerechnet = _vorbereiten(Session, pruefen)
    assert gespeichert == neu_gerechnet
    assert [x[2] for x in gespeichert if x[0] == t1] == ["d", "Eindecken", "c", "b"]


def _zwei_auftraege(s) -> dict:
    from tests.test_v325_contract_basis import beauftragen, make_quote
    werte = {}
    for nr in ("0201", "0202"):
        quote = make_quote(s, is_consumer=False, number=nr)
        s.add(QuoteItem(quote_id=quote.id, position_number="2", short_text="Rinne", quantity=D("4"), unit="m", unit_price=D("20")))
        s.commit()
        order = beauftragen(s, load_quote(s, quote.id))
        werte[nr] = (order.id, [i.id for i in s.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id))])
    mitarbeiter = Employee(employee_number="Z-1", first_name="Zoe", last_name="Zeit", employee_group="gewerblich", weekly_hours=D("40"),
                           active=True)
    s.add(mitarbeiter); s.commit()
    werte["mitarbeiter"] = mitarbeiter.id
    return werte


def _konsistent(s, model, row_id) -> tuple:
    row = s.get(model, row_id)
    item = s.get(OrderItem, row.order_item_id) if row.order_item_id else None
    return row.order_id, row.order_item_id, item is None or item.order_id == row.order_id


def test_postgresql_zeitbuchung_auftragswechsel_und_lv_position_gleichzeitig(pg):
    """Hier wechselt der Auftrag (die LV-Position entfällt), dort wird eine LV-Position des alten Auftrags gewählt. Unter der Sperre
    sieht die zweite den neuen Auftrag und lehnt die fremde Position ab (422) -- ohne sie prüfte sie gegen den alten Auftrag."""
    from app.routers.time_tracking import put_time_entry
    from app.schemas import TimeEntryUpdate
    from app.time_tracking import create_manual_entry
    Session, _ = pg
    w = _vorbereiten(Session, _zwei_auftraege)
    (o1, i1), (o2, _i2) = w["0201"], w["0202"]
    eid = _vorbereiten(Session, lambda s: create_manual_entry(s, employee_id=w["mitarbeiter"], order_id=o1, work_date=date(2026, 10, 1),
                                                                hours=D("4"), order_item_id=i1[0]).id)
    erste, zweite = _run(Session,
                         lambda s: put_time_entry(eid, TimeEntryUpdate(order_id=o2), ADMIN, db=s, _role=None),
                         lambda s: put_time_entry(eid, TimeEntryUpdate(order_item_id=i1[1]), ADMIN, db=s, _role=None))
    assert isinstance(zweite, HTTPException) and zweite.status_code == 422, zweite
    assert _vorbereiten(Session, lambda s: _konsistent(s, TimeEntry, eid)) == (o2, None, True)


def test_postgresql_gruppenbuchung_auftragswechsel_und_lv_position_gleichzeitig(pg):
    from app.models import TimeEntryGroup
    from app.routers.time_tracking import put_time_group
    from app.schemas import TimeGroupUpdate
    from app.time_tracking import create_group_manual_entry
    Session, _ = pg
    w = _vorbereiten(Session, _zwei_auftraege)
    (o1, i1), (o2, _i2) = w["0201"], w["0202"]
    gid = _vorbereiten(Session, lambda s: create_group_manual_entry(
        s, employee_ids=[w["mitarbeiter"]], team_id=None, actor_employee_id=None, is_admin=True, order_id=o1,
        work_date=date(2026, 10, 1), hours=D("4"), order_item_id=i1[0]).id)
    erste, zweite = _run(Session,
                         lambda s: put_time_group(gid, TimeGroupUpdate(order_id=o2), ADMIN, db=s, _role=None),
                         lambda s: put_time_group(gid, TimeGroupUpdate(order_item_id=i1[1]), ADMIN, db=s, _role=None))
    assert isinstance(zweite, HTTPException) and zweite.status_code == 422, zweite
    assert _vorbereiten(Session, lambda s: _konsistent(s, TimeEntryGroup, gid)) == (o2, None, True)
    eintraege = _vorbereiten(Session, lambda s: [(e.order_id, e.order_item_id) for e in s.scalars(
        select(TimeEntry).where(TimeEntry.employee_id == w["mitarbeiter"]))])
    assert eintraege == [(o2, None)]


def test_postgresql_auftragsposition_aendert_den_materialbedarf_im_selben_commit(pg, monkeypatch):
    """Der Materialbedarf der Arbeitsvorbereitung (Menge je Einheit x Menge der Position) entsteht noch unter der Sperre der
    Auftragszeile, im selben Commit wie die Menge -- bis 1.8.98 nach dem Commit, eine gleichzeitige Änderung einer anderen Position
    konnte ihn veralten lassen. Belegt: während des Neuaufbaus sieht eine andere Sitzung die neue Menge noch nicht."""
    import app.work_preparation as wp
    from app.routers.orders import put_order_item
    from app.schemas import OrderItemUpdate
    from app.work_preparation import ensure_preparation
    Session, order_id = pg

    def vorbereiten(s):
        item = s.scalar(select(OrderItem).where(OrderItem.order_id == order_id))
        snapshot = OrderItemCalculationSnapshot(order_item_id=item.id)
        s.add(snapshot); s.flush()
        s.add(OrderItemMaterialSnapshot(calculation_id=snapshot.id, name="Ziegel", unit="Stk", quantity=D("12"), waste_pct=D("0")))
        s.commit()
        ensure_preparation(s, order_id)
        s.commit()
        wp.refresh_preparation_materials(s, order_id)
        return item.id
    iid = _vorbereiten(Session, vorbereiten)
    gesehen = []
    echt = wp.refresh_preparation_materials

    def beobachtet(db, oid, *args, **kwargs):
        gesehen.append(_vorbereiten(Session, lambda s: s.get(OrderItem, iid).quantity))
        return echt(db, oid, *args, **kwargs)
    monkeypatch.setattr(wp, "refresh_preparation_materials", beobachtet)
    _vorbereiten(Session, lambda s: put_order_item(order_id, iid, OrderItemUpdate(quantity=D("7")), db=s, _role=None))
    assert gesehen == [D("10")]  # noch nicht committet, als der Bedarf neu aufgebaut wurde
    bedarf = _vorbereiten(Session, lambda s: [m.calculated_quantity for m in s.scalars(select(WorkPreparationMaterial))])
    assert bedarf == [D("84")]


def test_postgresql_kontakt_art_und_name_gleichzeitig(pg):
    """Hier wird aus der Person eine Firma (mit vorhandener Firmenbezeichnung), dort die Firmenbezeichnung geleert. Unter der Sperre sieht
    das Leeren die neue Art und lehnt ab -- ohne sie stand am Ende eine Firma ohne Namen."""
    from app.contacts import create_contact, update_contact
    Session, _ = pg
    cid = _vorbereiten(Session, lambda s: create_contact(s, {"kind": "person", "last_name": "Plan", "company_name": "Büro Plan"}).id)
    erste, zweite = _run(Session,
                         lambda s: update_contact(s, s.get(Contact, cid), {"kind": "firma"}),
                         lambda s: update_contact(s, s.get(Contact, cid), {"company_name": None}))
    assert isinstance(zweite, ValueError), zweite
    assert _vorbereiten(Session, lambda s: (lambda c: (c.kind, c.company_name))(s.get(Contact, cid))) == ("firma", "Büro Plan")


def _zeile_gesperrt(Session, aktion, model, row_id) -> bool:
    """Während aktion ihren Commit hält (tests/test_v375_rechnungen_sperren.py::_held): ist die Zeile row_id von model gesperrt?
    Belegt mit SELECT … FOR UPDATE NOWAIT aus einer anderen Sitzung -- unabhängig davon, ob eine zweite Aktion zufällig an einer anderen
    Zeilensperre wartet (z. B. beim Umnummerieren)."""
    import threading

    from sqlalchemy.exc import OperationalError

    from tests.test_v375_rechnungen_sperren import _held
    ready = threading.Event()
    holder, release, thread, result = _held(Session, aktion, ready)
    assert ready.wait(timeout=10)
    probe = Session()
    try:
        probe.execute(select(model.id).where(model.id == row_id).with_for_update(nowait=True))
        gesperrt = False
    except OperationalError:
        gesperrt = True
    finally:
        probe.close()
        release.set()
        thread.join(timeout=30)
        holder.close()
    assert not isinstance(result.get("result"), Exception), result
    return gesperrt


def test_postgresql_kalkulation_einer_leistung_sperrt_die_leistung(pg):
    from app.routers.services import update_service_calculation
    from app.schemas import ServiceCalculationUpdate
    Session, _ = pg
    sid = _vorbereiten(Session, _leistung)
    assert _zeile_gesperrt(Session, lambda s: update_service_calculation(
        sid, ServiceCalculationUpdate(other_cost=D("5")), db=s, _role=None), Service, sid)


def test_postgresql_verschieben_und_nummerieren_sperren_das_angebot(pg):
    from app.routers.quotes import move_quote_item_api, update_item_layout_api
    from app.schemas import QuoteItemLayoutUpdate, QuoteItemMove
    Session, _ = pg
    qid, p, (_t1, t2) = _vorbereiten(Session, lambda s: _angebot(s, "0301"))
    assert _zeile_gesperrt(Session, lambda s: move_quote_item_api(
        qid, p["d"], QuoteItemMove(before_item_id=p["a"]), db=s, _role=None), Quote, qid)
    assert _zeile_gesperrt(Session, lambda s: update_item_layout_api(
        qid, p["a"], QuoteItemLayoutUpdate(section_id=t2), db=s, _role=None), Quote, qid)
