"""JavaScript der Vorlagen lesen, ohne es auszuführen (seit 1.8.95) -- für den Strukturtest des Bausteins _speichern.html
(tests/test_v398_speichern_baustein.py).

Ein kleiner Tokenizer (Strings, Template-Literale mit ${…}, Kommentare, Regex-Literale, Klammern) und darauf die Fragen, die der
Strukturtest stellt: wo steht eine schreibende Anfrage (Objekt mit method ungleich 'GET'), ist sie der ganze Rumpf eines Pfeils,
der als zweites Argument an speichern() geht, und was läuft nach einem Speichern noch ohne lesen()/speichern(). Kein vollständiger
JS-Parser -- Funktionen erkennt er an `function name(` und `name = (…) =>`/`name = function`, Aufrufe an `name(`. Seit 1.8.96
zählt abschliessen() wie speichern() (tests/test_v399_abschliessen.py), seit 1.8.97 findet anfragen_ausserhalb() jede Anfrage außerhalb
von lesen()/speichern()/abschliessen() (tests/test_v400_lesen_ueber_baustein.py).

Jinja in der Vorlage: {% include "x.html" %} wird eingesetzt (rekursiv), sonstige {% … %} und {{ … }} werden zu Leerzeichen bzw.
einer 0 gleicher Länge -- die Stellen behalten ihre Position, Meldungen nennen Datei und Zeile der Vorlage.

Seit 1.8.123 (Stufe 0a des Redesigns) setzt zusammensetzen() eine Seite so zusammen, wie Jinja sie zeichnet: {% extends %} mit den
Blöcken der Seite (auch über mehrere Basis-Templates, mit {{ super() }}), {% include %}, und für {% import %}/{% from … import %} die
Makros der Datei an der Stelle des Imports -- so prüfen die Scanner das HTML im Makro im Zusammenhang der Seite. alle_vorlagen() liest
auch Unterordner (Namen wie "teile/x.html", wie Jinja sie nennt). Jinja-Kommentare {# … #} zählen nicht. Was sich nicht auflösen
lässt (Name aus einer Variablen, mehrere oder bedingte extends), ist ein VorlagenFehler -- lieber rot als still ungeprüft."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

# Seit 1.8.96 auch abschliessen() -- speichern() für abschließende Aktionen (Unterschrift, Festschreiben, Versand …).
SCHREIBEND = {"speichern", "abschliessen"}
BAUSTEIN = "_speichern.html"
GEPRUEFT_RUFE = ("lesen", "speichern", "abschliessen")
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

    def datei(self, pos: int) -> str | None:
        """Die Vorlage, aus der die Position stammt (seit 1.8.96)."""
        for start, ende, datei, _ in self.herkunft:
            if start <= pos < ende:
                return datei
        return None

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


# --- Vorlagen zusammensetzen (seit 1.8.123) -----------------------------------------------------------------------------

class VorlagenFehler(ValueError):
    """Eine Vorlage, die sich nicht zusammensetzen lässt -- die Strukturtests sähen sonst einen Teil der Seite nicht."""


_KOMMENTAR = re.compile(r"\{#.*?#\}", re.S)
_TAG = re.compile(r"\{%-?\s*(\w+)(.*?)-?%\}", re.S)
_SUPER = re.compile(r"\{\{-?\s*super\(\s*\)\s*-?\}\}")
_NAME = r"""(["'])([^"']+)\1"""
_ZIEL = {
    "include": re.compile(_NAME + r"(?:\s+ignore\s+missing)?(?:\s+with(?:out)?\s+context)?"),
    "extends": re.compile(_NAME),
    "import": re.compile(_NAME + r"\s+as\s+\w+(?:\s+with(?:out)?\s+context)?"),
    "from": re.compile(_NAME + r"\s+import\s+.+", re.S),
}
# Tags mit eigenem Ende ({% set x %}…{% endset %} nur ohne "=").
_OEFFNER = {"if", "for", "block", "macro", "call", "filter", "with", "autoescape", "trans"}


@dataclass
class _Tag:
    start: int
    ende: int
    art: str
    rest: str
    ziel: str | None = None   # include/extends/import/from: der Vorlagenname
    in_block: bool = False
    in_makro: bool = False


@dataclass
class _Struktur:
    roh: str
    tags: list
    basis: str | None                              # {% extends %}
    bloecke: dict                                  # Name -> (Inhalt von, Inhalt bis)
    block_ende: dict                               # Anfang des block-Tags -> Ende des endblock-Tags
    makros: list                                   # (von, bis) je Makro auf oberster Ebene, samt seinen Tags
    supers: list                                   # (von, bis) je {{ super() }}
    ohne_kommentare: str = ""                      # roh mit Jinja-Kommentaren als Leerzeichen (seit 1.8.124)
    alle_makros: list = field(default_factory=list)  # (Name, Inhalt von, Inhalt bis) je Makro, auch verschachtelt


def _zeile_in(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _struktur(wurzel: Path, name: str) -> _Struktur:
    roh = (wurzel / name).read_text(encoding="utf-8")
    ohne = _KOMMENTAR.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), roh)  # ein Tag im Kommentar zeichnet Jinja nicht
    tags, in_raw = [], False
    for m in _TAG.finditer(ohne):
        art, rest = m.group(1), m.group(2).strip()
        if in_raw:
            in_raw = art != "endraw"
            continue
        if art == "raw":
            in_raw = True
            continue
        tags.append(_Tag(m.start(), m.end(), art, rest))

    def fehler(t: _Tag, text: str) -> VorlagenFehler:
        return VorlagenFehler(f"{name}:{_zeile_in(roh, t.start)}: {text}")

    stapel, basis, bloecke, block_ende, makros, alle_makros = [], None, {}, {}, [], []
    for t in tags:
        t.in_block = any(a == "block" for a, _ in stapel)
        t.in_makro = any(a == "macro" for a, _ in stapel)
        if t.art in _ZIEL:
            m = _ZIEL[t.art].fullmatch(t.rest)
            if not m:
                raise fehler(t, f"{{% {t.art} {t.rest} %}} -- prüfbar ist nur ein fester Vorlagenname")
            t.ziel = m.group(2)
        if t.art in _OEFFNER or (t.art == "set" and "=" not in t.rest):
            if t.art == "block" and not re.fullmatch(r"\w+(?:\s+(?:scoped|required))*", t.rest):
                raise fehler(t, f"{{% block {t.rest} %}} -- unbekannte Form")
            stapel.append((t.art, t))
        elif t.art.startswith("end") and t.art[3:] in _OEFFNER | {"set"}:
            if not stapel or stapel[-1][0] != t.art[3:]:
                raise fehler(t, f"{{% {t.art} %}} ohne passendes {{% {t.art[3:]} %}}")
            _, auf = stapel.pop()
            if auf.art == "block":
                block = auf.rest.split()[0]
                if block in bloecke:
                    raise fehler(auf, f"Block {block!r} zweimal")
                bloecke[block] = (auf.ende, t.start)
                block_ende[auf.start] = t.ende
            elif auf.art == "macro":
                alle_makros.append((re.match(r"\w*", auf.rest).group(0), auf.ende, t.start))
                if not any(a == "macro" for a, _ in stapel):
                    makros.append((auf.start, t.ende))
        elif t.art == "extends":
            if stapel:
                raise fehler(t, "{% extends %} nur auf oberster Ebene -- ein bedingtes extends ist nicht prüfbar")
            if basis is not None:
                raise fehler(t, "zweites {% extends %}")
            basis = t.ziel
    if stapel:
        raise fehler(stapel[-1][1], f"{{% {stapel[-1][0]} %}} ohne Ende")
    supers = [(m.start(), m.end()) for m in _SUPER.finditer(ohne)]
    return _Struktur(roh, tags, basis, bloecke, block_ende, makros, supers, ohne, sorted(alle_makros, key=lambda x: x[1]))


class _Lauf:
    """Ein Zusammensetzen: die Teile (Datei, von, bis) in der Reihenfolge der Seite."""

    def __init__(self, wurzel: Path, mit_includes: bool):
        self.wurzel, self.mit_includes = wurzel, mit_includes
        self.teile: list[tuple[str, int, int]] = []
        self.makros_gelesen: set[str] = set()
        self._strukturen: dict[str, _Struktur] = {}

    def struktur(self, name: str) -> _Struktur:
        if name not in self._strukturen:
            self._strukturen[name] = _struktur(self.wurzel, name)
        return self._strukturen[name]


def _kette_der_basis(lauf: _Lauf, name: str, kette: tuple) -> list[str]:
    reihe = [name]
    while lauf.struktur(reihe[-1]).basis is not None:
        basis = lauf.struktur(reihe[-1]).basis
        if basis in reihe or basis in kette:
            raise VorlagenFehler(f"Schleife über extends: {' -> '.join(reihe + [basis])}")
        reihe.append(basis)
    return reihe


def _vorlage(lauf: _Lauf, name: str, kette: tuple) -> None:
    """Die ganze Vorlage, wie Jinja sie zeichnet: hat sie ein Basis-Template, dessen Text mit den Blöcken der abgeleiteten Vorlagen
    (die abgeleitete zuerst). Jede beteiligte Datei bekommt eine Marke der Länge 0 (die Herkunft nennt sie so, auch wenn sie leer ist)."""
    if name in kette:
        raise JsFehler(f"Include-Schleife: {' -> '.join(kette + (name,))}")
    reihe = _kette_der_basis(lauf, name, kette)
    kette = kette + tuple(reihe)
    bloecke: dict[str, list] = {}
    for datei in reihe:
        lauf.teile.append((datei, 0, 0))
        for block, (von, bis) in lauf.struktur(datei).bloecke.items():
            bloecke.setdefault(block, []).append((datei, von, bis))
    # Was eine abgeleitete Vorlage außerhalb ihrer Blöcke zeichnet, verwirft Jinja -- ihre Importe gelten aber für ihre Blöcke.
    for datei in reihe[:-1]:
        for t in lauf.struktur(datei).tags:
            if t.art in ("import", "from") and not t.in_block:
                _makros(lauf, t.ziel, kette)
    wurzel = reihe[-1]
    _abschnitt(lauf, wurzel, 0, len(lauf.struktur(wurzel).roh), bloecke, None, kette)


def _makros(lauf: _Lauf, name: str, kette: tuple) -> None:
    """Die Makros einer importierten Datei (je Seite einmal): nur ihre {% macro %}…{% endmacro %} -- was die Datei sonst zeichnet,
    verwirft Jinja beim Import. Importe der Datei selbst kommen mit."""
    if name in lauf.makros_gelesen:
        return
    if name in kette:
        raise JsFehler(f"Import-Schleife: {' -> '.join(kette + (name,))}")
    lauf.makros_gelesen.add(name)
    s = lauf.struktur(name)
    for t in s.tags:
        if t.art in ("import", "from") and not t.in_makro:
            _makros(lauf, t.ziel, kette + (name,))
    for von, bis in s.makros:
        _abschnitt(lauf, name, von, bis, {}, None, kette + (name,))


def _abschnitt(lauf: _Lauf, datei: str, von: int, bis: int, bloecke: dict, super_reihe, kette: tuple) -> None:
    """Der Text datei[von:bis] mit eingesetzten Blöcken, Includes und Makros. super_reihe: (Block, die weiteren Fassungen) für
    {{ super() }} im Inhalt eines Blocks."""
    s = lauf.struktur(datei)
    pos = von
    for t in s.tags:
        if t.start < pos or t.start < von or t.ende > bis:
            continue
        if t.art == "block":
            _text(lauf, datei, pos, t.start, bloecke, super_reihe, kette)
            block = t.rest.split()[0]
            fassungen = bloecke.get(block) or [(datei, *s.bloecke[block])]
            erste, weitere = fassungen[0], fassungen[1:]
            _abschnitt(lauf, erste[0], erste[1], erste[2], bloecke, (block, weitere), kette)
            pos = s.block_ende[t.start]
        elif t.art == "include" and lauf.mit_includes:
            _text(lauf, datei, pos, t.start, bloecke, super_reihe, kette)
            _vorlage(lauf, t.ziel, kette)
            pos = t.ende
        elif t.art in ("import", "from"):
            _text(lauf, datei, pos, t.start, bloecke, super_reihe, kette)
            _makros(lauf, t.ziel, kette)
            pos = t.ende
    _text(lauf, datei, pos, bis, bloecke, super_reihe, kette)


def _text(lauf: _Lauf, datei: str, von: int, bis: int, bloecke: dict, super_reihe, kette: tuple) -> None:
    if super_reihe is not None:
        block, weitere = super_reihe
        for s_von, s_bis in lauf.struktur(datei).supers:
            if von <= s_von and s_bis <= bis:
                lauf.teile.append((datei, von, s_von))
                if weitere:
                    d, a, b = weitere[0]
                    _abschnitt(lauf, d, a, b, bloecke, (block, weitere[1:]), kette)
                von = s_bis
    lauf.teile.append((datei, von, bis))


def zusammensetzen(name: str, *, mit_includes: bool = True, wurzel: Path | None = None) -> tuple[str, list]:
    """Text der Seite und die Herkunft je Abschnitt (start, ende, datei, versatz): Basis-Templates mit den Blöcken der Seite,
    Includes (mit_includes=False: die include-Tags bleiben stehen) und die Makros importierter Dateien."""
    lauf = _Lauf(TEMPLATES if wurzel is None else wurzel, mit_includes)
    _vorlage(lauf, name, ())
    teile, herkunft, pos = [], [], 0
    for datei, von, bis in lauf.teile:
        stueck = lauf.struktur(datei).roh[von:bis]
        teile.append(stueck)
        herkunft.append((pos, pos + len(stueck), datei, von))
        pos += len(stueck)
    return "".join(teile), herkunft


def vorlage_mit_includes(name: str, _kette: tuple = ()) -> tuple[str, list]:
    """Text der Vorlage mit eingesetzten Includes und die Herkunft je Abschnitt (start, ende, datei, versatz) -- seit 1.8.123 die
    zusammengesetzte Seite (zusammensetzen())."""
    return zusammensetzen(name)


def seitentext(name: str) -> tuple[str, list]:
    """Was die Vorlage selbst zur Seite beiträgt (seit 1.8.123): ihre Basis-Templates mit ihren Blöcken und die Makros, die sie
    importiert -- ohne eingesetzte Includes (eine Teilvorlage prüfen die Scanner als eigene Datei). Ohne extends und Import ist das
    der Text der Datei."""
    return zusammensetzen(name, mit_includes=False)


def alle_vorlagen(wurzel: Path | None = None) -> list[str]:
    """Jede Vorlage unter wurzel, auch in Unterordnern, mit ihrem Namen für Jinja ("teile/x.html")."""
    wurzel = TEMPLATES if wurzel is None else wurzel
    return sorted(p.relative_to(wurzel).as_posix() for p in wurzel.rglob("*.html"))


def vorlagen_verweise(name: str, wurzel: Path | None = None) -> set[str]:
    """Die Vorlagen, die name einbindet, erweitert oder importiert (nur die eigenen Tags)."""
    return {t.ziel for t in _struktur(TEMPLATES if wurzel is None else wurzel, name).tags if t.ziel}


def basis_kette(name: str, wurzel: Path | None = None) -> list[str]:
    """Die Basis-Templates von name, das nächste zuerst."""
    lauf = _Lauf(TEMPLATES if wurzel is None else wurzel, True)
    return _kette_der_basis(lauf, name, ())[1:]


def bindet_ein(name: str, baustein: str, wurzel: Path | None = None) -> bool:
    """Ob name den Baustein selbst per {% include %} einbindet oder eines seiner Basis-Templates (seit 1.8.124, Stufe 0b: so
    verlangen die Strukturtests ein Include -- in einem Kommentar zählt es nicht)."""
    wurzel = TEMPLATES if wurzel is None else wurzel
    return any(t.art == "include" and t.ziel == baustein
               for datei in [name, *basis_kette(name, wurzel)] for t in _struktur(wurzel, datei).tags)


def makro_bereiche(name: str, wurzel: Path | None = None) -> tuple[str, list]:
    """(Text ohne Jinja-Kommentare, [(Makro, Inhalt von, Inhalt bis)]) je {% macro %} der Datei, auch verschachtelt (seit 1.8.124)."""
    s = _struktur(TEMPLATES if wurzel is None else wurzel, name)
    return s.ohne_kommentare, s.alle_makros


def seiten(wurzel: Path | None = None) -> list[str]:
    """Die Seiten: Vorlagen, die keine andere einbindet, erweitert oder importiert, und deren Name nicht mit "_" beginnt."""
    alle = alle_vorlagen(wurzel)
    verwiesen = {z for v in alle for z in vorlagen_verweise(v, wurzel)}
    return [v for v in alle if v not in verwiesen and not Path(v).name.startswith("_")]


def ort(herkunft: list, pos: int, wurzel: Path | None = None) -> tuple[str | None, int]:
    """Datei und Zeile einer Stelle im zusammengesetzten Text."""
    for start, ende, datei, versatz in herkunft:
        if start <= pos < ende:
            roh = ((TEMPLATES if wurzel is None else wurzel) / datei).read_text(encoding="utf-8")
            return datei, _zeile_in(roh, versatz + pos - start)
    return None, 0


_SKRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", flags=re.S | re.I)


def _skripte(name: str, text: str, herkunft: list) -> Quelle:
    js = ["\n" if c == "\n" else " " for c in text]
    for m in _SKRIPT.finditer(text):
        js[m.start(1):m.end(1)] = _jinja_leeren(m.group(1))
    return Quelle(name, "".join(js), herkunft)


def skript_der_vorlage(name: str) -> Quelle:
    """Alle Inline-Skripte der Vorlage samt Includes, als ein Text (Lücken dazwischen mit Leerzeichen gefüllt -- die Positionen
    bleiben die der Vorlage). Seit 1.8.123 der zusammengesetzten Seite (Basis-Templates, Makros)."""
    return _skripte(name, *vorlage_mit_includes(name))


def seitenskripte(name: str) -> Quelle:
    """Die Inline-Skripte des Seitentexts (seitentext(), seit 1.8.123): eigene, der Basis-Templates und der importierten Makros."""
    return _skripte(name, *seitentext(name))


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
    baustein: set = field(default_factory=set)  # seit 1.8.96: Namen der Funktionen aus _speichern.html

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
    # Seit 1.8.96: die Funktionen des Bausteins selbst sind der geprüfte Weg (ihre Anfragen prüfen die node-Tests in
    # tests/test_v398_speichern_baustein.py und tests/test_v399_abschliessen.py) -- der Scanner folgt ihnen nicht, sonst hielte er
    # einen Namen im Baustein (z. B. eine Variable) für die gleichnamige Funktion der Seite.
    a.baustein = {n for n, rumpfe in a.funktionen.items()
                  if any(quelle.datei(t[s].pos) == BAUSTEIN for s, _ in rumpfe)}
    return a


_ANWEISUNG = {"const", "let", "var", "function", "async", "if", "for", "while", "return", "try", "switch", "class", "do"}


_ENDET_AUSDRUCK = {"this", "super", "true", "false", "null", "undefined"}
_SETZT_FORT = {"in", "instanceof", "of"}


def _neue_anweisung(vor: Token, nach: Token) -> bool:
    """Nach einem Zeilenumbruch zwischen vor und nach beginnt eine neue Anweisung, weil nach den Ausdruck nicht fortsetzen kann (wie
    die automatische Semikolon-Einfügung von JavaScript): vor schließt einen Ausdruck ab (Name, Literal, schließende Klammer, ++/--),
    nach beginnt einen neuen (Name außer in/instanceof/of, Zahl, String, ++/--, !, ~). Ein Operator, ein Punkt, eine öffnende Klammer
    oder ein Template-Literal setzt fort."""
    endet = (vor.art in ("num", "str", "tpl", "regex")
             or (vor.art == "name" and (vor.wert not in SCHLUESSELWOERTER or vor.wert in _ENDET_AUSDRUCK))
             or (vor.art == "punct" and vor.wert in (")", "]", "}", "++", "--")))
    beginnt = ((nach.art == "name" and nach.wert not in _SETZT_FORT) or nach.art in ("num", "str")
               or (nach.art == "punct" and nach.wert in ("++", "--", "!", "~")))
    return endet and beginnt


def _ausdruck_ende(a: Analyse, start: int) -> int:
    """Ende (einschließlich) des Ausdrucks ab start -- Rumpf eines Pfeils ohne geschweifte Klammern, Wert einer Zuweisung oder eines
    return: vor ; oder , derselben Ebene, vor einer Klammer, die eine Klammer vor start schließt, oder vor einer neuen Anweisung in einer
    neuen Zeile (Schlüsselwort wie const/function/return, oder _neue_anweisung()). Eine Klammer, die ab start geöffnet wurde, gehört
    zum Ausdruck.

    Bis 1.8.104 (Nebenbefund 1.8.102 Nr. 1) endete hier jeder Pfeil an der ersten schließenden Klammer derselben Ebene, auch wenn ihre
    öffnende im Rumpf stand: `s => String(s ?? '').replace(…)` endete nach `String(s ?? ''` -- was danach kam (eine Anfrage, ein
    Speichern, ein Wert im HTML), gehörte für die Scanner nicht mehr zur Funktion. tests/vorlagen_navigation.py hatte die Klammer
    schon richtig, aber nicht das Zeilenende; beide nutzen seit 1.8.105 diese Funktion."""
    t, ebene, k = a.t, a.eltern[start], start
    while k + 1 < len(t):
        nxt = t[k + 1]
        if nxt.art == "punct" and nxt.wert in (")", "]", "}") and a.partner[k + 1] < start:
            return k
        if a.eltern[k + 1] == ebene:
            if nxt.art == "punct" and nxt.wert in (";", ","):
                return k
            ende_vor = t[k].pos + len(t[k].wert)
            if "\n" in a.quelle.text[ende_vor:nxt.pos] and ((nxt.art == "name" and nxt.wert in _ANWEISUNG)
                                                            or _neue_anweisung(t[k], nxt)):
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
    ruf: str = ""         # seit 1.8.96: "speichern" oder "abschliessen" (nur wenn ok)
    ruf_index: int = -1   # Token-Index der öffnenden Klammer dieses Aufrufs


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
    if sp < 0 or a.aufruf_name(sp) not in SCHREIBEND or a.ist_methode(sp):
        return Schreibstelle(k, False, "die Anfrage geht nicht über speichern() bzw. abschliessen()")
    args = a.argumente(sp)
    if len(args) < 2 or args[1][0] != pfeil_auf:
        return Schreibstelle(k, False, f"der Pfeil ist nicht das zweite Argument von {a.aufruf_name(sp)}()")
    if not abgewartet(a, sp):
        return Schreibstelle(k, False, f"{a.aufruf_name(sp)}() ohne await bzw. return davor (oder .then/.finally danach)")
    return Schreibstelle(k, True, "", a.aufruf_name(sp), sp)


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
    if name in a.baustein:
        return False
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
    if name in a.baustein:
        return []
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
        if name in a.baustein:
            continue
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


# --- Anfragen außerhalb des Bausteins (seit 1.8.97, Vorgabe 1.8.96 Punkt 4) ----------------------------------------------

_HANDLER = re.compile(r"""\bon[a-z]+\s*=\s*(?:"([^"]*)"|'([^']*)'|\\"(.*?)\\")""", re.S)
_NAME_AUFRUF = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")


def _umgebend(a: Analyse, k: int) -> str:
    """Name der innersten Funktion um den Token k, sonst "<oben>" (Skript auf oberster Ebene)."""
    beste, laenge = "<oben>", None
    for n, liste in a.funktionen.items():
        for s, e in liste:
            if s <= k <= e and (laenge is None or e - s < laenge):
                beste, laenge = n, e - s
    return beste


def _handler(vorlage: str | None, html: str | None):
    """(Datei, Code) je on…-Attribut -- im Markup und in Strings/Template-Literalen der Skripte."""
    if vorlage:
        text, herkunft = vorlage_mit_includes(vorlage)
    else:
        text, herkunft = html or "", []
    for m in _HANDLER.finditer(text):
        datei = next((d for s, e, d, _ in herkunft if s <= m.start() < e), vorlage)
        yield datei, m.group(1) or m.group(2) or m.group(3) or ""


def aus_dem_html(a: Analyse, vorlage: str | None, html: str | None = None) -> set:
    """Funktionen der Seite, die ein on…-Attribut aufruft -- im Markup und in Strings/Template-Literalen der Skripte."""
    return {n for _, code in _handler(vorlage, html) for n in _NAME_AUFRUF.findall(code) if n in a.funktionen}


def anfragen_ausserhalb(a: Analyse, vorlage: str | None, html: str | None = None) -> set[tuple[str, str, str]]:
    """Jede Stelle, an der die Seite eine Anfrage außerhalb von lesen()/speichern()/abschliessen() abschickt: (Datei, Funktion, Ziel).

    - Anfrage-Helfer: eine Funktion der Seite, die fetch außerhalb eines geprüften Bereichs verwendet (api(), get() …).
    - Geprüfter Bereich: das Anfrage-Argument (das zweite) von lesen()/speichern()/abschliessen().
    - Nur im Baustein erreicht (G): eine Funktion, deren sämtliche Verweise in geprüften Bereichen oder in G-Funktionen stehen; ein Aufruf
      aus dem HTML (on…="name(…)") zählt als Verweis außerhalb.
    - Fund: ein Verweis auf fetch oder einen Anfrage-Helfer außerhalb geprüfter Bereiche, in einer Funktion (oder oben im Skript), die
      weder in G noch selbst ein Anfrage-Helfer ist. Ziel ist fetch bzw. der Name des Helfers; die Datei ist die, in der der Verweis
      steht (eine Teilvorlage zählt einmal, egal wie viele Seiten sie einbinden).
    - Seit 1.8.99 (Festlegung 1.8.97 Nr. 1, korrigiert) auch ein direkter Aufruf von fetch oder eines Anfrage-Helfers aus einem
      on…-Attribut (onclick="api(…)", auch in Template-Literalen): Funktion "<html>" -- bis 1.8.98 sah der Scanner nur Skripte."""
    gepr = a.gepruefte_bereiche()
    alle = list(verweise(a, 0, len(a.t) - 1))
    helfer = {n for n, liste in a.funktionen.items() if n not in a.baustein
              and any(m == "fetch" and not _in(gepr, k) for s, e in liste for k, m in verweise(a, s, e))}
    G = {n for n in a.funktionen if n not in a.baustein} - aus_dem_html(a, vorlage, html)
    umgebend = {k: _umgebend(a, k) for k, _ in alle}
    while True:
        raus = {m for k, m in alle if m in G and not _in(gepr, k) and umgebend[k] != m and umgebend[k] not in G}
        if not raus:
            break
        G -= raus
    funde = set()
    for k, m in alle:
        if (m != "fetch" and m not in helfer) or _in(gepr, k) or a.quelle.datei(a.t[k].pos) == BAUSTEIN:
            continue
        f = umgebend[k]
        if f in G or f in helfer or f in a.baustein:
            continue
        funde.add((a.quelle.datei(a.t[k].pos), f, m))
    for datei, code in _handler(vorlage, html):
        for n in _NAME_AUFRUF.findall(code):
            if n == "fetch" or n in helfer:
                funde.add((datei, "<html>", n))
    return funde
