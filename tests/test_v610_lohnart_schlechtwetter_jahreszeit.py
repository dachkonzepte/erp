"""Version 1.9.203 (Lohn L1a, Stufe 4, Punkt 2; Festlegung 1.9.169 Nr. 3): für die Kategorie Schlechtwetter gewinnt immer die Jahreszeit.

    zuordnung()   Schlechtwetter nach dem Datum (Winter 01.12.–31.03., sonst Sommer), ohne Blick auf die Art -- auch eine gespeicherte Zeile
                  „art:schlechtwetter“ oder eine Zeile einer Art, die zu jeder Kategorie passt („Sonstiges“), geht nicht mehr vor
    speichern()   eine Zuordnung für eine Art, die nur zu Schlechtwetter passt, wird abgelehnt (422 mit Meldung auf der Seite); leeren geht
    Altbestand    eine schon gespeicherte Zeile bleibt stehen (nicht still gelöscht), wird übergangen, die Liste sagt es, das Prüfskript nennt sie
                  als Befund (Rückgabe 1)

Bis 1.9.202 ging eine gespeicherte Zeile „art:schlechtwetter“ Winter und Sommer vor (gemeldet in den Gegenproben 1.9.197).
"""

from datetime import date
from pathlib import Path

import pytest

from app.lohnarten import NUR_JAHRESZEIT, liste, nur_jahreszeit, speichern, zuordnung
from app.models import LohnartZuordnung
from app.routers import time_backoffice as time_backoffice_router
from tests.test_v590_pruefe_zeitregeln import _lauf

ROOT = Path(__file__).resolve().parent.parent
WINTER, SOMMER = date(2026, 12, 7), date(2027, 6, 7)


def _altbestand(db, schluessel="art:schlechtwetter", kennzeichen="S", lohnart="8111"):
    """Eine Zeile, wie sie bis 1.9.202 über PUT …/lohnarten entstehen konnte -- direkt, am heutigen speichern() vorbei."""
    db.add(LohnartZuordnung(schluessel=schluessel, kennzeichen=kennzeichen, lohnart=lohnart, monatszeile=False))
    db.commit()


def _kurz(w):
    return None if w is None else (w["kennzeichen"], w["lohnart"], w["monatszeile"], w["schluessel"])


def test_nur_jahreszeit_erkennt_die_art():
    assert nur_jahreszeit("art:schlechtwetter") and nur_jahreszeit("art:Schlechtwetter")
    assert not any(nur_jahreszeit(s) for s in ("art:sonstiges", "art:weiterbildung", "art:kind krank", "schlechtwetter:winter",
                                                "kategorie:schlechtwetter", "", None))


def test_gespeicherte_art_wird_uebergangen(db_session):
    """Winter: WA / 8195 (seit 1.9.214, bis 1.9.213 die Monatszeile 8110) statt S / 8111; Sommer: nicht exportiert (die Zeile Sommer ist leer)
    -- die Zeile bleibt stehen."""
    db = db_session
    _altbestand(db)
    assert _kurz(zuordnung(db, "schlechtwetter", "Schlechtwetter", WINTER)) == ("WA", "8195", False, "schlechtwetter:winter")
    assert zuordnung(db, "schlechtwetter", "Schlechtwetter", SOMMER) is None
    zeile = db.query(LohnartZuordnung).filter_by(schluessel="art:schlechtwetter").one()
    assert (zeile.kennzeichen, zeile.lohnart) == ("S", "8111")


def test_auch_eine_art_fuer_jede_kategorie_nicht(db_session):
    """„Sonstiges“ passt zu jeder Kategorie: ihre Zuordnung gilt für Urlaub, bei Schlechtwetter gewinnt die Jahreszeit."""
    db = db_session
    speichern(db, "art:sonstiges", "X", "9999", False)
    assert _kurz(zuordnung(db, "urlaub", "Sonstiges", WINTER)) == ("X", "9999", False, "art:sonstiges")
    assert _kurz(zuordnung(db, "schlechtwetter", "Sonstiges", WINTER)) == ("WA", "8195", False, "schlechtwetter:winter")  # seit 1.9.214


def test_altbestand_wirkt_auch_ausserhalb_nie(db_session):
    """Eine Abwesenheit aus dem Altbestand ohne Kategorie („unbekannt“) mit der Art „Schlechtwetter“: die übergangene Zeile wirkt auch dort nicht."""
    db = db_session
    _altbestand(db)
    assert zuordnung(db, "unbekannt", "Schlechtwetter", WINTER) is None


