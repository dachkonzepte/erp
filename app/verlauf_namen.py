"""Lesbare Namen für die Änderungshistorie (seit 1.8.138, Fehlerrunde vor Stufe 2, Punkt 7).

Die Historie speichert beim Schreiben Art und Feldnamen (`TYPE_LABELS`, `FIELD_LABELS` in app/audit.py) und die Werte roh. Fehlte ein
Eintrag, stand bis 1.8.137 der Klassen- bzw. Spaltenname da („WorkPreparationTeamEmployee“, „property_address“), und jeder Code roh
(„entwurf → beauftragt“, „pending“, „site“). Übersetzt wird deshalb beim Lesen (`lesbar()`, aus /api/audit-logs) -- so werden auch
Einträge von vor 1.8.138 lesbar. Die gespeicherten `entity_type` und `field_name` bleiben roh: an ihnen hängen Filter und die Schwärzung
für Büro – Auftrag (app/routers/audit.py); angezeigt wird `entity_type_label`.

Werte: je Feldname eine Tabelle Code → Bezeichnung, wo möglich aus den Konstanten der Fachmodule (dieselben Wörter wie in der
Oberfläche). Ein Code, den keine Tabelle kennt, bleibt stehen. `tests/test_v436_fehlerrunde_vor_stufe_2.py` verlangt für jede feste
Kleinschreibung einer protokollierten Spalte (Katalog von tests/test_v364_feste_werte_spaltenlaenge.py) eine Bezeichnung.

Seit 1.9.123 (Stufe 5, R1 Nachrunde, Punkt 5, Merkliste 7b) auch die Werte selbst, beim Lesen je Antwort (lesbar_alle()): Zahlen deutsch mit
Einheit (Feld `einheit`, „850 → 851 m²“), Datum und Zeitpunkt deutsch, gespeicherte UTC-Zeitpunkte in Europe/Berlin (Regel 20; naive Ortszeit
bleibt, ORTSZEIT), eine ID als Name des Datensatzes (Kunde, Sachbearbeiter, Spalte …; je Tabelle eine Abfrage), JSON als „Daten (n Angaben)“,
Zeitarten nach der Auswahlliste „Zeitarten“ wie in der Oberfläche, und dieselben Werte im Namen des Datensatzes („· 14.10.2026 · Baustellenzeit
· 3,25 h“ statt „· 2026-10-14 · site · 3.2500 h“). Ein Eintrag von vor 1.9.123 wird so ebenfalls lesbar -- gespeichert bleibt alles roh.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from sqlalchemy import Date, DateTime, Float, Integer, Numeric, select
from sqlalchemy import inspect as sa_inspect

from .audit import FIELD_LABELS, RECHNUNGSARTEN, TYPE_LABELS


@lru_cache(maxsize=1)
def _art_namen() -> dict[str, str]:
    """Klassenname → Bezeichnung (für gespeicherte Klassennamen von vor 1.8.138)."""
    return {cls.__name__: name for cls, name in TYPE_LABELS.items()}


def art_lesbar(entity_type: str | None) -> str | None:
    if entity_type is None:
        return None
    return _art_namen().get(entity_type, entity_type)


def feld_lesbar(field_name: str | None, field_label: str | None = None) -> str | None:
    """Gespeicherte Bezeichnung, wenn sie eine ist (nicht der Feldname selbst), sonst die heutige aus FIELD_LABELS."""
    if field_label and field_label != field_name:
        return field_label
    if field_name is None:
        return field_label
    return FIELD_LABELS.get(field_name, field_label or field_name)


_STATUS = {
    "entwurf": "Entwurf", "versendet": "Versendet", "beauftragt": "Beauftragt", "storniert": "Storniert",
    "abgeschlossen": "Abgeschlossen", "gegenstandslos": "Gegenstandslos", "anfrage": "Anfrage", "angebot": "Angebot",
    "offen": "Offen", "erledigt": "Erledigt", "geplant": "Geplant", "bedarf": "Bedarf",
    # Abwesenheitsantrag
    "pending": "Beantragt", "approved": "Genehmigt", "rejected": "Abgelehnt", "cancelled": "Zurückgezogen",
    # Zeitbuchung
    "running": "Läuft", "booked": "Gebucht",
    # Anfrage
    "neu": "Neu", "termin_offen": "Termin offen", "termin_geplant": "Termin geplant", "aufmass_erfolgt": "Aufmaß erfolgt",
    "projekt_erstellt": "Projekt erstellt", "gewonnen": "Gewonnen", "verloren": "Verloren",
    # seit 1.9.115: Einsatzbericht, Wartungsvertrag (app/maintenance_contracts.py::STATUSES), Rechnung vor 1.8.78
    "unterschrieben": "Unterschrieben", "aktiv": "Aktiv", "pausiert": "Pausiert", "beendet": "Beendet", "bezahlt": "Bezahlt",
    # seit 1.9.124: Status des Auftrags (app/auftragsstatus.py); die alten Werte bis 1.9.123 bleiben für ältere Einträge lesbar
    "laeuft": "Läuft", "arbeitsvorbereitung": "Arbeitsvorbereitung", "in_ausfuehrung": "In Ausführung",
}
# Seit 1.9.123 die Namen der Auswahlliste „Zeitarten“ (app/option_settings.py, bis 1.9.122 „Baustelle“, „Werkstatt“, „Sonstige“); in einer
# Antwort gilt die Auswahlliste der Datenbank (lesbar_alle()), diese Tabelle nur ohne sie.
_ZEITARTEN = {"site": "Baustellenzeit", "workshop": "Werkstattzeit", "travel": "Fahrzeit", "other": "Sonstige Arbeitszeit",
              "weather_winter": "Schlechtwetter Winter", "weather_summer": "Schlechtwetter Sommer"}
_VON_HAND = {"manual": "Von Hand", "timer": "Zeitmessung"}
_ERKLAERT = {"auftraggeber": "Auftraggeber", "beteiligter": "Beteiligter"}
_GK_MODUS = {"eur": "Betrag (€)", "pct": "Prozent"}


@lru_cache(maxsize=1)
def _werte() -> dict[str, dict[str, str]]:
    """Feldname → {Code: Bezeichnung}. Lazy, damit app/audit.py die Fachmodule nicht beim Import lädt."""
    from .absence_requests import ABSENCE_CATEGORY_LABELS
    from .acceptances import KINDS as ABNAHME_ARTEN
    from .contacts import KINDS as KONTAKT_ARTEN
    from .contract_basis import CONTRACT_BASES
    from .defects import EVENT_KINDS, RELEASES, SOURCES as MANGEL_QUELLEN, STANCES, STATUSES as MANGEL_STATUS
    from .dunning_charges import BASIS_LABELS, KIND_LABELS as NEBENFORDERUNGEN
    from .dunning_texts import LEGAL_TEXT_LABELS
    from .option_settings import DEFAULT_OPTION_GROUPS
    from .payments import KIND_LABELS as ZAHLUNGSARTEN
    from .permissions import ROLE_LABELS
    from .project_participants import ROLES as BETEILIGTEN_ROLLEN
    from .service_reports import REPORT_TYPE_LABELS
    from .warranty import WORK_KINDS

    def gross(tabelle: dict) -> dict:
        """Bezeichnungen mit großem Anfangsbuchstaben, wie sie in der Historie als Wert stehen."""
        return {k: (v[:1].upper() + v[1:]) if isinstance(v, str) else v for k, v in tabelle.items()}

    beteiligte = {k: (v["label"] if isinstance(v, dict) else v) for k, v in dict(BETEILIGTEN_ROLLEN).items()}
    mangel = {**gross(MANGEL_STATUS), **gross(STANCES), **gross(RELEASES)}
    gruppen = {k: v["label"] for k, v in DEFAULT_OPTION_GROUPS.items() if isinstance(v, dict) and "label" in v}
    gruppen.update({  # Dachaufbau-Listen (Schichttypen, seit 1.2.18) -- nicht in DEFAULT_OPTION_GROUPS
        "layer_abdichtung": "Dachaufbau: Abdichtung", "layer_daemmung": "Dachaufbau: Dämmung",
        "layer_dampfsperre": "Dachaufbau: Dampfsperre", "layer_oberflaeche": "Dachaufbau: Oberflächenschutz",
        "layer_traglage": "Dachaufbau: Traglage", "layer_unterspannbahn": "Dachaufbau: Unterspannbahn",
    })
    return {
        "status": _STATUS,
        "old_status": _STATUS, "new_status": _STATUS,  # seit 1.9.124: Statuswechsel am Auftrag
        "role": {**ROLE_LABELS, **beteiligte},
        "entry_type": _ZEITARTEN,
        "absence_category": gross(ABSENCE_CATEGORY_LABELS),
        "compensation_type": {"hourly": "Stundenlohn", "fixed_salary": "Monatsfestgehalt"},
        "allocation_type": {"labor_rate": "Stundenkostenverrechnungssatz", "variable_overhead": "Variable Gemeinkosten",
                            "excluded": "Nicht zugeordnet"},
        "employee_group": {"gewerblich": "Gewerblich", "kaufmaennisch": "Kaufmännisch"},
        "contract_basis": CONTRACT_BASES,
        "work_kind": gross(WORK_KINDS),
        "kind": {"beleg": "Beleg", "foto": "Foto", "unterschrift": "Unterschrift", **gross(KONTAKT_ARTEN), **gross(EVENT_KINDS),
                 **NEBENFORDERUNGEN, **gross(ABNAHME_ARTEN), **ZAHLUNGSARTEN},
        "signer_kind": {"frei": "Frei", "konto": "Angemeldetes Konto", "auftraggeber": "Auftraggeber laut Auftrag",
                        "beteiligter": "Beteiligter", "ag_oder_beteiligter": "Auftraggeber oder Beteiligter"},
        "context_type": {"auftrag": "Auftrag", "objekt": "Objekt", "betriebsmittel": "Betriebsmittel", "betrieb": "Betrieb"},
        "declared_by": _ERKLAERT,
        "value": mangel, "previous_value": mangel,
        "source": {**MANGEL_QUELLEN, "sonstiges": "Sonstiges", "manual": "Von Hand", "migration": "Übernahme (Migration)",
                   "quote": "Aus dem Angebot", "quote_sync": "Abgleich mit dem Angebot", "timer": "Zeitmessung",
                   "group_manual": "Gruppe, von Hand", "group_timer": "Gruppe, Zeitmessung"},
        "text_key": LEGAL_TEXT_LABELS,
        "priority": {"niedrig": "Niedrig", "normal": "Normal", "hoch": "Hoch", "dringend": "Dringend"},
        "basis": gross(BASIS_LABELS),
        "fixed_overhead_mode": _GK_MODUS, "variable_overhead_mode": _GK_MODUS,
        "sequence_key": {"customer": "Kunden", "inquiry": "Anfragen", "project": "Projekte", "quote": "Angebote",
                         "order": "Aufträge", "invoice": "Rechnungen", "reminder": "Mahnungen"},
        "result": {"abgenommen": "Abgenommen", "verweigert": "Verweigert"},
        "scope": {"gesamt": "Gesamtabnahme", "teil": "Teilabnahme"},
        "origin": {"erfasst": "Erfasst", "uebernommen": "Übernommen"},
        "position_type": {"normal": "Normal"},
        "source_format": {"manual": "Von Hand"},
        "group_key": gruppen,
        "mode": _VON_HAND,
        "datev_target": {"lodas": "LODAS", "lohn_gehalt": "Lohn und Gehalt"},
        # seit 1.9.115: Rechnungen, Einsatzberichte, Termine
        "invoice_type": RECHNUNGSARTEN,
        "report_type": REPORT_TYPE_LABELS,
        "rounding_rule": {"half_up": "Kaufmännisch (ab 1.8.11)"},
        "external_source": {"erp": "Im ERP angelegt", "outlook": "Aus Outlook"},
        "unit": {"pschl.": "Pauschal (pschl.)"},
    }


MANGEL_ARTEN = {"Mangel", "Defect", "DefectEvent"}  # „value“/„previous_value“ sind nur am Mangel Codes (Haltung, Status, Freigabe)


def wert_lesbar(field_name: str | None, value: str | None, entity_type: str | None = None, zeitarten: dict | None = None) -> str | None:
    """Ein Code als Bezeichnung. entity_type (seit 1.9.123): „value“ und „previous_value“ nur am Mangel übersetzen -- bis 1.9.122 auch z. B.
    den Wert eines Kundenwissens („offen“ -> „Offen“). zeitarten: die Auswahlliste der Datenbank."""
    if value is None or field_name is None:
        return value
    if field_name in ("value", "previous_value") and entity_type is not None and entity_type not in MANGEL_ARTEN:
        return value
    if field_name == "entry_type" and zeitarten and value in zeitarten:
        return zeitarten[value]
    return _werte().get(field_name, {}).get(value, value)


# ---------------------------------------------------------------------------------------------------------------------------------------
# Seit 1.9.123: Werte lesbar (Kopf der Datei)
# ---------------------------------------------------------------------------------------------------------------------------------------

EINHEITEN = {
    "€": ("amount", "annual_overhead", "billed_total", "equipment_cost", "fee_amount", "hourly_wage", "labor_rate", "labor_rate_override",
          "lump_sum_net", "manual_sale_price", "monthly_salary", "other_cost", "outstanding_amount", "purchase_price",
          "purchase_price_override", "source_purchase_price", "source_unit_price", "subcontractor_cost", "unit_price"),
    "%": ("default_vat_rate", "employer_cost_pct", "material_markup_pct", "material_markup_pct_override", "overhead_pct",
          "overhead_pct_override", "productive_time_pct", "rate_percent", "risk_profit_pct", "risk_profit_pct_override", "skonto_percent",
          "target_profit_pct", "vat_rate", "waste_pct"),
    "h": ("daily_target_hours", "daily_work_hours", "default_travel_hours_per_employee_day", "hours", "planned_hours", "threshold_hours",
          "travel_hours_per_employee_day", "weekly_hours"),
    # ohne die Standardpause (seit 1.9.61 liest sie niemand, Wächter tests/test_v486) -- ein alter Eintrag dazu ohne Einheit
    "min": ("break_minutes", "min_break_minutes", "rounding_minutes", "site_time_minutes", "workshop_time_minutes"),
    "m²": ("area_sqm",), "°": ("pitch_degrees",), "px": ("sidebar_logo_height_px",),
    "Monate": ("interval_months", "warranty_months"), "Tage": ("skonto_days", "warranty_days"),
}
EINHEIT_JE_FELD = {feld: einheit for einheit, felder in EINHEITEN.items() for feld in felder}
MENGEN = {"quantity", "ist_quantity", "soll_quantity", "billed_quantity", "planned_quantity", "calculated_quantity"}  # Einheit der Position
GROESSEN = {"file_size", "poa_size_bytes", "acceptance_poa_size_bytes"}  # Bytes
ORTSZEIT = {"started_at", "ended_at", "start_at", "end_at", "visit_at", "follow_up_at"}  # naive Ortszeit (Regel 20), sonst naive UTC
OHNE_NAMEN = {"task_id"}  # den Titel einer Aufgabe sehen nur Admin und Zuständige -- bleibt „Nr. n“
_ISO_TAG = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_ZEIT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")
_DEZIMAL = re.compile(r"^-?\d+\.\d+$")


@lru_cache(maxsize=1)
def _klassen_je_art() -> dict[str, list]:
    """Gespeicherte Art (die Bezeichnung, vor 1.8.138 der Klassenname) -> Modellklassen."""
    je_art: dict[str, list] = {}
    for cls, name in TYPE_LABELS.items():
        je_art.setdefault(name, []).append(cls)
        je_art.setdefault(cls.__name__, []).append(cls)
    return je_art


@lru_cache(maxsize=1)
def _klasse_je_tabelle() -> dict:
    from .database import Base
    return {m.local_table.name: m.class_ for m in Base.registry.mappers}


def _spalte(entity_type: str | None, field_name: str | None):
    """(Klasse, Spalte) des Felds einer Art -- die erste Klasse der Art, die das Feld hat."""
    if not field_name:  # angelegt/gelöscht: kein Feld
        return None, None
    for cls in _klassen_je_art().get(entity_type or "", []):
        spalten = sa_inspect(cls).columns
        if field_name in spalten:
            return cls, spalten[field_name]
    return None, None


def _ziel(field_name: str, spalte) -> type | None:
    """Die Klasse, auf die eine ID zeigt: der Fremdschlüssel der Spalte; ein Konto (…_user_id) und die Herkunft einer Angebotsposition auch
    ohne Fremdschlüssel im Modell."""
    if field_name in OHNE_NAMEN:
        return None
    for fk in getattr(spalte, "foreign_keys", ()) or ():
        return _klasse_je_tabelle().get(fk.column.table.name)
    from .models import AppUser, QuoteItem, QuoteSection
    if field_name.endswith("_user_id"):
        return AppUser
    return {"source_quote_item_id": QuoteItem, "source_quote_section_id": QuoteSection}.get(field_name)


def _deutsch(text: str) -> str:
    """'1234.5' -> '1.234,5'."""
    ganz, _, nach = text.partition(".")
    zeichen = "-" if ganz.startswith("-") else ""
    ganz = ganz.lstrip("-")
    gruppen = []
    while len(ganz) > 3:
        gruppen.insert(0, ganz[-3:])
        ganz = ganz[:-3]
    gruppen.insert(0, ganz)
    return zeichen + ".".join(gruppen) + ("," + nach if nach else "")


def zahl_lesbar(wert: str, geld: bool = False) -> str:
    """Eine gespeicherte Zahl deutsch: Geld mit zwei Stellen (kaufmännisch, Regel 19), sonst ohne Nullen am Ende."""
    from .rounding import round_money
    try:
        zahl = Decimal(wert)
    except (InvalidOperation, ValueError):
        return wert
    if geld:
        return _deutsch(format(round_money(zahl), "f"))
    text = format(zahl, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return _deutsch(text or "0")


def _groesse(wert: str) -> str:
    try:
        n = int(wert)
    except ValueError:
        return wert
    if n < 1024:
        return f"{n} Byte"
    if n < 1024 * 1024:
        return zahl_lesbar(str(round(Decimal(n) / 1024, 1))) + " KB"
    return zahl_lesbar(str(round(Decimal(n) / (1024 * 1024), 1))) + " MB"


def zeit_lesbar(wert: str, ortszeit: bool) -> str:
    """Ein gespeicherter Zeitpunkt deutsch, in Europe/Berlin -- naive UTC umgerechnet, naive Ortszeit unverändert."""
    from .berlin_time import to_berlin
    try:
        zeitpunkt = datetime.fromisoformat(wert)
    except ValueError:
        return wert
    if not ortszeit:
        zeitpunkt = to_berlin(zeitpunkt)
    return zeitpunkt.strftime("%d.%m.%Y %H:%M")


def _json_lesbar(wert: str) -> str | None:
    if not wert or wert[0] not in "{[":
        return None
    try:
        daten = json.loads(wert)
    except ValueError:
        return None
    if isinstance(daten, dict):
        return f"Daten ({len(daten)} {'Angabe' if len(daten) == 1 else 'Angaben'})"
    if isinstance(daten, list):
        return f"{len(daten)} {'Eintrag' if len(daten) == 1 else 'Einträge'}"
    return None


@dataclass
class Kontext:
    """Was eine Antwort zum Lesen braucht: Namen zu IDs je Klasse, Einheiten der Positionen, die Zeitarten der Auswahlliste."""
    namen: dict = field(default_factory=dict)       # (Klasse, id) -> Name
    einheiten: dict = field(default_factory=dict)   # (Klasse, id) -> Einheit der Position
    zeitarten: dict = field(default_factory=dict)   # Code -> Name
    mitarbeiter: dict = field(default_factory=dict)  # id -> Name (für „Mitarbeiter #12“ im Namen des Datensatzes)


def _name(obj) -> str:
    """Der Name eines Datensatzes wie in der Historie (app/audit.py::_entity_label()); trägt die Klasse keinen eigenen, ein Feld des Satzes."""
    from .audit import _entity_label
    text = _entity_label(obj)
    if not text or text in (type(obj).__name__, TYPE_LABELS.get(type(obj))):
        for feld in ("display_name", "label", "name", "title", "invoice_number", "username"):
            wert = getattr(obj, feld, None)
            if wert:
                return str(wert)
        return f"Nr. {obj.id}"
    return str(text)


def _ids(werte) -> set[int]:
    return {int(w) for w in werte if w is not None and str(w).isdigit()}


def kontext_laden(db, zeilen) -> Kontext:
    """Je Klasse eine Abfrage für die Namen der IDs, je Positionsklasse eine für die Einheiten, dazu die Zeitarten."""
    from .models import Employee, SettingOption, SettingOptionGroup
    k = Kontext()
    gesucht: dict = {}
    mengen: dict = {}
    for z in zeilen:
        cls, spalte = _spalte(z.entity_type, z.field_name)
        if spalte is not None and (ziel := _ziel(z.field_name, spalte)) is not None:
            gesucht.setdefault(ziel, set()).update(_ids((z.old_value, z.new_value)))
        if z.field_name in MENGEN:
            for kl in _klassen_je_art().get(z.entity_type or "", []):
                spalten = sa_inspect(kl).columns
                if "unit" in spalten and z.field_name in spalten:
                    mengen.setdefault(kl, set()).update(_ids((z.entity_id,)))
        for treffer in re.findall(r"Mitarbeiter #(\d+)", z.entity_label or ""):
            gesucht.setdefault(Employee, set()).add(int(treffer))
    for ziel, ids in gesucht.items():
        if ids:
            for obj in db.scalars(select(ziel).where(ziel.id.in_(ids))):
                k.namen[(ziel, obj.id)] = _name(obj)
    k.mitarbeiter = {i: n for (cls, i), n in k.namen.items() if cls is Employee}
    for kl, ids in mengen.items():
        if ids:
            for obj in db.scalars(select(kl).where(kl.id.in_(ids))):
                if getattr(obj, "unit", None):
                    k.einheiten[(kl, obj.id)] = obj.unit
    gruppe = db.scalar(select(SettingOptionGroup).where(SettingOptionGroup.group_key == "time_entry_types"))
    if gruppe is not None:
        k.zeitarten = {o.value: o.label for o in db.scalars(select(SettingOption).where(SettingOption.group_id == gruppe.id))}
    return k


def _wert(zeile, wert: str | None, k: Kontext) -> tuple[str | None, bool]:
    """(lesbarer Wert, ob es eine Zahl ist -- dann gilt die Einheit)."""
    if wert is None:
        return None, False
    cls, spalte = _spalte(zeile.entity_type, zeile.field_name)
    feld = zeile.field_name or ""
    if spalte is not None:
        ziel = _ziel(feld, spalte)
        if ziel is not None and wert.isdigit():
            return k.namen.get((ziel, int(wert)), f"Nr. {wert} (nicht mehr vorhanden)"), False
        if feld in GROESSEN:
            return _groesse(wert), False
        typ = spalte.type
        if isinstance(typ, DateTime):
            return zeit_lesbar(wert, feld in ORTSZEIT), False
        if isinstance(typ, Date) and _ISO_TAG.match(wert):
            return date.fromisoformat(wert).strftime("%d.%m.%Y"), False
        if isinstance(typ, (Numeric, Float)) or (isinstance(typ, Integer) and feld in EINHEIT_JE_FELD):
            return zahl_lesbar(wert, geld=EINHEIT_JE_FELD.get(feld) == "€"), True
    json_text = _json_lesbar(wert)
    if json_text is not None:
        return json_text, False
    if spalte is None:  # eine Art ohne Modell (z. B. „Vertrag“, „Aufgabe“): nur, was der Wert selbst zeigt
        if _ISO_ZEIT.match(wert):
            return zeit_lesbar(wert, feld in ORTSZEIT), False
        if _ISO_TAG.match(wert):
            return date.fromisoformat(wert).strftime("%d.%m.%Y"), False
        if _DEZIMAL.match(wert):
            return zahl_lesbar(wert, geld=EINHEIT_JE_FELD.get(feld) == "€"), True
    return wert_lesbar(feld, wert, zeile.entity_type, k.zeitarten), False


def _einheit(zeile, k: Kontext) -> str | None:
    feld = zeile.field_name or ""
    if feld in MENGEN:
        for kl in _klassen_je_art().get(zeile.entity_type or "", []):
            if zeile.entity_id and zeile.entity_id.isdigit() and (kl, int(zeile.entity_id)) in k.einheiten:
                return k.einheiten[(kl, int(zeile.entity_id))]
        return None
    return EINHEIT_JE_FELD.get(feld)


def name_lesbar(text: str | None, k: Kontext) -> str | None:
    """Der Name des Datensatzes: ISO-Tage deutsch, Zeitarten übersetzt, Stunden deutsch, „Mitarbeiter #12“ als Name."""
    if not text:
        return text
    text = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: f"{m[3]}.{m[2]}.{m[1]}", text)
    zeitarten = {**_ZEITARTEN, **k.zeitarten}
    text = re.sub(r"(?<= · )([a-z_]+)(?= · | ?$)", lambda m: zeitarten.get(m[1], m[1]), text)
    text = re.sub(r"(-?\d+\.\d+)(?= h\b)", lambda m: zahl_lesbar(m[1]), text)
    text = re.sub(r"Mitarbeiter #(\d+)", lambda m: k.mitarbeiter.get(int(m[1]), f"Mitarbeiter Nr. {m[1]}"), text)
    return re.sub(r"Gruppe #(\d+)", r"Gruppenbuchung Nr. \1", text)


