from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import GeneralSettings, SettingOption, SettingOptionGroup


DEFAULT_OPTION_GROUPS = {
    "units": {
        "label": "Mengeneinheiten",
        "description": "Zentrale Einheiten für Leistungsverzeichnisse, freie Positionen und weitere Mengeneingaben.",
        "sort_order": 10,
        "options": [
            (10, "Stück", "Stück", True),
            (20, "Stck", "Stck", False),
            (30, "m", "m", False),
            (40, "m²", "m²", False),
            (50, "m³", "m³", False),
            (60, "kg", "kg", False),
            (70, "g", "g", False),
            (80, "t", "t", False),
            (90, "l", "l", False),
            (100, "h", "h", False),
            (110, "Tag", "Tag", False),
            (120, "Psch", "Psch", False),
            (130, "Rolle", "Rolle", False),
            (140, "Paket", "Paket", False),
            (150, "Set", "Set", False),
        ],
    },
    "quote_payment_terms": {
        "label": "Zahlungsbedingungen",
        "description": "Auswahltexte für Angebote und später Rechnungen.",
        "sort_order": 20,
        "options": [
            (10, "14 Tage netto", "Zahlbar innerhalb von 14 Tagen nach Rechnungsdatum ohne Abzug.", True),
            (20, "7 Tage netto", "Zahlbar innerhalb von 7 Tagen nach Rechnungsdatum ohne Abzug.", False),
            (30, "Nach Vereinbarung", "Zahlungsbedingungen nach Vereinbarung.", False),
        ],
    },
    "quote_intro_texts": {
        "label": "Angebots-Vortexte",
        "description": "Wiederverwendbare Einleitungstexte für Angebote.",
        "sort_order": 30,
        "options": [
            (10, "Standard", "Vielen Dank für Ihre Anfrage. Gerne bieten wir Ihnen die nachfolgend beschriebenen Leistungen an.", True),
        ],
    },
    "quote_outro_texts": {
        "label": "Angebots-Schlusstexte",
        "description": "Wiederverwendbare Schlusstexte für Angebote.",
        "sort_order": 40,
        "options": [
            (10, "Standard", "Wir freuen uns auf die Zusammenarbeit und stehen für Rückfragen gerne zur Verfügung.", True),
        ],
    },
    "invoice_intro_texts": {
        "label": "Rechnungs-Vortexte",
        "description": "Wiederverwendbare Einleitungstexte für Rechnungen.",
        "sort_order": 45,
        "options": [
            (10, "Standard", "Vielen Dank für die gute Zusammenarbeit. Wir erlauben uns, wie folgt zu berechnen.", True),
        ],
    },
    "invoice_outro_texts": {
        "label": "Rechnungs-Schlusstexte",
        "description": "Wiederverwendbare Schlusstexte für Rechnungen.",
        "sort_order": 46,
        "options": [
            (10, "Standard", "Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer auf das unten genannte Konto.", True),
        ],
    },
    "customer_categories": {
        "label": "Kundenkategorien",
        "description": "Zentrale Auswahl zur Kategorisierung von Kunden.",
        "sort_order": 50,
        "options": [
            (10, "Privatkunde", "Privatkunde", True),
            (20, "Gewerbekunde", "Gewerbekunde", False),
            (30, "Hausverwaltung", "Hausverwaltung", False),
            (40, "Architekt / Planer", "Architekt / Planer", False),
            (50, "Öffentlicher Auftraggeber", "Öffentlicher Auftraggeber", False),
            (60, "Versicherung", "Versicherung", False),
            (70, "Sonstige", "Sonstige", False),
        ],
    },
    "customer_salutations": {
        "label": "Anreden",
        "description": "Zentrale Auswahl für die Anrede von Kunden (Personen).",
        "sort_order": 55,
        "options": [
            (10, "Herr", "Herr", False),
            (20, "Frau", "Frau", False),
            (30, "Divers", "Divers", False),
            (40, "Firma", "Firma", False),
        ],
    },
    "project_categories": {
        "label": "Projektkategorien",
        "description": "Zentrale Kategorien zur Einordnung von Projekten und Projektmappen.",
        "sort_order": 60,
        "options": [
            (10, "Steildach", "Steildach", True),
            (20, "Flachdach", "Flachdach", False),
            (30, "Reparatur / Wartung", "Reparatur / Wartung", False),
            (40, "Dachfenster / Tageslicht", "Dachfenster / Tageslicht", False),
            (50, "Photovoltaik", "Photovoltaik", False),
            (60, "Fassade", "Fassade", False),
            (70, "Balkon / Terrasse", "Balkon / Terrasse", False),
            (80, "Klempner / Spengler", "Klempner / Spengler", False),
            (90, "Sonstiges", "Sonstiges", False),
        ],
    },
    "resource_types": {
        "label": "Ressourcentypen · Fuhrpark & Maschinen",
        "description": "Zentrale Typen für planbare Fahrzeuge, Maschinen, Anhänger und Geräte.",
        "sort_order": 65,
        "options": [
            (10, "Fahrzeug", "Fahrzeug", True),
            (20, "Anhänger", "Anhänger", False),
            (30, "Kran", "Kran", False),
            (40, "Maschine", "Maschine", False),
            (50, "Gerät / Werkzeug", "Gerät / Werkzeug", False),
            (60, "Sonstiges", "Sonstiges", False),
        ],
    },
    "operational_asset_inspection_types": {
        "label": "Prüfungsarten · Betriebsmittel",
        "description": "Zentrale Auswahl für Prüf- und Wartungsfristen von Betriebsmitteln.",
        "sort_order": 66,
        "options": [
            (10, "TÜV / Hauptuntersuchung", "TÜV / Hauptuntersuchung", True),
            (20, "Leiterprüfung", "Leiterprüfung", False),
            (30, "UVV-Prüfung", "UVV-Prüfung", False),
            (40, "Wartung", "Wartung", False),
            (50, "Sonstige Prüfung", "Sonstige Prüfung", False),
        ],
    },
    # Seit 1.4.2 (Betriebsmittel-Dokumentenablage, Punkt 4): bewusst dasselbe leichtgewichtige
    # Muster wie operational_asset_inspection_types oben -- KEINE DocumentCategory-Stammdaten
    # (1.3.62), da deren gesamter Zweck (is_sensitive/is_field_visible, zwei Schlösser gegen
    # "sensible Kategorie für Monteure sichtbar") hier gegenstandslos ist: Betriebsmittel-
    # Dokumente sind ausnahmslos Büro/Admin-only, es gibt keine Feld-sichtbare Stufe, die ein
    # Schloss überhaupt bräuchte. Siehe app/models.py::OperationalAssetDocument.
    "operational_asset_document_types": {
        "label": "Dokumentarten · Betriebsmittel",
        "description": "Zentrale Auswahl für die Dokumentenablage je Betriebsmittel (Anschaffungsrechnung, Leasingvertrag u. Ä.).",
        "sort_order": 66,
        "options": [
            (10, "Anschaffungsrechnung", "Anschaffungsrechnung", True),
            (20, "Leasingvertrag", "Leasingvertrag", False),
            (30, "Sonstiges", "Sonstiges", False),
        ],
    },
    "service_types": {
        "label": "Leistungstypen",
        "description": "Klassifizierung eigener (nicht importierter) Leistungen für spätere Auswertungen.",
        "sort_order": 67,
        "options": [
            (10, "Lohnarbeit", "lohnarbeit", True),
            (20, "Fremdleistung", "fremdleistung", False),
            (30, "Material", "material", False),
        ],
    },
    "absence_types": {
        "label": "Abwesenheitsarten",
        "description": "Zentrale Auswahl für Urlaub, Krankheit, Weiterbildung und weitere Abwesenheiten in der Plantafel.",
        "sort_order": 68,
        "options": [
            (10, "Urlaub", "Urlaub", True),
            (20, "Krankheit", "Krankheit", False),
            (30, "Weiterbildung", "Weiterbildung", False),
            (40, "Berufsschule", "Berufsschule", False),
            (50, "Freizeitausgleich", "Freizeitausgleich", False),
            (60, "Sonstiges", "Sonstiges", False),
        ],
    },
    "time_entry_types": {
        "label": "Zeiterfassung · Zeitarten",
        "description": "Zentrale Zeitarten für mobile und manuelle Zeitbuchungen. Fahrzeit wird getrennt von produktiven Soll-/Ist-Stunden ausgewertet.",
        "sort_order": 69,
        "options": [
            (10, "Baustellenzeit", "site", True),
            (20, "Fahrzeit", "travel", False),
            (30, "Werkstattzeit", "workshop", False),
            (40, "Sonstige Arbeitszeit", "other", False),
        ],
    },
    "time_entry_activities": {
        "label": "Zeiterfassung · Tätigkeiten",
        "description": "Optionale Tätigkeiten für Zeitbuchungen. Die Zuordnung zu einer LV-Position bleibt zusätzlich möglich.",
        "sort_order": 69,
        "options": [
            (10, "Allgemeine Baustellenarbeiten", "Allgemeine Baustellenarbeiten", True),
            (20, "Baustelleneinrichtung", "Baustelleneinrichtung", False),
            (30, "Abbruch / Rückbau", "Abbruch / Rückbau", False),
            (40, "Dämmung", "Dämmung", False),
            (50, "Dachdeckung", "Dachdeckung", False),
            (60, "Klempnerarbeiten", "Klempnerarbeiten", False),
            (70, "Dachfenster", "Dachfenster", False),
            (80, "Aufräumen / Baustellenordnung", "Aufräumen / Baustellenordnung", False),
            (90, "Reparatur", "Reparatur", False),
            (100, "Wartung", "Wartung", False),
        ],
    },
    "project_document_categories": {
        "label": "Dokumentkategorien (Kundenmappe & Projektmappe)",
        "description": "Zentrale Kategorien für Dateien in Kunden- und Projektmappen -- derselbe interne Schlüssel wie zuvor (project_document_categories), damit bestehende Dateien ihre gespeicherte Kategorie unverändert behalten. Bestehende Dateien behalten ihre gespeicherte Kategorie.",
        "sort_order": 70,
        "options": [
            (10, "Pläne", "Pläne", True),
            (20, "Bilder / Fotos", "Bilder / Fotos", False),
            (30, "Lieferscheine", "Lieferscheine", False),
            (40, "Aufmaß", "Aufmaß", False),
            (50, "Schriftverkehr", "Schriftverkehr", False),
            (60, "Verträge / Freigaben", "Verträge / Freigaben", False),
            (70, "Rechnungen / Belege", "Rechnungen / Belege", False),
            (80, "Sonstiges", "Sonstiges", False),
        ],
    },
    "roof_types": {
        "label": "Dachflächen · Dachtyp",
        "description": "Dachtyp einer einzelnen Dachfläche (RoofArea).",
        "sort_order": 71,
        "options": [
            (10, "Steildach", "Steildach", True),
            (20, "Flachdach", "Flachdach", False),
            (30, "Gründach", "Gründach", False),
            (40, "Terrasse", "Terrasse", False),
        ],
    },
    "roof_coverings": {
        "label": "Dachflächen · Eindeckung",
        "description": "Eindeckungsart einer einzelnen Dachfläche (RoofArea).",
        "sort_order": 72,
        "options": [
            (10, "Bitumen zweilagig", "Bitumen zweilagig", True),
            (20, "EPDM", "EPDM", False),
            (30, "FPO", "FPO", False),
            (40, "PVC", "PVC", False),
            (50, "Ziegel", "Ziegel", False),
            (60, "Schiefer", "Schiefer", False),
            (70, "Trapezblech", "Trapezblech", False),
            (80, "Sonstiges", "Sonstiges", False),
        ],
    },
    # "roof_component_types" seit 1.2.19 ENTFERNT -- zur echten Tabelle RoofComponentType
    # hochgestuft (siehe app/models.py), damit is_area (flächige vs. punktförmige Markierung auf
    # der Skizze) an der Bauteilart selbst hängen kann statt inkonsistent am einzelnen
    # RoofComponent. Migration 4609e3fc8976 übernimmt die zuvor hier gesäten setting_options-
    # Zeilen (inkl. eventueller eigener, selbst angelegter Bauteilarten) in die neue Tabelle;
    # bereits gesäte SettingOptionGroup/SettingOption-Zeilen einer laufenden Installation bleiben
    # als toter Datenbestand stehen (siehe CLAUDE.md, "Bekannte, bewusst offene Punkte").
    "layer_daemmung": {
        "label": "Dachaufbau · Dämmung",
        "description": "Ausführung für Dämmschichten im Dachaufbau (RoofLayer).",
        "sort_order": 74,
        "options": [
            (10, "Mineralwolle", "Mineralwolle", True),
            (20, "PIR", "PIR", False),
            (30, "EPS", "EPS", False),
            (40, "XPS", "XPS", False),
            (50, "Holzfaser", "Holzfaser", False),
            (60, "Zellulose", "Zellulose", False),
        ],
    },
    "layer_unterspannbahn": {
        "label": "Dachaufbau · Unterspannbahn",
        "description": "Ausführung der Unterspannbahn im Dachaufbau (RoofLayer).",
        "sort_order": 75,
        "options": [
            (10, "diffusionsoffen", "diffusionsoffen", True),
            (20, "diffusionshemmend", "diffusionshemmend", False),
            (30, "Bitumenbahn", "Bitumenbahn", False),
        ],
    },
    "layer_dampfsperre": {
        "label": "Dachaufbau · Dampfsperre",
        "description": "Ausführung der Dampfsperre im Dachaufbau (RoofLayer).",
        "sort_order": 76,
        "options": [
            (10, "PE-Folie", "PE-Folie", True),
            (20, "Aluminium-Verbundbahn", "Aluminium-Verbundbahn", False),
            (30, "Bitumendampfsperre", "Bitumendampfsperre", False),
        ],
    },
    "layer_abdichtung": {
        "label": "Dachaufbau · Abdichtung",
        "description": "Ausführung der Abdichtung im Dachaufbau (RoofLayer).",
        "sort_order": 77,
        "options": [
            (10, "Bitumen zweilagig", "Bitumen zweilagig", True),
            (20, "EPDM", "EPDM", False),
            (30, "FPO", "FPO", False),
            (40, "PVC", "PVC", False),
            (50, "Flüssigabdichtung", "Flüssigabdichtung", False),
        ],
    },
    "layer_oberflaeche": {
        "label": "Dachaufbau · Oberflächenschutz",
        "description": "Ausführung des Oberflächenschutzes im Dachaufbau (RoofLayer).",
        "sort_order": 78,
        "options": [
            (10, "Bekiesung", "Bekiesung", True),
            (20, "Plattenbelag", "Plattenbelag", False),
            (30, "Begrünung extensiv", "Begrünung extensiv", False),
            (40, "Begrünung intensiv", "Begrünung intensiv", False),
            (50, "ohne", "ohne", False),
        ],
    },
    "layer_traglage": {
        "label": "Dachaufbau · Traglage",
        "description": "Ausführung der Traglage im Dachaufbau (RoofLayer).",
        "sort_order": 79,
        "options": [
            (10, "Betondecke", "Betondecke", True),
            (20, "Trapezblech", "Trapezblech", False),
            (30, "Holzschalung", "Holzschalung", False),
            (40, "Sparren", "Sparren", False),
        ],
    },
}


