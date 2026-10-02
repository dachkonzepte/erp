"""Schalter für den Grunddaten-Hook in tests/conftest.py (seit 1.8.42).

Jede Testdatenbank aus Base.metadata.create_all() bekommt dort die Grunddaten (app/grunddaten.py), wie
eine Installation nach dem Start. Ein Test, der eine Datenbank OHNE sie braucht (z. B. um anlegen()
selbst zu prüfen), legt die Tabellen so an:

    with ohne_grunddaten():
        Base.metadata.create_all(engine)

Eigenes Modul statt conftest.py: conftest lädt pytest selbst, ein Import von dort hätte zwei Instanzen."""

from contextlib import contextmanager

_AUS: list[bool] = []


@contextmanager
def ohne_grunddaten():
    _AUS.append(True)
    try:
        yield
    finally:
        _AUS.pop()


def grunddaten_aus() -> bool:
    return bool(_AUS)
