"""Version 1.9.149 (Stufe 6, R1, Punkt 7, aus Stufe 5):

    Dateien        im Verlauf von Kunde und Projekt „hochgeladen“ statt „angelegt“ (Überschrift und Einzelheiten), das Protokoll selbst bleibt „angelegt“; gelöscht bleibt gelöscht
    Einzelheiten   nur, wenn sie mehr zeigen als die Zeile: nicht bei einer einzigen Änderung, wohl bei mehreren und beim Versand
    Projektzeile   „abgerechnet … · unbezahlt …“ unter dem Namen, rechts nur die Summe (gemessen im Klicktest: der Name wird bei 1440 px nicht gekürzt)
"""

import re
from pathlib import Path
from types import SimpleNamespace

from app.akte_verlauf import _einzelheit, ueberschrift
from tests.node_lauf import node_lauf
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v555_kundenakte_zahlen import welt  # noqa: F401  (Fixture)
from tests.test_v557_kundenakte_seite import ZEICHNEN, _lauf, akte_welt  # noqa: F401  (Fixture)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"


class Zeile(SimpleNamespace):
    def model_dump(self):
        return dict(self.__dict__)


def _gruppe(*zeilen, versand=None):
    return SimpleNamespace(zeilen=list(zeilen), versand=versand)


def _zeile(typ, aktion, name="plan.pdf", **mehr):
    return Zeile(**{"entity_type": typ, "entity_type_label": typ, "entity_label": name, "action": aktion, "field_name": None, "field_label": None, "old_value": None, "new_value": None,
                    "details": None, "entity_id": "7", "einheit": None, **mehr})


def test_datei_im_verlauf_hochgeladen():
    for typ in ("Kundendokument", "Projektdatei"):
        assert ueberschrift(_gruppe(_zeile(typ, "angelegt")))[0] == f"{typ} plan.pdf hochgeladen"
        assert ueberschrift(_gruppe(_zeile(typ, "gelöscht")))[0] == f"{typ} plan.pdf gelöscht"
        assert _einzelheit(_zeile(typ, "angelegt"))["kurz"] == f"{typ} plan.pdf hochgeladen"
        assert "kurz" not in _einzelheit(_zeile(typ, "gelöscht"))


def test_anderes_bleibt_angelegt():
    assert ueberschrift(_gruppe(_zeile("Objekt", "angelegt", name="Halle")))[0] == "Objekt Halle angelegt"
    assert "kurz" not in _einzelheit(_zeile("Objekt", "angelegt", name="Halle"))


def _verlauf_js(ausdruck):
    html = (TEMPLATES / "_verlauf.html").read_text(encoding="utf-8")
    skript = html[html.index("<script>") + 8:html.index("</script>")]
    return node_lauf(skript + f"\nconsole.log(JSON.stringify({ausdruck}));").stdout.strip()


@nur_mit_node
def test_einzelheiten_nur_wenn_sie_mehr_zeigen():
    assert _verlauf_js("[verlaufMehrEinzelheiten({einzelheiten:[]}),verlaufMehrEinzelheiten({})]") == "[false,false]"
    assert _verlauf_js("verlaufMehrEinzelheiten({einzelheiten:[{field_name:'status'}]})") == "false"  # steht schon in der Überschrift
    assert _verlauf_js("verlaufMehrEinzelheiten({einzelheiten:[{field_name:'status'},{field_name:'notes'}]})") == "true"
    assert _verlauf_js("verlaufMehrEinzelheiten({einzelheiten:[{field_name:'status'}],versand:{document_id:1}})") == "true"  # die Überschrift nennt den Versand


def test_akte_und_kundenakte_fragen_dieselbe_regel():
    for name in ("akte.html", "customer.html"):
        html = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "const details=verlaufMehrEinzelheiten(e)?" in html, name
        assert "e.einzelheiten[0].field_name" not in html, name


@nur_mit_node
def test_abrechnung_steht_unter_dem_namen_rechts_nur_die_summe(akte_welt):  # noqa: F811
    html = _lauf(akte_welt, ZEICHNEN)["ergebnis"]["projekte"]
    assert html.count('class="num sml mut projekt-abrechnung"') == html.count('class="li-rechts"') >= 1
    for rechts in re.findall(r'class="li-rechts">(.*?)</div>', html):
        assert "abgerechnet" not in rechts and "beauftragt" not in rechts and "netto" in rechts
