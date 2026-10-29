"""Klicktest: Status des Auftrags im Kopf der Akte, Übergänge im „⋮“ (1.9.130, Stufe 5, R2 Nachrunde, Punkt 1).

    Büro – Finanzen   Kopf mit dem Kennzeichen „Läuft“, keine Zeile unter den Phasen; „⋮“ mit Pausieren, Abschließen, Stornieren (Bild);
                      Auftrag mit Rechnungsentwurf ohne Schlussrechnung: kein „Abschließen …“; Pausieren über den Dialog -> „Pausiert“ mit
                      Hinweis und Begründung, im „⋮“ Fortsetzen statt Pausieren; Stornieren -> „Storniert“, kein Übergang mehr; der Verlauf
                      zeigt den Wechsel gleich (ohne Neuladen der Seite)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_status_im_menue.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.invoices import create_abschlag_pauschal
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id

    fiona = AppUser(username="fiona", display_name="Fiona Finanzen", role="buero_finanzen", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Status", last_name="Status", city="Uebach")
    db.add_all([fiona, kunde]); db.flush()

    def auftrag(nummer):
        p = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                    pipeline_column_id=default_pipeline_column_id(db))
        db.add(p); db.flush()
        q = Quote(quote_number=f"A-{nummer}", project_id=p.id, title="Sanierung", vat_rate=Decimal("19"))
        db.add(q); db.flush()
        db.add(QuoteItem(quote_id=q.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        o = create_order_from_quote(db, q.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
        return p, o

    frei, _ = auftrag("S-1")
    mit_entwurf, order_entwurf = auftrag("S-2")
    create_abschlag_pauschal(db, order_entwurf, lump_sum_net=Decimal("100"))
    return {"frei": frei.id, "mit_entwurf": mit_entwurf.id, "cookies": {"fiona": k.cookies(fiona)}}


AKTE = "typeof order!=='undefined'&&order&&order.id&&document.getElementById('seitenkopfStatus').textContent.length>0"
MENUE = ("(()=>{const m=document.getElementById('seitenkopfMenue');return [...m.querySelectorAll('[data-klick=\"statusAktion\"]')]"
         ".filter(e=>!e.hidden&&e.offsetParent!==null).map(e=>e.textContent)})()")
KOPF = "[document.getElementById('seitenkopfStatus').textContent,document.getElementById('statusZeile').hidden]"


async def dialog(tab, eintrag, begruendung, ziel_text):
    """„⋮“ öffnen, Eintrag wählen, Begründung eintragen, bestätigen; warten, bis das Kennzeichen ziel_text zeigt."""
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    await tab.js(f"[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')].find(e=>e.textContent==={eintrag!r}).click()")
    await tab.warten("document.getElementById('statusDialog').open")
    await tab.js(f"document.getElementById('statusBegruendung').value={begruendung!r};document.getElementById('statusDialogKnopf').click()")
    return await tab.warten(f"!document.getElementById('statusDialog').open&&document.getElementById('seitenkopfStatus').textContent==={ziel_text!r}")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["fiona"])

    await tab.oeffnen(f"/projects/{seed['frei']}", AKTE)
    p.pruefe("Büro: Kennzeichen „Läuft“ im Kopf, keine Zeile unter den Phasen", await tab.js(KOPF), ["Läuft", True])
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    p.pruefe("Büro: „⋮“ mit den erlaubten Übergängen", await tab.js(MENUE), ["Pausieren …", "Abschließen …", "Stornieren …"])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("kopf_mit_offenem_menue")
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")

    await tab.oeffnen(f"/projects/{seed['mit_entwurf']}", AKTE)
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    p.pruefe("Rechnungsentwurf ohne Schlussrechnung: kein „Abschließen …“", await tab.js(MENUE), ["Pausieren …", "Stornieren …"])
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")

    await tab.oeffnen(f"/projects/{seed['frei']}", AKTE)
    p.pruefe("Pausieren über den Dialog", await dialog(tab, "Pausieren …", "Gerüst fehlt", "Pausiert"), True)
    p.pruefe("Pausiert: Hinweis mit Begründung unter den Phasen", await tab.js(
        "[document.getElementById('statusZeile').hidden,document.getElementById('auftragsstatus').textContent.includes('Begründung: Gerüst fehlt')]"),
        [False, True])
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    p.pruefe("Pausiert: „⋮“ mit Fortsetzen statt Pausieren", await tab.js(MENUE), ["Fortsetzen …", "Abschließen …", "Stornieren …"])
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    p.pruefe("Stornieren über den Dialog", await dialog(tab, "Stornieren …", "Kunde hat abgesagt", "Storniert"), True)
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    p.pruefe("Storniert: kein Übergang im „⋮“ für das Büro", await tab.js(MENUE), [])
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    # seit 1.9.130: nach einem Statuswechsel lädt die Akte auch den Verlauf neu (bis dahin erst nach dem Neuladen der Seite)
    await tab.js("reiterZeigen('verlauf')")
    p.pruefe("Verlauf ohne Neuladen: „pausiert → storniert“ mit Begründung", await tab.warten(
        "document.getElementById('reiter-verlauf').textContent.includes('pausiert → storniert')&&"
        "document.getElementById('reiter-verlauf').textContent.includes('Begründung: Kunde hat abgesagt')"), True)

    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
