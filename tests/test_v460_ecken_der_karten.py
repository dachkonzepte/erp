"""Seit 1.9.30 (Nachtrag Stufe 2, Punkt A1): Karten auf allen Seiten mit 12 px Ecken, im Monteursrahmen 16 px (Entscheidung 2 der Stufe 2,
ersetzt Festlegung 1.9.27 Nr. 4 „Karten bleiben eckig“).

    Karte          eine Regel einer Vorlage, deren Ziel genau eine Karten-Klasse ist -- Name mit „card“ oder „karte“, oder eine der Flächen
                   gleicher Art ohne diesen Namen (KARTEN_OHNE_NAMEN: Kopf- und Formularkarten, Kennzahl-Kacheln, Spalten, Einträge und
                   Kästen in Karten, Hinweiskästen, Ablageflächen, Dialoge, Aufklappflächen) -- oder das Element dialog, und die eine Fläche
                   zeichnet: umlaufender Rand oder ein Grund. Ausgenommen sind Zustände (:hover …) und Teile einer Karte (.card h2).
    keine Karte    Knöpfe und Felder (eigene Ecke, nicht Teil dieses Punkts), Kennzeichen, Raster und Tafelteile, Vorschaubilder
                   (NICHT_KARTEN) -- jede umrandete Fläche einer Vorlage steht in einer der beiden Listen (oder heißt nach einer Karte)
    Ecke           jede Karte trägt border-radius: var(--ds-ecke-karte) (12 px) -- nie einen festen Wert, nie die Tablet-Ecke selbst; ein
                   Kasten, der unten an eine Karte anschließt (border-top:none), nur unten: 0 0 var(--ds-ecke-karte) var(--ds-ecke-karte)
    Monteursrahmen _mobile_header.html (steht genau in den Seiten des Monteursrahmens) setzt --ds-ecke-karte auf --ds-ecke-tablet-karte
                   (16 px); sonst setzt keine Vorlage einen --ds-Wert
    Anschluss      bis 1.9.44 hingen in /mobil der Hinweis „Offene Bedenken“ und der Link „Checklisten zu diesem Auftrag“ unter ihrer
                   Einsatzkarte (darüber unten eckig); seit 1.9.45 („Heute“) stehen sie in der Karte, nichts hängt mehr an

Im Browser misst das scripts/klicktest_rahmen.py, Teil „ecken“ (Büro 12 px, Monteursrahmen 16 px, hell und dunkel).
"""

import re

from tests import vorlagen_js as vj

