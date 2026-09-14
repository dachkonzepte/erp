"""Version 1.3.42 -- zwei reale Vorfälle beim Ausliefern von 1.3.38-1.3.41 auf dem
Produktivserver, siehe CLAUDE.md "Zwei Vorfälle beim Ausliefern von 1.3.38-1.3.41".

Vorfall 1: `alembic upgrade head` lief auf dem Server ohne geladene Umgebungsvariablen, fiel
dadurch stillschweigend auf einen falschen Wert zurück -- die Migration griff nicht, der Fehler
ging unbemerkt unter. alembic/env.py liest DATABASE_URL jetzt UNBEDINGT direkt aus der Umgebung
und bricht mit einer klaren Fehlermeldung ab, wenn sie fehlt (kein Rückfall wie app/database.py).

Vorfall 2: ein fehlgeschlagener Logo-Upload legte danach jede Seite lahm, einschließlich der
Anmeldeseite -- weil (a) der Upload-Endpunkt nur den spoofbaren content_type-Header prüfte, statt
die Datei tatsächlich zu dekodieren, und (b) keiner der vier Jinja-Globals in app/routers/pages.py
gegen eine Ausnahme abgesichert war. Beides ist hier getestet: validate_logo_image()/der 400-statt-
500-Endpunkt, und dass alle vier Globals unter einem simulierten DB-Fehler auf einen sicheren
Rückfallwert ausweichen, statt die Ausnahme durchschlagen zu lassen."""

