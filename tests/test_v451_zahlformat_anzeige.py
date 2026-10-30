"""Seit 1.9.17 (Runde 7, Punkt 4): Zahlen in der Anzeige über zahlText() (app/templates/_zahl.html) -- kein Rohformat.

Bis 1.9.16 stand der Steuerschlüssel als „Regelsteuersatz (19,0000 %)“ in der Auswahl der Rechnung (und von Auftrag und Angebot), weil der
Satz aus der API (Maschinenformat „19.0000“) nur sein Komma bekam; ebenso Skonto, Zinsaufschlag, Steuersatz der Konten, Dateigrößen
(„1.5 KB“ mit Punkt) und die Menge im Leistungsformular („2.500“ hieß zweitausendfünfhundert).

    Komma von Hand   `.replace('.', ',')` / `.replace(/\\./g, ',')` an einer Zahl -- verboten, überall
    toFixed          nur fürs Maschinenformat (Körper einer Anfrage, Adresse, Wert einer Auswahl), je Vorlage gezählt mit Grund
                     (MASCHINENFORMAT); eine neue Stelle in der Anzeige nimmt zahlText(wert, stellen)
    Dezimalfeld roh  ein Satz, eine Menge, Stunden … aus der API direkt im HTML (`${x.vat_rate}`, `${esc(r.quantity)}`) -- verboten
    Einbinden        wer zahlText() oder steuerschluesselOptionen() nutzt, bindet _zahl.html ein
    Anzeige          node: Steuerschlüssel der Rechnung, Skonto und Zinsaufschlag, Steuerschlüssel/Skonto/Konten der Einstellungen,
                     Dateigrößen, Menge im Leistungsformular

Lokale Formatierer, die schon deutsch formatieren (toLocaleString mit 'de-DE', z. B. qty(), num(), money()), bleiben.
"""

import re

import pytest

from tests import vorlagen_js as vj
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

KOMMA = re.compile(r"""\.replace\(\s*(?:(['"])\.\1|/\\\./g?)\s*,\s*(['"]),\2\s*\)""")
TOFIXED = re.compile(r"\.toFixed\(")
FELDER = (r"(?:quantity|hours|planned_hours|vat_rate|tax_rate_pct|default_tax_rate_pct|skonto_percent|surcharge|rate|pct|percent|"
          r"factor|waste_pct|hourly_rate|weekly_hours|daily_target_hours|threshold_hours|interest_rate)")
ROH = re.compile(r"\$\{\s*(?:esc\(\s*)?(?:String\(\s*)?[\w$?.\[\]]+\." + FELDER + r"\s*\)?\s*\)?\s*\}")

# toFixed nur im Maschinenformat: Vorlage -> (Anzahl, Grund)
MASCHINENFORMAT = {
    "customer.html": (3, "Beträge im Körper von Zuordnung und Erstattung (JSON)"),
    "incoming_invoices.html": (2, "Wert der Auswahl Steuersatz (Optionen 19.00/7.00/0.00)"),
    "invoice_detail.html": (7, "Beträge im Körper von Zahlung und Erstattung, Betrag in der Adresse des Zahlungsvorschlags (JSON/URL)"),
    "recurring_costs.html": (1, "Wert der Auswahl Steuersatz (Optionen 19.00/7.00/0.00)"),
    "settings.html": (1, "Mahngebühr im Körper der Mahnstufe (JSON)"),
}


def _vorlagen():
    return [n for n in vj.alle_vorlagen() if n != "_zahl.html"]


def _treffer(muster, text):
    return [(text.count("\n", 0, m.start()) + 1, m.group(0)) for m in muster.finditer(text)]


def test_kein_komma_von_hand():
    funde = {n: t for n in _vorlagen() if (t := _treffer(KOMMA, (vj.TEMPLATES / n).read_text(encoding="utf-8")))}
    assert funde == {}, "Zahl in der Anzeige über zahlText() (_zahl.html), nie Komma per replace: " + repr(funde)


