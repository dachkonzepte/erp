"""Version 1.9.120 (Stufe 5, R1 Nachrunde, Punkt 2): Einstellungen mit Geld -- Mahnstufen (Fristen, Gebühren, Texte), Zahlungsbedingungen,
Steuerschlüssel, Nummernkreise -- speichern nur Admin und Büro – Finanzen (darf_geld()); bis 1.9.119 jedes Büro (Festlegung 1.9.111 Nr. 1
und 5, nicht bestätigt).

    Struktur    jede schreibende Route der Zahlungsbedingungen und Steuerschlüssel, PUT Mahnstufe und PUT Nummernkreis: Rollen Admin und
                Büro – Finanzen, Meldung EINSTELLUNGEN_GELD_NUR_LESEN
    Rundgang    alle 12 Aktionen als Büro – Auftrag 403 und nichts geändert; als Büro – Finanzen und Admin 200 und geschrieben; Lesen
                bleibt jedem Büro
    Seite       Büro – Auftrag: Hinweis in jedem der vier Bereiche, kein „+ Zahlungsbedingung“/„+ Steuerschlüssel“, „Ansehen“ statt
                „Bearbeiten“ ohne Standard/Archivieren, die Texte einer Mahnstufe unter E-Mail-Vorlagen gesperrt; Büro – Finanzen wie bisher
"""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

from app.models import NumberSequence, PaymentTerm, ReminderLevel, TaxKey
from app.permissions import EINSTELLUNGEN_GELD_NUR_LESEN, GELD_ROLLEN
from app.routers.pages import router as pages_router
from app.routers.payment_terms import router as payment_terms_router
from app.routers.reminders import router as reminders_router
from app.routers.settings import router as settings_router
from app.routers.tax_keys import router as tax_keys_router
from tests.gerenderte_seite import gerenderte_seite
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node

ROUTER = (payment_terms_router, tax_keys_router, reminders_router, settings_router)
EINSTELLUNGEN_MIT_GELD = {
    ("POST", "/api/payment-terms"), ("PUT", "/api/payment-terms/{term_id}"), ("POST", "/api/payment-terms/{term_id}/set-default"),
    ("POST", "/api/payment-terms/{term_id}/archive"), ("POST", "/api/payment-terms/{term_id}/unarchive"),
    ("POST", "/api/tax-keys"), ("PUT", "/api/tax-keys/{key_id}"), ("POST", "/api/tax-keys/{key_id}/set-default"),
    ("POST", "/api/tax-keys/{key_id}/archive"), ("POST", "/api/tax-keys/{key_id}/unarchive"),
    ("PUT", "/api/reminder-levels/{level_id}"), ("PUT", "/api/settings/number-sequences/{sequence_key}"),
}
STAND = (PaymentTerm, TaxKey, ReminderLevel, NumberSequence)


def _rollen_und_meldungen(route):
    funde, offen = [], list(route.dependant.dependencies)
    while offen:
        dep = offen.pop()
        if getattr(dep.call, "_dk_roles", None) is not None:
            funde.append((dep.call._dk_roles, getattr(dep.call, "_dk_message", None)))
        offen.extend(dep.dependencies)
    return funde


def test_jede_schreibende_route_nur_admin_und_finanzen():
    gesehen = {}
    for router in ROUTER:
        for route in router.routes:
            for methode in getattr(route, "methods", set()) - {"GET", "HEAD"}:
                if (methode, route.path) in EINSTELLUNGEN_MIT_GELD:
                    gesehen[(methode, route.path)] = _rollen_und_meldungen(route)
    assert set(gesehen) == EINSTELLUNGEN_MIT_GELD
    for schluessel, funde in gesehen.items():
        assert funde and all(rollen <= GELD_ROLLEN for rollen, _ in funde), (schluessel, funde)
    # die Zahlungsbedingungen und Steuerschlüssel lesen weiter jedes Büro
    for router in (payment_terms_router, tax_keys_router):
        for route in router.routes:
            if route.methods & {"GET"}:
                assert any("buero_auftrag" in rollen for rollen, _ in _rollen_und_meldungen(route)), route.path


def _stand(db):
    db.expire_all()
    return {m.__name__: sorted(tuple(str(getattr(o, c.key)) for c in sa_inspect(m).mapper.column_attrs) for o in db.scalars(select(m)))
            for m in STAND}