def ensure_default_option_groups(db: Session) -> list[SettingOptionGroup]:
    """Initialisiert Gruppen genau einmal. Existierende Gruppen werden nicht wieder mit Defaults aufgefüllt."""
    existing = {g.group_key: g for g in db.scalars(select(SettingOptionGroup)).all()}
    changed = False
    for key, cfg in DEFAULT_OPTION_GROUPS.items():
        group = existing.get(key)
        if group is None:
            group = SettingOptionGroup(
                group_key=key, label=cfg["label"], description=cfg["description"], sort_order=cfg["sort_order"]
            )
            db.add(group)
            db.flush()
            option_rows = list(cfg["options"])
            # Bereits in älteren Versionen gepflegte Standardtexte beim ersten Upgrade übernehmen.
            general = db.get(GeneralSettings, 1)
            if key == "quote_intro_texts" and general and general.default_quote_intro:
                option_rows = [(10, "Bisheriger Standard", general.default_quote_intro, True)]
            elif key == "quote_outro_texts" and general and general.default_quote_outro:
                option_rows = [(10, "Bisheriger Standard", general.default_quote_outro, True)]
            for sort_order, label, value, is_default in option_rows:
                db.add(SettingOption(
                    group_id=group.id, label=label, value=value, sort_order=sort_order,
                    active=True, is_default=is_default,
                ))
            existing[key] = group
            changed = True
    if changed:
        db.commit()
    return db.scalars(
        select(SettingOptionGroup).options(selectinload(SettingOptionGroup.options))
        .order_by(SettingOptionGroup.sort_order, SettingOptionGroup.label)
    ).all()


