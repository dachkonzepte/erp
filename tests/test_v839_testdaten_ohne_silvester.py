"""1.11.47 (Nachtrag, 28.11.2026) -- Testdaten mit einem Urlaub relativ zu heute meiden Silvester.

Fund im Lauf vor dem Commit von 1.11.48: 30 Tests rot beim Aufbau der Welt von tests/test_v326_monteur_datengrenze.py (auch v403, v409, v411, v412, v510,
v762 nutzen sie). Die Welt legt einen Urlaub heute + 30/31 Tage an; am Samstag, 28.11.2026, stand die Uhr der Tests auf Montag, 30.11. (arbeitstag_ab()),
der Urlaub damit auf 30./31.12. -- Silvester fragt nach „ganzer Urlaubstag oder frei“ (KalendertagFrage, seit 1.9.176), ohne Antwort kein Antrag. Rot vom
28.11. bis 1.12. jedes Jahres; test_v519 legte einen eintägigen Urlaub „heute“ an und wäre am 31.12. rot gewesen. Beide nehmen jetzt tests/uhr.py::ohne_silvester().

    Helfer   ohne_silvester(von, bis): enthält der Zeitraum einen 31.12., rückt er um ganze Wochen, bis er keinen mehr enthält; sonst bleibt er
"""

from datetime import date

import pytest

from tests.uhr import ohne_silvester


@pytest.mark.parametrize("von, bis, soll", [
    (date(2026, 12, 30), date(2026, 12, 31), (date(2027, 1, 6), date(2027, 1, 7))),  # der Fall vom 28.11.2026
    (date(2026, 12, 31), date(2026, 12, 31), (date(2027, 1, 7), date(2027, 1, 7))),  # eintägig am Silvester (test_v519)
    (date(2026, 12, 29), date(2027, 1, 2), (date(2027, 1, 5), date(2027, 1, 9))),    # über den Jahreswechsel
    (date(2026, 12, 24), date(2026, 12, 31), (date(2027, 1, 7), date(2027, 1, 14))),  # eine Woche reicht nicht: zweimal
])
def test_silvester_im_zeitraum_rueckt_um_wochen(von, bis, soll):
    assert ohne_silvester(von, bis) == soll
    assert ohne_silvester(von, bis)[0].weekday() == von.weekday()


@pytest.mark.parametrize("von, bis", [
    (date(2026, 12, 28), date(2026, 12, 29)), (date(2027, 1, 1), date(2027, 1, 2)), (date(2026, 11, 30), date(2026, 12, 1)), (date(2027, 6, 1), date(2027, 6, 1)),
])
def test_ohne_silvester_bleibt_der_zeitraum(von, bis):
    assert ohne_silvester(von, bis) == (von, bis)
