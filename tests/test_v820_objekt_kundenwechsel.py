"""Ein Objekt wechselt den Kunden nur geprüft (seit 1.11.30, Nebenbefund N1 aus dem Bauplan P2).

Festlegungen 1.11.30 (Gegenproben in docs/archiv/gegenproben-portal.md, „1.11.30“):
1. Hängt am Objekt ein Vorgang -- Projekt (auch eines anderen Kunden), Anfrage, Wartungsvertrag, Dokument, Checkliste, Abnahme, Mangel --, wechselt es den
   Kunden nicht: 409 mit den Bereichen und ihrer Zahl und dem Rat, beim neuen Kunden ein neues Objekt anzulegen; nichts geändert.
2. Die Hauptadresse eines Kunden wechselt den Kunden nie (409).
3. Sonst nur mit Begründung (fehlt sie oder ist sie leer, 422; höchstens 500 Zeichen); nichts geändert ohne sie.
4. Der Wechsel steht mit alter und neuer Zuordnung und der Begründung in der Änderungshistorie; Dachflächen wechseln mit dem Objekt.
5. Bleibt der Kunde derselbe, braucht das Speichern keine Begründung (das Formular schickt den Kunden immer mit).
6. Jeder Fremdschlüssel auf properties steht in genau einer Liste: sperrt den Wechsel oder wechselt mit.
"""

import pytest
from sqlalchemy import select

from app.models import AuditLog, Customer, DocumentCategory, Inquiry, MaintenanceContract, Project, Property, RoofArea
from app.objekt_kundenwechsel import GRUND_FEHLT, SPERREN, WANDERT_MIT, fremdschluessel_auf_objekte
from app.project_pipeline_columns import default_pipeline_column_id
from app.property_documents import create_property_document
from app.roof_areas import create_roof_area
from app.routers.properties import router as properties_router
from app.berlin_time import berlin_today


@pytest.fixture
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    alt = Customer(name="Alte Kundin", last_name="Alte Kundin")
    neu = Customer(name="Neuer Kunde", last_name="Neuer Kunde")
    dritte = Customer(name="Dritte Firma", last_name="Dritte Firma")
    db.add_all([alt, neu, dritte]); db.flush()
    objekt = Property(customer_id=alt.id, name="Lagerhalle Süd")
    db.add(objekt); db.commit()
    return {"db": db, "alt": alt, "neu": neu, "dritte": dritte, "objekt": objekt, "client": router_test_client(db, properties_router)}


def _wechseln(w, **mehr):
    return w["client"].put(f"/api/properties/{w['objekt'].id}", json={"customer_id": w["neu"].id, **mehr})


def _kunde(w):
    w["db"].expire_all()
    return w["db"].get(Property, w["objekt"].id).customer_id


def _historie(w):
    return w["db"].scalars(select(AuditLog).where(AuditLog.action == "Kunde gewechselt").order_by(AuditLog.id)).all()


def _projekt(w, kunde):
    w["db"].add(Project(project_number=f"P-{kunde.id}", name="Dach", customer_id=kunde.id, property_id=w["objekt"].id, status="anfrage",
                        pipeline_column_id=default_pipeline_column_id(w["db"])))


def _anfrage(w, kunde):
    w["db"].add(Inquiry(inquiry_number="A-0001", customer_id=kunde.id, title="Rinne tropft", property_id=w["objekt"].id))


def _vertrag(w, kunde):
    w["db"].add(MaintenanceContract(customer_id=kunde.id, property_id=w["objekt"].id, title="Jahreswartung", next_due_date=berlin_today()))


def _dokument(w, kunde):
    kategorie = w["db"].scalar(select(DocumentCategory.id).order_by(DocumentCategory.id).limit(1))
    create_property_document(w["db"], w["objekt"].id, category_id=kategorie, file_data=b"%PDF-1.4 Plan", original_filename="plan.pdf")


@pytest.mark.parametrize("anlegen, bereich", [(_projekt, "1 Projekt"), (_anfrage, "1 Anfrage"), (_vertrag, "1 Wartungsvertrag"),
                                              (_dokument, "1 Dokument")])
def test_vorgaenge_sperren_den_wechsel(welt, anlegen, bereich):
    """Festlegung 1: ein Vorgang am Objekt -> 409 mit Bereich und Rat; Kunde und Historie unverändert (auch mit Begründung)."""
    anlegen(welt, welt["alt"])
    welt["db"].commit()
    antwort = _wechseln(welt, kundenwechsel_grund="Verkauft")
    assert antwort.status_code == 409, antwort.text
    text = antwort.json()["detail"]
    assert f"Am Objekt hängt noch {bereich} –" in text and "Lege beim neuen Kunden ein neues Objekt an." in text
    assert _kunde(welt) == welt["alt"].id and _historie(welt) == []


