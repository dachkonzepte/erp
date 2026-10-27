"""Version 1.9.96 (Stufe 4, R5b, Punkte 2–4 und 7): die Büroseite „Zeiten“ (app/templates/zeiten.html) -- Prüfen, Buchungen, Buchung ändern
oder neu, Löschen mit Rückfrage. Die Daten kommen aus app/zeiten.py (tests/test_v517_zeiten_server.py), die Seite zeigt sie nur.

    Rollen        /zeiten ab Büro – Auftrag; die Monteurin auf „Meine Zeiten“; „+ Buchung“ nur, wer bucht (darf_zeit_buchen())
    Prüfen        Zeiten von früher mit „Ende um“ und „Ende eintragen“ nur mit darf_schliessen; „Pause passt nicht zum Tag“ mit der Vorschau je
                  Buchung, „So buchen“ nur mit darf_buchen; Anträge, Genehmigen/Ablehnen nur für den Admin
    Buchungen     Spalten wie die Vorlage; laufend „06:45 – läuft“, von früher mit Kennzeichen und „Ende eintragen“; Dauer „Dauer · vom Büro“;
                  abgeschlossener Auftrag gekennzeichnet; „⋮“ mit Ändern und Löschen nur mit darf_aendern
    Dialog        „Von – Bis“ mit Vorschau vom Server oder „Dauer“ (netto) -- der Wechsel zu „Dauer“ leert Von und Bis und sagt es
    Befund R5     Zeitarten-Farben als Tokens (hell und dunkel), keine Emojis und ▶/■, fehlerText(), kein alert()/confirm()
Im Browser: scripts/klicktest_zeiten.py.
"""

import json
import re

import pytest

from app.routers import pages as pages_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren

VORLAGE = "zeiten.html"


def _skript() -> str:
    return vj.eigene_skripte(VORLAGE).text


