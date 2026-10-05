"""Version 1.8.58 -- Stufe 2c-2c, Punkt 4 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.58").

Die gemeinsame Zeichenfläche (app/templates/_unterschrift.html) vermisst sich neu, sobald sich ihre angezeigte Größe oder die
Geräteauflösung ändert (Tablet gedreht, Fenster verkleinert, Dialog erst nach dem Aufruf sichtbar), und zeichnet die gemerkten
Striche gleichmäßig skaliert neu. Das Verhalten im Browser prüft der Klicktest scripts/klicktest_zeichenflaeche.py (simulierte
Touch-Eingabe, Drehen); hier der Aufbau, damit eine spätere Änderung ihn nicht still verliert."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAD = (ROOT / "app" / "templates" / "_unterschrift.html").read_text(encoding="utf-8")


def _script() -> str:
    return re.search(r"<script>(.*?)</script>", PAD, flags=re.S).group(1)


def test_pad_remeasures_on_resize_and_rotation():
    js = _script()
    assert "new ResizeObserver(pruefen)" in js and "beobachter.observe(canvas)" in js
    assert "window.addEventListener('resize',pruefen)" in js  # Zoom ändert die Geräteauflösung
    assert "requestAnimationFrame" in js  # gebündelt, einmal je Bild
    assert re.search(r"function vermessen\(\)\{.*canvas\.width=w;canvas\.height=h", js, flags=re.S)
    assert "if(!r.width||!r.height)return false" in js  # unsichtbar (geschlossener Dialog): später


def test_strokes_are_kept_and_redrawn_uniformly():
    js = _script()
    assert "striche.push(aktuell)" in js and "function neuZeichnen()" in js
    assert "Math.min(breite/basis.w,hoehe/basis.h)" in js  # gleichmäßig -- nie verzerrt
    assert "ctx.lineWidth=STRICH/s" in js  # Strichstärke am Bildschirm gleich
    # Position in Punkten der Basisgröße -- ein Strich nach dem Drehen liegt unter dem Finger
    assert "return {x:(e.clientX-r.left)/s,y:(e.clientY-r.top)/s}" in js


def test_detached_or_reused_canvas_unsubscribes():
    js = _script()
    assert "if(!canvas.isConnected){abmelden();return}" in js
    assert "if(canvas._dkAbmelden)canvas._dkAbmelden()" in js
    assert "window.removeEventListener('resize',pruefen)" in js and "beobachter.disconnect()" in js


def test_interface_of_the_pad_is_unchanged_for_the_three_pages():
    js = _script()
    for name in ("leer:", "leeren:", "alsBlob:", "alsDataUrl:"):
        assert name in js
    for page, call in (("checklist.html", "unterschriftsfeld(canvas)"), ("service_reports.html", "unterschriftsfeld("),
                       ("order.html", "unterschriftsfeld(")):
        assert call in (ROOT / "app" / "templates" / page).read_text(encoding="utf-8"), page
