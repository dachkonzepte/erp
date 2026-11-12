"""Version 1.9.330 (Lohn L2c-2, Punkt 3): „Besprochen“ legt die Rechnung von heute als Abgleich-Zeile ab.

    ablegen      POST /api/time-backoffice/lohndateien/abgleich {monat, notiz} -- Admin und Büro – Finanzen; art „abgleich“ mit Notiz, die Bytes der Rechnung
                 von heute; danach vergleicht die Liste gegen sie: leer („Keine Änderung seit „Besprochen““), bis sich wieder etwas ändert
    Notiz        Pflicht (leer oder nur Leerzeichen 422), höchstens 500 Zeichen (422)
    nur, wenn    eine Datei gesendet ist (sonst 409 „Noch nichts versendet …“) und sich seitdem etwas geändert hat (sonst 409 „nichts zu besprechen“)
    Prüfungen    dieselben wie beim Erzeugen (Entscheidung 12.11.2026): fehlt etwas, 409 mit Liste, nichts abgelegt
    Seite        „Besprochen“ mit sichtbarem Notizfeld nur bei Änderungen, abschließend (Regel 29); in der Ablage „Besprochen … – „Notiz““ ohne Knopf
"""

from datetime import date

from sqlalchemy import select

from app.lohndatei_abgleich import KEIN_VERSAND, NICHTS_ZU_BESPRECHEN, nach_dem_versand
from app.models import Lohndatei, TimeTrackingSettings
from app.routers import time_backoffice as backoffice_router
from tests import vorlagen_js as vj
from tests.test_v729_nach_dem_versand import DEZ, _buchung, _funktion, als, w  # noqa: F401 -- w ist die Fixture

URL = "/api/time-backoffice/lohndateien/abgleich"


def _backoffice(router_test_client, w, rolle="buero_finanzen"):
    return router_test_client(w["db"], backoffice_router.router, role=rolle, user_id=7, display_name="Fin Finanzen")


def _aendern(db, w, tag=8, stunden=6):
    from datetime import datetime
    from decimal import Decimal
    with als():
        e = _buchung(db, w["ada"], tag)
        e.hours, e.ended_at = Decimal(stunden), datetime(2026, 12, tag, 7 + stunden)
        db.commit()


def test_besprochen_legt_ab_danach_leer_bis_zur_naechsten_aenderung(w, router_test_client):
    db = w["db"]
    gesendet = w["gesendet"]()
    _aendern(db, w)
    r = _backoffice(router_test_client, w).post(URL, json={"monat": "2026-12", "notiz": "  Telefonat 05.02.  "})
    assert r.status_code == 201, r.text
    f = r.json()
    assert (f["art"], f["notiz"], f["versendet_am"], f["erzeugt_von_name"], f["dateiname"]) == (
        "abgleich", "Telefonat 05.02.", None, "Fin Finanzen", "DATEV_Lohndaten_2026-12_Abgleich.txt")
    d = nach_dem_versand(db, DEZ)
    assert (d["stand"], d["text"], d["bezug"]["id"], d["bezug"]["gesendet_id"]) == ("gleich", "Keine Änderung seit „Besprochen“.", f["id"], gesendet.id)
    _aendern(db, w, tag=7, stunden=5)
    d = nach_dem_versand(db, DEZ)
    assert (d["stand"], d["text"], [z["tag"] for z in d["zeilen"]]) == ("geaendert", "1 Änderung seit „Besprochen“", [date(2026, 12, 7)])
    assert len(d["zeilen"][0]["gruende"]) == 1  # nur die Änderung nach „Besprochen“
    row = db.get(Lohndatei, f["id"])
    assert b"00094;8;1;1000;6,00;;;;;;" in row.inhalt  # die Rechnung von damals


def test_notiz_pflicht(w, router_test_client):
    w["gesendet"]()
    _aendern(w["db"], w)
    c = _backoffice(router_test_client, w)
    for notiz in ("", "   "):
        r = c.post(URL, json={"monat": "2026-12", "notiz": notiz})
        assert r.status_code == 422 and r.json()["detail"] == "Notiz fehlt – z. B. „Telefonat 05.02.“."
    assert c.post(URL, json={"monat": "2026-12", "notiz": "x" * 501}).status_code == 422
    assert c.post(URL, json={"monat": "2026-12"}).status_code == 422
    assert w["db"].scalar(select(Lohndatei).where(Lohndatei.art == "abgleich")) is None


def test_nur_mit_gesendeter_datei_und_aenderung(w, router_test_client):
    db = w["db"]
    c = _backoffice(router_test_client, w)
    r = c.post(URL, json={"monat": "2026-12", "notiz": "Telefonat"})
    assert r.status_code == 409 and r.json()["detail"] == KEIN_VERSAND
    w["gesendet"]()
    r = c.post(URL, json={"monat": "2026-12", "notiz": "Telefonat"})
    assert r.status_code == 409 and r.json()["detail"] == NICHTS_ZU_BESPRECHEN == "Keine Änderung nach dem Versand – nichts zu besprechen."
    assert db.scalar(select(Lohndatei).where(Lohndatei.art == "abgleich")) is None


def test_dieselben_pruefungen_wie_das_erzeugen(w, router_test_client):
    db = w["db"]
    w["gesendet"]()
    _aendern(db, w)
    db.get(TimeTrackingSettings, 1).datev_mandantennummer = None
    db.commit()
    r = _backoffice(router_test_client, w).post(URL, json={"monat": "2026-12", "notiz": "Telefonat"})
    assert r.status_code == 409 and r.json()["detail"].startswith("Kein DATEV-Export: ") and r.json()["liste"]
    assert db.scalar(select(Lohndatei).where(Lohndatei.art == "abgleich")) is None


def test_rechte(w, router_test_client):
    w["gesendet"]()
    _aendern(w["db"], w)
    for rolle in ("buero_auftrag", "field"):
        assert _backoffice(router_test_client, w, rolle).post(URL, json={"monat": "2026-12", "notiz": "Telefonat"}).status_code == 403
    assert _backoffice(router_test_client, w, "admin").post(URL, json={"monat": "2026-12", "notiz": "Telefonat"}).status_code == 201


def test_seite():
    text = vj.seitentext("zeiten.html")[0]
    zeichnen = _funktion(text, "nachVersandZeichnen")
    assert "el('nvBesprochen').hidden=d.stand!=='geaendert';" in zeichnen
    b = _funktion(text, "nachVersandBesprochen")
    assert "if(!notiz){el('nvFehlt').textContent='Notiz fehlt – z. B. „Telefonat 05.02.“.';el('nvNotiz').focus();return Promise.resolve()}" in b
    assert "abschliessen('monat',()=>api('/api/time-backoffice/lohndateien/abgleich',{method:'POST',headers:{'Content-Type':'application/json'}," in b
    assert "body:JSON.stringify({monat:LOHN_MONAT,notiz:notiz})}),{neuLaden:monatLaden})" in b
    assert '<input type="text" id="nvNotiz" maxlength="500" placeholder="z. B. Telefonat 05.02.">' in text  # sichtbares Feld, kein Popup (Regel 4)
    assert "+(f.art==='abgleich'?'Besprochen ':'Abgelegt ')+" in text and "+(f.art==='abgleich'&&f.notiz?' – „'+esc(f.notiz)+'“':'')+" in text
    assert "el('nvBesprochenKnopf').addEventListener('click',nachVersandBesprochen);" in text
    assert "el('nvNotiz').addEventListener('input',function(){el('nvFehlt').textContent=''});" in text
