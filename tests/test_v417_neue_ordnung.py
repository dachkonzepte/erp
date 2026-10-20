"""Version 1.8.112 -- neue Ordnung von Seitenleiste und Einstellungen, Stufe 1 "Ordnen" (docs/archiv/stammdaten-und-sidebar.md,
"Neue Ordnung, Stufe 1").

Nur verschoben, umbenannt und ausgeblendet; alle Adressen bleiben. Geprüft am vom Server gerenderten Markup je Rolle:
die Seitenleiste in Gruppen mit Überschrift, das Menü der Einstellungen in zehn Gruppen, und die Regel hinter dem Ausblenden --
ein Bereich fehlt für die Büro-Rollen genau dann, wenn nur ein Administrator dort speichern darf (Ausnahme die Rechtstexte: das
Büro liest sie). Der Klicktest scripts/klicktest_neue_ordnung.py prüft dasselbe im Browser samt Speichern und früheren Adressen."""

import re
from pathlib import Path

import pytest

from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.routers.pages import router as pages_router
from app.routers.pages import templates
from tests.test_v260_role_audit import _discover_api_routes, _iter_role_marked_dependants

ROOT = Path(__file__).parents[1]
BUERO = (ROLE_ADMIN, ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG)

# Seit 1.8.162 vier Gruppen (Stufe 2 „Rahmen“): Personal in Kaufmännisch, Stammdaten und System in Verwaltung
SEITENLEISTE = [
    ("Übersicht", ["Start", "Aufgaben", "Kalender"]),
    ("Aufträge", ["Anfragen", "Projekte", "Plantafel", "Checklisten", "Wartungen", "Befunde"]),
    ("Kaufmännisch", ["Finanzen", "Mahnwesen", "Eingangsrechnungen", "Betriebskosten", "Zeiterfassung", "Backoffice"]),
    ("Verwaltung", ["Stammdaten", "Einstellungen"]),
]

# Bereiche, die nur ein Administrator speichern darf, mit den Anfängen ihrer Schreibwege.
NUR_ADMIN = {
    "email-settings": ("/api/email-settings",), "outlook-sync": ("/api/outlook-sync-settings",),
    "ai-settings": ("/api/ai-settings",), "modules": ("/api/modules/",),
    "project-pipeline": ("/api/project-pipeline-columns",), "tasks": ("/api/task-settings", "/api/task-columns"),
    "maintenance": ("/api/maintenance-settings", "/api/maintenance-windows"), "mobile": ("/api/mobile-settings",),
}
# Die Rechtstexte bleiben für das Büro lesbar, obwohl nur ein Administrator sie speichert.
RECHTSTEXTE = {
    "contract-bases": ("/api/settings/contract-basis-clauses",), "contract-templates": ("/api/settings/contract-templates",),
    "notice-reservations": ("/api/settings/notice-reservations",), "dunning-legal-texts": ("/api/dunning-legal-texts",),
}


@pytest.fixture
def seite(threaded_db_session, router_test_client, monkeypatch):
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)

    def _seite(pfad: str, rolle: str) -> str:
        antwort = router_test_client(threaded_db_session, pages_router, role=rolle).get(pfad, follow_redirects=False)
        assert antwort.status_code == 200, (pfad, rolle, antwort.status_code)
        return antwort.text
    return _seite


def _seitenleiste(html: str) -> list[tuple[str, list[str]]]:
    nav = html[html.index('<nav class="app-sidebar-nav">'):]
    nav = nav[:nav.index("</nav>")]
    gruppen = []
    for m in re.finditer(r'class="app-sidebar-group">([^<]*)<|class="app-sidebar-label">([^<]*)<', nav):
        if m.group(1) is not None:
            gruppen.append((m.group(1).strip(), []))
        else:
            gruppen[-1][1].append(m.group(2).strip())
    return gruppen


def _menue(html: str) -> list[tuple[str, list[str]]]:
    seitenleiste = html[html.index('<aside class="settings-sidebar"'):]
    seitenleiste = seitenleiste[:seitenleiste.index("</aside>")]
    gruppen = []
    for m in re.finditer(r'class="settings-group">([^<]*)<|<button[^>]*>([^<]+)<span class="menu-sub">', seitenleiste):
        if m.group(1) is not None:
            gruppen.append((m.group(1).strip(), []))
        else:
            gruppen[-1][1].append(m.group(2).strip())
    return gruppen


def _rollen(pfad_anfang: str) -> list[set[str]]:
    """Rollen je Schreibweg (PUT/POST/DELETE/PATCH), dessen Pfad so beginnt."""
    return [set().union(*_iter_role_marked_dependants(route.dependant))
            for methode, pfad, route in _discover_api_routes() if methode != "GET" and pfad.startswith(pfad_anfang)]


@pytest.mark.parametrize("rolle", (*BUERO, ROLE_FIELD))
def test_seitenleiste_in_gruppen_je_rolle(seite, rolle):
    if rolle == ROLE_FIELD:
        erwartet = [("Übersicht", ["Start"]), ("Kaufmännisch", ["Zeiterfassung"])]
    elif rolle == ROLE_OFFICE_AUFTRAG:
        erwartet = [(g, [x for x in e if x not in ("Eingangsrechnungen", "Betriebskosten")]) for g, e in SEITENLEISTE]
    else:
        erwartet = SEITENLEISTE
    html = seite("/account", rolle)
    assert _seitenleiste(html) == erwartet
    assert 'href="/versandprotokoll"' not in html[html.index('<nav class="app-sidebar-nav">'):html.index("</nav>")]


