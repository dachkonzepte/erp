"""Version 1.9.255 (Stufe 6, R4b, Punkt 5): die Zeile eines Geräts trägt nur die Warnungen und Hinweise zu diesem Gerät.

    Daten       „Gerät doppelt“ und „Prüffrist abgelaufen“ nennen das Gerät (resource_id); ein Termin direkt im Postfach eines Geräts warnt jetzt auch auf
                der Tafel (bis 1.9.254 nur beim Speichern) -- als „Gerät doppelt“ mit dem Gerät, an den Tagen des Geräts, nicht bei geschlossenen Aufträgen
    Seite       einsatzBalken(…, 'geraet', …, geraet) zeigt nur Konflikte mit dieser resource_id -- in „Kolonnen“ (Abschnitt GERÄTE) und in „Geräte“; die Zeile
                der Kolonne zeigt weiter alles, „Personen“ nur die der Person (1.9.250)
Im Browser: scripts/klicktest_plantafel_tafel.py (Pritschen und Kran ohne Kais Warnung und Neles Punkt) und klicktest_plantafel_personen.py (Termin im
Postfach am Kran, abgelaufene Prüfung an der Pritsche -- nur in ihren Zeilen).
"""

import json
from datetime import date, datetime, timedelta

from app.models import CalendarEvent, OperationalAsset, OperationalAssetInspection
from app.planning import create_slot, planning_board
from tests.test_v090_planning_board import setup_order
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.test_v634_geraete_je_einsatz import _geraet

MO = date(2026, 11, 2)


def _tafel(db):
    return planning_board(db, MO, MO + timedelta(days=13))


def _konflikte(tafel, projekt):
    return sorted((k["type"], k.get("resource_id"), k.get("employee_id"), str(k.get("date"))) for s in tafel["slots"] if s["project_name"] == projekt
                  for k in s["conflicts"])


def _welt(db):
    tom, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Kai")
    kran, pritsche = _geraet(db, "K-1", "Kran"), _geraet(db, "F-1", "Pritsche")
    return {"tom": tom, "kai": kai, "kran": kran, "pritsche": pritsche, "nord": _kolonne(db, "N", [tom]),
            "a": setup_order(db, "1"), "b": setup_order(db, "2"), "c": setup_order(db, "3")}


def _einsatz(db, order, personen, tage, geraete, status="fest"):
    return create_slot(db, order_id=order.id, team_id=None, employee_ids=[p.id for p in personen], start_date=MO + timedelta(days=tage[0]),
                       end_date=MO + timedelta(days=tage[1]), status=status, geraete=geraete, planned_hours=1, trotzdem_planen=True)


def test_geraet_doppelt_und_person_doppelt_nennen_wen(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    _einsatz(db, w["a"], [w["kai"]], (0, 2), [{"resource_id": w["kran"]}, {"resource_id": w["pritsche"]}])
    _einsatz(db, w["b"], [w["kai"]], (1, 3), [{"resource_id": w["kran"]}])
    tafel = _tafel(db)
    assert [k for k in _konflikte(tafel, "Plan Projekt 1") if k[0] in ("employee", "resource")] == [
        ("employee", None, w["kai"].id, "None"), ("resource", w["kran"], None, "None")]  # die Pritsche ist nicht doppelt


def test_pruefung_nennt_das_geraet(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    asset = OperationalAsset(resource_id=w["pritsche"])
    db.add(asset); db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=MO))
    db.commit()
    _einsatz(db, w["a"], [w["tom"]], (0, 2), [{"resource_id": w["kran"]}, {"resource_id": w["pritsche"]}])
    assert _konflikte(_tafel(db), "Plan Projekt 1") == [("pruefung", w["pritsche"], None, "2026-11-03")]


def _termin(db, geraet, von, bis, **mehr):
    db.add(CalendarEvent(title=mehr.pop("title", "Müller"), start_at=von, end_at=bis, resource_id=geraet, external_source="outlook",
                         outlook_postfach="kran@x.de", outlook_event_id=f"e-{von:%d%H}", **mehr))
    db.commit()


