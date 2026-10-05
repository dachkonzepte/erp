"""Klicktest: Zeichenfläche nach Drehen und Größenänderung neu vermessen (1.8.58, Stufe 2c-2c, Punkt 4).

Befüllt: Monteurin, Auftrag, Vorlage mit Bemerkung und "Unterschrift Monteur", Checkliste der Monteurin; dazu ein
Einsatzbericht-Entwurf der Monteurin.

    Tablet hochkant (600 x 960, Geräteauflösung 2, Touch)   Fläche in Geräteauflösung vermessen; Strich mit simulierter
                                                            Touch-Eingabe (Input.dispatchTouchEvent) -- nicht leer.
    gedreht (960 x 600, quer)                               Fläche neu vermessen (Pixelbreite = angezeigte Breite x 2), der
                                                            erste Strich bleibt sichtbar; zweiter Strich liegt genau unter dem
                                                            Finger (Pixel an der Berührstelle gefärbt).
    zurückgedreht (hochkant)                                wieder vermessen, beide Striche in der Fläche, nichts verzerrt;
                                                            Unterschrift übernommen, vom Server geprüft (nicht leer), Siegel
                                                            unverändert.
    Fenster schmaler (Größenänderung ohne Drehen)           neu vermessen.
    Einsatzbericht                                          dieselbe Fläche im Unterschriften-Panel: nach dem Drehen vermessen.

Ohne das Neu-Vermessen (Fläche von 1.8.57) liegt der zweite Strich nicht unter dem Finger und die Pixelbreite passt nicht
mehr -- Gegenprobe im Bericht von 1.8.58. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zeichenflaeche.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402

HOCH = {"type": "portraitPrimary", "angle": 0}
QUER = {"type": "landscapePrimary", "angle": 90}


def befuellen(db, k):
    from decimal import Decimal

    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist
    from app.models import AppUser, Customer, Employee, Order, Project, WorkPreparationEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                   active=True, hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    user = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id,
                   password_hash=k.passwort())
    db.add(user); db.flush()
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-ZF", name="Dach Nord", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-ZF", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle",
                    property_address="Weg 1\n12345 Stadt")
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id)); db.commit()
    t = create_template(db, label="Kurzprotokoll", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig"})
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=mia.id, created_by_user_id=user.id)
    bericht = create_report(db, auftrag.id, "rapport", description="Dach kontrolliert.", created_by_employee_id=mia.id)
    return {"checklist": cl["id"], "sig": next(f["id"] for f in cl["fields"] if f["field_key"] == "sig"),
            "order": auftrag.id, "report": bericht["id"], "cookies": {"mia": k.cookies(user)}}


async def _geraet(tab, breite: int, hoehe: int, lage: dict) -> None:
    import asyncio

    await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe, deviceScaleFactor=2, mobile=True,
                  screenOrientation=lage)
    await asyncio.sleep(0.5)  # ResizeObserver und requestAnimationFrame


async def _touch_strich(tab, punkte: list[tuple[float, float]]) -> None:
    """Ein Strich mit simulierter Touch-Eingabe (daraus macht Chrome Zeigerereignisse vom Typ "touch")."""
    x, y = punkte[0]
    await tab.cmd("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
    for x, y in punkte[1:]:
        await tab.cmd("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": x, "y": y}])
    await tab.cmd("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])


def _flaeche(sel: str) -> str:
    """[angezeigte Breite, Höhe, Pixelbreite, Pixelhöhe, Geräteauflösung, gefärbte Pixel, links, oben] der Fläche."""
    return (f"(()=>{{const c=document.querySelector('{sel}');const r=c.getBoundingClientRect();"
            "const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>200)n++;"
            "return [r.width,r.height,c.width,c.height,window.devicePixelRatio,n,r.left,r.top]})()")


def _pixel_unter(sel: str, x: float, y: float) -> str:
    """Ist das Pixel unter der Berührstelle (x, y im Fenster) gefärbt? Umgerechnet über die angezeigte Größe -- genau so,
    wie der Browser die Fläche darstellt. 3 x 3 Pixel Umgebung (Strichstärke 2,4)."""
    return (f"(()=>{{const c=document.querySelector('{sel}');const r=c.getBoundingClientRect();"
            f"const px=Math.round(({x}-r.left)*c.width/r.width),py=Math.round(({y}-r.top)*c.height/r.height);"
            "const d=c.getContext('2d').getImageData(px-1,py-1,3,3).data;for(let i=3;i<d.length;i+=4)if(d[i]>200)return true;return false})()")


def _vermessen_ok(f) -> bool:
    w, h, pw, ph, dpr = f[:5]
    return abs(pw - round(w * dpr)) <= 1 and abs(ph - round(h * dpr)) <= 1


async def pruefen(tab, seed, p):
    sel = f"#pad_{seed['sig']}"
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    await tab.cmd("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    await tab.anmelden(seed["cookies"]["mia"])
    await _geraet(tab, 600, 960, HOCH)
    await tab.oeffnen(f"/checklisten/{seed['checklist']}", f"document.querySelector('{sel}')")
    await tab.js(f"document.querySelector('{sel}').scrollIntoView({{block:'center'}})")
    hoch = await tab.js(_flaeche(sel))
    p.pruefe("Hochkant: in Geräteauflösung vermessen", _vermessen_ok(hoch), True)
    l, o, w, h = hoch[6], hoch[7], hoch[0], hoch[1]
    await _touch_strich(tab, [(l + w * 0.1 + i * w * 0.03, o + h * (0.5 + (0.2 if i % 2 else -0.2))) for i in range(12)])
    p.pruefe("Touch-Strich: Fläche nicht leer", await tab.js(f"!pads[{seed['sig']}].leer()"), True)
    vorher = (await tab.js(_flaeche(sel)))[5]

    await _geraet(tab, 960, 600, QUER)
    await tab.js(f"document.querySelector('{sel}').scrollIntoView({{block:'center'}})")
    quer = await tab.js(_flaeche(sel))
    p.pruefe("Gedreht: neu vermessen (Pixelbreite = angezeigte Breite x 2)", [_vermessen_ok(quer), quer[0] > hoch[0]],
             [True, True])
    p.pruefe("Gedreht: erster Strich bleibt sichtbar, nicht leer", [quer[5] > vorher * 0.5, await tab.js(f"!pads[{seed['sig']}].leer()")],
             [True, True])
    l, o, w, h = quer[6], quer[7], quer[0], quer[1]
    ziel = (l + w * 0.75, o + h * 0.3)
    await _touch_strich(tab, [(ziel[0] - 40, ziel[1]), (ziel[0] - 20, ziel[1]), ziel, (ziel[0] + 20, ziel[1]),
                              (ziel[0] + 40, ziel[1])])
    p.pruefe("Gedreht: zweiter Strich liegt unter dem Finger", await tab.js(_pixel_unter(sel, *ziel)), True)

    await _geraet(tab, 600, 960, HOCH)
    await tab.js(f"document.querySelector('{sel}').scrollIntoView({{block:'center'}})")
    zurueck = await tab.js(_flaeche(sel))
    p.pruefe("Zurückgedreht: vermessen, Striche noch da", [_vermessen_ok(zurueck), zurueck[5] > 0], [True, True])

    await _geraet(tab, 420, 960, HOCH)  # Größenänderung ohne Drehen (z. B. geteilter Bildschirm)
    schmal = await tab.js(_flaeche(sel))
    p.pruefe("Schmaler: neu vermessen", [_vermessen_ok(schmal), schmal[0] < zurueck[0], schmal[5] > 0], [True, True, True])

    await tab.js(f"document.getElementById('padName_{seed['sig']}').value='Mia Monteurin'")
    await tab.js(f"document.querySelector('#q_{seed['sig']} .pad-actions .btn:not(.secondary)').click()")
    await tab.warten(f"document.querySelector('#q_{seed['sig']} .sig')", 10)
    antwort = await tab.js(f"fetch('/api/checklists/{seed['checklist']}').then(r=>r.json()).then(d=>d.attachments.filter(a=>a.kind==='unterschrift').map(a=>[a.signer_name,a.seal.status]))")
    p.pruefe("Unterschrift übernommen, vom Server geprüft, Siegel unverändert", antwort, [["Mia Monteurin", "unveraendert"]])
    p.pruefe("Checkliste: keine JS-Fehler", tab.fehler, [])
    await tab.bild("1_checkliste_schmal")

    # --- Einsatzbericht: dieselbe Fläche im Unterschriften-Panel ----------------------------------------------
    await _geraet(tab, 600, 960, HOCH)
    await tab.oeffnen(f"/orders/{seed['order']}/service-reports", "typeof openSignPanel==='function' || document.querySelector('#sigCanvas')")
    geoeffnet = await tab.js(f"(async()=>{{if(typeof openSignPanel==='function')await openSignPanel({seed['report']});"
                             "return !!document.getElementById('sigCanvas')})()")
    if geoeffnet:
        await tab.js("document.getElementById('sigCanvas').scrollIntoView({block:'center'})")
        await _geraet(tab, 960, 600, QUER)
        await tab.js("document.getElementById('sigCanvas').scrollIntoView({block:'center'})")
        bericht = await tab.js(_flaeche("#sigCanvas"))
        p.pruefe("Einsatzbericht gedreht: neu vermessen", _vermessen_ok(bericht) and bericht[0] > 0, True)
    else:
        p.pruefe("Einsatzbericht: Unterschriften-Panel geöffnet", geoeffnet, True)
    p.pruefe("Einsatzbericht: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Zeichenfläche nach Drehen neu vermessen (1.8.58)", uhr="10:00"))
