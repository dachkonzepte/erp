"""Seit 1.9.191 (Lohn L1a, Stufe 2, Punkt 6): „freigeben“ nur dort, wo die Freigabe möglich ist.

    Server   GET /api/time-backoffice/payroll-employees nennt je frühere Nummer, wer sie heute trägt ("fruehere_traeger", {Nummer: Name}) --
             dieselbe Regel wie die Freigabe (app/time_backoffice.py::personalnummern_traeger(), wie personalnummer_halter()): Lohnstammdaten
             mit dieser DATEV-Nummer, bei „DATEV-Nr. = ERP-Nr.“ eine Mitarbeiternummer; getragen <=> die Freigabe lehnt mit 409 ab
    Seite    Einstellungen: an einer getragenen Nummer statt des Knopfs „(trägt heute <Name>)“ -- auch für Büro – Finanzen; sonst „freigeben“
             nur für den Admin (Bild 05 der L1a-Korrekturen: Pia „früher: 91030 freigeben“, obwohl Kai 91030 trägt)
"""

import json

from app.models import EmployeePayrollSettings, TimeBackofficeAdvancedSettings
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v593_personalnummer_gesperrt import _client, _mitarbeiter_put, _put, welt  # noqa: F401

FREIGEBEN = "/api/time-backoffice/personalnummern/freigeben"


def _zeilen(w):
    r = _client(w).get("/api/time-backoffice/payroll-employees")
    assert r.status_code == 200, r.text
    return {z["employee_name"]: (z["fruehere_personalnummern"], z["fruehere_traeger"]) for z in r.json()}


def test_liste_nennt_wer_eine_fruehere_nummer_traegt(welt):
    """Mia 91008 -> 91016; Tom bekommt 91008 an der Sperre vorbei (wie aus einem alten Bestand): Mias „früher: 91008“ nennt Tom, die Freigabe
    lehnt ab. Tom gibt sie wieder ab -- niemand trägt sie, die Freigabe geht."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    assert _put(welt, mia, datev_personnel_number="91008").status_code == 200
    assert _put(welt, mia, datev_personnel_number="91016").status_code == 200
    assert _zeilen(welt)["Mia Monteurin"] == (["91008"], {})
    db.add(EmployeePayrollSettings(employee_id=tom.id, datev_personnel_number="91008", payroll_export_enabled=True))
    db.commit()
    assert _zeilen(welt)["Mia Monteurin"] == (["91008"], {"91008": "Tom Monteur"})
    assert _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91008"}).status_code == 409  # dieselbe Regel
    db.query(EmployeePayrollSettings).filter_by(employee_id=tom.id).one().datev_personnel_number = None
    db.commit()
    assert _zeilen(welt)["Mia Monteurin"] == (["91008"], {})
    assert _client(welt, "admin").post(FREIGEBEN, json={"nummer": "91008"}).status_code == 200


def test_bei_gleichsetzung_auch_die_mitarbeiternummer(welt):
    """„DATEV-Nr. = ERP-Nr.“: Mia 91001 -> 91002, Tom trägt 91001 als Mitarbeiternummer -- die Liste nennt ihn wie die Freigabe (409)."""
    db, mia, tom = welt["db"], welt["mia"], welt["tom"]
    db.get(TimeBackofficeAdvancedSettings, 1).datev_personnel_equals_erp_number = True
    client = _client(welt, "admin")
    assert _mitarbeiter_put(client, mia.id, employee_number="91001").status_code == 200
    assert _mitarbeiter_put(client, mia.id, employee_number="91002").status_code == 200
    tom.employee_number = " 91001"  # mit Leerzeichen: dieselbe Regel wie die Freigabe (getrimmt)
    db.commit()
    assert _zeilen(welt)["Mia Monteurin"] == (["M-1", "91001"], {"91001": "Tom Monteur"})  # M-1: ihre Nummer vor 91001, niemand trägt sie
    assert client.post(FREIGEBEN, json={"nummer": "91001"}).status_code == 409


# --- Seite --------------------------------------------------------------------------------------------------------------------------

def _funktion(text: str, kopf: str) -> str:
    i = text.index(kopf)
    tiefe, j = 0, text.index("{", i)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _fruehere(p: dict, freigeben: bool) -> list[str]:
    text = (vj.TEMPLATES / "settings.html").read_text(encoding="utf-8")
    js = ("function esc(s){return String(s==null?'':s).replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]))}\n"
          f"const PNR_FREIGEBEN={'true' if freigeben else 'false'};\n" + _funktion(text, "function fruehereNummer(")
          + f"\nconst p={json.dumps(p)};process.stdout.write(JSON.stringify(p.fruehere_personalnummern.map(n=>fruehereNummer(p,n))));")
    return node_ausfuehren(js)


PIA = {"employee_name": "Pia Monteurin", "fruehere_personalnummern": ["91008", "91030"], "fruehere_traeger": {"91030": "Kai <Monteur>"}}


def test_seite_knopf_nur_ohne_traeger():
    assert _fruehere(PIA, True) == [
        '91008 <button class="secondary" data-klick="pnr-freigeben" data-nummer="91008" data-name="Pia Monteurin">freigeben</button>',
        '91030 <span data-traegt="91030">(trägt heute Kai &lt;Monteur&gt;)</span>']


def test_seite_ohne_recht_zum_freigeben_nennt_den_traeger_auch():
    assert _fruehere(PIA, False) == ["91008", '91030 <span data-traegt="91030">(trägt heute Kai &lt;Monteur&gt;)</span>']
