"""Version 1.11.15 (Stufe P1e, Bauplan P1, Abschnitt 5 E „Wartung“): antwortet der Portal-Dienst nicht (502/504), zeigt nginx die feste Seite
„Gleich wieder da“ (scripts/server/portal-wartung.html).

    Seite       Wortlaut des Entwurfs (Portal-Handy, Tabelle der Fehlerseite), kein Skript, nichts von außen (kein src, kein href, kein url(), kein @import),
                genau ein <style>; hell und dunkel nach dem Gerät; dieselbe Bildmarke wie die Seite des Portals
    nginx       error_page 502 504 auf einen internen Ort, die Datei aus /etc/nginx/dk-portal/, CSP mit genau der Prüfsumme des Stils (wie der Server die
                Datei sieht: Zeilenende LF), dazu kein Einrahmen, nosniff, no-referrer, no-store, HSTS; proxy_intercept_errors nicht an
"""

import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEITE = (ROOT / "scripts" / "server" / "portal-wartung.html").read_bytes().decode("utf-8").replace("\r\n", "\n")
CONF = (ROOT / "scripts" / "server" / "nginx-kunde.conf").read_text(encoding="utf-8")
ZEILEN = [z.split("#")[0].strip() for z in CONF.splitlines() if z.split("#")[0].strip()]


def _ort() -> list[str]:
    anfang = ZEILEN.index("location = /_wartung.html {")
    return ZEILEN[anfang + 1:ZEILEN.index("}", anfang)]


def test_seite_ohne_skript_und_ohne_fremdes():
    klein = SEITE.lower()
    assert SEITE.startswith("<!DOCTYPE html>") and "<script" not in klein and not re.search(r"\son[a-z]+\s*=", klein)
    # seit 1.11.47 genau zwei Links: Impressum und Datenschutz im Fuß (Pflicht) -- bis dahin gar keiner
    assert "src=" not in klein and "url(" not in klein and "@import" not in klein and "<link" not in klein
    assert re.findall(r'href="([^"]*)"', SEITE) == ["https://dachkonzepte.gmbh/impressum", "https://dachkonzepte.gmbh/datenschutz"]
    assert klein.count("<style>") == 1 and ' style="' not in klein
    assert "<h1>Gleich wieder da</h1>" in SEITE and "<p>Das Kundenportal ist in wenigen Minuten wieder erreichbar.</p>" in SEITE
    assert "prefers-color-scheme: dark" in SEITE


def test_dieselbe_bildmarke_wie_das_portal():
    portal = (ROOT / "app" / "portal" / "seiten" / "portal.html").read_text(encoding="utf-8")
    marke = re.search(r'<polygon fill="#367337" points="[^"]+"/>', SEITE).group(0)
    assert marke in portal


def test_nginx_zeigt_sie_bei_502_und_504():
    assert "error_page 502 504 /_wartung.html;" in ZEILEN
    ort = _ort()
    assert ort[:4] == ["internal;", "alias /etc/nginx/dk-portal/wartung.html;", "default_type text/html;", "charset utf-8;"]
    assert not any(z.startswith("proxy_intercept_errors") for z in ZEILEN)  # Antworten des Dienstes gehen unverändert durch


def test_csp_mit_der_pruefsumme_des_stils():
    stil = re.search(r"<style>(.*?)</style>", SEITE, re.S).group(1)
    pruefsumme = base64.b64encode(hashlib.sha256(stil.encode("utf-8")).digest()).decode()
    csp = next(z for z in _ort() if z.startswith("add_header Content-Security-Policy"))
    assert csp == (f"add_header Content-Security-Policy \"default-src 'none'; style-src 'sha256-{pruefsumme}'; base-uri 'none'; form-action 'none'; "
                   "frame-ancestors 'none'\" always;")
    for z in ("add_header X-Frame-Options DENY always;", "add_header X-Content-Type-Options nosniff always;", "add_header Referrer-Policy no-referrer always;",
              "add_header Cache-Control no-store always;", 'add_header Strict-Transport-Security "max-age=31536000" always;'):
        assert z in _ort(), z


def test_fuss_wie_im_portal():
    """Seit 1.11.47: Impressum und Datenschutz wie im Portal -- dieselbe Form, die das Portal aus der Webseite der Unternehmensdaten bildet
    (app/portal/seiten.py::firma()), für die Webseite des Betriebs: die Domain über der festen Adresse des Portals (kunde.dachkonzepte.gmbh, F1)."""
    from app.portal.seiten import firma
    from app.portal_mails import PORTAL_ADRESSE

    webseite = PORTAL_ADRESSE.removeprefix("https://").split(".", 1)[1]
    f = firma({"company_name": "Betrieb", "website": webseite})
    assert re.findall(r'<a href="([^"]*)">(Impressum|Datenschutz)</a>', SEITE) == [(f.impressum, "Impressum"), (f.datenschutz, "Datenschutz")]
    assert '<footer><div class="fuss">' in SEITE
