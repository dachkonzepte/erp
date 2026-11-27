"""Version 1.11.34 (Stufe P2b, Bauplan P2, B2 „Weg B“, B6, B7, Nachtrag 3): die Dateien im Kundenportal -- Anfordern, X-Accel-Redirect, nginx.

    Ohne Datenbank   Dateiname aus dem Titel (Umlaute, Steuerzeichen, Anführungszeichen, Schrägstriche, Länge, leer); ein Name oder Typ der Kopie, der
                     nicht passt, geht nie an nginx (500); der internal-Block der nginx-Datei: internal, Ordner, feste Typen, default_type, genau der Satz
                     der Schutz-Kopfzeilen des Dienstes mit „always“ (die CSP ohne sandbox), nichts von dem, was nginx vom Dienst übernimmt; das Protokoll
                     ohne den internen Weg; die Einheit des Portals sieht den Ordner nicht; die Attrappe liest genau diesen Block
    PostgreSQL       (ein Schema für die Datei, der Dienst als Testrolle dkportal_test, davor die Attrappe von nginx): anfordern, dann ansehen und
                     herunterladen über nginx -- die Datei, die übernommenen und die eigenen Kopfzeilen, keine des Dienstes (keine CSP mit script-src), kein
                     X-Accel-Redirect beim Browser; HEAD und Range; direkt beim Dienst eine leere Antwort mit X-Accel-Redirect, kein GET schreibt; ohne
                     Anforderung, fremd, unbekannt, zurückgenommen, abgelaufen, andere Sitzung: 404, außen gleich; ohne Sitzung 401; Bremse 429; Eingaben
                     422; ein unpassender Name in der Datenbank 500 ohne X-Accel-Redirect; /_portal_dateien/ direkt 404; Angriffe mit allen Methoden
                     gegen einen echten uvicorn
"""

import http.client
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.portal import pruefwerte, rechte, routen
from app.portal.main import erzeugen, kopf_der_migrationen
from app.portal.schranke import schutz_kopfzeilen
from app.database import Base
from tests.test_v800_portal_funktionen import TESTROLLE, Welt
from tests.test_v801_portal_dienst import EIGEN, _einstellungen, _uvicorn, dienst  # noqa: F401 -- dienst ist eine Fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nginx_attrappe  # noqa: E402

PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
NGINX = ROOT / "scripts" / "server" / "nginx-kunde.conf"
CSP_DATEI = "default-src 'none'; frame-ancestors 'none'"


# --- ohne Datenbank -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("titel, typ, ascii_, voll", [
    ("Rechnung R-2026-0012", "application/pdf", "Rechnung R-2026-0012.pdf", "Rechnung R-2026-0012.pdf"),
    ("Prüfbericht Dachfläche Süd", "application/pdf", "Pruefbericht Dachflaeche Sued.pdf", "Prüfbericht Dachfläche Süd.pdf"),
    ('Foto "Nord"/Ost\\West\r\nX-Kopf: 1', "image/jpeg", "Foto Nord Ost West X-Kopf_ 1.jpg", "Foto Nord Ost West X-Kopf: 1.jpg"),
    ("", "application/pdf", "Unterlage.pdf", "Unterlage.pdf"),
    (None, "image/jpeg", "Unterlage.jpg", "Unterlage.jpg"),
    ("..", "application/pdf", "Unterlage.pdf", "Unterlage.pdf"),
    ("日本語", "application/pdf", "Unterlage.pdf", "日本語.pdf"),
])
def test_dateiname_aus_dem_titel(titel, typ, ascii_, voll):
    assert routen.dateiname(titel, typ) == (ascii_, voll)


def test_dateiname_hoechstens_100_zeichen_und_kopfzeile_lesbar():
    a, v = routen.dateiname("ä" * 300, "application/pdf")
    assert len(a) <= 2 * routen.DATEINAME_HOECHSTENS + 4 and len(v) == routen.DATEINAME_HOECHSTENS + 4
    for titel in ('a"b', "a\\b", "a\nb", "a\x00b", "a b"):
        a, v = routen.dateiname(titel, "image/jpeg")
        for zeichen in ('"', "\\", "\n", "\r", "\x00", " "):
            assert zeichen not in a and zeichen not in v, (titel, a, v)
        a.encode("latin-1")  # die Kopfzeile ist darstellbar


@pytest.mark.parametrize("name, typ", [("../../etc/passwd", "application/pdf"), ("a" * 64 + ".jpg", "application/pdf"),
                                       ("a" * 64 + ".pdf", "text/html"), ("A" * 64 + ".pdf", "application/pdf"), (None, "application/pdf")])
