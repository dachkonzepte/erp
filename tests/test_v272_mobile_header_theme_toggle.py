"""Version 1.3.68 -- Hell/Dunkel-Umschalter in der Monteurs-Kopfzeile (_mobile_header.html).

Die Büro-Sidebar hat den Umschalter seit 1.3.44 im Fußbereich, die Monteurs-Kopfzeile hatte
bislang keinen -- ergänzt nach demselben Mechanismus (data-theme-Attribut auf <html>,
localStorage-Schlüssel 'erp_theme'), damit ein Monteur, der auf dem Tablet umschaltet, seine
Wahl beim nächsten Öffnen wiederfindet (siehe CLAUDE.md "Monteursansicht").

Drei Teile:
1. Struktur/Platzierung von _mobile_header.html, über eine bare jinja2.Environment mit
   gestubbten Globals geprüft (Muster tests/test_v254_topbar.py::_render -- kein echtes
   Rendering über eine Seite, da die vier Jinja-Globals mit Datenbankzugriff nicht per
   Test-Session umstellbar sind, siehe CLAUDE.md "Bekannte, bewusst offene Punkte").
2. Derselbe Mechanismus wie _sidebar.html (data-theme/'erp_theme'), nicht nur ein Knopf ohne
   Funktion -- per Quelltextvergleich der beiden IIFEs geprüft.
3. Bis 1.9.4 Regressionsschutz für die Vorgabe "get_theme() greift auch auf den Monteursseiten" (get_theme().accent_color im
   eigenen :root-Block der vier Seiten mit _mobile_header.html). Seit 1.9.5 färbt die Akzentfarbe die Oberfläche nicht mehr: die
   vier Seiten tragen keine Kopie der alten Palette, die alten Namen kommen zentral aus ds-alte-namen.css (_ds_kopf.html).
"""

from pathlib import Path

import jinja2

TEMPLATES_DIR = Path(__file__).parents[1] / "app" / "templates"


def _render_mobile_header(user=None, path="/mobil"):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))
    # seit 1.8.164: Logo-Kachel und Kontomenü (_kontomenue.html) im Monteurskopf
    env.globals["sidebar_logo_url"] = lambda: None
    env.globals["account_display"] = lambda u: ({"full_name": "Max Mustermann", "initials": "MM"} if u is not None
                                                else {"full_name": "", "initials": ""})

    class _FakeURL:
        pass

    class _FakeState:
        def __init__(self, u):
            self.erp_user = u

    class _FakeRequest:
        def __init__(self, u):
            self.url = _FakeURL()
            self.url.path = path
            self.state = _FakeState(u)

    class _FakeUser:
        display_name = "Max Mustermann"

    tmpl = env.get_template("_mobile_header.html")
    return tmpl.render(request=_FakeRequest(user if user is not None else _FakeUser()))


def _kopfzeile(html):
    start = html.index('<div class="mobile-header">')
    return html[start:html.index('<div class="mobile-suche"', start)]


# ---------------------------------------------------------------------------
# Struktur/Platzierung (seit 1.8.164: eine Zeile mit Kachel, Reitern, Lupe und Kontomenü)
# ---------------------------------------------------------------------------

def test_hell_dunkel_steht_im_kontomenue_des_monteurskopfs():
    """Bis 1.8.163 ein eigener Knopf (#mobileThemeToggle, 30 px, Sonne/Mond) neben dem Namen. Seit 1.8.164 im Kontomenü -- dasselbe wie in
    der Kopfzeile des Büros (_kontomenue.html)."""
    kopf = _kopfzeile(_render_mobile_header())
    menue = kopf[kopf.index('id="appTopbarAccountMenu"'):]
    assert 'id="appThemeToggle"' in menue and "mobileThemeToggle" not in kopf


def test_kopf_ist_eine_zeile_mit_kachel_reitern_lupe_und_konto():
    kopf = _kopfzeile(_render_mobile_header())
    stellen = [kopf.index(s) for s in ('class="mobile-header-kachel', '<nav class="mobile-nav"', 'id="mobileSearchToggle"',
                                       'id="appTopbarAccountBtn"')]
    assert stellen == sorted(stellen)
    reiter = [t.split(">")[-1] for t in kopf[kopf.index("<nav"):kopf.index("</nav>")].split("</a>")[:-1]]
    assert reiter == ["Heute", "Zeiterfassung", "Stundenzettel"]


