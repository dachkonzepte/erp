"""Version 1.9.130 (Stufe 5, R2 Nachrunde, Punkt 1) -- Status wie die Vorlage: im Kopf nur das Kennzeichen, die Übergänge im „⋮“.

Die Akte zeigt den Status des gewählten Auftrags als Kennzeichen im Seitenkopf; Pausieren, Fortsetzen, Abschließen und Stornieren sind Einträge im
Menü „⋮“ -- nur die, die der Server gerade erlaubt (app/auftragsstatus.py::status_info()): kein „Abschließen …“ mit einer Rechnung (auch einem
Entwurf) und ohne Schlussrechnung. Über die API bleibt ein nicht erlaubter Übergang 409. Bis 1.9.129 stand unter den Phasen eine Zeile „Status“
mit Knöpfen für jeden Übergang aus dem Status (Festlegung 1.9.129 Nr. 15, nicht bestätigt).
"""

import re
from decimal import Decimal
from pathlib import Path

from app.invoices import create_abschlag_pauschal, create_schlussrechnung
from tests.leistungszeitraum import festschreiben
from tests.node_lauf import node_ausfuehren
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v544_auftragsstatus import _buero, _frisch, _status
from tests.test_v471_heute_server import welt  # noqa: F401  (Fixture)

import pytest

VORLAGEN = Path(__file__).resolve().parents[1] / "app" / "templates"


def _ziele(client, order_id):
    return [a["ziel"] for a in client.get(f"/api/orders/{order_id}").json()["status_info"]["aktionen"]]


def test_nur_erlaubte_uebergaenge(welt):  # noqa: F811
    """Ohne Rechnung: Abschließen („ohne Rechnung“) erlaubt; mit Entwurf und ohne Schlussrechnung fehlt es, über die API 409; nach der
    Schlussrechnung wieder da. Pausiert: Fortsetzen statt Pausieren."""
    db, order = welt["db"], welt["order"]
    client = _buero(welt)
    assert _ziele(client, order.id) == ["pausiert", "abgeschlossen", "storniert"]
    abschlag = create_abschlag_pauschal(db, order, lump_sum_net=Decimal("100"))
    assert _ziele(client, order.id) == ["pausiert", "storniert"]
    info = client.get(f"/api/orders/{order.id}").json()["status_info"]["abschluss"]
    assert "Entwurf" in info["grund"]
    antwort = _status(client, order.id, "abgeschlossen", "ohne Rechnung")
    assert antwort.status_code == 409 and "Entwurf" in antwort.json()["detail"]
    festschreiben(db, abschlag)
    assert _ziele(client, order.id) == ["pausiert", "storniert"]
    festschreiben(db, create_schlussrechnung(db, _frisch(welt)))
    assert _ziele(client, order.id) == ["pausiert", "abgeschlossen", "storniert"]
    assert _status(client, order.id, "pausiert", "Gerüst fehlt").status_code == 200
    assert _ziele(client, order.id) == ["laeuft", "abgeschlossen", "storniert"]


def test_akte_uebergaenge_im_menue():
    """Je Status ein Eintrag im Menü „⋮“ (data-klick="statusAktion", data-ziel), verborgen bis der Server ihn erlaubt; keine Knöpfe mehr unter den
    Phasen; das Kennzeichen im Kopf ist das des Auftrags."""
    text = (VORLAGEN / "akte.html").read_text(encoding="utf-8")
    start = text.index('{% elif teil == "menue" %}')
    menue = text[start:text.index("\n", start)]  # der Teil „menue“ steht in einer Zeile
    eintraege = re.findall(r'<button type="button" class="ds-menue-eintrag([^"]*)" data-klick="statusAktion" data-ziel="([a-z]+)" hidden>([^<]+)</button>',
                           menue)
    assert [(z, t) for _, z, t in eintraege] == [("laeuft", "Fortsetzen …"), ("pausiert", "Pausieren …"), ("abgeschlossen", "Abschließen …"),
                                                 ("storniert", "Stornieren …")]
    assert [k for k, z, _ in eintraege if "fehler" in k] == [" ds-menue-eintrag-fehler"]  # nur Stornieren in Rot
    baustein = (VORLAGEN / "_auftragsstatus.html").read_text(encoding="utf-8")
    hinweis = baustein[baustein.index("function auftragsstatusHinweis"):baustein.index("function auftragsstatusZeigen")]
    assert "auftragsstatus-knoepfe" not in text + baustein and "<button" not in hinweis  # der Hinweis unter den Phasen ohne Knöpfe
    assert "if(orderId&&order)seitenkopf({status:statusKennzeichen('auftrag',order.status)});else seitenkopf({status:statusKennzeichen('projekt',project.status)});" in text


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_menue_zeigt_nur_was_der_server_erlaubt():
    """auftragsstatusZeigen(): die Einträge, die status_info.aktionen nennt, sichtbar, die übrigen hidden; der Hinweis unter den Phasen nur, wenn
    der Auftrag nicht läuft (mit Begründung)."""
    skripte = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_auftragsstatus.html").read_text(encoding="utf-8"), flags=re.S))
    berlin = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_berlin_date.html").read_text(encoding="utf-8"), flags=re.S))
    kennzeichen = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_statuskennzeichen.html").read_text(encoding="utf-8"), flags=re.S))
    dom = """
      const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
      const eintraege = ['laeuft', 'pausiert', 'abgeschlossen', 'storniert'].map(z => ({dataset: {ziel: z}, hidden: true}));
      const elemente = {auftragsstatus: {innerHTML: ''}, statusZeile: {hidden: true}};
      var document = {querySelectorAll: s => s === '[data-klick="statusAktion"]' ? eintraege : [], getElementById: id => elemente[id] || null};
    """
    ablauf = """
      const sichtbar = () => eintraege.filter(e => !e.hidden).map(e => e.dataset.ziel);
      auftragsstatusZeigen({status: 'laeuft', status_info: {aktionen: [{ziel: 'pausiert'}, {ziel: 'storniert'}]}});
      const a = [sichtbar(), elemente.statusZeile.hidden];
      auftragsstatusZeigen({status: 'pausiert', status_info: {aktionen: [{ziel: 'laeuft'}, {ziel: 'abgeschlossen'}, {ziel: 'storniert'}],
        letzter_wechsel: {new_status: 'pausiert', changed_at: '2026-10-28T09:00:00', changed_by_name: 'Olga Office', reason: 'Gerüst <fehlt>'}}});
      const b = [sichtbar(), elemente.statusZeile.hidden, elemente.auftragsstatus.innerHTML];
      console.log(JSON.stringify([a, b]));
    """
    a, b = node_ausfuehren(dom + kennzeichen + berlin + skripte + ablauf, "Europe/Berlin")
    assert a == [["pausiert", "storniert"], True]
    assert b[0] == ["laeuft", "abgeschlossen", "storniert"] and b[1] is False
    assert "<b>Pausiert</b> seit 28.10.2026 · Olga Office · Begründung: Gerüst &lt;fehlt&gt;" in b[2]
