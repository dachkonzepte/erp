"""Bildgrundlage für das Redesign (seit 1.8.126, Stufe 0d): ganzseitige Screenshots jeder Seite und ein Vergleich zweier Läufe.

AUFRUF (aus dem Projektordner, in der Projekt-venv):

    .venv\\Scripts\\python.exe scripts\\bildgrundlage.py [aufnehmen] [--ziel ORDNER] [--nur TEIL ...] [Optionen von cdp_klicktest]
    .venv\\Scripts\\python.exe scripts\\bildgrundlage.py vergleichen ALT NEU [--differenzen ORDNER]

aufnehmen   Eine Testinstanz (scripts/cdp_klicktest.py, Wegwerf-SQLite, Regel 16) mit festen Testdaten (befuellen() unten) und
            stehender Uhr (UHR, Server, Befüllen und Browser), dann je Eintrag in AUFNAHMEN, je Rolle des Eintrags, je Thema (hell,
            dunkel) und je Breite (412 px als Gerät, 1440 px) ein ganzseitiges PNG; die Seiten der Monteurin zusätzlich auf dem
            TerraPad 1201, hoch (800 × 1100) und quer (1280 × 620), als Gerät (seit 1.8.131, Fenster seit 1.8.156). Danach die
            Zustände des Rahmens (ZUSTAENDE, seit
            1.8.131): Menü aufgeklappt, Seitenleiste eingeklappt (beide seit 1.8.164 nur fürs Büro), Kontomenü offen, Objektsuche
            offen (Monteurin, seit 1.8.164), Seitenleiste von Büro – Auftrag (bis 1.8.161 auch „Seitenleiste ganz unten“ -- seit
            1.8.162 scrollt sie bei 1440 × 900 nicht mehr, geprüft beim Aufnehmen) -- je auf
            der Seite aus ZUSTANDSSEITEN, je Thema, als Bild des Fensters (nicht der ganzen Seite: die Leiste und
            die Menüs hängen am Fenster). Vor jedem Bild: Seite geladen und keine Anfrage mehr unterwegs (seit 0,8 s), Schriften
            bereit, Animationen, Übergänge und Textcursor aus, kein Fokus. Geprüft je Bild: geladen und Status 200 (die Sperrseite
            403) -- sonst zeigte das Bild die Sperrseite statt der Seite --, bei einem Zustand dazu, dass er eingetreten ist;
            Rückgabecode 1.
            --ziel      Vorgabe bildgrundlage/<commit>[-geaendert] im Projektordner (in .gitignore; "-geaendert", wenn die
                        Arbeitskopie Änderungen hat). Muss leer sein oder fehlen.
            --nur TEIL  nur Einträge, deren Name TEIL enthält (mehrfach möglich).
            Dazu bilder.json: je Bild Seite, Vorlage, Adresse, Rolle, Thema, Breite, Höhe, Status, JS-Fehler.
vergleichen Je Bild die Zahl abweichender Pixel (ein Pixel weicht ab, wenn ein Kanal anders ist) und ein Differenzbild (das neue Bild
            blass, Abweichungen rot) in --differenzen (Vorgabe neben NEU: vergleich_<ALT>_<NEU>, bei gleichen Ordnernamen die
            Namen der übergeordneten Ordner). Rückgabecode 0 = alles gleich,
            1 = mindestens ein Bild weicht ab, fehlt oder ist neu, 2 = Abbruch (seit 1.8.127): die Chrome-Versionen in bilder.json
            sind verschieden -- ein anderer Chrome zeichnet anders, dann zuerst die Grundlage neu erzeugen.

Rollen: "buero" ist Büro – Finanzen (die Büro-Rolle, die jede Büroseite öffnet), "monteur" die Monteurin mit Planungsbezug zum Auftrag,
"admin" für Adressimport und (seit 1.8.134) Benutzer (die Seiten nur für Administratoren), "anonym" ohne Anmeldung (Anmeldeseite), "buero_auftrag" (seit
1.8.131) nur für die Seitenleiste dieser Rolle. Die Sperrseite zeigt die Monteurin auf /projects. tests/test_v431_bildgrundlage.py prüft, dass jede Seite aus tests/vorlagen_js.py::seiten() hier steht, jede
Adresse für ihre Rolle die genannte Vorlage zeichnet und jede Seite, die die Monteurin öffnet, mit ihrer Rolle aufgenommen wird.

Fest gehalten, damit zwei Läufe gleich sind: Uhr (UHR, stehend), alle gespeicherten Zeitstempel (nach dem Befüllen auf UHR gesetzt,
außer dem Ablauf der Sitzungen und BEWUSST_GESETZT), Versionsnummer und Changelog der Instanz (cdp_klicktest KLICKTEST_ANZEIGE -- beide
ändern sich mit jedem Commit), localStorage (leer bei jedem Laden), Thema über prefers-color-scheme, Text ohne LCD-Kantenglättung
(CHROME_ARGUMENTE), kein Flush mit zwei geänderten Objekten in den Testdaten (Projektstatus vorab, siehe befuellen()). Verglichen werden
volle Läufe -- mit --nur hängt eine Seite davon ab, welche vorher besucht wurden. Unter einer Gegenprobe (Marker GEGENPROBE unter app/)
gilt das Zeitlimit von 2 min je Bild statt für den ganzen Lauf (zeitlimit_je_schritt)."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import ANZEIGE_ENV, ROOT, klicktest_main  # noqa: E402

UHR = "2026-10-14 10:00"  # Mittwoch; steht in Befüllen, Server und Browser
# Seit 1.9.6: Dachtypen in den Testdaten nur aus der Auswahlliste ("Flachdach", wie das Programm speichert) -- dazu genau ein Altwert als
# eigener Fall (andere Schreibweise, wie aus älteren Versionen oder über die Schnittstelle), an einer eigenen Prüfvorlage
# (tests/test_v443_dachtyp.py). Bis 1.9.5 trug die einzige Prüfvorlage "flachdach".
DACHTYP_ALTWERT = "flachdach"
BUERO, MONTEUR, ADMIN, ANONYM = "buero", "monteur", "admin", "anonym"
BUERO_AUFTRAG = "buero_auftrag"  # seit 1.8.131, nur für die Seitenleiste dieser Rolle (ZUSTAENDE)
THEMEN = ("hell", "dunkel")
BREITEN = (412, 1440)
# Seit 1.8.131 (Stufe 2a): die Seiten der Monteurin zusätzlich auf dem TerraPad -- seit 1.8.156 die Fenster des TerraPad 1201 im
# Browser: hoch 800 x 1100, quer 1280 x 620 (bis 1.8.155 die ganze Anzeige, 800 x 1280 und 1280 x 800)
TABLET = (800, 1280)
GERAETE = (412, *TABLET)  # als Gerät aufgenommen (mobile: Viewport wie auf dem Gerät, Bildlaufleisten über dem Inhalt)
STARTHOEHE = 900
STARTHOEHEN = {800: 1100, 1280: 620}  # Höhe des Fensters, wo sie von STARTHOEHE abweicht
HOECHSTE_HOEHE = 16000  # Chrome zeichnet höhere Bilder nicht zuverlässig
CHANGELOG = Path(__file__).resolve().parent / "bildgrundlage_changelog.md"
# Text ohne farbige Subpixel-Kanten (ClearType): deren Stärke hing davon ab, welche Seiten der Browser vorher gezeichnet hatte -- der
# Verlauf allein (--nur verlauf) wich im ganzen Text vom Verlauf eines vollen Laufs ab, bei gleichem Layout
CHROME_ARGUMENTE = ["--disable-lcd-text"]


@dataclass(frozen=True)
class Aufnahme:
    name: str     # Teil des Dateinamens
    vorlage: str  # die Vorlage, die die Adresse für die Rollen zeichnet
    pfad: str     # Adresse; {schluessel} kommt aus dem Seed
    rollen: tuple


A = Aufnahme
AUFNAHMEN = (
    A("start", "dashboard.html", "/", (BUERO,)),
    A("aufgaben", "tasks.html", "/tasks", (BUERO,)),
    A("kalender", "calendar.html", "/kalender", (BUERO,)),
    A("anfragen", "inquiries.html", "/inquiries", (BUERO,)),
    A("projekte", "projects.html", "/projects", (BUERO,)),
    A("projekt_neu", "project_form.html", "/projects/new", (BUERO,)),
    A("projektmappe", "project_folder.html", "/projects/{projekt}", (BUERO,)),
    A("angebot_neu", "quote_form.html", "/quotes/new", (BUERO,)),
    A("angebot", "quote_editor.html", "/quotes/{angebot}/edit", (BUERO,)),
    A("auftrag", "order.html", "/orders/{auftrag}", (BUERO,)),
    A("arbeitsvorbereitung", "work_preparation.html", "/orders/{auftrag}/work-preparation", (BUERO,)),
    A("einsatzbericht", "service_reports.html", "/orders/{auftrag}/service-reports", (BUERO, MONTEUR)),
    A("rechnung", "invoice_detail.html", "/invoices/{rechnung}", (BUERO,)),
    A("plantafel", "planning.html", "/planning", (BUERO,)),
    A("checklisten", "checklists.html", "/checklisten", (BUERO,)),
    A("checklistenvorlagen", "checklist_templates.html", "/checklisten/vorlagen", (BUERO,)),
    A("checklistenvorlage", "checklist_template.html", "/checklisten/vorlagen/{checklistenvorlage}", (BUERO,)),
    A("checkliste", "checklist.html", "/checklisten/{checkliste}", (BUERO, MONTEUR)),
    A("checklisten_auftrag", "checklist_order.html", "/checklisten/auftrag/{auftrag}", (BUERO, MONTEUR)),
    A("wartungen", "maintenance_contracts.html", "/maintenance-contracts", (BUERO,)),
    A("wartungsvertrag", "maintenance_contract.html", "/maintenance-contracts/{vertrag}", (BUERO,)),
    A("befunde", "findings.html", "/findings", (BUERO,)),
    A("pruefvorlagen", "inspection_templates.html", "/inspection-templates", (BUERO,)),
    A("pruefvorlage", "inspection_template.html", "/inspection-templates/{pruefvorlage}", (BUERO,)),
    A("finanzen", "finanzen.html", "/finanzen", (BUERO,)),
    A("mahnwesen", "mahnwesen.html", "/mahnwesen", (BUERO,)),
    A("eingangsrechnungen", "incoming_invoices.html", "/eingangsrechnungen", (BUERO,)),
    A("betriebskosten", "recurring_costs.html", "/betriebskosten", (BUERO,)),
    A("zeiterfassung", "time_tracking.html", "/time-tracking", (BUERO,)),
    A("zeiterfassung_monteur", "time_tracking_field.html", "/time-tracking", (MONTEUR,)),
    A("backoffice", "time_backoffice.html", "/time-backoffice", (BUERO,)),
    A("stammdaten", "master_data.html", "/master-data", (BUERO,)),
    A("stammdaten_mitarbeiter", "master_data_form.html", "/master-data/employees/{mitarbeiter}/edit", (BUERO,)),
    A("kunde", "customer.html", "/customers/{kunde}", (BUERO,)),
    A("objekt", "property.html", "/properties/{objekt}", (BUERO,)),
    A("dachflaeche", "roof_area.html", "/roof-areas/{dachflaeche}", (BUERO,)),
    A("betriebsmittel", "operational_asset.html", "/betriebsmittel/{geraet}", (BUERO,)),
    A("betriebsmittel_monteur", "operational_asset_field.html", "/betriebsmittel/{geraet}", (MONTEUR,)),
    A("leistungskatalog", "index.html", "/leistungskatalog", (BUERO,)),
    A("leistung", "service_form.html", "/services/{leistung}/edit", (BUERO,)),
    A("einstellungen", "settings.html", "/settings", (BUERO,)),
    A("benutzer", "users.html", "/users", (ADMIN,)),  # seit 1.8.134 nur Admin (require_admin)
    A("verlauf", "history.html", "/history", (BUERO,)),
    A("adressimport", "address_import.html", "/address-import", (ADMIN,)),  # nur Admin (require_admin)
    A("versandprotokoll", "email_dispatches.html", "/versandprotokoll", (BUERO,)),
    A("changelog", "changelog.html", "/changelog", (BUERO,)),
    A("suche", "search_results.html", "/suche?q=Halle", (BUERO,)),
    A("konto", "account.html", "/account", (BUERO, MONTEUR)),
    A("mobil", "mobil.html", "/mobil", (BUERO, MONTEUR)),
    A("mobil_objekt", "mobil_objekt.html", "/mobil/objekt/{objekt}", (BUERO, MONTEUR)),
    A("stundenzettel", "field_timesheet.html", "/mobil/stundenzettel", (BUERO, MONTEUR)),
    A("anmeldung", "login.html", "/login", (ANONYM,)),
    A("sperrseite", "access_denied.html", "/projects", (MONTEUR,)),
)
AUFNAHME = {a.name: a for a in AUFNAHMEN}


@dataclass(frozen=True)
class Zustand:
    """Ein Zustand des Rahmens (Seitenleiste _sidebar.html, Kopfzeile _topbar.html), seit 1.8.131. aktion führt ihn nach dem Laden
    herbei und gibt zurück, ob er eingetreten ist (wahr) -- sonst zeigte das Bild die Seite ohne ihn."""
    name: str
    aktion: str
    breiten: tuple
    rollen: tuple


# Die Seite je Rolle: für das Büro die Startseite, für die Monteurin der Einsatzbericht (bis 1.8.163 eine ihrer zwei Seiten mit
# Seitenleiste und Kopfzeile; seit 1.8.164 hat sie überall den Monteurskopf, _mobile_header.html, mit Lupe und Kontomenü)
ZUSTANDSSEITEN = {BUERO: "start", BUERO_AUFTRAG: "start", MONTEUR: "einsatzbericht"}
_LEISTE_SCROLLT = "[...document.querySelectorAll('#appSidebar,#appSidebar .app-sidebar-nav')].find(e=>e.scrollHeight>e.clientHeight+1)"
Z = Zustand
ZUSTAENDE = (
    # Menü und eingeklappte Leiste seit 1.8.164 nur fürs Büro (die Monteurin hat keine Seitenleiste mehr)
    Z("menue_offen", "(()=>{document.getElementById('appTopbarMenuBtn').click();"
                     "return document.getElementById('appSidebar').classList.contains('mobile-open')})()", (412, 800), (BUERO,)),
    # seit 1.8.162 am Menüknopf der Kopfzeile (bis dahin #appSidebarToggle unten in der Leiste)
    Z("leiste_eingeklappt", "(()=>{document.getElementById('appTopbarMenuBtn').click();"
                            "return document.getElementById('appSidebar').classList.contains('collapsed')})()", (1280, 1440),
      (BUERO,)),
    # dasselbe Kontomenü (_kontomenue.html) in Kopfzeile und Monteurskopf
    Z("kontomenue_offen", "(()=>{document.getElementById('appTopbarAccountBtn').click();"
                          "return !document.getElementById('appTopbarAccountMenu').hidden})()", (1440,), (BUERO, MONTEUR)),
    # seit 1.8.164: die Lupe des Monteurskopfs öffnet die Objektsuche unter dem Kopf
    Z("suche_offen", "(()=>{document.getElementById('mobileSearchToggle').click();"
                     "return !document.getElementById('mobileSearchPanel').hidden})()", (800, 1280), (MONTEUR,)),
    Z("leiste", "!!document.getElementById('appSidebar')", (1440,), (BUERO_AUFTRAG,)),
)
LEISTE_OHNE_BILDLAUF = f"!{_LEISTE_SCROLLT}"


@dataclass(frozen=True)
class Bild:
    rolle: str
    thema: str
    breite: int
    aufnahme: Aufnahme
    zustand: Zustand | None = None

    @property
    def datei(self) -> str:
        seite = self.aufnahme.name + (f"--{self.zustand.name}" if self.zustand else "")
        return f"{self.rolle}__{self.thema}__{self.breite}__{seite}.png"


def geplante_bilder(nur: list | None = None) -> list[Bild]:
    """Alle Bilder in der Reihenfolge der Aufnahme: zuerst wie bis 1.8.130 (Rolle, Thema, Breite, Seite), dann die Monteurin auf dem
    TerraPad, dann die Zustände -- die bisherigen Bilder entstehen in derselben Reihenfolge wie vorher. nur: Teile der Seitennamen."""
    def gewollt(a: Aufnahme) -> bool:
        return not nur or any(t in a.name for t in nur)

    bilder = [Bild(rolle, thema, breite, a) for rolle in (BUERO, MONTEUR, ADMIN, ANONYM) for thema in THEMEN for breite in BREITEN
              for a in AUFNAHMEN if rolle in a.rollen and gewollt(a)]
    bilder += [Bild(MONTEUR, thema, breite, a) for thema in THEMEN for breite in TABLET for a in AUFNAHMEN
               if MONTEUR in a.rollen and gewollt(a)]
    for rolle in (BUERO, BUERO_AUFTRAG, MONTEUR):
        a = AUFNAHME[ZUSTANDSSEITEN[rolle]]
        if gewollt(a):
            bilder += [Bild(rolle, thema, breite, a, z) for z in ZUSTAENDE if rolle in z.rollen for thema in THEMEN for breite in z.breiten]
    return bilder

# Vor jedem Laden: localStorage leer (Thema kommt aus prefers-color-scheme, eingeklappte Seitenleiste u. ä. nie übernommen),
# Animationen, Übergänge und Textcursor aus.
STILL = """(()=>{try{localStorage.clear()}catch(e){}
const s=document.createElement('style');s.setAttribute('data-bildgrundlage','');
s.textContent='*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'
+'html{scroll-behavior:auto!important}';
const ein=()=>(document.head||document.documentElement).appendChild(s);
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ein);else ein();})()"""

# Fertig: Dokument geladen, Schriften bereit, keine Anfrage der Seite mehr unterwegs und seit 0,8 s keine fertig geworden.
BEREIT = ("document.readyState==='complete'&&document.fonts.status==='loaded'&&!!window.__dkAnfragen"
          "&&window.__dkAnfragen.offen===0&&performance.now()-window.__dkAnfragen.ruhigSeit>=800")

RUHE = "(async()=>{document.activeElement&&document.activeElement.blur&&document.activeElement.blur();window.scrollTo(0,0);" \
       "await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return true})()"
HOEHE = "Math.ceil(Math.max(document.documentElement.scrollHeight,document.body?document.body.scrollHeight:0))"

_ZIEL: dict = {}  # im Hauptprozess gesetzt: ziel, nur


# ---------------------------------------------------------------------------
# Feste Testdaten (im Kindprozess, isolierte Instanz)
# ---------------------------------------------------------------------------

def befuellen(db, k):
    from datetime import datetime, timedelta
    from decimal import Decimal

    from app.berlin_time import _utc_now, berlin_today
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist
    from app.inspection_templates import create_template as pruefvorlage_anlegen, create_template_item
    from app.invoices import create_abschlag_pauschal
    from app.models import (
        AppUser, CalendarEvent, Customer, Employee, Finding, ImportBatch, IncomingInvoice, Inquiry, MaintenanceContract,
        MaintenanceContractItem, MaintenanceWindow, OperationalAsset, PlanningSlot, Project, Property, Quote, QuoteItem, RecurringCost,
        RoofArea, Service, Supplier, Team, TeamEmployee, TimeEntry, WorkPreparationEmployee, WorkPreparationTeamAssignment,
        WorkPreparationTeamEmployee,
    )
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import add_inspection_item, create_report
    from app.tasks import create_task
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"), weekly_hours=Decimal("40"))
    olga = Employee(employee_number="E-2", first_name="Olga", last_name="Office", employee_group="kaufmaennisch", active=True,
                    hourly_wage=Decimal("25.00"), weekly_hours=Decimal("40"))
    bernd = Employee(employee_number="E-3", first_name="Bernd", last_name="Büro", employee_group="kaufmaennisch", active=True,
                     hourly_wage=Decimal("27.50"), weekly_hours=Decimal("38"))
    db.add_all([mia, olga, bernd]); db.flush()
    buero = AppUser(username="bernd", display_name="Bernd Büro", role="buero_finanzen", employee_id=bernd.id, password_hash=k.passwort())
    monteur = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    admin = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    team = Team(name="Team Nord")
    db.add_all([buero, monteur, admin, team]); db.flush()
    db.add(TeamEmployee(team_id=team.id, employee_id=mia.id))

    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False, street="Werkstr. 5", postal_code="52531",
                     city="Übach-Palenberg", email="info@hallenbau.example", phone="02451 12345")
    familie = Customer(name="Lena Sommer", first_name="Lena", last_name="Sommer", is_consumer=True, street="Lindenweg 3",
                       postal_code="52525", city="Heinsberg", email="lena.sommer@example.org")
    db.add_all([kunde, familie]); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(objekt); db.flush()
    nord = RoofArea(property_id=objekt.id, name="Nord")
    sued = RoofArea(property_id=objekt.id, name="Süd")
    db.add_all([nord, sued]); db.flush()

    spalte = default_pipeline_column_id(db)
    projekt = Project(project_number="P-2026-0001", name="Dachsanierung Halle Nord", customer_id=kunde.id, property_id=objekt.id,
                      status="angebot", pipeline_column_id=spalte)
    zweites = Project(project_number="P-2026-0002", name="Flachdach Sommer", customer_id=familie.id, status="anfrage",
                      pipeline_column_id=spalte)
    db.add_all([projekt, zweites]); db.flush()
    angebot = Quote(quote_number="A-2026-0001", project_id=projekt.id, title="Dachsanierung Halle Nord", vat_rate=Decimal("19"))
    angebot2 = Quote(quote_number="A-2026-0002", project_id=zweites.id, title="Flachdach abdichten", vat_rate=Decimal("19"))
    db.add_all([angebot, angebot2]); db.flush()
    db.add_all([
        QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung Bitumen, zweilagig", quantity=Decimal("850"),
                  unit="m²", unit_price=Decimal("48.90")),
        QuoteItem(quote_id=angebot.id, position_number="2", short_text="Attika verwahren", quantity=Decimal("120"), unit="m",
                  unit_price=Decimal("36.50")),
        QuoteItem(quote_id=angebot2.id, position_number="1", short_text="Abdichtung Flüssigkunststoff", quantity=Decimal("64"),
                  unit="m²", unit_price=Decimal("89.00")),
    ])
    db.commit()
    # Projektstatus vorab, eigener Commit: create_order_from_quote() ändert Angebot und Projekt im selben Flush, und app/audit.py
    # schreibt deren Verlaufseinträge in der Reihenfolge von session.dirty (ein set, nach Speicheradresse) -- sie wechselte von Lauf
    # zu Lauf (Archiv, "Reihenfolge im Verlauf"). So ändert jener Flush nur das Angebot.
    projekt.status = "beauftragt"
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=21), execution_start=heute,
                                      execution_end=heute + timedelta(days=4), caseworker_employee_id=bernd.id,
                                      project_manager_employee_id=olga.id, payment_terms=None, remarks=None)
    vorbereitung = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=vorbereitung.id, employee_id=mia.id))
    zuweisung = WorkPreparationTeamAssignment(preparation_id=vorbereitung.id, team_id=team.id, team_name_snapshot="Team Nord")
    db.add(zuweisung); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=zuweisung.id, employee_id=mia.id, employee_name_snapshot="Mia Monteurin"))
    db.add(PlanningSlot(preparation_id=vorbereitung.id, team_assignment_id=zuweisung.id, start_date=heute,
                        end_date=heute + timedelta(days=2)))
    db.commit()
    rechnung = create_abschlag_pauschal(db, auftrag, lump_sum_net=Decimal("12000"), progress_description="1. Abschlag Abdichtung",
                                        due_date=heute + timedelta(days=14))
    bericht = create_report(db, auftrag.id, "wartung", description="Wartung Halle Nord, Dachfläche Nord",
                            created_by_employee_id=mia.id)
    add_inspection_item(db, bericht["id"], "Rinne frei", "free_text", group_name="Entwässerung")
    add_inspection_item(db, bericht["id"], "Abdichtung Sichtprüfung", "ja_nein", group_name="Abdichtung")
    db.add(Finding(service_report_id=bericht["id"], description="Riss an der Attika West", severity="mittel", action="buero_pruefen"))

    vorlage = create_template(db, label="Sicherheitscheck", contexts=["auftrag"])
    add_field(db, vorlage["draft_version_id"], {"field_type": "ja_nein", "label": "Absturzsicherung geprüft", "field_key": "absturz",
                                                "required": True})
    add_field(db, vorlage["draft_version_id"], {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, vorlage["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig",
                                                "signer_label": "Monteur"})
    veroeffentlicht = publish_draft(db, vorlage["id"])
    checkliste = create_checklist(db, template_id=veroeffentlicht["id"], context_type="auftrag", order_id=auftrag.id,
                                  created_by_employee_id=mia.id, created_by_user_id=monteur.id)

    pruefvorlage = pruefvorlage_anlegen(db, "Flachdach-Wartung", roof_type="Flachdach")
    create_template_item(db, pruefvorlage["id"], "Abdichtung Sichtprüfung", "ja_nein")
    create_template_item(db, pruefvorlage["id"], "Rinnen und Abläufe frei", "ja_nein")
    altbestand = pruefvorlage_anlegen(db, "Altbestand Flachdach", roof_type=DACHTYP_ALTWERT)

    fenster = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
    vertrag = MaintenanceContract(customer_id=kunde.id, property_id=objekt.id, title="Wartung Halle Nord", interval_months=12,
                                  next_due_date=heute + timedelta(days=150))
    db.add_all([fenster, vertrag]); db.flush()
    db.add(MaintenanceContractItem(contract_id=vertrag.id, roof_area_id=nord.id, maintenance_window_id=fenster.id,
                                   next_due_date=heute + timedelta(days=150)))
    geraet = OperationalAsset(name="Anlegeleiter 3-teilig", asset_type="Leiter")
    stapel = ImportBatch(source_type="manuell", source_name="Manuell", filename="-")
    db.add_all([geraet, stapel]); db.flush()
    leistung = Service(import_batch_id=stapel.id, source_type="manuell", external_id="M-1", short_text="Rinne reinigen",
                       quantity=Decimal("1"), unit="m", site_time_raw=Decimal("0"), workshop_time_raw=Decimal("0"),
                       sale_price=Decimal("8.50"))
    db.add(leistung)
    for tag, stunden in ((heute - timedelta(days=1), "7.50"), (heute, "3.25")):
        db.add(TimeEntry(employee_id=mia.id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site",
                         counts_as_productive=True, hours=Decimal(stunden), status="booked", source="manual"))
    beginn = datetime.combine(heute, datetime.min.time()).replace(hour=14)
    db.add(CalendarEvent(title="Baubesprechung Halle Nord", start_at=beginn, end_at=beginn + timedelta(hours=1), owner_user_id=buero.id))
    lieferant = Supplier(name="Dachbaustoffe Nord GmbH", city="Aachen")
    db.add(lieferant); db.flush()
    db.add(IncomingInvoice(supplier_id=lieferant.id, supplier_invoice_number="ER-4711", invoice_date=heute - timedelta(days=5),
                           net_amount=Decimal("1234.50"), tax_rate_pct=Decimal("19"), due_date=heute + timedelta(days=9)))
    db.add(RecurringCost(label="Fahrzeugleasing Pritsche", net_amount=Decimal("450.00"), billing_interval="monatlich",
                         annual_amount=Decimal("5400.00")))
    db.add(Inquiry(inquiry_number="AN-2026-0001", customer_id=familie.id, title="Undichtes Flachdach"))
    db.commit()
    create_task(db, title="Rückruf Hallenbau wegen Gerüst", created_by_user_id=buero.id)

    # Seit 1.8.131: Büro – Auftrag für die Seitenleiste dieser Rolle -- ohne ORM eingefügt, damit kein Verlaufseintrag entsteht (AppUser
    # wird protokolliert; die Verlaufsseite der bisherigen Bilder bliebe sonst nicht gleich)
    from sqlalchemy import insert, select

    db.execute(insert(AppUser.__table__).values(username="berta", display_name="Berta Auftrag", role="buero_auftrag",
                                                password_hash=k.passwort(), active=True))
    berta = db.scalar(select(AppUser).where(AppUser.username == "berta"))
    cookies = {BUERO: k.cookies(buero), MONTEUR: k.cookies(monteur), ADMIN: k.cookies(admin), BUERO_AUFTRAG: k.cookies(berta)}
    _zeitstempel_festsetzen(db, _utc_now().replace(tzinfo=None))
    return {"cookies": cookies, "uhr_ms": k.uhr_ms(), "kunde": kunde.id, "objekt": objekt.id, "dachflaeche": nord.id,
            "projekt": projekt.id, "angebot": angebot.id, "auftrag": auftrag.id, "rechnung": rechnung.id, "checkliste": checkliste["id"],
            "checklistenvorlage": vorlage["id"], "vertrag": vertrag.id, "pruefvorlage": pruefvorlage["id"],
            "pruefvorlage_altwert": altbestand["id"], "geraet": geraet.id,
            "leistung": leistung.id, "mitarbeiter": mia.id}


# Zeitstempel, die befuellen() bewusst aus der stehenden Uhr setzt -- sie bleiben, wie sie sind
BEWUSST_GESETZT = {("calendar_events", "start_at"), ("calendar_events", "end_at")}


def _zeitstempel_festsetzen(db, zeitpunkt) -> None:
    """Jeden gespeicherten Zeitstempel (Spalte DateTime, nicht leer) auf den Zeitpunkt der Uhr setzen -- datetime.utcnow() beim
    Befüllen nähme sonst die echte Zeit, die Seiten zeigten sie. Ausgenommen der Ablauf der Sitzungen (expires_at, gegen die echte
    Zeit geprüft) und BEWUSST_GESETZT. Der Verlauf ordnet gleich alte Einträge nach ID (app/audit.py); welche ID ein Eintrag bekommt,
    entscheidet beim Schreiben die Reihenfolge von session.dirty -- siehe "Grenzen" im Archiv."""
    from sqlalchemy import DateTime, update

    from app.database import Base

    for tabelle in Base.metadata.sorted_tables:
        for spalte in tabelle.columns:
            if (isinstance(spalte.type, DateTime) and spalte.name != "expires_at"
                    and (tabelle.name, spalte.name) not in BEWUSST_GESETZT):
                db.execute(update(tabelle).where(spalte.isnot(None)).values({spalte.name: zeitpunkt}))


# ---------------------------------------------------------------------------
# Aufnehmen (im Hauptprozess)
# ---------------------------------------------------------------------------

def _commit() -> tuple[str, bool]:
    git = ["git", "-C", str(ROOT)]
    kurz = subprocess.run([*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "ohne-git"
    geaendert = bool(subprocess.run([*git, "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return kurz, geaendert


async def _bild(tab, pfad: str, breite: int, thema: str, datei: Path, zustand: Zustand | None = None) -> dict:
    """Ein Bild: ohne Zustand die ganze Seite, mit Zustand (seit 1.8.131) das Fenster nach zustand.aktion."""
    mobil = breite in GERAETE
    schema = "dark" if thema == "dunkel" else "light"
    hoehe = STARTHOEHEN.get(breite, STARTHOEHE)
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": schema}])
    await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe, deviceScaleFactor=1, mobile=mobil)
    marke = len(tab.netz.verlauf)
    bereit = await tab.oeffnen(pfad, BEREIT, timeout=45)
    dokument = next((e for e in tab.netz.verlauf[marke:] if e.get("art") == "Document"), {})
    await tab.js(RUHE)
    if zustand is not None:
        eingetreten = await tab.js(zustand.aktion)
        await tab.warten(BEREIT, 15, melden=False)
        await tab.js(RUHE)
        daten = (await tab.cmd("Page.captureScreenshot", format="png", fromSurface=True))["data"]
        datei.write_bytes(base64.b64decode(daten))
        return {"bereit": bereit, "hoehe": hoehe, "status": dokument.get("status"), "eingetreten": eingetreten}
    start = hoehe
    for _ in range(4):  # bis die Höhe sich nicht mehr ändert (ein höheres Fenster kann die Seite umbrechen lassen)
        gemessen = min(max(int(await tab.js(HOEHE) or start), start), HOECHSTE_HOEHE)
        if gemessen == hoehe:
            break
        hoehe = gemessen
        await tab.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe, deviceScaleFactor=1, mobile=mobil)
        await tab.warten(BEREIT, 15, melden=False)
        await tab.js(RUHE)
    daten = (await tab.cmd("Page.captureScreenshot", format="png", fromSurface=True))["data"]
    datei.write_bytes(base64.b64decode(daten))
    return {"bereit": bereit, "hoehe": hoehe, "status": dokument.get("status")}


async def pruefen(tab, seed, p):
    kurz, geaendert = _commit()
    ziel = (_ZIEL.get("ziel") or ROOT / "bildgrundlage" / f"{kurz}{'-geaendert' if geaendert else ''}").resolve()
    if ziel.exists() and any(ziel.iterdir()):
        raise SystemExit(f"Zielordner ist nicht leer: {ziel}")
    ziel.mkdir(parents=True, exist_ok=True)
    nur = _ZIEL.get("nur") or []
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=STILL)
    await tab.browser_uhr_fest(seed["uhr_ms"])
    chrome = (await tab.cmd("Browser.getVersion")).get("product", "?")
    bilder, beginn, angemeldet = [], time.monotonic(), None
    for b in geplante_bilder(nur):
        if b.rolle != angemeldet:
            await tab.anmelden({} if b.rolle == ANONYM else seed["cookies"][b.rolle])
            angemeldet = b.rolle
        if tab.wachhund:
            tab.wachhund.neu_starten()
        a, datei = b.aufnahme, ziel / b.datei
        pfad = a.pfad.format(**seed)
        stand = await _bild(tab, pfad, b.breite, b.thema, datei, b.zustand)
        # geladen, und die Rolle darf die Seite öffnen -- sonst wäre das Bild die Sperrseite (Status 403)
        p.pruefe(f"{datei.name}: geladen, Status", (stand["bereit"], stand["status"]),
                 (True, 403 if a.vorlage == "access_denied.html" else 200))
        if b.zustand is not None:
            p.pruefe(f"{datei.name}: Zustand eingetreten", stand["eingetreten"], True)
        if b.zustand is not None and b.zustand.name in ("kontomenue_offen", "leiste"):
            # seit 1.8.162 passt die Leiste bei 1440 × 900 in jeder Rolle ohne Bildlauf ins Fenster (bis dahin nur die der Monteurin;
            # fürs Büro gab es den Zustand "leiste_unten")
            p.pruefe(f"{datei.name}: Leiste ohne Bildlauf", await tab.js(LEISTE_OHNE_BILDLAUF), True)
        bilder.append({"datei": datei.name, "seite": a.name, "vorlage": a.vorlage, "pfad": pfad, "rolle": b.rolle, "thema": b.thema,
                       "breite": b.breite, "zustand": b.zustand.name if b.zustand else None, "hoehe": stand["hoehe"],
                       "status": stand["status"], "js_fehler": list(tab.fehler)})
    dauer = time.monotonic() - beginn
    (ziel / "bilder.json").write_text(json.dumps({"commit": kurz, "geaendert": geaendert, "uhr": UHR, "chrome": chrome,
                                                  "anzahl": len(bilder), "sekunden": round(dauer, 1), "bilder": bilder},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    mit_fehlern = [b["datei"] for b in bilder if b["js_fehler"]]
    print(f"{len(bilder)} Bilder in {dauer:.0f} s nach {ziel}" + (f"; mit JS-Fehlern: {mit_fehlern}" if mit_fehlern else ""), flush=True)


# ---------------------------------------------------------------------------
# Vergleichen
# ---------------------------------------------------------------------------

def bilder_vergleichen(alt: Path, neu: Path) -> tuple[int, int, int, object]:
    """(abweichende Pixel, Breite, Höhe, Differenzbild) -- unterschiedliche Größen: beide auf die größere Fläche gelegt, was nur
    in einem Bild liegt, weicht ab. Ein Pixel weicht ab, wenn einer der Kanäle R, G, B, A anders ist."""
    from PIL import Image, ImageChops

    a, b = Image.open(alt).convert("RGBA"), Image.open(neu).convert("RGBA")
    breite, hoehe = max(a.width, b.width), max(a.height, b.height)
    if a.size != (breite, hoehe) or b.size != (breite, hoehe):
        leer = (255, 0, 255, 0)
        a2, b2 = Image.new("RGBA", (breite, hoehe), leer), Image.new("RGBA", (breite, hoehe), leer)
        a2.paste(a, (0, 0)); b2.paste(b, (0, 0))
        maske_aussen = Image.new("L", (breite, hoehe), 255)
        maske_aussen.paste(0, (0, 0, min(a.width, b.width), min(a.height, b.height)))
        a, b = a2, b2
    else:
        maske_aussen = None
    differenz = ImageChops.difference(a, b)
    maske = differenz.getchannel(0)
    for kanal in (1, 2, 3):
        maske = ImageChops.lighter(maske, differenz.getchannel(kanal))
    maske = maske.point(lambda v: 255 if v else 0)
    if maske_aussen is not None:
        maske = ImageChops.lighter(maske, maske_aussen)
    anzahl = maske.histogram()[255]
    bild = b.convert("L").point(lambda v: 170 + v // 3).convert("RGB")
    bild.paste((220, 0, 0), mask=maske)
    return anzahl, breite, hoehe, bild


def chrome_version(ordner: Path) -> str | None:
    """Die Chrome-Version aus bilder.json des Ordners, None ohne Datei oder Angabe."""
    try:
        return json.loads((ordner / "bilder.json").read_text(encoding="utf-8")).get("chrome")
    except (OSError, ValueError):
        return None


ABBRUCH = 2  # seit 1.8.127: verschiedene Chrome-Versionen -- kein Vergleich


def vergleichen(alt: Path, neu: Path, differenzen: Path | None = None) -> int:
    namen_alt = {p.name for p in alt.glob("*.png")}
    namen_neu = {p.name for p in neu.glob("*.png")}
    if not namen_alt or not namen_neu:
        print(f"Keine Bilder in {alt if not namen_alt else neu}")
        return 1
    # Seit 1.8.127: ein anderer Chrome zeichnet Text und Kanten anders -- jedes Bild wiche ab, ohne dass sich eine Seite geändert hat
    chrome_alt, chrome_neu = chrome_version(alt), chrome_version(neu)
    if chrome_alt and chrome_neu and chrome_alt != chrome_neu:
        print(f"ABBRUCH: verschiedene Chrome-Versionen ({alt.name}: {chrome_alt}, {neu.name}: {chrome_neu}) -- zuerst die Grundlage mit "
              "dem Chrome von heute neu erzeugen (auf ihrem Commit, z. B. in einem Git-Worktree), dann vergleichen.")
        return ABBRUCH
    if not (chrome_alt and chrome_neu):
        print(f"Hinweis: Chrome-Version unbekannt ({alt.name if not chrome_alt else neu.name} ohne bilder.json) -- nicht geprüft.")
    if differenzen is None:
        namen = (alt.name, neu.name) if alt.name != neu.name else (alt.resolve().parent.name, neu.resolve().parent.name)
        differenzen = neu.parent / f"vergleich_{namen[0]}_{namen[1]}"
    fehlen, dazu = sorted(namen_alt - namen_neu), sorted(namen_neu - namen_alt)
    abweichend = []
    for name in sorted(namen_alt & namen_neu):
        anzahl, breite, hoehe, bild = bilder_vergleichen(alt / name, neu / name)
        if anzahl:
            differenzen.mkdir(parents=True, exist_ok=True)
            bild.save(differenzen / name)
            abweichend.append((name, anzahl, breite * hoehe))
    for name, anzahl, flaeche in abweichend:
        print(f"ABWEICHUNG  {name}: {anzahl} Pixel ({anzahl / flaeche:.4%})")
    for name in fehlen:
        print(f"FEHLT       {name}")
    for name in dazu:
        print(f"NEU         {name}")
    gleich = len(namen_alt & namen_neu) - len(abweichend)
    print(f"{gleich} gleich, {len(abweichend)} abweichend, {len(fehlen)} fehlen, {len(dazu)} neu"
          + (f" -- Differenzbilder: {differenzen}" if abweichend else ""))
    return 1 if abweichend or fehlen or dazu else 0


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------

def main() -> int:
    argumente = sys.argv[1:]
    if argumente and argumente[0] == "vergleichen":
        parser = argparse.ArgumentParser(prog="bildgrundlage.py vergleichen")
        parser.add_argument("alt", type=Path)
        parser.add_argument("neu", type=Path)
        parser.add_argument("--differenzen", type=Path)
        ns = parser.parse_args(argumente[1:])
        return vergleichen(ns.alt, ns.neu, ns.differenzen)
    if argumente and argumente[0] == "aufnehmen":
        argumente = argumente[1:]
    eigene = argparse.ArgumentParser(add_help=False)
    eigene.add_argument("--ziel", type=Path)
    eigene.add_argument("--nur", action="append")
    ns, rest = eigene.parse_known_args(argumente)
    _ZIEL.update({"ziel": ns.ziel, "nur": ns.nur})
    sys.argv = [sys.argv[0], *rest]
    return klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=UHR, zeitlimit_je_schritt=True,
                          umgebung={ANZEIGE_ENV: json.dumps({"version": "Bildgrundlage", "changelog": str(CHANGELOG)})},
                          chrome_argumente=CHROME_ARGUMENTE)


if __name__ == "__main__":
    sys.exit(main())
