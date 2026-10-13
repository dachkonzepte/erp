"""Version 1.8.87 -- der Testhelfer _run (tests/test_v375_rechnungen_sperren.py) schließt die Sitzung der zweiten Aktion
(Vorgabe R4c, Vorweg 2; Nebenbefund 5 aus 1.8.85).

Bis 1.8.86 blieb die Sitzung der zweiten Aktion offen: warf sie nach der Sperre der Auftragszeile, hielt ihre Transaktion die
Sperre weiter -- eine spätere Aktion auf derselben Zeile wartete ewig (so hing 1.8.85 ein Test im Nachlauf). Hier wirft die
zweite Aktion mit gehaltener Sperre; danach muss eine dritte Sitzung dieselbe Zeile sofort sperren können (lock_timeout)."""

from sqlalchemy import text

from app.invoices import lock_order_invoices
from tests.test_v375_rechnungen_sperren import _run, pg  # noqa: F401  (pg ist eine Fixture)


def test_pg_run_closes_the_session_of_the_second_action(pg):
    Session, order_id = pg

    def first(s):
        lock_order_invoices(s, order_id)
        s.commit()
        return "erste"

    def second(s):
        lock_order_invoices(s, order_id)  # wartet auf die erste, hält danach die Sperre
        raise RuntimeError("zweite Aktion wirft mit gehaltener Sperre")

    erste, zweite = _run(Session, first, second)
    assert erste == "erste"
    assert isinstance(zweite, RuntimeError)

    third = Session()
    try:
        third.execute(text("SET LOCAL lock_timeout = '2s'"))
        lock_order_invoices(third, order_id)  # ohne Schließen: LockNotAvailable nach 2 s
    finally:
        third.rollback()
        third.close()
