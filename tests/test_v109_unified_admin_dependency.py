from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.auth import hash_password
from app.database import Base
from app.deps import require_admin
from app.models import AppUser


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/test", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def test_require_admin_allows_admin_and_returns_user():
    db = new_db()
    admin = AppUser(username="admin1", display_name="Admin", role="admin", active=True, password_hash=hash_password("Passwort123"))
    db.add(admin); db.commit()
    dep = require_admin("Nur für Admins.")
    assert dep(request_with_user(admin)) is admin


def test_require_admin_blocks_non_admin_with_custom_message():
    db = new_db()
    user = AppUser(username="user1", display_name="User", role="user", active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    dep = require_admin("Nur für Admins.")
    try:
        dep(request_with_user(user))
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert getattr(exc, "detail", None) == "Nur für Admins."


def test_require_admin_blocks_anonymous_user():
    dep = require_admin()
    try:
        dep(request_with_user(None))
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_require_admin_factory_supports_independent_messages_per_route():
    db = new_db()
    user = AppUser(username="user2", display_name="User Zwei", role="user", active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    dep_a = require_admin("Meldung A")
    dep_b = require_admin("Meldung B")
    try:
        dep_a(request_with_user(user))
    except Exception as exc_a:
        try:
            dep_b(request_with_user(user))
        except Exception as exc_b:
            assert exc_a.detail == "Meldung A"
            assert exc_b.detail == "Meldung B"


def test_time_backoffice_router_fully_uses_shared_dependency():
    # Stellt sicher, dass die Konsolidierung vollständig ist: keine der 15
    # time-backoffice-Routen hat mehr eine eigene lokale _require_admin-Prüfung.
    # (Der Name taucht im Docstring der Datei noch als Erklärung auf, daher
    # gezielt auf die konkreten Code-Muster prüfen statt auf den bloßen Namen.)
    #
    # Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8, siehe CLAUDE.md): das Zeiterfassungs-
    # Backoffice ist von require_admin() auf require_min_role(ROLE_OFFICE_AUFTRAG) angehoben --
    # die "eine geteilte Abhängigkeit, keine lokale Kopie"-Eigenschaft, die dieser Test seit der
    # 1.1.x-Konsolidierung prüft, gilt unverändert weiter, nur mit der neuen Abhängigkeit statt
    # der alten. Kein Endpunkt darf mehr require_admin() nutzen (die Anhebung wäre sonst nicht
    # vollständig), alle 15 teilen sich weiterhin dieselbe, einmal definierte _role_dep-Variable.
    src = (Path(__file__).parents[1] / "app/routers/time_backoffice.py").read_text(encoding="utf-8")
    assert "def _require_admin" not in src
    assert "_require_admin(request)" not in src
    assert "Depends(require_admin(" not in src
    assert src.count("_role=_role_dep") >= 15


def test_all_local_relative_imports_in_routers_resolve():
    """Regressionsschutz: lokale (Funktionskörper-)relative Importe in
    app/routers/*.py müssen nach der main.py-Aufteilung (1.0.7) auf den
    tatsächlichen Ziel-Ort zeigen. 'from .modul import X' innerhalb einer
    Datei, die jetzt in app/routers/ liegt, zeigt auf app/routers/modul.py
    statt auf app/modul.py -- genau dieser Fehler ist 1.0.7 bei
    update_quote_document_meta (ensure_quote_structure) passiert."""
    import ast
    root = Path(__file__).parents[1]
    routers_dir = root / "app" / "routers"
    app_dir = root / "app"

    problems = []
    for f in sorted(routers_dir.glob("*.py")):
        if f.name == "__init__.py":
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        module_level = set(id(n) for n in tree.body if isinstance(n, ast.ImportFrom))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for n in ast.walk(node):
                    if isinstance(n, ast.ImportFrom) and id(n) not in module_level and n.level >= 1:
                        target_dir = routers_dir if n.level == 1 else app_dir
                        target_file = target_dir / f"{n.module}.py"
                        if not target_file.exists():
                            problems.append(f"{f.name}:{n.lineno}: Ziel {target_file} existiert nicht")
                            continue
                        target_src = target_file.read_text(encoding="utf-8")
                        for alias in n.names:
                            if f"def {alias.name}" not in target_src and f"class {alias.name}" not in target_src:
                                problems.append(f"{f.name}:{n.lineno}: '{alias.name}' nicht in {target_file} gefunden")
    assert not problems, "\n".join(problems)
