"""Ein ERP-Konto löschen (seit 1.9.340, Runde V1, Punkt 3 -- „Benutzer löschen“ aus dem Befund SQLite/PostgreSQL).

Bis 1.9.339 löschte DELETE /api/users/{id} das Konto einfach. Steht es irgendwo als Urheber (Aufgabe angelegt, Antrag entschieden, Zeit gebucht …),
lehnte PostgreSQL das mit einem Fremdschlüssel ab, und die Seite zeigte 500 (bekannt seit 1.8.13). Seitdem:

- Was zum Konto selbst gehört, geht mit ihm (MIT_DEM_KONTO): Sitzungen, vertraute Geräte, Wiederherstellungscodes (ORM-Kaskade am Konto) und die
  Kacheln der Startseite (hier gelöscht).
- Steht das Konto anderswo (BEREICHE), wird nicht gelöscht: 409 mit den Bereichen und dem Rat, das Konto zu deaktivieren.

Jeder Fremdschlüssel auf app_users steht in genau einer der beiden Listen (Wächter tests/test_v740_e1_bis_e5_und_konto.py); ein neuer kommt dort hinein.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import Base
from .models import AppUser, UserDashboardWidget

# Tabelle -> wie sie mit dem Konto geht
MIT_DEM_KONTO = {
    "user_sessions": "Kaskade (AppUser.sessions, ON DELETE CASCADE)",
    "trusted_devices": "Kaskade (AppUser.trusted_devices)",
    "two_factor_recovery_codes": "Kaskade (AppUser.recovery_codes)",
    "user_dashboard_widgets": "hier gelöscht (Kacheln der Startseite)",
}

# (Tabelle, Spalte) -> Bereich in der Meldung
BEREICHE = {
    ("tasks", "created_by_user_id"): "Aufgaben",
    ("checklists", "created_by_user_id"): "Checklisten",
    ("checklist_attachments", "discarded_by_user_id"): "verworfene Unterschriften in Checklisten",
    ("checklist_asset_releases", "released_by_user_id"): "Freigaben von Betriebsmitteln",
    ("checklist_template_versions", "published_by_user_id"): "veröffentlichte Checklisten-Vorlagen",
    ("employee_absence_requests", "requested_by_user_id"): "Abwesenheitsanträge",
    ("employee_absence_requests", "reviewed_by_user_id"): "entschiedene Abwesenheitsanträge",
    ("time_entries", "created_by_user_id"): "Zeitbuchungen",
    ("time_entry_groups", "created_by_user_id"): "Zeitbuchungen der Kolonne",
    ("time_tracking_settings", "locked_by_user_id"): "Abschluss der Zeiterfassung",
    ("calendar_events", "owner_user_id"): "Kalendertermine",
    ("outlook_series_occurrences", "owner_user_id"): "Kalendertermine",
}


def fremdschluessel_auf_konten() -> list[tuple[str, str]]:
    """Jede Spalte mit Fremdschlüssel auf app_users.id als (Tabelle, Spalte)."""
    return sorted((t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns
                  for fk in c.foreign_keys if fk.column.table.name == "app_users")


def verwendungen(db: Session, user_id: int) -> list[str]:
    """Die Bereiche, in denen das Konto steht (ohne MIT_DEM_KONTO), in fester Reihenfolge, ohne Doppelte."""
    bereiche: list[str] = []
    for (tabelle, spalte), bereich in BEREICHE.items():
        t = Base.metadata.tables[tabelle]
        if db.scalar(select(func.count()).select_from(t).where(t.c[spalte] == user_id)) and bereich not in bereiche:
            bereiche.append(bereich)
    return bereiche


class KontoVerwendet(ValueError):
    """Das Konto steht noch irgendwo -- nicht löschen, deaktivieren."""


def konto_loeschen(db: Session, user: AppUser) -> None:
    """Löscht das Konto mit allem, was zu ihm gehört; steht es anderswo, KontoVerwendet (nichts geändert). Committet."""
    bereiche = verwendungen(db, user.id)
    if bereiche:
        raise KontoVerwendet(
            f"Das Konto wurde schon verwendet ({', '.join(bereiche)}) und lässt sich deshalb nicht löschen. "
            "Deaktiviere es stattdessen – dann kann es sich nicht mehr anmelden, und alles, was es angelegt hat, bleibt."
        )
    db.execute(delete(UserDashboardWidget).where(UserDashboardWidget.user_id == user.id))
    db.delete(user)
    db.commit()
