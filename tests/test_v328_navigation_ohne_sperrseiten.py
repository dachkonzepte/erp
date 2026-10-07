"""Version 1.8.24 -- kein sichtbarer Link führt auf eine gesperrte Seite (siehe
docs/archiv/rechtekonzept.md, "Datengrenze für Monteure", Nachtrag 1.8.24).

Anlass: die Seitenleiste zeigte dem Monteur auf der Berichtsseite "Wartungen", "Mängel", "Anfragen",
"Projekte", "Planung" -- ohne Rollenbedingung, jeder Klick endete auf access_denied.html. Der
Rollen-Audit (test_v260_role_audit.py) prüft die Seiten selbst, nicht die Links dorthin.

Der Test rendert für jede der vier Rollen jede Seite, die diese Rolle öffnen darf (Seitenrouten aus
app/routers/pages.py, keine Liste im Test), sammelt jeden Link im vom Server gerenderten Markup --
Seitenleiste, Kopfzeile, mobile Kopfzeile, Seiteninhalt -- und ruft ihn als dieselbe Rolle auf, mit
allen Routern aus app.main. Keiner darf 403 liefern, seit 1.8.65 auch keiner 404 (Seite gibt es nicht). Einmal mit allen Modulen an (alle Modul-Links
sichtbar), einmal mit allen aus (dann erscheinen die Hinweise "Modul deaktiviert" mit Link in die
Einstellungen).

Nicht erfasst: Links, die erst das JavaScript der Seite aus geladenen Daten baut (z. B. "← Auftrag"
auf der Berichtsseite) -- dafür scripts/klicktest_monteur_navigation.py. Seit 1.8.65 prüft
test_jeder_link_im_code_fuehrt_auf_eine_vorhandene_route zusätzlich ohne Browser, dass jedes Link-Ziel, das im
JavaScript der Vorlagen (href, location.href, window.open) oder im Python-Code (Werte unter einem Schlüssel "…url")
steht, auf eine vorhandene GET-Route zeigt -- Anlass: 1.8.63 baute das JavaScript der Auftragsseite und die API Links
auf /checklists/{id}, die Seite heißt /checklisten/{id}; der Durchlauf oben sah sie nicht."""

import re
from html.parser import HTMLParser

import pytest

from app.models import AppUser, Employee
from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.routers.pages import router as pages_router
from app.routers.pages import templates
from tests.test_v218_template_rendering import _dummy_path
from tests.test_v326_monteur_datengrenze import _monteur_client as _client_als, _routers_in_betriebsreihenfolge

ROLLEN = (ROLE_ADMIN, ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG, ROLE_FIELD)

# (Rolle, Seite, Link) -> warum der Link trotz 403 noch da ist. Ein Eintrag, der nicht mehr greift,
# ist rot -- dann hier streichen. Seit 1.8.27 leer: der Adressimport-Knopf in den Einstellungen und
# der Einstellungs-Link im Modul-Hinweis der Berichtsseite erscheinen nur noch, wer die Seite öffnen
# darf (Gegenprobe unten).
BEKANNT_OFFEN: dict[tuple[str, str, str], str] = {}

_LEERE_ELEMENTE = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Links(HTMLParser):
    """Interne Links, die beim Laden sichtbar sind: nicht in <script> (dort gebaute Links hängen an
    geladenen Daten) und nicht unter einem Element mit hidden-Attribut, Klasse "hidden" oder
    display:none -- solche Elemente blendet erst das JavaScript der Seite ein, wenn die Rolle passt."""

    def __init__(self):
        super().__init__()
        self.links, self._verborgen = set(), []

    def handle_starttag(self, tag, attrs):
        werte = dict(attrs)
        verborgen = ("hidden" in werte or "hidden" in (werte.get("class") or "").split()
                     or "display:none" in (werte.get("style") or "").replace(" ", ""))
        href = werte.get("href") or ""
        if tag == "a" and not verborgen and not any(self._verborgen) and href.startswith("/") and not href.startswith("//"):
            self.links.add(href)
        if tag not in _LEERE_ELEMENTE:
            self._verborgen.append(verborgen)

    def handle_endtag(self, tag):
        if tag not in _LEERE_ELEMENTE and self._verborgen:
            self._verborgen.pop()


def _links(html: str) -> set[str]:
    parser = _Links()
    parser.feed(html)
    return parser.links


def _seiten():
    for route in pages_router.routes:
        if "GET" in getattr(route, "methods", set()) and route.path not in ("/health", "/login"):
            yield _dummy_path(route.path)


