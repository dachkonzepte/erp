"""Klicktest: Einstellungen mit Geld nur für Admin und Büro – Finanzen (1.9.120, Stufe 5, R1 Nachrunde, Punkt 2).

    Büro – Auftrag   Nummernkreise, Zahlungsbedingungen, Steuer, Mahnwesen: Hinweis, jedes Feld gesperrt, kein „Speichern“, kein
                     „+ Zahlungsbedingung“/„+ Steuerschlüssel“; „Ansehen“ öffnet die Zahlungsbedingung gesperrt mit „Schließen“ (Bild);
                     E-Mail-Vorlagen: eine Mahnstufe gesperrt mit Hinweis, das Angebot offen; Angriff aus der Seite (PUT Mahnstufe,
                     POST Zahlungsbedingung) 403
    Büro – Finanzen  Felder offen, Nummernkreis und Zahlungsbedingung gespeichert

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_einstellungen_geld.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from sqlalchemy import select

    from app.models import AppUser, PaymentTerm, ReminderLevel

    berta = AppUser(username="berta", display_name="Berta Auftrag", role="buero_auftrag", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([berta, fin, PaymentTerm(label="30 Tage netto", days=30, text_template="Zahlbar bis {faelligkeitsdatum}.")])
    db.commit()
    stufe = db.scalars(select(ReminderLevel).order_by(ReminderLevel.level)).first()
    return {"stufe": stufe.id, "cookies": {"berta": k.cookies(berta), "fin": k.cookies(fin)}}


BEREIT = "document.querySelector('.settings-menu')&&typeof sequences!=='undefined'&&sequences.length>0&&document.querySelector('.sequence')"
# je Bereich: Hinweis sichtbar, offene Felder, sichtbare Speichern-Knöpfe
STAND = ("(id=>{const s=document.getElementById(id);const sichtbar=e=>!!e&&!e.hidden&&e.offsetParent!==null;"
         "return {hinweis:sichtbar(s.querySelector('[data-geld-nur-lesen]')),"
         "offen:[...s.querySelectorAll('input,textarea,select')].filter(f=>sichtbar(f)&&!f.disabled).length,"
         "speichern:[...s.querySelectorAll('button')].filter(b=>sichtbar(b)&&/Speichern|Hinzufügen|\\+ /.test(b.textContent)).length}})")


async def _bereich(tab, schluessel, laden):
    await tab.js(f"document.querySelector('[data-settings-section=\"{schluessel}\"]').click()")
    await tab.warten(laden, 15)
    return await tab.js(f"{STAND}('settings-{schluessel}')")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["berta"])
    await tab.oeffnen("/settings", BEREIT)
    leer = {"hinweis": True, "offen": 0, "speichern": 0}
    p.pruefe("Büro – Auftrag: Nummernkreise gesperrt", await _bereich(tab, "numbers", "document.querySelector('.sequence input')"), leer)
    p.pruefe("Büro – Auftrag: Zahlungsbedingungen gesperrt", await _bereich(
        tab, "payment-terms", "document.querySelector('#paymentTermRows button')"), leer)
    p.pruefe("Büro – Auftrag: Steuer gesperrt", await _bereich(tab, "tax-keys", "document.querySelector('#taxKeyRows button')"), leer)
    p.pruefe("Büro – Auftrag: Mahnwesen gesperrt", await _bereich(
        tab, "reminder-levels", "document.querySelector('#reminderLevelRows input')"), leer)

    await tab.js("document.querySelector('[data-settings-section=\"payment-terms\"]').click()")
    p.pruefe("Zeile der Zahlungsbedingung: nur „Ansehen“", await tab.js(
        "[...document.querySelectorAll('#paymentTermRows tr')].find(t=>t.textContent.includes('30 Tage netto'))"
        ".querySelectorAll('button').length+' '+[...document.querySelectorAll('#paymentTermRows tr')].find(t=>t.textContent.includes('30 Tage netto'))"
        ".querySelector('button').textContent"), "1 Ansehen")
    await tab.js("[...document.querySelectorAll('#paymentTermRows tr')].find(t=>t.textContent.includes('30 Tage netto')).querySelector('button').click()")
    p.pruefe("„Ansehen“: Zahlungsbedingung gesperrt mit Text, ohne Speichern", await tab.js(
        "(()=>{const b=document.getElementById('paymentTermEditorPanel');return [b.offsetParent!==null,"
        "document.getElementById('paymentTermEditorHeading').textContent,document.getElementById('ptTextTemplate').value,"
        "[...b.querySelectorAll('input,textarea')].every(f=>f.disabled),document.getElementById('paymentTermSave').hidden,"
        "document.getElementById('paymentTermCancel').textContent]})()"),
        [True, "Zahlungsbedingung ansehen", "Zahlbar bis {faelligkeitsdatum}.", True, True, "Schließen"])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("einstellungen_zahlungsbedingung_als_buero_auftrag")

    await tab.js("document.querySelector('[data-settings-section=\"email-templates\"]').click()")
    await tab.js("(()=>{const s=document.getElementById('emailTemplateType');s.value='reminder:1';s.dispatchEvent(new Event('change'))})()")
    p.pruefe("E-Mail-Vorlagen: Mahnstufe gesperrt mit Hinweis", await tab.warten(
        "document.getElementById('emailTemplateSubject').disabled&&document.getElementById('emailTemplateSave').hidden"
        "&&!document.getElementById('emailTemplateGeldHinweis').hidden&&document.getElementById('emailTemplateGeldHinweis').offsetParent!==null"), True)
    await tab.js("(()=>{const s=document.getElementById('emailTemplateType');s.value='quote';s.dispatchEvent(new Event('change'))})()")
    p.pruefe("E-Mail-Vorlagen: Angebot offen", await tab.warten(
        "!document.getElementById('emailTemplateSubject').disabled&&!document.getElementById('emailTemplateSave').hidden"
        "&&document.getElementById('emailTemplateGeldHinweis').hidden"), True)

    angriff = await tab.js(
        f"Promise.all([fetch('/api/reminder-levels/{seed['stufe']}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({label:'x'})}),fetch('/api/payment-terms',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({label:'7 Tage',days:7})})]).then(rs=>Promise.all(rs.map(async r=>[r.status,(await r.json()).detail.slice(0,40)])))")
    p.pruefe("Angriff aus der Seite: Mahnstufe und Zahlungsbedingung 403", angriff,
             [[403, "Mahnstufen, Zahlungsbedingungen, Steuers"], [403, "Mahnstufen, Zahlungsbedingungen, Steuers"]])
    p.pruefe("JS-Fehler (Büro – Auftrag)", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["fin"])
    await tab.oeffnen("/settings", BEREIT)
    stand = await _bereich(tab, "numbers", "document.querySelector('.sequence input')")
    p.pruefe("Büro – Finanzen: Nummernkreise offen, ohne Hinweis", [stand["hinweis"], stand["offen"] > 0, stand["speichern"] > 0], [False, True, True])
    await tab.js("(()=>{const r=document.querySelector('.sequence[data-key=\"customer\"]');const f=r.querySelector('.next');"
                 "f.value=String(Number(f.value.replace(/\\./g,''))+5);r.querySelector('[data-klick=\"nummernkreis-speichern\"]').click()})()")
    p.pruefe("Büro – Finanzen: Nummernkreis gespeichert", await tab.warten(
        "(document.querySelector('.sequence[data-key=\"customer\"] .seqStatus')||{}).textContent?.startsWith('Gespeichert')"), True)
    await tab.js("document.querySelector('[data-settings-section=\"payment-terms\"]').click()")
    await tab.js("[...document.querySelectorAll('#paymentTermRows tr')].find(t=>t.textContent.includes('30 Tage netto')).querySelector('button').click()")
    await tab.js("(()=>{const f=document.getElementById('ptLabel');f.value='30 Tage rein netto';f.dispatchEvent(new Event('input'))})()")
    await tab.warte_auf_neu_geladene_liste("savePaymentTerm()", "#paymentTermRows")
    p.pruefe("Büro – Finanzen: Zahlungsbedingung gespeichert", await tab.js(
        "fetch('/api/payment-terms').then(r=>r.json()).then(l=>l.some(t=>t.label==='30 Tage rein netto'))"), True)
    p.pruefe("JS-Fehler (Büro – Finanzen)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
