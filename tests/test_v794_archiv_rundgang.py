"""Version 1.10.23 (Antwort F10): Rundgang -- jede schreibende Route der Anwendung mit den Kennungen eines Vorgangs im Archiv ändert nichts an ihm.

Jede Route mit POST, PUT, PATCH oder DELETE unter /api/ (alle Router in der Reihenfolge von app/main.py), als Admin, nacheinander in einer Datenbank: in
Pfad, Abfrage und Körper stehen die Kennungen des Kunden, Objekts, der Dachfläche, des Projekts, Angebots, der Anfrage … im Archiv, jede andere Kennung
zeigt ins Leere (999999). Danach je Route: keine 500, jede Zeile eines Teils im Archiv unverändert, kein neuer Teil und kein neuer Verweis auf ihn, keine
neue Datei in seinen Ordnern, kein Versand an ihm. Gezählt wird, wie viele Routen mit der Meldung des Archivs (409) endeten -- der Bericht nennt die Zahl.

Ergänzt test_v793_archivschutz.py (Struktur und gezielte Abläufe): dort steht, warum eine Route ablehnt; hier, dass keine an ihm vorbei schreibt.
"""

import io
import typing
from collections import Counter

from fastapi.routing import APIRoute
from sqlalchemy import func, select

from app.archivschutz import MELDUNGEN, TEILE, ZURUECKHOLEN
from app.database import Base
from app.models import EmailDispatch
from tests.test_v762_rundgang_postgresql import TAG, _json_modell, _koerper, _ohne_none
from tests.test_v793_archivschutz import PNG, _vorab, welt  # noqa: F401 -- welt ist die Fixture

LEER = 999999


class _Welt(dict):
    """Die Kennungen für Körper und Abfrage: die des Archivs, jede andere Kennung ins Leere."""

    def get(self, name, vorgabe=None):
        if name in self:
            return self[name]
        return LEER if name.endswith("_id") else vorgabe


def _kennungen(welt) -> _Welt:
    return _Welt(customer_id=welt.k.id, property_id=welt.objekt.id, roof_area_id=welt.flaeche.id, project_id=welt.pj.id, quote_id=welt.angebot.id,
                 inquiry_id=welt.anf.id, participant_id=welt.beteiligter.id, source_quote_id=welt.angebot.id, kunde_id=welt.k.id)


def _pfad(route: APIRoute, welt) -> str:
    """Jeder Pfadparameter: die Kennung des Teils im Archiv, wenn der Name (im Zusammenhang des Pfads) einen Teil nennt -- sonst ins Leere."""
    p = route.path
    werte = {"customer_id": welt.k.id, "property_id": welt.objekt.id, "roof_area_id": welt.flaeche.id, "project_id": welt.pj.id,
             "quote_id": welt.angebot.id, "inquiry_id": welt.anf.id, "participant_id": welt.beteiligter.id, "info_id": welt.info.id}
    if p.startswith("/api/quotes/"):
        werte.update(item_id=welt.position.id, section_id=welt.titel.id)
    if p.startswith(("/api/roof-components/", "/api/roof-areas/")):
        werte.update(component_id=welt.bauteil.id)
    if p.startswith("/api/customer-documents/"):
        werte.update(document_id=welt.kundendokument.id)
    if p.startswith("/api/project-documents/"):
        werte.update(document_id=welt.projektdokument.id)
    if p.startswith("/api/property-documents/"):
        werte.update(document_id=welt.objektdokument.id)
    if p.startswith("/api/aufbewahrung/"):
        werte.update(art="kunde", kennung=LEER)  # das Zurückholen selbst ist erlaubt (test_v793) -- hier nicht
    aus = {}
    for param in route.dependant.path_params:
        t = _ohne_none(param.field_info.annotation) if param.field_info.annotation is not None else str
        aus[param.name] = werte.get(param.name, LEER if t is not str or param.name.endswith("_id") else "x")
    return p.format(**aus)


def _abfrage(route: APIRoute, kennungen: _Welt) -> dict:
    q = {}
    for p in route.dependant.query_params:
        if not p.field_info.is_required():
            continue
        q[p.name] = kennungen.get(p.name, TAG if "date" in p.name or p.name in ("von", "bis", "tag", "start", "end") else "1")
    return q


def _formular(route: APIRoute, kennungen: _Welt) -> tuple[dict, dict]:
    """Felder und Dateien einer Formular-Route: Kennungen wie oben, Text „x“, Datum, eine kleine PNG-Datei."""
    felder, dateien = {}, {}
    for b in route.dependant.body_params:
        art = type(b.field_info).__name__
        if art == "File":
            dateien[b.alias or b.name] = ("plan.png", io.BytesIO(PNG), "image/png")
        elif art == "Form":
            t = _ohne_none(b.field_info.annotation)
            name = b.alias or b.name
            if name.endswith("_id") or t is int:
                felder[name] = str(kennungen.get(name, 1))
            elif t is bool:
                felder[name] = "false"
            elif "date" in name or name.endswith("_on"):
                felder[name] = TAG
            elif typing.get_origin(t) is list:
                felder[name] = []
            else:
                felder[name] = "x"
    return felder, dateien


