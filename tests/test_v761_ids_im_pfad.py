"""Version 1.9.361 -- IDs in Pfad, Abfrage und Formular mit den Grenzen von int4: darüber 404, nie 500 (Runde V3, Punkt 1; F1 aus dem Bericht V2c).

Bis 1.9.360 kam eine ID über int4 (`/api/customers/3000000000`) als Python-Zahl bis zur Datenbank: SQLite fand nichts (404), PostgreSQL brach mit
NumericValueOutOfRange ab (500). Jetzt prüft der Typ app/ids.py::Id die Grenzen von int4, bevor der Endpunkt läuft: außerhalb 404 „Nicht gefunden.“,
ohne Anfrage an die Datenbank. Jede andere ganze Zahl in Pfad, Abfrage oder Formular (Jahr, Monat, Grenze einer Liste …) hat Grenzen (422) oder eine
Prüfung der Geschäftslogik, die jeden Wert ohne 500 beantwortet (Bestand).

    Wächter    jeder Parameter einer Route, der eine ganze Zahl nimmt (auch in Abhängigkeiten, auch int | None und list[int]): eine ID (Name auf _id,
               _ids oder ID_NAMEN) über Id, jede andere in KEINE_ID je Route (die Liste stimmt genau) -- mit Grenzen oder geprüft
    Verhalten  jede Route mit einer ID: 2 147 483 648 und -2 147 483 649 -> 404 „Nicht gefunden.“ (jede Schreibweise: Pfad, Abfrage, Formular,
               Liste, mit Query()/Path()/Form() als Vorgabe), jede ID einzeln; jede andere ganze Zahl über ihrer Grenze -> 422, geprüfte
               mit Werten über int4 und über 64 Bit -> nie 500
    PostgreSQL 2 147 483 647 (die größte ID) -> 404 der Route, 2 147 483 648 -> 404 vor der Datenbank
"""

import re
import typing
from types import UnionType

import pytest
from annotated_types import Ge, Gt, Le, Lt
from fastapi import FastAPI, Form, Path, Query
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.ids import NICHT_GEFUNDEN, Id
from app.schemas import INT4_MAX, INT4_MIN

ID_NAMEN = {"auftrag": "Auftrag (Akte, Verlauf, Zeiten)", "mitarbeiter": "Mitarbeiter (Zeiten)", "vorwahl": "Auftrag der Vorwahl („Meine Zeiten“)"}

