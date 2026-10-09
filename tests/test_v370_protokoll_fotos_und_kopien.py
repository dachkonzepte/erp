"""Version 1.8.68 -- Nachtrag zu Stufe 2c-2e (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.68").

1. Fotos der Mängel im PDF des Abnahmeprotokolls (app/checklist_pdf.py, defect_photo_rows()): nur die Fotos, die bei der
   Unterschrift zum Mangel gehörten -- die beim Erfassen, wenn der Mangel zur Prüfsumme in der Kopie passt und die Datei zu ihrer
   Prüfsumme --, verkleinert wie die übrigen Fotos (Stufen der festen Fassung), mit Prüfsumme der Originaldatei.
2. Kopien des Protokolls genau an die in der Fassung eingefrorenen Empfänger (app/protocol_dispatch.py, frozen_copies()) --
   PDF und Mail nie auseinander; geänderte Beteiligte als Hinweis vor dem Versand (copy_changes()). Seit 1.8.69 als Personen an
   ihre Adresse von heute (app/frozen_copies.py, test_v371) -- die drei Tests dazu unten sind darauf angepasst.

Angriffe: Foto nach der Unterschrift ergänzt, Datei eines Fotos verändert, Foto am ORM vorbei in den Mangel geschoben (Prüfsumme
des Mangels passend nachgerechnet), CC über die API. Mails gehen nur an die Test-Attrappe (FakeSMTP), Adressen der eigenen Domain."""

import os
import random
import re
import stat
from io import BytesIO

from PIL import Image
from sqlalchemy import select, text

import app.acceptances as acceptances_module
from app.acceptances import content_sha256
from app.defects import defect_content
from app.models import ChecklistVersion, Defect, DefectFile, EmailDispatch, ProjectParticipant
from app.sent_documents import read_sent_document
from tests.test_v321_email_dispatch import FakeSMTP
from tests.test_v362_maengel_im_protokoll import _mangel
from tests.test_v363_zweck_abnahme import _sign_ag
from tests.test_v365_abnahme_aus_protokoll import ohne_folge, protokoll  # noqa: F401  (Fixtures)
from tests.test_v349_abnahme_und_gewaehrleistung import _welt, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v366_protokoll_seite_und_pdf import _pdf_text
from tests.test_v368_feste_fassung import _sign_an, _versions
from tests.test_v369_protokoll_versand import AG_EMAIL, ARCH_EMAIL, HV_EMAIL, _send, _state, versand  # noqa: F401

NEU_EMAIL = "architektin.neu@dachkonzepte.example"
BAU_EMAIL = "bauleitung@dachkonzepte.example"


def _foto(seed: int, size=(3000, 2000)) -> bytes:
    """Ein Foto größer als die Stufen der Fassung (Rauschen, damit es nicht winzig komprimiert)."""
    rng = random.Random(seed)
    small = Image.frombytes("RGB", (160, 120), rng.randbytes(160 * 120 * 3))
    buf = BytesIO()
    small.resize(size, Image.BILINEAR).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _beleg() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _text(pdf: bytes) -> str:
    return " ".join(_pdf_text(pdf).split())


def _image_widths(pdf: bytes) -> list[int]:
    return [int(w) for d in re.findall(rb"<<([^>]*?/Subtype /Image[^>]*?)>>", pdf)
            for w in re.findall(rb"/Width (\d+)", d)]


def _mit_fotos(p, n=2, beleg=True) -> tuple[int, list[DefectFile]]:
    """Ein zweiter Mangel mit n Fotos (3000 x 2000) und einem Beleg, vor der Unterschrift erfasst."""
    r = _mangel(p, "Rinne gerissen", photos=[(f"m{i}.jpg", _foto(i), "image/jpeg") for i in range(n)],
                receipts=[("b.pdf", _beleg(), "application/pdf")] if beleg else ())
    assert r.status_code == 200, r.text
    did = max(d["id"] for d in r.json())
    db = p["db"]
    db.expire_all()
    return did, db.scalars(select(DefectFile).where(DefectFile.defect_id == did, DefectFile.kind == "foto")
                           .order_by(DefectFile.id)).all()