def _sammeln(db, welt) -> tuple[dict, dict]:
    """Die Zeilen aller Teile, die am Vorgang im Archiv hängen (bis zum Fixpunkt über die Fremdschlüssel), und je Tabelle außerhalb der Teile die Zahl der
    Verweise auf sie."""
    tabellen = Base.metadata.tables
    ids = {"customers": {welt.k.id}, "projects": {welt.pj.id}, "inquiries": {welt.anf.id}}
    while True:
        neu = False
        for name in TEILE:
            t = tabellen[name]
            for fk in t.foreign_keys:
                ziel = fk.column.table.name
                if ziel in ids and ids[ziel]:
                    gefunden = set(db.scalars(select(t.c.id).where(fk.parent.in_(ids[ziel]))))
                    if not gefunden <= ids.setdefault(name, set()):
                        ids[name] |= gefunden
                        neu = True
        if not neu:
            break
    zeilen = {name: sorted((tuple(z) for z in db.execute(select(tabellen[name]).where(tabellen[name].c.id.in_(k)))), key=repr)
              for name, k in sorted(ids.items())}
    verweise = {}
    for name, t in tabellen.items():
        if name in TEILE:
            continue
        for fk in t.foreign_keys:
            ziel = fk.column.table.name
            if ziel in ids and ids[ziel]:
                verweise[f"{name}.{fk.parent.name}"] = db.scalar(select(func.count()).select_from(t).where(fk.parent.in_(ids[ziel])))
    return zeilen, verweise


def _dateien(welt) -> dict:
    from app.customer_documents import customer_directory
    from app.project_documents import project_directory
    from app.project_participants import POWER_OF_ATTORNEY_ROOT
    from app.property_documents import property_directory
    from app.roof_area_sketches import sketch_directory
    ordner = {"kunde": customer_directory(welt.k.id), "projekt": project_directory(welt.pj.id), "objekt": property_directory(welt.objekt.id),
              "skizzen": sketch_directory(), "vollmachten": POWER_OF_ATTORNEY_ROOT}
    return {k: sorted(str(p) for p in o.rglob("*") if p.is_file()) if o.exists() else [] for k, o in ordner.items()}


def test_jede_schreibende_route_aendert_nichts_am_archiv(welt, router_test_client, monkeypatch):
    from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge
    gesendet = []
    monkeypatch.setattr("app.email_sending.send_message", lambda *a, **k: gesendet.append(a))
    routers = _routers_in_betriebsreihenfolge()
    from fastapi.testclient import TestClient
    c = TestClient(router_test_client(welt.db, *routers).app, raise_server_exceptions=False)  # eine Ausnahme als 500, der Rundgang läuft weiter
    db, kennungen = welt.db, _kennungen(welt)
    routen = [r for router in routers for r in router.routes if isinstance(r, APIRoute) and r.path.startswith("/api/")
              and r.methods & {"POST", "PUT", "PATCH", "DELETE"} and r.path not in ZURUECKHOLEN]  # das Zurückholen ist erlaubt (test_v793)
    routen.sort(key=lambda r: ("DELETE" in r.methods, r.path))  # Löschen zuletzt
    vorher_zeilen, vorher_verweise = _sammeln(db, welt)
    vorher_dateien = _dateien(welt)
    status, archiv, rot, fehler = Counter(), [], [], []
    for route in routen:
        methode = sorted(route.methods & {"POST", "PUT", "PATCH", "DELETE"})[0]
        modell, als_liste = _json_modell(route)
        kw = {"params": _abfrage(route, kennungen)}
        if modell is not None:
            koerper = _koerper(modell, kennungen)
            kw["json"] = [koerper] if als_liste else koerper
        else:
            felder, dateien = _formular(route, kennungen)
            if felder:
                kw["data"] = felder
            if dateien:
                kw["files"] = dateien
        antwort = c.request(methode, _pfad(route, welt), **kw)
        db.rollback()  # nach einer Ablehnung im Flush stehen neue Objekte noch in der geteilten Testsitzung
        db.expire_all()
        status[antwort.status_code] += 1
        if antwort.status_code >= 500:
            fehler.append(f"{methode} {_pfad(route, welt)}")
        elif antwort.status_code == 409 and antwort.json().get("detail") in MELDUNGEN.values():
            archiv.append(f"{methode} {route.path}")
        zeilen, verweise = _sammeln(db, welt)
        if (zeilen, verweise) != (vorher_zeilen, vorher_verweise):
            geaendert = sorted({k for k in set(zeilen) | set(vorher_zeilen) if zeilen.get(k) != vorher_zeilen.get(k)}
                               | {k for k in set(verweise) | set(vorher_verweise) if verweise.get(k) != vorher_verweise.get(k)})
            rot.append(f"{methode} {route.path}: {antwort.status_code}, geändert: {geaendert}")
            vorher_zeilen, vorher_verweise = zeilen, verweise
        if _dateien(welt) != vorher_dateien:
            rot.append(f"{methode} {route.path}: neue oder gelöschte Datei")
            vorher_dateien = _dateien(welt)
    assert not rot, "\n".join(rot)
    assert db.scalar(select(func.count()).select_from(EmailDispatch).where(EmailDispatch.document_type == "angebot",
                                                                         EmailDispatch.document_id == welt.angebot.id)) == 0
    assert len(routen) > 450
    # jede Route mit archiv_vorab() und einem Teil im Pfad endet mit der Meldung des Archivs; dazu die, die erst die Sitzung ablehnt (Zahl im Bericht)
    vorab = {f"{sorted(r.methods & {'POST', 'PUT', 'PATCH', 'DELETE'})[0]} {r.path}" for r in routen
             if _vorab(r) is not None and {p.name for p in r.dependant.path_params} & set(_vorab(r).zuordnung)}
    assert vorab <= set(archiv), sorted(vorab - set(archiv))
    assert len(vorab) > 50
    print(f"\nRundgang Archiv: {len(routen)} Routen, Status {dict(sorted(status.items()))}, Meldung des Archivs {len(archiv)} (vorab {len(vorab)}, "
          f"aus der Sitzung: {sorted(set(archiv) - vorab)}); 500 (Kennungen ins Leere, nicht am Archiv): {fehler}")
