import logging
import os
from pathlib import Path

from app.auth import _parse_bool_env, warn_if_secret_key_mismatches_file
from app.models import Customer
from app.paths import data_dir


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


# --- Geheimnisse für den Serverbetrieb (app/paths.py, seit 1.3.33) ----------

def test_data_dir_is_independent_of_working_directory(tmp_path, monkeypatch):
    """Der zentrale Fund aus der Bestandsaufnahme: data_dir() muss denselben
    Pfad liefern, unabhängig davon, aus welchem Arbeitsverzeichnis der Prozess
    gestartet wurde -- sonst würde ein künftiger Serverstart mit einem anderen
    Arbeitsverzeichnis (systemd-Unit, Docker-WORKDIR) stillschweigend einen
    anderen Ordner treffen. Ohne gesetztes ERP_DATA_DIR muss der Pfad also
    dateibasiert (relativ zu app/paths.py), nicht CWD-relativ, bestimmt sein."""
    monkeypatch.delenv("ERP_DATA_DIR", raising=False)
    expected = Path(__file__).resolve().parents[1] / "data"

    monkeypatch.chdir(tmp_path)
    from_elsewhere = data_dir()

    assert from_elsewhere == expected


def test_data_dir_respects_erp_data_dir_override(tmp_path, monkeypatch):
    override = tmp_path / "irgendwo_ausserhalb"
    monkeypatch.setenv("ERP_DATA_DIR", str(override))
    result = data_dir()
    assert result == override
    assert override.is_dir()  # wird bei Bedarf angelegt


def test_warn_if_secret_key_mismatches_file_logs_when_different(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    (tmp_path / ".erp_secret").write_text("altes-geheimnis-aus-der-datei", encoding="utf-8")
    monkeypatch.setenv("ERP_SECRET_KEY", "anderes-geheimnis-aus-der-umgebung")

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        warn_if_secret_key_mismatches_file()

    assert any("unterscheidet sich" in r.message for r in caplog.records)
    # Der Schlüssel selbst darf in keiner Log-Zeile auftauchen, auch nicht gekürzt.
    full_log = "\n".join(r.message for r in caplog.records)
    assert "altes-geheimnis-aus-der-datei" not in full_log
    assert "anderes-geheimnis-aus-der-umgebung" not in full_log


def test_warn_if_secret_key_mismatches_file_silent_when_equal(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    (tmp_path / ".erp_secret").write_text("dasselbe-geheimnis", encoding="utf-8")
    monkeypatch.setenv("ERP_SECRET_KEY", "dasselbe-geheimnis")

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        warn_if_secret_key_mismatches_file()

    assert caplog.records == []


def test_warn_if_secret_key_mismatches_file_silent_when_file_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ERP_SECRET_KEY", "frische-installation-ohne-bestehende-datei")

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        warn_if_secret_key_mismatches_file()

    assert caplog.records == []


def test_warn_if_secret_key_mismatches_file_silent_when_env_unset(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
    (tmp_path / ".erp_secret").write_text("irrelevant-da-env-fehlt", encoding="utf-8")
    monkeypatch.delenv("ERP_SECRET_KEY", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.auth"):
        warn_if_secret_key_mismatches_file()

    assert caplog.records == []
