"""Einstellungen für die Monteursansicht (seit 1.3.0, /mobil -- bis 1.3.60 /vor-ort) -- bisher nur
die Feierabend-Uhrzeit, ab der die Fahrzeug-Tablet-Anmeldung als beendet gilt. Muster wie
load_maintenance_settings() in app/maintenance_contracts.py."""

from datetime import datetime, time as dt_time

from sqlalchemy.orm import Session

from .grunddaten import einzelzeile
from .berlin_time import berlin_now
from .models import MobileSettings


def load_mobile_settings(db: Session) -> MobileSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, MobileSettings)


def mobile_settings_to_dict(settings: MobileSettings) -> dict:
    return {"shift_end_time": settings.shift_end_time.strftime("%H:%M")}


def update_mobile_settings(db: Session, shift_end_time: dt_time) -> dict:
    settings = load_mobile_settings(db)
    settings.shift_end_time = shift_end_time
    db.commit()
    db.refresh(settings)
    return mobile_settings_to_dict(settings)


def is_past_shift_end(settings: MobileSettings, now: datetime | None = None) -> bool:
    """Geprüft nur an den beiden mobilen Einstiegspunkten (GET /mobil, GET
    /api/field-view/today -- /mobil hieß bis 1.3.60 /vor-ort), NICHT in der globalen Middleware --
    siehe MobileSettings-Docstring in app/models.py."""
    now = now or berlin_now()
    return now.time() >= settings.shift_end_time
