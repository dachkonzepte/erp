"""Feste Werte des Kundenportals (seit 1.11.0) -- eine Stelle für das ERP (Modelle, CHECK der Spalten), den Dienst des Portals und die Funktionen der
Datenbank (ab 1.11.1). Die Migration trägt die Listen wörtlich; tests/test_v799_portal_rechte.py vergleicht beide.
"""

# Auftrag an den Postboten (portal_post): heute nur der Anmeldecode.
POST_ARTEN = ("code",)
POST_STATUS = ("wartet", "gesendet", "fehler", "verworfen")

# Warum eine Sitzung endete (portal_sitzungen.beendet_grund).
SITZUNG_ENDE = ("abgemeldet", "ueberall", "gesperrt", "neu_erzeugt", "portal_aus")

# Zugriffsprotokoll (portal_zugriffe): nur feste Wörter, nie Inhalte, nie eine Adresse (Regel 18, F14).
AKTIONEN = (
    "link_geoeffnet",       # Link geöffnet (gültig oder nicht -- das Ergebnis sagt es)
    "code_angefordert",     # Code angefordert (vom Portal)
    "code_gesendet",        # Mail mit dem Code ging hinaus (Postbote)
    "code_fehler",          # Mail mit dem Code ging nicht hinaus (Postbote)
    "code_falsch",          # falscher Code eingegeben
    "code_abgelaufen",      # Code abgelaufen, verbraucht oder zu viele Versuche
    "angemeldet",           # richtiger Code -- Sitzung bestätigt
    "verlaengert",          # Sitzung gleitend verlängert (höchstens einmal je Stunde)
    "abgemeldet",           # dieses Gerät abgemeldet
    "ueberall_abgemeldet",  # alle Geräte des Zugangs abgemeldet
)
ERGEBNISSE = (
    "ok",
    "unbekannt",     # Link gehört zu keinem Zugang
    "gesperrt",      # Zugang gesperrt
    "abgelaufen",    # Zugang abgelaufen (gültig bis) oder noch ohne Link
    "portal_aus",    # Portal am Kunden aus
    "archiv",        # Kunde im Archiv
    "modul_aus",     # Modul „Kundenportal“ aus (Notaus)
    "bremse",        # eine Bremse griff
    "code_noetig",   # Gerät neu -- Code nötig
    "angemeldet",    # Gerät schon angemeldet
    "ungueltig",     # Sitzung oder Eingabe ungültig
)

# Prüfwerte: SHA-256 über Zweck + Wert, hexadezimal (64 Zeichen). Der Wert selbst steht nie in der Datenbank.
ZWECK_LINK = "dk-portal-link:"
ZWECK_SITZUNG = "dk-portal-sitzung:"
ZWECK_CODE = "dk-portal-code:"
