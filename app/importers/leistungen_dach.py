from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET


class LeistungenDachImportError(ValueError):
    pass


def parse_decimal(value: str | None, *, field_name: str) -> Decimal:
    if value is None or not value.strip():
        return Decimal("0")
    normalized = value.strip().replace(".", "").replace(",", ".") if "," in value else value.strip()
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise LeistungenDachImportError(f"Ungültiger Zahlenwert in {field_name}: {value!r}") from exc


@dataclass(slots=True)
class ParsedMaterial:
    name: str
    article_number: str | None
    quantity: Decimal
    unit: str
    waste_raw: Decimal
    purchase_price: Decimal
    price_basis: Decimal


@dataclass(slots=True)
class ParsedService:
    external_id: str
    title_name: str | None
    short_text: str
    long_text: str
    rtf_text: str | None
    image_reference: str | None
    quantity: Decimal
    unit: str
    site_time_raw: Decimal
    workshop_time_raw: Decimal
    sale_price: Decimal
    activity_code: str | None
    materials: list[ParsedMaterial] = field(default_factory=list)


@dataclass(slots=True)
class ParsedProject:
    source_name: str
    source_version: str | None
    title_count: int
    services: list[ParsedService]

    @property
    def material_item_count(self) -> int:
        return sum(len(service.materials) for service in self.services)


def _child_text(parent: ET.Element, tag: str) -> str:
    child = parent.find(tag)
    return "" if child is None or child.text is None else child.text.strip()


def _long_text(position: ET.Element) -> str:
    langtext = position.find("Langtext")
    if langtext is None:
        return ""
    lines = []
    for child in langtext:
        if child.text:
            lines.append(child.text.strip())
    return "\n".join(lines)


def parse_leistungen_dach_xml(xml_bytes: bytes) -> ParsedProject:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise LeistungenDachImportError(f"XML ist syntaktisch ungültig: {exc}") from exc

    if root.tag != "Projekt":
        raise LeistungenDachImportError(f"Unerwartetes Wurzelelement: {root.tag!r}; erwartet 'Projekt'.")

    source_name = root.attrib.get("Name", "Leistungen Dach")
    source_version = root.attrib.get("Version")
    titles = root.findall("./LVDaten/Titel")
    if not titles:
        raise LeistungenDachImportError("Keine Titel unter Projekt/LVDaten gefunden.")

    services: list[ParsedService] = []

    for title in titles:
        title_name = title.attrib.get("Name")
        for position in title.findall("Position"):
            external_id = _child_text(position, "LeistungenDachArtikel")
            if not external_id:
                raise LeistungenDachImportError("Position ohne LeistungenDachArtikel gefunden.")

            short_text = position.attrib.get("Name", "").replace("\r\n", "\n").strip()
            service = ParsedService(
                external_id=external_id,
                title_name=title_name,
                short_text=short_text,
                long_text=_long_text(position),
                rtf_text=_child_text(position, "LeistungenDachRTF") or None,
                image_reference=_child_text(position, "LeistungenDachBild") or None,
                quantity=parse_decimal(_child_text(position, "Menge"), field_name="Menge"),
                unit=_child_text(position, "Mengeneinheit"),
                site_time_raw=parse_decimal(_child_text(position, "Baustellenzeit"), field_name="Baustellenzeit"),
                workshop_time_raw=parse_decimal(_child_text(position, "Werkstattzeit"), field_name="Werkstattzeit"),
                sale_price=parse_decimal(_child_text(position, "VKPreis"), field_name="VKPreis"),
                activity_code=_child_text(position, "Taetigkeit") or None,
            )

            item_list = position.find("Stueckliste")
            if item_list is not None:
                for item in item_list.findall("Item"):
                    service.materials.append(
                        ParsedMaterial(
                            name=item.attrib.get("Name", "").replace("\r\n", "\n").strip(),
                            article_number=_child_text(item, "Artikelnummer") or None,
                            quantity=parse_decimal(_child_text(item, "Menge"), field_name="Stueckliste/Menge"),
                            unit=_child_text(item, "Mengeneinheit"),
                            waste_raw=parse_decimal(_child_text(item, "Verschnit"), field_name="Verschnit"),
                            purchase_price=parse_decimal(_child_text(item, "Preis"), field_name="Preis"),
                            price_basis=parse_decimal(_child_text(item, "Preisbasis"), field_name="Preisbasis"),
                        )
                    )

            services.append(service)

    return ParsedProject(
        source_name=source_name,
        source_version=source_version,
        title_count=len(titles),
        services=services,
    )
