"""Design-Dateien unter /static/ (seit 1.8.127, Stufe 1 des Redesigns): app/static/ ohne Anmeldung, nur GET und HEAD.

Ausgeliefert wird nur, was in app/static/ liegt -- das Design-System (ds/ds.css), seine Schriften (woff2) und deren Lizenztexte;
tests/test_v432_design_fundament.py lässt dort nichts anderes zu. Kein Verzeichnislisting (ein Verzeichnis ergibt 404), keine Symlinks
(auch keine, die innerhalb des Ordners bleiben), der Typ fest nach Endung (TYPEN), nie geraten, immer mit nosniff.

Ohne Anmeldung und ohne Datenbank geht eine Anfrage nur durch die Anmeldeschranke (app/anmeldeschranke.py), wenn ist_design_pfad()
sie annimmt -- eng gefasst: GET oder HEAD, Pfad /static/ und danach Abschnitte aus Kleinbuchstaben, Ziffern, Punkt, Bindestrich und
Unterstrich (Anfang und Ende ein Buchstabe oder eine Ziffer, kein ".."), und der Pfad kam ohne Prozent-Kodierung an. Alles andere --
/staticx, /static, /static/, ein Verzeichnis-Abschnitt "..", %2e, %2f, doppelt Kodiertes, Rückstrich, // -- geht durch die Schranke
wie jede andere Adresse (Anmeldung, Cache-Verbot). Ein reiner Präfixvergleich (path.startswith("/static")) ließe /staticx an der
Anmeldung vorbei; die Angriffstests prüfen das.

Eine Antwort 200 auf eine solche Anfrage trägt "Cache-Control: public, max-age=31536000, immutable" -- die einzige Ausnahme vom
Cache-Verbot der Regel 30; jede andere Antwort dort "no-store". Eine geänderte Datei braucht deshalb eine neue Adresse: ds.css und
ds-basis.css kommen seit 1.8.173 über ?v=<Prüfsumme ihres Inhalts> (pruefsumme(), _ds_kopf.html; bis dahin ?v=<Version> -- ein Commit,
der eine Datei ohne neue Version änderte, hätte sie ein Jahr lang alt gelassen), eine geänderte Schrift bekommt einen neuen Dateinamen."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

STATIC_DIR = Path(__file__).resolve().parent / "static"
DS_DIR = STATIC_DIR / "ds"
PRAEFIX = "/static"
DAUERHAFT = "public, max-age=31536000, immutable"
# Fest nach Endung -- in app/static/ liegen nur diese (Wächter in tests/test_v432_design_fundament.py)
TYPEN = {".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}

_ABSCHNITT = r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?"
_PFAD = re.compile(rf"/static(?:/{_ABSCHNITT})+")


def pruefsumme(name: str, ordner: Path = DS_DIR) -> str:
    """Die ersten 10 Zeichen der SHA-256 des Inhalts von <ordner>/<name> (seit 1.8.173): der Zusatz ?v= an ds.css und ds-basis.css in
    _ds_kopf.html -- ändert sich der Inhalt, ändert sich die Adresse, auch ohne neue Version. Beim Start gebildet (app/routers/pages.py),
    die Dateien ändern sich nur mit einem Deploy, und update.sh startet den Dienst neu."""
    return hashlib.sha256((ordner / name).read_bytes()).hexdigest()[:10]


def ist_design_pfad(scope) -> bool:
    """Ob die Anfrage eine Design-Datei ohne Anmeldung holen darf (siehe Modulkopf). scope ist der ASGI-Scope: path ist dekodiert,
    raw_path (falls vorhanden) die Bytes, wie sie kamen -- weichen sie ab, war etwas kodiert, und die Anfrage geht durch die Schranke."""
    if scope.get("type") != "http" or scope.get("method") not in ("GET", "HEAD"):
        return False
    pfad = scope.get("path") or ""
    if not _PFAD.fullmatch(pfad) or ".." in pfad:
        return False
    roh = scope.get("raw_path")
    if roh is not None and roh.split(b"?", 1)[0] != pfad.encode("ascii"):
        return False
    return True


class DesignDateien(StaticFiles):
    """StaticFiles für app/static/: html=False (kein Listing, keine index.html), keine Symlinks, Typ fest nach Endung, nosniff."""

    def __init__(self, directory: Path | str = STATIC_DIR):
        self._wurzel = os.path.realpath(directory)
        super().__init__(directory=str(directory), html=False, follow_symlink=False)

    def lookup_path(self, path: str):
        full_path, stat_result = super().lookup_path(path)
        if not full_path:
            return full_path, stat_result
        # StaticFiles löst Symlinks auf (realpath) und weist nur solche ab, die aus dem Ordner führen -- hier jeder: weicht der
        # aufgelöste Pfad vom zusammengesetzten ab, lag ein Symlink (unter Windows auch eine Verzeichnisverbindung) auf dem Weg.
        zusammengesetzt = os.path.normpath(os.path.join(self._wurzel, path))
        if os.path.normcase(full_path) != os.path.normcase(zusammengesetzt):
            return "", None
        return full_path, stat_result

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        typ = TYPEN.get(Path(full_path).suffix.lower())
        if typ is None:
            raise HTTPException(status_code=404)
        antwort = super().file_response(full_path, stat_result, scope, status_code)
        if antwort.status_code != 304:
            antwort.headers["content-type"] = typ
        antwort.headers["X-Content-Type-Options"] = "nosniff"
        return antwort


def einbinden(app, directory: Path | str = STATIC_DIR) -> None:
    """/static an app -- app/main.py und tests/anmeldung.py binden über diese eine Funktion ein."""
    app.mount(PRAEFIX, DesignDateien(directory), name="static")