# Jede andere ganze Zahl: (Pfad, Ort, Name) -> (Art, Grenzen, Grund). Art „grenzen“: ge und le (so festgelegt, innerhalb von int4), darüber 422 am
# Feld. Art „geprueft“: die Geschäftslogik klammert oder prüft jeden Wert (Bestand, z. B. die Änderungshistorie seit 1.8.150) -- der Rundgang schickt
# Werte über int4 und über 64 Bit, nie 500. Neue Grenzen in 1.9.361 nur, wo ein Wert sonst 500 ergab.
G, P = "grenzen", "geprueft"
KEINE_ID = {
    ("/api/time-backoffice/konten/{employee_id}/anspruch/{jahr}", "path", "jahr"): (P, None, "Jahr des Urlaubsanspruchs, 2026–2100 (anspruch_setzen())"),
    ("/api/time-backoffice/konten/{employee_id}/anspruch/{jahr}/anteilig", "path", "jahr"): (G, (2027, 2100), "Jahr des Urlaubskontos (seit 1.9.365)"),
    ("/api/mobile-icon/{size}.png", "path", "size"): (P, None, "Größe des App-Symbols, 16–1024, sonst 404"),
    ("/api/time-entries/dauer-vorschau", "query", "break_minutes"): (G, (0, 720), "Pause in Minuten"),
    ("/api/time-entry-groups/dauer-vorschau", "query", "break_minutes"): (G, (0, 720), "Pause in Minuten"),
    ("/api/time-entries/nachtrag-vorschau", "query", "pause_minuten"): (G, (0, 720), "Pause in Minuten"),
    ("/api/time-entries/{entry_id}/ende-vorschau", "query", "pause_minuten"): (G, (0, 720), "Pause in Minuten"),
    ("/api/time-entry-groups/nachtrag-vorschau", "query", "pause_minuten"): (G, (0, 720), "Pause in Minuten"),
    ("/api/time-entry-groups/mine", "query", "days"): (P, None, "Tage zurück, geklammert auf 1–62"),
    ("/api/zeiten/urlaubskonto", "query", "jahr"): (G, (2000, 2100), "Jahr des Urlaubskontos"),
    ("/api/audit-logs", "query", "limit"): (P, None, "Größe einer Seite, geklammert auf 1–1000 (1.8.150)"),
    ("/api/audit-logs", "query", "offset"): (P, None, "Versatz ab 0 (ge=0), über 2^62 eine leere Seite (1.8.150)"),
    ("/api/search", "query", "limit"): (P, None, "Treffer je Quelle, geklammert auf 1–100"),
    ("/api/contacts", "query", "limit"): (G, (1, 500), "Größe einer Seite"),
    ("/api/email-dispatches", "query", "limit"): (G, (1, 1000), "Größe einer Seite"),
    ("/api/time-entries", "query", "limit"): (G, (1, 2000), "Größe einer Seite"),
    ("/api/field-view/timesheet.pdf", "query", "month"): (P, None, "Monat, 1–12, sonst 422"),
    ("/api/field-view/timesheet.pdf", "query", "year"): (G, (2000, 2100), "Jahr des Stundenzettels -- seit 1.9.361, darüber bis dahin 500 (date())"),
    ("/api/planning/school-holidays/sync", "query", "start_year"): (G, (2000, 2100), "erstes Jahr der Schulferien -- seit 1.9.361, darüber bis dahin "
                                                                                      "500 unter PostgreSQL (Vergleich mit einer Spalte int4)"),
    ("/api/planning/school-holidays/sync", "query", "years"): (P, None, "Zahl der Jahre, geklammert auf 1–6"),
    ("/api/orders/{order_id}/warranty-preview", "query", "warranty_months"): (P, None, "0–360, sonst 422 (app/warranty.py)"),
    ("/api/orders/{order_id}/warranty-preview", "query", "warranty_days"): (P, None, "0–366, sonst 422 (app/warranty.py)"),
}


def ist_id(name: str) -> bool:
    return name.endswith("_id") or name.endswith("_ids") or name in ID_NAMEN


def _art(t):
    """'id' | 'int' | None -- auch durch Optional, list und Annotated hindurch."""
    if t is Id:
        return "id"
    if t is int:
        return "int"
    o, args = typing.get_origin(t), typing.get_args(t)
    if o is typing.Annotated:
        return _art(args[0])
    if o in (typing.Union, UnionType):
        arten = {_art(a) for a in args if a is not type(None)}
        return arten.pop() if len(arten) == 1 else None
    if o is list:
        return _art(args[0])
    return None


def _params(dep):
    for wo, liste in (("path", dep.path_params), ("query", dep.query_params), ("header", dep.header_params), ("cookie", dep.cookie_params)):
        yield from ((wo, p, dep.call) for p in liste)
    yield from (("form", b, dep.call) for b in dep.body_params if type(b.field_info).__name__ in ("Form", "File"))
    for sub in dep.dependencies:
        yield from _params(sub)


def _routen_von(eintraege):
    for e in eintraege:
        r = getattr(e, "original_router", None)
        if r is not None:
            yield from _routen_von(r.routes)
        elif isinstance(e, APIRoute):
            yield e


def _app_routen():
    import app.main  # noqa: F401  (conftest: Wegwerf-Datenbank)
    routen = list(_routen_von(app.main.app.routes))
    assert len(routen) > 500, f"nur {len(routen)} Routen gefunden -- hat sich die Einbindung geändert?"
    return routen


