"""Version 1.9.356 -- Antworten ohne Prüfung, Pflicht-Textfelder ohne Leerzeichen am Rand (Runde V2c, Punkt 1; B1 und B2 aus dem Bericht V2b).

    B1           ein gespeicherter Wert, den das Formular ablehnt, bringt keine Liste mehr auf 500: die Kundenliste mit einem Nachnamen "" (bis 1.9.355 500,
                 CustomerOut erbte min_length=1) -- dazu die übrigen sieben Antwortschemas, die Grenzen erbten (tests/test_v673_antworten_ohne_pruefung.py)
    B2           jedes Textfeld eines Eingabeschemas mit min_length >= 1 ist ein Pflichttext: Leerzeichen am Rand fallen vor der Prüfung weg, nur
                 Leerzeichen heißt 422 („fehlt“), gespeichert wird der Text ohne Rand -- Passwörter ausgenommen (jedes Zeichen zählt)
    Wächter      kein Textfeld mit min_length >= 1 ohne Pflichttext außer AUSNAHMEN (genau)
"""

import importlib
import inspect
import json
import pkgutil
import re
import sys
from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import pydantic
import pytest
from pydantic import BeforeValidator

import app
import app.schemas as schemas
from app.routers.customers import router as kunden_router
from tests.test_v314_dashboard_month_berlin import TEMPLATES, _node
from tests.test_v333_auswahl_inaktiv import nur_mit_node

AUSNAHMEN = {  # „Schema.feld“ -> Grund
    "AppUserCreate.password": "Passwort: jedes Zeichen zählt, auch ein Leerzeichen am Rand",
    "AppUserUpdate.new_password": "Passwort: jedes Zeichen zählt, auch ein Leerzeichen am Rand",
    "ChangePasswordRequest.new_password": "Passwort: jedes Zeichen zählt, auch ein Leerzeichen am Rand",
}


def _eingabeschemas():
    for m in pkgutil.walk_packages(app.__path__, "app."):
        if m.name != "app.main":
            importlib.import_module(m.name)
    gesehen = set()
    for name, modul in list(sys.modules.items()):
        if not name.startswith("app."):
            continue
        for _n, obj in inspect.getmembers(modul, inspect.isclass):
            if issubclass(obj, pydantic.BaseModel) and obj.__module__.startswith("app.") and not obj.__name__.endswith("Out"):
                gesehen.add(obj)
    return sorted(gesehen, key=lambda s: s.__name__)


def _teile(annotation):
    """Die Typen eines Felds: str, Annotated[str, …], und die Glieder einer Union (`Pflichttext | None` trägt seine Prüfung im Typ)."""
    if get_origin(annotation) in (Union, UnionType):
        return [t for a in get_args(annotation) for t in _teile(a)]
    return [annotation]


def _ist_text(annotation) -> bool:
    return any(t is str or (get_origin(t) is Annotated and get_args(t)[0] is str) for t in _teile(annotation))


def _schneidet(f) -> bool:
    validatoren = list(f.metadata) + [m for t in _teile(f.annotation) if get_origin(t) is Annotated for m in get_args(t)[1:]]
    return any(isinstance(x, BeforeValidator) and x.func is schemas._ohne_rand for x in validatoren)


def pflichtfelder():
    """(Schema, Feld, schneidet ab) je Textfeld eines Eingabeschemas mit min_length >= 1."""
    out = []
    for s in _eingabeschemas():
        for n, f in s.model_fields.items():
            if not _ist_text(f.annotation):
                continue
            ml = next((x.min_length for x in f.metadata if getattr(x, "min_length", None) is not None), None)
            if ml is None or ml < 1:
                continue
            out.append((s, n, _schneidet(f)))
    return out


FELDER = pflichtfelder()


def test_jedes_pflicht_textfeld_ohne_rand():
    ohne = {f"{s.__name__}.{n}" for s, n, schneidet in FELDER if not schneidet}
    assert ohne - set(AUSNAHMEN) == set(), "Pflicht-Textfeld ohne Pflichttext (app/schemas.py): Typ Pflichttext statt str"
    assert set(AUSNAHMEN) <= ohne, f"AUSNAHMEN an den Bestand anpassen: {sorted(set(AUSNAHMEN) - ohne)}"
    assert len(FELDER) >= 159  # die Zuordnung findet die Felder noch (1.9.356: 159 -- 156 Pflichttexte, 3 Passwörter)


