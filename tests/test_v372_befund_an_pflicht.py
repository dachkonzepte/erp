"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Vorab.

Bestätigt, keine xfail: Fehlt die Adresse des Auftraggebers (An) oder ist sie ungültig, wird der Versand abgelehnt (400) -- er geht
nicht nur an die Kopien. Festlegung 1.8.69 Nr. 3 ("eine ungültige Adresse sperrt den Versand nicht") gilt nur für die Kopien:
app/notice_letters.py::client_address() verlangt eine Adresse, app/email_dispatch.py::dispatch_email() prüft sie mit
parse_recipients(), bevor irgendetwas gespeichert oder gesendet wird. Abnahmeprotokoll und Brief der Behinderungsanzeige."""

import pytest
from sqlalchemy import func, select

from app.models import Customer, DispatchCopy, EmailDispatch, Order, Project
from tests.test_v321_email_dispatch import FakeSMTP
from tests.test_v343_behinderungsanzeige_versand import (  # noqa: F401  (Fixtures)
    _office as _n_office, _send as _n_send, _signed as _n_signed, nworld,
)
from tests.test_v305_checklist_filling import world  # noqa: F401  (Fixture)
from tests.test_v341_behinderungsanzeige import bworld  # noqa: F401  (Fixture)
from tests.test_v349_abnahme_und_gewaehrleistung import ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v363_zweck_abnahme import _sign_ag
from tests.test_v365_abnahme_aus_protokoll import protokoll  # noqa: F401  (Fixture)
from tests.test_v369_protokoll_versand import _send, _state, versand  # noqa: F401  (Fixture)

KAPUTT = ["", "   ", ";", "auftraggeber(at)dachkonzepte.example", "auftraggeber@dachkonzepte..example",
          "auftraggeber@dachkonzepte.example; kein-at-zeichen"]


def _nichts_versendet(db):
    db.expire_all()
    assert FakeSMTP.sent == []
    assert db.scalar(select(func.count()).select_from(EmailDispatch)) == 0
    assert db.scalar(select(func.count()).select_from(DispatchCopy)) == 0


@pytest.mark.parametrize("adresse", [None, *KAPUTT])
def test_protocol_without_valid_client_address_is_refused_not_sent_to_the_copies(versand, adresse):
    p, db = versand, versand["db"]
    assert _sign_ag(p).status_code == 200
    assert _state(p)["cc"], "Vorbedingung: die Fassung hat Kopien, an die der Versand gehen könnte"
    project = db.get(Project, db.get(Order, p["order_id"]).project_id)
    db.get(Customer, project.customer_id).email = adresse
    db.commit()
    r = _send(p)
    assert r.status_code == 400, r.text
    assert "E-Mail-Adresse" in r.json()["detail"]
    _nichts_versendet(db)


@pytest.mark.parametrize("adresse", [None, *KAPUTT])
def test_notice_letter_without_valid_client_address_is_refused_not_sent_to_the_copies(nworld, router_test_client,
                                                                                       adresse):
    from tests.test_v343_behinderungsanzeige_versand import _participant

    db = nworld["db"]
    _participant(db, nworld, name="Architekt", email="arch@example.com")
    office = _n_office(nworld, router_test_client)
    c = _n_signed(nworld, router_test_client)
    nworld["orders"]["mine"].project.customer.email = adresse
    db.commit()
    r = _n_send(office, c)
    assert r.status_code == 400, r.text
    assert "E-Mail-Adresse" in r.json()["detail"]
    _nichts_versendet(db)