def _caption(did, sha) -> str:
    return f"Foto zum Mangel Nr. {did} – Prüfsumme der Originaldatei (SHA-256): {sha}"


def _pdf(version: ChecklistVersion) -> bytes:
    return read_sent_document(version.sent_document)


# ---------------------------------------------------------------------------
# Punkt 1: Fotos der Mängel im PDF
# ---------------------------------------------------------------------------

def test_protocol_pdf_shows_the_defect_photos_reduced(protokoll):
    """Die Fassung zur Unterschrift des Auftraggebers zeigt beide Fotos verkleinert (höchstens 1600 Pixel, Hinweis im PDF), je
    mit Prüfsumme der Originaldatei; der Beleg als Anzahl; die Originale bleiben byte-gleich."""
    p, db = protokoll, protokoll["db"]
    did, fotos = _mit_fotos(p)
    original = {f.id: acceptances_module._path_for(f.stored_filename).read_bytes() for f in fotos}
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    pdf = _pdf(version)
    text_ = _text(pdf)
    for f in fotos:
        assert _caption(did, f.sha256) in text_
    assert "Belege: 1 (liegen im ERP am Mangel)" in text_ and "Fotos: 2" not in text_
    assert "Fotos in dieser Fassung auf höchstens 1600 Pixel verkleinert" in text_
    widths = _image_widths(pdf)
    assert max(widths) <= 1600 and widths.count(1600) == 2  # zwei Fotos, dazu die kleine Unterschrift
    assert {f.id: acceptances_module._path_for(f.stored_filename).read_bytes() for f in fotos} == original


def test_photos_added_after_the_signature_stay_out(protokoll):
    """Ein nach der Unterschrift ergänztes Foto (Ereignis am Mangel) gehört nicht zum Mangel bei der Unterschrift -- die nächste
    Fassung zeigt weiter genau die beiden Fotos beim Erfassen."""
    p, db = protokoll, protokoll["db"]
    did, fotos = _mit_fotos(p)
    assert _sign_ag(p).status_code == 200
    r = p["client"].post(f"/api/defects/{did}/photos", files=[("photos", ("spaeter.jpg", _foto(7), "image/jpeg"))])
    assert r.status_code == 200, r.text
    db.expire_all()
    [spaeter] = db.scalars(select(DefectFile).where(DefectFile.defect_id == did, DefectFile.event_id.is_not(None))).all()
    assert _sign_an(p).status_code == 200
    v1, v2 = _versions(db, p["c"]["id"])
    text_ = _text(_pdf(v2))
    assert [f.sha256 for f in fotos if _caption(did, f.sha256) in text_] == [f.sha256 for f in fotos]
    assert spaeter.sha256 not in text_ and text_.count("Foto zum Mangel Nr.") == 2


def test_attack_changed_photo_file_is_not_shown(protokoll):
    """Die Datei eines Fotos nach der Unterschrift verändert (am System vorbei): die nächste Fassung zeigt statt des Bildes den
    Hinweis, das andere Foto weiter; die schon abgelegte Fassung bleibt unverändert."""
    p, db = protokoll, protokoll["db"]
    did, (a, b) = _mit_fotos(p)
    assert _sign_ag(p).status_code == 200
    [v1] = _versions(db, p["c"]["id"])
    v1_sha = v1.sent_document.sha256
    path = acceptances_module._path_for(a.stored_filename)
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    path.write_bytes(_foto(99))
    assert _sign_an(p).status_code == 200
    _, v2 = _versions(db, p["c"]["id"])
    pdf = _pdf(v2)
    text_ = _text(pdf)
    assert (f"Foto zum Mangel Nr. {did} nicht gezeigt: weicht von der beim Speichern festgehaltenen Prüfsumme ab."
            in text_)
    assert _caption(did, a.sha256) not in text_ and _caption(did, b.sha256) in text_
    assert _image_widths(pdf).count(1600) == 1
    assert _pdf(v1) and v1.sent_document.sha256 == v1_sha