def _funktion(text: str, name: str) -> str:
    """Eine Funktion samt Rumpf (Klammern gezählt) aus dem Skript der Seite."""
    i = text.index("function " + name + "(")
    tiefe, j = 0, text.index("{", i)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _baustein(name: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


def _node(funktionen: tuple, ablauf: str, vorweg: str = ""):
    text = _skript()
    kopf = re.search(r"var WOCHENTAG=.*?;\n", text)[0] + re.search(r"var PUNKTE='.*?';\n", text)[0]
    js = (_baustein("_zahl.html") + "\n" + _baustein("_auftrag_text.html") + "\n" + kopf + vorweg + "\n"
          + "\n".join(_funktion(text, f) for f in ("esc", "pad2", "teile", "tagKurz", "tagLang", "uhr", "stundenUhr", "minutenUhr", "stunden")
                      + funktionen)
          + f"\nconst ergebnis=(()=>{{{ablauf}}})();process.stdout.write(JSON.stringify(ergebnis));")
    return node_ausfuehren(js)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# --- Rollen ------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rolle, aktion", [("buero_auftrag", False), ("buero_finanzen", True), ("admin", True)])
def test_seite_je_rolle(threaded_db_session, router_test_client, rolle, aktion):
    """Angriff: Büro – Auftrag bekommt kein „+ Buchung“ (Ausblenden statt ausgrauen). Gegenprobe: Büro – Finanzen und Admin."""
    antwort = router_test_client(threaded_db_session, pages_router.router, role=rolle).get("/zeiten")
    assert antwort.status_code == 200, antwort.text
    html = antwort.text
    assert ('id="neueBuchung"' in html) is aktion
    rechte = json.loads(re.search(r"var RECHTE=(\{.*?\});", html)[1])
    assert rechte["zeit_buchen"] is aktion and rechte["admin"] is (rolle == "admin")
    assert '<a href="#pruefen" data-reiter="pruefen" aria-current="page">Prüfen' in html and 'data-reiter="buchungen"' in html


def test_monteurin_auf_meine_zeiten(threaded_db_session, router_test_client):
    antwort = router_test_client(threaded_db_session, pages_router.router, role="field", employee_id=1).get("/zeiten", follow_redirects=False)
    assert (antwort.status_code, antwort.headers["location"]) == (302, "/mobil/zeiten")


# --- Buchungen ---------------------------------------------------------------------------------------------------------------------------

ZEILE = {"id": 7, "work_date": "2026-10-19", "employee_name": "Tom Monteur", "status": "booked", "started_at": "2026-10-19T07:00:00",
         "ended_at": "2026-10-19T16:30:00", "entry_type": "site", "zeitart": "Baustellenzeit", "order_number": "AUF-2026-0102",
         "order_title": "Attika", "auftrag_geschlossen": None, "break_minutes": 45, "hours": 8.75, "laeuft_seit_frueher": False,
         "vom_buero": False, "darf_aendern": True, "darf_schliessen": False}


def _zeile(**anders):
    html = _node(("auftragKurz", "spanneHtml", "buchungHtml"), f"return buchungHtml({json.dumps({**ZEILE, **anders})})")
    return html, [_text(z) for z in re.findall(r"<td[^>]*>(.*?)</td>", html)]


def test_buchung_mit_von_bis_und_menue():
    html, zellen = _zeile()
    assert zellen[:7] == ["Mo 19.10.", "Tom Monteur", "07:00–16:30", "Baustellenzeit", "AUF-2026-0102 · Attika", "0:45", "8,75"]
    assert 'data-art="site"' in html and 'data-aktion="aendern" data-id="7"' in html and 'data-aktion="loeschen" data-id="7"' in html


def test_buchung_ohne_recht_ohne_menue():
    """Angriff: ohne darf_aendern kein „⋮“ (Büro – Auftrag, abgeschlossener Zeitraum). Gegenprobe oben: mit „⋮“."""
    html, zellen = _zeile(darf_aendern=False)
    assert "ds-menue" not in html and "data-aktion" not in html and zellen[7] == ""


def test_laufende_zeit_von_frueher_mit_weg_zu_ende_eintragen():
    """Laufend „06:45 – läuft“ mit Kennzeichen „von früher“, Pause und Stunden „—“, statt „⋮“ der Weg zu „Ende eintragen“; heute laufend
    ohne Kennzeichen und ohne Weg."""
    html, zellen = _zeile(status="running", started_at="2026-10-19T06:45:00", ended_at=None, hours=0, laeuft_seit_frueher=True,
                          darf_schliessen=True)
    assert zellen[2] == "06:45 – läuft von früher" and zellen[5:7] == ["—", "—"]
    assert 'class="chip chip-signal">von früher<' in html and 'data-aktion="zu-ende" data-id="7"' in html and "ds-menue" not in html
    html, zellen = _zeile(status="running", started_at="2026-10-26T06:45:00", ended_at=None, hours=0, darf_schliessen=False)
    assert zellen[2] == "06:45 – läuft" and "data-aktion" not in html


def test_dauer_und_abgeschlossener_auftrag():
    html, zellen = _zeile(started_at=None, ended_at=None, vom_buero=True, auftrag_geschlossen="abgeschlossen", hours=6, break_minutes=30)
    assert zellen[2] == "Dauer · vom Büro" and zellen[4] == "AUF-2026-0102 · Attika abgeschlossen" and zellen[6] == "6,00"
    assert 'class="chip chip-neutral"' in html
    assert _zeile(started_at=None, ended_at=None)[1][2] == "Dauer"


def test_werte_in_esc():
    html, _ = _zeile(employee_name='<img src=x onerror=alert(1)>', order_title='"><b>')
    assert "<img" not in html and "<b>" not in html


# --- Prüfen ------------------------------------------------------------------------------------------------------------------------------

PAUSE = {"employee_id": 3, "name": "Mia Monteurin", "tag": "2026-10-10", "abgezogen": 15, "nach_zeitregel": 0, "darf_buchen": True,
         "buchungen": [{"id": 9, "zeitart": "Baustellenzeit", "von": "2026-10-10T13:00:00", "bis": "2026-10-10T16:00:00", "pause_alt": 15,
                        "pause_neu": 0, "gebucht_alt": 2.75, "gebucht_neu": 3.0}]}


def test_pause_passt_nicht_mit_vorschau_und_so_buchen():
    html = _node(("pauseHtml",), f"return pauseHtml({json.dumps(PAUSE)},0)", vorweg="var ZU={};")
    assert "Mia Monteurin · Sa 10.10." in _text(html) and "Pause abgezogen 0:15 h · nach Zeitregel 0:00 h" in _text(html)
    assert "Neu rechnen: Baustellenzeit 13:00–16:00 · Pause 0:15 → 0:00 h · gebucht 2,75 → 3,00 h" in _text(html)
    assert 'data-aktion="pause-buchen" data-i="0">So buchen<' in html and 'data-aktion="pause-zu"' in html
    ohne = _node(("pauseHtml",), f"return pauseHtml({json.dumps({**PAUSE, 'darf_buchen': False})},0)", vorweg="var ZU={};")
    assert "Neu rechnen: Baustellenzeit" in _text(ohne) and "data-aktion" not in ohne


OFFEN = {"id": 5, "employee_id": 2, "name": "Tom Monteur", "seit": "2026-10-19T06:45:00", "tag": "2026-10-19", "zeitart": "Baustellenzeit",
         "order_number": "AUF-2026-0001", "title": "Halle Nord", "auftrag_geschlossen": None, "gruppe": False, "darf_schliessen": True}


def test_zeit_von_frueher_mit_ende_um():
    html = _node(("auftragKurz", "offenHtml"), f"return offenHtml({json.dumps(OFFEN)})")
    assert "Tom Monteur Baustellenzeit seit Mo 19.10., 06:45 · AUF-2026-0001 · Halle Nord" in _text(html)
    assert 'type="time" id="ende-5" data-ende="5"' in html and 'data-aktion="ende" data-id="5" disabled>Ende eintragen<' in html
    ohne = _node(("auftragKurz", "offenHtml"), f"return offenHtml({json.dumps({**OFFEN, 'darf_schliessen': False})})")
    assert "Ende um" not in ohne and "data-aktion" not in ohne


def test_antraege_entscheidet_nur_der_admin():
    antrag = {"id": 4, "employee_name": "Tom Monteur", "absence_type": "Urlaub", "absence_category": "urlaub", "start_date": "2026-11-02",
              "end_date": "2026-11-06", "arbeitstage": 5, "created_at": "2026-10-20T08:00:00", "notes": None}
    vorweg = ("var KATEGORIE={urlaub:'Urlaub'};function berlinZeitpunkt(w,a){return '20.10.2026'};var P={rechte:{antraege_entscheiden:%s}};"
              "var RECHTE={admin:%s};")
    admin = _node(("beantragtText", "antragHtml"), f"return antragHtml({json.dumps(antrag)})", vorweg=vorweg % ("true", "true"))
    assert "Tom Monteur · Urlaub Mo 02.11.–Fr 06.11.2026 · 5 Arbeitstage · beantragt am 20.10." in _text(admin)
    assert 'data-entscheidung="approved"' in admin and 'data-entscheidung="rejected"' in admin
    buero = _node(("beantragtText", "antragHtml"), f"return antragHtml({json.dumps(antrag)})", vorweg=vorweg % ("false", "false"))
    assert "data-aktion" not in buero


# --- Dialog und Befund -------------------------------------------------------------------------------------------------------------------

def test_wechsel_zu_dauer_leert_von_bis_und_sagt_es():
    text = _skript()
    modus = _funktion(text, "modusSetzen")
    assert "el('bdDauerHinweis').hidden=!dauer;" in modus and "if(dauer){el('bdVon').value='';el('bdBis').value=''}" in modus
    html = (vj.TEMPLATES / VORLAGE).read_text(encoding="utf-8")
    assert "Mit „Dauer“ entfallen Von und Bis – gespeichert wird nur die Dauer (netto), ohne Pausenregel." in html
    speichern = _funktion(text, "buchungSpeichern")
    # „Dauer“ schickt Stunden und Pause, nie Von/Bis -- der Server leert dann Beginn und Ende (seit 1.9.90, _als_dauer())
    assert "body=Object.assign(felder,{hours:h,break_minutes:p});" in speichern
    assert "knopf.textContent=stunden(v.gebucht)+' speichern';" in _funktion(text, "vorschauZeigen")


def test_befund_r5_farben_symbole_meldungen():
    html = (vj.TEMPLATES / VORLAGE).read_text(encoding="utf-8")
    for art, token in (("site", "baustelle"), ("travel", "fahrt"), ("workshop", "werkstatt")):
        assert f'.zeitart-punkt[data-art="{art}"]{{background:var(--ds-zeitart-{token})}}' in html
    assert "background:var(--ds-zeitart-sonstige)" in html
    ds = (vj.TEMPLATES.parent / "static" / "ds" / "ds.css").read_text(encoding="utf-8")
    hell, dunkel = ds.split(':root[data-theme="dark"]', 1)
    for token in ("baustelle", "fahrt", "werkstatt", "sonstige"):
        assert f"--ds-zeitart-{token}:" in hell and f"--ds-zeitart-{token}:" in dunkel
    assert not re.search("[\U0001F300-\U0001FAFF▶■]", html)
    assert "alert(" not in html and "confirm(" not in html and "prompt(" not in html
    assert "fehlerText(body,r.status,FELDER)" in _skript()


# --- seit 1.9.102 (R5b Nachrunde, Punkt 4): „Prüfen“ für Büro – Auftrag ------------------------------------------------------------------

def test_karte_zeiten_von_frueher_wartet_nur_auf_wer_das_ende_eintraegt():
    """Darf das Konto an einer Zeit das Ende eintragen: Signalkarte „Wartet auf dich“ mit dem Satz zum Klick. Sonst (Büro – Auftrag) ruhige
    Karte „Zur Info“ ohne Punkt und „Das Ende trägt der Admin oder Büro – Finanzen ein.“ (bis 1.9.101 immer „Wartet auf dich“)."""
    wartet = _node(("offenArt",), f"return offenArt([{json.dumps({**OFFEN, 'darf_schliessen': False})},{json.dumps(OFFEN)}])")
    assert (wartet["karte"], wartet["eb"], wartet["punkt"], wartet["text"]) == ("karte-signal", "eb-signal", True, "Wartet auf dich")
    assert wartet["fuss"].startswith("Gebucht wird erst mit deinem Klick")
    info = _node(("offenArt",), f"return offenArt([{json.dumps({**OFFEN, 'darf_schliessen': False})}])")
    assert info == {"karte": "karte", "eb": "eb", "punkt": False, "text": "Zur Info", "fuss": "Das Ende trägt der Admin oder Büro – Finanzen ein."}
    rumpf = _funktion(_skript(), "pruefenZeichnen")
    assert "var art=offenArt(d.offene_zeiten);" in rumpf and "el('offenKarte').className=art.karte" in rumpf
