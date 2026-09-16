"""Web-App-Manifest und PWA-Icons für die Monteursansicht (seit 1.3.0, /mobil -- bis 1.3.60
/vor-ort, siehe CLAUDE.md "Monteursansicht: Umbenennung zu /mobil"). Reine
Laufzeit-Erzeugung ohne Caching -- Icons werden selten angefragt (nur beim "Zum Startbildschirm
hinzufügen"), Einfachheit vor Optimierung, kein Cache-Invalidierungsproblem bei einem späteren
Logo-Wechsel. Kein StaticFiles-Mount (im ganzen Projekt gibt es keinen, geprüft in app/main.py)
-- Icons werden wie jede andere Datei-Auslieferung über einen dedizierten Endpunkt ausgeliefert.
Kein Service Worker, keine Offline-Logik (bewusst außerhalb dieser Iteration)."""

import io

from PIL import Image
from sqlalchemy.orm import Session

from .company_logo import logo_path
from .settings import get_accent_color, get_or_create_general_settings

ICON_SIZES = (192, 512)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (r, g, b)


def build_icon_png(db: Session, size: int) -> bytes:
    """Ist ein Firmenlogo hinterlegt, wird es zentriert/gepolstert auf ein einfarbiges Quadrat in
    der Akzentfarbe gesetzt und auf size skaliert; sonst bleibt es beim schlichten, einfarbigen
    Platzhalter-Quadrat."""
    general = get_or_create_general_settings(db)
    canvas = Image.new("RGB", (size, size), _hex_to_rgb(get_accent_color(db)))
    if general.logo_filename:
        path = logo_path(general.logo_filename)
        if path.is_file():
            logo = Image.open(path).convert("RGBA")
            padded_size = max(1, int(size * 0.7))
            logo.thumbnail((padded_size, padded_size), Image.LANCZOS)
            offset = ((size - logo.width) // 2, (size - logo.height) // 2)
            canvas.paste(logo, offset, logo)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def build_manifest(db: Session) -> dict:
    general = get_or_create_general_settings(db)
    accent = get_accent_color(db)
    return {
        "name": f"{general.company_name} – Mobil",
        "short_name": "Mobil",
        "start_url": "/mobil",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": accent,
        "icons": [
            {"src": f"/api/mobile-icon/{size}.png", "sizes": f"{size}x{size}", "type": "image/png"}
            for size in ICON_SIZES
        ],
    }
