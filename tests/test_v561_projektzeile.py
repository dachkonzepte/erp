"""Version 1.9.141 (Stufe 5, R4, Punkt 4) -- Projektzeile der Kundenakte: das Kennzeichen der Phase bricht nicht um.

Name und Kennzeichen stehen in einer Zeile, die nicht umbricht; ein langer Name endet mit „…“, der volle Name steht im title (maskiert, Regel 32). Gemessen im Browser
in klicktest_kundenakte (Übersicht und Reiter Projekte, 1440 und 412 px)."""

from sqlalchemy.orm import Session  # noqa: F401  (Typ der Fixture)

from app.models import Project
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v314_dashboard_month_berlin import TEMPLATES
from tests.test_v555_kundenakte_zahlen import welt  # noqa: F401  (Fixture)
from tests.test_v557_kundenakte_seite import ZEICHNEN, _lauf, akte_welt  # noqa: F401  (Fixture)

LANG = 'Dachsanierung "Am Wasserturm" <b>4</b> mit Erneuerung der gesamten Dachentwässerung und aller Anschlüsse'


def _regel(selektor: str) -> str:
    text = (TEMPLATES / "customer.html").read_text(encoding="utf-8")
    i = text.index(selektor + "{")
    return text[i: text.index("}", i)]


def test_die_zeile_bricht_nicht_um():
    kopf = _regel(".projekt-kopf")
    assert "flex-wrap:nowrap" in kopf and "min-width:0" in kopf
    assert "flex:none" in _regel(".projekt-kopf .chip")  # das Kennzeichen wird nie schmaler
    name = _regel(".projekt-name")
    assert all(t in name for t in ("min-width:0", "white-space:nowrap", "overflow:hidden", "text-overflow:ellipsis"))


@nur_mit_node
def test_langer_name_steht_im_title_und_maskiert(akte_welt):  # noqa: F811
    db = akte_welt["db"]
    projekt = db.get(Project, akte_welt["a"].id)
    projekt.name = LANG
    db.commit()
    html = _lauf(akte_welt, ZEICHNEN)["ergebnis"]["projekte"]
    roh = LANG.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    voll = f"{projekt.project_number} · {roh}"
    assert f'class="projekt-name" href="/projects/{projekt.id}" title="{voll}">{voll}</a>' in html
    assert "<b>4</b>" not in html


@nur_mit_node
def test_jede_projektzeile_traegt_ihren_namen_als_title(akte_welt):  # noqa: F811
    html = _lauf(akte_welt, ZEICHNEN)["ergebnis"]["projekte"]
    assert html.count('class="projekt-name"') == html.count("data-projekt=") >= 1
    assert html.count('title="') >= html.count('class="projekt-name"')
