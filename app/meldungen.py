"""Gemeinsame Meldungen der Oberfläche (seit 1.8.159, Runde „Du“).

Eine Meldung, die an vielen Stellen vorkommt, steht hier einmal -- der Server nimmt die Konstante, die Vorlagen bekommen sie als
Jinja-Global (app/routers/pages.py, in Skripten als `{{ kein_mitarbeiter|tojson }}`). Bis 1.8.158 gab es „… keinem Mitarbeiter
zugeordnet“ in neun Fassungen an 20 Stellen (Befund: docs/archiv/befund-du-statt-sie.md); tests/test_v440_runde_du.py hält sie bei
dieser einen.
"""

KEIN_MITARBEITER = "Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → Benutzer und Zugriff ändern."

# Seit 1.9.35 (Stufe 4, R1): eine Zeit von früher im abgeschlossenen Monat schließt nur das Büro -- seit 1.9.45 hier, weil auch
# „Heute“ auf /mobil sie zeigt (app/heute.py), bis dahin in app/routers/time_tracking.py.
MONAT_ABGESCHLOSSEN = "Monat abgeschlossen – das Büro schließt die Zeit."

# Seit 1.9.60 (Stufe 4, R3, Punkt 3): eine reine Dauer trägt nur das Büro ein -- die Monteurin mit Von und Bis (Pausenregel des Tages)
NUR_VON_BIS = "Bitte Von und Bis angeben – eine reine Dauer trägt nur das Büro ein."

# Seit 1.9.74 (Stufe 4, R4 Nachtrag): einen Bericht legt die Monteurin nur für einen Auftrag ihrer Liste an (app/planning.py::
# field_order_in_list(), dieselbe Liste wie „Zeit nachtragen“)
BERICHT_NUR_EIGENE_AUFTRAEGE = ("Einen Bericht legst du nur für einen deiner Aufträge an – dieselbe Auswahl wie bei „Zeit nachtragen“. "
                                "Fehlt ein Auftrag, wende dich an das Büro.")
