"""Version 1.9.366 (Urlaubsrunde, Punkt 2): Übertrag zuerst.

    Konto        genehmigter Urlaub bis zum Verfall (am Anspruch, sonst die Vorgabe „Verfall“) verbraucht zuerst den Übertrag aus dem Vorjahr; danach
                 verbraucht Urlaub den Anspruch. uebertrag_noch = Übertrag − dieser Urlaub (nie unter 0); ohne Verfall verbraucht jeder Urlaub des Jahrs
                 zuerst den Übertrag. Hinweis bis zum Verfall „davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027“, danach „Übertrag nicht genommen: …“
    danach Rest  „ · davon Übertrag noch 0,5 Tage, verfällt am 31.03.2027“, wenn nach diesem Urlaub noch Übertrag übrig ist
    Vorgabe      „Verfall“ ausgeliefert 31.03.; Migration c5e2f8a1d047 setzt sie im Bestand, wo sie leer ist; ein eigener Wert bleibt; downgrade ändert nichts
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.models import EmployeeAbsence, LohnStartwert, TimeTrackingSettings, Urlaubsanspruch
from app.urlaubskonto import konten, rest_danach
from tests import vorlagen_js as vj
from tests.test_v224_field_view import make_employee
from tests.test_v380_nummern_eindeutig import _alembic, _ok

D = Decimal
MIGRATION, VORHER = "c5e2f8a1d047", "a4d1e6c93b20"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
FEB = date(2027, 2, 10)


@pytest.fixture
def w(threaded_db_session, fester_tag):
    db = threaded_db_session
    mia = make_employee(db, "M-1", "Mia", "Monteurin")
    db.add(LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=D("4.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    db.commit()
    return {"db": db, "mia": mia}


def urlaub(w, von, bis, halb=False):
    w["db"].add(EmployeeAbsence(employee_id=w["mia"].id, absence_type="Urlaub", absence_category="urlaub", start_date=von, end_date=bis,
                                halber_tag=halb))
    w["db"].commit()


def konto(w, heute=FEB, jahr=2027):
    return konten(w["db"], jahr, [w["mia"].id], heute=heute)[0]


def test_vorgabe_ist_der_31_maerz(w):
    assert w["db"].get(TimeTrackingSettings, 1).urlaub_verfall == "31.03."
    k = konto(w)
    assert (k.verfall_am, k.uebertrag_noch, k.hinweise) == (date(2027, 3, 31), D("4.5"), ["davon Übertrag noch 4,5 Tage, verfällt am 31.03.2027"])


def test_urlaub_bis_zum_verfall_nimmt_zuerst_den_uebertrag(w):
    urlaub(w, date(2027, 2, 1), date(2027, 2, 2))   # 2 Tage vor dem Verfall
    urlaub(w, date(2027, 4, 5), date(2027, 4, 9))   # 5 Tage danach: nimmt den Anspruch
    k = konto(w)
    assert (k.genehmigt, k.uebertrag_noch, k.rest) == (D("7"), D("2.5"), D("27.5"))  # der Rest bleibt Anspruch + Übertrag − genehmigt
    assert k.hinweise == ["davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027"]
    d = k.als_dict()
    assert (d["verfall_am"], d["uebertrag_noch"]) == (date(2027, 3, 31), D("2.5"))
    urlaub(w, date(2027, 3, 31), date(2027, 3, 31), halb=True)  # am Verfallstag zählt noch
    assert konto(w).uebertrag_noch == D("2")
    urlaub(w, date(2027, 3, 1), date(2027, 3, 5))  # mehr als übrig: nie unter 0
    k = konto(w)
    assert (k.uebertrag_noch, k.hinweise) == (D("0"), [])


def test_nach_dem_verfall_nicht_genommen(w):
    urlaub(w, date(2027, 2, 1), date(2027, 2, 2))
    k = konto(w, heute=date(2027, 4, 1))
    assert k.hinweise == ["Übertrag nicht genommen: 2,5 Tage – Verfall am 31.03.2027, nichts verfällt von selbst"]
    assert k.rest == D("32.5")  # nichts verfällt von selbst


def test_ohne_verfall_nimmt_jeder_urlaub_zuerst_den_uebertrag(w):
    w["db"].get(TimeTrackingSettings, 1).urlaub_verfall = None
    w["db"].commit()
    urlaub(w, date(2027, 4, 5), date(2027, 4, 6))
    k = konto(w, heute=date(2027, 6, 1))
    assert (k.verfall_am, k.uebertrag_noch, k.hinweise) == (None, D("2.5"), ["davon Übertrag noch 2,5 Tage"])


def test_verfall_am_anspruch_geht_vor(w):
    w["db"].add(Urlaubsanspruch(employee_id=w["mia"].id, jahr=2027, verfall_am=date(2027, 6, 30)))
    w["db"].commit()
    urlaub(w, date(2027, 5, 3), date(2027, 5, 4))
    k = konto(w, heute=date(2027, 5, 10))
    assert (k.verfall_am, k.uebertrag_noch, k.hinweise) == (date(2027, 6, 30), D("2.5"), ["davon Übertrag noch 2,5 Tage, verfällt am 30.06.2027"])


def test_ohne_uebertrag_nichts(w):
    w["db"].query(LohnStartwert).delete()
    w["db"].add(LohnStartwert(employee_id=w["mia"].id, stichtag=date(2026, 12, 31), resturlaub_tage=D("-1.5"), saldo_stunden=D("0"), herkunft="steuerbuero"))
    w["db"].commit()
    k = konto(w)
    assert (k.uebertrag, k.uebertrag_noch, k.hinweise) == (D("-1.5"), D("0"), [])


def test_danach_rest_mit_dem_uebertrag(w):
    db, mia = w["db"], w["mia"]
    urlaub(w, date(2027, 2, 1), date(2027, 2, 2))  # noch 2,5
    assert rest_danach(db, mia.id, date(2027, 3, 1), date(2027, 3, 2), heute=FEB)["text"] == (
        "danach Rest 30,5 Tage · davon Übertrag noch 0,5 Tage, verfällt am 31.03.2027")
    assert rest_danach(db, mia.id, date(2027, 3, 1), date(2027, 3, 5), heute=FEB)["text"] == "danach Rest 27,5 Tage"  # alles verbraucht
    assert rest_danach(db, mia.id, date(2027, 4, 12), date(2027, 4, 16), heute=FEB)["text"] == (
        "danach Rest 27,5 Tage · davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027")  # nach dem Verfall: der Übertrag bleibt übrig
    assert rest_danach(db, mia.id, date(2027, 4, 12), date(2027, 4, 16), heute=date(2027, 4, 1))["text"] == "danach Rest 27,5 Tage"
    # über den Jahreswechsel: 2028 ohne Übertrag (von Hand, leer) -- der Satz nur für 2027, mit dem Jahr
    assert rest_danach(db, mia.id, date(2027, 12, 27), date(2028, 1, 7), heute=FEB)["text"] == (
        "danach Rest 2027: 27,5 Tage · 2028: 25 Tage · 2027: davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027")


def test_alter_hinweis_und_nur_vorgemerkt_sind_weg():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    assert 'f"Verfall des Übertrags vorgemerkt' not in (root / "app" / "urlaubskonto.py").read_text(encoding="utf-8")  # der Hinweis entsteht nicht mehr
    einstellungen = vj.seitentext("settings.html")[0]
    assert "nur vorgemerkt" not in einstellungen
    assert "Bis zum Verfall verbraucht Urlaub zuerst den Übertrag aus dem Vorjahr" in einstellungen


# --- Migration ------------------------------------------------------------------------------------------------------------------------------

def _probe(url: str, engine, wert) -> None:
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        c.execute(text("INSERT INTO time_tracking_settings (id, rounding_minutes, default_break_minutes, allow_manual_entries, allow_group_bookings, "
                       "require_order_item, require_activity, datev_target, urlaub_vorgabe_tage, urlaub_uebertrag, urlaub_verfall, updated_at) VALUES "
                       "(1, 0, 0, true, true, false, false, 'lohn_gehalt', 30, 'von_hand', :v, '2026-11-01')"), {"v": wert})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        nachher = c.execute(text("SELECT urlaub_verfall FROM time_tracking_settings")).scalar()
    assert nachher == ("31.03." if wert in (None, "") else wert)  # leer -> 31.03., ein eigener Wert bleibt
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert c.execute(text("SELECT urlaub_verfall FROM time_tracking_settings")).scalar() == nachher  # downgrade ändert nichts
    _ok(_alembic(url, "upgrade", "head"))


@pytest.mark.parametrize("wert", [None, "30.06."])
def test_migration_auf_einem_bestand_sqlite(tmp_path, wert):
    url = f"sqlite:///{(tmp_path / 'verfall.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine, wert)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_verfall_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"  # ohne Prozentkodierung (configparser)
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine, None)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
