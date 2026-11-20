"""Kontaktvermerke (seit 1.10.10, Stufe W1c; docs/archiv/webseite-und-kundenportal.md, „Umsetzung 1.10.10“).

„Kontakt vermerken“ an einer Anfrage, einem Projekt oder einem Kunden: nur der Tag und der Weg (Telefon, E-Mail, Brief, Gespräch, Sonstiges) -- nie ein
Inhalt, es gibt kein Feld dafür. Ein Vermerk zählt für die Aufbewahrung wie ein sicherer Kontakt (6 Monate ab dem letzten Kontakt bis zum Archiv, ab 1.10.11
in app/aufbewahrung.py). Er bleibt, wie er ist: kein Ändern, kein Löschen -- er geht nur mit seinem Projekt (app/projects.py::delete_project()).
Rollen sitzen im Router (app/routers/kontaktvermerke.py); hier keine.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .berlin_time import berlin_today, utc_jetzt
from .models import AppUser, Customer, Inquiry, Kontaktvermerk, Project

WEGE = {"telefon": "Telefon", "email": "E-Mail", "brief": "Brief", "gespraech": "Gespräch", "sonstiges": "Sonstiges"}
FRUEHESTENS = date(2000, 1, 1)
# Bezug -> (Modell, Spalte am Vermerk, Name für Meldungen)
BEZUEGE = {"anfrage": (Inquiry, "inquiry_id", "Anfrage"), "projekt": (Project, "project_id", "Projekt"), "kunde": (Customer, "customer_id", "Kunde")}


class BezugFehlt(LookupError):
    """Anfrage, Projekt oder Kunde gibt es nicht (404)."""


class ImArchiv(ValueError):
    """Seit 1.10.11: der Bezug ist im Archiv -- erst zurückholen (409)."""


def tag_pruefen(kontakt_am: date) -> date:
    """Nicht in der Zukunft (Berlin), nicht vor dem 01.01.2000 -- sonst ValueError (422 im Eingabeschema)."""
    if kontakt_am > berlin_today():
        raise ValueError("Der Kontakt darf nicht in der Zukunft liegen")  # ohne Punkt: fehlerText() setzt ihn
    if kontakt_am < FRUEHESTENS:
        raise ValueError("Der Kontakt darf nicht vor dem 01.01.2000 liegen")
    return kontakt_am


def _bezug_pruefen(db: Session, bezug: str, bezug_id: int) -> str:
    modell, spalte, name = BEZUEGE[bezug]
    if db.get(modell, bezug_id) is None:
        raise BezugFehlt(f"{name} nicht gefunden.")
    return spalte


def vermerke(db: Session, bezug: str, bezug_id: int) -> list[dict]:
    """Alle Vermerke des Bezugs, der jüngste Kontakt zuerst (bei gleichem Tag der zuletzt vermerkte)."""
    spalte = _bezug_pruefen(db, bezug, bezug_id)
    zeilen = db.scalars(select(Kontaktvermerk).where(getattr(Kontaktvermerk, spalte) == bezug_id)
                        .order_by(Kontaktvermerk.kontakt_am.desc(), Kontaktvermerk.id.desc())).all()
    konten = {u.id: u for u in db.scalars(select(AppUser).where(AppUser.id.in_({z.created_by_user_id for z in zeilen if z.created_by_user_id}))
                                          .order_by(AppUser.id))}
    return [als_dict(z, konten.get(z.created_by_user_id)) for z in zeilen]


def als_dict(v: Kontaktvermerk, konto: AppUser | None) -> dict:
    return {"id": v.id, "kontakt_am": v.kontakt_am, "weg": v.weg, "weg_text": WEGE.get(v.weg, v.weg), "created_at": v.created_at,
            "von": (konto.display_name or konto.username) if konto else None}


def vermerken(db: Session, bezug: str, bezug_id: int, kontakt_am: date, weg: str, user_id: int | None) -> list[dict]:
    """Legt einen Vermerk an (Tag geprüft, Weg aus WEGE) und gibt alle Vermerke des Bezugs zurück."""
    spalte = _bezug_pruefen(db, bezug, bezug_id)
    from .aufbewahrung import im_archiv
    if im_archiv(db, bezug, bezug_id):
        raise ImArchiv(f"{BEZUEGE[bezug][2]} ist im Archiv – erst zurückholen, dann den Kontakt vermerken.")
    if weg not in WEGE:
        raise ValueError(weg)
    tag_pruefen(kontakt_am)
    db.add(Kontaktvermerk(**{spalte: bezug_id}, kontakt_am=kontakt_am, weg=weg, created_at=utc_jetzt(), created_by_user_id=user_id))
    db.commit()
    return vermerke(db, bezug, bezug_id)
