"""Feste Fassung einer Checkliste (seit 1.8.66, Stufe 2c-2e, Punkt 1, Modul "checklisten").

Herleitung: docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.66". Jede Unterschrift legt das PDF der Checkliste im
Stand genau dieses Moments als feste Fassung in die Ablage (app/sent_documents.py: Art "checkliste", Dokument-ID = Checkliste,
Nummer "Nr. … · Fassung N", SHA-256) -- im selben Commit wie die Unterschrift, unter der Zeilensperre der Checkliste: keine
Unterschrift ohne Fassung, und zwischen Unterschrift und PDF kann keine Antwort dazwischenkommen. Ebenso der Abschluss und "als
gegenstandslos abschließen" (Festlegung 1.8.66 Nr. 1). Danach wird dieses PDF nie neu erzeugt: Download, Versand und
nachgetragene Zustellung verwenden die abgelegten Bytes, nur mit stimmender Prüfsumme (sonst 409/410, nie still neu gerendert).

Überholt (abgeleitet, nicht gespeichert): eine Fassung zeigt die Unterschriften, die beim Erstellen galten (signature_ids). Ist
eine davon inzwischen verworfen -- die eigene oder eine andere, die das PDF als gültig zeigt --, ist die Fassung überholt und wird
nicht mehr versendet. Eine Fassung des Abschlusses wird nie überholt (danach lässt sich nichts mehr verwerfen).

Größe: wie das Versand-PDF der Checkliste (app/checklist_pdf.py, EMAIL_PHOTO_STEPS) werden die Fotos stufenweise im Speicher
verkleinert, bis das PDF unter 3.000.000 Bytes liegt -- so lässt sich jede Fassung per E-Mail versenden. Passt es auch mit der
kleinsten Stufe nicht, bleibt diese (der Versand meldet dann die Größe, Zustellung auf anderem Weg). Die Originale bleiben
unverändert im ERP; das PDF sagt, auf wie viele Pixel verkleinert wurde.

Rollenlos; die Liste der Fassungen sieht nur das Büro (app/routers/checklists.py), die Dateien liefert die Ablage
(GET /api/sent-documents/{id}/file, ab buero_auftrag). Der PDF-Renderer wird lokal importiert (Regel 3)."""

import json
import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .berlin_time import to_berlin
from .models import Checklist, ChecklistAttachment, ChecklistVersion

logger = logging.getLogger(__name__)

VERSION_KINDS = {"unterschrift": "nach einer Unterschrift", "abschluss": "beim Abschluss",
                 "gegenstandslos": "beim Abschluss als gegenstandslos"}


def _next_no(db: Session, checklist_id: int) -> int:
    return (db.scalar(select(func.max(ChecklistVersion.version_no)).where(ChecklistVersion.checklist_id == checklist_id))
            or 0) + 1


