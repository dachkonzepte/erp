"""Version 1.9.181 (L1a-Korrekturen, Punkt 2, Vorgabe Tobias 03.11.2026): eine gemerkte Personalnummer wieder freigeben.

    wer           nur der Admin (app/permissions.py::darf_personalnummer_freigeben()), Büro – Finanzen und Büro – Auftrag 403
    wann          nur solange niemand die Nummer trägt -- keine Lohnstammdaten mit dieser DATEV-Nummer, bei „DATEV-Nr. = ERP-Nr.“ keine
                  Mitarbeiternummer (sonst 409, nichts geändert); eine nicht gemerkte Nummer 404
    danach        frei für jede Person; die Freigabe steht im Änderungsprotokoll (welche Nummer, wem sie gehörte)
    Seite         Einstellungen: „freigeben“ je frühere Nummer nur für den Admin, Dialog mit Warnung (Festlegung 1.9.177 Nr. 3 neu gefasst)
"""

from sqlalchemy import select

from app.models import AuditLog, PersonalnummerVergabe, TimeBackofficeAdvancedSettings
from tests.test_v593_personalnummer_gesperrt import _client, _gemerkt, _mitarbeiter_put, _put, welt  # noqa: F401

FREIGEBEN = "/api/time-backoffice/personalnummern/freigeben"


def _wechsel(w):
    """Mia 91008 -> 91016: 91008 ist ihr gemerkt und gehört heute niemandem."""
    assert _put(w, w["mia"], datev_personnel_number="91008").status_code == 200
    assert _put(w, w["mia"], datev_personnel_number="91016").status_code == 200


def test_admin_gibt_eine_fruehere_nummer_frei(welt):
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    _wechsel(welt)
    r = _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91008"})
    assert r.status_code == 200, r.text
    assert {z["employee_name"]: z["fruehere_personalnummern"] for z in r.json()} == {"Mia Monteurin": [], "Tom Monteur": []}
    assert _gemerkt(welt) == [("91016", mia.id)]
    assert _put(welt, tom, datev_personnel_number="91008").status_code == 200  # jetzt frei
    eintrag = db.scalars(select(AuditLog).where(AuditLog.action == "Personalnummer freigegeben")).one()
    assert (eintrag.entity_type, eintrag.entity_id, eintrag.entity_label, eintrag.field_label, eintrag.old_value, eintrag.new_value) == (
        "Personalnummer", "91008", "Personalnummer 91008", "Personalnummer", "gesperrt, gehörte Mia Monteurin", "frei")


def test_nur_der_admin(welt):
    _wechsel(welt)
    for rolle in ("buero_finanzen", "buero_auftrag", "field"):
        r = _client(welt, rolle).post(FREIGEBEN, json={"nummer": "91008"})
        assert r.status_code == 403, rolle
    assert ("91008", welt["mia"].id) in _gemerkt(welt)
    assert welt["db"].scalar(select(AuditLog.id).where(AuditLog.action == "Personalnummer freigegeben")) is None


def test_eine_getragene_nummer_bleibt(welt):
    """Mias heutige Nummer 91016 trägt sie selbst -- 409, nichts geändert."""
    _wechsel(welt)
    r = _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91016"})
    assert (r.status_code, r.json()["detail"]) == (
        409, "Die Personalnummer 91016 trägt heute Mia Monteurin – freigeben geht nur, solange sie niemand trägt.")
    assert ("91016", welt["mia"].id) in _gemerkt(welt)


def test_eine_mitarbeiternummer_bei_gleichsetzung_bleibt(welt):
    """„DATEV-Nr. = ERP-Nr.“: Mia 91001 -> 91002 über das Mitarbeiterformular, Tom bekommt (an der Sperre vorbei, wie von Hand) 91001 als
    Mitarbeiternummer -- er trägt sie, also 409."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    client = _client(welt, "admin")
    assert _mitarbeiter_put(client, mia.id, employee_number="91001").status_code == 200
    assert _mitarbeiter_put(client, mia.id, employee_number="91002").status_code == 200
    tom.employee_number = "91001"
    db.commit()
    r = client.post(FREIGEBEN, json={"nummer": "91001"})
    assert (r.status_code, r.json()["detail"]) == (
        409, "Die Personalnummer 91001 trägt heute Tom Monteur – freigeben geht nur, solange sie niemand trägt.")
    tom.employee_number = "M-2"
    db.commit()
    assert client.post(FREIGEBEN, json={"nummer": "91001"}).status_code == 200


def test_eine_nicht_gemerkte_nummer(welt):
    r = _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91099"})
    assert (r.status_code, r.json()["detail"]) == (404, "Die Personalnummer 91099 ist nicht gesperrt.")
    assert _client(welt, "admin").post(FREIGEBEN, json={"nummer": ""}).status_code == 422


def test_seite():
    """Der Knopf nur für den Admin (Recht der Seitenroute), der Dialog warnt, das Senden geht über speichern()."""
    from tests import vorlagen_js as vj
    html = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert "const PNR_FREIGEBEN=\"{{ 'ja' if personalnummer_freigeben else 'nein' }}\"===\"ja\";" in html
    # seit 1.9.191 über fruehereNummer(): der Knopf nur an einer Nummer, die niemand trägt (tests/test_v601_freigeben_nur_wo_moeglich.py)
    assert "früher: ${p.fruehere_personalnummern.map(n=>fruehereNummer(p,n)).join(', ')}" in html and 'data-klick="pnr-freigeben"' in html
    assert 'id="pnrFreigabeDialog"' in html and "gib sie nur frei, wenn sie nie abgerechnet wurde" in html
    assert "await speichern('lohn',()=>api('/api/time-backoffice/personalnummern/freigeben',{method:'POST'" in html
    from app.permissions import darf_personalnummer_freigeben
    from app.models import AppUser
    assert [darf_personalnummer_freigeben(AppUser(role=r)) for r in ("admin", "buero_finanzen", "buero_auftrag", "field")] == [True, False, False, False]
    assert PersonalnummerVergabe.__tablename__ == "personalnummern_vergeben"