def get_option_group(db: Session, group_key: str) -> SettingOptionGroup | None:
    ensure_default_option_groups(db)
    return db.scalar(
        select(SettingOptionGroup).options(selectinload(SettingOptionGroup.options))
        .where(SettingOptionGroup.group_key == group_key)
    )


def option_group_to_dict(group: SettingOptionGroup) -> dict:
    return {
        "id": group.id,
        "group_key": group.group_key,
        "label": group.label,
        "description": group.description,
        "sort_order": group.sort_order,
        "options": [
            {
                "id": o.id, "group_key": group.group_key, "label": o.label, "value": o.value,
                "sort_order": o.sort_order, "active": o.active, "is_default": o.is_default,
            }
            for o in sorted(group.options, key=lambda x: (x.sort_order, x.id))
        ],
    }


def set_default_option(db: Session, group: SettingOptionGroup, option: SettingOption) -> None:
    if option.is_default:
        for sibling in group.options:
            if sibling.id != option.id:
                sibling.is_default = False


def active_options(db: Session, group_key: str) -> list[SettingOption]:
    group = get_option_group(db, group_key)
    if group is None:
        return []
    return [o for o in sorted(group.options, key=lambda x: (x.sort_order, x.id)) if o.active]


def default_option_value(db: Session, group_key: str) -> str | None:
    rows = active_options(db, group_key)
    default = next((o for o in rows if o.is_default), None)
    return (default or (rows[0] if rows else None)).value if rows else None
