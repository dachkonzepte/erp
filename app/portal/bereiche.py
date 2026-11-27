"""Die Bereiche des Kundenportals als fertige Texte (seit 1.11.45, Stufe P2e, Teil 3; Bauplan P2, B10; Entwürfe P2, Seiten 1–5).

Die Funktionen der Datenbank liefern Zeilen (app/portal/unterlagen.py, app/portal/schaufenster.py); hier wird daraus, was die Seite zeigt -- jede Zahl und jeder
Text kommt vom Server, die Seite setzt ihn nur als Text (textContent). Nichts hier liest die Datenbank; reine Funktionen, ohne Datenbank testbar.

- Gruppe: „Auftrag <Nummer> · <Betreff>“, darunter die Adresse; ohne Auftrag die Adresse, darunter „ohne bestimmten Auftrag“; ohne beides „Allgemeine
  Unterlagen“ (am Ende) -- dieselbe Regel wie im ERP (app/portal_freigaben.py::gruppe_text(), tests/test_v835 vergleicht beide).
- Beträge deutsch mit Tausenderpunkt („2.380,00 €“), Daten „20.11.2026“, Stand in Berlin („heute, 14:05 Uhr“ bzw. „26.11.2026, 9:12 Uhr“), älter als eine
  Stunde: alt (Hinweis auf der Seite).
- Zustand einer Rechnung (Entwurf Seite 5): Kennzeichen und Hinweis -- „fällig seit“ statt „fällig am“, wenn überfällig; keine roten Warnfarben.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..berlin_time import to_berlin

ALLGEMEIN = "Allgemeine Unterlagen"
OHNE_AUFTRAG = "ohne bestimmten Auftrag"
WOCHENTAG = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
MONAT = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
MONAT_KURZ = ("Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez.")
STAND_ALT = timedelta(hours=1)

# Art einer Unterlage in Worten (Entwurf Seite 2) -- Rechnungen und Mahnungen stehen unter „Rechnungen“, Fotos unter „Fotos“
ART_TEXT = {"angebot": "Angebot", "auftrag": "Auftragsbestätigung", "vertrag": "Vertrag", "abnahmeprotokoll": "Protokoll", "einsatzbericht": "Einsatzbericht",
            "brief": "Brief", "checkliste": "Protokoll", "dokument": "Dokument"}
NICHT_UNTER_UNTERLAGEN = ("rechnung", "mahnung", "foto")

# Zustand einer Rechnung -> (Kennzeichen, Farbe); Farben ohne Rot (Entwurf Seite 5)
ZUSTAND = {"offen": ("offen", "warn"), "teilweise_bezahlt": ("teilweise bezahlt", "warn"), "bezahlt": ("bezahlt", "ok"), "guthaben": ("Guthaben", "info"),
           "enthalten": ("in Schlussrechnung enthalten", "neutral"), "storniert": ("storniert", "neutral"), "storno": ("Storno", "neutral")}


def geld(betrag) -> str:
    """„2.380,00 €“, negativ „-380,80 €“ -- kaufmännisch auf den Cent."""
    d = Decimal(str(betrag)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    zeichen = "-" if d < 0 else ""
    ganz, cent = f"{abs(d):.2f}".split(".")
    gruppen = []
    while len(ganz) > 3:
        gruppen.insert(0, ganz[-3:])
        ganz = ganz[:-3]
    gruppen.insert(0, ganz)
    return f"{zeichen}{'.'.join(gruppen)},{cent} €"


def datum(tag: date | None) -> str:
    return tag.strftime("%d.%m.%Y") if tag else ""


def stand(am: datetime | None, jetzt: datetime) -> dict:
    """am, jetzt: naive UTC (wie die Datenbank). {"text": „heute, 14:05 Uhr“ | „26.11.2026, 9:12 Uhr“ | None, "alt": älter als eine Stunde oder nie}."""
    if am is None:
        return {"text": None, "alt": True}
    b, h = to_berlin(am), to_berlin(jetzt)
    uhr = f"{b.hour}:{b.minute:02d} Uhr"
    return {"text": f"heute, {uhr}" if b.date() == h.date() else f"{datum(b.date())}, {uhr}", "alt": jetzt - am > STAND_ALT}


def gruppe(auftrag: str | None, betreff: str | None, objekt: str | None) -> tuple[str, str]:
    betreff = (betreff or "").strip()
    if auftrag:
        return (f"Auftrag {auftrag} · {betreff}" if betreff else f"Auftrag {auftrag}"), objekt or ""
    if objekt:
        return objekt, OHNE_AUFTRAG
    return ALLGEMEIN, OHNE_AUFTRAG


def zahl_text(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def tage(von: date, bis: date, *, kurz: bool = False) -> str:
    """„Mo 7. – Mi 9. Dezember“, „Fr 11. Dezember“, über den Monat „Mo 30. November – Mi 2. Dezember“; kurz mit „Dez.“ (Übersicht)."""
    monat = MONAT_KURZ if kurz else MONAT

    def tag(d: date, mit_monat: bool) -> str:
        return f"{WOCHENTAG[d.weekday()]} {d.day}." + (f" {monat[d.month - 1]}" if mit_monat else "")

    if von == bis:
        return tag(von, True)
    if (von.year, von.month) == (bis.year, bis.month):
        return f"{tag(von, False)} – {tag(bis, True)}"
    return f"{tag(von, True)} – {tag(bis, True)}"


def _gruppen(zeilen: list[dict], schluessel) -> list[dict]:
    """Zeilen je Gruppe in der Reihenfolge des ersten Auftretens; „Allgemeine Unterlagen“ am Ende."""
    gruppen: dict[tuple, dict] = {}
    for z in zeilen:
        titel, unter = gruppe(z.get("auftrag"), z.get("betreff"), z.get("objekt"))
        gruppen.setdefault((titel, unter), {"titel": titel, "unter": unter, "zeilen": []})["zeilen"].append(schluessel(z))
    return sorted(gruppen.values(), key=lambda g: g["titel"] == ALLGEMEIN)


# --- Unterlagen und Fotos (portal_unterlagen) ---------------------------------------------------------------------------------------------------------

def unterlagen(zeilen: list[dict]) -> dict:
    """Die Liste (neueste zuerst, wie die Funktion sie liefert) geteilt: Unterlagen (ohne Rechnungen, Mahnungen, Fotos) und Fotos, je in Gruppen."""
    papier = [z for z in zeilen if z["art"] not in NICHT_UNTER_UNTERLAGEN]
    fotos = [z for z in zeilen if z["art"] == "foto"]
    u = _gruppen(papier, lambda z: {"freigabe": z["freigabe"], "titel": z["titel"], "art": z["art"], "art_text": ART_TEXT.get(z["art"], "Dokument"),
                                    "datum": datum(z["datum"])})
    for g in u:
        g["zahl_text"] = zahl_text(len(g["zeilen"]), "Unterlage", "Unterlagen")
    f = _gruppen(fotos, lambda z: {"freigabe": z["freigabe"], "titel": z["titel"], "datum": datum(z["datum"]),
                                   "bildtext": " · ".join(t for t in (f"Auftrag {z['auftrag']}" if z.get("auftrag") else "", datum(z["datum"])) if t)})
    for g in f:
        g["zahl_text"] = zahl_text(len(g["zeilen"]), "Foto", "Fotos")
    return {"unterlagen": u, "fotos": f}


# --- Rechnungen (portal_rechnungen) ---------------------------------------------------------------------------------------------------------------

def _zustand(z: dict) -> dict:
    """Kennzeichen, Farbe und Hinweis einer Rechnung (Entwurf Seite 5)."""
    if z["zustand"] is None or z["zustand"] not in ZUSTAND:
        return {"kennzeichen": None, "farbe": None, "hinweis": []}
    text, farbe = ZUSTAND[z["zustand"]]
    if z["zustand"] == "guthaben":
        text = f"Guthaben {geld(z['offen'])}"
    elif z["zustand"] == "storno" and z["bezug"]:
        text = f"Storno zu {z['bezug']}"
    hinweis = []
    if z["zustand"] in ("offen", "teilweise_bezahlt"):
        if z["zustand"] == "teilweise_bezahlt":
            hinweis.append(f"noch offen {geld(z['offen'])}")
        if z["faellig"]:
            hinweis.append(f"fällig seit {datum(z['faellig'])}" if z["ueberfaellig"] else f"fällig am {datum(z['faellig'])}")
    return {"kennzeichen": text, "farbe": farbe, "hinweis": hinweis}


def rechnungen(zeilen: list[dict]) -> dict:
    """Je Auftrag die Rechnungen (neueste zuerst), jede Mahnung unter ihrer Rechnung (sonst als eigene Zeile); dazu offen insgesamt."""
    rech = [z for z in zeilen if z["art"] == "rechnung"]
    mahn = [z for z in zeilen if z["art"] == "mahnung"]
    unter: dict[int, list] = {}
    for m in mahn:
        if m["zu_freigabe"] in {r["freigabe"] for r in rech}:
            unter.setdefault(m["zu_freigabe"], []).append({"freigabe": m["freigabe"], "titel": m["titel"], "datum": datum(m["datum"])})

    def zeile(z: dict) -> dict:
        if z["art"] == "mahnung":
            return {"freigabe": z["freigabe"], "art": "mahnung", "titel": z["titel"], "nummer": z["nummer"] or "", "datum": datum(z["datum"]),
                    "betrag": None, "kennzeichen": None, "farbe": None, "hinweis": [], "mahnungen": []}
        return {"freigabe": z["freigabe"], "art": "rechnung", "titel": z["titel"], "nummer": z["nummer"] or "", "datum": datum(z["datum"]),
                "betrag": geld(z["betrag"]) if z["betrag"] is not None else None, **_zustand(z),
                "mahnungen": sorted(unter.get(z["freigabe"], []), key=lambda m: m["freigabe"])}

    allein = [m for m in mahn if m["zu_freigabe"] not in {r["freigabe"] for r in rech}]
    gruppen = _gruppen(rech + allein, zeile)
    for g in gruppen:
        g["zahl_text"] = zahl_text(sum(1 for z in g["zeilen"] if z["art"] == "rechnung"), "Rechnung", "Rechnungen")
    offen = sum((Decimal(str(z["offen"])) for z in rech if z["zustand"] in ("offen", "teilweise_bezahlt") and z["offen"]), Decimal("0"))
    return {"gruppen": gruppen, "offen": geld(offen) if offen > 0 else None, "alles_bezahlt": bool(rech) and offen <= 0}


# --- Termine (portal_termine) ---------------------------------------------------------------------------------------------------------------------

def termine(zeilen: list[dict], heute: date) -> dict:
    """Je Auftrag die festen Tage: kommende (enden heute oder später, „heute“ gekennzeichnet) und vergangene (die jüngsten zuerst)."""
    kommend = [z for z in zeilen if z["bis"] >= heute]
    vorbei = sorted((z for z in zeilen if z["bis"] < heute), key=lambda z: z["von"], reverse=True)

    def eintrag(z: dict) -> dict:
        n = (z["bis"] - z["von"]).days + 1
        return {"wann": tage(z["von"], z["bis"]), "dauer": zahl_text(n, "Tag", "Tage"), "heute": z["von"] <= heute <= z["bis"]}

    return {"kommend": _gruppen(kommend, eintrag), "vergangen": _gruppen(vorbei, eintrag)}


# --- Übersicht (portal_uebersicht) ----------------------------------------------------------------------------------------------------------------

def uebersicht(z: dict) -> dict:
    """Die vier Kacheln der Startseite (Entwurf Seite 1) aus der einen Zeile."""
    einsatz = None
    if z["einsatz_von"]:
        wo = " · ".join(t for t in ((z["einsatz_betreff"] or "").strip(), z["einsatz_objekt"] or "") if t)
        einsatz = {"wann": tage(z["einsatz_von"], z["einsatz_bis"], kurz=True), "wo": wo}
    faellig = None
    if z["faellig_nummer"] or z["faellig_titel"]:
        faellig = " ".join(t for t in (z["faellig_titel"], z["faellig_nummer"]) if t) + (f", fällig am {datum(z['faellig_am'])}" if z["faellig_am"] else "")
    return {
        "rechnungen": {"offen": z["offen_anzahl"], "betrag": geld(z["offen_summe"]) if z["offen_anzahl"] else None, "faellig": faellig},
        "einsatz": einsatz,
        "unterlagen": {"zahl": z["unterlagen"], "zuletzt": f"{z['unterlage_titel']} vom {datum(z['unterlage_datum'])}" if z["unterlage_titel"] else None},
        "fotos": {"zahl": z["fotos"], "zuletzt": datum(z["foto_am"]) if z["foto_am"] else None},
    }
