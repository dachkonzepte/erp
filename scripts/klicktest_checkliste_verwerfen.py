"""Klicktest: Verwerfen je Unterschrift und Abschluss mit Prüfsumme (1.8.15, Stufe 2 Runde 2a-1c).

Vorlage wie ein Erlaubnisschein: Abschnitt 1 (Freigabe, Arbeitsbereich) → Unterschrift
Ausführender, Abschnitt 2 (Ende, Nachkontrolle ohne Befund) → Unterschrift Brandwache. Beide
Abschnitte sind ausgefüllt und unterschrieben (Mia, Karl).

    Büro       (Desktop) wählt im Verwerfen-Feld die Unterschriften nacheinander: bei der des
               Ausführenden nennt die Seite die Brandwache als "mit verworfen", bei der Brandwache
               "nur diese". Verwirft die Brandwache mit Begründung: Nachkontrolle offen, Freigabe
               weiter gesperrt, die verworfene steht unten mit Begründung.
    Monteurin  (Handybreite) ändert das Ende, die Brandwache unterschreibt neu, abschließen: oben
               "Abschluss: Inhalt unverändert" mit Prüfsumme.
    Datenbank  Name der Brandwache an der Sperre vorbei geändert (Wegwerf-SQLite dieses Laufs) --
               der Abschluss zeigt die Abweichung samt Feld, seit 1.8.57 auch die Unterschrift der Brandwache
               ("Unterzeichner", der Name steht in ihrem Siegel), die des Ausführenden nicht.
    Büro       sieht es im hellen und im dunklen Modus, PDF-Abruf.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben (Headless-Chrome
blockiert sonst). Unterschriften mit echten Mausereignissen.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_checkliste_verwerfen.py [--app-port N]
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

    from PIL import Image, ImageDraw

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

    def unterschrift_png() -> bytes:
        bild = Image.new("RGB", (400, 120), "white")
        ImageDraw.Draw(bild).line([(20, 90), (120, 30), (220, 95), (380, 40)], fill="black", width=4)
        puffer = BytesIO()
        bild.save(puffer, format="PNG")
        return puffer.getvalue()

    for key, wert in (("frei", "ja"), ("bereich", "Attika Nord")):
        save_answer(db, cl["id"], felder[key], wert, recorded_by_employee_id=ma["mia"].id)
    add_attachment(db, cl["id"], felder["sig1"], unterschrift_png(), signer_name="Mia Monteurin", created_by_employee_id=ma["mia"].id)
    for key, wert in (("ende", "16:30"), ("befund", "ja")):
        save_answer(db, cl["id"], felder[key], wert, recorded_by_employee_id=ma["mia"].id)
    add_attachment(db, cl["id"], felder["sig2"], unterschrift_png(), signer_name="Karl Kollege", created_by_employee_id=ma["mia"].id)

    return {"checklist": cl["id"], "fields": felder, "db_url": os.environ["DATABASE_URL"],
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


def _name_direkt_aendern(db_url: str, checklist_id: int, alt: str, neu: str) -> int:
    """An der Sperre vorbei, direkt in der Wegwerf-SQLite dieses Laufs (nie die echte, Regel 16:
    cdp_klicktest.py setzt DATABASE_URL auf den markierten Arbeitsordner)."""
    import sqlite3

    pfad = db_url.removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute("update checklist_attachments set signer_name=? where checklist_id=? and signer_name=? "
                         "and discarded_at is null", (neu, checklist_id, alt)).rowcount


async def pruefen(tab, seed, p):
    import asyncio

    cid, f = seed["checklist"], seed["fields"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    api = f"/api/checklists/{cid}"
    bereit = "document.querySelector('#clMain .q')"
    seal = lambda key: f"document.querySelector('#q_{f[key]} .seal')?.dataset.seal"  # noqa: E731
    waehle = lambda text: f"(()=>{{const s=document.getElementById('discardSig');s.selectedIndex=[...s.options].findIndex(o=>o.textContent.startsWith('{text}'));s.dispatchEvent(new Event('change'))}})()"  # noqa: E731
    mit = "document.getElementById('discardWith').textContent"

    # --- Büro: Unterschrift wählen, Brandwache verwerfen -----------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('discardSig')")
    p.pruefe("Auswahl: beide Unterschriften in Vorlagenreihenfolge", await tab.js(
        "[...document.getElementById('discardSig').options].slice(1).map(o=>o.textContent.split(' (')[0])"),
        ["Unterschrift Ausführender: Mia Monteurin", "Unterschrift Brandwache: Karl Kollege"])
    await tab.js(waehle("Unterschrift Ausführender"))
    p.pruefe("Ausführender gewählt: Brandwache fällt mit", await tab.js(
        f"{mit}.startsWith('Mit verworfen werden (Felder darunter): Unterschrift Brandwache: Karl Kollege (') && !{mit}.includes('Mia')"), True)
    await tab.js(waehle("Unterschrift Brandwache"))
    p.pruefe("Brandwache gewählt: nur diese", await tab.js(mit), "Nur diese Unterschrift.")
    await tab.js("document.getElementById('discardReason').value='Nachkontrolle zu früh beendet'")
    await tab.js("document.getElementById('discardBtn').click()")
    await tab.warten("document.querySelector('.discarded-row')", 10)
    confirms = await tab.js("window.__confirms")
    p.pruefe("Rückfrage nennt die Unterschrift und 'nur diese'",
             bool(confirms) and "Unterschrift Brandwache: Karl Kollege" in confirms[-1] and "Nur diese Unterschrift." in confirms[-1], True)
    p.pruefe("Nachkontrolle wieder offen", await tab.js(
        f"!!document.querySelector('#q_{f['ende']} input') && [...document.querySelectorAll('#q_{f['befund']} .tile')].every(b=>!b.disabled)"), True)
    p.pruefe("Freigabe weiter gesperrt", await tab.js(
        f"[[...document.querySelectorAll('#q_{f['frei']} .tile')].every(b=>b.disabled), document.querySelector('#q_{f['bereich']} .value-ro')?.textContent]"),
        [True, "Attika Nord"])
    p.pruefe("Ausführender weiter gültig und unverändert", await tab.js(seal("sig1")), "unveraendert")
    p.pruefe("Brandwache: Zeichenfeld statt Unterschrift", await tab.js(f"!!document.getElementById('pad_{f['sig2']}')"), True)
    p.pruefe("Verworfene mit Begründung", await tab.js(
        "[...document.querySelectorAll('.discarded-row')].map(r=>r.textContent.includes('Karl Kollege')&&r.textContent.includes('Nachkontrolle zu früh beendet'))"), [True])
    p.pruefe("Auswahl danach: nur noch Ausführender", await tab.js("document.getElementById('discardSig').options.length"), 2)
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])
    await tab.bild("buero_brandwache_verworfen")

    # --- Monteurin: korrigieren, Brandwache neu, abschließen ---------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js(f"(()=>{{const el=document.querySelector('#q_{f['ende']} input');el.value='17:15';el.dispatchEvent(new Event('input'));el.dispatchEvent(new Event('blur'))}})()")
    await asyncio.sleep(0.5)
    p.pruefe("Ende gespeichert", await tab.js(f"fetch('{api}').then(r=>r.json()).then(d=>d.answers['{f['ende']}']?.value)"), "17:15")
    await _unterschreiben(tab, f["sig2"], "Karl Kollege")
    await tab.warten(f"document.querySelector('#q_{f['sig2']} .seal')", 10)
    p.pruefe("Kein Abschluss-Hinweis im Entwurf", await tab.js("!document.getElementById('completionSeal')"), True)
    await tab.js("document.getElementById('completeBtn').click()")
    await tab.warten("document.querySelector('.badge.done')", 10)
    p.pruefe("Abschluss: Inhalt unverändert", await tab.js(
        "[document.querySelector('#completionSeal .seal')?.dataset.seal, document.getElementById('completionSeal').textContent.trim().split(' · ')[0]]"),
        ["unveraendert", "Abschluss: ✓ Inhalt unverändert – passt zur Prüfsumme."])
    p.pruefe("Abschluss: Prüfsumme gekürzt, voll im Titel", await tab.js(
        f"fetch('{api}').then(r=>r.json()).then(d=>{{const m=document.querySelector('#completionSeal .sig-meta');return m.title.endsWith(d.completion_sha256)&&m.textContent.includes(d.completion_sha256.slice(0,12))}})"), True)
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_abgeschlossen")

    # --- An der Sperre vorbei: Name der Brandwache ------------------------------------------------
    p.pruefe("Datenbank direkt geändert (1 Zeile)", _name_direkt_aendern(seed["db_url"], cid, "Karl Kollege", "Mallory"), 1)
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('completionSeal')")
    p.pruefe("Abschluss zeigt die Abweichung samt Feld", await tab.js(
        "[document.querySelector('#completionSeal .seal').dataset.seal, document.querySelector('#completionSeal .seal').textContent]"),
        ["abweichend", "Inhalt weicht von der Prüfsumme ab: Unterschrift Brandwache."])
    # Seit 1.8.57 steht der Unterzeichner im Siegel jeder Unterschrift -- die geänderte Brandwache sieht auch ihre eigene.
    p.pruefe("Ausführender unverändert, Brandwache weicht ab (Unterzeichner)", [await tab.js(seal("sig1")), await tab.js(seal("sig2")),
             await tab.js(f"document.querySelector('#q_{f['sig2']} .seal').textContent")],
             ["unveraendert", "abweichend", "Inhalt weicht von der Prüfsumme ab: Unterzeichner."])
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('completionSeal')")
    p.pruefe("Hellmodus: Abweichung in der Warnfarbe", await tab.js(
        "[document.documentElement.dataset.theme, getComputedStyle(document.querySelector('#completionSeal .seal')).color]"),
        ["light", "rgb(192, 54, 44)"])
    await tab.bild("buero_abschluss_abweichung_hell")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('completionSeal')")
    p.pruefe("Dunkelmodus: Abweichung in der Warnfarbe", await tab.js(
        "[document.documentElement.dataset.theme, getComputedStyle(document.querySelector('#completionSeal .seal')).color]"),
        ["dark", "rgb(242, 131, 122)"])
    await tab.bild("buero_abschluss_abweichung_dunkel")
    await tab.js("localStorage.removeItem('erp_theme')")
    p.pruefe("PDF", await tab.js(f"fetch('{api}/pdf').then(r=>[r.status,r.headers.get('content-type')])"), [200, "application/pdf"])
    p.pruefe("Büro (2): JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
