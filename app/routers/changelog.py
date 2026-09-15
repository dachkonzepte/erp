"""Router: changelog (seit 1.0.52).

Ein einzelner, schreibgeschützter Endpunkt -- liest CHANGELOG.md und liefert
sie strukturiert aus. Siehe app/changelog.py für die Begründung, warum ohne
Markdown-Bibliothek geparst wird.
"""

from fastapi import APIRouter, Depends

from ..changelog import read_changelog_entries
from ..models import AppUser
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from ..schemas import ChangelogEntryOut

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): nur aus den Einstellungen erreichbar, Büro/Admin --
# keine sensiblen Daten (reine Software-Versionshistorie), aber ohne fachlichen Grund, sie
# einem Monteur zu zeigen.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE))


@router.get("/api/changelog", response_model=list[ChangelogEntryOut])
def get_changelog(_role: AppUser = _role_dep):
    return read_changelog_entries()
