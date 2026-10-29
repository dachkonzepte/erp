"""Version 1.9.133 (Stufe 5, R2 Nachrunde, Punkt 6) -- „Zahlbetrag unbezahlt“ statt „Zahlbetrag offen“, wie die Listen.

Nach einer gültigen Endrechnung zählt je Auftrag ihr Zahlbetrag (app/final_dunning.py::overview()). Die Rechnungslisten sagen seit 1.9.129 (D5)
„Zahlbetrag unbezahlt“, der Kopf der Rechnungsseite und der Name am Server (OVERVIEW_LABELS) bis 1.9.132 „Zahlbetrag offen“. Jetzt überall
„unbezahlt“; der Schlüssel zahlbetrag_offen bleibt (Filter, Kennzeichen).
"""

import re
from pathlib import Path

import pytest

from app.final_dunning import OVERVIEW_LABELS
from tests.node_lauf import node_ausfuehren
from tests.test_v133_invoices import db_session, make_order_with_item
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v394_finanzen_zahlbetrag import _abschlag, _ov, _schluss, _zahlen

VORLAGEN = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_name_am_server():
    """Abschlag teilweise bezahlt, dann die Schlussrechnung: ihr Zahlbetrag heißt „Zahlbetrag unbezahlt“."""
    db = db_session()
    order, _ = make_order_with_item(db)
    abschlag = _abschlag(db, order, "40")
    _zahlen(db, abschlag, "1000")
    schluss = _schluss(db, order)
    row = _ov(db, schluss)
    assert (row["state"], row["state_label"]) == ("zahlbetrag_offen", "Zahlbetrag unbezahlt")
    assert OVERVIEW_LABELS["zahlbetrag_offen"] == "Zahlbetrag unbezahlt"


@pytest.mark.skipif(NODE is None, reason="node nicht installiert")
def test_kopf_der_rechnungsseite_wie_die_liste():
    """Das Kennzeichen im Kopf der Rechnungsseite (statusKennzeichen) und die Rechnungsliste (rechnungsZahlstand) sagen dasselbe."""
    skripte = lambda name: "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / name).read_text(encoding="utf-8"), flags=re.S))  # noqa: E731
    ablauf = ("const esc = s => String(s ?? '');\n" + skripte("_statuskennzeichen.html") + "\n" + skripte("_rechnungsliste.html") + """
      const kopf = statusKennzeichen('rechnung', 'zahlbetrag_offen', {zusatz: '495,00 €'}).text;
      const liste = rechnungsZahlstand({status: 'versendet', invoice_type: 'schluss', overview: {state: 'zahlbetrag_offen', open: '495'}}).text;
      console.log(JSON.stringify([kopf, liste]));
    """)
    kopf, liste = node_ausfuehren(ablauf, "Europe/Berlin")
    assert kopf == "Zahlbetrag unbezahlt 495,00 €"
    assert liste.startswith("Zahlbetrag unbezahlt ") and liste.replace(" ", " ").endswith("495,00 €")
