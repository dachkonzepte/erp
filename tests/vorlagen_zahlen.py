"""Zahleneingaben in den Vorlagen finden (seit 1.8.109, Vorgabe "Vor dem Abnahmetest" Punkt 1) -- für
tests/test_v414_zahleneingaben.py.

Eine Seite macht aus einer Eingabe nur über den Baustein app/templates/_zahl.html eine Zahl (zahlFeld(), zahlLesen(),
zahlVorschau()) und füllt ein Zahlenfeld nur über zahlText(). Der Scanner findet, was daran vorbeigeht -- je Fund Vorlage, Zeile,
Art und Ausschnitt:

  type-number   ein Feld type="number" (Markup oder Template-Literal) -- Chrome liest dort bei deutscher Sprache den Punkt als
                Dezimaltrenner ("1.250" wird 1,25), den Rohtext bekommt die Seite nie zu sehen.
  parse         parseFloat()/parseInt()/valueAsNumber -- jede Verwendung (auch auf Daten der API: dort tut es Number()).
  komma         ein Komma durch einen Punkt ersetzen (replace/replaceAll mit "," bzw. /,/ und ".") -- eine eigene Umwandlung.
  wert          ein Feldwert (.value) wird zur Zahl: als Argument von Number()/Math.*()/isNaN()/isFinite(), mit + davor, in einer
                Rechnung (* / % - **), auch über eine Variable oder einen Helfer der Seite (v('id') → …value). Ausgenommen sind
                Felder, die keinen freien Text tragen: Auswahllisten (<select>) und input type checkbox/radio/hidden/date/month/
                time/datetime-local/range/color/week/file -- erkannt über die ID (getElementById, querySelector('#…'), ein
                Helfer der Seite mit der ID als erstem Argument, eine Variable mit einem solchen Wert, this im on…-Attribut).
  roh           der Text eines Zahlenfelds (data-zahl) wird gelesen, ohne zahlLesen() -- etwa roh an den Server geschickt (Pydantic
                liest "1.250" als 1,25) oder auf leer geprüft; erkannt wie bei wert über die ID.
  schreiben     ein Zahlenfeld (data-zahl) wird ohne zahlText() gefüllt: value="${…}" im Tag, el.value = …, ein Helfer der Seite.
  inputmode     ein Feld data-zahl ohne inputmode="decimal"/"numeric" (die Zifferntastatur auf dem Tablet).
  einbinden     eine Seite nutzt den Baustein, bindet ihn aber nicht ein (auch nicht über eine Teilvorlage).

Kein vollständiger JS-Parser (Tokenizer aus tests/vorlagen_js.py): Ziele, die sich nicht auflösen lassen (z. B. e.target.value,
row.querySelector('.x').value ohne Element mit dieser Klasse), gelten als Textfeld -- lieber ein Fund zu viel als eine Umwandlung
übersehen. Der Baustein selbst wird nicht geprüft (seine Regeln prüft die Angriffstabelle in node).

Seit 1.8.123 liest der Scanner je Vorlage ihren Seitentext (tests/vorlagen_js.py::seitentext(): die Datei samt Basis-Templates und
importierten Makros) und löst Felder in der zusammengesetzten Seite auf; ein Fund nennt die Datei und Zeile, in der er steht.
Vorlagen auch in Unterordnern."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from tests import vorlagen_js
from tests.vorlagen_js import (_HANDLER, SCHLUESSELWOERTER, TEMPLATES, Analyse, JsFehler, Quelle, _ausdruck_ende, analysieren,
                               seitenskripte, seitentext, tokens, vorlage_mit_includes)

BAUSTEIN = "_zahl.html"
FUNKTIONEN = {"zahlLesen", "zahlFeld", "zahlVorschau", "zahlText"}
# Felder ohne freien Text: ihre Werte setzt die Seite selbst (IDs einer Auswahl, Datum, Häkchen) -- Number() darauf ist keine
# Zahleneingabe.
NICHT_TEXT = {"select", "checkbox", "radio", "hidden", "date", "month", "time", "datetime-local", "range", "color", "week", "file"}
ELEMENT_SUCHE = {"getElementById", "querySelector", "closest"}
UMWANDLUNG = {"Number", "isNaN", "isFinite"}
RECHNEN = {"*", "/", "%", "-", "**", "*=", "/=", "%=", "-="}
_TAG = re.compile(r"<(input|select|textarea)\b((?:[^>\"'`$]|\"[^\"]*\"|'[^']*'|\$\{[^}]*\}|`[^`]*`)*)>", re.I | re.S)
_ATTR = re.compile(r"""([\w:-]+)\s*(?:=\s*(?:\\?"([^"\\]*(?:\\.[^"\\]*)*?)\\?"|\\?'([^'\\]*)\\?'|([^\s>]+)))?""")
_TYPE_NUMBER = re.compile(r"""\btype\s*=\s*\\?["']?number\b|\.type\s*=\s*["']number["']|setAttribute\(\s*["']type["']\s*,\s*["']number""",
                          re.I)


@dataclass(frozen=True)
class Fund:
    vorlage: str
    zeile: int
    art: str
    ausschnitt: str

    def __str__(self) -> str:
        return f"{self.vorlage}:{self.zeile}: [{self.art}] {self.ausschnitt}"


@dataclass(frozen=True)
class Element:
    tag: str          # input | select | textarea
    typ: str          # type-Attribut (input), sonst der Tag
    id: str           # wörtlich, ${…} bleibt stehen
    klassen: tuple
    zahl: bool        # data-zahl
    inputmode: str
    pos: int          # im Rohtext der Vorlage
    tagtext: str

    @property
    def freier_text(self) -> bool:
        return self.tag == "textarea" or (self.tag == "input" and self.typ not in NICHT_TEXT)

    @property
    def id_anfang(self) -> str:
        return self.id.split("${")[0]


def _zeile(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _attribute(tagtext: str) -> dict:
    out = {}
    for m in _ATTR.finditer(tagtext):
        name = m.group(1).lower()
        wert = next((g for g in m.groups()[1:] if g is not None), "")
        out.setdefault(name, wert)
    return out


@lru_cache(maxsize=None)
def elemente(vorlage: str) -> tuple[Element, ...]:
    """Alle input/select/textarea der Vorlage samt Includes (Markup und Template-Literale)."""
    text, _ = vorlage_mit_includes(vorlage)
    out = []
    for m in _TAG.finditer(text):
        attrs = _attribute(m.group(2))
        tag = m.group(1).lower()
        typ = (attrs.get("type") or "text").lower() if tag == "input" else tag
        out.append(Element(tag, typ, attrs.get("id", ""), tuple((attrs.get("class") or "").split()), "data-zahl" in attrs,
                           (attrs.get("inputmode") or "").lower(), m.start(), m.group(0)))
    return tuple(out)


def _passend(vorlage: str, *, id_wort: str | None = None, id_teile: tuple[str, str] | None = None, klasse: str | None = None):
    """id_wort: die ID genau; id_teile: (Anfang, Ende) einer zusammengesetzten ID ('rl' + id + 'Days', `mqty-${id}`) -- passt zu
    jeder ID mit diesem Anfang und diesem Ende, auch zu einer im Markup zusammengesetzten (rl${x.id}Days)."""
    for e in elemente(vorlage):
        if id_wort is not None and e.id == id_wort:
            yield e
        elif id_teile is not None and e.id:
            anfang, ende = id_teile
            if "${" not in e.id:
                if e.id.startswith(anfang) and e.id.endswith(ende) and len(e.id) > len(anfang) + len(ende):
                    yield e
                continue
            e_ende = e.id.rsplit("}", 1)[-1]
            vorn = anfang.startswith(e.id_anfang) or e.id_anfang.startswith(anfang)
            hinten = ende.endswith(e_ende) or e_ende.endswith(ende)
            belegt = (anfang and e.id_anfang) or (ende and e_ende)  # mindestens ein Stück auf beiden Seiten
            if vorn and hinten and belegt:
                yield e
        elif klasse is not None and klasse in e.klassen:
            yield e


class Scanner:
    """Die Funde einer Vorlage (ihr Seitentext: eigene Skripte und Markup, seit 1.8.123 samt Basis-Templates und importierten Makros;
    Teilvorlagen werden als eigene Datei geprüft). Alle Positionen sind Stellen im Seitentext."""

    def __init__(self, vorlage: str):
        self.vorlage = vorlage
        self.roh, self.herkunft = seitentext(vorlage)
        self._dateien: dict[str, str] = {}
        self.funde: set[Fund] = set()
        try:
            self.a: Analyse | None = analysieren(seitenskripte(vorlage))
        except JsFehler:
            self.a = None
        self.getter: dict[str, int] = {}   # Name -> Index des Parameters, der die ID trägt
        self.setter: dict[str, int] = {}
        self.wert_getter: set[str] = set()  # Helfer, die einen Feldwert liefern (Ziel nicht auflösbar)

    # --- Hilfen --------------------------------------------------------------------------------------------------------
    def _fund(self, pos: int, art: str, ausschnitt: str) -> None:
        """Ein Fund an der Stelle pos des Seitentexts -- gemeldet mit der Datei und Zeile, in der er steht."""
        datei, zeile = self.vorlage, _zeile(self.roh, pos)
        for start, ende, d, versatz in self.herkunft:
            if start <= pos < ende:
                if d not in self._dateien:
                    self._dateien[d] = (vorlagen_js.TEMPLATES / d).read_text(encoding="utf-8")
                datei, zeile = d, _zeile(self._dateien[d], versatz + pos - start)
                break
        self.funde.add(Fund(datei, zeile, art, " ".join(ausschnitt.split())[:140]))

    def _code(self, a: Analyse, s: int, e: int) -> str:
        return a.quelle.text[a.t[s].pos:a.t[e].pos + len(a.t[e].wert) + (2 if a.t[e].art == "str" else 0)]

    # --- Element eines Ausdrucks ---------------------------------------------------------------------------------------
    def _ziel_aus_aufruf(self, a: Analyse, auf: int, name: str) -> list[Element] | None:
        args = a.argumente(auf)
        i = self.getter.get(name, self.setter.get(name, 0)) if name not in ELEMENT_SUCHE else 0
        if len(args) <= i:
            return None
        s, e = args[i]
        erstes = a.t[s]
        if name in ("getElementById",) or name in self.getter or name in self.setter:
            if erstes.art == "str" and s == e:
                return list(_passend(self.vorlage, id_wort=erstes.wert))
            anfang = erstes.wert if erstes.art in ("str", "tpl") else ""
            ende = a.t[e].wert if e > s and a.t[e].art in ("str", "tpl") else ""
            if not anfang and not ende:
                return None
            return list(_passend(self.vorlage, id_teile=(anfang, ende)))
        if name in ("querySelector", "querySelectorAll", "closest") and erstes.art == "str" and s == e:
            return self._selektor(erstes.wert)
        return None

    def _selektor(self, sel: str) -> list[Element] | None:
        """Elemente zu einem einfachen CSS-Selektor (letzter Teil: tag, #id, .klasse, [type=…], [name=…], Pseudoklassen
        ignoriert); None, wenn er nichts eingrenzt."""
        teil = re.split(r"[\s>+~]+", sel.strip())[-1]
        teil = re.sub(r":[\w-]+(\([^)]*\))?", "", teil)
        m = re.fullmatch(r"(input|select|textarea)?((?:[#.][\w-]+|\[[^\]]+\])*)", teil)
        if not m:
            return None
        tag, rest = m.group(1), m.group(2)
        ids = re.findall(r"#([\w-]+)", rest)
        klassen = re.findall(r"\.([\w-]+)", rest)
        attrs = dict((k.lower(), v) for k, v in re.findall(r"\[([\w-]+)\s*=\s*['\"]?([^'\"\]]+)['\"]?\]", rest))
        if not (ids or klassen or attrs or tag == "select"):
            return None
        out = []
        for el in elemente(self.vorlage):
            if tag and el.tag != tag:
                continue
            if ids and el.id != ids[0]:
                continue
            if any(k not in el.klassen for k in klassen):
                continue
            if "type" in attrs and el.typ != attrs["type"].lower():
                continue
            if "name" in attrs and f'name="{attrs["name"]}"' not in el.tagtext:
                continue
            out.append(el)
        return out or None

    def _parameter_ziel(self, a: Analyse, k: int, name: str) -> list[Element] | None:
        """name ist Parameter eines Pfeils, der an .map/.forEach/… über querySelectorAll('…') geht: die Elemente des Selektors."""
        t = a.t
        for j in range(k - 1, 0, -1):
            if t[j].wert != "=>" or t[j].art != "punct":
                continue
            if t[j - 1].art == "name" and t[j - 1].wert == name:
                anfang = j - 1
            elif t[j - 1].wert == ")" and any(x.art == "name" and x.wert == name for x in t[a.partner[j - 1]:j - 1]):
                anfang = a.partner[j - 1]
            else:
                continue
            rumpf_s, rumpf_e = (j + 1, a.partner[j + 1]) if t[j + 1].wert == "{" else (j + 1, _ausdruck_ende(a, j + 1))
            if not (rumpf_s <= k <= rumpf_e):
                continue
            auf = a.eltern[anfang]
            if auf < 0 or t[auf].wert != "(" or a.aufruf_name(auf) not in ("map", "forEach", "filter", "some", "every", "find",
                                                                             "flatMap"):
                return None
            for x in range(auf - 1, max(auf - 40, 0), -1):
                if t[x].art == "name" and t[x].wert == "querySelectorAll" and t[x + 1].wert == "(" and t[x + 2].art == "str":
                    return self._selektor(t[x + 2].wert)
            return None
        return None

    def _ziel(self, a: Analyse, ende: int, umfeld: list[Element] | None = None) -> list[Element] | None:
        """Elemente, deren Wert der Ausdruck mit letztem Token ende (vor .value) bezeichnet; None, wenn nicht auflösbar."""
        t = a.t
        tok = t[ende]
        if tok.art == "punct" and tok.wert == ")":
            auf = a.partner[ende]
            name = a.aufruf_name(auf)
            if name is None:
                return None
            if name not in ELEMENT_SUCHE and name not in self.getter:
                return None
            return self._ziel_aus_aufruf(a, auf, name)
        if tok.art == "name" and (ende == 0 or t[ende - 1].wert not in (".", "?.")):
            if tok.wert == "this":
                return umfeld
            return self._variable(a, ende, tok.wert) or self._parameter_ziel(a, ende, tok.wert)
        return None

    def _variable(self, a: Analyse, k: int, name: str) -> list[Element] | None:
        """Wert der letzten Deklaration const/let/var name = … vor k in einem umgebenden Block."""
        t = a.t
        for j in range(k - 1, 1, -1):
            if t[j].art == "name" and t[j].wert == name and t[j - 1].wert in ("const", "let", "var") and t[j + 1].wert == "=":
                if not self._im_block_von(a, j, k):
                    continue
                ende = _ausdruck_ende(a, j + 2)
                if ende >= j + 2 and t[ende].wert == ")":
                    return self._ziel(a, ende)
                return None
        return None

    def _im_block_von(self, a: Analyse, dekl: int, k: int) -> bool:
        block = a.eltern[dekl]
        while block >= 0 and a.t[block].wert != "{":
            block = a.eltern[block]
        if block < 0:
            return True
        return block < k <= a.partner[block]

    # --- Feldwerte -----------------------------------------------------------------------------------------------------
    def _wertlesungen(self, a: Analyse, s: int, e: int, umfeld=None):
        """(Index, Elemente|None) je Feldwert (.value, Getter-Aufruf, Variable aus einem Feldwert) im Bereich s..e."""
        t = a.t
        for k in range(s, e + 1):
            tok = t[k]
            if tok.art == "name" and tok.wert == "value" and k >= 2 and t[k - 1].wert in (".", "?."):
                if k + 2 <= e + 1 and k + 1 < len(t) and t[k + 1].wert == "." and k + 2 < len(t) and t[k + 2].wert == "length":
                    continue
                yield k, self._ziel(a, k - 2, umfeld)
            elif tok.art == "name" and tok.wert == "valueAsNumber" and t[k - 1].wert in (".", "?."):
                yield k, None
            elif tok.art == "name" and k + 1 < len(t) and t[k + 1].wert == "(" and (k == 0 or t[k - 1].wert not in (".", "?.")):
                if tok.wert in self.getter and tok.wert in self.wert_getter_ids:
                    yield k, self._ziel_aus_aufruf(a, k + 1, tok.wert)
                elif tok.wert in self.wert_getter:
                    yield k, None
            elif tok.art == "name" and (k == 0 or t[k - 1].wert not in (".", "?.")) and tok.wert in self._wertvariablen(a):
                for dekl, ziel in self._wertvariablen(a)[tok.wert]:
                    if dekl < k and self._im_block_von(a, dekl, k):
                        yield k, ziel
                        break

    def _wertvariablen(self, a: Analyse) -> dict:
        """Name -> [(Index der Deklaration, Elemente|None)] für const/let/var name = <Feldwert> -- der Feldwert auf oberster Ebene
        des Ausdrucks (el.value, el.value.trim(), el.value || '0'), nicht in einem Aufruf (liste.find(x => x.id == sel.value))."""
        cache = self.__dict__.setdefault("_wv", {})
        if id(a) not in cache:
            wv = cache[id(a)] = {}
            t = a.t
            for j in range(1, len(t) - 2):
                if t[j].art == "name" and t[j - 1].wert in ("const", "let", "var") and t[j + 1].wert == "=":
                    ende = _ausdruck_ende(a, j + 2)
                    for k in range(j + 2, ende + 1):
                        if t[k].art == "name" and t[k].wert == "value" and t[k - 1].wert in (".", "?.") \
                                and a.eltern[k] == a.eltern[j + 2]:
                            if k + 1 < len(t) and t[k + 1].wert == "." and k + 2 < len(t) and t[k + 2].wert == "length":
                                continue
                            wv.setdefault(t[j].wert, []).append((j, self._ziel(a, k - 2)))
                            break
        return cache[id(a)]

    def _helfer_erkennen(self, a: Analyse) -> None:
        """Getter (gibt den Wert des Feldes mit der ID aus Parameter i zurück) und Setter der Seite."""
        t = a.t
        self.wert_getter_ids = set()
        for name, rumpfe in a.funktionen.items():
            if name in FUNKTIONEN:
                continue
            for s, e in rumpfe:
                if e - s > 40:
                    continue
                params = self._parameter(a, s)
                code = [x.wert for x in t[s:e + 1]]
                for k in range(s, e + 1):
                    if t[k].art == "name" and t[k].wert in ("getElementById", "$", "el", "byId") and k + 3 <= e \
                            and t[k + 1].wert == "(" and t[k + 2].art == "name" and t[k + 2].wert in params \
                            and t[k + 3].wert == ")":
                        rest = code[k + 4 - s:]
                        if rest[:2] == [".", "value"] and (len(rest) < 3 or rest[2] != "="):
                            self.getter[name] = params.index(t[k + 2].wert)
                            self.wert_getter_ids.add(name)
                        elif rest[:3] == [".", "value", "="]:
                            self.setter[name] = params.index(t[k + 2].wert)
                        elif not rest or rest[0] in (";", "}", ")"):
                            self.getter.setdefault(name, params.index(t[k + 2].wert))  # Element-Helfer
                if name not in self.getter and name not in self.setter and "value" in code and "=" not in code and e - s <= 12:
                    self.wert_getter.add(name)

    def _parameter(self, a: Analyse, rumpf_start: int) -> list[str]:
        t = a.t
        k = rumpf_start - 1
        if t[k].wert == "=>":
            k -= 1
        if t[k].art == "name":
            return [t[k].wert]
        if t[k].wert == ")":
            auf = a.partner[k]
            return [x.wert for x in t[auf + 1:k] if x.art == "name"]
        if t[rumpf_start].wert == "{" and t[rumpf_start - 1].wert == ")":
            auf = a.partner[rumpf_start - 1]
            return [x.wert for x in t[auf + 1:rumpf_start - 1] if x.art == "name"]
        return []

    def _verbotene_lesung(self, ziel) -> bool:
        return ziel is None or not ziel or any(e.freier_text for e in ziel)

    # --- Regeln im Skript ----------------------------------------------------------------------------------------------
    def _skript(self, a: Analyse, versatz: int, umfeld=None, datei_pos=None) -> None:
        t = a.t

        def fund(k, art, s, e):
            pos = datei_pos if datei_pos is not None else t[k].pos + versatz
            self._fund(pos, art, self._code(a, s, e))

        for k, tok in enumerate(t):
            if tok.art != "name":
                continue
            # parse
            if tok.wert in ("parseFloat", "parseInt", "valueAsNumber"):
                fund(k, "parse", max(k - 2, 0), min(k + 3, len(t) - 1))
                continue
            # komma
            if tok.wert in ("replace", "replaceAll") and k >= 1 and t[k - 1].wert in (".", "?.") and k + 1 < len(t) \
                    and t[k + 1].wert == "(":
                args = a.argumente(k + 1)
                if len(args) >= 2:
                    (s1, e1), (s2, e2) = args[0], args[1]
                    erstes, zweites = t[s1], t[s2]
                    komma = (s1 == e1 and ((erstes.art == "str" and erstes.wert == ",")
                                           or (erstes.art == "regex" and re.fullmatch(r"/,/[gimsuy]*", erstes.wert))))
                    if komma and s2 == e2 and zweites.art == "str" and zweites.wert == ".":
                        fund(k, "komma", max(k - 3, 0), a.partner[k + 1])
                continue
            # Number(…), Math.x(…), isNaN(…)
            if k + 1 < len(t) and t[k + 1].wert == "(" and (
                    (tok.wert in UMWANDLUNG and (k == 0 or t[k - 1].wert not in (".", "?.")))
                    or (k >= 2 and t[k - 1].wert == "." and t[k - 2].wert == "Math")):
                zu = a.partner[k + 1]
                for j, ziel in self._wertlesungen(a, k + 2, zu - 1, umfeld):
                    if self._verbotene_lesung(ziel):
                        fund(k, "wert", k, zu)
                        break
        for k, tok in enumerate(t):
            if tok.art != "punct":
                continue
            # + vor einem Feldwert (unär)
            if tok.wert == "+" and k + 1 < len(t) and self._unaer(a, k):
                ende = self._kette_ende(a, k + 1)
                for j, ziel in self._wertlesungen(a, k + 1, ende, umfeld):
                    if self._verbotene_lesung(ziel):
                        fund(k, "wert", k, ende)
                        break
            # Rechnen mit einem Feldwert
            if tok.wert in RECHNEN and not (tok.wert == "-" and self._unaer(a, k)):
                links_anfang = self._kette_anfang(a, k - 1)
                rechts_ende = self._kette_ende(a, k + 1) if k + 1 < len(t) else k
                for s, e in ((links_anfang, k - 1), (k + 1, rechts_ende)):
                    if s > e:
                        continue
                    if any(self._verbotene_lesung(z) for _, z in self._wertlesungen(a, s, e, umfeld)):
                        fund(k, "wert", links_anfang, rechts_ende)
                        break

    def _unaer(self, a: Analyse, k: int) -> bool:
        if k == 0:
            return True
        v = a.t[k - 1]
        if v.art in ("num", "str", "tpl", "regex"):
            return False
        if v.art == "name":
            return v.wert in SCHLUESSELWOERTER and v.wert not in ("this", "true", "false", "null", "undefined")
        return v.wert not in (")", "]", "}", "++", "--")

    def _kette_ende(self, a: Analyse, k: int) -> int:
        """Ende eines Operanden ab k: Name/Literal mit .x, [..], (..) dahinter, oder eine Klammer."""
        t = a.t
        if k >= len(t):
            return len(t) - 1
        if t[k].wert in ("(", "[") and t[k].art == "punct":
            k = a.partner[k]
        elif t[k].wert in ("!", "-", "+", "typeof", "await", "~"):
            return self._kette_ende(a, k + 1)
        while k + 1 < len(t):
            n = t[k + 1]
            if n.wert in (".", "?.") and k + 2 < len(t):
                k += 2
            elif n.wert in ("(", "[") and n.art == "punct":
                k = a.partner[k + 1]
            else:
                break
        return k

    def _kette_anfang(self, a: Analyse, k: int) -> int:
        t = a.t
        while k >= 0:
            tok = t[k]
            if tok.wert in (")", "]") and tok.art == "punct":
                k = a.partner[k]
                if k >= 1 and (t[k - 1].art == "name" or t[k - 1].wert in (")", "]")):
                    k -= 1
                    continue
                return k
            if k >= 1 and t[k - 1].wert in (".", "?."):
                k -= 2
                continue
            return k
        return 0

    # --- Markup --------------------------------------------------------------------------------------------------------
    def _markup(self) -> None:
        for m in _TYPE_NUMBER.finditer(self.roh):
            zeile_anfang = self.roh.rfind("\n", 0, m.start()) + 1
            self._fund(m.start(), "type-number", self.roh[max(zeile_anfang, m.start() - 60):m.end() + 40])
        for m in _TAG.finditer(self.roh):
            attrs = _attribute(m.group(2))
            if "data-zahl" not in attrs:
                continue
            if (attrs.get("inputmode") or "").lower() not in ("decimal", "numeric"):
                self._fund(m.start(), "inputmode", m.group(0)[:120])
            wert = attrs.get("value")
            if wert and "${" in wert and "zahlText(" not in wert:
                self._fund(m.start(), "schreiben", m.group(0)[:140])

    def _rohe_lesungen(self, a: Analyse, umfeld=None, datei_pos=None) -> None:
        """roh: der Text eines Zahlenfelds (data-zahl) außerhalb von zahlLesen(…) -- geht er so an den Server, liest Pydantic
        "1.250" als 1,25 (bis 1.8.108 lieferte Chrome dort Maschinenformat)."""
        t = a.t
        in_zahl_lesen = []
        for auf, name in a.aufrufe("zahlLesen"):
            in_zahl_lesen.append((auf, a.partner[auf]))
        for k, tok in enumerate(t):
            ziel, start, ende = None, k, k
            if tok.art == "name" and tok.wert == "value" and k >= 2 and t[k - 1].wert in (".", "?."):
                if k + 1 < len(t) and t[k + 1].art == "punct" and t[k + 1].wert in ("=", "+=") or \
                        (k + 2 < len(t) and t[k + 1].wert == "." and t[k + 2].wert == "length"):
                    continue
                ziel = self._ziel(a, k - 2, umfeld)
                start = self._kette_anfang(a, k - 2)
            elif tok.art == "name" and tok.wert in getattr(self, "wert_getter_ids", ()) and k + 1 < len(t) \
                    and t[k + 1].wert == "(" and (k == 0 or t[k - 1].wert not in (".", "?.")):
                ziel = self._ziel_aus_aufruf(a, k + 1, tok.wert)
                ende = a.partner[k + 1]
            if not ziel or not any(e.zahl for e in ziel):
                continue
            if any(s < k < e for s, e in in_zahl_lesen):
                continue
            pos = datei_pos if datei_pos is not None else t[k].pos
            self._fund(pos, "roh", self._code(a, start, ende))

    def _zuweisungen(self, a: Analyse) -> None:
        t = a.t
        for k, tok in enumerate(t):
            ziel, ausdruck = None, None
            if tok.art == "name" and tok.wert == "value" and k >= 2 and t[k - 1].wert in (".", "?.") and k + 1 < len(t) \
                    and t[k + 1].wert == "=" and t[k + 1].art == "punct":
                ziel = self._ziel(a, k - 2)
                ausdruck = (k + 2, _ausdruck_ende(a, k + 2))
                start = self._kette_anfang(a, k - 2)
            elif tok.art == "name" and tok.wert in self.setter and k + 1 < len(t) and t[k + 1].wert == "(" \
                    and (k == 0 or t[k - 1].wert not in (".", "?.")):
                args = a.argumente(k + 1)
                i = self.setter[tok.wert]
                if len(args) > max(i, 1):
                    ziel = self._ziel_aus_aufruf(a, k + 1, tok.wert)
                    ausdruck = args[1] if i == 0 else args[0]
                    start = k
            if not ziel or not any(e.zahl for e in ziel):
                continue
            s, e = ausdruck
            werte = [x for x in t[s:e + 1]]
            if any(x.art == "name" and x.wert == "zahlText" for x in werte):
                continue
            if len(werte) == 1 and werte[0].art == "str" and werte[0].wert == "":
                continue
            self._fund(t[k].pos, "schreiben", self._code(a, start, e))

    def _handler_code(self) -> None:
        """on…-Attribute (Markup und Strings der Skripte): dieselben Regeln, this = das Element des Attributs."""
        for m in _HANDLER.finditer(self.roh):
            code = m.group(1) or m.group(2) or m.group(3) or ""
            if not code.strip():
                continue
            tag_anfang = self.roh.rfind("<", 0, m.start())
            tag = re.match(r"<(input|select|textarea)\b", self.roh[tag_anfang:tag_anfang + 10] or "", re.I)
            umfeld = None
            if tag:
                el = next((e for e in elemente(self.vorlage) if self.roh[tag_anfang:tag_anfang + 40] in e.tagtext[:40]), None)
                if el is None:
                    tagtext = self.roh[tag_anfang:self.roh.find(">", m.end()) + 1]
                    attrs = _attribute(tagtext[len(tag.group(0)):])
                    t = tag.group(1).lower()
                    el = Element(t, (attrs.get("type") or "text").lower() if t == "input" else t, attrs.get("id", ""), (), False,
                                 "", tag_anfang, tagtext)
                umfeld = [el]
            code = code.replace('\\"', '"').replace("\\'", "'")
            try:
                quelle = Quelle(self.vorlage, code, [(0, len(code), self.vorlage, 0)])
                a = analysieren(quelle)
            except (JsFehler, KeyError, IndexError):
                continue
            a.funktionen = {}
            self._skript(a, 0, umfeld=umfeld, datei_pos=m.start())
            self._rohe_lesungen(a, umfeld=umfeld, datei_pos=m.start())

    # --- Ablauf --------------------------------------------------------------------------------------------------------
    def pruefen(self) -> set[Fund]:
        self._markup()
        self.wert_getter_ids = set()
        if self.a is not None:
            self._helfer_erkennen(self.a)
            self._skript(self.a, 0)
            self._zuweisungen(self.a)
            self._rohe_lesungen(self.a)
        self._handler_code()
        return self.funde


def alle_vorlagen() -> list[str]:
    """Seit 1.8.123 auch in Unterordnern (tests/vorlagen_js.py::alle_vorlagen())."""
    return [v for v in vorlagen_js.alle_vorlagen(TEMPLATES) if v != BAUSTEIN]


def seiten() -> list[str]:
    """Die Seiten (seit 1.8.123: auch in Unterordnern; ohne Teilvorlagen, Basis-Templates und Makro-Dateien -- die prüft die Seite,
    die sie einbindet, erweitert oder importiert)."""
    return [v for v in vorlagen_js.seiten(TEMPLATES) if v != BAUSTEIN]


@lru_cache(maxsize=None)
def funde_der_vorlage(vorlage: str) -> frozenset[Fund]:
    return frozenset(Scanner(vorlage).pruefen())


def alle_funde() -> list[Fund]:
    """Je Stelle einmal: ein Fund im Basis-Template meldet auch jede Seite, die von ihr erbt (seit 1.8.123)."""
    out: set[Fund] = set()
    for v in alle_vorlagen():
        out |= funde_der_vorlage(v)
    return sorted(out, key=lambda f: (f.vorlage, f.zeile, f.art, f.ausschnitt))


def ohne_einbindung() -> list[str]:
    """Seiten (keine Teilvorlage), die zahlFeld()/zahlLesen()/zahlVorschau()/zahlText() aufrufen -- auch über eine eingebundene
    Teilvorlage, ihr Basis-Template oder ein Makro --, ohne _zahl.html einzubinden."""
    out = []
    aufruf = re.compile(r"\b(" + "|".join(sorted(FUNKTIONEN)) + r")\s*\(")
    for v in seiten():
        text, herkunft = vorlage_mit_includes(v)
        dateien = {d for _, _, d, _ in herkunft}
        if aufruf.search(text) and BAUSTEIN not in dateien:
            out.append(v)
    return out


def js_tokens(code: str):
    return tokens(code)
