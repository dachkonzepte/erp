"""Version 1.8.65 -- Stufe 2c-2e, Vorweg (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.65").

Festlegungen 1.8.62 bis 1.8.64 bestätigt (07.10.2026), mit zwei Änderungen:

1. Für "bleibt im Protokoll" zählt die erste gültige Unterschrift unter dem Feld "Mängel" -- überall: Protokollseite, PDF,
   Abnahme aus dem Protokoll und jede weitere Kopie. Bis 1.8.64 versiegelte eine spätere Unterschrift nur die nicht
   verworfenen Mängel; unterschrieb der Auftragnehmer vor dem Auftraggeber und wurde dazwischen ein Mangel verworfen, stand er
   "im Protokoll" (Seite, PDF), fehlte aber in der Kopie des Auftraggebers und an der Abnahme.
2. Eine unlesbare oder von ihrer Prüfsumme abweichende Kopie gilt nicht als "ohne Mängel": sichtbarer Fehler, logger.error,
   kein Schluss daraus -- keine Liste "im Protokoll", keine Zahl, keine Erklärungen aus ihr, keine weitere Unterschrift, kein
   Abschluss, keine Abnahme.

Der Navigationstest (Punkt 0) steht in tests/test_v328_navigation_ohne_sperrseiten.py."""

import hashlib
import json
import logging

import pytest
from sqlalchemy import text

import app.checklists as checklists_module
from app.checklist_pdf import build_checklist_pdf
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v358_unterschrift_pruefung import SIGNATUR
from tests.test_v363_zweck_abnahme import _mangel, _sig, _sign_ag
from tests.test_v365_abnahme_aus_protokoll import AN, _acceptances, _defect, _nachholen, ohne_folge, protokoll  # noqa: F401
from tests.test_v366_protokoll_seite_und_pdf import _pdf_text, _summary


def _entry(signature, key):
    return next(e for e in json.loads(signature.sealed_content)["fields"] if e["field_key"] == "abnahme." + key)


def _sign_an(p):
    return p["client"].post(f"/api/checklists/{p['c']['id']}/attachments", data={"field_id": p["f"][AN]},
                            files={"file": ("s.png", SIGNATUR, "image/png")})


def _discard_defect(p, defect_id):
    r = p["client"].post(f"/api/defects/{defect_id}/discard", json={"reason": "doch keiner"})
    assert r.status_code == 200, r.text


def _liste(p) -> dict:
    r = p["client"].get(f"/api/checklists/{p['c']['id']}/defects")
    assert r.status_code == 200, r.text
    return {d["id"]: d for d in r.json()}