def test_unpassende_kopie_geht_nie_an_nginx(dienst, monkeypatch, name, typ):
    client, app = dienst
    db = app.app.state.db
    monkeypatch.setattr(db, "datei", lambda *a: ("ok", name, typ, 10, "Titel"))
    r = client.get("/datei/1", headers={**EIGEN, "Cookie": f"{routen.COOKIE}={pruefwerte.neuer_wert()}"})
    assert (r.status_code, r.json()) == (500, {"fehler": "technisch"}) and "x-accel-redirect" not in r.headers


def _zeilen(conf: str) -> list[str]:
    return [z.split("#")[0].strip() for z in conf.splitlines() if z.split("#")[0].strip()]


def test_internal_block_vollstaendig():
    """Nachtrag 3: internal, Ordner, feste Typen und default_type; genau der Satz der Schutz-Kopfzeilen des Dienstes, jede mit always -- die CSP der Datei
    ohne sandbox und ohne script-src; keine Kopfzeile, die nginx aus der Antwort des Dienstes übernimmt (sonst stünde sie doppelt da)."""
    block = nginx_attrappe.internal_block(NGINX)
    assert block["internal"] and block["typen"] == {"pdf": "application/pdf", "jpg": "image/jpeg"} and block["vorgabe"] == "application/octet-stream"
    conf = NGINX.read_text(encoding="utf-8")
    teil = conf[conf.index("location ^~ /_portal_dateien/ {"):]  # seit 1.11.47 mit ^~ (tests/test_v837_portal_pflicht_und_orte.py)
    teil = teil[:teil.index("\n    }") + 6]
    assert "alias /srv/dk-portal/dateien/;" in _zeilen(teil)
    assert len(re.findall(r"add_header", "\n".join(_zeilen(teil)))) == len(block["kopf"])  # jede add_header mit always
    eigene = {k.lower(): v for k, v in block["kopf"]}
    dienst_ = {k.decode(): v.decode() for k, v in schutz_kopfzeilen(True)}
    assert set(eigene) == set(dienst_), set(eigene) ^ set(dienst_)
    for name, wert in dienst_.items():
        assert eigene[name] == (CSP_DATEI if name == "content-security-policy" else wert), name
    assert "sandbox" not in eigene["content-security-policy"] and "script-src" not in eigene["content-security-policy"]
    assert not set(eigene) & set(nginx_attrappe.UEBERNOMMEN)


def test_protokoll_ohne_den_internen_weg():
    zeilen = _zeilen(NGINX.read_text(encoding="utf-8"))
    log = next(z for z in zeilen if z.startswith("log_format"))
    assert "$dkportal_pfad" in log and "$uri" not in log and "$request_uri" not in log and "$request " not in log and "$remote_addr" not in log
    conf = NGINX.read_text(encoding="utf-8")
    assert re.search(r'map \$request_uri \$dkportal_pfad \{\s*"~\^\(\?<pfad>\[\^\?\]\*\)" \$pfad;\s*\}', conf)


def test_einheit_des_portals_sieht_den_ordner_nicht():
    einheit = (ROOT / "scripts" / "server" / "erp-portal.service").read_text(encoding="utf-8")
    assert "InaccessiblePaths=/srv/dk-portal\n" in einheit.replace("\r\n", "\n")
    assert "/srv/dk-portal" not in "\n".join(z for z in einheit.splitlines() if z.startswith(("BindPaths", "BindReadOnlyPaths", "ReadWritePaths")))


def test_attrappe_nur_lokal(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_ENV", "production")
    with pytest.raises(RuntimeError):
        nginx_attrappe.Attrappe(1, tmp_path)


# --- PostgreSQL ---------------------------------------------------------------------------------------------------------------------------------------

PDF = b"%PDF-1.4\n% erfunden fuer test_v825\n" + b"0123456789" * 50 + b"\n%%EOF\n"


@pytest.fixture(scope="module")
def pg_modul(tmp_path_factory):
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_dat_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    erp = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    portal = None
    try:
        with erp.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(erp)
        with erp.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)
            c.execute(text("INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', true, now())"))
            c.execute(text("INSERT INTO document_categories (key, label, created_at, updated_at) VALUES ('test-dat', 'Sonstiges', now(), now())"))
        portal = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema} -crole={TESTROLLE}", "application_name": schema},
                               pool_size=3, max_overflow=3, pool_timeout=10)
        app = erzeugen(_einstellungen(), engine=portal, pruefen=False)
        server, faden, port = _uvicorn(app, "h11")
        ordner = tmp_path_factory.mktemp("kopien")
        os.environ.setdefault("ERP_ENV", "test")
        attrappe = nginx_attrappe.Attrappe(port, ordner)
        attrappe.starten()
        try:
            yield SimpleNamespace(w=Welt(erp, schema), erp=erp, schema=schema, port=port, nginx=attrappe.port, ordner=ordner)
        finally:
            attrappe.beenden()
            server.should_exit = True
            faden.join(15)
    finally:
        if portal is not None:
            portal.dispose()
        erp.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture
