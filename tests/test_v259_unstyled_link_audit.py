"""Version 1.3.50 -- Nebenbefund aus 1.3.49 behoben: der damals entfernte "Mein Konto"-Link in
_sidebar.html hatte keine eigene CSS-Regel und wäre als blau unterstrichener Browser-
Standardlink erschienen, nicht im Design-System. Auf Nachfrage projektweit nach demselben
Muster gesucht (ein <a> ohne eigene Farb-/Unterstreichungsregel -- weder über eine allgemeine
a{...}-Regel im datei-eigenen <style> noch über eine spezifische, tatsächlich definierte
Klasse) -- vier weitere, unabhängige Funde:

- app/templates/account.html -- "Bitte zuerst <a href="/login">anmelden</a>." im
  "nicht angemeldet"-Hinweis.
- app/templates/settings.html -- "<a href="/master-data#employees">Stammdaten -> Mitarbeiter
  </a>" im Kalkulationsgrundlagen-Hinweistext.
- app/templates/service_reports.html -- der PDF-Öffnen-Link in historyCard()
  (Wartungshistorie-Panel) -- eine zweite, unabhängige Kopie desselben Features, die (anders
  als die bereits über .report-actions a{...} gestylte erste Kopie) unstyled blieb.
  Nachgemessen, dass historyCard() tatsächlich der einzige betroffene Aufrufer ist:
  card()/loadReports() nutzt weiterhin die bereits gestylte .report-actions.
- app/templates/work_preparation.html -- der Datei-Öffnen-Link in renderDelivery()
  (Lieferscheine-Tabelle) -- eine zweite, unabhängige Kopie desselben Features wie
  deliveryTags() (dort über .delivery-tag a{...} korrekt gestylt), hier ohne die
  umschließende Klasse.

Alle vier folgen demselben Muster: ein per JS-Template-String zusammengesetzter <a>, bei dem
die passende CSS-Klasse beim Bauen vergessen wurde. Behoben nach dem in login.html bereits
etablierten, einfachsten Muster -- eine allgemeine a{color:var(--accent)} Regel je Datei
(jeweils per Grep bestätigt: der einzige unstyled <a> in der jeweiligen Datei, sämtliche
bereits spezifischer gestylten Links -- .back, .report-actions a, .top-actions a,
.delivery-tag a -- bleiben davon durch höhere CSS-Spezifität unberührt) -- keine
HTML-Umstrukturierung, kein Layoutrisiko."""

from pathlib import Path

TEMPLATES = Path(__file__).parents[1] / "app" / "templates"


def _style_block(html):
    return html[html.index("<style>"):html.index("</style>")]


def test_account_html_has_a_general_link_color_rule():
    html = (TEMPLATES / "account.html").read_text(encoding="utf-8")
    assert "a{color:var(--accent)}" in _style_block(html)
    assert '<a href="/login">anmelden</a>' in html  # der ursprünglich gemeldete Link bleibt


def test_settings_html_has_a_general_link_color_rule():
    html = (TEMPLATES / "settings.html").read_text(encoding="utf-8")
    assert "a{color:var(--accent)}" in _style_block(html)
    assert '<a href="/master-data#employees">Stammdaten → Mitarbeiter</a>' in html


def test_service_reports_html_has_a_general_link_color_rule():
    html = (TEMPLATES / "service_reports.html").read_text(encoding="utf-8")
    assert "a{color:var(--accent)}" in _style_block(html)
    history_start = html.index("function historyCard(")
    history_end = html.index("\n}", history_start)
    assert 'href="/api/service-reports/${r.id}/pdf"' in html[history_start:history_end]


def test_work_preparation_html_has_a_general_link_color_rule():
    html = (TEMPLATES / "work_preparation.html").read_text(encoding="utf-8")
    assert "a{color:var(--accent)}" in _style_block(html)
    delivery_start = html.index("function renderDelivery(")
    delivery_end = html.index("\n", delivery_start)
    assert 'href="/api/project-documents/${x.project_document_id}/view"' in html[delivery_start:delivery_end]


def test_more_specific_link_styles_are_still_present_and_unaffected():
    """Die allgemeine a{}-Regel ist die am wenigsten spezifische -- diese bereits bestehenden,
    spezifischeren Regeln müssen unverändert erhalten bleiben (sie gewinnen weiterhin gegen
    die neue Fallback-Regel, unabhängig von der Reihenfolge im Stylesheet)."""
    account_html = (TEMPLATES / "account.html").read_text(encoding="utf-8")
    assert ".back{color:var(--accent);text-decoration:none" in account_html

    service_reports_html = (TEMPLATES / "service_reports.html").read_text(encoding="utf-8")
    assert ".report-actions a{" in service_reports_html

    work_preparation_html = (TEMPLATES / "work_preparation.html").read_text(encoding="utf-8")
    assert ".top-actions a{" in work_preparation_html
    assert ".delivery-tag a{" in work_preparation_html
