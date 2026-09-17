"""QR-Code-Erzeugung, geteilt zwischen Zwei-Faktor-Setup (app/two_factor.py) und der
Betriebsmittelverwaltung (Stufe 2, siehe CLAUDE.md). Nutzt dieselbe, bereits als
Projektabhängigkeit vorhandene qrcode[pil]-Bibliothek (BSD-3-Clause, siehe requirements.txt) --
keine neue Abhängigkeit. Bewusst ein eigenes, dokumenttyp-loses Modul statt einer Erweiterung
von app/two_factor.py: dessen private _qr_code_data_uri() bleibt unverändert (kein Anfassen
eines sicherheitskritischen Moduls für einen zweiten, fachlich unabhängigen Anwendungsfall)."""

from io import BytesIO

import qrcode


def qr_code_png_bytes(data: str) -> bytes:
    """Erzeugt für einen beliebigen Textinhalt (hier: eine vollständige URL) einen QR-Code als
    rohe PNG-Bytes -- library-Vorgaben (Fehlerkorrektur/Boxgröße/Rand), keine eigene
    Anpassung nötig."""
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
