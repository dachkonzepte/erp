"""Version 1.10.1 (Stufe W1a): Eingang der Anfragen der Webseite -- Router (app/routers/webanfragen.py) und Seiten (webanfragen.html,
webanfrage.html), nur Musterdaten.

    Rollen      Büro ab buero_auftrag (wie die Anfragen), Monteurin 403 an jedem Weg
    Liste       die neuesten zuerst (ohne Eingang am Ende), nur die geprüften Auszüge -- nie der Umschlag
    Anfrage     der Umschlag unverändert, die Dateien als Liste
    Dateien     nur eine Datei DIESER Anfrage (Regel 25), nur über datei_antwort() (Typ am Inhalt, nosniff); fehlt sie: 404
    Knopf       „Jetzt abholen“ holt höchstens KNOPF_HOECHSTENS mit Frist, Antwort mit Ergebnis und Stand -- ohne Schlüssel
    Seiten      jeder Wert aus dem Umschlag, auch ein Schlüssel, geht nur über esc() ins HTML; Links nur mit festem Anfang
"""

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app import webanfragen as W
from app.models import WebAnfrage, WebAnfrageDatei
from app.routers import webanfragen as router_modul
from app.webanfrage_angaben import abschnitte, nachricht_wiederholt
from scripts.empfangsdienst_attrappe import Attrappe, jpeg_bytes, muster
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

R1, R2 = "R-20261119-0910-0A1B", "R-20261119-0911-0C2D"
K1 = "K-20261119-0912-0E3F"


def _zeile(db, nummer, eingang, **mehr):
    umschlag = json.dumps(muster(nummer)["umschlag"], ensure_ascii=False)
    z = WebAnfrage(nummer=nummer, fassung="dk-anfrage/1", eingang_am=eingang, umschlag=umschlag, umschlag_sha256="0" * 64, status="neu",
                   kontakt_name="Max Muster", **mehr)
    db.add(z)
    db.commit()
    return z


