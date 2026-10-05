"""Unterschrift unter dem Vertrag (seit 1.8.34, Stufe 2b, Runde 2b-1b Teil 2b).

Zwei Wege, beide nur für die gültige festgeschriebene Fassung (app/contract_versions.py):

- Auf dem Gerät (sign_contract_on_device()): Kunde und Betrieb unterschreiben nacheinander auf derselben
  Zeichenfläche (app/templates/_unterschrift.html). Die Anfrage trägt die ID der Fassung und die
  PDF-Prüfsumme, die der Kunde gesehen hat -- eine andere als die der gültigen Fassung (falsche,
  abgelöste, inzwischen neu festgeschriebene) wird mit 409 abgelehnt, ebenso eine Fassung, die nicht mehr
  zum Auftrag passt (version_differences()) oder deren PDF in der Ablage nicht mehr unversehrt ist. Die
  Ankreuzfelder der Fassung (Abschnitte mit Ankreuzfeld im eingefrorenen Inhalt, z. B. das Verlangen des
  vorzeitigen Beginns) setzt der Kunde beim Unterschreiben; jedes muss ausdrücklich angekreuzt oder nicht
  angekreuzt übergeben werden. Ergebnis: Unterschriftsblatt (PDF) und beide Unterschriftsbilder in der
  Ablage.
- Papier (record_paper_signature()): das Büro lädt den Scan des unterschriebenen Papiers hoch (am Inhalt
  erkannt wie der Beleg einer Zustellung, app/email_dispatch.py::receipt_content_type()), mit dem Datum der
  Unterschrift und den vom Papier übertragenen Ankreuzfeldern. Festlegung: eine Abweichung der Fassung vom
  Auftrag sperrt das Eintragen hier nicht -- der Kunde hat womöglich vor der Änderung unterschrieben; die
  Karte zeigt die Abweichung danach als Hinweis wie bei jeder Unterschrift.

Beide Wege legen den unterschriebenen Inhalt als kanonisches JSON mit Prüfsumme ab (Fassung, deren
Inhalts- und PDF-Prüfsumme, Ankreuzfelder mit Stand, Namen, Prüfsummen der Bilder bzw. des Scans, Datum)
und setzen den Vertrag auf "unterschrieben": danach keine neue Fassung, Vertragsgrundlage und Abgleich am
Auftrag gesperrt (app/contract_basis.py::ensure_contract_not_signed()). Spätere Änderungen am Auftrag
machen den Vertrag nicht ungültig; die Karte zeigt sie nur.

Unterschriebene Abschrift (seit 1.8.35): mit der Unterschrift entsteht ein PDF aus der Fassung und dem
Unterschriftsblatt bzw. -- auf Papier -- dem Scan (ein Foto als eigene Seite), mit eigener Prüfsumme in der
Ablage (OrderContractSignature.copy_document_id). Versand und Zustellung nach der Unterschrift verwenden
sie (app/contract_versions.py::deliverable_document()): bei Verbrauchern außerhalb von Geschäftsräumen
verlangt § 312f BGB eine Abschrift des unterzeichneten Vertrags. Eine Unterschrift von vor 1.8.35 bekommt
ihre Abschrift beim ersten Versand (ensure_signed_copy()), aus den Dateien in der Ablage.

Gleichzeitigkeit: Unterschreiben, Festschreiben, "Neue Fassung", Vertragsgrundlage ändern und Abgleich
sperren dieselbe Vertragszeile (SELECT ... FOR UPDATE, PostgreSQL); der Statuswechsel ist zusätzlich ein
bedingtes UPDATE, und je Vertrag gibt es höchstens eine Unterschrift (unique).

Widerrufsfrist (withdrawal_info()): nur bei einem Verbrauchervertrag (Verbraucher-Merkmal der Fassung).
Voraussichtliches Ende = Tag der Unterschrift + 14 Tage; fällt es auf einen Samstag oder Sonntag, der
nächste Montag (§ 193 BGB) -- Feiertage kennt das ERP nicht. Vermerk, ob der vorzeitige Beginn verlangt
wurde: das als solches gekennzeichnete Ankreuzfeld der Vorlage (early_start); ohne Kennzeichen sagt die
Karte das.

Rollenlos wie jede Geschäftslogik; wer was darf, entscheidet app/routers/contract_templates.py.
"""