import os
import subprocess
import sys
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import company_logo
from app.routers import pages as pages_router_module

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_png_bytes(size=(200, 100)):
    buf = BytesIO()
    Image.new("RGBA", size, (30, 130, 60, 255)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Vorfall 1: alembic/env.py verlangt DATABASE_URL unbedingt, kein stiller Rückfall
# ---------------------------------------------------------------------------

def _run_alembic(args, env, timeout=180):
    return subprocess.run(
        [sys.executable, "-m", "alembic"] + args,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_alembic_fails_loudly_without_database_url():
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    result = _run_alembic(["current"], env)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "DATABASE_URL" in combined


def test_alembic_upgrade_head_honors_the_given_database_url(tmp_path):
    """Beweist das Gegenteil des Vorfalls: mit gesetzter DATABASE_URL migriert alembic
    tatsächlich GENAU diese (frische, temporäre) Datenbank -- nicht die App-eigene
    SQLite-Vorgabedatei, die dieselbe URL nur zufällig träfe, wenn man sie nicht explizit setzt."""
    db_path = tmp_path / "alembic_env_test.db"
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    upgrade_result = _run_alembic(["upgrade", "head"], env)
    assert upgrade_result.returncode == 0, upgrade_result.stdout + upgrade_result.stderr
    assert db_path.is_file()

    current_result = _run_alembic(["current"], env)
    assert current_result.returncode == 0
    assert current_result.stdout.strip()  # zeigt eine echte Revision, keine leere Ausgabe


# ---------------------------------------------------------------------------
# Vorfall 2, Teil 1: validate_logo_image() -- Pillow-Dekodierbarkeit statt content_type-Vertrauen
# ---------------------------------------------------------------------------

def test_validate_logo_image_accepts_real_png():
    company_logo.validate_logo_image("image/png", _make_png_bytes())  # wirft nicht


def test_validate_logo_image_rejects_undecodable_bytes_despite_claimed_content_type():
    with pytest.raises(ValueError, match="Ungültiges Bild"):
        company_logo.validate_logo_image("image/png", b"das ist keine Bilddatei")


def test_validate_logo_image_skips_check_for_svg():
    """Pillow kann SVG grundsätzlich nicht öffnen -- das ist dort kein Fehler, kein
    Dateiformatproblem, deshalb bewusst ausgenommen."""
    company_logo.validate_logo_image("image/svg+xml", b"<svg></svg>")  # wirft nicht


# ---------------------------------------------------------------------------
# Vorfall 2, Teil 2: der Endpunkt selbst -- 400 statt 500, kein Zustand bleibt zurück
# ---------------------------------------------------------------------------

def test_upload_company_logo_returns_400_not_500_for_undecodable_file(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    from app.routers.settings import router as settings_router
    client = router_test_client(threaded_db_session, settings_router)

    resp = client.post(
        "/api/settings/general/logo",
        files={"file": ("logo.png", b"das ist keine Bilddatei", "image/png")},
    )
    assert resp.status_code == 400
    assert "Ungültiges Bild" in resp.json()["detail"]


def test_failed_upload_leaves_no_destructive_state_behind(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    """Ein gescheiterter Upload darf keinen Zustand hinterlassen, der Seiten zerstört --
    logo_filename bleibt unverändert, solange die Datei nicht tatsächlich gültig gespeichert
    wurde (siehe CLAUDE.md, Vorfall 2)."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    from app.routers.settings import router as settings_router
    client = router_test_client(threaded_db_session, settings_router)

    resp = client.post(
        "/api/settings/general/logo",
        files={"file": ("logo.png", b"das ist keine Bilddatei", "image/png")},
    )
    assert resp.status_code == 400

    logo_resp = client.get("/api/settings/general/logo")
    assert logo_resp.status_code == 404  # kein Logo hinterlegt -- nicht auf eine kaputte Datei zeigend


def test_upload_company_logo_still_succeeds_for_a_real_png(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    """Regression: die neue Prüfung darf einen echten, gültigen Upload nicht blockieren."""
    monkeypatch.setattr(company_logo, "LOGO_ROOT", tmp_path / "company_logo")
    from app.routers.settings import router as settings_router
    client = router_test_client(threaded_db_session, settings_router)

    resp = client.post(
        "/api/settings/general/logo",
        files={"file": ("logo.png", _make_png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["logo_filename"]


# ---------------------------------------------------------------------------
# Vorfall 2, Teil 3: die vier Jinja-Globals werfen nie -- Rückfall statt Ausnahme
# ---------------------------------------------------------------------------

def test_get_theme_falls_back_to_default_accent_color_on_error(monkeypatch):
    def _boom(db):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(pages_router_module, "get_accent_color", _boom)
    assert pages_router_module._current_theme() == {"accent_color": "#0d9488"}


def test_is_module_enabled_falls_back_to_true_on_error(monkeypatch):
    """True, nicht False -- dieselbe Opt-out-Philosophie wie der Normalfall (app/modules.py):
    ein DB-Fehler soll ein Modul nicht fälschlich abschalten."""
    def _boom(db, module_key):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(pages_router_module, "is_module_enabled", _boom)
    assert pages_router_module._is_module_enabled("wartungen") is True


def test_sidebar_logo_url_falls_back_to_none_on_error(monkeypatch):
    def _boom(db):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(pages_router_module, "sidebar_logo_filename", _boom)
    assert pages_router_module._sidebar_logo_url() is None


def test_sidebar_logo_height_px_falls_back_to_default_on_error(monkeypatch):
    def _boom(db):
        raise RuntimeError("simulierter DB-Fehler")

    monkeypatch.setattr(pages_router_module, "_sidebar_logo_height_px_lookup", _boom)
    assert pages_router_module._sidebar_logo_height_px() == company_logo.DEFAULT_SIDEBAR_LOGO_HEIGHT_PX


# ---------------------------------------------------------------------------
# Ende-zu-Ende-Simulation von Vorfall 1: eine fehlende Tabelle (übersprungene Migration)
# darf get_theme()/is_module_enabled() nicht mit einer Ausnahme durchschlagen lassen
# ---------------------------------------------------------------------------

@contextmanager
def _broken_session_local_factory():
    """Ein Engine OHNE Base.metadata.create_all() -- keine einzige Tabelle existiert, genau das
    Vorfall-1-Symptom (eine übersprungene Migration, hier im Extremfall: die ganze Kette)."""
    engine = create_engine("sqlite:///:memory:")
    yield sessionmaker(bind=engine)


def test_get_theme_survives_a_missing_general_settings_table(monkeypatch):
    with _broken_session_local_factory() as broken_session_local:
        monkeypatch.setattr(pages_router_module, "SessionLocal", broken_session_local)
        assert pages_router_module._current_theme() == {"accent_color": "#0d9488"}


def test_is_module_enabled_survives_a_missing_enabled_modules_table(monkeypatch):
    with _broken_session_local_factory() as broken_session_local:
        monkeypatch.setattr(pages_router_module, "SessionLocal", broken_session_local)
        assert pages_router_module._is_module_enabled("wartungen") is True


def test_sidebar_logo_url_survives_a_missing_general_settings_table(monkeypatch):
    with _broken_session_local_factory() as broken_session_local:
        monkeypatch.setattr(pages_router_module, "SessionLocal", broken_session_local)
        assert pages_router_module._sidebar_logo_url() is None


def test_sidebar_logo_height_px_survives_a_missing_general_settings_table(monkeypatch):
    with _broken_session_local_factory() as broken_session_local:
        monkeypatch.setattr(pages_router_module, "SessionLocal", broken_session_local)
        assert pages_router_module._sidebar_logo_height_px() == company_logo.DEFAULT_SIDEBAR_LOGO_HEIGHT_PX


# ---------------------------------------------------------------------------
# Audit: die vier bekannten Globals sind die einzigen mit Datenbankzugriff
# ---------------------------------------------------------------------------

def test_no_further_database_backed_jinja_globals_exist_unguarded():
    """Geprüft wie in CLAUDE.md dokumentiert: grep über app/ auf env.globals[ -- es dürfen nur
    die fünf bereits abgesicherten Zuweisungen (plus das statische app_version) existieren --
    seit 1.3.45 zusätzlich account_display() (_topbar.html), ebenso try/except-gehärtet wie die
    vier seit 1.3.42. Schlägt fehl, falls ein künftiges Global registriert wird, ohne dass dieser
    Test (und die Absicherung selbst) mitbedacht werden."""
    root = Path(__file__).parents[1]
    matches = []
    for py_file in (root / "app").rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "env.globals[" in text:
            matches.append(py_file.relative_to(root).as_posix())
    assert matches == ["app/routers/pages.py"]

    src = (root / "app" / "routers" / "pages.py").read_text(encoding="utf-8")
    assigned = [line.strip() for line in src.splitlines() if line.strip().startswith("templates.env.globals[")]
    assert len(assigned) == 6  # app_version + die fünf abgesicherten Globals
