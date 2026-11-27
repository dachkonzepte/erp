"""Version 1.11.38 (Stufe P2c, Teil 3): was die Karte „Im Portal“ und „vor dem Einladen“ vom Server bekommen (app/portal_freigaben.py::stand()).

    Zahlen      je Art, was der Kunde sieht oder gleich sieht (sichtbar, wird vorbereitet) -- nicht gescheitert, ruhend oder zurückgenommen; in der
                Reihenfolge der Arten, Einzahl und Mehrzahl („1 Rechnung“, „2 Fotos“), zusammen als ein Text; die Zahl am Reiter
    Gruppe      wie das Portal (P2-10): Auftragsnummer und Adresse des Objekts, nie der Projekttitel

Die Seite (auch: ohne Modul kein Reiter und keine Anfrage) prüft scripts/klicktest_kundenportal_im_portal.py.
"""

from __future__ import annotations

from datetime import datetime

from app import portal_freigaben as pf
from app.models import PortalFreigabe
from tests.test_v829_portal_regeln import EMAIL, Regeln, r  # noqa: F401 -- r ist die Fixture der Regeln


def _bereit(r, fid):
    f = r.db.get(PortalFreigabe, fid)
    f.kopie_name, f.kopie_typ, f.kopie_bereit_am = f"{fid:064d}.pdf", "application/pdf", datetime(2026, 11, 27)
    r.db.commit()


def test_zahlen_je_art_nur_was_der_kunde_sieht(r):
    rechnungen = [r.rechnung() for _ in range(2)]
    for i in rechnungen:
        r.versand("rechnung", i.id)
    r.anwenden()
    fotos = r.fotos(r.projekt(r.a), 3)  # eigener Auftrag (die Nummer des Auftrags aus Regeln ist vergeben)
    r.freigeben(r.a, "service_report_photos", fotos)
    dok = r.freigeben(r.a, "customer_documents", [r.dokument(r.a).id]).json()["neu"][0]
    _bereit(r, dok)
    gescheitert = r.freigeben(r.a, "customer_documents", [r.dokument(r.a).id]).json()["neu"][0]
    f = r.db.get(PortalFreigabe, gescheitert)
    f.kopie_fehler = "abbruch"
    r.db.commit()
    zurueck = r.freigeben(r.a, "customer_documents", [r.dokument(r.a).id]).json()["neu"][0]
    r.client.post(r.url(r.a, f"/{zurueck}/zuruecknehmen"), json={})
    stand = r.client.get(r.url(r.a)).json()
    assert [(z["art"], z["anzahl"], z["text"]) for z in stand["zahlen"]] == [("rechnung", 2, "2 Rechnungen"), ("foto", 3, "3 Fotos"),
                                                                             ("dokument", 1, "1 Dokument")]
    assert stand["zahlen_text"] == "2 Rechnungen · 3 Fotos · 1 Dokument" and stand["anzahl_sichtbar"] == 6


def test_ohne_freigaben_leer(r):
    stand = r.client.get(r.url(r.a)).json()
    assert (stand["zahlen"], stand["zahlen_text"], stand["anzahl_sichtbar"]) == ([], "", 0)


def test_ruhend_zaehlt_nicht(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)
    r.anwenden()
    assert r.client.get(r.url(r.a)).json()["zahlen_text"] == "1 Rechnung"
    r.p.archived = True
    r.db.commit()
    stand = r.client.get(r.url(r.a)).json()
    assert stand["zahlen_text"] == "" and stand["eintraege"][0]["zustand"] == "ruht"


def test_jede_art_hat_ein_und_mehrzahl():
    assert set(pf.ART_MEHRZAHL) == set(pf.ART_TEXT) and all(pf.ART_MEHRZAHL[a] != pf.ART_TEXT[a] for a in pf.ART_TEXT)


def test_gruppe_wie_im_portal(r):
    i = r.rechnung()
    r.versand("rechnung", i.id)
    r.anwenden()
    d = r.freigeben(r.a, "customer_documents", [r.dokument(r.a).id])
    gruppen = {e["titel"]: (e["gruppe"], e["gruppe_unter"]) for e in d.json()["eintraege"]}
    # seit 1.11.43: „Auftrag <Nummer> · <Betreff>“, darunter die Adresse (Betreff = Titel des Auftrags, nie der Projekttitel)
    assert gruppen[next(t for t in gruppen if t.endswith(i.invoice_number))] == (f"Auftrag {r.o.order_number} · Dach", "Hafenweg 3, 12345 Musterstadt")
    assert "Interner Titel" not in str(gruppen)  # nie der Projekttitel (P2-10)
    assert pf.gruppe_text("A-1", "  ", None) == ("Auftrag A-1", "") and pf.gruppe_text("A-1", None, "Hafenweg 3") == ("Auftrag A-1", "Hafenweg 3")
    assert pf.gruppe_text(None, None, "Hafenweg 3") == ("Hafenweg 3", "ohne bestimmten Auftrag")
    assert pf.gruppe_text(None, None, None) == ("Allgemeine Unterlagen", "ohne bestimmten Auftrag")