import hashlib
import json
from datetime import date, datetime, timedelta
from io import BytesIO

from sqlalchemy import update
from sqlalchemy.orm import Session

from . import contract_versions
from .berlin_time import berlin_today, to_berlin
from .contract_versions import (
    CONTRACT_ENTITY_TYPE, ContractStateError, canonical_json, checkbox_sections, contract_document_number,
    current_version, frozen_content, sha256_text, version_differences,
)
from .models import Order, OrderContract, OrderContractSignature, OrderContractVersion, SentDocument
from .signature_image import check_signature_png
from .sent_documents import (
    CONTENT_TYPE_SUFFIXES, ArchiveFileError, read_sent_document, sent_document_to_dict, store_sent_document,
    verify_sent_document,
)

METHODS = {"geraet": "auf dem Gerät", "papier": "auf Papier (Scan)"}
MAX_SCAN_BYTES = 15_000_000  # wie der Beleg einer Zustellung
MAX_SIGNER_NAME = 160
WITHDRAWAL_DAYS = 14
SCAN_PAGE_MARGIN_MM = 10
SCAN_JPEG_QUALITY = 88


# --- Eingaben ---------------------------------------------------------------------------------------

def _signer_name(value: str | None, who: str) -> str:
    name = " ".join((value or "").split())
    if not name:
        raise ValueError(f"Bitte den Namen {who} angeben.")
    if len(name) > MAX_SIGNER_NAME:
        raise ValueError(f"Der Name {who} ist zu lang (höchstens {MAX_SIGNER_NAME} Zeichen).")
    return name


def _box_label(box: dict) -> str:
    text = box["heading"] or box["text"] or box["key"]
    return text if len(text) <= 60 else text[:59] + "…"


def checkbox_values(content: dict, values: dict | None) -> list[dict]:
    """Der Stand jedes Ankreuzfelds der Fassung, in ihrer Reihenfolge. Jedes muss ausdrücklich mit
    true/false übergeben werden; ein fehlendes, ein anderer Wert oder ein unbekannter Schlüssel: ValueError."""
    values = values or {}
    boxes = checkbox_sections(content)
    unknown = sorted(set(values) - {b["key"] for b in boxes})
    if unknown:
        raise ValueError(f"Diese Ankreuzfelder gibt es in der Fassung nicht: {', '.join(unknown)}.")
    missing = [_box_label(b) for b in boxes if not isinstance(values.get(b["key"]), bool)]
    if missing:
        raise ValueError(
            "Bitte jedes Ankreuzfeld ausdrücklich setzen (angekreuzt oder nicht angekreuzt): " + "; ".join(missing)
        )
    return [{**b, "checked": values[b["key"]]} for b in boxes]


# --- Unterschriebene Abschrift (seit 1.8.35) --------------------------------------------------------