def test_tofixed_nur_im_maschinenformat():
    zaehlung = {n: len(t) for n in _vorlagen() if (t := _treffer(TOFIXED, (vj.TEMPLATES / n).read_text(encoding="utf-8")))}
    assert zaehlung == {n: k for n, (k, _) in MASCHINENFORMAT.items()}, (
        "toFixed() nur fürs Maschinenformat (in MASCHINENFORMAT mit Grund zählen); in der Anzeige zahlText(wert, stellen)")


def test_keine_dezimalfelder_roh_in_der_anzeige():
    funde = {n: t for n in _vorlagen() if (t := _treffer(ROH, (vj.TEMPLATES / n).read_text(encoding="utf-8")))}
    assert funde == {}, "Satz, Menge oder Stunden aus der API über zahlText(), nie roh: " + repr(funde)


def test_wer_zahltext_nutzt_bindet_zahl_ein():
    """Auch steuerschluesselOptionen() aus _auswahl.html nutzt zahlText() -- jede Seite mit Steuerschlüsseln bindet _zahl.html ein."""
    fehlt = [n for n in vj.alle_vorlagen() if not n.startswith("_")
             and re.search(r"\b(zahlText|steuerschluesselOptionen)\(", (vj.TEMPLATES / n).read_text(encoding="utf-8"))
             and not vj.bindet_ein(n, "_zahl.html")]
    assert fehlt == []


def test_waechter_findet_rohformate():
    """Gegenprobe der drei Muster an erfundenen Stücken."""
    text = ("a=String(t.vat_rate).replace('.', ',');b=x.replace(/\\./g,',');c=(n/1024).toFixed(1)+' KB';"
            "d=`<td>${esc(r.quantity)}</td><td>${x.vat_rate} %</td><td>${zahlText(r.quantity)}</td><td>${esc(r.name)}</td>`;")
    assert [g for _, g in _treffer(KOMMA, text)] == [".replace('.', ',')", ".replace(/\\./g,',')"]
    assert len(_treffer(TOFIXED, text)) == 1
    assert [g for _, g in _treffer(ROH, text)] == ["${esc(r.quantity)}", "${x.vat_rate}"]


# --- Anzeige in node ------------------------------------------------------------------------------------------------------------

STEUERSCHLUESSEL = ("[{id: 1, label: 'Regelsteuersatz', vat_rate: '19.0000', archived: false},"
                    " {id: 2, label: 'Ermäßigt', vat_rate: '7.0000', archived: false}, {id: 3, label: 'Sonder', vat_rate: '10.7000', archived: false}]")


@nur_mit_node
@pytest.mark.parametrize("vorlage,start", [("invoice_detail.html", "load().catch("), ("akte.html", "akteStarten().catch("),
                                           ("quote_editor.html", "load().catch(")])
def test_steuerschluessel_in_der_auswahl(vorlage, start):
    """Auswahl Steuerschlüssel in Rechnung, Auftrag und Angebot: „Regelsteuersatz (19 %)“ (bis 1.9.16 „19,0000 %“)."""
    ablauf = f"return _optionen(steuerschluesselOptionen({STEUERSCHLUESSEL}, 1)).map(o => o.text);"
    assert im_browser(seite(vorlage, start), ablauf)["ergebnis"] == ["Regelsteuersatz (19 %)", "Ermäßigt (7 %)", "Sonder (10,7 %)"]


@nur_mit_node
def test_rechnung_skonto_und_zinsaufschlag():
    ablauf = ("paymentTerms = [{id: 1, label: 'Skonto', days: 14, skonto_percent: '2.50', skonto_days: 7}]; invoice = {payment_term_id: 1};"
              "try { renderPaymentTermSelect(); } catch (e) { if (!_element('iPaymentTermSelect').innerHTML) throw e; }"
              "const zinsen = chargesEditorHtml({charges_enabled: true, charges: [], proposals: {fee: {block: 'keine'}, flat_fee: {block: 'keine'},"
              " interest: {amount: '12.34', period_start: '2026-09-01', period_end: '2026-10-14', surcharge: '9.00', base_rate: '1.27',"
              " rate: '10.27', accepted: false}}}, 'x');"
              "return [_optionen(_element('iPaymentTermSelect').innerHTML).map(o => o.text)[0], /([\\d.,]+) Prozentpunkte/.exec(zinsen)[1]];")
    assert im_browser(seite("invoice_detail.html", "load().catch("), ablauf)["ergebnis"] == ["Skonto (14 Tage, 2,5 % Skonto bei 7 Tagen)", "9"]


