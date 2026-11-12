"""Version 1.9.331 (Lohn L2c-2, Punkt 4): „Prüfen“ nennt je Monat die Zahl der Änderungen nach dem Versand -- ohne Namen, mit Weg zu „Monat & Lohn“.

    je Monat     jeder Monat mit gesendeter Datei der letzten 12 Monate bis heute, nur mit Änderungen: „Dezember 2026: 3 Änderungen nach dem Versand“
                 (nach „Besprochen“: „… seit „Besprochen““); eine Datei mit falscher Prüfsumme steht mit ihrer Meldung da
    Rechte       GET /api/zeiten/pruefen gibt sie nur Admin und Büro – Finanzen (Schlüssel nach_dem_versand, sonst leer)
    Seite        Karte „Nach dem Versand geändert“ (zur Info), je Monat die Zeile und der Weg /zeiten?lohnmonat=JJJJ-MM#monat; „Monat & Lohn“ öffnet diesen Monat
"""

from datetime import date, datetime
from decimal import Decimal

from app.lohndatei import ablegen, berechnen, datei
from app.lohndatei_abgleich import aenderungen_je_monat
from app.models import Lohndatei
from app.routers import zeiten as zeiten_router
from tests import vorlagen_js as vj
from tests.test_v729_nach_dem_versand import DEZ, _buchung, als, w  # noqa: F401 -- w ist die Fixture
from tests.uhr import uhr_festhalten

JAN = date(2027, 1, 5)


def _aendern(db, w, tag=8, stunden=6):
    with als():
        e = _buchung(db, w["ada"], tag)
        e.hours, e.ended_at = Decimal(stunden), datetime(2026, 12, tag, 7 + stunden)
        db.commit()


def test_je_monat_ohne_namen(w):
    db = w["db"]
    assert aenderungen_je_monat(db, JAN) == []  # nichts gesendet
    w["gesendet"]()
    assert aenderungen_je_monat(db, JAN) == []  # gesendet, nichts geändert
    _aendern(db, w)
    assert aenderungen_je_monat(db, JAN) == [{"monat": "2026-12", "titel": "Dezember 2026", "anzahl": 1, "text": "Dezember 2026: 1 Änderung nach dem Versand"}]
    assert "Ada" not in str(aenderungen_je_monat(db, JAN))
    # zwölf Monate bis heute: Dezember 2026 zählt bis November 2027, nicht mehr im Dezember 2027; ein Monat nach heute nie
    assert [x["monat"] for x in aenderungen_je_monat(db, date(2027, 11, 30))] == ["2026-12"]
    assert aenderungen_je_monat(db, date(2027, 12, 1)) == [] and aenderungen_je_monat(db, date(2026, 11, 30)) == []
    # nach „Besprochen“ zählt die Liste ab dort
    ablegen(db, DEZ, datei("1234567", "12345", DEZ, berechnen(db, DEZ)), "abgleich.txt", user_id=7, user_name="Fin", art="abgleich", notiz="Telefonat")
    db.commit()
    assert aenderungen_je_monat(db, JAN) == []
    _aendern(db, w, tag=7, stunden=5)
    assert [x["text"] for x in aenderungen_je_monat(db, JAN)] == ["Dezember 2026: 1 Änderung seit „Besprochen“"]


def test_falsche_pruefsumme(w):
    db = w["db"]
    w["gesendet"]()
    db.execute(Lohndatei.__table__.update().values(sha256="0" * 64))
    db.commit()
    [x] = aenderungen_je_monat(db, JAN)
    assert (x["monat"], x["anzahl"]) == ("2026-12", 0) and x["text"].startswith("Dezember 2026: Die abgelegte Lohndatei passt nicht zu ihrer Prüfsumme")


def test_pruefen_nur_admin_und_finanzen(w, router_test_client):
    db = w["db"]
    w["gesendet"]()
    _aendern(db, w)
    with uhr_festhalten(tag=JAN):
        for rolle, erwartet in (("buero_finanzen", 1), ("admin", 1), ("buero_auftrag", 0)):
            c = router_test_client(db, zeiten_router.router, role=rolle, user_id=7, display_name="X")
            r = c.get("/api/zeiten/pruefen")
            assert r.status_code == 200, r.text
            assert len(r.json()["nach_dem_versand"]) == erwartet, rolle


def test_seite():
    text = vj.seitentext("zeiten.html")[0]
    assert '<section class="karte" id="nachVersandKarte" aria-labelledby="nachVersandPruefenTitel" hidden>' in text
    assert "var nv=d.nach_dem_versand||[],nvSumme=nv.reduce(function(s,x){return s+x.anzahl},0);" in text
    assert "+'</span><a href=\"/zeiten?lohnmonat='+encodeURIComponent(x.monat)+'#monat\">Monat &amp; Lohn</a></li>'" in text
    assert "if(/^\\d{4}-\\d{2}$/.test(q.get('lohnmonat')||''))LOHN_MONAT=q.get('lohnmonat');" in text
