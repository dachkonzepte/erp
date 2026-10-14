"""Daten im HTML der Vorlagen (seit 1.8.102, Vorgabe vom 14.10.2026 Punkt 2; Befund 1.8.100 Nr. 5–8) -- für
tests/test_v407_daten_im_html.py.

Drei Fragen an das JavaScript jeder Vorlage (Tokenizer aus tests/vorlagen_js.py, kein vollständiger JS-Parser):

1. ungeschuetzt(): ein Wert, der ohne esc() in HTML gelangt. HTML ist (a) ein Template-Literal mit Markup ("<" und ein Buchstabe, "/"
   oder "!"), (b) eine Verkettung mit einem String oder Template-Literal mit Markup ('<td>'+x+'</td>'), (c) der Wert eines HTML-Ziels
   (innerHTML, outerHTML, insertAdjacentHTML, document.write). Geprüft wird jedes ${…} in (a), jedes Glied in (b) und der Wert in (c);
   gemeldet wird der kleinste ungeschützte Ausdruck.
2. handler_mit_werten(): ein on…-Attribut in solchem HTML (oder im Markup mit {{ … }}), in dem ein Wert eingesetzt wird -- auch mit
   esc(): esc() schützt das HTML, nicht den Code im Attribut (der Browser dekodiert &#39; vor dem Ausführen). Werte gehören in
   data-Attribute, der Handler wird mit addEventListener angehängt.
3. links_aus_daten(): ein href/src/action (Attribut in solchem HTML, Zuweisung an .href/.src/.action, setAttribute) oder eine
   Navigation (location, location.href, location.assign/replace, window.open), deren Wert nicht mit einem festen erlaubten Anfang
   beginnt (lokaler Pfad "/x" mit x weder "/" noch "\\", "#", "?", mailto:, tel:, http://, https://) und nicht über sichererLink()
   (app/templates/_links.html) bzw. sicheresZiel() (_weiterleitung.html) geht.

Sicher (für 1.) ist ein Wert, dessen Text kein Markup enthalten kann:
- ein HTML-Baustein selbst (Template-Literal oder Verkettung mit Markup): seine eigenen Werte prüft 1. dort, wo er steht;
- esc(…) und jede Funktion der Seite, die wie esc() & < > " ' ersetzt (am Rumpf erkannt), auswahlOptionen() (_auswahl.html),
  encodeURIComponent();
- Literale (Text, Zahl, Regex), true/false/null/undefined/NaN;
- Zahlen und Wahrheitswerte: Number(), parseInt(), parseFloat(), Rechnen mit - * / %, .length, Vergleiche, !x, typeof x, .toFixed() und
  die Zahl-/Datumsformate des Browsers (toLocaleString, toLocaleDateString, toISOString, getFullYear …);
- eine ID: ein Feld "id" oder "…_id" -- außer TEXT_IDS (tests/test_v407_daten_im_html.py prüft, dass jede Spalte und jedes Antwortfeld
  mit Text unter diesem Namen dort steht);
- a ? b : c, a || b, a ?? b, wenn jeder mögliche Wert sicher ist; a && b, wenn b sicher ist (sonst ist das Ergebnis falsch: false, 0,
  '', null, undefined);
- Verkettung und Template-Literal aus sicheren Teilen; .map(f).join(…), [a, b].filter(…).join(…), wenn f bzw. a, b sicher sind;
  Textmethoden (slice, trim, toUpperCase …) auf Sicherem; ein Treffer von .match() mit nur Ziffern in den Gruppen;
- eine Funktion der Seite (oder einer eingebundenen Teilvorlage), deren Rückgabewerte alle sicher sind;
- eine Variable, der in ihrem Gültigkeitsbereich (let/const/var, auch im Kopf von for) nur Sicheres zugewiesen wird;
- ein Parameter: einer benannten Funktion, wenn jede Aufrufstelle Sicheres übergibt (und die Funktion nicht als Wert weitergegeben oder
  aus einem on…-Attribut gerufen wird); eines Rückrufs von map/forEach/filter/some/every/find/findIndex/flatMap und Array.from: der
  Index (zweiter Parameter) immer, das Element, wenn die Elemente sicher sind.
Alles andere -- vor allem ein Feld aus einer Antwort des Servers (x.name) -- ist ungeschützt. Über-Annäherung ist gewollt: lieber
eine Stelle zu viel in der Ausnahmeliste als eine übersehene."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tests.vorlagen_js import SCHLUESSELWOERTER, TEMPLATES, Analyse, Quelle, _handler, _umgebend, analysieren, skript_der_vorlage
from tests.vorlagen_navigation import _ende

ESCAPE = {"esc", "auswahlOptionen", "encodeURIComponent", "encodeURI"}
URL_PRUEFER = {"sichererLink", "sichereBildquelle", "sicheresZiel"}
ZAHL_FUNKTIONEN = {"Number", "parseInt", "parseFloat", "Boolean", "isNaN", "isFinite"}
ZAHL_METHODEN = {"toFixed", "toLocaleString", "toLocaleDateString", "toLocaleTimeString", "toISOString", "getTime", "getFullYear",
                 "getMonth", "getDate", "getDay", "getHours", "getMinutes", "getSeconds", "indexOf", "lastIndexOf", "findIndex",
                 "includes", "some", "every", "test", "startsWith", "endsWith", "localeCompare", "has", "valueOf", "toPrecision",
                 "now"}  # Date.now(), performance.now()
TEXT_METHODEN = {"slice", "substring", "substr", "trim", "trimStart", "trimEnd", "toUpperCase", "toLowerCase", "padStart", "padEnd",
                 "repeat", "at", "charAt", "toString", "normalize"}
ARRAY_FOLGEN = {"filter", "slice", "sort", "reverse", "concat", "flat"}
RUECKRUF_INDEX = {"map", "forEach", "filter", "some", "every", "find", "findIndex", "flatMap"}
# Felder "id"/"…_id", deren Wert Text ist (Import, Outlook, Steuernummer, Audit, Microsoft 365): sie gelten nicht als ID.
TEXT_IDS = {"external_id", "source_external_id", "service_external_id", "vat_id", "entity_id", "graph_tenant_id", "graph_client_id",
            "tenant_id", "client_id", "outlook_event_id", "series_master_id"}
WERTE_SICHER = {"true", "false", "null", "undefined", "NaN", "Infinity"}
URL_ATTRIBUTE = {"href", "src", "action", "formaction", "poster", "xlink:href", "data"}
_ERLAUBTER_ANFANG = re.compile(r"(?:/(?![/\\])|#|\?|mailto:|tel:|https?://)", re.I)
_MARKUP = re.compile(r"<[A-Za-z!/]")
_VERGLEICH = {"==", "===", "!=", "!==", "<", ">", "<=", ">="}
_ZUWEISUNG = {"=", "+="}
_ZIFFERN_GRUPPE = re.compile(r"(?:\\d(?:\{\d+(?:,\d*)?\}|[+*?])?)+")
# Funktionen aus _berlin_date.html: liefern nur Ziffern, "-" und ":" (tests/test_v407_daten_im_html.py prüft das in node).
DATUM_FUNKTIONEN = {"berlinToday", "berlinMonth", "berlinTime", "berlinAddDays"}


def nur_ziffern_gruppen(regex: str) -> bool:
    """Ein Regex-Literal /…/, dessen fangende Gruppen nur Ziffern erfassen (\\d mit Anzahl) -- und das mindestens eine hat."""
    quelle = regex[1:regex.rindex("/")]
    gruppen, i, klasse = 0, 0, False
    while i < len(quelle):
        c = quelle[i]
        if c == "\\":
            i += 2
            continue
        if klasse:
            klasse = c != "]"
        elif c == "[":
            klasse = True
        elif c == "(" and not quelle.startswith("(?", i):
            tiefe, j = 1, i + 1
            while j < len(quelle) and tiefe:
                if quelle[j] == "\\":
                    j += 2
                    continue
                tiefe += {"(": 1, ")": -1}.get(quelle[j], 0)
                j += 1
            if not _ZIFFERN_GRUPPE.fullmatch(quelle[i + 1:j - 1]):
                return False
            gruppen += 1
            i = j
            continue
        i += 1
    return gruppen > 0


@dataclass(frozen=True)
class Fund:
    datei: str
    funktion: str
    ausdruck: str
    stelle: str = field(compare=False)
    pos: int = field(default=-1, compare=False)  # Zeichen in der Datei (gleiche Ausdrücke in einer Zeile zählen einzeln)
    ende: int = field(default=-1, compare=False)  # Ende (ausschließlich) in der Datei

    def schluessel(self) -> str:
        return f"{self.datei} | {self.funktion} | {self.ausdruck}"


def _unescape(roh: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), roh)


class _TextQuelle(Quelle):
    """Ein Skript ohne Vorlagendatei (Tests des Scanners): die Stelle ist die Zeile im Text."""

    def stelle(self, pos: int) -> str:
        return f"{self.name}:{self.text.count(chr(10), 0, pos) + 1}"


@dataclass
class Bereich:
    """Eine Funktion: Parameter (Name -> Position), Rumpf (Token-Indizes), wie sie verwendet wird."""
    start: int          # erster Token der Funktion (function/async/Parameterliste)
    rumpf: tuple        # (s, e) -- Block {…} oder Ausdruck
    params: dict        # Name -> Index (nur einfache Namen; aus Destrukturierung: -1)
    name: str | None    # benannte Funktion
    aufruf: int | None  # Rückruf: öffnende Klammer des Aufrufs, an den er geht
    arg: int = 0        # Rückruf: an welcher Stelle
    block: int = -1     # benannte Funktion: der Block, in dem der Name gilt (-1: oberste Ebene)


class Pruefer:
    """Alle Prüfungen für eine Vorlage. vorlage: die Datei, deren eigene Stellen gemeldet werden; gelesen wird sie samt Includes
    (Funktionen aus Teilvorlagen sind so auflösbar, ihre Stellen meldet die Teilvorlage selbst)."""

    def __init__(self, vorlage: str, *, text: str | None = None):
        """text: statt der Vorlage ein Skript (für Tests des Scanners) -- vorlage ist dann nur der Name."""
        self.vorlage = vorlage
        quelle = skript_der_vorlage(vorlage) if text is None else _TextQuelle(vorlage, text, [(0, len(text), vorlage, 0)])
        self.a: Analyse = analysieren(quelle)
        self.literale = self._literale()
        self.lit_ende = {s: e for s, (_, e) in self.literale.items()}
        self.lit_von_ende = {e: s for s, (_, e) in self.literale.items()}
        self.markup_literale = {s for s, (teile, _) in self.literale.items()
                                if _MARKUP.search("".join(x[1] for x in teile if x[0] == "text"))}
        self.bereiche = self._bereiche()
        self.escaper_ids = self._escaper()
        self.aus_html = {n for _, code in (_handler(vorlage, None) if text is None else _handler(None, text))
                         for n in re.findall(r"([A-Za-z_$][\w$]*)\s*\(", code)}
        self._memo: dict = {}

    # --- Hilfen über die Tokens -----------------------------------------------------------------------------------------
    def _interpol(self, k: int) -> bool:
        return self.a.t[k].art == "punct" and self.a.t[k].wert == "(" and self.a.quelle.text[self.a.t[k].pos] == "$"

    def _literale(self) -> dict:
        t, src, out = self.a.t, self.a.quelle.text, {}
        for i, tok in enumerate(t):
            if tok.art != "tpl" or src[tok.pos - 1] != "`":
                continue
            teile, k = [], i
            while True:
                teile.append(("text", _unescape(t[k].wert)))
                if src[t[k].pos + len(t[k].wert)] == "`":
                    break
                zu = self.a.partner[k + 1]
                teile.append(("expr", k + 2, zu - 1))
                k = zu + 1
            out[i] = (teile, k)
        return out

    def _escaper(self) -> set:
        """Funktionen der Seite (Start-Token), deren Rumpf wie esc() & < > " ' ersetzt."""
        out = set()
        for b in self.bereiche:
            if b.name is None:
                continue
            s, e = b.rumpf
            text = self.a.quelle.text[self.a.t[s].pos:self.a.t[e].pos + len(self.a.t[e].wert) + 1]
            if len(text) < 400 and ".replace(" in text and all(x in text for x in ("&amp;", "&lt;", "&gt;", "&quot;")) \
                    and ("&#39;" in text or "&#x27;" in text):
                out.add(b.start)  # eine kurze Ersetzung wie esc() -- nicht eine Funktion, die nur eine solche enthält
        return out

    def funktionen_fuer(self, name: str, k: int) -> list[Bereich]:
        """Die Funktionen name, die an der Stelle k gelten: benannt in einem Block, der k enthält -- der innerste."""
        kandidaten = [b for b in self.bereiche if b.name == name
                      and (b.block < 0 or b.block < k <= self.a.partner.get(b.block, -1))]
        if not kandidaten:
            return []
        innen = max(b.block for b in kandidaten)
        return [b for b in kandidaten if b.block == innen]

    def ist_escaper(self, name: str, k: int) -> bool:
        fs = self.funktionen_fuer(name, k)
        return all(b.start in self.escaper_ids for b in fs) if fs else name in ESCAPE

    def _eigen(self, k: int) -> bool:
        """Stellen aller Dateien des Zusammenhangs werden gemeldet (eine Teilvorlage in jeder Seite, die sie einbindet --
        alle_funde() fasst zusammen); ausgenommen _speichern.html (Baustein, eigene Tests)."""
        return self.a.quelle.datei(self.a.t[k].pos) not in (None, "_speichern.html")

    def bereich(self, s: int, e: int) -> tuple[int, int]:
        """Anfang und Ende (ausschließlich) der Tokens s … e im Text des Skripts -- mit Anführungszeichen und Backticks."""
        t = self.a.t
        start = t[s].pos - (1 if s in self.literale else 0)  # ein String beginnt mit seinem Anführungszeichen
        ende = t[e].pos + len(t[e].wert) + {"str": 2, "tpl": 1}.get(t[e].art, 0)
        return start, ende

    def _text(self, s: int, e: int) -> str:
        if s > e:
            return ""
        start, ende = self.bereich(s, e)
        return re.sub(r"\s+", " ", self.a.quelle.text[start:ende]).strip()

    def _oben(self, s: int, e: int):
        """Token-Indizes auf oberster Ebene in [s, e] -- Klammern und Template-Literale als ein Glied (ihr erster Token)."""
        t, k = self.a.t, s
        while k <= e:
            yield k
            if t[k].art == "punct" and t[k].wert in "([{" and k in self.a.partner:
                k = self.a.partner[k] + 1
            elif k in self.lit_ende:
                k = self.lit_ende[k] + 1
            else:
                k += 1

    def _endet_operand(self, k: int) -> bool:
        tok = self.a.t[k]
        if tok.art in ("num", "str", "regex", "tpl"):
            return True
        if tok.art == "name":
            return tok.wert not in SCHLUESSELWOERTER or tok.wert in WERTE_SICHER or tok.wert == "this"
        return tok.wert in (")", "]", "}", "++", "--")

    def _binaer(self, oben: list, idx: int) -> bool:
        if idx == 0:
            return False
        vor = oben[idx - 1]
        if self.a.t[vor].art == "punct" and self.a.t[vor].wert in "([{":
            return True
        return vor in self.lit_ende or self._endet_operand(vor)

    def _kette_mit_markup(self, s: int, e: int) -> bool:
        """[s, e] ist eine Verkettung mit + auf oberster Ebene, in der ein Glied ein String oder Template-Literal mit Markup ist."""
        t = self.a.t
        oben = list(self._oben(s, e))
        if not any(t[k].art == "punct" and t[k].wert == "+" and self._binaer(oben, i) for i, k in enumerate(oben)):
            return False
        return any((t[k].art == "str" and _MARKUP.search(_unescape(t[k].wert))) or k in self.markup_literale for k in oben)

    # --- Funktionen und Bindungen -------------------------------------------------------------------------------------------
    def _params(self, s: int, e: int) -> dict:
        """Parameterliste von s bis e (ohne Klammern): Name -> Position; aus Destrukturierung -1."""
        t, out, pos, k = self.a.t, {}, 0, s
        while k <= e:
            tok = t[k]
            if tok.art == "punct" and tok.wert in ("{", "["):
                for j in range(k + 1, self.a.partner[k]):
                    if t[j].art == "name" and t[j + 1].wert in (",", "}", "]", "=", ":") and t[j - 1].wert != ":":
                        out.setdefault(t[j].wert, -(10 + pos))  # aus Destrukturierung des Parameters an Stelle pos
                k = self.a.partner[k] + 1
                continue
            if tok.art == "name" and tok.wert not in SCHLUESSELWOERTER and (k == s or t[k - 1].wert in (",", "...")):
                out[tok.wert] = pos if t[k - 1].wert != "..." else -1
            if tok.art == "punct" and tok.wert == "," and self.a.eltern[k] == self.a.eltern[s]:
                pos += 1
            if tok.art == "punct" and tok.wert in ("(",) and k in self.a.partner:
                k = self.a.partner[k] + 1
                continue
            k += 1
        return out

    def _bereiche(self) -> list[Bereich]:
        t, a, out = self.a.t, self.a, []
        for k, tok in enumerate(t):
            if tok.art == "name" and tok.wert == "function":
                j = k + 1
                name = None
                if t[j].art == "name":
                    name, j = t[j].wert, j + 1
                if t[j].wert != "(":
                    continue
                zu = a.partner[j]
                if zu + 1 >= len(t) or t[zu + 1].wert != "{":
                    continue
                anfang = k - 1 if k > 0 and t[k - 1].wert == "async" else k
                block = a.eltern[k]
                if name is None and anfang >= 2 and t[anfang - 1].wert == "=" and t[anfang - 2].art == "name" \
                        and (anfang < 3 or t[anfang - 3].wert not in (".", "?.")):
                    name, block = t[anfang - 2].wert, a.eltern[anfang - 2]
                out.append(self._bereich(anfang, (zu + 1, a.partner[zu + 1]), self._params(j + 1, zu - 1), name, block))
            elif tok.art == "punct" and tok.wert == "=>":
                if t[k - 1].wert == ")" and t[k - 1].art == "punct":
                    auf = a.partner[k - 1]
                    params = self._params(auf + 1, k - 2)
                    anfang = auf - 1 if auf > 0 and t[auf - 1].wert == "async" else auf
                elif t[k - 1].art == "name":
                    params = {t[k - 1].wert: 0}
                    anfang = k - 2 if k > 1 and t[k - 2].wert == "async" else k - 1
                else:
                    continue
                if t[k + 1].wert == "{" and t[k + 1].art == "punct":
                    rumpf = (k + 1, a.partner[k + 1])
                else:
                    rumpf = (k + 1, _ende(a, k + 1))
                name, block = None, -1
                if anfang >= 2 and t[anfang - 1].wert == "=" and t[anfang - 2].art == "name" \
                        and (anfang < 3 or t[anfang - 3].wert not in (".", "?.")):
                    name, block = t[anfang - 2].wert, a.eltern[anfang - 2]
                out.append(self._bereich(anfang, rumpf, params, name, block))
        return out

    def _bereich(self, anfang: int, rumpf: tuple, params: dict, name: str | None, block: int = -1) -> Bereich:
        a = self.a
        b = Bereich(anfang, rumpf, params, name, None, 0, block)
        if name is None:
            auf = a.eltern[anfang]
            if auf >= 0 and a.t[auf].wert == "(" and a.aufruf_name(auf) is not None:
                for i, (s, e) in enumerate(a.argumente(auf)):
                    if s == anfang:
                        b.aufruf, b.arg = auf, i
        return b

    def _bindung(self, name: str, k: int):
        """Die innerste Bindung von name, die k sieht: ("param", Bereich, Position) | ("var", Block) | ("for", Kopf) | None."""
        beste, beste_start = None, -2
        for b in self.bereiche:
            if name in b.params and b.rumpf[0] <= k <= b.rumpf[1] and b.start > beste_start:
                beste, beste_start = ("param", b, b.params[name]), b.start
        t = self.a.t
        block = self.a.eltern[k]
        while True:
            if block < 0 or t[block].wert in ("{", "("):
                if block > beste_start and self._deklariert_in(name, block) is not None:
                    if block < 0 or t[block].wert == "{":
                        return ("var", block) if block > beste_start else beste
                    return ("for", block)
                if block < 0 and beste is None and self._deklariert_in(name, -1) is not None:
                    return ("var", -1)
            if block < 0:
                break
            block = self.a.eltern[block]
        return beste

    def _deklariert_in(self, name: str, block: int) -> int | None:
        """Position der Deklaration let/const/var name direkt in block (-1: oberste Ebene; "(": Kopf von for)."""
        t = self.a.t
        if block >= 0 and t[block].wert == "(" and not (block > 0 and t[block - 1].wert == "for"):
            return None
        start, ende = (block + 1, self.a.partner[block] - 1) if block >= 0 else (0, len(t) - 1)
        for j in range(start, ende + 1):
            if self.a.eltern[j] != block or t[j].art != "name" or t[j].wert != name:
                continue
            if t[j + 1].wert not in ("=", ",", ";", "of", "in", ")") or t[j - 1].wert in (".", "?."):
                continue
            k = j - 1
            while k >= start and self.a.eltern[k] == block and not (t[k].art == "punct" and t[k].wert in (";", "{", "}")):
                if t[k].art == "name" and t[k].wert in ("let", "const", "var"):
                    return j
                if t[k].art == "punct" and t[k].wert in ("(", "[", "{") or k in self.lit_ende:
                    pass
                k -= 1
                while k >= start and self.a.eltern[k] != block:
                    k -= 1
        return None

    # --- 1. sicher ---------------------------------------------------------------------------------------------------------
    def unsicher(self, s: int, e: int) -> list[tuple[int, int]]:
        """Die ungeschützten Teil-Ausdrücke (Token-Bereiche) von [s, e]; leer = sicher."""
        t = self.a.t
        if s > e:
            return []
        while t[s].art == "punct" and t[s].wert == "(" and self.a.partner.get(s) == e and not self._interpol(s):
            s, e = s + 1, e - 1
            if s > e:
                return []
        if s in self.markup_literale and self.lit_ende[s] == e:
            return []  # HTML-Baustein: seine Werte prüft ungeschuetzt() am Baustein selbst
        if s in self.literale and self.lit_ende[s] == e:
            return self._literal_unsicher(s)  # Template-Literal ohne Markup: seine Werte einzeln
        oben = list(self._oben(s, e))
        ops = [k for k in oben if t[k].art == "punct"]
        werte = [t[k].wert for k in ops]
        if "," in werte:
            return self.unsicher(max(k for k in ops if t[k].wert == ",") + 1, e)
        if "=>" in werte:
            return [(s, e)]
        for k in ops:
            if t[k].wert in _ZUWEISUNG | {"-=", "*=", "/=", "||=", "??=", "&&="}:
                return self.unsicher(k + 1, e)
        if "?" in werte:
            q = next(k for k in ops if t[k].wert == "?")
            doppel = self._doppelpunkt(ops, q)
            if doppel is None:
                return [(s, e)]
            return self.unsicher(q + 1, doppel - 1) + self.unsicher(doppel + 1, e)
        for gruppe, nur_letztes in ((("??", "||"), False), (("&&",), True)):
            trenner = [k for k in ops if t[k].wert in gruppe]
            if trenner:
                grenzen = [s - 1, *trenner, e + 1]
                teile = [(grenzen[j] + 1, grenzen[j + 1] - 1) for j in range(len(grenzen) - 1)]
                return [b for ts, te in (teile[-1:] if nur_letztes else teile) for b in self.unsicher(ts, te)]
        if any(w in _VERGLEICH for w in werte) or any(t[k].art == "name" and t[k].wert in ("instanceof", "in") for k in oben[1:]):
            return []
        if self._kette_mit_markup(s, e):
            return []  # HTML-Baustein (Verkettung): seine Glieder prüft ungeschuetzt() am Baustein selbst
        plus = [k for i, k in enumerate(oben) if t[k].art == "punct" and t[k].wert == "+" and self._binaer(oben, i)]
        if plus:
            grenzen = [s - 1, *plus, e + 1]
            out = []
            for j in range(len(grenzen) - 1):
                ts, te = grenzen[j] + 1, grenzen[j + 1] - 1
                teil_oben = list(self._oben(ts, te))
                if any(t[k].art == "punct" and t[k].wert in ("-", "*", "/", "%", "**") and self._binaer(teil_oben, i)
                       for i, k in enumerate(teil_oben)):
                    continue
                out += self.unsicher(ts, te)
            return out
        if any(t[k].wert in ("-", "*", "/", "%", "**") and self._binaer(oben, i) for i, k in enumerate(oben) if t[k].art == "punct"):
            return []
        erster = t[s]
        if erster.art == "punct" and erster.wert in ("!", "-", "+", "~"):
            return []
        if erster.art == "name" and erster.wert in ("typeof", "void", "delete"):
            return []
        if erster.art == "name" and erster.wert == "await":
            return self.unsicher(s + 1, e)
        if erster.art == "name" and erster.wert == "new":
            if s + 1 <= e and t[s + 1].wert == "Date":
                return []
            if s + 3 <= e and t[s + 1].wert == "Intl" and t[e].wert == ")" and t[self.a.partner[e] - 1].wert in ("format", "formatRange"):
                return []  # new Intl.NumberFormat(…).format(…): Zahl bzw. Datum im Format des Browsers
            return [(s, e)]
        if self._kette_sicher(s, e):
            return []
        if s == e and t[s].art == "name":
            wurzeln = self._variable_wurzeln(t[s].wert, s)
            if wurzeln is not None:
                return wurzeln
        return [(s, e)]

    def _traegt_markup(self, s: int, e: int) -> bool:
        t = self.a.t
        return any(k in self.markup_literale or (t[k].art == "str" and _MARKUP.search(_unescape(t[k].wert))) for k in range(s, e + 1))

    def _variable_wurzeln(self, name: str, k: int):
        """Trägt die Variable name HTML (eine Zuweisung enthält Markup), die ungeschützten Teile ihrer Zuweisungen -- dort wird
        behoben, nicht an der Verwendung (dort esc() hieße das Markup maskieren); sonst None."""
        bindung = self._bindung(name, k)
        if bindung is None or bindung[0] != "var":
            return None
        schluessel = ("wurzeln", bindung[1], name)
        if schluessel in self._memo:
            return self._memo[schluessel] if self._memo[schluessel] is not None else []
        self._memo[schluessel] = None
        block, t = bindung[1], self.a.t
        start, ende = (block + 1, self.a.partner[block] - 1) if block >= 0 else (0, len(t) - 1)
        werte = [(j + 2, _ende(self.a, j + 2)) for j in range(start, ende)
                 if t[j].art == "name" and t[j].wert == name and (j == 0 or t[j - 1].wert not in (".", "?."))
                 and t[j + 1].art == "punct" and t[j + 1].wert in _ZUWEISUNG]
        if not any(self._traegt_markup(vs, ve) for vs, ve in werte):
            del self._memo[schluessel]
            return None
        wurzeln = [b for vs, ve in werte for b in self.unsicher(vs, ve)]
        self._memo[schluessel] = wurzeln
        return wurzeln

    def _doppelpunkt(self, ops: list, q: int) -> int | None:
        t, tiefe = self.a.t, 0
        for k in ops:
            if k <= q:
                continue
            if t[k].wert == "?":
                tiefe += 1
            elif t[k].wert == ":":
                if tiefe == 0:
                    return k
                tiefe -= 1
        return None

    def _primaer_ende(self, s: int) -> int:
        t = self.a.t
        if s in self.lit_ende:
            return self.lit_ende[s]
        if t[s].art == "punct" and t[s].wert in "([{":
            return self.a.partner[s]
        return s

    def _suffixe(self, p: int, e: int):
        """Suffixe nach dem Primärausdruck bis e: ("prop", name, k) | ("index", k) | ("call", k); None, wenn etwas anderes folgt."""
        t, k, out = self.a.t, p + 1, []
        while k <= e:
            if t[k].art == "punct" and t[k].wert in (".", "?.") and k + 1 <= e and t[k + 1].art == "name":
                out.append(("prop", t[k + 1].wert, k + 1))
                k += 2
            elif t[k].art == "punct" and t[k].wert == "?." and k + 1 <= e and t[k + 1].wert in ("(", "["):
                k += 1
            elif t[k].art == "punct" and t[k].wert == "[":
                out.append(("index", k))
                k = self.a.partner[k] + 1
            elif t[k].art == "punct" and t[k].wert == "(" and not self._interpol(k):
                out.append(("call", k))
                k = self.a.partner[k] + 1
            else:
                return None
        return out

    def _kette_sicher(self, s: int, e: int) -> bool:
        p = self._primaer_ende(s)
        suffixe = self._suffixe(p, e)
        return suffixe is not None and self._wert_sicher(s, p, suffixe)

    def _wert_sicher(self, s: int, p: int, suffixe: list) -> bool:
        t = self.a.t
        if not suffixe:
            return self._primaer_sicher(s, p)
        letzter = suffixe[-1]
        if letzter[0] == "prop":
            name = letzter[1]
            return name in ("length", "size") or ((name == "id" or name.endswith("_id")) and name not in TEXT_IDS)
        if letzter[0] == "index":
            if len(suffixe) != 1:
                return False
            if t[s].art == "punct" and t[s].wert in ("{", "["):  # {offen: '…', …}[status]
                return self._objekt_werte_sicher(s, p) if t[s].wert == "{" else self._elemente_sicher(s, p, [])
            if p != s or t[s].art != "name":
                return False
            return self._ziffern_treffer(t[s].wert, s) or self._objekt_werte_sicher(s, s) or self._elemente_sicher(s, s, [])
        auf = letzter[1]
        if len(suffixe) == 1:
            if p == s and t[s].art == "name":
                return self._aufruf_sicher(t[s].wert, s, auf)
            return False
        vor = suffixe[-2]
        if vor[0] != "prop":
            return False
        m = vor[1]
        empf = (s, p, suffixe[:-2])
        if p == s and len(suffixe) == 2 and t[s].art == "name":
            if t[s].wert == "Math" or (t[s].wert == "Number" and m in ("isFinite", "isInteger", "parseFloat", "parseInt")):
                return True
            if t[s].wert in ("JSON", "Object"):
                return False
        if m in ZAHL_METHODEN:
            return True
        if m == "join":
            return self._elemente_sicher(*empf)
        if m == "map":
            return self._rueckgaben_sicher_arg(auf)
        if m in TEXT_METHODEN:
            return self._wert_sicher(*empf)
        if m in ("replace", "replaceAll"):
            args = self.a.argumente(auf)
            return len(args) == 2 and self._wert_sicher(*empf) and not self.unsicher(*args[1])
        return False

    def _primaer_sicher(self, s: int, p: int) -> bool:
        tok = self.a.t[s]
        if tok.art in ("str", "num", "regex"):
            return True
        if s in self.literale:
            return not self._literal_unsicher(s)
        if tok.art == "name":
            return tok.wert in WERTE_SICHER or self._name_sicher(tok.wert, s)
        if tok.art == "punct" and tok.wert == "[":
            return all(self._element_sicher(x, y) for x, y in self._elemente(s))
        if tok.art == "punct" and tok.wert == "{":
            return self._objekt_werte_sicher(s, p)
        return False

    def _element_sicher(self, x: int, y: int) -> bool:
        """Ein Element eines Array-Literals; ...a nur, wenn die Elemente von a sicher sind."""
        if self.a.t[x].wert == "...":
            return self._ausdruck_elemente_sicher(x + 1, y)
        return not self.unsicher(x, y)

    def _objekt_werte_sicher(self, s: int, e: int) -> bool:
        """Ein Objekt-Literal {…} (oder eine Variable, der nur solche zugewiesen werden), dessen Schlüssel und Werte sicher sind --
        eine feste Tabelle wie {offen: 'Offen', …}."""
        t = self.a.t
        if t[s].art == "punct" and t[s].wert == "{" and self.a.partner.get(s) == e:
            for es, ee in self._elemente(s):
                if t[es].wert == "...":
                    return False
                doppel = next((k for k in self._oben(es, ee) if t[k].art == "punct" and t[k].wert == ":"), None)
                if doppel is None:
                    if es == ee and t[es].art == "name" and self._name_sicher(t[es].wert, es):
                        continue
                    return False
                if t[es].art == "punct" and t[es].wert == "[" and self.unsicher(es + 1, self.a.partner[es] - 1):
                    return False
                if self.unsicher(doppel + 1, ee):
                    return False
            return True
        if s == e and t[s].art == "name":
            name = t[s].wert
            return self._memo_get(("objekt", name, s), lambda: self._variable_alle(
                name, s, lambda vs, ve: self._objekt_werte_sicher(vs, ve)) and self._eigenschaften_sicher(name, s))
        return False

    def _eigenschaften_sicher(self, name: str, k: int) -> bool:
        """Was das Objekt name in seinem Gültigkeitsbereich sonst bekommt: name[x] = …, name.x = …"""
        bindung = self._bindung(name, k)
        if bindung is None or bindung[0] != "var":
            return False
        block, t = bindung[1], self.a.t
        start, ende = (block + 1, self.a.partner[block] - 1) if block >= 0 else (0, len(t) - 1)
        for j in range(start, ende):
            if t[j].art != "name" or t[j].wert != name or (j > 0 and t[j - 1].wert in (".", "?.")):
                continue
            if t[j + 1].art == "punct" and t[j + 1].wert == "[":
                zu = self.a.partner[j + 1]
            elif t[j + 1].art == "punct" and t[j + 1].wert == "." and t[j + 2].art == "name":
                zu = j + 2
            else:
                continue
            if t[zu + 1].art == "punct" and t[zu + 1].wert in _ZUWEISUNG and self.unsicher(zu + 2, _ende(self.a, zu + 2)):
                return False
        return True

    def _elemente(self, auf: int) -> list[tuple[int, int]]:
        t, zu = self.a.t, self.a.partner[auf]
        out, start = [], auf + 1
        for k in range(auf + 1, zu):
            if self.a.eltern[k] == auf and t[k].art == "punct" and t[k].wert == ",":
                out.append((start, k - 1))
                start = k + 1
        if start <= zu - 1:
            out.append((start, zu - 1))
        return out

    def _elemente_sicher(self, s: int, p: int, suffixe: list) -> bool:
        """Sind die Elemente des Arrays [s … Ende der Suffixe] sicher?"""
        t = self.a.t
        if not suffixe:
            if t[s].art == "punct" and t[s].wert == "[":
                return all(self._element_sicher(x, y) for x, y in self._elemente(s))
            if t[s].art == "name":
                bindung = self._bindung(t[s].wert, s)
                if bindung is not None and bindung[0] == "param":
                    b, stelle = bindung[1], bindung[2]
                    if stelle < 0 or b.aufruf is not None or b.name is None or b.name in self.aus_html:
                        return False
                    return self._memo_get(("param-elemente", b.name, stelle),
                                          lambda: self._aufrufstellen_sicher(b.name, stelle, elemente=True))
                return self._memo_get(("elemente", t[s].wert, s), lambda: self._variable_alle(
                    t[s].wert, s, lambda vs, ve: self._ausdruck_elemente_sicher(vs, ve)) and self._hinzugefuegt_sicher(t[s].wert, s))
            return False
        letzter = suffixe[-1]
        if letzter[0] != "call" or len(suffixe) < 2 or suffixe[-2][0] != "prop":
            return False
        m = suffixe[-2][1]
        if m in ("map", "flatMap"):
            return self._rueckgaben_sicher_arg(letzter[1])
        if m in ARRAY_FOLGEN:
            if m == "concat" and any(self.unsicher(*arg) for arg in self.a.argumente(letzter[1])):
                return False
            return self._elemente_sicher(s, p, suffixe[:-2])
        if m == "from" and len(suffixe) == 2 and t[s].wert == "Array":
            args = self.a.argumente(letzter[1])
            return len(args) == 2 and self._rueckgaben_sicher_arg(letzter[1], 1)
        if m in ("entries", "keys", "values") and len(suffixe) == 2 and t[s].wert == "Object":
            args = self.a.argumente(letzter[1])
            return len(args) == 1 and self._objekt_werte_sicher(*args[0])
        return False

    def _hinzugefuegt_sicher(self, name: str, k: int) -> bool:
        """Was das Array name in seinem Gültigkeitsbereich sonst bekommt: name.push(…)/unshift(…)/splice(a, b, …), name[i] = …"""
        bindung = self._bindung(name, k)
        if bindung is None or bindung[0] != "var":
            return False
        block, t = bindung[1], self.a.t
        start, ende = (block + 1, self.a.partner[block] - 1) if block >= 0 else (0, len(t) - 1)
        for j in range(start, ende):
            if t[j].art != "name" or t[j].wert != name or (j > 0 and t[j - 1].wert in (".", "?.")):
                continue
            if t[j + 1].wert in (".", "?.") and t[j + 2].wert in ("push", "unshift", "splice") and t[j + 3].wert == "(":
                args = self.a.argumente(j + 3)
                if t[j + 2].wert == "splice":
                    args = args[2:]
                if any(t[a_s].wert == "..." or self.unsicher(a_s, a_e) for a_s, a_e in args):
                    return False
            elif t[j + 1].wert == "[" and t[j + 1].art == "punct":
                zu = self.a.partner[j + 1]
                if t[zu + 1].art == "punct" and t[zu + 1].wert in _ZUWEISUNG and self.unsicher(zu + 2, _ende(self.a, zu + 2)):
                    return False
        return True

    def _ausdruck_elemente_sicher(self, s: int, e: int) -> bool:
        p = self._primaer_ende(s)
        suffixe = self._suffixe(p, e)
        return suffixe is not None and self._elemente_sicher(s, p, suffixe)

    def _rueckgaben_sicher_arg(self, auf: int, idx: int = 0) -> bool:
        """Das Argument idx des Aufrufs ist eine Funktion (Pfeil, function, Name): sind ihre Rückgaben sicher?"""
        args = self.a.argumente(auf)
        if len(args) <= idx:
            return False
        s, e = args[idx]
        t = self.a.t
        if s == e and t[s].art == "name":
            return self._aufruf_sicher(t[s].wert, s, None)
        b = next((b for b in self.bereiche if b.start == s), None)
        return b is not None and self._rumpf_sicher(b.rumpf)

    def _rumpf_sicher(self, rumpf: tuple) -> bool:
        t = self.a.t
        rs, re_ = rumpf
        if not (t[rs].wert == "{" and t[rs].art == "punct" and self.a.partner.get(rs) == re_):
            return not self.unsicher(rs, re_)
        for r in range(rs + 1, re_):
            if t[r].art != "name" or t[r].wert != "return" or not self._gehoert_zu(r, rs):
                continue
            if t[r + 1].art == "punct" and t[r + 1].wert in (";", "}"):
                continue
            if self.unsicher(r + 1, _ende(self.a, r + 1)):
                return False
        return True

    def _gehoert_zu(self, r: int, rumpf: int) -> bool:
        k = self.a.eltern[r]
        while k != rumpf and k >= 0:
            if any(b.rumpf[0] == k for b in self.bereiche):
                return False
            k = self.a.eltern[k]
        return k == rumpf

    def _memo_get(self, schluessel, rechnen) -> bool:
        if schluessel in self._memo:
            return self._memo[schluessel] is not False
        self._memo[schluessel] = None  # in Arbeit: optimistisch
        wert = bool(rechnen())
        self._memo[schluessel] = wert
        return wert

    def _aufruf_sicher(self, name: str, k: int, auf: int | None) -> bool:
        """Ist das Ergebnis eines Aufrufs von name an der Stelle k sicher? Die Funktion wird im Gültigkeitsbereich aufgelöst."""
        if name in ZAHL_FUNKTIONEN or name in DATUM_FUNKTIONEN:
            return True
        fs = self.funktionen_fuer(name, k)
        if not fs:
            if name in ESCAPE:
                return True
            if name == "String" and auf is not None:
                args = self.a.argumente(auf)
                return len(args) == 1 and not self.unsicher(*args[0])
            return False
        if all(b.start in self.escaper_ids for b in fs):
            return True
        return self._memo_get(("funktion", tuple(b.start for b in fs)), lambda: all(self._rumpf_sicher(b.rumpf) for b in fs))

    def _name_sicher(self, name: str, k: int) -> bool:
        bindung = self._bindung(name, k)
        if bindung is None:
            return False
        if bindung[0] == "var":
            return self._memo_get(("var", bindung[1], name), lambda: self._variable_alle(
                name, k, lambda vs, ve: not self.unsicher(vs, ve)))
        if bindung[0] == "for":
            return self._for_sicher(name, bindung[1])
        return self._param_sicher(bindung[1], bindung[2])

    def _variable_alle(self, name: str, k: int, pruefe) -> bool:
        """Jede Zuweisung an name in seinem Gültigkeitsbereich erfüllt pruefe(s, e)."""
        bindung = self._bindung(name, k)
        if bindung is None or bindung[0] != "var":
            return False
        block, t = bindung[1], self.a.t
        start, ende = (block + 1, self.a.partner[block] - 1) if block >= 0 else (0, len(t) - 1)
        for j in range(start, ende):
            if t[j].art != "name" or t[j].wert != name or (j > 0 and t[j - 1].wert in (".", "?.")):
                continue
            op = t[j + 1]
            if op.art == "punct" and op.wert in _ZUWEISUNG and not pruefe(j + 2, _ende(self.a, j + 2)):
                return False
        return True

    def _for_sicher(self, name: str, kopf: int) -> bool:
        """Variable aus dem Kopf von for: for(let i=0;…) über die Zuweisungen; for(const x of a) über die Elemente von a."""
        t, zu = self.a.t, self.a.partner[kopf]
        for j in range(kopf + 1, zu):
            if t[j].art == "name" and t[j].wert == name and t[j + 1].wert == "of":
                return self._ausdruck_elemente_sicher(j + 2, zu - 1)
        werte = [not self.unsicher(j + 2, _ende(self.a, j + 2)) for j in range(kopf + 1, zu)
                 if t[j].art == "name" and t[j].wert == name and t[j + 1].art == "punct" and t[j + 1].wert in _ZUWEISUNG]
        return bool(werte) and all(werte)

    def _param_sicher(self, b: Bereich, pos: int) -> bool:
        t = self.a.t
        if pos <= -10:  # aus Destrukturierung: ([k, l]) => …, ({a}) => … -- sicher, wenn das Element es ganz ist
            stelle = -(pos + 10)
            if b.aufruf is not None and stelle == 0 and b.arg == 0 and self.a.ist_methode(b.aufruf) \
                    and self.a.aufruf_name(b.aufruf) in RUECKRUF_INDEX:
                empf_ende = b.aufruf - 3
                return self._ausdruck_elemente_sicher(self._operand_anfang(empf_ende), empf_ende)
            return False
        if pos < 0:
            return False
        if b.aufruf is not None:
            m = self.a.aufruf_name(b.aufruf)
            if self.a.ist_methode(b.aufruf) and m in RUECKRUF_INDEX and b.arg == 0:
                if pos == 1:
                    return True
                if pos == 0:
                    empf_ende = b.aufruf - 3
                    empf_start = self._operand_anfang(empf_ende)
                    return self._ausdruck_elemente_sicher(empf_start, empf_ende)
            if m == "from" and b.arg == 1 and t[b.aufruf - 2].wert == "." and t[b.aufruf - 3].wert == "Array":
                if pos == 1:
                    return True
                args = self.a.argumente(b.aufruf)
                if pos == 0 and args and t[args[0][0]].wert == "{":
                    return True  # Array.from({length:n}, …): die Elemente sind undefined
            return False
        if b.name is None or b.name in self.aus_html:
            return False
        return self._memo_get(("param", b.name, pos), lambda: self._aufrufstellen_sicher(b.name, pos))

    def _aufrufstellen_sicher(self, name: str, pos: int, elemente: bool = False) -> bool:
        """Jede Aufrufstelle von name übergibt an Stelle pos Sicheres (elemente: ein Array mit sicheren Elementen)."""
        t = self.a.t
        for k, tok in enumerate(t):
            if tok.art != "name" or tok.wert != name or (k > 0 and t[k - 1].wert in (".", "?.", "function")):
                continue
            if k + 1 < len(t) and t[k + 1].wert == "=" and t[k + 1].art == "punct":
                continue  # Definition name = …
            if k > 0 and t[k - 1].wert in ("const", "let", "var"):
                continue
            if k + 1 < len(t) and t[k + 1].wert == "(" and t[k + 1].art == "punct":
                args = self.a.argumente(k + 1)
                if pos < len(args) and (not self._ausdruck_elemente_sicher(*args[pos]) if elemente else self.unsicher(*args[pos])):
                    return False
                continue
            auf = self.a.eltern[k]
            if auf >= 0 and t[auf].wert == "(" and self.a.ist_methode(auf) and self.a.aufruf_name(auf) in RUECKRUF_INDEX \
                    and not elemente:
                if pos == 1:
                    continue
                if pos == 0 and self._ausdruck_elemente_sicher(self._operand_anfang(auf - 3), auf - 3):
                    continue
            return False  # als Wert weitergegeben
        return True  # jede Aufrufstelle übergibt Sicheres (keine: die Funktion läuft in diesem Zusammenhang nicht)

    def _ziffern_treffer(self, name: str, k: int) -> bool:
        """name ist das Ergebnis von x.match(/…/) mit nur Ziffern in den Gruppen (m[1] ist dann Ziffern oder undefined)."""
        def pruefe(vs, ve):
            t = self.a.t
            return any(t[j].art == "name" and t[j].wert == "match" and t[j - 1].wert in (".", "?.") and t[j + 1].wert == "("
                       and t[j + 2].art == "regex" and nur_ziffern_gruppen(t[j + 2].wert) for j in range(vs, ve + 1)) \
                and not any(t[j].wert in ("||", "??") and t[j].art == "punct" for j in self._oben(vs, ve))
        return self._memo_get(("treffer", name, k), lambda: self._variable_alle(name, k, pruefe))

    def _literal_unsicher(self, s: int) -> list[tuple[int, int]]:
        teile, _ = self.literale[s]
        return [b for teil in teile if teil[0] == "expr" for b in self.unsicher(teil[1], teil[2])]

    # --- HTML-Stücke ------------------------------------------------------------------------------------------------------
    def _operand_anfang(self, k: int) -> int:
        t = self.a.t
        while True:
            if k in self.lit_von_ende:
                k = self.lit_von_ende[k]
            elif t[k].art == "punct" and t[k].wert in (")", "]", "}"):
                k = self.a.partner[k]
            if k - 1 >= 0 and t[k - 1].art == "punct" and t[k - 1].wert in (".", "?."):
                k -= 2
                continue
            if (t[k].art == "punct" and t[k].wert in ("(", "[") and k - 1 >= 0 and not self._interpol(k)
                    and self._endet_operand(k - 1) and not (t[k - 1].art == "name" and t[k - 1].wert in SCHLUESSELWOERTER)):
                k -= 1
                continue
            break
        while k - 1 >= 0 and ((t[k - 1].art == "punct" and t[k - 1].wert in ("!", "~"))
                              or (t[k - 1].art == "name" and t[k - 1].wert in ("typeof", "new", "await", "void"))):
            k -= 1
        return k

    def _operand_ende(self, k: int) -> int:
        t = self.a.t
        while k < len(t) and t[k].art == "name" and t[k].wert in ("typeof", "new", "await", "void"):
            k += 1
        k = self._primaer_ende(k) + 1
        while k < len(t):
            if t[k].art == "punct" and t[k].wert in (".", "?.") and k + 1 < len(t) and t[k + 1].art == "name":
                k += 2
            elif t[k].art == "punct" and t[k].wert in ("[", "(") and not self._interpol(k):
                k = self.a.partner[k] + 1
            elif t[k].art == "punct" and t[k].wert == "?." and k + 1 < len(t) and t[k + 1].wert in ("(", "["):
                k += 1
            else:
                break
        return k - 1

    def stuecke(self):
        """(Teile, Anker) je HTML-Stück: Template-Literal mit Markup und Verkettung mit einem String oder Template-Literal mit Markup.
        Teile: ("text", str) oder ("expr", s, e) -- ein Template-Literal in einer Verkettung wird eingesetzt."""
        t, gesehen = self.a.t, set()
        anker = [i for i, tok in enumerate(t) if tok.art == "str" and _MARKUP.search(_unescape(tok.wert))]
        anker = sorted(anker + list(self.markup_literale))
        for i in anker:
            if i in gesehen:
                continue
            ebene = self.a.eltern[i]
            anfang, ende = self._operand_anfang(i), self._operand_ende(i)
            while anfang >= 2 and t[anfang - 1].art == "punct" and t[anfang - 1].wert == "+" and self.a.eltern[anfang - 1] == ebene \
                    and self._endet_operand(anfang - 2):
                anfang = self._operand_anfang(anfang - 2)
            while ende + 2 < len(t) and t[ende + 1].art == "punct" and t[ende + 1].wert == "+" and self.a.eltern[ende + 1] == ebene:
                ende = self._operand_ende(ende + 2)
            glieder, k = [], anfang
            while k <= ende:
                g_ende = self._operand_ende(k)
                glieder.append((k, g_ende))
                k = g_ende + 2
            teile = []
            for g_s, g_e in glieder:
                if g_s == g_e and t[g_s].art == "str":
                    teile.append(("text", _unescape(t[g_s].wert)))
                    gesehen.add(g_s)
                elif g_s in self.literale and self.lit_ende[g_s] == g_e:
                    teile += self.literale[g_s][0]
                    gesehen.add(g_s)
                else:
                    teile.append(("expr", g_s, g_e))
            if i in self.markup_literale or len(glieder) > 1:
                yield teile, anfang

    def kontexte(self, teile):
        """Je Ausdruck eines Stücks der HTML-Zusammenhang: ("text",), ("tag",), ("kommentar",) oder ("attr", name, anfang) --
        anfang = fester Text des Attributwerts vor diesem Ausdruck (None, wenn schon ein Wert davor steht)."""
        zustand, attr, wert, anfang_fest = "daten", "", "", True
        out = []
        for teil in teile:
            if teil[0] == "expr":
                if zustand in ("wert_dq", "wert_sq", "wert_oq", "vor_wert"):
                    out.append((teil, ("attr", attr.lower(), wert if anfang_fest else None)))
                    anfang_fest = False
                    if zustand == "vor_wert":
                        zustand = "wert_oq"
                elif zustand in ("tag", "attr_name", "nach_attr", "tagname"):
                    out.append((teil, ("tag",)))
                elif zustand == "kommentar":
                    out.append((teil, ("kommentar",)))
                else:
                    out.append((teil, ("text",)))
                continue
            text, i = teil[1], 0
            while i < len(text):
                c = text[i]
                if zustand == "daten":
                    if text.startswith("<!--", i):
                        zustand, i = "kommentar", i + 4
                        continue
                    if c == "<" and i + 1 < len(text) and (text[i + 1].isalpha() or text[i + 1] == "/"):
                        zustand = "tagname"
                elif zustand == "kommentar":
                    if text.startswith("-->", i):
                        zustand, i = "daten", i + 3
                        continue
                elif zustand == "tagname":
                    if c.isspace():
                        zustand = "tag"
                    elif c == ">":
                        zustand = "daten"
                elif zustand == "tag":
                    if c == ">":
                        zustand = "daten"
                    elif not c.isspace() and c != "/":
                        zustand, attr = "attr_name", c
                elif zustand == "attr_name":
                    if c == "=":
                        zustand, wert, anfang_fest = "vor_wert", "", True
                    elif c.isspace():
                        zustand = "nach_attr"
                    elif c == ">":
                        zustand = "daten"
                    else:
                        attr += c
                elif zustand == "nach_attr":
                    if c == "=":
                        zustand, wert, anfang_fest = "vor_wert", "", True
                    elif c == ">":
                        zustand = "daten"
                    elif not c.isspace():
                        zustand, attr = "attr_name", c
                elif zustand == "vor_wert":
                    if c == '"':
                        zustand = "wert_dq"
                    elif c == "'":
                        zustand = "wert_sq"
                    elif c == ">":
                        zustand = "daten"
                    elif not c.isspace():
                        zustand, wert = "wert_oq", c
                elif zustand in ("wert_dq", "wert_sq"):
                    if c == ('"' if zustand == "wert_dq" else "'"):
                        zustand = "tag"
                    elif anfang_fest:
                        wert += c
                elif zustand == "wert_oq":
                    if c.isspace():
                        zustand = "tag"
                    elif c == ">":
                        zustand = "daten"
                    elif anfang_fest:
                        wert += c
                i += 1
        return out

    def _fund(self, s: int, e: int, zusatz: str = "") -> Fund:
        pos, ende = self.bereich(s, e)
        datei = self.a.quelle.datei(self.a.t[s].pos) or self.vorlage
        versatz = next((v - st for st, en, d, v in self.a.quelle.herkunft if st <= pos < en), 0)
        return Fund(datei, _umgebend(self.a, s), (zusatz + self._text(s, e))[:160], self.a.stelle(s), pos + versatz,
                    ende + versatz)

    def _ziele(self):
        """(s, e) je Wert eines HTML-Ziels: X.innerHTML/outerHTML = …, += …, insertAdjacentHTML(p, …), document.write(…)."""
        t = self.a.t
        for k in range(1, len(t) - 2):
            if t[k].art == "name" and t[k].wert in ("innerHTML", "outerHTML") and t[k - 1].wert in (".", "?.") \
                    and t[k + 1].art == "punct" and t[k + 1].wert in _ZUWEISUNG:
                yield k + 2, _ende(self.a, k + 2)
            if t[k].art == "name" and t[k].wert in ("insertAdjacentHTML", "write", "writeln") and t[k + 1].wert == "(" \
                    and t[k - 1].wert in (".", "?."):
                if t[k].wert != "insertAdjacentHTML" and not (k >= 2 and t[k - 2].wert == "document"):
                    continue
                args = self.a.argumente(k + 1)
                if args:
                    yield args[-1]

    def ungeschuetzt(self) -> list[Fund]:
        funde, gesehen = [], set()

        def melden(bereiche):
            for s, e in bereiche:
                if (s, e) in gesehen or not self._eigen(s):
                    continue
                gesehen.add((s, e))
                funde.append(self._fund(s, e))

        for teile, _ in self.stuecke():
            for teil, ctx in self.kontexte(teile):
                if ctx[0] == "attr" and ctx[1].startswith("on"):
                    continue  # ein Wert in einem on…-Attribut: dort hilft esc() nicht -- handler_mit_werten()
                melden(self.unsicher(teil[1], teil[2]))
        for s, e in self._ziele():
            melden(self.unsicher(s, e))
        return funde

    def handler_mit_werten(self) -> list[Fund]:
        funde, gesehen = [], set()
        for teile, _ in self.stuecke():
            for teil, ctx in self.kontexte(teile):
                if ctx[0] == "attr" and ctx[1].startswith("on") and (teil[1], teil[2]) not in gesehen and self._eigen(teil[1]):
                    gesehen.add((teil[1], teil[2]))
                    funde.append(self._fund(teil[1], teil[2], f"{ctx[1]}: "))
        return funde

    # --- 3. Links ----------------------------------------------------------------------------------------------------------
    def _url_ok(self, s: int, e: int, tiefe: int = 0) -> bool:
        """Beginnt der Wert mit einem festen erlaubten Anfang oder geht er über sichererLink()/sicheresZiel()?"""
        t = self.a.t
        if s > e or tiefe > 12:
            return s > e
        while t[s].art == "punct" and t[s].wert == "(" and self.a.partner.get(s) == e and not self._interpol(s):
            s, e = s + 1, e - 1
        oben = list(self._oben(s, e))
        ops = [k for k in oben if t[k].art == "punct"]
        werte = [t[k].wert for k in ops]
        if "=" in werte:  # a.href = b.href = '/x' -- der Wert ist der ganz rechts
            return self._url_ok(max(k for k in ops if t[k].wert == "=") + 1, e, tiefe + 1)
        if s == e and t[s].art == "name" and t[s].wert in ("null", "undefined"):
            return True  # kein Link
        if "?" in werte:
            q = next(k for k in ops if t[k].wert == "?")
            doppel = self._doppelpunkt(ops, q)
            return doppel is not None and self._url_ok(q + 1, doppel - 1, tiefe + 1) and self._url_ok(doppel + 1, e, tiefe + 1)
        trenner = [k for k in ops if t[k].wert in ("??", "||")]
        if trenner:
            grenzen = [s - 1, *trenner, e + 1]
            return all(self._url_ok(grenzen[j] + 1, grenzen[j + 1] - 1, tiefe + 1) for j in range(len(grenzen) - 1))
        plus = [k for i, k in enumerate(oben) if t[k].art == "punct" and t[k].wert == "+" and self._binaer(oben, i)]
        if plus:
            return self._url_ok(s, plus[0] - 1, tiefe + 1)
        if t[s].art == "str":
            return bool(_ERLAUBTER_ANFANG.match(_unescape(t[s].wert)))
        if s in self.literale:
            teile = self.literale[s][0]
            if teile[0][1]:
                return bool(_ERLAUBTER_ANFANG.match(teile[0][1]))
            return len(teile) > 1 and self._url_ok(teile[1][1], teile[1][2], tiefe + 1)
        p = self._primaer_ende(s)
        suffixe = self._suffixe(p, e)
        if suffixe is None:
            return False
        if len(suffixe) == 1 and suffixe[0][0] == "call" and t[s].art == "name" and p == s:
            name = t[s].wert
            if name in URL_PRUEFER:
                return True
            if self.ist_escaper(name, s):
                args = self.a.argumente(suffixe[0][1])
                return len(args) == 1 and self._url_ok(*args[0], tiefe + 1)
            fs = self.funktionen_fuer(name, s)
            if fs:
                return all(self._rueckgabe_url_ok(b.rumpf, tiefe + 1) for b in fs)
        if not suffixe and t[s].art == "name":
            bindung = self._bindung(t[s].wert, s)
            if bindung is None or bindung[0] != "var":
                return False
            return self._variable_alle(t[s].wert, s, lambda vs, ve: self._url_ok(vs, ve, tiefe + 1))
        if len(suffixe) == 2 and t[s].wert == "URL" and suffixe[0][0] == "prop" and suffixe[0][1] == "createObjectURL":
            return True
        if len(suffixe) == 1 and suffixe[0][0] == "index" and t[s].art == "punct" and t[s].wert == "{":
            werte = []  # {angebot:`/quotes/${id}`, …}[art]: jeder Wert der Tabelle
            for es, ee in self._elemente(s):
                doppel = next((k for k in self._oben(es, ee) if t[k].art == "punct" and t[k].wert == ":"), None)
                if doppel is None:
                    return False
                werte.append((doppel + 1, ee))
            return all(self._url_ok(vs, ve, tiefe + 1) for vs, ve in werte)
        return False

    def _rueckgabe_url_ok(self, rumpf: tuple, tiefe: int) -> bool:
        t = self.a.t
        rs, re_ = rumpf
        if t[rs].wert == "{" and self.a.partner.get(rs) == re_:
            return all(self._url_ok(r + 1, _ende(self.a, r + 1), tiefe) for r in range(rs + 1, re_)
                       if t[r].art == "name" and t[r].wert == "return" and self._gehoert_zu(r, rs))
        return self._url_ok(rs, re_, tiefe)

    def _dom_links(self):
        """(s, e, art) je Zuweisung an .href/.src/.action, setAttribute('href'|'src'|…, …), Navigation."""
        t = self.a.t
        for k in range(1, len(t) - 2):
            tok = t[k]
            if tok.art != "name":
                continue
            if tok.wert in ("href", "src") and t[k - 1].wert in (".", "?.") and t[k + 1].art == "punct" \
                    and t[k + 1].wert == "=":
                yield k + 2, _ende(self.a, k + 2), tok.wert
            elif tok.wert == "location" and t[k + 1].art == "punct" and t[k + 1].wert == "=" \
                    and (t[k - 1].wert not in (".", "?.") or t[k - 2].wert in ("window", "document")):
                yield k + 2, _ende(self.a, k + 2), "location"
            elif tok.wert == "setAttribute" and t[k + 1].wert == "(":
                args = self.a.argumente(k + 1)
                if len(args) == 2 and args[0][0] == args[0][1] and t[args[0][0]].art == "str" \
                        and t[args[0][0]].wert.lower() in URL_ATTRIBUTE:
                    yield args[1][0], args[1][1], t[args[0][0]].wert
            elif tok.wert in ("assign", "replace") and t[k - 1].wert in (".", "?.") and t[k - 2].wert == "location" \
                    and t[k + 1].wert == "(":
                args = self.a.argumente(k + 1)
                if args:
                    yield args[0][0], args[0][1], f"location.{tok.wert}"
            elif tok.wert == "open" and t[k + 1].wert == "(" and t[k - 1].wert != "function" and (
                    (t[k - 1].wert in (".", "?.") and t[k - 2].wert == "window") or t[k - 1].wert not in (".", "?.")):
                args = self.a.argumente(k + 1)
                if args:
                    yield args[0][0], args[0][1], "window.open"

    def links_aus_daten(self) -> list[Fund]:
        funde, gesehen = [], set()
        for teile, _ in self.stuecke():
            for teil, ctx in self.kontexte(teile):
                if ctx[0] != "attr" or ctx[1] not in URL_ATTRIBUTE or not self._eigen(teil[1]) or ctx[2] is None:
                    continue
                anfang = ctx[2]
                if anfang and _ERLAUBTER_ANFANG.match(anfang):
                    continue
                if not anfang and self._url_ok(teil[1], teil[2]):
                    continue
                if (teil[1], teil[2]) not in gesehen:
                    gesehen.add((teil[1], teil[2]))
                    funde.append(self._fund(teil[1], teil[2], f"{ctx[1]}={anfang!r}+" if anfang else f"{ctx[1]}: "))
        for s, e, art in self._dom_links():
            if self._eigen(s) and not self._url_ok(s, e) and (s, e) not in gesehen:
                gesehen.add((s, e))
                funde.append(self._fund(s, e, f"{art} = "))
        return funde


