"""Version 1.9.219 (L1a Stufe 7, Punkt 2): der Hinweis zum Nummernkreis beruhigt nicht mehr oberhalb der genutzten Kreise.

    genutzt     00000–00099 sv-pflichtig Beschäftigte, 00100–00199 Minijobber, 00200–00299 Azubis (je Hundert wie die beiden ersten)
    darüber     „Die Personalnummer 91008 liegt außerhalb der vom Lohnbüro genannten Bereiche (genutzt: 00000–00299) – bitte prüfen.“
                (bis 1.9.218: „… liegt im Kreis Azubis (ab 00200).“) -- weiter nur ein Hinweis, keine Sperre
    Grenze      fest im Code, nicht aus den vergebenen Nummern: eine aus den Daten abgeleitete Grenze zöge jede Fehleingabe mit (Begründung
                berichtigt 1.9.229 -- die 91… der Tests sind erfundene Musternummern, auf dem Server steht keine)
"""

import pytest

from app.models import PersonalnummerVergabe
from app.routers import time_backoffice as time_backoffice_router
from app.time_backoffice import nummernkreis
from tests.test_v224_field_view import make_employee

AUSSERHALB = "Die Personalnummer {n} liegt außerhalb der vom Lohnbüro genannten Bereiche (genutzt: 00000–00299) – bitte prüfen."


@pytest.mark.parametrize("nummer, text", [
    ("00204", "Die Personalnummer 00204 liegt im Kreis Azubis (ab 00200)."),
    ("00299", "Die Personalnummer 00299 liegt im Kreis Azubis (ab 00200)."),
    ("00300", AUSSERHALB.format(n="00300")),
    ("91008", AUSSERHALB.format(n="91008")),
    ("99999", AUSSERHALB.format(n="99999")),
])
def test_grenze_der_genutzten_kreise(nummer, text):
    assert nummernkreis(nummer) == text


@pytest.fixture
def welt(threaded_db_session, router_test_client, fester_tag):
    db = threaded_db_session
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.commit()
    return {"db": db, "mia": mia, "client": router_test_client}


def test_ausserhalb_ist_keine_sperre(welt):
    """Gespeichert wird trotzdem, mit dem Hinweis -- auch wenn 91008 schon gemerkt (vergeben) ist wie aus Time 4."""
    db = welt["db"]
    db.add(PersonalnummerVergabe(nummer="91016", employee_id=welt["mia"].id))
    db.commit()
    r = welt["client"](db, time_backoffice_router.router, role="buero_finanzen").put(
        f"/api/time-backoffice/payroll-employees/{welt['mia'].id}", json={"datev_personnel_number": "91008"})
    assert (r.status_code, r.json()["datev_personnel_number"], r.json()["nummernkreis"]) == (200, "91008", AUSSERHALB.format(n="91008"))


def test_grenze_haengt_nicht_an_den_vergebenen_nummern(welt):
    """Die Sperrliste mit Nummern bis 91030 (wie aus Time 4) verschiebt die Grenze nicht."""
    db = welt["db"]
    db.add_all([PersonalnummerVergabe(nummer=n, employee_id=None) for n in ("00204", "91016", "91030")])
    db.commit()
    assert nummernkreis("91008") == AUSSERHALB.format(n="91008")


def test_pruefskript_zaehlt_ausserhalb():
    from tests.test_v590_pruefe_zeitregeln import _lauf, _person, db_session
    db = db_session()
    _person(db, "E-1", datev="00204")
    _person(db, "E-2", datev="91008")
    _person(db, "E-3", datev="00300")
    rc, zeilen = _lauf(db)
    assert "  Personalnummern je Kreis: sv-pflichtig Beschäftigte 0, Minijobber 0, Azubis 1, außerhalb 2" in zeilen
    assert not any("91008" in z for z in zeilen if z.startswith("  ! "))  # kein Befund


def test_seite_nennt_die_grenze():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "über 00299 sagt er, dass die Nummer außerhalb der genannten Bereiche liegt." in text
