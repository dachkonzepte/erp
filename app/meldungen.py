"""Gemeinsame Meldungen der Oberfläche (seit 1.8.159, Runde „Du“).

Eine Meldung, die an vielen Stellen vorkommt, steht hier einmal -- der Server nimmt die Konstante, die Vorlagen bekommen sie als
Jinja-Global (app/routers/pages.py, in Skripten als `{{ kein_mitarbeiter|tojson }}`). Bis 1.8.158 gab es „… keinem Mitarbeiter
zugeordnet“ in neun Fassungen an 20 Stellen (Befund: docs/archiv/befund-du-statt-sie.md); tests/test_v440_runde_du.py hält sie bei
dieser einen.
"""

KEIN_MITARBEITER = "Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → Benutzer und Zugriff ändern."