def _vorbereitet(db):
    """Eine zweite, archivierte Zahlungsbedingung und ein zweiter, archivierter Steuerschlüssel -- für Standard und Wiederherstellen."""
    zb = PaymentTerm(label="30 Tage netto", days=30, archived=False)
    zb_alt = PaymentTerm(label="60 Tage netto", days=60, archived=True)
    sk = TaxKey(label="Ermäßigt", vat_rate=7, archived=False)
    sk_alt = TaxKey(label="Alt", vat_rate=16, archived=True)
    db.add_all([zb, zb_alt, sk, sk_alt])
    db.commit()
    stufe = db.scalars(select(ReminderLevel).order_by(ReminderLevel.level)).first()
    kreis = db.scalars(select(NumberSequence).where(NumberSequence.sequence_key == "customer")).one()
    return {"zb": zb.id, "zb_alt": zb_alt.id, "sk": sk.id, "sk_alt": sk_alt.id, "stufe": stufe.id, "kreis": kreis}


def _aktionen(ids):
    k = ids["kreis"]
    return [
        ("POST", "/api/payment-terms", {"label": "21 Tage netto", "days": 21}),
        ("PUT", f"/api/payment-terms/{ids['zb']}", {"label": "30 Tage rein netto", "days": 30}),
        ("POST", f"/api/payment-terms/{ids['zb']}/set-default", None),
        ("POST", f"/api/payment-terms/{ids['zb']}/archive", None),
        ("POST", f"/api/payment-terms/{ids['zb_alt']}/unarchive", None),
        ("POST", "/api/tax-keys", {"label": "Solar", "vat_rate": "0"}),
        ("PUT", f"/api/tax-keys/{ids['sk']}", {"label": "Ermäßigt 7", "vat_rate": "7"}),
        ("POST", f"/api/tax-keys/{ids['sk']}/set-default", None),
        ("POST", f"/api/tax-keys/{ids['sk']}/archive", None),
        ("POST", f"/api/tax-keys/{ids['sk_alt']}/unarchive", None),
        ("PUT", f"/api/reminder-levels/{ids['stufe']}", {"label": "Zahlungserinnerung", "days_after_previous_step": 10}),
        ("PUT", "/api/settings/number-sequences/customer",
         {"format_pattern": k.format_pattern, "start_value": k.start_value, "next_value": k.next_value + 5, "reset_yearly": k.reset_yearly}),
    ]


def test_rundgang_deckt_jede_route():
    from starlette.routing import compile_path
    pfade = {(m, compile_path(p)[0]) for m, p in EINSTELLUNGEN_MIT_GELD}
    abgedeckt = {(m, next(r for mm, r in pfade if mm == m and r.match(url))) for m, url, _ in _aktionen(
        {"zb": 1, "zb_alt": 2, "sk": 3, "sk_alt": 4, "stufe": 5,
         "kreis": NumberSequence(format_pattern="K-{NNNN}", start_value=1, next_value=1, reset_yearly=False)})}
    assert abgedeckt == pfade


@pytest.mark.parametrize("nr", range(12))
def test_buero_auftrag_403_und_nichts_geaendert(threaded_db_session, router_test_client, nr):
    db = threaded_db_session
    methode, url, body = _aktionen(_vorbereitet(db))[nr]
    vorher = _stand(db)
    antwort = router_test_client(db, *ROUTER, role="buero_auftrag").request(methode, url, json=body)
    assert (antwort.status_code, antwort.json()["detail"]) == (403, EINSTELLUNGEN_GELD_NUR_LESEN)
    assert _stand(db) == vorher


@pytest.mark.parametrize("rolle", ["buero_finanzen", "admin"])
@pytest.mark.parametrize("nr", range(12))
def test_finanzen_und_admin_200_und_geschrieben(threaded_db_session, router_test_client, nr, rolle):
    db = threaded_db_session
    methode, url, body = _aktionen(_vorbereitet(db))[nr]
    vorher = _stand(db)
    antwort = router_test_client(db, *ROUTER, role=rolle).request(methode, url, json=body)
    assert antwort.status_code == 200, antwort.text
    assert _stand(db) != vorher


