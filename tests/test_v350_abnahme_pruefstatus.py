"""Version 1.8.48 -- Stufe 2c-2a, Punkt 0: Prüfstatus neben jedem Gewährleistungsende, Siegel des Verwerfens,
Fassung des Prüfsummenformats (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.48").

- acceptance_warranty() ist die eine Quelle für Ende UND Prüfstatus: Auftrag (Liste, Vorschau einer Änderung), Objekt
  (Karte und spätestes Ende je Dachfläche), Dachfläche. Eine Abweichung meldet zusätzlich logger.error, nur mit
  Kennungen (Regel 18).
- "Erfasst von" steht seit 1.8.46 im gebundenen Inhalt; "Verworfen von" bekommt ein eigenes Siegel (discard_sha256).
- Vorhandene Einträge behalten Fassung 1 und ihre Prüfsumme; neue sind Fassung 2 (Fassung im Inhalt).

Angriffe mit Gegenprobe: Begründung des Verwerfens am ORM vorbei geändert, Siegel entfernt, Fassung auf 1
zurückgesetzt, Verwerfen zurückgenommen, Abnahmedatum am ORM vorbei verschoben."""

import importlib.util
import logging
from datetime import datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text, update

from app import acceptances as acceptances_module
from app.database import Base
from app.models import OrderAcceptance
from tests.test_v349_abnahme_und_gewaehrleistung import (  # noqa: F401  (Fixtures)
    _dauer, _erfassen, _vorschau, ablage, buero, welt,
)

ROOT = Path(__file__).resolve().parent.parent


def _set(db, acceptance_id, **values):
    """Am ORM vorbei ändern (wie ein direkter Datenbankzugriff)."""
    db.execute(update(OrderAcceptance).where(OrderAcceptance.id == acceptance_id).values(**values)
               .execution_options(synchronize_session=False))
    db.commit()
    db.expire_all()


def _liste(buero, welt):
    return {x["id"]: x for x in buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()}


def _verwerfen(buero, acceptance_id, grund="Falsches Datum erfasst"):
    r = buero.post(f"/api/order-acceptances/{acceptance_id}/discard", json={"reason": grund})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Fassung des Prüfsummenformats
# ---------------------------------------------------------------------------

def test_new_entry_is_format_2_with_the_format_in_its_content(welt, buero):
    a = _erfassen(buero, welt["order_id"]).json()
    row = welt["db"].get(OrderAcceptance, a["id"])
    assert row.checksum_format == acceptances_module.CHECKSUM_FORMAT == 2 and a["checksum_format"] == 2
    content = acceptances_module.acceptance_content(row)
    assert content["checksum_format"] == 2 and content["created_by_name"] == "Buero_auftrag"  # "Erfasst von" gebunden
    assert a["intact"] is True and a["check"] == {"ok": True, "text": "Prüfsumme stimmt"}


def test_format_1_entry_keeps_its_checksum(welt, buero, monkeypatch):
    """Ein Eintrag von vor 1.8.48 (Fassung 1): Inhalt ohne Fassung, Prüfsumme unverändert gültig."""
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 1)
    a = _erfassen(buero, welt["order_id"]).json()
    row = welt["db"].get(OrderAcceptance, a["id"])
    assert row.checksum_format == 1 and "checksum_format" not in acceptances_module.acceptance_content(row)
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 2)
    stand = _liste(buero, welt)[a["id"]]
    assert stand["intact"] is True and stand["content_sha256"] == a["content_sha256"]


def test_attack_resetting_the_format_to_1_is_detected(welt, buero):
    a = _erfassen(buero, welt["order_id"]).json()
    _verwerfen(buero, a["id"])
    # Wer Fassung 1 vortäuscht, damit ein fehlendes Siegel als "vor 1.8.48" durchgeht, ändert den gebundenen Inhalt.
    _set(welt["db"], a["id"], checksum_format=1, discard_sha256=None)
    stand = _liste(buero, welt)[a["id"]]
    assert stand["content_ok"] is False and stand["intact"] is False
    assert stand["check"]["text"].startswith("Inhalt weicht von seiner Prüfsumme ab")


# ---------------------------------------------------------------------------
# Siegel des Verwerfens
# ---------------------------------------------------------------------------

def test_discard_is_sealed_with_the_name_as_copy(welt, buero):
    a = _erfassen(buero, welt["order_id"]).json()
    v = _verwerfen(buero, a["id"])
    row = welt["db"].get(OrderAcceptance, a["id"])
    erwartet = acceptances_module.content_sha256(acceptances_module.discard_content(
        row.content_sha256, row.discarded_at, "Buero_auftrag", "Falsches Datum erfasst"))
    assert row.discard_sha256 == erwartet
    assert v["discard_check"] == "unveraendert" and v["intact"] is True and v["discarded_by_name"] == "Buero_auftrag"


