"""Nachrunde 2 zur Fehlerrunde (1.8.151 ff., Vorgabe vom 19.10.2026): erst prüfen, dann je Punkt ein Test, der vor der Behebung scheiterte.

    1  Prüfung: zahlLesen() seit 1.8.148 (Tabelle) und Rundweg Menge/EP im Auftrag -- angezeigt mit Tausenderpunkt, unverändert
       gespeichert, derselbe Betrag in der Datenbank (1.8.151)
    2  Einsatzbericht: Auswahl „Mitarbeiter“ nur, wer laut Server für andere bucht -- in tests/test_v437_befund_zeit_fuer_andere.py
       (1.8.152)
    3  DELETE /api/teams/{id}: Rückfrage (409) bei laufender Gruppenzeit; mit Gruppenbuchungen deaktiviert statt gelöscht (1.8.153)
    4  Zurück-Links mit echtem Ziel statt history.back() in address_import.html, history.html, index.html (1.8.154)
"""

import html
import json
import re
from decimal import Decimal

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v414_zahleneingaben import _lesen
from tests.test_v437_befund_zeit_fuer_andere import _als, _gruppe_starten, _laufend, welt  # noqa: F401 (welt: Fixture)


# ---------------------------------------------------------------------------
# 1. Prüfung: zahlLesen() und der Rundweg im Auftrag
# ---------------------------------------------------------------------------

def test_zahllesen_tabelle_seit_1_8_148():
    """Die verlangte Tabelle Eingabe → Ergebnis (Regel 34: Komma dezimal, Punkt nur als Tausender vor je drei Ziffern)."""
    tabelle = {"1.234,50": 1234.5, "1.234": 1234, "1,5": 1.5, "1.5": "nicht eindeutig", "1234.5": "nicht eindeutig",
               "12.345.678,9": 12345678.9}
    ergebnis = _lesen([[t, {"feld": "Menge"}] for t in tabelle])
    gelesen = {t: (e["wert"] if "wert" in e else ("nicht eindeutig" if "nicht eindeutig" in e["fehler"] else e["fehler"]))
               for t, e in zip(tabelle, ergebnis)}
    assert gelesen == tabelle


RUNDWEG = r"""
  renderOrderEmailSection = () => {};  // Versand-Karte (_email_dispatch.html, nicht in der Attrappe) -- hier ohne Belang
  akteNachAenderung = () => {};  // seit 1.9.129: Kopf der Akte neu (GET /api/projects/{id}/akte) -- hier ohne Belang
  const puts = [];
  globalThis.fetch = async (url, opt = {}) => {
    if ((opt.method || 'GET') !== 'GET') puts.push({url, body: JSON.parse(opt.body)});
    const antwort = /^\/api\/orders\/\d+(\/items\/\d+)?$/.test(url) ? ORDER : /\/zahlen$/.test(url) ? null : [];  // Auftrag; Zahlen keine; sonst leer
    return {ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'}, json: async () => antwort};
  };
  order = JSON.parse(JSON.stringify(ORDER)); units = []; orderId = ORDER.id;
  const i = order.items[0];
  // seit 1.9.129 (Akte): die Zeile zeigt Menge und EP als Text (EP mit zwei Stellen), bearbeitet wird im Dialog
  const m = /<td class="r num">([^<]*)<\/td><td>[^<]*<\/td><td class="r num">([^<]*)<\/td>/.exec(rowHtml(i));
  const angezeigt = {menge: m[1], ep: m[2]};
  // Dialog der Position: geöffnet, unverändert gespeichert
  openItem(i.id);
  const dialog = {menge: _element('iQty').value, ep: _element('iPrice').value};
  await saveItemDialog();
  return {angezeigt, dialog, puts};
"""


