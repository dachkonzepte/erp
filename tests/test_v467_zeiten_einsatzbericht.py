"""Seit 1.9.42 (Stufe 4, R1 Nachrunde, Punkt 1): Zeiten im Einsatzbericht -- ein Bericht je Tag, mit der Unterschrift gespeichert.

    Regel          alle Zeiten auf dem Auftrag des Berichts am Tag des Berichts, alle Personen, mit und ohne Plantafel
                   (app/service_reports.py::zeiten_am_tag()); ersetzt 1.9.37 (Plantafel-Abschnitt, eingeteilte Personen)
    gespeichert    mit der Unterschrift (sign_report()) als „Tag, Person, von–bis, Stunden“, eine laufende Zeit als „läuft seit HH:MM“ ohne
                   Stunden; danach zeigen Seite (GET …/zeiten) und PDF nur diesen Stand
    alt            vor 1.9.42 unterschrieben, ohne gespeicherten Stand: wie vor 1.9.37 alle Zeiten des Auftrags mit Tätigkeit
    dieselben      Berichtsseite und PDF zeigen dieselben Zeilen (zeiten_des_berichts())
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app import service_reports as service_reports_module
from app.models import ServiceReport, TimeEntry
from app.routers.service_reports import router as service_reports_router
from app.service_reports import create_report, sign_report
from app.time_tracking import create_manual_entry, start_timer, stop_timer
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _make_order_for_report
from tests.test_v224_field_view import make_employee, make_slot_for_individual, make_team

TAG = date(2026, 10, 14)


@pytest.fixture
def welt(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
    db = threaded_db_session
    order = _make_order_for_report(db)
    mia, tom = make_employee(db, "M-1", "Mia", "Monteurin"), make_employee(db, "M-2", "Tom", "Monteur")
    zeit = start_timer(db, employee_id=mia.id, order_id=order.id, started_at=datetime.combine(TAG, time(6, 45)), activity="Abdichtung")
    stop_timer(db, zeit.id, ended_at=datetime.combine(TAG, time(12)))
    create_manual_entry(db, employee_id=tom.id, order_id=order.id, work_date=TAG, hours=Decimal("3"), activity="Rinne")
    create_manual_entry(db, employee_id=mia.id, order_id=order.id, work_date=TAG - timedelta(days=1), hours=Decimal("2"), activity="Vortag")
    create_manual_entry(db, employee_id=mia.id, order_id=order.id, work_date=TAG + timedelta(days=1), hours=Decimal("1.5"), activity="Folgetag")
    return {"db": db, "order": order, "mia": mia, "tom": tom, "zeit": zeit.id,
            "client": router_test_client(db, service_reports_router)}


ZEILEN_AM_TAG = [
    {"tag": "2026-10-14", "person": "Mia Monteurin", "von": "06:45", "bis": "12:00", "stunden": "5.25", "laeuft": False},
    {"tag": "2026-10-14", "person": "Tom Monteur", "von": None, "bis": None, "stunden": "3.00", "laeuft": False},
]


def _bericht(w, **mehr):
    return create_report(w["db"], w["order"].id, "rapport", performed_at=TAG, description="Dach abgedichtet", **mehr)["id"]


def _unterschreiben(w, report_id):
    sign_report(w["db"], report_id, installer_signature_png_bytes=TINY_PNG, installer_signature_name="Mia Monteurin",
                customer_signature_png_bytes=TINY_PNG, customer_signature_name="Bernd Bauherr")


def _zeiten(w, report_id, client=None):
    antwort = (client or w["client"]).get(f"/api/service-reports/{report_id}/zeiten")
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _pdf(w, report_id):
    antwort = w["client"].get(f"/api/service-reports/{report_id}/pdf")
    assert antwort.status_code == 200, antwort.text
    return _extract_pdf_text(antwort.content)


def test_alle_zeiten_am_tag_alle_personen(welt):
    """Angriff: Zeiten vom Vortag und Folgetag desselben Auftrags gehören nicht in den Bericht / Gegenprobe: die Zeit des Kollegen am
    Berichtstag schon (ohne Beginn und Ende: „–“)."""
    z = _zeiten(welt, _bericht(welt))
    assert (z["art"], z["tag"], z["zeilen"]) == ("aktuell", "2026-10-14", ZEILEN_AM_TAG)


def test_mit_plantafel_dieselbe_regel(welt):
    """Ein Plantafel-Abschnitt nur für Mia ändert nichts: der Bezug zur Plantafel entfällt (bis 1.9.41 fehlte Tom dann im PDF)."""
    make_slot_for_individual(welt["db"], welt["order"], make_team(welt["db"], "K-1", "Kolonne 1"), welt["mia"], TAG, TAG)
    assert _zeiten(welt, _bericht(welt))["zeilen"] == ZEILEN_AM_TAG


def test_unterschrift_speichert_den_stand(welt):
    """Angriff: nach der Unterschrift eine Zeit am Berichtstag buchen und eine ändern -- Seite und PDF des unterschriebenen Berichts
    bleiben / Gegenprobe: ein unsignierter Bericht desselben Tages zeigt beides."""
    db = welt["db"]
    bericht = _bericht(welt)
    _unterschreiben(welt, bericht)
    vorher_seite, vorher_pdf = _zeiten(welt, bericht), _pdf(welt, bericht)
    assert (vorher_seite["art"], vorher_seite["zeilen"]) == ("gespeichert", ZEILEN_AM_TAG)

    create_manual_entry(db, employee_id=welt["tom"].id, order_id=welt["order"].id, work_date=TAG, hours=Decimal("2.75"))
    db.get(TimeEntry, welt["zeit"]).hours = Decimal("6.5")
    db.commit()
    assert _zeiten(welt, bericht) == vorher_seite
    nachher_pdf = _pdf(welt, bericht)
    assert b"2,75" not in nachher_pdf and b"6,50" not in nachher_pdf and b"5,25" in nachher_pdf
    assert nachher_pdf.split(b"Zeiten am")[1][:400] == vorher_pdf.split(b"Zeiten am")[1][:400]

    entwurf = _zeiten(welt, _bericht(welt))
    assert ("6.50", "2.75") == (entwurf["zeilen"][0]["stunden"], entwurf["zeilen"][-1]["stunden"])
    assert len(entwurf["zeilen"]) == 3


def test_laufende_zeit_beim_unterschreiben(welt):
    """Läuft beim Unterschreiben eine Zeit am Berichtstag: Zeile „läuft seit HH:MM“ ohne Stunden, so gespeichert -- auch nach dem Stopp."""
    db = welt["db"]
    laufend = start_timer(db, employee_id=welt["tom"].id, order_id=welt["order"].id, started_at=datetime.combine(TAG, time(13)))
    bericht = _bericht(welt)
    _unterschreiben(welt, bericht)
    zeile = {"tag": "2026-10-14", "person": "Tom Monteur", "von": "13:00", "bis": None, "stunden": None, "laeuft": True}
    assert _zeiten(welt, bericht)["zeilen"][1] == zeile
    stop_timer(db, laufend.id, ended_at=datetime.combine(TAG, time(15)))
    assert _zeiten(welt, bericht)["zeilen"][1] == zeile
    assert b"seit 13:00" in _pdf(welt, bericht)


def test_alter_bericht_ohne_stand_wie_vor_1937(welt):
    """Ein vor 1.9.42 unterschriebener Bericht (ohne gespeicherten Stand): Seite und PDF wie vor 1.9.37 -- alle Zeiten des Auftrags, mit
    Tätigkeit, auch Vortag und Folgetag; nichts rückwirkend geändert."""
    db = welt["db"]
    bericht = _bericht(welt)
    _unterschreiben(welt, bericht)
    db.get(ServiceReport, bericht).time_rows_json = None
    db.commit()
    z = _zeiten(welt, bericht)
    assert z["art"] == "alt"
    assert sorted((x["tag"], x["person"], x["taetigkeit"], x["stunden"]) for x in z["zeilen"]) == [
        ("2026-10-13", "Mia Monteurin", "Vortag", "2.00"), ("2026-10-14", "Mia Monteurin", "Abdichtung", "5.25"),
        ("2026-10-14", "Tom Monteur", "Rinne", "3.00"), ("2026-10-15", "Mia Monteurin", "Folgetag", "1.50")]
    text = _pdf(welt, bericht)
    assert b"Erfasste Zeiten" in text and b"Mitarbeiter" in text and b"Zeiten am" not in text
    assert [s in text for s in (b"2,00", b"5,25", b"3,00", b"1,50", b"Vortag", b"Folgetag")] == [True] * 6


def test_seite_und_pdf_dieselben_zeilen(welt):
    bericht = _bericht(welt)
    _unterschreiben(welt, bericht)
    zeilen, text = _zeiten(welt, bericht)["zeilen"], _pdf(welt, bericht)
    assert b"Zeiten am 14.10.2026" in text and b"Person" in text
    for z in zeilen:
        assert z["person"].encode() in text and f"{Decimal(z['stunden']):.2f}".replace(".", ",").encode() in text
        for uhrzeit in (z["von"], z["bis"]):
            assert uhrzeit is None or uhrzeit.encode() in text
    assert [s in text for s in (b"2,00", b"1,50", b"Vortag", b"Folgetag", b"Abdichtung")] == [False] * 5


def test_monteurin_eigener_und_fremder_bericht(router_test_client, welt):
    """Die Monteurin sieht in ihrem eigenen Bericht die Zeilen aller Personen des Tages (wie im PDF dieses Berichts) / einen fremden
    Bericht nicht (403)."""
    eigener = _bericht(welt, created_by_employee_id=welt["mia"].id)
    fremder = _bericht(welt, created_by_employee_id=welt["tom"].id)
    make_slot_for_individual(welt["db"], welt["order"], make_team(welt["db"], "K-2", "Kolonne 2"), welt["mia"], TAG, TAG)
    monteurin = router_test_client(welt["db"], service_reports_router, role="field", employee_id=welt["mia"].id)
    assert _zeiten(welt, eigener, monteurin)["zeilen"] == ZEILEN_AM_TAG
    assert monteurin.get(f"/api/service-reports/{fremder}/zeiten").status_code == 403
