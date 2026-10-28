"""Version 1.9.117 (Stufe 5, R1, Punkt 7, Befund F6/F15): Mustervorgang nicht beauftragbar, „Projekt löschen“ nur ohne Auftrag.

    F6   Das Angebot eines Mustervorgangs (Project.is_template) wird nicht beauftragt: 409 mit Weg, kein Auftrag (bis 1.9.116 ging das); der
         Angebots-Editor zeigt statt „Angebot beauftragen“ den Hinweis; die Projektmappe kennzeichnet einen Mustervorgang. Gegenprobe: dasselbe Angebot
         nach „Neuen Vorgang erstellen“ (duplicate_project) lässt sich beauftragen.
    F15  „Löschen“ gibt es in Projektliste und Projektmappe nur ohne Auftrag (der Server lehnt mit Auftrag ab -- unverändert 400).
"""

import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Order, Project, Quote
from app.orders import MUSTERVORGANG_TEXT, MustervorgangNichtBeauftragbar, create_order_from_quote
from app.projects import duplicate_project
from app.routers.quotes import router as quotes_router
from tests.test_v192_project_templates import make_full_project
from tests.test_v334_auswahl_restfaelle import FAKE_DOM, im_browser, nur_mit_node, seite

VORLAGEN = Path(__file__).resolve().parent.parent / "app" / "templates"
BEAUFTRAGEN = {"order_date": "2026-10-28", "execution_start": None, "execution_end": None, "caseworker_employee_id": None,
               "project_manager_employee_id": None, "payment_terms": None, "remarks": None}


def _muster(db):
    project = make_full_project(db)
    quote = db.scalar(select(Quote).where(Quote.project_id == project.id))
    project.is_template = True
    db.commit()
    return project, quote


def test_angebot_eines_mustervorgangs_409(threaded_db_session, router_test_client):
    db = threaded_db_session
    _, quote = _muster(db)
    antwort = router_test_client(db, quotes_router, role="buero_auftrag").post(f"/api/quotes/{quote.id}/convert-to-order", json=BEAUFTRAGEN)
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == MUSTERVORGANG_TEXT
    assert db.scalar(select(func.count()).select_from(Order)) == 0
    assert router_test_client(db, quotes_router).get(f"/api/quotes/{quote.id}").json()["project_is_template"] is True


def test_gegenprobe_neuer_vorgang_aus_dem_muster_laesst_sich_beauftragen(threaded_db_session, router_test_client):
    db = threaded_db_session
    muster, _ = _muster(db)
    neu = duplicate_project(db, muster, as_template=False)
    neues_angebot = db.scalar(select(Quote).where(Quote.project_id == neu.id))
    antwort = router_test_client(db, quotes_router).post(f"/api/quotes/{neues_angebot.id}/convert-to-order", json=BEAUFTRAGEN)
    assert antwort.status_code == 200, antwort.text
    assert router_test_client(db, quotes_router).get(f"/api/quotes/{neues_angebot.id}").json()["project_is_template"] is False


def test_fachfunktion_wirft_auch_ohne_router():
    from tests.test_v133_invoices import db_session
    db = db_session()
    _, quote = _muster(db)
    with pytest.raises(MustervorgangNichtBeauftragbar):
        create_order_from_quote(db, quote.id, order_date=date(2026, 10, 28), execution_start=None, execution_end=None,
                                caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)


def _auftragsknopf() -> str:
    """Der Teil von renderAll() bis zum Seitenkopf -- Hauptknopf, Link und Hinweis zum Auftrag (der Rest braucht die ganze Seite)."""
    text = (VORLAGEN / "quote_editor.html").read_text(encoding="utf-8")
    rumpf = re.search(r"function renderAll\(\)\{(.*?)/\* seit 1\.9\.18", text, re.S).group(1)
    return ("var existingOrder=null, quote=null;\nfunction renderBreadcrumb(){}\nfunction openOrderDialog(){}\n"
            "function auftragsknopf(){" + rumpf + "}")


@nur_mit_node
@pytest.mark.parametrize("muster", [True, False])
def test_editor_zeigt_hinweis_statt_beauftragen(muster):
    ablauf = (f"quote = {{project_is_template: {str(muster).lower()}}}; auftragsknopf();"
              "return [_element('orderButton').hidden === true, _element('orderButton').textContent || '', _element('orderSyncBanner').innerHTML];")
    versteckt, knopf, hinweis = im_browser(FAKE_DOM + "\n" + _auftragsknopf(), ablauf)["ergebnis"]
    assert versteckt is muster
    assert knopf == ("" if muster else "Angebot beauftragen")
    assert ("Mustervorgang." in hinweis and "Neuen Vorgang erstellen" in hinweis) is muster


@nur_mit_node
@pytest.mark.parametrize("nur_muster", [False, True])
def test_projektliste_loeschen_nur_ohne_auftrag(nur_muster):
    ablauf = (f"onlyTemplates = {str(nur_muster).lower()};"
              "return [menuItemsFor({id: 1, order_count: 0, archived: false}).includes('deleteProjectRow(1)'),"
              " menuItemsFor({id: 2, order_count: 1, archived: false}).includes('deleteProjectRow(2)')];")
    assert im_browser(seite("projects.html", "load().catch("), ablauf)["ergebnis"] == [True, False]


def test_projektmappe_kennzeichnet_muster_und_loeschen_nur_ohne_auftrag():
    text = (VORLAGEN / "project_folder.html").read_text(encoding="utf-8")
    assert ("document.getElementById('templateBadge').hidden=!project.is_template;"
            "document.getElementById('deleteMenuItem').hidden=(project.order_count||0)>0;") in text
    assert 'id="templateBadge" class="badge" data-mustervorgang hidden>Mustervorgang</span>' in text
    assert 'id="deleteMenuItem"' in text
