import os

from app.auth import _parse_bool_env
from app.models import Customer


def test_parse_bool_env_recognizes_common_true_values():
    for val in ("1", "true", "True", "TRUE", "yes", "Yes", "  1  "):
        os.environ["_TEST_BOOL_ENV"] = val
        assert _parse_bool_env("_TEST_BOOL_ENV") is True, f"sollte True sein für {val!r}"


def test_parse_bool_env_recognizes_common_false_values_and_default():
    for val in ("0", "false", "False", "nein", ""):
        os.environ["_TEST_BOOL_ENV"] = val
        assert _parse_bool_env("_TEST_BOOL_ENV") is False, f"sollte False sein für {val!r}"
    os.environ.pop("_TEST_BOOL_ENV", None)
    assert _parse_bool_env("_TEST_BOOL_ENV") is False  # Standard-Default
    assert _parse_bool_env("_TEST_BOOL_ENV", default=True) is True  # eigener Default


def test_cookie_secure_defaults_to_off():
    import app.auth as auth_module
    # In einer normalen Testumgebung ist ERP_COOKIE_SECURE nicht gesetzt,
    # der beim Modulimport berechnete Wert sollte daher False sein. Die
    # Parsing-Logik selbst ist bereits oben separat und ausführlicher
    # abgedeckt (_parse_bool_env) -- hier geht es nur um die Verdrahtung.
    assert auth_module.COOKIE_SECURE is False


def test_db_session_fixture_provides_working_session(db_session):
    # Nutzt die neue gemeinsame Fixture aus conftest.py statt einer eigenen
    # lokalen Hilfsfunktion -- so, wie künftige Tests sie verwenden sollen.
    kunde = Customer(name="Fixture-Test GmbH", last_name="Fixture-Test GmbH")
    db_session.add(kunde)
    db_session.commit()
    assert kunde.id is not None
    assert db_session.get(Customer, kunde.id).name == "Fixture-Test GmbH"


def test_docker_compose_uses_env_vars_not_hardcoded_credentials():
    from pathlib import Path
    compose = (Path(__file__).parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD: dachkonzepte" not in compose
    assert "${POSTGRES_PASSWORD:-dachkonzepte}" in compose


def test_start_windows_bat_has_no_reload_and_explicit_host():
    from pathlib import Path
    bat = (Path(__file__).parents[1] / "start_windows.bat").read_text(encoding="utf-8")
    assert "--reload" not in bat
    assert "--host 127.0.0.1" in bat