@pytest.fixture
def welt(threaded_db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    db = threaded_db_session
    alt = _zeile(db, R1, datetime(2026, 11, 18, 8, 0))
    neu = _zeile(db, R2, datetime(2026, 11, 19, 8, 0), spamverdacht=True)
    ohne = _zeile(db, "X-20261119-0912-0E3F", None, pruefen_grund=W.P_EINGANG)
    bild = jpeg_bytes()
    datei = WebAnfrageDatei(webanfrage_id=alt.id, name="foto-1.jpg", typ="image/jpeg", groesse=len(bild), sha256="0" * 64,
                            gespeichert_als="a" * 32 + ".jpg")
    db.add(datei)
    db.commit()
    W.datei_pfad(datei).write_bytes(bild)
    return {"db": db, "alt": alt.id, "neu": neu.id, "ohne": ohne.id, "datei": datei.id, "bild": bild}


def _client(router_test_client, welt, rolle="buero_auftrag"):
    return router_test_client(welt["db"], router_modul.router, role=rolle)


def test_monteurin_nirgends(welt, router_test_client):
    c = _client(router_test_client, welt, "field")
    for pfad in ["/api/webanfragen", "/api/webanfragen/stand", f"/api/webanfragen/{welt['alt']}",
                 f"/api/webanfragen/{welt['alt']}/dateien/{welt['datei']}"]:
        assert c.get(pfad).status_code == 403, pfad
    assert c.post("/api/webanfragen/abholen").status_code == 403


def test_liste_neueste_zuerst_ohne_umschlag(welt, router_test_client):
    antwort = _client(router_test_client, welt).get("/api/webanfragen")
    assert antwort.status_code == 200
    liste = antwort.json()
    assert [z["id"] for z in liste] == [welt["neu"], welt["alt"], welt["ohne"]]  # ohne Eingang am Ende
    assert all("umschlag" not in z for z in liste) and liste[0]["spamverdacht"] is True and liste[1]["dateien"] == 1
    assert liste[2]["pruefen_grund"] == W.P_EINGANG


def test_eine_anfrage_mit_umschlag_und_dateien(welt, router_test_client):
    d = _client(router_test_client, welt).get(f"/api/webanfragen/{welt['alt']}").json()
    assert d["umschlag"]["nr"] == R1 and d["umschlag"]["kontakt"]["name"] == "Max Muster"
    assert d["dateiliste"] == [{"id": welt["datei"], "name": "foto-1.jpg", "typ": "image/jpeg", "groesse": len(welt["bild"])}]
    assert _client(router_test_client, welt).get("/api/webanfragen/999999").status_code == 404


def test_datei_nur_dieser_anfrage(welt, router_test_client):
    c = _client(router_test_client, welt)
    r = c.get(f"/api/webanfragen/{welt['alt']}/dateien/{welt['datei']}")
    assert r.status_code == 200 and r.content == welt["bild"]
    assert r.headers["content-type"] == "image/jpeg" and r.headers["x-content-type-options"] == "nosniff"
    assert c.get(f"/api/webanfragen/{welt['neu']}/dateien/{welt['datei']}").status_code == 404  # fremde Anfrage: wie unbekannt
    assert c.get(f"/api/webanfragen/{welt['alt']}/dateien/999999").status_code == 404


def test_datei_fehlt_oder_name_manipuliert(welt, router_test_client, tmp_path):
    db = welt["db"]
    datei = db.get(WebAnfrageDatei, welt["datei"])
    W.datei_pfad(datei).unlink()
    c = _client(router_test_client, welt)
    assert c.get(f"/api/webanfragen/{welt['alt']}/dateien/{welt['datei']}").status_code == 404
    (tmp_path / "geheim.jpg").write_bytes(welt["bild"])  # liegt neben der Ablage -- ein Ablagename mit ../ fände sie
    datei.gespeichert_als = "../geheim.jpg"
    db.commit()
    assert c.get(f"/api/webanfragen/{welt['alt']}/dateien/{welt['datei']}").status_code == 404


def test_weg_ueber_anfragen_und_seiten(welt, router_test_client):
    from app.routers import pages
    c = router_test_client(welt["db"], pages.router, role="buero_auftrag")
    assert 'href="/anfragen/webseite"' in c.get("/inquiries").text
    assert c.get("/anfragen/webseite").status_code == 200 and c.get(f"/anfragen/webseite/{welt['alt']}").status_code == 200
    gesperrt = router_test_client(welt["db"], pages.router, role="field").get("/anfragen/webseite")
    assert "eingangTabelle" not in gesperrt.text and "standKarte" not in gesperrt.text


def test_knopf_ruft_mit_seinen_grenzen(welt, router_test_client, monkeypatch):
    aufrufe = []

    def abholen(db, **kw):
        aufrufe.append(kw)
        return W.Ergebnis()

    monkeypatch.setattr(router_modul, "abholen", abholen)
    assert _client(router_test_client, welt).post("/api/webanfragen/abholen").status_code == 200
    assert aufrufe == [{"hoechstens": 20, "frist_sekunden": 40}] == [{"hoechstens": W.KNOPF_HOECHSTENS, "frist_sekunden": W.KNOPF_FRIST}]


def test_stand_ohne_schluessel(welt, router_test_client, monkeypatch):
    monkeypatch.delenv(W.SCHLUESSEL_VARIABLE, raising=False)
    s = _client(router_test_client, welt).get("/api/webanfragen/stand").json()
    assert s["eingerichtet"] is False and s["neu"] == 3 and s["spamverdacht"] == 1 and s["pruefen"] == 1


def test_knopf_holt_mit_grenze_und_ohne_schluessel_in_der_antwort(welt, router_test_client, monkeypatch):
    monkeypatch.setattr(W, "KNOPF_HOECHSTENS", 2)
    monkeypatch.setattr(router_modul, "KNOPF_HOECHSTENS", 2)
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        for i in range(3):
            a.dazu(muster(f"R-20261119-10{i:02d}-0B0{i}"))
        r = _client(router_test_client, welt).post("/api/webanfragen/abholen")
        assert r.status_code == 200, r.text
        e = r.json()
        assert (e["neu"], e["weitere"], e["fehler"], e["stand"]["neu"]) == (2, True, None, 5)
        assert a.schluessel not in r.text
    assert len(welt["db"].scalars(select(WebAnfrage)).all()) == 5


# --- Seiten in node ----------------------------------------------------------------------------------------------------------------------

BOESE = '<img src=x onerror="window.__boese=1">'


def _detail(umschlag: dict, **mehr) -> dict:
    """Die Antwort von GET /api/webanfragen/{id}; Abschnitte und „wiederholt“ seit 1.10.3 aus denselben Funktionen wie der Server."""
    art = mehr.get("art", "reparatur")
    return {"id": 7, "nummer": R1, "art": "reparatur", "art_name": "Reparatur-Anfrage", "fassung": "dk-anfrage/1", "eingang_am": "2026-11-19T08:10:00",
            "betreff": None, "kontakt_name": None, "spamverdacht": False, "pruefen_grund": None, "status": "neu", "abgeholt_am": "2026-11-19T08:11:00",
            "gemeldet_am": None, "dateien": 0, "umschlag": umschlag, "dateiliste": [],
            "abschnitte": abschnitte(art, umschlag), "nachricht_wiederholt": nachricht_wiederholt(art, umschlag), **mehr}


def _lauf_detail(d: dict) -> dict:
    ablauf = (f"zeichnen({json.dumps(d)});"
              "return Object.fromEntries(['hinweise','kontakt','anfrage','angaben','dateien','herkunft'].map(i => [i, _element(i).innerHTML]));")
    return im_browser(seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM, ablauf)["ergebnis"]


@nur_mit_node
def test_detail_setzt_jeden_wert_ueber_esc():
    a = muster(R1, name=BOESE)["umschlag"]
    a["betreff"] = BOESE
    a["text"] = BOESE
    a["kontakt"]["email"] = f'x@y.z" onclick="{BOESE}'
    a["kontakt"]["telefon"] = f'0000"{BOESE}'
    a["daten"]["anfrage"]["beschreibung"] = BOESE
    a["daten"][BOESE] = {BOESE: [BOESE]}  # auch ein Schlüssel aus dem Umschlag
    html = "".join(_lauf_detail(_detail(a, pruefen_grund=BOESE)).values())
    assert "<img" not in html and "&lt;img src=x onerror=" in html
    import re
    links = re.findall(r'href="tel:([^"]*)"', html)
    assert "00001" in links and all(re.fullmatch(r"[0-9+]*", x) for x in links)  # nur Ziffern und + im Link
    assert 'onclick="' not in html
    assert re.findall(r'href="mailto:([^"]*)"', html) == ["muster@example.invalid"]  # die ungültige Adresse des Kontakts ohne Link


@nur_mit_node
def test_liste_ohne_schluessel_mit_hinweis():
    stand = {"eingerichtet": False, "laeuft": False, "letzter_lauf_am": None, "letzter_erfolg_am": None, "letzter_fehler": "Schnittstelle nicht eingerichtet",
             "letzte_neu": 0, "nicht_abgeholt": [], "neu": 0, "spamverdacht": 0, "pruefen": 0}
    ablauf = f"stand = {json.dumps(stand)}; liste = []; standZeichnen(); listeZeichnen(); return [_element('standText').innerHTML, _element('standHinweis').innerHTML, _element('listeRahmen').innerHTML];"
    text, hinweis, liste = im_browser(seite("webanfragen.html", "\nladen().catch("), ablauf)["ergebnis"]
    assert "noch nie" in text and "Noch keine Anfragen der Webseite im Eingang." in liste
    assert hinweis == ('<div class="hinweis">Die Schnittstelle zum Empfangsdienst ist auf diesem Server noch nicht eingerichtet – ein Administrator '
                       'trägt den Schlüssel ein.</div>')


@nur_mit_node
def test_detail_allgemeine_angaben_und_dateien():
    a = muster(R1, "kantservice")["umschlag"]
    a["daten"] = {"version": 1, "ergebnis": {"netto": 1234.5}, BOESE: BOESE}
    d = _detail(a, art="dach", dateiliste=[{"id": 3, "name": "anfrage.pdf", "typ": "application/pdf", "groesse": 2048},
                                           {"id": 4, "name": "foto-1.jpg", "typ": "image/jpeg", "groesse": 4096}])
    erg = _lauf_detail(d)
    assert "Preise und Förderung hat der Konfigurator" in erg["angaben"] and "1234,5" in erg["angaben"]
    # seit 1.10.3: Positionen und Aufmaß gehören nur zum Kantservice -- bei einer Dach-Anfrage nicht (Fund aus echten Anfragen)
    assert "traufblech" not in erg["angaben"] and "Aufmaß vor Ort gewünscht" not in erg["angaben"]
    assert 'href="/api/webanfragen/1/dateien/3"' in erg["dateien"] and 'src="/api/webanfragen/1/dateien/4"' in erg["dateien"]
    assert "<img src=x" not in erg["angaben"]
    k = muster(K1, "kantservice", aufmass=True)["umschlag"]
    erg = _lauf_detail(_detail(k, art="kantservice"))
    assert "traufblech" in erg["angaben"] and "Aufmaß vor Ort gewünscht</dt><dd>ja" in erg["angaben"]


@nur_mit_node
def test_liste_setzt_jeden_wert_ueber_esc():
    zeile = {"id": 5, "nummer": R1, "art": "reparatur", "art_name": BOESE, "fassung": "dk-anfrage/1", "eingang_am": "2026-11-19T08:10:00",
             "betreff": BOESE, "kontakt_name": BOESE, "spamverdacht": True, "pruefen_grund": BOESE, "status": "neu",
             "abgeholt_am": "2026-11-19T08:11:00", "gemeldet_am": None, "dateien": 2}
    stand = {"eingerichtet": True, "laeuft": False, "letzter_lauf_am": "2026-11-19T08:11:00", "letzter_erfolg_am": "2026-11-19T08:11:00",
             "letzter_fehler": None, "letzte_neu": 1, "nicht_abgeholt": [{"nummer": R2, "grund": BOESE}], "neu": 1, "spamverdacht": 1, "pruefen": 1}
    ablauf = (f"stand = {json.dumps(stand)}; liste = [{json.dumps(zeile)}]; standZeichnen(); listeZeichnen();"
              "return [_element('standText').innerHTML, _element('standHinweis').innerHTML, _element('listeRahmen').innerHTML];")
    text, hinweis, tabelle = im_browser(seite("webanfragen.html", "\nladen().catch(") + WIRKSAM, ablauf)["ergebnis"]
    assert "<img" not in text + hinweis + tabelle and "&lt;img" in tabelle and "&lt;img" in hinweis
    assert 'href="/anfragen/webseite/5"' in tabelle and "Spamverdacht" in tabelle and "noch nicht gemeldet" in tabelle
    assert "19.11.2026 09:10" in tabelle  # Eingang in Berliner Zeit


@nur_mit_node
def test_ergebnis_des_knopfs_in_worten():
    ablauf = ("return [ergebnisText({neu: 1, pruefen: 0, nicht_abgeholt: [], weitere: false, fehler: null, laeuft_schon: false}),"
              " ergebnisText({neu: 3, pruefen: 1, nicht_abgeholt: [{}], weitere: true, fehler: null, laeuft_schon: false}),"
              " ergebnisText({neu: 0, pruefen: 0, nicht_abgeholt: [], weitere: false, fehler: 'Empfangsdienst nicht erreichbar', laeuft_schon: false}),"
              " ergebnisText({laeuft_schon: true})];")
    assert im_browser(seite("webanfragen.html", "\nladen().catch("), ablauf)["ergebnis"] == [
        "1 Anfrage neu abgeholt.", "3 Anfragen neu abgeholt, davon 1 zu prüfen; 1 nicht abgeholt (siehe oben) – weitere holt der nächste Lauf.",
        "Empfangsdienst nicht erreichbar", "Gerade holt schon ein anderer Lauf ab – die Liste zeigt gleich, was er bringt."]
