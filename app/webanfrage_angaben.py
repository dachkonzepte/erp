"""Angaben einer Anfrage der Webseite lesen (seit 1.10.3, Stufe W1b; docs/archiv/webseite-und-kundenportal.md).

Nur aus den strukturierten Feldern des Umschlags (dk-anfrage/1), je Art -- nie aus Betreff oder Nachricht. Was der Empfangsdienst je Art liefert, geprüft
am Code des Empfangsdienstes (Paket anfrage-2026-11-18a: anfrage.py::_pruefe(), umschlag(); reparatur.py) und der Webseite (konfigurator-dach.js,
konfigurator-pv.js, kantservice.js):

    reparatur, wartung  daten im Format dk-reparatur/1, vom Dienst Feld für Feld geprüft: objekt {strasse (Pflicht, höchstens 100 Zeichen), plz (fünf
                        Ziffern), ort (Pflicht, höchstens 60), land, lage, gebaeude, …, vor_ort {name, telefon}}, melder {rolle, name, firma,
                        hausverwaltung, telefon, email, erreichbar}. kontakt ist daraus abgeleitet (name „Name (Firma)“, ort „PLZ Ort“ des Objekts).
    dach                daten version 1 aus dem Konfigurator (im Browser gerechnet, nur grob geprüft): strasse, plz, ort -- freiwillig.
                        kontakt.ort ist daraus abgeleitet („Straße, PLZ Ort“).
    pv                  daten version 2 (die Beschreibung der Schnittstelle nennt 1): strasse, plz, ort -- freiwillig, kontakt.ort wie bei Dach.
    kantservice         keine Adresse eines Objekts: nur kontakt.ort, ein freies Feld „Ort“ (Beispiel der Webseite „52511 Geilenkirchen“), keine Straße.

Jede Art trägt positionen ([] außer beim Kantservice) und aufmass (false außer beim Kantservice): ein Abschnitt einer Art gehört nur zu dieser Art und
nur mit Inhalt (abschnitte()). Die Nachricht (text) baut der Dienst bei Reparatur und Wartung allein aus den Angaben (reparatur.text());
nachricht_wiederholt() baut sie gleich nach und vergleicht -- nur dann ist sie bloß eine Wiederholung.

Werte sind Fremddaten: nur Text ohne Steuerzeichen und innerhalb der Grenzen gilt, sonst nichts (nie ein Fehler). Rollenlos wie jede Geschäftslogik.
"""

from __future__ import annotations

import json
import re

FASSUNG_REPARATUR = "dk-reparatur/1"
ARTEN_REPARATUR = ("reparatur", "wartung")
ARTEN_KONFIGURATOR = ("dach", "pv")
TITEL_REPARATUR = {"reparatur": "Reparatur-Anfrage", "wartung": "Wartungs-Anfrage"}  # wie reparatur.py::TITEL des Empfangsdienstes

# Grenzen der Auszüge = Spalten webanfragen.objekt_* (Reparatur: Straße 100, Ort 60, PLZ 5; Konfigurator im Browser: 60, 40, 10)
STRASSE_MAX = 100
PLZ_MAX = 10
ORT_MAX = 60

_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")
_LEERRAUM = re.compile(r"\s+")


def umschlag_lesen(text: str | None) -> dict | None:
    """Der gespeicherte Umschlag als dict -- None, wenn er unlesbar ist."""
    try:
        wert = json.loads(text) if text else None
    except (ValueError, RecursionError):
        return None
    return wert if isinstance(wert, dict) else None


def einzeilig(wert, hoechstens: int) -> str | None:
    """Ein Text aus den Angaben: nur str, ohne Steuerzeichen, Leerraum zusammengefasst, höchstens so lang -- sonst None."""
    if not isinstance(wert, str) or _STEUERZEICHEN.search(wert):
        return None
    text = _LEERRAUM.sub(" ", wert).strip()
    return text if text and len(text) <= hoechstens else None


def _daten(umschlag: dict | None) -> dict | None:
    daten = umschlag.get("daten") if isinstance(umschlag, dict) else None
    return daten if isinstance(daten, dict) else None


def reparatur_daten(art: str | None, umschlag: dict | None) -> dict | None:
    """Die Angaben einer Reparatur oder Wartung im Format dk-reparatur/1 -- sonst None."""
    daten = _daten(umschlag)
    if art in ARTEN_REPARATUR and daten is not None and daten.get("schema") == FASSUNG_REPARATUR:
        return daten
    return None


def objekt_adresse(art: str | None, umschlag: dict | None) -> dict | None:
    """Die Adresse des Objekts aus den strukturierten Feldern: {strasse, plz, ort} (jede Angabe Text oder None) -- None ohne jede Angabe. Reparatur und
    Wartung: daten.objekt (dk-reparatur/1); Dach und PV: daten.strasse, plz, ort; Kantservice und jede andere Art: keine."""
    if art in ARTEN_REPARATUR:
        daten = reparatur_daten(art, umschlag)
        quelle = daten.get("objekt") if daten is not None else None
    elif art in ARTEN_KONFIGURATOR:
        quelle = _daten(umschlag)
    else:
        return None
    if not isinstance(quelle, dict):
        return None
    adresse = {"strasse": einzeilig(quelle.get("strasse"), STRASSE_MAX), "plz": einzeilig(quelle.get("plz"), PLZ_MAX),
               "ort": einzeilig(quelle.get("ort"), ORT_MAX)}
    return adresse if any(adresse.values()) else None


