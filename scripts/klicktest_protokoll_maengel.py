"""Klicktest: Feld "Mängel" im Abnahmeprotokoll (1.8.60, Stufe 2c-2d, Punkt 1).

Befüllt: Gewerbekunde "Hallenbau GmbH", Objekt "Halle Nord" mit den Dachflächen Nord, Süd und Alt (archiviert), Auftrag aus
einem Angebot, die Monteurin Mia über die Arbeitsvorbereitung zugewiesen. Vorlage "Abnahmeprotokoll (Klicktest)" am Auftrag:
Befund (Pflicht) -> Mängel -> Unterschrift Auftraggeber (laut Auftrag) -> Notiz -> Unterschrift Auftragnehmer (Konto). Das
Feld "Mängel" gibt es nur als Systemfeld eines Zwecks; bis der Zweck "abnahme" mit 1.8.61 kommt, setzt `befuellen()` den
Feldtyp direkt in der Wegwerf-Datenbank. Büro hat die Checkliste angelegt, der Befund ist ausgefüllt.

    Büro (1400 px, dunkel)  "Noch kein Mangel erfasst", Dachflächen nur des Objekts ohne die archivierte; ohne Beschreibung
                            abgelehnt; Mangel mit Fläche, Ort, Frist, Foto und Beleg erfasst; zweiter Mangel vor der
                            Unterschrift verworfen -> "nicht im Protokoll"; dritter erfasst.
    Büro (412 px, hell)     Formular ohne waagrechten Scrollbalken.
    Auftragsseite           drei Mängel "Aus dem Abnahmeprotokoll – noch ohne Abnahme", als Aktion nur "Verwerfen …",
                            Aufgabe "entsteht mit der Abnahme aus dem Abnahmeprotokoll".
    Unterschrift            Auftraggeber mit Person unterschrieben -> Formular weg, Erfassen über die API 409; dritter Mangel
                            danach verworfen -> "bleibt im Protokoll", die Unterschrift bleibt "Inhalt unverändert".
    Monteurin (412 px)      "Mängel erfasst das Büro.", Liste über die API 403, keine JS-Fehler.

`confirm()` wird automatisch bestätigt und mitgeschrieben. Unterschrift mit echten Mausereignissen. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_protokoll_maengel.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402
from klicktest_maengel import PDF, _bild, _datei_setzen  # noqa: E402
from klicktest_unterzeichner import _knopf, _zeichnen  # noqa: E402


def befuellen(db, k):
    import os
    from datetime import timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.berlin_time import berlin_today
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist, save_answer
    from app.models import (AppUser, ChecklistTemplateField, Customer, Employee, Project, Property, Quote, QuoteItem,
                            RoofArea, WorkPreparationEmployee)
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach, gruppe in (("mia", "E-1", "Mia", "Monteurin", "gewerblich"),
                                              ("olga", "E-2", "Olga", "Office", "angestellt"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id,
                         password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id,
                       password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    flaechen = {"nord": RoofArea(property_id=objekt.id, name="Nord"), "sued": RoofArea(property_id=objekt.id, name="Süd"),
                "alt": RoofArea(property_id=objekt.id, name="Alt", archived=True)}
    db.add_all(flaechen.values()); db.flush()
    projekt = Project(project_number="P-KT-PM", name="Dachsanierung Halle", customer_id=kunde.id, property_id=objekt.id,
                      status="angebot", pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-PM", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"),
                     unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=60), execution_start=None,
                                      execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                      payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    # field_readable: die Monteurin darf die Checkliste des Büros lesen -- sonst sähe sie den Hinweis im Feld nie
    t = create_template(db, label="Abnahmeprotokoll (Klicktest)", contexts=["auftrag"], field_readable=True)
    v = t["draft_version_id"]
    for spec in (
        {"field_type": "text", "label": "Befund", "field_key": "befund", "required": True},
        {"field_type": "text", "label": "Mängel", "field_key": "maengel"},
        {"field_type": "unterschrift", "label": "Unterschrift Auftraggeber", "field_key": "ag", "signer_mode": "auftraggeber"},
        {"field_type": "text", "label": "Notiz", "field_key": "notiz"},
        {"field_type": "unterschrift", "label": "Unterschrift Auftragnehmer", "field_key": "an", "signer_mode": "konto"},
    ):
        add_field(db, v, spec)
    # Nur Systemfeld eines Zwecks (1.8.61: Zweck "abnahme") -- hier direkt in der Wegwerf-Datenbank gesetzt.
    feld = db.scalar(select(ChecklistTemplateField).where(ChecklistTemplateField.version_id == v,
                                                          ChecklistTemplateField.field_key == "maengel"))
    feld.field_type = "maengel"
    db.commit()
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=ma["olga"].id, created_by_user_id=benutzer["buero"].id)
    felder = {f["field_key"]: f["id"] for f in cl["fields"]}
    save_answer(db, cl["id"], felder["befund"], "Dach dicht, Attika nachzuarbeiten", recorded_by_employee_id=ma["olga"].id)

    ordner = Path(os.environ["ERP_DATA_DIR"]) / "klicktest-uploads"
    ordner.mkdir(parents=True, exist_ok=True)
    dateien = {"pdf": ordner / "Ruege.pdf", "jpg": ordner / "Attika.jpg"}
    dateien["pdf"].write_bytes(PDF)
    dateien["jpg"].write_bytes(_bild("JPEG"))
    frist = heute + timedelta(days=14)
    return {"checklist": cl["id"], "fields": felder, "auftrag": auftrag.id,
            "frist": frist.isoformat(), "frist_text": frist.strftime("%d.%m.%Y"),
            "dateien": {n: str(p) for n, p in dateien.items()},
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def pruefen(tab, seed, p):
    cid, f, m = seed["checklist"], seed["fields"], seed["fields"]["maengel"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    liste = f"document.getElementById('pdefList_{m}')"
    bereit = f"document.querySelector('#clMain .q') && {liste} && !{liste}.textContent.includes('Lädt')"
    eintraege = f"[...{liste}.querySelectorAll('.pdef')]"
    status = f"document.getElementById('st_{m}').textContent"
    api_liste = f"fetch('/api/checklists/{cid}/defects').then(r=>r.json())"

    async def erfassen(beschreibung: str, n: int) -> None:
        await tab.js(f"document.getElementById('pdefDesc_{m}').value={beschreibung!r}")
        await tab.js(f"document.getElementById('pdefSave_{m}').click()")
        await tab.warten(f"{eintraege}.length==={n}", 15)

    async def verwerfen(defect_id: int, grund: str) -> None:
        await tab.js(f"document.getElementById('pdefReason_{defect_id}').value={grund!r};"
                     f"document.querySelector('.pdef[data-defect=\"{defect_id}\"] button').click()")
        await tab.warten(f"!!document.querySelector('.pdef[data-defect=\"{defect_id}\"] [data-verworfen]')", 15)

    # --- Büro: erfassen -----------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(f"document.getElementById('pdefArea_{m}').options.length>1", 10)
    p.pruefe("Leer, Dachflächen nur des Objekts ohne archivierte", await tab.js(
        f"[{liste}.innerText.trim(), [...document.getElementById('pdefArea_{m}').options].map(o=>o.textContent)]"),
        ["Noch kein Mangel erfasst.", ["— keine Dachfläche —", "Nord", "Süd"]])
    await tab.js(f"document.getElementById('pdefSave_{m}').click()")
    p.pruefe("Ohne Beschreibung abgelehnt", await tab.js(status), "Bitte den Mangel beschreiben.")

    await tab.js(f"(s=>{{s.selectedIndex=1}})(document.getElementById('pdefArea_{m}'));"
                 f"document.getElementById('pdefLoc_{m}').value='Attika West';"
                 f"document.getElementById('pdefDue_{m}').value='{seed['frist']}'")
    await _datei_setzen(tab, f"#pdefPhotos_{m}", seed["dateien"]["jpg"])
    await _datei_setzen(tab, f"#pdefReceipts_{m}", seed["dateien"]["pdf"])
    await erfassen("Attika undicht", 1)
    erster = await tab.js(f"Number({eintraege}[0].dataset.defect)")
    p.pruefe("Erster Mangel: Kopf, Frist, zwei Dateien, Formular geleert", await tab.js(
        f"[{eintraege}[0].querySelector('.pdef-head').textContent, {eintraege}[0].innerText.includes('Beseitigungsfrist: {seed['frist_text']}'), "
        f"[...{eintraege}[0].querySelectorAll('a[href*=\"/files/\"]')].map(a=>a.textContent), "
        f"document.getElementById('pdefDesc_{m}').value, document.getElementById('pdefArea_{m}').value, {status}]"),
        [f"Mangel Nr. {erster} · Nord · Attika West", True, ["Foto", "Beleg"], "", "", "Mangel erfasst"])
    p.pruefe("Foto über den Link abrufbar", await tab.js(
        f"fetch({eintraege}[0].querySelector('a[href*=\"/files/\"]').href).then(r=>[r.status, r.headers.get('content-type')])"),
        [200, "image/jpeg"])
    await erfassen("Doppelt erfasst", 2)
    zweiter = await tab.js(f"Number({eintraege}[1].dataset.defect)")
    await verwerfen(zweiter, "doppelt")
    p.pruefe("Vor der Unterschrift verworfen: nicht im Protokoll", await tab.js(
        f"document.querySelector('.pdef[data-defect=\"{zweiter}\"] [data-verworfen]').textContent"),
        "Verworfen (doppelt) – nicht im Protokoll")
    await erfassen("Rinne verbeult", 3)
    dritter = await tab.js(f"Number({eintraege}[2].dataset.defect)")
    p.pruefe("Büro: keine JS-Fehler beim Erfassen", tab.fehler, [])

    # --- Büro 412 px hell -------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js(f"document.getElementById('q_{m}').scrollIntoView()")
    await tab.bild("1_buero_maengel_412_hell")

    # --- Auftragsseite ------------------------------------------------------------------------------------------
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "!document.getElementById('defectList').textContent.includes('Lädt')")
    item = f"document.getElementById('mangel-{erster}')"
    p.pruefe("Auftragsseite: aus dem Protokoll, nur Verwerfen, Aufgabe erst mit der Abnahme", await tab.js(
        f"[document.querySelectorAll('#defectList .def-item').length, {item}.querySelector('[data-protokoll]').textContent, "
        f"{item}.querySelector('[data-protokoll] a').getAttribute('href'), "
        f"[...{item}.querySelectorAll('.def-actions button')].map(b=>b.textContent), "
        f"{item}.innerText.includes('entsteht mit der Abnahme aus dem Abnahmeprotokoll')]"),
        [3, "Aus dem Abnahmeprotokoll – noch ohne Abnahme: Haltung, Freigabe und Status erst danach", f"/checklisten/{cid}",
         ["Verwerfen …"], True])
    await tab.js(f"{item}.scrollIntoView()")
    await tab.bild("2_auftrag_maengel_aus_protokoll")

    # --- Unterschrift des Auftraggebers ------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js(f"document.getElementById('padPerson_{f['ag']}').value='Herbert Halle'")
    await _zeichnen(tab, f["ag"])
    await tab.js(_knopf(f["ag"]))
    await tab.warten(f"document.querySelectorAll('#q_{f['ag']} .sig').length===1", 15)
    await tab.warten(f"{liste} && !{liste}.textContent.includes('Lädt') && {eintraege}.length===3", 10)
    p.pruefe("Nach der Unterschrift: kein Formular mehr, drei Einträge", await tab.js(
        f"[!document.getElementById('pdefForm_{m}'), {eintraege}.length]"), [True, 3])
    p.pruefe("Erfassen über die API abgelehnt (409)", await tab.js(
        f"(()=>{{const fd=new FormData();fd.append('data',JSON.stringify({{description:'nachgeschoben'}}));"
        f"return fetch('/api/checklists/{cid}/defects',{{method:'POST',body:fd}}).then(async r=>[r.status,(await r.json()).detail])}})()"),
        [409, "Das Protokoll ist unterschrieben – an diesem Protokoll entstehen keine neuen Mängel mehr."])
    await verwerfen(dritter, "Kunde zieht zurück")
    p.pruefe("Nach der Unterschrift verworfen: bleibt im Protokoll", await tab.js(
        f"document.querySelector('.pdef[data-defect=\"{dritter}\"] [data-verworfen]').textContent"),
        "Verworfen (Kunde zieht zurück) – bleibt im Protokoll (erst nach der Unterschrift verworfen)")
    p.pruefe("Liste: im Protokoll je Mangel", sorted((d["id"], d["in_protocol"], d["discarded"]) for d in await tab.js(api_liste)),
             [(erster, True, False), (zweiter, False, True), (dritter, True, True)])
    p.pruefe("Unterschrift bleibt unverändert", await tab.js(
        f"fetch('/api/checklists/{cid}').then(r=>r.json()).then(d=>d.attachments.filter(a=>a.kind==='unterschrift').map(a=>a.seal.status))"),
        ["unveraendert"])
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])
    await tab.js(f"document.getElementById('q_{m}').scrollIntoView()")
    await tab.bild("3_buero_nach_unterschrift_dunkel")

    # --- Monteurin ----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", "document.querySelector('#clMain .q')")
    p.pruefe("Monteurin: Hinweis statt Liste, API 403", [
        await tab.js(f"document.querySelector('#q_{m} .q-body').innerText.trim()"),
        await tab.js(f"!!document.getElementById('pdefList_{m}')"),
        await tab.js(f"fetch('/api/checklists/{cid}/defects').then(r=>r.status)")],
        ["Mängel erfasst das Büro.", False, 403])
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])
    await tab.bild("4_monteurin_412")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