def _durchlauf(welt: dict, rolle: str) -> dict:
    """Je Seite, die die Rolle öffnen darf, ihre Links; dazu jeder Link, der der Rolle 403 gibt.
    Gespeicherte Konten statt router_test_client(): der berechnet je Anfrage einen Passwort-Hash,
    bei rund 300 Anfragen je Lauf ein Vielfaches der Laufzeit. "with" hält eine Event-Loop offen."""
    seiten = {}
    with _client_als(welt["db"], _routers_in_betriebsreihenfolge(), welt["user_ids"][rolle]) as client:
        for pfad in _seiten():
            response = client.get(pfad)
            if response.status_code == 403:
                continue
            assert response.status_code == 200, f"{rolle} {pfad}: {response.status_code}"
            seiten[pfad] = _links(response.text)
        status = {link: client.get(link.split("#")[0]).status_code for link in set().union(*seiten.values())}
    # Seit 1.8.65 auch 404: ein Link auf eine Seite, die es nicht gibt (Anlass 1.8.63: /checklists/ statt /checklisten/).
    gesperrt = {(rolle, seite, link) for seite, links in seiten.items() for link in links if status[link] in (403, 404)}
    return {"seiten": seiten, "gesperrt": gesperrt}


@pytest.fixture
def welt(threaded_db_session):
    """Ein gespeichertes Konto je Rolle (damit ist /users auch nicht im Ersteinrichtungs-Fall für
    jeden offen), alle mit Mitarbeiter -- manche Endpunkte verlangen die Verknüpfung."""
    db = threaded_db_session
    employee = Employee(first_name="Max", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add(employee)
    db.flush()
    users = {rolle: AppUser(username=rolle, password_hash="x", display_name=rolle, role=rolle,
                            employee_id=employee.id, active=True) for rolle in ROLLEN}
    db.add_all(users.values())
    db.commit()
    return {"db": db, "user_ids": {rolle: user.id for rolle, user in users.items()}}


@pytest.fixture(params=[True, False], ids=["module_an", "module_aus"])
def module(request, monkeypatch):
    """is_module_enabled() liest sonst die (Wegwerf-)Datenbankdatei -- hier fest an bzw. aus."""
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: request.param)
    return request.param


def test_kein_sichtbarer_link_fuehrt_auf_eine_gesperrte_seite(welt, module):
    gesperrt, seiten_je_rolle = set(), {}
    for rolle in ROLLEN:
        ergebnis = _durchlauf(welt, rolle)
        gesperrt |= ergebnis["gesperrt"]
        seiten_je_rolle[rolle] = ergebnis["seiten"]
    offen = sorted(gesperrt - set(BEKANNT_OFFEN))
    assert offen == [], "\n".join(["Sichtbare Links auf gesperrte oder nicht vorhandene Seiten (Rolle, Seite, Link):",
                                   *map(str, offen)])
    if not module:
        assert set(BEKANNT_OFFEN) <= gesperrt, "Eintrag in BEKANNT_OFFEN greift nicht mehr -- streichen"

    # Der Durchlauf hat wirklich etwas gesehen: das Büro alle Seiten mit Leiste, der Monteur seine.
    assert len(seiten_je_rolle[ROLE_ADMIN]) > 40
    assert {"/projects", "/planning", "/inquiries"} <= seiten_je_rolle[ROLE_ADMIN]["/"]
    assert "/orders/1/service-reports" in seiten_je_rolle[ROLE_FIELD]
    assert "/mobil" in seiten_je_rolle[ROLE_FIELD]


def test_seitenleiste_des_monteurs_auf_der_berichtsseite(welt, monkeypatch):
    """Punkt 3 dieser Runde: auf der Berichtsseite bleiben dem Monteur in der Seitenleiste nur Start
    (leitet auf /mobil) und Zeiterfassung -- Wartungen, Mängel, Anfragen, Projekte, Planung sind weg
    ("Mein Konto" steckt im Kontomenü der Kopfzeile, das erst ein Klick öffnet). Das Büro sieht sie
    unverändert."""
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)
    db, pfad = welt["db"], "/orders/1/service-reports"
    monteur = _client_als(db, [pages_router], welt["user_ids"][ROLE_FIELD]).get(pfad)
    assert _links(monteur.text) == {"/", "/time-tracking"}
    buero = _client_als(db, [pages_router], welt["user_ids"][ROLE_OFFICE_AUFTRAG]).get(pfad)
    assert {"/maintenance-contracts", "/findings", "/inquiries", "/projects", "/planning"} <= _links(buero.text)


def test_gegenprobe_links_ohne_rollenbedingung_fallen_auf(welt, monkeypatch):
    """Alle Rollenbedingungen in den Vorlagen aufgehoben (can() immer wahr) -- der Durchlauf muss die
    fünf Links aus 1.8.24 beim Monteur als gesperrt melden."""
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)
    monkeypatch.setitem(templates.env.globals, "can", lambda user, *roles: True)
    ergebnis = _durchlauf(welt, ROLE_FIELD)
    links = {link for _, seite, link in ergebnis["gesperrt"] if seite == "/orders/1/service-reports"}
    assert {"/maintenance-contracts", "/findings", "/inquiries", "/projects", "/planning"} <= links


