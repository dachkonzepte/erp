"""Router: search (Büro-Suche, Etappe 1 -- seit 1.3.66, siehe CLAUDE.md "Büro-Suche" und
app/search.py für Registry/Dispatcher). Die Oberfläche (Suchfeld in der Kopfzeile,
Ergebnisseite) folgt erst in Etappe 2 -- dieser Router existiert bereits vollständig
funktionsfähig, damit Etappe 2 nur noch eine Oberfläche darauf bauen muss.

**Separater Endpunkt von der Monteurs-Suche** (app/routers/field_view.py::
get_field_view_property_search()) -- niemals ein gemeinsamer, rollenverzweigender Endpunkt
(Prinzip seit 1.3.64, siehe CLAUDE.md "Suche als Einstieg"). Das macht die Router-Dependency
`require_min_role(ROLE_OFFICE_AUFTRAG)` (ROLE_FIELD ausdrücklich NICHT dabei) zur PRIMÄREN
Sicherung: ein Monteur bekommt 403, BEVOR search_office() auch nur eine Zeile liest -- die
rolleninterne Filterung in search_office() selbst (jede Quelle prüft role gegen
source.allowed_roles) ist eine zweite, unabhängige Absicherung, kein Ersatz für diese hier.
Automatisch durch den bestehenden Rollen-Audit-Test (tests/test_v260_role_audit.py) erfasst,
da require_role() die dafür nötige _dk_roles-Markierung trägt."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role, require_role
from ..schemas import OfficeSearchGroupOut
from ..search import OFFICE_SEARCH_RESULT_LIMIT, search_office

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Die Suche ist nur für Büro und Administratoren verfügbar."))


@router.get("/api/search", response_model=list[OfficeSearchGroupOut])
def get_office_search(
    q: str = "",
    types: str | None = None,
    limit: int = OFFICE_SEARCH_RESULT_LIMIT,
    db: Session = Depends(get_db),
    _role: AppUser = _role_dep,
):
    """`types` ist eine optionale, kommagetrennte Liste von SearchSource-Schlüsseln (z. B.
    "customers,orders") -- unbekannte Schlüssel werden von search_office() stillschweigend nie
    getroffen (keine Quelle trägt sie), kein Fehler. `limit` wird auf [1, 100] geklammert, bevor
    er als limit_per_type an search_office() geht -- ein Client kann damit nie mehr als 100
    Treffer je Datensatzart erzwingen, unabhängig vom übergebenen Wert."""
    type_filter = frozenset(t.strip() for t in types.split(",") if t.strip()) if types else None
    capped_limit = max(1, min(limit, 100))
    return search_office(db, _role.role, q, limit_per_type=capped_limit, types=type_filter, employee_id=_role.employee_id)