def _photo_page(scan: bytes) -> bytes:
    """Ein Foto des unterschriebenen Papiers als PDF-Seite (A4, hoch oder quer wie das Bild, 10 mm Rand).
    Ausrichtung nach EXIF; ein JPEG ohne Drehung wird ohne Neukodierung eingebettet (reportlab schreibt es
    ASCII85-kodiert, rund ein Viertel größer), alles andere als JPEG (Durchsichtiges auf Weiß)."""
    from PIL import Image, ImageOps
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    with Image.open(BytesIO(scan)) as image:
        if image.format == "JPEG" and image.mode in ("RGB", "L") and image.getexif().get(0x0112, 1) == 1:
            data, (width, height) = scan, image.size
        else:
            upright = ImageOps.exif_transpose(image)
            if upright.mode in ("RGBA", "LA", "P", "PA"):
                rgba = upright.convert("RGBA")
                upright = Image.new("RGB", rgba.size, "white")
                upright.paste(rgba, mask=rgba.getchannel("A"))
            else:
                upright = upright.convert("RGB")
            buf = BytesIO()
            upright.save(buf, "JPEG", quality=SCAN_JPEG_QUALITY)
            data, (width, height) = buf.getvalue(), upright.size
    page_w, page_h = landscape(A4) if width > height else A4
    margin = SCAN_PAGE_MARGIN_MM * mm
    scale = min((page_w - 2 * margin) / width, (page_h - 2 * margin) / height)
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(page_w, page_h))
    pdf.setTitle("Scan des unterschriebenen Vertrags")
    pdf.drawImage(ImageReader(BytesIO(data)), (page_w - width * scale) / 2, (page_h - height * scale) / 2,
                  width=width * scale, height=height * scale)
    pdf.showPage()
    pdf.save()
    return out.getvalue()


def scan_pages(scan: bytes, content_type: str) -> bytes:
    """Der Papier-Scan als PDF für die Abschrift: ein PDF unverändert -- es muss sich öffnen lassen und
    mindestens eine Seite haben (ValueError) --, ein Foto als eigene Seite."""
    if content_type != "application/pdf":
        return _photo_page(scan)
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(scan)
        try:
            pages = len(doc)
        finally:
            doc.close()
    except pdfium.PdfiumError as e:
        raise ValueError("Der Scan lässt sich nicht als PDF öffnen (beschädigt oder mit Kennwort geschützt).") from e
    if pages < 1:
        raise ValueError("Der Scan enthält keine Seite.")
    return scan


def signed_copy_number(order_number: str, version_no: int) -> str:
    """Nummer der Abschrift in Ablage und Versandprotokoll: die der Fassung mit "· unterschrieben"."""
    return f"{contract_document_number(order_number, version_no)} · unterschrieben"


def _store_signed_copy(
    db: Session, order: Order, contract: OrderContract, version: OrderContractVersion, *, version_pdf: bytes,
    signature_pages: bytes, user_id: int | None, user_name: str,
) -> SentDocument:
    """Fassung und Unterschriftsblatt bzw. Scan zu einem PDF zusammenführen und ablegen (flush, kein Commit)."""
    from .contract_pdf import merge_pdfs

    return store_sent_document(
        db, document_type="vertrag", document_id=contract.id,
        document_number=signed_copy_number(order.order_number, version.version_no),
        filename=_filename(order, version, "unterschrieben.pdf"), content=merge_pdfs([version_pdf, signature_pages]),
        user_id=user_id, user_name=user_name,
    )


