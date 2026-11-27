"""Die Seiten des Kundenportals (seit 1.11.14, Stufe P1e; Bauplan P1, Abschnitt 5; Entwürfe bildgrundlage/entwurf-p1/Portal-Anmelden, -Willkommen,
-Handy, freigegeben vom Betrieb).

Eine Seite für alles (/): A „Link prüfen“, B „Code senden“, C „Code eingeben“, D „Willkommen“, E „Fehlerseite“ -- das Skript des Portals
(seiten/portal.js) zeigt je Zustand einen Abschnitt und füllt nur Text (textContent, nie innerHTML; die Seite verlangt Trusted Types). Der Server
setzt nur, was ohne Sitzung öffentlich ist: Name des Betriebs, Kontakt (Firmendaten, P1-14), Impressum und Datenschutz (Links auf die Webseite wie
in den Mails), das Jahr -- jeder Wert über Jinja mit autoescape. Was je Kunde gilt (Begrüßung, verdeckte Adresse), kommt nur aus den Wegen mit
Sitzung bzw. Vorstufe (routen.py).

- Kein Inline-Skript, kein style-Attribut (CSP: script-src und style-src 'self'); Stil aus dem Design-System (/static/ds/ds.css: Tokens hell und
  dunkel, Schriften) und seiten/portal.css; hell oder dunkel nach dem Gerät (prefers-color-scheme, das Skript setzt data-theme wie im ERP).
- Skript und Stil des Portals unter /s/portal.js und /s/portal.css, im Link mit ?v=<Prüfsumme des Inhalts> -- sie dürfen ein Jahr im Speicher des
  Browsers bleiben; eine geänderte Datei hat eine neue Adresse. Die Seite selbst nie (no-store).
- Ohne JavaScript zeigt <noscript> die Fehlerseite „JavaScript ist ausgeschaltet“ samt Kontakt.
- Eine Adresse, die es nicht gibt (GET/HEAD außerhalb von /api/), beantwortet die Fehlerseite „Diese Seite gibt es nicht“ mit 404; liest die Seite
  die Firmendaten nicht, „Gerade klappt etwas nicht“ mit 500 (data-fall am <body>, FAELLE).

Das Paket importiert aus dem ERP nur app.portal, app.berlin_time und app.design_dateien (tests/test_v799_portal_rechte.py) -- deshalb steht die Prüfung
der Webseite hier noch einmal (wie app/portal_mails.py::webseite_host(); ein Test hält beide gleich).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.berlin_time import berlin_today
from app.design_dateien import pruefsumme

ORDNER = Path(__file__).resolve().parent / "seiten"
SEITE = "portal.html"
DATEIEN = {"portal.js": "text/javascript; charset=utf-8", "portal.css": "text/css; charset=utf-8"}
DAUERHAFT = "public, max-age=31536000, immutable"
FAELLE = ("nicht_gefunden", "technisch")  # was der Server selbst als Fehlerseite setzt; alle übrigen Fälle wählt das Skript
PORTAL = "Kundenportal"

_HOST = re.compile(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}")


def webseite_host(webseite: str | None) -> str | None:
    """Der Host der Webseite aus den Firmendaten („www.beispiel.de“, auch mit https:// oder / am Ende eingetragen); nichts Gültiges -> None."""
    text = (webseite or "").strip()
    for vorne in ("https://", "http://"):
        if text.lower().startswith(vorne):
            text = text[len(vorne):]
    text = text.rstrip("/")
    return text if _HOST.fullmatch(text) else None


def tel_link(telefon: str | None) -> str | None:
    """Die Nummer als tel:-Ziel in internationaler Form („02451 9433606“ -> „+4924519433606“): führende 0 -> +49, 00 -> +, + bleibt; nur Ziffern
    danach. Ohne erkennbare Vorwahl (weder 0 noch +) oder mit weniger als 6 Ziffern kein Ziel -- die Nummer steht dann nur als Text."""
    text = (telefon or "").strip()
    ziffern = re.sub(r"[^0-9]", "", text)
    if len(ziffern) < 6:
        return None
    if text.startswith("+"):
        return "+" + ziffern
    if ziffern.startswith("00"):
        return "+" + ziffern[2:]
    if ziffern.startswith("0"):
        return "+49" + ziffern[1:]
    return None


@dataclass(frozen=True)
class Firma:
    name: str                 # „DACHKONZEPTE Rödchen GmbH“ (leer: nur „Kundenportal“)
    marke: str                # erste Zeile der Wortmarke (erstes Wort)
    rest: str                 # der Rest des Namens („Rödchen GmbH“), leer bei einem Wort
    strasse: str | None
    ort: str | None           # „PLZ Ort“
    telefon: str | None
    tel: str | None           # tel_link()
    email: str | None         # nur eine gültige Adresse (sonst kein mailto:)
    webseite: str | None      # Host
    impressum: str | None
    datenschutz: str | None

    @property
    def hat_kontakt(self) -> bool:
        return bool(self.telefon or self.email)


def firma(kontakt: dict | None) -> Firma:
    """Die öffentlichen Firmendaten (app/portal/datenbank.py::kontakt(), die Spalten aus rechte.LESEN) für Kopf, Kontakt und Fuß."""
    k = kontakt or {}

    def wert(name: str) -> str | None:
        return " ".join(str(k.get(name) or "").split()) or None

    name = wert("company_name") or ""
    marke, _, rest = name.partition(" ")
    ort = " ".join(t for t in (wert("postal_code"), wert("city")) if t) or None
    email = wert("email")
    host = webseite_host(k.get("website"))
    telefon = wert("phone")
    return Firma(name=name, marke=marke, rest=rest.strip(), strasse=wert("street"), ort=ort, telefon=telefon, tel=tel_link(telefon),
                 email=email if email and _EMAIL.fullmatch(email) else None, webseite=host,
                 impressum=f"https://{host}/impressum" if host else None, datenschutz=f"https://{host}/datenschutz" if host else None)


class Seiten:
    """Hält Vorlage, Skript und Stil (beim Start gelesen) und baut die Seite je Anfrage aus den Firmendaten."""

    def __init__(self, ordner: Path = ORDNER):
        self._env = Environment(loader=FileSystemLoader(str(ordner)), autoescape=True, trim_blocks=True, lstrip_blocks=True)
        self._vorlage = self._env.get_template(SEITE)
        self._dateien = {name: (ordner / name).read_bytes() for name in DATEIEN}
        self.version = {name: hashlib.sha256(inhalt).hexdigest()[:10] for name, inhalt in self._dateien.items()}
        self.version["ds.css"] = pruefsumme("ds.css")

    @staticmethod
    def pflicht_da(kontakt: dict | None) -> bool:
        """Seit 1.11.47: Impressum und Datenschutz lassen sich verlinken (gültige Webseite in den Firmendaten) -- sonst zeigt das Portal statt jeder Seite
        die Fehlerseite „technisch“ (routen.seite_antwort(); Entscheidung des Betriebs 27.11.2026: beide sind Pflicht). Bis 1.11.46 fehlten sie dann still."""
        f = firma(kontakt)
        return bool(f.impressum and f.datenschutz)

    def seite(self, kontakt: dict | None, fall: str = "") -> str:
        if fall and fall not in FAELLE:
            raise ValueError("unbekannter Fall der Fehlerseite")
        f = firma(kontakt)
        return self._vorlage.render(firma=f, portal=PORTAL, fall=fall, jahr=berlin_today().year, v=self.version)

    def datei(self, name: str) -> bytes:
        return self._dateien[name]
