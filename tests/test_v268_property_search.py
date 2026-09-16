"""Version "Dateiablage je Objekt", Schritt 3 (nach 1.3.63) -- geteilte Suche als Einstieg in
die mobile Objektansicht. Siehe CLAUDE.md "Suche als Einstieg" bzw. app/search.py für die
Kernfunktion. Deckt beide Schichten ab (search_properties() als rollenlose Kernfunktion,
search_properties_for_field() als die einzige für Monteure zulässige Reduktion) sowie den
tatsächlichen Router-Endpunkt GET /api/field-view/properties/search -- und den vom Nutzer
verlangten Angriffstest: findet ein Monteur über die Suche etwas anderes als Objekte, liefert die
Vorschlagsantwort ein gesperrtes Feld mit, kommt ein Monteur mit manipulierten Parametern an mehr
als Objekte."""

import pytest

from app.models import Customer, Property
from app.search import MIN_QUERY_LENGTH, SEARCH_RESULT_LIMIT, search_properties, search_properties_for_field
from tests.test_v153_mahnwesen import db_session  # noqa: F401 -- re-exportiert db_session als Fixture


def _customer(db, name, last_name=None):
    c = Customer(name=name, last_name=last_name or name)
    db.add(c); db.commit()
    return c


def _property(db, customer, name, street=None, postal_code=None, city=None):
    p = Property(customer_id=customer.id, name=name, street=street, postal_code=postal_code, city=city)
    db.add(p); db.commit()
    return p


_FORBIDDEN_SUBSTRINGS = (
    "price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten",
    "betrag", "amount", "vergüt", "customer_note", "property_note", "notiz", "kunden_nr",
    "customer_number", "legacy_address_number", "street", "strasse", "postal", "plz",
    "customer_id", "customer_name",
)


def _offending_keys(payload):
    keys = set()
    for row in payload:
        keys |= set(row.keys())
    return sorted({k for k in keys if any(f in k.lower() for f in _FORBIDDEN_SUBSTRINGS)})


# --- Schicht 1: search_properties() ist die rollenlose Kernfunktion, keine Reduktion ---

def test_search_properties_finds_by_name_street_city_and_customer_name(db_session):
    db = db_session
    kunde = _customer(db, "Erika Schmidt")
    treffer_name = _property(db, kunde, "Bürogebäude Musterstraße", street="Musterstraße 5", city="Kölle")
    treffer_kunde = _property(db, kunde, "Zweitobjekt", street="Nebenweg 2", city="Aachen")
    _property(db, _customer(db, "Peter Müller"), "Ganz anderes Objekt", street="Fernstraße 9", city="Berlin")

    by_name = search_properties(db, "Musterstraße")
    assert [p.id for p in by_name] == [treffer_name.id]

    by_customer = search_properties(db, "Schmidt")
    assert {p.id for p in by_customer} == {treffer_name.id, treffer_kunde.id}


def test_search_properties_returns_full_orm_objects_no_role_reduction(db_session):
    """Schicht 1 ist bewusst rollenlos -- eine künftige, reichhaltigere Büro-Suche liest hieraus
    volle Felder (street/postal_code/customer), ohne diese Funktion anzufassen. Die Reduktion
    passiert ausschließlich in Schicht 2 (field_safe_property_search_results())."""
    db = db_session
    kunde = _customer(db, "Vertraulich GmbH")
    _property(db, kunde, "Geheimobjekt", street="Verschwiegen 1", postal_code="99999", city="Nirgends")
    rows = search_properties(db, "Geheimobjekt")
    assert len(rows) == 1
    assert rows[0].street == "Verschwiegen 1"
    assert rows[0].customer_id == kunde.id


def test_search_properties_below_min_length_returns_nothing(db_session):
    db = db_session
    kunde = _customer(db, "Test Kunde")
    _property(db, kunde, "e")  # ein einzelnes Zeichen wuerde sonst fast jede Zeile treffen
    assert MIN_QUERY_LENGTH >= 2
    assert search_properties(db, "e") == []
    assert search_properties(db, "") == []
    assert search_properties(db, "   ") == []


def test_search_properties_caps_at_limit(db_session):
    db = db_session
    kunde = _customer(db, "Vielobjekt GmbH")
    for i in range(15):
        _property(db, kunde, f"Sammelobjekt {i:02d}", city="Vielstadt")
    rows = search_properties(db, "Sammelobjekt")
    assert len(rows) == SEARCH_RESULT_LIMIT == 10


# --- Schicht 2: field_safe_property_search_results()/search_properties_for_field() ---

