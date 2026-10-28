"""Klicktest: das Leistungsverzeichnis in LV-Editor und Auftrag (seit 1.9.129 Reiter „Leistungen“ der Akte) läuft nicht rechts aus
seiner Karte (1.8.133, Fehlerrunde vor Stufe 2, Punkt 2, Vorgabe vom 19.10.2026).

Bis 1.8.132 hatten die Spalten des LV feste Breiten (LV-Editor rund 920 px, Auftrag rund 850 px), die linke Spalte des Seitenrasters war
bei 1440 px aber nur rund 770 bzw. 760 px breit -- Gesamtpreis und EP standen rechts außerhalb der Karte, im LV-Editor unter dem Katalog.
Bei 1280 px war schon das zweispaltige Seitenraster breiter als der Inhaltsbereich (die Seite scrollte waagerecht).

    gemessen        je Seite (LV-Editor, Auftrag) und Breite (1440, 1280 px, Desktop) jede Zelle jeder LV-Zeile samt Kopf: rechte Kante
                    innerhalb der Karte, kein abgeschnittener Inhalt in den Preisspalten (scrollWidth <= clientWidth); die Seite selbst
                    ohne waagerechten Bildlauf; Preise mit großen Beträgen (12.345,678 m² zu 1.234,56 €)

Seit 1.9.129 ist der Auftrag ein Reiter der Akte (/orders/{id} leitet auf /projects/{p}?auftrag={id}, Reiter „Leistungen“): die LV-Zeile
zeigt Menge und EP als Text (Tabelle #lvTabelle, Zeilen #lv tr.lv-row), bearbeitet wird im Dialog der Position (#itemDialog, „✎“). Geprüft
wird deshalb, dass der Text mit Tausenderpunkt in die Zelle passt und das Feld im Dialog ihn ganz zeigt; der Rundweg speichert den Dialog
unverändert.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_lv_ueberlauf.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

# Zeilen und Zellen je Seite: Kopf und Positionen des LV (seit 1.9.129 im Auftrag eine Tabelle im Reiter „Leistungen“ der Akte)
ZEILEN = {"angebot": ".lv-columns, .lv-item", "auftrag": "#lvTabelle thead tr, #lv tr.lv-row"}

# seit 1.9.129: Menge und EP der Position mit großen Beträgen als Text in der Zeile -- [Spalte, Text, passt in die Zelle]
ZELLEN_TAUSENDER = r"""(()=>{
const z=[...document.querySelectorAll('#lv tr.lv-row')].find(r=>r.cells[2]&&r.cells[2].textContent.includes('.'));if(!z)return [];
return [['Menge',z.cells[2]],['Einheitspreis',z.cells[4]]].map(([n,c])=>[n,c.textContent.trim(),c.scrollWidth<=c.clientWidth]);
})()"""

# seit 1.9.129: dieselben Werte im Dialog der Position -- [Feld, Wert, passt ins Feld]
DIALOG_TAUSENDER = r"""(()=>{
const d=document.getElementById('itemDialog');if(!d.open)return null;
return [['Menge','iQty'],['Einheitspreis','iPrice']].map(([n,id])=>{const f=document.getElementById(id);return [n,f.value,f.scrollWidth<=f.clientWidth]});
})()"""

# „✎“ der Position mit großen Beträgen anklicken (öffnet #itemDialog)
DIALOG_OEFFNEN = ("[...document.querySelectorAll('#lv tr.lv-row')].find(r=>r.cells[2]&&r.cells[2].textContent.includes('.'))"
                  ".querySelector('[data-klick=\"position-bearbeiten\"]').click()")

MESSEN = r"""((auswahl)=>{
const fehler=[];
const zeilen=[...document.querySelectorAll(auswahl)].filter(z=>z.offsetParent!==null);
for(const z of zeilen){
  const karte=z.closest('.card,section,.section')||document.body;const kr=karte.getBoundingClientRect();
  [...z.children].forEach((zelle,i)=>{
    if(zelle.offsetParent===null)return;
    const r=zelle.getBoundingClientRect();
    if(r.right>kr.right+0.5)fehler.push(`Zelle ${i+1} „${(zelle.innerText||'').trim().slice(0,20)}“ endet bei ${Math.round(r.right)}, Karte bei ${Math.round(kr.right)}`);
    if(zelle.scrollWidth>zelle.clientWidth+1&&zelle.clientWidth>0&&!zelle.querySelector('input,select,textarea'))
      fehler.push(`Zelle ${i+1} „${(zelle.innerText||'').trim().slice(0,20)}“ abgeschnitten (${zelle.scrollWidth} > ${zelle.clientWidth})`);
  });
}
const seite=document.documentElement.scrollWidth-window.innerWidth;
if(seite>0)fehler.push(`Seite ${seite} px breiter als das Fenster`);
return {zeilen:zeilen.length,fehler};
})"""


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="bea", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH")
    db.add_all([buero, kunde]); db.flush()
    projekt = Project(project_number="P-2026-0001", name="Dachsanierung Halle Nord", customer_id=kunde.id, status="beauftragt",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-2026-0001", project_id=projekt.id, title="Dachsanierung Halle Nord", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add_all([
        QuoteItem(quote_id=quote.id, position_number="01.001", short_text="Abdichtung Bitumen, zweilagig, mit Gefälledämmung",
                  quantity=Decimal("12345.678"), unit="m²", unit_price=Decimal("1234.56")),
        QuoteItem(quote_id=quote.id, position_number="01.002", short_text="Attika verwahren", quantity=Decimal("120"), unit="m",
                  unit_price=Decimal("36.50")),
    ])
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    return {"cookies": k.cookies(buero), "angebot": quote.id, "auftrag": order.id}


async def pruefen(tab, seed, p):
    await tab.anmelden(seed["cookies"])
    # seit 1.9.129: der Auftrag ist der Reiter „Leistungen“ der Akte -- ohne ihn wäre die Tabelle verborgen (Maße 0)
    seiten = {"angebot": (f"/quotes/{seed['angebot']}/edit", "document.querySelectorAll('.lv-item').length>=2"),
              "auftrag": (f"/orders/{seed['auftrag']}#leistungen",
                          "order&&order.id&&!document.getElementById('reiter-leistungen').hidden"
                          "&&document.querySelectorAll('#lv tr.lv-row').length>=2")}
    erwartet = [["Menge", "12.345,678", True], ["Einheitspreis", "1.234,56", True]]
    for breite in (1440, 1280):
        await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=900, deviceScaleFactor=1, mobile=False)
        for name, (pfad, bereit) in seiten.items():
            p.pruefe(f"{name} {breite}: geladen", await tab.oeffnen(pfad, bereit), True)
            await tab.warte_auf_ruhe()
            stand = await tab.js(f"{MESSEN}({ZEILEN[name]!r})")
            p.pruefe(f"{name} {breite}: LV-Zeilen gemessen", stand["zeilen"] >= 3, True)
            p.pruefe(f"{name} {breite}: kein Überlauf", stand["fehler"], [])
            await tab.bild(f"lv_{name}_{breite}")
            if name == "auftrag":
                # seit 1.8.148 Menge und EP mit Tausenderpunkt; seit 1.9.129 als Text in der Zeile (bis dahin ein Feld in der Zeile),
                # der Text passt in die Zelle -- und das Feld im Dialog der Position zeigt ihn ganz
                p.pruefe(f"auftrag {breite}: Tausenderpunkt, passt in die Zelle", await tab.js(ZELLEN_TAUSENDER), erwartet)
                await tab.js(DIALOG_OEFFNEN)
                await tab.warten("document.getElementById('itemDialog').open", 5)
                p.pruefe(f"auftrag {breite}: Dialog der Position: Tausenderpunkt, passt ins Feld", await tab.js(DIALOG_TAUSENDER),
                         erwartet)
                await tab.bild(f"lv_auftrag_dialog_{breite}")
                await tab.js("document.getElementById('itemDialog').close()")
    # seit 1.8.151: Rundweg -- die angezeigten Werte unverändert verlassen, gespeichert ist derselbe Betrag; seit 1.9.129 über den Dialog
    # der Position (unverändert speichern), bis dahin „change“ an den Feldern der Zeile
    await tab.js(DIALOG_OEFFNEN)
    await tab.warten("document.getElementById('itemDialog').open", 5)
    await tab.js("saveItemDialog()")
    p.pruefe("auftrag: Rundweg -- Dialog gespeichert und geschlossen", await tab.js(
        "[document.getElementById('itemDialog').open,document.getElementById('itemStatus').textContent]"), [False, ""])
    await tab.warte_auf_ruhe()
    p.pruefe("auftrag: Rundweg speichert denselben Betrag", await tab.js(
        f"fetch('/api/orders/{seed['auftrag']}').then(r=>r.json()).then(o=>o.items.filter(i=>Number(i.quantity)>1000)"
        ".map(i=>[Number(i.quantity),Number(i.unit_price)]))"), [[12345.678, 1234.56]])
    # seit 1.9.129: bei 412 px läuft der Reiter „Leistungen“ nicht über -- bis dahin hing der Vorlesetext „Aktionen“ im Kopf des LV
    # (position:absolute) an der Seite statt am Bildlauf der Tabelle (Fund der Umstellung auf die Akte)
    await tab.fenster(412, 900, mobil=True)
    p.pruefe("auftrag 412: geladen", await tab.oeffnen(*seiten["auftrag"]), True)
    await tab.warte_auf_ruhe()
    p.pruefe("auftrag 412: kein waagrechter Bildlauf der Seite", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("lv_auftrag_412")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
