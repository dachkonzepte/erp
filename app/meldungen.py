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

# Seit 1.9.79 (Stufe 4, R4 Nachtrag 3): einen Bericht legt die Monteurin zu jedem Auftrag an, nur nicht zu einem stornierten
# (app/service_reports.py::bericht_zum_auftrag_moeglich()) -- 1.9.74–1.9.78 nur zu einem Auftrag ihrer Liste (BERICHT_NUR_EIGENE_AUFTRAEGE)
BERICHT_STORNIERT = "Der Auftrag ist storniert – dazu legst du keinen Bericht an."
