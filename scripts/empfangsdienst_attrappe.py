"""Attrappe des Empfangsdienstes der Webseite (seit 1.10.0, Stufe W1a) -- für Tests und Klicktests, nie im Betrieb.

Bildet die ERP-Schnittstelle nach (dk-anfrage/1, ERP-SCHNITTSTELLE.txt des Empfangsdienstes; Zusammenfassung in
docs/archiv/webseite-und-kundenportal.md): GET /erp/v1/anfragen (anzahl, nach, alle), GET /erp/v1/anfragen/<nr>, GET …/dateien/<name>,
POST …/<nr>/uebernommen. Schlüssel als Bearer, falscher Schlüssel oder eine Kopfzeile X-Real-IP: 404 wie das Original. Lauscht nur auf 127.0.0.1.

Seit 1.10.3 (Stufe W1b) Aufbau und Zeitformat wie der echte Dienst (anfrage.py::umschlag(), erp_liste(), zeit_iso(), neue_nr()): Nummer und Eingang
in Ortszeit Europe/Berlin, die Liste mit allen Kopfdaten nach Minute und Nummer, je Art die echten Felder (siehe muster()).

Musterdaten (muster()) mit erfundenen Namen; Störungen über das Wörterbuch stoerung (siehe Handler): Status der Liste, Umleitung, roher Inhalt der Liste
oder eines Umschlags, Abbruch mitten in einer Datei, Status beim Melden. Jeder Aufruf steht in aufrufe (Methode, Pfad, mit Schlüssel ja/nein).

    with Attrappe() as a:
        a.dazu(muster("R-20261119-0910-0A1B", "reparatur", fotos=2))
        os.environ["DK_ANFRAGE_URL"], os.environ["DK_ANFRAGE_SCHLUESSEL"] = a.adresse, a.schluessel
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit


def pdf_bytes(text: str) -> bytes:
    """Ein kleines, echtes PDF (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    c.setFont("Helvetica", 14)
    c.drawString(72, 760, text)
    c.drawString(72, 736, "Musterdaten -- Attrappe des Empfangsdienstes")
    c.showPage()
    c.save()
    return puffer.getvalue()


def jpeg_bytes(farbe: tuple[int, int, int] = (90, 120, 160), groesse: tuple[int, int] = (320, 240)) -> bytes:
    """Ein kleines, echtes JPEG (Pillow)."""
    from PIL import Image, ImageDraw
    bild = Image.new("RGB", groesse, farbe)
    ImageDraw.Draw(bild).rectangle([20, 20, groesse[0] - 20, groesse[1] - 20], outline=(255, 255, 255), width=4)
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", quality=80)
    return puffer.getvalue()


ARTEN = {"reparatur": ("R", "Reparatur-Anfrage"), "wartung": ("W", "Wartungs-Anfrage"), "kantservice": ("K", "Kantservice-Anfrage"),
         "dach": ("D", "Anfrage Dachsanierung"), "pv": ("P", "Anfrage Photovoltaik")}
BERLIN = ZoneInfo("Europe/Berlin")
QUELLE = "www.dachkonzepte.gmbh"


def zeit_iso(zeitpunkt: datetime) -> str:
    """Wie anfrage.py::zeit_iso() des Empfangsdienstes: Ortszeit Europe/Berlin (der Dienst läuft mit TZ=Europe/Berlin) mit Versatz, ohne Bruchteile --
    2026-11-10T09:13:27+01:00."""
    z = zeitpunkt.astimezone(BERLIN).strftime("%Y-%m-%dT%H:%M:%S%z")
    return z[:-2] + ":" + z[-2:]


def nummer_aus(art: str, eingang: datetime, kennung: str = "0A1B") -> str:
    """Wie anfrage.py::neue_nr(): Kürzel, Datum und Minute in Ortszeit Europe/Berlin, vier Hex-Zeichen."""
    return f"{ARTEN.get(art, ('X',))[0]}-{eingang.astimezone(BERLIN):%Y%m%d-%H%M}-{kennung}"


def eingang_aus(nummer: str) -> datetime | None:
    """Der Eingang zur Nummer (Minute aus der Nummer, Ortszeit Europe/Berlin, 27 Sekunden) -- None bei einer anderen Form."""
    try:
        return datetime.strptime(nummer[2:15], "%Y%m%d-%H%M").replace(second=27, tzinfo=BERLIN)
    except (ValueError, IndexError):
        return None


# --- Reparatur und Wartung: dk-reparatur/1, Texte wie reparatur.py des Empfangsdienstes (eigene Kopie -- das ERP baut sie unabhängig nach) -----------
ROLLE_TEXT = {"eigentuemer": "Eigentümer/in", "verwaltung": "Hausverwaltung / Firma", "mieter": "Mieter/in"}


def reparatur_daten(art: str, *, name: str, rolle: str, firma: str | None, hausverwaltung: str | None, telefon: str | None, email: str | None,
                    strasse: str, plz: str, ort: str, fotos: int, vor_ort: dict | None, beschreibung: str | None) -> dict:
    rep = art == "reparatur"
    return {
        "schema": "dk-reparatur/1",
        "anliegen": art, "anliegen_text": "Reparatur" if rep else "Wartung",
        "wartung_art": None if rep else "vertrag", "wartung_art_text": None if rep else "Wartungsvertrag (jährliche Wartung)",
        "melder": {"rolle": rolle, "rolle_text": ROLLE_TEXT[rolle], "name": name, "firma": firma if rolle == "verwaltung" else None,
                   "hausverwaltung": hausverwaltung if rolle == "mieter" else None, "telefon": telefon, "email": email, "erreichbar": "vormittags"},
        "objekt": {"strasse": strasse, "plz": plz, "ort": ort, "land": "DE", "gebaeude": "efh", "gebaeude_text": "Einfamilienhaus", "geschosse": "2",
                   "geschosse_text": "2", "lage": None, "objektnummer": None,
                   "vor_ort": {"name": (vor_ort or {}).get("name"), "telefon": (vor_ort or {}).get("telefon")}},
        "anfrage": {"bereiche": ["rinne"] if rep else [], "bereiche_text": "Dachrinne / Fallrohr" if rep else None,
                    "schaeden": ["rinne"] if rep else [], "schaeden_text": "Rinne verstopft / läuft über" if rep else None,
                    "seit": "tage" if rep else None, "seit_text": "Seit einigen Tagen" if rep else None,
                    "beschreibung": beschreibung if beschreibung is not None else ("Die Rinne läuft bei Regen über. <b>Musterdaten</b>" if rep else None)},
        "termin": {"zeitraum": "2wochen", "zeitraum_text": "In den nächsten 2 Wochen"},
        "fotos": fotos,
    }


def _reparatur_zeilen(d: dict) -> list:
    m, o, a, t = d["melder"], d["objekt"], d["anfrage"], d["termin"]
    out = [("Anliegen", d["anliegen_text"] + (f" – {d['wartung_art_text']}" if d["wartung_art"] else ""))]
    out += [(None, "Wer meldet"), ("Rolle", m["rolle_text"]), ("Name", m["name"])]
    for lab, v in (("Firma / Hausverwaltung", m["firma"]), ("Hausverwaltung/Vermieter (laut Mieter)", m["hausverwaltung"]), ("Telefon", m["telefon"]),
                   ("E-Mail", m["email"]), ("Erreichbar", m["erreichbar"])):
        if v:
            out.append((lab, v))
    out += [(None, "Gebäude"), ("Anschrift", f"{o['strasse']}, {o['plz']} {o['ort']}"), ("Art des Gebäudes", o["gebaeude_text"])]
    for lab, v in (("Geschosse", o["geschosse_text"]), ("Wohnung / Lage", o["lage"]), ("Objekt-/Auftragsnummer", o["objektnummer"]),
                   ("Ansprechpartner vor Ort", o["vor_ort"]["name"]), ("Telefon vor Ort", o["vor_ort"]["telefon"])):
        if v:
            out.append((lab, v))
    out.append((None, "Schaden" if d["anliegen"] == "reparatur" else "Wartung"))
    for lab, v in (("Bereich", a["bereiche_text"]), ("Was ist passiert", a["schaeden_text"]), ("Seit wann", a["seit_text"]),
                   ("Beschreibung", a["beschreibung"])):
        if v:
            out.append((lab, v))
    if t["zeitraum"]:
        out += [(None, "Termin"), ("Zeitraum", t["zeitraum_text"])]
    out.append(("Fotos", str(d["fotos"]) if d["fotos"] else "keine"))
    return out


def reparatur_text(d: dict) -> str:
    z = [f"{'Reparatur-Anfrage' if d['anliegen'] == 'reparatur' else 'Wartungs-Anfrage'} über die Webseite (Wartung & Reparatur)"]
    for lab, v in _reparatur_zeilen(d):
        z += ["", v] if lab is None else [f"{lab}: {v}"]
    return "\n".join(z)


def reparatur_betreff(d: dict) -> str:
    o, a = d["objekt"], d["anfrage"]
    teil = (a["bereiche_text"] or "") if d["anliegen"] == "reparatur" else (d["wartung_art_text"] or "Wartung")
    return " ".join((o["strasse"] + (f" – {teil}" if teil else "")).split())[:160]


def muster(nummer: str | None = None, art: str = "reparatur", *, fotos: int = 0, spam: bool = False, name: str = "Max Muster",
           eingang: datetime | None = None, rolle: str = "eigentuemer", firma: str | None = None, hausverwaltung: str | None = None,
           telefon: str | None = "0000 000000", email: str | None = "muster@example.invalid", strasse: str = "Musterweg 1", plz: str = "00000",
           ort: str = "Musterstadt", adresse: bool = True, vor_ort: dict | None = None, beschreibung: str | None = None,
           nachricht: str | None = None, aufmass: bool = False, kennung: str = "0A1B") -> dict:
    """Eine Musteranfrage: {"umschlag": dict, "dateien": {name: bytes}} -- erfundene Daten, Aufbau wie anfrage.py::umschlag() des Empfangsdienstes
    (seit 1.10.3, Stufe W1b):

    - Nummer und Eingang in Ortszeit Europe/Berlin: ohne Eingang aus der Nummer (ihre Minute), ohne Nummer aus dem Eingang; Vorgabe 19.11.2026 09:10
      in Berlin. Eingang als ISO 8601 mit Versatz, zeit als Unix-Zeit.
    - jede Art trägt positionen ([] außer Kantservice) und aufmass (false außer Kantservice) -- wie der echte Dienst.
    - Reparatur und Wartung: daten dk-reparatur/1, kontakt abgeleitet („Name (Firma)“, ort „PLZ Ort“ des Objekts), betreff „Straße – Bereich“, text aus
      den Angaben (rolle eigentuemer | verwaltung mit firma | mieter mit hausverwaltung); PDF und fotos Fotos. nachricht ersetzt den Text.
    - Dach (daten version 1) und PV (version 2): Straße, PLZ, Ort freiwillig (adresse=False: leer), kontakt.ort „Straße, PLZ Ort“; keine Dateien;
      nachricht kommt wie auf der Webseite unter „Nachricht:“ in den Text.
    - Kantservice: keine daten, nur kontakt.ort (freies Feld), positionen und aufmass; PDF der Skizzen.
    """
    if eingang is None:
        eingang = (eingang_aus(nummer) if nummer else None) or datetime(2026, 11, 19, 9, 10, 27, tzinfo=BERLIN)
    if eingang.tzinfo is None:
        eingang = eingang.replace(tzinfo=timezone.utc)  # naiv = UTC wie im ERP
    nummer = nummer or nummer_aus(art, eingang, kennung)
    art_name = ARTEN.get(art, ("X", "Anfrage"))[1]
    dateien: dict[str, bytes] = {}
    daten = None
    positionen: list = []
    if art in ("reparatur", "wartung"):
        daten = reparatur_daten(art, name=name, rolle=rolle, firma=firma, hausverwaltung=hausverwaltung, telefon=telefon, email=email,
                                strasse=strasse, plz=plz, ort=ort, fotos=fotos, vor_ort=vor_ort, beschreibung=beschreibung)
        kontakt_name = name + (f" ({daten['melder']['firma']})" if daten["melder"]["firma"] else "")
        kontakt_ort = f"{plz} {ort}"
        betreff = reparatur_betreff(daten)
        text = nachricht if nachricht is not None else reparatur_text(daten)
        dateien["anfrage.pdf"] = pdf_bytes(f"Anfrage {nummer}")
        for i in range(1, fotos + 1):
            dateien[f"foto-{i}.jpg"] = jpeg_bytes((60 + 40 * i, 110, 150))
    elif art in ("dach", "pv"):
        s, pz, o = (strasse, plz, ort) if adresse else ("", "", "")
        kontakt_name = name
        kontakt_ort = ", ".join(x for x in (s, " ".join(x for x in (pz, o) if x)) if x) or None
        if art == "dach":
            daten = {"version": 1, "haustyp": "efh", "dachform": "satteldach", "wohneinheiten": 1, "flaeche": 120, "flaeche_unbekannt": False,
                     "konzept": "standard", "fenster": [], "wann": "", "strasse": s, "plz": pz, "ort": o,
                     "ergebnis": {"dach_netto": 30000, "fenster_netto": 0, "netto": 30000, "brutto": 35700, "von": 32000, "bis": 39000, "mwst": 19},
                     "foerderung": None, "stand_werte": "2026-11", "stand_foerderung": "2026-11"}
            betreff = "Standard, 120 m², Satteldach"
            text = "Dach-Konfigurator – Anfrage Dachsanierung\nDachfläche: 120 m²" + (f"\nAnschrift des Hauses: {kontakt_ort}" if kontakt_ort else "")
        else:
            daten = {"version": 2, "kunde": "privat", "verbrauch": 4500, "verbrauch_quelle": "eingetragen", "personen": None, "betrieb": None, "eautos": 0,
                     "dachform": "satteldach", "ausrichtung": "sued", "flaeche": None, "vorschlag": "mittel", "anlage_kwp": 9.6, "speicher_kwh": 10,
                     "ertrag_kwh": 9200, "begrenzt": False, "extras": [], "extras_enthalten": [], "zustand": [], "wann": "", "strasse": s, "plz": pz,
                     "ort": o, "ergebnis": {"anlage_speicher": 21000, "extras": 0, "summe": 21000, "von": 19000, "bis": 23000, "netto": False},
                     "stand_werte": "2026-11"}
            betreff = "Mittel, 9,6 kWp, 10 kWh Speicher, Satteldach"
            text = "PV-Konfigurator – Anfrage Photovoltaik\nAnlage: 9,6 kWp" + (f"\nAnschrift des Gebäudes: {kontakt_ort}" if kontakt_ort else "")
        if nachricht:
            text += "\n\nNachricht:\n" + nachricht
    else:
        kontakt_name = name
        kontakt_ort = "00000 Musterstadt"
        betreff = "Anfrage Kantteil" + (" mit Aufmaß vor Ort" if aufmass else "")
        text = nachricht if nachricht is not None else "Kantteil: Traufblech, 3 × 2000 mm"
        if art == "kantservice":
            positionen = [{"typ": "kt", "vorlage": "traufblech", "laenge": 2000, "stk": 3}]
        dateien["anfrage.pdf"] = pdf_bytes(f"Anfrage {nummer}")
    umschlag = {
        "schema": "dk-anfrage/1", "nr": nummer, "art": art, "art_name": art_name, "eingang": zeit_iso(eingang), "zeit": int(eingang.timestamp()),
        "quelle": QUELLE, "kontakt": {"name": kontakt_name, "telefon": telefon or None, "email": email or None, "ort": kontakt_ort or None},
        "betreff": betreff, "text": text, "daten": daten, "positionen": positionen, "aufmass": bool(aufmass and art == "kantservice"),
        "spamverdacht": spam,
        "dateien": [{"name": n, "typ": "application/pdf" if n.endswith(".pdf") else "image/jpeg", "bytes": len(b),
                     "sha256": hashlib.sha256(b).hexdigest(), "pfad": f"/erp/v1/anfragen/{nummer}/dateien/{n}"}
                    | ({} if n.endswith(".pdf") else {"breite": 320, "hoehe": 240}) for n, b in dateien.items()],
        "uebernommen": None,
    }
    return {"umschlag": umschlag, "dateien": dateien}


def _folge(nummer: str) -> tuple[str, str]:
    """Reihenfolge der Liste wie anfrage.py::_erp_folge(): Minute des Eingangs (aus der Nummer), dann Nummer."""
    return (nummer[2:15], nummer)


class Attrappe:
    def __init__(self, schluessel: str | None = None):
        self.schluessel = schluessel or secrets.token_hex(32)
        self.anfragen: dict[str, dict] = {}
        self.uebernommen: dict[str, str] = {}
        self.meldungen: list[tuple[str, str]] = []  # jedes „übernommen“ in Reihenfolge (Nummer, erp_id) -- auch wiederholte
        self.stoerung: dict = {}
        self.aufrufe: list[tuple[str, str, bool]] = []
        self._server: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()

    def vermerk(self, nummer: str) -> dict | None:
        """Wie anfrage.py::erp_vermerk(): {zeit, erp_id} oder None."""
        if nummer not in self.uebernommen:
            return None
        return {"zeit": zeit_iso(datetime.now(timezone.utc)), "erp_id": self.uebernommen[nummer]}

    def kopfdaten(self, nummer: str) -> dict:
        """Ein Eintrag der Liste wie anfrage.py::erp_liste(): schema, nr, art, art_name, eingang, zeit, betreff, kontakt {name}, spamverdacht,
        uebernommen, pfad (eine Nummer aus liste_extra ohne Anfrage nur mit nr)."""
        u = self.anfragen.get(nummer, {}).get("umschlag")
        if u is None:
            return {"nr": nummer}
        return {"schema": u["schema"], "nr": nummer, "art": u["art"], "art_name": u["art_name"], "eingang": u["eingang"], "zeit": u["zeit"],
                "betreff": u["betreff"], "kontakt": {"name": u["kontakt"]["name"]}, "spamverdacht": u["spamverdacht"],
                "uebernommen": self.vermerk(nummer), "pfad": f"/erp/v1/anfragen/{nummer}"}

    def dazu(self, anfrage: dict) -> str:
        nummer = anfrage["umschlag"]["nr"]
        self.anfragen[nummer] = anfrage
        return nummer

    @property
    def adresse(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> "Attrappe":
        attrappe = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # still
                pass

            def _antwort(self, status: int, koerper: bytes = b"", typ: str = "application/json", kopf: dict | None = None):
                self.send_response(status)
                self.send_header("Content-Type", typ)
                self.send_header("Content-Length", str(len(koerper)))
                for k, w in (kopf or {}).items():
                    self.send_header(k, w)
                self.end_headers()
                self.wfile.write(koerper)

            def _json(self, status: int, wert):
                self._antwort(status, json.dumps(wert, ensure_ascii=False).encode("utf-8"))

            def _ohne_laenge(self, koerper: bytes, typ: str = "application/json"):
                """Antwort ohne Content-Length, bis die Verbindung schließt -- prüft die Lesegrenzen jenseits der Angabe."""
                self.send_response(200)
                self.send_header("Content-Type", typ)
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(koerper)
                self.wfile.flush()
                self.close_connection = True

            def _erlaubt(self) -> bool:
                art, _, wert = (self.headers.get("Authorization") or "").partition(" ")
                gut = art.lower() == "bearer" and secrets.compare_digest(wert.strip(), attrappe.schluessel) and self.headers.get("X-Real-IP") is None
                attrappe.aufrufe.append((self.command, self.path, bool(self.headers.get("Authorization"))))
                return gut

            def do_GET(self):  # noqa: N802
                if not self._erlaubt():
                    return self._json(404, {"ok": False})
                teile = urlsplit(self.path)
                pfad = teile.path.split("/")
                st = attrappe.stoerung
                if teile.path == "/erp/v1/anfragen":
                    if "umleitung" in st:
                        return self._antwort(302, b"", kopf={"Location": st["umleitung"]})
                    if "liste_status" in st:
                        return self._json(st["liste_status"], {"ok": False})
                    if "liste_roh" in st:
                        if st.get("ohne_laenge") == "liste":
                            return self._ohne_laenge(st["liste_roh"])
                        return self._antwort(200, st["liste_roh"])
                    q = parse_qs(teile.query)
                    anzahl = int(q.get("anzahl", ["100"])[0])
                    nach = q.get("nach", [None])[0]
                    alle = q.get("alle", ["0"])[0] == "1"
                    nummern = sorted((n for n in attrappe.anfragen if alle or n not in attrappe.uebernommen), key=_folge)
                    if "liste_extra" in st:
                        nummern = nummern + list(st["liste_extra"])
                    if nach:
                        nummern = [n for n in nummern if _folge(n) > _folge(nach)]
                    seite, weitere = nummern[:anzahl], len(nummern) > anzahl
                    eintraege = [attrappe.kopfdaten(n) for n in seite]
                    return self._json(200, {"ok": True, "schema": "dk-anfrage/1", "anfragen": eintraege, "weitere": weitere,
                                            "naechste": seite[-1] if weitere else None, "version": "attrappe"})
                if len(pfad) == 5 and pfad[:4] == ["", "erp", "v1", "anfragen"]:
                    nummer = unquote(pfad[4])
                    if nummer in st.get("umschlag_roh", {}):
                        return self._antwort(200, st["umschlag_roh"][nummer])
                    if nummer not in attrappe.anfragen:
                        return self._json(404, {"ok": False})
                    umschlag = dict(attrappe.anfragen[nummer]["umschlag"])
                    umschlag["uebernommen"] = attrappe.vermerk(nummer)
                    return self._json(200, umschlag)
                if len(pfad) == 7 and pfad[:4] == ["", "erp", "v1", "anfragen"] and pfad[5] == "dateien":
                    nummer, name = unquote(pfad[4]), unquote(pfad[6])
                    daten = attrappe.anfragen.get(nummer, {}).get("dateien", {}).get(name)
                    if daten is None:
                        return self._json(404, {"ok": False})
                    if st.get("abbruch_datei") == (nummer, name):
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(len(daten)))
                        self.end_headers()
                        self.wfile.write(daten[: len(daten) // 2])
                        self.wfile.flush()
                        self.close_connection = True
                        try:
                            self.connection.shutdown(2)
                        except OSError:
                            pass
                        return None
                    if st.get("ohne_laenge") == (nummer, name):
                        return self._ohne_laenge(daten, "application/octet-stream")
                    if st.get("langsam"):
                        time.sleep(st["langsam"])
                    return self._antwort(200, daten, typ="application/pdf" if name.endswith(".pdf") else "image/jpeg")
                return self._json(404, {"ok": False})

            def do_POST(self):  # noqa: N802
                laenge = int(self.headers.get("Content-Length") or 0)
                koerper = self.rfile.read(laenge) if 0 < laenge <= 65536 else b""
                if not self._erlaubt():
                    return self._json(404, {"ok": False})
                pfad = urlsplit(self.path).path.split("/")
                if len(pfad) == 6 and pfad[:4] == ["", "erp", "v1", "anfragen"] and pfad[5] == "uebernommen":
                    nummer = unquote(pfad[4])
                    if nummer not in attrappe.anfragen:
                        return self._json(404, {"ok": False})
                    if "melden_status" in attrappe.stoerung:
                        return self._json(attrappe.stoerung["melden_status"], {"ok": False})
                    try:
                        erp_id = json.loads(koerper.decode("utf-8"))["erp_id"]
                    except (ValueError, KeyError, TypeError):
                        return self._json(400, {"ok": False, "fehler": "erp_id fehlt"})
                    attrappe.uebernommen[nummer] = erp_id
                    attrappe.meldungen.append((nummer, erp_id))
                    return self._json(200, {"ok": True})
                return self._json(404, {"ok": False})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> "Attrappe":
        return self.start()

    def __exit__(self, *args) -> None:
        self.stop()