def welt(pg_modul):
    pg_modul.erp_sql = pg_modul.w.erp
    pg_modul.w.erp("DELETE FROM portal_bremsen")
    return pg_modul


def _kunde(p):
    kid, _zugang, link = p.w.kunde(link=f"dat-{uuid.uuid4().hex[:8]}")
    return kid, p.w.angemeldet(link)


def _freigabe(p, kunde, *, titel="Plan Süd", typ="application/pdf", inhalt=PDF):
    did = p.w.erp("INSERT INTO customer_documents (customer_id, category, category_id, original_filename, stored_filename, file_size, uploaded_at) "
                  "VALUES (:k, 'Sonstiges', (SELECT id FROM document_categories WHERE key = 'test-dat'), 'geheimer-name.pdf', :s, 1, now()) RETURNING id",
                  k=kunde, s=uuid.uuid4().hex)[0][0]
    name = uuid.uuid4().hex + uuid.uuid4().hex + (".pdf" if typ == "application/pdf" else ".jpg")
    (p.ordner / name).write_bytes(inhalt)
    fid = p.w.erp("INSERT INTO portal_freigaben (customer_id, art, quelle, quelle_id, titel, datum, freigegeben_am, freigegeben_von_name, kopie_name, "
                  "kopie_typ, kopie_groesse, kopie_bereit_am) VALUES (:k, 'dokument', 'customer_documents', :d, :t, DATE '2026-11-26', now(), 'Büro', :n, "
                  ":y, :g, now()) RETURNING id", k=kunde, d=did, t=titel, n=name, y=typ, g=len(inhalt))[0][0]
    return fid, name


def _anfrage(port, methode, pfad, *, keks=None, koerper=None, kopf=None):
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        k = {"Host": "kunde.test", **EIGEN, **(kopf or {})}
        if keks:
            k["Cookie"] = f"{routen.COOKIE}={keks}"
        daten = None
        if koerper is not None:
            import json
            daten = json.dumps(koerper).encode()
            k["Content-Type"] = "application/json"
        verbindung.request(methode, pfad, body=daten, headers=k)
        antwort = verbindung.getresponse()
        return SimpleNamespace(status=antwort.status, kopf={a.lower(): b for a, b in antwort.getheaders()}, koerper=antwort.read(),
                               alle=antwort.getheaders())
    finally:
        verbindung.close()


def _anfordern(p, keks, fid, port=None):
    return _anfrage(port or p.nginx, "POST", "/api/datei/anfordern", keks=keks, koerper={"freigabe": fid})


def _zugriffe(p):
    return p.w.erp("SELECT count(*) FROM portal_zugriffe")[0][0]


def test_pg_anfordern_dann_ansehen_und_herunterladen_ueber_nginx(welt):
    p = welt
    kunde, keks = _kunde(p)
    fid, name = _freigabe(p, kunde)
    r = _anfordern(p, keks, fid)
    assert (r.status, r.koerper) == (200, b'{"stand":"angefordert"}')
    assert p.w.erp("SELECT aktion, ergebnis, objekt_id FROM portal_zugriffe ORDER BY id DESC LIMIT 1")[0] == ("datei_angefordert", "ok", fid)
    for pfad, art in ((f"/datei/{fid}", "inline"), (f"/datei/{fid}/herunterladen", "attachment")):
        r = _anfrage(p.nginx, "GET", pfad, keks=keks)
        assert r.status == 200 and r.koerper == PDF, (r.status, r.koerper[:100])
        k = r.kopf
        assert k["content-type"] == "application/pdf" and k["cache-control"] == "private, no-store" and k["content-length"] == str(len(PDF))
        assert k["content-disposition"] == f"{art}; filename=\"Plan Sued.pdf\"; filename*=UTF-8''Plan%20S%C3%BCd.pdf"
        assert k["content-security-policy"] == CSP_DATEI and k["strict-transport-security"] == "max-age=31536000"
        assert k["x-content-type-options"] == "nosniff" and k["x-frame-options"] == "DENY" and k["referrer-policy"] == "no-referrer"
        assert k["cross-origin-resource-policy"] == "same-origin" and "permissions-policy" in k
        assert "x-accel-redirect" not in k and name not in str(r.alle) and "geheimer-name" not in str(r.alle)
        assert sum(1 for a, _b in r.alle if a.lower() == "content-security-policy") == 1  # die des Dienstes ist weg
    kopf = _anfrage(p.nginx, "HEAD", f"/datei/{fid}", keks=keks)
    assert kopf.status == 200 and kopf.koerper == b"" and kopf.kopf["content-length"] == str(len(PDF))
    spanne = _anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks, kopf={"Range": "bytes=0-9"})
    assert spanne.status == 206 and spanne.koerper == PDF[:10] and spanne.kopf["content-range"] == f"bytes 0-9/{len(PDF)}"


