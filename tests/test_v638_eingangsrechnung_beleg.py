"""Version 1.9.238 (Stufe 6, R3b, Punkt 0a): Beleg einer Eingangsrechnung hochladen und entfernen mit derselben Reihenfolge und Sperre wie das
Speichern seit 1.9.232.

    Sperre       Hochladen und Entfernen sperren zuerst die Zeile; ist die Rechnung inzwischen gelöscht, 404 und keine Datei liegt herum
    Antwort      entsteht vor dem Commit, aus dem Stand, der festgeschrieben wird -- ein Löschen danach macht kein 500
    Dateien      der alte Beleg fällt erst nach dem Commit weg; scheitert das Speichern, bleibt der alte und der neue fällt weg

Bis 1.9.237 legte der Router die neue Datei ohne Sperre ab und löschte dabei schon die alte, das Entfernen löschte die Datei vor dem Commit, beide
lasen die Rechnung nach dem Commit neu (Bericht R3a, Abschnitt 3 d).
"""

import io
import threading

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from starlette.datastructures import Headers, UploadFile

import app.incoming_invoices as eingang
from app import incoming_invoice_documents as docs_module
from app.models import IncomingInvoice
from app.routers.incoming_invoices import (
    delete_incoming_invoice, delete_incoming_invoice_document, router as incoming_router, upload_incoming_invoice_document,
)
from tests.test_v375_rechnungen_sperren import _bis, _vorbereiten, _wartet_auf_sperre, pg  # noqa: F401  (pg ist eine Fixture)
from tests.test_v399_teil_updates_geld import _eingangsrechnung


