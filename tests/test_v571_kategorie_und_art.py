"""Version 1.9.153 (Stufe 6, R1 Nachrunde, Punkt 4, Befund D2): Kategorie und Art einer Abwesenheit.

    Befund     „Monat & Lohn“ und der Lohnexport lesen keine Abwesenheit; gezählt wird nur die Kategorie, und nur bei den Krankheitstagen
    Server     Widerspruch 422 auf beiden Wegen, nichts angelegt; ohne Art der Name der Kategorie (bis 1.9.152 „Urlaub“); „Sonstiges“ und eigene Arten passen zu jeder
    Bestand    was schon dasteht, bleibt: auch ein älterer offener Antrag mit Widerspruch lässt sich entscheiden
    Seite      Art leer vorbelegt, nur passende Arten, passende bleibt beim Wechsel -- auf allen drei Seiten aus derselben Liste vom Server
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.absence_requests import ABSENCE_CATEGORIES, art_kategorien, arten_fuer_auswahl, ist_widerspruch, review_request
from app.models import Employee, EmployeeAbsence, EmployeeAbsenceRequest, EmployeePayrollSettings, SettingOption, SettingOptionGroup, TimeEntry, TimeTrackingSettings
from app.productive_hours import sick_days_actual
from app.routers.absence_requests import router as antraege_router
from app.routers.planning import router as planning_router
from app.routers.time_backoffice import router as backoffice_router
from app.routers.zeiten import router as zeiten_router
from app.time_backoffice import build_datev_export
from app.zeiten import monat
from tests.node_lauf import node_lauf
from tests.test_v133_invoices import make_order_with_item
from tests.vorlagen_js import TEMPLATES, bindet_ein

ROOT = Path(__file__).resolve().parent.parent
TAG = date(2026, 11, 2)


def _person(db, nummer="M-1", name="Mia"):
    emp = Employee(employee_number=nummer, first_name=name, last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return emp


def _body(emp, kategorie, **mehr):
    return {"employee_id": emp.id, "absence_category": kategorie, "start_date": TAG.isoformat(), "end_date": TAG.isoformat(), **mehr}


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    return db, router_test_client(db, antraege_router, planning_router, zeiten_router, backoffice_router)


WEGE = ["/api/absence-requests", "/api/planning/absences"]


# --- Befund: wer zählt was -------------------------------------------------------------------------------------------------------

def test_befund_lohnexport_und_monat_zaehlen_keine_abwesenheit(threaded_db_session):
    """Dieselbe Datei und dieselben Zeilen mit und ohne Abwesenheit: Urlaub und Krankheit stehen in keiner Lohndatei. Festgehalten, nicht gebaut -- ändert das jemand, fällt es hier auf."""
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    mia = _person(db)
    db.add(EmployeePayrollSettings(employee_id=mia.id, datev_personnel_number="1001", payroll_export_enabled=True))
    db.add(TimeEntry(employee_id=mia.id, project_id=order.project_id, order_id=order.id, work_date=date(2026, 9, 1), entry_type="site", counts_as_productive=True,
                     hours=Decimal("8"), status="booked", source="manual"))
    s = db.get(TimeTrackingSettings, 1)
    s.datev_wage_type_site, s.datev_beraternummer, s.datev_mandantennummer, s.locked_until = "100", "1234567", "12345", date(2026, 9, 30)
    db.commit()
    datei_vorher = build_datev_export(db, date(2026, 9, 1), date(2026, 9, 30))
    zeilen_vorher = monat(db, date(2026, 9, 1))["zeilen"]

    for kategorie, art in (("krankheit", "Krankheit"), ("urlaub", "Urlaub"), ("unbezahlt", "Unbezahlt")):
        db.add(EmployeeAbsence(employee_id=mia.id, absence_category=kategorie, absence_type=art, start_date=date(2026, 9, 2), end_date=date(2026, 9, 3)))
    db.commit()
    assert build_datev_export(db, date(2026, 9, 1), date(2026, 9, 30)) == datei_vorher
    assert monat(db, date(2026, 9, 1))["zeilen"] == zeilen_vorher


def test_befund_gezaehlt_wird_nur_die_kategorie(threaded_db_session):
    """Die Krankheitstage zählen die Kategorie: „Krankheit“ + Art „Urlaub“ zählt, „Urlaub“ + Art „Krankheit“ nicht -- ein Widerspruch zählt also, was die Tafel anders nennt."""
    db = threaded_db_session
    leute = [_person(db, f"M-{i}", f"P{i}") for i in range(5)]
    heute = date(2026, 10, 14)
    tag = heute - timedelta(days=30)
    db.add(EmployeeAbsence(employee_id=leute[0].id, absence_category="krankheit", absence_type="Urlaub", start_date=tag, end_date=tag))
    db.add(EmployeeAbsence(employee_id=leute[1].id, absence_category="urlaub", absence_type="Krankheit", start_date=tag, end_date=tag))
    db.commit()
    ergebnis = sick_days_actual(db, today=heute)
    assert ergebnis["suppressed"] is False and ergebnis["total_days"] == 1


# --- Zuordnung ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("art, kategorien", [
    ("Urlaub", ("urlaub",)), ("Freizeitausgleich", ("urlaub",)), ("Krankheit", ("krankheit",)), ("Weiterbildung", ("fortbildung",)), ("Berufsschule", ("fortbildung",)),
    ("Fortbildung", ("fortbildung",)), ("Unbezahlt", ("unbezahlt",)), ("Sonstiges", ABSENCE_CATEGORIES), ("Kur", ABSENCE_CATEGORIES), ("  krankheit ", ("krankheit",)), ("URLAUB", ("urlaub",)),
])
def test_zuordnung(art, kategorien):
    assert art_kategorien(art) == kategorien


def test_jede_art_der_grundeinstellung_ist_eingeordnet(threaded_db_session):
    """Außer „Sonstiges“ hat jede Art der Grundeinstellung eine feste Kategorie -- eine neue in app/option_settings.py fiele sonst still unter „passt zu jeder“."""
    arten = {a["value"]: a["kategorien"] for a in arten_fuer_auswahl(threaded_db_session)}
    assert set(arten) == {"Urlaub", "Krankheit", "Weiterbildung", "Berufsschule", "Freizeitausgleich", "Sonstiges"}
    assert [a for a, k in arten.items() if len(k) > 1] == ["Sonstiges"]


def test_altbestand_ohne_kategorie_widerspricht_nicht():
    assert ist_widerspruch("unbekannt", "Urlaub") is False


# --- Server ------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("kategorie, art", [("krankheit", "Urlaub"), ("urlaub", "Krankheit"), ("fortbildung", "Urlaub"), ("unbezahlt", "Krankheit"), ("krankheit", "URLAUB ")])
def test_widerspruch_422_nichts_angelegt(welt, weg, kategorie, art):
    db, client = welt
    antwort = client.post(weg, json=_body(_person(db), kategorie, absence_type=art))
    assert antwort.status_code == 422, antwort.text
    assert "passt nicht zur Kategorie" in antwort.json()["detail"]
    assert db.scalar(select(func.count()).select_from(EmployeeAbsenceRequest)) == 0
    assert db.scalar(select(func.count()).select_from(EmployeeAbsence)) == 0


@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("kategorie, art", [("krankheit", "Krankheit"), ("urlaub", "Urlaub"), ("urlaub", "Freizeitausgleich"), ("fortbildung", "Berufsschule"), ("krankheit", "Sonstiges"),
                                            ("unbezahlt", "Sonstiges"), ("krankheit", "Kur")])
def test_passend_200(welt, weg, kategorie, art):
    db, client = welt
    antwort = client.post(weg, json=_body(_person(db), kategorie, absence_type=art))
    assert antwort.status_code == 200, antwort.text
    assert db.scalar(select(EmployeeAbsenceRequest.absence_type)) == art


@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("kategorie, name", [("krankheit", "Krankheit"), ("urlaub", "Urlaub"), ("fortbildung", "Fortbildung"), ("unbezahlt", "Unbezahlt")])
@pytest.mark.parametrize("mehr", [{}, {"absence_type": None}, {"absence_type": ""}, {"absence_type": "   "}])
def test_ohne_art_der_name_der_kategorie(welt, weg, kategorie, name, mehr):
    """Bis 1.9.152 stand hier fest „Urlaub“ -- daher „Krankheit (Urlaub)“."""
    db, client = welt
    antwort = client.post(weg, json=_body(_person(db), kategorie, **mehr))
    assert antwort.status_code == 200, antwort.text
    assert db.scalar(select(EmployeeAbsenceRequest.absence_type)) == name


def test_unbekannte_kategorie_bleibt_abgelehnt(welt):
    db, client = welt
    assert client.post("/api/absence-requests", json=_body(_person(db), "unbekannt", absence_type="Urlaub")).status_code == 422


# --- Bestand -----------------------------------------------------------------------------------------------------------------------

def test_aelterer_offener_antrag_mit_widerspruch_laesst_sich_entscheiden(threaded_db_session):
    """Bestehendes wird nicht geändert und nicht gesperrt: die Abwesenheit trägt die Werte des Antrags (scripts/pruefe_abwesenheiten.py nennt sie)."""
    db = threaded_db_session
    alt = EmployeeAbsenceRequest(employee_id=_person(db).id, absence_category="krankheit", absence_type="Urlaub", start_date=TAG, end_date=TAG, status="pending")
    db.add(alt)
    db.commit()
    review_request(db, alt.id, decision="approved", reviewed_by_user_id=None)
    abwesenheit = db.scalar(select(EmployeeAbsence))
    assert (abwesenheit.absence_category, abwesenheit.absence_type) == ("krankheit", "Urlaub")


# --- Liste vom Server --------------------------------------------------------------------------------------------------------------

def test_liste_mit_kategorien_nur_aktive_und_eigene_art(welt):
    db, client = welt
    gruppe = db.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == "absence_types"))
    db.add(SettingOption(group_id=gruppe.id, label="Kur", value="Kur", sort_order=70, active=True))
    db.add(SettingOption(group_id=gruppe.id, label="Alt", value="Alt", sort_order=80, active=False))
    db.commit()
    antwort = client.get("/api/absence-requests/arten")
    assert antwort.status_code == 200
    je_art = {a["value"]: a["kategorien"] for a in antwort.json()}
    assert je_art["Krankheit"] == ["krankheit"]
    assert je_art["Kur"] == list(ABSENCE_CATEGORIES)
    assert "Alt" not in je_art


@pytest.mark.parametrize("rolle", ["field", "buero_auftrag", "buero_finanzen", "admin"])
def test_liste_fuer_jede_rolle(threaded_db_session, router_test_client, rolle):
    """Wer einen Antrag stellen darf, bekommt die Liste; sie enthält nichts über Personen."""
    client = router_test_client(threaded_db_session, antraege_router, role=rolle)
    antwort = client.get("/api/absence-requests/arten")
    assert antwort.status_code == 200 and antwort.json()[0].keys() == {"value", "label", "active", "kategorien"}


# --- Seite -------------------------------------------------------------------------------------------------------------------------

def _baustein():
    teile = [(TEMPLATES / name).read_text(encoding="utf-8") for name in ("_auswahl.html", "_abwesenheit.html")]
    return "\n".join(t.split("<script>", 1)[1].rsplit("</script>", 1)[0] for t in teile)


ARTEN = [{"value": "Urlaub", "label": "Urlaub", "kategorien": ["urlaub"]}, {"value": "Krankheit", "label": "Krankheit", "kategorien": ["krankheit"]},
         {"value": "Sonstiges", "label": "Sonstiges", "kategorien": ["urlaub", "krankheit", "fortbildung", "unbezahlt"]}]


def _fuellen(*schritte):
    """Führt abwArtenFuellen() aus und liefert je Schritt (Optionen, gewählter Wert) -- gewählt ist, was die Vorlage als selected baut."""
    skript = _baustein() + "\nconst feld={value:'',set innerHTML(h){this.html=h;const m=/<option value=\"([^\"]*)\" selected/.exec(h);this.value=m?m[1]:''}};const arten=" + json.dumps(ARTEN) + ";const aus=[];"
    for wert, kategorie, behalten in schritte:
        if wert is not None:
            skript += f"feld.value={json.dumps(wert)};"
        skript += f"abwArtenFuellen(feld,arten,{json.dumps(kategorie)},{json.dumps(behalten)});aus.push([[...feld.html.matchAll(/value=\"([^\"]*)\"/g)].map(m=>m[1]),feld.value]);"
    return json.loads(node_lauf(skript + "console.log(JSON.stringify(aus));").stdout.strip())


def test_art_leer_vorbelegt_und_nur_passende():
    assert _fuellen((None, "krankheit", False)) == [[["", "Krankheit", "Sonstiges"], ""]]
    assert _fuellen((None, "urlaub", False)) == [[["", "Urlaub", "Sonstiges"], ""]]


def test_neu_oeffnen_vergisst_die_wahl_und_wechsel_behaelt_was_passt():
    assert _fuellen(("Sonstiges", "urlaub", False))[0][1] == ""
    assert _fuellen(("Sonstiges", "krankheit", True))[0][1] == "Sonstiges"
    assert _fuellen(("Urlaub", "krankheit", True))[0][1] == ""


@pytest.mark.parametrize("kategorie, art, text", [("Krankheit", "Krankheit", "Krankheit"), ("Fortbildung", "Berufsschule", "Fortbildung (Berufsschule)"), ("Urlaub", None, "Urlaub"), ("Urlaub", "", "Urlaub")])
def test_art_text(kategorie, art, text):
    skript = _baustein() + f"\nconsole.log(abwArtText({json.dumps(kategorie)},{json.dumps(art)}));"
    assert node_lauf(skript).stdout.strip() == text


@pytest.mark.parametrize("seite", ["planning.html", "zeiten.html", "mobil_zeiten.html"])
def test_alle_drei_seiten_nehmen_den_baustein(seite):
    assert bindet_ein(seite, "_abwesenheit.html")
    assert bindet_ein(seite, "_auswahl.html")
    assert "abwArtenFuellen(" in (TEMPLATES / seite).read_text(encoding="utf-8")


def test_keine_seite_kennt_die_zuordnung_und_keine_setzt_die_kategorie_als_art():
    """Die Zuordnung steht nur in app/absence_requests.py: bis 1.9.152 schickte „Zeiten“ ohne Art den Namen der Kategorie selbst, die Plantafel den ersten Eintrag der Liste."""
    for seite in ("planning.html", "zeiten.html", "mobil_zeiten.html"):
        text = (TEMPLATES / seite).read_text(encoding="utf-8")
        assert "||KATEGORIE[el('adKategorie').value]" not in text
        assert "'/api/settings/option-groups/absence_types'" not in text
