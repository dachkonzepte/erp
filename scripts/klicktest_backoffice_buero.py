"""Klicktest: Zeiterfassungs-Backoffice für die Büro-Rollen (1.8.117, Vorgabe vom 16.10.2026, Punkt 3; seit 1.9.89 Stufe 4, R5a).

Bis 1.8.116 brach die Seite für jede Rolle außer Admin mit "Dieses Backoffice ist nur für Administratoren verfügbar" ab, obwohl Seite und
Endpunkte seit 1.4.8 Büro – Auftrag und Büro – Finanzen offenstehen und die Seitenleiste den Link zeigt. Seit 1.9.89 (Entscheidungen
Tobias): Büro – Auftrag liest die Zeiten nur, Zeiten anderer und Lohndaten haben Admin und Büro – Finanzen.

    Büro – Auftrag  Bea (mit Mitarbeiterin verknüpft): Dashboard mit Kennzahlen, kein Fehler; ihr eigener offener Antrag ohne
                    Genehmigen/Ablehnen, mit Hinweis "nur deine eigenen Anträge" (Mias Antrag sieht nur ein Admin, wie der Server es
                    regelt); Buchungen: alle "nur lesen", keine Knöpfe, Hinweis "du kannst sie lesen" über der Liste; keine Anfrage an
                    Buchungskontext und Personalnummern; keine Reiter "Stundenzettel" und "DATEV / Lohn"; Stundenzettel PDF und CSV,
                    DATEV-Export vom Server 403; keine JS-Fehler; 412 px ohne waagrechte Scrollleiste
    Büro – Finanzen Fin (ohne Mitarbeiter): Seite lädt, Buchungskontext gelesen, keine Anfrage an Anträge (wäre 403), Hinweis "keinem
                    Mitarbeiter zugeordnet"; Buchungen am Ersten (abgeschlossen) "nur Admin", am Zweiten mit Bearbeiten/Löschen, Hinweis
                    über der Liste; Mias Buchung (fremd) auf 2,5 Std. geändert und gespeichert; Stundenzettel PDF und CSV, DATEV-Export:
                    200; "Abgeschlossen bis" auf den Zweiten vorgerückt -- die Buchungen sofort "nur Admin"; zurück auf den Ersten mit
                    Meldung abgelehnt, nichts gesendet, kein Knopf "Abschluss aufheben"; keine JS-Fehler; 412 px ohne waagrechte Scrollleiste

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_backoffice_buero.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "document.getElementById('metrics')&&document.getElementById('metrics').children.length>0"


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.models import (AppUser, Customer, Employee, EmployeeAbsenceRequest, Order, OrderItem, Project, TimeEntry,
                            TimeTrackingSettings)
    from app.project_pipeline_columns import default_pipeline_column_id

    monat = berlin_today().replace(day=1)
    kunde = Customer(name="Kundin Backoffice", last_name="Backoffice")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-BO-1", name="Dach Backoffice", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-BO-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-BO-1", title="Auftrag BO",
                    customer_name="Kundin Backoffice", customer_number="K-1")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=Decimal("10"),
                     unit="m²", unit_price=Decimal("50")))
    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="angestellt", active=True,
                      hourly_wage=Decimal("22.00"))
    mia_ma = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                      hourly_wage=Decimal("22.00"))
    db.add_all([bea_ma, mia_ma]); db.flush()
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id, password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([bea, fin]); db.flush()

    def te(ma, tag, stunden):
        return TimeEntry(employee_id=ma.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site",
                         counts_as_productive=True, hours=Decimal(stunden), status="booked", source="manual")

    eigen_zu, eigen_offen = te(bea_ma, monat, "1.00"), te(bea_ma, monat + timedelta(days=1), "1.50")
    mia_offen = te(mia_ma, monat + timedelta(days=1), "7.00")
    db.add_all([te(mia_ma, monat, "8.00"), mia_offen, eigen_zu, eigen_offen])
    for ma in (mia_ma, bea_ma):
        db.add(EmployeeAbsenceRequest(employee_id=ma.id, absence_type="Urlaub", start_date=monat + timedelta(days=40),
                                      end_date=monat + timedelta(days=41), status="pending"))
    einstellungen = db.get(TimeTrackingSettings, 1)
    einstellungen.locked_until = monat
    db.commit()
    return {"bea": k.cookies(bea), "fin": k.cookies(fin), "eigen_zu": eigen_zu.id, "eigen_offen": eigen_offen.id, "mia_offen": mia_offen.id,
            "monat": monat.isoformat(), "abschluss_neu": (monat + timedelta(days=1)).isoformat()}


def _zeile(eintrag_id: int) -> str:
    return f"[...document.querySelectorAll('#entryRows tr')].find(tr=>tr.querySelector('[data-klick=buchungBearbeiten][data-id=\"{eintrag_id}\"]'))"


async def _exporte(tab):
    # den Körper lesen: sonst hält Chrome die Anfrage offen (das Netzprotokoll zeigte sie so, der Server war längst fertig)
    return await tab.js("Promise.all(['timesheet.pdf','timesheet.csv'].map(x=>'/api/time-backoffice/'+x+'?'+qs())"
                        ".concat([`/api/time-backoffice/datev-export?start_date=${$('from').value}&end_date=${$('to').value}`])"
                        ".map(u=>fetch(u).then(r=>r.arrayBuffer().then(()=>r.status))))")


def _buchungen():
    return ("[...document.querySelectorAll('#entryRows tr')].map(tr=>[tr.cells[1].innerText.split('\\n')[0],"
            "tr.querySelectorAll('button').length,tr.cells[8].innerText.trim()])")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.confirm=()=>true;window.alert=m=>{window.__alert=m};")

    # ---- Büro – Auftrag: liest nur (seit 1.9.89) ------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    vorher = len(tab.netz.verlauf)
    p.pruefe("Bea: Backoffice geladen", await tab.oeffnen("/time-backoffice", BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    p.pruefe("Bea: kein Fehler auf der Seite", await tab.js("document.querySelector('main').innerText.includes('konnte nicht geladen')"
                                                            "||document.body.innerText.includes('nur für Administratoren verfügbar')"), False)
    p.pruefe("Bea: Kennzahl Buchungen", await tab.js("[...document.querySelectorAll('#metrics *')].some(x=>x.innerText.trim()==='4')"),
             True)
    p.pruefe("Bea: keine Anfrage an Buchungskontext und Personalnummern", [
        tab.netz.suche(r"/api/time-tracking/context", "GET", ab=vorher), tab.netz.suche(r"/api/time-backoffice/payroll-employees", "GET", ab=vorher)],
        [[], []])
    p.pruefe("Bea: eigener offener Antrag im Dashboard, ohne Entscheiden, nur die eigenen", await tab.js(
        "(()=>{const t=document.getElementById('absenceDashboard').innerText;return [t.includes('Bea Büro'),t.includes('Mia Monteurin'),"
        "t.includes('Genehmigen oder Ablehnen dürfen nur Administratoren.'),t.includes('Hier stehen nur deine eigenen Anträge'),"
        "!!document.querySelector('#absenceDashboard button')]})()"), [True, False, True, True, False])
    p.pruefe("Bea: keine Reiter Stundenzettel und DATEV / Lohn, kein Abschluss", await tab.js(
        "[!!document.querySelector('[data-tab=timesheets]'),!!document.querySelector('[data-tab=datev]'),!!document.getElementById('lockDate')]"),
        [False, False, False])

    await tab.js("showTab('entries')")
    zeilen = await tab.js(_buchungen())
    p.pruefe("Bea: Buchungen nur lesen (Mitarbeiterin, Knöpfe, Spalte)", sorted(map(tuple, zeilen or [])), sorted([
        ("Bea Büro", 0, "nur lesen"), ("Bea Büro", 0, "nur lesen"), ("Mia Monteurin", 0, "nur lesen"), ("Mia Monteurin", 0, "nur lesen")]))
    p.pruefe("Bea: Hinweis über der Liste", await tab.js("document.getElementById('nurAdminBuchung').innerText"),
             "Zeiten buchen und ändern Admin und Büro – Finanzen – du kannst sie lesen.")

    await tab.js("showTab('absences')")
    p.pruefe("Bea: Abwesenheiten -- der eigene Antrag ohne Genehmigen/Ablehnen", await tab.js(
        "[document.getElementById('absenceRows').innerText.includes('Bea Büro'),"
        "document.getElementById('absenceRows').innerText.includes('Genehmigen oder Ablehnen dürfen nur Administratoren.'),"
        "document.querySelectorAll('#absenceRows button').length]"), [True, True, 0])
    p.pruefe("Bea: Stundenzettel PDF, CSV und DATEV-Export vom Server abgelehnt", await _exporte(tab), [403, 403, 403])
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    await tab.fenster(412, 900, mobil=True)
    p.pruefe("Bea: 412 px geladen", await tab.oeffnen("/time-backoffice", BEREIT), True)
    p.pruefe("Bea: 412 px ohne waagrechte Scrollleiste", await tab.js("document.documentElement.scrollWidth<=window.innerWidth+1"), True)
    await tab.bild("backoffice_bea_412")
    await tab.fenster(1400, 1000)

    # ---- Büro – Finanzen ohne Mitarbeiter: Zeiten aller und Lohndaten (seit 1.9.89) ------------------------------------------
    await tab.anmelden(seed["fin"])
    vorher = len(tab.netz.verlauf)
    p.pruefe("Fin: Backoffice geladen", await tab.oeffnen("/time-backoffice", BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    p.pruefe("Fin: Buchungskontext gelesen, keine Anfrage an Anträge", [
        len(tab.netz.suche(r"/api/time-tracking/context", "GET", ab=vorher)) > 0, tab.netz.suche(r"/api/absence-requests", "GET", ab=vorher)],
        [True, []])
    # seit 1.8.159 genau die gemeinsame Meldung (app/meldungen.py::KEIN_MITARBEITER)
    p.pruefe("Fin: Hinweis 'keinem Mitarbeiter zugeordnet'", await tab.js(
        "document.getElementById('absenceDashboard').innerText.includes('Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator "
        "kann das unter Einstellungen → Benutzer und Zugriff ändern.')"), True)
    await tab.js("showTab('entries')")
    p.pruefe("Fin: Buchungen (Mitarbeiterin, Knöpfe, Spalte)", sorted(map(tuple, await tab.js(_buchungen()) or [])), sorted([
        ("Bea Büro", 0, "nur Admin"), ("Bea Büro", 2, "Bearbeiten Löschen"), ("Mia Monteurin", 0, "nur Admin"),
        ("Mia Monteurin", 2, "Bearbeiten Löschen")]))
    p.pruefe("Fin: Hinweis über der Liste", await tab.js("document.getElementById('nurAdminBuchung').innerText"),
             "Buchungen im abgeschlossenen Zeitraum ändern und löschen nur Administratoren.")

    await tab.js(f"document.querySelector('[data-klick=buchungBearbeiten][data-id=\"{seed['mia_offen']}\"]').click()")
    p.pruefe("Fin: Bearbeiten-Dialog offen (Mias Buchung)", await tab.warten("document.getElementById('editDialog').open", 10), True)
    await tab.js("document.getElementById('editHours').value='2,5'")
    await tab.warte_auf_neu_geladene_liste("saveEntryEdit()", "#entryRows")
    p.pruefe("Fin: Mias Buchung gespeichert (2,50 Std.)", await tab.js(
        f"(()=>{{const tr={_zeile(seed['mia_offen'])};return tr?tr.cells[7].innerText.trim():null}})()"), "2,50")
    # seit 1.9.92: DATEV nur für einen abgeschlossenen Zeitraum -- der laufende Monat ist es nicht (409, nicht 403)
    p.pruefe("Fin: Stundenzettel PDF und CSV, DATEV-Export für den offenen Monat abgelehnt", await _exporte(tab), [200, 200, 409])

    await tab.js("showTab('datev')")
    p.pruefe("Fin: kein Knopf 'Abschluss aufheben', stattdessen der Hinweis", await tab.js(
        "[[...document.querySelectorAll('#tab-datev button')].some(b=>b.innerText.includes('aufheben')),"
        "!!document.getElementById('nurAdminOeffnen')]"), [False, True])
    await tab.js(f"document.getElementById('lockDate').value='{seed['abschluss_neu']}'")
    await tab.js("saveLock()")
    p.pruefe("Fin: Abschluss vorgerückt", await tab.warten(
        f"document.getElementById('lockStatus').innerText.includes(fd('{seed['abschluss_neu']}'))", 10), True)
    p.pruefe("Fin: Buchungen am Zweiten sofort abgeschlossen -> nur Admin", await tab.warten(
        f"!({_zeile(seed['mia_offen'])})&&!({_zeile(seed['eigen_offen'])})", 10), True)
    await tab.nachlesen()
    puts = len(tab.netz.suche(r"/api/time-backoffice/lock$", "PUT"))
    await tab.js(f"document.getElementById('lockDate').value='{seed['monat']}'")
    await tab.js("saveLock()")
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    p.pruefe("Fin: zurück auf den Ersten abgelehnt, nichts gesendet", [
        await tab.js("document.getElementById('lockMsg').innerText"), len(tab.netz.suche(r"/api/time-backoffice/lock$", "PUT")) - puts,
        await tab.js(f"document.getElementById('lockStatus').innerText.includes(fd('{seed['abschluss_neu']}'))")],
        ["Einen abgeschlossenen Zeitraum wieder öffnen darf nur ein Administrator.", 0, True])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])
    await tab.bild("backoffice_fin")

    await tab.fenster(412, 900, mobil=True)
    p.pruefe("Fin: 412 px geladen", await tab.oeffnen("/time-backoffice", BEREIT), True)
    p.pruefe("Fin: 412 px ohne waagrechte Scrollleiste", await tab.js("document.documentElement.scrollWidth<=window.innerWidth+1"), True)
    print(json.dumps({"bea_zeilen": zeilen}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
