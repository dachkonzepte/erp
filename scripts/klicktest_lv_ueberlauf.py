"""Klicktest: das Leistungsverzeichnis in LV-Editor und Auftrag läuft nicht rechts aus seiner Karte (1.8.133, Fehlerrunde vor Stufe 2,
Punkt 2, Vorgabe vom 19.10.2026).

Bis 1.8.132 hatten die Spalten des LV feste Breiten (LV-Editor rund 920 px, Auftrag rund 850 px), die linke Spalte des Seitenrasters war
bei 1440 px aber nur rund 770 bzw. 760 px breit -- Gesamtpreis und EP standen rechts außerhalb der Karte, im LV-Editor unter dem Katalog.
Bei 1280 px war schon das zweispaltige Seitenraster breiter als der Inhaltsbereich (die Seite scrollte waagerecht).

    gemessen        je Seite (LV-Editor, Auftrag) und Breite (1440, 1280 px, Desktop) jede Zelle jeder LV-Zeile samt Kopf: rechte Kante
                    innerhalb der Karte, kein abgeschnittener Inhalt in den Preisspalten (scrollWidth <= clientWidth); die Seite selbst
                    ohne waagerechten Bildlauf; Preise mit großen Beträgen (12.345,678 m² zu 1.234,56 €)

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

# Zeilen und Zellen je Seite: Kopf und Positionen des LV
ZEILEN = {"angebot": ".lv-columns, .lv-item", "auftrag": ".lv-head, .lv-row"}

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
    seiten = {"angebot": (f"/quotes/{seed['angebot']}/edit", "document.querySelectorAll('.lv-item').length>=2"),
              "auftrag": (f"/orders/{seed['auftrag']}", "document.querySelectorAll('.lv-row').length>=2")}
    for breite in (1440, 1280):
        await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=900, deviceScaleFactor=1, mobile=False)
        for name, (pfad, bereit) in seiten.items():
            p.pruefe(f"{name} {breite}: geladen", await tab.oeffnen(pfad, bereit), True)
            await tab.warte_auf_ruhe()
            stand = await tab.js(f"{MESSEN}({ZEILEN[name]!r})")
            p.pruefe(f"{name} {breite}: LV-Zeilen gemessen", stand["zeilen"] >= 3, True)
            p.pruefe(f"{name} {breite}: kein Überlauf", stand["fehler"], [])
            await tab.bild(f"lv_{name}_{breite}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