def test_gegenprobe_die_frueheren_ausnahmen_fallen_auf(welt, monkeypatch):
    """1.8.27: dieselbe Gegenprobe für die drei bis dahin bekannten Ausnahmen -- ohne Rollenbedingung
    meldet der Durchlauf den Adressimport-Knopf bei beiden Bürorollen und, bei abgeschaltetem Modul,
    den Einstellungs-Link der Berichtsseite beim Monteur."""
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: False)
    monkeypatch.setitem(templates.env.globals, "can", lambda user, *roles: True)
    gesperrt = set()
    for rolle in (ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN):
        gesperrt |= _durchlauf(welt, rolle)["gesperrt"]
    assert {(ROLE_OFFICE_AUFTRAG, "/settings", "/address-import"),
            (ROLE_OFFICE_FINANZEN, "/settings", "/address-import"),
            (ROLE_FIELD, "/orders/1/service-reports", "/settings#modules")} <= gesperrt


@pytest.mark.parametrize("rolle,erwartet", [(ROLE_FIELD, False), (ROLE_OFFICE_AUFTRAG, True), (ROLE_ADMIN, True)])
def test_berichtsseite_baut_auftrags_und_kundenlinks_nur_fuers_buero(welt, monkeypatch, rolle, erwartet):
    """Die Breadcrumb (Kunde, Auftragsnummer), "← Auftrag" und "Folgeauftrag ansehen" baut erst das
    JavaScript -- der Durchlauf oben sieht sie nicht. Die Seite bekommt deshalb vom Server, ob die Rolle
    Büro-Seiten öffnen darf; "← Auftrag" fehlt für den Monteur schon im Markup. Im Browser prüft das
    scripts/klicktest_monteur_navigation.py."""
    monkeypatch.setitem(templates.env.globals, "is_module_enabled", lambda key: True)
    html = _client_als(welt["db"], [pages_router], welt["user_ids"][rolle]).get("/orders/1/service-reports").text
    assert f"const darfBueroSeiten={'true' if erwartet else 'false'};" in html
    assert ('id="orderLink"' in html) is erwartet


# ---------------------------------------------------------------------------
# Seit 1.8.65: Link-Ziele im Code (JavaScript der Vorlagen, Python) -- ohne Browser
# ---------------------------------------------------------------------------

_LUECKE = "\x00"  # Platzhalter für einen erst zur Laufzeit eingesetzten Teil (${…}, {{ … }}, {…} im f-String)
_LINK_START = re.compile(
    r"""(?:\bhref\s*=\s*\\?|(?:location\.href|window\.location)\s*=\s*|"""
    r"""(?:location\.assign|location\.replace|window\.open)\(\s*)(["'`])(/[A-Za-z][^"'`\s<>]*)""")


def _luecken(text: str) -> tuple[str, bool]:
    """${…} und {{ … }} durch den Platzhalter ersetzen; ein offenes ${ (Ausdruck mit Anführungszeichen darin) beendet das
    Ziel -- dann ist es nur ein Anfang. (Text, vollständig?)"""
    text = re.sub(r"\{%.*?%\}", "", re.sub(r"\{\{.*?\}\}", _LUECKE, text))
    text = re.sub(r"\$\{[^{}]*\}", _LUECKE, text)
    if "${" in text:
        return text.split("${", 1)[0] + _LUECKE, False
    return text, True


def _vorlagen_links() -> list[tuple[str, str, bool]]:
    """(Datei, Ziel, vollständig?) für jedes Link-Ziel in den Vorlagen, das mit /<Buchstabe> beginnt. Vollständig ist es,
    wenn nach ihm das öffnende Anführungszeichen folgt; sonst geht es mit einem Ausdruck weiter ('/orders/'+id) und ist
    nur ein Anfang."""
    from pathlib import Path

    gefunden = []
    for datei in sorted((Path(__file__).resolve().parents[1] / "app" / "templates").glob("*.html")):
        text = datei.read_text(encoding="utf-8")
        for m in _LINK_START.finditer(text):
            ziel, vollstaendig = _luecken(m.group(2))
            danach = text[m.end():m.end() + 1]
            gefunden.append((datei.name, ziel, vollstaendig and danach == m.group(1)))
    return gefunden


