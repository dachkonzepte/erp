"""Version 1.11.33 (Stufe P2b, Bauplan P2, B2 „Weg B“, B5, B6, Nachtrag 3–4): Kopien der freigegebenen Unterlagen im Ordner des Portals.

    Ohne Datenbank   jede Quelle aus FREIGABE_QUELLEN hat ihren Weg in quelle_lesen(); die Fehlerwörter des Moduls sind genau KOPIE_FEHLER; die Migration
                     a7c3e9f1d2b4 trägt den Weckruf und die Prüfung wörtlich
    PostgreSQL       (ein Schema für die Datei, je Test eigene Kunden, Freigaben je Test geleert, die Ablagen des ERP in einem Wegwerf-Ordner):
                     je Zeile der Matrix (test_v822) eine echte Datei -> Kopie: PDF byte-gleich, Foto neu kodiert ohne Metadaten, Name zufällig mit Endung,
                     Prüfsumme und Größe an der Zeile, im Portal sichtbar; Rücknahme, Ruhen (Kundenwechsel) und Kunde im Archiv -> Kopie weg, zurück -> neu;
                     jedes Fehlerwort einmal, ohne zweiten Versuch, ohne Inhalt im Protokoll; voller Lauf: Waisen, alte Teil-Dateien und fehlende Dateien,
                     fremde Dateien bleiben; ein Ordner einer anderen Datenbank wird nicht angefasst; Zeitgrenze je Durchgang; Rücknahme während des
                     Kodierens; Weckruf nur bei Freigabe und Rücknahme; der Postbote legt auf den Weckruf an und entfernt; ein Fehler am Ordner beendet ihn
                     nicht
"""

import io
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import portal_kopien
from app import portal_postbote as postbote
from app.models import portal_in
from app.portal import weckruf, werte
from tests.test_v822_portal_unterlagen_matrix import ZEILEN, Bau, _freigabe, _ids, _kunde, welt  # noqa: F401  (welt ist eine Fixture)

ROOT = Path(__file__).resolve().parents[1]
GEHEIM = b"GEHEIM-ORT-IM-FOTO"


# --- ohne Datenbank -----------------------------------------------------------------------------------------------------------------------------------

def test_jede_quelle_hat_einen_weg_und_die_woerter_passen():
    quelltext = (ROOT / "app" / "portal_kopien.py").read_text(encoding="utf-8")
    rumpf = quelltext.split("def quelle_lesen", 1)[1].split("\ndef ", 1)[0]
    for quelle in werte.FREIGABE_QUELLEN:
        assert f'"{quelle}"' in rumpf, quelle
    woerter = set(re.findall(r'QuelleFehlt\("(\w+)"\)', quelltext)) | set(re.findall(r'return "(\w+)"', quelltext))
    woerter |= set(re.findall(r'"(\w+)" if e\.status', quelltext)) | set(portal_kopien.KIND_WORT.values()) | {"nicht_lesbar"}
    assert woerter == set(werte.KOPIE_FEHLER), woerter ^ set(werte.KOPIE_FEHLER)


