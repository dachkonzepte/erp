"""Abgeleitete Werte passen in ihre Spalte (seit 1.8.71, Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ Punkt 5,
docs/archiv/befund-vor-echtbetrieb.md).

Ein Wert, den der Code aus einer Eingabe ableitet (z. B. der Schlüssel einer Spalte aus ihrer Bezeichnung), wird dort gekürzt,
wo er entsteht -- gegen die kürzeste Spalte, in die er geschrieben wird, die Länge gelesen aus dem Modell. Unter PostgreSQL lehnt
eine zu kurze String(n)-Spalte einen längeren Wert ab (DataError, 500), SQLite nimmt ihn still an. Ändert sich eine Spaltenlänge
im Modell, folgt die Kürzung von selbst.

Gegenstück für feste Werte im Code: tests/test_v364_feste_werte_spaltenlaenge.py."""

from collections.abc import Callable


def laenge(*spalten) -> int:
    """Länge der kürzesten der angegebenen String-Spalten (Modellattribute, z. B. TaskColumn.key, Task.status)."""
    return min(spalte.property.columns[0].type.length for spalte in spalten)


def eindeutig_gekuerzt(basis: str, max_laenge: int, belegt: Callable[[str], bool]) -> str:
    """basis, auf max_laenge gekürzt; ist der Wert schon belegt, mit "_2", "_3" … -- die basis dann so weit gekürzt, dass der
    Wert samt Anhang passt. Ein "_" am Ende der gekürzten basis fällt weg (kein "wartet__2")."""
    def gekuerzt(n: int) -> str:
        return basis[:n].rstrip("_") or basis[:n]

    kandidat, nummer = gekuerzt(max_laenge), 2
    while belegt(kandidat):
        anhang = f"_{nummer}"
        kandidat, nummer = gekuerzt(max_laenge - len(anhang)) + anhang, nummer + 1
    return kandidat
