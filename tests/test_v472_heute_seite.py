"""Seit 1.9.45 (Stufe 4, R2): die Seite „Heute“ (/mobil) nach den Vorlagen heute-quer, heute-hoch, heute-gestern.

    Einsatz        die eigenen Berichte des Auftrags mit Titel „<Art> · <Dachflächen>“ und „noch n offen“ aus noch_offen(), die eigenen
                   offenen Checklisten mit der Zahl der fehlenden Pflichtangaben -- nie der Bericht eines Kollegen
    Reiter         „Heute“ statt „Einsätze“ (Adresse /mobil bleibt), ebenso der Anfang des Pfads auf den Seiten darunter
    Seite          ab 1000 px zwei Spalten (rechts 420 px), darunter eine; Zeilen ≥ 56 px, Hauptknöpfe 64 px, „Weiter“ 56 px; [hidden] gilt
                   auch für Karten und Kacheln; die Route öffnet die Adresse über einen festen https-Anfang; alles aus GET
                   /api/field-view/today über lesen()
Im Browser misst und klickt das scripts/klicktest_heute.py.
"""

import re
from datetime import timedelta

from app import berlin_time
from app.checklist_templates import add_field, create_template as create_checklist_template, publish_draft
from app.checklists import create_checklist
from app.inspection_templates import create_template, create_template_item
from app.models import Property, RoofArea
from app.service_reports import create_report
from tests import vorlagen_js as vj
from tests.test_v471_heute_server import _einsatz, _heute, welt  # noqa: F401  (Fixture)


def test_einsatz_mit_eigenen_berichten_und_checklisten(welt):  # noqa: F811
    db, order = welt["db"], welt["order"]
    halle = Property(customer_id=order.customer_id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()
    flaeche = RoofArea(property_id=halle.id, name="Dachfläche Nord", roof_type="flachdach")
    db.add(flaeche); db.flush()
    order.project.property_id = halle.id
    db.commit()
    vorlage = create_template(db, "Flachdach-Wartung", roof_type="flachdach")
    for text in ("Abdichtung", "Gully", "Attika"):
        create_template_item(db, vorlage["id"], text, "ja_nein", required=True)
    _einsatz(welt, order, [(welt["heute"], welt["heute"] + timedelta(days=1))], [welt["mia"], welt["tom"]])
    eigener = create_report(db, order.id, "wartung", created_by_employee_id=welt["mia"].id, roof_area_ids=[flaeche.id])
    create_report(db, order.id, "rapport", created_by_employee_id=welt["tom"].id)  # Toms Bericht -- nicht in Mias Karte
    cl = create_checklist_template(db, label="Sicherheitscheck", contexts=["auftrag"], field_readable=True)
    add_field(db, cl["draft_version_id"], {"field_type": "ja_nein", "label": "Absturzsicherung", "field_key": "abs", "required": True})
    publish_draft(db, cl["id"])
    liste = create_checklist(db, template_id=cl["id"], context_type="auftrag", order_id=order.id, created_by_employee_id=welt["mia"].id)
    karte = _heute(welt, welt["mia"])["einsaetze"][0]
    assert karte["berichte"] == [{"id": eigener["id"], "titel": "Wartungsbericht · Dachfläche Nord", "status": "entwurf", "noch_offen": 3}]
    # seit 1.9.50 „Checkliste <Name>“ (bis dahin der Name allein)
    assert karte["checklisten"] == [{"id": liste["id"], "titel": "Checkliste Sicherheitscheck", "status": "entwurf", "noch_offen": 1}]
    assert (karte["objekt"], karte["adresse"]) == ("Halle Nord", "Werkstr. 5, 52531 Übach-Palenberg")
    assert _heute(welt, welt["tom"])["einsaetze"][0]["berichte"][0]["titel"] == "Rapportbericht"


def _stil() -> str:
    return re.sub(r"\s", "", "\n".join(re.findall(r"<style>(.*?)</style>", (vj.TEMPLATES / "mobil.html").read_text(encoding="utf-8"), flags=re.S)))


def test_seite_masse_und_spalten():
    stil = _stil()
    assert ".heute{display:grid;grid-template-columns:minmax(0,1fr)420px;" in stil
    assert "@media(max-width:999px){.heute{grid-template-columns:minmax(0,1fr);" in stil
    assert "[hidden]{display:none!important}" in stil
    assert re.search(r"\.knopf\{height:64px;", stil) and ".zeile.knopf-aktion{height:56px;" in stil
    assert re.search(r"\.zeile\{[^}]*min-height:56px", stil) and ".offen-zeile{min-height:60px}" in stil
    # seit 1.9.50 sind die Wege des Einsatzes Knöpfe 48 px (bis dahin Links mit min-height 48 px)
    assert re.search(r"\.route\{min-height:48px", stil) and re.search(r"\.knopf-klein\{height:48px;", stil)


def test_seite_liest_ueber_den_baustein_und_baut_die_route_fest():
    text, _ = vj.seitentext("mobil.html")
    assert "return lesen('heute',()=>fetch('/api/field-view/today')" in text
    assert "'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(k.adresse)" in text
    assert "speichern('heute',()=>api(url,{method:'POST'" in text


def test_reiter_und_pfad_heissen_heute():
    kopf = (vj.TEMPLATES / "_mobile_header.html").read_text(encoding="utf-8")
    assert ">Heute</a>" in kopf and ">Einsätze</a>" not in kopf
    for name in vj.alle_vorlagen():
        text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
        assert 'href="/mobil">Einsätze</a>' not in text and "{text:'Einsätze',href:'/mobil'}" not in text, name
