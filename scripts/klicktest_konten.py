"""Klicktest: Urlaub und Startwerte der Konten in Einstellungen → Zeitregeln und DATEV (1.9.310, Lohn L2a, Punkt 3; Antworten 11 und 12 des Befunds L2).

Stehende Uhr Mi 11.11.2026 10:00. Mia (gewerblich), Kai (gewerblich), Bea (kaufmännisch, Konto Büro – Auftrag); Fin (Büro – Finanzen, ohne Mitarbeiter).

    Büro – Finanzen  Block „Urlaub und Startwerte der Konten“: Vorgabe 30 Tage, Übertrag „von Hand“, Verfall leer; jede Person mit „30 Tage (Vorgabe)“ und „—“;
                     Vorgaben 28,5 Tage und Verfall 31.03. gespeichert; „Ändern“ an Mia: Dialog „Urlaub und Startwert – Mia Monteurin“, Jahr 2027 (dazu
                     2028), Urlaubstage leer mit „Vorgabe 28,5“; 24 Tage, Übertrag -1,5, Notiz gespeichert -> „24 Tage · Übertrag -1,5“; Startwert
                     Resturlaub 4,5, Saldo -12,25 h, Bemerkung, „geprüft“ -> „Geprüft am 11.11.2026 durch Fin Finanzen.“, in der Zeile „4,5 Tage“,
                     „-12,25 h“, „Steuerbüro · geprüft 11.11.2026“; Resturlaub 4,3 -> Meldung „in halben Tagen“, nichts gespeichert; Saldo -11 ohne
                     „geprüft“ -> „Noch nicht geprüft.“, mit dem Haken wieder geprüft; Jahr 2028 -> leer
    Bilder           der Block und der Dialog bei 1440 und 412 px, hell und dunkel; bei 412 px läuft die Seite nicht über
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

    from app.models import AppUser, Customer, Employee, EmployeeAbsence, Order, Project, TimeEntry
    from app.project_pipeline_columns import default_pipeline_column_id

    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    kai = Employee(employee_number="M-2", first_name="Kai", last_name="Kolonne", employee_group="gewerblich", active=True)
    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add_all([mia, kai, bea_ma])
    db.flush()
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
    return {"fin": k.cookies(fin), "bea": k.cookies(bea), "mia": mia.id, "bea_ma": bea_ma.id}


async def _setze(tab, werte: dict):
    await tab.js(";".join(f"document.getElementById('{i}').value={json.dumps(v)}" for i, v in werte.items()))


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
             [["Bea Büro", "30 Tage (Vorgabe)", "—", "—", "—", "Ändern"], ["Kai Kolonne", "30 Tage (Vorgabe)", "—", "—", "—", "Ändern"],
              ["Mia Monteurin", "30 Tage (Vorgabe)", "—", "—", "—", "Ändern"]])
    await _setze(tab, {"kvTage": "28,5", "kvVerfall": "31.03."})
    p.pruefe("Fin: Vorgaben gespeichert", await _klick_bis(tab, "[data-klick=konten-vorgaben]", "kontenVorgabenStatus", "Gespeichert."), True)
    p.pruefe("Fin: Vorgaben auf dem Server", (await _api(tab, "/api/time-backoffice/konten"))["vorgaben"],
             {"urlaub_vorgabe_tage": "28.5", "urlaub_uebertrag": "von_hand", "urlaub_verfall": "31.03."})

    p.pruefe("Fin: Dialog an Mia", await _oeffnen(tab, mia), True)
    p.pruefe("Fin: Titel, Jahre, leer mit der Vorgabe", await tab.js(
        "[document.getElementById('kontenTitel').innerText,[...document.getElementById('kdJahr').options].map(o=>o.text),document.getElementById('kdJahr').value,"
        "document.getElementById('kdTage').value,document.getElementById('kdTage').placeholder,document.getElementById('kdStichtag').innerText,"
        "document.getElementById('kdGeprueftText').innerText,document.getElementById('kdGesperrt').hidden]"),
        ["Urlaub und Startwert – Mia Monteurin", ["2027", "2028"], "2027", "", "Vorgabe 28,5", "31.12.2026", "Noch nicht geprüft.", True])
    await _setze(tab, {"kdTage": "24", "kdUebertrag": "-1,5", "kdNotiz": "Teilzeit 4 Tage"})
    p.pruefe("Fin: Anspruch gespeichert", await _klick_bis(tab, "#kdAnspruchKnopf", "kdAnspruchStatus", "Gespeichert."), True)
    await _setze(tab, {"kdRest": "4,5", "kdSaldo": "-12,25", "kdHerkunftNotiz": "Liste vom 30.12.2026"})
    await tab.js("document.getElementById('kdGeprueft').checked=true")
    p.pruefe("Fin: Startwert gespeichert", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: geprüft heute durch Fin", await tab.js("document.getElementById('kdGeprueftText').innerText"),
             "Geprüft am 11.11.2026 durch Fin Finanzen.")
    p.pruefe("Fin: Mias Zeile", [z for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"],
             [["Mia Monteurin", "24 Tage · Übertrag -1,5", "4,5 Tage", "-12,25 h", "Steuerbüro · geprüft 11.11.2026", "Ändern"]])
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
                                         [z[3:5] for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"]],
             ["Noch nicht geprüft.", [["-11,00 h", "Steuerbüro · nicht geprüft"]]])
    await _setze(tab, {"kdSaldo": "-12,25"})
    await tab.js("document.getElementById('kdGeprueft').checked=true")
    p.pruefe("Fin: wieder geprüft", await _klick_bis(tab, "#kdStartwertKnopf", "kdStartwertStatus", "Gespeichert."), True)
    p.pruefe("Fin: Zeile wieder geprüft", [z[3:5] for z in await tab.js(ZEILEN) if z[0] == "Mia Monteurin"],
             [["-12,25 h", "Steuerbüro · geprüft 11.11.2026"]])
    await tab.js("auswahlWert(document.getElementById('kdJahr'),'2028');document.getElementById('kdJahr').dispatchEvent(new Event('change',{bubbles:true}))")
    p.pruefe("Fin: Jahr 2028 leer", await tab.js("[document.getElementById('kdTage').value,document.getElementById('kdUebertrag').value]"), ["", ""])
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
            await tab.bild(f"lohnstammdaten_konten_{breite}_{name}")
            await _oeffnen(tab, mia)
            await tab.bild(f"konten_dialog_{breite}_{name}")
            await tab.js("document.getElementById('kontenDialog').close()")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")

    # ---- Büro – Auftrag ------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Zeitregeln geladen", await tab.oeffnen("/settings?n=20#time-rules", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: nur die eigene Zeile, „Ansehen“", await tab.js(ZEILEN), [["Bea Büro", "28,5 Tage (Vorgabe)", "—", "—", "—", "Ansehen"]])
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
