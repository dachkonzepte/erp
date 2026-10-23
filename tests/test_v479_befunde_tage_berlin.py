"""Seit 1.9.52 (Stufe 4, R2 Nachrunde, Nebenbefund aus R2): der Datumsfilter der Befundliste (app/findings.py::list_findings(),
date_from/date_to) zählt Tage in Europe/Berlin.

    Grenze         Finding.created_at ist naive UTC (datetime.utcnow()); „am Tag d“ heißt berlin_tag_beginn_utc(d) <= created_at <
                   berlin_tag_beginn_utc(d + 1 Tag) (app/berlin_time.py)
    bis 1.9.51     Mitternacht als naive Zeit, also UTC-Mitternacht -- ein Befund kurz nach Mitternacht in Berlin zählte zum Vortag
                   (Grenzen 1 Std. im Winter, 2 Std. im Sommer verschoben)
"""

from datetime import date, datetime, timedelta

import pytest

from app.berlin_time import berlin_tag_beginn_utc
from app.findings import create_finding, list_findings
from app.models import Finding
from app.service_reports import create_report
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _make_order_for_report


@pytest.mark.parametrize("tag, utc", [
    (date(2026, 10, 23), datetime(2026, 10, 22, 22, 0)),   # Sommerzeit
    (date(2026, 1, 16), datetime(2026, 1, 15, 23, 0)),     # Winterzeit
    (date(2026, 3, 29), datetime(2026, 3, 28, 23, 0)),     # Tag der Umstellung auf Sommerzeit: Mitternacht noch Winterzeit
    (date(2026, 10, 25), datetime(2026, 10, 24, 22, 0)),   # Tag der Umstellung auf Winterzeit: Mitternacht noch Sommerzeit
])
def test_tag_beginn_in_utc(tag, utc):
    assert berlin_tag_beginn_utc(tag) == utc


def _befund(db, erfasst_utc: datetime) -> int:
    _, prop = make_customer_and_property(db)
    order = _make_order_for_report(db, prop)
    report = create_report(db, order.id, "rapport")
    fid = create_finding(db, report["id"], "Gully verstopft", "gering", "sofort_behoben")["id"]
    db.get(Finding, fid).created_at = erfasst_utc
    db.commit()
    return fid


@pytest.mark.parametrize("erfasst_utc, tag", [
    (datetime(2026, 10, 22, 22, 30), date(2026, 10, 23)),  # 00:30 am 23.10. in Berlin (bis 1.9.51: 22.10.)
    (datetime(2026, 1, 15, 23, 30), date(2026, 1, 16)),    # 00:30 am 16.01. in Berlin (bis 1.9.51: 15.01.)
    (datetime(2026, 10, 23, 21, 59), date(2026, 10, 23)),  # 23:59 am 23.10. in Berlin
], ids=["sommer_nach_mitternacht", "winter_nach_mitternacht", "kurz_vor_mitternacht"])
def test_befund_zaehlt_zu_seinem_tag_in_berlin(erfasst_utc, tag):
    """Angriff: ein Befund kurz nach Mitternacht in Berlin steht am neuen Tag, nicht am Vortag; Gegenprobe: am Vortag und am Folgetag fehlt er."""
    db = db_session()
    fid = _befund(db, erfasst_utc)
    ids = lambda von, bis: [f["id"] for f in list_findings(db, date_from=von, date_to=bis)]  # noqa: E731
    assert ids(tag, tag) == [fid]
    assert ids(tag - timedelta(days=1), tag - timedelta(days=1)) == []
    assert ids(tag + timedelta(days=1), tag + timedelta(days=1)) == []
    assert ids(tag, None) == [fid] and ids(None, tag) == [fid]