@pytest.mark.parametrize("schema, feld", [(s, n) for s, n, schneidet in FELDER if schneidet], ids=lambda x: getattr(x, "__name__", str(x)))
def test_nur_leerzeichen_heisst_fehlt(schema, feld):
    for wert in (" ", "   ", "\t \n"):
        with pytest.raises(pydantic.ValidationError) as fehler:
            schema.model_validate({feld: wert})
        treffer = [e for e in fehler.value.errors() if e["loc"] and e["loc"][-1] == feld]
        assert [e["type"] for e in treffer] == ["string_too_short"], (wert, fehler.value.errors())


@pytest.mark.parametrize("schema, feld", [(s, n) for s, n, schneidet in FELDER if schneidet], ids=lambda x: getattr(x, "__name__", str(x)))
def test_rand_faellt_weg(schema, feld):
    """„  x  “ verhält sich wie „x“: dieselben Fehler am Feld (ein eigenes Muster -- E-Mail, Schlüssel, Rolle -- lehnt beide gleich ab), und wo das
    Schema sonst passt, kommt „x“ an."""
    def lauf(wert):
        try:
            return getattr(schema.model_validate({feld: wert}), feld), []
        except pydantic.ValidationError as fehler:
            return None, [(e["type"], e.get("ctx")) for e in fehler.errors() if e["loc"] and e["loc"][-1] == feld]
    mit_rand, ohne_rand = lauf("  x  "), lauf("x")
    assert mit_rand == ohne_rand, (mit_rand, ohne_rand)


def test_passwort_behaelt_seine_leerzeichen():
    assert schemas.ChangePasswordRequest.model_validate({"current_password": "alt", "new_password": "  geheim 1234  "}).new_password == "  geheim 1234  "


# --- über echte Routen: B2 (Nachname aus Leerzeichen) und B1 (gespeicherter leerer Nachname) ---------------------------------------------------

def test_kunde_mit_nachnamen_aus_leerzeichen_wird_abgelehnt(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, kunden_router)
    r = client.post("/api/customers", json={"last_name": "   "})
    assert r.status_code == 422, r.text
    assert [(e["loc"][-1], e["type"], e["ctx"]["min_length"]) for e in r.json()["detail"]] == [("last_name", "string_too_short", 1)]
    ok = client.post("/api/customers", json={"salutation": "Frau", "first_name": "Erika", "last_name": "  Probe  "})
    assert ok.status_code == 200, ok.text
    assert (ok.json()["last_name"], ok.json()["name"]) == ("Probe", "Frau Erika Probe")
    kunde_id = ok.json()["id"]
    leer = client.put(f"/api/customers/{kunde_id}", json={"last_name": " "})
    assert leer.status_code == 422 and leer.json()["detail"][0]["loc"][-1] == "last_name", leer.text


@pytest.mark.parametrize("nachname", ["", " "])
def test_kundenliste_mit_gespeichertem_leeren_nachnamen(threaded_db_session, router_test_client, nachname):
    """B1: bis 1.9.355 prüfte CustomerOut wie das Formular (min_length=1) -- ein gespeicherter Nachname "" brachte die ganze Kundenliste auf 500."""
    from app.models import Customer
    db = threaded_db_session
    db.add_all([Customer(name="Probe", last_name="Probe"), Customer(name=nachname.strip(), last_name=nachname)])
    db.commit()
    client = router_test_client(db, kunden_router)
    r = client.get("/api/customers")
    assert r.status_code == 200, r.text
    assert [k["last_name"] for k in r.json()] == ["Probe", nachname]  # der gespeicherte Wert, wie er ist -- nichts abgeschnitten


@nur_mit_node
def test_meldung_fehlt_statt_zu_kurz():
    """fehlerText() (_fehlertext.html) sagt seit 1.9.356 „fehlt“, wenn ein Pflichtfeld nach dem Abschneiden leer ist (min_length 1)."""
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_fehlertext.html").read_text(encoding="utf-8"), re.S))
    faelle = [
        {"detail": [{"type": "string_too_short", "loc": ["body", "last_name"], "msg": "x", "ctx": {"min_length": 1}}]},
        {"detail": [{"type": "string_too_short", "loc": ["body", "last_name"], "msg": "x", "ctx": {"min_length": 8}}]},
    ]
    ergebnis = _node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(b=>fehlerText(b,422,{{last_name:'Nachname'}}))));",
                     "Europe/Berlin")
    assert ergebnis == ["Bitte die Eingabe prüfen – Nachname fehlt.", "Bitte die Eingabe prüfen – Nachname ist zu kurz (mindestens 8 Zeichen)."]
