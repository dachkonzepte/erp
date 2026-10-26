"""Seit 1.9.88 (Stufe 4, R5, Teil 1 Punkt 2; Beschluss aus Stufe 2): der Monteursrahmen setzt .ds-tablet.

    Klasse     jede Seite, die den Monteurskopf einbindet (_mobile_header.html), setzt am <body> ds-tablet -- unter derselben Bedingung wie
               die Einbindung (monteursrahmen, is_field) oder immer; die Büroansicht derselben Vorlage bleibt ohne
    Wirkung    ds-basis.css: Knöpfe und Felder 12 px (--ds-ecke-tablet-feld), Grundschrift 17 px, seit 1.9.88 Knöpfe, Auswahlen und
               einzeilige Felder mindestens 48 px hoch; ds.css: Seitentitel 26 px, seit 1.9.88 auch der Knopf des Seitenkopfs (.ds-knopf)
               12 px; „Zeit nachtragen“ (ein Link als Knopf) ebenso; die Segmentgruppe des Berichts innen ohne Ecke
Gemessen auf jeder Seite der Monteurin: scripts/klicktest_tablet.py (Ecken, Seitentitel, Ziele ≥ 48 px, Dialog).
"""

import re

from app.routers import pages as pages_router
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee

KOPF = '{% include "_mobile_header.html" %}'


def _monteursseiten():
    seiten = {}
    for name in vj.alle_vorlagen():
        if name.startswith("_") or "/" in name or not vj.bindet_ein(name, "_mobile_header.html", nur_selbst=True):
            continue
        seiten[name] = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    return seiten


def test_jede_monteursseite_setzt_ds_tablet_unter_derselben_bedingung():
    seiten = _monteursseiten()
    assert set(seiten) >= {"mobil.html", "mobil_zeiten.html", "mobil_offen.html", "mobil_objekt.html", "service_report.html",
                           "service_reports.html", "account.html", "checklist.html", "checklist_order.html", "operational_asset_field.html"}
    falsch = []
    for name, text in seiten.items():
        body = re.search(r"<body[^>]*>", text)[0]
        bedingung = re.search(r"\{% if (\w+) %\}" + re.escape(KOPF), text)
        if bedingung is None:
            ok = re.search(r'class="[^"{]*\bds-tablet\b', body) is not None
        else:
            x = bedingung.group(1)
            ok = (f"{{% if {x} %}} ds-tablet{{% endif %}}" in body) or re.search(r"'[^']*\bds-tablet\b[^']*' if " + x + r"\b", body) is not None
        if not ok:
            falsch.append(f"{name}: {body}")
    assert falsch == []


def test_buero_ansicht_ohne_ds_tablet(threaded_db_session, router_test_client):
    """Dieselbe Vorlage: die Monteurin bekommt ds-tablet, das Büro nicht (Einsatzberichte des Auftrags)."""
    db = threaded_db_session
    mia = make_employee(db, "M-509", "Mia", "Monteurin")
    for rolle, emp, soll in (("field", mia.id, True), ("buero_auftrag", None, False)):
        client = router_test_client(db, pages_router.router, role=rolle, employee_id=emp)
        for pfad in ("/orders/1/service-reports", "/account"):
            antwort = client.get(pfad)
            assert antwort.status_code == 200, (rolle, pfad, antwort.status_code)
            body = re.search(r"<body[^>]*>", antwort.text)[0]
            assert ("ds-tablet" in body) is soll, (rolle, pfad, body)


def test_ds_css_und_zeit_nachtragen_mit_der_tablet_ecke():
    ds = (vj.TEMPLATES.parent / "static" / "ds" / "ds.css").read_text(encoding="utf-8")
    assert re.search(r"\.ds-tablet \.ds-knopf \{\s*border-radius: var\(--ds-ecke-tablet-feld\);\s*\}", ds)
    assert re.search(r"\.ds-tablet \.ds-kopf-titel \{\s*font-size: var\(--ds-groesse-9-tablet\);\s*\}", ds)
    basis = (vj.TEMPLATES.parent / "static" / "ds" / "ds-basis.css").read_text(encoding="utf-8")
    assert re.search(r":where\(\.ds-seite\.ds-tablet input, \.ds-seite\.ds-tablet select, \.ds-seite\.ds-tablet textarea, "
                     r"\.ds-seite\.ds-tablet button\) \{\s*border-radius: var\(--ds-ecke-tablet-feld\);", basis)
    assert re.search(r":where\(\.ds-seite\.ds-tablet button, \.ds-seite\.ds-tablet select,\s*\.ds-seite\.ds-tablet input:not\(\[type=\"checkbox\"\]\)"
                     r":not\(\[type=\"radio\"\]\):not\(\[type=\"hidden\"\]\):not\(\[type=\"file\"\]\)\) \{\s*min-height: 48px;", basis)
    seite = vj.seitentext("service_reports.html")[0]
    assert ".ds-tablet .zeit-nachtragen{border-radius:var(--ds-ecke-tablet-feld)}" in seite
    bericht = vj.seitentext("service_report.html")[0]
    assert re.search(r"\.segment\{[^}]*border-left-width:0;border-radius:0;", bericht)  # der mittlere Knopf ohne Ecke
