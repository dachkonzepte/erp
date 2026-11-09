"""Version 1.9.275 (Nachrunde R5b, Punkt 4; Nebenbefund 1.9.271): Stammdaten bei 412 px ohne Überlauf, die Mitarbeitertabelle bei 1440 px ohne Rollen.

    412 px     unter 850 px ist die Spalte des Rasters minmax(0,1fr) statt 1fr -- eine Tabelle rollt in ihrem Rahmen, statt die Seite zu verbreitern
    Spalten    Mitarbeiter (Nr. und Geburtstag darunter) · Funktion (Gruppe und Stunden je Woche darunter) · Kontakt · Vergütung (ab Büro – Finanzen) ·
               Kosten-Zuordnung · Kennzeichen (Sachbearbeiter, Plantafel bzw. Bauleitung, sonst „—“) · Status · Bearbeiten -- elf Spalten wurden acht
    Umbruch    die E-Mail-Adresse bricht bevorzugt vor dem „@“ (<wbr>), wenn nötig mitten im Wort; Funktion und Kosten-Zuordnung trennen nach Silben;
               Namen, Telefonnummern, Kennzeichen, Status und „Bearbeiten“ nie -- unter 850 px (die Tabelle rollt ohnehin) beides nicht
Der Klicktest scripts/klicktest_stammdaten_breite.py misst im Browser: 412 px in allen neun Ansichten, 1440 px für Admin und Büro – Finanzen hell und
dunkel (auch ohne Silbentrennung), 1280 px mit Silbentrennung.
"""

import re

from tests.test_v671_inaktive_mitarbeiter_ausblenden import _mitarbeiter_zweig, _text


def _css() -> str:
    text = _text()
    return text[text.index("<style>"):text.index("</style>")]


def _unter(px: int) -> str:
    css = _css()
    start = css.index(f"@media(max-width:{px}px){{")
    return css[start:css.index("}}", start) + 2]


def _schmal() -> str:
    return _unter(850)


def test_raster_unter_850_px_rollt_im_rahmen():
    # seit 1.9.278 steht das Raster mit dem Untermenü oben schon unter 1400 px (bis 1.9.277 in der Regel für 850 px)
    assert ".layout{grid-template-columns:minmax(0,1fr)}" in _unter(1400)
    assert not re.search(r"grid-template-columns:\s*1fr", _css())  # 1fr nimmt die Mindestbreite der Tabelle an -- die Seite liefe über


def test_acht_spalten():
    zweig = _mitarbeiter_zweig()
    assert ("let headers=['Mitarbeiter','Funktion','Kontakt',...(canManageEmployees?['Vergütung']:[]),'Kosten-Zuordnung','Kennzeichen','Status',''];"
            in zweig)
    assert "'Nr.'" not in zweig and "'Std./Woche'" not in zweig and "'Sachbearbeiter','Planung'" not in zweig


def test_nummer_und_geburtstag_unter_dem_namen():
    zweig = _mitarbeiter_zweig()
    assert "<td>${esc(x.employee_number||'—')}</td>" not in zweig
    name = zweig[zweig.index("<td><b>${esc(x.first_name)} ${esc(x.last_name)}</b>"):]
    name = name[:name.index("</td>")]
    assert "Nr. ${esc(x.employee_number)}" in name and "Geb. ${new Date(x.birthday+'T00:00:00').toLocaleDateString('de-DE')}" in name
    assert "${x.employee_number&&x.birthday?' · ':''}" in name  # der Punkt nur zwischen beiden


def test_stunden_unter_der_funktion():
    zweig = _mitarbeiter_zweig()
    assert "<td class=\"number\">${Number(x.weekly_hours)" not in zweig
    assert ("<td class=\"trennbar\">${esc(x.function_name||x.job_title||'—')}<div class=\"muted small\">${x.employee_group==='gewerblich'?"
            "'Gewerblich':'Kaufmännisch'} · ${Number(x.weekly_hours).toLocaleString('de-DE')} h/Woche</div></td>") in zweig


def test_kennzeichen_in_einer_spalte():
    zweig = _mitarbeiter_zweig()
    zelle = zweig[zweig.index('<td class="kennzeichen">'):]
    zelle = zelle[:zelle.index("</td>")]
    assert "<span class=\"pill\">Sachbearbeiter</span> " in zelle  # mit Leerzeichen dahinter: vorgelesen und kopiert zwei Wörter
    assert "x.plantafel==='bauleitung'?'<span class=\"pill\">Bauleitung</span>':x.plantafel==='nicht_zeigen'?'':'<span class=\"pill\">Plantafel</span>'" in zelle
    assert "${!x.available_as_caseworker&&x.plantafel==='nicht_zeigen'?'—':''}" in zelle


def test_umbruch_nur_email_und_silben():
    css, schmal, zweig = _css(), _schmal(), _mitarbeiter_zweig()
    assert "td.kontakt .mail{overflow-wrap:anywhere}" in css and "td.trennbar{hyphens:auto}" in css
    assert "td.kontakt .mail{overflow-wrap:normal}" in schmal and "td.trennbar{hyphens:manual}" in schmal
    assert "<span class=\"mail\">${esc(x.email.split('@')[0])}${x.email.includes('@')?`<wbr>@${esc(x.email.split('@').slice(1).join('@'))}`:''}</span>" in zweig
    assert zweig.count('class="trennbar"') == 2  # Funktion und Kosten-Zuordnung -- nicht Name, Kennzeichen, Status, Bearbeiten
    # die Telefonnummer außerhalb von .mail: bricht nie mitten in der Zahl -- seit 1.9.278 in .tel, auch nicht an Leerzeichen
    assert "${x.mobile||x.phone?`<span class=\"tel\">${esc(x.mobile||x.phone)}</span>`:''}" in zweig


def test_nur_die_mitarbeitertabelle_hat_die_klasse():
    text = _text()
    assert "function table(headers,rows,mitarbeiter=false){return `<div class=\"wrap\"><table${mitarbeiter?' class=\"mitarbeiter\"':''}>" in text
    assert text.count("table(headers,rows,true)") == 1 and "`+table(headers,rows,true)}" in _mitarbeiter_zweig()
    assert "table.mitarbeiter th,table.mitarbeiter td{padding-left:8px;padding-right:8px}" in _css()
