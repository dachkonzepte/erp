"""Klicktest: Anfragen der Webseite (1.10.1, Stufe W1a) -- gegen die Attrappe des Empfangsdienstes (scripts/empfangsdienst_attrappe.py), nur
Musterdaten.

    Büro – Auftrag  von „Anfragen“ über „Anfragen der Webseite“ in den Eingang; „Jetzt abholen“ holt drei Musteranfragen (Reparatur mit zwei
                    Fotos, Kantservice, Wartung mit Spamverdacht und einem Namen mit HTML), meldet sie beim Empfangsdienst als übernommen; die
                    Liste neueste zuerst mit Kennzeichen; kein Skript aus den Daten läuft; die Anfrage mit Kontakt, Angaben, PDF und Fotos (die
                    Fotos laden, das PDF kommt als PDF); noch einmal abholen: nichts Neues; Empfangsdienst aus: Meldung, Stand mit Fehler
    Seit 1.10.3     Eingang in Berliner Zeit gleich der Minute der Nummer (Attrappe wie der echte Dienst); Adresse des Objekts in Liste, Start und
                    oben auf der Anfrage; Kantservice ohne Adresse, mit „Ort“ im Kontakt; Abschnitte nur der Art (Reparatur ohne Kantteil-Zeichner);
                    die Nachricht der Reparatur wiederholt nur die Angaben und steht eingeklappt
    Seit 1.10.4     die Wartung mit Spamverdacht steht in der Prüfliste, nicht im Eingang und nicht auf „Start“; verwerfen mit Grund (Meldung
                    „verworfen“ an die Attrappe), Erledigt, zurück in den Eingang (wieder Prüfliste, Meldung eingang-<ID>), „Kein Spam – in den Eingang“
    Bilder          Eingang und Anfrage bei 1440 px hell und dunkel, bei 412 px hell (nichts läuft über); seit 1.10.4 Prüfliste und Bearbeitung
    Monteurin       der Eingang ist gesperrt, die Schnittstelle des ERP antwortet 403

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_webanfragen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
Die Attrappe läuft in diesem Prozess auf 127.0.0.1; die Instanz bekommt ihre Adresse und ihren Schlüssel über die Umgebung.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from empfangsdienst_attrappe import Attrappe, muster  # noqa: E402

ATTRAPPE = Attrappe()
BOESE = '<img src=x onerror="window.__boese=1">'
R, K, W = "R-20261119-0910-0A1B", "K-20261119-0911-0C2D", "W-20261119-0912-0E3F"


def befuellen(db, k):
    from app.models import AppUser
    buero = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort())
    monteur = AppUser(username="mo", display_name="Mo Monteur", role="field", password_hash=k.passwort())
    db.add_all([buero, monteur])
    db.commit()
    return {"cookies": {"buero": k.cookies(buero), "mo": k.cookies(monteur)}}


EINGANG_BEREIT = "!document.getElementById('standText').textContent.includes('Lädt')"
ANFRAGE_BEREIT = "!!document.querySelector('#kontakt .zeile')"
ZEILEN = "[...document.querySelectorAll('#eingangTabelle tbody tr')]"
STATUS = "document.getElementById('abholStatus')"


async def _thema(tab, thema: str, pfad: str, bereit: str):
    await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
    await tab.oeffnen(pfad + ("&" if "?" in pfad else "?") + "thema=" + thema, bereit)
    await tab.warte_auf_ruhe()


async def _abholen(tab):
    await tab.js(f"{STATUS}.textContent='';document.querySelector('[data-klick=\"abholen\"]').click()")
    await tab.warten(f"{STATUS}.textContent.length>0&&!{STATUS}.textContent.startsWith('Holt')")
    await tab.warte_auf_ruhe()
    return await tab.js(f"[{STATUS}.textContent,{STATUS}.className]")


async def pruefen(tab, seed, p):
    a = ATTRAPPE
    # seit 1.10.3: der Eingang folgt der Nummer in Berliner Zeit (wie der echte Dienst)
    a.dazu(muster(R, "reparatur", fotos=2))
    a.dazu(muster(K, "kantservice"))
    a.dazu(muster(W, "wartung", spam=True, name=BOESE))

    # --- Büro: der Weg in den Eingang ---
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen("/inquiries", "!!document.getElementById('webanfragenLink')")
    await tab.js("document.getElementById('webanfragenLink').click()")
    await tab.warten(f"location.pathname==='/anfragen/webseite'&&{EINGANG_BEREIT}")
    await tab.warte_auf_ruhe()
    p.pruefe("Eingang: leer", await tab.js("document.getElementById('listeRahmen').textContent.trim()"),
             "Noch keine Anfragen der Webseite im Eingang.")
    p.pruefe("Eingang: zuletzt abgeholt noch nie", await tab.js("document.getElementById('standText').textContent.includes('noch nie')"), True)

    # --- Jetzt abholen ---
    p.pruefe("Abholen: Ergebnis", await _abholen(tab), ["3 Anfragen neu abgeholt.", "status ok"])
    p.pruefe("Abholen: beim Empfangsdienst gemeldet", sorted(a.uebernommen), [K, R, W])
    # seit 1.10.4: die Wartung mit Spamverdacht steht in der Prüfliste, nicht im Eingang
    p.pruefe("Liste: neueste zuerst", await tab.js(f"{ZEILEN}.map(z=>z.children[1].textContent)"), [K, R])
    p.pruefe("Liste: Eingang in Berliner Zeit wie die Nummer", await tab.js(f"{ZEILEN}.map(z=>z.children[0].textContent)"),
             ["19.11.2026 09:11", "19.11.2026 09:10"])
    p.pruefe("Liste: Adresse des Objekts", await tab.js(f"{ZEILEN}.map(z=>z.children[4].textContent)"), ["—", "Musterweg 1, 00000 Musterstadt"])
    p.pruefe("Liste: Dateien", await tab.js(f"{ZEILEN}.map(z=>z.children[7].textContent)"), ["1", "3"])
    p.pruefe("Stand: 2 im Eingang, 1 in der Prüfliste", await tab.js(
        "['2 im Eingang','1 in der Prüfliste'].map(x=>document.getElementById('standText').textContent.includes(x))"), [True, True])
    p.pruefe("Reiter: Zahlen", await tab.js("[zahlEingang.textContent,zahlPruefliste.textContent]"), ["2", "1"])
    await tab.js("document.querySelector('.reiter a[data-ansicht=\"pruefliste\"]').click()")
    await tab.warten(f"location.hash==='#pruefliste'&&{ZEILEN}.length===1")
    await tab.warte_auf_ruhe()
    p.pruefe("Prüfliste: die Wartung mit Spamverdacht", await tab.js(f"[{ZEILEN}[0].children[1].textContent,!!{ZEILEN}[0].querySelector('.kennzeichen.spam')]"),
             [W, True])
    p.pruefe("Prüfliste: Name mit HTML als Text", await tab.js(f"{ZEILEN}[0].children[3].textContent"), BOESE)
    p.pruefe("Liste: kein Skript aus den Daten", await tab.js("window.__boese===undefined&&!document.querySelector('#eingangTabelle img')"), True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/anfragen/webseite?thema=light#pruefliste", f"{EINGANG_BEREIT}&&{ZEILEN}.length===1")  # Anker nach der Abfrage
    await tab.warte_auf_ruhe()
    p.pruefe("Prüfliste: hell", await tab.js("document.documentElement.getAttribute('data-theme')"), "light")
    await tab.bild_ganz("webanfragen_pruefliste_1440_hell")
    await tab.oeffnen("/anfragen/webseite#eingang", EINGANG_BEREIT)
    p.pruefe("Eingang: JS-Fehler", tab.fehler, [])
    await _thema(tab, "light", "/anfragen/webseite", EINGANG_BEREIT)
    await tab.bild_ganz("webanfragen_eingang_1440_hell")
    await _thema(tab, "dark", "/anfragen/webseite", EINGANG_BEREIT)
    await tab.bild_ganz("webanfragen_eingang_1440_dunkel")
    await _thema(tab, "light", "/anfragen/webseite", EINGANG_BEREIT)

    # --- Startseite (seit 1.10.2): das Widget „Anfragen der Webseite“ unter „Meine Aufgaben“ ---
    widget = "document.getElementById('widget-body-webanfragen')"
    await tab.oeffnen("/", f"!!{widget}&&!!{widget}.querySelector('.task-list')")
    await tab.warte_auf_ruhe()
    p.pruefe("Start: Widgets", await tab.js("[...document.querySelectorAll('.widget-card h2')].map(h=>h.textContent).slice(0,2)"),
             ["Meine Aufgaben", "Anfragen der Webseite"])
    p.pruefe("Start: Zahl im Eingang", await tab.js(f"{widget}.querySelector('a').textContent"), "2 im Eingang")
    p.pruefe("Start: Prüfliste mit Weg", await tab.js(f"(a=>[a.textContent,a.getAttribute('href')])({widget}.querySelectorAll('a')[1])"),
             ["1 in der Prüfliste", "/anfragen/webseite#pruefliste"])
    p.pruefe("Start: die neuesten mit Weg (ohne Prüfliste)",
             await tab.js(f"[...{widget}.querySelectorAll('a.task-row')].map(a=>a.getAttribute('href').split('/').length)"), [4, 4])
    p.pruefe("Start: kein Skript aus den Daten", await tab.js("window.__boese===undefined"), True)
    p.pruefe("Start: Adresse des Objekts", await tab.js(f"[...{widget}.querySelectorAll('a.task-row')].map(a=>a.textContent.includes('Musterweg 1, 00000 Musterstadt'))"),
             [False, True])
    p.pruefe("Start: JS-Fehler", tab.fehler, [])
    await tab.bild("webanfragen_start_1440_hell")
    await tab.js(f"[...{widget}.querySelectorAll('a.task-row')][1].click()")
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    p.pruefe("Start: Klick öffnet die Anfrage", await tab.js("document.getElementById('seitenkopfKennung').textContent"), R)
    await tab.oeffnen("/anfragen/webseite", EINGANG_BEREIT)

    # --- eine Anfrage ---
    await tab.js(f"{ZEILEN}[1].querySelector('a').click()")
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    await tab.warte_auf_ruhe()
    p.pruefe("Anfrage: Kopf", await tab.js("[document.getElementById('seitenkopfTitel').textContent,document.getElementById('seitenkopfKennung').textContent]"),
             ["Reparatur-Anfrage", R])
    p.pruefe("Anfrage: Kontakt", await tab.js("document.querySelector('#kontakt .zeile dd').textContent"), "Max Muster")
    p.pruefe("Anfrage: Adresse oben", await tab.js("document.getElementById('seitenkopfUntertitel').textContent"),
             "Objekt: Musterweg 1, 00000 Musterstadt · Eingang 19.11.2026 09:10")
    p.pruefe("Anfrage: Kontakt ohne abgeleiteten Ort", await tab.js("[...document.querySelectorAll('#kontakt dt')].map(x=>x.textContent)"),
             ["Name", "Telefon", "E-Mail"])
    p.pruefe("Anfrage: Angaben aus dk-reparatur/1", await tab.js("document.getElementById('angaben').textContent.includes('Rinne verstopft')"), True)
    p.pruefe("Anfrage: kein Abschnitt des Kantservice", await tab.js(
        "['Kantteil-Zeichner','Aufmaß vor Ort'].map(x=>document.getElementById('angaben').textContent.includes(x))"), [False, False])
    p.pruefe("Anfrage: Nachricht eingeklappt", await tab.js(
        "(d=>!!d&&!d.open&&d.querySelector('summary').textContent)(document.querySelector('#anfrage details.nachricht'))"),
        "Wiederholt nur die Angaben aus dem Formular – anzeigen")
    await tab.warten("[...document.querySelectorAll('.fotos img')].every(i=>i.complete&&i.naturalWidth>0)")
    p.pruefe("Anfrage: zwei Fotos geladen", await tab.js("[...document.querySelectorAll('.fotos img')].filter(i=>i.naturalWidth>0).length"), 2)
    p.pruefe("Anfrage: PDF als PDF", await tab.js(
        "fetch(document.querySelector('.dateien a').href).then(r=>[r.status,r.headers.get('content-type'),r.headers.get('x-content-type-options')])"),
        [200, "application/pdf", "nosniff"])
    p.pruefe("Anfrage: gemeldet", await tab.js("document.getElementById('herkunft').textContent.includes('noch nicht')"), False)
    p.pruefe("Anfrage: JS-Fehler", tab.fehler, [])
    await tab.bild_ganz("webanfragen_anfrage_1440_hell")
    await _thema(tab, "dark", f"/anfragen/webseite/{await tab.js('ID')}", ANFRAGE_BEREIT)
    await tab.bild_ganz("webanfragen_anfrage_1440_dunkel")
    await _thema(tab, "light", f"/anfragen/webseite/{await tab.js('ID')}", ANFRAGE_BEREIT)

    # --- Kantservice: ohne Adresse, „Ort“ im Kontakt, Positionen ---
    await tab.oeffnen("/anfragen/webseite", EINGANG_BEREIT)
    await tab.js(f"{ZEILEN}[0].querySelector('a').click()")
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    await tab.warte_auf_ruhe()
    p.pruefe("Kantservice: ohne Adresse", await tab.js("document.getElementById('seitenkopfUntertitel').textContent.split(' · ')[0]"),
             "Kantservice – ohne Objekt-Adresse")
    p.pruefe("Kantservice: Ort im Kontakt", await tab.js("[...document.querySelectorAll('#kontakt dt')].map(x=>x.textContent).includes('Ort')"), True)
    p.pruefe("Kantservice: Positionen", await tab.js("document.getElementById('angaben').textContent.includes('Kantteil-Zeichner')"), True)
    p.pruefe("Kantservice: Nachricht offen", await tab.js("!document.querySelector('#anfrage details')"), True)

    # --- die Anfrage mit Spamverdacht und HTML im Namen (Prüfliste) ---
    await tab.oeffnen("/anfragen/webseite#pruefliste", f"{EINGANG_BEREIT}&&{ZEILEN}.length===1")
    await tab.js(f"{ZEILEN}[0].querySelector('a').click()")
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    await tab.warte_auf_ruhe()
    p.pruefe("Spam: Hinweis", await tab.js("document.getElementById('hinweise').textContent.startsWith('Spamverdacht')"), True)
    p.pruefe("Spam: Name als Text, kein Skript", await tab.js(
        "[document.querySelector('#kontakt .zeile dd').textContent, window.__boese===undefined]"), [BOESE, True])
    # --- seit 1.10.4: Bearbeitung ---
    BEARB = "[document.getElementById('seitenkopfStatus').textContent,document.getElementById('bearbeitungStand').textContent.split(':')[0]," \
            "!inDenEingangKnopf.hidden,!verwerfenOeffnenKnopf.hidden,!zurueckholenKnopf.hidden]"
    p.pruefe("Prüfliste: Stand und Knöpfe", await tab.js(BEARB), ["Prüfliste", "In der Prüfliste", True, True, False])
    p.pruefe("Verwerfen: Feld erst nach dem Klick sichtbar", await tab.js("getComputedStyle(verwerfenPanel).display"), "none")
    await tab.bild_ganz("webanfragen_bearbeitung_1440_hell")
    await tab.js("verwerfenOeffnenKnopf.click()")
    p.pruefe("Verwerfen: Feld nach dem Klick sichtbar", await tab.js("getComputedStyle(verwerfenPanel).display"), "flex")
    p.pruefe("Verwerfen: ohne Grund nicht", await tab.js("verwerfenKnopf.click(),aktionStatus.textContent"), "Bitte einen Grund wählen.")
    await tab.js("verwerfenGrund.value='spam';verwerfenKnopf.click()")
    await tab.warten("document.getElementById('seitenkopfStatus').textContent==='Verworfen'")
    await tab.warte_auf_ruhe()
    p.pruefe("Verwerfen: Stand", await tab.js("bearbeitungStand.textContent.startsWith('Verworfen (Spam) am 19.11.2026')"), True)
    p.pruefe("Verwerfen: an die Attrappe gemeldet", a.uebernommen.get(W), "verworfen")
    p.pruefe("Verwerfen: Meldung auf der Seite", await tab.js("meldungText.textContent"), "Beim Empfangsdienst gemeldet als „verworfen“.")
    p.pruefe("Verwerfen: Knöpfe", await tab.js(BEARB + ".slice(2)"), [False, False, True])
    await tab.oeffnen("/anfragen/webseite#erledigt", f"{EINGANG_BEREIT}&&{ZEILEN}.length===1")
    p.pruefe("Erledigt: verworfen mit Grund", await tab.js(f"{ZEILEN}[0].querySelector('.kennzeichen.erledigt').textContent"), "verworfen: Spam")
    await tab.js(f"{ZEILEN}[0].querySelector('a').click()")
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    await tab.warte_auf_ruhe()
    await tab.js("window.confirm=()=>true;zurueckholenKnopf.click()")
    await tab.warten("document.getElementById('seitenkopfStatus').textContent==='Prüfliste'")
    await tab.warte_auf_ruhe()
    p.pruefe("Zurückholen: wieder in der Prüfliste, Meldung eingang", [a.meldungen[-1][0], a.meldungen[-1][1].startswith("eingang-")], [W, True])
    await tab.js("inDenEingangKnopf.click()")
    await tab.warten("document.getElementById('seitenkopfStatus').textContent==='Neu'")
    await tab.warte_auf_ruhe()
    p.pruefe("In den Eingang: Stand", await tab.js("bearbeitungStand.textContent.startsWith('Im Eingang (aus der Prüfliste gegeben am 19.11.2026')"), True)
    p.pruefe("Bearbeitung: JS-Fehler", tab.fehler, [])

    # --- 412 px ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/anfragen/webseite", EINGANG_BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("412: Eingang läuft nicht über", await tab.ueberlauf(), [])
    await tab.bild_ganz("webanfragen_eingang_412_hell")
    await tab.js(f"{ZEILEN}[2].querySelector('a').click()")  # R (die Wartung steht seit dem Klick „in den Eingang“ wieder im Eingang)
    await tab.warten(f"location.pathname.startsWith('/anfragen/webseite/')&&{ANFRAGE_BEREIT}")
    await tab.warte_auf_ruhe()
    p.pruefe("412: Anfrage läuft nicht über", await tab.ueberlauf(), [])
    await tab.bild_ganz("webanfragen_anfrage_412_hell")
    await tab.fenster(1440, 1000)

    # --- noch einmal abholen, dann ohne Empfangsdienst ---
    await tab.oeffnen("/anfragen/webseite", EINGANG_BEREIT)
    p.pruefe("Noch einmal: nichts Neues", await _abholen(tab), ["0 Anfragen neu abgeholt.", "status ok"])
    a.stop()
    p.pruefe("Empfangsdienst aus: Meldung", await _abholen(tab), ["Empfangsdienst nicht erreichbar", "status err"])
    p.pruefe("Empfangsdienst aus: Stand", await tab.js("document.getElementById('standHinweis').textContent"),
             "Letzter Lauf: Empfangsdienst nicht erreichbar")
    p.pruefe("Empfangsdienst aus: Liste bleibt", await tab.js(f"{ZEILEN}.length"), 3)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["mo"])
    p.pruefe("Monteurin: Schnittstelle 403", await tab.js("fetch('/api/webanfragen').then(r=>r.status)"), 403)
    await tab.oeffnen("/anfragen/webseite", "document.readyState==='complete'")
    p.pruefe("Monteurin: Eingang gesperrt", await tab.js("!document.getElementById('eingangTabelle')&&!document.getElementById('standKarte')"), True)


if __name__ == "__main__":
    ATTRAPPE.start()
    try:
        rc = klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-19 11:00",
                            umgebung={"DK_ANFRAGE_URL": ATTRAPPE.adresse, "DK_ANFRAGE_SCHLUESSEL": ATTRAPPE.schluessel})
    finally:
        ATTRAPPE.stop()
    sys.exit(rc)
