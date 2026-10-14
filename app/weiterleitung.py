"""Weiterleitungsziele aus einer Anfrage prüfen (seit 1.8.98).

Ein Ziel, das von außen kommt (`next` der Anmeldeseite und jeder andere Wert aus Query, Formular oder Kopfzeilen), führt nur auf
einen lokalen Pfad dieses Servers -- sonst auf die Startseite. Ohne diese Prüfung leitete `/login?next=//fremd.example` auf eine
fremde Seite weiter (offene Weiterleitung), und im Browser führte `next=javascript:…` ein Skript im ERP aus.

Dieselbe Regel steht für den Browser in `app/templates/_weiterleitung.html` (`sicheresZiel()`); `tests/test_v401_weiterleitung.py`
prüft beide an derselben Tabelle von Angriffen. Jede Weiterleitung des Servers (`RedirectResponse`) nimmt ein festes Ziel oder geht
über `sicheres_ziel()` -- der Strukturtest dort prüft das per AST.

Lokal heißt:
- beginnt mit genau einem "/" (nicht "//", nicht "/\\"),
- nur druckbare ASCII-Zeichen ohne Leerzeichen und ohne Rückstrich (Browser entfernen Tab und Zeilenumbruch und lesen "\\" wie
  "/" -- "/\\t/fremd" wäre sonst "//fremd"),
- jedes "%" mit zwei Hex-Ziffern; auch dekodiert (wiederholt, höchstens fünfmal) kein Steuerzeichen, kein Rückstrich und kein "//"
  am Anfang (kodierte Varianten wie "/%2F/fremd", "/%5Cfremd", "/%09/fremd"),
- weder Schema noch Host (urllib.parse.urlsplit)."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

STARTSEITE = "/"
MAX_LAENGE = 2000

_ROH = re.compile(r"/(?![/\\])[\x21-\x7e]*\Z")
_PROZENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_DEKODIERT_VERBOTEN = re.compile(r"[\x00-\x20\x7f\\]")


def ist_lokal(wert: object) -> bool:
    """Ob wert ein lokaler Pfad dieses Servers ist (Regeln oben)."""
    if not isinstance(wert, str) or not wert or len(wert) > MAX_LAENGE:
        return False
    if not _ROH.match(wert) or "\\" in wert:
        return False
    teile = urlsplit(wert)
    if teile.scheme or teile.netloc:
        return False
    s = wert
    for _ in range(5):
        if _PROZENT.search(s):
            return False  # "%" ohne zwei Hex-Ziffern (im Browser wirft decodeURIComponent)
        try:
            d = unquote(s, errors="strict")
        except UnicodeDecodeError:
            return False
        if d == s:
            return True
        if _DEKODIERT_VERBOTEN.search(d) or d.startswith("//"):
            return False
        s = d
    return False  # nach fünfmal Dekodieren noch immer kodiert: kein echter Pfad


def sicheres_ziel(wert: object, startseite: str = STARTSEITE) -> str:
    """wert, wenn es ein lokaler Pfad ist, sonst startseite (ein festes Ziel des Aufrufers)."""
    return wert if ist_lokal(wert) else startseite
