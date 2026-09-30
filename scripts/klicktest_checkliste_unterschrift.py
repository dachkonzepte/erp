"""Klicktest: Unterschrift bindet den Inhalt einer Checkliste (1.8.13, Stufe 2 Runde 2a-1).

    Monteurin  (Handybreite) tippt eine Bemerkung und unterschreibt sofort danach: die Bemerkung
               wird vor der Unterschrift gespeichert, der Hinweis vor der ersten Unterschrift nennt
               die noch offene Pflichtangabe. Danach: Felder gesperrt, Karte "Unterschrieben",
               Zeit und Prüfsumme an der Unterschrift, kein "Entwurf löschen", die zweite
               Unterschrift (Kunde) bleibt möglich, kein Verwerfen-Feld.
    Büro       (Desktop) verwirft die Unterschriften -- erst ohne Begründung (Meldung, nichts
               passiert), dann mit. Danach offen, "Verworfene Unterschriften" mit Begründung.
    Monteurin  ergänzt die Pflichtangabe, unterschreibt neu, schließt ab.
    Büro       Geräteseite: "Als repariert markieren" ohne Notiz → Meldung, mit Notiz → erledigt.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben (Headless-Chrome
blockiert sonst, siehe docs/archiv/modul-checklisten.md, 1.8.1). Unterschriften werden mit
echten Mausereignissen auf die Zeichenfläche gezeichnet.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_checkliste_unterschrift.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

CONFIRM = "window.__confirms=[];window.confirm=m=>{window.__confirms.push(String(m));return true};"


def befuellen(db, k):
    from decimal import Decimal

    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import complete_checklist, create_checklist, save_answer
    from app.models import AppUser, Customer, Employee, OperationalAsset, Order, Project, WorkPreparationEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("karl", "E-2", "Karl", "Kollege"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="buero", display_name="Karl Kollege", role="buero_auftrag", employee_id=ma["karl"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle", property_address="Weg 1\n12345 Stadt")
    db.add(auftrag)
    geraet = OperationalAsset(name="Hubsteiger", asset_type="Maschine", asset_number="BM-7")
    db.add(geraet); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    t = create_template(db, label="Sicherheitscheck", contexts=["auftrag"])
    v = t["draft_version_id"]
    add_field(db, v, {"field_type": "ja_nein", "label": "Freigegeben", "field_key": "frei", "required": True})
    add_field(db, v, {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, v, {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig",
                      "required": True, "signer_label": "Monteur"})
    add_field(db, v, {"field_type": "unterschrift", "label": "Unterschrift Kunde", "field_key": "kunde", "signer_label": "Kunde"})
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)

    g = create_template(db, label="Geräte-Sichtprüfung", contexts=["betriebsmittel"], field_readable=True)
    add_field(db, g["draft_version_id"], {"field_type": "ja_nein", "label": "Einsatzbereit", "field_key": "einsatzbereit", "required": True})
    geraete_vorlage = publish_draft(db, g["id"])
    meldung = create_checklist(db, template_id=geraete_vorlage["id"], context_type="betriebsmittel", asset_id=geraet.id,
                               created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    feld = next(f["id"] for f in meldung["fields"] if f["field_key"] == "einsatzbereit")
    save_answer(db, meldung["id"], feld, "nein", recorded_by_employee_id=ma["mia"].id)
    complete_checklist(db, meldung["id"], completed_by_employee_id=ma["mia"].id)

    return {"checklist": cl["id"], "asset": geraet.id, "fields": {f["field_key"]: f["id"] for f in cl["fields"]},
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _unterschreiben(tab, feld_id: int, name: str) -> None:
    """Zeichnet mit echten Mausereignissen auf die Zeichenfläche und übernimmt die Unterschrift."""
    import asyncio

    await tab.js(f"document.getElementById('pad_{feld_id}').scrollIntoView({{block:'center'}})")
    await asyncio.sleep(0.2)
    r = await tab.js(f"(()=>{{const r=document.getElementById('pad_{feld_id}').getBoundingClientRect();return [r.left,r.top,r.width,r.height]}})()")
    x0, y0 = r[0] + 20, r[1] + r[3] / 2
    await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
    for i in range(1, 12):
        await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + i * 15, y=y0 + (12 if i % 2 else -12), button="left", buttons=1)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x0 + 180, y=y0, button="left", buttons=0, clickCount=1)
    await tab.js(f"document.getElementById('padName_{feld_id}').value={name!r}")
    await tab.js(f"document.querySelector('#q_{feld_id} .pad-actions .btn:not(.secondary)').click()")


async def pruefen(tab, seed, p):
    import asyncio

    cid, f = seed["checklist"], seed["fields"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    api = f"/api/checklists/{cid}"
    bereit = "document.querySelector('#clMain .q')"

    # --- Monteurin: tippen, sofort unterschreiben -----------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js(f"(()=>{{const el=document.querySelector('#q_{f['bem']} input');el.value='Dachrand gesichert';el.dispatchEvent(new Event('input'))}})()")
    await _unterschreiben(tab, f["sig"], "Mia Monteurin")
    await tab.warten("document.getElementById('lockCard')", 10)
    antworten = await tab.js(f"fetch('{api}').then(r=>r.json()).then(d=>d.answers['{f['bem']}']?.value)")
    p.pruefe("Bemerkung vor der Unterschrift gespeichert", antworten, "Dachrand gesichert")
    confirms = await tab.js("window.__confirms")
    p.pruefe("Hinweis vor erster Unterschrift: Sperre + offene Angabe",
             bool(confirms) and "gesperrt" in confirms[-1] and "Freigegeben" in confirms[-1], True)
    p.pruefe("Karte 'Unterschrieben' nennt fehlende Pflichtangabe",
             await tab.js("document.querySelector('#lockCard .warn')?.textContent.includes('Freigegeben')"), True)
    p.pruefe("Ja/Nein gesperrt", await tab.js(f"[...document.querySelectorAll('#q_{f['frei']} .tile')].every(b=>b.disabled)"), True)
    p.pruefe("Bemerkung nur noch Anzeige", await tab.js(f"!document.querySelector('#q_{f['bem']} input') && document.querySelector('#q_{f['bem']} .value-ro')?.textContent"),
             "Dachrand gesichert")
    meta = await tab.js(f"document.querySelector('#q_{f['sig']} .sig-meta')?.textContent||''")
    p.pruefe("Unterschrift zeigt Uhrzeit und Prüfsumme", "Uhr" in meta and "Prüfsumme" in meta, True)
    p.pruefe("Monteur-Unterschrift: keine zweite Zeichenfläche", await tab.js(f"!document.getElementById('pad_{f['sig']}')"), True)
    p.pruefe("Kunden-Unterschrift weiter möglich", await tab.js(f"!!document.getElementById('pad_{f['kunde']}')"), True)
    p.pruefe("Kein 'Entwurf löschen', 'Abschließen' da", await tab.js(
        "[...document.querySelectorAll('.footer-card .btn')].map(b=>b.textContent.trim())"), ["Abschließen"])
    p.pruefe("Monteurin: kein Verwerfen-Feld", await tab.js("!document.getElementById('discardReason')"), True)
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_unterschrieben")

    # --- Büro: verwerfen --------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('discardBtn')")
    await tab.js("document.getElementById('discardBtn').click()")
    await asyncio.sleep(0.4)
    p.pruefe("Verwerfen ohne Begründung: Meldung", await tab.js("document.getElementById('discardStatus').textContent"),
             "Bitte eine Begründung eintragen.")
    p.pruefe("Verwerfen ohne Begründung: weiter unterschrieben", await tab.js(f"fetch('{api}').then(r=>r.json()).then(d=>d.signed)"), True)
    await tab.js("document.getElementById('discardReason').value='Freigabe fehlt, bitte nachtragen'")
    await tab.js("document.getElementById('discardBtn').click()")
    await tab.warten("!document.getElementById('lockCard')", 10)
    p.pruefe("Nach Verwerfen: offen", await tab.js(f"!!document.querySelector('#q_{f['bem']} input')"), True)
    p.pruefe("Verworfene Unterschrift mit Begründung", await tab.js(
        "[...document.querySelectorAll('.discarded-row')].map(r=>r.textContent.includes('Freigabe fehlt, bitte nachtragen')&&r.textContent.includes('Mia Monteurin'))"), [True])
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])
    await tab.bild("buero_verworfen")

    # --- Monteurin: ergänzen, neu unterschreiben, abschließen -------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js(f"document.querySelector('#q_{f['frei']} .tile').click()")
    await tab.warten(f"document.querySelector('#q_{f['frei']} .tile.on')", 10)
    await _unterschreiben(tab, f["sig"], "Mia Monteurin")
    await tab.warten("document.getElementById('lockCard')", 10)
    p.pruefe("Neu unterschrieben, keine offene Angabe", await tab.js("!document.querySelector('#lockCard .warn')"), True)
    await tab.js("document.getElementById('completeBtn').click()")
    await tab.warten("document.querySelector('.badge.done')", 10)
    p.pruefe("Abgeschlossen, PDF-Knopf da", await tab.js("!!document.getElementById('pdfLink')"), True)
    p.pruefe("Monteurin (2): JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_abgeschlossen")

    # --- Büro: Gerät als repariert markieren ------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/betriebsmittel/{seed['asset']}", "document.getElementById('releaseBtn')")
    await tab.js("document.getElementById('releaseBtn').click()")
    await asyncio.sleep(0.4)
    p.pruefe("Repariert ohne Notiz: Meldung", await tab.js("document.getElementById('releaseStatus').textContent"),
             "Bitte eintragen, was repariert wurde.")
    p.pruefe("Repariert ohne Notiz: roter Hinweis bleibt", await tab.js("document.getElementById('readinessBanner').className"), "readiness-banner")
    await tab.js("document.getElementById('releaseNote').value='Kabel getauscht'")
    await tab.js("document.getElementById('releaseBtn').click()")
    await tab.warten("document.getElementById('readinessBanner').className==='readiness-info'", 10)
    p.pruefe("Repariert mit Notiz", await tab.js("document.getElementById('readinessBanner').textContent.includes('Kabel getauscht')"), True)
    p.pruefe("Geräteseite: JS-Fehler", tab.fehler, [])
    await tab.bild("geraet_repariert")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