def test_termin_im_postfach_warnt_auf_der_tafel(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    _termin(db, w["kran"], datetime(2026, 11, 4, 9), datetime(2026, 11, 4, 11))                  # Mi
    _termin(db, w["kran"], datetime(2026, 11, 7), datetime(2026, 11, 8), all_day=True, title="Wochenende")  # Sa/So: kein Arbeitstag
    _termin(db, w["kran"], datetime(2026, 11, 11, 9), datetime(2026, 11, 11, 10), title="Meier")            # Mi der zweiten Woche
    _einsatz(db, w["a"], [w["tom"]], (0, 6), [{"resource_id": w["kran"]}])                        # Mo–So mit dem Kran
    _einsatz(db, w["b"], [w["kai"]], (2, 2), [{"resource_id": w["pritsche"]}])                   # Mi, ohne den Kran
    _einsatz(db, w["c"], [w["kai"]], (7, 11), [{"resource_id": w["kran"], "tage": [(MO + timedelta(days=11)).isoformat()]}])  # Kran nur am Fr 13.11.
    tafel = _tafel(db)
    a = [s for s in tafel["slots"] if s["project_name"] == "Plan Projekt 1"][0]
    assert [(k["type"], k["stufe"], k["resource_id"], k["label"], str(k["date"])) for k in a["conflicts"] if k.get("resource_id") == w["kran"]] == [
        ("resource", "warnung", w["kran"], "Kran · Termin: Müller", "2026-11-04")]  # das Wochenende belegt nicht (an Arbeitstagen, wie beim Speichern)
    assert _konflikte(tafel, "Plan Projekt 2") == [] and [k for k in _konflikte(tafel, "Plan Projekt 3") if k[1] == w["kran"]] == []
    assert tafel["zaehler"]["warnungen"] >= 1


def test_termin_eines_geschlossenen_auftrags_warnt_nicht(threaded_db_session):
    from app.auftragsstatus import status_aendern
    db = threaded_db_session
    w = _welt(db)
    _termin(db, w["kran"], datetime(2026, 11, 3, 9), datetime(2026, 11, 3, 10))
    _einsatz(db, w["a"], [w["tom"]], (0, 2), [{"resource_id": w["kran"]}])
    status_aendern(db, w["a"].id, "storniert", "Test")
    db.commit()
    assert _konflikte(_tafel(db), "Plan Projekt 1") == []


def _balken(slot, zeile, person=None, geraet=None):
    vorbereitung = (f"var board = {{teams: []}}; var s = {json.dumps(slot)}; "
                    "function vornamen() { return ''; } function einsatzTitel() { return ''; }")
    ablauf = f"const b = einsatzBalken(s, {json.dumps(zeile)}, undefined, {json.dumps(person)}, {json.dumps(geraet)}); AUFRUFE.push([b.warn, b.hint]);"
    [erg] = im_browser("planning.html", ["imStueck", "einsatzBalken"], vorbereitung, ablauf)  # seit 1.9.264 mit imStueck
    return erg


SLOT = {"id": 1, "team_id": None, "art": "baustelle", "status": "fest", "order_status": "laeuft", "project_name": "A", "project_number": "P-1",
        "customer_name": "K", "start_date": "2026-11-02", "end_date": "2026-11-04", "art_label": "Baustelle", "status_label": "fest",
        "employees": [{"id": 5, "name": "Kai K", "vorname": "Kai"}, {"id": 6, "name": "Nele N", "vorname": "Nele"}],
        "resources": [{"id": 20, "name": "Kran"}, {"id": 21, "name": "Pritsche"}],
        "conflicts": [{"type": "employee", "stufe": "warnung", "employee_id": 5, "label": "Kai"},
                      {"type": "antrag_offen", "stufe": "hinweis", "employee_id": 6, "label": "Nele"},
                      {"type": "holiday", "stufe": "hinweis", "label": "Feiertag"}]}


@nur_mit_node
def test_geraetezeile_ohne_konflikte_der_personen():
    assert _balken(SLOT, "geraet", geraet=20) == [False, False]   # Kais Warnung, Neles Antrag, der Feiertag: nicht am Gerät
    assert _balken(SLOT, "kolonne") == [True, True]               # die Zeile der Kolonne zeigt alles
    assert _balken(SLOT, "person", person=6) == [False, True]     # „Personen“: nur Neles Punkt (1.9.250)


@nur_mit_node
def test_geraetezeile_mit_ihren_eigenen():
    slot = {**SLOT, "conflicts": SLOT["conflicts"] + [{"type": "resource", "stufe": "warnung", "resource_id": 20, "label": "Kran · Termin: Müller"},
                                                      {"type": "pruefung", "stufe": "warnung", "resource_id": 21, "label": "Pritsche · UVV"}]}
    assert _balken(slot, "geraet", geraet=20) == [True, False]    # Kran: nur sein Termin
    assert _balken(slot, "geraet", geraet=21) == [True, False]    # Pritsche: nur ihre Prüfung
    assert _balken({**slot, "conflicts": slot["conflicts"][-1:]}, "geraet", geraet=20) == [False, False]  # die Prüfung der Pritsche nicht am Kran