def ensure_signed_copy(
    db: Session, order: Order, contract: OrderContract, *, user_id: int | None = None, user_name: str | None = None,
) -> SentDocument:
    """Die unterschriebene Abschrift. Eine Unterschrift von vor 1.8.35 hat keine: dann wird sie hier einmal
    aus der Fassung und dem Unterschriftsblatt bzw. Scan in der Ablage erzeugt, abgelegt und eingetragen
    (bedingtes UPDATE von leer unter der Vertragssperre; committet). Wirft ContractStateError, wenn der
    Vertrag nicht unterschrieben ist oder eine der Dateien in der Ablage nicht mehr unversehrt ist."""
    from .audit import current_actor, record_audit_entry

    signature = contract.signature
    if signature is None:
        raise ContractStateError("Der Vertrag ist nicht unterschrieben.")
    if signature.copy_document is not None:
        return signature.copy_document
    if user_id is None and user_name is None:
        user_id, user_name = current_actor()
    user_name = user_name or "System"
    try:
        contract = contract_versions._locked_contract(db, order.id)
        db.expire_all()
        signature = contract.signature
        if signature.copy_document is not None:  # ein gleichzeitiger Versand war schneller
            copy = signature.copy_document
            db.commit()
            return copy
        version = signature.version
        try:
            version_pdf = read_sent_document(version.sent_document)
            part = read_sent_document(signature.document)
        except ArchiveFileError as e:
            raise ContractStateError(
                f"Die unterschriebene Abschrift lässt sich nicht erzeugen: Fassung {version.version_no} bzw. "
                f"Unterschriftsblatt/Scan in der Ablage ist nicht mehr unversehrt ({e}). Es wurde nichts versendet."
            ) from e
        copy = _store_signed_copy(
            db, order, contract, version, version_pdf=version_pdf,
            signature_pages=scan_pages(part, signature.document.content_type), user_id=user_id, user_name=user_name,
        )
        claimed = db.execute(
            update(OrderContractSignature)
            .where(OrderContractSignature.id == signature.id, OrderContractSignature.copy_document_id.is_(None))
            .values(copy_document_id=copy.id).execution_options(synchronize_session=False)
        ).rowcount
        if claimed != 1:
            raise ContractStateError("Die Abschrift wurde inzwischen erzeugt. Bitte erneut versuchen.")
        record_audit_entry(
            db, action="geändert", entity_type=CONTRACT_ENTITY_TYPE, entity_id=contract.id,
            entity_label=f"Vertrag zu Auftrag {order.order_number}", project_id=order.project_id,
            field_name="copy_document_id", field_label="Unterschriebene Abschrift nachgeholt",
            new_value=f"Fassung {version.version_no} · Prüfsumme {copy.sha256}",
            actor_user_id=user_id, actor_name=user_name,
        )
        db.commit()
    except Exception:
        # Eine schon abgelegte Datei bleibt ohne Eintrag liegen -- die Ablage löscht nie.
        db.rollback()
        raise
    return copy


# --- Gemeinsamer Ablauf -----------------------------------------------------------------------------

def _signable(
    db: Session, order: Order, *, version_id: int, pdf_sha256: str, require_matching: bool,
) -> tuple[OrderContract, OrderContractVersion, bytes]:
    """Sperrt den Vertrag und prüft, ob genau diese Fassung unterschrieben werden darf (ContractStateError).
    Liefert dazu die geprüften Bytes ihres PDFs (für die Abschrift)."""
    contract = contract_versions._locked_contract(db, order.id)
    if contract is None:
        raise LookupError("Zu diesem Auftrag gibt es keinen Vertrag.")
    # Nach der Sperre alles frisch lesen: eine gleichzeitige Änderung (neue Fassung, Vertragsgrundlage,
    # Abgleich) ist jetzt entweder vollständig sichtbar oder wartet auf diese Transaktion.
    db.expire_all()
    if contract.status == "unterschrieben":
        raise ContractStateError("Der Vertrag ist bereits unterschrieben.")
    version = current_version(contract)
    if contract.status != "festgeschrieben" or version is None:
        raise ContractStateError("Unterschrieben wird nur ein festgeschriebener Vertrag – bitte zuerst festschreiben.")
    if version.id != version_id:
        raise ContractStateError(
            f"Die Fassung, die unterschrieben werden sollte, ist nicht die gültige (gültig ist Fassung "
            f"{version.version_no}). Bitte die Seite neu laden und die gültige Fassung zeigen."
        )
    if (pdf_sha256 or "").strip().lower() != version.sent_document.sha256:
        raise ContractStateError(
            f"Die Prüfsumme passt nicht zum PDF der Fassung {version.version_no} – unterschrieben wird nur genau "
            "das abgelegte PDF. Bitte die Seite neu laden."
        )
    try:
        version_pdf = read_sent_document(version.sent_document)
    except ArchiveFileError as e:
        raise ContractStateError(f"Die Fassung {version.version_no} in der Ablage ist nicht mehr unversehrt: {e}") from e
    if require_matching:
        differences = version_differences(db, order, version)
        if differences:
            raise ContractStateError(
                f"Fassung {version.version_no} passt nicht mehr zum Auftrag ({'; '.join(differences)}). "
                "Bitte eine neue Fassung festschreiben."
            )
    return contract, version, version_pdf


