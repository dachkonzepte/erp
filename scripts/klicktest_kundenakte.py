"""Klicktest: die Kundenakte (1.9.137, Stufe 5, R3, Punkte 2, 3 und 5) nach den Vorlagen bildgrundlage/entwurf_stufe5_kunde/kunde-*.html.

Kunde „Wohnbau Kessler GmbH“ (Gewerbekunde, K-10042) mit
    Projekt A   Dachsanierung Am Wasserturm 4: Auftrag 300 m² × 100 €; pauschaler Abschlag 2.400 € netto im Vorjahr, bezahlt mit 3.000 €
                (Rest 144 € am Kunden); Abschlag 10.000 € netto vor 40 Tagen, unbezahlt und überfällig; Abschlag 5.000 € netto vor 20 Tagen,
                bezahlt
    Projekt B   Flachdach Garage Lindenweg 7: nur ein Angebot (8.950 € netto), per E-Mail vor 17 Tagen
    Projekt C   Sturmschaden Lindenweg 7: Auftrag storniert („Abgeschlossen: …“)
    dazu        zwei Objekte mit Dachflächen, Kontakte & Kundenwissen, eine Anfrage
und Kunde „Hausverwaltung Maus“ ohne Projekt.

    Büro – Finanzen  Kopf (Pfad, Name, Kennung, Kategorie, Anschrift, Telefon und E-Mail als Link), Reiter mit Zählern, Übersicht (laufende
                     Projekte mit Zahlen, Geld mit Vorschlag, Stammdaten, Kontakte, Objekte), jeder Reiter per Klick, #zahlungen öffnet den
                     Reiter; „⋮“ eines Eingangs mit Zuordnen, Erstatten, Trennlinie, Zurücknehmen; Dialog „Erstattung buchen“ mit der Zeile
                     des Rests; Vorschlag „Auf RE-… zuordnen …“ -> Dialog vorbelegt -> zugeordnet, Rest 0, Vorschlag weg; Dialog
                     „Stammdaten bearbeiten“: Eingabe bleibt beim Neuzeichnen, gesendet wird nur das Geänderte; Verlauf mit beidem;
                     „⋮“ des Kopfs und der Akte mit Trennlinien; dunkel; 412 px ohne waagrechtes Scrollen
    Büro – Auftrag   Zahlungen und Vorschlag lesend, ohne Knöpfe, mit Hinweis; Zuordnen über die API 403
    Kunde ohne Proj. Hinweis statt Projektliste, Vorschlag „Erstattung buchen“ nicht (kein Guthaben)
    Monteurin        Kundenakte 403

Die Bilder (ganze Seite, 1440 px) nimmt die Übergabe der Runde neben die Vorlagen (reiter_*.png, uebersicht_dunkel.png,
zahlungen_buero_auftrag.png, kunde_ohne_projekt.png).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kundenakte.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_anmelden import DIALOGE, _klick, _tippen  # noqa: E402

REITER = ["uebersicht", "projekte", "objekte", "anfragen", "zahlungen", "dokumente", "kontakte", "verlauf"]
# schreibende Anfragen der Seite mitschneiden (Körper), um „nur Geändertes“ zu prüfen
MITSCHNITT = ("try{localStorage.setItem('erp_theme','light')}catch(e){}"  # Bilder hell (headless meldet sonst ein dunkles Schema)
              "window.__schreiben=[];const __f=window.fetch;window.fetch=(u,o={})=>{if(o.method&&o.method!=='GET'&&typeof o.body==='string')"
              "window.__schreiben.push({u:String(u),m:o.method,b:JSON.parse(o.body)});return __f(u,o)};")
BEREIT = "akte&&customer&&verlaufDaten&&customerPaymentsData&&document.getElementById('uProjekteListe').children.length>0"


def befuellen(db, k):
    from contextlib import contextmanager
    from datetime import date, datetime, time, timedelta, timezone
    from decimal import Decimal as D

    from app import berlin_time
    from app.auftragsstatus import status_aendern
    from app.berlin_time import berlin_today
    from app.crm import ensure_customer_profile
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, CustomerExtraInfo, Inquiry, Project, Property, Quote, QuoteItem, RoofArea
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id

    @contextmanager
    def am(tag):
        vorher = berlin_time._utc_now
        start = datetime.combine(tag, time(10, 0), tzinfo=berlin_time.BERLIN).astimezone(timezone.utc)
        berlin_time._utc_now = lambda: start
        try:
            yield
        finally:
            berlin_time._utc_now = vorher

    heute = berlin_today()
    vorjahr = date(heute.year - 1, 8, 1)
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    olga = AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", password_hash=k.passwort())
    mia = AppUser(username="mia", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Wohnbau Kessler GmbH", last_name="Wohnbau Kessler GmbH", street="Bahnhofstraße 12", postal_code="52511",
                     city="Geilenkirchen", phone="02451 55 01 20", email="info@kessler-wohnbau.example", is_consumer=False,
                     notes="Rechnungen immer mit Objektanschrift")
    maus = Customer(name="Hausverwaltung Maus", last_name="Hausverwaltung Maus", street="Markt 3", postal_code="52525", city="Heinsberg",
                    email="post@maus.example", is_consumer=False)
    db.add_all([fin, olga, mia, kunde, maus]); db.flush()
    ensure_customer_profile(db, kunde, category="Gewerbekunde", customer_number="K-10042")
    ensure_customer_profile(db, maus, category="Hausverwaltung", customer_number="K-10077")
    db.add_all([CustomerExtraInfo(customer_id=kunde.id, info_type="phone", label="Sabine Kessler, Geschäftsführung", value="0151 23 45 67 80"),
                CustomerExtraInfo(customer_id=kunde.id, info_type="phone", label="Jens Brandt, Hausverwaltung", value="02451 55 01 27"),
                CustomerExtraInfo(customer_id=kunde.id, info_type="info", label=None,
                                  value="Schlüssel beim Hausmeister, Zufahrt über den Hof ab 7 Uhr")])
    turm = Property(customer_id=kunde.id, name="Am Wasserturm 4", street="Am Wasserturm 4", postal_code="52531", city="Übach-Palenberg")
    linde = Property(customer_id=kunde.id, name="Lindenweg 7", street="Lindenweg 7", postal_code="52511", city="Geilenkirchen")
    db.add_all([turm, linde]); db.flush()
    db.add_all([RoofArea(property_id=turm.id, name=n, area_sqm=D(a)) for n, a in (("Hauptdach Süd", "180"), ("Hauptdach Nord", "160"),
                                                                                  ("Gaube", "12"))]
               + [RoofArea(property_id=linde.id, name=n, area_sqm=D(a)) for n, a in (("Garage", "54"), ("Carport", "30"))])
    db.add(Inquiry(inquiry_number="AN-2026-0031", customer_id=kunde.id, property_id=turm.id, title="Wartung Am Wasserturm 2–6",
                   status="termin_geplant"))
    db.commit()

    def projekt(nummer, name, prop, menge, preis):
        p = Project(project_number=nummer, name=name, customer_id=kunde.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(p); db.flush()
        q = Quote(quote_number="A-" + nummer[2:], project_id=p.id, title=name, vat_rate=D("19"))
        db.add(q); db.flush()
        db.add(QuoteItem(quote_id=q.id, position_number="1", short_text="Dacheindeckung", quantity=D(menge), unit="m2", unit_price=D(preis)))
        db.commit()
        return p, q

    def abschlag(order, netto, tag):
        with am(tag):
            inv = create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=D(netto))
            update_invoice_header(db, inv, service_period_start=tag - timedelta(days=20), service_period_end=tag)
            return finalize_and_send_invoice(db, inv)

    def zahlen(betrag, tag, inv=None, teil=None):
        with am(tag):
            return book_payment(db, customer_id=kunde.id, received_on=tag, amount=D(betrag), note=None,
                                lines=[Line(inv.id, zahlung=D(teil or betrag))] if inv is not None else [], user_name="Fin Finanzen")

    a, qa = projekt("P-2026-0118", "Dachsanierung Am Wasserturm 4", turm, "300", "100")
    with am(vorjahr):
        auftrag_a = create_order_from_quote(db, qa.id, order_date=vorjahr, execution_start=None, execution_end=None,
                                            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    a1 = abschlag(auftrag_a, "2400", vorjahr + timedelta(days=5))
    rest = zahlen("3000", vorjahr + timedelta(days=17), a1, "2856")
    a2 = abschlag(auftrag_a, "10000", heute - timedelta(days=40))
    a3 = abschlag(auftrag_a, "5000", heute - timedelta(days=20))
    zahlen("5950", heute - timedelta(days=15), a3)
    b, qb = projekt("P-2026-0131", "Flachdach Garage Lindenweg 7", linde, "179", "50")
    qb.status = "versendet"
    qb.email_sent_at = datetime.combine(heute - timedelta(days=17), time(12, 10))
    db.commit()
    c, qc = projekt("P-2025-0064", "Sturmschaden Lindenweg 7", linde, "10", "80")
    with am(heute - timedelta(days=60)):
        auftrag_c = create_order_from_quote(db, qc.id, order_date=heute - timedelta(days=60), execution_start=None, execution_end=None,
                                            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
        status_aendern(db, auftrag_c.id, "storniert", "Versicherung zahlt nicht", user_name="Fin Finanzen")
    objekte = len(list(db.query(Property).filter(Property.customer_id == kunde.id)))
    return {"kunde": kunde.id, "maus": maus.id, "a": a.id, "a2": a2.id, "a2_nr": a2.invoice_number, "rest": rest.id, "objekte": objekte,
            "rest_tag": (vorjahr + timedelta(days=17)).strftime("%d.%m.%Y"), "faellig_a2": a2.due_date.strftime("%d.%m.%Y"),
            "cookies": {"fin": k.cookies(fin), "olga": k.cookies(olga), "mia": k.cookies(mia)}}


async def _bild_ganz(tab, name: str):
    """Die ganze Seite als PNG (über das Fenster hinaus)."""
    m = await tab.cmd("Page.getLayoutMetrics")
    groesse = m.get("cssContentSize") or m["contentSize"]
    breite, hoehe = int(groesse["width"]), int(min(groesse["height"], 6000))
    data = (await tab.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                          clip={"x": 0, "y": 0, "width": breite, "height": hoehe, "scale": 1}))["data"]
    (tab.shots / f"{name}.png").write_bytes(base64.b64decode(data))


async def _reiter(tab, name):
    await _klick(tab, f'.reiter a[data-reiter="{name}"]')
    await tab.warten(f"document.getElementById('reiter-{name}').hidden===false")
    await tab.js("window.scrollTo(0,0)")


def _text(js):
    return f"({js}).replace(/\\u00a0/g,' ')"


def _nb(wert):
    """Geschützte Leerzeichen (Beträge) als Leerzeichen -- auch in Listen."""
    if isinstance(wert, str):
        return wert.replace(" ", " ")
    if isinstance(wert, list):
        return [_nb(w) for w in wert]
    return wert


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE + MITSCHNITT)
    k, nr = seed["kunde"], seed["a2_nr"]

    # --- Büro – Auftrag: Zahlungen lesend ---
    await tab.anmelden(seed["cookies"]["olga"])
    await tab.fenster(1440, 1240)
    await tab.oeffnen(f"/customers/{k}#zahlungen", BEREIT)
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Büro – Auftrag: Reiter Zahlungen aus dem Anker", await tab.js("document.getElementById('reiter-zahlungen').hidden"), False)
    p.pruefe("Büro – Auftrag: keine Knöpfe an Eingängen und Vorschlag, Hinweis da", await tab.js(
        "[document.querySelectorAll('#customerPayments button').length,document.querySelectorAll('#zVorschlaege button').length,"
        "document.querySelectorAll('#uGeldHinweis button').length,!!document.querySelector('[data-geld-nur-lesen]'),"
        "document.getElementById('zVorschlaege').textContent.includes('Auf die unbezahlte')]"), [0, 0, 0, True, True])
    p.pruefe("Büro – Auftrag: Zuordnen über die API 403", await tab.js(
        f"fetch('/api/payments/{seed['rest']}/allocations',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{lines:[{{invoice_id:{seed['a2']},zahlung:'144.00'}}]}})}}).then(r=>r.status)"), 403)
    await _bild_ganz(tab, "zahlungen_buero_auftrag")
    p.pruefe("Büro – Auftrag: JS-Fehler", tab.fehler, [])

    # --- Büro – Finanzen: Kopf und Übersicht ---
    await tab.anmelden(seed["cookies"]["fin"])
    await tab.oeffnen(f"/customers/{k}", BEREIT)
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Kopf: Pfad, Titel, Kennung, Kategorie", await tab.js(
        "[[...document.querySelectorAll('#seitenkopfPfad a, #seitenkopfPfad span:not(.ds-kopf-trenner)')].map(e=>e.textContent),"
        "document.getElementById('seitenkopfTitel').textContent,document.getElementById('seitenkopfKennung').textContent,"
        "document.getElementById('seitenkopfStatus').textContent,document.getElementById('seitenkopfStatus').className]"),
        [["Stammdaten", "Kunden", "Wohnbau Kessler GmbH"], "Wohnbau Kessler GmbH", "K-10042", "Gewerbekunde", "ds-status ds-status-info"])
    p.pruefe("Kopf: Anschrift, Telefon und E-Mail als Link", await tab.js(
        "[document.getElementById('seitenkopfUntertitel').textContent,[...document.querySelectorAll('#seitenkopfUntertitel a')].map(a=>a.getAttribute('href'))]"),
        ["Bahnhofstraße 12, 52511 Geilenkirchen · 02451 55 01 20 · info@kessler-wohnbau.example",
         ["tel:02451550120", "mailto:info@kessler-wohnbau.example"]])
    p.pruefe("Hauptaktion „+ Projekt“", await tab.js("document.getElementById('newProjectLink').textContent"), "+ Projekt")
    p.pruefe("Zähler an den Reitern", await tab.js(
        "['zahlProjekte','zahlObjekte','zahlAnfragen','zahlDokumente','zahlKontakte'].map(i=>document.getElementById(i).hidden?'':document.getElementById(i).textContent)"),
        ["3", str(seed["objekte"]), "1", "", "3"])
    projekte = await tab.js(_text("document.getElementById('uProjekteListe').innerText"))
    p.pruefe("Übersicht: Projekt A mit abgerechnet und unbezahlt", ["P-2026-0118 · Dachsanierung Am Wasserturm 4" in projekte,
             "abgerechnet 17.400,00 € · unbezahlt 11.900,00 €" in projekte], [True, True])
    p.pruefe("Übersicht: Projekt B als Angebot", ["8.950,00 € netto" in projekte, "noch nicht beauftragt" in projekte], [True, True])
    p.pruefe("Übersicht: Abgeschlossen", await tab.js(_text("document.getElementById('uAbgeschlossen').textContent")),
             "Abgeschlossen: P-2025-0064 Sturmschaden Lindenweg 7")
    geld = await tab.js(_text("document.getElementById('uGeld').innerText"))
    p.pruefe("Übersicht: Geld", ["11.900,00 €" in geld, f"überfällig seit {seed['faellig_a2']}" in geld, "144,00 €" in geld,
                                 f"Rest einer Zahlung vom {seed['rest_tag']}" in geld, f"auf {nr} zuordnen" in geld], [True] * 5)
    p.pruefe("Übersicht: Stammdaten lesend", await tab.js(_text(
        "[...document.querySelectorAll('#stammdatenListe dt')].map(e=>e.textContent).join(', ')")),
        "Kundennummer, Kategorie, Verbraucher, Zahlungsbedingung, Rechnungen an, Interne Notiz")
    await _bild_ganz(tab, "reiter_uebersicht")

    # --- jeder Reiter per Klick ---
    for name in REITER[1:]:
        await _reiter(tab, name)
        p.pruefe(f"Reiter {name} sichtbar, Anker", await tab.js(
            f"[REITER.filter(r=>!document.getElementById('reiter-'+r).hidden),location.hash]"), [[name], f"#{name}"])
        if name not in ("zahlungen", "verlauf"):
            await _bild_ganz(tab, f"reiter_{name}")

    # --- Zahlungen: „⋮“ eines Eingangs, Erstatten, Zurücknehmen, Zuordnen über den Vorschlag ---
    await _reiter(tab, "zahlungen")
    zeile = f'tr[data-zahlung="{seed["rest"]}"]'
    p.pruefe("Eingang mit Rest", await tab.js(_text(f"document.querySelector('{zeile} [data-rest]').textContent")), "Rest 144,00 €")
    await _bild_ganz(tab, "reiter_zahlungen")  # mit Rest und Vorschlag, neben der Vorlage
    await _klick(tab, f"{zeile} .menue-anker button")
    p.pruefe("„⋮“: Einträge und Trennlinie", await tab.js(
        f"(()=>{{const m=document.querySelector('{zeile} .ds-menue');return [m.hidden,[...m.children].filter(e=>!e.hidden).map(e=>e.classList.contains('ds-menue-trenner')?'—':e.textContent)]}})()"),
        [False, ["Zuordnen …", "Erstatten …", "—", "Zurücknehmen …"]])
    await _bild_ganz(tab, "zahlungen_menue")
    await _klick(tab, f'{zeile} [data-klick="zahlung-erstatten"]')
    await tab.warten("document.getElementById('erstattenDialog').open")
    p.pruefe("Dialog Erstatten: Zeile des Rests vorbelegt", await tab.js(
        "[...document.querySelectorAll('#erstattenZeilen input')].map(i=>i.value)"), ["144,00"])
    await _klick(tab, '#erstattenDialog [data-klick="dialog-zu"]')
    await _klick(tab, f"{zeile} .menue-anker button")
    await _klick(tab, f'{zeile} [data-klick="zahlung-zuruecknehmen"]')
    await tab.warten("document.getElementById('zuruecknehmenDialog').open")
    p.pruefe("Dialog Zurücknehmen: Begründung und Knopf", await tab.js(
        "[document.getElementById('zuruecknehmenFeld').hidden,document.getElementById('zuruecknehmenKnopf').hidden]"), [False, False])
    await _klick(tab, '#zuruecknehmenDialog [data-klick="dialog-zu"]')
    await _klick(tab, '#zVorschlaege [data-klick="vorschlag-zuordnen"]')
    await tab.warten("document.getElementById('zuordnenDialog').open")
    p.pruefe("Dialog Zuordnen: Rechnung und Betrag vorbelegt", await tab.js(
        "[Number(document.getElementById('restInvoice').value),document.getElementById('restAmount').value]"), [seed["a2"], "144,00"])
    await _bild_ganz(tab, "dialog_zuordnen")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('zuordnenKnopf').click()", "#customerPayments")
    await tab.warten("!document.getElementById('zuordnenDialog').open&&akte.vorschlaege.length===0")
    p.pruefe("Zugeordnet: Rest weg, Vorschlag weg, unbezahlt kleiner", _nb(await tab.js(
        f"[document.getElementById('customerPaymentsStatus').textContent,!!document.querySelector('{zeile} [data-rest]'),"
        "document.getElementById('zVorschlaege').children.length,document.getElementById('zKacheln').innerText.includes('11.756,00')]")),
        ["Zugeordnet.", False, 0, True])
    await _bild_ganz(tab, "zahlungen_zugeordnet")

    # --- Stammdaten im Dialog ---
    await _reiter(tab, "uebersicht")
    await _klick(tab, '#uStammdaten [data-klick="stammdaten-bearbeiten"]')
    await tab.warten("document.getElementById('stammdatenDialog').open")
    await _tippen(tab, "#phone", "02451 55 01 99")
    await tab.js("render()")
    p.pruefe("Dialog: Eingabe bleibt beim Neuzeichnen", await tab.js("document.getElementById('phone').value"), "02451 55 01 99")
    await _bild_ganz(tab, "dialog_stammdaten")
    vorher = await tab.js("window.__schreiben.length")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"stammdaten-speichern\"]').click()", "#stammdatenListe")
    await tab.warten("!document.getElementById('stammdatenDialog').open")
    p.pruefe("Dialog: gesendet nur das Telefon", await tab.js(f"window.__schreiben.slice({vorher}).map(s=>[s.m,s.b])"),
             [["PUT", {"phone": "02451 55 01 99"}]])
    p.pruefe("Kopf: neue Nummer als Link", await tab.js("[...document.querySelectorAll('#seitenkopfUntertitel a')].map(a=>a.getAttribute('href'))[0]"),
             "tel:02451550199")

    # --- Verlauf mit der Änderung und der Zuordnung ---
    await _reiter(tab, "verlauf")
    await tab.warte_auf_neu_geladene_liste()
    verlauf = await tab.js(_text("document.getElementById('verlaufListe').innerText"))
    p.pruefe("Verlauf: Stammdaten und Zahlung", ["Fin Finanzen" in verlauf, "Zahlung" in verlauf, "Kunde" in verlauf], [True, True, True])
    await _bild_ganz(tab, "reiter_verlauf")

    # --- „⋮“ des Kopfs: Kunde · Wege ---
    await _reiter(tab, "uebersicht")
    await _klick(tab, "#seitenkopfMenueKnopf")
    p.pruefe("„⋮“ des Kopfs: zwei Gruppen", await tab.js(
        "[...document.getElementById('seitenkopfMenue').children].filter(e=>!e.hidden).map(e=>e.classList.contains('ds-menue-trenner')?'—':e.textContent)"),
        ["Stammdaten bearbeiten", "+ Objekt", "+ Eintrag in „Kontakte & Kundenwissen“", "Neue Anfrage", "—", "Versandprotokoll des Kunden",
         "Ganze Änderungshistorie"])
    await _bild_ganz(tab, "kopf_menue")
    await _klick(tab, "#seitenkopfMenueKnopf")

    # --- dunkel ---
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await _bild_ganz(tab, "uebersicht_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")

    # --- 412 px ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/master-data", "document.readyState==='complete'")
    await tab.oeffnen(f"/customers/{k}", BEREIT)
    for name in REITER:
        await _reiter(tab, name)
        # gegen die Breite des Geräts gemessen: innerWidth wächst in der Mobil-Emulation mit dem Inhalt mit
        p.pruefe(f"412 px {name}: nichts ragt über den Bildschirm", await tab.js(
            "[document.documentElement.scrollWidth<=412,[...document.querySelectorAll('main .menue-anker,main .karte')]"
            ".filter(e=>e.offsetParent!==null&&e.getBoundingClientRect().right>412).length]"), [True, 0])
    await _reiter(tab, "zahlungen")
    await _bild_ganz(tab, "zahlungen_412")
    await tab.fenster(1440, 1240)

    # --- „⋮“ der Akte: Status · Projekt · Wege ---
    await tab.oeffnen(f"/projects/{seed['a']}", "akte&&project&&order")
    await _klick(tab, "#seitenkopfMenueKnopf")
    gruppen = await tab.js(
        "(()=>{const g=[[]];for(const e of document.getElementById('seitenkopfMenue').children){if(e.hidden)continue;"
        "if(e.classList.contains('ds-menue-trenner'))g.push([]);else g[g.length-1].push(e.textContent)}return g})()")
    p.pruefe("„⋮“ der Akte: drei Gruppen", [len(gruppen), "Stornieren …" in gruppen[0], "Projekt bearbeiten" in gruppen[1],
                                          "Arbeitsvorbereitung" in gruppen[-1]], [3, True, True, True])
    await _bild_ganz(tab, "akte_menue")

    # --- Kunde ohne Projekt ---
    await tab.oeffnen(f"/customers/{seed['maus']}", "akte&&customer&&verlaufDaten")
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Kunde ohne Projekt", _nb(await tab.js(
        "[document.getElementById('uProjekteListe').textContent,document.getElementById('zahlProjekte').hidden,document.getElementById('uGeldHinweis').children.length]")),
        ["Noch kein Projekt – „+ Projekt“ legt eines an.", True, 0])
    await _bild_ganz(tab, "kunde_ohne_projekt")
    p.pruefe("Büro – Finanzen: JS-Fehler", tab.fehler, [])

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["mia"])
    p.pruefe("Monteurin: Kundenakte 403", await tab.js(f"fetch('/customers/{k}').then(r=>r.status)"), 403)


if __name__ == "__main__":
    raise SystemExit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
