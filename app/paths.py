"""Zentrale Auflösung des Datenverzeichnisses (`ERP_DATA_DIR`).

Verschlüsselungsschlüssel (`.erp_secret`), Protokoll (`erp.log`) und alle sieben
Upload-Ordner (Firmenlogo, Briefpapier-Hintergründe, Kunden-/Projektdateien,
Dachflächen-Skizzen, Einsatzbericht-Fotos/-Unterschriften) landen ohne gesetzte
Umgebungsvariable hier -- ein Ordner unterhalb des Projektverzeichnisses.

Der Fallback ist bewusst DATEIBASIERT (`Path(__file__).resolve().parent.parent`),
NICHT relativ zum aktuellen Arbeitsverzeichnis (etwa `Path("data")`). Ein
arbeitsverzeichnis-relativer Fallback funktioniert nur, solange der Prozess
zufällig immer aus dem Projektordner heraus gestartet wird -- heute zufällig
überall der Fall (start_windows.bat wechselt vorher per `cd /d %~dp0` dorthin,
pytest liest pytest.ini aus dem Projektordner), aber ein künftiger Serverstart
über eine systemd-Unit oder einen Docker-`WORKDIR` mit einem anderen
Arbeitsverzeichnis würde sonst STILLSCHWEIGEND einen anderen Ordner treffen --
ohne sofort sichtbaren Fehler, da der Ordner ja automatisch neu angelegt wird;
der Schaden zeigt sich erst später als "die Uploads von vorher sind weg". Der
dateibasierte Fallback ist unabhängig vom Arbeitsverzeichnis und war schon
vorher die Bauweise der sieben Upload-Pfade (app/company_logo.py,
app/customer_documents.py, app/document_layout_background.py,
app/project_documents.py, app/roof_area_sketches.py, app/service_reports.py,
app/service_report_photos.py) -- data_dir() vereinheitlicht das jetzt für
alle. Bitte bei einer künftigen Vereinfachung NICHT wieder auf einen
arbeitsverzeichnis-relativen Fallback zurückdrehen.
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Liefert den Datenordner (per ERP_DATA_DIR überschreibbar) und legt ihn bei Bedarf an."""
    root = Path(os.getenv("ERP_DATA_DIR", str(_PROJECT_ROOT / "data")))
    root.mkdir(parents=True, exist_ok=True)
    return root