@nur_mit_node
@pytest.mark.parametrize("menge,ep", [("12345.678", "1234.56"), ("1234.5", "1000"), ("1000000", "0.5"), ("0.125", "12345678.9")])
def test_auftrag_rundweg_menge_und_ep_mit_tausenderpunkt(threaded_db_session, router_test_client, menge, ep):
    """Angezeigt mit Tausenderpunkt (1.8.148), unverändert gespeichert ergibt in der Datenbank denselben Betrag. Die Anfragen baut das
    echte Seitenskript (node), gesendet werden sie an den echten Dienst. Seit 1.9.129 (Akte) nur noch aus dem Dialog der Position -- bis
    1.9.128 auch Menge und EP in der Zeile des LV (drei Anfragen)."""
    from app.models import OrderItem
    from app.routers.orders import router as orders_router
    from tests.test_v133_invoices import make_order_with_item

    db = threaded_db_session
    order, item = make_order_with_item(db, quantity=Decimal(menge), unit_price=Decimal(ep))
    client = router_test_client(db, orders_router, role="buero_finanzen")
    auftrag = client.get(f"/api/orders/{order.id}").json()
    lauf = im_browser(seite("akte.html", "akteStarten().catch("),
                      f"const ORDER = {json.dumps(auftrag)};" + RUNDWEG)["ergebnis"]
    assert len(lauf["puts"]) == 1, lauf["puts"]  # der Dialog (bis 1.9.128 dazu Menge und EP aus der Zeile)
    for put in lauf["puts"]:
        antwort = client.put(f"/api/orders/{order.id}/items/{item.id}", json=put["body"])
        assert antwort.status_code == 200, antwort.text
        db.expire_all()
        gespeichert = db.get(OrderItem, item.id)
        assert (gespeichert.quantity, gespeichert.unit_price) == (Decimal(menge), Decimal(ep)), (put["body"], lauf["angezeigt"])
    assert lauf["dialog"]["menge"] == lauf["angezeigt"]["menge"]  # EP: die Zeile mit zwei Stellen, der Dialog genau
    if Decimal(menge) >= 1000:
        assert "." in lauf["angezeigt"]["menge"]  # wirklich mit Tausenderpunkt angezeigt


# ---------------------------------------------------------------------------
# 3. DELETE /api/teams/{id}: Rückfrage bei laufender Gruppenzeit
# ---------------------------------------------------------------------------

def _team(welt, team_id):
    from app.models import Team

    with welt["sitzung"]() as db:
        team = db.get(Team, team_id)
        return None if team is None else team.active


def test_team_loeschen_bei_laufender_gruppenzeit_fragt_nach(welt):
    """Bis 1.8.152 löschte DELETE /api/teams/{id} ein Team ohne Rückfrage, auch während seine Gruppenzeit lief -- und ein Team ohne
    Arbeitsvorbereitung hart, obwohl die Gruppe darauf verweist. Seit 1.8.153 dieselbe Rückfrage wie beim Entziehen des Kennzeichens
    (409), mit Bestätigung deaktiviert (nicht gelöscht), gestoppt wird nichts."""
    ids, nord, sued = welt["ids"], welt["nord"], welt["sued"]
    gid = _gruppe_starten(welt, 2)
    ada = _als(welt, "Ada")

    antwort = ada.delete(f"/api/teams/{nord}")
    assert antwort.status_code == 409, antwort.text
    assert antwort.json()["detail"] == {"code": "laufende_gruppenzeit", "message": "Gruppenzeit läuft noch – trotzdem entziehen?"}
    assert _team(welt, nord) is True

    bestaetigt = ada.delete(f"/api/teams/{nord}?trotz_laufender_gruppenzeit=true")
    assert (bestaetigt.status_code, bestaetigt.json()) == (200, {"deleted": False, "deactivated": True}), bestaetigt.text
    assert _team(welt, nord) is False  # deaktiviert, die Gruppe verweist weiter darauf
    assert _laufend(welt) == (sorted([ids["Lea"], ids["Max"]]), [gid])  # nichts gestoppt

    # Kontrolle: ein Team ohne Gruppenzeit und ohne Gruppenbuchungen löscht ohne Rückfrage
    assert ada.delete(f"/api/teams/{sued}").json() == {"deleted": True}
    assert _team(welt, sued) is None


