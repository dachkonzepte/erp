"""Version 1.9.352 -- jede Seite zeigt eine abgelehnte Antwort über fehlerText() (Runde V2b, Punkt 0; Entscheidung Tobias 17.11.2026).

Bis 1.9.351 reichten 37 Vorlagen `detail` roh weiter (Error(d.detail), textContent=d.detail …) -- eine 422 mit der Liste der Schemaprüfung erschien
als „Fehler: [object Object]“, ein Status ohne Text als Englisch („Unprocessable Entity“). Der Wächter hier:

    Regel A   keine Vorlage liest `.detail` -- außer _fehlertext.html selbst und AUSNAHMEN (eine Stelle, die detail als Objekt auswertet und die
              Meldung schon über fehlerText() zeigt); die Liste darf nur kürzer werden
    Regel B   jeder Zweig einer Prüfung `if(!x.ok)`, der etwas zeigt oder wirft (throw, Error, alert, textContent, innerHTML, confirm, eine
              Funktion „…Fehler…“), ruft fehlerText() -- still endende Zweige (return [] / null) zeigen nichts
    Einbinden wer fehlerText() im eigenen Skript aufruft, bindet _fehlertext.html selbst ein (der Baustein lässt sich mehrfach einbinden)
    Baustein  fehlerText() gibt für keine Form der Antwort „[object Object]“ zurück
"""

import json
import re

from tests import vorlagen_js as vj
from tests.test_v314_dashboard_month_berlin import TEMPLATES, _node
from tests.test_v333_auswahl_inaktiv import nur_mit_node

BAUSTEIN = "_fehlertext.html"
ZEIGT = {"throw", "Error", "alert", "textContent", "innerHTML", "innerText", "confirm"}
AUSNAHMEN = {
    # Vorlage: (Zahl der Stellen, Grund) -- darf nur kürzer werden
    "master_data_form.html": (5, "Teams: die Rückfrage „laufende Gruppenzeit“ liest detail.code/detail.message aus der 409; die Meldung jeder anderen "
                                 "Ablehnung zeigt api() über fehlerText()"),
}


def verstoesse(quelle) -> list[tuple[str, str]]:
    """(Regel, Stelle) je Verstoß in den Skripten der Quelle."""
    a = vj.analysieren(quelle)
    t, out = a.t, []
    for k, tok in enumerate(t):
        if tok.art == "name" and tok.wert == "detail" and k > 0 and t[k - 1].wert in (".", "?."):
            out.append(("A", a.stelle(k)))
        if (tok.wert == "!" and k + 3 < len(t) and t[k + 1].art == "name" and t[k + 2].wert in (".", "?.") and t[k + 3].wert == "ok"
                and not (k + 4 < len(t) and t[k + 4].wert == "(")):
            auf = a.eltern[k]
            if auf <= 0 or t[auf].wert != "(" or t[auf - 1].wert != "if":
                continue
            start = a.partner[auf] + 1
            ende = a.partner[start] if t[start].wert == "{" else vj._ausdruck_ende(a, start)
            zweig = t[start:ende + 1]
            if any(x.art == "name" and x.wert == "fehlerText" for x in zweig):
                continue
            if any(x.wert in ZEIGT or (x.art == "name" and "ehler" in x.wert) for x in zweig):
                out.append(("B", a.stelle(k)))
    return out


def _alle():
    return {n: verstoesse(vj.eigene_skripte(n)) for n in vj.alle_vorlagen() if n != BAUSTEIN}


def test_keine_vorlage_liest_detail_an_fehlertext_vorbei():
    regel_a = {n: [s for r, s in v if r == "A"] for n, v in _alle().items()}
    offen = {n: s for n, s in regel_a.items() if s and n not in AUSNAHMEN}
    assert offen == {}, f"liest .detail -- die Meldung über fehlerText(d, status, felder, ersatz): {offen}"
    zu_viel = {n: len(regel_a.get(n, [])) for n, (zahl, _grund) in AUSNAHMEN.items() if len(regel_a.get(n, [])) > zahl}
    assert zu_viel == {}, f"AUSNAHMEN darf nur kürzer werden: {zu_viel}"


