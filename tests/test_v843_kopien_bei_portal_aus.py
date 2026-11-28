"""Version 1.11.52 (W1c Stufe 2, S2-0 d; Antwort W2-6 vom 28.11.2026) -- „Portal aus“ löscht die Kopien.

Bis 1.11.51 entfernte der Abgleich eine Kopie bei Rücknahme, Ruhen der Quelle und Kunde im Archiv, nicht bei „Portal aus“ (Befund B4 des Bauplans W1c Stufe 2);
das Schaufenster leerte der Postbote dagegen schon. Gegen PostgreSQL in der Welt von tests/test_v823_portal_kopien.py.

    Portal aus   der nächste Abgleich entfernt die Kopie (Datei und Angaben an der Freigabe), die Freigabe bleibt; solange aus, entsteht keine neue
    Portal an    der nächste Abgleich legt eine neue Kopie mit neuem Namen an
    Freigeben    eine Freigabe bei ausgeschaltetem Portal (erlaubt, Bauplan P2, B4.2) bekommt ihre Kopie erst, wenn das Portal an ist
"""

from tests.test_v822_portal_unterlagen_matrix import _freigabe, _ids, _kunde, welt  # noqa: F401  (welt ist eine Fixture)
from tests.test_v823_portal_kopien import _abgleich, _dateien, _zeile, echte_quelle, w  # noqa: F401  (w ist eine Fixture)


def test_pg_portal_aus_entfernt_die_kopie_an_legt_neu_an(w):  # noqa: F811
    kunde, sitz = _kunde(w, "PortalAus")
    q, _inhalt = echte_quelle(w, "invoices", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    assert _abgleich(w).angelegt == 1
    erster = _zeile(w, fid)[0]
    assert _dateien(w) == {erster} and fid in _ids(w, sitz)
    w.erp("UPDATE customers SET portal_aktiv = false WHERE id = :k", k=kunde)
    stand = _abgleich(w, voll=True)
    assert stand.entfernt == 1 and _dateien(w) == set() and _zeile(w, fid)[:5] == (None,) * 5
    assert w.erp("SELECT count(*) FROM portal_freigaben WHERE id = :i AND zurueckgenommen_am IS NULL", i=fid)[0][0] == 1  # die Freigabe bleibt
    assert _abgleich(w, voll=True).angelegt == 0  # solange aus: keine neue
    w.erp("UPDATE customers SET portal_aktiv = true WHERE id = :k", k=kunde)
    assert _abgleich(w, voll=True).angelegt == 1
    zweiter = _zeile(w, fid)[0]
    assert zweiter and zweiter != erster and _dateien(w) == {zweiter} and fid in _ids(w, sitz)


def test_pg_freigabe_bei_portal_aus_bekommt_erst_mit_portal_an_eine_kopie(w):  # noqa: F811
    kunde, _sitz = _kunde(w, "Vorher")
    w.erp("UPDATE customers SET portal_aktiv = false WHERE id = :k", k=kunde)
    q, _inhalt = echte_quelle(w, "invoices", kunde)
    fid = _freigabe(w, kunde, q, bereit=False)
    assert _abgleich(w, voll=True).angelegt == 0 and _zeile(w, fid)[0] is None and _dateien(w) == set()
    w.erp("UPDATE customers SET portal_aktiv = true WHERE id = :k", k=kunde)
    assert _abgleich(w, voll=True).angelegt == 1 and _zeile(w, fid)[0] is not None
