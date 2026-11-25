"""Version 1.11.19 (Antwort 1.11.17-F1, Ort auf Rückfrage am 25.11.2026): unter dem Text jeder Mailvorlage steht, dass das ERP beim Senden Name,
Anschrift und Pflichtangaben darunter setzt (seit 1.11.17, app/email_dispatch.py). Ein Textfeld vor dem Versand gibt es nicht -- an den Versandstellen
stehen nur „An“ und „CC“, der Text kommt aus der Vorlage.

    Vorlagen    Einstellungen → E-Mail-Vorlagen: direkt unter dem Feld „Text“ (jede Art der Auswahl, auch die Mahnstufen)
    Mahnstufen  Einstellungen → Mahnwesen: direkt unter „E-Mail-Text“ jeder Stufe
    Immer       für jede Rolle der Seite und ohne Firmendaten (der Satz sagt, woher die Angaben kommen) -- sichtbar und an der Stelle prüft
                scripts/klicktest_mail_schluss.py, auch bei gesperrtem Feld
    Gilt        jede Art der Auswahl ist eine Mail an Kunden: keine fällt unter OHNE_FIRMENANGABEN
    Nur dort    der Satz steht in keiner anderen Vorlage (nicht an den Versandstellen)
"""

import re

import pytest

from app.document_email_templates import DOCUMENT_TYPES
from app.email_dispatch import DISPATCH_TYPES, OHNE_FIRMENANGABEN
from app.routers.pages import router as pages_router
from tests.vorlagen_js import TEMPLATES, alle_vorlagen

SATZ = "Darunter setzt das ERP beim Senden Name, Anschrift und Pflichtangaben aus den Firmendaten."
HINWEIS = f'<div class="small muted" data-mail-schluss style="margin-top:4px">{SATZ}</div>'


def _seite(db, router_test_client, rolle="admin"):
    antwort = router_test_client(db, pages_router, role=rolle).get("/settings")
    assert antwort.status_code == 200
    return antwort.text


@pytest.mark.parametrize("rolle", ["admin", "buero_finanzen", "buero_auftrag"])
def test_satz_direkt_unter_dem_text_der_vorlagen(threaded_db_session, router_test_client, rolle):
    html = _seite(threaded_db_session, router_test_client, rolle)
    assert re.search(r'<textarea id="emailTemplateBody"[^>]*></textarea>\s*' + re.escape(HINWEIS) + r"\s*</div>", html), "Satz unter „Text“ fehlt"


@pytest.mark.parametrize("rolle", ["admin", "buero_auftrag"])
def test_satz_direkt_unter_dem_e_mail_text_jeder_mahnstufe(threaded_db_session, router_test_client, rolle):
    html = _seite(threaded_db_session, router_test_client, rolle)
    assert re.search(r'<textarea id="rl\$\{x\.id\}EmailBody"[^>]*>\$\{esc\(x\.email_body_template\|\|\'\'\)\}</textarea>' + re.escape(HINWEIS) + "</div>", html), \
        "Satz unter „E-Mail-Text“ der Mahnstufe fehlt"


def test_satz_ohne_firmendaten(threaded_db_session, router_test_client):
    """Ohne Firmendaten setzt das ERP nichts darunter -- der Satz steht trotzdem („aus den Firmendaten“)."""
    from app.firmenangaben import zeilen
    from app.settings import load_general_settings

    s = load_general_settings(threaded_db_session)
    for feld in ('company_name', 'street', 'postal_code', 'city', 'register_court', 'register_number', 'managing_director'):
        setattr(s, feld, "")
    threaded_db_session.commit()
    assert zeilen(threaded_db_session) == []
    assert _seite(threaded_db_session, router_test_client).count(HINWEIS) == 2


def test_jede_art_der_auswahl_ist_eine_mail_an_kunden(threaded_db_session, router_test_client):
    html = _seite(threaded_db_session, router_test_client)
    auswahl = re.search(r'<select id="emailTemplateType"[^>]*>(.*?)</select>', html, re.S).group(1)
    arten = set(re.findall(r'<option value="([^"]+)"', auswahl))
    assert arten == DOCUMENT_TYPES  # dazu die Mahnstufen („reminder:n“, aus dem Skript)
    assert not (arten | {"mahnung"}) & OHNE_FIRMENANGABEN
    assert "mahnung" in DISPATCH_TYPES


def test_satz_nur_unter_den_vorlagen():
    funde = {name: (TEMPLATES / name).read_text(encoding="utf-8").count(SATZ) for name in alle_vorlagen()}
    assert {n: z for n, z in funde.items() if z} == {"settings.html": 2}
