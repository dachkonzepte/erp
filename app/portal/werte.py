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
    "unterlagen",           # seit 1.11.31 (P2a): Liste der Unterlagen geladen
    "datei_angefordert",    # seit 1.11.31 (P2a): eine Unterlage angefordert (objekt_art „freigabe“, objekt_id = Freigabe)
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

# Freigaben (portal_freigaben, seit 1.11.31, Stufe P2a; Bauplan P2, B4): was der Kunde sieht. Art = was das Portal zeigt, Quelle = woher die Unterlage
# im ERP stammt (Tabelle; die Funktion der Datenbank prüft je Quelle die Kette zum Kunden, app/portal/unterlagen.py).
FREIGABE_ARTEN = ("angebot", "auftrag", "vertrag", "rechnung", "mahnung", "abnahmeprotokoll", "einsatzbericht", "brief", "checkliste", "foto",
                  "dokument")
FREIGABE_QUELLEN = ("sent_documents", "invoices", "reminders", "service_reports", "checklist_versions", "notice_letters", "service_report_photos",
                    "customer_documents", "project_documents", "property_documents", "defect_files", "order_acceptance_files")
# Warum eine Kopie nicht entstand (ab P2b, der Postbote, app/portal_kopien.py): nur feste Wörter. „fehlt“ seit 1.11.33 (Quelle oder ihre Datei fehlt;
# bis dahin wäre es „nicht_lesbar“ gewesen).
KOPIE_FEHLER = ("zu_gross", "nicht_lesbar", "falscher_typ", "pruefsumme", "abbruch", "fehlt")
# Typ einer Kopie (ab P2b): nur PDF und JPEG (Fotos werden neu kodiert, Bauplan P2, B5/B6).
KOPIE_TYPEN = ("application/pdf", "image/jpeg")
# Zustand einer Rechnung im Schaufenster (seit 1.11.41, Stufe P2d; Bauplan P2, B3, Entscheidung P2-7): wie das ERP sie zählt (app/portal_schaufenster.py)
# -- „offen“ ist nur, was das ERP mahnen würde; ein offener Einbehalt oder ein genutztes Skonto ist nie offen. „ohne“: eine Rechnung, die nie offen ist (über
# 0 € oder weniger, keine Endrechnung).
RECHNUNG_ZUSTAENDE = ("offen", "teilweise_bezahlt", "bezahlt", "guthaben", "enthalten", "storniert", "storno", "ohne")
