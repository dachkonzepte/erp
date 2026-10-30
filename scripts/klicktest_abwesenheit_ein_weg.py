"""Klicktest: Abwesenheiten, ein Weg wie unter „Zeiten“ (1.9.146, Stufe 6, R1, Punkt 4).

Stehende Uhr 14.10.2026 10:00. Befüllt: Mia und Ole in Kolonne Nord, Kai mit einer früher direkt auf der Tafel eingetragenen Abwesenheit (Migration legt den Antrag an), Berta
(Büro – Auftrag) mit eigenem Mitarbeiter, Finn (Büro – Finanzen), Anna (Admin).

    Admin        Dialog „Abwesenheiten“: Art und Notiz sichtbar (P2); „Abwesenheit eintragen“ für Mia -> gleich genehmigt, in der Liste und auf der Tafel; „Zeiten → Abwesenheiten“ zeigt
                 alle, auch Kais mit dem Vermerk; „Löschen“ in „Zeiten“ mit Rückfrage -> Antrag „zurückgezogen“; „Löschen“ im Dialog der Tafel -> weg, Meldung; überlappend -> Meldung
    Finanzen     für Ole eintragen -> „Antrag gestellt“, zählt noch nicht; kein „Löschen“; „Zeiten“ zeigt den Antrag offen
    Büro–Auftrag Auswahl nur die eigene Person, gesperrt; „Abwesend“ ohne Art; „Antrag gestellt“; kein „Löschen“
    Fehler       Löschen scheitert (Server 500 nachgestellt) -> Meldung im Dialog statt Stille

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abwesenheit_ein_weg.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HEUTE = "2026-10-14"
UHR_MS = int(datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)
ROOT = Path(__file__).resolve().parent.parent


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeeAbsence, Team, TeamEmployee

    def person(nummer, name):
        return Employee(employee_number=nummer, first_name=name, last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)

    mia, ole, kai, bea, tim = person("M-1", "Mia"), person("M-2", "Ole"), person("M-3", "Kai"), person("M-4", "Bea"), person("M-5", "Tim")
    db.add_all([mia, ole, kai, bea, tim]); db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    finn = AppUser(username="finn", display_name="Finn Finanzen", role="buero_finanzen", password_hash=k.passwort())
    berta = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort(), employee_id=bea.id)
    team = Team(name="Nord", active=True)
    db.add_all([anna, finn, berta, team]); db.flush()
    for p in (mia, ole, kai, tim):
        db.add(TeamEmployee(team_id=team.id, employee_id=p.id))
    db.add(EmployeeAbsence(employee_id=kai.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 10, 15), end_date=date(2026, 10, 16), notes="Hochzeit"))
    db.add(EmployeeAbsence(employee_id=tim.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 10, 21), end_date=date(2026, 10, 21), notes="Kur"))
    db.commit()
    pfad = next((ROOT / "alembic" / "versions").glob("*_abwesenheiten_als_antraege.py"))
    spec = importlib.util.spec_from_file_location("migration_abwesenheiten", pfad)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.uebernehmen(db.connection())
    db.commit()
    return {"mia": mia.id, "ole": ole.id, "bea": bea.id, "anna": k.cookies(anna), "finn": k.cookies(finn), "berta": k.cookies(berta)}


BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0"
OFFEN = "document.getElementById('absenceDialog').open"


async def _dialog(tab):
    await tab.js("void openAbsences()")
    await tab.warten(OFFEN)


async def _eintragen(tab, *, mitarbeiter=None, von="2026-10-19", bis="2026-10-20", notiz="Attest liegt vor"):
    if mitarbeiter is not None:
        await tab.js(f"document.getElementById('absenceEmployee').value='{mitarbeiter}'")
    await tab.js(f"document.getElementById('absenceCategory').value='krankheit';document.getElementById('absenceStart').value='{von}';document.getElementById('absenceEnd').value='{bis}';"
                 f"document.getElementById('absenceNotes').value='{notiz}';document.getElementById('absenceStatus').textContent=''")
    await tab.js("void saveAbsence()")
    await tab.warten("document.getElementById('absenceStatus').textContent.length>0")
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('absenceStatus').textContent")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")  # Bilder hell
    await tab.browser_uhr_fest(UHR_MS)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.confirm=()=>true;")

    # --- Admin ---
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await _dialog(tab)
    zeilen = await tab.js("document.getElementById('absenceRows').textContent")
    p.pruefe("P2: Art und Notiz sichtbar", "Urlaub · Urlaub" in zeilen and "Hochzeit" in zeilen and "Abwesend" not in zeilen, True)
    p.pruefe("Admin: Auswahl offen", await tab.js("document.getElementById('absenceEmployee').disabled"), False)
    p.pruefe("Admin: gleich genehmigt", await _eintragen(tab, mitarbeiter=seed["mia"]), "Abwesenheit eingetragen.")
    p.pruefe("Admin: in der Liste", "Mia Test" in await tab.js("document.getElementById('absenceRows').textContent"), True)
    p.pruefe("Admin: auf der Tafel", await tab.js(f"!!board.employee_capacity['{seed['mia']}']['2026-10-19'].absence"), True)
    await tab.bild("abwesenheiten_admin")
    p.pruefe("Überlappend: Meldung", "bereits eine genehmigte Abwesenheit" in await _eintragen(tab, mitarbeiter=seed["mia"]), True)

    # Löschen scheitert: Meldung statt Stille
    mias = await tab.js(f"board.absences.find(a=>a.employee_id==={seed['mia']}).id")
    await tab.js("window.__echt=window.fetch;window.fetch=(u,o)=>o&&o.method==='DELETE'?Promise.resolve(new Response('{}',{status:500})):window.__echt(u,o)")
    await tab.js("document.getElementById('absenceStatus').textContent=''")
    await tab.js(f"void deleteAbsence({mias})")
    p.pruefe("Löschen scheitert: Meldung", await tab.warten("document.getElementById('absenceStatus').textContent.startsWith('Fehler:')"), True)
    await tab.js("window.fetch=window.__echt")
    await tab.js("document.getElementById('absenceStatus').textContent=''")
    await tab.js(f"void deleteAbsence({mias})")
    p.pruefe("Löschen: Meldung", await tab.warten("document.getElementById('absenceStatus').textContent==='Abwesenheit gelöscht.'"), True)
    p.pruefe("Löschen: weg", "Mia Test" in await tab.js("document.getElementById('absenceRows').textContent"), False)
    await tab.js("absenceDialog.close()")
    p.pruefe("Admin Tafel: JS-Fehler", tab.fehler, [])

    # --- Zeiten als Admin: alle, auch die früher direkt eingetragene ---
    await tab.oeffnen("/zeiten#abwesenheiten", "typeof A!=='undefined'&&A&&A.antraege")
    liste = await tab.js("document.getElementById('abwListe').textContent")
    p.pruefe("Zeiten: Kai aus der Migration", "Kai Test" in liste and "Auf der Plantafel eingetragen (vor 1.9.146)" in liste, True)
    p.pruefe("Zeiten: Mias Antrag zurückgezogen", "Mia Test" in liste and "Die genehmigte Abwesenheit wurde gelöscht." in liste, True)
    await tab.bild_ganz("zeiten_abwesenheiten_admin")
    genehmigt = await tab.js("A.antraege.filter(a=>a.status==='approved').length")
    await tab.js("document.querySelector('[data-aktion=\"abwl-fragen\"]').click()")
    p.pruefe("Zeiten: Rückfrage", "Abwesenheit löschen?" in await tab.js("document.getElementById('abwListe').textContent"), True)
    await tab.js("document.querySelector('[data-aktion=\"abwl-ja\"]').click()")
    p.pruefe("Zeiten: gelöscht, Antrag folgt", await tab.warten(f"A.antraege.filter(a=>a.status==='approved').length==={genehmigt - 1}"), True)
    p.pruefe("Zeiten: JS-Fehler", tab.fehler, [])

    # --- Büro – Finanzen ---
    await tab.anmelden(seed["finn"])
    await tab.oeffnen("/planning", BEREIT)
    await _dialog(tab)
    p.pruefe("Finanzen: für andere", await tab.js("document.getElementById('absenceEmployee').options.length>=3&&!document.getElementById('absenceEmployee').disabled"), True)
    p.pruefe("Finanzen: Antrag gestellt", (await _eintragen(tab, mitarbeiter=seed["ole"], notiz="Reha")).startswith("Antrag gestellt"), True)
    p.pruefe("Finanzen: zählt noch nicht", await tab.js(f"board.absences.some(a=>a.employee_id==={seed['ole']})"), False)
    await tab.js("absenceDialog.close()")
    await tab.oeffnen("/zeiten#abwesenheiten", "typeof A!=='undefined'&&A&&A.antraege")
    p.pruefe("Finanzen: Antrag in „Zeiten“ offen", await tab.js(f"A.antraege.some(a=>a.employee_id==={seed['ole']}&&a.status==='pending')"), True)
    p.pruefe("Finanzen: kein Löschen", await tab.js("!!document.querySelector('[data-aktion=\"abwl-fragen\"]')"), False)
    p.pruefe("Finanzen: JS-Fehler", tab.fehler, [])

    # --- Büro – Auftrag ---
    await tab.anmelden(seed["berta"])
    await tab.oeffnen("/planning", BEREIT)
    await _dialog(tab)
    p.pruefe("Auftrag: nur sich", await tab.js("[...document.getElementById('absenceEmployee').options].map(o=>o.textContent)"), ["Bea Test"])
    p.pruefe("Auftrag: Auswahl gesperrt", await tab.js("document.getElementById('absenceEmployee').disabled"), True)
    p.pruefe("Auftrag: kein Löschen", await tab.js("document.querySelectorAll('#absenceRows button').length"), 0)
    p.pruefe("Auftrag: nur „Abwesend“", await tab.js("document.getElementById('absenceRows').textContent.includes('Abwesend')&&!/Hochzeit|Kur|Urlaub/.test(document.getElementById('absenceRows').textContent)"), True)
    p.pruefe("Auftrag: Antrag gestellt", (await _eintragen(tab, notiz="Zahnarzt")).startswith("Antrag gestellt"), True)
    await tab.bild("abwesenheiten_buero_auftrag")
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
