"""Version 1.9.118 (Stufe 5, R1, Punkt 8, Befund B12): lesbare Fehler auch in der Berichtsliste („Einsatzberichte“) und im Objekt (mobil).

Bis 1.9.117 reichten beide Seiten detail unverändert an Error() weiter -- eine 422-Liste der Schemaprüfung erschien als „[object Object]“. Jetzt über
fehlerText() (_fehlertext.html) mit den Feldnamen der Seite; ein Text (400/404/409) bleibt wörtlich.
"""

import json
import re
from pathlib import Path

import pytest

from tests import vorlagen_js
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v314_dashboard_month_berlin import _node

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"
LISTE_BERICHT = {"detail": [{"type": "missing", "loc": ["body", "report_type"], "msg": "Field required"},
                            {"type": "date_parsing", "loc": ["body", "performed_at"], "msg": "Input should be a valid date"}]}
LISTE_OBJEKT = {"detail": [{"type": "int_parsing", "loc": ["body", "category_id"], "msg": "Input should be a valid integer"},
                           {"type": "missing", "loc": ["body", "file"], "msg": "Field required"}]}


@pytest.mark.parametrize("vorlage", ["service_reports.html", "mobil_objekt.html"])
def test_bindet_fehlertext_ein_und_reicht_detail_nicht_roh_weiter(vorlage):
    text = (VORLAGEN / vorlage).read_text(encoding="utf-8")
    assert vorlagen_js.bindet_ein(vorlage, "_fehlertext.html", wurzel=VORLAGEN)
    assert "fehlerText(" in text
    assert not re.search(r"Error\(\s*\(?\s*(?:await\s+r\.json\(\)[^)]*\)\s*\)?\.detail|d\.detail)", text), "detail roh an Error()"


def _api_der_seite(vorlage: str) -> str:
    text = (VORLAGEN / vorlage).read_text(encoding="utf-8")
    m = re.search(r"(async function api\(u,o\)\{.*?\n?\s*\}\n?)", text, re.S)
    felder = re.search(r"((?:const|var) FELDNAMEN=\{[^}]*\};)", text).group(1)
    return felder + "\n" + re.search(r"async function api\(u,o\)\{.*?return r\.json\(\);?\s*\}", text, re.S).group(0)


@nur_mit_node
@pytest.mark.parametrize("vorlage, liste, erwartet", [
    ("service_reports.html", LISTE_BERICHT, "Bitte die Eingabe prüfen – Berichtstyp fehlt; Datum des Einsatzes ist kein gültiges Datum."),
    ("mobil_objekt.html", LISTE_OBJEKT, "Bitte die Eingabe prüfen – Kategorie muss eine ganze Zahl sein; Datei fehlt."),
])
def test_eine_422_liste_erscheint_lesbar(vorlage, liste, erwartet):
    baustein = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_fehlertext.html").read_text(encoding="utf-8"), re.S))
    skript = (baustein + "\n" + _api_der_seite(vorlage) +
              f"\nglobalThis.fetch=async()=>({{ok:false,status:422,statusText:'Unprocessable',json:async()=>({json.dumps(liste)})}});"
              "\napi('/x').catch(e=>process.stdout.write(JSON.stringify(e.message)));")
    assert _node(skript, "Europe/Berlin") == erwartet


@nur_mit_node
def test_ein_text_bleibt_woertlich():
    baustein = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_fehlertext.html").read_text(encoding="utf-8"), re.S))
    skript = (baustein + "\n" + _api_der_seite("service_reports.html") +
              "\nglobalThis.fetch=async()=>({ok:false,status:409,statusText:'Conflict',json:async()=>({detail:'Der Bericht ist schon unterschrieben.'})});"
              "\napi('/x').catch(e=>process.stdout.write(JSON.stringify(e.message)));")
    assert _node(skript, "Europe/Berlin") == "Der Bericht ist schon unterschrieben."
