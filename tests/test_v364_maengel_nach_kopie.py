"""Version 1.8.62 -- Stufe 2c-2d, Teil 2, Vorweg (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.62").

1. Ob ein verworfener Mangel im Protokoll bleibt, sagt die abgelegte Kopie der Unterschrift (bzw. des Abschlusses), nicht ein
   Vergleich von Verwerfen und Unterschriftszeit: steht er darin, wurde er erst danach verworfen. Die Tests verschieben deshalb
   den Zeitpunkt des Verwerfens am ORM vorbei auf die andere Seite der Unterschrift -- ein Zeitvergleich käme dann zum
   falschen Ergebnis, die Kopie nicht.
2. Die bekannte Ausnahme der Behinderungsanzeige (Festlegung 1.8.59 Nr. 5, entschieden: behalten) deckt genau die vier
   Büro-Pflichtfelder der Anzeige über der Wegfall-Unterschrift ab -- ein weiteres Büro-Pflichtfeld darüber lehnt das
   Veröffentlichen wieder ab. Beendigung und Wiederaufnahme sind eigene Datumsfelder im Abschnitt Wegfall."""

from datetime import timedelta

import pytest
from sqlalchemy import select, text

import app.checklists as checklists_module
from app.checklist_purposes import OBSTRUCTION_SYSTEM_FIELDS, PURPOSES, ChecklistPurpose, SystemField
from app.checklist_templates import (
    SIGNER_FILL_EXCEPTIONS, create_template, signer_fill_findings, signer_fill_problems, template_to_dict,
)
from app.models import ChecklistTemplate
from app.notice_letters import LETTER_KINDS
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v362_maengel_im_protokoll import (  # noqa: F401  (Fixture protokoll)
    P, _defects, _discard, _entry, _mangel, _sig, _sign, _view, protokoll,
)

B = "behinderungsanzeige."


def _liste(p) -> dict:
    return {x["id"]: x for x in p["client"].get(f"/api/checklists/{p['c']['id']}/defects").json()}


def _verschiebe_verwerfen(db, defect_id: int, wann) -> None:
    db.execute(text("UPDATE defects SET discarded_at = :w WHERE id = :i"), {"w": wann, "i": defect_id})
    db.commit()


def test_discarded_after_the_signature_stays_even_with_an_earlier_discard_time(protokoll):
    """Nach der Unterschrift verworfen, dann den Zeitpunkt des Verwerfens vor die Unterschrift gelegt: der Mangel steht in der
    Kopie -- er bleibt im Protokoll, das Siegel stimmt. Nur das Siegel des Verwerfens am Mangel selbst weicht ab."""
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    sig = _sig(p, "ag")
    [d] = _defects(db)
    assert _discard(p, d.id).status_code == 200
    _verschiebe_verwerfen(db, d.id, sig.created_at - timedelta(hours=1))
    eintrag = _liste(p)[d.id]
    assert (eintrag["discarded"], eintrag["in_protocol"], eintrag["sealed"]) == (True, True, True)
    assert _view(p)[sig.id]["seal"]["status"] == "unveraendert"
    assert "Verwerfen weicht" in eintrag["check"]["text"]


def test_discarded_before_the_signature_stays_out_even_with_a_later_discard_time(protokoll):
    """Vor der Unterschrift verworfen, dann den Zeitpunkt hinter die Unterschrift gelegt: nicht in der Kopie -- nicht im
    Protokoll, das Siegel stimmt (ein Zeitvergleich nähme ihn jetzt auf und meldete eine Abweichung)."""
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    [d] = _defects(db)
    assert _discard(p, d.id).status_code == 200
    assert _sign(p, "ag").status_code == 200
    sig = _sig(p, "ag")
    assert _entry(sig, "maengel")["defects"] == []
    _verschiebe_verwerfen(db, d.id, sig.created_at + timedelta(hours=1))
    eintrag = _liste(p)[d.id]
    assert (eintrag["discarded"], eintrag["in_protocol"]) == (True, False)
    assert _view(p)[sig.id]["seal"]["status"] == "unveraendert"


def test_completion_copy_decides_too(protokoll):
    """Dasselbe für den Abschluss: nach dem Abschluss verworfen und zurückdatiert bleibt der Abschluss unverändert."""
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    done = p["client"].post(f"/api/checklists/{p['c']['id']}/complete")
    assert done.status_code == 200, done.text
    [d] = _defects(db)
    assert _discard(p, d.id).status_code == 200
    checklist = db.get(checklists_module.Checklist, p["c"]["id"])
    _verschiebe_verwerfen(db, d.id, checklist.completed_at - timedelta(hours=2))
    assert p["client"].get(f"/api/checklists/{p['c']['id']}").json()["completion_seal"]["status"] == "unveraendert"