@pytest.mark.parametrize("aenderung,teil", [
    ({"discard_reason": "Andere Begründung"}, "Verwerfen weicht"),
    ({"discarded_by_name": "Jemand anderes"}, "Verwerfen weicht"),
    ({"discarded_at": datetime(2026, 1, 1, 12, 0)}, "Verwerfen weicht"),
    ({"discard_sha256": None}, "Verwerfen weicht"),            # Siegel entfernt (Fassung 2: Pflicht)
    ({"discarded_at": None}, "Verwerfen weicht"),              # Verwerfen zurückgenommen, Siegel bleibt
])
def test_attack_discard_changed_past_the_orm_is_detected(welt, buero, caplog, aenderung, teil):
    a = _erfassen(buero, welt["order_id"]).json()
    _verwerfen(buero, a["id"])
    _set(welt["db"], a["id"], **aenderung)
    with caplog.at_level(logging.ERROR, logger="app.acceptances"):
        stand = _liste(buero, welt)[a["id"]]
    assert stand["discard_check"] == "abweichend" and stand["intact"] is False and teil in stand["check"]["text"]
    assert stand["content_ok"] is True  # der Inhalt selbst ist unverändert
    # Protokoll: nur Kennungen, nicht die Begründung (Regel 18).
    meldung = " ".join(r.getMessage() for r in caplog.records if r.name == "app.acceptances")
    assert f"Abnahme {a['id']}" in meldung and "Verwerfen abweichend" in meldung
    assert "Begründung" not in meldung and "Falsches Datum" not in meldung and "Jemand" not in meldung


def test_format_1_discarded_before_the_update_is_unsealed_but_not_a_deviation(welt, buero, monkeypatch, caplog):
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 1)
    a = _erfassen(buero, welt["order_id"]).json()
    alt = _erfassen(buero, welt["order_id"], accepted_on="2026-09-16").json()
    monkeypatch.setattr(acceptances_module, "CHECKSUM_FORMAT", 2)
    # So stand ein vor 1.8.48 verworfener Eintrag in der Datenbank: Verwerfen ohne Siegel.
    _set(welt["db"], a["id"], discarded_at=datetime(2026, 10, 4, 9, 0), discarded_by_name="Büro",
         discard_reason="vor dem Update verworfen")
    with caplog.at_level(logging.ERROR, logger="app.acceptances"):
        stand = _liste(buero, welt)[a["id"]]
    assert stand["discard_check"] == "ohne_pruefsumme" and stand["intact"] is True
    assert stand["discard_check_text"] == "Verwerfen vor 1.8.48 erfasst, ohne Prüfsumme"
    assert not [r for r in caplog.records if r.name == "app.acceptances"]
    # Ein Eintrag der Fassung 1, der NACH dem Update verworfen wird, bekommt das Siegel.
    assert _verwerfen(buero, alt["id"])["discard_check"] == "unveraendert"
    assert welt["db"].get(OrderAcceptance, alt["id"]).discard_sha256 is not None


# ---------------------------------------------------------------------------
# Prüfstatus neben jedem Gewährleistungsende
# ---------------------------------------------------------------------------

def _alle_enden(buero, welt):
    liste = _liste(buero, welt)
    objekt = buero.get(f"/api/properties/{welt['property_id']}/acceptance-warranties").json()
    nord = buero.get(f"/api/roof-areas/{welt['areas']['Nord']}/acceptance-warranties").json()
    vorschau = _vorschau(buero, welt, "bauwerk", 60)
    return liste, objekt, nord, vorschau


