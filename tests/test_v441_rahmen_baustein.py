"""Stufe 2 „Rahmen“, Runde 1, Teil 1 (1.8.161): der Baustein ohne sichtbare Änderung.

    ds-basis.css   Grundregeln für Schrift und Steuerelemente, jede Regel nur unter .ds-seite und seit 1.9.4 ganz in :where(…)
                   (Gewicht null), keine --ds-*-Werte, keine At-Regeln, kein !important; über _ds_kopf.html auf jeder Seite geladen;
                   .ds-seite tragen die Seiten in UMGEZOGEN (seit 1.9.3 die Prüfvorlagen als Pilot)
    Makro          teile/seitenkopf.html: Pfad, Kennung, genau ein h1, Status, Untertitel, Hauptaktion, Menü „⋮“ mit aria; Makro-Regel
    Skript         seitenkopf() (_seitenkopf.html) und dsMenue() (_menue.html) in node: Text nur als Text, Links über sichererLink(),
                   Status-Art aus fester Liste; Menü nach dem Muster „Menu Button“ (Tastatur, aria, schließen)
    bereich        jede Seite mit Seitenleiste nennt ihren Bereich ({% set bereich = "…" %}) aus BEREICHE, als erste Anweisung
"""

import json
import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.design_dateien import STATIC_DIR, ist_design_pfad
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v432_design_fundament import _deklarationen, _oberste_ebene, css_regeln
from tests.vorlagen_html import jinja_handler

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
DS_BASIS = STATIC_DIR / "ds" / "ds-basis.css"

# Die Bereiche der Seitenleiste (seit 1.8.162 je ein Eintrag) und "keiner" (Suche, Konto) -- eine Seite mit Seitenleiste nennt einen davon
BEREICHE = {"start", "aufgaben", "kalender", "anfragen", "projekte", "plantafel", "checklisten", "wartungen", "befunde", "finanzen",
            "mahnwesen", "eingangsrechnungen", "betriebskosten", "zeiterfassung", "backoffice", "stammdaten", "einstellungen", "keiner"}
# Seiten, die auf das Design-System umgezogen sind (<body class="… ds-seite …">) -- wird mit jedem Umzug länger
UMGEZOGEN: set[str] = {"inspection_templates.html"}  # seit 1.9.3 (Pilot)
# seit 1.9.7 die Gruppe „Titelzeilen und Titelkarten“ (docs/archiv/befund-rahmen.md: K1 ohne Prüfvorlagen, K2)
TITELZEILEN_UND_TITELKARTEN = {
    "dashboard.html", "tasks.html", "checklists.html", "checklist_templates.html", "maintenance_contracts.html", "findings.html",
    "incoming_invoices.html", "recurring_costs.html",
    "projects.html", "finanzen.html", "mahnwesen.html", "email_dispatches.html", "changelog.html", "search_results.html",
    "time_tracking.html",
}
UMGEZOGEN |= TITELZEILEN_UND_TITELKARTEN
# seit 1.9.10 die Gruppe „Datensatz mit Pfad“ (befund-rahmen.md: K3)
DATENSATZ_MIT_PFAD = {
    "property.html", "roof_area.html", "operational_asset.html", "maintenance_contract.html", "checklist_template.html",
    "inspection_template.html", "service_reports.html",
}
UMGEZOGEN |= DATENSATZ_MIT_PFAD
# seit 1.9.13 die Rechnung aus der Gruppe „Belegkopf in Karte“ (K4)
BELEGKOPF = {"invoice_detail.html", "quote_editor.html"}  # Angebot seit 1.9.18
UMGEZOGEN |= BELEGKOPF
# seit 1.9.21 die Gruppen „Untermenü links“ (K5) und „Zurück-Link + Karte“ (K6)
UNTERMENUE_LINKS = {"master_data.html", "settings.html", "time_backoffice.html"}
ZURUECK_UND_KARTE = {"account.html", "users.html", "history.html", "address_import.html", "index.html"}
UMGEZOGEN |= UNTERMENUE_LINKS | ZURUECK_UND_KARTE
# seit 1.9.22 die Formularseiten Stammdaten-Formular und Leistung im Rahmen (K7; Neues Projekt und Neues Angebot werden Dialoge)
FORMULARSEITEN = {"master_data_form.html", "service_form.html"}
UMGEZOGEN |= FORMULARSEITEN