@pytest.mark.parametrize("url", ["/api/payment-terms", "/api/tax-keys", "/api/reminder-levels", "/api/settings/number-sequences"])
def test_buero_auftrag_liest(threaded_db_session, router_test_client, url):
    assert router_test_client(threaded_db_session, *ROUTER, role="buero_auftrag").get(url).status_code == 200


def _seite(db, router_test_client, rolle):
    antwort = router_test_client(db, pages_router, role=rolle).get("/settings")
    assert antwort.status_code == 200
    return antwort.text


def test_seite_buero_auftrag_liest_nur(threaded_db_session, router_test_client):
    html = _seite(threaded_db_session, router_test_client, "buero_auftrag")
    assert html.count(f'<div class="hint" data-geld-nur-lesen>{EINSTELLUNGEN_GELD_NUR_LESEN}</div>') == 4
    assert "const GELD=\"nein\"!==\"nein\";" in html
    assert "+ Zahlungsbedingung" not in html and "+ Steuerschlüssel" not in html
    finanzen = _seite(threaded_db_session, router_test_client, "buero_finanzen")
    assert "data-geld-nur-lesen" not in finanzen and "const GELD=\"ja\"!==\"nein\";" in finanzen
    assert "+ Zahlungsbedingung" in finanzen and "+ Steuerschlüssel" in finanzen


BEDINGUNGEN = ("paymentTerms=[{id:1,label:'14 Tage',days:14,is_default:true,archived:false},{id:2,label:'30 Tage',days:30,is_default:false,"
               "archived:false},{id:3,label:'60 Tage',days:60,is_default:false,archived:true}];renderPaymentTerms();"
               "taxKeys=[{id:4,label:'Regel',vat_rate:'19.00',is_default:false,archived:false}];renderTaxKeys();")


@nur_mit_node
@pytest.mark.parametrize("rolle, erwartet", [
    ("buero_auftrag", {"knoepfe": ["Ansehen", "Ansehen", "Ansehen", "Ansehen"], "gesperrt": [True, True, False]}),
    ("buero_finanzen", {"knoepfe": ["Bearbeiten", "Bearbeiten", "Als Standard", "Archivieren", "Bearbeiten", "Wiederherstellen",
                                    "Bearbeiten", "Als Standard", "Archivieren"], "gesperrt": [False, False, True]}),
])
def test_listen_und_mahnstufe_unter_e_mail_vorlagen(threaded_db_session, router_test_client, rolle, erwartet):
    skript = gerenderte_seite(_seite(threaded_db_session, router_test_client, rolle), "load().catch(")
    ablauf = (BEDINGUNGEN +
              "const knoepfe=[..._element('paymentTermRows').innerHTML.matchAll(/<button[^>]*>([^<]*)<\\/button>/g),"
              "..._element('taxKeyRows').innerHTML.matchAll(/<button[^>]*>([^<]*)<\\/button>/g)].map(m=>m[1]);"
              "reminderLevels=[{id:7,level:1,label:'1. Mahnung'}];_element('emailTemplateType').value='reminder:1';await loadEmailTemplate();"
              "const gesperrt=[_element('emailTemplateSubject').disabled===true,_element('emailTemplateSave').hidden===true,"
              "_element('emailTemplateGeldHinweis').hidden===true];"
              "return {knoepfe,gesperrt};")
    lauf = im_browser(skript, ablauf, {"/api/reminder-levels": [{"id": 7, "level": 1, "label": "1. Mahnung",
                                                                "email_subject_template": "Mahnung", "email_body_template": "Text"}]})
    assert lauf["ergebnis"] == erwartet


@nur_mit_node
def test_angebot_unter_e_mail_vorlagen_bleibt_offen(threaded_db_session, router_test_client):
    """Nur die Texte einer Mahnstufe sind gesperrt -- die Vorlagen der anderen Dokumente speichert Büro – Auftrag wie bisher."""
    skript = gerenderte_seite(_seite(threaded_db_session, router_test_client, "buero_auftrag"), "load().catch(")
    ablauf = ("_element('emailTemplateType').value='quote';await loadEmailTemplate();"
              "return [_element('emailTemplateSubject').disabled,_element('emailTemplateSave').hidden,_element('emailTemplateGeldHinweis').hidden];")
    lauf = im_browser(skript, ablauf, {"/api/document-email-templates/quote": {"subject_template": "Angebot", "body_template": "Text"}})
    assert lauf["ergebnis"] == [False, False, True]