def test_check_status_appears_wherever_the_end_appears(welt, buero, caplog):
    _dauer(buero, welt, 48)
    a = _erfassen(buero, welt["order_id"], accepted_on="2025-08-31", roof_area_ids=[welt["areas"]["Nord"]]).json()
    ok = {"ok": True, "text": "Prüfsumme stimmt"}
    liste, objekt, nord, vorschau = _alle_enden(buero, welt)  # Gegenprobe: alles stimmt
    assert liste[a["id"]]["warranty"]["check"] == ok
    assert objekt["acceptances"][0]["warranty"]["check"] == ok
    assert objekt["roof_areas"][str(welt["areas"]["Nord"])]["check"] == ok
    assert nord["acceptances"][0]["warranty"]["check"] == ok
    assert vorschau["shifts"][0]["check"] == ok

    # Angriff: Abnahmedatum am ORM vorbei verschoben -- das Ende rückt mit, der Prüfstatus sagt es überall.
    _set(welt["db"], a["id"], accepted_on=datetime(2026, 8, 31).date())
    with caplog.at_level(logging.ERROR, logger="app.acceptances"):
        liste, objekt, nord, vorschau = _alle_enden(buero, welt)
    for check in (liste[a["id"]]["warranty"]["check"], objekt["acceptances"][0]["warranty"]["check"],
                  nord["acceptances"][0]["warranty"]["check"], vorschau["shifts"][0]["check"]):
        assert check == {"ok": False, "text": "Inhalt weicht von seiner Prüfsumme ab"}
    flaeche = objekt["roof_areas"][str(welt["areas"]["Nord"])]["check"]
    assert flaeche["ok"] is False and a["order_number"] in flaeche["text"]
    assert liste[a["id"]]["warranty"]["end"] == "2030-08-31"  # das Ende wird weiter angezeigt, aber gekennzeichnet
    assert any(r.name == "app.acceptances" and r.levelno == logging.ERROR for r in caplog.records)


def test_latest_end_of_a_roof_area_is_only_as_reliable_as_every_acceptance(welt, buero):
    """Das späteste Ende je Dachfläche ist ein Höchstwert -- weicht irgendeine Abnahme ab, die die Fläche nennt, ist
    er nicht verlässlich, auch wenn er aus einer anderen stammt."""
    _dauer(buero, welt, 48)
    frueh = _erfassen(buero, welt["order_id"], accepted_on="2024-03-01", scope="teil", scope_description="Nord alt",
                      roof_area_ids=[welt["areas"]["Nord"]]).json()
    _erfassen(buero, welt["order_id"], accepted_on="2026-03-01", roof_area_ids=[welt["areas"]["Nord"]])
    _set(welt["db"], frueh["id"], scope_description="manipuliert")
    flaeche = buero.get(f"/api/properties/{welt['property_id']}/acceptance-warranties").json()["roof_areas"][
        str(welt["areas"]["Nord"])]
    assert flaeche["end"] == "2030-03-01" and flaeche["check"]["ok"] is False


def test_file_deviation_is_part_of_the_check(welt, buero, ablage):
    import os
    import stat
    _dauer(buero, welt, 48)
    a = _erfassen(buero, welt["order_id"]).json()
    pfad = next(ablage.rglob("*.pdf"))
    os.chmod(pfad, stat.S_IWRITE | stat.S_IREAD)
    pfad.unlink()
    assert _liste(buero, welt)[a["id"]]["warranty"]["check"] == {"ok": False, "text": "Beleg fehlt"}


def test_pages_show_the_check_status():
    for name, marker in (("_abnahme.html", "accCheck("), ("property.html", "acceptanceCheck("),
                         ("roof_area.html", "w.check.ok")):
        source = (ROOT / "app" / "templates" / name).read_text(encoding="utf-8")
        assert marker in source and "nicht verlässlich" in source, name
    abnahme = (ROOT / "app" / "templates" / "_abnahme.html").read_text(encoding="utf-8")
    assert "a.discard_check_text" in abnahme and "<th>Prüfung</th>" in abnahme


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_abnahme_pruefsummenformat.py"))
    spec = importlib.util.spec_from_file_location("migration_1848_pruefsummenformat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_keeps_existing_entries_in_format_1_and_refuses_to_lose_format_2():
    module = _migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()
    run("downgrade")
    assert not {"checksum_format", "discard_sha256"} & {c["name"] for c in inspect(engine).get_columns("order_acceptances")}
    with engine.begin() as conn:  # ein Eintrag aus 1.8.47
        conn.execute(text("INSERT INTO order_acceptances (order_id, kind, accepted_on, scope, result, declared_by, "
                          "declared_by_name, content_sha256, created_at, created_by_name) VALUES (1, 'foermlich', "
                          "'2026-09-15', 'gesamt', 'verweigert', 'auftraggeber', 'K', 'abc', '2026-10-03 00:00:00', 'X')"))
    run("upgrade")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT checksum_format, content_sha256, discard_sha256 FROM order_acceptances")).one() \
            == (1, "abc", None)
    run("downgrade")  # nur Fassung 1 ohne Siegel: nichts ginge verloren
    run("upgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE order_acceptances SET checksum_format = 2"))
    with pytest.raises(RuntimeError, match="1 Abnahmen in Prüfsummenformat 2"):
        run("downgrade")
    with engine.begin() as conn:
        conn.execute(text("UPDATE order_acceptances SET checksum_format = 1, discard_sha256 = 'x'"))
    with pytest.raises(RuntimeError, match="1 versiegelte Verwerfen"):
        run("downgrade")
