from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.modules import OPTIONAL_MODULES, is_module_enabled, list_module_states, set_module_enabled
from app.routers.modules import get_modules, update_module
from app.schemas import ModuleStateUpdate


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_module_defaults_to_enabled_without_a_row():
    db = db_session()
    assert is_module_enabled(db, "aufgabenmanagement") is True


def test_set_module_enabled_toggles_and_persists():
    db = db_session()
    set_module_enabled(db, "aufgabenmanagement", False)
    assert is_module_enabled(db, "aufgabenmanagement") is False
    set_module_enabled(db, "aufgabenmanagement", True)
    assert is_module_enabled(db, "aufgabenmanagement") is True


def test_set_module_enabled_rejects_unknown_module():
    db = db_session()
    try:
        set_module_enabled(db, "does-not-exist", False)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_list_module_states_covers_registry():
    db = db_session()
    states = list_module_states(db)
    assert {s["module_key"] for s in states} == set(OPTIONAL_MODULES)
    assert all(s["enabled"] for s in states)


def test_update_module_route_wires_require_admin_dependency():
    """Der eigentliche 403-ohne-Admin-Fall wird bereits ausführlich für
    require_admin() selbst getestet (test_v109_unified_admin_dependency.py) -- hier
    nur sicherstellen, dass der Router diese gemeinsame Dependency tatsächlich
    verwendet, statt (wie andernorts historisch passiert) eine eigene Prüfung
    mitzuführen."""
    src = (Path(__file__).parents[1] / "app" / "routers" / "modules.py").read_text(encoding="utf-8")
    assert "Depends(require_admin(" in src


def test_get_modules_router_reachable_for_any_user():
    db = db_session()
    result = get_modules(db=db)
    assert {r["module_key"] for r in result} == set(OPTIONAL_MODULES)


def test_update_module_function_persists():
    db = db_session()
    result = update_module("aufgabenmanagement", ModuleStateUpdate(enabled=False), db=db, _admin=None)
    assert result["enabled"] is False
    assert is_module_enabled(db, "aufgabenmanagement") is False