KARTEN_OHNE_NAMEN = {
    # Karten einer Seite
    "wrap": "Formularseiten: die Karte um das Formular",
    "hero": "Kopfkarte (Changelog, Projektmappe, Arbeitsvorbereitung)",
    "top": "Kopfkarte von Auftrag und Rechnung",
    "side": "Untermenü der Stammdaten",
    "settings-sidebar": "Untermenü der Einstellungen",
    "metric": "Kennzahl-Kachel",
    "toolbar": "Werkzeugleiste als Karte",
    "column": "Spalte einer Tafel (Aufgaben, Anfragen)",
    "kanban-col": "Spalte der Projekt-Tafel",
    "day-col": "Tag im Wochenkalender (8 px Abstand)",
    "timer": "Karte der laufenden Zeit (Zeiterfassung Büro)",
    # Einträge und Kästen in einer Karte
    "lead": "Eintrag der Anfragen-Tafel",
    "entry": "Eintrag (Changelog, Zeiterfassung)",
    "entry-row": "Eintrag des Stundenzettels",
    "event-row": "Termin im Kalender",
    "q": "Frage der Checkliste",
    "pdef": "Mangel im Feld „Mängel“ der Checkliste",
    "doc": "Dokumentkachel",
    "section": "Abschnitt des Angebots",
    "info-block": "Kasten in der Übersicht der Projektmappe",
    "cl-row": "Checkliste in der Liste je Auftrag oder Objekt",
    "cl-focus": "hervorgehobene Checkliste",
    "crew-member": "Mitglied der Kolonne (Zeiterfassung der Monteure)",
    "request-row": "Abwesenheitsantrag",
    "rule-row": "Regel einer Checklisten-Vorlage",
    "frow": "Feld einer Checklisten-Vorlage",
    "setting-row": "Einstellung im Backoffice",
    "sequence": "Nummernkreis in den Einstellungen",
    "worklist-row": "Eintrag der Arbeitsliste des Adressimports",
    "extra": "Zusatzfeld im Stammdaten-Formular",
    "extra-row": "Zusatzfeld in der Kundenakte",
    "bulkbar": "Leiste für mehrere Positionen (Arbeitsvorbereitung)",
    "editor": "Bearbeiten-Kasten der Anfragen",
    "member-list": "Liste der Mitglieder (Zeiterfassung Büro)",
    "dh-form": "Formular im Versandverlauf",
    "finding-form": "Formular „Mangel“ im Einsatzbericht",
    "sign-box": "Kasten zur Unterschrift am Auftrag",
    "notice-to": "Empfänger einer Anzeige in der Checkliste",
    "preview": "Vorschau eines Werts in den Einstellungen",
    "formula": "Rechenweg (Einstellungen, Plantafel)",
    "recovery-codes": "Wiederherstellungscodes im Konto",
    # Hinweiskästen
    "warning-box": "Hinweis (Konto)",
    "danger-box": "Warnung (Konto)",
    "source-box": "Hinweis zur Quelle (Leistungskatalog)",
    "calc-box": "Rechenkasten (Leistungskatalog)",
    "concern-alert": "Hinweis „Offene Bedenken“",
    "office-hint": "Hinweis fürs Büro (Einsatzbericht)",
    "group-note": "Hinweis zur Gruppe (Zeiterfassung Büro)",
    "warn": "Warnung (Backoffice, Arbeitsvorbereitung)",
    "ok": "Erfolg (Backoffice)",
    "warning": "Warnung (Plantafel)",
    "suggestion": "Vorschlag (Plantafel)",
    "linked": "verknüpft (Anfragen)",
    "lost": "verloren (Anfragen)",
    # Ablage-, Leer- und Aufklappflächen
    "upload": "Ablagefläche zum Hochladen",
    "drop": "Ablagefläche (Arbeitsvorbereitung)",
    "empty": "leere Liste",
    "placeholder": "Platzhalter der Projekt-Tafel",
    "unassigned": "Positionen ohne Titel (Angebot)",
    "pm-results": "Trefferliste (Projektmappe)",
    "suggest-box": "Vorschläge (Kalender)",
    "modal": "Dialog",
    "menu": "Aufklappmenü",
}
NICHT_KARTEN = {
    **{k: "Knopf oder Feld -- eigene Ecke, nicht Teil dieses Punkts" for k in (
        "add", "btn", "btnlink", "cat", "danger", "dh-btn", "filter", "ghost", "iconbtn", "menu-btn", "more-btn", "p-role", "perform-btn",
        "secondary", "tile", "view-toggle", "checklist-link",
        "knopf-neutral", "knopf-gesperrt")},  # seit 1.9.45 die Knöpfe von „Heute“ (/mobil)
    **{k: "Kennzeichen" for k in (
        "addendum-badge", "badge", "cl-badge", "count", "def-badge", "delivery-tag", "dot", "entry-version", "pill", "psum-tag",
        "status-pill")},
    **{k: "Raster oder Tafelteil (Linien zwischen den Zellen, Plantafel, Zeitstrahl, Kopf der Positionen)" for k in (
        "month-grid", "rate-result", "timeline", "lv-columns", "slot")},
    **{k: "Skizze der Dachfläche" for k in ("sketch-wrap", "sketch-rect", "sketch-rect-preview", "sketch-marker", "sketch-marker-label")},
    "marke-kachel": "Kachel der Bildmarke -- eigene Ecke wie in Leiste und Monteurskopf (_marke.html)",
    **{k: "Vorschau eines Bilds (Foto, Unterschrift)" for k in ("thumb", "sig")},
}
ECKE = "var(--ds-ecke-karte)"
ECKE_UNTEN = "0 0 var(--ds-ecke-karte) var(--ds-ecke-karte)"
RAND = re.compile(r"(?<![-\w])border\s*:\s*(?!none|0\b)[^;]+")