def test_team_mit_gruppenbuchungen_wird_unter_postgresql_deaktiviert():
    """Gegen PostgreSQL: ein Team ohne Arbeitsvorbereitung, aber mit einer (abgeschlossenen) Gruppenbuchung -- bis 1.8.152 ein hartes
    Löschen, das am Fremdschlüssel time_entry_groups.team_id scheiterte (IntegrityError, 500). Seit 1.8.153 deaktiviert."""
    from datetime import date

    from app.models import Team, TeamEmployee
    from app.routers.resource_planning import delete_team
    from app.time_tracking import create_group_manual_entry
    from tests.befund_vor_echtbetrieb import pg_sitzung
    from tests.test_v264_field_time_tracking import _employee
    from tests.test_v325_contract_basis import beauftragen, make_quote

    with pg_sitzung("teamloeschen") as db:
        lea, max_ = _employee(db, "P-1", "Lea", "Test"), _employee(db, "P-2", "Max", "Test")
        team = Team(name="Kolonne Ost")
        db.add(team)
        db.flush()
        db.add_all([TeamEmployee(team_id=team.id, employee_id=lea.id, is_crew_leader=True),
                    TeamEmployee(team_id=team.id, employee_id=max_.id)])
        db.commit()
        order = beauftragen(db, make_quote(db, is_consumer=False, number="439"))  # echtes Angebot (Fremdschlüssel unter PostgreSQL)
        create_group_manual_entry(db, employee_ids=[lea.id, max_.id], team_id=team.id, actor_employee_id=None, is_admin=True,
                                  order_id=order.id, work_date=date(2026, 10, 1), hours=Decimal("4"))
        assert delete_team(team.id, db=db, _role=None) == {"deleted": False, "deactivated": True}  # keine laufende Gruppe: keine Rückfrage
        db.expire_all()
        assert db.get(Team, team.id).active is False


# ---------------------------------------------------------------------------
# 4. Zurück-Links mit echtem Ziel statt history.back()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("adresse,rolle,glieder,ende", [
    ("/address-import", "admin", [("/settings", "Einstellungen")], "Adressimport"),
    ("/history", "buero_finanzen", [("/settings", "Einstellungen")], "Änderungshistorie"),
    ("/leistungskatalog", "buero_finanzen", [("/master-data", "Stammdaten"), ("/master-data#catalogs", "Leistungskataloge")],
     "Leistungskatalog"),
])
def test_zurueck_link_mit_echtem_ziel(threaded_db_session, router_test_client, adresse, rolle, glieder, ende):
    """Bis 1.8.153 gingen die drei Seiten per history.back() zurück -- nach direktem Aufruf ins Leere. Seit 1.9.21 (Stufe 2, Runde 8)
    steht das Ziel als Pfad im Seitenkopf (bis dahin „← Einstellungen“ bzw. „← Stammdaten: Leistungskataloge“)."""
    from app.routers.pages import router as pages_router

    client = router_test_client(threaded_db_session, pages_router, role=rolle)
    antwort = client.get(adresse)
    assert antwort.status_code == 200
    markup = re.sub(r"<script.*?</script>", "", antwort.text, flags=re.S | re.I)
    assert 'class="back' not in markup
    nav = re.search(r'<nav class="ds-kopf-pfad"[^>]*>(.*?)</nav>', markup, flags=re.S).group(1)
    assert re.findall(r'<a class="ds-kopf-pfadglied" href="([^"]*)">([^<]*)</a>', nav) == glieder and "onclick" not in nav
    assert html.unescape(re.search(r'class="ds-kopf-pfadende" aria-current="page">([^<]*)<', nav).group(1)) == ende
    for ziel, _ in glieder:
        assert client.get(ziel.split("#")[0]).status_code == 200


def test_kein_history_back_mehr_in_den_vorlagen():
    """Nach 1.8.135 (vier Formularseiten), 1.8.146 (users.html) und 1.8.154 ruft keine Vorlage mehr history.back() auf -- ein
    Kommentar, der es erwähnt, zählt nicht."""
    from tests.test_v334_auswahl_restfaelle import TEMPLATES
    from tests.vorlagen_js import alle_vorlagen

    def ohne_kommentare(text):
        text = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        return re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    treffer = [name for name in alle_vorlagen() if "history.back" in ohne_kommentare((TEMPLATES / name).read_text(encoding="utf-8"))]
    assert treffer == []