def _zahlen():
    """(Route, Ort, Parameter, Art) für jeden Parameter mit einer ganzen Zahl."""
    out = []
    for r in _app_routen():
        for wo, p, call in _params(r.dependant):
            art = _art(p.field_info.annotation)
            if art:
                out.append((r, wo, p, art))
    return out


def _grenzen(p) -> tuple:
    unten = [m.ge for m in p.field_info.metadata if isinstance(m, Ge)] + [m.gt + 1 for m in p.field_info.metadata if isinstance(m, Gt)]
    oben = [m.le for m in p.field_info.metadata if isinstance(m, Le)] + [m.lt - 1 for m in p.field_info.metadata if isinstance(m, Lt)]
    return (max(unten) if unten else None, min(oben) if oben else None)


def test_jede_id_ueber_den_typ():
    falsch = sorted({f"{sorted(r.methods)[0]} {r.path}: {wo} {p.name}" for r, wo, p, art in _zahlen() if ist_id(p.name) and art != "id"})
    assert not falsch, f"ID über app/ids.py::Id (x_id: Id): {falsch}"
    assert len([1 for _r, _w, p, _a in _zahlen() if ist_id(p.name)]) > 550


def test_jede_andere_zahl_eingeordnet():
    """Jede ganze Zahl, die keine ID ist, steht in KEINE_ID; mit Art „grenzen“ genau mit den festgelegten Grenzen (innerhalb von int4)."""
    falsch = []
    for r, wo, p, art in _zahlen():
        if ist_id(p.name):
            continue
        eintrag = KEINE_ID.get((r.path, wo, p.name))
        if art == "id" or eintrag is None:
            falsch.append(f"{sorted(r.methods)[0]} {r.path}: {wo} {p.name} {art} -- nicht eingeordnet")
        elif eintrag[0] == G and (_grenzen(p) != eintrag[1] or eintrag[1][0] < INT4_MIN or eintrag[1][1] > INT4_MAX):
            falsch.append(f"{sorted(r.methods)[0]} {r.path}: {wo} {p.name} Grenzen {_grenzen(p)} statt {eintrag[1]}")
    assert not falsch, sorted(set(falsch))


def test_keine_id_stimmt_genau():
    da = {(r.path, wo, p.name) for r, wo, p, _a in _zahlen() if not ist_id(p.name)}
    assert da == set(KEINE_ID), (sorted(da - set(KEINE_ID)), sorted(set(KEINE_ID) - da))


# --- der Typ in jeder Schreibweise -------------------------------------------------------------------------------------------------------------

def test_der_typ_in_jeder_schreibweise():
    app = FastAPI()

    @app.get("/p/{a}")
    def p(a: Id, b: Id = Query(...), c: Id | None = Query(None), d: list[Id] = Query(default=[]), e: Id = Query(1, ge=1), f: Id | None = None):
        return [a, b, c, d, e, f, type(a).__name__]

    @app.get("/p2/{a}")
    def p2(a: Id = Path(...)):
        return a

    @app.post("/f")
    def f(t: str = Form(...), d: Id = Form(...), o: Id | None = Form(None), li: list[Id] = Form([])):
        return [d, o, li]

    c = TestClient(app)
    assert c.get("/p/1?b=2").json() == [1, 2, None, [], 1, None, "int"]  # der Endpunkt bekommt eine gewöhnliche Zahl
    assert c.get(f"/p/{INT4_MAX}?b={INT4_MIN}").status_code == 200       # die Grenzen selbst gehen durch
    for url in (f"/p/{INT4_MAX + 1}?b=2", f"/p/1?b={INT4_MIN - 1}", "/p/1?b=2&c=3000000000", "/p/1?b=2&d=1&d=3000000000", "/p/1?b=2&e=3000000000",
                "/p/1?b=2&f=3000000000", "/p2/3000000000"):
        r = c.get(url)
        assert (r.status_code, r.json()) == (404, {"detail": NICHT_GEFUNDEN}), url
    assert c.get("/p/1?b=2&e=0").status_code == 422      # eine eigene Grenze bleibt
    assert c.get("/p/x?b=2").status_code == 422          # keine Zahl bleibt 422
    for daten in ({"t": "a", "d": "3000000000"}, {"t": "a", "d": "5", "o": "3000000000"}, {"t": "a", "d": "5", "li": ["1", "3000000000"]}):
        r = c.post("/f", data=daten)
        assert (r.status_code, r.json()) == (404, {"detail": NICHT_GEFUNDEN}), daten
    assert c.post("/f", data={"t": "a"}).status_code == 422