def test_der_name_steht_immer_im_kopf():
    """„Ein Bericht, der versehentlich unter fremdem Namen unterschrieben wird, ist das Schlimmste, was hier passieren kann“ (1.3.0) --
    der volle Name steht im Kontoknopf, auch schmal (anders als in der Kopfzeile des Büros)."""
    html = _render_mobile_header()
    assert '<span class="app-konto-name">Max Mustermann</span>' in _kopfzeile(html)
    css = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8").split("</style>")[0]
    assert "app-konto-name{display:none" not in css.replace(" ", "") and ".app-konto-name,.mobile" not in css


def test_kopf_64_px_reiter_48_px_lupe_48_px():
    css = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8").split("</style>")[0]
    regel = lambda sel: css.split(sel + "{")[1].split("}")[0]  # noqa: E731
    kopf = regel(".mobile-header-wrap .mobile-header")
    assert "height:64px" in kopf and "box-sizing:border-box" in kopf and "background:var(--ds-navi-grund)" in kopf
    reiter = regel(".mobile-header-wrap .mobile-nav-reiter")
    # seit 1.8.170 Ecken 10 px und der Strich als inset-Schatten auf navi-aktiv (bis dahin ein unterer Rand von 3 px ohne Fläche)
    assert "height:48px" in reiter and "font-size:16px" in reiter and "border-radius:10px" in reiter and "border-bottom" not in reiter
    aktiv = regel(".mobile-header-wrap .mobile-nav-reiter.active")
    assert "background:var(--ds-navi-aktiv)" in aktiv and "box-shadow:inset 0 -3px 0 var(--ds-marke-hell)" in aktiv and "border" not in aktiv
    assert "color:#FFFFFF" in aktiv and "font-weight:600" in aktiv  # seit 1.9.0 wie in der Leiste (bis dahin navi-text in 500)
    # seit 1.9.1 Hover über --ds-navi-hover, geöffnet (Lupe, Kontomenü) navi-aktiv
    assert "background:var(--ds-navi-hover)" in regel(".mobile-header-wrap .mobile-nav-reiter:hover")
    assert regel(".mobile-header-wrap .mobile-lupe:hover") == "background:var(--ds-navi-hover)"
    assert regel('.mobile-header-wrap .mobile-lupe[aria-expanded="true"]') == "background:var(--ds-navi-aktiv)"
    assert regel(".mobile-header-wrap .app-konto .app-konto-knopf:hover") == "background:var(--ds-navi-hover)"
    lupe = regel(".mobile-header-wrap .mobile-lupe")
    assert "width:48px" in lupe and "height:48px" in lupe
    assert "width:40px" in regel(".mobile-header-wrap .mobile-header-kachel")


def test_seitenregeln_greifen_nicht_in_den_kopf():
    """Zeiterfassung, Objekt und Stundenzettel der Monteurin setzen button{min-height:44px;width:100%} -- bis 1.8.163 wurde der Kopf dort
    188 statt 173 px hoch. Seit 1.8.164 trägt jede Regel des Kopfs (außer der des Wrappers selbst) zwei Klassen. Seit 1.9.30 steht dahinter
    ein zweiter Block mit genau einer Regel: :root legt die Ecke der Karten im Monteursrahmen auf 16 px (tests/test_v460_ecken_der_karten.py)."""
    import re

    css = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8").split("<style>")[1].split("</style>")[0]
    css = re.sub(r"@media[^{]*\{", "", css)
    for selektoren in re.findall(r"([^{}]+)\{", css):
        for sel in selektoren.split(","):
            if sel.strip() != ".mobile-header-wrap":
                assert sel.strip().startswith(".mobile-header-wrap ") and len(re.findall(r"\.[\w-]+", sel)) >= 2, sel.strip()
    bloecke = (TEMPLATES_DIR / "_mobile_header.html").read_text(encoding="utf-8").split("<style>")[2:]
    assert [b.split("</style>")[0] for b in bloecke] == [":root{--ds-ecke-karte:var(--ds-ecke-tablet-karte)}"]


