"""Seit 1.9.9 (Stufe 2 „Rahmen“, Runde 5): der Status im Seitenkopf an einer Stelle -- app/templates/_statuskennzeichen.html.

    Bedeutungen   läuft = info, erledigt/bezahlt = ok, wartet auf dich = signal, überfällig/Fehler = fehler, Entwurf = warn, ruht =
                  neutral; jede Art eine des Seitenkopfs (seitenkopfArten())
    Tabelle       jeder Wert, den der Server für einen Auftrag, einen Wartungsvertrag und eine Fassung einer Checklisten-Vorlage schreibt,
                  steht darin (abgelöste Fassungen sind nie der Stand einer Vorlage); jeder Eintrag mit Text und bekannter Bedeutung
    Lesbar        ein unbekannter Wert erscheint mit großem Anfangsbuchstaben und neutral, ein leerer gar nicht
    Eine Stelle   jeder Status in seitenkopf({…}) kommt aus statusKennzeichen() mit einer Gruppe der Tabelle, jeder feste Wert darin ist
                  ein Wert dieser Gruppe; kein Skript setzt das Kennzeichen (seitenkopfStatus) an seitenkopf() vorbei; _seitenkopf.html
                  bindet den Baustein ein
"""

import re

import pytest

from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v364_feste_werte_spaltenlaenge import FESTE_LITERALE

BAUSTEIN = "_statuskennzeichen.html"


def _baustein_js(*namen: str) -> str:
    text = "\n".join(vj.zusammensetzen(n)[0] for n in namen)
    return "\n".join(re.findall(r"<script>(.*?)</script>", text, flags=re.S))


@pytest.fixture(scope="module")
def tabellen():
    dom = "const document = { readyState: 'complete', getElementById() { return null; }, addEventListener() {} };"
    skript = dom + "\n" + _baustein_js("_seitenkopf.html") + r"""
    console.log(JSON.stringify({ arten: seitenkopfArten(), bedeutungen: statusBedeutungen(), tabelle: statusTabelle(),
      beispiele: [statusKennzeichen('auftrag', 'beauftragt'), statusKennzeichen('auftrag', 'abgeschlossen'),
                  statusKennzeichen('betriebsmittel', 'pruefung_faellig'), statusKennzeichen('betriebsmittel', 'pruefung_ueberfaellig'),
                  statusKennzeichen('checklistenvorlage', 'entwurf'), statusKennzeichen('wartungsvertrag', 'pausiert'),
                  statusKennzeichen('auftrag', 'in_pruefung'), statusKennzeichen('gibt_es_nicht', 'x'),
                  statusKennzeichen('auftrag', ''), statusKennzeichen('auftrag', null), statusKennzeichen('auftrag', '<b>neu</b>'),
                  statusKennzeichen('rechnung', 'zahlbetrag_offen', { zusatz: '495,00 €' }),
                  statusKennzeichen('rechnung', 'zahlbetrag_offen', { zusatz: '495,00 €', ueberfaellig: true }),
                  statusKennzeichen('rechnung', 'guthaben', { zusatz: '119,00 €' }),
                  statusKennzeichen('rechnung', 'enthalten', { zusatz: 'R-2026-0003' }),
                  statusKennzeichen('rechnung', 'entwurf'), statusKennzeichen('rechnung', 'versendet'),
                  statusKennzeichen('auftrag', 'in_ausfuehrung')] }));
    """
    return node_ausfuehren(skript)


def test_bedeutungen_wie_festgelegt(tabellen):
    assert tabellen["bedeutungen"] == {"laeuft": "info", "erledigt": "ok", "wartet": "signal", "fehler": "fehler", "entwurf": "warn",
                                       "ruht": "neutral"}
    assert set(tabellen["bedeutungen"].values()) == set(tabellen["arten"])


def test_jeder_eintrag_mit_text_und_bekannter_bedeutung(tabellen):
    for gruppe, werte in tabellen["tabelle"].items():
        assert werte, gruppe
        for wert, (text, bedeutung) in werte.items():
            assert text and text[0].isupper() and text != wert, (gruppe, wert)
            assert bedeutung in tabellen["bedeutungen"], (gruppe, wert)


def test_jeder_wert_des_servers_steht_in_der_tabelle(tabellen):
    from app.maintenance_contracts import STATUSES

    t = tabellen["tabelle"]
    assert set(FESTE_LITERALE["orders.status"]) <= set(t["auftrag"])
    assert set(STATUSES) | {"archiviert"} <= set(t["wartungsvertrag"])
    fassungen = set(FESTE_LITERALE["checklist_template_versions.status"]) - {"abgeloest"}
    assert fassungen | {"archiviert"} <= set(t["checklistenvorlage"])
    # seit 1.9.13: jeder Status, den die Auftragsseite anbietet (der Server nimmt ihn vom Client), und jeder Stand einer Rechnung
    from app.final_dunning import OVERVIEW_LABELS
    from app.payments import STATES

    auswahl = re.search(r'<select id="status">(.*?)</select>', (vj.TEMPLATES / "order.html").read_text(encoding="utf-8"), flags=re.S)
    assert set(re.findall(r'value="([^"]*)"', auswahl.group(1))) <= set(t["auftrag"])
    # seit 1.9.18: jeder Status, den der LV-Editor anbietet (der Server nimmt ihn vom Client), und jeder, den er selbst schreibt
    angebot = re.search(r'<select id="hStatus">(.*?)</select>', (vj.TEMPLATES / "quote_editor.html").read_text(encoding="utf-8"), flags=re.S)
    assert set(re.findall(r'value="([^"]*)"', angebot.group(1))) | set(FESTE_LITERALE["quotes.status"]) <= set(t["angebot"])
    rechnung = set(FESTE_LITERALE["invoices.status"]) | set(STATES) | set(OVERVIEW_LABELS) | {"enthalten"}
    # seit 1.9.25: jeder Stand einer Checkliste
    from app.checklists import STATUS_LABELS

    assert set(STATUS_LABELS) <= set(t["checkliste"])
    # seit 1.9.24: jeder Status, den die Arbeitsvorbereitung anbietet (der Server nimmt ihn vom Client), und der, den er selbst schreibt
    av = re.search(r'<select id="prepStatus">(.*?)</select>', (vj.TEMPLATES / "work_preparation.html").read_text(encoding="utf-8"), flags=re.S)
    assert set(re.findall(r'value="([^"]*)"', av.group(1))) | set(FESTE_LITERALE["work_preparations.status"]) <= set(t["arbeitsvorbereitung"])
    assert rechnung <= set(t["rechnung"]), sorted(rechnung - set(t["rechnung"]))


