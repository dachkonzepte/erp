"""Router: changelog (seit 1.0.52).

Ein einzelner, schreibgeschützter Endpunkt -- liest CHANGELOG.md und liefert
sie strukturiert aus. Siehe app/changelog.py für die Begründung, warum ohne
Markdown-Bibliothek geparst wird.
"""

from fastapi import APIRouter

from ..changelog import read_changelog_entries
from ..schemas import ChangelogEntryOut

router = APIRouter()


@router.get("/api/changelog", response_model=list[ChangelogEntryOut])
def get_changelog():
    return read_changelog_entries()
