"""Klicktest: Unterzeichner je Unterschriftsfeld (1.8.57, Stufe 2c-2c, Punkt 3).

Befüllt: Gewerbekunde "Hallenbau GmbH", Projekt mit zwei Beteiligten -- Bernd Bau (Bauleitung des Auftraggebers, mit
Vollmacht zur Abnahme als PDF) und Petra Plan (Architekt/Planer, ohne). Vorlage "Abnahmeprotokoll (Klicktest)" am
Auftrag: Feststellung (Pflicht) -> Unterschrift Auftraggeber (Auftraggeber laut Auftrag) -> Unterschrift Beteiligte
(Beteiligter, mehrere) -> Unterschrift Betrieb (angemeldetes Konto) -> Bemerkung -> Unterschrift Zeuge (frei). Die
Monteurin hat die Checkliste angelegt, die Feststellung ist ausgefüllt.

    Monteurin (412 px, hell)  Auftraggeber und Konto ohne Namensfeld, der Name steht fest; Beteiligte als Auswahl mit
                              Hinweis ohne Vollmacht; ohne Wahl abgelehnt; Petra (ohne Vollmacht, gekennzeichnet) und
                              Bernd (Vollmacht festgehalten, für sie ohne Link) unterschreiben, danach keine Wahl mehr;
                              Auftraggeber und Konto unterschreiben; jede Unterschrift "Inhalt unverändert"; die
                              Vollmacht über die API 403; kein waagrechter Scrollbalken.
    Büro (1400 px, dunkel)    Link "Vollmacht zur Abnahme" an Bernds Unterschrift liefert das PDF (nosniff); Editor zeigt
                              "Unterzeichner" mit den vier Arten, gesperrt in der veröffentlichten Fassung.

`confirm()` wird automatisch bestätigt und mitgeschrieben. Unterschriften mit echten Mausereignissen. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_unterzeichner.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def befuellen(db, k):
    from decimal import Decimal

    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist, save_answer
    from app.contacts import create_contact
    from app.models import AppUser, Customer, Employee, Order, Project, WorkPreparationEmployee
    from app.project_participants import add_participant, store_power_of_attorney
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("karl", "E-2", "Karl", "Kollege"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id,
                       password_hash=k.passwort()),
        "buero": AppUser(username="buero", display_name="Karl Kollege", role="buero_auftrag", employee_id=ma["karl"].id,
                         password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-UZ", name="Halle Nord", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-UZ", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Halle Nord", customer_name="Hallenbau GmbH", property_name="Halle",
                    property_address="Werkstr. 5\n52531 Uebach")
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()
    bau = add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Bernd", "last_name": "Bau"}),
                          role="bauleitung_ag", acceptance_authorized=True)
    store_power_of_attorney(db, bau, filename="abnahmevollmacht.pdf", data=PDF, user_name="Karl Kollege", kind="abnahme")
    add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Petra", "last_name": "Plan"}),
                    role="architekt_planer")

    t = create_template(db, label="Abnahmeprotokoll (Klicktest)", contexts=["auftrag"])
    v = t["draft_version_id"]
    for spec in (
        {"field_type": "text", "label": "Feststellung", "field_key": "feststellung", "required": True},
        {"field_type": "unterschrift", "label": "Unterschrift Auftraggeber", "field_key": "ag", "signer_mode": "auftraggeber"},
        {"field_type": "unterschrift", "label": "Unterschrift Beteiligte", "field_key": "bet", "signer_mode": "beteiligter",
         "multiple": True, "max_count": 3},
        {"field_type": "unterschrift", "label": "Unterschrift Betrieb", "field_key": "betrieb", "signer_mode": "konto"},
        {"field_type": "text", "label": "Bemerkung", "field_key": "bem"},
        {"field_type": "unterschrift", "label": "Unterschrift Zeuge", "field_key": "zeuge"},
    ):
        add_field(db, v, spec)
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    felder = {f["field_key"]: f["id"] for f in cl["fields"]}
    save_answer(db, cl["id"], felder["feststellung"], "Abgenommen ohne Mängel", recorded_by_employee_id=ma["mia"].id)
    return {"checklist": cl["id"], "fields": felder, "template": vorlage["id"],
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _zeichnen(tab, feld_id: int) -> None:
    """Strich mit echten Mausereignissen auf die Zeichenfläche des Felds."""
    import asyncio

    await tab.js(f"document.getElementById('pad_{feld_id}').scrollIntoView({{block:'center'}})")
    await asyncio.sleep(0.2)
    r = await tab.js(f"(()=>{{const r=document.getElementById('pad_{feld_id}').getBoundingClientRect();return [r.left,r.top,r.width,r.height]}})()")
    x0, y0 = r[0] + 20, r[1] + r[3] / 2
    await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
    for i in range(1, 12):
        await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + i * 15, y=y0 + (12 if i % 2 else -12),
                      button="left", buttons=1)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x0 + 180, y=y0, button="left", buttons=0, clickCount=1)


def _knopf(feld_id: int) -> str:
    return f"document.querySelector('#q_{feld_id} .pad-actions .btn:not(.secondary)').click()"


async def pruefen(tab, seed, p):
    cid, f = seed["checklist"], seed["fields"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    bereit = "document.querySelector('#clMain .q')"
    sigs = "fetch('/api/checklists/%d').then(r=>r.json()).then(d=>d.attachments.filter(a=>a.kind==='unterschrift'))" % cid
    zeile = lambda key: f"[...document.querySelectorAll('#q_{f[key]} .sig')].map(s=>s.innerText.split('\\n').slice(0,2).join(' | '))"  # noqa: E731

    # --- Monteurin ------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Auftraggeber und Konto: Name fest, kein Namensfeld", await tab.js(
        f"[document.querySelector('[data-signer=\"{f['ag']}\"]')?.textContent, document.querySelector('[data-signer=\"{f['betrieb']}\"]')?.textContent, "
        f"!document.getElementById('padName_{f['ag']}'), !document.getElementById('padName_{f['betrieb']}'), !!document.getElementById('padName_{f['zeuge']}')]"),
        ["Unterschreibt: Hallenbau GmbH (Auftraggeber laut Auftrag)", "Unterschreibt: Mia Monteurin (angemeldetes Konto)",
         True, True, True])
    p.pruefe("Beteiligte: Auswahl ohne Vorauswahl", await tab.js(
        f"[...document.getElementById('padPart_{f['bet']}').options].map(o=>o.textContent)"),
        ["– Beteiligten wählen –", "Bernd Bau (Bauleitung des Auftraggebers)", "Petra Plan (Architekt/Planer) – ohne Vollmacht"])
    await _zeichnen(tab, f["bet"])
    await tab.js(_knopf(f["bet"]))
    await tab.warten(f"document.getElementById('st_{f['bet']}').classList.contains('err')", 10)
    p.pruefe("Ohne Wahl abgelehnt", await tab.js(f"document.getElementById('st_{f['bet']}').textContent"),
             "Bitte den Beteiligten wählen, der unterschreibt.")
    await tab.js(f"(s=>{{s.selectedIndex=2;s.dispatchEvent(new Event('change'))}})(document.getElementById('padPart_{f['bet']}'))")
    p.pruefe("Petra gewählt: Hinweis ohne Vollmacht", await tab.js(
        f"(h=>[h.hidden,h.textContent.includes('keine Vollmacht zur Abnahme')])(document.getElementById('padPoa_{f['bet']}'))"),
        [False, True])
    await tab.js(_knopf(f["bet"]))
    await tab.warten(f"document.querySelectorAll('#q_{f['bet']} .sig').length===1", 10)
    await _zeichnen(tab, f["bet"])
    await tab.js(f"(s=>{{s.selectedIndex=1;s.dispatchEvent(new Event('change'))}})(document.getElementById('padPart_{f['bet']}'))")
    p.pruefe("Bernd gewählt: kein Hinweis", await tab.js(f"document.getElementById('padPoa_{f['bet']}').hidden"), True)
    await tab.js(_knopf(f["bet"]))
    await tab.warten(f"document.querySelectorAll('#q_{f['bet']} .sig').length===2", 10)
    p.pruefe("Beteiligte: Art, Rolle, Vollmacht je Unterschrift (Monteurin ohne Link)", await tab.js(zeile("bet")), [
        "Petra Plan | Unterzeichner: Beteiligter des Projekts (Architekt/Planer) · ⚠ ohne Vollmacht zur Abnahme",
        "Bernd Bau | Unterzeichner: Beteiligter des Projekts (Bauleitung des Auftraggebers) · Vollmacht zur Abnahme festgehalten"])
    p.pruefe("Beteiligte: keiner mehr zur Wahl, kein Link für die Monteurin", await tab.js(
        f"[[...document.getElementById('padPart_{f['bet']}').options].length, document.querySelectorAll('#q_{f['bet']} a[href*=power-of-attorney]').length]"),
        [1, 0])
    for key in ("ag", "betrieb"):
        await _zeichnen(tab, f[key])
        await tab.js(_knopf(f[key]))
        await tab.warten(f"document.querySelectorAll('#q_{f[key]} .sig').length===1", 10)
    p.pruefe("Auftraggeber und Konto unterschrieben", [await tab.js(zeile("ag")), await tab.js(zeile("betrieb"))], [
        ["Hallenbau GmbH | Unterzeichner: Auftraggeber laut Auftrag"],
        ["Mia Monteurin | Unterzeichner: angemeldetes Konto"]])
    alle = await tab.js(sigs)
    p.pruefe("Vier Unterschriften, Siegelformat 3, jede unverändert",
             sorted((a["signer_kind"], a["seal_format"], a["seal"]["status"]) for a in alle or []),
             [("auftraggeber", 3, "unveraendert"), ("beteiligter", 3, "unveraendert"), ("beteiligter", 3, "unveraendert"),
              ("konto", 3, "unveraendert")])
    bernd = next((a["id"] for a in alle or [] if a["signer_name"] == "Bernd Bau"), 0)
    p.pruefe("Monteurin: Vollmacht über die API gesperrt", await tab.js(
        f"fetch('/api/checklist-attachments/{bernd}/power-of-attorney').then(r=>r.status)"), 403)
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])
    await tab.js(f"document.getElementById('q_{f['bet']}').scrollIntoView()")
    await tab.bild("1_monteurin_unterzeichner_412")

    # --- Büro ----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Büro dunkel: Link zur Vollmacht an Bernds Unterschrift", await tab.js(
        f"[document.documentElement.dataset.theme, document.querySelectorAll('#q_{f['bet']} a[href*=power-of-attorney]').length]"),
        ["dark", 1])
    p.pruefe("Vollmacht: das eingefrorene PDF, nosniff", await tab.js(
        f"fetch(document.querySelector('#q_{f['bet']} a[href*=power-of-attorney]').href).then(async r=>[r.status,r.headers.get('content-type'),r.headers.get('x-content-type-options'),(await r.text()).startsWith('%PDF')])"),
        [200, "application/pdf", "nosniff", True])
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])
    await tab.bild("2_buero_dunkel")
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['template']}", "document.querySelector('#fieldList .frow')")
    await tab.js(f"toggleField({f['ag']})")  # Details der Unterschrift Auftraggeber aufklappen
    p.pruefe("Editor: Unterzeichner mit vier Arten, gesperrt in der veröffentlichten Fassung", await tab.js(
        f"(s=>s&&[[...s.options].map(o=>o.value), s.value, s.disabled])(document.querySelector('#frow_{f['ag']} select[data-k=signer_mode]'))"),
        [["frei", "konto", "auftraggeber", "beteiligter"], "auftraggeber", True])
    p.pruefe("Editor: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Unterzeichner je Unterschriftsfeld (1.8.57)", uhr="10:00"))