def test_pg_beim_dienst_eine_leere_antwort_mit_x_accel_redirect_und_kein_get_schreibt(welt):
    p = welt
    kunde, keks = _kunde(p)
    fid, name = _freigabe(p, kunde, titel="Foto Dach", typ="image/jpeg", inhalt=b"\xff\xd8\xff\xe0jpeg")
    assert _anfordern(p, keks, fid).status == 200
    vorher = _zugriffe(p)
    for methode in ("GET", "HEAD"):
        r = _anfrage(p.port, methode, f"/datei/{fid}", keks=keks)
        assert r.status == 200 and r.koerper == b"" and r.kopf["x-accel-redirect"] == f"/_portal_dateien/{name}"
        assert r.kopf["content-type"] == "image/jpeg" and r.kopf["content-disposition"].startswith('inline; filename="Foto Dach.jpg"')
        assert r.kopf["cache-control"] == "private, no-store" and "set-cookie" not in r.kopf
    assert _zugriffe(p) == vorher  # ein GET schreibt nichts


def test_pg_404_aussen_gleich(welt):
    """Ohne Anforderung, fremde Freigabe, unbekannte Nummer, zurückgenommen, Anforderung abgelaufen, andere Sitzung desselben Kunden: dieselbe Antwort."""
    p = welt
    kunde, keks = _kunde(p)
    fremd_kunde, fremd_keks = _kunde(p)
    fid, _ = _freigabe(p, kunde)
    fremd, _ = _freigabe(p, fremd_kunde)
    antworten = []
    antworten.append(_anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks))                       # ohne Anforderung
    antworten.append(_anfordern(p, keks, fremd))                                                 # fremd
    antworten.append(_anfrage(p.nginx, "GET", f"/datei/{fremd}", keks=keks))
    antworten.append(_anfordern(p, keks, 987654))                                                # unbekannt
    antworten.append(_anfrage(p.nginx, "GET", "/datei/987654", keks=keks))
    assert _anfordern(p, keks, fid).status == 200
    link2 = f"dat2-{uuid.uuid4().hex[:8]}"
    p.w.erp("UPDATE portal_zugaenge SET link_sha256 = :l WHERE customer_id = :k", l=pruefwerte.link(link2), k=kunde)
    keks2 = p.w.angemeldet(link2)
    antworten.append(_anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks2))                      # andere Sitzung
    p.w.erp("UPDATE portal_zugriffe SET zeitpunkt = zeitpunkt - interval '31 minutes' WHERE objekt_id = :f", f=fid)
    antworten.append(_anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks))                       # abgelaufen
    assert _anfordern(p, keks, fid).status == 200 and _anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks).status == 200
    p.w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :f", f=fid)
    antworten.append(_anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks))                       # zurückgenommen
    antworten.append(_anfordern(p, keks, fid))
    for r in antworten:
        assert (r.status, r.koerper) == (404, b'{"fehler":"nicht_gefunden"}'), (r.status, r.koerper)
        assert "x-accel-redirect" not in r.kopf
    assert _anfrage(p.nginx, "GET", f"/datei/{fremd}", keks=fremd_keks).status == 404  # der fremde Kunde hat sie nicht angefordert


def test_pg_ohne_sitzung_401_und_bremse_429(welt):
    p = welt
    kunde, keks = _kunde(p)
    fid, _ = _freigabe(p, kunde)
    r = _anfrage(p.nginx, "GET", f"/datei/{fid}")
    assert (r.status, r.koerper) == (401, b'{"fehler":"sitzung"}') and "set-cookie" not in r.kopf
    r = _anfordern(p, None, fid)
    assert r.status == 401 and "max-age=0" in r.kopf.get("set-cookie", "").lower()
    r = _anfrage(p.nginx, "GET", f"/datei/{fid}", keks=pruefwerte.neuer_wert())
    assert r.status == 401
    zugang = p.w.erp("SELECT id FROM portal_zugaenge WHERE customer_id = :k", k=kunde)[0][0]
    p.w.erp("INSERT INTO portal_bremsen (schluessel, fenster_beginn, zaehler) VALUES (:s, date_trunc('hour', now() at time zone 'utc'), 300)",
            s=f"datei:z:{zugang}")
    r = _anfordern(p, keks, fid)
    assert r.status == 429 and b'"bremse"' in r.koerper and int(r.kopf["retry-after"]) >= 60


