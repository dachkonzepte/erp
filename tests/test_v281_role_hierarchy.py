"""Rechtekonzept, Etappe 1 -- die Hierarchie selbst (siehe CLAUDE.md "Rechtekonzept" ->
"Vier Rollen"). Zentrale Frage des Betreibers vor dem Bau dieser Etappe: "Wie werden die vier
Rollen in einer sinnvollen Hierarchie geprüft? admin ⊇ buero_finanzen ⊇ buero_auftrag ⊇ field --
kann buero_finanzen alles, was buero_auftrag kann, plus mehr? Prüfe, ob has_role() das als
Hierarchie abbilden kann, sodass require_role(buero_auftrag) automatisch auch buero_finanzen und
admin durchlässt." Dieser Test-Datei ist der direkte, end-to-end erbrachte Nachweis dafür --
nicht nur an der Funktion isoliert (das leistet test_v260_role_audit.py bereits für die
_dk_roles-Markierung), sondern über eine echte, laufende FastAPI-Route mit echten HTTP-Antworten.

Vier Dinge werden hier belegt:
1. ROLE_RANK bildet exakt die vom Betreiber vorgegebene Kette ab (admin > buero_finanzen >
   buero_auftrag > field), als reine Ganzzahl-Rangfolge (Total Order, kein Baum).
2. has_min_role() prüft diese Kette korrekt für JEDE der 16 (4×4) Rolle/Schwelle-Kombinationen,
   inklusive der Randfälle None und ein unbekannter/nicht mehr existierender Rollenwert (z. B.
   das abgelöste "office") -- beide fallen sicher durch (Standardverweigerung, kein stiller
   Rückfall auf "irgendwie erlaubt").
3. require_min_role() setzt das end-to-end tatsächlich durch: eine echte Route hinter
   require_min_role(ROLE_OFFICE_AUFTRAG) lässt buero_auftrag, buero_finanzen UND admin durch
   (200), field bekommt 403 -- ohne dass buero_finanzen/admin in der Dependency-Definition
   einzeln genannt werden mussten. Das ist die eigentliche Antwort auf die Frage des Betreibers.
4. has_role() (die FLACHE Mengenzugehörigkeits-Prüfung) bleibt davon unberührt -- sie kennt keine
   Hierarchie und soll auch keine kennen (für die echten "für jede Rolle offen"-Fälle wie
   require_role(ROLE_ADMIN, ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG, ROLE_FIELD), die
   inhaltlich einer Mindestrang-Prüfung auf ROLE_FIELD entsprechen, aber weiterhin auch direkt
   als Menge ausdrückbar bleiben)."""

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.models import AppUser
from app.permissions import (
    ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_RANK, has_min_role,
    has_role, require_min_role,
)


def _user(role):
    return AppUser(username=f"u-{role}", display_name=role, role=role, active=True, password_hash="x")


# ---------------------------------------------------------------------------
# 1. ROLE_RANK selbst
# ---------------------------------------------------------------------------

def test_role_rank_is_exactly_the_operator_specified_chain():
    """admin ⊇ buero_finanzen ⊇ buero_auftrag ⊇ field -- wörtlich als Betreibervorgabe genannt."""
    assert ROLE_RANK[ROLE_FIELD] < ROLE_RANK[ROLE_OFFICE_AUFTRAG]
    assert ROLE_RANK[ROLE_OFFICE_AUFTRAG] < ROLE_RANK[ROLE_OFFICE_FINANZEN]
    assert ROLE_RANK[ROLE_OFFICE_FINANZEN] < ROLE_RANK[ROLE_ADMIN]
    # Keine fünfte, unbekannte Rolle hat sich eingeschlichen -- genau die vier.
    assert set(ROLE_RANK) == {ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN}


# ---------------------------------------------------------------------------
# 2. has_min_role() -- die volle 4x4-Matrix plus Randfälle
# ---------------------------------------------------------------------------