def test_kennzeichen_lesbar_und_in_der_farbe_der_bedeutung(tabellen):
    assert tabellen["beispiele"] == [
        {"text": "Beauftragt", "art": "info"}, {"text": "Abgeschlossen", "art": "ok"},
        {"text": "Prüfung fällig", "art": "signal"}, {"text": "Prüfung überfällig", "art": "fehler"},
        {"text": "Entwurf", "art": "warn"}, {"text": "Pausiert", "art": "neutral"},
        {"text": "In pruefung", "art": "neutral"}, {"text": "X", "art": "neutral"},
        {"text": "", "art": "neutral"}, {"text": "", "art": "neutral"}, {"text": "<b>neu</b>", "art": "neutral"},  # Text, kein HTML
        # seit 1.9.13 mit Zusatz und überfällig -- dieselben Texte wie bis 1.9.12 im Kennzeichen der Rechnungsseite
        {"text": "Zahlbetrag offen 495,00 €", "art": "info"}, {"text": "Zahlbetrag offen 495,00 € · überfällig", "art": "fehler"},
        {"text": "Guthaben 119,00 €", "art": "signal"}, {"text": "Enthalten in Schlussrechnung R-2026-0003", "art": "neutral"},
        {"text": "Entwurf", "art": "warn"}, {"text": "Finalisiert", "art": "info"}, {"text": "In Ausführung", "art": "info"},
    ]


def test_seitenkopf_bindet_den_baustein_ein():
    assert vj.bindet_ein("_seitenkopf.html", BAUSTEIN, nur_selbst=True)


def status_in_seitenkopf(name: str) -> list[tuple[str, str]]:
    """Je Aufruf seitenkopf({…, status: …}) in den Skripten der Vorlage: (Stelle, Gruppe) -- die Gruppe ist "" (verstößt), wenn der
    Status nicht als statusKennzeichen('<gruppe>', …) dasteht; dazu je fester Wert im Aufruf (Stelle, "<gruppe>=<wert>")."""
    a = vj.analysieren(vj.eigene_skripte(name))
    funde = []
    for auf, _ in a.aufrufe("seitenkopf"):
        if a.ist_methode(auf) or a.t[auf + 1].wert != "{":
            continue
        obj = auf + 1
        for k in range(obj + 1, a.partner[obj]):
            if a.eltern[k] == obj and a.t[k].art == "name" and a.t[k].wert == "status" and a.t[k + 1].wert == ":":
                ruf, klammer, gruppe = a.t[k + 2], a.t[k + 3], a.t[k + 4]
                if ruf.wert == "statusKennzeichen" and klammer.wert == "(" and gruppe.art == "str":
                    funde.append((a.stelle(k), gruppe.wert))
                    zu = a.partner[k + 3]
                    funde += [(a.stelle(j), f"{gruppe.wert}={a.t[j].wert}") for j in range(k + 6, zu) if a.t[j].art == "str"]
                else:
                    funde.append((a.stelle(k), ""))
    return funde


def test_status_im_seitenkopf_nur_ueber_statuskennzeichen(tabellen):
    verstoesse = []
    for name in vj.alle_vorlagen():
        if name in ("_seitenkopf.html", "teile/seitenkopf.html", BAUSTEIN):
            continue
        for stelle, eintrag in status_in_seitenkopf(name):
            gruppe, _, wert = eintrag.partition("=")
            if not gruppe or gruppe not in tabellen["tabelle"] or (wert and wert not in tabellen["tabelle"][gruppe]):
                verstoesse.append(f"{stelle}: {eintrag or 'Status nicht über statusKennzeichen()'}")
        text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
        if "seitenkopfStatus" in text:
            verstoesse.append(f"{name}: setzt seitenkopfStatus an seitenkopf() vorbei")
    assert verstoesse == []


def test_waechter_findet_verstoesse(tmp_path, monkeypatch):
    """Gegenprobe des Scanners an erfundenen Vorlagen."""
    (tmp_path / "a.html").write_text("<script>seitenkopf({titel:'x',status:{text:'Beauftragt',art:'info'}});</script>", encoding="utf-8")
    (tmp_path / "b.html").write_text("<script>seitenkopf({status:statusKennzeichen('auftrag',o.x?'erledigt':o.status)});</script>",
                                     encoding="utf-8")
    (tmp_path / "c.html").write_text("<script>seitenkopf({pfad:[],status:statusKennzeichen('auftrag',o.status)});</script>",
                                     encoding="utf-8")
    monkeypatch.setattr(vj, "TEMPLATES", tmp_path)
    assert [e for _, e in status_in_seitenkopf("a.html")] == [""]
    assert [e for _, e in status_in_seitenkopf("b.html")] == ["auftrag", "auftrag=erledigt"]
    assert [e for _, e in status_in_seitenkopf("c.html")] == ["auftrag"]