def test_migration_traegt_weckruf_und_pruefung_woertlich():
    import importlib.util
    pfad = next((ROOT / "alembic" / "versions").glob("a7c3e9f1d2b4_*.py"))
    spec = importlib.util.spec_from_file_location("migration_kopien", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.ANWEISUNGEN == weckruf.ANWEISUNGEN
    assert modul.CHECKS == {"ck_portal_freigabe_kopie_fehler": portal_in("kopie_fehler", werte.KOPIE_FEHLER, leer=True)}
    assert modul.down_revision == "f2b7d4a9c1e3"
    assert "SET search_path = pg_catalog, @SCHEMA@, pg_temp" in weckruf.ANWEISUNGEN[0] and "FOR EACH STATEMENT" in weckruf.ANWEISUNGEN[1]
    assert weckruf.ANWEISUNGEN[2] == "REVOKE ALL ON FUNCTION portal_freigabe_geweckt() FROM PUBLIC"
    assert weckruf.KANAL == portal_kopien.KANAL


# --- PostgreSQL ---------------------------------------------------------------------------------------------------------------------------------------

def _pdf() -> bytes:
    return b"%PDF-1.4\n% erfunden " + uuid.uuid4().hex.encode() + b"\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


def _jpeg() -> bytes:
    exif = Image.Exif()
    exif[0x010E] = GEHEIM.decode()
    aus = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(aus, "JPEG", exif=exif.tobytes(), comment=GEHEIM)
    return aus.getvalue()


FOTO_ZEILEN = {"service_report_photos", "defect_files"}


@pytest.fixture
def w(welt, tmp_path, monkeypatch):
    """Die Welt aus test_v822 mit den Ablagen des ERP in einem Wegwerf-Ordner und einem leeren Ordner für die Kopien; Freigaben geleert."""
    import app.acceptances
    import app.customer_documents
    import app.project_documents
    import app.property_documents
    import app.sent_documents
    import app.service_report_photos
    erp = tmp_path / "erp"
    for modul, name, sub in ((app.sent_documents, "SENT_DOCUMENT_ROOT", "sent"), (app.acceptances, "ACCEPTANCE_FILE_ROOT", "acc"),
                             (app.service_report_photos, "PHOTO_ROOT", "fotos"), (app.customer_documents, "CUSTOMER_ROOT", "kunden"),
                             (app.project_documents, "PROJECT_ROOT", "projekte"), (app.property_documents, "PROPERTY_ROOT", "objekte")):
        (erp / sub).mkdir(parents=True)
        monkeypatch.setattr(modul, name, erp / sub)
    welt.erp("DELETE FROM portal_freigaben")
    welt.erp("DELETE FROM portal_bremsen")
    welt.ordner = tmp_path / "kopien"
    welt.ordner.mkdir()
    welt.roots = {sub: erp / sub for sub in ("sent", "acc", "fotos", "kunden", "projekte", "objekte")}
    return welt


def _schreiben(pfad: Path, inhalt: bytes) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(inhalt)


def _ablage_echt(w, doc_id: int, inhalt: bytes) -> None:
    import hashlib
    stored = w.erp("SELECT stored_filename FROM sent_documents WHERE id = :i", i=doc_id)[0][0]
    _schreiben(w.roots["sent"] / stored, inhalt)
    w.erp("UPDATE sent_documents SET sha256 = :s, size_bytes = :g WHERE id = :i", s=hashlib.sha256(inhalt).hexdigest(), g=len(inhalt), i=doc_id)


def _neue_ablage(w, art: str, dok_id: int) -> int:
    return w.erp("INSERT INTO sent_documents (document_type, document_id, filename, stored_filename, size_bytes, sha256, created_at, created_by_name, "
                 "content_type) VALUES (:a, :d, 'x.pdf', :s, 1, :h, now(), 'Test', 'application/pdf') RETURNING id",
                 a=art, d=dok_id, s=f"2026/11/{uuid.uuid4().hex}.pdf", h="0" * 64)[0][0]


def echte_quelle(w, zeile: str, kunde: int, *, inhalt: bytes | None = None, ohne_datei=False):
    """Eine Quelle der Zeile (Bau aus test_v822) mit einer echten Datei in der Ablage des ERP. (Quelle, Inhalt)."""
    import hashlib
    q = Bau(w).bauen(zeile, kunde, kunde)
    inhalt = inhalt if inhalt is not None else (_jpeg() if zeile in FOTO_ZEILEN else _pdf())
    if ohne_datei:
        return q, inhalt
    if q.quelle == "sent_documents":
        _ablage_echt(w, q.id, inhalt)
    elif q.quelle == "invoices":
        doc = _neue_ablage(w, "rechnung", q.id)
        w.erp("UPDATE invoices SET pdf_document_id = :d WHERE id = :i", d=doc, i=q.id)
        _ablage_echt(w, doc, inhalt)
    elif q.quelle == "reminders":
        doc = _neue_ablage(w, "mahnung", q.id)
        w.erp("INSERT INTO email_dispatches (dispatch_key, message_ref, status, channel, document_type, document_id, to_recipients, subject, "
              "sent_document_id, created_at, created_by_name) VALUES (:k, :m, 'gesendet', 'smtp', 'mahnung', :d, 'kunde@example.invalid', 'Mahnung', :s, "
              "now(), 'Test')", k=f"test-{uuid.uuid4().hex}", m=str(uuid.uuid4()), d=q.id, s=doc)
        _ablage_echt(w, doc, inhalt)
    elif q.quelle == "service_reports":
        _ablage_echt(w, w.erp("SELECT pdf_document_id FROM service_reports WHERE id = :i", i=q.id)[0][0], inhalt)
    elif q.quelle in ("checklist_versions", "notice_letters"):
        _ablage_echt(w, w.erp(f"SELECT sent_document_id FROM {q.quelle} WHERE id = :i", i=q.id)[0][0], inhalt)
    elif q.quelle == "service_report_photos":
        _schreiben(w.roots["fotos"] / w.erp("SELECT file_path FROM service_report_photos WHERE id = :i", i=q.id)[0][0], inhalt)
    elif q.quelle in ("customer_documents", "project_documents", "property_documents"):
        eltern = {"customer_documents": ("customer_id", "kunden"), "project_documents": ("project_id", "projekte"),
                  "property_documents": ("property_id", "objekte")}[q.quelle]
        eltern_id, stored = w.erp(f"SELECT {eltern[0]}, stored_filename FROM {q.quelle} WHERE id = :i", i=q.id)[0]
        _schreiben(w.roots[eltern[1]] / str(eltern_id) / stored, inhalt)
    elif q.quelle in ("defect_files", "order_acceptance_files"):
        stored = w.erp(f"SELECT stored_filename FROM {q.quelle} WHERE id = :i", i=q.id)[0][0]
        _schreiben(w.roots["acc"] / stored, inhalt)
        w.erp(f"UPDATE {q.quelle} SET sha256 = :s, size_bytes = :g WHERE id = :i", s=hashlib.sha256(inhalt).hexdigest(), g=len(inhalt), i=q.id)
    else:
        raise AssertionError(q.quelle)
    return q, inhalt


def _abgleich(w, **kw):
    with Session(w.engine) as db:
        return portal_kopien.abgleich(db, w.ordner, **kw)


def _zeile(w, fid):
    return w.erp("SELECT kopie_name, kopie_typ, kopie_groesse, kopie_sha256, kopie_bereit_am, kopie_fehler FROM portal_freigaben WHERE id = :i", i=fid)[0]


def _dateien(w) -> set[str]:
    return {p.name for p in w.ordner.iterdir()} - {portal_kopien.BESITZER}


@pytest.mark.parametrize("zeile", ZEILEN)
def test_pg_kopie_je_zeile(w, zeile):
    import hashlib
    kunde, sitz = _kunde(w, "Kopie")
    q, inhalt = echte_quelle(w, zeile, kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    assert fid not in _ids(w, sitz)  # ohne Kopie nichts im Portal
    stand = _abgleich(w, voll=True)
    assert (stand.angelegt, stand.fehler, stand.entfernt) == (1, {}, 0), stand
    name, typ, groesse, sha, bereit, fehler = _zeile(w, fid)
    assert fehler is None and bereit is not None and portal_kopien.NAME.match(name), name
    datei = w.ordner / name
    daten = datei.read_bytes()
    assert len(daten) == groesse and hashlib.sha256(daten).hexdigest() == sha
    if zeile in FOTO_ZEILEN:
        assert typ == "image/jpeg" and name.endswith(".jpg") and GEHEIM not in daten and daten != inhalt
        assert Image.open(io.BytesIO(daten)).size == (64, 48)
    else:
        assert typ == "application/pdf" and name.endswith(".pdf") and daten == inhalt  # byte-gleich
    if os.name == "posix":
        assert datei.stat().st_mode & 0o777 == 0o640
    # seit 1.11.44: bei einem Foto dazu die Vorschau (tests/test_v834_portal_vorschau.py)
    vorschau = w.erp("SELECT kopie_vorschau FROM portal_freigaben WHERE id = :i", i=fid)[0][0]
    assert _dateien(w) == ({name, vorschau} if zeile in FOTO_ZEILEN else {name}) and (vorschau is None) == (zeile not in FOTO_ZEILEN)
    assert fid in _ids(w, sitz)
    assert _abgleich(w, voll=True).angelegt == 0  # nichts doppelt


def test_pg_ruecknahme_ruhen_und_archiv(w):
    kunde, sitz = _kunde(w, "Ruhen")
    anderer, _ = _kunde(w, "Anderer")
    q, _inhalt = echte_quelle(w, "invoices", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    _abgleich(w)
    erster = _zeile(w, fid)[0]
    # Ruhen: die Kette führt zu einem anderen Kunden -> Kopie weg (nicht nur im vollen Lauf), zurück -> neue Kopie mit neuem Namen
    w.erp("UPDATE invoices SET customer_id = :a WHERE id = :i", a=anderer, i=q.id)
    stand = _abgleich(w)
    assert stand.entfernt == 1 and _dateien(w) == set() and _zeile(w, fid)[:5] == (None,) * 5
    w.erp("UPDATE invoices SET customer_id = :k WHERE id = :i", k=kunde, i=q.id)
    assert _abgleich(w).angelegt == 1
    zweiter = _zeile(w, fid)[0]
    assert zweiter and zweiter != erster and _dateien(w) == {zweiter}
    # Kunde im Archiv -> weg; zurückgeholt -> neu
    w.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kunde)
    assert _abgleich(w).entfernt == 1 and _dateien(w) == set()
    w.erp("UPDATE customers SET archiviert_am = NULL WHERE id = :k", k=kunde)
    assert _abgleich(w).angelegt == 1 and fid in _ids(w, sitz)
    # Rücknahme: im Portal sofort weg (die Funktion), die Datei im nächsten Lauf
    w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :i", i=fid)
    assert fid not in _ids(w, sitz) and len(_dateien(w)) == 1
    assert _abgleich(w).entfernt == 1 and _dateien(w) == set() and _zeile(w, fid)[0] is None
    assert _abgleich(w, voll=True).angelegt == 0  # zurückgenommen bleibt ohne Kopie


@pytest.mark.parametrize("wort", ["fehlt", "pruefsumme", "zu_gross", "falscher_typ", "nicht_lesbar", "nicht_lesbar_rechte", "abbruch"])
def test_pg_fehler_je_wort_ohne_zweiten_versuch_und_ohne_inhalt(w, wort, monkeypatch, caplog):
    kunde, sitz = _kunde(w, "Fehler")
    zeile = "customer_documents"
    inhalt = {"falscher_typ": b"PK\x03\x04 kein PDF, ein Office-Dokument", "nicht_lesbar": b"\xff\xd8\xff\xe0" + b"kaputt" * 100}.get(wort)
    q, _ = echte_quelle(w, "invoices" if wort == "pruefsumme" else zeile, kunde, inhalt=inhalt, ohne_datei=(wort == "fehlt"))
    if wort == "pruefsumme":  # die Datei der Ablage wurde nach dem Ablegen verändert
        doc = w.erp("SELECT pdf_document_id FROM invoices WHERE id = :i", i=q.id)[0][0]
        stored = w.erp("SELECT stored_filename FROM sent_documents WHERE id = :i", i=doc)[0][0]
        (w.roots["sent"] / stored).write_bytes(_pdf())
    if wort == "zu_gross":
        monkeypatch.setattr(portal_kopien, "HOECHSTENS_BYTES", 10)
    if wort == "nicht_lesbar_rechte":
        def keine_rechte(*_a, **_k):
            raise PermissionError("keine Rechte")
        monkeypatch.setattr(portal_kopien, "quelle_lesen", keine_rechte)
    aufrufe = []

    def foto(daten):
        aufrufe.append(1)
        return "abbruch"
    if wort == "abbruch":
        q, _ = echte_quelle(w, "service_report_photos", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    with caplog.at_level(logging.WARNING, logger="app.portal_kopien"):
        stand = _abgleich(w, voll=True, **({"foto": foto} if wort == "abbruch" else {}))
    erwartet = "nicht_lesbar" if wort == "nicht_lesbar_rechte" else wort
    assert stand.fehler == {erwartet: 1} and stand.angelegt == 0, stand
    assert _zeile(w, fid)[5] == erwartet and _zeile(w, fid)[0] is None and _dateien(w) == set()
    assert fid not in _ids(w, sitz)
    assert f"Freigabe {fid}" in caplog.text and "Unterlage" not in caplog.text and "Fehler" not in caplog.text  # kein Titel, kein Kundenname
    assert _abgleich(w, voll=True, **({"foto": foto} if wort == "abbruch" else {})).fehler == {}  # kein zweiter Versuch
    assert len(aufrufe) == (1 if wort == "abbruch" else 0)


def test_pg_voller_lauf_waisen_teile_fremde_und_fehlende_dateien(w):
    kunde, _ = _kunde(w, "Voll")
    q, _ = echte_quelle(w, "project_documents", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    _abgleich(w)
    erster = _zeile(w, fid)[0]
    waise = "a" * 64 + ".pdf"
    (w.ordner / waise).write_bytes(b"%PDF-waise")
    alt, frisch = w.ordner / f".{'b' * 64}.pdf.teil", w.ordner / f".{'c' * 64}.jpg.teil"
    alt.write_bytes(b"x")
    frisch.write_bytes(b"x")
    vor_zwei_stunden = time.time() - 7200
    os.utime(alt, (vor_zwei_stunden, vor_zwei_stunden))
    (w.ordner / "notiz.txt").write_text("fremd")
    (w.ordner / erster).unlink()  # die Kopie einer bereiten Zeile fehlt
    assert _abgleich(w).waisen == 0  # nur der volle Lauf räumt
    stand = _abgleich(w, voll=True)
    assert (stand.nachgeholt, stand.angelegt, stand.waisen, stand.fremd) == (1, 1, 2, 1), stand
    neu = _zeile(w, fid)[0]
    assert neu != erster and _dateien(w) == {neu, frisch.name, "notiz.txt"}


def test_pg_ordner_einer_anderen_datenbank_bleibt_unberuehrt(w):
    kunde, _ = _kunde(w, "Fremd")
    q, _ = echte_quelle(w, "invoices", kunde)
    _freigabe(w, kunde, q, bereit=False)
    waise = w.ordner / ("d" * 64 + ".pdf")
    waise.write_bytes(b"%PDF-")
    with pytest.raises(portal_kopien.OrdnerFremd):  # Kopien, aber keine Kennung
        _abgleich(w, voll=True)
    (w.ordner / portal_kopien.BESITZER).write_text("spielwiese/public\n")
    with pytest.raises(portal_kopien.OrdnerFremd):
        _abgleich(w, voll=True)
    assert waise.exists() and _dateien(w) == {waise.name}
    waise.unlink()
    (w.ordner / portal_kopien.BESITZER).unlink()
    assert _abgleich(w, voll=True).angelegt == 1  # leer: die Kennung entsteht
    with Session(w.engine) as db:
        assert (w.ordner / portal_kopien.BESITZER).read_text(encoding="utf-8").strip() == portal_kopien.kennung(db) and w.schema in portal_kopien.kennung(db)


def test_pg_zeitgrenze_je_durchgang(w):
    kunde, _ = _kunde(w, "Zeit")
    for _ in range(3):
        q, _i = echte_quelle(w, "customer_documents", kunde)
        _freigabe(w, kunde, q, bereit=False)
    stand = _abgleich(w, sekunden=0)
    assert stand.mehr and stand.angelegt == 0
    stand = _abgleich(w)
    assert not stand.mehr and stand.angelegt == 3


def test_pg_ruecknahme_waehrend_des_kodierens(w):
    kunde, _ = _kunde(w, "Wettlauf")
    q, _ = echte_quelle(w, "service_report_photos", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)

    def foto(daten):
        w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :i", i=fid)
        return portal_kopien.foto_neu_kodieren(daten)
    stand = _abgleich(w, foto=foto)
    assert stand.angelegt == 0 and _zeile(w, fid)[0] is None and _zeile(w, fid)[5] is None and _dateien(w) == set()


def _weckrufe(w, schritte) -> list[int]:
    """Je Schritt (SQL auf derselben Verbindung, committet) die Zahl der Weckrufe dieser Verbindung (andere Testprozesse senden auf demselben Kanal)."""
    hoerer = w.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    sender = w.engine.connect()
    try:
        hoerer.exec_driver_sql(f"LISTEN {weckruf.KANAL}")
        roh = hoerer.connection.driver_connection
        pid = sender.execute(text("SELECT pg_backend_pid()")).scalar()
        sender.commit()
        zahlen = []
        for sql, werte_ in schritte:
            sender.execute(text(sql), werte_)
            sender.commit()
            zahlen.append(sum(1 for n in roh.notifies(timeout=1.0) if n.pid == pid))
        return zahlen
    finally:
        sender.close()
        hoerer.close()


def test_pg_weckruf_nur_bei_freigabe_und_ruecknahme(w):
    kunde, _ = _kunde(w, "Weckruf")
    q, _ = echte_quelle(w, "customer_documents", kunde)
    einfuegen = ("INSERT INTO portal_freigaben (customer_id, art, quelle, quelle_id, titel, datum, freigegeben_am, freigegeben_von_name) "
                 "VALUES (:k, 'dokument', :q, :i, 'Unterlage', DATE '2026-11-20', now(), 'Büro')", {"k": kunde, "q": q.quelle, "i": q.id})
    kopie = ("UPDATE portal_freigaben SET kopie_name = :n, kopie_typ = 'application/pdf', kopie_bereit_am = now() WHERE quelle_id = :i AND quelle = :q",
             {"n": "e" * 64 + ".pdf", "i": q.id, "q": q.quelle})
    fehler = ("UPDATE portal_freigaben SET kopie_fehler = 'abbruch' WHERE quelle_id = :i AND quelle = :q", {"i": q.id, "q": q.quelle})
    zurueck = ("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE quelle_id = :i AND quelle = :q",
               {"i": q.id, "q": q.quelle})
    assert _weckrufe(w, [einfuegen, kopie, fehler, zurueck]) == [1, 0, 0, 1]


def _laeuft(w, ordner, **kw):
    halt, fehler = threading.Event(), []

    def lauf():
        try:
            postbote.laufen(w.engine, halt=halt.is_set, nachsehen=30, aufraeumen_alle=3600, ordner=ordner, **kw)
        except Exception as e:  # pragma: no cover -- im Test sichtbar machen
            fehler.append(e)
    faden = threading.Thread(target=lauf, daemon=True)
    faden.start()
    return halt, faden, fehler


def _bis(bedingung, was, sicherheitsnetz=20.0):
    ende = time.monotonic() + sicherheitsnetz
    while not bedingung():
        assert time.monotonic() < ende, f"nach {sicherheitsnetz:.0f} s nicht: {was}"
        time.sleep(0.05)


def _sperre_gehalten(w) -> bool:
    return bool(w.erp("SELECT 1 FROM pg_locks WHERE locktype = 'advisory' AND classid = :k AND objsubid = 2 "
                      "AND objid = (hashtext(:s)::bigint & 4294967295)::oid", k=postbote.SPERRE, s=w.schema))


def test_pg_postbote_legt_auf_den_weckruf_an_und_entfernt(w):
    kunde, sitz = _kunde(w, "Postbote")
    q, _ = echte_quelle(w, "invoices", kunde)
    halt, faden, fehler = _laeuft(w, w.ordner)
    try:
        _bis(lambda: _sperre_gehalten(w) and (w.ordner / portal_kopien.BESITZER).exists(), "Postbote bereit, erster voller Lauf")
        fid = _freigabe(w, kunde, q, bereit=False)  # ohne Weckruf käme er erst nach 30 Sekunden
        _bis(lambda: _zeile(w, fid)[4] is not None, "Kopie angelegt")
        assert fid in _ids(w, sitz)
        w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Büro' WHERE id = :i", i=fid)
        _bis(lambda: _dateien(w) == set(), "Kopie entfernt")
    finally:
        halt.set()
        w.erp("SELECT pg_notify('portal_post', '')")  # aus dem Warten wecken
        faden.join(30)
    assert fehler == [] and not faden.is_alive()


def test_pg_fehler_am_ordner_beendet_den_postboten_nicht(w, caplog):
    with Session(w.engine) as db, caplog.at_level(logging.ERROR, logger="app.portal_postbote"):
        assert postbote.kopien(db, w.ordner / "gibt-es-nicht", voll=True) is False
    assert "Kopien nicht abgeglichen (FileNotFoundError)" in caplog.text
    (w.ordner / portal_kopien.BESITZER).write_text("andere/datenbank\n")
    with Session(w.engine) as db, caplog.at_level(logging.ERROR, logger="app.portal_postbote"):
        assert postbote.kopien(db, w.ordner, voll=True) is False
    assert "Kopien nicht abgeglichen (OrdnerFremd)" in caplog.text


def test_pg_postbote_ohne_ordner_meldet_es_und_laeuft(w, caplog):
    with caplog.at_level(logging.WARNING, logger="app.portal_postbote"):
        halt, faden, fehler = _laeuft(w, None)
        try:
            _bis(lambda: _sperre_gehalten(w), "Postbote bereit")
            _bis(lambda: "PORTAL_DATEIEN nicht gesetzt" in caplog.text, "Hinweis im Protokoll")
        finally:
            halt.set()
            w.erp("SELECT pg_notify('portal_post', '')")
            faden.join(30)
    assert fehler == [] and not faden.is_alive()


def test_pg_teil_datei_eines_abgebrochenen_schreibens_bleibt_nicht(w, monkeypatch):
    kunde, _ = _kunde(w, "Abbruch")
    q, _ = echte_quelle(w, "customer_documents", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)

    def kaputt(*_a, **_k):
        raise OSError("Platte voll")
    with monkeypatch.context() as m:  # nur dieses -- die Ablagen der Fixture bleiben umgelenkt
        m.setattr(portal_kopien.os, "replace", kaputt)
        with pytest.raises(OSError):
            _abgleich(w)
    assert _dateien(w) == set() and _zeile(w, fid)[0] is None and _zeile(w, fid)[5] is None  # kein Rest, kein Fehlerwort: nächster Lauf versucht es
    assert _abgleich(w).angelegt == 1


def test_pg_datum_der_kopie_aus_der_datenbank(w):
    kunde, _ = _kunde(w, "Zeit")
    q, _ = echte_quelle(w, "customer_documents", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    _abgleich(w)
    bereit, jetzt = _zeile(w, fid)[4], w.erp("SELECT portal_jetzt()")[0][0]
    assert abs(jetzt - bereit) < timedelta(minutes=1) and isinstance(bereit, datetime)


def test_pg_postbote_gibt_sperre_und_listen_am_ende_frei(w):
    """Nebenbefund 1.11.33: laufen() gab seine Verbindung mit Sperre und LISTEN an den Pool zurück -- ein zweiter Postbote derselben Engine hielt sich
    dann für überzählig. Seither am Ende freigegeben."""
    postbote.laufen(w.engine, halt=lambda: True, ordner=None)
    assert not _sperre_gehalten(w)
    postbote.laufen(w.engine, halt=lambda: True, ordner=None)  # ein zweiter in derselben Engine: keine AndererPostbote
