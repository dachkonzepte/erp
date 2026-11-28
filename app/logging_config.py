"""Zentrale Logging-Konfiguration (seit 1.0.8).

Bisher gab es außer dem fachlichen AuditLog (wer hat was geändert) keine
technische Fehlerprotokollierung -- unbehandelte Exceptions landeten nur in
der uvicorn-Konsole und waren nach dem nächsten Neustart verloren.

configure_logging() richtet die Ausgabe auf die Konsole (stderr) ein und -- nur
lokal -- einen rotierenden Datei-Handler unter data/erp.log (max. 5 MB je
Datei, 5 Sicherungen). Wird einmalig beim Start der App aufgerufen
(app/main.py), ebenso von den Skripten des Servers (Postbote, Outlook-Abgleich,
Notfallskripte).

Seit 1.11.49 (W1c Stufe 2, S2-0 a; Antwort W2-1 vom 28.11.2026): im Betrieb
keine Datei mehr. Die Datei wechselte nach Größe, nicht nach Tagen -- bei der
Last des Betriebs hielt sie Monate, lag in jeder Sicherung, und ein Traceback
konnte über die Fehlermeldung der Datenbank Werte einer Anweisung enthalten.
Die Datenschutzerklärung sagt „jedes Protokoll des Servers höchstens 15 Tage“.
Im Betrieb geht deshalb alles nur nach stderr: unter systemd ins Journal
(MaxRetentionSec=14day), der Outlook-Abgleich per Cron über systemd-cat
ebenso. Die Datei gibt es nur mit ERP_ENV development oder test (lokal,
Klicktests, Tests). „Betrieb“ ist jede andere ERP_ENV, auch eine fehlende --
dieselbe Regel wie NUR_HTTPS in app/auth.py. Dazu verdeckt die Engine im
Betrieb die Parameter in Fehlermeldungen (app/database.py, hide_parameters).
"""

import logging
import logging.handlers
import os

from .paths import data_dir

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
LOKALE_UMGEBUNGEN = ("development", "test")


def im_betrieb() -> bool:
    """Seit 1.11.49: True außer bei ERP_ENV development oder test (auch ohne ERP_ENV) -- dann keine Protokolldatei, Parameter verdeckt."""
    return (os.getenv("ERP_ENV") or "").strip().lower() not in LOKALE_UMGEBUNGEN


def configure_logging() -> None:
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Idempotent: bei --reload bzw. mehrfachem Import nicht doppelt anhängen (seit 1.11.49 über die Markierung der eigenen Handler --
    # im Betrieb gibt es keinen RotatingFileHandler mehr, an dem es sich erkennen ließe).
    if any(getattr(h, "_dk_erp", False) or isinstance(h, logging.handlers.RotatingFileHandler) for h in root_logger.handlers):
        return

    if not im_betrieb():
        file_handler = logging.handlers.RotatingFileHandler(
            data_dir() / "erp.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler._dk_erp = True
        root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler._dk_erp = True
    root_logger.addHandler(console_handler)

    # SQLAlchemys Engine-Logger ist auf INFO sehr gesprächig (jede SQL-
    # Anweisung) -- eigene App-Logger sind davon nicht betroffen.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
