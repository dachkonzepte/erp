"""Dokumentkategorien -- echte Stammdatentabelle (seit 1.3.62, Fundament für die Dateiablage je
Objekt, siehe CLAUDE.md "Dateiablage je Objekt"). Löst die bisherige freie Optionsgruppe
project_document_categories ab (galt für Kunden- UND Projektmappe, siehe app/option_settings.py)
-- exakt dieselbe Hochstufung SettingOptionGroup -> echte Tabelle wie bei RoofComponentType/
RoofLayerType (1.2.18/1.2.19), da eine reine Auswahlliste is_sensitive/is_field_visible nicht
tragen konnte.

Zwei unabhängige Schlösser gegen "sensible Kategorie für Monteure sichtbar":
1. is_sensitive/is_field_visible in DocumentCategory selbst -- create_category()/
   update_category() lehnen die Kombination is_sensitive=True + is_field_visible=True IMMER ab,
   und is_sensitive kann, sobald True, über update_category() nie wieder auf False gesetzt
   werden (kein Weg zurück, weder über die Oberfläche noch über die API).
2. HARD_LOCKED_CATEGORY_KEYS -- eine feste, im Code verankerte Sperrliste, unabhängig von
   jedem Datenbankinhalt geprüft. Selbst wenn jemand die document_categories-Tabelle direkt
   manipuliert (rohes SQL, ein Bug in einer künftigen Änderung), bleibt field_may_see_category()
   für diese beiden Kategorien hart auf False -- das zweite Schloss hat keinen gemeinsamen
   Schlüssel mit dem ersten."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import DocumentCategory

# Seit 1.3.62 (siehe Klassen-Docstring oben): Rechnungen/Belege und Verträge/Freigaben sind
# unabhängig von jeder Kategorie-Einstellung für Monteure gesperrt -- Betreibervorgabe, "zwei
# unabhängige Schlösser". Schlüssel sind bewusst die vollen Label-Texte (siehe DEFAULT_CATEGORIES
# unten, key==label bei der Erstbefüllung, Muster RoofComponentType), nicht ein separat
# gepflegter technischer Kurzname -- ein zweiter Name für dieselben zwei Kategorien wäre selbst
# eine Fehlerquelle (Tippfehler entkoppelt die Sperre lautlos von der echten Zeile).
HARD_LOCKED_CATEGORY_KEYS = frozenset({"Rechnungen / Belege", "Verträge / Freigaben"})

# (sort_order, key, label, is_sensitive, is_field_visible) -- Erstbefüllung, siehe CLAUDE.md für
# die Migrations-Begründung der einzelnen Werte. key==label, exakt das RoofComponentType-Muster,
# damit die BESTEHENDEN CustomerDocument.category/ProjectDocument.category-Freitexte (identische
# Werte aus der bisherigen Optionsgruppe project_document_categories) unverändert weiter matchen.
DEFAULT_CATEGORIES = [
    (10, "Pläne", "Pläne", False, True),
    (20, "Bilder / Fotos", "Bilder / Fotos", False, True),
    (30, "Lieferscheine", "Lieferscheine", False, True),
    (40, "Aufmaß", "Aufmaß", False, True),
    (50, "Schriftverkehr", "Schriftverkehr", False, False),
    (60, "Verträge / Freigaben", "Verträge / Freigaben", True, False),
    (70, "Rechnungen / Belege", "Rechnungen / Belege", True, False),
    (80, "Sonstiges", "Sonstiges", False, False),
]

FALLBACK_CATEGORY_KEY = "Sonstiges"


def category_to_dict(category: DocumentCategory) -> dict:
    return {
        "id": category.id, "key": category.key, "label": category.label,
        "is_sensitive": category.is_sensitive, "is_field_visible": category.is_field_visible,
        "sort_order": category.sort_order, "active": category.active,
    }


def list_categories(db: Session, include_inactive: bool = False) -> list[dict]:
    ensure_default_categories(db)
    query = select(DocumentCategory)
    if not include_inactive:
        query = query.where(DocumentCategory.active == True)  # noqa: E712 -- SQLAlchemy-Vergleich, kein Python-Bool-Vergleich
    query = query.order_by(DocumentCategory.sort_order, DocumentCategory.id)
    return [category_to_dict(c) for c in db.scalars(query).all()]


def _validate_combination(key: str, is_sensitive: bool, is_field_visible: bool) -> None:
    if is_sensitive and is_field_visible:
        raise ValueError("Eine sensible Kategorie kann nicht gleichzeitig für Monteure sichtbar sein.")
    if key in HARD_LOCKED_CATEGORY_KEYS:
        if is_field_visible:
            raise ValueError(f'"{key}" ist fest gesperrt und kann nicht für Monteure sichtbar gemacht werden.')
        if not is_sensitive:
            raise ValueError(f'"{key}" ist fest gesperrt und muss als sensibel markiert sein.')


def create_category(db: Session, key: str, label: str, *, is_sensitive: bool = False, is_field_visible: bool = False) -> dict:
    key = key.strip()
    if not key:
        raise ValueError("Bitte einen technischen Schlüssel angeben.")
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    _validate_combination(key, is_sensitive, is_field_visible)
    if db.scalar(select(DocumentCategory.id).where(DocumentCategory.key == key).limit(1)):
        raise ValueError(f'Die Kategorie "{key}" existiert bereits.')
    max_sort = db.scalar(select(DocumentCategory.sort_order).order_by(DocumentCategory.sort_order.desc()).limit(1)) or 0
    category = DocumentCategory(key=key, label=label, is_sensitive=is_sensitive, is_field_visible=is_field_visible, sort_order=max_sort + 10)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category_to_dict(category)


def update_category(db: Session, category_id: int, *, label: str, is_field_visible: bool, is_sensitive: bool | None = None) -> dict | None:
    """is_sensitive ist hier bewusst optional und nur in EINE Richtung wirksam: fehlt es (None),
    bleibt der bestehende Wert unverändert; wird es mitgeschickt, darf es den bestehenden Wert
    nur von False auf True heben, nie zurück (siehe Klassen-Docstring "einmal gesetzt,
    unveränderlich"). label/is_field_visible sind dagegen jederzeit frei änderbar, solange die
    Kombination mit is_sensitive nicht verboten ist."""
    category = db.get(DocumentCategory, category_id)
    if category is None:
        return None
    label = label.strip()
    if not label:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    effective_sensitive = category.is_sensitive
    if is_sensitive is not None:
        if category.is_sensitive and not is_sensitive:
            raise ValueError("Eine als sensibel markierte Kategorie kann nicht wieder als nicht-sensibel markiert werden.")
        effective_sensitive = is_sensitive
    _validate_combination(category.key, effective_sensitive, is_field_visible)
    category.label = label
    category.is_sensitive = effective_sensitive
    category.is_field_visible = is_field_visible
    db.commit()
    db.refresh(category)
    return category_to_dict(category)


def set_category_active(db: Session, category_id: int, active: bool) -> dict | None:
    category = db.get(DocumentCategory, category_id)
    if category is None:
        return None
    category.active = active
    db.commit()
    db.refresh(category)
    return category_to_dict(category)


def field_may_see_category(category: DocumentCategory) -> bool:
    """Die eine Stelle, die "darf ein Monteur Dokumente dieser Kategorie sehen" beantwortet --
    absichtlich robust gegen einen einzelnen falschen Datenbankwert: prüft die feste
    Code-Sperrliste UNABHÄNGIG von is_sensitive/is_field_visible, nicht nur zusätzlich zu ihnen.
    Wird von der künftigen Objekt-Dateiablage (nächste Runde) für jede einzelne Datei aufgerufen,
    nicht nur beim Anzeigen der Kategorieliste selbst."""
    if category.key in HARD_LOCKED_CATEGORY_KEYS:
        return False
    if category.is_sensitive:
        return False
    return bool(category.is_field_visible) and category.active


def ensure_default_categories(db: Session) -> None:
    """Selbst-Seeding wie bei den SettingOptionGroups/RoofComponentType -- greift nur, wenn die
    Tabelle noch komplett leer ist (z. B. eine per Base.metadata.create_all() erzeugte
    Testdatenbank ohne die eigentliche Migration). Rührt eine bereits gesäte Zeile nie wieder
    an, exakt das etablierte Muster dieses Projekts.

    Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding gegen
    gleichzeitigen Zugriff absichern"): der komplette Satz wird in einem SAVEPOINT eingefügt --
    kollidiert er mit der UNIQUE-Verletzung auf key (ein anderer Prozess war zwischen dem obigen
    SELECT und hier schneller), gilt das als "schon gesät", kein Fehler."""
    if db.scalar(select(DocumentCategory.id).limit(1)) is not None:
        return
    try:
        with db.begin_nested():
            for sort_order, key, label, is_sensitive, is_field_visible in DEFAULT_CATEGORIES:
                db.add(DocumentCategory(key=key, label=label, is_sensitive=is_sensitive, is_field_visible=is_field_visible, sort_order=sort_order))
            db.flush()
    except IntegrityError:
        return
    db.commit()


def resolve_category_id(db: Session, category_label: str | None) -> int:
    """Löst einen frei eingetippten/ausgewählten Kategorie-String (CustomerDocument.category/
    ProjectDocument.category, unverändert Freitext) auf die passende DocumentCategory auf --
    exakte Übereinstimmung, da key==label bei der Erstbefüllung (siehe DEFAULT_CATEGORIES).
    Kein Treffer (unbekannter/leerer String) fällt auf "Sonstiges" zurück, NIE auf eine
    sichtbare oder sensible Kategorie -- im Zweifel gesperrt, nie offen, siehe CLAUDE.md."""
    ensure_default_categories(db)
    label = (category_label or "").strip()
    if label:
        category_id = db.scalar(select(DocumentCategory.id).where(DocumentCategory.key == label))
        if category_id is not None:
            return category_id
    fallback_id = db.scalar(select(DocumentCategory.id).where(DocumentCategory.key == FALLBACK_CATEGORY_KEY))
    if fallback_id is None:
        raise RuntimeError('Fallback-Kategorie "Sonstiges" fehlt -- ensure_default_categories() nicht gelaufen?')
    return fallback_id
