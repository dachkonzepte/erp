"""Version 1.9.116 (Stufe 5, R1, Punkt 6, Befund E2/E4): keine Eingabe geht beim Neuzeichnen verloren.

    Rechnung    getippt (Einleitung, Schlusstexte, Pauschalbetrag, An/CC) gilt vor dem Stand vom Server, bis es gespeichert bzw. versendet ist;
                ein Feld, das nach dem Senden weiter geändert wurde, bleibt (EINGABEN, feldWert(), eingabenGespeichert())
    Zeichenfläche  stand()/setzen() nehmen die Striche über ein Neuzeichnen mit (auf eine Fläche anderer Größe skaliert); „Leeren“ leert
    Bericht     vor jedem Neuzeichnen werden Namen und Striche von Schritt 5 gemerkt, beim Einrichten wieder gesetzt; der Befund merkt Text und
                Wiedervorlage

Den Ablauf in echten Seiten (Leistungszeitraum ändern, Schritt wechseln und zurück, Unterschrift gezeichnet) prüft scripts/klicktest_eingaben_bleiben.py.
"""

import re
from pathlib import Path

from tests import vorlagen_js
from tests.test_v314_dashboard_month_berlin import _node
from tests.test_v334_auswahl_restfaelle import FAKE_DOM, im_browser, nur_mit_node, seite

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"
# Lauscher am Dokument sammeln (die Attrappe verwirft sie), damit der Test eine Eingabe auslösen kann; _aktionen.html prüft
# ev.target instanceof Element -- in node gibt es Element nicht
LAUSCHER = ("\nglobalThis.Element = class {}; var LAUSCHER = {};"
            " document.addEventListener = (art, fn) => { (LAUSCHER[art] = LAUSCHER[art] || []).push(fn); };\n")
TIPPEN = "const tippen = (id, wert) => { const f = _element(id); f.value = wert; (LAUSCHER.input || []).forEach(fn => fn({target: f})); };"


def _rechnungsseite():
    skript = seite("invoice_detail.html", "load().catch(")
    assert skript.startswith(FAKE_DOM)
    return FAKE_DOM + LAUSCHER + skript[len(FAKE_DOM):]


@nur_mit_node
def test_rechnung_getippt_vor_server_bis_gespeichert():
    lauf = im_browser(_rechnungsseite(), TIPPEN + """
      tippen('iIntro', 'Neue Einleitung'); tippen('pAmount', '150,00'); tippen('iNichtGemerkt', 'x');
      const vorher = [feldWert('iIntro', 'vom Server'), feldWert('pAmount', '100,00'), feldWert('iOutro', 'Schluss vom Server'), 'iNichtGemerkt' in EINGABEN];
      eingabenGespeichert({iIntro: 'Neue Einleitung', pAmount: '140,00'});  // pAmount nach dem Senden weiter geändert
      const nachher = [feldWert('iIntro', 'vom Server'), feldWert('pAmount', '100,00')];
      return {vorher, nachher};""")
    assert lauf["ergebnis"] == {"vorher": ["Neue Einleitung", "150,00", "Schluss vom Server", False],
                                "nachher": ["vom Server", "150,00"]}


@nur_mit_node
def test_rechnung_an_und_cc_bleiben_im_neu_gezeichneten_versand():
    lauf = im_browser(_rechnungsseite(), TIPPEN + """
      invoice = {recipient_email: 'kunde@example.com'};
      const leer = emailSendControlsHtml();
      tippen('invoiceEmailInput', 'buchhaltung@example.com'); tippen('invoiceCcInput', 'chef@example.com');
      const getippt = emailSendControlsHtml();
      return [/id="invoiceEmailInput"[^>]*value="([^"]*)"/.exec(leer)[1], /id="invoiceCcInput"[^>]*value="([^"]*)"/.exec(leer)[1],
              /id="invoiceEmailInput"[^>]*value="([^"]*)"/.exec(getippt)[1], /id="invoiceCcInput"[^>]*value="([^"]*)"/.exec(getippt)[1]];""")
    assert lauf["ergebnis"] == ["kunde@example.com", "", "buchhaltung@example.com", "chef@example.com"]


@nur_mit_node
def test_rechnung_vorlage_aus_der_auswahl_zaehlt_wie_getippt():
    lauf = im_browser(_rechnungsseite(), """
      _element('outroSelect').innerHTML = '<option value="Vielen Dank">Dank</option>';
      applyTextTemplate('iOutro', 'outroSelect');
      return feldWert('iOutro', 'vom Server');""")
    assert lauf["ergebnis"] == "Vielen Dank"


