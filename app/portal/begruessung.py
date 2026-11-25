"""Begrüßung auf „Willkommen“ (seit 1.11.3, Bauplan P1, Abschnitt 5 D) -- gesiezt, aus Anrede, Titel und Namen des Kunden der Sitzung.

Die Werte liefert portal_willkommen() (app/portal/funktionen.py) live aus dem Kundenstamm, nur für den Kunden der Sitzung; das Portal liest customers nicht
(Nachtrag N1). Regeln (Bauplan D (1)); seit 1.11.23 ohne Komma nach „Guten Tag“ (Betreibervorgabe 25.11.2026) -- die Mails setzen das Komma ans Ende
der Zeile (app/portal_mails.py::anrede()):

    Herr, Frau         „Guten Tag Herr Dr. Muster“ -- Anrede, Titel, Nachname
    Firma              „Guten Tag Muster Bedachung GmbH“ -- der Name ohne Anrede und Titel (eine Firma steht im Nachnamen)
    sonst              „Guten Tag Dr. Max Muster“ -- Titel, Vor- und Nachname (Divers und ohne Anrede; wie salutation_line() im ERP bei Divers)
    ohne jeden Namen   der zusammengesetzte Name (customers.name), sonst nur „Guten Tag“

Die Seite setzt den Text nur über textContent (Bauplan 3.5); Markup darin bleibt Text.
"""

from __future__ import annotations

GRUSS = "Guten Tag"


def _verbunden(*teile: str | None) -> str:
    return " ".join(t.strip() for t in teile if t and t.strip())


def begruessung(anrede: str | None, titel: str | None, vorname: str | None, nachname: str | None, name: str | None) -> str:
    art = (anrede or "").strip()
    if art in ("Herr", "Frau") and _verbunden(nachname):
        return f"{GRUSS} {art} {_verbunden(titel, nachname)}"
    voll = _verbunden(vorname, nachname) if art == "Firma" else _verbunden(titel, vorname, nachname)
    voll = voll or _verbunden(name)
    return f"{GRUSS} {voll}" if voll else GRUSS
