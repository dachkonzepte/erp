"""Klicktest: eine gemerkte Personalnummer freigeben (1.9.181, L1a-Korrekturen, Punkt 2) -- Einstellungen → Zeitregeln und DATEV.

    Tabelle          seit 1.9.189: bei 1440 px rollt die Tabelle waagrecht; nach rechts gerollt steht die Spalte Mitarbeiter (Kopf und Zeilen)
                     am linken Rand, obenauf, mit den Namen -- Bild
    Admin            Ada (1440): Mia „früher: 91008 freigeben“; 91030 trägt heute Kai (an der Sperre vorbei, wie aus einem alten Bestand) --
                     seit 1.9.191 Pia „früher: 91030 (trägt heute Kai Monteur)“ ohne Knopf (bis 1.9.190 „freigeben“, der Dialog meldete
                     dann den Fehler des Servers), derselbe POST 409, nichts geändert; 91008 -> Dialog
                     „Personalnummer 91008 freigeben“ mit Warnung (gehörte Mia Monteurin, DATEV, Tippfehler, Änderungshistorie) -- Bild;
                     „Freigeben“ -> Dialog zu, „Personalnummer 91008 freigegeben.“, Mia ohne „früher“; Tom bekommt 91008 („Gespeichert.“);
                     Änderungshistorie mit „Personalnummer freigegeben“, alt „gesperrt, gehörte Mia Monteurin“, neu „frei“ -- Bild; keine JS-Fehler
                     Seit 1.9.218 (L1a Stufe 7, Punkt 1): eigene Liste „Eingelesene Personalnummern ohne Person“ mit 00011 und 00012 -- Bild;
                     00011 „freigeben“ -> dieselbe Warnung, vorn „steht in der eingelesenen Liste vergebener Nummern“ -- Bild; freigegeben,
                     die Liste zeigt nur noch 00012
    Büro – Finanzen  Fin: „früher: 91030 (trägt heute Kai Monteur)“ ohne Knopf, derselbe POST vom Server 403 -- Bild; seit 1.9.218 keine Liste
                     der eingelesenen Nummern; keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_personalnummer_freigeben.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof payroll!=='undefined'&&payroll.length>0&&!!document.querySelector('#payrollRows [data-fruehere]')"
FRUEHER = "document.querySelector('[data-fruehere=\"{id}\"]')"
KNOPF = "document.querySelector('[data-klick=pnr-freigeben][data-nummer=\"{n}\"]')"
ROLLEN = "document.getElementById('payrollRollen')"
EINGELESEN = "[...document.querySelectorAll('#eingeleseneZeilen tr')].map(tr=>[...tr.cells].map(c=>c.textContent.trim()))"  # seit 1.9.218
# seit 1.9.189: Abstand der Kopf- und der ersten Zeilenzelle „Mitarbeiter“ zum linken Rand des Rollbereichs, ob sie dort obenauf liegt, die Namen,
# und ob die Spalte ERP-Nr. links unter ihr verschwunden ist
SPALTE = ("(r=>{const k=r.getBoundingClientRect(),kopf=r.querySelector('thead th'),z=[...document.querySelectorAll('#payrollRows tr')].map(tr=>tr.cells[0]),"
          "erste=z[0].getBoundingClientRect(),oben=document.elementFromPoint(k.left+20,erste.top+10);"
          "return [Math.round(kopf.getBoundingClientRect().left-k.left),Math.round(erste.left-k.left),z[0]===oben||z[0].contains(oben),"
          "z.map(c=>c.innerText.trim()).sort(),document.querySelector('#payrollRows tr').cells[1].getBoundingClientRect().right<=erste.right]})"
          "(document.getElementById('payrollRollen'))")


def befuellen(db, k):
    from datetime import datetime

    from app.models import AppUser, Employee, EmployeePayrollSettings, PersonalnummerVergabe

    ada = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([ada, fin])
    leute = {}
    for nr, vorname in (("M-1", "Mia"), ("M-2", "Tom"), ("M-3", "Pia"), ("M-4", "Kai")):
        leute[vorname] = Employee(employee_number=nr, first_name=vorname, last_name="Monteurin" if vorname in ("Mia", "Pia") else "Monteur",
                                  employee_group="gewerblich", active=True)
        db.add(leute[vorname])
    db.flush()
    db.add_all([EmployeePayrollSettings(employee_id=leute["Mia"].id, datev_personnel_number="91016", payroll_export_enabled=True),
                EmployeePayrollSettings(employee_id=leute["Kai"].id, datev_personnel_number="91030", payroll_export_enabled=True),
                PersonalnummerVergabe(nummer="91008", employee_id=leute["Mia"].id),
                PersonalnummerVergabe(nummer="91016", employee_id=leute["Mia"].id),
                PersonalnummerVergabe(nummer="91030", employee_id=leute["Pia"].id),
                # seit 1.9.218: eingelesen, ohne Person (erfundene Nummern)
                PersonalnummerVergabe(nummer="00011", employee_id=None, vergeben_am=datetime(2026, 11, 5, 9, 0)),
                PersonalnummerVergabe(nummer="00012", employee_id=None, vergeben_am=datetime(2026, 11, 5, 9, 0))])
    db.commit()
    return {"ada": k.cookies(ada), "fin": k.cookies(fin), **{v: e.id for v, e in leute.items()}}


async def _freigeben(tab) -> str:
    await tab.js("document.getElementById('pnrFreigabeStatus').textContent='';document.getElementById('payrollStatus').textContent='';pnrFreigeben()")
    await tab.warten("document.getElementById('pnrFreigabeStatus').textContent!==''||document.getElementById('payrollStatus').textContent!==''", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('pnrFreigabeDialog').open?'Dialog: '+document.getElementById('pnrFreigabeStatus').textContent"
                        ":document.getElementById('payrollStatus').textContent")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # ---- Admin ------------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["ada"])
    await tab.fenster(1440, 900)
    p.pruefe("Ada: Personalnummern geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)

    # seit 1.9.189 (L1a Stufe 2, Punkt 4): bei 1440 px rollt die Tabelle waagrecht, die Spalte Mitarbeiter bleibt stehen
    p.pruefe("1440 px: die Tabelle rollt waagrecht", await tab.js(f"{ROLLEN}.scrollWidth>{ROLLEN}.clientWidth"), True)
    await tab.js(f"{ROLLEN}.scrollIntoView({{block:'start'}});{ROLLEN}.scrollLeft={ROLLEN}.scrollWidth")
    await tab.warten(f"{ROLLEN}.scrollLeft>0", 5)
    p.pruefe("Nach rechts gerollt: Mitarbeiter am linken Rand, obenauf, Namen lesbar; ERP-Nr. darunter verschwunden", await tab.js(SPALTE),
             [0, 0, True, sorted(["Mia Monteurin", "Tom Monteur", "Pia Monteurin", "Kai Monteur"]), True])
    await tab.bild("lohn_tabelle_gerollt_1440")
    await tab.js(f"{ROLLEN}.scrollLeft=0")
    p.pruefe("Ada: frühere Nummern mit „freigeben“", await tab.js(
        f"[{FRUEHER.format(id=seed['Mia'])}.innerText.trim(),{FRUEHER.format(id=seed['Pia'])}.innerText.trim()]"),
        ["früher: 91008 freigeben", "früher: 91030 (trägt heute Kai Monteur)"])

    # seit 1.9.191 (L1a Stufe 2, Punkt 6): an 91030 (trägt Kai) kein Knopf -- der Server lehnt weiter ab, nichts geändert
    p.pruefe("Ada: an 91030 kein „freigeben“, dafür wer sie trägt", await tab.js(
        f"[!!{KNOPF.format(n='91030')},document.querySelector('[data-fruehere=\"{seed['Pia']}\"] [data-traegt=\"91030\"]').textContent]"),
        [False, "(trägt heute Kai Monteur)"])
    p.pruefe("Ada: 91030 trägt Kai -- der Server lehnt ab, nichts geändert", await tab.js(
        "fetch('/api/time-backoffice/personalnummern/freigeben',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({nummer:'91030'})}).then(async r=>[r.status,(await r.json()).detail])"),
        [409, "Die Personalnummer 91030 trägt heute Kai Monteur – freigeben geht nur, solange sie niemand trägt."])
    await tab.oeffnen("/settings#time-rules", BEREIT)
    p.pruefe("Ada: Pia weiter „früher: 91030“", await tab.js(FRUEHER.format(id=seed["Pia"]) + ".innerText.trim()"),
             "früher: 91030 (trägt heute Kai Monteur)")

    await tab.js(KNOPF.format(n="91008") + ".scrollIntoView({block:'center'});" + KNOPF.format(n="91008") + ".click()")
    p.pruefe("Ada: Warnung zu 91008", await tab.js("document.getElementById('pnrFreigabeWarnung').textContent"),
             "Die Personalnummer 91008 gehörte Mia Monteurin und ist für alle anderen gesperrt. Gibst du sie frei, kann jede andere Person sie "
             "bekommen. Stand sie schon in einer Lohnabrechnung, führt DATEV danach zwei Personen unter derselben Nummer – gib sie nur frei, "
             "wenn sie nie abgerechnet wurde (z. B. nach einem Tippfehler). Die Freigabe steht in der Änderungshistorie.")
    await tab.bild("freigeben_dialog")
    p.pruefe("Ada: 91008 freigegeben", await _freigeben(tab), "Personalnummer 91008 freigegeben.")
    p.pruefe("Ada: Dialog zu, Mia ohne „früher“", await tab.js(
        f"[document.getElementById('pnrFreigabeDialog').open,!!{FRUEHER.format(id=seed['Mia'])}]"), [False, False])

    await tab.js(f"document.getElementById('pnr-{seed['Tom']}').value='91008';document.getElementById('payrollStatus').textContent=''")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=lohn-speichern][data-mitarbeiter=\"{seed['Tom']}\"]').click()",
                                           "#payrollRows")
    p.pruefe("Ada: Tom bekommt 91008", await tab.js(
        f"[document.getElementById('payrollStatus').textContent,document.getElementById('pnr-{seed['Tom']}').value]"),
        ["Gespeichert. Die Personalnummer 91008 liegt außerhalb der vom Lohnbüro genannten Bereiche (genutzt: 00000–00299) – bitte prüfen.", "91008"])
    # seit 1.9.212 mit dem Kreis (bis 1.9.211 „Gespeichert.“), seit 1.9.219 „außerhalb“ (1.9.212–1.9.218 „… liegt im Kreis Azubis (ab 00200).“)
    p.pruefe("Ada: Änderungshistorie", await tab.js(
        "fetch('/api/audit-logs?entity_type=Personalnummer').then(r=>r.json()).then(l=>l.map(x=>[x.action,x.entity_id,x.old_value,x.new_value,"
        "x.actor_name]))"), [["Personalnummer freigegeben", "91008", "gesperrt, gehörte Mia Monteurin", "frei", "Ada Admin"]])
    await tab.js("document.getElementById('payrollRows').scrollIntoView({block:'start'})")
    await tab.bild("freigeben_danach")

    # seit 1.9.218 (L1a Stufe 7, Punkt 1): die eingelesenen Nummern ohne Person -- eigene Liste nur für den Admin, freigeben mit derselben Warnung
    await tab.warte_auf_ruhe()
    p.pruefe("Ada: Liste der eingelesenen Nummern", await tab.js(EINGELESEN),
             [["00011", "05.11.2026", "freigeben"], ["00012", "05.11.2026", "freigeben"]])
    await tab.js("document.getElementById('eingeleseneBlock').scrollIntoView({block:'start'})")
    await tab.bild("eingelesene_liste")
    await tab.js(KNOPF.format(n="00011") + ".click()")
    p.pruefe("Ada: dieselbe Warnung, vorn die eingelesene Liste", await tab.js("document.getElementById('pnrFreigabeWarnung').textContent"),
             "Die Personalnummer 00011 steht in der eingelesenen Liste vergebener Nummern und ist für alle gesperrt. Gibst du sie frei, kann jede "
             "andere Person sie bekommen. Stand sie schon in einer Lohnabrechnung, führt DATEV danach zwei Personen unter derselben Nummer – gib "
             "sie nur frei, wenn sie nie abgerechnet wurde (z. B. nach einem Tippfehler). Die Freigabe steht in der Änderungshistorie.")
    await tab.bild("eingelesen_dialog")
    await tab.js("document.getElementById('pnrFreigabeStatus').textContent='';document.getElementById('eingeleseneStatus').textContent='';pnrFreigeben()")
    await tab.warten("document.getElementById('pnrFreigabeStatus').textContent!==''||document.getElementById('eingeleseneStatus').textContent!==''", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Ada: 00011 freigegeben, die Liste zeigt nur noch 00012", [
        await tab.js("document.getElementById('pnrFreigabeDialog').open?'Dialog: '+document.getElementById('pnrFreigabeStatus').textContent"
                     ":document.getElementById('eingeleseneStatus').textContent"), await tab.js(EINGELESEN)],
        ["Personalnummer 00011 freigegeben.", [["00012", "05.11.2026", "freigeben"]]])
    p.pruefe("Ada: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Finanzen ------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: geladen", await tab.oeffnen("/settings?als=fin#time-rules", BEREIT), True)
    p.pruefe("Fin: „früher: 91030“ ohne Knopf", await tab.js(
        f"[{FRUEHER.format(id=seed['Pia'])}.innerText.trim(),document.querySelectorAll('[data-klick=pnr-freigeben]').length]"),
        ["früher: 91030 (trägt heute Kai Monteur)", 0])
    p.pruefe("Fin: der Server lehnt ab", await tab.js(
        "fetch('/api/time-backoffice/personalnummern/freigeben',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({nummer:'91030'})}).then(async r=>[r.status,(await r.json()).detail])"),
        [403, "Eine gemerkte Personalnummer gibt nur der Admin wieder frei."])
    p.pruefe("Fin: keine Liste der eingelesenen Nummern (seit 1.9.218)", await tab.js(
        "[!!document.getElementById('eingeleseneBlock'),document.body.textContent.includes('Eingelesene Personalnummern')]"), [False, False])
    await tab.js(f"{FRUEHER.format(id=seed['Pia'])}.scrollIntoView({{block:'center'}})")
    await tab.bild("freigeben_finanzen")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
