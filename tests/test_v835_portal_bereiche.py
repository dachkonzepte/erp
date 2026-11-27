"""Version 1.11.45 (Stufe P2e, Teil 3a): die Bereiche des Kundenportals als fertige Texte -- app/portal/bereiche.py und die Wege POST /api/uebersicht,
/api/unterlagen, /api/rechnungen, /api/termine (Entwürfe P2, Seiten 1–5).

    Ohne Datenbank  Beträge, Daten, Stand in Berlin (auch über Mitternacht), Tage; Gruppe wie im ERP (dieselbe Regel, Wächter); Unterlagen ohne Rechnungen,
                    Mahnungen und Fotos, „Allgemeine Unterlagen“ am Ende; Zustand je Rechnung mit Kennzeichen und Hinweis (fällig am / seit), Mahnung unter
                    ihrer Rechnung; offen insgesamt; Termine kommend, heute, vergangen; Übersicht
    PostgreSQL      die Wege gegen den echten Dienst unter der Testrolle: Antworten mit genau den Feldern, je Aufruf ein Eintrag im Protokoll, ohne Sitzung
                    401, Bremse 429, ein GET gibt es nicht
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app import portal_freigaben as pf
from app.portal import bereiche, routen

D = Decimal


# --- ohne Datenbank ------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("betrag, text", [(2380, "2.380,00 €"), (D("-380.8"), "-380,80 €"), (D("1234567.505"), "1.234.567,51 €"), (0, "0,00 €"),
                                          (D("999.995"), "1.000,00 €")])
def test_geld(betrag, text):
    assert bereiche.geld(betrag) == text


def test_stand_in_berlin_heute_anderer_tag_und_alt():
    jetzt = datetime(2026, 11, 27, 8, 0)  # UTC = 9:00 in Berlin
    assert bereiche.stand(datetime(2026, 11, 26, 23, 30), jetzt) == {"text": "heute, 0:30 Uhr", "alt": True}  # in Berlin schon der 27.
    assert bereiche.stand(datetime(2026, 11, 26, 22, 59), jetzt) == {"text": "26.11.2026, 23:59 Uhr", "alt": True}
    assert bereiche.stand(datetime(2026, 11, 27, 7, 30), jetzt) == {"text": "heute, 8:30 Uhr", "alt": False}
    assert bereiche.stand(None, jetzt) == {"text": None, "alt": True}


def test_tage():
    assert bereiche.tage(date(2026, 12, 7), date(2026, 12, 9)) == "Mo 7. – Mi 9. Dezember"
    assert bereiche.tage(date(2026, 12, 11), date(2026, 12, 11)) == "Fr 11. Dezember"
    assert bereiche.tage(date(2026, 11, 30), date(2026, 12, 2)) == "Mo 30. November – Mi 2. Dezember"
    assert bereiche.tage(date(2026, 12, 7), date(2026, 12, 9), kurz=True) == "Mo 7. – Mi 9. Dez."


@pytest.mark.parametrize("auftrag, betreff, objekt", [("A-1", "Dach", "Hafenweg 3"), ("A-1", "  ", "Hafenweg 3"), ("A-1", None, None), (None, None, "Hafenweg 3"),
                                                      (None, "Dach", None), (None, None, None)])
def test_gruppe_wie_im_erp(auftrag, betreff, objekt):
    """Wächter: Portal und Reiter „Im Portal“ gruppieren nach derselben Regel (app/portal_freigaben.py::gruppe_text())."""
    assert bereiche.gruppe(auftrag, betreff, objekt) == pf.gruppe_text(auftrag, betreff, objekt)


def _u(freigabe, art, titel, tag, auftrag=None, betreff=None, objekt=None):
    return {"freigabe": freigabe, "art": art, "titel": titel, "datum": tag, "auftrag": auftrag, "betreff": betreff, "objekt": objekt}


def test_unterlagen_und_fotos_getrennt_allgemein_am_ende():
    zeilen = [_u(1, "dokument", "Förderunterlagen", date(2026, 11, 20)),
              _u(2, "abnahmeprotokoll", "Abnahmeprotokoll", date(2026, 11, 18), "A-1", "Dach", "Musterweg 12"),
              _u(3, "rechnung", "Schlussrechnung R-1", date(2026, 11, 17), "A-1", "Dach", "Musterweg 12"),
              _u(4, "foto", "Foto", date(2026, 11, 16), "A-1", "Dach", "Musterweg 12"),
              _u(5, "mahnung", "1. Mahnung", date(2026, 11, 15), "A-1", "Dach", "Musterweg 12"),
              _u(6, "angebot", "Angebot", date(2026, 9, 21), "A-1", "Dach", "Musterweg 12")]
    d = bereiche.unterlagen(zeilen)
    assert [(g["titel"], g["unter"], g["zahl_text"], [z["freigabe"] for z in g["zeilen"]]) for g in d["unterlagen"]] == [
        ("Auftrag A-1 · Dach", "Musterweg 12", "2 Unterlagen", [2, 6]), ("Allgemeine Unterlagen", "ohne bestimmten Auftrag", "1 Unterlage", [1])]
    assert [z["art_text"] for z in d["unterlagen"][0]["zeilen"]] == ["Protokoll", "Angebot"]
    assert d["fotos"] == [{"titel": "Auftrag A-1 · Dach", "unter": "Musterweg 12", "zahl_text": "1 Foto",
                           "zeilen": [{"freigabe": 4, "titel": "Foto", "datum": "16.11.2026", "bildtext": "Auftrag A-1 · 16.11.2026"}]}]


def _r(freigabe, zustand, *, art="rechnung", offen="0", faellig=date(2026, 12, 4), ueber=False, bezug=None, zu=None, betrag="2380"):
    return {"freigabe": freigabe, "art": art, "titel": "Schlussrechnung" if art == "rechnung" else "Zahlungserinnerung", "nummer": f"R-{freigabe}",
            "datum": date(2026, 11, 20), "faellig": faellig, "betrag": D(betrag) if art == "rechnung" else None, "zustand": zustand, "offen": D(offen),
            "ueberfaellig": ueber, "bezug": bezug, "zu_freigabe": zu, "auftrag": "A-1", "betreff": "Dach", "objekt": "Musterweg 12"}


def test_zustand_je_rechnung_wie_der_entwurf():
    zeilen = [_r(1, "teilweise_bezahlt", offen="2380"), _r(2, "offen", offen="100", ueber=True), _r(3, "bezahlt"), _r(4, "guthaben", offen="120"),
              _r(5, "enthalten", bezug="R-9"), _r(6, "storniert"), _r(7, "storno", bezug="R-6", betrag="-380.8"), _r(8, None),
              _r(9, None, art="mahnung", zu=2), _r(10, None, art="mahnung", zu=99)]
    d = bereiche.rechnungen(zeilen)
    (g,) = d["gruppen"]
    je = {z["freigabe"]: (z["kennzeichen"], z["farbe"], z["hinweis"]) for z in g["zeilen"]}
    assert je == {
        1: ("teilweise bezahlt", "warn", ["noch offen 2.380,00 €", "fällig am 04.12.2026"]),
        2: ("offen", "warn", ["fällig seit 04.12.2026"]),
        3: ("bezahlt", "ok", []), 4: ("Guthaben 120,00 €", "info", []), 5: ("in Schlussrechnung enthalten", "neutral", []),
        6: ("storniert", "neutral", []), 7: ("Storno zu R-6", "neutral", []), 8: (None, None, []),
        10: (None, None, []),  # Mahnung, deren Rechnung nicht sichtbar ist: eigene Zeile
    }
    assert [m["freigabe"] for z in g["zeilen"] for m in z["mahnungen"]] == [9]  # unter Rechnung 2
    assert next(z for z in g["zeilen"] if z["freigabe"] == 7)["betrag"] == "-380,80 €"
    assert (g["zahl_text"], d["offen"], d["alles_bezahlt"]) == ("8 Rechnungen", "2.480,00 €", False)
    alles = bereiche.rechnungen([_r(3, "bezahlt"), _r(4, "guthaben", offen="120")])
    assert (alles["offen"], alles["alles_bezahlt"]) == (None, True)
    assert bereiche.rechnungen([]) == {"gruppen": [], "offen": None, "alles_bezahlt": False}


def test_termine_kommend_heute_vergangen():
    heute = date(2026, 12, 8)
    zeilen = [{"auftrag": "A-1", "betreff": "Dach", "objekt": "Musterweg 12", "von": v, "bis": b}
              for v, b in ((date(2026, 11, 16), date(2026, 11, 20)), (date(2026, 12, 7), date(2026, 12, 9)), (date(2026, 12, 11), date(2026, 12, 11)))]
    d = bereiche.termine(zeilen, heute)
    assert [(g["titel"], g["zeilen"]) for g in d["kommend"]] == [("Auftrag A-1 · Dach", [
        {"wann": "Mo 7. – Mi 9. Dezember", "dauer": "3 Tage", "heute": True}, {"wann": "Fr 11. Dezember", "dauer": "1 Tag", "heute": False}])]
    assert [z["wann"] for g in d["vergangen"] for z in g["zeilen"]] == ["Mo 16. – Fr 20. November"]


def test_uebersicht():
    z = {"offen_anzahl": 1, "offen_summe": D("2380"), "faellig_titel": "Schlussrechnung", "faellig_nummer": "R-2026-0031", "faellig_am": date(2026, 12, 4),
         "einsatz_von": date(2026, 12, 7), "einsatz_bis": date(2026, 12, 9), "einsatz_auftrag": "A-1", "einsatz_betreff": "Steildachsanierung",
         "einsatz_objekt": "Musterweg 12, 52531 Übach-Palenberg", "unterlagen": 10, "unterlage_titel": "Abnahmeprotokoll", "unterlage_datum": date(2026, 11, 18),
         "fotos": 24, "foto_am": date(2026, 11, 18)}
    assert bereiche.uebersicht(z) == {
        "rechnungen": {"offen": 1, "betrag": "2.380,00 €", "faellig": "Schlussrechnung R-2026-0031, fällig am 04.12.2026"},
        "einsatz": {"wann": "Mo 7. – Mi 9. Dez.", "wo": "Steildachsanierung · Musterweg 12, 52531 Übach-Palenberg"},
        "unterlagen": {"zahl": 10, "zuletzt": "Abnahmeprotokoll vom 18.11.2026"}, "fotos": {"zahl": 24, "zuletzt": "18.11.2026"}}
    leer = dict(z, offen_anzahl=0, offen_summe=D("0"), faellig_titel=None, faellig_nummer=None, faellig_am=None, einsatz_von=None, einsatz_bis=None,
                unterlagen=0, unterlage_titel=None, unterlage_datum=None, fotos=0, foto_am=None)
    assert bereiche.uebersicht(leer) == {"rechnungen": {"offen": 0, "betrag": None, "faellig": None}, "einsatz": None,
                                         "unterlagen": {"zahl": 0, "zuletzt": None}, "fotos": {"zahl": 0, "zuletzt": None}}


def test_wege_nur_post_und_in_der_liste_der_sitzung():
    for pfad in ("/api/uebersicht", "/api/unterlagen", "/api/rechnungen", "/api/termine"):
        assert pfad in routen.SITZUNG
        (route,) = [r for r in routen.router.routes if r.path == pfad]
        assert route.methods == {"POST"}, pfad


# --- PostgreSQL: die Wege gegen den echten Dienst ---------------------------------------------------------------------------------------------------------

from tests.test_v825_portal_dateien import _anfrage, _freigabe, _kunde, pg_modul  # noqa: E402,F401  (pg_modul ist eine Fixture)


@pytest.fixture
def p(pg_modul):  # noqa: F811
    pg_modul.w.erp("DELETE FROM portal_bremsen")
    return pg_modul


def _post(p, pfad, keks):
    import json
    r = _anfrage(p.port, "POST", pfad, keks=keks)
    return r.status, (json.loads(r.koerper) if r.koerper else None)


def test_pg_wege_antworten_protokoll_401_und_429(p):
    kunde, keks = _kunde(p)
    fid, _name = _freigabe(p, kunde, titel="Plan Süd")
    vorher = p.w.erp("SELECT count(*) FROM portal_zugriffe")[0][0]
    status, d = _post(p, "/api/unterlagen", keks)
    assert status == 200 and d["unterlagen"][0]["zeilen"][0]["freigabe"] == fid and d["fotos"] == []
    assert d["unterlagen"][0]["titel"] == "Allgemeine Unterlagen" and d["unterlagen"][0]["zeilen"][0]["titel"] == "Plan Süd"
    status, d = _post(p, "/api/rechnungen", keks)
    assert (status, d) == (200, {"stand": {"text": None, "alt": True}, "offen": None, "alles_bezahlt": False, "gruppen": []})
    status, d = _post(p, "/api/termine", keks)
    assert (status, d["kommend"], d["vergangen"]) == (200, [], [])
    status, d = _post(p, "/api/uebersicht", keks)
    assert status == 200 and d["unterlagen"] == {"zahl": 1, "zuletzt": "Plan Süd vom 26.11.2026"} and d["einsatz"] is None
    aktionen = [a for (a,) in p.w.erp("SELECT aktion FROM portal_zugriffe ORDER BY id")[vorher:]]
    assert aktionen == ["unterlagen", "rechnungen", "termine", "uebersicht"]  # je Aufruf ein Eintrag
    for pfad in ("/api/uebersicht", "/api/unterlagen", "/api/rechnungen", "/api/termine"):
        assert _post(p, pfad, None)[0] == 401, pfad
        assert _anfrage(p.port, "GET", pfad, keks=keks).status == 405, pfad  # kein GET
    sitzung = p.w.erp("SELECT s.id FROM portal_sitzungen s JOIN portal_zugaenge z ON z.id = s.zugang_id WHERE z.customer_id = :k "
                      "ORDER BY s.id DESC LIMIT 1", k=kunde)[0][0]
    p.w.erp("INSERT INTO portal_bremsen AS b (schluessel, fenster_beginn, zaehler) VALUES (:k, "
            "to_timestamp(floor(extract(epoch FROM portal_jetzt()) / 3600) * 3600) AT TIME ZONE 'utc', 120) "
            "ON CONFLICT (schluessel, fenster_beginn) DO UPDATE SET zaehler = EXCLUDED.zaehler", k=f"liste:s:{sitzung}")
    r = _anfrage(p.port, "POST", "/api/rechnungen", keks=keks)
    assert r.status == 429 and "retry-after" in r.kopf


def test_titel_der_rechnung_wie_auf_dem_pdf():
    """Seit 1.11.45: im Portal heißt eine Rechnung wie auf ihrem PDF, kurz (Entwurf Seite 3) -- nie die Art der Listen im ERP („2. Abschlag nach …“)."""
    from app import portal_schaufenster
    from app.invoice_pdf import INVOICE_TYPE_LABELS
    from app.invoices import INVOICE_TYPES
    assert set(portal_schaufenster.TITEL) == set(INVOICE_TYPES)
    for art, titel in portal_schaufenster.TITEL.items():
        assert INVOICE_TYPE_LABELS[art].split(" ")[0] == titel, art
