"""Feste Fassung des Einsatzberichts beim Unterschreiben (seit 1.11.29, Nebenbefund N3 aus dem Bauplan P2).

Festlegungen 1.11.29 (Gegenproben in docs/archiv/gegenproben-portal.md, „1.11.29“):
1. Die Unterschrift legt im selben Commit das PDF als feste Fassung in die Ablage (Art „einsatzbericht“, Dokument-ID = Bericht) und vermerkt sie am
   Bericht (ServiceReport.pdf_document_id).
2. Nach der Unterschrift kommt der Download aus der Ablage (X-DK-Ablage), nie neu erzeugt; verändert oder fehlend 409 bzw. 410.
3. Scheitert das PDF oder die Ablage, ist nichts gespeichert -- kein Status, keine Unterschrift, keine Unterschriftsbilder, kein Eintrag in der Ablage.
4. Die feste Fassung steht fest (genau einmal von leer auf die Ablage).
5. Bestand (vor 1.11.29 unterschrieben, ohne Fassung): wie bisher bei jedem Abruf neu erzeugt, ein Abruf legt nichts ab; ein Entwurf hat wie bisher
   kein PDF.
6. Ein Einsatzbericht wird über das Versandprotokoll weder versendet noch zugestellt; er gehört dort zu seinem Projekt.
7. Zwei gleichzeitige Unterschriften ergeben eine Unterschrift und eine Fassung (Sperre der Berichtszeile, nur PostgreSQL).
"""

import hashlib
import os
import stat
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import service_report_pdf as service_report_pdf_module
from app import service_reports as service_reports_module
from app.database import Base
from app.dispatch_documents import dispatch_document, document_filter, project_id_of
from app.models import ArchiveImmutableError, EmailDispatch, SentDocument, ServiceReport
from app.routers.service_reports import router as service_reports_router
from app.sent_documents import SENT_DOCUMENT_ROOT, read_sent_document, store_sent_document
from app.service_reports import FESTE_FASSUNG_GESCHEITERT, create_report, sign_report
from tests.test_v213_inspection_items import TINY_PNG, _make_order_for_report
from tests.test_v375_rechnungen_sperren import _run

TAG = date(2026, 10, 14)



