"""Klicktest: Restfälle des Auswahl-Musters (1.8.31).

Geprüft über die echten Seiten als Admin:

    Backoffice     Buchung der ausgeschiedenen Bernd auf einem abgeschlossenen Auftrag: der Auftrag bleibt
                   vorgewählt ("(abgeschlossen)"), Speichern gelingt und behält ihn
    Angebot        archivierter Steuerschlüssel vorgewählt "(inaktiv)"; leerer Schlusstext 2 bleibt leer, auch nach
                   dem Speichern des Kopfs; Position ohne Einheit zeigt "— keine Einheit —"
    Auftrag,       archivierter Steuerschlüssel vorgewählt "(inaktiv)"
    Rechnung
    Dachfläche     Schicht eines abgeschalteten Schichttyps in der Liste, gekennzeichnet, nicht unter "Passt nicht"
    Kunde          abgeschaltete Kategorie vorgewählt "(inaktiv)"

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_auswahl_restfaelle.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.crm import ensure_customer_profile
    from app.invoices import create_schlussrechnung
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, Project, Property, Quote, QuoteItem, RoofArea, RoofLayer,
        RoofLayerType, SettingOption, SettingOptionGroup, TaxKey, TimeEntry,
    )
    from app.option_settings import ensure_default_option_groups
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.tax_keys import ensure_default_tax_keys

    ensure_default_option_groups(db)
    ensure_default_tax_keys(db)
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Kundin Klar", last_name="Klar")
    bernd = Employee(employee_number="E-1", first_name="Bernd", last_name="Bau", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    alt = TaxKey(label="Alt 16", vat_rate=Decimal("16"), is_default=False, archived=False)
    db.add_all([admin, kunde, bernd, alt]); db.flush()
    ensure_customer_profile(db, kunde, "Gewerbekunde")
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    offen = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                  title="Dachsanierung", customer_name=kunde.name, vat_rate=Decimal("16"), tax_key_id=alt.id)
    erledigt = Order(order_number="AU-KT-0002", project_id=projekt.id, source_quote_id=2, quote_number_snapshot="A-KT-2",
                     title="Gaube", customer_name=kunde.name, vat_rate=Decimal("19"), status="abgeschlossen")
    angebot = Quote(quote_number="A-KT-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("16"),
                    tax_key_id=alt.id, intro_text="Wir bieten an:", outro_text="Mit freundlichen Grüßen", outro_text_2=None)
    db.add_all([offen, erledigt, angebot]); db.flush()
    db.add(OrderItem(order_id=offen.id, sort_order=10, position_number="1", short_text="Eindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    gaube = OrderItem(order_id=erledigt.id, sort_order=10, position_number="1", short_text="Gaube abdichten",
                      quantity=Decimal("1"), unit="psch", unit_price=Decimal("0"))
    position = QuoteItem(quote_id=angebot.id, sort_order=10, position_number="1", short_text="Altposition", long_text="",
                         quantity=Decimal("1"), unit="", unit_price=Decimal("0"))
    db.add_all([gaube, position]); db.flush()
    buchung = TimeEntry(employee_id=bernd.id, project_id=projekt.id, order_id=erledigt.id, order_item_id=gaube.id,
                        work_date=berlin_today(), entry_type="site", hours=Decimal("4"), break_minutes=30,
                        source="manual", status="booked")
    db.add(buchung); db.commit()
    rechnung = create_schlussrechnung(db, offen)
    rechnung.tax_key_id = alt.id

    objekt = Property(customer_id=kunde.id, name="Halle", street="Weg 1", postal_code="12345", city="Ort")
    db.add(objekt); db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Hauptdach", roof_type="Flachdach")
    abdichtung = RoofLayerType(key="kt_abdichtung", label="Abdichtung", roof_type="Flachdach", option_group=None, sort_order=10)
    kies = RoofLayerType(key="kt_kies", label="Kiesschüttung", roof_type="Flachdach", option_group=None, sort_order=20)
    db.add_all([flaeche, abdichtung, kies]); db.flush()
    db.add(RoofLayer(roof_area_id=flaeche.id, layer_type_id=kies.id, present=True, notes="16/32"))

    gewerbe = db.query(SettingOption).join(SettingOptionGroup).filter(
        SettingOptionGroup.group_key == "customer_categories", SettingOption.value == "Gewerbekunde").one()
    # nach der Zuordnung ausgeschieden, archiviert bzw. abgeschaltet
    bernd.active, alt.archived, kies.active, gewerbe.active = False, True, False, False
    db.commit()
    return {"buchung": buchung.id, "erledigt": erledigt.id, "gaube": gaube.id, "angebot": angebot.id,
            "position": position.id, "auftrag": offen.id, "rechnung": rechnung.id, "flaeche": flaeche.id,
            "kunde": kunde.id, "cookies": {"anna": k.cookies(admin)}}


def _archiviert_gewaehlt(auswahl) -> str | None:
    """Text der vorgewählten Option, wenn es der archivierte Steuerschlüssel "Alt 16" mit "(inaktiv)" ist."""
    text = (auswahl or [None, None])[1] or ""
    return "Alt 16 … (inaktiv)" if text.startswith("Alt 16") and text.endswith("(inaktiv)") else text


def _gewaehlt(select_id: str) -> str:
    return f"(s=>[s.value,s.selectedOptions[0]?.textContent])(document.getElementById('{select_id}'))"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 900)

    # --- Backoffice-Korrektur ------------------------------------------------------------------
    b = seed["buchung"]
    await tab.oeffnen("/time-backoffice#entries", f"entries.some(e=>e.id==={b})")
    await tab.js(f"openEdit({b})")
    p.pruefe("Backoffice: abgeschlossener Auftrag vorgewählt", await tab.js(_gewaehlt("editOrder")),
             [str(seed["erledigt"]), "AU-KT-0002 · Gaube (abgeschlossen)"])
    p.pruefe("Backoffice: LV-Position vorgewählt", await tab.js("document.getElementById('editOrderItem').value"),
             str(seed["gaube"]))
    await tab.bild("backoffice_abgeschlossener_auftrag")
    await tab.js("document.getElementById('editHours').value='5';saveEntryEdit()")
    await tab.warten("!document.getElementById('editDialog').open||document.getElementById('editStatus').textContent")
    p.pruefe("Backoffice: Speichern gelingt (Bernd ist ausgeschieden)",
             await tab.js("document.getElementById('editStatus').textContent"), "")
    p.pruefe("Backoffice: Auftrag, Position und Person bleiben",
             await tab.js(f"fetch('/api/time-entries?limit=2000').then(r=>r.json()).then(l=>l.find(e=>e.id==={b}))"
                          ".then(e=>[e.order_id,e.order_item_id,Number(e.hours),e.employee_name])"),
             [seed["erledigt"], seed["gaube"], 5, "Bernd Bau"])
    p.pruefe("Backoffice: JS-Fehler", tab.fehler, [])

    # --- Angebot -------------------------------------------------------------------------------
    a = seed["angebot"]
    await tab.oeffnen(f"/quotes/{a}/edit", "quote&&document.getElementById('hTaxKey').options.length>0")
    p.pruefe("Angebot: archivierter Steuerschlüssel vorgewählt", _archiviert_gewaehlt(await tab.js(_gewaehlt("hTaxKey"))),
             "Alt 16 … (inaktiv)")
    p.pruefe("Angebot: leerer Schlusstext 2 bleibt leer", await tab.js(_gewaehlt("hOutro2")), ["", "— keine Auswahl —"])
    await tab.js("saveHeader()")
    await tab.warten("document.getElementById('headerStatus').textContent")
    p.pruefe("Angebot: Kopf speichern lässt Schlusstext 2 leer",
             await tab.js(f"fetch('/api/quotes/{a}').then(r=>r.json()).then(q=>[q.intro_text,q.outro_text,q.outro_text_2])"),
             ["Wir bieten an:", "Mit freundlichen Grüßen", None])
    await tab.js(f"editItem({seed['position']})")
    p.pruefe("Angebot: Position ohne Einheit", await tab.js(_gewaehlt("iUnit")), ["", "— keine Einheit —"])
    p.pruefe("Angebot: JS-Fehler", tab.fehler, [])

    # --- Auftrag und Rechnung ------------------------------------------------------------------
    for pfad, bereit, select_id, name in (
            (f"/orders/{seed['auftrag']}", "order&&document.getElementById('taxKey').options.length>0", "taxKey", "Auftrag"),
            (f"/invoices/{seed['rechnung']}", "invoice&&document.getElementById('iTaxKeySelect').options.length>0",
             "iTaxKeySelect", "Rechnung")):
        await tab.oeffnen(pfad, bereit)
        p.pruefe(f"{name}: archivierter Steuerschlüssel vorgewählt",
                 _archiviert_gewaehlt(await tab.js(_gewaehlt(select_id))), "Alt 16 … (inaktiv)")
        p.pruefe(f"{name}: JS-Fehler", tab.fehler, [])

    # --- Dachfläche ----------------------------------------------------------------------------
    await tab.oeffnen(f"/roof-areas/{seed['flaeche']}", "document.getElementById('layerRows').textContent.includes('Abdichtung')")
    p.pruefe("Dachfläche: Schicht des abgeschalteten Typs in der Liste",
             await tab.js("document.getElementById('layerRows').textContent.includes('Kiesschüttung (inaktiv)')"), True)
    p.pruefe("Dachfläche: nicht unter \"Passt nicht zum aktuellen Dachtyp\"",
             await tab.js("document.getElementById('layerMismatchSection').classList.contains('hidden')"), True)
    p.pruefe("Dachfläche: JS-Fehler", tab.fehler, [])
    await tab.bild("dachflaeche_inaktiver_schichttyp")

    # --- Kunde ---------------------------------------------------------------------------------
    await tab.oeffnen(f"/customers/{seed['kunde']}", "customer&&document.getElementById('category').options.length>0")
    p.pruefe("Kunde: abgeschaltete Kategorie vorgewählt", await tab.js(_gewaehlt("category")),
             ["Gewerbekunde", "Gewerbekunde (inaktiv)"])
    p.pruefe("Kunde: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
