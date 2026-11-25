"""Begrüßung ohne Komma nach „Guten Tag“ (seit 1.11.23, Betreibervorgabe 25.11.2026).

Im Portal „Guten Tag Herr Dr. Muster“, in den Mails „Guten Tag Herr Dr. Muster,“ -- ein Komma steht nur am Ende der ersten Zeile einer Mail. Die Begrüßung
mit Namen entsteht nur in `app/portal/begruessung.py`; die Mails des Portals hängen das Komma an (`app/portal_mails.py::anrede()`), die Briefe der Anzeigen
schreiben bei „Divers“ „Guten Tag <Name>,“ (`app/notice_letters.py::salutation_line()`). Kein Text unter `app/` setzt ein Komma zwischen „Guten Tag“ und einen
Namen -- auch nicht über die Konstante (`{GRUSS},`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models import Customer
from app.notice_letters import salutation_line
from app.portal.begruessung import begruessung
from app.portal_mails import anrede

ROOT = Path(__file__).resolve().parents[1]
ENDUNGEN = {".py", ".html", ".js", ".css", ".txt", ".md", ".json"}
# „Guten Tag,“ vor einem Namen (Buchstabe oder Platzhalter) auf derselben Zeile; „Guten Tag,“ allein (Ende der Zeile, vor \n, Anführungszeichen, Tag) bleibt.
MIT_KOMMA = re.compile(r"Guten Tag,[ \t]*(?=[^\W\d_]|\{)|\{GRUSS\},")


def _fundstellen() -> list[str]:
    treffer = []
    for datei in sorted((ROOT / "app").rglob("*")):
        if not datei.is_file() or datei.suffix not in ENDUNGEN or "__pycache__" in datei.parts:
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if MIT_KOMMA.search(zeile):
                treffer.append(f"{datei.relative_to(ROOT).as_posix()}:{nr}")
    return treffer


def test_kein_komma_nach_guten_tag_unter_app():
    assert _fundstellen() == []


@pytest.mark.parametrize("zeile, erwartet", [
    ("Guten Tag, Herr Dr. Muster", True),
    ("x = f\"{GRUSS}, {art}\"", True),
    ("Guten Tag,Herr", True),
    ("Guten Tag Herr Dr. Muster", False),
    ("text = \"Guten Tag,\\n\\nanbei\"", False),
    ("<p>Guten Tag,</p>", False),
    ("Guten Tag,", False),
    ("ohne Namen „Guten Tag,“.", False),
    ("Guten Tag, {kundenname}", True),
    ("Guten Tag, Ärztehaus Muster", True),
])
def test_suchmuster(zeile, erwartet):
    assert bool(MIT_KOMMA.search(zeile)) is erwartet


def _kunde(**werte) -> Customer:
    vorgabe = {"salutation": "Herr", "title": "Dr.", "first_name": "Max", "last_name": "Muster", "name": "Herr Dr. Max Muster"}
    return Customer(**{**vorgabe, **werte})


def test_portal_und_mail():
    assert begruessung("Herr", "Dr.", "Max", "Muster", "Herr Dr. Max Muster") == "Guten Tag Herr Dr. Muster"
    assert anrede(_kunde()) == "Guten Tag Herr Dr. Muster,"
    assert anrede(_kunde(salutation=None, title=None, first_name=None, last_name=None, name=None)) == "Guten Tag,"


def test_brief_bei_divers_ohne_komma_nach_guten_tag():
    assert salutation_line(_kunde(salutation="Divers", first_name="Kim")) == "Guten Tag Dr. Kim Muster,"
