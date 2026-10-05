"""Klicktest: Monteur-Sicht auf Mängel in /mobil (1.8.52, Stufe 2c-2b, Punkt 1; seit 1.8.54 Hinweis des Monteurs und
Aufgabe, die dem Status folgt).

Befüllt: Gewerbekunde (VOB/B), Objekt "Halle Nord" mit Dachfläche "Nord", Auftrag (Monteurin Mia über die
Arbeitsvorbereitung zugeordnet), Abnahme vor 20 Tagen mit Vorbehalt Mängel; Mängel: "Attika undicht" (Nord, Attika West,
Frist gestern, Foto und Beleg, freigegeben, Haltung bestritten), "Rinne lose" (nicht freigegeben), "Kehle offen"
(freigegeben und zurückgenommen); ein zweiter Auftrag ohne Mia mit einem freigegebenen Mangel "Fremder Mangel".

    Monteurin (412 px, dunkel)  /mobil: Abschnitt "Mängel zur Beseitigung" nur mit "Attika undicht" -- Beschreibung,
                                Dachfläche, Ort, Frist überschritten, Foto geladen; keine Haltung, keine Abnahme, kein
                                Beleg. "Beseitigt melden": Datum vorbelegt mit heute, ohne Foto abgelehnt, mit Foto und
                                Hinweis (seit 1.8.54, höchstens 500 Zeichen, "nur fürs Büro") gesendet -> Meldung,
                                Abschnitt leer; dieselbe Kennung noch einmal: dieselbe Antwort. Nicht freigegebener und
                                fremder Mangel: Foto und Meldung 404; Büro-Wege 403.
    Büro (1400 px, hell)        Auftrag: "beseitigt", Verlauf "gemeldet in der Monteursansicht" mit dem Foto, "Hinweis aus
                                der Monteursansicht", "Aufgabe „Beseitigung abnehmen lassen“ angelegt", Aufgabenzeile mit
                                Art und Link auf die Aufgabe; "Rinne lose" freigeben.
    Monteurin (412 px, hell)    "Rinne lose" erscheint; nach dem Zurücknehmen durch das Büro (API) verschwindet er. Das Büro
                                setzt "Attika undicht" zurück auf offen (API): er erscheint wieder, ohne den Hinweis; im
                                Büro steht die Aufgabe "Erneut beseitigen".

Feste Uhr 10:00 (cdp_klicktest.py, /mobil meldet ab 19 Uhr ab); die Daten liegen relativ zum heutigen Tag.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_maengel_monteur.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
HINWEIS = "Anschluss neu eingeklebt, Attika trocken"


def _bild(fmt: str, farbe=(30, 110, 160), groesse=(320, 200)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, format=fmt)
    return buf.getvalue()


def befuellen(db, k):
    import os
    from datetime import timedelta
    from decimal import Decimal

    from app.acceptances import create_acceptance
    from app.berlin_time import berlin_today
    from app.defects import create_defect, set_release, set_stance
    from app.models import (
        AppUser, Customer, Employee, Project, Property, Quote, QuoteItem, RoofArea, WorkPreparationEmployee,
    )
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.warranty import set_order_warranty
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                   active=True, hourly_wage=Decimal("22.00"))
    olga = Employee(employee_number="E-2", first_name="Olga", last_name="Office", employee_group="angestellt",
                    active=True, hourly_wage=Decimal("25.00"))
    db.add_all([mia, olga]); db.flush()
    benutzer = {
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=olga.id,
                         password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id,
                       password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    nord = RoofArea(property_id=objekt.id, name="Nord")
    db.add(nord); db.flush()

    def auftrag(nr: str):
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dachsanierung {nr}", customer_id=kunde.id,
                          property_id=objekt.id, status="angebot", pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        angebot = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}",
                        vat_rate=Decimal("19"))
        db.add(angebot); db.flush()
        db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"),
                         unit="m²", unit_price=Decimal("48.90")))
        db.commit()
        o = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=60), execution_start=None,
                                    execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                    payment_terms=None, remarks=None)
        set_order_warranty(db, o, work_kind="bauwerk", warranty_months=48, warranty_days=0, reason=None)
        a = create_acceptance(db, o, {"kind": "ausdruecklich", "scope": "gesamt", "declared_by": "auftraggeber",
                                      "conduct_reason": "per E-Mail", "roof_area_ids": [],
                                      "accepted_on": heute - timedelta(days=20), "result": "abgenommen",
                                      "reservation_defects": True, "reservation_penalty": False}, [], user_id=None,
                              user_name="Olga Office")
        return o, a

    eigen, abnahme = auftrag("MM1")
    fremd, fremde_abnahme = auftrag("MM2")
    prep = ensure_preparation(db, eigen.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    db.commit()

    def mangel(a, text, **werte):
        dateien = werte.pop("dateien", [])
        return create_defect(db, a, {"description": text, "remedy_due_on": werte.pop("frist", None), **werte}, dateien,
                             user_id=None, user_name="Olga Office")

    attika = mangel(abnahme, "Attika undicht, Wasser tritt bei Regen ein", roof_area_id=nord.id, location="Attika West",
                    frist=heute - timedelta(days=1),
                    dateien=[("foto", "vorher.jpg", _bild("JPEG")), ("beleg", "ruege.pdf", PDF)])
    set_stance(db, attika, stance="bestritten", reason="Abnutzung durch den Nutzer", user_id=None, user_name="Olga Office")
    set_release(db, attika, released=True, reason="Kulanz", user_id=None, user_name="Olga Office")
    rinne = mangel(abnahme, "Rinne lose", dateien=[("foto", "rinne.jpg", _bild("JPEG", (90, 90, 90)))])
    kehle = mangel(abnahme, "Kehle offen")
    set_release(db, kehle, released=True, reason=None, user_id=None, user_name="Olga Office")
    set_release(db, kehle, released=False, reason="Kunde zieht zurück", user_id=None, user_name="Olga Office")
    fremder = mangel(fremde_abnahme, "Fremder Mangel", dateien=[("foto", "f.jpg", _bild("JPEG", (200, 30, 30)))])
    set_release(db, fremder, released=True, reason=None, user_id=None, user_name="Olga Office")

    ordner = Path(os.environ["ERP_DATA_DIR"]) / "klicktest-uploads"
    ordner.mkdir(parents=True, exist_ok=True)
    nachher = ordner / "Nachher.png"
    nachher.write_bytes(_bild("PNG", (40, 160, 60)))

    def erstes_foto(d):
        return next(f.id for f in d.files if f.kind == "foto")
    return {"auftrag": eigen.id, "maengel": {"attika": attika.id, "rinne": rinne.id, "kehle": kehle.id,
                                             "fremd": fremder.id},
            "fotos": {"attika": erstes_foto(attika), "rinne": erstes_foto(rinne), "fremd": erstes_foto(fremder)},
            "beleg_attika": next(f.id for f in attika.files if f.kind == "beleg"),
            "heute": heute.isoformat(), "nachher": str(nachher),
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


MOBIL_BEREIT = "!document.getElementById('defectsList').textContent.includes('Lädt')"
BUERO_BEREIT = "!document.getElementById('defectList').textContent.includes('Lädt')"


def _karte(mangel_id: int) -> str:
    return f"document.getElementById('mmangel-{mangel_id}')"


async def pruefen(tab, seed, p):
    import asyncio

    m, fotos = seed["maengel"], seed["fotos"]
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    p.pruefe("Monteurin dunkel: Thema", await tab.js("document.documentElement.dataset.theme"), "dark")

    # --- Liste: nur der freigegebene, offene Mangel des eigenen Auftrags ------------------------------------------
    p.pruefe("Liste: nur 'Attika undicht'", await tab.js(
        "[...document.querySelectorAll('#defectsList .defect-card')].map(c=>Number(c.dataset.defect))"), [m["attika"]])
    text = await tab.js(f"{_karte(m['attika'])}.innerText")
    p.pruefe("Karte: Beschreibung, Dachfläche, Ort, Frist überschritten", [
        "Attika undicht, Wasser tritt bei Regen ein" in (text or ""), "Dachfläche: Nord" in (text or ""),
        "Ort: Attika West" in (text or ""), "überschritten" in (text or "")], [True, True, True, True])
    p.pruefe("Karte: keine Haltung, Abnahme, Gewährleistung, kein Beleg", [
        w in (text or "") for w in ("bestritten", "Haltung", "Abnahme", "Gewährleistung", "Beleg", "Kulanz")],
        [False] * 6)
    await tab.warten(f"[...{_karte(m['attika'])}.querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)")
    p.pruefe("Karte: ein Foto, geladen über den Monteur-Weg", await tab.js(
        f"[...{_karte(m['attika'])}.querySelectorAll('img')].map(i=>[new URL(i.src).pathname, i.naturalWidth>0])"),
        [[f"/api/field-view/defects/{m['attika']}/photos/{fotos['attika']}", True]])
    p.pruefe("412 px dunkel: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js(f"{_karte(m['attika'])}.scrollIntoView()")
    await tab.bild("1_mobil_mangel_dunkel_412")

    # --- Angriffe aus dem Browser ------------------------------------------------------------------------------------
    p.pruefe("Foto: nicht freigegeben, fremd, Beleg über eigenen Mangel -> 404", await tab.js(
        f"Promise.all(['/api/field-view/defects/{m['rinne']}/photos/{fotos['rinne']}',"
        f"'/api/field-view/defects/{m['fremd']}/photos/{fotos['fremd']}',"
        f"'/api/field-view/defects/{m['attika']}/photos/{seed['beleg_attika']}'].map(u=>fetch(u).then(r=>r.status)))"),
        [404, 404, 404])
    melden_js = ("(id,kennung)=>new Promise(res=>{const c=document.createElement('canvas');c.width=c.height=8;"
                 "c.toBlob(b=>{const f=new FormData();f.append('data',JSON.stringify({client_uuid:kennung,"
                 f"event_date:'{seed['heute']}'}}));f.append('photos',b,'x.png');"
                 "fetch(`/api/field-view/defects/${id}/remedied`,{method:'POST',body:f}).then(async r=>res([r.status,"
                 "await r.json()]))},'image/png')})")
    p.pruefe("Meldung: nicht freigegeben, zurückgenommen, fremd -> 404", await tab.js(
        f"Promise.all([{m['rinne']},{m['kehle']},{m['fremd']}].map(id=>({melden_js})(id,crypto.randomUUID())"
        ".then(x=>x[0])))"), [404, 404, 404])
    p.pruefe("Büro-Wege gesperrt", await tab.js(
        f"Promise.all(['/api/orders/{seed['auftrag']}/defects','/api/defects/{m['attika']}/files/{fotos['attika']}']"
        ".map(u=>fetch(u).then(r=>r.status)))"), [403, 403])

    # --- Beseitigt melden ----------------------------------------------------------------------------------------------
    await tab.js(f"{_karte(m['attika'])}.querySelector('button.defect-report-btn').click()")
    await tab.warten(f"!{_karte(m['attika'])}.querySelector('.defect-report').hidden")
    p.pruefe("Meldung: Datum vorbelegt mit heute, kein Foto gewählt", await tab.js(
        f"[{_karte(m['attika'])}.querySelector('input[type=date]').value, "
        f"{_karte(m['attika'])}.querySelector('input[type=file]').files.length]"), [seed["heute"], 0])
    await tab.js(f"{_karte(m['attika'])}.querySelector('button.defect-send-btn').click()")
    p.pruefe("Meldung ohne Foto abgelehnt", await tab.js(f"{_karte(m['attika'])}.querySelector('.defect-status').textContent"),
             "Bitte mindestens ein Foto der Beseitigung aufnehmen.")
    kennung = await tab.js(f"{_karte(m['attika'])}.querySelector('.defect-report').dataset.kennung")
    await _datei_setzen(tab, f"#mmangel-{m['attika']} input[type=file]", seed["nachher"])
    p.pruefe("Hinweis: optional, höchstens 500 Zeichen, nur fürs Büro", await tab.js(
        f"(t=>[t.maxLength, t.closest('label').textContent.includes('nur fürs Büro')])"
        f"({_karte(m['attika'])}.querySelector('textarea'))"), [500, True])
    await tab.js(f"{_karte(m['attika'])}.querySelector('textarea').value={HINWEIS!r}")
    await tab.bild("2_mobil_meldung_dunkel_412")
    await tab.js(f"{_karte(m['attika'])}.querySelector('button.defect-send-btn').click()")
    await tab.warten("document.getElementById('defectsStatus').textContent.includes('beseitigt gemeldet')")
    await tab.warten("!document.querySelector('#defectsList .defect-card')")
    p.pruefe("Gemeldet: Hinweis, Abschnitt leer", await tab.js(
        "[document.getElementById('defectsStatus').textContent, document.getElementById('defectsList').innerText]"),
        ["Mangel als beseitigt gemeldet – das Büro prüft die Abnahme der Beseitigung.",
         "Keine Mängel zur Beseitigung."])
    await tab.bild("3_mobil_gemeldet_dunkel_412")
    wiederholt = await tab.js(f"({melden_js})({m['attika']},{kennung!r})")
    p.pruefe("Dieselbe Kennung noch einmal: 200, ein Foto, dieselbe Meldung",
             [wiederholt[0], wiederholt[1].get("photo_count"), wiederholt[1].get("defect_id")] if wiederholt else None,
             [200, 1, m["attika"]])
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro -------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/orders/{seed['auftrag']}", BUERO_BEREIT)
    karte = f"document.getElementById('mangel-{m['attika']}')"
    await tab.js(f"{karte}.querySelector('details').open=true;{karte}.scrollIntoView()")
    p.pruefe("Büro: Status beseitigt, Meldung aus der Monteursansicht mit Foto", await tab.js(
        f"(t=>[t.split('\\n')[1].startsWith('beseitigt'), t.includes('gemeldet in der Monteursansicht'), "
        f"[...{karte}.querySelectorAll('.def-event')].pop().querySelectorAll('a[href*=\"/files/\"]').length, "
        f"t.includes('Mia Monteurin')])({karte}.innerText)"), [True, True, 1, True])
    p.pruefe("Büro: Hinweis aus der Monteursansicht, Aufgabe angelegt", await tab.js(
        f"(t=>[t.includes('Hinweis aus der Monteursansicht: {HINWEIS}'), "
        "t.includes('Aufgabe „Beseitigung abnehmen lassen“ angelegt'), "
        "t.includes('Aufgabe (Beseitigung abnehmen lassen): Beseitigung abnehmen lassen – Mangel aus Abnahme')])"
        f"({karte}.innerText)"), [True, True, True])
    p.pruefe("Büro: Link auf die Aufgabe", await tab.js(
        f"[...{karte}.querySelectorAll('a[href^=\"/tasks?task=\"]')].length"), 1)
    await tab.bild("4_buero_beseitigt_hell")
    await tab.js(f"defOpen({m['rinne']},'freigabe');document.getElementById('defPanel{m['rinne']}').querySelector('button').click()")
    await tab.warten(f"document.getElementById('mangel-{m['rinne']}').innerText.includes('zur Beseitigung freigegeben')")
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])

    # --- Monteurin hell: freigegeben erscheint, zurückgenommen verschwindet --------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    p.pruefe("Hell: 'Rinne lose' nach der Freigabe sichtbar", await tab.js(
        "[...document.querySelectorAll('#defectsList .defect-card')].map(c=>Number(c.dataset.defect))"), [m["rinne"]])
    await tab.bild("5_mobil_hell_412")
    await tab.anmelden(seed["cookies"]["buero"])
    status = await tab.js(
        f"fetch('/api/defects/{m['rinne']}/release',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({released:false,reason:'Kunde zieht zurück'})}).then(r=>r.status)")
    p.pruefe("Büro nimmt die Freigabe zurück", status, 200)
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    await asyncio.sleep(0.2)
    p.pruefe("Zurückgenommen: verschwunden", await tab.js("document.getElementById('defectsList').innerText"),
             "Keine Mängel zur Beseitigung.")

    # --- Seit 1.8.54: zurück auf offen -- wieder in /mobil ohne Hinweis, im Büro "Erneut beseitigen" --------------------
    await tab.anmelden(seed["cookies"]["buero"])
    status = await tab.js(
        f"(()=>{{const f=new FormData();f.append('data',JSON.stringify({{status:'offen',reason:'Nachbesserung misslungen'}}));"
        f"return fetch('/api/defects/{m['attika']}/status',{{method:'POST',body:f}}).then(r=>r.status)}})()")
    p.pruefe("Büro setzt 'Attika undicht' zurück auf offen", status, 200)
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    p.pruefe("Wieder offen: sichtbar, ohne Hinweis", await tab.js(
        "[[...document.querySelectorAll('#defectsList .defect-card')].map(c=>Number(c.dataset.defect)),"
        f"document.getElementById('defectsList').innerText.includes({HINWEIS!r})]"), [[m["attika"]], False])
    p.pruefe("Monteurin hell: keine JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/orders/{seed['auftrag']}", BUERO_BEREIT)
    p.pruefe("Büro: aktuelle Aufgabe 'Erneut beseitigen'", await tab.js(
        f"{karte}.innerText.includes('Aufgabe (Mangel beseitigen): Erneut beseitigen – Mangel aus Abnahme')"), True)
    await tab.js(f"{karte}.scrollIntoView()")
    await tab.bild("6_buero_wieder_offen_hell")
    p.pruefe("Büro (zweiter Besuch): keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Monteur-Sicht auf Mängel (1.8.52)", uhr="10:00"))
