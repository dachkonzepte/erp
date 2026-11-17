"""Suchmuster für LIKE (seit 1.9.358, Runde V2c, Punkt 3; Befund SQLite/PostgreSQL 13.11.2026, Abschnitt 3 F, P8).

Ein Suchtext geht nie roh in ein LIKE-Muster: „%“ und „_“ sind dort Platzhalter, und PostgreSQL nimmt den Backslash als Fluchtzeichen, SQLite nicht --
bis 1.9.357 fand die Büro-Suche „a\\b“ unter PostgreSQL „ab“ (Befund P8), und „50_“ fand „500“. Jetzt schützt der Baustein jedes dieser Zeichen und
nennt das Fluchtzeichen ausdrücklich:

    spalte.ilike(enthaelt(text), escape=ESCAPE)        enthält den Text
    spalte.like(beginnt_mit(text), escape=ESCAPE)      beginnt mit dem Text

Vorbild war die Auftragssuche der Monteurin (app/search.py::search_orders_for_field(), seit 1.9.80). Der Wächter tests/test_v758_suchmuster.py findet
jedes like/ilike unter app/, dessen Muster nicht aus diesem Baustein kommt oder das kein escape=ESCAPE trägt.
"""

ESCAPE = "\\"


def _schuetzen(text) -> str:
    """Backslash zuerst (er schützt die beiden anderen), dann % und _."""
    return str(text).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def enthaelt(text) -> str:
    """Muster „enthält den Text“ -- jedes Zeichen gilt wörtlich."""
    return "%" + _schuetzen(text) + "%"


def beginnt_mit(text) -> str:
    """Muster „beginnt mit dem Text“ -- jedes Zeichen gilt wörtlich."""
    return _schuetzen(text) + "%"
