"""Version 1.9.278 (Stufe 6, R5c, Punkt 0c; Antwort 2 der Nachrunde R5b, Weg a): das Untermenü der Stammdaten unter 1400 px oben.

    Untermenü     unter 1400 px Fensterbreite über der Karte (eine Zeile, rollt waagrecht -- wie bis 1.9.277 erst unter 850 px); ab 1401 px links
    Telefon       die Telefonnummer bricht nie um, auch nicht an Leerzeichen (gegen 1.9.275 Nr. 3: bei 1280 px brach sie um)
    unter 850 px  wie bisher: E-Mail und Funktion ohne Umbruch im Wort, Suchfeld volle Breite
Der Klicktest scripts/klicktest_stammdaten_breite.py misst im Browser: Untermenü links bei 1440, oben bei 1400 und 1280 px; bei 1280 px die Tabelle ohne Rollen,
auch ohne Silbentrennung, die E-Mail höchstens zweizeilig, die Telefonnummer einzeilig.
"""

from tests.test_v671_inaktive_mitarbeiter_ausblenden import _mitarbeiter_zweig
from tests.test_v675_stammdaten_breite import _css, _unter


def test_untermenue_unter_1400_px_oben():
    oben = _unter(1400)
    assert ".layout{grid-template-columns:minmax(0,1fr)}" in oben
    assert all(r in oben for r in (".side{position:static;display:flex;overflow:auto}", ".side h3{display:none}", ".side button{white-space:nowrap}"))
    assert ".side{" not in _unter(850)  # nur noch an einer Stelle


def test_unter_850_px_wie_bisher():
    schmal = _unter(850)
    assert all(r in schmal for r in ("td.kontakt .mail{overflow-wrap:normal}", "td.trennbar{hyphens:manual}", "input{min-width:0;width:100%}"))


def test_telefonnummer_ohne_umbruch():
    assert "td.kontakt .tel{white-space:nowrap}" in _css()
    assert "${x.mobile||x.phone?`<span class=\"tel\">${esc(x.mobile||x.phone)}</span>`:''}" in _mitarbeiter_zweig()