def lesbar(zeile, kontext: Kontext | None = None):
    """Übersetzt eine Zeile (AuditLogOut) für die Anzeige -- nach der Schwärzung, die an den rohen Namen hängt. Ohne Kontext (ohne Datenbank)
    bleiben IDs Zahlen und Mengen ohne Einheit."""
    k = kontext or Kontext()
    zeile.entity_type_label = art_lesbar(zeile.entity_type)
    if zeile.entity_label and zeile.entity_label in _art_namen():
        zeile.entity_label = _art_namen()[zeile.entity_label]
    zeile.entity_label = name_lesbar(zeile.entity_label, k)
    zeile.field_label = feld_lesbar(zeile.field_name, zeile.field_label)
    alt, alt_zahl = _wert(zeile, zeile.old_value, k)
    neu, neu_zahl = _wert(zeile, zeile.new_value, k)
    zeile.einheit = _einheit(zeile, k) if (alt_zahl or neu_zahl) else None
    zeile.old_value, zeile.new_value = alt, neu
    return zeile


def lesbar_alle(db, zeilen: list) -> list:
    """Seit 1.9.123: jede Zeile einer Antwort lesbar, mit einem Kontext für alle (wenige Abfragen statt einer je Zeile)."""
    k = kontext_laden(db, zeilen)
    return [lesbar(z, k) for z in zeilen]
