"""Klicktest: eine gemerkte Personalnummer freigeben (1.9.181, L1a-Korrekturen, Punkt 2) -- Einstellungen → Zeitregeln und DATEV.

    Admin            Ada (1440): Mia „früher: 91008 freigeben“, Pia „früher: 91030 freigeben“; 91030 trägt heute Kai (an der Sperre vorbei, wie
                     aus einem alten Bestand) -> Dialog mit Warnung, „Freigeben“ -> Meldung des Servers im Dialog, nichts geändert; 91008 -> Dialog
                     „Personalnummer 91008 freigeben“ mit Warnung (gehörte Mia Monteurin, DATEV, Tippfehler, Änderungshistorie) -- Bild;
                     „Freigeben“ -> Dialog zu, „Personalnummer 91008 freigegeben.“, Mia ohne „früher“; Tom bekommt 91008 („Gespeichert.“);
                     Änderungshistorie mit „Personalnummer freigegeben“, alt „gesperrt, gehörte Mia Monteurin“, neu „frei“ -- Bild; keine JS-Fehler
    Büro – Finanzen  Fin: „früher: 91030“ ohne Knopf, derselbe POST vom Server 403 -- Bild; keine JS-Fehler

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


def befuellen(db, k):
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
                PersonalnummerVergabe(nummer="91030", employee_id=leute["Pia"].id)])
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
    p.pruefe("Ada: frühere Nummern mit „freigeben“", await tab.js(
        f"[{FRUEHER.format(id=seed['Mia'])}.innerText.trim(),{FRUEHER.format(id=seed['Pia'])}.innerText.trim()]"),
        ["früher: 91008 freigeben", "früher: 91030 freigeben"])

    await tab.js(KNOPF.format(n="91030") + ".click()")
    p.pruefe("Ada: Dialog zu 91030 mit Warnung", await tab.js(
        "[document.getElementById('pnrFreigabeDialog').open,document.getElementById('pnrFreigabeTitel').textContent,"
        "document.getElementById('pnrFreigabeWarnung').textContent.startsWith('Die Personalnummer 91030 gehörte Pia Monteurin und ist für alle "
        "anderen gesperrt.')]"), [True, "Personalnummer 91030 freigeben", True])
    p.pruefe("Ada: 91030 trägt Kai -- Meldung, nichts geändert", await _freigeben(tab),
             "Dialog: Fehler: Die Personalnummer 91030 trägt heute Kai Monteur – freigeben geht nur, solange sie niemand trägt.")
    await tab.js("document.getElementById('pnrFreigabeDialog').close()")
    p.pruefe("Ada: Pia weiter „früher: 91030“", await tab.js(FRUEHER.format(id=seed["Pia"]) + ".innerText.trim()"), "früher: 91030 freigeben")

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
        f"[document.getElementById('payrollStatus').textContent,document.getElementById('pnr-{seed['Tom']}').value]"), ["Gespeichert.", "91008"])
    p.pruefe("Ada: Änderungshistorie", await tab.js(
        "fetch('/api/audit-logs?entity_type=Personalnummer').then(r=>r.json()).then(l=>l.map(x=>[x.action,x.entity_id,x.old_value,x.new_value,"
        "x.actor_name]))"), [["Personalnummer freigegeben", "91008", "gesperrt, gehörte Mia Monteurin", "frei", "Ada Admin"]])
    await tab.js("document.getElementById('payrollRows').scrollIntoView({block:'start'})")
    await tab.bild("freigeben_danach")
    p.pruefe("Ada: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Finanzen ------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: geladen", await tab.oeffnen("/settings?als=fin#time-rules", BEREIT), True)
    p.pruefe("Fin: „früher: 91030“ ohne Knopf", await tab.js(
        f"[{FRUEHER.format(id=seed['Pia'])}.innerText.trim(),document.querySelectorAll('[data-klick=pnr-freigeben]').length]"),
        ["früher: 91030", 0])
    p.pruefe("Fin: der Server lehnt ab", await tab.js(
        "fetch('/api/time-backoffice/personalnummern/freigeben',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({nummer:'91030'})}).then(async r=>[r.status,(await r.json()).detail])"),
        [403, "Eine gemerkte Personalnummer gibt nur der Admin wieder frei."])
    await tab.js(f"{FRUEHER.format(id=seed['Pia'])}.scrollIntoView({{block:'center'}})")
    await tab.bild("freigeben_finanzen")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
