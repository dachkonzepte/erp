"""JavaScript der Vorlagen lesen, ohne es auszuführen (seit 1.8.95) -- für den Strukturtest des Bausteins _speichern.html
(tests/test_v398_speichern_baustein.py).

Ein kleiner Tokenizer (Strings, Template-Literale mit ${…}, Kommentare, Regex-Literale, Klammern) und darauf die Fragen, die der
Strukturtest stellt: wo steht eine schreibende Anfrage (Objekt mit method ungleich 'GET'), ist sie der ganze Rumpf eines Pfeils,
der als zweites Argument an speichern() geht, und was läuft nach einem Speichern noch ohne lesen()/speichern(). Kein vollständiger
JS-Parser -- Funktionen erkennt er an `function name(` und `name = (…) =>`/`name = function`, Aufrufe an `name(`.

Jinja in der Vorlage: {% include "x.html" %} wird eingesetzt (rekursiv), sonstige {% … %} und {{ … }} werden zu Leerzeichen bzw.
einer 0 gleicher Länge -- die Stellen behalten ihre Position, Meldungen nennen Datei und Zeile der Vorlage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

SCHREIBEND = {"speichern"}
GEPRUEFT_RUFE = ("lesen", "speichern")
SCHLUESSELWOERTER = {
    "if", "for", "while", "switch", "catch", "function", "return", "typeof", "new", "await", "async", "else", "do", "in", "of",
    "case", "delete", "void", "throw", "instanceof", "yield", "const", "let", "var", "try", "finally", "class", "super", "this",
    "import", "export", "default", "break", "continue", "true", "false", "null", "undefined",
}
_REGEX_DAVOR_NAME = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "instanceof",
                     "yield", "await"}
_PUNKT_MEHR = ("===", "!==", "...", "**=", "<<=", ">>=", "&&=", "||=", "??=", "=>", "==", "!=", "<=", ">=", "&&", "||", "??",
               "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>")


@dataclass
class Token:
    art: str     # name | str | tpl | num | regex | punct
    wert: str
    pos: int


@dataclass
class Quelle:
    """Ein Skript einer Vorlage: Text (mit eingesetzten Includes) und für jede Position Datei und Zeile."""
    name: str
    text: str
    herkunft: list = field(default_factory=list)  # (start, ende, datei, versatz_in_datei)

    def stelle(self, pos: int) -> str:
        for start, ende, datei, versatz in self.herkunft:
            if start <= pos < ende:
                original = (TEMPLATES / datei).read_text(encoding="utf-8")
                return f"{datei}:{original.count(chr(10), 0, versatz + pos - start) + 1}"
        return f"{self.name}:?"


class JsFehler(ValueError):
    pass


def _jinja_leeren(text: str) -> str:
    text = re.sub(r"\{#.*?#\}", lambda m: " " * len(m.group(0)), text, flags=re.S)
    text = re.sub(r"\{%.*?%\}", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"\{\{.*?\}\}", lambda m: "0" + re.sub(r"[^\n]", " ", m.group(0))[1:], text, flags=re.S)


_INCLUDE = re.compile(r"""\{%-?\s*include\s+["']([^"']+)["']\s*-?%\}""")


def vorlage_mit_includes(name: str, _kette: tuple = ()) -> tuple[str, list]:
    """Text der Vorlage mit eingesetzten Includes und die Herkunft je Abschnitt (start, ende, datei, versatz)."""
    if name in _kette:
        raise JsFehler(f"Include-Schleife: {' -> '.join(_kette + (name,))}")
    roh = (TEMPLATES / name).read_text(encoding="utf-8")
    teile, herkunft, pos, aus = [], [], 0, 0
    for m in _INCLUDE.finditer(roh):
        stueck = roh[aus:m.start()]
        teile.append(stueck)
        herkunft.append((pos, pos + len(stueck), name, aus))
        pos += len(stueck)
        innen, innen_herkunft = vorlage_mit_includes(m.group(1), _kette + (name,))
        teile.append(innen)
        herkunft += [(pos + s, pos + e, d, v) for s, e, d, v in innen_herkunft]
        pos += len(innen)
        aus = m.end()
    stueck = roh[aus:]
    teile.append(stueck)
    herkunft.append((pos, pos + len(stueck), name, aus))
    return "".join(teile), herkunft


_SKRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", flags=re.S | re.I)


def skript_der_vorlage(name: str) -> Quelle:
    """Alle Inline-Skripte der Vorlage samt Includes, als ein Text (Lücken dazwischen mit Leerzeichen gefüllt -- die Positionen
    bleiben die der Vorlage)."""
    text, herkunft = vorlage_mit_includes(name)
    js = ["\n" if c == "\n" else " " for c in text]
    for m in _SKRIPT.finditer(text):
        js[m.start(1):m.end(1)] = _jinja_leeren(m.group(1))
    return Quelle(name, "".join(js), herkunft)


def eigene_skripte(name: str) -> Quelle:
    """Nur die Inline-Skripte der Vorlage selbst, ohne eingesetzte Includes (Positionen wie in der Datei)."""
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    js = ["\n" if c == "\n" else " " for c in text]
    for m in _SKRIPT.finditer(text):
        js[m.start(1):m.end(1)] = _jinja_leeren(m.group(1))
    return Quelle(name, "".join(js), [(0, len(text), name, 0)])


def tokens(src: str) -> list[Token]:
    out: list[Token] = []
    _tokenisieren(src, 0, out, im_ausdruck=False)
    return out


def _regex_moeglich(out: list[Token]) -> bool:
    if not out:
        return True
    t = out[-1]
    if t.art == "name":
        return t.wert in _REGEX_DAVOR_NAME
    if t.art in ("str", "tpl", "num", "regex"):
        return False
    return t.wert not in (")", "]", "}")


def _tokenisieren(src: str, i: int, out: list[Token], im_ausdruck: bool) -> int:
    """Liest ab i; im_ausdruck: innerhalb von ${…} -- endet an der schließenden Klammer (gibt deren Position + 1 zurück)."""
    tiefe, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                raise JsFehler(f"Kommentar ohne Ende ab {i}")
            i = j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    raise JsFehler(f"Zeilenumbruch im String ab {i}")
                j += 1
            out.append(Token("str", src[i + 1:j], i))
            i = j + 1
            continue
        if c == "`":
            i = _template(src, i, out)
            continue
        if c == "/" and _regex_moeglich(out):
            j, in_klasse = i + 1, False
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "\n":
                    raise JsFehler(f"Zeilenumbruch im Regex ab {i}")
                if src[j] == "[":
                    in_klasse = True
                elif src[j] == "]":
                    in_klasse = False
                elif src[j] == "/" and not in_klasse:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum()):
                j += 1
            out.append(Token("regex", src[i:j], i))
            i = j
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "._" or (src[j] in "+-" and src[j - 1] in "eE"
                                                                    and not src[i:j].lower().startswith("0x"))):
                j += 1
            out.append(Token("num", src[i:j], i))
            i = j
            continue
        if c.isalpha() or c in "_$" or ord(c) > 127:
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "_$" or ord(src[j]) > 127):
                j += 1
            out.append(Token("name", src[i:j], i))
            i = j
            continue
        p = next((x for x in _PUNKT_MEHR if src.startswith(x, i)), c)
        if p == "?." and i + 2 < n and src[i + 2].isdigit():
            p = "?"  # a?.5:b ist der Bedingungsoperator
        if im_ausdruck:
            if p == "{":
                tiefe += 1
            elif p == "}":
                if tiefe == 0:
                    return i + 1
                tiefe -= 1
        out.append(Token("punct", p, i))
        i += len(p)
    if im_ausdruck:
        raise JsFehler("${ ohne Ende")
    return i


def _template(src: str, i: int, out: list[Token]) -> int:
    """Template-Literal ab dem Backtick bei i: Textteile als tpl, ${…} als ( … ) mit den Tokens des Ausdrucks."""
    j, start, n = i + 1, i + 1, len(src)
    while j < n:
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == "`":
            out.append(Token("tpl", src[start:j], start))
            return j + 1
        if src.startswith("${", j):
            out.append(Token("tpl", src[start:j], start))
            out.append(Token("punct", "(", j))
            k = _tokenisieren(src, j + 2, out, im_ausdruck=True)
            out.append(Token("punct", ")", k - 1))
            j = start = k
            continue
        j += 1
    raise JsFehler(f"Template-Literal ohne Ende ab {i}")


@dataclass
class Analyse:
    quelle: Quelle
    t: list[Token]
    partner: dict          # Index einer Klammer -> Index der Gegenklammer
    eltern: list           # je Token: Index der innersten offenen Klammer (oder -1)
    funktionen: dict       # Name -> [(start, ende)] Rumpf (Token-Indizes, einschließlich)

    def stelle(self, i: int) -> str:
        return self.quelle.stelle(self.t[i].pos)

    # --- Aufrufe ------------------------------------------------------------------------------------------------------
    def aufruf_name(self, auf: int) -> str | None:
        """Name des Aufrufs, wenn die Klammer bei auf eine Aufrufklammer ist (name( oder .name(), sonst None."""
        if self.t[auf].wert != "(" or auf == 0:
            return None
        v = self.t[auf - 1]
        if v.art != "name" or v.wert in SCHLUESSELWOERTER:
            return None
        if auf >= 2 and self.t[auf - 2].art == "name" and self.t[auf - 2].wert == "function":
            return None
        return v.wert

    def ist_methode(self, auf: int) -> bool:
        return auf >= 2 and self.t[auf - 2].wert in (".", "?.")

    def argumente(self, auf: int) -> list[tuple[int, int]]:
        """(start, ende) je Argument des Aufrufs mit der öffnenden Klammer auf -- Token-Indizes, einschließlich."""
        zu = self.partner[auf]
        args, start = [], auf + 1
        for k in range(auf + 1, zu):
            if self.t[k].wert == "," and self.eltern[k] == auf and self.t[k].art == "punct":
                args.append((start, k - 1))
                start = k + 1
        if start <= zu - 1:
            args.append((start, zu - 1))
        return args

    def aufrufe(self, name: str | None = None):
        for k, tok in enumerate(self.t):
            if tok.art == "punct" and tok.wert == "(":
                n = self.aufruf_name(k)
                if n is not None and (name is None or n == name):
                    yield k, n

    def gepruefte_bereiche(self) -> list[tuple[int, int]]:
        """Das zweite Argument (die Anfrage) jedes lesen()/speichern()-Aufrufs."""
        out = []
        for auf, n in self.aufrufe():
            if n in GEPRUEFT_RUFE and not self.ist_methode(auf):
                args = self.argumente(auf)
                if len(args) >= 2:
                    out.append(args[1])
        return out


def analysieren(quelle: Quelle) -> Analyse:
    t = tokens(quelle.text)
    partner, eltern, stapel = {}, [], []
    paare = {")": "(", "]": "[", "}": "{"}
    for k, tok in enumerate(t):
        if tok.art == "punct" and tok.wert in paare:
            if not stapel or t[stapel[-1]].wert != paare[tok.wert]:
                raise JsFehler(f"{quelle.stelle(tok.pos)}: unpassende Klammer {tok.wert!r}")
            auf = stapel.pop()
            partner[auf], partner[k] = k, auf
        eltern.append(stapel[-1] if stapel else -1)
        if tok.art == "punct" and tok.wert in "([{":
            stapel.append(k)
    if stapel:
        raise JsFehler(f"{quelle.stelle(t[stapel[-1]].pos)}: Klammer ohne Ende")
    a = Analyse(quelle, t, partner, eltern, {})
    a.funktionen = _funktionen(a)
    return a


_ANWEISUNG = {"const", "let", "var", "function", "async", "if", "for", "while", "return", "try", "switch", "class", "do"}


def _ausdruck_ende(a: Analyse, start: int) -> int:
    """Ende (einschließlich) eines Pfeilrumpfs ohne Klammern: bis ; , oder die schließende Klammer der Umgebung, oder eine neue
    Anweisung in einer neuen Zeile."""
    t, ebene = a.t, a.eltern[start]
    k = start
    while k + 1 < len(t):
        nxt = t[k + 1]
        if a.eltern[k + 1] == ebene:
            if nxt.art == "punct" and nxt.wert in (";", ",", ")", "]", "}"):
                return k
            if (nxt.art == "name" and nxt.wert in _ANWEISUNG
                    and "\n" in a.quelle.text[t[k].pos:nxt.pos]):
                return k
        elif a.eltern[k + 1] != ebene and nxt.art == "punct" and nxt.wert in (")", "]", "}") and a.partner.get(k + 1, 10**9) < start:
            return k
        k += 1
    return k


def _rumpf_nach_pfeil(a: Analyse, pfeil: int) -> tuple[int, int]:
    nach = pfeil + 1
    if a.t[nach].wert == "{" and a.t[nach].art == "punct":
        return nach, a.partner[nach]
    return nach, _ausdruck_ende(a, nach)


def _funktionen(a: Analyse) -> dict:
    t, f = a.t, {}
    for k, tok in enumerate(t):
        if tok.art != "name":
            continue
        # function name(…) { … }
        if tok.wert == "function" and k + 2 < len(t) and t[k + 1].art == "name" and t[k + 2].wert == "(":
            zu = a.partner[k + 2]
            if t[zu + 1].wert == "{":
                f.setdefault(t[k + 1].wert, []).append((zu + 1, a.partner[zu + 1]))
            continue
        # name = (async)? (…) => …   |   name = (async)? x => …   |   name = (async)? function(…) { … }
        if k + 1 < len(t) and t[k + 1].wert == "=" and (k == 0 or t[k - 1].wert not in (".", "?.")):
            j = k + 2
            if j < len(t) and t[j].wert == "async":
                j += 1
            if j < len(t) and t[j].wert == "function":
                j += 1
                if t[j].art == "name":
                    j += 1
                if t[j].wert == "(":
                    zu = a.partner[j]
                    if t[zu + 1].wert == "{":
                        f.setdefault(tok.wert, []).append((zu + 1, a.partner[zu + 1]))
                continue
            if j < len(t) and t[j].wert == "(" and t[a.partner[j] + 1].wert == "=>":
                pfeil = a.partner[j] + 1
                f.setdefault(tok.wert, []).append(_rumpf_nach_pfeil(a, pfeil))
            elif j + 1 < len(t) and t[j].art == "name" and t[j + 1].wert == "=>":
                f.setdefault(tok.wert, []).append(_rumpf_nach_pfeil(a, j + 1))
    return f


# --- Schreibende Anfragen ---------------------------------------------------------------------------------------------

@dataclass
class Schreibstelle:
    index: int            # Token-Index des Schlüssels method
    ok: bool
    grund: str


def schreibstellen(a: Analyse) -> list[Schreibstelle]:
    """Jede Objekt-Eigenschaft method mit einem anderen Wert als 'GET' -- und ob sie so steht, wie der Baustein es verlangt:
    Objekt direkt als Argument einer Anfrage (api(…, {method: …}) bzw. fetch(…)), diese Anfrage der ganze Rumpf eines Pfeils
    ohne Parameter, der Pfeil das zweite Argument von speichern(), speichern() mit await oder return davor."""
    t, out = a.t, []
    for k, tok in enumerate(t):
        if tok.art != "name" or tok.wert != "method":
            continue
        obj = a.eltern[k]
        if obj < 0 or t[obj].wert != "{" or t[k - 1].wert not in ("{", ","):
            continue
        if t[k + 1].wert == ":":
            ende, schluss = k + 2, a.partner[obj]
            while ende < schluss and not (a.eltern[ende] == obj and t[ende].wert == "," and t[ende].art == "punct"):
                ende += 1
            wert = t[k + 2:ende]
            if len(wert) == 1 and wert[0].art == "str" and wert[0].wert.upper() == "GET":
                continue
        elif t[k + 1].wert not in (",", "}"):
            continue
        out.append(_pruefe_schreibstelle(a, k, obj))
    return out


def _pruefe_schreibstelle(a: Analyse, k: int, obj: int) -> Schreibstelle:
    t = a.t
    auf = a.eltern[obj]
    if auf < 0 or a.aufruf_name(auf) is None or t[obj - 1].wert not in ("(", ","):
        return Schreibstelle(k, False, "die Optionen mit method stehen nicht direkt im Aufruf der Anfrage")
    name_i = auf - 1
    zu = a.partner[auf]
    vor = name_i - 1
    if a.ist_methode(auf):
        return Schreibstelle(k, False, f"Anfrage als Methode .{t[name_i].wert}(…) -- erwartet api(…) oder fetch(…)")
    if not (t[vor].wert == "=>" and t[vor - 1].wert == ")" and t[vor - 2].wert == "("):
        return Schreibstelle(k, False, "die Anfrage ist nicht der Rumpf eines Pfeils ()=>…")
    if t[zu + 1].wert not in (",", ")"):
        return Schreibstelle(k, False, "nach der Anfrage folgt noch etwas -- der Pfeil darf nur die Anfrage enthalten")
    pfeil_auf = vor - 2
    sp = a.eltern[pfeil_auf]
    if sp < 0 or a.aufruf_name(sp) != "speichern" or a.ist_methode(sp):
        return Schreibstelle(k, False, "die Anfrage geht nicht über speichern()")
    args = a.argumente(sp)
    if len(args) < 2 or args[1][0] != pfeil_auf:
        return Schreibstelle(k, False, "der Pfeil ist nicht das zweite Argument von speichern()")
    if not abgewartet(a, sp):
        return Schreibstelle(k, False, "speichern() ohne await bzw. return davor (oder .then/.finally danach)")
    return Schreibstelle(k, True, "")


def abgewartet(a: Analyse, auf: int) -> bool:
    """Der Aufruf mit der öffnenden Klammer auf wird abgewartet: await bzw. return davor, oder .then(…)/.finally(…) danach -- was
    danach kommt, läuft erst nach dem Anwenden."""
    t, zu = a.t, a.partner[auf]
    if auf >= 2 and t[auf - 2].wert in ("await", "return"):
        return True
    return zu + 2 < len(t) and t[zu + 1].wert == "." and t[zu + 2].wert in ("then", "finally")


# --- Was nach einem Speichern läuft -----------------------------------------------------------------------------------

def _in(bereiche, i):
    return any(s <= i <= e for s, e in bereiche)


def verweise(a: Analyse, start: int, ende: int):
    """(Index, Name) jedes Verweises auf eine bekannte Funktion oder fetch zwischen start und ende -- Aufruf oder Name als Wert,
    nicht als Eigenschaft (.name), Schlüssel ({name: …}) oder Definition."""
    t = a.t
    for k in range(start, ende + 1):
        tok = t[k]
        if tok.art != "name" or (tok.wert not in a.funktionen and tok.wert != "fetch"):
            continue
        if k > 0 and t[k - 1].wert in (".", "?.", "function"):
            continue
        if k + 1 < len(t) and t[k + 1].wert == ":" and k > 0 and t[k - 1].wert in ("{", ","):
            continue
        if k + 1 < len(t) and t[k + 1].wert == "=" :
            continue
        if k > 0 and t[k - 1].wert in ("const", "let", "var"):
            continue
        yield k, tok.wert


def _schreibt(a: Analyse, name: str, memo: dict, kette=()) -> bool:
    if name in memo:
        return memo[name]
    if name in kette:
        return False
    ergebnis = False
    for s, e in a.funktionen.get(name, []):
        for auf, n in a.aufrufe():
            if s <= auf <= e and (n in SCHREIBEND or (n in a.funktionen and n != name and _schreibt(a, n, memo, kette + (name,)))):
                ergebnis = True
                break
    memo[name] = ergebnis
    return ergebnis


def ungepruefte_anfragen(a: Analyse, name: str, memo: dict, gepr: list, kette=()) -> list[tuple[int, str]]:
    """Wo eine Funktion (oder etwas, das sie anstößt) eine Anfrage ohne lesen()/speichern() stellt: (Index, Weg). Leer = sie
    liest und schreibt nur über den Baustein."""
    if name == "fetch":
        return [(-1, "fetch")]
    if name in memo:
        return memo[name]
    if name in kette:
        return []
    out = []
    for s, e in a.funktionen.get(name, []):
        for k, n in verweise(a, s, e):
            if _in(gepr, k):
                continue
            if n == "fetch":
                out.append((k, f"{name} → fetch"))
                continue
            for k2, weg in ungepruefte_anfragen(a, n, memo, gepr, kette + (name,)):
                out.append((k if k2 < 0 or not (s <= k2 <= e) else k2, f"{name} → {weg}"))
    memo[name] = out
    return out


def nach_dem_speichern(a: Analyse) -> list[tuple[int, str]]:
    """In jeder Funktion, die speichert (speichern() oder eine Funktion, die speichert, aufruft): alles, was danach kommt --
    Aufrufe, übergebene Funktionen, anwenden/neuLaden -- liest nur über lesen()/speichern(). (Index, Weg) je Verstoß."""
    gepr = a.gepruefte_bereiche()
    schreib_memo, anfrage_memo, out = {}, {}, []
    for name, rumpfe in a.funktionen.items():
        for s, e in rumpfe:
            erster = None
            for auf, n in a.aufrufe():
                if s <= auf <= e and not a.ist_methode(auf) and (n in SCHREIBEND or (n in a.funktionen and n != name
                                                                                       and _schreibt(a, n, schreib_memo))):
                    erster = auf if erster is None else min(erster, auf)
            if erster is None:
                continue
            for k, n in verweise(a, erster, e):
                if _in(gepr, k):
                    continue
                if n == "fetch":
                    out.append((k, f"{name}: fetch nach dem Speichern"))
                    continue
                for _, weg in ungepruefte_anfragen(a, n, anfrage_memo, gepr):
                    out.append((k, f"{name}: nach dem Speichern {weg}"))
    return sorted(set(out))
