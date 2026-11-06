"""Version 1.9.239 (Stufe 6, R3b, Punkt 0b): die Einstellungen nennen die Lohndatei, nicht mehr den LODAS-Export.

Seit 1.9.224 (Lohn L1b) gibt es nur noch die Lohndatei für DATEV Lohn und Gehalt (app/lohndatei.py); Berater- und Mandantennummer stehen in ihrem Kopf
„Berater;Mandant;MM/JJJJ“. Der Hinweis unter „DATEV-Berater und -Mandant“ sprach bis 1.9.238 noch vom „Kopf des LODAS-Exports“ (Bericht R3a, 3 j).
"""

import re
from pathlib import Path

from tests.vorlagen_js import TEMPLATES, alle_vorlagen

ROOT = Path(__file__).resolve().parents[1]


def _hinweis(seite: str) -> str:
    treffer = re.search(r'id="datevNummernHinweis">(.*?)</div>', seite, re.S)
    assert treffer, "Hinweis unter „DATEV-Berater und -Mandant“ nicht gefunden"
    return treffer.group(1)


def test_der_hinweis_nennt_die_lohndatei():
    hinweis = _hinweis((ROOT / "app/templates/settings.html").read_text(encoding="utf-8"))
    assert "sie stehen im Kopf der Lohndatei; ohne sie entsteht keine Lohndatei." in hinweis, hinweis
    assert "LODAS" not in hinweis and "DATEV-Export" not in hinweis, hinweis


def test_keine_vorlage_nennt_lodas():
    """Sichtbarer Text: keine Vorlage nennt LODAS (den Namen alter Einträge im Änderungsprotokoll übersetzt app/verlauf_namen.py)."""
    funde = [name for name in alle_vorlagen() if "LODAS" in (TEMPLATES / name).read_text(encoding="utf-8")]
    assert funde == [], funde
