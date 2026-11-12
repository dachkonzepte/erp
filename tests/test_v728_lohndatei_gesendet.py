"""Version 1.9.328 (Lohn L2c-2, Punkt 1): an jeder abgelegten Datei „An das Steuerbüro gesendet“.

    setzen         POST /api/time-backoffice/lohndateien/{id}/versendet -- Admin und Büro – Finanzen (require_lohndaten), mit Zeitpunkt und Konto
    je Monat eine  eine zweite im selben Monat 409 mit Grund (auch wenn zwei zugleich klicken: der eindeutige Index, dieselbe Meldung); ein anderer Monat geht
    nur Dateien    ein Abgleich (art „abgleich“) 409; schon vermerkt 409; unbekannt 404
    zurücknehmen   DELETE …/versendet -- nur der Admin (403 für Büro – Finanzen); nicht vermerkt 409
    Historie       jedes Setzen und Zurücknehmen ein Eintrag in der Änderungshistorie (Entscheidung 12.11.2026)
    Seite          „Monat & Lohn“: der Vermerk an der Datei, der Knopf nur an Dateien und nur, solange im Monat keine gesendet ist; „Zurücknehmen“ nur für den Admin;
                   „gesendet“ vermerken ist abschließend (Regel 29)
"""

import json
import re

import pytest
from sqlalchemy import select

from app.lohndatei import VersandAbgelehnt, versendet_setzen
from app.models import AuditLog, Lohndatei
from app.routers import time_backoffice as backoffice_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v727_lohndatei_versand_spalten import JAN, datei

URL = "/api/time-backoffice/lohndateien"


@pytest.fixture
def w(threaded_db_session, router_test_client):
    db = threaded_db_session
    return {"db": db, "client": lambda rolle="buero_finanzen", user_id=7, name="Fin Finanzen": router_test_client(
        db, backoffice_router.router, role=rolle, user_id=user_id, display_name=name)}


def _historie(db, row_id):
    return [(a.action, a.old_value, a.new_value, a.actor_name) for a in db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "Lohndatei", AuditLog.entity_id == str(row_id)).order_by(AuditLog.id))]


def test_setzen_mit_zeitpunkt_und_konto(w):
    db, a = w["db"], datei(w["db"])
    r = w["client"]().post(f"{URL}/{a.id}/versendet")
    assert r.status_code == 200, r.text
    f = r.json()
    db.expire_all()
    row = db.get(Lohndatei, a.id)
    assert (f["versendet_von_name"], row.versendet_von_user_id, row.versendet_von_name) == ("Fin Finanzen", 7, "Fin Finanzen")
    assert row.versendet_am is not None and f["versendet_am"].startswith(row.versendet_am.isoformat()[:16])
    assert row.inhalt == a.inhalt and row.art == "datei"  # sonst nichts geändert
    [(aktion, alt, neu, wer)] = _historie(db, a.id)
    assert (aktion, alt, wer) == ("Lohndatei an das Steuerbüro gesendet", "nein", "Fin Finanzen") and neu.endswith(" von Fin Finanzen")


def test_je_monat_eine_nur_dateien(w):
    db = w["db"]
    a, b, c = datei(db), datei(db), datei(db, monat=JAN)
    g = datei(db, art="abgleich", notiz="Telefonat 05.02.")
    k = w["client"]()
    assert k.post(f"{URL}/{a.id}/versendet").status_code == 200
    zweite = k.post(f"{URL}/{b.id}/versendet")
    assert zweite.status_code == 409 and "Für 12/2026 ist schon die Datei vom" in zweite.json()["detail"] and "je Monat eine" in zweite.json()["detail"]
    nochmal = k.post(f"{URL}/{a.id}/versendet")
    assert nochmal.status_code == 409 and nochmal.json()["detail"].startswith("Diese Datei ist schon als gesendet vermerkt")
    assert k.post(f"{URL}/{c.id}/versendet").status_code == 200  # ein anderer Monat
    abgleich = k.post(f"{URL}/{g.id}/versendet")
    assert abgleich.status_code == 409 and abgleich.json()["detail"] == "Ein Abgleich geht nicht an das Steuerbüro – nur eine erzeugte Datei."
    assert k.post(f"{URL}/999999/versendet").status_code == 404
    db.expire_all()
    assert [r.id for r in db.scalars(select(Lohndatei).where(Lohndatei.versendet_am.is_not(None)).order_by(Lohndatei.id))] == [a.id, c.id]
    assert _historie(db, b.id) == [] and _historie(db, g.id) == []  # abgelehnt: kein Eintrag


def test_zwei_zugleich_dieselbe_meldung(db_session, monkeypatch):
    """Zwei klicken zugleich auf zwei Dateien desselben Monats: beide sehen „keine andere“ -- der eindeutige Index lehnt die zweite ab, mit Meldung statt 500."""
    db = db_session
    a, b = datei(db), datei(db)
    versendet_setzen(db, a.id, user_id=1, user_name="Erste")
    monkeypatch.setattr(db, "scalar", lambda *x, **k: None)  # die Abfrage nach einer anderen findet (noch) nichts
    with pytest.raises(VersandAbgelehnt, match="ist schon eine Datei als gesendet vermerkt – je Monat eine"):
        versendet_setzen(db, b.id, user_id=2, user_name="Zweite")
    db.expire_all()
    assert db.get(Lohndatei, b.id).versendet_am is None and _historie(db, b.id) == []


