"""Klicktest: Kundenliste in der Reihenfolge des Telefonbuchs (1.9.353, Runde V2b, Punkt 1, F6).

Testdaten: Anna Admin (angemeldet); 17 Kunden mit Groß- und Kleinbuchstaben am Anfang, Umlauten, ß, Akzenten, Bindestrich und Leerzeichen und einem
leeren Namen -- ein Altbestand mit dem Nachnamen " " (bis 1.9.355 nahm die API ihn an, compose_customer_name() macht daraus ""; die Formulare
prüfen selbst, seit 1.9.356 lehnt auch der Server ihn ab, B2). Die Kunden kommen in einer Reihenfolge in die Datenbank, die weder binär noch nach dem Telefonbuch sortiert ist.

    Liste       Stammdaten → Kunden: nach Nachname, dann Vorname (seit 1.9.355, ohne Anrede und Titel: „Herr Bernd Abel“ zuerst) in der
                Reihenfolge des Telefonbuchs -- „apfelbaum“ vor „Äpfelmann“ vor „bauhof“ vor „Bauhof“,
                „Müller Probe“ vor „MÜLLER Probe“ vor „Müller-Probe“, „Straßenbau“ vor „Strassmann“ (ß wie ss), der leere Name zuletzt
    Suche       Büro-Suche „probe“: die Kunden in derselben Reihenfolge
    Bilder      1440 und 412 px, hell und dunkel; bei 412 px läuft nichts über die Seite
    überall     keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_telefonbuch.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

# So angelegt (IDs in dieser Reihenfolge) -- weder binär noch nach dem Telefonbuch sortiert. Ein Name allein ist der Nachname (Firma); seit 1.9.355
# (F1) dazu zwei Personen mit Anrede, Titel und Vorname: (Anrede, Titel, Vorname, Nachname).
ANGELEGT = ["Zimmerei Zander GmbH", "Müller-Probe Bau", "", "Ökohaus Probe", ("Frau", "Dr.", "Erika", "Probe"), "bauhof Nord", "MÜLLER Probe KG",
            "Strassmann Probe", "Äpfelmann Dachbau", "Łukasz Probe", ("Herr", None, "Bernd", "Abel"), "Bauhof Süd", "Müller Probe Bau",
            "Straßenbau Probe", "Émile Probe", "apfelbaum Gartenbau", "Oelbach Probe"]
# nach Nachname, dann Vorname -- „Herr Bernd Abel“ unter A, „Frau Dr. Erika Probe“ unter P (bis 1.9.354 unter H und F)
TELEFONBUCH = ["Herr Bernd Abel", "apfelbaum Gartenbau", "Äpfelmann Dachbau", "bauhof Nord", "Bauhof Süd", "Émile Probe", "Łukasz Probe",
               "Müller Probe Bau", "MÜLLER Probe KG", "Müller-Probe Bau", "Oelbach Probe", "Ökohaus Probe", "Frau Dr. Erika Probe", "Straßenbau Probe",
               "Strassmann Probe", "Zimmerei Zander GmbH", ""]
BEREIT = ("document.getElementById('seitenkopfTitel')?.textContent==='Kunden'"
          f"&&document.querySelectorAll('#content tbody tr').length==={len(ANGELEGT)}")
NAMEN = "[...document.querySelectorAll('#content tbody tr')].map(tr=>tr.cells[1].querySelector('a').textContent)"


def befuellen(db, k):
    from app.crm import compose_customer_name
    from app.models import AppUser, Customer, CustomerProfile

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(anna)
    for i, eintrag in enumerate(ANGELEGT, start=1):
        anrede, titel, vorname, nachname = eintrag if isinstance(eintrag, tuple) else (None, None, None, eintrag)
        nachname = nachname or " "  # der leere Name: Nachname aus einem Leerzeichen (Altbestand, siehe oben)
        kunde = Customer(name=compose_customer_name(anrede, titel, vorname, nachname), salutation=anrede, title=titel, first_name=vorname,
                         last_name=nachname, city="Musterstadt")
        db.add(kunde)
        db.flush()
        db.add(CustomerProfile(customer_id=kunde.id, customer_number=f"K-9{i:03d}", category="Privat"))
    db.commit()
    return {"anna": k.cookies(anna)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);")
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/master-data#customers", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Kundenliste geladen", await tab.oeffnen("/master-data?n=1#customers", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Kundenliste in der Reihenfolge des Telefonbuchs", await tab.js(NAMEN), TELEFONBUCH)
    p.pruefe("API in derselben Reihenfolge", await tab.js("fetch('/api/customers').then(r=>r.json()).then(k=>k.map(x=>x.name))"), TELEFONBUCH)
    p.pruefe("Büro-Suche „probe“ in derselben Reihenfolge", await tab.js(
        "fetch('/api/search?q=probe&types=customers&limit=50').then(r=>r.json()).then(d=>d.find(g=>g.key==='customers').hits.map(x=>x.title))"),
        [n for n in TELEFONBUCH if "probe" in n.lower()])

    for breite, hoehe, mobil in ((1440, 1000, False), (412, 1600, True)):  # 412: hoch genug für alle 17 Zeilen samt leerem Namen
        await tab.fenster(breite, hoehe, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/master-data?n=b{breite}{name}#customers", BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"Bild {breite} {name}: Reihenfolge", await tab.js(NAMEN), TELEFONBUCH)
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild(f"kundenliste_telefonbuch_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