def adresse_text(adresse: dict | None) -> str | None:
    """„Straße, PLZ Ort“ -- None ohne Angabe."""
    if not adresse:
        return None
    ort = " ".join(x for x in (adresse.get("plz"), adresse.get("ort")) if x)
    return ", ".join(x for x in (adresse.get("strasse"), ort) if x) or None


def abschnitte(art: str | None, umschlag: dict | None) -> list[str]:
    """Welche Abschnitte die Seite unter „Angaben aus dem Formular“ zeigt -- nur die der Art, nur mit Inhalt:
    reparatur (dk-reparatur/1), konfigurator (Dach, PV mit Angaben), kantservice (nur Kantservice, mit Positionen oder gewünschtem Aufmaß),
    weitere (Angaben einer unbekannten Fassung oder Art, verschachtelt)."""
    teile: list[str] = []
    daten = _daten(umschlag)
    if reparatur_daten(art, umschlag) is not None:
        teile.append("reparatur")
    elif art in ARTEN_KONFIGURATOR and daten:
        teile.append("konfigurator")
    elif daten:
        teile.append("weitere")
    if art == "kantservice" and isinstance(umschlag, dict):
        positionen = umschlag.get("positionen")
        if (isinstance(positionen, list) and positionen) or umschlag.get("aufmass") is True:
            teile.append("kantservice")
    return teile


def _reparatur_zeilen(d: dict) -> list[tuple[str | None, object]]:
    """Wie reparatur.py::zeilen() des Empfangsdienstes: [(Bezeichnung, Wert)] bzw. (None, Abschnittstitel) -- nur ausgefüllte Angaben."""
    m, o, a, t = d["melder"], d["objekt"], d["anfrage"], d["termin"]
    out: list[tuple[str | None, object]] = [("Anliegen", d["anliegen_text"] + (f" – {d['wartung_art_text']}" if d["wartung_art"] else ""))]
    out += [(None, "Wer meldet"), ("Rolle", m["rolle_text"]), ("Name", m["name"])]
    for lab, v in (("Firma / Hausverwaltung", m["firma"]), ("Hausverwaltung/Vermieter (laut Mieter)", m["hausverwaltung"]), ("Telefon", m["telefon"]),
                   ("E-Mail", m["email"]), ("Erreichbar", m["erreichbar"])):
        if v:
            out.append((lab, v))
    out += [(None, "Gebäude"), ("Anschrift", f"{o['strasse']}, {o['plz']} {o['ort']}"), ("Art des Gebäudes", o["gebaeude_text"])]
    for lab, v in (("Geschosse", o["geschosse_text"]), ("Wohnung / Lage", o["lage"]), ("Objekt-/Auftragsnummer", o["objektnummer"]),
                   ("Ansprechpartner vor Ort", o["vor_ort"]["name"]), ("Telefon vor Ort", o["vor_ort"]["telefon"])):
        if v:
            out.append((lab, v))
    out.append((None, "Schaden" if d["anliegen"] == "reparatur" else "Wartung"))
    for lab, v in (("Bereich", a["bereiche_text"]), ("Was ist passiert", a["schaeden_text"]), ("Seit wann", a["seit_text"]),
                   ("Beschreibung", a["beschreibung"])):
        if v:
            out.append((lab, v))
    if t["zeitraum"]:
        out += [(None, "Termin"), ("Zeitraum", t["zeitraum_text"])]
    out.append(("Fotos", str(d["fotos"]) if d["fotos"] else "keine"))
    return out


def reparatur_text(daten: dict) -> str | None:
    """Die Nachricht, wie sie der Empfangsdienst aus den Angaben baut (reparatur.py::text()) -- None, wenn die Angaben dafür nicht reichen."""
    try:
        zeilen = [f"{TITEL_REPARATUR[daten['anliegen']]} über die Webseite (Wartung & Reparatur)"]
        for lab, v in _reparatur_zeilen(daten):
            zeilen += ["", str(v)] if lab is None else [f"{lab}: {v}"]
        return "\n".join(zeilen)
    except (KeyError, TypeError, AttributeError):
        return None


def _vergleichbar(text: str) -> str:
    zeilen = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(z.rstrip() for z in zeilen).strip()


def nachricht_wiederholt(art: str | None, umschlag: dict | None) -> bool:
    """Die Nachricht wiederholt nur die strukturierten Angaben (Reparatur, Wartung): sie gleicht der aus den Angaben gebauten -- dann zeigt die Seite
    sie eingeklappt. Jede andere Nachricht (auch eine leicht abweichende) zeigt sie offen."""
    daten = reparatur_daten(art, umschlag)
    text = umschlag.get("text") if isinstance(umschlag, dict) else None
    if daten is None or not isinstance(text, str) or not text.strip():
        return False
    nachgebaut = reparatur_text(daten)
    return nachgebaut is not None and _vergleichbar(nachgebaut) == _vergleichbar(text)
