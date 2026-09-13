from pathlib import Path
import re


def test_settings_sidebar_has_all_sections():
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    for key in ["general", "numbers", "payment-terms", "tax-keys", "option-lists", "employee-functions", "labor-rate", "calculation", "planning"]:
        assert f'data-settings-section="{key}"' in html
        assert f'id="settings-{key}"' in html
    assert "settings-sidebar" in html
    assert "showSettingsSection" in html


def test_every_sidebar_section_is_in_the_settings_sections_whitelist():
    """Regressionstest für genau den 1.0.46-Fehler: showSettingsSection()
    verwirft jeden Aufruf mit einem Wert, der nicht in der JS-Konstante
    SETTINGS_SECTIONS steht, und fällt still auf 'general' zurück -- ein neu
    angelegter Sidebar-Button ohne passenden Eintrag in dieser Liste sieht
    dann klickbar aus, öffnet aber nie die eigene Sektion. Da beim Anlegen
    der Steuerschlüssel-Sektion genau das passiert ist, prüft dieser Test ab
    jetzt automatisch, dass JEDER data-settings-section-Wert im HTML auch in
    der Whitelist auftaucht -- unabhängig davon, welche Sektionen künftig
    dazukommen."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    sidebar_keys = set(re.findall(r'data-settings-section="([a-z0-9-]+)"', html))
    assert sidebar_keys, "keine data-settings-section-Buttons gefunden -- Regex vermutlich falsch"
    whitelist_match = re.search(r"const SETTINGS_SECTIONS\s*=\s*\[(.*?)\]", html)
    assert whitelist_match, "SETTINGS_SECTIONS-Konstante nicht gefunden"
    whitelist_keys = set(re.findall(r"'([a-z0-9-]+)'", whitelist_match.group(1)))
    missing = sidebar_keys - whitelist_keys
    assert not missing, f"Sidebar-Button(s) ohne Eintrag in SETTINGS_SECTIONS (Sektion bliebe unklickbar): {missing}"


def test_version_is_current():
    root = Path(__file__).parents[1]
    main_py = (root / "app" / "main.py").read_text(encoding="utf-8")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    assert re.match(r"^\d+\.\d+\.\d+$", version)
    assert "version=APP_VERSION" in main_py


def test_main_app_sidebar_stays_pinned_while_scrolling():
    """Seit 1.0.51: die App-weite Hauptnavigation (_sidebar.html, nicht zu
    verwechseln mit der Einstellungen-eigenen .settings-sidebar oben in
    dieser Datei) bleibt auf Desktop-Breiten beim Scrollen sichtbar
    (position:sticky), statt mit der Seite mitzuscrollen -- fiel besonders
    auf langen Seiten wie der seit 1.0.48 konsolidierten Projektmappe auf.
    Die bestehende Mobile-Sonderregel (position:fixed als Ausklapp-Menü bei
    schmalen Bildschirmen) bleibt davon unberührt."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    base_rule = html[html.index(".app-sidebar{width:240px"):html.index("}", html.index(".app-sidebar{width:240px"))]
    assert "position:sticky" in base_rule
    assert "top:0" in base_rule
    assert "height:100vh" in base_rule
    # Mobile-Override (Ausklapp-Menü) muss weiterhin bestehen bleiben.
    assert "position:fixed;top:0;left:0;bottom:0;z-index:40" in html


def test_settings_load_is_resilient_to_a_single_failed_request():
    """Regressionstest: load() in settings.html lud bisher alle Bereiche in
    einem einzigen Promise.all() -- schlug irgendein einzelner Aufruf fehl
    (z.B. eine noch nicht ausgeführte Migration), brach das komplette Laden
    ab und KEIN Bereich wurde befüllt, obwohl die übrigen Aufrufe
    erfolgreich gewesen wären. Jetzt Promise.allSettled() mit
    typgerechten Ausweich-Werten (leeres Array/Objekt) je fehlgeschlagenem
    Aufruf, damit ein einzelner Fehler nicht die ganze Seite leert."""
    html = (Path(__file__).parents[1] / "app" / "templates" / "settings.html").read_text(encoding="utf-8")
    assert "Promise.allSettled" in html
    assert "Promise.all(" not in html.replace("Promise.allSettled(", "")
    assert "status==='fulfilled'" in html
    # Klare, aufrufspezifische Fehlermeldung statt nur der ersten Ablehnung.
    assert "konnten nicht geladen werden" in html
