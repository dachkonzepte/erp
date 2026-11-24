"""Name, Anschrift und Pflichtangaben des Betriebs für Mails (seit 1.11.17; § 35a GmbHG) -- eine Quelle für die Mails des ERP und des Kundenportals.

- anschrift(): „Name · Straße · PLZ Ort“ ohne leere Teile (die Fußzeile der Portal-Mails, app/portal_mails.py, seit 1.11.8).
- pflichtangaben(): „Sitz <Ort> · <Registergericht> <Registernummer> · Geschäftsführer: <Name(n)>“ (seit 1.11.12); fehlt ein Feld, fällt nur dieses weg, fehlen
  alle, None. Sitz ist der Ort der Anschrift (ein eigenes Feld „Sitz“ gibt es nicht).
- text_fusszeile(): was dispatch_email() unter jede Mail an Kunden und Beteiligte setzt -- nach einer Leerzeile die Anschrift und die Pflichtangaben; ohne
  jede Angabe nichts. Die Aufgaben-Mails an Mitarbeiter bekommen sie nicht (app/email_dispatch.py::OHNE_FIRMENANGABEN).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .settings import load_general_settings


def _rein(wert: str | None) -> str:
    return " ".join((wert or "").split())


def anschrift(name: str | None, strasse: str | None, plz: str | None, ort: str | None) -> str:
    plz_ort = " ".join(t for t in (_rein(plz), _rein(ort)) if t)
    return " · ".join(t for t in (_rein(name), _rein(strasse), plz_ort) if t)


def pflichtangaben(ort: str | None, gericht: str | None, nummer: str | None, geschaeftsfuehrer: str | None) -> str | None:
    """Die Pflichtangaben nach § 35a GmbHG als eine Zeile. Fehlt ein Feld, fällt nur dieses weg (Gericht ohne Nummer und umgekehrt bleibt stehen); ohne jedes
    Feld None."""
    register = " ".join(t for t in (_rein(gericht), _rein(nummer)) if t)
    teile = (f"Sitz {_rein(ort)}" if _rein(ort) else "", register, f"Geschäftsführer: {_rein(geschaeftsfuehrer)}" if _rein(geschaeftsfuehrer) else "")
    return " · ".join(t for t in teile if t) or None


def zeilen(db: Session) -> list[str]:
    """Anschrift und Pflichtangaben aus den Firmendaten der Einstellungen, ohne leere Zeilen."""
    s = load_general_settings(db)
    return [z for z in (anschrift(s.company_name, s.street, s.postal_code, s.city),
                        pflichtangaben(s.city, s.register_court, s.register_number, s.managing_director)) if z]


def text_fusszeile(db: Session) -> str:
    """Der Schluss einer Mail an Kunden und Beteiligte: eine Leerzeile, dann Anschrift und Pflichtangaben -- ohne jede Angabe leer."""
    z = zeilen(db)
    return "\n\n" + "\n".join(z) if z else ""