def test_has_min_role_full_matrix():
    """Für jede der vier Rollen gegen jede der vier Schwellen: erfüllt genau dann, wenn der
    eigene Rang mindestens dem Schwellenrang entspricht -- keine Ausnahme, keine Sonderregel."""
    roles = (ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN)
    for role in roles:
        user = _user(role)
        for threshold in roles:
            expected = ROLE_RANK[role] >= ROLE_RANK[threshold]
            assert has_min_role(user, threshold) is expected, (role, threshold)


def test_has_min_role_kann_buero_finanzen_alles_was_buero_auftrag_kann():
    """Die konkrete, wörtlich gestellte Frage: kann buero_finanzen alles, was buero_auftrag
    kann, PLUS mehr? Ja -- erfüllt dieselbe Schwelle UND eine strengere."""
    finanzen = _user(ROLE_OFFICE_FINANZEN)
    assert has_min_role(finanzen, ROLE_OFFICE_AUFTRAG)  # "alles, was buero_auftrag kann"
    assert has_min_role(finanzen, ROLE_OFFICE_FINANZEN)  # "plus mehr" -- die eigene, strengere Schwelle
    auftrag = _user(ROLE_OFFICE_AUFTRAG)
    assert has_min_role(auftrag, ROLE_OFFICE_AUFTRAG)
    assert not has_min_role(auftrag, ROLE_OFFICE_FINANZEN)  # buero_auftrag NICHT umgekehrt


def test_has_min_role_fails_safe_on_none_and_unknown_role():
    """Standardverweigerung gilt auch hier: kein angemeldeter Benutzer und ein nicht mehr
    existierender Rollenwert (z. B. das mit dieser Version abgelöste "office") erfüllen KEINE
    Schwelle -- kein stiller Rückfall auf "irgendwie erlaubt"."""
    assert not has_min_role(None, ROLE_FIELD)  # selbst die niedrigste Schwelle
    legacy = _user("office")
    assert not has_min_role(legacy, ROLE_FIELD)
    assert not has_min_role(legacy, ROLE_OFFICE_AUFTRAG)


# ---------------------------------------------------------------------------
# 3. require_min_role() -- end-to-end über eine echte Route
# ---------------------------------------------------------------------------

def _make_test_app():
    """Mini-FastAPI mit je einer Route pro Mindestrang -- Muster
    test_v260_role_audit.py::test_403_on_a_page_route_renders_access_denied_html_not_json(),
    hier ohne den Seiten-Exception-Handler, da nur der Statuscode selbst geprüft wird."""
    app = FastAPI()

    @app.middleware("http")
    async def _fake_identity(request: Request, call_next):
        role = request.headers.get("x-test-role")
        request.state.erp_user = _user(role) if role else None
        return await call_next(request)

    @app.get("/min-field")
    def min_field(_role: AppUser = Depends(require_min_role(ROLE_FIELD))):
        return {"role": _role.role}

    @app.get("/min-auftrag")
    def min_auftrag(_role: AppUser = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))):
        return {"role": _role.role}

    @app.get("/min-finanzen")
    def min_finanzen(_role: AppUser = Depends(require_min_role(ROLE_OFFICE_FINANZEN))):
        return {"role": _role.role}

    @app.get("/min-admin")
    def min_admin(_role: AppUser = Depends(require_min_role(ROLE_ADMIN))):
        return {"role": _role.role}

    return TestClient(app, raise_server_exceptions=False)


def test_require_min_role_auftrag_lets_both_office_roles_and_admin_through_without_naming_them():
    """Die eigentliche Antwort auf die Betreiberfrage: require_min_role(ROLE_OFFICE_AUFTRAG)
    lässt buero_auftrag, buero_finanzen UND admin durch (200) -- KEINE der beiden letzteren
    wurde in der Dependency-Definition oben einzeln genannt, die Hierarchie leistet das allein.
    field bekommt 403."""
    client = _make_test_app()
    for role, expected_status in (
        (ROLE_ADMIN, 200), (ROLE_OFFICE_FINANZEN, 200), (ROLE_OFFICE_AUFTRAG, 200), (ROLE_FIELD, 403),
    ):
        resp = client.get("/min-auftrag", headers={"x-test-role": role})
        assert resp.status_code == expected_status, (role, resp.text)