@pytest.fixture
def welt(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
    db = threaded_db_session
    order = _make_order_for_report(db)
    return {"db": db, "order": order, "sigs": tmp_path / "sigs", "client": router_test_client(db, service_reports_router)}


def _bericht(w) -> int:
    return create_report(w["db"], w["order"].id, "rapport", performed_at=TAG, description="Dach abgedichtet")["id"]


def _unterschreiben(db, report_id):
    return sign_report(db, report_id, installer_signature_png_bytes=TINY_PNG, installer_signature_name="Mia Monteurin",
                       customer_signature_png_bytes=TINY_PNG, customer_signature_name="Bernd Bauherr")


def _unterschreiben_router(w, report_id):
    import base64
    bild = "data:image/png;base64," + base64.b64encode(TINY_PNG).decode()
    return w["client"].post(f"/api/service-reports/{report_id}/sign", json={
        "installer_signature_png_base64": bild, "installer_signature_name": "Mia Monteurin",
        "customer_signature_png_base64": bild, "customer_signature_name": "Bernd Bauherr"})


def _ablage(db, report_id):
    return db.scalars(select(SentDocument).where(SentDocument.document_type == "einsatzbericht",
                                                 SentDocument.document_id == report_id).order_by(SentDocument.id)).all()


def test_unterschrift_legt_feste_fassung_ab(welt):
    """Festlegung 1: Unterschrift -> genau eine Fassung in der Ablage, am Bericht vermerkt, Prüfsumme stimmt, ein PDF."""
    db, rid = welt["db"], _bericht(welt)
    antwort = _unterschreiben_router(welt, rid)
    assert antwort.status_code == 200, antwort.text
    db.expire_all()
    report = db.get(ServiceReport, rid)
    fassungen = _ablage(db, rid)
    assert [f.id for f in fassungen] == [report.pdf_document_id]
    fassung = fassungen[0]
    inhalt = read_sent_document(fassung)
    assert inhalt.startswith(b"%PDF-") and hashlib.sha256(inhalt).hexdigest() == fassung.sha256
    assert (fassung.document_number, fassung.filename) == (welt["order"].order_number,
                                                          f"Einsatzbericht_{welt['order'].order_number}_{rid}.pdf".replace("/", "-"))
    assert report.status == "unterschrieben"


def test_download_kommt_aus_der_ablage(welt, monkeypatch):
    """Festlegung 2: nach der Unterschrift die abgelegten Bytes, auch wenn der Renderer heute scheitern würde (Gegenprobe der Herkunft);
    ein Entwurf hat wie bisher kein PDF (400)."""
    db, rid = welt["db"], _bericht(welt)
    entwurf = welt["client"].get(f"/api/service-reports/{rid}/pdf")
    assert entwurf.status_code == 400 and "unterschriebene" in entwurf.json()["detail"], entwurf.text
    _unterschreiben(db, rid)
    fassung = _ablage(db, rid)[0]

    def kaputt(*a, **k):
        raise RuntimeError("Renderer darf nach der Unterschrift nicht mehr laufen")
    monkeypatch.setattr(service_report_pdf_module, "build_service_report_pdf", kaputt)
    monkeypatch.setattr("app.routers.service_reports.build_service_report_pdf", kaputt)
    antwort = welt["client"].get(f"/api/service-reports/{rid}/pdf")
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["x-dk-ablage"] == str(fassung.id)
    assert hashlib.sha256(antwort.content).hexdigest() == fassung.sha256


def test_veraenderte_oder_fehlende_fassung_wird_nicht_neu_erzeugt(welt):
    """Festlegung 2: verändert 409, fehlend 410 -- kein stilles Neu-Erzeugen."""
    db, rid = welt["db"], _bericht(welt)
    _unterschreiben(db, rid)
    pfad = SENT_DOCUMENT_ROOT / _ablage(db, rid)[0].stored_filename
    os.chmod(pfad, stat.S_IWRITE | stat.S_IREAD)
    pfad.write_bytes(b"%PDF-1.4 verfaelscht")
    assert welt["client"].get(f"/api/service-reports/{rid}/pdf").status_code == 409
    pfad.unlink()
    assert welt["client"].get(f"/api/service-reports/{rid}/pdf").status_code == 410


def test_pdf_scheitert_nichts_gespeichert(welt, monkeypatch):
    """Festlegung 3: scheitert das PDF, bleibt der Bericht Entwurf ohne Unterschrift, ohne Bilder auf der Platte, ohne Eintrag in der Ablage;
    danach gelingt dieselbe Unterschrift."""
    db, rid = welt["db"], _bericht(welt)

    def kaputt(*a, **k):
        raise RuntimeError("Renderer kaputt")
    monkeypatch.setattr(service_report_pdf_module, "build_service_report_pdf", kaputt)
    antwort = _unterschreiben_router(welt, rid)
    assert antwort.status_code == 400 and antwort.json()["detail"] == FESTE_FASSUNG_GESCHEITERT
    db.expire_all()
    report = db.get(ServiceReport, rid)
    assert (report.status, report.signature_path, report.installer_signature_path, report.pdf_document_id) == ("entwurf", None, None, None)
    assert _ablage(db, rid) == []
    assert not welt["sigs"].exists() or list(welt["sigs"].iterdir()) == []
    monkeypatch.undo()
    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", welt["sigs"])
    assert _unterschreiben_router(welt, rid).status_code == 200
    assert len(_ablage(db, rid)) == 1


def test_feste_fassung_steht_fest(welt):
    """Festlegung 4: eine zweite Fassung am selben Bericht lehnt das Modell ab."""
    db, rid = welt["db"], _bericht(welt)
    _unterschreiben(db, rid)
    andere = store_sent_document(db, document_type="einsatzbericht", document_id=rid, document_number="X", filename="x.pdf",
                                 content=b"%PDF-1.4 andere", user_id=None, user_name="Test")
    db.get(ServiceReport, rid).pdf_document_id = andere.id
    with pytest.raises(ArchiveImmutableError):
        db.flush()
    db.rollback()


def test_entwurf_und_bestand_neu_erzeugt_ohne_ablage(welt, monkeypatch):
    """Festlegung 5: ein Bericht ohne Fassung (Bestand vor 1.11.29, hier nachgestellt) wird beim Abruf neu erzeugt und nicht nachträglich
    abgelegt."""
    db, rid = welt["db"], _bericht(welt)
    monkeypatch.setattr(service_reports_module, "_feste_fassung", lambda db, report: None)
    _unterschreiben(db, rid)
    assert db.get(ServiceReport, rid).pdf_document_id is None
    for _ in range(2):
        antwort = welt["client"].get(f"/api/service-reports/{rid}/pdf")
        assert antwort.status_code == 200 and antwort.content.startswith(b"%PDF-") and "x-dk-ablage" not in antwort.headers
    assert _ablage(db, rid) == []
    assert db.scalar(select(func.count()).select_from(SentDocument)) == 0


def test_nicht_zustellbar_aber_im_projekt(welt):
    """Festlegung 6: weder Versand noch Zustellung; Projekt und Filter des Versandprotokolls kennen die Art."""
    db, rid = welt["db"], _bericht(welt)
    _unterschreiben(db, rid)
    with pytest.raises(ValueError, match="über das Versandprotokoll versendet oder zugestellt"):
        dispatch_document(db, "einsatzbericht", rid)
    assert project_id_of(db, "einsatzbericht", rid) == welt["order"].project_id
    bedingung = document_filter(project_id=welt["order"].project_id)
    assert "einsatzbericht" in str(bedingung.compile(compile_kwargs={"literal_binds": True}))
    assert db.scalar(select(func.count()).select_from(EmailDispatch)) == 0


def test_zweite_unterschrift_abgelehnt(welt):
    db, rid = welt["db"], _bericht(welt)
    _unterschreiben(db, rid)
    with pytest.raises(ValueError, match="bereits unterschrieben"):
        _unterschreiben(db, rid)
    assert len(_ablage(db, rid)) == 1


@pytest.mark.parametrize("utc, berlin", [(datetime(2026, 1, 15, 10, 5), "15.01.2026 11:05"), (datetime(2026, 7, 15, 10, 5), "15.07.2026 12:05")],
                         ids=["winter", "sommer"])
def test_feste_fassung_zeigt_die_unterschrift_in_berliner_zeit(welt, monkeypatch, utc, berlin):
    """Seit 1.11.32 (Vorgabe des Betriebs): die feste Fassung zeigt die Zeit der Unterschrift in Berliner Zeit -- Winter UTC+1, Sommer UTC+2. Die
    Unterschrift läuft zur festen Uhrzeit (UTC, wie datetime.utcnow() speichert); geprüft wird das PDF aus der Ablage, nicht ein neu erzeugtes."""
    from tests.test_v213_inspection_items import _extract_pdf_text

    class FesteZeit(datetime):
        @classmethod
        def utcnow(cls):
            return utc
    monkeypatch.setattr(service_reports_module, "datetime", FesteZeit)
    db, rid = welt["db"], _bericht(welt)
    _unterschreiben(db, rid)
    antwort = welt["client"].get(f"/api/service-reports/{rid}/pdf")
    assert antwort.status_code == 200 and "x-dk-ablage" in antwort.headers
    text_ = _extract_pdf_text(antwort.content)
    assert text_.count(f"{berlin} Uhr".encode()) == 2, text_  # Monteur und Kunde
    assert f"{utc:%d.%m.%Y %H:%M} Uhr".encode() not in text_


# ---------------------------------------------------------------------------
# PostgreSQL: zwei Unterschriften gleichzeitig (Festlegung 7)
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(tmp_path, monkeypatch):
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from app.grunddaten import anlegen

    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
    schema = f"pgtest_bericht_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, pool_size=6, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            order = _make_order_for_report(setup)
            rid = create_report(setup, order.id, "rapport", performed_at=TAG, description="Dach abgedichtet")["id"]
        finally:
            setup.close()
        yield Session, rid
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_postgresql_zwei_unterschriften_gleichzeitig_eine_fassung(pg):
    """Festlegung 7: die zweite wartet auf die Sperre der Berichtszeile und bekommt „bereits unterschrieben“; genau eine Fassung."""
    Session, rid = pg

    def zweite(s):
        s.get(ServiceReport, rid)  # wie der Router: der Bericht ist vorher geladen (alter Stand)
        return _unterschreiben(s, rid)
    _, ergebnis = _run(Session, lambda s: _unterschreiben(s, rid)["id"], zweite)
    assert isinstance(ergebnis, ValueError) and "bereits unterschrieben" in str(ergebnis), ergebnis
    s = Session()
    try:
        fassungen = _ablage(s, rid)
        assert [f.id for f in fassungen] == [s.get(ServiceReport, rid).pdf_document_id]
    finally:
        s.close()