@pytest.mark.parametrize("schluessel, kennzeichen, lohnart, monatszeile", [
    ("art:schlechtwetter", "S", "8111", False), ("art:Schlechtwetter", "S", "8111", False), ("art:schlechtwetter", None, "8110", True),
    ("art:schlechtwetter", "S", None, False)], ids=["wert", "gross", "monatszeile", "nur_kennzeichen"])
def test_neue_zuordnung_abgelehnt(db_session, schluessel, kennzeichen, lohnart, monatszeile):
    with pytest.raises(ValueError) as fehler:
        speichern(db_session, schluessel, kennzeichen, lohnart, monatszeile)
    assert str(fehler.value) == NUR_JAHRESZEIT
    assert db_session.query(LohnartZuordnung).filter(LohnartZuordnung.schluessel.ilike("art:schlechtwetter")).count() == 0


def test_schnittstelle_422_mit_meldung_leeren_geht(threaded_db_session, router_test_client):
    """PUT mit Wert: 422 und die Meldung (die Seite zeigt sie unter der Tabelle); leeren: 200, danach „nach der Jahreszeit“."""
    db = threaded_db_session
    _altbestand(db)
    client = router_test_client(db, time_backoffice_router.router, role="buero_finanzen")
    r = client.put("/api/time-backoffice/lohnarten", json={"schluessel": "art:schlechtwetter", "kennzeichen": "S", "lohnart": "8112",
                                                           "monatszeile": False})
    assert (r.status_code, r.json()["detail"]) == (422, NUR_JAHRESZEIT), r.text
    zeilen = {z["schluessel"]: z for z in client.get("/api/time-backoffice/lohnarten").json()}
    assert zeilen["art:schlechtwetter"]["wirkt"] == ("gespeichert S / 8111 – wird übergangen, es gilt die Jahreszeit "
                                                    "(Schlechtwetter Winter bzw. Sommer)")
    r = client.put("/api/time-backoffice/lohnarten", json={"schluessel": "art:schlechtwetter", "kennzeichen": None, "lohnart": None,
                                                           "monatszeile": False})
    assert r.status_code == 200, r.text
    zeile = next(z for z in r.json() if z["schluessel"] == "art:schlechtwetter")
    assert (zeile["kennzeichen"], zeile["lohnart"], zeile["wirkt"]) == (None, None, "nach der Jahreszeit (Schlechtwetter Winter bzw. Sommer)")


def test_liste_mit_der_art_schlechtwetter(db_session):
    """Legt jemand die Art „Schlechtwetter“ unter den Abwesenheitsarten an, steht ihre Zeile mit „nach der Jahreszeit“ da (bis 1.9.202
    „wie die Kategorie – “ ohne Kategorie)."""
    from app.models import SettingOption, SettingOptionGroup
    db = db_session
    gruppe = db.query(SettingOptionGroup).filter_by(group_key="absence_types").one()
    db.add(SettingOption(group_id=gruppe.id, label="Schlechtwetter", value="Schlechtwetter", sort_order=70, active=True))
    db.commit()
    zeile = next(z for z in liste(db) if z["schluessel"] == "art:schlechtwetter")
    assert (zeile["bezeichnung"], zeile["kennzeichen"], zeile["lohnart"], zeile["wirkt"]) == (
        "Art Schlechtwetter", None, None, "nach der Jahreszeit (Schlechtwetter Winter bzw. Sommer)")


def test_pruefskript_nennt_die_uebergangene_zeile(db_session):
    db = db_session
    rc, zeilen = _lauf(db)
    assert rc == 0, zeilen
    _altbestand(db)
    rc, zeilen = _lauf(db)
    assert rc == 1, zeilen
    assert "  art:schlechtwetter: gespeichert S / 8111 – wird übergangen" in zeilen  # seit 1.9.215 (bis 1.9.214 „S / 8111“)
    assert ("  ! Zuordnung art:schlechtwetter (S / 8111) wird übergangen: für Schlechtwetter gilt die Jahreszeit (schlechtwetter:winter "
            "bzw. schlechtwetter:sommer). In den Einstellungen leeren.") in zeilen
    assert zeilen[-1] == "Zu klären: 1"
    zeile = db.query(LohnartZuordnung).filter_by(schluessel="art:schlechtwetter").one()
    zeile.kennzeichen, zeile.lohnart = None, None  # geleert: kein Befund mehr
    db.commit()
    assert _lauf(db)[0] == 0


def test_seite_sagt_es():
    text = (ROOT / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "Eine Art mit eigener Zuordnung geht ihrer Kategorie vor – außer bei Schlechtwetter: dort gilt immer die Jahreszeit." in text
