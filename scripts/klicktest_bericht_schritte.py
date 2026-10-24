"""Klicktest: der Einsatzbericht in fünf Schritten (1.9.67, Stufe 4, R4 Fortsetzung).

Befüllt: Monteurin Mia (in der Planung des Auftrags, heute eingeplant), Admin Anna; Objekt „Halle Nord“ mit zwei Dachflächen (Flachdach),
Prüfvorlage mit je einem Punkt jeder Art (OK/Nicht OK/Entfällt, Gully mit Bauteil, Zustand 1–4, Messwert mit Soll, Menge, Dichtheit, Freitext,
Foto-Punkt, Vorher/Nachher); Berichte der Monteurin: Wartung über beide Flächen (danach ein zweiter Gully -> „1 Prüfpunkt ergänzt“), Rapport
ohne Vorlage, ein leerer Rapport; Katalogmaterial „Dichtband“, Betriebsmittel „Kran“, eine Zeit der Monteurin heute.

    Eingänge          „Heute“ -> „Weiter“ am Bericht landet auf /service-reports/{id}; /orders/{id}/service-reports?report={id} ebenso;
                      „+ Bericht“ auf der Auftragsseite legt an und öffnet den neuen Bericht.
    Auftragsseite     Monteurin: keine Buchungskarte, „Zeit nachtragen“ -> /mobil/zeiten?order_id=…; Büro: Buchungskarte unverändert.
    Kopf              Pfad Heute / Auftrag / Art, Status, „⋮“ mit Datum ändern, Art ändern, Prüfpunkte neu erzeugen, Löschen (rot).
    Funktionen        jede Funktion der bisherigen Berichtsseite im passenden Schritt erreichbar (Liste aus dem Befund R4).
    Schritt 1         „Nicht OK“ öffnet den Befund direkt darunter, „Noch offen“ sofort aktuell; Befund anlegen -> „Foto fehlt“, Foto über
                      „Aus Galerie“ -> Eintrag weg; Foto löschen 48 px mit Rückfrage; Bemerkung tippen -> nach dem Speichern Fokus und Text
                      im Feld; ein Segmentknopf behält nach dem Speichern den Fokus.
    Schritte 2–4      Befund-Status ändern, Material aus dem Katalog erfassen, Menge ändern, löschen mit Rückfrage, Betriebsmittel mit Notiz.
    Schritt 5         „Das steht im Bericht“, „Zeiten am <heute>“, Zeichenflächen ≥ 160 px, „Bericht abschließen“ gesperrt mit „Fehlt: …“.
    Rapport ohne      Schritt 1 „Arbeiten“ mit der Beschreibung, „Noch offen“ nennt sie und sperrt; ausgefüllt -> nichts offen,
    Vorlage           unterschrieben über beide Flächen -> „Unterschrieben“, PDF im Menü.
    Art               leerer Rapport -> Wartung (Schritt 1 „Prüfpunkte“ mit Punkten); nach einer Antwort gesperrt mit Hinweis.
    Datum, Löschen    Datum ändern im Dialog; Löschen mit Rückfrage -> zurück auf die Auftragsseite.
    48 px             jedes Ziel der Seite (Schritte, Inhalt, „Noch offen“, Dialoge) ≥ 48 px hoch, quer (1280 × 620) und hoch (800 × 1100);
                      hoch eine Spalte, Schritte als Zeile mit Bildlauf, „Noch offen“ unten fest.

Feste Uhr 10:00 (die Monteurin öffnet /mobil).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_bericht_schritte.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

QUER, HOCH = (1280, 620), (800, 1100)
BEREIT = "document.getElementById('raster')&&!document.getElementById('raster').hidden&&typeof SCHRITT!=='undefined'&&SCHRITT"
GEZEICHNET = "(()=>{const z=document.querySelector('#schritte .schritt');return !!z})()"


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal
    from io import BytesIO

    from PIL import Image

    from app.berlin_time import berlin_today
    from app.inspection_templates import create_template, create_template_item
    from app.models import (
        AppUser, Customer, Employee, Material, Order, OrderItem, PlanningSlot, Project, Property, Team, TeamEmployee,
        WorkPreparationEmployee, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
    )
    from app.operational_assets import create_asset
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.roof_areas import create_roof_area, create_roof_component
    from app.service_reports import create_report
    from app.time_tracking import start_timer, stop_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    benutzer = {"mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
                "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())}
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()
    nord = create_roof_area(db, halle.id, "Dachfläche Nord", roof_type="Flachdach")
    sued = create_roof_area(db, halle.id, "Dachfläche Süd", roof_type="Flachdach")
    create_roof_component(db, nord["id"], "Gully 1", component_type="Gully", sort_order=10)
    vorlage = create_template(db, "Flachdach-Wartung", roof_type="Flachdach")
    t = vorlage["id"]
    create_template_item(db, t, "Zugang und Absturzsicherung geprüft", "ja_nein", group_name="Allgemein", required=True, sort_order=10)
    create_template_item(db, t, "Gesamtzustand Dachfläche", "condition_grade", group_name="Allgemein", required=True, sort_order=20)
    create_template_item(db, t, "Ablauf frei und funktionsfähig", "ja_nein", group_name="Entwässerung", component_type="Gully",
                         required=True, sort_order=30)
    create_template_item(db, t, "Feuchte Dämmung", "measurement", group_name="Fläche", target_min=Decimal("0"), target_max=Decimal("12"),
                         unit="%", sort_order=40)
    create_template_item(db, t, "Kies nachgefüllt", "quantity", group_name="Fläche", unit="kg", sort_order=50)
    create_template_item(db, t, "Dichtheitsprüfung", "leak_test", group_name="Abschluss", sort_order=60)
    create_template_item(db, t, "Anschluss Attika", "ja_nein", group_name="Abschluss", photo_before_after=True, sort_order=70)
    create_template_item(db, t, "Übersichtsfoto", "photo", group_name="Abschluss", sort_order=80)
    create_template_item(db, t, "Bemerkungen", "free_text", group_name="Abschluss", sort_order=90)

    projekt = Project(project_number="P-KT-BS", name="Wartung Halle Nord", customer_id=kunde.id, property_id=halle.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-BS", project_id=projekt.id, source_quote_id=901, quote_number_snapshot="A-KT-BS",
                    title="Wartung Halle Nord", customer_name=kunde.name, property_name=halle.name,
                    property_address="Werkstr. 5\n52531 Übach-Palenberg")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Wartung", quantity=Decimal("1"), unit="psch",
                     unit_price=Decimal("1")))
    db.commit()
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    db.add(TeamEmployee(team_id=team.id, employee_id=mia.id))
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=mia.id, employee_name_snapshot="Mia"))
    db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=heute, end_date=heute + timedelta(days=1)))
    db.add(Material(name="Dichtband Butyl", unit="m", article_number="DB-100", purchase_price=Decimal("4.20")))
    db.commit()
    create_asset(db, {"name": "Kran 40t", "selectable_in_reports": True})

    wartung = create_report(db, auftrag.id, "wartung", performed_at=heute, roof_area_ids=[nord["id"], sued["id"]],
                            created_by_employee_id=mia.id)
    create_roof_component(db, nord["id"], "Gully 2", component_type="Gully", sort_order=20)  # -> „1 Prüfpunkt ergänzt“ beim Öffnen
    rapport = create_report(db, auftrag.id, "rapport", performed_at=heute, roof_area_ids=[nord["id"]], created_by_employee_id=mia.id)
    leer = create_report(db, auftrag.id, "rapport", performed_at=heute, created_by_employee_id=mia.id)
    zeit = start_timer(db, employee_id=mia.id, order_id=auftrag.id, started_at=datetime.combine(heute, time(7)), activity="Wartung")
    stop_timer(db, zeit.id, ended_at=datetime.combine(heute, time(9, 30)))
    puffer = BytesIO()
    Image.new("RGB", (60, 40), (40, 120, 200)).save(puffer, format="PNG")
    return {"auftrag": auftrag.id, "wartung": wartung["id"], "rapport": rapport["id"], "leer": leer["id"], "heute": heute.isoformat(),
            "heute_de": f"{heute:%d.%m.%Y}", "foto_png": puffer.getvalue().hex(),
            "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


async def _bild(tab, name: str, theme: str = "light") -> None:
    """Bild der Seite von oben, im angegebenen Theme (die Vorgabe des Browsers im Klicktest ist dunkel)."""
    await tab.js(f"document.documentElement.setAttribute('data-theme','{theme}');window.scrollTo(0,0);true")
    await tab.bild(name)


async def _schritt(tab, key: str) -> None:
    await tab.js(f"document.getElementById('schritt-{key}').click()")
    await tab.warte_auf_ruhe()


def _offen() -> str:
    return "[...document.querySelectorAll('#offenListe li')].map(l=>l.textContent)"


# Was ein Ziel ist: Knöpfe, Links als Knopf, Felder, Schritte und Segmente in Inhalt, „Noch offen“, Schritten und offenen Dialogen; der
# Seitenkopf hat eigene Maße (Variante tablet, tests/test_v457_monteursseiten.py), seine Pfadglieder sind Text.
ZU_KLEIN = ("(()=>{const sichtbar=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};"
            "const wurzeln=['#schritte','#raster','#abschlussLeiste','dialog[open]'].flatMap(s=>[...document.querySelectorAll(s)]);"
            "const ziele=wurzeln.flatMap(w=>[...w.querySelectorAll('button,a.knopf,input:not([type=file]),select,textarea,.segment,.schritt')]);"
            "return [...new Set(ziele)].filter(sichtbar).map(e=>[e.id||e.dataset.klick||e.className||e.tagName,Math.round(e.getBoundingClientRect().height)])"
            ".filter(([,h])=>h<48)})()")


# Seit 1.9.72 (R4 Nachrunde, Punkt 1): Schritt 5 hat unten eine feste Leiste -- von oben (ohne Bildlauf) sind „Bericht abschließen“ und
# „Fehlt: …“ im Bild, der Knopf nicht verdeckt, beide Zeichenflächen auf der Seite und die Seite länger als das Fenster (sonst bewiese die
# Prüfung nichts).
LEISTE_IM_BILD = ("(()=>{window.scrollTo(0,0);const k=document.getElementById('abschliessenKnopf'),f=document.getElementById('fehltText'),"
                  "r=k.getBoundingClientRect();return [Math.round(scrollY),r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth,"
                  "document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)===k,f.getBoundingClientRect().bottom<=innerHeight,"
                  "!!document.getElementById('padMonteur')&&!!document.getElementById('padKunde'),"
                  "document.documentElement.scrollHeight>innerHeight+50]})()")
LEISTE_SOLL = [0, True, True, True, True, True]

# Seit 1.9.72 (Punkt 3): „⋮“ eines Prüfpunkts steht in seiner Titelzeile -- rechts neben dem Text, auf Höhe seiner ersten Zeile, auch bei
# Bewertungen (die Eingabe darunter über die ganze Breite). Ergebnis: [Punkte außerhalb der Titelzeile, Zahl der geprüften Bewertungen]
MENUE_IN_TITELZEILE = ("(()=>{const geprueft=PUNKTE.filter(p=>['condition_grade','ja_nein','leak_test','measurement','quantity'].includes(p.item_type)"
                       "&&document.getElementById('punkt-menue-knopf-'+p.id));"
                       "const falsch=geprueft.filter(p=>{const m=document.getElementById('punkt-menue-knopf-'+p.id).getBoundingClientRect(),"
                       "t=document.querySelector('#punkt-kopf-'+p.id+' .punkt-text').getBoundingClientRect();"
                       "return !(m.top<t.top+30&&m.bottom>t.top&&m.left>=t.right-1)}).map(p=>p.item_type+': '+p.text);"
                       "return [falsch,geprueft.filter(p=>p.item_type==='condition_grade').length>0]})()")


async def _alle_schritte_messen(tab) -> list:
    zu_klein = []
    for key in await tab.js("schritte().map(s=>s.key)"):
        await _schritt(tab, key)
        zu_klein += [[key, *z] for z in await tab.js(ZU_KLEIN)]
    return zu_klein


async def pruefen(tab, seed, p):
    a, w, r, leer = seed["auftrag"], seed["wartung"], seed["rapport"], seed["leer"]
    foto = tab.shots / "foto.png"
    foto.write_bytes(bytes.fromhex(seed["foto_png"]))
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(*QUER, mobil=True)

    # --- Eingänge -----------------------------------------------------------------------------------------------------------------
    await tab.oeffnen("/mobil", f"document.querySelector('[data-bericht=\"{w}\"] a')")
    p.pruefe("Heute: „Weiter“ am Bericht führt zur Berichtsseite",
             await tab.js(f"document.querySelector('[data-bericht=\"{w}\"] a').getAttribute('href')"), f"/service-reports/{w}")
    await tab.oeffnen(f"/orders/{a}/service-reports?report={w}", BEREIT)
    p.pruefe("?report= landet auf /service-reports/{id}", await tab.js("location.pathname"), f"/service-reports/{w}")

    # --- Kopf und Schritte --------------------------------------------------------------------------------------------------------
    p.pruefe("Kopf: Pfad Heute / Auftrag / Art, Status Entwurf",
             await tab.js("[[...document.querySelectorAll('#seitenkopfPfad a, #seitenkopfPfad span:not(.ds-kopf-trenner)')].map(x=>x.textContent),"
                          "document.getElementById('seitenkopfStatus').textContent]"),
             [["Heute", "AUF-KT-BS", "Wartungsbericht"], "Entwurf"])
    p.pruefe("Kopf: „⋮“ mit Datum, Art, Prüfpunkte neu, Löschen (rot), ohne PDF",
             await tab.js("['menueDatum','menueArt','menueNeu','menuePdf','menueLoeschen'].map(i=>!document.getElementById(i).hidden)"
                          ".concat(document.getElementById('menueLoeschen').classList.contains('ds-menue-eintrag-fehler'))"),
             [True, True, True, False, True, True])
    p.pruefe("Fünf Schritte", await tab.js("[...document.querySelectorAll('#schritte .schritt')].map(s=>s.textContent.replace(/^\\d/,''))"),
             ["Prüfpunkte", "Befunde", "Material", "Betriebsmittel", "Unterschrift"])
    p.pruefe("Hinweis: Prüfpunkte für neu erfasste Bauteile ergänzt",
             await tab.js("document.getElementById('schrittInhalt').textContent.includes('1 Prüfpunkt für neu erfasste Bauteile ergänzt')"), True)
    # seit 1.9.70: zwei Flächen mit gleichem Pflichtpunkt -> zwei verschiedene Zeilen mit der Fläche, keine Zeile doppelt
    p.pruefe("„Noch offen“: derselbe Pflichtpunkt je Fläche, keine zwei gleichen Zeilen", await tab.js(
        f"(l=>[l.filter(t=>t.startsWith('Pflichtpunkt „Zugang und Absturzsicherung geprüft“')),l.length===new Set(l).size])({_offen()})"),
        [["Pflichtpunkt „Zugang und Absturzsicherung geprüft“ beantworten · Dachfläche Nord",
          "Pflichtpunkt „Zugang und Absturzsicherung geprüft“ beantworten · Dachfläche Süd"], True])

    # --- jede Funktion der bisherigen Seite erreichbar ------------------------------------------------------------------------------
    erreichbar = {}
    erreichbar["pruefpunkte"] = await tab.js(
        "(()=>{const q=s=>!!document.querySelector(s);return {"
        "antworten:q('.segment[data-wert=ok]')&&q('.segment[data-wert=nok]')&&q('.segment[data-wert=na]'),"
        "dichtheit:q('input[id^=dauer-]'),zustand:q('.segment[data-feld=condition_grade][data-wert=\"4\"]'),"
        "messwert:q('input[id^=wert-]')&&document.getElementById('schrittInhalt').textContent.includes('Soll:'),"
        "menge:q('input[id^=menge-]'),freitext:q('textarea[id^=text-]'),"
        "fotopunkt:document.getElementById('schrittInhalt').textContent.includes('Übersichtsfoto'),"
        "bemerkung:q('[data-klick=bemerkung]'),foto_aufnehmen:q('[data-klick=foto-aufnehmen]'),foto_galerie:q('[data-klick=foto-galerie]'),"
        "vorher_nachher:document.querySelectorAll('.foto-platz').length>=2,punkt_neu:q('[data-klick=punkt-neu]'),"
        "stand:q('#punkteZaehler'),beschreibung:q('#beschreibung'),flaechen:document.querySelectorAll('h3.gruppe').length>=2}})()")
    await _schritt(tab, "befunde")
    erreichbar["befunde"] = await tab.js("({ohne_pruefpunkt:!!document.querySelector('#befundOhnePunkt [data-klick=befund-anlegen]')})")
    await _schritt(tab, "material")
    erreichbar["material"] = await tab.js(
        "['matSuche','matTreffer','matBezeichnung','matMenge','matEinheit','matFlaeche'].map(i=>!!document.getElementById(i))"
        ".concat(!!document.querySelector('[data-klick=material-neu]'))")
    await _schritt(tab, "betriebsmittel")
    erreichbar["betriebsmittel"] = await tab.js("['bmWahl','bmNotiz'].map(i=>!!document.getElementById(i))")
    await _schritt(tab, "unterschrift")
    erreichbar["unterschrift"] = await tab.js(
        "['signMonteurName','signKundeName','padMonteur','padKunde','abschliessenKnopf'].map(i=>!!document.getElementById(i))"
        ".concat(document.getElementById('schrittInhalt').textContent.includes('Zeiten am '),!!document.getElementById('offenListe'))")
    p.pruefe("Funktionen erreichbar: Prüfpunkte", erreichbar["pruefpunkte"],
             {k: True for k in ("antworten", "dichtheit", "zustand", "messwert", "menge", "freitext", "fotopunkt", "bemerkung", "foto_aufnehmen",
                                "foto_galerie", "vorher_nachher", "punkt_neu", "stand", "beschreibung", "flaechen")})
    p.pruefe("Funktionen erreichbar: Befunde, Material, Betriebsmittel, Unterschrift",
             [erreichbar["befunde"], erreichbar["material"], erreichbar["betriebsmittel"], erreichbar["unterschrift"]],
             [{"ohne_pruefpunkt": True}, [True] * 7, [True, True], [True] * 7])

    # --- Schritt 1: Nicht OK -> Befund darunter, Noch offen sofort aktuell -------------------------------------------------------------
    await _schritt(tab, "pruefpunkte")
    gully = await tab.js("PUNKTE.find(p=>p.text.startsWith('Gully 1')).id")
    await tab.js(f"(b=>{{b.focus();b.click()}})(document.getElementById('seg-{gully}-nok'))")  # wie ein Tipp: Fokus, dann Klick
    await tab.warten(f"!!document.getElementById('befund-form-p{gully}')")
    p.pruefe("„Nicht OK“: Befund direkt unter dem Punkt, „Noch offen“ nennt ihn",
             [await tab.js(f"document.getElementById('punkt-befund-{gully}').contains(document.getElementById('befund-form-p{gully}'))"),
              await tab.js(f"{_offen()}.some(t=>t.startsWith('Befund zum Prüfpunkt „Gully 1'))")],
             [True, True])
    p.pruefe("Segmentknopf behält nach dem Speichern den Fokus", await tab.js("document.activeElement.id"), f"seg-{gully}-nok")
    await tab.js(f"document.getElementById('befund-text-p{gully}').value='Gully verstopft, Laub'")
    await tab.js(f"document.querySelector('#befund-form-p{gully} [data-klick=befund-anlegen]').click()")
    await tab.warten("BEFUNDE.length===1&&!!document.querySelector('.befund-box')")
    await tab.warte_auf_ruhe()
    p.pruefe("Befund angelegt: „Foto fehlt“, Noch offen: Foto zum Befund",
             [await tab.js("document.querySelector('.befund-box .befund-stand').textContent"),
              await tab.js(f"{_offen()}.some(t=>t==='Foto zum Befund „Gully verstopft, Laub“ aufnehmen · Dachfläche Nord')")],
             ["Foto fehlt", True])
    befund = await tab.js("BEFUNDE[0].id")
    await tab.js(f"document.querySelector('#befund-box-{befund} [data-klick=foto-galerie]').click()")
    await _datei_setzen(tab, "#fotoGalerie", str(foto))
    await tab.warten(f"FOTOS.some(f=>f.finding_id==={befund})")
    await tab.warte_auf_ruhe()
    p.pruefe("Foto aus der Galerie: am Befund, Eintrag unter „Noch offen“ weg",
             [await tab.js(f"document.querySelector('#befund-box-{befund} .befund-stand').textContent"),
              await tab.js(f"{_offen()}.some(t=>t.startsWith('Foto zum Befund'))")], ["1 Foto", False])
    p.pruefe("Foto: „Aufnehmen“ öffnet die Kamera (capture), „Aus Galerie“ die Dateiauswahl",
             await tab.js("[document.getElementById('fotoKamera').getAttribute('capture'),document.getElementById('fotoGalerie').hasAttribute('capture')]"),
             ["environment", False])
    # Foto löschen: Fotos am Punkt Anschluss Attika (Vorher) -- aus der Galerie, dann löschen mit Rückfrage
    attika = await tab.js("PUNKTE.find(p=>p.text==='Anschluss Attika').id")
    await tab.js(f"document.querySelector('#punkt-zusatz-{attika} [data-klick=foto-galerie][data-art=vorher]').click()")
    await _datei_setzen(tab, "#fotoGalerie", str(foto))
    await tab.warten(f"FOTOS.some(f=>f.inspection_item_id==={attika}&&f.kind==='vorher')")
    await tab.warte_auf_ruhe()
    loesch = await tab.js(f"(()=>{{const b=document.querySelector('#punkt-zusatz-{attika} [data-klick=foto-loeschen]');const r=b.getBoundingClientRect();"
                          "return [Math.round(r.width),Math.round(r.height),b.id]})()")
    p.pruefe("Foto löschen: 48 × 48 px", loesch[:2], [48, 48])
    await tab.js(f"document.getElementById('{loesch[2]}').click()")
    await tab.warten("document.getElementById('rueckfrageDialog').open")
    p.pruefe("Foto löschen fragt zurück", await tab.js("document.getElementById('rueckfrageText').textContent"),
             "Dieses Foto aus dem Bericht löschen?")
    await tab.js("document.getElementById('rueckfrageJa').click()")
    await tab.warten(f"!FOTOS.some(f=>f.inspection_item_id==={attika})")
    await tab.warte_auf_ruhe()
    p.pruefe("Foto gelöscht, Platz „Vorher“ wieder mit Aufnehmen/Aus Galerie",
             await tab.js(f"!!document.querySelector('#punkt-zusatz-{attika} [data-klick=foto-galerie][data-art=vorher]')"), True)

    # --- Fokus bleibt beim Tippen einer Bemerkung --------------------------------------------------------------------------------------
    zugang = await tab.js("PUNKTE.find(p=>p.text==='Zugang und Absturzsicherung geprüft').id")
    await tab.js(f"document.querySelector('#punkt-menue-{zugang} [data-klick=bemerkung]').click()")
    await tab.warten(f"document.activeElement&&document.activeElement.id==='notiz-{zugang}'")
    await tab.cmd("Input.insertText", text="Leiter am Giebel")
    await tab.warten(f"(PUNKTE.find(p=>p.id==={zugang})||{{}}).notes==='Leiter am Giebel'", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Bemerkung gespeichert, Fokus und Text bleiben im Feld",
             await tab.js(f"[document.activeElement.id,document.getElementById('notiz-{zugang}').value]"),
             [f"notiz-{zugang}", "Leiter am Giebel"])
    # … auch wenn eine Antwort ankommt, während weiter getippt wird: das Feld wird dann nicht neu gezeichnet, nichts Getipptes geht
    # verloren (beide Antworten zurückgehalten -- die Prüfung hängt an keiner Zeitspanne)
    await tab.zurueckhalten(rf"/api/inspection-items/{zugang}$", "PUT", anzahl=2)
    await tab.cmd("Input.insertText", text=" links")
    await tab.warte_bis_gehalten(1)
    await tab.cmd("Input.insertText", text=" oben")
    await tab.freigeben()
    await tab.warte_bis_gehalten(1)
    p.pruefe("Antwort kommt beim Weitertippen an: Fokus und Text bleiben",
             await tab.js(f"[document.activeElement.id,document.getElementById('notiz-{zugang}').value]"),
             [f"notiz-{zugang}", "Leiter am Giebel links oben"])
    await tab.freigeben()
    await tab.warten(f"(PUNKTE.find(p=>p.id==={zugang})||{{}}).notes==='Leiter am Giebel links oben'", 10)
    await tab.warte_auf_ruhe()

    # --- 48 px quer --------------------------------------------------------------------------------------------------------------------
    p.pruefe("Quer: jedes Ziel in jedem Schritt ≥ 48 px", await _alle_schritte_messen(tab), [])
    await _schritt(tab, "pruefpunkte")
    p.pruefe("Quer: „⋮“ jedes Prüfpunkts in seiner Titelzeile", await tab.js(MENUE_IN_TITELZEILE), [[], True])
    await _bild(tab, "1_schritt1_quer_hell")

    # --- Schritte 2–4 ----------------------------------------------------------------------------------------------------------------
    await _schritt(tab, "befunde")
    await tab.js(f"(s=>{{s.value='in_bearbeitung';s.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('befund-status-{befund}'))")
    await tab.warten("BEFUNDE[0].status==='in_bearbeitung'")
    p.pruefe("Befunde: Status geändert", await tab.js("BEFUNDE[0].status_label"), "In Bearbeitung")
    await _schritt(tab, "material")
    await tab.js("document.getElementById('matSuche').focus()")
    await tab.cmd("Input.insertText", text="Dicht")
    await tab.warten("MAT_SUCHE.length===1")
    await tab.js("(s=>{s.value=String(MAT_SUCHE[0].id);s.dispatchEvent(new Event('change',{bubbles:true}))})(document.getElementById('matTreffer'))")
    await tab.js("document.getElementById('matMenge').value='2,5'")
    await tab.js("document.querySelector('[data-klick=material-neu]').click()")
    await tab.warten("MATERIAL.length===1")
    await tab.warte_auf_ruhe()
    m = await tab.js("MATERIAL[0].id")
    p.pruefe("Material aus dem Katalog erfasst", await tab.js("[MATERIAL[0].description,Number(MATERIAL[0].quantity),MATERIAL[0].unit]"),
             ["Dichtband Butyl", 2.5, "m"])
    await tab.js(f"(f=>{{f.value='3';f.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.getElementById('mat-menge-{m}'))")
    await tab.warten("Number(MATERIAL[0].quantity)===3")
    p.pruefe("Material: Menge geändert", await tab.js("Number(MATERIAL[0].quantity)"), 3)
    await _schritt(tab, "betriebsmittel")
    await tab.js("(s=>{s.value=String(WAEHLBAR[0].id);})(document.getElementById('bmWahl'));document.getElementById('bmNotiz').value='Hubhöhe 30 m'")
    await tab.js("document.querySelector('[data-klick=bm-neu]').click()")
    await tab.warten("BETRIEBSMITTEL.length===1")
    p.pruefe("Betriebsmittel mit Notiz erfasst", await tab.js("[BETRIEBSMITTEL[0].asset_name_snapshot,BETRIEBSMITTEL[0].notes]"),
             ["Kran 40t", "Hubhöhe 30 m"])

    # --- Schritt 5 ---------------------------------------------------------------------------------------------------------------------
    await _schritt(tab, "unterschrift")
    p.pruefe("Unterschrift: Zusammenfassung, Zeiten am Tag, Flächen ≥ 160 px, gesperrt mit „Fehlt: …“",
             await tab.js("[document.getElementById('schrittInhalt').textContent.includes('Das steht im Bericht'),"
                          f"document.getElementById('schrittInhalt').textContent.includes('Zeiten am {seed['heute_de']}'),"
                          "document.getElementById('schrittInhalt').textContent.includes('Mia Monteurin · 07:00–09:30'),"
                          "Math.round(document.getElementById('padMonteur').getBoundingClientRect().height)>=160,"
                          "Math.round(document.getElementById('padKunde').getBoundingClientRect().height)>=160,"
                          "document.getElementById('abschliessenKnopf').disabled,document.getElementById('fehltText').textContent.startsWith('Fehlt: '),"
                          "document.getElementById('signMonteurName').value]"),
             [True, True, True, True, True, True, True, "Mia Monteurin"])
    p.pruefe("Schritt 5 quer (1280 × 620): „Bericht abschließen“ und „Fehlt: …“ ohne Bildlauf im Bild, mit beiden Zeichenflächen",
             await tab.js(LEISTE_IM_BILD), LEISTE_SOLL)
    await _bild(tab, "2_schritt5_quer_hell")
    await _bild(tab, "3_schritt5_quer_dunkel", "dark")
    await _schritt(tab, "pruefpunkte")
    await _bild(tab, "4_schritt1_quer_dunkel", "dark")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")

    # --- hoch ---------------------------------------------------------------------------------------------------------------------------
    await tab.fenster(*HOCH, mobil=True)
    await tab.warten("window.innerWidth===800")
    p.pruefe("Hoch: eine Spalte, Schritte als Zeile mit Bildlauf, „Noch offen“ unten fest",
             await tab.js("[getComputedStyle(document.getElementById('raster')).gridTemplateColumns.split(' ').length,"
                          "getComputedStyle(document.getElementById('schritte')).overflowX,"
                          "getComputedStyle(document.querySelector('.offen-karte')).position,getComputedStyle(document.querySelector('.offen-karte')).bottom]"),
             [1, "auto", "sticky", "0px"])
    p.pruefe("Hoch: jedes Ziel in jedem Schritt ≥ 48 px", await _alle_schritte_messen(tab), [])
    await _schritt(tab, "pruefpunkte")
    p.pruefe("Hoch: „⋮“ jedes Prüfpunkts in seiner Titelzeile, auch bei Bewertungen", await tab.js(MENUE_IN_TITELZEILE), [[], True])
    await _bild(tab, "5_schritt1_hoch_hell")
    await _schritt(tab, "unterschrift")
    p.pruefe("Schritt 5 hoch: die Leiste unten im Bild", await tab.js(LEISTE_IM_BILD), LEISTE_SOLL)
    await _bild(tab, "6_schritt5_hoch_hell")
    voll = await tab.js("Math.ceil(document.documentElement.scrollHeight)")  # dazu bis zum Seitenende (Knopf „Bericht abschließen“)
    await tab.fenster(HOCH[0], max(HOCH[1], voll), mobil=True)
    await tab.bild("6b_schritt5_hoch_hell_ganz")
    await tab.fenster(*HOCH, mobil=True)
    await _bild(tab, "7_schritt5_hoch_dunkel", "dark")
    await _schritt(tab, "pruefpunkte")
    await _bild(tab, "8_schritt1_hoch_dunkel", "dark")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.fenster(*QUER, mobil=True)

    # --- Rapport ohne Vorlage: Schritt „Arbeiten“ -------------------------------------------------------------------------------------
    await tab.oeffnen(f"/service-reports/{r}", BEREIT)
    p.pruefe("Rapport ohne Vorlage: Schritt 1 „Arbeiten“, Beschreibung, „Noch offen“ nennt sie",
             [await tab.js("document.querySelector('#schritte .schritt').textContent.replace(/^\\d/,'')"),
              await tab.js("!!document.getElementById('beschreibung')"), await tab.js(_offen())],
             ["Arbeiten", True, ["Durchgeführte Arbeiten beschreiben"]])
    await _bild(tab, "9_arbeiten_quer_hell")
    await _bild(tab, "9_arbeiten_quer_dunkel", "dark")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await _schritt(tab, "unterschrift")
    await tab.strich("document.getElementById('padMonteur')")
    await tab.strich("document.getElementById('padKunde')")
    await tab.js("document.getElementById('signKundeName').value='Bernd Bauherr';document.getElementById('signKundeName').dispatchEvent(new Event('input',{bubbles:true}))")
    p.pruefe("Ohne Beschreibung: „Bericht abschließen“ gesperrt, „Fehlt“ nennt „Noch offen“",
             await tab.js("[document.getElementById('abschliessenKnopf').disabled,document.getElementById('fehltText').textContent]"),
             [True, "Fehlt: 1 Punkt unter „Noch offen“"])
    await _schritt(tab, "arbeiten")
    p.pruefe("Andere Schritte ohne die Leiste von Schritt 5", await tab.js("document.getElementById('abschlussLeiste').hidden"), True)
    await tab.js("document.getElementById('beschreibung').focus()")
    await tab.cmd("Input.insertText", text="Rinne gereinigt, Ablauf frei.")
    await tab.warten(f"{_offen()}.length===0", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Beschreibung gespeichert, nichts mehr offen, Fokus im Feld",
             await tab.js("[R.description,document.activeElement.id,document.getElementById('offenLeer').hidden]"),
             ["Rinne gereinigt, Ablauf frei.", "beschreibung", False])
    await _schritt(tab, "unterschrift")
    await tab.strich("document.getElementById('padMonteur')")
    await tab.strich("document.getElementById('padKunde')")
    await tab.js("document.getElementById('signKundeName').value='Bernd Bauherr';document.getElementById('signKundeName').dispatchEvent(new Event('input',{bubbles:true}))")
    p.pruefe("Ausgefüllt: „Bericht abschließen“ frei", await tab.js("document.getElementById('abschliessenKnopf').disabled"), False)
    p.pruefe("Mit beiden Unterschriften: „Bericht abschließen“ ohne Bildlauf im Bild", await tab.js(LEISTE_IM_BILD), LEISTE_SOLL)
    await tab.js("document.getElementById('abschliessenKnopf').click()")
    await tab.warten("R.status==='unterschrieben'", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Abgeschlossen: Status Unterschrieben, PDF im Menü",
             await tab.js("[document.getElementById('seitenkopfStatus').textContent,!document.getElementById('menuePdf').hidden,"
                          "document.getElementById('menueLoeschen').hidden]"),
             ["Unterschrieben", True, True])
    p.pruefe("Abgeschlossen: keine Leiste mehr", await tab.js("document.getElementById('abschlussLeiste').hidden"), True)

    # --- Art ändern: leer geht, mit Antwort gesperrt -----------------------------------------------------------------------------------
    await tab.oeffnen(f"/service-reports/{leer}", BEREIT)
    await tab.js("document.getElementById('menueArt').click()")
    await tab.warten("document.getElementById('artDialog').open")
    p.pruefe("Art ändern (leer): Auswahl frei", await tab.js("document.getElementById('artFeld').disabled"), False)
    await tab.js("document.getElementById('artFeld').value='wartung';document.getElementById('artSpeichern').click()")
    await tab.warten("R.report_type==='wartung'&&!document.getElementById('artDialog').open", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Art geändert: Wartungsbericht, Schritt 1 „Prüfpunkte“",
             await tab.js("[document.getElementById('seitenkopfTitel').textContent,document.querySelector('#schritte .schritt').textContent.replace(/^\\d/,'')]"),
             ["Wartungsbericht", "Prüfpunkte"])
    await tab.js("document.getElementById('beschreibung').focus()")
    await tab.cmd("Input.insertText", text="Begehung")
    await tab.warten("R.description==='Begehung'", 10)
    await tab.js("document.getElementById('menueArt').click()")
    await tab.warten("document.getElementById('artDialog').open")
    p.pruefe("Art ändern (nicht leer): gesperrt mit Hinweis",
             await tab.js("[document.getElementById('artFeld').disabled,document.getElementById('artSpeichern').disabled,"
                          "document.getElementById('artHinweis').textContent.includes('Entwurf löschen und neu anlegen')]"),
             [True, True, True])
    await tab.js("document.getElementById('artAbbrechen').click()")

    # --- Datum ändern, Löschen ---------------------------------------------------------------------------------------------------------
    await tab.js("document.getElementById('menueDatum').click()")
    await tab.warten("document.getElementById('datumDialog').open")
    await tab.js("document.getElementById('datumFeld').value='2026-01-15';document.getElementById('datumSpeichern').click()")
    await tab.warten("R.performed_at==='2026-01-15'&&!document.getElementById('datumDialog').open", 15)
    p.pruefe("Datum geändert", await tab.js("R.performed_at"), "2026-01-15")
    await tab.js("document.getElementById('menueLoeschen').click()")
    await tab.warten("document.getElementById('rueckfrageDialog').open")
    await tab.js("document.getElementById('rueckfrageJa').click()")
    await tab.warten(f"location.pathname==='/orders/{a}/service-reports'", 15)
    p.pruefe("Gelöscht: zurück auf der Auftragsseite", await tab.js("location.pathname"), f"/orders/{a}/service-reports")

    # --- Auftragsseite der Monteurin -----------------------------------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{a}/service-reports", "document.querySelectorAll('#reportList .bericht-zeile').length===2")
    p.pruefe("Auftragsseite Monteurin: keine Buchungskarte, „Zeit nachtragen“ auf „Meine Zeiten“",
             await tab.js("[!!document.getElementById('teDate'),document.getElementById('zeitNachtragen').getAttribute('href')]"),
             [False, f"/mobil/zeiten?order_id={a}"])
    p.pruefe("Auftragsseite: die Berichte führen zur Berichtsseite",
             await tab.js("[...document.querySelectorAll('#reportList a.bericht-zeile')].map(x=>x.getAttribute('href')).sort()"),
             sorted([f"/service-reports/{w}", f"/service-reports/{r}"]))
    await _bild(tab, "10_auftragsseite_monteurin_quer")
    await _bild(tab, "10_auftragsseite_monteurin_quer_dunkel", "dark")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.js("document.getElementById('neuerBericht').click()")
    await tab.warten("!document.getElementById('editorCard').classList.contains('hidden')")
    await tab.js("document.querySelector('[data-klick=bericht-anlegen]').click()")
    await tab.warten("location.pathname.startsWith('/service-reports/')", 15)
    p.pruefe("„+ Bericht“: angelegt und geöffnet", await tab.js("location.pathname.startsWith('/service-reports/')"), True)
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro --------------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1440, 900)
    await tab.oeffnen(f"/orders/{a}/service-reports", "document.querySelectorAll('#reportList .bericht-zeile').length>=2")
    p.pruefe("Büro: Buchungskarte unverändert", await tab.js("['teDate','teType','teHours'].map(i=>!!document.getElementById(i))"), [True] * 3)
    await tab.oeffnen(f"/service-reports/{w}", BEREIT)
    p.pruefe("Büro: Pfad ab Projekte bis Einsatzberichte",
             await tab.js("[...document.querySelectorAll('#seitenkopfPfad a')].map(x=>x.textContent)"),
             ["Projekte", "Hallenbau GmbH", "Wartung Halle Nord", "AUF-KT-BS", "Einsatzberichte"])
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Einsatzbericht in fünf Schritten (1.9.67)", uhr="10:00"))