@pytest.mark.parametrize("pfad, koerper", [
    ("/api/datei/anfordern", {"freigabe": "1"}), ("/api/datei/anfordern", {"freigabe": 0}), ("/api/datei/anfordern", {"freigabe": 2 ** 31}),
    ("/api/datei/anfordern", {"freigabe": 1, "kunde": 2}), ("/api/datei/anfordern", {}), ("/api/datei/anfordern", {"freigabe": True}),
    ("/datei/abc", None), ("/datei/0", None), ("/datei/99999999999", None), ("/datei/-1/herunterladen", None),
])
def test_pg_eingaben_422(welt, pfad, koerper):
    p = welt
    _kunde_, keks = _kunde(p)
    r = _anfrage(p.port, "POST" if koerper is not None else "GET", pfad, keks=keks, koerper=koerper)
    assert (r.status, r.koerper) == (422, b'{"fehler":"eingabe"}'), (r.status, r.koerper)


def test_pg_unpassender_name_in_der_datenbank_500_ohne_x_accel(welt):
    p = welt
    kunde, keks = _kunde(p)
    fid, _ = _freigabe(p, kunde)
    p.w.erp("UPDATE portal_freigaben SET kopie_name = '../../home/tobias/erp/.env' WHERE id = :f", f=fid)
    assert _anfordern(p, keks, fid).status == 200
    r = _anfrage(p.nginx, "GET", f"/datei/{fid}", keks=keks)
    assert (r.status, r.koerper) == (500, b'{"fehler":"technisch"}') and "x-accel-redirect" not in r.kopf


def test_pg_interner_weg_von_aussen_404(welt):
    p = welt
    kunde, keks = _kunde(p)
    _fid, name = _freigabe(p, kunde)
    for pfad in (f"/_portal_dateien/{name}", f"/_portal_dateien/{name}?x=1", "/_portal_dateien/"):
        r = _anfrage(p.nginx, "GET", pfad, keks=keks)
        assert r.status == 404 and PDF not in r.koerper, pfad


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_pg_angriffe_gegen_einen_echten_uvicorn(welt, http_art):
    """Jede Methode auf jeden neuen Weg, ohne Sitzung, mit fremdem Host und von fremder Seite: nichts erreicht etwas, nichts landet im Protokoll."""
    pytest.importorskip(http_art)
    p = welt
    kunde, _keks = _kunde(p)
    fid, _ = _freigabe(p, kunde)
    motor = create_engine(PG_URL, connect_args={"options": f"-csearch_path={p.schema} -crole={TESTROLLE}"})
    app = erzeugen(_einstellungen(), engine=motor, pruefen=False)
    server, faden, port = _uvicorn(app, http_art)
    vorher = _zugriffe(p)
    try:
        erreicht = []
        for methode in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "ERFUNDEN"):
            for pfad in (f"/datei/{fid}", f"/datei/{fid}/herunterladen", "/api/datei/anfordern", "/_portal_dateien/x.pdf"):
                for kopf in ({"Host": "kunde.test"}, {"Host": "kunde.test", **EIGEN}, {"Host": "app.dachkonzepte.gmbh", **EIGEN}, {},
                             {"Host": "kunde.test", "Origin": "https://app.dachkonzepte.gmbh", "Sec-Fetch-Site": "same-site",
                              "Cookie": f"{routen.COOKIE}={pruefwerte.neuer_wert()}"}):
                    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
                    try:
                        verbindung.putrequest(methode, pfad, skip_host=True, skip_accept_encoding=True)
                        for k, v in kopf.items():
                            verbindung.putheader(k, v)
                        verbindung.putheader("Content-Length", "0")
                        verbindung.endheaders()
                        antwort = verbindung.getresponse()
                        antwort.read()
                        if antwort.status < 400 or antwort.getheader("x-accel-redirect"):
                            erreicht.append((methode, pfad, kopf.get("Host"), antwort.status))
                    finally:
                        verbindung.close()
        assert erreicht == []
        assert _zugriffe(p) == vorher
    finally:
        server.should_exit = True
        faden.join(15)
        motor.dispose()