def test_rechnung_fuellt_jedes_merkfeld_ueber_feldwert():
    text = (VORLAGEN / "invoice_detail.html").read_text(encoding="utf-8")
    felder = re.search(r"MERKFELDER=\[([^\]]*)\]", text).group(1)
    assert [f.strip("'") for f in felder.split(",")] == ["iIntro", "iOutro", "iOutro2", "pDesc", "pAmount", "invoiceEmailInput", "invoiceCcInput"]
    for feld in ("iIntro", "iOutro", "iOutro2", "pDesc"):
        assert f"document.getElementById('{feld}').value=feldWert('{feld}'," in text, feld
    assert "document.getElementById('pAmount').value=feldWert('pAmount',zahlText(invoice.lump_sum_net))" in text
    assert "value=\"${esc(feldWert('invoiceEmailInput',invoice.recipient_email||''))}\"" in text
    assert "value=\"${esc(feldWert('invoiceCcInput',''))}\"" in text
    # gespeichert wird nur, was gesendet wurde
    assert text.count("anwenden:d=>{eingabenGespeichert(gesendet);zeigeRechnung(d)}") == 2


# --- Zeichenfläche ----------------------------------------------------------------------------------------------------------------

LEINWAND = r"""
var window = globalThis; window.devicePixelRatio = 1; window.addEventListener = () => {}; window.removeEventListener = () => {};
globalThis.requestAnimationFrame = f => f();
function leinwand(breite, hoehe) {
  const ctx = {aufrufe: [], massstab: null, setTransform(a) { this.massstab = a; }, clearRect() { this.aufrufe = []; }, beginPath() {}, moveTo() {},
               lineTo(x, y) { this.aufrufe.push(['linie', Math.round(x), Math.round(y)]); }, stroke() {}, arc() {}, fill() {}};
  return {ctx, width: 0, height: 0, isConnected: true, getContext: () => ctx,
          getBoundingClientRect: () => ({width: breite, height: hoehe, left: 0, top: 0}), setPointerCapture() {},
          toDataURL: () => 'data:image/png;base64,', toBlob: f => f(null)};
}
const zeiger = (x, y) => ({clientX: x, clientY: y, pointerId: 1, preventDefault() {}});
"""


@nur_mit_node
def test_zeichenflaeche_nimmt_die_striche_ueber_ein_neuzeichnen_mit():
    baustein = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_unterschrift.html").read_text(encoding="utf-8"), re.S))
    ergebnis = _node(LEINWAND + baustein + r"""
      const alt = leinwand(300, 150), pad = unterschriftsfeld(alt);
      alt.onpointerdown(zeiger(10, 10)); alt.onpointermove(zeiger(100, 50)); alt.onpointerup();
      const stand = pad.stand();
      const neu = leinwand(600, 300), pad2 = unterschriftsfeld(neu);
      const leerVorher = pad2.leer();
      pad2.setzen(stand);
      const nachSetzen = [pad2.leer(), neu.ctx.aufrufe, neu.ctx.massstab];
      pad2.setzen(null);  // nichts gemerkt -- bleibt, wie es ist
      const nachNull = pad2.leer();
      pad2.leeren();
      process.stdout.write(JSON.stringify({leerVorher, nachSetzen, nachNull, geleert: pad2.leer(), stand: pad2.stand().striche.length}));
    """, "Europe/Berlin")
    # die Striche in Punkten der Basisgröße (300 × 150), gezeichnet auf der doppelt so großen Fläche über den Maßstab der Transformation
    assert ergebnis == {"leerVorher": True, "nachSetzen": [False, [["linie", 100, 50]], 2], "nachNull": False, "geleert": True, "stand": 0}


# --- Einsatzbericht --------------------------------------------------------------------------------------------------------------

def test_bericht_merkt_schritt_5_und_den_befund():
    text = (VORLAGEN / "service_report.html").read_text(encoding="utf-8")
    zeichnen = re.search(r"function inhaltZeichnen\(\)\{\n(.*?)\n\}", text, re.S).group(1)
    assert zeichnen.splitlines()[0].strip() == "unterschriftMerken();"  # vor dem Ersetzen des Schritts
    einrichten = re.search(r"function unterschriftEinrichten\(\)\{\n(.*?)\n\}", text, re.S).group(1)
    assert "PAD_MONTEUR.setzen(SIGN_STAND.monteur);PAD_KUNDE.setzen(SIGN_STAND.kunde)" in einrichten
    assert "if(R.status!=='entwurf'){PAD_MONTEUR=PAD_KUNDE=null;SIGN_STAND=null;return}" in einrichten
    assert 'data-eingabe="befund-text" data-form="\'+schluessel+\'"' in text
    assert 'value="\'+esc(stand.wiedervorlage||\'\')+\'" data-aenderung="befund-wiedervorlage"' in text
    assert "aktion('befund-text',function(f){" in text and "},'input');" in text
    assert vorlagen_js.bindet_ein("service_report.html", "_unterschrift.html", wurzel=VORLAGEN)
