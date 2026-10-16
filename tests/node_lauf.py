"""Seitenskripte in node ausführen -- eine JS-Ausnahme lässt den Test scheitern (seit 1.8.116, Vorgabe vom 16.10.2026, Punkt 5).

Anlass: tests/test_v405_befund_seiten.py::test_namen_im_planungsvorschlag_bleiben_text prüfte nichts. Die Attrappe kannte
element.remove() nicht; calculateSuggestion() scheiterte mit "TypeError: el.remove is not a function", fing die Ausnahme selbst und
schrieb ihren Text in den Hinweis -- dort stand dann kein <img>, und der Test war grün. Eine Seite fängt fast jede Ausnahme (sie zeigt
den Fehler an); ohne Blick auf die gefangenen sieht ein Test nur, dass "nichts Falsches" erscheint.

Deshalb hängt node_ausfuehren() vor jedes Skript einen Vorspann: ein Worker-Thread verbindet sich mit dem Inspector des Hauptthreads
(inspector.Session.connectToMainThread()) und hält bei JEDER Ausnahme an, auch einer gefangenen (Debugger.setPauseOnExceptions "all"),
merkt sie sich in einem gemeinsamen Speicher und lässt weiterlaufen. Am Ende meldet der Vorspann jede Ausnahme, die ein Programmfehler
ist, auf stderr (Zeilen "JS-AUSNAHME: …") und setzt den Rückgabecode -- der Test scheitert mit Klasse, Text und Funktion.

Ein Programmfehler ist eine Ausnahme der Klassen in PROGRAMMFEHLER (TypeError, ReferenceError, SyntaxError, RangeError, URIError,
EvalError). Eine gewollte Ausnahme der Seite ist ein Error (api() bei 4xx/5xx, zahlLesen() bei einer ungültigen Eingabe, speichern() nach
dem Zeitlimit) und bleibt erlaubt. Gewollt gefangene Programmfehler nennt ERLAUBT mit Funktion und Grund (decodeURIComponent beim Prüfen
eines Weiterleitungsziels), ERLAUBT_TEXT mit Text (der Netzfehler "Failed to fetch"); ein Test kann weitere für sich erlauben (erlaubt=,
z. B. eine Attrappe, die absichtlich wirft). Ausnahmen in node selbst (node:internal) zählen nicht."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

NODE = shutil.which("node")

PROGRAMMFEHLER = ("TypeError", "ReferenceError", "SyntaxError", "RangeError", "URIError", "EvalError")

# (Funktion, in der die Ausnahme entsteht, Klasse): gewollt gefangen, mit Grund.
ERLAUBT: dict[tuple[str, str], str] = {
    ("istLokalesZiel", "URIError"): "_weiterleitung.html: kaputte Prozentkodierung im Ziel einer Weiterleitung gilt als nicht lokal "
                                    "(decodeURIComponent in try/catch, Regel 30)",
}

# (Klasse, Text): gewollte Ausnahmen der Plattform, gleich wo.
ERLAUBT_TEXT: dict[tuple[str, str], str] = {
    ("TypeError", "Failed to fetch"): "ein Netzfehler -- so meldet ihn fetch(), und der Baustein beim Hochladen ebenso (_speichern.html, "
                                      "XMLHttpRequest)",
}

MARKE = "JS-AUSNAHME: "
RUECKGABE = 97

VORSPANN = r"""
;(() => {
  const {Worker} = require('worker_threads');
  const speicher = new SharedArrayBuffer(8 + (1 << 20));
  const stand = new Int32Array(speicher, 0, 2);   // [bereit, Länge]
  const bytes = new Uint8Array(speicher, 8);
  const w = new Worker(`
    const {workerData} = require('worker_threads');
    const inspector = require('inspector');
    const stand = new Int32Array(workerData, 0, 2), bytes = new Uint8Array(workerData, 8);
    const s = new inspector.Session();
    s.connectToMainThread();
    const enc = new TextEncoder();
    s.on('Debugger.paused', m => {
      const p = m.params, d = p.data || {}, f = (p.callFrames || [])[0] || {};
      if (p.reason === 'exception' || p.reason === 'promiseRejection') {
        const eintrag = enc.encode(JSON.stringify({klasse: d.className || d.type || '?', text: String(d.description || d.value || '')
          .split('\\n')[0].slice(0, 300), funktion: f.functionName || '', url: f.url || '',
          zeile: f.location ? f.location.lineNumber + 1 : null}) + '\\n');
        const laenge = Atomics.load(stand, 1);
        if (laenge + eintrag.length <= bytes.length) { bytes.set(eintrag, laenge); Atomics.store(stand, 1, laenge + eintrag.length); }
      }
      s.post('Debugger.resume');
    });
    setInterval(() => {}, 1 << 30);  // hält den Worker am Leben; der Hauptthread hat ihn mit unref() vom Ende ausgenommen
    s.post('Debugger.enable', () => s.post('Debugger.setPauseOnExceptions', {state: 'all'}, () => {
      Atomics.store(stand, 0, 1); Atomics.notify(stand, 0);
    }));
  `, {eval: true, workerData: speicher});
  w.unref();
  if (Atomics.wait(stand, 0, 0, 10000) === 'timed-out') { process.stderr.write('JS-VORSPANN: Inspector nicht bereit\n'); process.exit(98); }
  globalThis.__dkAusnahmen = () => new TextDecoder().decode(bytes.slice(0, Atomics.load(stand, 1))).split('\n').filter(Boolean)
    .map(z => JSON.parse(z));
  process.on('exit', () => {
    const fehler = globalThis.__dkAusnahmen().filter(a => !String(a.url).startsWith('node:') && PROGRAMMFEHLER.includes(a.klasse)
      && !ERLAUBT.has(a.funktion + '|' + a.klasse) && !ERLAUBT_TEXT.has(a.text));
    for (const a of fehler) process.stderr.write('MARKE' + JSON.stringify(a) + '\n');
    if (fehler.length) process.exitCode = RUECKGABE;
  });
})();
"""


def vorspann(erlaubt: dict[tuple[str, str], str] | None = None) -> str:
    alle = {**ERLAUBT, **(erlaubt or {})}
    return (VORSPANN.replace("PROGRAMMFEHLER.includes", f"{json.dumps(list(PROGRAMMFEHLER))}.includes")
            .replace("ERLAUBT.has", f"new Set({json.dumps([f'{f}|{k}' for f, k in alle])}).has")
            .replace("ERLAUBT_TEXT.has", f"new Set({json.dumps([f'{k}: {t}' for k, t in ERLAUBT_TEXT])}).has")
            .replace("'MARKE'", json.dumps(MARKE)).replace("= RUECKGABE", f"= {RUECKGABE}"))


class JsAusnahme(AssertionError):
    """Eine Ausnahme im Seitenskript, die ein Programmfehler ist."""


def ausnahmen_aus(stderr: str) -> list[dict]:
    return [json.loads(z[len(MARKE):]) for z in stderr.splitlines() if z.startswith(MARKE)]


def node_lauf(script: str, *, tz: str | None = None, erlaubt: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """Führt script in node aus (mit Vorspann). Scheitert mit JsAusnahme, wenn ein Programmfehler auftrat -- gefangen oder nicht."""
    env = {**os.environ, **({"TZ": tz} if tz else {})}
    result = subprocess.run([NODE], input=vorspann(erlaubt) + "\n" + script, capture_output=True, text=True, encoding="utf-8",
                            env=env, timeout=timeout)
    funde = ausnahmen_aus(result.stderr)
    if funde:
        zeilen = [f"{a['klasse']} in {a['funktion'] or '(oben)'}" + (f" (Zeile {a['zeile']})" if a.get("zeile") else "")
                  + f": {re.sub(r'^[A-Za-z]+: ', '', a['text'])}" for a in funde]
        raise JsAusnahme("JS-Ausnahme im Seitenskript (auch gefangene zählen, tests/node_lauf.py):\n  " + "\n  ".join(zeilen))
    return result


def node_ausfuehren(script: str, tz: str | None = None, **kwargs):
    """Wie node_lauf(), dazu Rückgabecode 0 und die Ausgabe als JSON."""
    result = node_lauf(script, tz=tz, **kwargs)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
