"""Klicktest: Feldtyp "Beleg" und Hinweis "Offene Bedenken" auf weiteren Seiten (1.8.45, Bedenkenanzeige abrunden).

Die Instanz entsteht per create_all() ohne Alembic -- die Startvorlage kommt im Befüllen über die Funktionen der
Migrationen 0816ece7159b und 2798ba2fb235, veröffentlicht wie vom Büro. Am Auftrag zwei offene Bedenkenanzeigen:
eine der Monteurin (leer), eine des Büros (Meldung und Anzeige unterschrieben, Vorlage nicht für Monteure lesbar).

    Monteurin (412 px, hell)    Einsatzbericht-Seite: Hinweis oben mit beiden Anzeigen -- die eigene mit Link, die des
                                Büros ohne (sie darf sie nicht öffnen); kein waagrechter Scrollbalken.
    Monteurin (412 px, dunkel)  Checklisten-Seite des Auftrags: derselbe Hinweis, lesbar.
    Büro (1400 px, dunkel)      Einsatzbericht- und Checklisten-Seite: Hinweis mit zwei Links; Anzeige des Büros:
                                "Antwort als Beleg" nimmt PDF oder Foto (accept), eine SVG wird mit Meldung abgelehnt,
                                ein PDF erscheint als Kachel "PDF" (Datei als application/pdf), ein Foto als Vorschau;
                                Entscheidung unterschreiben -- Belege ohne ×; Hinweis nennt nur noch eine Anzeige.
    Büro (1400 px, hell)        Vorlagen-Editor: "Antwort als Beleg" mit Typ "Beleg (PDF oder Foto)", kein Hinweis
                                auf abweichende Systemfelder.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_beleg_und_hinweis.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_behinderungsanzeige import _feld_ids, _migration  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402

K = "bedenkenanzeige."
HINWEIS = "Offene Bedenken – vor Ausführung der betroffenen Leistung Entscheidung des Auftraggebers abwarten oder mit dem Büro klären."
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>'


def _bild(fmt: str, farbe=(30, 110, 160), groesse=(320, 200)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, format=fmt)
    return buf.getvalue()


def befuellen(db, k):
    import os
    from decimal import Decimal

    from sqlalchemy import select

    from app.berlin_time import berlin_today
    from app.checklist_templates import publish_draft
    from app.checklists import add_attachment, create_checklist, save_answer
    from app.models import (
        AppUser, ChecklistTemplate, Customer, Employee, Order, PlanningSlot, Project, Property, Team,
        WorkPreparationEmployee, WorkPreparationTeamAssignment,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("olga", "E-2", "Olga", "Office"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle Nord",
                    property_address="Weg 1\n12345 Stadt", caseworker_employee_id=ma["olga"].id)
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id))
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    zuweisung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuweisung); db.flush()
    db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuweisung.id, start_date=berlin_today(),
                        end_date=berlin_today()))
    db.commit()

    _migration("bedenkenanzeige_startvorlage").insert_concern_template(db.connection())
    _migration("bedenkenanzeige_antwort_als_beleg").answer_as_beleg(db.connection())
    db.commit()
    vorlage = db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Bedenkenanzeige"))
    publish_draft(db, vorlage)

    eigene = create_checklist(db, template_id=vorlage, context_type="auftrag", order_id=auftrag.id,
                              created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    buero = create_checklist(db, template_id=vorlage, context_type="auftrag", order_id=auftrag.id,
                             created_by_employee_id=ma["olga"].id, created_by_user_id=benutzer["buero"].id)
    f = {x["field_key"]: x["id"] for x in buero["fields"]}
    for key, wert in ((K + "bekannt_seit", "2026-10-02T07:45"), (K + "beschreibung", "Gelieferte Dämmplatten sind nass.")):
        save_answer(db, buero["id"], f[key], wert, recorded_by_employee_id=ma["olga"].id)
    # Seit 1.8.56 prüft die gemeinsame Bildprüfung "nicht leer" -- ein weißes Bild wäre abgelehnt (app/signature_image.py).
    add_attachment(db, buero["id"], f[K + "unterschrift_meldung"], _bild("PNG", (40, 40, 40), (300, 100)),
                   signer_name="Olga Office", created_by_employee_id=ma["olga"].id)
    for key, wert in ((K + "bedenken_gegen", ["stoffe_bauteile"]), (K + "begruendung", "Durchfeuchtete Dämmung."),
                      (K + "moegliche_folgen", "Tauwasser, Schimmel."), (K + "entscheidung_bis", "2026-10-09")):
        save_answer(db, buero["id"], f[key], wert, recorded_by_employee_id=ma["olga"].id)
    add_attachment(db, buero["id"], f[K + "unterschrift_buero"], _bild("PNG", (40, 40, 40), (300, 100)),
                   signer_name="Olga Office", created_by_employee_id=ma["olga"].id)

    ordner = Path(os.environ["ERP_DATA_DIR"]) / "klicktest-uploads"  # im Wegwerf-Ordner der Instanz
    ordner.mkdir(parents=True, exist_ok=True)
    dateien = {"pdf": ordner / "Antwort.pdf", "svg": ordner / "Antwort.svg", "jpg": ordner / "Antwort.jpg"}
    dateien["pdf"].write_bytes(PDF)
    dateien["svg"].write_bytes(SVG)
    dateien["jpg"].write_bytes(_bild("JPEG"))
    return {"auftrag": auftrag.id, "vorlage": vorlage, "eigene": eigene["id"], "buero": buero["id"],
            "dateien": {k: str(v) for k, v in dateien.items()},
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


async def _thema(tab, pfad: str, bereit: str, theme: str, p, wer: str) -> None:
    await tab.oeffnen(pfad, bereit)
    await tab.js(f"localStorage.setItem('erp_theme','{theme}')")
    await tab.oeffnen(pfad, bereit)
    p.pruefe(f"{wer}: {theme}", await tab.js("document.documentElement.dataset.theme"), theme)


HINWEIS_DA = "document.getElementById('concernAlert') && !document.getElementById('concernAlert').hidden"
EINTRAEGE = ("[...document.querySelectorAll('#concernAlert .concern-item')].map(e=>[e.tagName,e.textContent,"
             "e.getAttribute('href')])")
LESBAR = ("(()=>{const s=getComputedStyle(document.getElementById('concernAlert'));"
          "return s.color!==s.backgroundColor&&s.borderTopColor===s.color})()")


async def pruefen(tab, seed, p):
    import asyncio

    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    auftrag, eigene, buero = seed["auftrag"], seed["eigene"], seed["buero"]
    eigener_eintrag = ["A", f"Bedenkenanzeige Nr. {eigene} →", f"/checklisten/{eigene}"]
    bueros_eintrag = f"Bedenkenanzeige Nr. {buero} – Entscheidung erbeten bis 9.10.2026"

    # --- Monteurin: Einsatzbericht-Seite (hell) und Checklisten-Seite des Auftrags (dunkel) -------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await _thema(tab, f"/orders/{auftrag}/service-reports", HINWEIS_DA, "light", p, "Monteurin Einsatzbericht")
    p.pruefe("Monteurin Einsatzbericht: Hinweistext", await tab.js(
        "document.getElementById('concernAlert').childNodes[0].textContent"), HINWEIS)
    p.pruefe("Monteurin Einsatzbericht: eigene Anzeige mit Link, die des Büros ohne", await tab.js(EINTRAEGE),
             [eigener_eintrag, ["SPAN", bueros_eintrag, None]])
    p.pruefe("Monteurin Einsatzbericht: Hinweis vor den Berichten", await tab.js(
        "!!(document.getElementById('concernAlert').compareDocumentPosition(document.getElementById('reportList'))"
        "&Node.DOCUMENT_POSITION_FOLLOWING)"), True)
    p.pruefe("Monteurin Einsatzbericht: deutlich (Rahmen in Warnfarbe, Text lesbar)", await tab.js(LESBAR), True)
    p.pruefe("Monteurin Einsatzbericht: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("1_monteurin_einsatzbericht_hell")
    await _thema(tab, f"/checklisten/auftrag/{auftrag}", HINWEIS_DA, "dark", p, "Monteurin Checklisten-Seite")
    p.pruefe("Monteurin Checklisten-Seite: dieselben Einträge", await tab.js(EINTRAEGE),
             [eigener_eintrag, ["SPAN", bueros_eintrag, None]])
    p.pruefe("Monteurin Checklisten-Seite: lesbar im Dunkelmodus", await tab.js(LESBAR), True)
    p.pruefe("Monteurin Checklisten-Seite: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("2_monteurin_checklisten_seite_dunkel")
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: Hinweis auf beiden Seiten, dann Beleg an der Anzeige des Büros -----------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await _thema(tab, f"/orders/{auftrag}/service-reports", HINWEIS_DA, "dark", p, "Büro Einsatzbericht")
    beide = [eigener_eintrag, ["A", bueros_eintrag + " →", f"/checklisten/{buero}"]]
    p.pruefe("Büro Einsatzbericht: beide Anzeigen mit Link", await tab.js(EINTRAEGE), beide)
    p.pruefe("Büro Einsatzbericht: lesbar im Dunkelmodus", await tab.js(LESBAR), True)
    await tab.bild("3_buero_einsatzbericht_dunkel")
    await tab.oeffnen(f"/checklisten/auftrag/{auftrag}", HINWEIS_DA)
    p.pruefe("Büro Checklisten-Seite: beide Anzeigen mit Link", await tab.js(EINTRAEGE), beide)

    await tab.oeffnen(f"/checklisten/{buero}", "document.querySelector('#clMain .q')")
    f = await _feld_ids(tab)
    q = f"#q_{f[K + 'antwort_beleg']}"
    p.pruefe("Büro: Belegfeld nimmt PDF und Fotos", await tab.js(
        f"document.querySelector('{q} input[type=file]').accept"), "application/pdf,image/jpeg,image/png,image/webp")
    await _datei_setzen(tab, f"{q} input[type=file]", seed["dateien"]["svg"])
    await tab.warten(f"document.getElementById('st_{f[K + 'antwort_beleg']}')?.textContent.includes('nicht gespeichert')")
    p.pruefe("Büro: SVG abgelehnt mit Meldung", await tab.js(
        f"[document.getElementById('st_{f[K + 'antwort_beleg']}').textContent, document.querySelectorAll('{q} .thumb').length]"),
        ["Beleg nicht gespeichert: Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF sein.", 0])
    await _datei_setzen(tab, f"{q} input[type=file]", seed["dateien"]["pdf"])
    await tab.warten(f"document.querySelectorAll('{q} .thumb').length===1")
    await _datei_setzen(tab, f"{q} input[type=file]", seed["dateien"]["jpg"])
    await tab.warten(f"document.querySelectorAll('{q} .thumb').length===2")
    p.pruefe("Büro: PDF als Kachel, Foto als Vorschau", await tab.js(
        f"[...document.querySelectorAll('{q} .thumb')].map(t=>[t.dataset.beleg,!!t.querySelector('.pdf-tile'),!!t.querySelector('img'),!!t.querySelector('button')])"),
        [["application/pdf", True, False, True], ["image/jpeg", False, True, True]])
    p.pruefe("Büro: PDF-Datei wird als PDF ausgeliefert", await tab.js(
        f"fetch(document.querySelector('{q} .pdf-tile').href).then(r=>[r.headers.get('content-type'),r.headers.get('x-content-type-options')])"),
        ["application/pdf", "nosniff"])
    await tab.js(f"document.querySelector('{q}').scrollIntoView({{block:'center'}})")
    await asyncio.sleep(0.2)
    await tab.bild("4_buero_belege_dunkel")
    tiles = f"#q_{f[K + 'entscheidung']} .tile"
    await tab.js(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==='Bedenken gefolgt').click()")
    await tab.warten(f"document.getElementById('st_{f[K + 'entscheidung']}')?.textContent==='Gespeichert'")
    await _unterschreiben(tab, f[K + "unterschrift_entscheidung"], "Olga Office")
    await tab.warten(f"document.querySelector('#q_{f[K + 'unterschrift_entscheidung']} .sig')")
    p.pruefe("Büro: nach der Unterschrift Belege gesperrt (kein ×, kein Hochladen)", await tab.js(
        f"[document.querySelectorAll('{q} .thumb button').length, !!document.querySelector('{q} input[type=file]'), "
        f"document.querySelector('#q_{f[K + 'unterschrift_entscheidung']} .seal').dataset.seal]"), [0, False, "unveraendert"])
    await tab.bild("5_buero_entscheidung_unterschrieben")
    await tab.oeffnen(f"/orders/{auftrag}/service-reports", HINWEIS_DA)
    await asyncio.sleep(0.3)
    p.pruefe("Büro Einsatzbericht: nur noch die Anzeige der Monteurin", await tab.js(EINTRAEGE), [eigener_eintrag])

    # --- Büro: Vorlagen-Editor, hell -----------------------------------------------------------------
    bereit = "document.querySelector('#fieldList .frow')"
    await _thema(tab, f"/checklisten/vorlagen/{seed['vorlage']}", bereit, "light", p, "Büro Editor")
    p.pruefe("Büro Editor: 'Antwort als Beleg' mit Typ Beleg, kein Systemfeld-Hinweis", await tab.js(
        "[[...document.querySelectorAll('#fieldList .frow')].find(r=>r.querySelector('.key').textContent==='bedenkenanzeige.antwort_beleg')"
        ".querySelector('.badge').textContent, !!document.getElementById('publishedSystemHint')]"),
        ["Beleg (PDF oder Foto)", False])
    await tab.bild("6_buero_editor_hell")
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Beleg und Hinweis Offene Bedenken (1.8.45)", uhr="10:00"))