def test_attack_photo_pushed_into_the_defect_after_the_signature(protokoll):
    """Ein Foto am ORM vorbei als Datei beim Erfassen nachgeschoben, die Prüfsumme des Mangels passend nachgerechnet: der Mangel
    passt nicht mehr zur Kopie der Unterschrift -- die nächste Fassung zeigt keines seiner Fotos, nur den Hinweis."""
    p, db = protokoll, protokoll["db"]
    did, (a, b) = _mit_fotos(p)
    assert _sign_ag(p).status_code == 200
    db.execute(text("INSERT INTO defect_files (defect_id, event_id, kind, stored_filename, content_type, size_bytes, sha256, "
                    "created_at) VALUES (:d, NULL, 'foto', :s, :ct, :sz, :sha, CURRENT_TIMESTAMP)"),
               {"d": did, "s": b.stored_filename, "ct": b.content_type, "sz": b.size_bytes, "sha": b.sha256})
    db.commit()
    db.expire_all()
    neu = content_sha256(defect_content(db.get(Defect, did)))
    db.execute(text("UPDATE defects SET content_sha256 = :s WHERE id = :id"), {"s": neu, "id": did})
    db.commit()
    db.expire_all()
    assert _sign_an(p).status_code == 200
    _, v2 = _versions(db, p["c"]["id"])
    pdf = _pdf(v2)
    text_ = _text(pdf)
    assert "Fotos nicht gezeigt: der Mangel passt nicht zur Kopie der Unterschrift." in text_
    assert "Foto zum Mangel Nr." not in text_ and 1600 not in _image_widths(pdf)


def test_many_defect_photos_keep_the_version_under_the_limit(protokoll, monkeypatch):
    """Die Fotos der Mängel zählen in den Stufen der Fassung mit: bei enger Grenze wird verkleinert, bis das PDF passt."""
    import app.email_sending as email_sending_module

    monkeypatch.setattr(email_sending_module, "MAX_ATTACHMENT_BYTES", 250_000)
    p, db = protokoll, protokoll["db"]
    _mit_fotos(p, n=3, beleg=False)
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    text_ = _text(_pdf(version))
    assert "Fotos in dieser Fassung auf höchstens" in text_
    assert version.sent_document.size_bytes <= 250_000 or "360 Pixel" in text_


# ---------------------------------------------------------------------------
# Punkt 2: Kopien genau an die eingefrorenen Empfänger
# ---------------------------------------------------------------------------

def _cc_header(mail) -> str:
    return mail["message"]["Cc"] or ""


