"""Seit 1.9.25 (Stufe 2, Runde 9, Punkt 3): Seitenkopf der Monteursseiten, die bleiben -- Checkliste, Checklisten zum Auftrag, Objekt der
Monteursansicht, Betriebsmittel der Monteurin -- im Monteursrahmen mit Tablet-Maßen; ebenso Einsatzbericht und Konto der Monteurin.

    Tablet         der Kopf im Monteursrahmen trägt ds-kopf-tablet (seitenkopf(…, tablet=…)): Pfad 15 px, Titel 26 px, Knöpfe, Menüknopf
                   und Menüeinträge 48 px hoch (ds.css); im Büro (Leiste) der gewohnte Kopf
    Pfad           zurück zu „Einsätze“ (/mobil), die Checkliste eines Auftrags über „Checklisten zum Auftrag“ (der bisherige Rückweg);
                   das Büro über Checklisten bzw. den Auftrag; jedes feste Ziel öffnet sich für die Rolle (200 ohne Umleitung)
    kein alter     kein „← …“ (.back, .back-link), genau ein h1 (die Abschnitte des Objekts als h2)

Im Browser prüft das scripts/klicktest_rahmen.py, Teil „monteursseiten“ (Maße, Pfad nach dem Laden, Status, PDF).
"""

import re

import pytest

from app.design_dateien import STATIC_DIR
from tests import vorlagen_js as vj
from tests.test_v441_rahmen_baustein import MONTEURSSEITEN

# Adresse je Seite; Rollen: (Rolle, Tablet?, feste Pfad-Links vor dem Laden)
FAELLE = [
    ("/checklisten/1", "field", True, [("/mobil", "Heute")]),
    ("/checklisten/1", "buero_auftrag", False, [("/checklisten", "Checklisten")]),
    ("/checklisten/auftrag/1", "field", True, [("/mobil", "Heute")]),
    # seit 1.9.129 vor dem Laden ohne den Auftrag (er führt in die Akte, dafür fehlt dort das Projekt; bis 1.9.128 fest „/orders/1“)
    ("/checklisten/auftrag/1", "buero_auftrag", False, [("/checklisten", "Checklisten")]),
    ("/mobil/objekt/1", "field", True, [("/mobil", "Heute")]),
    ("/mobil/objekt/1", "buero_auftrag", True, [("/mobil", "Heute")]),  # die Seite steht für jede Rolle im Monteursrahmen
    ("/mobil/offen", "field", True, [("/mobil", "Heute")]),  # seit 1.9.49 „Heute / Offen“
    ("/mobil/offen", "buero_auftrag", True, [("/mobil", "Heute")]),
    ("/betriebsmittel/1", "field", True, [("/mobil", "Heute")]),
    ("/orders/1/service-reports", "field", True, [("/mobil", "Heute")]),  # Einsatzbericht
    ("/orders/1/service-reports", "buero_auftrag", False, [("/projects", "Projekte")]),
    ("/account", "field", True, [("/mobil", "Heute")]),
    ("/account", "buero_auftrag", False, [("/", "Start")]),
]


def test_die_vier_monteursseiten_sind_umgezogen():
    assert MONTEURSSEITEN == {"checklist.html", "checklist_order.html", "mobil_objekt.html", "operational_asset_field.html"}


@pytest.mark.parametrize("adresse,rolle,tablet,glieder", FAELLE)
def test_kopf_im_monteursrahmen_mit_tablet_massen(threaded_db_session, router_test_client, feste_uhr, adresse, rolle, tablet, glieder):
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role=rolle)
    antwort = client.get(adresse, follow_redirects=False)
    assert antwort.status_code == 200, antwort.status_code
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    kopf = re.search(r'<header class="([^"]*)" id="seitenkopf">', markup).group(1)
    assert kopf == ("ds-kopf ds-kopf-tablet" if tablet else "ds-kopf"), kopf
    assert ('id="mobileHeaderWrap"' in markup) is tablet  # Tablet-Maße genau im Monteursrahmen
    nav = re.search(r'<nav class="ds-kopf-pfad" id="seitenkopfPfad" aria-label="Pfad">(.*?)</nav>', markup, flags=re.S).group(1)
    assert re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav) == glieder
    assert not re.search(r'class="back(-link)?\b', markup) and markup.count("<h1") == 1
    for ziel, _ in glieder:
        z = client.get(ziel, follow_redirects=False)
        assert z.status_code == 200 and z.headers["content-type"].startswith("text/html"), (ziel, z.status_code)


def test_ds_css_tablet_masse_des_kopfs():
    css = (STATIC_DIR / "ds" / "ds.css").read_text(encoding="utf-8")
    assert re.search(r"--ds-groesse-4:\s*15px;", css) and re.search(r"--ds-groesse-9-tablet:\s*26px;", css)
    assert re.search(r"\.ds-kopf-tablet \.ds-kopf-pfad \{\s*font-size: var\(--ds-groesse-4\);\s*\}", css)
    assert re.search(r"\.ds-kopf-tablet \.ds-kopf-titel \{\s*font-size: var\(--ds-groesse-9-tablet\);\s*\}", css)
    assert re.search(r"\.ds-kopf-tablet \.ds-knopf,\s*\.ds-kopf-tablet \.ds-menue-eintrag \{\s*height: 48px;\s*min-height: 48px;\s*\}", css)
    assert re.search(r"\.ds-kopf-tablet \.ds-knopf-symbol \{\s*width: 48px;\s*\}", css)


@pytest.mark.parametrize("name,ausdruck", [
    ("checklist.html", "tablet=is_field"), ("checklist_order.html", "tablet=is_field"), ("mobil_objekt.html", "tablet=true"),
    ("operational_asset_field.html", "tablet=true"), ("service_reports.html", "tablet=monteursrahmen"), ("account.html", "tablet=monteursrahmen"),
    ("mobil_offen.html", "tablet=true"), ("service_report.html", "tablet=monteursrahmen"),
])
def test_jede_seite_im_monteursrahmen_nimmt_die_tablet_variante(name, ausdruck):
    text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    aufruf = re.search(r"\{%\s*call\(teil\)\s*seitenkopf\(([^%]*)\)\s*%\}", text).group(1)
    assert ausdruck in aufruf, aufruf


def test_checkliste_pfad_nach_dem_laden_ueber_den_bisherigen_rueckweg():
    """Der Pfad der Checkliste nach dem Laden: Bereich (Büro Checklisten, Monteur Einsätze), dann der Kontext mit dem bisherigen Rückweg
    (backLink(): Monteur „Checklisten zum Auftrag“, Büro der Auftrag), am Ende der Titel; Status nur über statusKennzeichen('checkliste')."""
    skript = vj.eigene_skripte("checklist.html").text
    kopf = skript[skript.index("function kopfZeichnen()"):skript.index("function renderHeader()")]
    assert "IS_FIELD?{text:'Heute',href:'/mobil'}:{text:'Checklisten',href:'/checklisten'}" in kopf
    assert "{text:cl.context_label,href:zurueck}" in kopf and "const zurueck=backLink();" in kopf
    assert "status:statusKennzeichen('checkliste',cl.status)" in kopf
    rueck = skript[skript.index("function backLink()"):skript.index("function answerOf(")]
    assert "IS_FIELD?`/checklisten/auftrag/${cl.order_id}`:`/orders/${cl.order_id}#ausfuehrung`" in rueck  # seit 1.9.129 auf den Reiter der Akte
