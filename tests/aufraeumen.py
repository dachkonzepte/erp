"""Wegwerf-Engines der Tests schließen sich selbst (seit 1.9.195, Lohn L1a, Stufe 3, Punkt 4).

Bis 1.9.194 gaben viele Testaufbauten (z. B. tests/test_v133_invoices.py::db_session()) eine Sitzung zurück, deren Engine niemand schloss.
Die Speicherbereinigung räumte sie irgendwann ab -- oft im Thread eines späteren TestClient, in dem SQLite die Verbindung nicht anfassen darf:
„Exception during reset or similar … SQLite objects created in a thread can only be used in that same thread“, je vollem Lauf 79 bis 197
solche Zeilen im Protokoll (der Wackler in test_v564, 1.9.177/1.9.183, hing an genau so einem Abräumen).

wegwerf_engine() legt eine Engine an wie sqlalchemy.create_engine() und merkt sie; tests/conftest.py schließt am Ende jedes Tests jede in ihm
gemerkte Engine -- zuerst ihre noch offenen Sitzungen, dann die Engine mit engine.dispose() -- im Thread des Tests, also in dem, in dem ihre
Verbindungen entstanden. Eine Engine, die ein Aufbau mit
größerem Umfang anlegt (Fixture des Moduls oder des Laufs), schließt das Ende dieses Umfangs. Eine Funktion, die ihre Engine selbst mit
dispose() schließt, darf create_engine() weiter direkt nehmen; tests/test_v603_engines_aufraeumen.py prüft das für jede Datei unter tests/.
"""

from __future__ import annotations

import threading

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import _sessions as _alle_sitzungen  # alle lebenden Sitzungen des Prozesses (schwach gehalten)

_GEMERKT: list[Engine] = []
_SPERRE = threading.Lock()


def wegwerf_engine(*args, **kwargs) -> Engine:
    """Wie sqlalchemy.create_engine(); die Engine wird am Ende des Tests (bzw. des Aufbaus, der sie anlegte) mit dispose() geschlossen."""
    engine = create_engine(*args, **kwargs)
    with _SPERRE:
        _GEMERKT.append(engine)
    return engine


def marke() -> int:
    """Wie viele Engines gerade gemerkt sind -- schliessen(marke) schließt nur die danach angelegten."""
    with _SPERRE:
        return len(_GEMERKT)


def _sitzungen_schliessen(engine: Engine) -> None:
    """Schließt jede noch offene Sitzung auf der Engine (eine Hilfsfunktion gab sie zurück, niemand schloss sie). Danach erst dispose():
    eine Sitzung auf einer schon geschlossenen Verbindung wirft beim nächsten close() -- etwa in close_all_sessions() eines späteren
    Tests (tests/befund_vor_echtbetrieb.py::pg_sitzung()). Die Liste der lebenden Sitzungen ist dieselbe, die close_all_sessions() nimmt."""
    for sitzung in list(_alle_sitzungen.values()):
        if getattr(sitzung.bind, "engine", None) is engine:
            try:
                sitzung.close()
            except Exception:  # Verbindung aus einem anderen Thread (SQLite): dispose() schließt sie trotzdem
                pass


def schliessen(ab: int) -> int:
    """Schließt jede ab der Marke gemerkte Engine, die jüngste zuerst -- zuerst ihre offenen Sitzungen, dann die Engine mit dispose() -- und
    vergisst sie; zurück: wie viele."""
    with _SPERRE:
        offen = _GEMERKT[ab:]
        del _GEMERKT[ab:]
    for engine in reversed(offen):
        _sitzungen_schliessen(engine)
        engine.dispose()
    return len(offen)
