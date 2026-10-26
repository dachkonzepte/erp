"""Version 1.9.93 (Stufe 4, R5a, Punkt 6): Kleinigkeiten.

    Einsatzkarte   „Heute“ nennt den Auftrag mit „Nummer · Titel“ (heute.einsaetze() trägt den Titel, die Karte zeigt auftragTitel(k)) -- zwei
                   Aufträge am selben Objekt unterscheidet der Titel
    /mobil         das Büro bekommt „„Heute“ gibt es nur in der Monteursansicht.“ (bis 1.9.92 „Die Einsätze …“, der Reiter heißt „Heute“)
    Meine Zeiten   ein Büro-Konto bekommt "buero" und damit nicht die rote Zeile „… wende dich an das Büro.“; Nachtragen und Ändern nur, wer
                   Zeiten bucht (Büro – Auftrag liest nur, seit 1.9.89)
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.heute import einsaetze
from app.permissions import NUR_MONTEURSANSICHT
from app.routers import field_view as field_view_router
from tests.test_v471_heute_server import _einsatz, welt  # noqa: F401  (Fixture)

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_einsatz_traegt_den_titel(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"] - timedelta(days=1), welt["heute"] + timedelta(days=1))], [welt["mia"]])
    karte = einsaetze(welt["db"], welt["mia"].id, heute=welt["heute"])[0]
    assert (karte["order_number"], karte["title"]) == (welt["order"].order_number, "Wartung")


def test_einsatzkarte_zeigt_nummer_und_titel():
    """Die Karte zeigt den Auftrag über auftragTitel() aus _auftrag_text.html (dieselbe Stelle wie Dialog und Auswahl)."""
    quelle = (VORLAGEN / "mobil.html").read_text(encoding="utf-8")
    karte = re.search(r"function einsatzKarte\(k\)\{(.*?)\n  \}", quelle, flags=re.S).group(1)
    assert "<p class=\"einsatz-auftrag\">'+esc(auftragTitel(k))+'</p>" in karte


def test_buero_auf_mobil_bekommt_heute_statt_einsaetze(welt):  # noqa: F811
    assert NUR_MONTEURSANSICHT == "„Heute“ gibt es nur in der Monteursansicht."
    client = welt["client"](welt["db"], field_view_router.router, role="buero_finanzen", employee_id=welt["mia"].id)
    antwort = client.get("/api/field-view/today")
    assert (antwort.status_code, antwort.json()["detail"]) == (403, NUR_MONTEURSANSICHT)


@pytest.mark.parametrize("rolle, buero, nachtragen", [("field", False, True), ("buero_auftrag", True, False),
                                                      ("buero_finanzen", True, True), ("admin", True, True)])
def test_meine_zeiten_kennt_das_buero(welt, rolle, buero, nachtragen):  # noqa: F811
    client = welt["client"](welt["db"], field_view_router.router, role=rolle, employee_id=welt["mia"].id)
    d = client.get("/api/field-view/meine-zeiten").json()
    assert (d["buero"], d["nachtragen_erlaubt"]) == (buero, nachtragen)


def test_meine_zeiten_ohne_rote_zeile_fuers_buero():
    quelle = (VORLAGEN / "mobil_zeiten.html").read_text(encoding="utf-8")
    assert "ladeHinweis(d.auftraege.length||d.buero?'':'Keine eigenen Aufträge im Zeitraum gefunden. Fehlt ein Einsatz, wende dich an das Büro.')" in quelle