def test_copies_go_exactly_to_the_frozen_recipients(versand):
    """Nach der Unterschrift ändern sich die Beteiligten (Architektin neue Adresse, Hausverwaltung ohne "Kopie bei Anzeigen",
    Bauleitung neu mit Kopie): die Karte nennt alle drei Änderungen, die Mail geht trotzdem genau an die Empfänger der Fassung --
    dieselben wie "Kopie an:" im PDF; eine mitgeschickte CC-Adresse wird nicht beachtet. Seit 1.8.69 an ihre Adresse von heute:
    die Architektin an die neue (bis 1.8.68 an die der Fassung)."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    arch = db.get(ProjectParticipant, p["architektin"])
    arch.contact.email = NEU_EMAIL
    db.get(ProjectParticipant, p["verwaltung"]).copy_on_notices = False
    bau = db.get(ProjectParticipant, p["bauleitung"])
    bau.copy_on_notices, bau.contact.email = True, BAU_EMAIL
    db.commit()
    s = _state(p)
    assert s["cc"] == [NEU_EMAIL, HV_EMAIL] and "cc_prefill" not in s
    assert [(c["name"], c["email"], c["email_then"]) for c in s["version"]["copy_to"]] == [
        ("Petra Plan", NEU_EMAIL, ARCH_EMAIL), ("HV Muster", HV_EMAIL, HV_EMAIL)]
    changes = " ".join(s["copy_changes"])
    assert len(s["copy_changes"]) == 3
    assert NEU_EMAIL in changes and "HV Muster (Hausverwaltung) hat heute keine" in changes and "Bernd Bau" in changes
    r = _send(p, cc_email=f"angriff@dachkonzepte.example, {NEU_EMAIL}")
    assert r.status_code == 200, r.text
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, NEU_EMAIL, HV_EMAIL]
    assert [a.strip() for a in _cc_header(mail).split(",")] == [NEU_EMAIL, HV_EMAIL]
    [row] = db.scalars(select(EmailDispatch)).all()
    assert row.cc_recipients.replace(" ", "") == f"{NEU_EMAIL},{HV_EMAIL}"
    kopie = _text(_pdf(version)).split("Kopie an: ")[1].split("Abschluss")[0]
    assert "Petra Plan" in kopie and "HV Muster" in kopie and "Bernd Bau" not in kopie


def test_frozen_recipient_without_address_gets_no_mail(versand):
    """Die Hausverwaltung hat bei der Unterschrift keine E-Mail-Adresse und seither eine: seit 1.8.69 bekommt sie die Kopie an die
    Adresse von heute (bis 1.8.68 keine Mail), der Hinweis nennt beide. Umgekehrt (Adresse seither weg) keine Mail."""
    p, db = versand, versand["db"]
    db.get(ProjectParticipant, p["verwaltung"]).contact.email = None
    db.commit()
    assert _sign_ag(p).status_code == 200
    db.get(ProjectParticipant, p["verwaltung"]).contact.email = HV_EMAIL
    db.commit()
    db.get(ProjectParticipant, p["architektin"]).contact.email = None
    db.commit()
    s = _state(p)
    assert [(c["name"], c["email"], c["email_then"]) for c in s["version"]["copy_to"]] == [
        ("Petra Plan", None, ARCH_EMAIL), ("HV Muster", HV_EMAIL, None)]
    assert s["cc"] == [HV_EMAIL]
    assert s["copy_changes"] == [
        f"Petra Plan (Architekt/Planer): heute keine E-Mail-Adresse statt {ARCH_EMAIL} – keine Mail; die Kopie bitte auf anderem "
        "Weg zustellen.",
        f"HV Muster (Hausverwaltung): E-Mail-Adresse heute {HV_EMAIL} statt keine – die Kopie geht an {HV_EMAIL}."]
    assert _send(p).status_code == 200
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, HV_EMAIL]


def test_client_address_among_the_copies_is_not_doubled(versand):
    p, db = versand, versand["db"]
    db.get(ProjectParticipant, p["architektin"]).contact.email = AG_EMAIL
    db.commit()
    assert _sign_ag(p).status_code == 200
    assert _state(p)["cc"] == [HV_EMAIL]
    assert _send(p).status_code == 200
    [mail] = FakeSMTP.sent
    assert mail["recipients"] == [AG_EMAIL, HV_EMAIL]


def test_version_before_1_8_68_uses_the_address_of_the_same_participant_today(versand):
    """Eine Fassung von 1.8.66/1.8.67 hat in "Kopie an:" noch keine Adresse: dieselben Beteiligten wie im PDF, mit ihrer Adresse
    von heute; kein Hinweis auf eine geänderte Adresse (die alte ist unbekannt). Seit 1.8.69 gilt die Adresse von heute für alle
    Fassungen -- "email_source" gibt es nicht mehr, then_known sagt, ob die alte bekannt ist."""
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    [version] = _versions(db, p["c"]["id"])
    alt = version.copy_to.replace(f', "email": "{ARCH_EMAIL}"', "").replace(f', "email": "{HV_EMAIL}"', "")
    assert "email" not in alt
    db.execute(text("UPDATE checklist_versions SET copy_to = :c WHERE id = :id"), {"c": alt, "id": version.id})
    db.get(ProjectParticipant, p["architektin"]).contact.email = NEU_EMAIL
    db.commit()
    db.expire_all()
    s = _state(p)
    assert [(c["email"], c["then_known"]) for c in s["version"]["copy_to"]] == [(NEU_EMAIL, False), (HV_EMAIL, False)]
    assert s["cc"] == [NEU_EMAIL, HV_EMAIL] and s["copy_changes"] == []
    assert _send(p).status_code == 200
    assert FakeSMTP.sent[0]["recipients"] == [AG_EMAIL, NEU_EMAIL, HV_EMAIL]

