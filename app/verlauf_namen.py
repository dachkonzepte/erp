"""Lesbare Namen für die Änderungshistorie (seit 1.8.138, Fehlerrunde vor Stufe 2, Punkt 7).

Die Historie speichert beim Schreiben Art und Feldnamen (`TYPE_LABELS`, `FIELD_LABELS` in app/audit.py) und die Werte roh. Fehlte ein
Eintrag, stand bis 1.8.137 der Klassen- bzw. Spaltenname da („WorkPreparationTeamEmployee“, „property_address“), und jeder Code roh
(„entwurf → beauftragt“, „pending“, „site“). Übersetzt wird deshalb beim Lesen (`lesbar()`, aus /api/audit-logs) -- so werden auch
Einträge von vor 1.8.138 lesbar. Die gespeicherten `entity_type` und `field_name` bleiben roh: an ihnen hängen Filter und die Schwärzung
für Büro – Auftrag (app/routers/audit.py); angezeigt wird `entity_type_label`.

Werte: je Feldname eine Tabelle Code → Bezeichnung, wo möglich aus den Konstanten der Fachmodule (dieselben Wörter wie in der
Oberfläche). Ein Code, den keine Tabelle kennt, bleibt stehen. `tests/test_v436_fehlerrunde_vor_stufe_2.py` verlangt für jede feste
Kleinschreibung einer protokollierten Spalte (Katalog von tests/test_v364_feste_werte_spaltenlaenge.py) eine Bezeichnung.
"""

from functools import lru_cache

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
}
_ZEITARTEN = {"site": "Baustelle", "workshop": "Werkstatt", "travel": "Fahrzeit", "other": "Sonstige",
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


def wert_lesbar(field_name: str | None, value: str | None) -> str | None:
    if value is None or field_name is None:
        return value
    return _werte().get(field_name, {}).get(value, value)


def lesbar(zeile):
    """Übersetzt eine Zeile (AuditLogOut) für die Anzeige -- nach der Schwärzung, die an den rohen Namen hängt."""
    zeile.entity_type_label = art_lesbar(zeile.entity_type)
    if zeile.entity_label and zeile.entity_label in _art_namen():
        zeile.entity_label = _art_namen()[zeile.entity_label]
    zeile.field_label = feld_lesbar(zeile.field_name, zeile.field_label)
    zeile.old_value = wert_lesbar(zeile.field_name, zeile.old_value)
    zeile.new_value = wert_lesbar(zeile.field_name, zeile.new_value)
    return zeile