@nur_mit_node
def test_einstellungen_steuerschluessel_skonto_konten():
    ablauf = (f"taxKeys = {STEUERSCHLUESSEL}; renderTaxKeys();"
              "paymentTerms = [{id: 1, label: 'Skonto', days: 14, skonto_percent: '2.50', skonto_days: 7}]; renderPaymentTerms();"
              "settingsAccounts = [{id: 1, account_number: '3400', label: 'Wareneingang', default_tax_rate_pct: '19.00', active: true}];"
              " renderAccounts();"
              "return [_element('taxKeyRows').innerHTML.match(/<td>([^<]*%)<\\/td>/g), /([\\d.,]+ % bei)/.exec(_element('paymentTermRows').innerHTML)[1],"
              " /<td>([\\d.,]+ %)<\\/td>/.exec(_element('accountRows').innerHTML)[1]];")
    assert im_browser(seite("settings.html", "load().catch("), ablauf)["ergebnis"] == [
        ["<td>19 %</td>", "<td>7 %</td>", "<td>10,7 %</td>"], "2,5 % bei", "19 %"]


@nur_mit_node
@pytest.mark.parametrize("vorlage,start,aufruf,soll", [
    ("customer.html", "kundenakteStarten().catch(", "fileSize(1536)", "1,5 KB"),  # seit 1.9.137 (bis 1.9.136 load().catch()
    ("akte.html", "akteStarten().catch(", "size(1536)", "1,5 KB"),
    ("akte.html", "akteStarten().catch(", "fmtSize(1572864)", "1,5 MB"),
])
def test_dateigroessen(vorlage, start, aufruf, soll):
    """Dateigrößen (bis 1.9.16 in Kundenakte und Projektmappe „1.5 KB“ mit Punkt)."""
    assert im_browser(seite(vorlage, start), f"return {aufruf};")["ergebnis"] == soll


@nur_mit_node
def test_versandprotokoll_dateigroesse():
    """Die Seite selbst braucht in node _email_dispatch.html (nicht in der Attrappe) -- geprüft wird fmtSize() mit _zahl.html."""
    from tests.node_lauf import node_ausfuehren

    zahl = re.search(r"<script>(.*?)</script>", (vj.TEMPLATES / "_zahl.html").read_text(encoding="utf-8"), flags=re.S).group(1)
    funktion = re.search(r"function fmtSize\(n\)\{.*?\}(?=\s)", (vj.TEMPLATES / "email_dispatches.html").read_text(encoding="utf-8")).group(0)
    dom = "const document = {readyState: 'complete', addEventListener() {}, querySelectorAll() { return []; }};"
    assert node_ausfuehren(dom + zahl + funktion + "\nconsole.log(JSON.stringify(fmtSize(1572864)));") == "1,5 MB"


@nur_mit_node
def test_leistungsformular_menge():
    """Menge eines Materials (bis 1.9.16 roh „2.500“ -- im Deutschen zweitausendfünfhundert)."""
    ablauf = ("materialRows = [{id: 1, name: 'Bahn', quantity: '2.500', unit: 'm²', unit_price: '10.00', total: '25.00'}];"
              "try { renderMaterialRows(); } catch (e) { if (!_element('materialRows').innerHTML.includes('Bahn')) throw e; }"
              "return /<td class=\"number\">([^<]*)<\\/td>/.exec(_element('materialRows').innerHTML)[1];")
    assert im_browser(seite("service_form.html", "init().catch("), ablauf)["ergebnis"] == "2,5"
