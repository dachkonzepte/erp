"""Attrappe des Empfangsdienstes der Webseite (seit 1.10.0, Stufe W1a) -- für Tests und Klicktests, nie im Betrieb.

Bildet die ERP-Schnittstelle nach (dk-anfrage/1, ERP-SCHNITTSTELLE.txt des Empfangsdienstes; Zusammenfassung in
docs/archiv/webseite-und-kundenportal.md): GET /erp/v1/anfragen (anzahl, nach, alle), GET /erp/v1/anfragen/<nr>, GET …/dateien/<name>,
POST …/<nr>/uebernommen. Schlüssel als Bearer, falscher Schlüssel oder eine Kopfzeile X-Real-IP: 404 wie das Original. Lauscht nur auf 127.0.0.1.

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


def muster(nummer: str, art: str = "reparatur", *, fotos: int = 0, spam: bool = False, name: str = "Max Muster",
           eingang: datetime | None = None) -> dict:
    """Eine Musteranfrage: {"umschlag": dict, "dateien": {name: bytes}} -- erfundene Daten, Prüfsummen passend."""
    eingang = eingang or datetime(2026, 11, 19, 9, 10, tzinfo=timezone.utc)
    dateien = {"anfrage.pdf": pdf_bytes(f"Anfrage {nummer}")}
    for i in range(1, fotos + 1):
        dateien[f"foto-{i}.jpg"] = jpeg_bytes((60 + 40 * i, 110, 150))
    art_name = ARTEN.get(art, ("X", "Anfrage"))[1]
    daten = None
    if art in ("reparatur", "wartung"):
        daten = {"schema": "dk-reparatur/1", "anliegen": art, "anliegen_text": art_name,
                 "melder": {"rolle": "eigentuemer", "rolle_text": "Eigentümer/in", "name": name, "firma": None, "hausverwaltung": None,
                            "telefon": "0000 000000", "email": "muster@example.invalid", "erreichbar": "vormittags"},
                 "objekt": {"strasse": "Musterweg 1", "plz": "00000", "ort": "Musterstadt", "land": "DE", "lage": None, "gebaeude": "efh",
                            "gebaeude_text": "Einfamilienhaus", "geschosse": "2", "geschosse_text": "2", "objektnummer": None, "vor_ort": None},
                 "anfrage": {"bereiche": ["rinne"], "bereiche_text": "Dachrinne / Fallrohr", "schaeden": ["rinne"],
                             "schaeden_text": "Rinne verstopft / läuft über", "seit": "tage", "seit_text": "Seit einigen Tagen",
                             "beschreibung": "Die Rinne läuft bei Regen über. <b>Musterdaten</b>"},
                 "termin": {"zeitraum": "2wochen", "zeitraum_text": "In den nächsten 2 Wochen"}, "fotos": fotos}
    umschlag = {
        "schema": "dk-anfrage/1", "nr": nummer, "art": art, "art_name": art_name,
        "eingang": eingang.isoformat(), "zeit": int(eingang.timestamp()), "quelle": "www.example.invalid",
        "kontakt": {"name": name, "telefon": "0000 000000", "email": "muster@example.invalid", "ort": "00000 Musterstadt"},
        "betreff": f"{art_name} {nummer} – {name}, 00000 Musterstadt", "text": f"{art_name}\nName: {name}\nMusterdaten.",
        "daten": daten, "spamverdacht": spam, "uebernommen": None,
        "dateien": [{"name": n, "typ": "application/pdf" if n.endswith(".pdf") else "image/jpeg", "bytes": len(b),
                     "sha256": hashlib.sha256(b).hexdigest(), "pfad": f"/erp/v1/anfragen/{nummer}/dateien/{n}"} for n, b in dateien.items()],
    }
    if art == "kantservice":
        umschlag["positionen"] = [{"vorlage": "traufblech", "laenge": 2000, "stk": 3}]
        umschlag["aufmass"] = False
    return {"umschlag": umschlag, "dateien": dateien}


class Attrappe:
    def __init__(self, schluessel: str | None = None):
        self.schluessel = schluessel or secrets.token_hex(32)
        self.anfragen: dict[str, dict] = {}
        self.uebernommen: dict[str, str] = {}
        self.stoerung: dict = {}
        self.aufrufe: list[tuple[str, str, bool]] = []
        self._server: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()

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
                    nummern = sorted(n for n in attrappe.anfragen if alle or n not in attrappe.uebernommen)
                    if "liste_extra" in st:
                        nummern = nummern + list(st["liste_extra"])
                    if nach:
                        nummern = [n for n in nummern if n > nach]
                    seite, weitere = nummern[:anzahl], len(nummern) > anzahl
                    eintraege = [{"nr": n, "art": attrappe.anfragen.get(n, {}).get("umschlag", {}).get("art")} for n in seite]
                    return self._json(200, {"ok": True, "schema": "dk-anfrage/1", "anfragen": eintraege, "weitere": weitere,
                                            "naechste": seite[-1] if weitere else None, "version": "attrappe"})
                if len(pfad) == 5 and pfad[:4] == ["", "erp", "v1", "anfragen"]:
                    nummer = unquote(pfad[4])
                    if nummer in st.get("umschlag_roh", {}):
                        return self._antwort(200, st["umschlag_roh"][nummer])
                    if nummer not in attrappe.anfragen:
                        return self._json(404, {"ok": False})
                    umschlag = dict(attrappe.anfragen[nummer]["umschlag"])
                    umschlag["uebernommen"] = {"erp_id": attrappe.uebernommen[nummer]} if nummer in attrappe.uebernommen else None
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
