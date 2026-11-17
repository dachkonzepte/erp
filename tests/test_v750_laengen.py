"""Version 1.9.350 -- jedes Eingabefeld, das in eine Spalte String(n) geht, hat max_length ≤ n (Runde V2a, Punkt 1; Befund SQLite/PostgreSQL, Abschnitt 3 A).

SQLite nimmt einen zu langen Text still an, PostgreSQL lehnt ihn ab -- bis 1.9.349 ergab das live 500 statt 422 (Befund P1–P1d). Zuordnung wie im Befund:
ein Eingabeschema gehört zum Modell, mit dessen Klassennamen sein Name beginnt (CustomerCreate -> Customer, der längste Treffer), ein Feld zur Spalte
gleichen Namens. Zu lang heißt 422 mit Feld (loc) und Grenze (ctx.max_length), nie 500. OFFEN darf nur kürzer werden; seit 1.9.350 leer (89 Spalten in
127 Felddefinitionen nachgezogen)."""

import importlib
import inspect
import json
import pkgutil
import re

import pydantic
import pytest
from sqlalchemy import String

import app
from app.database import Base
from app.routers.customers import router as kunden_router
from app.routers.properties import router as objekte_router
from app.routers.settings import router as einstellungen_router
from app.routers.tasks import router as aufgaben_router
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v314_dashboard_month_berlin import TEMPLATES, _node
from tests.test_v333_auswahl_inaktiv import nur_mit_node

OFFEN: set[str] = set()  # „Schema.feld“; darf nur kürzer werden


def _eingabeschemas():
    for m in pkgutil.walk_packages(app.__path__, "app."):
        if m.name != "app.main":
            importlib.import_module(m.name)
    gesehen = set()
    for name, modul in list(__import__("sys").modules.items()):
        if not name.startswith("app."):
            continue
        for _n, obj in inspect.getmembers(modul, inspect.isclass):
            if issubclass(obj, pydantic.BaseModel) and obj.__module__.startswith("app.") and not obj.__name__.endswith("Out"):
                gesehen.add(obj)
    return sorted(gesehen, key=lambda s: s.__name__)


_KLASSEN = sorted((m.class_ for m in Base.registry.mappers), key=lambda c: -len(c.__name__))


def _modell_zu(name):
    for c in _KLASSEN:
        if name.startswith(c.__name__) and re.match(r"[A-Z]|$", name[len(c.__name__):]):
            return c
    return None


def eingabefelder_mit_laenge():
    """(Schema, Feld, Tabelle.Spalte, n, max_length) je Textfeld eines Eingabeschemas, das in eine Spalte String(n) seines Modells geht."""
    felder = []
    for s in _eingabeschemas():
        cls = _modell_zu(s.__name__)
        if cls is None:
            continue
        for c in cls.__table__.columns:
            if not isinstance(c.type, String) or not getattr(c.type, "length", None) or c.name not in s.model_fields:
                continue
            f = s.model_fields[c.name]
            if "str" not in str(f.annotation):
                continue
            ml = next((x.max_length for x in f.metadata if getattr(x, "max_length", None) is not None), None)
            felder.append((s, c.name, f"{cls.__tablename__}.{c.name}", c.type.length, ml))
    return felder


FELDER = eingabefelder_mit_laenge()


def test_jedes_eingabefeld_hat_eine_grenze_bis_zur_spalte():
    offen = {f"{s.__name__}.{feld}" for s, feld, _spalte, n, ml in FELDER if ml is None or ml > n}
    assert offen <= OFFEN, f"ohne passende max_length (Spalte String(n), Grenze ≤ n): {sorted(offen - OFFEN)}"
    assert not OFFEN - offen, f"erledigt, aus OFFEN nehmen: {sorted(OFFEN - offen)}"
    # die Zuordnung findet die Spalten des Befunds noch: 264 (175 hatten 1.9.349 schon eine passende Grenze, 89 kamen 1.9.350 dazu), in 417 Feldern
    assert len({spalte for _s, _f, spalte, _n, _ml in FELDER}) >= 264


@pytest.mark.parametrize("schema, feld, spalte, n", [(s, f, sp, n) for s, f, sp, n, _ml in FELDER], ids=lambda x: getattr(x, "__name__", str(x)))
def test_ein_zeichen_zu_viel_wird_mit_feld_und_grenze_abgelehnt(schema, feld, spalte, n):
    with pytest.raises(pydantic.ValidationError) as fehler:
        schema.model_validate({feld: "x" * (n + 1)})
    treffer = [e for e in fehler.value.errors() if e["loc"][-1] == feld and e["type"] == "string_too_long"]
    assert treffer and treffer[0]["ctx"]["max_length"] <= n, (spalte, fehler.value.errors())


# Die Proben des Befunds über echte Routen (P1, P1b, P1c, P1d): bis 1.9.349 unter SQLite 200 (live unter PostgreSQL 500), jetzt 422 mit Feld und Grenze.
def _zu_lang(antwort, feld, n):
    assert antwort.status_code == 422, antwort.text
    eintraege = [e for e in antwort.json()["detail"] if e["loc"][-1] == feld]
    assert [(e["type"], e["ctx"]["max_length"]) for e in eintraege] == [("string_too_long", n)], antwort.text


def test_route_kunde_plz(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, kunden_router)
    _zu_lang(client.post("/api/customers", json={"last_name": "Probe", "postal_code": "1" * 21}), "postal_code", 20)


def test_route_einstellungen_plz(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, einstellungen_router)
    _zu_lang(client.put("/api/settings/general", json={"postal_code": "1" * 21}), "postal_code", 20)


def test_route_objekt_strasse(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde, _objekt = make_customer_and_property(db)
    client = router_test_client(db, objekte_router)
    _zu_lang(client.post("/api/properties", json={"customer_id": kunde.id, "name": "Halle", "street": "s" * 256}), "street", 255)


def test_route_aufgabe_prioritaet(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, aufgaben_router)
    _zu_lang(client.post("/api/tasks", json={"title": "Rückruf", "priority": "p" * 31}), "priority", 30)


@nur_mit_node
def test_meldung_nennt_die_grenze():
    """fehlerText() (_fehlertext.html) hängt seit 1.9.350 die Grenze an „ist zu lang“, wenn die Antwort sie nennt."""
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_fehlertext.html").read_text(encoding="utf-8"), re.S))
    faelle = [
        {"detail": [{"type": "string_too_long", "loc": ["body", "postal_code"], "msg": "x", "ctx": {"max_length": 20}}]},
        {"detail": [{"type": "string_too_long", "loc": ["body", "postal_code"], "msg": "x"}]},
    ]
    ergebnis = _node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(b=>fehlerText(b,422,{{postal_code:'PLZ'}}))));",
                     "Europe/Berlin")
    assert ergebnis == ["Bitte die Eingabe prüfen – PLZ ist zu lang (höchstens 20 Zeichen).", "Bitte die Eingabe prüfen – PLZ ist zu lang."]