def test_search_properties_for_field_reduces_to_id_name_city_only(db_session):
    db = db_session
    kunde = _customer(db, "Firma mit Kundennummer")
    kunde.legacy_address_number = "K-99887"
    db.commit()
    prop = _property(db, kunde, "Objekt mit Geheimnissen", street="Geheimstraße 1", postal_code="12345", city="Verrat")
    prop.notes = "Interne Bemerkung, niemals für Monteure"
    prop.access_notes = "Schluessel beim Nachbarn"
    db.commit()

    hits = search_properties_for_field(db, "Geheimnissen")
    assert len(hits) == 1
    hit = hits[0]
    assert set(hit.keys()) == {"id", "name", "city"}
    assert hit["id"] == prop.id
    assert hit["name"] == "Objekt mit Geheimnissen"
    assert hit["city"] == "Verrat"
    assert not _offending_keys(hits)


def test_search_properties_for_field_matched_via_customer_leaks_nothing_about_customer(db_session):
    """Ein Treffer über den Kundennamen darf trotzdem nur die Objektfelder zeigen -- der Kunde
    selbst (Name, Kundennummer, Adresse) darf nicht in der Antwort auftauchen."""
    db = db_session
    kunde = _customer(db, "Sehr Geheime Schmidt AG")
    prop = _property(db, kunde, "Baustelle Nord", city="Nordstadt")
    hits = search_properties_for_field(db, "Sehr Geheime Schmidt")
    assert len(hits) == 1
    assert set(hits[0].keys()) == {"id", "name", "city"}
    for value in hits[0].values():
        assert "Schmidt" not in str(value)


# --- Router: GET /api/field-view/properties/search ---

def test_field_view_search_endpoint_finds_property_and_returns_only_harmless_fields(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    kunde = _customer(db, "Musterfirma Schmidt")
    prop = _property(db, kunde, "Bürogebäude", street="Musterstraße 5", postal_code="12345", city="Musterstadt")

    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get("/api/field-view/properties/search", params={"q": "Musterstraße"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"id", "name", "city"}
    assert body[0]["id"] == prop.id

    resp2 = field.get("/api/field-view/properties/search", params={"q": "Schmidt"})
    assert resp2.status_code == 200
    assert [row["id"] for row in resp2.json()] == [prop.id]


def test_field_view_search_endpoint_never_returns_more_than_objects(router_test_client, threaded_db_session):
    """Angriffstest: findet ein Monteur über die Suche etwas anderes als Objekte? Über den
    einzigen tatsächlichen Router-Weg geprüft, nicht nur die Kernfunktion direkt."""
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    kunde = _customer(db, "Angreifer Suchziel GmbH")
    _property(db, kunde, "Angreifer Objekt", city="Angriffstadt")

    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get("/api/field-view/properties/search", params={"q": "Angreifer"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert set(body[0].keys()) == {"id", "name", "city"}
    assert not _offending_keys(body)


def test_field_view_search_endpoint_manipulated_parameters_still_only_objects(router_test_client, threaded_db_session):
    """Angriffstest: kommt ein Monteur, der den Such-Endpunkt mit anderen Parametern aufruft, an
    mehr als Objekte? FastAPI ignoriert unbekannte Query-Parameter -- limit bleibt serverseitig
    fest auf SEARCH_RESULT_LIMIT, unabhaengig von einem client-seitig gesetzten Wert."""
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    kunde = _customer(db, "Parametertest GmbH")
    for i in range(12):
        _property(db, kunde, f"Parameterobjekt {i:02d}", city="Parameterstadt")

    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get(
        "/api/field-view/properties/search",
        params={"q": "Parameterobjekt", "type": "customer", "full": "true", "fields": "all", "limit": "99999"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) <= SEARCH_RESULT_LIMIT
    for row in body:
        assert set(row.keys()) == {"id", "name", "city"}
    assert not _offending_keys(body)


def test_field_view_search_endpoint_short_query_returns_empty(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    kunde = _customer(db, "Kurz GmbH")
    _property(db, kunde, "e-Objekt", city="e-Stadt")

    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get("/api/field-view/properties/search", params={"q": "e"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp2 = field.get("/api/field-view/properties/search")
    assert resp2.status_code == 200
    assert resp2.json() == []


def test_field_view_search_endpoint_registered_before_property_id_route(router_test_client, threaded_db_session):
    """Literal-vs-Platzhalter-Kollisionscheck (Muster wie in test_v167_pagination.py, siehe
    CLAUDE.md): /properties/search darf nicht am {property_id}:int-Platzhalter scheitern."""
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get("/api/field-view/properties/search", params={"q": "irrelevant"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_field_view_search_endpoint_unreachable_without_login(router_test_client, threaded_db_session):
    """Standardverweigerung (Regel 11): der Endpunkt braucht eine Rollenpruefung, ist ueber
    require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD) markiert -- der Audit-Test
    (test_v260_role_audit.py) deckt das bereits ab; hier nur die positive Bestätigung, dass field
    tatsächlich durchkommt (kein 403)."""
    from app.routers.field_view import router as field_router
    db = threaded_db_session
    field = router_test_client(db, field_router, role="field", employee_id=None)
    resp = field.get("/api/field-view/properties/search", params={"q": "xy"})
    assert resp.status_code == 200
