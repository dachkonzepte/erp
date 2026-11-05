"""Version 1.9.215 (L1a Stufe 6, Punkt 4): je Zeile der Zuordnung einer von drei Fällen -- Festlegung 1.9.175 Nr. 5 neu gefasst.

    Kennzeichen leer                     nicht exportiert
    Kennzeichen gesetzt, Lohnart leer    exportiert, Stunden ohne Lohnart (UU, FE)
    beides gesetzt                       exportiert mit Lohnart

Die Regel „zum Kennzeichen gehört eine Lohnart“ entfällt (bis 1.9.214 nur am Kalendertag ohne Lohnart, dort nicht exportiert). „Wirkt“ sagt je
Zeile den Fall. Eine Art geht ihrer Kategorie vor, sobald sie ein Kennzeichen hat (Festlegung 1.9.169 Nr. 2, bis 1.9.214: eine Lohnart). Die
Monatszeile bleibt bis L1b ein eigener Fall (Befund 1.9.217).
"""

from datetime import date
from pathlib import Path

import pytest

from app.lohnarten import fest, kalender, liste, speichern, wirkt, zuordnung
from app.routers import time_backoffice as time_backoffice_router

TAG = date(2026, 12, 7)


def _wirkt(db, schluessel):
    return {z["schluessel"]: z["wirkt"] for z in liste(db)}[schluessel]


@pytest.mark.parametrize("schluessel", ["kategorie:unbezahlt", "art:fortbildung", "kalender:heiligabend", "feiertag"])  # leer: eine Art wie ihre (leere) Kategorie
def test_drei_faelle_in_wirkt(db_session, schluessel):
    db = db_session
    speichern(db, schluessel, None, None, False)
    assert _wirkt(db, schluessel).endswith("nicht exportiert")
    speichern(db, schluessel, "XY", None, False)
    assert _wirkt(db, schluessel) == "XY – exportiert, Stunden ohne Lohnart"
    speichern(db, schluessel, "XY", "1234", False)
    assert _wirkt(db, schluessel) == "XY / 1234 – exportiert mit Lohnart"


def test_ohne_kennzeichen_nicht_exportiert(db_session):
    assert wirkt(None) == "nicht exportiert"
    speichern(db_session, "arbeit", None, None, False)
    assert fest(db_session, "arbeit") is None


def test_kennzeichen_ohne_lohnart_wird_exportiert(db_session):
    db = db_session
    speichern(db, "kategorie:unbezahlt", "UB", None, False)
    w = zuordnung(db, "unbezahlt", None, TAG)
    assert (w["kennzeichen"], w["lohnart"]) == ("UB", None)
    speichern(db, "arbeit", "1", None, False)
    assert (fest(db, "arbeit")["kennzeichen"], fest(db, "arbeit")["lohnart"]) == ("1", None)
    assert kalender(db, "silvester") == {"kennzeichen": "UU", "lohnart": None, "schluessel": "kalender:silvester", "exportiert": True}


def test_berufsschule_fe_ohne_lohnart(db_session):
    """Die Werte des Lohnbüros (1.9.214) wirken: Berufsschule FE geht der Kategorie Fortbildung (leer) vor."""
    w = zuordnung(db_session, "fortbildung", "Berufsschule", TAG)
    assert (w["kennzeichen"], w["lohnart"], w["schluessel"]) == ("FE", None, "art:berufsschule")
    assert _wirkt(db_session, "art:berufsschule") == "FE – exportiert, Stunden ohne Lohnart"


def test_art_mit_kennzeichen_geht_der_kategorie_vor(db_session):
    """Festlegung 1.9.169 Nr. 2 neu gefasst: ein Kennzeichen genügt (bis 1.9.214 brauchte die Art eine Lohnart)."""
    db = db_session
    speichern(db, "art:sonderurlaub", "SU", None, False)
    w = zuordnung(db, "urlaub", "Sonderurlaub", TAG)
    assert (w["kennzeichen"], w["lohnart"]) == ("SU", None)
    speichern(db, "art:sonderurlaub", None, None, False)  # geleert: wieder wie die Kategorie
    w = zuordnung(db, "urlaub", "Sonderurlaub", TAG)
    assert (w["kennzeichen"], w["lohnart"]) == ("U", "8000")


def test_lohnart_ohne_kennzeichen_weiter_abgelehnt(db_session):
    with pytest.raises(ValueError, match="Zur Lohnart gehört ein Kennzeichen"):
        speichern(db_session, "kategorie:unbezahlt", None, "9000", False)


def test_monatszeile_bleibt_ein_eigener_fall(db_session):
    """Bis L1b möglich (nur Schlechtwetter, ohne Kennzeichen), von keiner Zeile genutzt -- Befund 1.9.217."""
    db = db_session
    speichern(db, "schlechtwetter:winter", None, "8110", True)
    assert _wirkt(db, "schlechtwetter:winter") == "Monatszeile 8110 – exportiert als eine Zeile je Monat"
    assert zuordnung(db, "schlechtwetter", None, TAG)["monatszeile"] is True


def test_schnittstelle_kennzeichen_ohne_lohnart(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, time_backoffice_router.router, role="buero_finanzen")
    r = client.put("/api/time-backoffice/lohnarten", json={"schluessel": "kategorie:unbezahlt", "kennzeichen": "ub", "lohnart": None, "monatszeile": False})
    assert r.status_code == 200, r.text
    assert {z["schluessel"]: z["wirkt"] for z in r.json()}["kategorie:unbezahlt"] == "UB – exportiert, Stunden ohne Lohnart"


def test_seite_nennt_die_drei_faelle():
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert ("Ohne Kennzeichen wird eine Zeile nicht exportiert; mit Kennzeichen ohne Lohnart stehen die Stunden ohne Lohnart in der Datei "
            "(z. B. UU, FE); mit beidem mit Lohnart – „Wirkt“ sagt je Zeile, welcher Fall gilt.") in text
    assert "exportiert wird er erst mit Lohnart" not in text