def test_rechte(w):
    a = datei(w["db"])
    for rolle in ("buero_auftrag", "field"):
        assert w["client"](rolle).post(f"{URL}/{a.id}/versendet").status_code == 403
    assert w["client"]("admin", 1, "Ada Admin").post(f"{URL}/{a.id}/versendet").status_code == 200


def test_zuruecknehmen_nur_der_admin(w):
    db, a = w["db"], datei(w["db"])
    assert w["client"]().post(f"{URL}/{a.id}/versendet").status_code == 200
    for rolle in ("buero_finanzen", "buero_auftrag"):
        assert w["client"](rolle).delete(f"{URL}/{a.id}/versendet").status_code == 403
    admin = w["client"]("admin", 1, "Ada Admin")
    r = admin.delete(f"{URL}/{a.id}/versendet")
    assert r.status_code == 200 and (r.json()["versendet_am"], r.json()["versendet_von_name"]) == (None, None)
    db.expire_all()
    row = db.get(Lohndatei, a.id)
    assert (row.versendet_am, row.versendet_von_user_id, row.versendet_von_name) == (None, None, None)
    [setzen, zurueck] = _historie(db, a.id)
    assert (zurueck[0], zurueck[2], zurueck[3]) == ("Vermerk „gesendet“ zurückgenommen", "nein", "Ada Admin") and zurueck[1] == setzen[2]
    assert admin.delete(f"{URL}/{a.id}/versendet").status_code == 409  # nicht (mehr) vermerkt
    b = datei(db)
    assert w["client"]().post(f"{URL}/{b.id}/versendet").status_code == 200  # danach geht eine andere Datei des Monats


# --- Seite ---

def _text():
    return vj.seitentext("zeiten.html")[0]


def _funktion(text: str, name: str) -> str:
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", text.index(")", i))
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _node(admin: bool, ablauf: str):
    js = ("function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;')}"
          "function berlinZeitpunkt(w){return 'Z['+w+']'}" + f"var RECHTE={{admin:{json.dumps(admin)}}};var LD_ZURUECK=null;\n"
          + "\n".join(_funktion(_text(), f) for f in ("lohndateiVermerk", "lohndateiKnopf"))
          + f"\nconst ergebnis=(()=>{{{ablauf}}})();process.stdout.write(JSON.stringify(ergebnis));")
    return node_ausfuehren(js)


ABLAUF = ("const d={id:1,art:'datei',versendet_am:null},g={id:2,art:'datei',versendet_am:'2027-01-05T09:00:00',versendet_von_name:'Fin <F>'},"
          "a={id:3,art:'abgleich',versendet_am:null};"
          "return [lohndateiVermerk(d),lohndateiVermerk(g),lohndateiVermerk(a),lohndateiKnopf(d,false),lohndateiKnopf(d,true),lohndateiKnopf(g,true),"
          "lohndateiKnopf(a,false),(LD_ZURUECK='2',lohndateiKnopf(g,true))]")


def test_seite_vermerk_und_knopf():
    fin = _node(False, ABLAUF)
    assert fin[0] == "" and fin[2] == ""
    assert fin[1] == '<span class="lohndatei-vermerk" data-gesendet="2">An das Steuerbüro gesendet Z[2027-01-05T09:00:00] · Fin &lt;F></span>'
    assert 'data-aktion="lohndatei-gesendet" data-id="1">An das Steuerbüro gesendet</button>' in fin[3]
    assert fin[4:] == ["", "", "", ""]  # im Monat schon eine gesendet; Büro – Finanzen nimmt nicht zurück (auch nicht mit Rückfrage); ein Abgleich hat keinen Knopf
    admin = _node(True, ABLAUF)
    assert admin[5] == '<button type="button" class="knopf knopf-neutral" data-aktion="lohndatei-fragen" data-id="2">Zurücknehmen</button>'
    assert admin[4] == "" and admin[6] == ""
    # nach „Zurücknehmen“ die Rückfrage auf der Seite (kein Dialog des Browsers, Befund R5): Abbrechen oder Zurücknehmen
    assert admin[7] == ('<span class="rueckfrage">Vermerk „gesendet“ zurücknehmen?</span><button type="button" class="knopf knopf-neutral" data-aktion="lohndatei-nein" '
                        'data-id="2">Abbrechen</button><button type="button" class="knopf knopf-gefahr" data-aktion="lohndatei-zuruecknehmen" data-id="2">Zurücknehmen</button>')


def test_seite_abschliessend_und_verdrahtet():
    text = _text()
    gesendet = _funktion(text, "lohndateiGesendet")
    assert "abschliessen('monat',()=>api('/api/time-backoffice/lohndateien/'+Number(id)+'/versendet',{method:'POST'}),{neuLaden:monatLaden})" in gesendet
    zurueck = _funktion(text, "lohndateiZuruecknehmen")
    assert "confirm(" not in zurueck and "speichern('monat',()=>api('/api/time-backoffice/lohndateien/'+Number(id)+'/versendet',{method:'DELETE'})" in zurueck
    assert "else if(b.dataset.aktion==='lohndatei-fragen'){LD_ZURUECK=b.dataset.id;monatZeichnen(M)}" in text
    assert re.search(r"var gesendet=\(d\.lohndateien\|\|\[\]\)\.some\(function\(f\)\{return !!f\.versendet_am\}\);", text)
    assert "+lohndateiVermerk(f)+" in text and "+lohndateiKnopf(f,gesendet)+" in text
    assert "if(b.dataset.aktion==='lohndatei-gesendet')lohndateiGesendet(b.dataset.id,b);" in text
    assert "else if(b.dataset.aktion==='lohndatei-zuruecknehmen')lohndateiZuruecknehmen(b.dataset.id,b);" in text

