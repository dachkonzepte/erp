"""Klicktest: Unterschrift versiegelt abschnittsweise (1.8.14, Stufe 2 Runde 2a-1b).

Vorlage wie ein Erlaubnisschein: Abschnitt 1 (Freigabe, Arbeitsbereich, Fotos vorher) →
Unterschrift Ausführender, Abschnitt 2 (Ende, Nachkontrolle ohne Befund) → Unterschrift Brandwache.

    Monteurin  (Handybreite) tippt den Arbeitsbereich und unterschreibt sofort: der Hinweis nennt
               "oberhalb gesperrt, darunter offen"; danach Abschnitt 1 gesperrt und markiert,
               Abschnitt 2 weiter ausfüllbar, an der Unterschrift "Inhalt unverändert".
    Datenbank  Arbeitsbereich wird an der Sperre vorbei direkt geändert (Wegwerf-SQLite dieses
               Laufs) -- nach dem Neuladen zeigt die Unterschrift die Abweichung samt Feld.
    Büro       (Desktop) sieht die Abweichung, verwirft mit Begründung. Das Foto aus Abschnitt 1
               gehört zur verworfenen Unterschrift: kein Entfernen-Knopf.
    Monteurin  unterschreibt neu, die Brandwache unterschreibt, abschließen, PDF.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben (Headless-Chrome
blockiert sonst). Unterschriften mit echten Mausereignissen.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_checkliste_abschnitte.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402


def befuellen(db, k):
    import os
    from decimal import Decimal
    from io import BytesIO

    from PIL import Image

    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import add_attachment, create_checklist, save_answer
    from app.models import AppUser, Customer, Employee, Order, Project, WorkPreparationEmployee
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
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    t = create_template(db, label="Heißarbeiten", contexts=["auftrag"])
    v = t["draft_version_id"]
    for spec in (
        {"field_type": "ja_nein", "label": "Freigabe durch den Auftraggeber", "field_key": "frei", "required": True, "group_name": "Freigabe vor Arbeitsbeginn"},
        {"field_type": "text", "label": "Arbeitsbereich", "field_key": "bereich", "group_name": "Freigabe vor Arbeitsbeginn"},
        {"field_type": "foto", "label": "Fotos vorher", "field_key": "fotos_vorher", "max_count": 3, "group_name": "Freigabe vor Arbeitsbeginn"},
        {"field_type": "unterschrift", "label": "Unterschrift Ausführender", "field_key": "sig1", "signer_label": "Ausführender", "group_name": "Freigabe vor Arbeitsbeginn"},
        {"field_type": "text", "label": "Ende der Arbeiten", "field_key": "ende", "group_name": "Nachkontrolle"},
        {"field_type": "ja_nein", "label": "Nachkontrolle ohne Befund", "field_key": "befund", "required": True, "group_name": "Nachkontrolle"},
        {"field_type": "unterschrift", "label": "Unterschrift Brandwache", "field_key": "sig2", "signer_label": "Brandwache", "group_name": "Nachkontrolle"},
    ):
        add_field(db, v, spec)
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    felder = {f["field_key"]: f["id"] for f in cl["fields"]}
    save_answer(db, cl["id"], felder["frei"], "ja", recorded_by_employee_id=ma["mia"].id)
    bild = BytesIO()
    Image.new("RGB", (800, 600), (180, 90, 40)).save(bild, format="JPEG")
    add_attachment(db, cl["id"], felder["fotos_vorher"], bild.getvalue(), created_by_employee_id=ma["mia"].id)

    return {"checklist": cl["id"], "fields": felder, "db_url": os.environ["DATABASE_URL"],
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


def _antwort_direkt_aendern(db_url: str, checklist_id: int, field_key: str, wert: str) -> int:
    """An der Sperre vorbei, direkt in der Wegwerf-SQLite dieses Laufs (nie die echte, Regel 16:
    cdp_klicktest.py setzt DATABASE_URL auf den markierten Arbeitsordner)."""
    import sqlite3

    pfad = db_url.removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute("update checklist_answers set value_text=? where checklist_id=? and field_key=?",
                         (wert, checklist_id, field_key)).rowcount


async def pruefen(tab, seed, p):
    import asyncio

    cid, f = seed["checklist"], seed["fields"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    api = f"/api/checklists/{cid}"
    bereit = "document.querySelector('#clMain .q')"
    seal = lambda key: f"document.querySelector('#q_{f[key]} .seal')?.dataset.seal"  # noqa: E731
    seal_text = lambda key: f"document.querySelector('#q_{f[key]} .seal')?.textContent||''"  # noqa: E731

    # --- Monteurin: Abschnitt 1 unterschreiben --------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Vor der Unterschrift: Foto entfernbar", await tab.js(f"!!document.querySelector('#q_{f['fotos_vorher']} .thumb button')"), True)
    await tab.js(f"(()=>{{const el=document.querySelector('#q_{f['bereich']} input');el.value='Attika Nord';el.dispatchEvent(new Event('input'))}})()")
    await _unterschreiben(tab, f["sig1"], "Mia Monteurin")
    await tab.warten("document.getElementById('lockCard')", 10)
    p.pruefe("Arbeitsbereich vor der Unterschrift gespeichert",
             await tab.js(f"fetch('{api}').then(r=>r.json()).then(d=>d.answers['{f['bereich']}']?.value)"), "Attika Nord")
    confirms = await tab.js("window.__confirms")
    p.pruefe("Hinweis: oberhalb gesperrt, darunter offen",
             bool(confirms) and "oberhalb gesperrt" in confirms[-1] and "darunter bleiben" in confirms[-1], True)
    p.pruefe("Karte nennt den Abschnitt", await tab.js("document.querySelector('#lockCard .lock-title').textContent.includes('oberhalb')"), True)
    p.pruefe("Abschnitt 1: Ja/Nein gesperrt", await tab.js(f"[...document.querySelectorAll('#q_{f['frei']} .tile')].every(b=>b.disabled)"), True)
    p.pruefe("Abschnitt 1: Arbeitsbereich nur Anzeige", await tab.js(f"document.querySelector('#q_{f['bereich']} .value-ro')?.textContent"), "Attika Nord")
    p.pruefe("Abschnitt 1: Foto ohne Entfernen", await tab.js(f"!document.querySelector('#q_{f['fotos_vorher']} .thumb button')"), True)
    p.pruefe("Abschnitt 1: als gesperrt markiert", await tab.js(
        "[...document.querySelectorAll('.sealed-tag')].map(s=>s.closest('.q').id)"), [f"q_{f['frei']}", f"q_{f['bereich']}", f"q_{f['fotos_vorher']}"])
    p.pruefe("Abschnitt 2: offen", await tab.js(
        f"!!document.querySelector('#q_{f['ende']} input') && [...document.querySelectorAll('#q_{f['befund']} .tile')].every(b=>!b.disabled)"), True)
    p.pruefe("Unterschrift 1: Inhalt unverändert", [await tab.js(seal("sig1")), "unverändert" in await tab.js(seal_text("sig1"))], ["unveraendert", True])
    p.pruefe("Kein 'Entwurf löschen'", await tab.js("[...document.querySelectorAll('.footer-card .btn')].map(b=>b.textContent.trim())"), ["Abschließen"])

    await tab.js(f"(()=>{{const el=document.querySelector('#q_{f['ende']} input');el.value='16:30';el.dispatchEvent(new Event('input'));el.dispatchEvent(new Event('blur'))}})()")
    await tab.js(f"document.querySelector('#q_{f['befund']} .tile').click()")
    await tab.warten(f"document.querySelector('#q_{f['befund']} .tile.on')", 10)
    await asyncio.sleep(0.3)
    antworten = await tab.js(f"fetch('{api}').then(r=>r.json()).then(d=>[d.answers['{f['ende']}']?.value,d.answers['{f['befund']}']?.value])")
    p.pruefe("Abschnitt 2 nach der Unterschrift gespeichert", antworten, ["16:30", "ja"])
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_abschnitt1_unterschrieben")

    # --- An der Sperre vorbei geändert ------------------------------------------------------------
    p.pruefe("Datenbank direkt geändert (1 Zeile)", _antwort_direkt_aendern(seed["db_url"], cid, "bereich", "Attika Süd"), 1)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Unterschrift 1 zeigt die Abweichung", [await tab.js(seal("sig1")), await tab.js(seal_text("sig1"))],
             ["abweichend", "Inhalt weicht von der Prüfsumme ab: Arbeitsbereich."])
    await tab.bild("monteurin_abweichung")

    # --- Büro: sieht es, verwirft -----------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('discardBtn')")
    p.pruefe("Büro sieht die Abweichung", await tab.js(seal("sig1")), "abweichend")
    await tab.js("document.getElementById('discardReason').value='Arbeitsbereich wurde nachträglich geändert'")
    await tab.js("document.getElementById('discardBtn').click()")
    await tab.warten("!document.getElementById('lockCard')", 10)
    p.pruefe("Nach Verwerfen: Abschnitt 1 offen", await tab.js(f"!!document.querySelector('#q_{f['bereich']} input')"), True)
    p.pruefe("Foto der verworfenen Unterschrift: kein Entfernen, Upload möglich", await tab.js(
        f"[!document.querySelector('#q_{f['fotos_vorher']} .thumb button'), !!document.querySelector('#q_{f['fotos_vorher']} input[type=file]')]"), [True, True])
    p.pruefe("Kein 'Entwurf löschen' (verworfene Unterschrift bleibt)", await tab.js(
        "[...document.querySelectorAll('.footer-card .btn')].map(b=>b.textContent.trim())"), ["Abschließen"])
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])
    await tab.bild("buero_verworfen")

    # --- Monteurin: neu unterschreiben, Brandwache, abschließen -----------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await _unterschreiben(tab, f["sig1"], "Mia Monteurin")
    await tab.warten("document.getElementById('lockCard')", 10)
    p.pruefe("Neu unterschrieben: unverändert", await tab.js(seal("sig1")), "unveraendert")
    await _unterschreiben(tab, f["sig2"], "Karl Kollege")
    await tab.warten(f"document.querySelector('#q_{f['sig2']} .seal')", 10)
    p.pruefe("Hinweis vor 2. Unterschrift ohne 'darunter'", "darunter" not in (await tab.js("window.__confirms"))[-1], True)
    p.pruefe("Alles gesperrt, keine Markierung mehr nötig", await tab.js(
        f"[!document.querySelector('#q_{f['ende']} input'), document.querySelectorAll('.sealed-tag').length, document.querySelector('#lockCard .lock-title').textContent.includes('Antworten und Fotos')]"),
        [True, 0, True])
    await tab.js("document.getElementById('completeBtn').click()")
    await tab.warten("document.querySelector('.badge.done')", 10)
    p.pruefe("Abgeschlossen, beide Unterschriften unverändert, PDF-Knopf",
             [await tab.js(seal("sig1")), await tab.js(seal("sig2")), await tab.js("!!document.getElementById('pdfLink')")],
             ["unveraendert", "unveraendert", True])
    p.pruefe("Monteurin (2): JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_abgeschlossen")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
