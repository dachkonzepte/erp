"""Version 1.8.51 -- Stufe 2c-2b, Punkt 0 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.51").

- Belege am Mangel nachreichen wie Fotos: nur ergänzen, eigener Eintrag "Belege ergänzt" im Verlauf, PDF oder Foto am
  Inhalt erkannt, auch nach der Erledigung, nicht nach dem Verwerfen; Monteure nicht.
- Aufgabentitel mit Kurzfassung der Beschreibung; die Beschreibung der Aufgabe bleibt bei Metadaten."""

import pytest
from sqlalchemy import select

from app.defects import TASK_SHORT_TEXT, short_text
from app.models import DefectEvent, DefectFile, Task
from tests.test_v349_abnahme_und_gewaehrleistung import PDF, SVG, _png, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v351_maengel import _abnahme, _anzahl, _mangel, _ok, _routers, _status, buero  # noqa: F401


def _belege(client, defect_id, *dateien):
    return client.post(f"/api/defects/{defect_id}/receipts", files=[("receipts", d) for d in dateien])


# ---------------------------------------------------------------------------
# Belege nachreichen
# ---------------------------------------------------------------------------

def test_receipts_can_only_be_added(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png(), "image/png")]))
    v = _ok(_belege(buero, d["id"], ("protokoll.pdf", PDF, "application/pdf"), ("brief.png", _png("red"), "image/png")))
    e = v["events"][-1]
    assert e["kind"] == "belege" and e["kind_label"] == "Belege ergänzt"
    assert sorted(f["kind"] for f in e["files"]) == ["beleg", "beleg"]
    assert sorted(f["content_type"] for f in e["files"]) == ["application/pdf", "image/png"]
    assert len(v["files"]) == 1 and v["files"][0]["kind"] == "foto"  # die beim Erfassen bleiben, wie sie waren
    assert v["intact"] is True and all(f["status"] == "unveraendert" for f in e["files"])
    # Abrufbar wie jede Datei des Mangels.
    r = buero.get(f"/api/defects/{d['id']}/files/{e['files'][0]['id']}")
    assert r.status_code == 200 and r.headers["X-Content-Type-Options"] == "nosniff"
    # Ein zweites Mal ist ein weiterer Eintrag, nichts wird ersetzt.
    _ok(_belege(buero, d["id"], ("nachtrag.pdf", PDF + b"2", "application/pdf")))
    db = welt["db"]
    db.expire_all()
    assert [x.kind for x in db.scalars(select(DefectEvent).order_by(DefectEvent.id))] == ["belege", "belege"]
    assert _anzahl(db, DefectFile) == 4


@pytest.mark.parametrize("dateien,teil", [
    ((), "mindestens einen Beleg"),
    ((("bild.svg", SVG, "image/svg+xml"),), "PDF"),
    ((("a.pdf", PDF, "application/pdf"), ("b.pdf", PDF, "application/pdf")), "mehrfach"),
])
def test_attack_invalid_receipts_are_rejected_and_nothing_stored(welt, buero, ablage, dateien, teil):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    vorher = sorted(p.name for p in ablage.rglob("*.*"))
    r = _belege(buero, d["id"], *dateien)
    assert r.status_code == 400 and teil in r.json()["detail"], r.text
    assert _anzahl(welt["db"], DefectEvent) == 0 and sorted(p.name for p in ablage.rglob("*.*")) == vorher


def test_receipts_after_done_but_not_after_discard(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_status(buero, d["id"], status="erledigt_ohne", reason="Minderung vereinbart"))
    assert _belege(buero, d["id"], ("minderung.pdf", PDF, "application/pdf")).status_code == 200
    _ok(buero.post(f"/api/defects/{d['id']}/discard", json={"reason": "doppelt erfasst"}))
    r = _belege(buero, d["id"], ("spaet.pdf", PDF + b"x", "application/pdf"))
    assert r.status_code == 409 and "verworfen" in r.json()["detail"]
    assert _anzahl(welt["db"], DefectEvent) == 2  # Status und Belege, nach dem Verwerfen nichts mehr


def test_attack_field_worker_cannot_add_receipts(welt, buero, router_test_client):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    monteur = router_test_client(welt["db"], *_routers(), role="field")
    assert _belege(monteur, d["id"], ("x.pdf", PDF, "application/pdf")).status_code == 403
    assert _anzahl(welt["db"], DefectEvent) == 0
    # Gegenprobe: das Büro darf.
    assert _belege(buero, d["id"], ("x.pdf", PDF, "application/pdf")).status_code == 200


def test_order_page_offers_adding_receipts(welt, router_test_client):
    from app.routers import pages
    html = router_test_client(welt["db"], pages.router, role="buero_auftrag").get(f"/orders/{welt['order_id']}").text
    teil = html.split('id="defectCard"')[1]
    assert "Belege ergänzen …" in teil and "/receipts`" in teil and "prompt(" not in teil


# ---------------------------------------------------------------------------
# Aufgabentitel mit Kurzfassung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,erwartet", [
    ("Attika undicht", "Attika undicht"),
    ("  Attika\n undicht \t ", "Attika undicht"),
    ("x" * 80, "x" * (TASK_SHORT_TEXT - 1) + "…"),
    ("Anschluss an der Attika undicht, Wasser tritt bei jedem Regen ein und läuft bis in die Halle",
     "Anschluss an der Attika undicht, Wasser tritt bei jedem…"),  # "Regen" endet nach Zeichen 59
])
def test_short_text(text, erwartet):
    assert short_text(text) == erwartet and len(short_text(text)) <= TASK_SHORT_TEXT


def test_task_title_carries_a_short_version_of_the_description(welt, buero):
    db = welt["db"]
    lang = "Anschluss an der Attika undicht, Wasser tritt bei jedem Regen ein und läuft bis in die Halle"
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], description=lang, roof_area_id=welt["areas"]["Nord"]))
    task = db.get(Task, d["task"]["id"])
    order_number = d["order_number"]
    assert task.title == f"Mangel aus Abnahme {order_number} – Nord: {short_text(lang)}"
    assert "Halle" not in task.title  # gekürzt
    assert "Attika" not in (task.description or "") and "Regen" not in (task.description or "")  # nur Metadaten
    # Ohne Dachfläche mit Ortsangabe, ohne beides nur die Kurzfassung.
    d2 = _ok(_mangel(buero, _abnahme(buero, welt)["id"], description="Rinne lose", location="Traufe Ost"))
    assert db.get(Task, d2["task"]["id"]).title == f"Mangel aus Abnahme {order_number} – Traufe Ost: Rinne lose"
    d3 = _ok(_mangel(buero, _abnahme(buero, welt)["id"], description="Rinne lose"))
    assert db.get(Task, d3["task"]["id"]).title == f"Mangel aus Abnahme {order_number}: Rinne lose"