def test_jeder_abgelehnte_zweig_zeigt_ueber_fehlertext():
    regel_b = {n: [s for r, s in v if r == "B"] for n, v in _alle().items()}
    assert {n: s for n, s in regel_b.items() if s} == {}


def test_wer_fehlertext_aufruft_bindet_ihn_ein():
    fehlt = []
    for name in vj.alle_vorlagen():
        if name == BAUSTEIN:
            continue
        a = vj.analysieren(vj.eigene_skripte(name))
        if any(n == "fehlerText" for _auf, n in a.aufrufe("fehlerText")) and not vj.bindet_ein(name, BAUSTEIN):
            fehlt.append(name)
    assert fehlt == []


def _probe(src: str):
    return verstoesse(vj.Quelle("probe", src, []))


def test_der_waechter_erkennt_jede_form():
    rot = [
        "async function api(u){const r=await fetch(u);if(!r.ok)throw Error((await r.json()).detail||r.statusText);return r.json()}",
        "async function api(u){const r=await fetch(u);if(!r.ok)throw Error(r.statusText);return r.json()}",
        "fetch(u).then(function(r){if(!r.ok){el.textContent='Fehler';return}})",
        "fetch(u).then(r=>r.json().then(d=>{box.textContent=d.detail}))",
        "fetch(u).then(function(r){if(!r.ok)return r.json().then(function(d){zeigeFehler(d)})})",
    ]
    gruen = [
        "async function api(u){const r=await fetch(u);if(!r.ok)throw Error(fehlerText(await r.json().catch(()=>null),r.status));return r.json()}",
        "fetch(u).then(function(r){if(!r.ok)return [];return r.json()})",
        "fetch(u).then(function(r){return r.ok?r.json():null})",
        "const e=ergebnis;if(!e.ok)return daten;",
    ]
    assert [bool(_probe(s)) for s in rot] == [True] * len(rot)
    assert [_probe(s) for s in gruen] == [[]] * len(gruen)


@nur_mit_node
def test_fehlertext_zeigt_nie_object_object_und_laesst_sich_zweimal_einbinden():
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / BAUSTEIN).read_text(encoding="utf-8"), re.S))
    faelle = [
        ({"detail": [{"type": "string_too_long", "loc": ["body", "postal_code"], "msg": "x", "ctx": {"max_length": 20}}]}, 422, {"postal_code": "PLZ"}, None),
        ({"detail": [{"loc": "kaputt"}, 7, None, {"msg": {"a": 1}}]}, 422, None, None),
        ({"detail": {"code": "x", "werte": [1, 2]}}, 409, None, None),
        ({"detail": {"code": "x"}}, 409, None, "Bitte neu laden."),
        ({"detail": {"message": "Sie läuft noch."}}, 409, None, None),
        ({"detail": "Nicht gefunden."}, 404, None, None),
        (None, 500, None, None),
        ({}, 403, None, "Für deine Rolle nicht verfügbar."),
        ({"detail": ""}, 418, None, None),
    ]
    aufrufe = ",".join(f"fehlerText({json.dumps(b)},{s},{json.dumps(f)},{json.dumps(e)})" for b, s, f, e in faelle)
    ergebnis = _node(skript + "\n" + skript + f"\nprocess.stdout.write(JSON.stringify([{aufrufe}]));", "Europe/Berlin")
    assert not any("[object" in x for x in ergebnis), ergebnis
    assert ergebnis == [
        "Bitte die Eingabe prüfen – PLZ ist zu lang (höchstens 20 Zeichen).",
        "Bitte die Eingabe prüfen – ist ungültig.",
        "Der Stand hat sich inzwischen geändert. Bitte die Seite neu laden und es erneut versuchen.",
        "Bitte neu laden.",
        "Sie läuft noch.",
        "Nicht gefunden.",
        "Serverfehler (500) – bitte später erneut versuchen.",
        "Für deine Rolle nicht verfügbar.",
        "Fehler 418",
    ]
