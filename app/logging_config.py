"""Zentrale Logging-Konfiguration (seit 1.0.8).

Bisher gab es außer dem fachlichen AuditLog (wer hat was geändert) keine
technische Fehlerprotokollierung -- unbehandelte Exceptions landeten nur in
der uvicorn-Konsole und waren nach dem nächsten Neustart verloren.

configure_logging() richtet einen rotierenden Datei-Handler unter
data/erp.log ein (max. 5 MB je Datei, 5 Sicherungen -- ältere Einträge
verschwinden dadurch automatisch, statt die Datei unbegrenzt wachsen zu
lassen) sowie zusätzlich weiterhin Ausgabe auf die Konsole. Wird einmalig
beim Start der App aufgerufen (app/main.py).
"""

import logging
import logging.handlers

from .paths import data_dir

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    log_path = data_dir() / "erp.log"

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Idempotent: bei --reload bzw. mehrfachem Import nicht doppelt anhängen.
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root_logger.handlers):
        return

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # SQLAlchemys Engine-Logger ist auf INFO sehr gesprächig (jede SQL-
    # Anweisung) -- eigene App-Logger sind davon nicht betroffen.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
