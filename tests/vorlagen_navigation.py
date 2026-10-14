"""Navigationen der Vorlagen zu Werten aus der Adresse finden (seit 1.8.98, tests/test_v401_weiterleitung.py).

Eine Navigation ist eine Zuweisung an location, location.href oder X.href, oder ein Aufruf von location.assign(), location.replace()
oder window.open()/open(). Ein Wert aus der Adresse kommt aus location.search, location.hash, location.href (gelesen),
document.referrer, document.URL/documentURI/baseURI oder window.name -- auch über Variablen (jede Zuweisung, deren rechte Seite einen
solchen Wert enthält, macht die Variable dazu, bis nichts Neues mehr dazukommt) und über Funktionen, deren Rumpf einen enthält.

Eine solche Navigation ist geprüft, wenn ihr Ziel
- sicheresZiel(…) ist (app/templates/_weiterleitung.html), oder
- mit einem festen Text beginnt, der ein lokaler Pfad ist ("/x…", x weder "/" noch "\\") -- dann bestimmt der Wert nur den Rest des
  Pfads, nie den Server,
- bei a ? b : c und a || b bzw. a ?? b: jeder mögliche Wert (b und c bzw. a und b) ist geprüft.

Gelesen wird mit dem Tokenizer aus tests/vorlagen_js.py (kein vollständiger JS-Parser); Handler im HTML (on…="…") werden als eigenes
Skript gelesen, mit den belasteten Namen des Skripts der Vorlage. Über-Annäherung ist gewollt: eine Variable gleichen Namens in
einer anderen Funktion zählt mit."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tests.vorlagen_js import _ANWEISUNG, TEMPLATES, Analyse, Quelle, analysieren, eigene_skripte

_QUELLEN = {("location", "search"), ("location", "hash"), ("location", "href"), ("document", "referrer"), ("document", "URL"),
            ("document", "documentURI"), ("document", "baseURI"), ("window", "name")}
_HANDLER = re.compile(r"""\bon[a-z]+\s*=\s*"([^"]*)\"""", re.S)
_PUNKT = (".", "?.")


@dataclass
class Navigation:
    vorlage: str
    stelle: str
    ziel: str          # Quelltext des Ziels
    aus_adresse: bool
    geprueft: bool


def _ende(a: Analyse, start: int) -> int:
    """Ende (einschließlich) des Ausdrucks ab start: vor ; oder , derselben Ebene, vor einer Klammer, die eine Klammer vor start
    schließt, oder vor einer neuen Anweisung in einer neuen Zeile."""
    t, ebene, k = a.t, a.eltern[start], start
    while k + 1 < len(t):
        nxt = t[k + 1]
        if nxt.art == "punct" and nxt.wert in (")", "]", "}") and a.partner[k + 1] < start:
            return k
        if a.eltern[k + 1] == ebene:
            if nxt.art == "punct" and nxt.wert in (";", ","):
                return k
            if nxt.art == "name" and nxt.wert in _ANWEISUNG and "\n" in a.quelle.text[t[k].pos:nxt.pos]:
                return k
        k += 1
    return k


def _text(a: Analyse, start: int, ende: int) -> str:
    letzt = a.t[ende]
    return a.quelle.text[a.t[start].pos:letzt.pos + len(letzt.wert) + (1 if letzt.art == "str" else 0)].strip()


def _ist_quelle(a: Analyse, k: int) -> bool:
    """Token k ist das Objekt einer Quelle (location.search …), die gelesen und nicht zugewiesen wird."""
    t = a.t
    if k + 2 >= len(t) or t[k].art != "name" or t[k + 1].wert not in _PUNKT or t[k + 2].art != "name":
        return False
    if (t[k].wert, t[k + 2].wert) not in _QUELLEN:
        return False
    return not (k + 3 < len(t) and t[k + 3].art == "punct" and t[k + 3].wert == "=")


def _zuweisungen(a: Analyse):
    """(Name, Start, Ende) je Zuweisung name = … (auch const/let/var, auch mehrere Deklaratoren)."""
    t = a.t
    for k in range(1, len(t) - 1):
        if t[k].art == "punct" and t[k].wert == "=" and t[k - 1].art == "name" and (k < 2 or t[k - 2].wert not in _PUNKT):
            yield t[k - 1].wert, k + 1, _ende(a, k + 1)


def _belastet(a: Analyse, start: int, ende: int, namen: set, funktionen: set) -> bool:
    t = a.t
    for k in range(start, ende + 1):
        if _ist_quelle(a, k):
            return True
        if t[k].art == "name" and (k == 0 or t[k - 1].wert not in _PUNKT):
            if t[k].wert in namen:
                return True
            if t[k].wert in funktionen and k + 1 <= ende and t[k + 1].wert == "(":
                return True
    return False


def belastete_namen(a: Analyse, namen: set | None = None, funktionen: set | None = None) -> tuple[set, set]:
    """Variablen und Funktionen, die einen Wert aus der Adresse tragen können (Fixpunkt), ausgehend von namen/funktionen."""
    namen, funktionen = set(namen or ()), set(funktionen or ())
    while True:
        neu = False
        for name, start, ende in _zuweisungen(a):
            if name not in namen and name not in a.funktionen and _belastet(a, start, ende, namen, funktionen):
                namen.add(name)
                neu = True
        for name, rumpfe in a.funktionen.items():
            if name not in funktionen and any(_belastet(a, s, e, namen, funktionen) for s, e in rumpfe):
                funktionen.add(name)
                neu = True
        if not neu:
            return namen, funktionen


def _lokaler_text(wert: str) -> bool:
    return len(wert) >= 2 and wert[0] == "/" and wert[1] not in "/\\"


def _oberste(a: Analyse, start: int, ende: int, zeichen: tuple) -> list[int]:
    ebene = a.eltern[start]
    return [k for k in range(start, ende + 1) if a.t[k].art == "punct" and a.t[k].wert in zeichen and a.eltern[k] == ebene]


def geprueft(a: Analyse, start: int, ende: int) -> bool:
    """Ob das Ziel t[start..ende] geprüft ist (Regeln oben)."""
    t = a.t
    if start > ende:
        return False
    if t[start].art == "punct" and t[start].wert == "(" and a.partner.get(start) == ende:
        return geprueft(a, start + 1, ende - 1)
    frage = _oberste(a, start, ende, ("?",))
    if frage:
        q, tiefe, doppel = frage[0], 0, None
        for k in range(q + 1, ende + 1):
            if a.eltern[k] != a.eltern[start] or t[k].art != "punct":
                continue
            if t[k].wert == "?":
                tiefe += 1
            elif t[k].wert == ":":
                if tiefe == 0:
                    doppel = k
                    break
                tiefe -= 1
        return doppel is not None and geprueft(a, q + 1, doppel - 1) and geprueft(a, doppel + 1, ende)
    oder = _oberste(a, start, ende, ("||", "??"))
    if oder:
        grenzen = [start - 1, *oder, ende + 1]
        return all(geprueft(a, grenzen[i] + 1, grenzen[i + 1] - 1) for i in range(len(grenzen) - 1))
    if t[start].art == "name" and t[start].wert == "sicheresZiel" and start + 1 <= ende and t[start + 1].wert == "(":
        return a.partner[start + 1] == ende
    if t[start].art in ("str", "tpl"):
        return _lokaler_text(t[start].wert) or (start == ende and t[start].art == "str" and t[start].wert == "/")
    return False


def _ziele(a: Analyse):
    """(Start, Ende) des Ziels je Navigation."""
    t = a.t
    for k, tok in enumerate(t):
        if tok.art != "punct":
            continue
        if tok.wert == "=" and k >= 1 and t[k - 1].art == "name":
            letztes = t[k - 1].wert
            vorn_punkt = k >= 2 and t[k - 2].wert in _PUNKT
            if letztes == "location" or (letztes == "href" and vorn_punkt):
                yield k + 1, _ende(a, k + 1)
        elif tok.wert == "(" and k >= 1 and t[k - 1].art == "name":
            n = t[k - 1].wert
            methode = k >= 3 and t[k - 2].wert in _PUNKT
            objekt = t[k - 3].wert if methode else None
            if (n in ("assign", "replace") and objekt == "location") or (n == "open" and (objekt == "window" or not methode)):
                args = a.argumente(k)
                if args:
                    yield args[0]


def navigationen(quelle: Quelle, namen: set | None = None, funktionen: set | None = None) -> list[Navigation]:
    a = analysieren(quelle)
    namen, funktionen = belastete_namen(a, namen, funktionen)
    return [Navigation(quelle.name, a.stelle(s), _text(a, s, e), _belastet(a, s, e, namen, funktionen), geprueft(a, s, e))
            for s, e in _ziele(a) if s <= e]


def navigationen_der_vorlage(name: str, unlesbar: list | None = None) -> list[Navigation]:
    """Die Navigationen der eigenen Skripte einer Vorlage und ihrer Handler im HTML (on…="…", auch in Template-Literalen). Ein
    Handler, den der Tokenizer nicht lesen kann, landet in unlesbar (Vorlage, Code)."""
    quelle = eigene_skripte(name)
    out = navigationen(quelle)
    namen, funktionen = belastete_namen(analysieren(quelle))
    roh = (TEMPLATES / name).read_text(encoding="utf-8")
    for m in _HANDLER.finditer(roh):
        code = m.group(1).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
        code = re.sub(r"\$\{([^}]*)\}", r"(\1)", code)  # ${…} eines Template-Literals als Ausdruck
        try:
            out += navigationen(Quelle(name, code, [(0, len(code), name, m.start(1))]), namen, funktionen)
        except Exception:
            if unlesbar is not None:
                unlesbar.append((name, code))
    return out


def alle_vorlagen() -> list[str]:
    return sorted(p.name for p in TEMPLATES.glob("*.html"))