def _kopie(db, signature_id: int, content: str, *, mit_pruefsumme: bool = False) -> None:
    """Die Kopie einer Unterschrift am ORM vorbei ersetzen (mit_pruefsumme: auch ihre Prüfsumme dazu passend)."""
    werte = {"c": content, "i": signature_id}
    if mit_pruefsumme:
        db.execute(text("UPDATE checklist_attachments SET sealed_content = :c, content_sha256 = :h WHERE id = :i"),
                   {**werte, "h": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    else:
        db.execute(text("UPDATE checklist_attachments SET sealed_content = :c WHERE id = :i"), werte)
    db.commit()


def _ohne_maengel(sealed_content: str) -> str:
    """Dieselbe Kopie, aber ohne Mängel -- lesbar, weicht von ihrer Prüfsumme ab."""
    content = json.loads(sealed_content)
    for entry in content["fields"]:
        if "defects" in entry:
            entry["defects"] = []
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. "bleibt im Protokoll": die erste gültige Unterschrift unter dem Feld -- überall
# ---------------------------------------------------------------------------

def test_contractor_signs_first_discarded_defect_stays_for_customer_copy_and_acceptance(protokoll):
    """Der Auftragnehmer unterschreibt zuerst (seine Kopie enthält beide Mängel), dann wird ein Mangel verworfen, dann
    unterschreibt der Auftraggeber: der verworfene bleibt im Protokoll -- auf der Seite, in der Kopie des Auftraggebers und an
    der Abnahme (ohne Aufgabe); das Siegel des Auftraggebers stimmt."""
    p, db = protokoll, protokoll["db"]
    zweiter = _mangel(p, "Rinne lose")
    assert _sign_an(p).status_code == 200
    assert {d["id"] for d in _entry(_sig(p, AN), "maengel")["defects"]} == {p["mangel"], zweiter}
    _discard_defect(p, zweiter)
    r = _sign_ag(p)
    assert r.status_code == 200, r.text
    ag = _sig(p)
    assert {d["id"] for d in _entry(ag, "maengel")["defects"]} == {p["mangel"], zweiter}
    assert {a["id"]: a for a in r.json()["attachments"]}[ag.id]["seal"]["status"] == "unveraendert"
    liste = _liste(p)
    assert (liste[zweiter]["discarded"], liste[zweiter]["in_protocol"]) == (True, True)
    [acceptance] = _acceptances(db)
    assert _defect(db, zweiter).acceptance_id == acceptance.id and _defect(db, zweiter).task_id is None
    assert _defect(db, p["mangel"]).acceptance_id == acceptance.id and _defect(db, p["mangel"]).task_id is not None
    assert _summary(p)["defects_in_protocol"] == 2


def test_acceptance_follows_the_first_signature_even_for_an_older_customer_copy(protokoll, ohne_folge, monkeypatch):
    """Eine Kopie des Auftraggebers wie vor 1.8.65 (ohne den nach der ersten Unterschrift verworfenen Mangel): die Abnahme
    bekommt ihn trotzdem -- er steht in der Kopie der ersten gültigen Unterschrift unter dem Feld."""
    p, db = protokoll, protokoll["db"]
    zweiter = _mangel(p, "Rinne lose")
    assert _sign_an(p).status_code == 200
    _discard_defect(p, zweiter)
    with monkeypatch.context() as m:
        m.setattr(checklists_module, "_seal_defect_ids", lambda checklist, upto: None)  # Versiegeln wie bis 1.8.64
        assert _sign_ag(p).status_code == 200
    assert [d["id"] for d in _entry(_sig(p), "maengel")["defects"]] == [p["mangel"]]
    r = _nachholen(p)
    assert r.status_code == 200, r.text
    [acceptance] = _acceptances(db)
    assert {_defect(db, i).acceptance_id for i in (p["mangel"], zweiter)} == {acceptance.id}


def test_completion_copy_keeps_the_defect_that_stays_in_the_protocol(protokoll):
    """Der Abschluss versiegelt ebenfalls die Mängel im Protokoll, auch den nach der ersten Unterschrift verworfenen."""
    p, db = protokoll, protokoll["db"]
    zweiter = _mangel(p, "Rinne lose")
    assert _sign_ag(p).status_code == 200
    _discard_defect(p, zweiter)
    assert _sign_an(p).status_code == 200
    assert {d["id"] for d in _entry(_sig(p, AN), "maengel")["defects"]} == {p["mangel"], zweiter}
    r = p["client"].post(f"/api/checklists/{p['c']['id']}/complete")
    assert r.status_code == 200, r.text
    db.expire_all()
    checklist = db.get(checklists_module.Checklist, p["c"]["id"])
    entry = next(e for e in json.loads(checklist.sealed_content)["fields"] if "defects" in e)
    assert {d["id"] for d in entry["defects"]} == {p["mangel"], zweiter}
    assert r.json()["completion_seal"]["status"] == "unveraendert"


# ---------------------------------------------------------------------------
# 2. Unlesbare oder abweichende Kopie: Fehler, kein "ohne Mängel"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("art", ["unlesbar", "abweichend"])
def test_broken_copy_is_an_error_and_no_conclusion(protokoll, ohne_folge, caplog, art):
    """Die Kopie der ersten Unterschrift unter dem Feld (hier die des Auftraggebers) unlesbar bzw. ohne Mängel und damit
    abweichend: kein "im Protokoll"/"nicht im Protokoll", keine Zahl, keine Erklärungen aus ihr, ein Fehler mit logger.error;
    keine weitere Unterschrift, kein Abschluss, keine Abnahme."""
    p, db = protokoll, protokoll["db"]
    zweiter = _mangel(p, "Rinne lose")
    _discard_defect(p, zweiter)
    assert _sign_ag(p).status_code == 200
    ag = _sig(p)
    _kopie(db, ag.id, "kaputt{" if art == "unlesbar" else _ohne_maengel(ag.sealed_content))
    caplog.set_level(logging.ERROR)
    liste = _liste(p)
    assert {d["in_protocol"] for d in liste.values()} == {None}
    assert all("lässt sich nicht feststellen" in d["seal_problem"] for d in liste.values())
    assert any(r.levelno == logging.ERROR and "nicht feststellbar" in r.getMessage() for r in caplog.records)
    s = _summary(p)
    assert s["defects_in_protocol"] is None and s["declarations"] == []
    assert any("Unterschrift des Auftraggebers" in e for e in s["errors"])
    assert {d["status_label"] for d in s["defects"]} == {"nicht feststellbar – Kopie der Unterschrift fehlerhaft"}
    r = _sign_an(p)
    assert r.status_code == 409 and "lässt sich nicht feststellen" in r.json()["detail"], r.text
    r = _nachholen(p)
    assert r.status_code == 409 and _acceptances(db) == [], r.text


def test_broken_copy_shows_in_the_pdf_instead_of_no_defects(protokoll):
    """Nach dem Abschluss die Kopie des Auftraggebers ohne Mängel ersetzt: das PDF nennt den Fehler, nicht "Keine Mängel."."""
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    assert _sign_an(p).status_code == 200
    assert p["client"].post(f"/api/checklists/{p['c']['id']}/complete").status_code == 200
    ag = _sig(p)
    _kopie(db, ag.id, _ohne_maengel(ag.sealed_content))
    db.expire_all()
    pdf = " ".join(_pdf_text(build_checklist_pdf(db, checklists_module.get_checklist_row(db, p["c"]["id"]))).split())
    # zweimal: in der Zusammenfassung oben und am Feld "Mängel" selbst
    assert pdf.count("welche Mängel im Protokoll stehen, lässt sich nicht feststellen") == 2, pdf
    assert "Keine Mängel." not in pdf and "Mangel Nr." not in pdf


def test_unreadable_copy_with_matching_checksum_does_not_break_the_page(protokoll):
    """Kopie UND Prüfsumme am ORM vorbei unlesbar gemacht: die Seite lädt, die Unterschrift weicht ab (kein 500)."""
    p, db = protokoll, protokoll["db"]
    assert _sign_ag(p).status_code == 200
    ag = _sig(p)
    _kopie(db, ag.id, "kaputt{", mit_pruefsumme=True)
    r = p["client"].get(f"/api/checklists/{p['c']['id']}")
    assert r.status_code == 200, r.text
    assert {a["id"]: a for a in r.json()["attachments"]}[ag.id]["seal"]["status"] == "abweichend"
    assert {d["in_protocol"] for d in _liste(p).values()} == {None}