def _python_links() -> list[tuple[str, str, bool]]:
    """(Datei, Ziel, True) für jeden Text oder f-String unter app/, der mit "/" beginnt und als Wert unter einem Schlüssel,
    Argument oder Attribut steht, dessen Name auf "url" endet (url, target_url, source_url …)."""
    import ast
    from pathlib import Path

    def texte(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value
        elif isinstance(node, ast.JoinedStr):
            yield "".join(v.value if isinstance(v, ast.Constant) else _LUECKE for v in node.values)
        elif isinstance(node, ast.IfExp):
            yield from texte(node.body)
            yield from texte(node.orelse)

    gefunden = []
    wurzel = Path(__file__).resolve().parents[1] / "app"
    for datei in sorted(wurzel.rglob("*.py")):
        for node in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            werte = []
            if isinstance(node, ast.Dict):
                werte = [v for k, v in zip(node.keys, node.values)
                         if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.endswith("url")]
            elif isinstance(node, ast.keyword) and node.arg and node.arg.endswith("url"):
                werte = [node.value]
            elif isinstance(node, ast.Assign):
                werte = [node.value for z in node.targets if isinstance(z, ast.Attribute) and z.attr.endswith("url")]
            for wert in werte:
                for text in texte(wert):
                    if re.match(r"^/[A-Za-z]", text):
                        gefunden.append((str(datei.relative_to(wurzel.parent)), text, True))
    return gefunden


def _get_routen() -> list[list[str]]:
    """Die Segmente jeder GET-Route der App (Router aus app.main)."""
    routen = []
    for router in _routers_in_betriebsreihenfolge():
        for route in router.routes:
            if "GET" in (getattr(route, "methods", None) or set()):
                routen.append(route.path.strip("/").split("/"))
    return routen


def _passt(segment: str, routen_segment: str, *, anfang: bool) -> bool:
    if routen_segment.startswith("{"):
        return segment != "" or anfang
    muster = "".join(".*" if c == _LUECKE else re.escape(c) for c in segment) + (".*" if anfang else "")
    return re.fullmatch(muster, routen_segment) is not None


def _fuehrt_auf_route(ziel: str, vollstaendig: bool, routen: list[list[str]]) -> bool:
    """Gibt es eine GET-Route, die zu diesem Ziel passt (vollständig) bzw. mit ihm beginnt (Anfang)? Anfrage und Anker
    zählen nicht; ein Platzhalter passt auf jedes Stück."""
    pfad = re.split(r"[?#]", ziel, maxsplit=1)[0]
    if pfad != ziel:
        vollstaendig = True  # vor ? oder # ist der Pfad zu Ende
    segmente = pfad.strip("/").split("/") if pfad.strip("/") else [""]
    if pfad.endswith("/") and pfad != "/":
        segmente.append("")  # "/checklisten/" + id: das nächste Segment folgt erst
        vollstaendig = False
    for route in routen:
        if route and route[-1].endswith(":path}"):
            route = route[:-1] + [route[-1]] * max(1, len(segmente) - len(route) + 1)
        if (vollstaendig and len(route) != len(segmente)) or len(route) < len(segmente):
            continue
        letzte = len(segmente) - 1
        if all(_passt(s, route[i], anfang=not vollstaendig and i == letzte) for i, s in enumerate(segmente)):
            return True
    return False


def test_jeder_link_im_code_fuehrt_auf_eine_vorhandene_route():
    """Seit 1.8.65 (Punkt 0 der Runde 2c-2e): jedes Link-Ziel im JavaScript der Vorlagen und jeder "…url"-Wert im Python-Code
    zeigt auf eine GET-Route, die es gibt -- 1.8.63 hatte /checklists/{id} statt /checklisten/{id} gebaut."""
    routen = _get_routen()
    links = _vorlagen_links() + _python_links()
    assert len(links) > 300, "Link-Ziele nicht gefunden -- hat sich die Schreibweise geändert?"
    ohne_route = sorted({(datei, ziel.replace(_LUECKE, "…")) for datei, ziel, vollstaendig in links
                         if not _fuehrt_auf_route(ziel, vollstaendig, routen)})
    assert ohne_route == [], "\n".join(["Link-Ziele ohne Route (Datei, Ziel):", *map(str, ohne_route)])


@pytest.mark.parametrize("ziel, vollstaendig, erwartet", [
    ("/checklisten/\x00", True, True), ("/checklists/\x00", True, False), ("/checklists/", False, False),
    ("/checklisten/", False, True), ("/orders/\x00#acceptanceCard", True, True), ("/tasks?task=\x00", True, True),
    ("/api/checklists/\x00/pdf", True, True), ("/api/checklisten/\x00/pdf", True, False), ("/quotes/", False, True),
], ids=["checklisten", "checklists", "checklists_anfang", "checklisten_anfang", "anker", "anfrage", "api", "api_tippfehler",
        "anfang_vor_edit"])
def test_gegenprobe_falsche_link_ziele_fallen_auf(ziel, vollstaendig, erwartet):
    """Die Prüfung oben erkennt den Fehler aus 1.8.63 -- als vollständiges Ziel und als Anfang ("/checklists/" + id)."""
    assert _fuehrt_auf_route(ziel, vollstaendig, _get_routen()) is erwartet