# ---------------------------------------------------------------------------
# ds-basis.css
# ---------------------------------------------------------------------------

def _where_inhalt(sel: str) -> str | None:
    """Seit 1.9.4: der Inhalt von :where(…), wenn der Selektor ganz darin steht (die schließende Klammer ist sein letztes Zeichen) --
    sonst None. Ganz in :where() hat ein Selektor das Gewicht null, jede Klasse überstimmt ihn."""
    if not sel.startswith(":where("):
        return None
    tiefe = 0
    for i, c in enumerate(sel):
        tiefe += {"(": 1, ")": -1}.get(c, 0)
        if tiefe == 0 and c == ")":
            return sel[len(":where("):i] if i == len(sel) - 1 else None
    return None


def basis_verstoesse(text: str) -> list[str]:
    regeln, rest = css_regeln(text)
    funde = [f"außerhalb einer Regel: {rest[:60]!r}"] if rest else []
    for kopf, rumpf in regeln:
        if kopf.startswith("@"):
            funde.append(f"At-Regel {kopf}")
            continue
        if "{" in rumpf or "}" in rumpf:
            funde.append(f"{kopf}: verschachtelt")
        for sel in _oberste_ebene(kopf, lambda c: c == ","):
            innen = _where_inhalt(sel)
            if innen is None:
                funde.append(f"Selektor nicht ganz in :where(…): {sel}")
                continue
            for teil in _oberste_ebene(innen, lambda c: c == ","):
                if not re.match(r"\.ds-seite(?![A-Za-z0-9_-])", teil):
                    funde.append(f"Selektor nicht unter .ds-seite: {teil}")
        for name, wert in _deklarationen(rumpf):
            if name.startswith("--"):
                funde.append(f"{kopf}: Wert {name} (nur in ds.css)")
            if "!important" in wert.replace(" ", ""):
                funde.append(f"{kopf}: !important")
    return funde


