from pathlib import Path

from app.changelog import _inline_format, read_changelog_entries


def test_changelog_md_exists_and_is_parseable():
    entries = read_changelog_entries()
    assert len(entries) >= 40  # rückwirkend seit 1.0.6 rekonstruiert, wächst mit jeder neuen Version
    for e in entries:
        assert e["version"].count(".") == 2
        assert e["title"]
        assert e["html"].startswith("<p>")


def test_changelog_entries_are_ordered_newest_first():
    entries = read_changelog_entries()

    def vkey(v):
        return tuple(int(x) for x in v.split("."))

    versions = [vkey(e["version"]) for e in entries]
    assert versions == sorted(versions, reverse=True)


def test_changelog_covers_from_1_0_6_onward():
    """Bewusst nicht ab 1.0.5 -- die allererste Version wurde anders erstellt
    (kein durchgehendes README-Muster), das war beim Rekonstruieren explizit
    so besprochen."""
    entries = read_changelog_entries()
    versions = {e["version"] for e in entries}
    assert "1.0.6" in versions
    assert "1.0.5" not in versions


def test_inline_format_converts_code_and_bold():
    result = _inline_format("Ein `code`-Wort und **fetter** Text.")
    assert "<code>code</code>" in result
    assert "<b>fetter</b>" in result


def test_inline_format_escapes_html_to_prevent_injection():
    result = _inline_format("<script>alert(1)</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_changelog_router_registered():
    root = Path(__file__).parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    pages = (root / "app" / "routers" / "pages.py").read_text(encoding="utf-8")
    changelog_router = (root / "app" / "routers" / "changelog.py").read_text(encoding="utf-8")
    assert "changelog" in main
    assert '@router.get("/changelog"' in pages
    assert '@router.get("/api/changelog"' in changelog_router


def test_changelog_linked_from_settings_not_main_sidebar():
    """Seit 1.0.57 bewusst aus der Hauptnavigation in die Einstellungen
    verschoben (System-Gruppe, neben Änderungshistorie) -- muss dort nicht
    stehen, siehe entsprechende Klärung."""
    sidebar_html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    settings_html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert 'href="/changelog"' not in sidebar_html
    assert 'href="/changelog"' in settings_html