def test_mehrere_bereiche_in_einer_meldung(welt):
    _projekt(welt, welt["alt"])
    _dokument(welt, welt["alt"]); _dokument(welt, welt["alt"])
    welt["db"].commit()
    antwort = _wechseln(welt, kundenwechsel_grund="Verkauft")
    assert antwort.status_code == 409 and "Am Objekt hängen noch 1 Projekt und 2 Dokumente –" in antwort.json()["detail"]


def test_projekt_eines_anderen_kunden_sperrt(welt):
    """Festlegung 1 (U3 aus dem Bauplan): auch ein Projekt eines dritten Kunden auf dem Objekt sperrt."""
    _projekt(welt, welt["dritte"])
    welt["db"].commit()
    assert _wechseln(welt, kundenwechsel_grund="Verkauft").status_code == 409
    assert _kunde(welt) == welt["alt"].id


def test_hauptadresse_wechselt_nicht(welt):
    """Festlegung 2."""
    welt["objekt"].is_primary_address = True
    welt["db"].commit()
    antwort = _wechseln(welt, kundenwechsel_grund="Verkauft")
    assert antwort.status_code == 409 and "Hauptadresse des Kunden" in antwort.json()["detail"]
    assert _kunde(welt) == welt["alt"].id


@pytest.mark.parametrize("grund", [None, "", "   "])
def test_ohne_begruendung_nichts_geaendert(welt, grund):
    """Festlegung 3: ohne Begründung 422, auch die übrigen Felder bleiben."""
    mehr = {} if grund is None else {"kundenwechsel_grund": grund}
    antwort = _wechseln(welt, name="Neuer Name", **mehr)
    assert antwort.status_code == 422 and antwort.json()["detail"] == GRUND_FEHLT
    welt["db"].expire_all()
    objekt = welt["db"].get(Property, welt["objekt"].id)
    assert (objekt.customer_id, objekt.name) == (welt["alt"].id, "Lagerhalle Süd")


def test_begruendung_hoechstens_500_zeichen(welt):
    assert _wechseln(welt, kundenwechsel_grund="x" * 501).status_code == 422
    assert _kunde(welt) == welt["alt"].id


def test_mit_begruendung_wechselt_mit_historie_und_dachflaechen(welt):
    """Festlegung 4: gewechselt, Eintrag mit altem und neuem Kunden und der Begründung; die Dachfläche bleibt am Objekt (wechselt mit)."""
    flaeche = create_roof_area(welt["db"], welt["objekt"].id, "Hauptdach", roof_type="Flachdach")
    antwort = _wechseln(welt, kundenwechsel_grund="  Halle an den neuen Eigentümer verkauft  ")
    assert antwort.status_code == 200, antwort.text
    assert _kunde(welt) == welt["neu"].id
    eintraege = _historie(welt)
    assert [(e.entity_type, e.entity_id, e.field_name, e.old_value, e.new_value) for e in eintraege] == [
        ("Objekt", str(welt["objekt"].id), "kundenwechsel_grund", "Alte Kundin", "Neuer Kunde – Halle an den neuen Eigentümer verkauft")]
    assert welt["db"].get(RoofArea, flaeche["id"]).property_id == welt["objekt"].id


def test_gleicher_kunde_braucht_keine_begruendung(welt):
    """Festlegung 5: das Formular schickt den Kunden immer mit -- derselbe Kunde ist kein Wechsel."""
    _projekt(welt, welt["alt"])
    welt["db"].commit()
    antwort = welt["client"].put(f"/api/properties/{welt['objekt'].id}", json={"customer_id": welt["alt"].id, "name": "Halle Süd"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["name"] == "Halle Süd" and _historie(welt) == []


def test_unbekannter_kunde_weiter_404(welt):
    antwort = welt["client"].put(f"/api/properties/{welt['objekt'].id}", json={"customer_id": 999999, "kundenwechsel_grund": "x"})
    assert antwort.status_code == 404


def test_jeder_fremdschluessel_auf_objekte_eingeordnet():
    """Festlegung 6: jede Spalte mit Fremdschlüssel auf properties in genau einer Liste -- eine neue Tabelle mit Objekt kommt hier hinein."""
    sperren, mit = set(SPERREN), set(WANDERT_MIT)
    assert not sperren & mit
    assert sorted(sperren | mit) == fremdschluessel_auf_objekte()