def _signed_content(
    order: Order, contract: OrderContract, version: OrderContractVersion, content: dict, *, method: str,
    signed_on: date, boxes: list[dict], recorded_at: datetime, recorded_by: str, **extra,
) -> dict:
    return {
        "v": 1,
        "contract_id": contract.id, "order_id": order.id, "order_number": order.order_number,
        "version_id": version.id, "version_no": version.version_no,
        "version_content_sha256": version.content_sha256, "pdf_sha256": version.sent_document.sha256,
        "basis_key": version.basis_key, "is_consumer": bool(version.is_consumer),
        "method": method, "signed_on": signed_on.isoformat(),
        "checkboxes": [
            {"key": b["key"], "heading": b["heading"], "text": b["text"], "early_start": b["early_start"], "checked": b["checked"]}
            for b in boxes
        ],
        "recorded_at": recorded_at.isoformat(timespec="seconds"), "recorded_by": recorded_by,
        "customer": None, "company": None, "scan": None,
        **extra,
    }


def _finish(
    db: Session, order: Order, contract: OrderContract, version: OrderContractVersion, signed: dict, *,
    document_id: int, copy: SentDocument, customer_image_id: int | None = None, company_image_id: int | None = None,
    user_id: int | None, user_name: str, now: datetime,
) -> OrderContractSignature:
    from .audit import record_audit_entry

    text = canonical_json(signed)
    claimed = db.execute(
        update(OrderContract).where(OrderContract.id == contract.id, OrderContract.status == "festgeschrieben")
        .values(status="unterschrieben", updated_at=now, updated_by_name=user_name)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        raise ContractStateError("Der Vertrag wurde inzwischen geändert. Bitte die Seite neu laden.")
    signature = OrderContractSignature(
        contract_id=contract.id, version_id=version.id, method=signed["method"],
        signed_on=date.fromisoformat(signed["signed_on"]),
        customer_signer_name=(signed["customer"] or {}).get("name"),
        company_signer_name=(signed["company"] or {}).get("name"),
        signed_content=text, content_sha256=sha256_text(text), document_id=document_id,
        customer_image_document_id=customer_image_id, company_image_document_id=company_image_id,
        recorded_at=now, recorded_by_user_id=user_id, recorded_by_name=user_name, copy_document_id=copy.id,
    )
    db.add(signature)
    checked = [f"{_box_label(b)}: {'angekreuzt' if b['checked'] else 'nicht angekreuzt'}" for b in signed["checkboxes"]]
    record_audit_entry(
        db, action="geändert", entity_type=CONTRACT_ENTITY_TYPE, entity_id=contract.id,
        entity_label=f"Vertrag zu Auftrag {order.order_number}", project_id=order.project_id,
        field_name="status", field_label="Vertrag unterschrieben",
        old_value=f"Fassung {version.version_no} festgeschrieben",
        new_value=(f"Fassung {version.version_no} {METHODS[signed['method']]} am "
                   f"{date.fromisoformat(signed['signed_on']):%d.%m.%Y}" + (f" · {'; '.join(checked)}" if checked else "")
                   + f" · Prüfsumme {signature.content_sha256} · Abschrift {copy.sha256}"),
        actor_user_id=user_id, actor_name=user_name,
    )
    db.commit()
    db.refresh(signature)
    return signature


def _filename(order: Order, version: OrderContractVersion, suffix: str) -> str:
    return f"Vertrag_{order.order_number}_Fassung_{version.version_no}_{suffix}".replace("/", "-").replace("\\", "-")


# --- Auf dem Gerät ----------------------------------------------------------------------------------

def sign_contract_on_device(
    db: Session, order: Order, *, version_id: int, pdf_sha256: str, checkboxes: dict | None,
    customer_name: str, customer_png: bytes, company_name: str, company_png: bytes,
    user_id: int | None = None, user_name: str | None = None,
) -> OrderContractSignature:
    """Unterschrift von Kunde und Betrieb auf dem Gerät. Wirft ValueError (Eingabe, 400), LookupError (kein
    Vertrag, 404), ContractStateError (Zustand oder falsche Fassung, 409)."""
    from .contract_pdf import render_signature_sheet_pdf

    user_name = user_name or "System"
    customer_name = _signer_name(customer_name, "des Kunden")
    company_name = _signer_name(company_name, "der Person, die für den Betrieb unterschreibt")
    # Seit 1.8.56 die gemeinsame Prüfung aller Unterschrift-Wege (app/signature_image.py), vorher eine eigene hier.
    check_signature_png(customer_png, "des Kunden")
    check_signature_png(company_png, "für den Betrieb")
    try:
        contract, version, version_pdf = _signable(db, order, version_id=version_id, pdf_sha256=pdf_sha256,
                                                   require_matching=True)
        content = frozen_content(version)
        boxes = checkbox_values(content, checkboxes)
        now = datetime.utcnow()
        number = contract_document_number(order.order_number, version.version_no)
        stored = {}
        for key, png in (("Kunde", customer_png), ("Betrieb", company_png)):
            stored[key] = store_sent_document(
                db, document_type="vertrag", document_id=contract.id, document_number=number,
                filename=_filename(order, version, f"Unterschrift_{key}.png"), content=png,
                user_id=user_id, user_name=user_name, content_type="image/png",
            )
        signed = _signed_content(
            order, contract, version, content, method="geraet", signed_on=berlin_today(), boxes=boxes,
            recorded_at=now, recorded_by=user_name,
            customer={"name": customer_name, "image_sha256": stored["Kunde"].sha256},
            company={"name": company_name, "image_sha256": stored["Betrieb"].sha256},
        )
        sheet = render_signature_sheet_pdf(
            db, content, signed, content_sha256=sha256_text(canonical_json(signed)),
            customer_png=customer_png, company_png=company_png, recorded_local=to_berlin(now),
        )
        document = store_sent_document(
            db, document_type="vertrag", document_id=contract.id, document_number=number,
            filename=_filename(order, version, "Unterschriftsblatt.pdf"), content=sheet,
            user_id=user_id, user_name=user_name,
        )
        copy = _store_signed_copy(db, order, contract, version, version_pdf=version_pdf, signature_pages=sheet,
                                  user_id=user_id, user_name=user_name)
        return _finish(db, order, contract, version, signed, document_id=document.id, copy=copy,
                       customer_image_id=stored["Kunde"].id, company_image_id=stored["Betrieb"].id,
                       user_id=user_id, user_name=user_name, now=now)
    except Exception:
        # Schon abgelegte Dateien bleiben ohne Eintrag liegen -- die Ablage löscht nie (wie beim Festschreiben).
        db.rollback()
        raise


# --- Papier -----------------------------------------------------------------------------------------

def record_paper_signature(
    db: Session, order: Order, *, version_id: int, pdf_sha256: str, signed_on: date, checkboxes: dict | None,
    scan_bytes: bytes, user_id: int | None = None, user_name: str | None = None,
) -> OrderContractSignature:
    """Scan des unterschriebenen Papiers mit Datum und vom Büro übertragenen Ankreuzfeldern. Wirft ValueError
    (400), LookupError (404), ContractStateError (409)."""
    from .email_dispatch import receipt_content_type

    user_name = user_name or "System"
    if not scan_bytes:
        raise ValueError("Bitte den Scan des unterschriebenen Vertrags hochladen.")
    if len(scan_bytes) > MAX_SCAN_BYTES:
        raise ValueError(f"Der Scan ist größer als {MAX_SCAN_BYTES // 1_000_000} MB.")
    try:
        scan_type = receipt_content_type(scan_bytes)
    except ValueError as e:
        raise ValueError("Der Scan muss ein PDF oder ein Foto (JPEG, PNG, WebP) sein.") from e
    pages = scan_pages(scan_bytes, scan_type)  # für die Abschrift; ein PDF muss sich öffnen lassen
    if signed_on is None:
        raise ValueError("Bitte das Datum der Unterschrift angeben.")
    if signed_on > berlin_today():
        raise ValueError("Das Datum der Unterschrift liegt in der Zukunft.")
    try:
        contract, version, version_pdf = _signable(db, order, version_id=version_id, pdf_sha256=pdf_sha256,
                                                   require_matching=False)
        if signed_on < to_berlin(version.created_at).date():
            raise ValueError(
                f"Das Datum der Unterschrift liegt vor dem Festschreiben der Fassung {version.version_no} "
                f"({to_berlin(version.created_at):%d.%m.%Y})."
            )
        boxes = checkbox_values(frozen_content(version), checkboxes)
        now = datetime.utcnow()
        document = store_sent_document(
            db, document_type="vertrag", document_id=contract.id,
            document_number=contract_document_number(order.order_number, version.version_no),
            filename=_filename(order, version, f"Unterschrift_Papier{CONTENT_TYPE_SUFFIXES[scan_type]}"), content=scan_bytes,
            user_id=user_id, user_name=user_name, content_type=scan_type,
        )
        signed = _signed_content(
            order, contract, version, frozen_content(version), method="papier", signed_on=signed_on, boxes=boxes,
            recorded_at=now, recorded_by=user_name,
            scan={"sha256": document.sha256, "content_type": scan_type, "filename": document.filename},
        )
        copy = _store_signed_copy(db, order, contract, version, version_pdf=version_pdf, signature_pages=pages,
                                  user_id=user_id, user_name=user_name)
        return _finish(db, order, contract, version, signed, document_id=document.id, copy=copy,
                       user_id=user_id, user_name=user_name, now=now)
    except Exception:
        db.rollback()
        raise


# --- Anzeige ----------------------------------------------------------------------------------------

def withdrawal_info(signed: dict) -> dict | None:
    """Voraussichtliches Ende der Widerrufsfrist bei einem Verbrauchervertrag, mit Vermerk zum vorzeitigen
    Beginn (siehe Moduldocstring). None, wenn kein Verbrauchervertrag."""
    if not signed.get("is_consumer"):
        return None
    signed_on = date.fromisoformat(signed["signed_on"])
    deadline = signed_on + timedelta(days=WITHDRAWAL_DAYS)
    shifted = False
    while deadline.weekday() >= 5:
        deadline += timedelta(days=1)
        shifted = True
    marked = [b for b in signed.get("checkboxes", []) if b.get("early_start")]
    return {
        "signed_on": signed_on, "deadline": deadline, "shifted_from_weekend": shifted,
        "early_start": marked[0]["checked"] if marked else None,
        "early_start_label": _box_label(marked[0]) if marked else None,
        "running": berlin_today() <= deadline,
    }


def signature_to_dict(signature: OrderContractSignature) -> dict:
    from .email_sending import MAX_ATTACHMENT_BYTES

    signed = json.loads(signature.signed_content)
    copy = signature.copy_document
    return {
        # Seit 1.8.35; None bei einer Unterschrift von vor 1.8.35, bis der erste Versand sie nachholt.
        "copy_document": sent_document_to_dict(copy) if copy else None,
        "copy_check": verify_sent_document(copy) if copy else None,
        "copy_too_large": bool(copy and copy.size_bytes > MAX_ATTACHMENT_BYTES),
        "id": signature.id, "method": signature.method, "method_label": METHODS.get(signature.method, signature.method),
        "version_id": signature.version_id, "version_no": signed["version_no"], "signed_on": signature.signed_on,
        "customer_signer_name": signature.customer_signer_name, "company_signer_name": signature.company_signer_name,
        "checkboxes": signed["checkboxes"], "content_sha256": signature.content_sha256,
        "content_intact": hashlib.sha256(signature.signed_content.encode("utf-8")).hexdigest() == signature.content_sha256,
        "document": sent_document_to_dict(signature.document), "document_check": verify_sent_document(signature.document),
        "recorded_at_local": to_berlin(signature.recorded_at), "recorded_by_name": signature.recorded_by_name,
        "withdrawal": withdrawal_info(signed),
    }
