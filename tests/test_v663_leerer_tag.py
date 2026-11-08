"""Version 1.9.263 (Stufe 6, R5a, Punkt 4): der leere Tag -- ein Tag ohne Personen und Geräte.

    Rand        am Anfang und Ende fällt jeder Tag ohne jemanden weg (auch ein Wochenende), nach jedem Schreiben; einzelne Tage bleiben, wer danach an allen
                Tagen steht, heißt „alle Tage“; die Stunden bleiben am Einsatz
    Mitte       der Einsatz bleibt einer: leere_tage (nur Arbeitstage), abschnitte (die Stücke des Balkens, ein Tag ohne Arbeit an der Lücke gehört nicht
                dazu); kein Hinweis, kein Zähler
    Ganz leer   nimmt eine Änderung dem Einsatz den letzten Tag mit jemandem: 409 „Der Einsatz hat dann niemanden mehr.“ mit Löschen | Behalten, nichts
                gespeichert; wenn_leer=loeschen löscht, behalten lässt ihn mit dem zuletzt geleerten Tag stehen (mehrere zugleich: der erste); die Prüfung
                des Dialogs fragt nicht, sie sagt „leer“
    Regeln      ohne Kolonne beim Anlegen eine Person oder ein Gerät (Antwort 4), danach darf er leer werden; eine Kranvermietung braucht ihr Gerät nur
                beim Anlegen
    Seite       die Rückfrage im Dialog und beim Ziehen (leerFrage(), wenn_leer)
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.kran_kalender import soll
from app.main import create_resource
from app.models import OperationalResource, PlanningSlot
from app.planning import EINSATZ_LEER, EinsatzWirdLeer, _load_slot, create_slot, einsatz_pruefen, planning_board, slot_to_dict, update_slot
from app.schemas import OperationalResourceCreate
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v660_besetzung_je_tag import _personen, welt  # noqa: F401 -- welt ist eine Fixture

ROOT = Path(__file__).resolve().parent.parent
MO = date(2026, 11, 2)
FR_VORHER = MO - timedelta(days=3)


def _tag(n):
    return MO + timedelta(days=n)


def _iso(d):
    return d.isoformat()


def _einsatz(w, personen, von, bis, auftrag="b", **mehr):
    return create_slot(w["db"], order_id=w[auftrag].id, team_id=None, start_date=von, end_date=bis, planned_hours=Decimal("12"), trotzdem_planen=True,
                       besetzung=[{"employee_id": w[n], "tage": t} for n, t in personen.items()], **mehr)


def _zeitraum(db, slot_id):
    db.expire_all()
    s = db.get(PlanningSlot, slot_id)
    return (s.start_date, s.end_date) if s is not None else None


# --- Rand ---------------------------------------------------------------------------------------------------------------------------------

def test_rand_kuerzt_beim_anlegen_und_die_stunden_bleiben(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [_tag(1), _tag(2)]}, _tag(0), _tag(4))
    assert _zeitraum(db, slot.id) == (_tag(1), _tag(2))
    assert _personen(db, slot.id) == [(welt["tom"], None)]  # danach an allen Tagen
    assert _load_slot(db, slot.id).capacity.planned_hours == Decimal("12.00")


def test_rand_kuerzt_auch_ein_wochenende(welt):
    samstag = MO - timedelta(days=2)
    slot = _einsatz(welt, {"tom": [MO]}, samstag, MO)  # Sa und So ohne jemanden am Anfang fallen weg
    assert _zeitraum(welt["db"], slot.id) == (MO, MO)


def test_rand_kuerzt_beim_aendern(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": None, "mia": None}, _tag(0), _tag(4))
    update_slot(db, slot.id, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(1), _tag(3)]}, {"employee_id": welt["mia"], "tage": [_tag(2)]}],
                trotzdem_planen=True)
    assert _zeitraum(db, slot.id) == (_tag(1), _tag(3))
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(_tag(1)), _iso(_tag(3))]), (welt["mia"], [_iso(_tag(2))])]


# --- Mitte --------------------------------------------------------------------------------------------------------------------------------

def test_mitte_bleibt_ein_einsatz_mit_luecke(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [_tag(0), _tag(2)]}, _tag(0), _tag(2))
    d = slot_to_dict(_load_slot(db, slot.id), db=db)
    assert (d["start_date"], d["end_date"], d["niemand"]) == (_tag(0), _tag(2), False)
    assert d["leere_tage"] == [_iso(_tag(1))]
    assert d["abschnitte"] == [[_iso(_tag(0)), _iso(_tag(0))], [_iso(_tag(2)), _iso(_tag(2))]]


def test_lucke_am_wochenende_ohne_die_tage_ohne_arbeit(welt):
    db = welt["db"]
    do, di = MO - timedelta(days=4), MO + timedelta(days=1)  # Do 29.10. bis Di 03.11.: Fr und Mo leer, Sa und So dazwischen
    slot = _einsatz(welt, {"tom": [do, di]}, do, di)
    d = slot_to_dict(_load_slot(db, slot.id), db=db)
    assert d["leere_tage"] == [_iso(do + timedelta(days=1)), _iso(MO)]
    assert d["abschnitte"] == [[_iso(do), _iso(do)], [_iso(di), _iso(di)]]


def test_wochenende_in_der_mitte_ist_nie_leer(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [FR_VORHER, MO]}, FR_VORHER, MO)
    d = slot_to_dict(_load_slot(db, slot.id), db=db)
    assert (d["leere_tage"], d["abschnitte"]) == ([], [[_iso(FR_VORHER), _iso(MO)]])


def test_leerer_tag_zaehlt_nirgends(welt):
    db = welt["db"]
    _einsatz(welt, {"tom": [_tag(0), _tag(2)]}, _tag(0), _tag(2))
    tafel = planning_board(db, MO, MO + timedelta(days=13))
    assert tafel["zaehler"] == {"warnungen": 0, "hinweise": 0}
    [s] = tafel["slots"]
    assert (s["conflicts"], s["leere_tage"]) == ([], [_iso(_tag(1))])


def test_kran_termin_teilt_sich_am_leeren_tag(welt):
    db = welt["db"]
    kran = create_resource(OperationalResourceCreate(resource_number="K-9", resource_type="Kran", name="Kran 30 m", identifier="K9"), db)
    db.get(OperationalResource, kran.id).outlook_mailbox = "kran@dachkonzepte.example"
    db.commit()
    slot = _einsatz(welt, {"tom": [_tag(0), _tag(2)]}, _tag(0), _tag(2), geraete=[{"resource_id": kran.id, "tage": [_tag(0), _tag(2)]}])
    assert sorted((von, bis) for _, von, bis in soll(_load_slot(db, slot.id))) == [(_tag(0), _tag(0)), (_tag(2), _tag(2))]


# --- Ganz leer ----------------------------------------------------------------------------------------------------------------------------

def test_leer_werden_fragt_zurueck_und_aendert_nichts(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [_tag(0), _tag(2)]}, _tag(0), _tag(2))
    with pytest.raises(EinsatzWirdLeer, match=EINSATZ_LEER):
        update_slot(db, slot.id, besetzung=[])
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(_tag(0)), _iso(_tag(2))])]
    r = welt["client"].put(f"/api/planning/slots/{slot.id}", json={"besetzung": []})
    assert r.status_code == 409, r.text
    assert r.json() == {"detail": EINSATZ_LEER, "rueckfrage": {"art": "einsatz_leer", "text": EINSATZ_LEER, "optionen": ["loeschen", "behalten"]}}
    assert welt["client"].put(f"/api/planning/slots/{slot.id}", json={"besetzung": [], "wenn_leer": "weg"}).status_code == 422


def test_behalten_mit_dem_zuletzt_geleerten_tag(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [_tag(2)], "mia": None}, _tag(0), _tag(2))
    update_slot(db, slot.id, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(2)]}], trotzdem_planen=True)  # Mia weg -> der Rand kürzt auf Mi
    assert _zeitraum(db, slot.id) == (_tag(2), _tag(2))
    r = welt["client"].put(f"/api/planning/slots/{slot.id}", json={"besetzung": [], "wenn_leer": "behalten"})
    assert r.status_code == 200, r.text
    assert (r.json()["start_date"], r.json()["end_date"], r.json()["niemand"], r.json()["employees"]) == (_iso(_tag(2)), _iso(_tag(2)), True, [])
    assert r.json()["abschnitte"] == [[_iso(_tag(2)), _iso(_tag(2))]]  # bleibt sichtbar


def test_behalten_mehrere_zugleich_der_erste(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": [_tag(0), _tag(2)]}, _tag(0), _tag(2))
    update_slot(db, slot.id, besetzung=[], wenn_leer="behalten")
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(0))


def test_loeschen(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": None}, _tag(0), _tag(2))
    r = welt["client"].put(f"/api/planning/slots/{slot.id}", json={"besetzung": [], "wenn_leer": "loeschen"})
    assert r.status_code == 200 and r.json() == {"deleted": True, "id": slot.id}, r.text
    assert _zeitraum(db, slot.id) is None


def test_schon_leer_fragt_nicht(welt):
    db = welt["db"]
    slot = create_slot(db, order_id=welt["b"].id, team_id=None, start_date=_tag(0), end_date=_tag(0), planned_hours=Decimal("1"),
                       employee_ids=[welt["tom"]])
    update_slot(db, slot.id, besetzung=[], wenn_leer="behalten")
    update_slot(db, slot.id, notes="nur die Notiz")  # ganz leer bleibt ganz leer -- keine Rückfrage
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(0))


def test_pruefung_des_dialogs_sagt_leer_und_fragt_nicht(welt):
    db = welt["db"]
    slot = _einsatz(welt, {"tom": None}, _tag(0), _tag(2))
    assert einsatz_pruefen(db, slot.id, besetzung=[])["leer"] is True
    assert einsatz_pruefen(db, slot.id, notes="x")["leer"] is False
    assert _personen(db, slot.id) == [(welt["tom"], None)]


# --- Regeln (Antwort 4) -------------------------------------------------------------------------------------------------------------------

def test_ohne_kolonne_genuegt_beim_anlegen_ein_geraet(welt):
    client = welt["client"]
    body = {"order_id": welt["b"].id, "team_id": None, "start_date": _iso(_tag(0)), "end_date": _iso(_tag(0)), "planned_hours": "1"}
    r = client.post("/api/planning/slots", json={**body, "geraete": [{"resource_id": welt["kran"]}]})
    assert r.status_code == 200 and r.json()["employees"] == [], r.text
    r = client.post("/api/planning/slots", json=body)
    assert r.status_code == 422 and "mindestens eine Person oder ein Gerät" in r.text, r.text
    from app.planning import BesetzungUngueltig
    with pytest.raises(BesetzungUngueltig, match="Person oder ein Gerät"):
        create_slot(welt["db"], order_id=welt["b"].id, team_id=None, start_date=_tag(0), end_date=_tag(0), planned_hours=Decimal("1"))


# --- Seite --------------------------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_seite_fragt_und_schickt_die_wahl():
    vorbereitung = "var leerDialog = {open: false, showModal() { this.open = true }, close() { this.open = false }}; var gewaehlt = [];"
    ablauf = ("const e = Object.assign(new Error('x'), {status: 409, rueckfrage: {art: 'einsatz_leer', text: 'Der Einsatz hat dann niemanden mehr.'}});"
              "const andere = Object.assign(new Error('y'), {status: 409, warnungen: [{}]});"
              "AUFRUFE.push({andere: leerFrage(andere, () => null), frage: leerFrage(e, async w => { gewaehlt.push(w) }), offen: leerDialog.open,"
              " titel: document.getElementById('ldTitel').textContent});"
              "await leerEntscheiden('behalten'); AUFRUFE.push({gewaehlt, offen: leerDialog.open});")
    aufrufe = im_browser("planning.html", ["leerFrage", "leerEntscheiden"], vorbereitung + "var leerWeiter = null;", ablauf)
    assert aufrufe[-2] == {"andere": False, "frage": True, "offen": True, "titel": "Der Einsatz hat dann niemanden mehr."}
    assert aufrufe[-1] == {"gewaehlt": ["behalten"], "offen": False}


def test_dialog_und_ziehen_nehmen_die_rueckfrage():
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "if(leerFrage(e,async wahl=>{const a=await speichern('tafel',()=>api(url,{method:methode,headers:{'Content-Type':'application/json'},body:JSON.stringify({...w,wenn_leer:wahl})}))" in seite
    assert "&&!leerFrage(err,wahl=>senden(false,wahl))" in seite and "...(wahl?{wenn_leer:wahl}:{})" in seite
    assert '<button type="button" class="ds-knopf" id="leerLoeschen" data-klick="leerWahl" data-wahl="loeschen">Löschen</button>' in seite
    assert "textContent=p.leer?'Der Einsatz hat dann niemanden mehr – beim Speichern: löschen oder behalten.':''" in seite  # der Dialog sagt es vorher


def test_ganz_leer_mit_stunden_meldet_die_kapazitaet(welt):
    """Der leere Tag selbst meldet nichts; fehlt dadurch Kapazität für die Stunden des Einsatzes, sagt das „Kapazität reicht nicht“ wie bisher -- auch an
    einem behaltenen, ganz leeren Einsatz (seine Stunden bleiben)."""
    db = welt["db"]
    slot = _einsatz(welt, {"tom": None}, _tag(0), _tag(0))
    update_slot(db, slot.id, besetzung=[], wenn_leer="behalten")
    [s] = planning_board(db, MO, MO + timedelta(days=13))["slots"]
    assert [(k["type"], k["stufe"]) for k in s["conflicts"]] == [("capacity", "hinweis")]