# --- jede Route ----------------------------------------------------------------------------------------------------------------------------------

def _admin_client(db):
    """Alle Router, angemeldet als Admin (wie test_v326_monteur_datengrenze._monteur_client)."""
    from app.database import get_db
    from app.models import AppUser
    from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge
    app = FastAPI()
    for router in _routers_in_betriebsreihenfolge():
        app.include_router(router)
    admin = AppUser(username="admin_ids", password_hash="x", display_name="Anna Admin", role="admin", active=True)
    db.add(admin)
    db.commit()

    @app.middleware("http")
    async def _admin(request, call_next):
        request.state.erp_user = admin
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


GUELTIG = {"jahr": "2027", "size": "192", "month": "1", "year": "2027", "years": "1", "start_year": "2027", "days": "7", "limit": "10", "offset": "0",
           "break_minutes": "0", "pause_minuten": "0", "warranty_days": "0", "warranty_months": "60"}


def _anfrage(client, route: APIRoute, id_wert: int, nur: str):
    """Die ID `nur` auf id_wert, jede andere ID 1, jede andere ganze Zahl gültig; andere Pflichtangaben fehlen (die ID scheitert zuerst).
    Je ID einzeln: eine ID im Pfad, die zuerst scheitert, verdeckte sonst eine in Abfrage oder Formular."""
    werte, query, form = {}, {}, {}
    for wo, p, _call in _params(route.dependant):
        art = _art(p.field_info.annotation)
        wert = (str(id_wert) if p.name == nur else "1") if art and ist_id(p.name) else GUELTIG.get(p.name, "1") if art else "x"
        ziel = {"path": werte, "query": query, "form": form}.get(wo)
        if ziel is not None and (wo == "path" or art):
            ziel[p.name] = wert
    return client.request(_methode(route), _url(route, werte), params=query, data=form or None)


def _url(route: APIRoute, werte: dict) -> str:
    """Der Pfad mit den Werten -- auch {name:typ} (Starlette)."""
    return re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: str(werte.get(m.group(1), "x")), route.path)


def _methode(route: APIRoute) -> str:
    andere = sorted(route.methods - {"HEAD"})
    return andere[0] if andere else "HEAD"


def _ids(route) -> list[str]:
    """Die IDs der Route -- am Namen erkannt, nicht am Typ: so prüft der Rundgang das Verhalten auch einer ID, die den Typ nicht hat."""
    return sorted({p.name for _w, p, _c in _params(route.dependant) if _art(p.field_info.annotation) and ist_id(p.name)})


def _mit_id(routen):
    return [r for r in routen if _ids(r)]


def test_jede_route_mit_id_ausserhalb_von_int4_404(threaded_db_session):
    client = _admin_client(threaded_db_session)
    routen = _mit_id(_app_routen())
    assert len(routen) > 450
    falsch, proben = [], 0
    for route in routen:
        for nur in _ids(route):
            for wert in (INT4_MAX + 1, INT4_MIN - 1):
                proben += 1
                r = _anfrage(client, route, wert, nur)
                # {x:int} (Starlette) nimmt nur Ziffern: eine negative Zahl trifft die Route gar nicht -- 404 ohne Route, auch kein 500
                ohne_route = wert < 0 and ":int}" in route.path and r.status_code == 404 and r.json() == {"detail": "Not Found"}
                if not ohne_route and (r.status_code != 404 or r.content and r.json() != {"detail": NICHT_GEFUNDEN}):
                    falsch.append(f"{sorted(route.methods)[0]} {route.path} {nur}={wert}: {r.status_code} {r.text[:80]}")
    assert proben > 1100
    assert not falsch, falsch[:20]