def test_ds_basis_nur_unter_ds_seite():
    assert basis_verstoesse(DS_BASIS.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("css,fund", [
    ("body{margin:0}", "nicht ganz in :where"),
    (".ds-seite a{color:red}", "nicht ganz in :where"),
    (":where(.ds-seite a):hover{color:red}", "nicht ganz in :where"),
    (":where(.ds-seite a) b{color:red}", "nicht ganz in :where"),
    (":where(.ds-seite a), .ds-seite b{color:red}", "nicht ganz in :where"),
    (":where(.x .ds-seite a){color:red}", "nicht unter .ds-seite"),
    (":where(.ds-seiten a){color:red}", "nicht unter .ds-seite"),
    (":where(.ds-seite a, button){color:red}", "nicht unter .ds-seite"),
    (":where(.ds-seite){--ds-grund:#fff}", "Wert --ds-grund"),
    (":where(.ds-seite a){color:red !important}", "!important"),
    ("@media (max-width:600px){:where(.ds-seite){margin:0}}", "At-Regel"),
])
def test_waechter_ds_basis_findet(css, fund):
    assert any(fund in f for f in basis_verstoesse(css)), basis_verstoesse(css)


def test_waechter_ds_basis_laesst_durch():
    assert basis_verstoesse(":where(.ds-seite){margin:0}:where(.ds-seite a, .ds-seite.ds-tablet button:hover)"
                            "{color:var(--ds-link)}:where(.ds-seite :is(a, b)){color:var(--ds-link)}") == []


def test_ds_basis_ist_eine_design_datei_und_auf_jeder_seite_geladen():
    assert ist_design_pfad({"type": "http", "method": "GET", "path": "/static/ds/ds-basis.css", "raw_path": b"/static/ds/ds-basis.css"})
    funde = []
    for name in vj.seiten():
        text = vj.zusammensetzen(name)[0]
        if text.count('href="/static/ds/ds-basis.css?v=') != 1:
            funde.append(f"{name}: ds-basis.css nicht genau einmal")
        elif text.find('href="/static/ds/ds-basis.css?v=') < text.find('href="/static/ds/ds.css?v='):
            funde.append(f"{name}: ds-basis.css vor ds.css")
    assert funde == []


def test_umgezogen_heisst_ds_seite_am_body():
    """Eine Seite schaltet beim Umzug um: <body class="… ds-seite …">. Seit 1.9.3 die Prüfvorlagen (bis dahin keine), seit 1.9.7 die
    15 Seiten der Gruppe „Titelzeilen und Titelkarten“."""
    mit = {name for name in vj.seiten() if re.search(r"<body[^>]*class=\"[^\"]*\bds-seite\b", vj.zusammensetzen(name)[0])}
    assert mit == UMGEZOGEN


def _seitenstil(name: str) -> str:
    """Die <style>-Blöcke der Seite selbst (ohne eingebundene Bausteine)."""
    return "\n".join(re.findall(r"<style>(.*?)</style>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


@pytest.mark.parametrize("name", sorted(UMGEZOGEN))
def test_umgezogene_seite_hat_den_gemeinsamen_kopf(name):
    """Seit 1.9.7 (befund-rahmen.md, „Reihenfolge“: umgezogen heißt kein eigenes .hero/.head/.breadcrumb/.back, h1 nur aus dem Makro):
    Kopf über teile/seitenkopf.html mit _seitenkopf.html, genau ein h1 (das des Makros), höchstens eine grüne Hauptaktion im Kopf
    (.ds-knopf-aktion), Fokusregeln der Seite in --ds-fokus, Links der Seite nicht in der Akzent- oder Aktionsfarbe."""
    eigen = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    seite = vj.zusammensetzen(name)[0]
    assert vj.bindet_ein(name, "_seitenkopf.html"), name
    assert re.search(r"\{%\s*from \"teile/seitenkopf.html\" import seitenkopf\s*%\}", eigen), name
    assert not re.search(r"class=\"(hero|head|breadcrumb|back)\b", eigen), name
    assert re.findall(r"<h1\b", seite) == ["<h1"], name
    # die Teile des Kopfs stehen im call-Block der Seite (das Makro setzt sie über caller() ein)
    aufrufe = re.findall(r"\{%\s*call\(teil\)\s*seitenkopf\(.*?\{%\s*endcall\s*%\}", eigen, flags=re.S)
    assert len(aufrufe) + len(re.findall(r"\{\{\s*seitenkopf\(", eigen)) == 1, name
    assert sum(a.count("ds-knopf-aktion") for a in aufrufe) <= 1, name
    # seit 1.9.13: daneben höchstens eine neutrale Nebenaktion (.ds-knopf ohne -aktion) im Teil "aktion"
    for a in aufrufe:
        teil = re.search(r'teil == "aktion" %\}(.*?)(?:\{%\s*(?:elif|endif))', a, flags=re.S)
        if teil:
            klassen = re.findall(r'class="(ds-knopf[^"]*)"', teil.group(1))
            assert sum("ds-knopf-aktion" not in k.split() for k in klassen) <= 1, (name, klassen)
    stil = _seitenstil(name)
    fokus = [r for r in re.findall(r"[^{}]*:focus[^{}]*\{[^}]*\}", stil) if re.search(r"outline:[^;}]*var\(--(?!ds-fokus)", r)]
    assert fokus == [], (name, fokus)
    for selektor, rumpf in re.findall(r"([^{}]+)\{([^}]*)\}", stil):
        ziele = [re.split(r"[\s>+~]+", s.strip())[-1] for s in selektor.split(",")]
        if any(re.match(r"a(\.|:|$)", z) for z in ziele):
            assert not re.search(r"(?<![-\w])color:var\(--(accent|ds-aktion|ds-aktion-text)\)", rumpf), (name, selektor)
    assert not re.search(r"<a [^>]*style=\"[^\"]*color:var\(--accent\)", eigen), name


# ---------------------------------------------------------------------------
# Makro teile/seitenkopf.html
# ---------------------------------------------------------------------------

def _rendern(quelle: str, **werte) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.from_string(quelle).render(**werte)


AUFRUF = """{% from "teile/seitenkopf.html" import seitenkopf %}
{% call(teil) seitenkopf(titel, untertitel="Kunde · Objekt", kennung="P-2026-0001", mit_pfad=true, mit_aktion=true, mit_menue=true) %}
{% if teil == "pfad" %}<a class="ds-kopf-pfadglied" href="/projects">Projekte</a>{% elif teil == "aktion" %}<button type="button" class="ds-knopf ds-knopf-aktion" data-klick="bearbeiten">Bearbeiten</button>{% elif teil == "menue" %}<button type="button" class="ds-menue-eintrag" data-klick="loeschen">Löschen</button>{% endif %}
{% endcall %}"""


def test_makro_gliederung_mit_allen_teilen():
    html = re.sub(r">\s+<", "><", _rendern(AUFRUF, titel="Dachsanierung <Nord>"))
    assert html.count("<h1") == 1 and 'id="seitenkopfTitel">Dachsanierung &lt;Nord&gt;</h1>' in html
    assert '<nav class="ds-kopf-pfad" id="seitenkopfPfad" aria-label="Pfad"><a class="ds-kopf-pfadglied" href="/projects">Projekte</a></nav>' in html
    assert 'id="seitenkopfKennung">P-2026-0001</span>' in html and 'id="seitenkopfUntertitel">Kunde · Objekt</p>' in html
    # seit 1.9.11: die Kennung als Kennzeichen in der Titelzeile, zwischen Titel und Status (bis dahin eine Zeile über dem Titel)
    zeile = re.search(r'<div class="ds-kopf-titelzeile">(.*?)</div>', html).group(1)
    assert re.findall(r'id="(seitenkopf\w+)"', zeile) == ["seitenkopfTitel", "seitenkopfKennung", "seitenkopfStatus"]
    assert '<span class="ds-kopf-kennung" id="seitenkopfKennung">' in zeile
    assert re.search(r'<span class="ds-status ds-status-neutral" id="seitenkopfStatus" role="status"></span>', html)
    knopf = re.search(r'<button[^>]*id="seitenkopfMenueKnopf"[^>]*>', html).group(0)
    for attr in ('type="button"', 'aria-haspopup="menu"', 'aria-expanded="false"', 'aria-controls="seitenkopfMenue"', 'aria-label="Weitere Aktionen"'):
        assert attr in knopf, attr
    assert re.search(r'<div class="ds-menue" id="seitenkopfMenue" role="menu" aria-label="Weitere Aktionen" hidden><button[^>]*>Löschen</button></div>', html)
    assert html.index("Bearbeiten") < html.index("seitenkopfMenueKnopf")  # Hauptaktion vor dem Menü


def test_makro_kennzahlen_zwischen_text_und_aktionen():
    """Seit 1.9.13: Teil "kennzahlen" (Rechnung: Netto, MwSt., Brutto) zwischen Text und Aktionen."""
    quelle = ('{% from "teile/seitenkopf.html" import seitenkopf %}{% call(teil) seitenkopf("R", mit_aktion=true, mit_kennzahlen=true) %}'
              '{% if teil == "kennzahlen" %}<div class="ds-kennzahl"><span class="ds-kennzahl-name">Netto</span>'
              '<b class="ds-kennzahl-wert" id="mNet">1</b></div>{% elif teil == "aktion" %}<button type="button" class="ds-knopf">PDF</button>'
              '{% endif %}{% endcall %}')
    html = re.sub(r">\s+<", "><", _rendern(quelle))
    assert html.index('class="ds-kopf-text"') < html.index('class="ds-kopf-kennzahlen"') < html.index('class="ds-kopf-aktionen"')
    assert '<div class="ds-kopf-kennzahlen"><div class="ds-kennzahl">' in html
    assert "ds-kopf-kennzahlen" not in _rendern('{% from "teile/seitenkopf.html" import seitenkopf %}{{ seitenkopf("X") }}')


def test_makro_variante_breit():
    """Seit 1.9.18: breit=true setzt ds-kopf-breit -- der Text über die ganze erste Zeile, Kennzahlen und Aktionen darunter (Angebot);
    ohne bleibt der Kopf wie bisher."""
    breit = _rendern('{% from "teile/seitenkopf.html" import seitenkopf %}{{ seitenkopf("A", breit=true) }}')
    schmal = _rendern('{% from "teile/seitenkopf.html" import seitenkopf %}{{ seitenkopf("A") }}')
    assert '<header class="ds-kopf ds-kopf-breit" id="seitenkopf">' in breit
    assert '<header class="ds-kopf" id="seitenkopf">' in schmal and "ds-kopf-breit" not in schmal
    css = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    assert re.search(r"\.ds-kopf-breit \.ds-kopf-text \{\s*flex-basis: 100%;\s*\}", css)


def test_makro_ohne_teile_ohne_pfad_aktion_und_menue():
    html = _rendern('{% from "teile/seitenkopf.html" import seitenkopf %}{{ seitenkopf("Prüfvorlagen") }}')
    assert "seitenkopfPfad" not in html and "seitenkopfMenue" not in html and "ds-knopf-aktion" not in html
    assert 'id="seitenkopfKennung"></span>' in html and 'id="seitenkopfUntertitel"></p>' in html  # leer: ds.css blendet aus (:empty)
    assert html.count("<h1") == 1


def test_makro_haelt_die_makro_regel_ein():
    assert jinja_handler("teile/seitenkopf.html") == []


def test_wer_das_makro_nutzt_bindet_das_skript_ein():
    funde = [name for name in vj.alle_vorlagen() if "import seitenkopf" in (TEMPLATES / name).read_text(encoding="utf-8")
             and name not in ("teile/seitenkopf.html", "_seitenkopf.html") and not vj.bindet_ein(name, "_seitenkopf.html")]
    assert funde == []


def test_kennung_ist_ein_kennzeichen_in_mono_mit_rahmen():
    """Seit 1.9.11 (Runde 6, Punkt 3): die Kennung ein Kennzeichen wie der Status (24 px hoch), in Mono, mit Rahmen in linie-stark,
    Schrift text-2 (geprüftes Kontrastpaar auf grund und flaeche)."""
    css = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    rumpf = re.search(r"\n\.ds-kopf-kennung\s*\{([^}]*)\}", css).group(1)
    for deklaration in ("display: inline-flex", "height: 24px", "border: 1px solid var(--ds-linie-stark)",
                        "font-family: var(--ds-schrift-mono)", "font-size: var(--ds-groesse-1)", "color: var(--ds-text-2)"):
        assert deklaration in rumpf, deklaration


def test_leere_teile_blendet_ds_css_aus():
    css = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    for klasse in ("ds-kopf-pfad", "ds-kopf-kennung", "ds-kopf-untertitel", "ds-status"):
        assert re.search(r"\." + klasse + r":empty\s*\{\s*display:\s*none", css), klasse


# ---------------------------------------------------------------------------
# seitenkopf() und dsMenue() in node
# ---------------------------------------------------------------------------

DOM = r"""
class El {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.attrs = {}; this.children = []; this.parentNode = null; this.listeners = {};
    this._text = ''; this.hidden = false; this.disabled = false; this.className = ''; this.id = ''; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'id') this.id = String(v); if (k === 'class') this.className = String(v); }
  getAttribute(k) { return k === 'class' ? this.className : (k in this.attrs ? this.attrs[k] : null); }
  removeAttribute(k) { delete this.attrs[k]; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  replaceChildren(...cs) { this.children.forEach((c) => { c.parentNode = null; }); this.children = []; cs.forEach((c) => this.appendChild(c)); }
  get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join('') : this._text; }
  set textContent(v) { this.children = []; this._text = String(v); }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  focus() { document.activeElement = this; }
  contains(o) { while (o) { if (o === this) return true; o = o.parentNode; } return false; }
  matches(sel) { return sel.startsWith('.') && this.className.split(/\s+/).includes(sel.slice(1)); }
  closest(sel) { let e = this; while (e) { if (e.matches && e.matches(sel)) return e; e = e.parentNode; } return null; }
  querySelectorAll(sel) { const out = []; const lauf = (e) => { for (const c of e.children) { if (c.matches(sel)) out.push(c); lauf(c); } }; lauf(this); return out; }
}
const document = { listeners: {}, activeElement: null, readyState: 'complete', ids: {},
  getElementById(id) { return this.ids[id] || null; }, createElement(t) { return new El(t); },
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); } };
function ausloesen(el, typ, extra) {
  const ev = Object.assign({ type: typ, target: el, defaultPrevented: false }, extra || {});
  ev.preventDefault = () => { ev.defaultPrevented = true; };
  for (let e = el; e; e = e.parentNode) (e.listeners[typ] || []).forEach((f) => f(ev));
  (document.listeners[typ] || []).forEach((f) => f(ev));
  return ev;
}
function neu(tag, id, klasse) { const e = new El(tag); if (id) { e.setAttribute('id', id); document.ids[id] = e; } if (klasse) e.className = klasse; return e; }
const window = { location: { origin: 'https://erp.example' } };
"""


def _bausteine_js() -> str:
    text = vj.zusammensetzen("_seitenkopf.html")[0]
    return "\n".join(re.findall(r"<script>(.*?)</script>", text, flags=re.S))


def test_dsmenue_tastatur_aria_und_schliessen():
    skript = DOM + r"""
    const knopf = neu('button', 'seitenkopfMenueKnopf'); const liste = neu('div', 'seitenkopfMenue', 'ds-menue'); liste.hidden = true;
    const draussen = neu('div', 'draussen');
    const a = liste.appendChild(neu('button', null, 'ds-menue-eintrag')); const b = liste.appendChild(neu('button', null, 'ds-menue-eintrag'));
    const c = liste.appendChild(neu('a', null, 'ds-menue-eintrag'));
    """ + _bausteine_js() + r"""
    const r = {};
    r.aria = [knopf.getAttribute('aria-haspopup'), knopf.getAttribute('aria-expanded'), knopf.getAttribute('aria-controls'), liste.getAttribute('role'),
              [a, b, c].map((e) => e.getAttribute('role') + '/' + e.getAttribute('tabindex')).join(',')];
    r.zweiter = dsMenue(knopf, liste);
    ausloesen(knopf, 'click'); r.offen = [liste.hidden, knopf.getAttribute('aria-expanded'), document.activeElement === a];
    ausloesen(a, 'keydown', { key: 'ArrowDown' }); r.runter = document.activeElement === b;
    ausloesen(b, 'keydown', { key: 'ArrowUp' }); ausloesen(a, 'keydown', { key: 'ArrowUp' }); r.ringsum = document.activeElement === c;
    ausloesen(c, 'keydown', { key: 'Home' }); r.pos1 = document.activeElement === a;
    ausloesen(a, 'keydown', { key: 'End' }); r.ende = document.activeElement === c;
    const esc = ausloesen(c, 'keydown', { key: 'Escape' });
    r.escape = [liste.hidden, knopf.getAttribute('aria-expanded'), document.activeElement === knopf, esc.defaultPrevented];
    ausloesen(knopf, 'keydown', { key: 'ArrowUp' }); r.hochAmKnopf = [liste.hidden, document.activeElement === c];
    ausloesen(draussen, 'click'); r.daneben = liste.hidden;
    ausloesen(knopf, 'click'); ausloesen(b, 'click'); r.eintrag = liste.hidden;
    ausloesen(knopf, 'click'); ausloesen(a, 'keydown', { key: 'Tab' }); r.tab = liste.hidden;
    ausloesen(knopf, 'click'); ausloesen(knopf, 'click'); r.knopfZu = [liste.hidden, knopf.getAttribute('aria-expanded')];
    console.log(JSON.stringify(r));
    """
    r = node_ausfuehren(skript)
    assert r["aria"] == ["menu", "false", "seitenkopfMenue", "menu", "menuitem/-1,menuitem/-1,menuitem/-1"]
    assert r["zweiter"] is None
    assert r["offen"] == [False, "true", True] and r["runter"] and r["ringsum"] and r["pos1"] and r["ende"]
    assert r["escape"] == [True, "false", True, True]
    assert r["hochAmKnopf"] == [False, True] and r["daneben"] and r["eintrag"] and r["tab"]
    assert r["knopfZu"] == [True, "false"]


def test_seitenkopf_setzt_text_status_und_pfad():
    skript = DOM + r"""
    const kennung = neu('div', 'seitenkopfKennung'); const titel = neu('h1', 'seitenkopfTitel'); const status = neu('span', 'seitenkopfStatus', 'ds-status ds-status-neutral');
    const untertitel = neu('p', 'seitenkopfUntertitel'); const pfad = neu('nav', 'seitenkopfPfad');
    """ + _bausteine_js() + r"""
    seitenkopf({ kennung: 'P-2026-0001', titel: '<b>Dach</b>', untertitel: 'Kunde', status: { text: 'beauftragt', art: 'ok' },
                 pfad: [{ text: 'Projekte', href: '/projects' }, { text: 'Böse', href: 'javascript:alert(1)' }, { text: '<i>Seite</i>' }] });
    const r = { kennung: kennung.textContent, titel: titel.textContent, kinderTitel: titel.children.length, status: [status.textContent, status.className],
                pfad: pfad.children.map((e) => [e.tagName, e.className, e.getAttribute('href'), e.getAttribute('aria-current'), e.textContent]) };
    seitenkopf({ titel: 'Neu', status: { text: 'x', art: 'rot' } });
    r.nurTitel = [kennung.textContent, titel.textContent, status.className];
    seitenkopf({ status: null, pfad: null }); r.leer = [status.textContent, pfad.children.length];
    console.log(JSON.stringify(r));
    """
    r = node_ausfuehren(skript)
    assert r["kennung"] == "P-2026-0001" and r["titel"] == "<b>Dach</b>" and r["kinderTitel"] == 0
    assert r["status"] == ["beauftragt", "ds-status ds-status-ok"]
    assert r["pfad"] == [
        ["A", "ds-kopf-pfadglied", "/projects", None, "Projekte"], ["SPAN", "ds-kopf-trenner", None, None, "/"],
        ["A", "ds-kopf-pfadglied", "#", None, "Böse"], ["SPAN", "ds-kopf-trenner", None, None, "/"],
        ["SPAN", "ds-kopf-pfadende", None, "page", "<i>Seite</i>"]]
    assert r["nurTitel"] == ["P-2026-0001", "Neu", "ds-status ds-status-neutral"]
    assert r["leer"] == ["", 0]


# ---------------------------------------------------------------------------
# bereich je Seite
# ---------------------------------------------------------------------------

BEREICH_RE = re.compile(r'\{%-?\s*set\s+bereich\s*=\s*"([a-z]+)"\s*-?%\}')


def bereich_verstoesse(name: str, wurzel: Path = TEMPLATES) -> list[str]:
    text = (wurzel / name).read_text(encoding="utf-8")
    werte = BEREICH_RE.findall(text)
    if len(werte) != 1:
        return [f"{name}: {len(werte)} × bereich"]
    if werte[0] not in BEREICHE:
        return [f"{name}: unbekannter Bereich {werte[0]!r}"]
    # erste Anweisung der Vorlage -- so steht er sicher vor der Seitenleiste (ein {% set %} danach sähe sie nicht)
    if not BEREICH_RE.match(text):
        return [f"{name}: bereich nicht als erste Anweisung"]
    return []


def test_jede_seite_mit_leiste_nennt_ihren_bereich():
    mit_leiste = [name for name in vj.seiten() if vj.bindet_ein(name, "_sidebar.html")]
    assert len(mit_leiste) == 44  # seit 1.9.22 mit Stammdaten-Formular und Leistung (bis dahin 42)
    assert [f for name in mit_leiste for f in bereich_verstoesse(name)] == []


def test_seiten_ohne_leiste_nennen_keinen_bereich():
    ohne = [name for name in vj.seiten() if not vj.bindet_ein(name, "_sidebar.html")]
    assert [name for name in ohne if BEREICH_RE.search((TEMPLATES / name).read_text(encoding="utf-8"))] == []


@pytest.mark.parametrize("text,fund", [
    ('<html>{% include "_sidebar.html" %}</html>', "0 × bereich"),
    ('{% set bereich = "projekte" %}{% set bereich = "start" %}{% include "_sidebar.html" %}', "2 × bereich"),
    ('{% set bereich = "rechnungen" %}{% include "_sidebar.html" %}', "unbekannter Bereich"),
    ('<html>{% set bereich = "projekte" %}', "nicht als erste Anweisung"),
])
def test_waechter_bereich_findet(tmp_path, text, fund):
    (tmp_path / "x.html").write_text(text, encoding="utf-8")
    assert any(fund in f for f in bereich_verstoesse("x.html", tmp_path)), bereich_verstoesse("x.html", tmp_path)


def test_bereich_aendert_das_gerenderte_html_nicht(threaded_db_session, router_test_client):
    """{% set … -%} vor dem doctype: die Seite beginnt weiter mit <!doctype html> (kein Zeilenumbruch, kein Leerraum davor)."""
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role="admin")
    for adresse in ("/projects", "/settings", "/suche?q=x", "/account"):
        text = client.get(adresse).text
        assert text.startswith("<!doctype html>"), (adresse, text[:40])


# ---------------------------------------------------------------------------
# Seit 1.8.162: die Seitenleiste markiert den Bereich der Seite
# ---------------------------------------------------------------------------

def test_bereiche_sind_die_eintraege_der_seitenleiste():
    leiste = (TEMPLATES / "_sidebar.html").read_text(encoding="utf-8")
    assert set(re.findall(r'data-bereich="([a-z]+)"', leiste)) | {"keiner"} == BEREICHE


def test_jede_seite_markiert_ihren_bereich(threaded_db_session, router_test_client):
    """Gezeichnet als Admin (sieht jeden Eintrag): genau der Eintrag des Bereichs ist aktiv und trägt aria-current, bei "keiner" keiner."""
    import scripts.bildgrundlage as bg
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role="admin")
    werte = {k: 1 for k in ("projekt", "angebot", "auftrag", "rechnung", "checkliste", "checklistenvorlage", "vertrag", "pruefvorlage",
                            "kunde", "objekt", "dachflaeche", "geraet", "leistung", "mitarbeiter")}
    geprueft = set()
    for a in bg.AUFNAHMEN:
        if a.vorlage in geprueft or not vj.bindet_ein(a.vorlage, "_sidebar.html") or bg.MONTEUR in a.rollen and len(a.rollen) == 1:
            continue
        text = client.get(a.pfad.format(**werte), follow_redirects=False).text
        bereich = BEREICH_RE.match((TEMPLATES / a.vorlage).read_text(encoding="utf-8")).group(1)
        nav = text[text.index('<nav class="app-sidebar-nav">'):text.index("</nav>", text.index('<nav class="app-sidebar-nav">'))]
        aktiv = re.findall(r'<a class="app-sidebar-link[^"]*\bactive\b[^"]*" data-bereich="([a-z]+)"[^>]*aria-current="page"', nav)
        assert aktiv == ([] if bereich == "keiner" else [bereich]) and nav.count('aria-current="page"') == len(aktiv), (a.vorlage, aktiv)
        geprueft.add(a.vorlage)
    assert len(geprueft) == 44  # seit 1.9.22 mit Stammdaten-Formular und Leistung (bis dahin 42)


def test_grundregeln_mit_gewicht_null():
    """Seit 1.9.4 (ersetzt „nur ohne Klasse“, 1.9.3): jede Grundregel gilt für alle Elemente, mit dem Gewicht null -- jeder Selektor
    steht ganz in :where(…) (Wächter oben), keiner trägt noch :not([class]), und a, button, input, select, textarea, h1–h3 haben je eine
    Regel. Ein Element unter .ds-seite (0,1,1) überstimmte vorher die Klassen der Bausteine (0,1,0). Im Browser misst klicktest_rahmen
    (Teil pruefvorlagen) Leiste, Kontomenü, grünen Knopf und einen eingeschobenen alten Knopf mit Klasse."""
    regeln, _ = css_regeln(DS_BASIS.read_text(encoding="utf-8"))
    ziele = set()
    for kopf, _rumpf in regeln:
        assert ":not([class])" not in kopf, kopf
        for sel in _oberste_ebene(kopf, lambda c: c == ","):
            for teil in _oberste_ebene(_where_inhalt(sel), lambda c: c == ","):
                ziele.add(re.split(r"[\s>+~]+", teil)[-1])
    assert {"a", "a:hover", "button", "input", "select", "textarea", "h1", "h2", "h3", ":focus-visible"} <= ziele, ziele

