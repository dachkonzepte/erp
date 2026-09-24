"""Ein-/Ausschalter für optionale ERP-Module, pro Installation (seit 1.0.103).

OPTIONAL_MODULES ist die eine Stelle, an der sich ein künftiges Modul einträgt --
alles, was hier nicht auftaucht (die Kern-ERP-Kette: Kunde/Projekt/Angebot/Auftrag/
Rechnung/Mahnung, Zeiterfassung, Planung), bleibt immer aktiv und ist nicht abschaltbar.

Live aus der Datenbank gelesen (analog zu get_theme()/accent_color), kein Neustart
nötig, wenn ein Admin ein Modul umschaltet.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EnabledModule

OPTIONAL_MODULES = {
    "aufgabenmanagement": "Aufgabenmanagement",
    "wartungen": "Wartungen & Reparaturen",
    "betriebsmittel": "Betriebsmittelverwaltung",
    "betriebskosten": "Betriebskosten-Übersicht",
    "buchhaltung": "Buchhaltung (Eingangsrechnungen)",
    "kalender": "Kalender (Büro-Termine)",
}


def is_module_enabled(db: Session, module_key: str) -> bool:
    """Fehlt eine Zeile für module_key, gilt das Modul als aktiv (Opt-out statt
    Opt-in) -- ein neuer Registry-Eintrag ändert dadurch nie stillschweigend etwas an
    einer bestehenden Installation, bis ein Admin ihn bewusst abschaltet."""
    row = db.scalar(select(EnabledModule).where(EnabledModule.module_key == module_key))
    return row.enabled if row is not None else True


def list_module_states(db: Session) -> list[dict]:
    return [
        {"module_key": key, "label": label, "enabled": is_module_enabled(db, key)}
        for key, label in OPTIONAL_MODULES.items()
    ]


def set_module_enabled(db: Session, module_key: str, enabled: bool) -> dict:
    if module_key not in OPTIONAL_MODULES:
        raise ValueError(f"Unbekanntes Modul: {module_key}")
    row = db.scalar(select(EnabledModule).where(EnabledModule.module_key == module_key))
    if row is None:
        row = EnabledModule(module_key=module_key, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    return {"module_key": module_key, "label": OPTIONAL_MODULES[module_key], "enabled": row.enabled}
