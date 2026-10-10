"""Zugehörigkeit von IDs aus der Anfrage (seit 1.8.70, Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ Punkt 2,
docs/archiv/befund-vor-echtbetrieb.md).

Eine ID aus der Anfrage, die gespeichert wird, muss zum selben Objekt, Auftrag oder Kunden gehören wie der Datensatz, an den
sie kommt -- sonst nimmt der Server z. B. die Dachfläche eines fremden Objekts in einen Einsatzbericht auf (2a–2e), und der
Monteur sieht danach deren Namen. tests/test_v373_zugehoerigkeit_struktur.py findet jede solche Eingabe an jeder schreibenden
Route und verlangt, dass sie über eine Prüfung läuft (die Prüfungen dieser Datei oder eine benannte andere).

- require_in_order_property(): Dachflächen und Bauteile nur aus dem Objekt des Auftrags (Einsatzbericht, Prüfpunkt, Mangel,
  Material). Unbekannt und fremd antworten gleich (NotInOrderProperty, Router: 404 "… nicht gefunden.") -- die Antwort verrät
  nicht, ob es die ID gibt.
- property_customer_mismatch() / require_confirmed_property(): Objekt eines anderen Kunden (Generalunternehmer,
  Hausverwaltung) nur mit bewusster Bestätigung (Schnellauftrag, Wartungsvertrag) -- dasselbe Muster wie der abweichende
  Kunde der Anzeigen (app/notice_letters.py::customer_mismatch()): Hinweistext, Häkchen, ohne Bestätigung 409.
- IdNichtGefunden / require_customer() (seit 1.8.71): eine unbekannte ID antwortet 404 mit Text, nicht 500 am Fremdschlüssel
  (PostgreSQL) bzw. still gespeichert (SQLite) -- Kunde beim Schnellauftrag und Wartungsvertrag, auch ohne Objekt."""

from collections.abc import Iterable

from sqlalchemy.orm import Session

from .models import Customer, Order, Project, Property, RoofArea, RoofComponent


class IdNichtGefunden(ValueError):
    """Eine ID aus der Anfrage gibt es nicht (seit 1.8.71) -- Router: 404 mit dem Text. Ein ValueError, damit Aufrufer, die
    ValueError fangen, unverändert bleiben."""


def require_customer(db: Session, customer_id: int) -> Customer:
    """Der Kunde aus der Anfrage -- IdNichtGefunden, wenn es ihn nicht gibt."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise IdNichtGefunden("Kunde nicht gefunden.")
    return customer


def require_project(db: Session, project_id: int) -> Project:
    """Das Projekt aus der Anfrage -- IdNichtGefunden, wenn es es nicht gibt (Aufgabe: frei an jedes Projekt, aber an ein
    vorhandenes)."""
    project = db.get(Project, project_id)
    if project is None:
        raise IdNichtGefunden("Projekt nicht gefunden.")
    return project


class NotInOrderProperty(ValueError):
    """Dachfläche oder Bauteil gehört nicht zum Objekt des Auftrags (oder existiert nicht) -- bewusst ohne Grund im Text."""


ROOF_AREA_NOT_FOUND = "Dachfläche nicht gefunden."
ROOF_COMPONENT_NOT_FOUND = "Bauteil nicht gefunden."


def order_property_id(order: Order | None) -> int | None:
    """Das Objekt des Auftrags -- über das Projekt (Order trägt nur einen Text-Schnappschuss). None: kein Objekt verknüpft
    (Hauptadresse), dann gibt es auch keine Dachflächen (list_roof_areas_for_order() liefert dort ebenfalls nichts)."""
    if order is None or order.project is None:
        return None
    return order.project.property_id


def require_in_order_property(db: Session, order: Order | None, *, roof_area_ids: Iterable[int] = (),
                              roof_component_id: int | None = None, roof_area_id: int | None = None) -> None:
    """Die eine Prüfung für die Monteur-Wege am Einsatzbericht: jede Dachfläche (roof_area_ids, roof_area_id) und das
    Bauteil (roof_component_id) gehören zum Objekt des Auftrags; sind Bauteil und Dachfläche beide angegeben, sitzt das
    Bauteil auf genau dieser Fläche. Sonst NotInOrderProperty -- für eine fremde wie für eine nicht vorhandene ID derselbe
    Text. Archivierte Flächen und Bauteile des eigenen Objekts bleiben erlaubt (gehören dazu)."""
    property_id = order_property_id(order)
    areas = list(roof_area_ids) + ([roof_area_id] if roof_area_id is not None else [])
    for area_id in areas:
        area = db.get(RoofArea, area_id) if property_id is not None else None
        if area is None or area.property_id != property_id:
            raise NotInOrderProperty(ROOF_AREA_NOT_FOUND)
    if roof_component_id is not None:
        component = db.get(RoofComponent, roof_component_id) if property_id is not None else None
        area = db.get(RoofArea, component.roof_area_id) if component is not None else None
        if area is None or area.property_id != property_id or (roof_area_id is not None and component.roof_area_id != roof_area_id):
            raise NotInOrderProperty(ROOF_COMPONENT_NOT_FOUND)


def roof_area_in_order_property(db: Session, order: Order | None, roof_area_id: int) -> bool:
    """Für den Rückfall ohne ausdrückliche Auswahl (Fläche aus der Vertragsposition): gehört sie zum Objekt des Auftrags?"""
    try:
        require_in_order_property(db, order, roof_area_ids=[roof_area_id])
    except NotInOrderProperty:
        return False
    return True


class PropertyCustomerMismatch(ValueError):
    """Objekt eines anderen Kunden ohne Bestätigung -- Router: 409 mit dem Hinweistext."""


def property_customer_mismatch(db: Session, customer_id: int, property_id: int | None) -> dict | None:
    """Gehört das Objekt einem anderen Kunden? None = kein Objekt oder dasselbe. IdNichtGefunden (seit 1.8.71, vorher
    ValueError -> 400), wenn es Objekt oder Kunden nicht gibt (dann gibt es auch nichts zu bestätigen)."""
    if property_id is None:
        return None
    prop = db.get(Property, property_id)
    if prop is None:
        raise IdNichtGefunden("Objekt nicht gefunden.")
    if prop.customer_id == customer_id:
        return None
    customer = require_customer(db, customer_id)
    owner = db.get(Customer, prop.customer_id)
    owner_name = owner.name if owner is not None else "einem anderen Kunden"
    return {
        "customer": customer.name, "property_customer": owner_name, "property": prop.name,
        "text": (f"Das Objekt „{prop.name}“ gehört zu {owner_name}, nicht zu {customer.name}. Auftrag bzw. Vertrag laufen "
                 f"dann auf {customer.name} am Objekt von {owner_name} (z. B. Generalunternehmer oder Hausverwaltung). "
                 f"Bitte prüfen und die Abweichung ausdrücklich bestätigen."),
    }


def require_confirmed_property(db: Session, customer_id: int, property_id: int | None, confirmed: bool) -> dict | None:
    """PropertyCustomerMismatch, solange ein Objekt eines anderen Kunden nicht bestätigt ist; sonst die (bestätigte)
    Abweichung oder None. Seit 1.8.71 zuerst der Kunde selbst (IdNichtGefunden) -- auch ohne Objekt: vorher prüfte ihn beim
    Schnellauftrag und Wartungsvertrag ohne Objekt nur der Fremdschlüssel (PostgreSQL 500)."""
    require_customer(db, customer_id)
    mismatch = property_customer_mismatch(db, customer_id, property_id)
    if mismatch is not None and not confirmed:
        raise PropertyCustomerMismatch(mismatch["text"])
    return mismatch