def create_version(db: Session, checklist: Checklist, *, kind: str, signature: ChecklistAttachment | None = None,
                   user_id: int | None = None, user_name: str | None = None) -> ChecklistVersion:
    """Rendert das PDF des jetzigen Stands, legt es ab und trägt die Fassung ein (flush, kein Commit -- der Aufrufer committet
    mit der Unterschrift bzw. dem Abschluss). Aufruf unter der Zeilensperre der Checkliste, nachdem die Unterschrift bzw. die
    Kopie des Abschlusses geschrieben (geflusht) ist. ValueError, wenn das PDF nicht entsteht -- dann rollt der Aufrufer zurück."""
    from .audit import current_actor
    from .checklist_pdf import build_checklist_version_pdf  # lokal, Regel 3
    from .checklists import active_attachments
    from .sent_documents import store_sent_document

    if kind not in VERSION_KINDS:
        raise ValueError(f"Unbekannter Anlass einer Fassung: {kind}")
    if user_id is None and user_name is None:
        user_id, user_name = current_actor()
    user_name = (user_name or "System")[:160]
    version_no = _next_no(db, checklist.id)
    signature_ids = sorted(a.id for a in active_attachments(checklist) if a.kind == "unterschrift")
    stand = {"version_no": version_no, "kind": kind, "signature": signature,
             "at": signature.created_at if signature is not None else checklist.completed_at}
    try:
        pdf = build_checklist_version_pdf(db, checklist, stand)
    except Exception as exc:  # noqa: BLE001 -- ohne PDF keine Unterschrift und kein Abschluss
        logger.error("Checkliste %s: feste Fassung %s nicht erstellt (%s)", checklist.id, version_no, type(exc).__name__)
        raise ValueError("Die feste Fassung (PDF) der Checkliste ließ sich nicht erstellen – es wurde nichts gespeichert. "
                         "Bitte erneut versuchen; bleibt es dabei, das Büro verständigen.") from exc
    document = store_sent_document(
        db, document_type="checkliste", document_id=checklist.id,
        document_number=f"Nr. {checklist.id} · Fassung {version_no}"[:80],
        filename=f"Checkliste-{checklist.id}-Fassung-{version_no}.pdf", content=pdf, user_id=user_id, user_name=user_name,
    )
    version = ChecklistVersion(
        checklist_id=checklist.id, version_no=version_no, kind=kind,
        signature_id=signature.id if signature is not None else None, signature_ids=json.dumps(signature_ids),
        seal_sha256=signature.content_sha256 if signature is not None else checklist.content_sha256,
        sent_document_id=document.id, created_at=datetime.utcnow(), created_by_user_id=user_id, created_by_name=user_name,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:  # Nummer oder Unterschrift schon vergeben -- unter der Zeilensperre nicht zu erwarten
        raise ValueError("Inzwischen ist eine andere Fassung dieser Checkliste entstanden – bitte die Seite neu laden und "
                         "erneut versuchen.") from exc
    return version


def versions_of(db: Session, checklist_id: int) -> list[ChecklistVersion]:
    return list(db.scalars(select(ChecklistVersion).options(selectinload(ChecklistVersion.sent_document))
                           .where(ChecklistVersion.checklist_id == checklist_id)
                           .order_by(ChecklistVersion.version_no)).all())


def shown_signature_ids(version: ChecklistVersion) -> list[int]:
    return list(json.loads(version.signature_ids or "[]"))


def superseded_by(version: ChecklistVersion, checklist: Checklist) -> ChecklistAttachment | None:
    """Die (zuerst) verworfene Unterschrift, die diese Fassung als gültig zeigt -- None, solange die Fassung gilt."""
    shown = set(shown_signature_ids(version))
    discarded = [a for a in checklist.attachments if a.id in shown and a.discarded_at is not None]
    return min(discarded, key=lambda a: (a.discarded_at, a.id), default=None)


def version_valid(version: ChecklistVersion, checklist: Checklist) -> bool:
    return superseded_by(version, checklist) is None


def latest_valid_version(db: Session, checklist: Checklist) -> ChecklistVersion | None:
    """Die jüngste Fassung, die noch gilt (keine der gezeigten Unterschriften verworfen)."""
    return next((v for v in reversed(versions_of(db, checklist.id)) if version_valid(v, checklist)), None)


def completion_version(db: Session, checklist: Checklist) -> ChecklistVersion | None:
    """Die Fassung des Abschlusses (abgeschlossen oder gegenstandslos) -- None bei einem Entwurf und bei Checklisten, die vor
    1.8.66 abgeschlossen wurden (deren PDF wird wie bisher neu erzeugt)."""
    return next((v for v in reversed(versions_of(db, checklist.id)) if v.kind != "unterschrift"), None)


def version_to_dict(version: ChecklistVersion, checklist: Checklist) -> dict:
    from .sent_documents import sent_document_to_dict

    labels = {f.id: f.label for f in checklist.template_version.fields}
    by_id = {a.id: a for a in checklist.attachments}
    signature = by_id.get(version.signature_id) if version.signature_id is not None else None
    superseded = superseded_by(version, checklist)
    return {
        "id": version.id, "version_no": version.version_no, "kind": version.kind,
        "kind_label": VERSION_KINDS.get(version.kind, version.kind),
        "signature_id": version.signature_id,
        "signature": None if signature is None else {
            "field_label": labels.get(signature.template_field_id, "Unterschrift"), "signer_name": signature.signer_name,
            "signed_at_local": to_berlin(signature.created_at)},
        "seal_sha256": version.seal_sha256, "created_at": version.created_at,
        "created_at_local": to_berlin(version.created_at), "created_by_name": version.created_by_name,
        "valid": superseded is None,
        "superseded": None if superseded is None else {
            "field_label": labels.get(superseded.template_field_id, "Unterschrift"), "signer_name": superseded.signer_name,
            "discarded_at": superseded.discarded_at, "discarded_at_local": to_berlin(superseded.discarded_at),
            "discarded_by_name": superseded.discarded_by_name},
        "sent_document": sent_document_to_dict(version.sent_document),
    }


def list_versions(db: Session, checklist: Checklist) -> list[dict]:
    """Alle Fassungen der Checkliste fürs Büro, älteste zuerst, mit gilt/überholt."""
    return [version_to_dict(v, checklist) for v in versions_of(db, checklist.id)]
