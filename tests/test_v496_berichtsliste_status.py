"""Seit 1.9.73 (Stufe 4, R4 Nachrunde, Punkt 4): die Seite „Einsatzberichte“ (/orders/{id}/service-reports, service_reports.html) zeigt den
Status eines Berichts über statusKennzeichen() aus _statuskennzeichen.html -- wie der Kopf der Berichtsseite („Entwurf“, „Unterschrieben“,
Klassen ds-status ds-status-<art>), nicht mehr den Rohwert als Kennzeichen in Großbuchstaben (.badge). Die Darstellung im Browser prüft
scripts/klicktest_bericht_schritte.py."""

import re

from tests import vorlagen_js as vj

SEITE = "service_reports.html"


def _bericht_zeile() -> str:
    text = (vj.TEMPLATES / SEITE).read_text(encoding="utf-8")
    m = re.search(r"function reportRow\(r\)\{(.*?)\n\}\n", text, flags=re.S)
    assert m, "reportRow() nicht gefunden"
    return m[1]


def test_status_ueber_den_statusbaustein():
    zeile = _bericht_zeile()
    assert "statusKennzeichen('einsatzbericht',r.status)" in zeile
    assert 'class="ds-status ds-status-${esc(stand.art)}"' in zeile and "${esc(stand.text)}" in zeile


def test_kein_rohwert_als_kennzeichen():
    """Angriff: der Rohwert des Status steht nirgends mehr in der Zeile (weder als Klasse noch als Text)."""
    zeile = _bericht_zeile()
    assert "esc(r.status)" not in zeile and "badge" not in zeile


def test_seite_hat_den_baustein():
    seite, _ = vj.zusammensetzen(SEITE)
    assert "function statusKennzeichen(" in seite
    assert "einsatzbericht: { entwurf: ['Entwurf', 'entwurf'], unterschrieben: ['Unterschrieben', 'erledigt'] }" in seite