def _regeln(css: str):
    """(Selektorliste, Rumpf) jeder Regel, Kommentare entfernt, @media-Köpfe übersprungen (ihre Regeln zählen mit)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@media[^{]*\{", "", css)
    return [(" ".join(s.split()), r) for s, r in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _ziele(sel: str) -> list[str]:
    return [re.split(r"\s*[\s>+~]\s*", s.strip())[-1] for s in sel.split(",")]


def ist_karte(ziel: str) -> bool:
    """Ziel = letzter Teil eines Selektors. Karte: genau eine Klasse ohne Zustand, deren Name „card“/„karte“ enthält oder in
    KARTEN_OHNE_NAMEN steht -- oder das Element dialog."""
    if ziel == "dialog":
        return True
    m = re.fullmatch(r"\.([A-Za-z0-9_-]+)", ziel)
    return bool(m) and ("card" in m[1] or "karte" in m[1] or m[1] in KARTEN_OHNE_NAMEN)


def zeichnet_flaeche(rumpf: str) -> bool:
    grund = re.search(r"(?<![-\w])background(?:-color)?\s*:\s*(?!none|transparent)[^;]+", rumpf)
    return bool(RAND.search(rumpf) or grund)


def soll_ecke(rumpf: str) -> str:
    """Die Ecke, die eine Karte tragen muss: unten angeschlossen (border-top:none) nur unten, sonst ringsum."""
    return ECKE_UNTEN if re.search(r"border-top\s*:\s*none", rumpf) else ECKE


def karten_regeln(css: str):
    """Jede Regel, die eine Karte zeichnet: (Selektorliste, Ecke oder None, Soll-Ecke)."""
    funde = []
    for sel, rumpf in _regeln(css):
        if any(ist_karte(z) for z in _ziele(sel)) and zeichnet_flaeche(rumpf):
            ecke = re.search(r"border-radius\s*:\s*([^;]+)", rumpf)
            funde.append((sel, ecke[1].strip() if ecke else None, soll_ecke(rumpf)))
    return funde


def _stil(name: str) -> str:
    return "\n".join(re.findall(r"<style>(.*?)</style>", (vj.TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


def test_jede_karte_hat_die_ecke_der_karte():
    falsch = [f"{name}: {sel} -> {ecke} (soll {soll})" for name in vj.alle_vorlagen()
              for sel, ecke, soll in karten_regeln(_stil(name)) if ecke != soll]
    assert falsch == []


def test_jede_umrandete_flaeche_ist_eingeordnet():
    """Eine umrandete Fläche mit genau einer Klasse als Ziel ist Karte oder steht mit Grund in NICHT_KARTEN -- eine neue kommt in eine der
    Listen (sonst bliebe sie still eckig)."""
    offen, beide = set(), set()
    for name in vj.alle_vorlagen():
        for sel, rumpf in _regeln(_stil(name)):
            if not RAND.search(rumpf):
                continue
            for ziel in _ziele(sel):
                m = re.fullmatch(r"\.([A-Za-z0-9_-]+)", ziel)
                if not m or m[1].startswith(("app-", "mobile-", "ds-")):
                    continue  # Leiste, Kopfzeile, Monteurskopf und Design-System haben eigene Maße
                if ist_karte(ziel) and m[1] in NICHT_KARTEN:
                    beide.add(m[1])
                elif not ist_karte(ziel) and m[1] not in NICHT_KARTEN:
                    offen.add(f"{name}: .{m[1]}")
    assert sorted(offen) == [] and sorted(beide) == []


def test_karten_auf_allen_seiten():
    """Jede Seite mit Karten zeichnet sie mit Ecke -- die 44 Seiten mit .card, dazu u. a. Start (Widgets) und Aufgaben."""
    mit = {name for name in vj.seiten() if karten_regeln(_stil(name))}
    assert len(mit) >= 48, sorted(set(vj.seiten()) - mit)
    assert {"dashboard.html", "tasks.html", "mobil.html", "master_data_form.html", "service_form.html"} <= mit


def test_monteursrahmen_setzt_die_ecke_auf_16_px():
    text = (vj.TEMPLATES / "_mobile_header.html").read_text(encoding="utf-8")
    bloecke = re.findall(r"<style>(.*?)</style>", text, flags=re.S)
    assert ":root{--ds-ecke-karte:var(--ds-ecke-tablet-karte)}" in [re.sub(r"/\*.*?\*/|\s", "", b, flags=re.S) for b in bloecke]


def test_sonst_setzt_keine_vorlage_einen_ds_wert():
    funde = []
    for name in vj.alle_vorlagen():
        for sel, rumpf in _regeln(_stil(name)):
            for prop in re.findall(r"(--ds-[a-z0-9-]+)\s*:", rumpf):
                if (name, sel, prop) != ("_mobile_header.html", ":root", "--ds-ecke-karte"):
                    funde.append(f"{name}: {sel} {prop}")
    assert funde == []


def test_tablet_ecke_der_karte_nur_ueber_den_monteursrahmen():
    """Keine Seite nimmt --ds-ecke-tablet-karte selbst -- die 16 px kommen aus dem Rahmen (sonst stimmte die Ecke für das Büro nicht)."""
    funde = [name for name in vj.alle_vorlagen() if name != "_mobile_header.html" and "--ds-ecke-tablet-karte" in _stil(name)]
    assert funde == []


def test_kaesten_unter_der_einsatzkarte_schliessen_an():
    """Seit 1.9.45 („Heute“): der Hinweis „Offene Bedenken“ steht in der Einsatzkarte, mit eigener Ecke; kein Kasten hängt mehr unten an
    einer Karte (bis 1.9.44: Hinweis und „Checklisten zu diesem Auftrag“ unter der Karte, die darüber unten eckig)."""
    stil = re.sub(r"\s", "", _stil("mobil.html"))
    assert ":has(+" not in stil and "border-top:none" not in stil and ".checklist-link" not in stil
    rumpf = re.search(r"\.concern-alert\{([^}]*)\}", stil)[1]
    assert "border-radius:var(--ds-ecke-karte)" in rumpf


def test_waechter_findet_und_laesst_durch():
    assert karten_regeln(".card{background:var(--card);border:1px solid var(--line)}") == [(".card", None, ECKE)]
    assert karten_regeln(".editor-card{border:1px solid red;border-radius:0}") == [(".editor-card", "0", ECKE)]
    assert karten_regeln("dialog{background:#fff}") == [("dialog", None, ECKE)]
    assert karten_regeln("@media (max-width:800px){.metric{background:var(--soft)}}") == [(".metric", None, ECKE)]
    assert karten_regeln(".concern-alert{border:2px solid red;border-top:none}") == [(".concern-alert", None, ECKE_UNTEN)]
    for nicht in (".card h2{background:red}", ".card:hover{background:red}", ".kanban-card.dragging{background:red}",
                  ".secondary{border:1px solid red}", ".wrap{overflow:auto;max-height:70vh}", ".lock-card{border-left:3px solid red}",
                  ".toolbar{display:flex}", "input{border:1px solid red}"):
        assert karten_regeln(nicht) == [], nicht
