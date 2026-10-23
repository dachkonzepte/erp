"""Seit 1.9.58 (Stufe 4, R3, Punkte 1 und 6): „Heute“ startet auch mit Tätigkeit und für die Kolonne -- bis dahin auf der Zeiterfassung
der Monteurin, die „Meine Zeiten“ ersetzt (Starten und Stoppen nur noch auf „Heute“); Zeitart-Kacheln quer 3, hoch 2 Spalten.

    Server   "nichts" liefert die aktiven Tätigkeiten (Optionsgruppe time_entry_activities), ob die Zeitregeln eine verlangen, und die
             Kolonnen des Kolonnenführers -- nur mit Gruppenbuchungen (der Start lehnte sonst ab, 403); einem Mitglied keine
    Starten  der Dialog schickt, was die Zeiterfassung schickte (IDs als Text): POST /api/time-entries/start mit Tätigkeit,
             POST /api/time-entry-groups/start mit Kolonne und Mitgliedern
    Seite    „⋮“ (48 px, dsMenue()) nur, wenn es etwas zu wählen gibt; verlangen die Zeitregeln eine Tätigkeit, öffnet auch eine Kachel den
             Dialog; Kacheln quer immer 3 Spalten, hoch (unter 1000 px wie die Seite) 2
Im Browser: scripts/klicktest_heute.py (Lea mit Tätigkeit, Kai für die Kolonne, Spalten der Kacheln quer und hoch).
"""

import re
from datetime import timedelta

from sqlalchemy import select

from app.models import SettingOption, SettingOptionGroup, TimeEntry
from app.time_backoffice import load_time_settings
from tests import vorlagen_js as vj
from tests.test_v471_heute_server import _als, _einsatz, _heute, welt  # noqa: F401  (Fixture)


def _option(db, gruppe, wert):
    return db.scalar(select(SettingOption).join(SettingOptionGroup).where(SettingOptionGroup.group_key == gruppe, SettingOption.value == wert))


def test_nichts_mit_taetigkeiten_und_kolonne(welt):  # noqa: F811
    """Angriff: Mia führt die Kolonne -- Tätigkeiten und ihre Kolonne mit beiden Mitgliedern; Gegenprobe: Tom (Mitglied) keine Kolonne."""
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert z["zustand"] == "nichts" and z["taetigkeit_pflicht"] is False
    assert "Dachdeckung" in [t["label"] for t in z["taetigkeiten"]] and all(set(t) == {"value", "label"} for t in z["taetigkeiten"])
    assert [(k["team_id"], k["name"], sorted(m["name"] for m in k["members"])) for k in z["kolonnen"]] == \
        [(welt["team"].id, "Kolonne 1", ["Mia Monteurin", "Tom Monteur"])]
    assert _heute(welt, welt["tom"])["arbeitszeit"]["kolonnen"] == []


def test_ohne_gruppenbuchungen_keine_kolonne_und_taetigkeit_pflicht(welt):  # noqa: F811
    regeln = load_time_settings(welt["db"])
    regeln.allow_group_bookings, regeln.require_activity = False, True
    welt["db"].commit()
    z = _heute(welt, welt["mia"])["arbeitszeit"]
    assert (z["kolonnen"], z["taetigkeit_pflicht"]) == ([], True)


def test_inaktive_taetigkeit_fehlt(welt):  # noqa: F811
    _option(welt["db"], "time_entry_activities", "Dachdeckung").active = False
    welt["db"].commit()
    assert "Dachdeckung" not in [t["label"] for t in _heute(welt, welt["mia"])["arbeitszeit"]["taetigkeiten"]]


def test_start_mit_taetigkeit_wie_der_dialog(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"] + timedelta(days=1))], [welt["mia"], welt["tom"]])
    r = _als(welt, welt["mia"]).post("/api/time-entries/start", json={
        "employee_id": welt["mia"].id, "order_id": str(welt["order"].id), "entry_type": "workshop", "activity": "Dachdeckung"})
    assert r.status_code == 200, r.text
    row = welt["db"].get(TimeEntry, r.json()["id"])
    assert (row.status, row.entry_type, row.activity) == ("running", "workshop", "Dachdeckung")


def test_start_fuer_die_kolonne_wie_der_dialog(welt):  # noqa: F811
    _einsatz(welt, welt["order"], [(welt["heute"], welt["heute"] + timedelta(days=1))], [welt["mia"], welt["tom"]])
    r = _als(welt, welt["mia"]).post("/api/time-entry-groups/start", json={
        "employee_ids": [str(welt["mia"].id), str(welt["tom"].id)], "team_id": str(welt["team"].id), "order_id": str(welt["order"].id),
        "entry_type": "site", "activity": "Dachdeckung"})
    assert r.status_code == 200, r.text
    zeilen = welt["db"].scalars(select(TimeEntry).where(TimeEntry.status == "running")).all()
    assert sorted((z.employee_id, z.activity) for z in zeilen) == sorted([(welt["mia"].id, "Dachdeckung"), (welt["tom"].id, "Dachdeckung")])
    # Gegenprobe: Tom führt die Kolonne nicht -- 403 wie bisher
    tom = _als(welt, welt["tom"]).post("/api/time-entry-groups/start", json={
        "employee_ids": [str(welt["tom"].id)], "team_id": str(welt["team"].id), "order_id": str(welt["order"].id), "entry_type": "site"})
    assert tom.status_code in (403, 409), tom.text


def _stil() -> str:
    return re.sub(r"\s", "", "\n".join(re.findall(r"<style>(.*?)</style>", (vj.TEMPLATES / "mobil.html").read_text(encoding="utf-8"), flags=re.S)))


def test_kacheln_quer_drei_hoch_zwei():
    stil = _stil()
    assert ".kacheln{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));" in stil
    assert "@media(max-width:999px){.kacheln{grid-template-columns:repeat(2,minmax(0,1fr))}}" in stil
    assert "auto-fill" not in stil


def test_menue_und_dialog_auf_heute():
    stil, (text, _) = _stil(), vj.seitentext("mobil.html")
    assert vj.bindet_ein("mobil.html", "_menue.html")
    assert "dsMenue(el('startMenueKnopf'),el('startMenue'))" in text
    assert re.search(r"\.knopf-symbol\{width:48px;height:48px;", stil) and ".menue-anker.ds-menue-eintrag{height:48px;min-height:48px;" in stil
    assert ".dialog-karte.feldselect{height:52px}" in stil and ".dialog-knoepfe.knopf{height:56px;" in stil
    assert "url='/api/time-entry-groups/start'" in text and "url='/api/time-entries/start'" in text
    assert "if(z.taetigkeit_pflicht){startDialogOeffnen(z,'taetigkeit',b.dataset.zeitart);return}" in text
    # „⋮“ nur mit etwas zu wählen
    assert "if(!eintraege)return '';" in text
