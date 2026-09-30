"""Geschäftslogik für das personalisierbare Start-Dashboard (seit 1.0.102).

Das Layout (welche Widgets sichtbar sind, in welcher Reihenfolge) wird pro
Benutzer in user_dashboard_widgets gespeichert. Die Widget-Inhalte selbst
kommen aus bestehenden, bereits vorhandenen Endpunkten (siehe dashboard.html)
-- hier geht es ausschließlich um das Layout, nicht um Aufgaben/Kennzahlen-Daten.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import UserDashboardWidget

# open_office_tasks ("Ohne Zuständigkeit") seit 1.8.18 Standard, vorher nur per "+ Widget".
DEFAULT_WIDGETS = [
    {"widget_key": "my_tasks", "sort_order": 10, "visible": True},
    {"widget_key": "open_office_tasks", "sort_order": 15, "visible": True},
    {"widget_key": "kpis", "sort_order": 20, "visible": True},
    {"widget_key": "active_projects", "sort_order": 30, "visible": True},
]


def get_widget_layout(db: Session, user_id: int) -> list[dict]:
    """Gespeichertes Dashboard-Layout eines Benutzers. Existieren noch keine
    Zeilen (erster Aufruf), wird der Standard synthetisiert, aber NICHT
    gespeichert -- erst eine bewusste Änderung (save_widget_layout) legt
    tatsächlich Zeilen an.

    Seit 1.8.18: fehlt einem gespeicherten Layout ein Standard-Widget ganz (keine
    Zeile, auch keine ausgeblendete), wird es angehängt, ebenfalls ohne zu speichern
    -- so erreicht ein neues Standard-Widget auch Benutzer, die ihr Layout schon
    einmal gespeichert haben. Entfernen speichert eine ausgeblendete Zeile
    (dashboard.html, removeWidget()) und bleibt deshalb wirksam."""
    rows = db.scalars(
        select(UserDashboardWidget)
        .where(UserDashboardWidget.user_id == user_id)
        .order_by(UserDashboardWidget.sort_order, UserDashboardWidget.id)
    ).all()
    if not rows:
        return [dict(w) for w in DEFAULT_WIDGETS]
    layout = [{"widget_key": r.widget_key, "sort_order": r.sort_order, "visible": r.visible} for r in rows]
    stored_keys = {r.widget_key for r in rows}
    layout += [dict(w) for w in DEFAULT_WIDGETS if w["widget_key"] not in stored_keys]
    return sorted(layout, key=lambda w: w["sort_order"])


def save_widget_layout(db: Session, user_id: int, widgets: list[dict]) -> list[dict]:
    """Ersetzt das komplette Layout eines Benutzers (Full-Replace-Muster,
    analog zu reorder_quote() in app/projects.py)."""
    for row in db.scalars(select(UserDashboardWidget).where(UserDashboardWidget.user_id == user_id)).all():
        db.delete(row)
    db.flush()
    for w in widgets:
        db.add(UserDashboardWidget(
            user_id=user_id,
            widget_key=w["widget_key"],
            sort_order=w.get("sort_order", 100),
            visible=w.get("visible", True),
        ))
    db.commit()
    return get_widget_layout(db, user_id)