def test_einsaetze_ist_auch_auf_den_seiten_darunter_aktiv():
    def aktiv(pfad):
        nav = _kopfzeile(_render_mobile_header(path=pfad))
        nav = nav[nav.index("<nav"):nav.index("</nav>")]
        reiter = [stueck[stueck.rindex("<a "):] for stueck in nav.split("</a>")[:-1]]
        return [r.split(">")[-1] for r in reiter if "active" in r.split(">")[0] and 'aria-current="page"' in r.split(">")[0]]

    assert aktiv("/mobil") == ["Heute"] and aktiv("/orders/5/service-reports") == ["Heute"]
    assert aktiv("/checklisten/3") == ["Heute"] and aktiv("/mobil/objekt/2") == ["Heute"]
    assert aktiv("/time-tracking") == ["Zeiterfassung"] and aktiv("/mobil/stundenzettel") == ["Stundenzettel"]
    assert aktiv("/account") == []


# ---------------------------------------------------------------------------
# Derselbe Mechanismus wie die Kopfzeile des Büros: seit 1.8.164 dasselbe Kontomenü
# ---------------------------------------------------------------------------

def test_toggle_uses_the_same_storage_key_and_attribute_as_the_account_menu():
    """Bis 1.8.163 eigener Code im Monteurskopf, verglichen mit der Kopfzeile; seit 1.8.164 binden beide _kontomenue.html ein."""
    from tests import vorlagen_js

    assert vorlagen_js.bindet_ein("_mobile_header.html", "_kontomenue.html", TEMPLATES_DIR, nur_selbst=True)
    assert vorlagen_js.bindet_ein("_topbar.html", "_kontomenue.html", TEMPLATES_DIR, nur_selbst=True)
    konto = (TEMPLATES_DIR / "_kontomenue.html").read_text(encoding="utf-8")
    for needle in ("document.documentElement.getAttribute('data-theme')", "document.documentElement.setAttribute('data-theme'",
                   "localStorage.setItem('erp_theme'"):
        assert needle in konto, needle


def test_toggle_shows_the_current_theme():
    """Bis 1.8.163 wechselte der Knopf zwischen Sonne und Mond; seit 1.8.164 nennt der Eintrag im Kontomenü den Zustand."""
    konto = (TEMPLATES_DIR / "_kontomenue.html").read_text(encoding="utf-8")
    assert "themaZustand.textContent=thema()==='dark'?'dunkel':'hell'" in konto


def test_toggle_click_handler_writes_to_localstorage_and_updates_the_dom():
    konto = (TEMPLATES_DIR / "_kontomenue.html").read_text(encoding="utf-8")
    handler = konto[konto.index("themaKnopf.addEventListener('click'"):]
    handler = handler[:handler.index("});")]
    assert "document.documentElement.setAttribute('data-theme',neu)" in handler
    assert "localStorage.setItem('erp_theme',neu)" in handler


# ---------------------------------------------------------------------------
# Seit 1.9.5: die Monteursseiten nehmen die alten Farbnamen zentral, keine Akzentfarbe im :root
# ---------------------------------------------------------------------------

def test_monteursseiten_nehmen_die_alten_farbnamen_zentral():
    from tests import vorlagen_js

    for page in ("mobil.html", "mobil_objekt.html", "field_timesheet.html", "time_tracking_field.html"):
        text = (TEMPLATES_DIR / page).read_text(encoding="utf-8")
        assert vorlagen_js.bindet_ein(page, "_mobile_header.html", TEMPLATES_DIR), page  # seit 1.8.124 auch im Basis-Template
        assert vorlagen_js.bindet_ein(page, "_ds_kopf.html", TEMPLATES_DIR), page  # bindet ds-alte-namen.css ein
        root_start = text.index(":root{")
        root = text[root_start:text.index("}", root_start)]
        assert "get_theme()" not in root and "--accent:" not in root and "--card:" not in root, page