def test_require_min_role_finanzen_excludes_buero_auftrag():
    """Die engere Schwelle -- genau das, was Etappe 2 für Kalkulationsgrundlagen/
    Betriebskosten/Mitarbeitervergütung braucht: buero_auftrag bleibt draußen, buero_finanzen
    und admin kommen durch."""
    client = _make_test_app()
    for role, expected_status in (
        (ROLE_ADMIN, 200), (ROLE_OFFICE_FINANZEN, 200), (ROLE_OFFICE_AUFTRAG, 403), (ROLE_FIELD, 403),
    ):
        resp = client.get("/min-finanzen", headers={"x-test-role": role})
        assert resp.status_code == expected_status, (role, resp.text)


def test_require_min_role_field_lets_everyone_through():
    """Der Boden der Kette -- entspricht inhaltlich der bisherigen require_role(ROLE_ADMIN,
    ROLE_OFFICE, ROLE_FIELD)/"_any_role_dep"-Konvention: jede angemeldete Rolle kommt durch,
    nur eine fehlende Anmeldung nicht."""
    client = _make_test_app()
    for role in (ROLE_ADMIN, ROLE_OFFICE_FINANZEN, ROLE_OFFICE_AUFTRAG, ROLE_FIELD):
        resp = client.get("/min-field", headers={"x-test-role": role})
        assert resp.status_code == 200, (role, resp.text)
    resp_anon = client.get("/min-field")
    assert resp_anon.status_code == 403


def test_require_min_role_admin_excludes_every_other_role():
    """Die Spitze der Kette -- deckungsgleich mit require_admin()/require_role(ROLE_ADMIN)."""
    client = _make_test_app()
    for role, expected_status in (
        (ROLE_ADMIN, 200), (ROLE_OFFICE_FINANZEN, 403), (ROLE_OFFICE_AUFTRAG, 403), (ROLE_FIELD, 403),
    ):
        resp = client.get("/min-admin", headers={"x-test-role": role})
        assert resp.status_code == expected_status, (role, resp.text)


def test_require_min_role_rejects_an_unknown_legacy_role_value():
    """Ein Konto mit einem nicht mehr existierenden Rollenwert (z. B. "office", das mit dieser
    Version abgelöste Drei-Rollen-Modell) fällt an JEDER Schwelle durch -- selbst der niedrigsten
    (ROLE_FIELD). Betrifft auf der echten, lokalen Datenbank aktuell 0 Konten (siehe CLAUDE.md
    "Rechtekonzept" -> "Bestandskonten"), ist aber für jede andere Installation die entscheidende
    Sicherheitseigenschaft der Migration: ein liegen gebliebener Altwert öffnet keine Tür, er
    schließt sie."""
    client = _make_test_app()
    resp = client.get("/min-field", headers={"x-test-role": "office"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. has_role() bleibt eine reine Mengenprüfung, unberührt von der Hierarchie
# ---------------------------------------------------------------------------

def test_has_role_stays_flat_and_is_unaffected_by_rank():
    """has_role() kennt keinen Rang -- ROLE_FIELD gehört zur Menge {ROLE_FIELD} genauso wie zur
    Menge {ROLE_ADMIN, ROLE_FIELD}, aber NICHT automatisch zu {ROLE_OFFICE_AUFTRAG}, obwohl
    field rangmäßig darunter liegt (has_min_role würde das umgekehrt gerade verneinen -- beide
    Funktionen beantworten bewusst unterschiedliche Fragen, siehe ihre Docstrings in
    app/permissions.py)."""
    field = _user(ROLE_FIELD)
    assert has_role(field, ROLE_FIELD)
    assert has_role(field, ROLE_ADMIN, ROLE_FIELD)
    assert not has_role(field, ROLE_OFFICE_AUFTRAG)
    admin = _user(ROLE_ADMIN)
    assert not has_role(admin, ROLE_OFFICE_AUFTRAG)  # admin ist NICHT Mitglied dieser Menge,
    # obwohl admin rangmäßig darüber liegt -- has_role() prüft Mitgliedschaft, keinen Rang.
