"""Klicktest: Urlaub und Startwerte der Konten in Einstellungen → Zeitregeln und DATEV (1.9.310, Lohn L2a, Punkt 3; Antworten 11 und 12 des Befunds L2).

Stehende Uhr Mi 11.11.2026 10:00. Mia (gewerblich), Kai (gewerblich), Bea (kaufmännisch, Konto Büro – Auftrag); Fin (Büro – Finanzen, ohne Mitarbeiter);
seit 1.9.312 Ute (gewerblich, inaktiv) und am Anspruch 2027 von Kai ein Übertrag von 2 Tagen aus der Zeit vor 1.9.312 (Bestand).

    Büro – Finanzen  Block „Urlaub und Startwerte der Konten“: Vorgabe 30 Tage, Übertrag „von Hand“, Verfall leer; jede Person mit „30 Tage (Vorgabe)“ und „—“;
                     Vorgaben 28,5 Tage und Verfall 31.03. gespeichert; „Ändern“ an Mia: Dialog „Urlaub und Startwert – Mia Monteurin“, Jahr 2027 (dazu
                     2028), Urlaubstage leer mit „Vorgabe 28,5“; 24 Tage, Notiz gespeichert -> „24 Tage“; Startwert Resturlaub 4,5, Saldo -12,25 h,
                     Bemerkung, „geprüft“ -> „Geprüft am 11.11.2026 durch Fin Finanzen.“, in der Zeile „24 Tage · Übertrag 4,5“, „4,5 Tage“,
                     „-12,25 h“, „Steuerbüro · geprüft 11.11.2026“; Resturlaub 4,3 -> Meldung „in halben Tagen“, nichts gespeichert; Saldo -11 ohne
                     „geprüft“ -> „Noch nicht geprüft.“, mit dem Haken wieder geprüft; Jahr 2028 -> leer
    seit 1.9.312     Inaktive ausblenden: beide Kästchen an, Ute fehlt in Lohnstammdaten und Konten, „1 inaktiv“; ein Kästchen ab -> Ute in beiden
                     grau, das andere Kästchen folgt, nach dem Neuladen gemerkt; wieder an -> weg. Übertrag 2027: Feld gesperrt, zeigt den Startwert
                     „Resturlaub“ (leer bzw. 4,5) mit Hinweis; 2028 von Hand frei; Kais Übertrag aus dem Bestand: in der Zeile „Übertrag doppelt –
                     prüfen“, im Dialog der Hinweis mit 2 Tagen, nach „Diesen Übertrag entfernen“ weg (nichts still gelöscht). „geprüft“: der Haken
                     zeigt den Stand; Saldo getippt -> Haken heraus, „Wert geändert – neu prüfen“; zurückgetippt bleibt er heraus; ohne Haken
                     gespeichert -> nicht geprüft; Bemerkung getippt ohne vorherige Prüfung -> kein Hinweis
    Bilder           der Block und der Dialog bei 1440 und 412 px, hell und dunkel; bei 412 px läuft die Seite nicht über, „28,5 Tage (Vorgabe)“ auf
                     einer Zeile; seit 1.9.312 die Liste mit und ohne „Inaktive ausblenden“, der Dialog 2027 (Übertrag aus dem Startwert) und der
                     Dialog „Wert geändert – neu prüfen“
    Büro – Auftrag   Bea sieht nur ihre eigene Zeile, „Ansehen“ statt „Ändern“, die Vorgaben gesperrt ohne Knopf; im Dialog alles gesperrt, keine Knöpfe zum
                     Speichern; derselbe PUT vom Server 403
    Monat & Lohn     (seit 1.9.311) November 2026: Mia mit Buchung, Kai den ganzen Monat im Urlaub, Bea ohne alles -- alle drei mit Sollzeit stehen in der
                     Tabelle, Kai und Bea mit 0,00 (bis 1.9.310 fehlten sie); Bilder bei 1440 und 412 px, hell und dunkel; bei 412 px läuft nichts über
    Januar zu        Fin schließt bis 31.01.2027 ab: im Dialog der Hinweis „… ändert jetzt nur ein Administrator.“, der Startwert gesperrt, der Anspruch
                     weiter änderbar
    überall          keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_konten.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof konten!=='undefined'&&!!konten&&document.querySelectorAll('#kontenZeilen tr[data-konto]').length>0"
ZEILEN = ("[...document.querySelectorAll('#kontenZeilen tr[data-konto]')].map(tr=>[...tr.cells].map(c=>c.innerText.trim()))")
DIALOG_BEREIT = "document.getElementById('kontenDialog').open"
# seit 1.9.311: „Monat & Lohn“ -- je Zeile Name, Tage und „Zusammen“ (die Spalte über den Kopf; „Ausfall Schlechtwetter“ gibt es nur mit Ausfalltagen)
MONAT_BEREIT = "!!window.P&&!!document.querySelector('#lohnZeilen tr')"
MONAT_ZEILEN = ("(()=>{const k=[...document.querySelectorAll('#lohnKopf th')].map(t=>t.textContent.trim()).indexOf('Zusammen');"
                "return [...document.querySelectorAll('#lohnZeilen tr')].map(tr=>[tr.cells[0].innerText.trim(),tr.cells[2].innerText.trim(),"
                "tr.cells[k].innerText.trim()])})()")


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, EmployeeAbsence, Order, Project, TimeEntry, Urlaubsanspruch
    from app.project_pipeline_columns import default_pipeline_column_id

    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    kai = Employee(employee_number="M-2", first_name="Kai", last_name="Kolonne", employee_group="gewerblich", active=True)
    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    ute = Employee(employee_number="M-9", first_name="Ute", last_name="Ehemalig", employee_group="gewerblich", active=False)  # seit 1.9.312
    db.add_all([mia, kai, bea_ma, ute])
    db.flush()
    # seit 1.9.312: ein Übertrag am Anspruch 2027 aus der Zeit vor 1.9.312 -- jetzt „Übertrag doppelt – prüfen“ (2027 gilt der Startwert)
    db.add(Urlaubsanspruch(employee_id=kai.id, jahr=2027, uebertrag=Decimal("2")))
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id, password_hash=k.passwort())
    db.add_all([fin, bea])
    # seit 1.9.311: im November bucht Mia einen Tag, Kai hat den ganzen Monat Urlaub, Bea nichts
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde)
    db.flush()
    projekt = Project(project_number="P-KT-KO1", name="Halle", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    auftrag = Order(order_number="AUF-2026-0311", project_id=projekt.id, source_quote_id=311, quote_number_snapshot="A-KT-311", title="Halle",
                    customer_name=kunde.name)
    db.add(auftrag)
    db.flush()
    tag = date(2026, 11, 3)
    db.add(TimeEntry(employee_id=mia.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site", hours=Decimal("7.5"),
                     break_minutes=30, status="booked", started_at=datetime.combine(tag, time(7)), ended_at=datetime.combine(tag, time(15))))
    db.add(EmployeeAbsence(employee_id=kai.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 11, 2), end_date=date(2026, 11, 30)))
    db.commit()
    return {"fin": k.cookies(fin), "bea": k.cookies(bea), "mia": mia.id, "bea_ma": bea_ma.id, "kai": kai.id}


async def _setze(tab, werte: dict):
    await tab.js(";".join(f"document.getElementById('{i}').value={json.dumps(v)}" for i, v in werte.items()))


# seit 1.9.312: echt tippen (Input.insertText löst „input“ aus wie eine Eingabe)
async def _tippen(tab, feld: str, text: str):
    await tab.js(f"(()=>{{const el=document.getElementById('{feld}');el.focus();el.select()}})()")
    await tab.cmd("Input.insertText", text=text)


PAYROLL = "[...document.querySelectorAll('#payrollRows tr')].map(tr=>[tr.cells[0].innerText.trim(),tr.className])"
KAESTCHEN = ("[document.getElementById('lohnInaktiveAusblenden').checked,document.getElementById('kontenInaktiveAusblenden').checked,"
             "document.getElementById('lohnInaktivZahl').innerText,document.getElementById('kontenInaktivZahl').innerText]")


async def _api(tab, pfad: str):
    return await tab.js(f"fetch({json.dumps(pfad)}).then(r=>r.json())")


async def _oeffnen(tab, mitarbeiter: int):
    await tab.js(f"document.querySelector('[data-klick=konten-oeffnen][data-mitarbeiter=\"{mitarbeiter}\"]').click()")
    return await tab.warten(DIALOG_BEREIT, 10)


async def _klick_bis(tab, knopf: str, status: str, text: str) -> bool:
    await tab.js(f"document.getElementById('{status}').textContent=''")
    await tab.js(f"document.querySelector('{knopf}').click()")
    await tab.warte_auf_ruhe()
    return await tab.warten(f"document.getElementById('{status}').textContent.includes({json.dumps(text)})", 10)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    mia = seed["mia"]

    # ---- Büro – Finanzen ----------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 1000)
    p.pruefe("Fin: Zeitregeln geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Vorgaben 30 Tage, von Hand, kein Verfall", await tab.js(
        "[document.getElementById('kvTage').value,document.getElementById('kvUebertrag').value,document.getElementById('kvVerfall').value,"
        "document.getElementById('kontenJahrKopf').textContent]"), ["30", "von_hand", "", "Urlaub 2027"])
    p.pruefe("Fin: jede Person mit der Vorgabe, ohne Startwert", await tab.js(ZEILEN),
             [["Bea Büro", "30 Tage (Vorgabe)", "30 Tage", "—", "—", "—", "Ändern"],  # seit 1.9.316 die Spalte „Rest 2027“
              ["Kai Kolonne", "30 Tage (Vorgabe) · Übertrag doppelt – prüfen", "30 Tage", "—", "—", "—", "Ändern"],
              ["Mia Monteurin", "30 Tage (Vorgabe)", "30 Tage", "—", "—", "—", "Ändern"]])
    p.pruefe("Fin: Kopf „Rest 2027“", await tab.js("document.getElementById('kontenRestKopf').textContent"), "Rest 2027")
    # ---- seit 1.9.312: Inaktive ausblenden -- ein Stand für beide Kästchen, gemerkt im Browser ----------------------------------------------
    p.pruefe("Fin: Inaktive ausgeblendet (Vorgabe)", [await tab.js(KAESTCHEN), await tab.js(PAYROLL)],
             [[True, True, "1 inaktiv", "1 inaktiv"], [["Bea Büro", ""], ["Kai Kolonne", ""], ["Mia Monteurin", ""]]])
    await tab.js("document.getElementById('kontenInaktiveAusblenden').click()")
    p.pruefe("Fin: Kästchen ab -- Ute in beiden Listen, grau", [await tab.js(KAESTCHEN), await tab.js(PAYROLL),
             await tab.js("[...document.querySelectorAll('#kontenZeilen tr[data-konto]')].map(tr=>[tr.cells[0].innerText.trim(),tr.className])"),
             await tab.js("getComputedStyle(document.querySelector('#kontenZeilen tr.inaktiv td')).color!==getComputedStyle(document.querySelector('#kontenZeilen tr:not(.inaktiv) td')).color")],
             [[False, False, "1 inaktiv", "1 inaktiv"], [["Bea Büro", ""], ["Kai Kolonne", ""], ["Mia Monteurin", ""], ["Ute Ehemalig", "inaktiv"]],
              [["Bea Büro", ""], ["Kai Kolonne", ""], ["Mia Monteurin", ""], ["Ute Ehemalig", "inaktiv"]], True])
    p.pruefe("Fin: nach dem Neuladen gemerkt", await tab.oeffnen("/settings?n=90#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: weiter gezeigt", [await tab.js(KAESTCHEN), len(await tab.js(ZEILEN))], [[False, False, "1 inaktiv", "1 inaktiv"], 4])
    await tab.js("document.getElementById('lohnInaktiveAusblenden').click()")
    p.pruefe("Fin: wieder ausgeblendet", [await tab.js(KAESTCHEN), [z[0] for z in await tab.js(ZEILEN)]],
             [[True, True, "1 inaktiv", "1 inaktiv"], ["Bea Büro", "Kai Kolonne", "Mia Monteurin"]])
    await _setze(tab, {"kvTage": "28,5", "kvVerfall": "31.03."})
    p.pruefe("Fin: Vorgaben gespeichert", await _klick_bis(tab, "[data-klick=konten-vorgaben]", "kontenVorgabenStatus", "Gespeichert."), True)
    p.pruefe("Fin: Vorgaben auf dem Server", (await _api(tab, "/api/time-backoffice/konten"))["vorgaben"],
             {"urlaub_vorgabe_tage": "28.5", "urlaub_uebertrag": "von_hand", "urlaub_verfall": "31.03.",
              "konto_hinweis_plus": None, "konto_hinweis_minus": None})  # seit 1.9.336 dazu die Grenzen des Arbeitszeitkontos (leer)

    p.pruefe("Fin: Dialog an Mia", await _oeffnen(tab, mia), True)
    p.pruefe("Fin: Titel, Jahre, leer mit der Vorgabe", await tab.js(
        "[document.getElementById('kontenTitel').innerText,[...document.getElementById('kdJahr').options].map(o=>o.text),document.getElementById('kdJahr').value,"
        "document.getElementById('kdTage').value,document.getElementById('kdTage').placeholder,document.getElementById('kdStichtag').innerText,"
        "document.getElementById('kdGeprueftText').innerText,document.getElementById('kdGesperrt').hidden]"),
        ["Urlaub und Startwert – Mia Monteurin", ["2027", "2028"], "2027", "", "Vorgabe 28,5", "31.12.2026", "Noch nicht geprüft.", True])
    p.pruefe("Fin: Übertrag 2027 gesperrt, aus dem Startwert", await tab.js(
        "[document.getElementById('kdUebertrag').disabled,document.getElementById('kdUebertrag').value,document.getElementById('kdUebertragHinweis').innerText,"
        "document.getElementById('kdUebertragDoppelt').hidden,document.getElementById('kdUebertragLeeren').hidden,document.getElementById('kdGeprueft').checked]"),
        [True, "", "2027: der Startwert „Resturlaub“ (unten) – hier nur angezeigt.", True, True, False])
    await _setze(tab, {"kdTage": "24", "kdNotiz": "Teilzeit 4 Tage"})
    p.pruefe("Fin: Anspruch gespeichert", await _klick_bis(tab, "#kdAnspruchKnopf", "kdAnspruchStatus", "Gespeichert."), True)
    await _setze(tab, {"kdRest": "4,5", "kdSaldo": "-12,25", "kdHerkunftNotiz": "Liste vom 30.12.2026"})
    await tab.js("document.getElementById('kdGeprueft').checked=true")
    p.pruefe("Fin: Startwert gespeichert", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: geprüft heute durch Fin, der Haken zeigt es", await tab.js(
        "[document.getElementById('kdGeprueftText').innerText,document.getElementById('kdGeprueft').checked,document.getElementById('kdGeprueftHinweis').hidden]"),
        ["Geprüft am 11.11.2026 durch Fin Finanzen.", True, True])
    p.pruefe("Fin: Mias Zeile mit dem Übertrag aus dem Startwert", [z for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"],
             [["Mia Monteurin", "24 Tage · Übertrag 4,5", "28,5 Tage", "4,5 Tage", "-12,25 h", "Steuerbüro · geprüft 11.11.2026", "Ändern"]])
    await tab.js("auswahlWert(document.getElementById('kdJahr'),'2027');document.getElementById('kdJahr').dispatchEvent(new Event('change',{bubbles:true}))")
    p.pruefe("Fin: Dialog 2027 zeigt den Startwert als Übertrag", await tab.js("document.getElementById('kdUebertrag').value"), "4,5")
    await tab.bild("konten_dialog_2027_1440")
    # ---- seit 1.9.312: „Wert geändert – neu prüfen“ ------------------------------------------------------------------------------------------
    await _tippen(tab, "kdSaldo", "-13")
    p.pruefe("Fin: Saldo getippt -- Haken heraus, Hinweis", await tab.js(
        "[document.getElementById('kdGeprueft').checked,document.getElementById('kdGeprueftHinweis').hidden,document.getElementById('kdGeprueftHinweis').innerText]"),
        [False, False, "Wert geändert – neu prüfen"])
    await tab.js("document.getElementById('kdGeprueftHinweis').scrollIntoView({block:'center'})")
    await tab.bild("konten_dialog_neu_pruefen_1440")
    await _tippen(tab, "kdSaldo", "-12,25")
    p.pruefe("Fin: zurückgetippt -- der Haken bleibt heraus", await tab.js(
        "[document.getElementById('kdGeprueft').checked,document.getElementById('kdGeprueftHinweis').hidden]"), [False, False])
    p.pruefe("Fin: ohne Haken gespeichert", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: nicht mehr geprüft", [await tab.js("[document.getElementById('kdGeprueftText').innerText,document.getElementById('kdGeprueft').checked]"),
                                         [z[5] for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"]],
             [["Noch nicht geprüft.", False], ["Steuerbüro · nicht geprüft"]])
    await _tippen(tab, "kdHerkunftNotiz", "Liste vom 31.12.2026")
    p.pruefe("Fin: ohne vorherige Prüfung kein Hinweis", await tab.js(
        "[document.getElementById('kdGeprueft').checked,document.getElementById('kdGeprueftHinweis').hidden]"), [False, True])
    await _setze(tab, {"kdHerkunftNotiz": "Liste vom 30.12.2026"})
    await tab.js("document.getElementById('kdGeprueft').checked=true")
    p.pruefe("Fin: neu geprüft", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    await _setze(tab, {"kdRest": "4,3"})
    p.pruefe("Fin: Resturlaub 4,3 abgelehnt", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "in halben Tagen"), True)
    p.pruefe("Fin: nichts gespeichert, geprüft bleibt", [
        x["startwert"] for x in (await _api(tab, "/api/time-backoffice/konten"))["personen"] if x["employee_id"] == mia][0],
        {"stichtag": "2026-12-31", "resturlaub_tage": "4.5", "saldo_stunden": "-12.25", "herkunft": "steuerbuero", "herkunft_text": "Steuerbüro",
         "herkunft_notiz": "Liste vom 30.12.2026", "geprueft_am": "2026-11-11", "geprueft_von": "Fin Finanzen"})
    # ein geänderter Wert ohne „geprüft“: die Prüfung fällt weg; mit dem Haken wieder geprüft
    await _setze(tab, {"kdRest": "4,5", "kdSaldo": "-11"})
    p.pruefe("Fin: Saldo geändert ohne „geprüft“", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: die Prüfung ist weg", [await tab.js("document.getElementById('kdGeprueftText').innerText"),
                                         [z[4:6] for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"]],
             ["Noch nicht geprüft.", [["-11,00 h", "Steuerbüro · nicht geprüft"]]])
    await _setze(tab, {"kdSaldo": "-12,25"})
    await tab.js("document.getElementById('kdGeprueft').checked=true")
    p.pruefe("Fin: wieder geprüft", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: Zeile wieder geprüft", [z[4:6] for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"],
             [["-12,25 h", "Steuerbüro · geprüft 11.11.2026"]])
    await tab.js("auswahlWert(document.getElementById('kdJahr'),'2028');document.getElementById('kdJahr').dispatchEvent(new Event('change',{bubbles:true}))")
    p.pruefe("Fin: Jahr 2028 leer, Übertrag von Hand frei", await tab.js(
        "[document.getElementById('kdTage').value,document.getElementById('kdUebertrag').value,document.getElementById('kdUebertrag').disabled,"
        "document.getElementById('kdUebertragHinweis').innerText]"), ["", "", False, ""])
    await tab.js("document.getElementById('kontenDialog').close()")
    # ---- seit 1.9.312: Kais Übertrag aus dem Bestand -- „doppelt – prüfen“, entfernt nur von Hand --------------------------------------------
    p.pruefe("Fin: Dialog an Kai", await _oeffnen(tab, seed["kai"]), True)
    p.pruefe("Fin: Hinweis „doppelt“ mit 2 Tagen", await tab.js(
        "[document.getElementById('kdUebertragDoppelt').hidden,document.getElementById('kdUebertragDoppelt').innerText,"
        "document.getElementById('kdUebertragLeeren').hidden,document.getElementById('kdUebertrag').value]"),
        [False, "Übertrag doppelt – prüfen: am Anspruch 2027 steht zusätzlich ein Übertrag von 2 Tagen.", False, ""])
    await tab.bild("konten_dialog_doppelt_1440")
    await _setze(tab, {"kdNotiz": "Teilzeit"})
    p.pruefe("Fin: Anspruch gespeichert -- der Übertrag bleibt", await _klick_bis(tab, "#kdAnspruchKnopf", "kdAnspruchStatus", "Gespeichert."), True)
    p.pruefe("Fin: Kai weiter doppelt", [x["ansprueche"] for x in (await _api(tab, "/api/time-backoffice/konten"))["personen"] if x["employee_id"] == seed["kai"]][0][0]["uebertrag"], "2.0")
    p.pruefe("Fin: entfernt", await _klick_bis(tab, "#kdUebertragLeeren", "kdAnspruchStatus", "Übertrag entfernt."), True)
    p.pruefe("Fin: Hinweis weg, Zeile ohne", [await tab.js("[document.getElementById('kdUebertragDoppelt').hidden,document.getElementById('kdUebertragLeeren').hidden]"),
                                              [z[1] for z in await tab.js(ZEILEN) if z[0] == "Kai Kolonne"]],
             [[True, True], ["28,5 Tage (Vorgabe)"]])
    await tab.js("document.getElementById('kontenDialog').close()")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Bilder: der Block und der Dialog --------------------------------------------------------------------------------------------------
    n = 0
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/settings?n={n}#time-rules", BEREIT), True)
            await tab.warte_auf_ruhe()
            await tab.js("document.getElementById('kontenBlock').scrollIntoView({block:'start'})")
            if mobil:
                p.pruefe(f"Bild 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
                # seit 1.9.312: „28,5 Tage (Vorgabe)“ auf einer Zeile (bis 1.9.311 auf drei); die erste Spalte zieht die Trennlinie selbst
                p.pruefe(f"Bild 412 {name}: Anspruch auf einer Zeile", await tab.js(
                    "[...document.querySelectorAll('#kontenZeilen tr[data-konto]')].every(tr=>{const r=document.createRange();r.selectNodeContents(tr.cells[1]);"
                    "return new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size===1})"), True)
                p.pruefe(f"Bild 412 {name}: Trennlinie in der ersten Spalte", await tab.js(
                    "getComputedStyle(document.querySelector('#kontenZeilen tr[data-konto] td')).boxShadow.split('inset').length-1"), 2)
            await tab.bild(f"lohnstammdaten_konten_{breite}_{name}")
            await tab.js("document.getElementById('kontenInaktiveAusblenden').click()")
            await tab.bild(f"lohnstammdaten_konten_inaktive_gezeigt_{breite}_{name}")
            await tab.js("document.getElementById('lohnInaktiveAusblenden').scrollIntoView({block:'start'})")
            await tab.bild(f"lohnstammdaten_liste_inaktive_gezeigt_{breite}_{name}")
            await tab.js("document.getElementById('lohnInaktiveAusblenden').click()")
            await tab.bild(f"lohnstammdaten_liste_{breite}_{name}")
            await _oeffnen(tab, mia)
            await tab.bild(f"konten_dialog_{breite}_{name}")
            await tab.js("document.getElementById('kontenDialog').close()")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")

    # ---- Büro – Auftrag ------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Zeitregeln geladen", await tab.oeffnen("/settings?n=20#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: nur die eigene Zeile, „Ansehen“", await tab.js(ZEILEN), [["Bea Büro", "28,5 Tage (Vorgabe)", "28,5 Tage", "—", "—", "—", "Ansehen"]])
    p.pruefe("Bea: „Inaktive ausblenden“ bleibt bedienbar (nur Anzeige)", await tab.js(
        "[document.getElementById('kontenInaktiveAusblenden').disabled,document.getElementById('lohnInaktiveAusblenden').disabled]"), [False, False])
    p.pruefe("Bea: Vorgaben gesperrt, ohne Knopf", await tab.js(
        "[document.getElementById('kvTage').disabled,document.querySelector('[data-klick=konten-vorgaben]').hidden]"), [True, True])
    p.pruefe("Bea: Dialog", await _oeffnen(tab, seed["bea_ma"]), True)
    p.pruefe("Bea: im Dialog alles gesperrt, keine Knöpfe", await tab.js(
        "[['kdTage','kdUebertrag','kdVerfall','kdNotiz','kdRest','kdSaldo','kdHerkunft','kdGeprueft'].every(i=>document.getElementById(i).disabled),"
        "document.getElementById('kdAnspruchKnopf').hidden,document.getElementById('kdStartwertKnopf').hidden]"), [True, True, True])
    await tab.js("document.getElementById('kontenDialog').close()")
    p.pruefe("Bea: Speichern vom Server abgelehnt (403)", await tab.js(
        f"fetch('/api/time-backoffice/konten/{seed['bea_ma']}/startwert',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({resturlaub_tage:5})}).then(r=>r.status)"), 403)
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    # ---- seit 1.9.311: „Monat & Lohn“ mit allen, die im Monat Sollzeit haben ---------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    n = 30
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Monat {breite} {name}: Zeiten geladen", await tab.oeffnen(f"/zeiten?n={n}#monat", MONAT_BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"Monat {breite} {name}: alle drei mit Sollzeit, Kai nur Urlaub, Bea ohne alles", await tab.js(MONAT_ZEILEN),
                     [["Bea Büro", "0", "0,00"], ["Kai Kolonne", "0", "0,00"], ["Mia Monteurin", "1", "7,50"], ["Zusammen", "", "7,50"]])
            if mobil:
                p.pruefe(f"Monat 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild_ganz(f"monat_und_lohn_nur_urlaub_{breite}_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Monat: keine JS-Fehler", tab.fehler, [])

    # ---- Januar abgeschlossen ----------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: abgeschlossen bis 31.01.2027", await tab.js(
        "fetch('/api/time-backoffice/lock',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({locked_until:'2027-01-31'})})"
        ".then(r=>r.status)"), 200)
    p.pruefe("Fin: Zeitregeln neu geladen", await tab.oeffnen("/settings?n=21#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Dialog an Mia", await _oeffnen(tab, mia), True)
    p.pruefe("Fin: Startwert gesperrt mit Hinweis, Anspruch änderbar", await tab.js(
        "[document.getElementById('kdGesperrt').hidden,document.getElementById('kdGesperrt').innerText,document.getElementById('kdRest').disabled,"
        "document.getElementById('kdStartwertKnopf').hidden,document.getElementById('kdTage').disabled,document.getElementById('kdAnspruchKnopf').hidden]"),
        [False, "Der Monat nach dem Stichtag ist abgeschlossen – den Startwert ändert jetzt nur ein Administrator.", True, True, False, False])
    await tab.bild("konten_dialog_januar_abgeschlossen")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