@pytest.fixture
def ablage(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    return tmp_path


def _dateien(ordner):
    return sorted(p.name for p in ordner.iterdir())


def _datei(name="beleg.pdf", daten=b"%PDF-1.4 neu"):
    return UploadFile(file=io.BytesIO(daten), filename=name, headers=Headers({"content-type": "application/pdf"}))


def test_hochladen_ersetzt_den_alten_beleg_erst_nach_dem_commit(threaded_db_session, ablage):
    db = threaded_db_session
    invoice_id, _ = _eingangsrechnung(db)
    erster = eingang.set_invoice_document(db, invoice_id, original_filename="alt.pdf", data=b"%PDF alt")
    assert erster["has_document"] and len(_dateien(ablage)) == 1
    alt = _dateien(ablage)[0]
    zweiter = eingang.set_invoice_document(db, invoice_id, original_filename="neu.pdf", data=b"%PDF neu")
    assert zweiter["document_original_name"] == "neu.pdf"
    assert _dateien(ablage) == [db.get(IncomingInvoice, invoice_id).document_filename] != [alt]


def test_scheitert_das_hochladen_bleibt_der_alte_beleg(threaded_db_session, ablage, monkeypatch):
    db = threaded_db_session
    invoice_id, _ = _eingangsrechnung(db)
    eingang.set_invoice_document(db, invoice_id, original_filename="alt.pdf", data=b"%PDF alt")
    alt = _dateien(ablage)

    def kaputt(*_a, **_k):
        raise RuntimeError("Antwort scheitert vor dem Commit")
    monkeypatch.setattr(eingang, "invoice_to_dict", kaputt)
    with pytest.raises(RuntimeError):
        eingang.set_invoice_document(db, invoice_id, original_filename="neu.pdf", data=b"%PDF neu")
    db.expire_all()
    assert _dateien(ablage) == alt  # der neue fällt weg, der alte bleibt
    assert (db.get(IncomingInvoice, invoice_id).document_filename, db.get(IncomingInvoice, invoice_id).document_original_name) == (alt[0], "alt.pdf")


def test_scheitert_das_entfernen_bleibt_der_beleg(threaded_db_session, ablage, monkeypatch):
    db = threaded_db_session
    invoice_id, _ = _eingangsrechnung(db)
    eingang.set_invoice_document(db, invoice_id, original_filename="alt.pdf", data=b"%PDF alt")
    alt = _dateien(ablage)

    def kaputt(*_a, **_k):
        raise RuntimeError("Antwort scheitert vor dem Commit")
    monkeypatch.setattr(eingang, "invoice_to_dict", kaputt)
    with pytest.raises(RuntimeError):
        eingang.remove_invoice_document(db, invoice_id)
    db.rollback()
    db.expire_all()
    assert _dateien(ablage) == alt
    assert db.get(IncomingInvoice, invoice_id).document_filename == alt[0]


def test_unbekannte_rechnung_404_ohne_datei(threaded_db_session, router_test_client, ablage):
    client = router_test_client(threaded_db_session, incoming_router, role="buero_finanzen")
    antwort = client.post("/api/incoming-invoices/99999/document", files={"file": ("beleg.pdf", b"%PDF", "application/pdf")})
    assert antwort.status_code == 404, antwort.text
    assert eingang.set_invoice_document(threaded_db_session, 99999, original_filename="x.pdf", data=b"%PDF") is None
    assert _dateien(ablage) == []


def _gleichzeitig(Session, erste, zweite, halt_name, halt_an, monkeypatch, modul_attr):
    """erste hält an halt_an (Funktion in eingang, nach ihrer Sperre aufgerufen), bis zweite nachweislich auf die Sperre wartet."""
    echt = getattr(eingang, modul_attr)
    gesperrt, weiter = threading.Event(), threading.Event()

    def angehalten(*a, **k):
        if threading.current_thread().name == halt_name:
            gesperrt.set()
            weiter.wait(timeout=30)
        return echt(*a, **k)
    monkeypatch.setattr(eingang, modul_attr, angehalten)
    ergebnis = {}
    s1, s2 = Session(), Session()

    def laufen(name, s, aktion):
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
    t1 = threading.Thread(name=halt_name, target=laufen, args=("erste", s1, erste))
    t2 = threading.Thread(name="zweite", target=laufen, args=("zweite", s2, zweite))
    t1.start()
    assert gesperrt.wait(timeout=10)
    wartet = _wartet_auf_sperre(s2)
    t2.start()
    _bis(wartet, "die zweite Aktion wartet auf die Sperre der Rechnung")
    weiter.set()
    t1.join(timeout=30)
    t2.join(timeout=30)
    return ergebnis


def test_pg_hochladen_waehrend_des_loeschens_404_und_keine_datei(pg, ablage, monkeypatch):  # noqa: F811
    """Das Löschen hält die Sperre (angehalten beim Löschen seiner Datei); das Hochladen wartet an der Sperre und findet danach keine Rechnung mehr:
    404, keine Datei bleibt liegen. Bis 1.9.237: 500 (das UPDATE fand die Zeile nicht mehr) und die neue Datei blieb liegen."""
    Session, _ = pg
    invoice_id = _vorbereiten(Session, lambda s: _eingangsrechnung(s)[0])
    ergebnis = _gleichzeitig(Session, lambda s: delete_incoming_invoice(invoice_id, db=s, _role=None),
                             lambda s: upload_incoming_invoice_document(invoice_id, file=_datei(), db=s, _role=None),
                             "loeschen", None, monkeypatch, "delete_document_file")
    assert ergebnis["erste"] == {"deleted": True}, ergebnis
    assert isinstance(ergebnis["zweite"], HTTPException) and ergebnis["zweite"].status_code == 404, ergebnis
    assert _dateien(ablage) == []


def test_pg_hochladen_dann_loeschen_kein_500(pg, ablage, monkeypatch):  # noqa: F811
    """Das Hochladen hält die Sperre (angehalten bei der Antwort), das Löschen wartet. Liest das Hochladen nach seinem Commit neu, wartet es dort, bis
    das Löschen fertig ist (alte Reihenfolge = immer 500) -- es antwortet aber aus dem Stand vor dem Commit: 200 mit Beleg, danach löscht das Löschen
    Rechnung und Datei."""
    Session, _ = pg
    invoice_id = _vorbereiten(Session, lambda s: _eingangsrechnung(s)[0])
    echt_laden = eingang._load
    festgeschrieben, geloescht = threading.Event(), threading.Event()
    s_beobachtet = []

    def laden(db, iid):
        if threading.current_thread().name == "hochladen" and festgeschrieben.is_set():
            _bis(geloescht.is_set, "das Löschen nach dem Commit des Hochladens")
        return echt_laden(db, iid)
    monkeypatch.setattr(eingang, "_load", laden)
    echt_settings = eingang.load_incoming_invoice_settings
    gesperrt, weiter = threading.Event(), threading.Event()

    def einstellungen(db):
        if threading.current_thread().name == "hochladen":
            if not s_beobachtet:
                s_beobachtet.append(db)
                event.listen(db, "after_commit", lambda _s: festgeschrieben.set())
            gesperrt.set()
            weiter.wait(timeout=30)
        return echt_settings(db)
    monkeypatch.setattr(eingang, "load_incoming_invoice_settings", einstellungen)
    ergebnis = {}
    s1, s2 = Session(), Session()

    def laufen(name, s, aktion, fertig=None):
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
            if fertig is not None:
                fertig.set()
    t1 = threading.Thread(name="hochladen", target=laufen,
                          args=("hochladen", s1, lambda s: upload_incoming_invoice_document(invoice_id, file=_datei(), db=s, _role=None)))
    t2 = threading.Thread(target=laufen, args=("loeschen", s2, lambda s: delete_incoming_invoice(invoice_id, db=s, _role=None), geloescht))
    t1.start()
    assert gesperrt.wait(timeout=10)
    wartet = _wartet_auf_sperre(s2)
    t2.start()
    _bis(wartet, "das Löschen wartet auf die Sperre der Rechnung")
    weiter.set()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not isinstance(ergebnis["hochladen"], Exception), ergebnis
    assert ergebnis["hochladen"]["has_document"] is True
    assert ergebnis["loeschen"] == {"deleted": True}, ergebnis
    assert _vorbereiten(Session, lambda s: s.get(IncomingInvoice, invoice_id)) is None
    assert _dateien(ablage) == []


def test_pg_entfernen_waehrend_des_loeschens_404(pg, ablage, monkeypatch):  # noqa: F811
    """Das Löschen hält die Sperre, das Entfernen des Belegs wartet und findet danach keine Rechnung mehr: 404. Bis 1.9.237: das Entfernen löschte die
    Datei ohne Sperre und vor dem Commit, das UPDATE fand die Zeile nicht mehr -- 500."""
    Session, _ = pg

    def anlegen(s):
        iid = _eingangsrechnung(s)[0]
        eingang.set_invoice_document(s, iid, original_filename="alt.pdf", data=b"%PDF alt")
        return iid
    invoice_id = _vorbereiten(Session, anlegen)
    ergebnis = _gleichzeitig(Session, lambda s: delete_incoming_invoice(invoice_id, db=s, _role=None),
                             lambda s: delete_incoming_invoice_document(invoice_id, db=s, _role=None),
                             "loeschen", None, monkeypatch, "delete_document_file")
    assert ergebnis["erste"] == {"deleted": True}, ergebnis
    assert isinstance(ergebnis["zweite"], HTTPException) and ergebnis["zweite"].status_code == 404, ergebnis
    assert _dateien(ablage) == []
