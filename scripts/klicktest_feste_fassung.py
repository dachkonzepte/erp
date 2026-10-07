"""Klicktest: feste Fassung einer Checkliste (1.8.66, Stufe 2c-2e, Punkt 1).

Befüllt wie scripts/klicktest_abnahmeprotokoll.py (Hallenbau GmbH, Abnahmeprotokoll aus der Startvorlage), dazu ein Protokoll mit
drei Fassungen: Unterschrift des Auftraggebers (Fassung 1), des Auftragnehmers (Fassung 2), die Unterschrift des Auftragnehmers
verworfen und neu geleistet (Fassung 3). Außerdem eine eigene Checkliste der Monteurin, unterschrieben.

    Büro (1400 px, dunkel)  Karte "Feste Fassungen": drei Fassungen, neueste oben; Fassung 2 "überholt" mit der verworfenen
                            Unterschrift, 1 und 3 "gilt"; "PDF" liefert ein PDF; "Prüfen" -> "Datei unverändert".
    Büro (412 px, hell)     Karte ohne waagrechten Scrollbalken.
    Monteurin               an der eigenen Checkliste keine Karte, die Liste der Fassungen 403.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_feste_fassung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00 (die Monteurin öffnet ihre Checkliste).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_abnahme_aus_protokoll import _unterschrift_png  # noqa: E402
from klicktest_abnahmeprotokoll import befuellen as befuellen_basis  # noqa: E402

A = "abnahme."


def befuellen(db, k):
    from sqlalchemy import select

    from app import checklists as cl
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.models import AppUser

    seed = befuellen_basis(db, k)
    olga = db.scalar(select(AppUser).where(AppUser.username == "olga"))
    mia = db.scalar(select(AppUser).where(AppUser.username == "mia"))
    c = cl.create_checklist(db, template_id=seed["vorlage"], context_type="auftrag", order_id=seed["auftrag"])
    f = {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}
    for key, wert in (("teilnehmer", "Herbert Halle, Olga Office"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                      ("vorbehalt_maengel", "nein"), ("vorbehalt_vertragsstrafe", "nein")):
        cl.save_answer(db, c["id"], f[key], wert)
    cl.add_attachment(db, c["id"], f["unterschrift_auftraggeber"], _unterschrift_png(), signer_person="Herbert Halle",
                      account_user_id=olga.id, account_name="Olga Office")
    an = cl.add_attachment(db, c["id"], f["unterschrift_auftragnehmer"], _unterschrift_png(), account_user_id=olga.id,
                           account_name="Olga Office")
    sig = next(a["id"] for a in an["attachments"] if a["field_id"] == f["unterschrift_auftragnehmer"])
    cl.discard_signatures(db, c["id"], signature_id=sig, reason="falsches Konto", user_id=olga.id, by_name="Olga Office")
    cl.add_attachment(db, c["id"], f["unterschrift_auftragnehmer"], _unterschrift_png(), account_user_id=olga.id,
                      account_name="Olga Office")

    t = create_template(db, label="Sicherheitscheck (Klicktest)", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "ja_nein", "label": "Freigegeben", "field_key": "frei",
                                          "required": True})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Monteur", "field_key": "sig"})
    tpl = publish_draft(db, t["id"])
    eigene = cl.create_checklist(db, template_id=tpl["id"], context_type="auftrag", order_id=seed["auftrag"],
                                 created_by_employee_id=mia.employee_id, created_by_user_id=mia.id)
    g = {x["field_key"]: x["id"] for x in eigene["fields"]}
    cl.save_answer(db, eigene["id"], g["frei"], "ja")
    cl.add_attachment(db, eigene["id"], g["sig"], _unterschrift_png(), signer_name="Mia Monteurin",
                      created_by_employee_id=mia.employee_id, account_user_id=mia.id, account_name="Mia Monteurin")
    return {**seed, "protokoll": c["id"], "eigene": eigene["id"]}


async def pruefen(tab, seed, p):
    bereit = "document.querySelector('#clMain .q') && !document.querySelector('#clMain').textContent.includes('Lädt')"
    karte = "document.getElementById('versionsCard')"
    cid = seed["protokoll"]

    # --- Büro, 1400 px, dunkel --------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(f"{karte} && {karte}.querySelectorAll('.ver-row').length===3", 15)
    p.pruefe("Karte: drei Fassungen, neueste oben, 2 überholt", await tab.js(
        f"[...{karte}.querySelectorAll('.ver-row')].map(r=>[r.dataset.version, r.querySelector('.badge').textContent])"),
        [["3", "gilt"], ["2", "überholt"], ["1", "gilt"]])
    p.pruefe("Fassung 2: verworfene Unterschrift genannt, nicht mehr versendbar", await tab.js(
        f"(t=>[t.includes('Unterschrift „Unterschrift Auftragnehmer“'), t.includes('nicht mehr versendbar')])"
        f"({karte}.querySelector('[data-version=\"2\"] [data-superseded]').textContent)"), [True, True])
    p.pruefe("Fassung 1: Anlass und Ersteller", await tab.js(
        f"(t=>[t.includes('nach der Unterschrift „Unterschrift Auftraggeber“'), t.includes('erstellt von Olga Office')])"
        f"({karte}.querySelector('[data-version=\"1\"] .ver-main').textContent)"), [True, True])
    p.pruefe("PDF-Link liefert das PDF", await tab.js(
        f"fetch({karte}.querySelector('[data-version=\"1\"] a').getAttribute('href')).then(async r=>[r.status, "
        f"r.headers.get('content-type'), new TextDecoder().decode((await r.arrayBuffer()).slice(0,5))])"),
        [200, "application/pdf", "%PDF-"])
    await tab.js(f"{karte}.querySelector('[data-version=\"1\"] button').click()")
    await tab.warten(f"{karte}.querySelector('[data-version=\"1\"] [id^=verCheck_]').textContent.length>2", 15)
    p.pruefe("Prüfen: Datei unverändert", await tab.js(
        f"{karte}.querySelector('[data-version=\"1\"] [id^=verCheck_]').textContent.includes('Datei unverändert')"), True)
    p.pruefe("PDF-Link in Akzentfarbe (nicht die Linkfarbe des Browsers)", await tab.js(
        f"(a=>{{const probe=document.createElement('span');probe.style.color='var(--accent)';document.body.appendChild(probe);"
        f"const soll=getComputedStyle(probe).color;probe.remove();return getComputedStyle(a).color===soll}})"
        f"({karte}.querySelector('.ver-row a'))"), True)
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])
    await tab.js(f"{karte}.scrollIntoView()")
    await tab.bild("1_fassungen_dunkel")

    # --- Büro, 412 px, hell -----------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(f"{karte} && {karte}.querySelectorAll('.ver-row').length===3", 15)
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js(f"{karte}.scrollIntoView()")
    await tab.bild("2_fassungen_412_hell")

    # --- Monteurin -------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{seed['eigene']}", bereit)
    p.pruefe("Monteurin: keine Karte, Liste der Fassungen 403", await tab.js(
        f"fetch('/api/checklists/{seed['eigene']}/versions').then(r=>[!document.getElementById('versionsCard'), r.status])"),
        [True, 403])
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])
    await tab.bild("3_monteurin_ohne_fassungen")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
