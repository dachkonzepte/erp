"""Abgelegte Dateien ausliefern (seit 1.8.101, Befund 1.8.100 Nr. 4).

Jede Datei, die jemand hochgeladen hat (Kundenakte, Projektmappe, Objekt, Skizze, Foto, Beleg, Vollmacht, Logo, Hintergrund …), geht
über `datei_antwort()` an den Browser -- nie direkt über `FileResponse` oder `Response(media_type=<gespeicherter Typ>)`. Bis 1.8.100
gingen Dokumente inline mit dem Typ hinaus, den der Browser beim Hochladen nannte: eine SVG- oder HTML-Datei mit Skript lief beim Öffnen
auf dem Ursprung des ERP, mit der Sitzung der Person, die öffnet.

Regeln:
- **Den Typ bestimmt der Server, am Inhalt** (`typ_aus_inhalt()`: die ersten Bytes), nie am Dateinamen oder an der Angabe des Browsers --
  auch für alte Einträge, deren gespeicherter Typ noch vom Browser stammt.
- **Im Browser angezeigt (inline) werden nur Rasterbilder (JPEG, PNG, GIF, WebP) und PDF**, mit genau diesem Typ. Alles andere kommt als
  Download: `application/octet-stream`, `Content-Disposition: attachment`, dazu `Content-Security-Policy: sandbox` (würde ein Browser es
  doch zeigen, dann ohne Skript und ohne den Ursprung des ERP).
- **Immer `X-Content-Type-Options: nosniff`**: der Browser rät keinen anderen Typ.
- **SVG nur als Bild** (`svg_als_bild=True`, nur das Logo der Seitenleiste): Typ `image/svg+xml`, aber `attachment` und eine CSP ohne
  Skript -- in `<img>` erscheint es (dort läuft nie ein Skript), direkt geöffnet kommt es als Download.

Was der Server selbst erzeugt (PDF einer Rechnung, PNG eines QR-Codes, CSV) hat einen festen Typ und braucht diese Funktion nicht.
`tests/test_v406_dateien_nie_aktiv.py` prüft per AST, dass `FileResponse` nur hier vorkommt und jede andere Antwort mit Inhalt einen
festen Typ trägt."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import FileResponse, Response

RASTERBILDER = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
ANZEIGBAR = RASTERBILDER | {"application/pdf"}
UNBEKANNT = "application/octet-stream"
KOPF_BYTES = 4096  # reicht für die Signaturen und für den Anfang eines SVG mit XML-Kopf und Kommentar

_SVG = re.compile(rb"\A(?:\xef\xbb\xbf)?\s*(?:<\?xml[^>]*>\s*)?(?:(?:<!--.*?-->|<!doctype[^>]*>)\s*)*<svg[\s>]", re.I | re.S)


def typ_aus_inhalt(daten: bytes) -> str | None:
    """Der Typ einer Datei an ihren ersten Bytes -- einer aus ANZEIGBAR, sonst None (auch SVG, HTML, XML, Text, Office)."""
    if daten.startswith(b"%PDF-"):
        return "application/pdf"
    if daten.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if daten.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if daten[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
        return "image/webp"
    return None


def gespeicherter_typ(daten: bytes) -> str:
    """Der Typ, den eine neue Ablage speichert (Liste, Vorschau): vom Server am Inhalt bestimmt, sonst `application/octet-stream`."""
    return typ_aus_inhalt(daten) or UNBEKANNT


def ist_rasterbild(typ: str | None) -> bool:
    return (typ or "").lower() in RASTERBILDER


def anzeigbar(typ: str | None) -> bool:
    """Ob der Browser eine Datei dieses Typs zeigen darf ("Öffnen", Vorschau) -- nur Rasterbilder und PDF."""
    return (typ or "").lower() in ANZEIGBAR


def _disposition(art: str, dateiname: str | None) -> str:
    if not dateiname:
        return art
    name = dateiname.replace("\r", " ").replace("\n", " ")
    kodiert = quote(name, safe="")
    if kodiert != name:
        return f"{art}; filename*=utf-8''{kodiert}"
    return f'{art}; filename="{name}"'


def _kopf(quelle: Path | bytes) -> bytes:
    if isinstance(quelle, bytes):
        return quelle[:KOPF_BYTES]
    with open(quelle, "rb") as datei:
        return datei.read(KOPF_BYTES)


def datei_antwort(quelle: Path | bytes, dateiname: str | None = None, *, herunterladen: bool = False, svg_als_bild: bool = False,
                  kopfzeilen: dict[str, str] | None = None) -> Response:
    """Die Antwort für eine abgelegte Datei (Pfad oder Inhalt) nach den Regeln oben. herunterladen=True: immer `attachment` (der Typ
    bleibt der erkannte, sonst `application/octet-stream`). kopfzeilen: weitere Kopfzeilen (z. B. Cache), nie Typ, Disposition, nosniff
    oder CSP."""
    kopf = _kopf(quelle)
    typ = typ_aus_inhalt(kopf)
    sicher = {"X-Content-Type-Options": "nosniff"}
    if typ is not None:
        sicher["Content-Disposition"] = _disposition("attachment" if herunterladen else "inline", dateiname)
    elif svg_als_bild and _SVG.match(kopf):
        typ = "image/svg+xml"
        sicher["Content-Disposition"] = _disposition("attachment", dateiname)
        sicher["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    else:
        typ = UNBEKANNT
        sicher["Content-Disposition"] = _disposition("attachment", dateiname)
        sicher["Content-Security-Policy"] = "sandbox"
    weitere = {k: v for k, v in (kopfzeilen or {}).items()
               if k.lower() not in ("content-type", "content-disposition", "x-content-type-options", "content-security-policy")}
    headers = {**weitere, **sicher}
    if isinstance(quelle, bytes):
        return Response(content=quelle, media_type=typ, headers=headers)
    return FileResponse(quelle, media_type=typ, headers=headers)
