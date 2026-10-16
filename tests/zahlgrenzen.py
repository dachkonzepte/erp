"""Grenzen der Zahlenfelder im Browser und auf dem Server lesen (seit 1.8.119, tests/test_v424_zahlgrenzen.py).

Browser: ein Zahlenfeld ist `<input … data-zahl …>` (Regel 34); Grenzen stehen als data-min, data-max, data-stellen, data-zahl="ganz",
required am Feld, oder als Optionen des Aufrufs, der es liest (zahlFeld()/zahlLesen(), min, max, stellen, ganz, pflicht) -- eine Option
gilt vor dem Attribut (_zahl.html::_zahlOptionen()). Server: die Grenzen des Pydantic-Felds (ge/gt/le/lt, decimal_places, int, Pflicht).

Eine Grenze ist ein Paar (Wert, inklusive). Strenger ist der Browser, wenn er etwas ablehnt, das der Server annimmt."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
SCHLUESSEL_ATTRIBUTE = ("id", "data-k", "data-r", "data-field", "data-feld", "class")


def _tag_ende(text: str, start: int) -> int:
    """Ende des Tags ab start (Position nach '>'), '>' in ${…} übersprungen."""
    tiefe, i = 0, start
    while i < len(text):
        if text.startswith("${", i):
            tiefe += 1
            i += 2
            continue
        c = text[i]
        if c == "}" and tiefe:
            tiefe -= 1
        elif c == ">" and not tiefe:
            return i + 1
        i += 1
    return len(text)


def zahl_tags(text: str):
    """Jedes <input … data-zahl …> der Vorlage: (Position, Tag)."""
    for m in re.finditer(r"<input\b", text):
        tag = text[m.start():_tag_ende(text, m.start())]
        if re.search(r"\sdata-zahl\b", tag):
            yield m.start(), tag


def attribut(tag: str, name: str) -> str | None:
    m = re.search(r'\s' + re.escape(name) + r'="([^"]*)"', tag)
    return m.group(1) if m else None


@dataclass
class Grenzen:
    min: tuple[Decimal, bool] | None = None   # (Wert, inklusive)
    max: tuple[Decimal, bool] | None = None
    stellen: int | None = None
    ganz: bool = False
    pflicht: bool = False
    herkunft: list[str] = field(default_factory=list)


def _zahl(text: str) -> Decimal:
    return Decimal(text)


def grenzen_im_markup(tag: str) -> Grenzen:
    g = Grenzen()
    if (v := attribut(tag, "data-min")) not in (None, ""):
        g.min = (_zahl(v), True)
    if (v := attribut(tag, "data-max")) not in (None, ""):
        g.max = (_zahl(v), True)
    if (v := attribut(tag, "data-stellen")) not in (None, ""):
        g.stellen = int(v) if v.isdigit() else -1  # -1: aus einem Ausdruck (z. B. ${…}), Vergleich je Eintrag
    g.ganz = attribut(tag, "data-zahl") == "ganz"
    g.pflicht = bool(re.search(r"\srequired\b", tag))
    return g


def optionen_anwenden(g: Grenzen, optionen: str) -> Grenzen:
    """Optionen eines Leseaufrufs ({min: 0, pflicht: true, …}) gelten vor den Attributen."""
    if m := re.search(r"\bmin\s*:\s*(-?[\d.]+)", optionen):
        g.min = (_zahl(m.group(1)), True)
    if m := re.search(r"\bmax\s*:\s*(-?[\d.]+)", optionen):
        g.max = (_zahl(m.group(1)), True)
    if m := re.search(r"\bstellen\s*:\s*(\d+)", optionen):
        g.stellen = int(m.group(1))
    if re.search(r"\bganz\s*:\s*true", optionen):
        g.ganz = True
    if re.search(r"\bpflicht\s*:\s*true", optionen):
        g.pflicht = True
    if re.search(r"\bpflicht\s*:\s*false", optionen):
        g.pflicht = False
    return g


def schluessel(tag: str) -> str:
    """Ein Schlüssel, der das Feld in seiner Vorlage benennt: das erste vorhandene von id, data-k, data-r, data-field, data-feld, class."""
    for name in SCHLUESSEL_ATTRIBUTE:
        if (v := attribut(tag, name)) is not None:
            return f"{name}={v}"
    return "?"


def felder_mit_grenzen(vorlage: str) -> list[tuple[str, str]]:
    """(Schlüssel, Tag) jedes Zahlenfelds der Vorlage mit einer Grenze im Markup."""
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    out = []
    for _, tag in zahl_tags(text):
        g = grenzen_im_markup(tag)
        if g.min or g.max or g.stellen is not None or g.ganz or g.pflicht:
            out.append((schluessel(tag), tag))
    return out


LESEAUFRUF = re.compile(r"\b(zahlFeld|zahlLesen)\(\s*((?:[^,{}();]|\([^()]*\))+?)\s*,\s*(\{[^{}]*\})")


def leseaufrufe_mit_grenzen(vorlage: str) -> list[tuple[str, str]]:
    """Jeder Aufruf zahlFeld()/zahlLesen() der Vorlage mit Grenzen in seinen Optionen: (Schlüssel "zahlFeld('ptDays')", Optionen)."""
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    return [(f"{m.group(1)}({m.group(2)})", m.group(3)) for m in LESEAUFRUF.finditer(text)
            if re.search(r"\b(min|max|stellen|ganz|pflicht)\s*:", m.group(3))]


# -- Server ---------------------------------------------------------------------------------------------------------------------

def grenzen_im_schema(ref: str) -> Grenzen:
    """Die Grenzen des Felds "Klasse.feld" aus app/schemas.py."""
    import typing

    import annotated_types as at

    from app import schemas

    klasse, name = ref.split(".")
    modell = getattr(schemas, klasse)
    info = modell.model_fields[name]
    g = Grenzen(herkunft=[ref])
    for m in info.metadata:
        if isinstance(m, at.Ge):
            g.min = (Decimal(str(m.ge)), True)
        elif isinstance(m, at.Gt):
            g.min = (Decimal(str(m.gt)), False)
        elif isinstance(m, at.Le):
            g.max = (Decimal(str(m.le)), True)
        elif isinstance(m, at.Lt):
            g.max = (Decimal(str(m.lt)), False)
        elif getattr(m, "decimal_places", None) is not None:
            g.stellen = m.decimal_places
    typ = info.annotation
    argumente = [a for a in typing.get_args(typ) if a is not type(None)] or [typ]
    g.ganz = all(a is int for a in argumente)
    # Pflicht heißt hier: ein gesendetes null lehnt der Server ab (der Browser schickt das Feld immer, leer als null) -- ein Typ ohne
    # None oder ein Feld in NOT_NULL eines Teil-Updates (Regel 22).
    nimmt_none = type(None) in typing.get_args(typ)
    pflicht_spalten = getattr(modell, "NOT_NULL", frozenset())
    g.pflicht = (not nimmt_none) or (name in pflicht_spalten)
    return g


def strenger(browser: Grenzen, server: Grenzen) -> list[str]:
    """Wo der Browser etwas ablehnt, das der Server annimmt."""
    gruende = []
    if browser.min is not None:
        if server.min is None:
            gruende.append(f"Mindestwert {browser.min[0]} nur im Browser")
        elif browser.min[0] > server.min[0] or (browser.min[0] == server.min[0] and not browser.min[1] and server.min[1]):
            gruende.append(f"Mindestwert {browser.min[0]} im Browser, Server ab {'' if server.min[1] else 'über '}{server.min[0]}")
    if browser.max is not None:
        if server.max is None:
            gruende.append(f"Höchstwert {browser.max[0]} nur im Browser")
        elif browser.max[0] < server.max[0] or (browser.max[0] == server.max[0] and not browser.max[1] and server.max[1]):
            gruende.append(f"Höchstwert {browser.max[0]} im Browser, Server bis {'' if server.max[1] else 'unter '}{server.max[0]}")
    if browser.stellen is not None and browser.stellen >= 0 and (server.stellen is None or browser.stellen < server.stellen):
        gruende.append(f"höchstens {browser.stellen} Nachkommastellen im Browser, Server {server.stellen if server.stellen is not None else 'beliebig'}")
    if browser.ganz and not server.ganz:
        gruende.append("ganze Zahl im Browser, Server nimmt Dezimalzahlen")
    if browser.pflicht and not server.pflicht:
        gruende.append("Pflicht im Browser, Server nimmt leer (null) an")
    return gruende