def test_defect_added_after_the_signature_past_the_orm_shows_at_the_signature(protokoll):
    """Ein nicht verworfener Mangel, der nicht in der Kopie steht (am ORM vorbei eingefügt), gehört trotzdem zum
    nachgerechneten Inhalt -- die Unterschrift weicht ab."""
    p, db = protokoll, protokoll["db"]
    _mangel(p)
    assert _sign(p, "ag").status_code == 200
    [d] = _defects(db)
    db.execute(text(
        "INSERT INTO defects (order_id, property_id, source, checklist_id, description, content_sha256, checksum_format, "
        "created_at, created_by_name) SELECT order_id, property_id, source, checklist_id, 'nachgeschoben', content_sha256, "
        "checksum_format, created_at, created_by_name FROM defects WHERE id = :i"), {"i": d.id})
    db.commit()
    seal = _view(p)[_sig(p, "ag").id]["seal"]
    assert seal["status"] == "abweichend" and seal["changed_fields"] == ["Mängel"], seal


@pytest.mark.parametrize("inhalt, erwartet", [
    (None, None), ('{"fields":[{"field_key":"x","defects":[{"id":3,"sha256":"a"}]},{"field_key":"y","value":1}]}', {3}),
    ("kein json", checklists_module.SealedCopyError),
    ('{"fields":[{"field_key":"x","defects":[{"sha256":"a"}]}]}', checklists_module.SealedCopyError),
], ids=["ohne_kopie", "kopie", "unlesbar", "ohne_kennung"])
def test_sealed_defect_ids_reads_the_copy(inhalt, erwartet):
    """Seit 1.8.65 gilt eine unlesbare Kopie nicht mehr als leer ("ohne Mängel"), sondern als Fehler."""
    if erwartet is checklists_module.SealedCopyError:
        with pytest.raises(checklists_module.SealedCopyError):
            checklists_module.sealed_defect_ids(inhalt)
    else:
        assert checklists_module.sealed_defect_ids(inhalt) == erwartet


# ---------------------------------------------------------------------------
# Behinderungsanzeige: Ausnahme genau für die Büro-Felder der Anzeige
# ---------------------------------------------------------------------------

def test_obstruction_exception_covers_exactly_the_office_fields_of_the_notice():
    [(fields, _grund)] = SIGNER_FILL_EXCEPTIONS.values()
    wegfall = next(i for i, s in enumerate(OBSTRUCTION_SYSTEM_FIELDS) if s.key == B + "unterschrift_wegfall")
    office_required_above = {s.key for s in OBSTRUCTION_SYSTEM_FIELDS[:wegfall]
                             if s.office_only and s.required and s.field_type != "unterschrift"}
    assert fields == office_required_above == {B + "ursache", B + "ursache_beschreibung", B + "betroffene_leistungen",
                                               B + "beginn"}
    assert {s.section for s in OBSTRUCTION_SYSTEM_FIELDS if s.key in fields} == {"Anzeige"}
    # Beendigung und Wiederaufnahme: eigene Datumsfelder im Abschnitt Wegfall, Pflicht -- der Brief nimmt sie aus der Kopie
    dates = {s.key: s for s in OBSTRUCTION_SYSTEM_FIELDS[:wegfall] if s.section == "Wegfall"}
    assert {k: (s.field_type, s.required, s.office_only) for k, s in dates.items()} == {
        B + "beendet_am": ("datum", True, False), B + "wieder_aufgenommen_am": ("datum", True, False)}
    assert LETTER_KINDS["wiederaufnahme"].signature_field == B + "unterschrift_wegfall"


@pytest.fixture
def behinderung_plus(monkeypatch):
    """Die Behinderungsanzeige mit einem zusätzlichen Büro-Pflichtfeld in der Anzeige."""
    spec = PURPOSES["behinderungsanzeige"]
    index = next(i for i, s in enumerate(spec.system_fields) if s.key == B + "unterschrift_buero")
    extra = SystemField(B + "aktenzeichen", "text", "Aktenzeichen", required=True, section="Anzeige", office_only=True)
    fields = spec.system_fields[:index] + (extra,) + spec.system_fields[index:]
    monkeypatch.setitem(PURPOSES, "behinderungsanzeige", ChecklistPurpose(
        spec.key, spec.label, spec.contexts, fields, spec.follow_ups, voidable=spec.voidable))


def test_exception_no_longer_covers_an_additional_office_field(welt, behinderung_plus):  # noqa: F811
    db = welt["db"]
    t = create_template(db, label="Behinderung mit Aktenzeichen", contexts=["auftrag"], purpose="behinderungsanzeige")
    template = db.get(ChecklistTemplate, t["id"])
    [(key, text_)] = signer_fill_findings("behinderungsanzeige", template.versions[0])
    assert key == B + "unterschrift_wegfall" and "Aktenzeichen" in text_
    assert signer_fill_problems("behinderungsanzeige", template.versions[0]) == [text_]
    detail = template_to_dict(db.get(ChecklistTemplate, t["id"]), with_editable_version=True)
    assert detail["signer_fill_findings"] == [{"text": text_, "known_exception": False}]


def test_exception_still_lets_the_real_obstruction_template_publish(welt):  # noqa: F811
    db = welt["db"]
    t = create_template(db, label="Behinderung", contexts=["auftrag"], purpose="behinderungsanzeige")
    template = db.get(ChecklistTemplate, t["id"])
    assert signer_fill_problems("behinderungsanzeige", template.versions[0]) == []
    detail = template_to_dict(db.get(ChecklistTemplate, t["id"]), with_editable_version=True)
    assert [x["known_exception"] for x in detail["signer_fill_findings"]] == [True]
    assert db.scalars(select(ChecklistTemplate)).all()