def test_jede_andere_zahl_ueber_ihrer_grenze_422_sonst_nie_500(threaded_db_session):
    """Art „grenzen“: über und unter der Grenze 422 an diesem Feld. Art „geprueft“: Werte über int4 und über 64 Bit -- nie 500."""
    client = _admin_client(threaded_db_session)
    falsch = []
    for r, wo, p, art in _zahlen():
        eintrag = KEINE_ID.get((r.path, wo, p.name))
        if art != "int" or wo not in ("path", "query") or eintrag is None:
            continue
        werte_der_probe = (eintrag[1][1] + 1, eintrag[1][0] - 1) if eintrag[0] == G else (INT4_MAX + 1, 2**63, 10**30, -(10**30))
        for wert in werte_der_probe:
            werte = {q.name: GUELTIG.get(q.name, "1") for q in r.dependant.path_params}
            query = {p.name: str(wert)} if wo == "query" else {}
            if wo == "path":
                werte[p.name] = str(wert)
            antwort = client.request(_methode(r), _url(r, werte), params=query)
            if eintrag[0] == P:
                if antwort.status_code >= 500:
                    falsch.append(f"{_methode(r)} {r.path} {p.name}={wert}: {antwort.status_code} {antwort.text[:100]}")
                continue
            if _methode(r) == "HEAD" and antwort.status_code == 422:  # HEAD ohne Körper: der Status genügt
                continue
            fehler = antwort.json().get("detail") if antwort.status_code == 422 and antwort.content else None
            if not (isinstance(fehler, list) and any(e.get("loc", [None])[-1] == p.name and e.get("type") in ("less_than_equal", "greater_than_equal")
                                                     for e in fehler)):
                falsch.append(f"{_methode(r)} {r.path} {p.name}={wert}: {antwort.status_code} {antwort.text[:100]}")
    assert not falsch, falsch


# --- PostgreSQL ----------------------------------------------------------------------------------------------------------------------------------

def test_unter_postgresql():
    """Die größte ID geht bis zur Datenbank (404 der Route), eine größere nicht (404 vor der Datenbank) -- bis 1.9.360 dort 500."""
    from fastapi import FastAPI as _F
    from app.database import get_db
    from app.models import AppUser, Customer
    from app.routers import customers, orders, projects
    from tests.befund_vor_echtbetrieb import pg_sitzung
    with pg_sitzung("ids_im_pfad") as db:
        admin = AppUser(username="admin_pg", password_hash="x", display_name="Anna Admin", role="admin", active=True)
        db.add(admin)
        db.add(Customer(name="Probe", last_name="Probe"))
        db.commit()
        app = _F()
        for m in (customers, orders, projects):
            app.include_router(m.router)

        @app.middleware("http")
        async def _admin(request, call_next):
            request.state.erp_user = admin
            return await call_next(request)

        app.dependency_overrides[get_db] = lambda: db
        c = TestClient(app, raise_server_exceptions=False)
        for url in ("/api/customers/{}", "/api/orders/{}", "/api/projects/{}/akte", "/api/customers/{}/akte"):
            for wert in (INT4_MAX, INT4_MAX + 1, 3_000_000_000, INT4_MIN - 1):
                r = c.get(url.format(wert))
                assert r.status_code == 404, (url, wert, r.status_code, r.text[:120])
        assert c.get("/api/projects/1/akte", params={"auftrag": 3_000_000_000}).status_code == 404
