"""Version 1.11.36 (Stufe P2c): die Kette je Quelle in Python (app/portal_freigaben.py::kette()) sagt in jeder Zelle der Matrix aus 1.11.32 dasselbe wie
die Funktion der Datenbank (portal_quelle()) -- und „sichtbar“ im ERP (zustand()) dasselbe wie portal_sichtbar(). Gegen PostgreSQL mit der Matrix-Welt aus
tests/test_v822_portal_unterlagen_matrix.py (gleiche Zeilen, gleiche Fälle, gleiche Zustandswechsel).

Warum: das ERP nennt den Grund, warum eine Freigabe ruht, und prüft beim Freigeben, ob die Kette zum Kunden führt -- unter SQLite gibt es portal_quelle()
nicht. Weichen beide ab, zeigte die Karte „sichtbar“, wo der Kunde nichts sieht (oder umgekehrt), oder das ERP gäbe frei, was das Portal nie zeigt.
Dazu: jede Quelle aus FREIGABE_QUELLEN hat in kette() ihren Zweig; jede ruhende Freigabe trägt einen Grund.
"""

import inspect

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import portal_freigaben as pf
from app.models import PortalFreigabe
from app.portal import werte
from tests.test_v822_portal_unterlagen_matrix import ZELLEN, Bau, _freigabe, _kunde, welt  # noqa: F401 -- welt ist die Fixture der Matrix


def test_jede_quelle_hat_ihren_zweig_in_python():
    text = inspect.getsource(pf.kette)
    for quelle in werte.FREIGABE_QUELLEN:
        assert text.count(f'quelle == "{quelle}"') + text.count(f'"{quelle}"') >= 1, quelle


def _vergleichen(w, q, f, kunde, wann):
    """SQL und Python für die Quelle q und die Freigabe f (des Kunden kunde)."""
    sql_kunden = [r[0] for r in w.erp("SELECT kunde FROM portal_quelle(:q, :i)", q=q.quelle, i=q.id)]
    sql_sichtbar = w.erp("SELECT portal_sichtbar(:f, :k)", f=f, k=kunde)[0][0]
    s = sessionmaker(bind=w.engine)()
    try:
        k = pf.kette(s, q.quelle, q.id)
        zeile = s.scalar(select(PortalFreigabe).where(PortalFreigabe.id == f))
        z, grund = pf.zustand(s, zeile, k)
    finally:
        s.close()
    assert len(sql_kunden) <= 1, sql_kunden
    sql_kunde = sql_kunden[0] if sql_kunden else None
    assert (k.kunde if k.gilt else None) == sql_kunde, f"{wann}: Kette Python {k} gegen SQL {sql_kunde}"
    assert (z == "sichtbar") is bool(sql_sichtbar), f"{wann}: ERP „{z}“ ({grund}) gegen portal_sichtbar {sql_sichtbar}"
    if z in ("ruht", "gescheitert"):
        assert grund, f"{wann}: „{z}“ ohne Grund"
    return z


@pytest.mark.parametrize("zeile, fall", ZELLEN, ids=[f"{z}-{f}" for z, f in ZELLEN])
def test_python_gleich_sql(welt, zeile, fall):
    w = welt
    w.erp("DELETE FROM portal_bremsen")
    kunde, _sitz = _kunde(w, "Kundin")
    anderer, _sitz2 = _kunde(w, "Fremd")
    q = Bau(w).bauen(zeile, kunde, anderer if fall == "objekt_anderer_kunde" else kunde)
    f = _freigabe(w, anderer if fall == "fremder_kunde" else kunde, q, bereit=fall != "kopie_nicht_bereit")
    vorher = _vergleichen(w, q, f, anderer if fall == "fremder_kunde" else kunde, "vorher")
    if fall in ("positiv", "objekt_anderer_kunde", "kunde_archiv"):
        pass
    elif fall == "fremder_kunde":
        assert vorher == "ruht"
    elif fall == "kopie_nicht_bereit":
        assert vorher == "wird_vorbereitet"
    else:
        assert vorher == "sichtbar", zeile
        if fall == "kundenwechsel":
            tabelle, spalte, zid = q.kette
            w.erp(f"UPDATE {tabelle} SET {spalte} = :k WHERE id = :i", k=anderer, i=zid)
        elif fall in ("mustervorgang", "projekt_archiv"):
            w.erp(f"UPDATE projects SET {'is_template' if fall == 'mustervorgang' else 'archived'} = true WHERE id = :p", p=q.projekt)
        elif fall == "zurueckgenommen":
            w.erp("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_grund = 'Test' WHERE id = :f", f=f)
        elif fall == "quelle_ungueltig":
            q.ungueltig()
        nachher = _vergleichen(w, q, f, kunde, f"nach „{fall}“")
        assert nachher == ("zurueckgenommen" if fall == "zurueckgenommen" else "ruht"), (zeile, fall, nachher)
    if fall == "kunde_archiv":
        w.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kunde)
        _vergleichen(w, q, f, kunde, "Kunde im Archiv")  # die Kette kennt das Archiv des Kunden nicht -- das prüft die Sitzung (P1)


def test_gescheitert_und_erneut_wecken_den_postboten(welt):
    """Eine gescheiterte Kopie: Zustand „gescheitert“ mit Grund in Worten; „erneut“ leert kopie_fehler und weckt den Postboten (pg_notify) -- gezählt nur
    Weckrufe dieser Verbindung (NOTIFY gilt für die ganze Datenbank)."""
    w = welt
    kunde, _s = _kunde(w, "Kundin")
    q = Bau(w).bauen("customer_documents", kunde, kunde)
    f = _freigabe(w, kunde, q, bereit=False)
    w.erp("UPDATE portal_freigaben SET kopie_fehler = 'zu_gross' WHERE id = :f", f=f)
    hoerer = w.engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        hoerer.exec_driver_sql(f"LISTEN {pf.KANAL}")
        roh = hoerer.connection.driver_connection
        s = sessionmaker(bind=w.engine)()
        try:
            zeile = s.get(PortalFreigabe, f)
            assert pf.zustand(s, zeile) == ("gescheitert", pf.FEHLER_TEXT["zu_gross"])
            pid = s.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar()  # dieselbe Verbindung bis zum Commit in erneut()
            pf.erneut(s, kunde, f)
            zeile = s.get(PortalFreigabe, f)
            assert zeile.kopie_fehler is None and pf.zustand(s, zeile)[0] == "wird_vorbereitet"
        finally:
            s.close()
        assert sum(1 for n in roh.notifies(timeout=1.0) if n.pid == pid) == 1, "kein Weckruf aus „erneut“"
    finally:
        hoerer.close()