@pytest.mark.parametrize("rolle", BUERO)
def test_menue_der_einstellungen_je_rolle(seite, rolle):
    admin, finanzen = rolle == ROLE_ADMIN, rolle in (ROLE_ADMIN, ROLE_OFFICE_FINANZEN)
    erwartet = [
        ("Firma", ["Unternehmensdaten", "Erscheinungsbild"]),
        ("Finanzen", ["Nummernkreise", "Steuer", "Zahlungsbedingungen", "Mahnwesen"]),
        *([("Kalkulation", ["Stundenverrechnungssatz", "Kalkulationsgrundlagen", "Kontenstamm"])] if finanzen else []),
        ("Vorlagen und Texte", ["Dokumentlayout", "E-Mail-Vorlagen", "Textbausteine", "Checklisten-Vorlagen", "Prüfvorlagen"]),
        ("Rechtstexte", ["Vertragsgrundlagen", "Vertragsvorlagen", "Vorbehalte", "Mahn-Rechtstexte"]),
        ("Listen", ["Auswahllisten", "Dachaufbau", "Bauteilarten", "Dokumentkategorien", "Zeitarten", "Tätigkeiten",
                    "Abwesenheitsarten"]),
        ("Betrieb", ["Arbeitszeit und Kalender", "Fristen und Erinnerungen"]
         + (["Wartungen", "Projekt-Pipeline", "Aufgaben", "Vor Ort"] if admin else [])),
        ("Personal", ["Funktionen", "Zeitregeln und DATEV"]),
        *([("Anbindungen", ["E-Mail und Microsoft 365", "Outlook-Kalender", "KI", "Adressimport"])] if admin else []),
        ("System", (["Module", "Benutzer und Zugriff"] if admin else []) + ["Versandprotokoll", "Änderungshistorie", "Changelog"]),
    ]
    html = seite("/settings", rolle)
    assert _menue(html) == erwartet
    assert ('href="/users"' in html) is admin  # "Benutzer und Zugriff" nur für Admin


def test_ausgeblendet_genau_wo_nur_ein_administrator_speichert(seite):
    """Ein Bereich fehlt für die Büro-Rollen im Markup, wenn jeder seiner Schreibwege nur Administratoren offensteht --
    und umgekehrt bleibt jeder andere Bereich drin. Ausnahme die Rechtstexte: nur Admin speichert, das Büro liest."""
    seiten = {rolle: seite("/settings", rolle) for rolle in BUERO}
    for bereich, anfaenge in {**NUR_ADMIN, **RECHTSTEXTE}.items():
        rollen = [r for anfang in anfaenge for r in _rollen(anfang)]
        assert rollen and all(r == {ROLE_ADMIN} for r in rollen), (bereich, rollen)
        assert f'id="settings-{bereich}"' in seiten[ROLE_ADMIN], bereich
        for rolle in (ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG):
            assert (f'id="settings-{bereich}"' in seiten[rolle]) is (bereich in RECHTSTEXTE), (bereich, rolle)
    # Jeder übrige Bereich, den das Büro sieht, steht auch im Markup des Admins -- und nichts sonst fehlt dem Büro.
    bereiche = {rolle: set(re.findall(r'id="settings-([a-z-]+)"', html)) for rolle, html in seiten.items()}
    kalkulation = {"labor-rate", "calculation", "accounts"}
    assert bereiche[ROLE_ADMIN] - bereiche[ROLE_OFFICE_FINANZEN] == set(NUR_ADMIN)
    assert bereiche[ROLE_ADMIN] - bereiche[ROLE_OFFICE_AUFTRAG] == set(NUR_ADMIN) | kalkulation


def test_jeder_menuepunkt_hat_seinen_bereich_und_fruehere_adressen_gelten():
    html = (ROOT / "app/templates/settings.html").read_text(encoding="utf-8")
    abschnitte = set(re.findall(r'id="settings-([a-z-]+)"', html))
    erlaubt = set(re.findall(r"'([a-z-]+)'", re.search(r"const SETTINGS_SECTIONS=\[(.*?)\];", html).group(1)))
    gemeinsam = dict(re.findall(r"'([a-z-]+)':'([a-z-]+)'", re.search(r"const GEMEINSAMER_BEREICH=\{(.*?)\};", html).group(1)))
    frueher = dict(re.findall(r"'([a-z-]+)':'([a-z-]+)'", re.search(r"const FRUEHERE_ADRESSEN=\{(.*?)\};", html).group(1)))
    for key in set(re.findall(r'data-settings-section="([a-z-]+)"', html)):
        assert key in erlaubt and gemeinsam.get(key, key) in abschnitte, key
    # Bis 1.8.111 eigene Bereiche, seit 1.8.112 in "Fristen und Erinnerungen" -- die Adresse gilt weiter.
    assert frueher == {"recurring-costs": "deadlines", "incoming-invoices": "deadlines", "operational-assets": "deadlines"}
    assert set(frueher) <= erlaubt and not set(frueher) & abschnitte
    assert gemeinsam == {"text-blocks": "option-lists", "time-entry-types": "time-lists",
                         "time-entry-activities": "time-lists", "absence-types": "time-lists"}


def test_backoffice_behaelt_pruefen_abschluss_und_export():
    html = (ROOT / "app/templates/time_backoffice.html").read_text(encoding="utf-8")
    reiter = re.findall(r'data-tab="([a-z]+)"', html)
    assert reiter == ["dashboard", "entries", "absences", "timesheets", "datev"]
    assert 'id="lockDate"' in html and "downloadDatev()" in html and "downloadTimesheet('pdf')" in html
    for weg in ("saveCoreSettings", "saveModel", "saveOption", "savePayroll", "id=\"payrollRows\""):
        assert weg not in html, weg
    # Frühere Reiter führen in die Einstellungen.
    assert "if(h==='workmodels'||h==='settings'){location.replace('/settings#time-rules');return}" in html
    assert "if(h==='options'){location.replace('/settings#time-entry-types');return}" in html