_JINJA_HANDLER = re.compile(r"""\son[a-z]+\s*=\s*(?:"[^"]*\{\{[^"]*"|'[^']*\{\{[^']*')""", re.I)


def jinja_handler(vorlage: str) -> list[Fund]:
    """on…-Attribute im Markup der Vorlage mit {{ … }} -- Jinja escapt das HTML, nicht den Code im Attribut."""
    text = (TEMPLATES / vorlage).read_text(encoding="utf-8")
    out = []
    for m in _JINJA_HANDLER.finditer(text):
        zeile = text.count("\n", 0, m.start()) + 1
        out.append(Fund(vorlage, "<markup>", re.sub(r"\s+", " ", m.group(0).strip())[:160], f"{vorlage}:{zeile}"))
    return out


def alle_vorlagen() -> list[str]:
    return sorted(p.name for p in TEMPLATES.glob("*.html"))


_INCLUDE = re.compile(r"""\{%-?\s*include\s+["']([^"']+)["']\s*-?%\}""")


def zusammenhaenge() -> list[str]:
    """Die Vorlagen, in deren Zusammenhang gelesen wird: jede, die keine andere einbindet (Seiten), und jede Teilvorlage, die
    keine Seite einbindet. Eine Teilvorlage wird so in jeder Seite gelesen, die sie einbindet -- ihre Funktionen sehen dort deren
    Aufrufstellen."""
    eingebunden = {m for v in alle_vorlagen() for m in _INCLUDE.findall((TEMPLATES / v).read_text(encoding="utf-8"))}
    return [v for v in alle_vorlagen() if v not in eingebunden or not any(
        v in _INCLUDE.findall((TEMPLATES / w).read_text(encoding="utf-8")) for w in alle_vorlagen() if w not in eingebunden)]


_CACHE: dict = {}


def alle_funde(art: str) -> list[Fund]:
    """Die Funde einer Art ("ungeschuetzt", "handler_mit_werten", "links_aus_daten", "jinja") über alle Vorlagen, je Stelle einmal
    (eine Teilvorlage zählt in jedem Zusammenhang; ungeschützt ist sie, wenn sie es in einem ist)."""
    if art == "jinja":
        return [f for v in alle_vorlagen() for f in jinja_handler(v)]
    if art not in _CACHE:
        funde, gesehen = [], set()
        for v in zusammenhaenge():
            for f in getattr(Pruefer(v), art)():
                if (f.datei, f.pos, f.ausdruck) not in gesehen:
                    gesehen.add((f.datei, f.pos, f.ausdruck))
                    funde.append(f)
        _CACHE[art] = sorted(funde, key=lambda f: (f.datei, f.pos, f.ausdruck))
    return _CACHE[art]
