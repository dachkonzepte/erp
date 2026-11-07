"""Version 1.9.247 (Stufe 6, R4, Punkt 1): die Tafel „Kolonnen“ nach bildgrundlage/entwurf-stufe6/plantafel-kolonnen.html.

    Daten        GET /api/planning: je Mitglied einer Kolonne Vorname und Kolonnenführer (kf), je Gerät die nächste Prüfung („UVV gültig bis 03/2027“,
                 abgelaufen „fällig seit …“) und ob es einen Kalender hat; die Termine direkt im Kalender eines Geräts (nicht die der Einsätze, privat
                 „Belegt“); Zähler „Warnungen · Hinweise“ -- ein Paar (Person oder Gerät doppelt) zählt einmal
    Seite        umgezogen (Seitenkopf, ds-seite); Zeilen je Kolonne, „Ohne Kolonne“ immer (auch leer), darunter die Geräte nach Namen; eine Kranvermietung
                 steht in der Zeile ihres Geräts, nicht in „Ohne Kolonne“; was sich überschneidet, steht in eigenen Spuren untereinander; 14 Tage passen
                 in die Breite (Sa/So schmal); der title jedes Balkens beginnt mit seinem Text
Im Browser misst scripts/klicktest_plantafel_tafel.py (Zeichnung nachgestellt, Überdeckung, gekürzte Texte, 1440/1280, hell/dunkel).
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models import CalendarEvent, EnabledModule, OperationalAsset, OperationalAssetInspection, OperationalResource, OutlookSeriesOccurrence, TeamEmployee
from app.planning import create_slot, planning_board, tafel_zaehler, termin_tage
from tests.test_v090_planning_board import setup_order
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.test_v634_geraete_je_einsatz import _geraet

MO = date(2026, 11, 2)
D = Decimal


def _welt(db):
    tom, mia, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Mia"), _person(db, "M-3", "Kai")
    nord = _kolonne(db, "Nord", [tom, mia])
    db.query(TeamEmployee).filter_by(team_id=nord.id, employee_id=tom.id).update({"is_crew_leader": True})
    kran = _geraet(db, "K-1", "Kran")
    db.commit()
    return {"tom": tom, "mia": mia, "kai": kai, "nord": nord, "kran": kran}


def test_kolonne_nennt_vornamen_und_kolonnenfuehrer(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    [team] = planning_board(db, MO, MO + timedelta(days=13))["teams"]
    assert [(e["vorname"], e["kf"]) for e in team["employees"]] == [("Tom", True), ("Mia", False)]


def test_geraet_mit_pruefung_und_kalender(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    asset = OperationalAsset(resource_id=w["kran"])
    db.add(asset); db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=date(2027, 3, 31)))
    db.get(OperationalResource, w["kran"]).outlook_mailbox = "kran@example.invalid"
    db.commit()
    [r] = [x for x in planning_board(db, MO, MO + timedelta(days=13))["resources"] if x["id"] == w["kran"]]
    assert (r["pruefung"], r["kalender"]) == ("UVV gültig bis 03/2027", True)
    db.query(OperationalAssetInspection).update({"next_due_date": date(2026, 10, 30)})
    db.commit()
    [r] = [x for x in planning_board(db, MO, MO + timedelta(days=13))["resources"] if x["id"] == w["kran"]]
    assert r["pruefung"] == "UVV fällig seit 30.10.2026"  # abgelaufen am Tag der App-Uhr (feste Testwelt ab 2026)
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()
    [r] = [x for x in planning_board(db, MO, MO + timedelta(days=13))["resources"] if x["id"] == w["kran"]]
    assert r["pruefung"] is None  # ohne Betriebsmittelverwaltung pflegt niemand die Fristen


def test_termine_am_geraet_ohne_die_der_einsaetze(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    order = setup_order(db, "1")
    slot = create_slot(db, order_id=order.id, team_id=None, employee_ids=[w["tom"].id], start_date=MO, end_date=MO, planned_hours=D("1"),
                       geraete=[{"resource_id": w["kran"]}], trotzdem_planen=True)
    kran = w["kran"]
    db.add_all([
        CalendarEvent(title="Müller", start_at=datetime(2026, 11, 10), end_at=datetime(2026, 11, 11), all_day=True, resource_id=kran, external_source="outlook"),
        CalendarEvent(title="Geheim", start_at=datetime(2026, 11, 4, 8), end_at=datetime(2026, 11, 4, 12), resource_id=kran, is_private=True,
                      external_source="outlook"),
        CalendarEvent(title="Einsatz", start_at=datetime(2026, 11, 2), end_at=datetime(2026, 11, 2), all_day=True, resource_id=kran, planning_slot_id=slot.id),
        CalendarEvent(title="Später", start_at=datetime(2026, 12, 1), end_at=datetime(2026, 12, 1), all_day=True, resource_id=kran, external_source="outlook"),
        OutlookSeriesOccurrence(title="Wartung Kran", start_at=datetime(2026, 11, 6, 7), end_at=datetime(2026, 11, 6, 9), resource_id=kran,
                                outlook_postfach="kran@example.invalid", outlook_event_id="s-1", occurrence_type="occurrence"),
    ])
    db.commit()
    termine = planning_board(db, MO, MO + timedelta(days=13))["geraete_termine"]
    assert [(t["titel"], t["von"], t["bis"], t["zeit"], t["uebernehmbar"]) for t in termine] == [
        ("Belegt", date(2026, 11, 4), date(2026, 11, 4), "08:00", True),
        ("Müller", date(2026, 11, 10), date(2026, 11, 11), None, True),
        ("Wartung Kran", date(2026, 11, 6), date(2026, 11, 6), "07:00", False),
    ]


def test_abwesenheiten_genehmigt_freistellung_beantragt(threaded_db_session, router_test_client):
    """Je Person die Zeiträume im Bild: genehmigt, Freistellung (Heiligabend, aus dem Arbeitszeitkalender) und offener Antrag; Büro – Auftrag ohne Art."""
    from app.models import EmployeeAbsence, EmployeeAbsenceRequest
    from app.routers.planning import router as planning_router
    db = threaded_db_session
    mia, tom = _person(db, "M-1", "Mia"), _person(db, "M-2", "Tom")
    _kolonne(db, "Nord", [mia, tom])
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Krankheit", absence_category="krankheit", start_date=date(2026, 12, 21),
                           end_date=date(2026, 12, 22)))
    db.add(EmployeeAbsenceRequest(employee_id=tom.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 12, 28),
                                  end_date=date(2026, 12, 29), status="pending"))
    db.commit()
    von, bis = date(2026, 12, 21), date(2027, 1, 3)
    liste = planning_board(db, von, bis)["abwesenheiten"]
    assert sorted((a["employee_id"], a["art"], a["stand"], a["von"], a["bis"]) for a in liste) == sorted([
        (mia.id, "Krankheit", "genehmigt", date(2026, 12, 21), date(2026, 12, 22)),
        (mia.id, "Heiligabend", "frei", date(2026, 12, 24), date(2026, 12, 24)), (tom.id, "Heiligabend", "frei", date(2026, 12, 24), date(2026, 12, 24)),
        (mia.id, "Silvester", "frei", date(2026, 12, 31), date(2026, 12, 31)), (tom.id, "Silvester", "frei", date(2026, 12, 31), date(2026, 12, 31)),
        (tom.id, "Urlaub", "beantragt", date(2026, 12, 28), date(2026, 12, 29))])
    for rolle, mit_art in (("buero_auftrag", False), ("buero_finanzen", True), ("admin", True)):
        tafel = router_test_client(db, planning_router, role=rolle).get(f"/api/planning?start={von}&end={bis}").json()
        assert {a["art"] is not None for a in tafel["abwesenheiten"]} == {mit_art}, rolle
        assert ("Krankheit" in json.dumps(tafel)) is mit_art, rolle


def test_termin_tage():
    class T:
        def __init__(self, a, b, ganz=False):
            self.start_at, self.end_at, self.all_day = a, b, ganz
    assert termin_tage(T(datetime(2026, 11, 10), datetime(2026, 11, 11), True)) == (date(2026, 11, 10), date(2026, 11, 11))
    assert termin_tage(T(datetime(2026, 11, 10, 8), datetime(2026, 11, 12))) == (date(2026, 11, 10), date(2026, 11, 11))  # bis Mitternacht
    assert termin_tage(T(datetime(2026, 11, 10, 8), datetime(2026, 11, 10, 9))) == (date(2026, 11, 10), date(2026, 11, 10))


def test_zaehler_ein_paar_zaehlt_einmal(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    a, b = setup_order(db, "1"), setup_order(db, "2")
    for o in (a, b):
        create_slot(db, order_id=o.id, team_id=None, employee_ids=[w["kai"].id], start_date=MO, end_date=MO + timedelta(days=1), planned_hours=D("1"),
                    trotzdem_planen=True)
    tafel = planning_board(db, MO, MO + timedelta(days=13))
    assert sum(1 for s in tafel["slots"] for k in s["conflicts"] if k["stufe"] == "warnung") == 2  # je Einsatz einmal
    assert tafel["zaehler"] == {"warnungen": 1, "hinweise": 0}
    hinweis = {"id": 9, "conflicts": [{"type": "antrag_offen", "stufe": "hinweis", "label": "Kai", "other_slot_id": None, "date": MO}]}
    assert tafel_zaehler(tafel["slots"] + [hinweis]) == {"warnungen": 1, "hinweise": 1}


# --- Seite (node) ---------------------------------------------------------------------------------------------------------------------

ESC = ("function esc(s){return String(s==null?'':s).replace(/[&<>'\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;',"
       "\"'\":'&#39;','\"':'&quot;'}[c]})}")


def _slot(i, team, von, bis, **mehr):
    return {"id": i, "team_id": team, "start_date": von, "end_date": bis, "art": "baustelle", "art_label": "Baustelle", "status": "fest",
            "status_label": "fest", "project_number": f"P-{i}", "project_name": f"Dach {i}", "customer_name": "Kunde", "employees": [],
            "resources": [], "conflicts": [], "order_status": "laeuft", **mehr}


@nur_mit_node
def test_spuren_und_geometrie():
    aufrufe = im_browser("planning.html", ["spurenVerteilen", "istWochenende", "geometrie"], ESC + ";const LABEL_W=168,WE_W=22,MIN_TAG=44;"
                         "document.getElementById=()=>({clientWidth:879});",
                         "const it=[{i:0,j:4},{i:1,j:3},{i:5,j:6},{i:2,j:2}];const n=spurenVerteilen(it);"
                         "AUFRUFE.push({n,spuren:it.map(x=>x.spur)});"
                         "const tage=Array.from({length:14},(_,k)=>{const d=new Date(Date.UTC(2026,10,2+k));return d.toISOString().slice(0,10)});"
                         "const g=geometrie(tage);AUFRUFE.push({breite:g.breite,we:g.spalten.filter(c=>c.w===22).length,tag:g.spalten[0].w});")
    spuren, geo = aufrufe
    assert spuren == {"n": 3, "spuren": [0, 1, 0, 2]}  # der dritte überschneidet beide ersten, der vierte (Tag 5) passt in Spur 0
    assert geo["we"] == 4 and geo["tag"] == 62 and geo["breite"] <= 879 - 168  # 14 Tage passen in die Tafel der Zeichnung (879 px)


@nur_mit_node
def test_zeilen_der_kolonnen():
    board = {"teams": [{"id": 1, "name": "Nord", "employees": [{"id": 11, "name": "Tom Test", "vorname": "Tom", "kf": True},
                                                                 {"id": 12, "name": "Mia Test", "vorname": "Mia", "kf": False}]}],
             "employees": [{"id": 11, "name": "Tom Test", "vorname": "Tom"}, {"id": 12, "name": "Mia Test", "vorname": "Mia"}],
             "resources": [{"id": 2, "name": "Pritsche", "type": "Fahrzeug", "pruefung": None, "kalender": False},
                           {"id": 1, "name": "Kran", "type": "Maschine", "pruefung": "UVV gültig bis 03/2027", "kalender": True}],
             "abwesenheiten": [{"employee_id": 11, "art": "Urlaub", "stand": "genehmigt", "von": "2026-10-30", "bis": "2026-11-06"},
                               {"employee_id": 12, "art": "Urlaub", "stand": "beantragt", "von": "2026-11-05", "bis": "2026-11-06"}],
             "slots": [_slot(5, None, "2026-11-04", "2026-11-05", art="kranvermietung", art_label="Kranvermietung",
                             employees=[{"id": 13, "name": "Lia Test", "vorname": "Lia"}], resources=[{"id": 1, "name": "Kran", "tage": None}])],
             "geraete_termine": []}
    vorbereitung = (ESC + f";let board={json.dumps(board)};let view='teams';let filterAn=false;"
                    "const geo={spalten:Array.from({length:14},(_,k)=>({d:new Date(Date.UTC(2026,10,2+k)).toISOString().slice(0,10)}))};"
                    "function fmt(s){const t=String(s).slice(0,10).split('-');return t[2]+'.'+t[1]+'.'}"
                    "function addDays(s,n){const d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}")
    aufrufe = im_browser("planning.html", ["fmtSpanne", "vornamen", "einsatzTitel", "slotHinweis", "einsatzBalken", "mitgliederText", "abwesendText",
                                           "abwesenheitItems", "geraeteSortiert", "geraetUnter", "geraetFolgen", "geraetItems", "zeilen"],
                         vorbereitung + ";const KONFLIKT_ART={};",
                         "AUFRUFE.push({z:zeilen().map(z=>z.abschnitt?['['+z.abschnitt+']']:[z.name,z.unter,z.items.map(i=>i.b.text+(i.b.leise?' · '+i.b.leise:''))])});")
    [z] = aufrufe
    assert z["z"] == [
        ["Nord", ["Tom (KF), Mia", "Tom Urlaub 02.–06.11."], []],  # ein Antrag (Mia) steht nicht in der Zeile der Kolonne
        ["Ohne Kolonne", ["Personen einzeln gewählt"], []],  # immer, auch leer -- die Kranvermietung steht in der Zeile ihres Geräts
        ["[Geräte]"],
        ["Kran", ["UVV gültig bis 03/2027", "mit Outlook-Kalender"], ["Vermietung · Lia"]],
        ["Pritsche", ["Fahrzeug"], []],
    ]


@nur_mit_node
def test_geraet_an_einzelnen_tagen_je_folge():
    vorbereitung = ("function addDays(s,n){const d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}")
    aufrufe = im_browser("planning.html", ["geraetFolgen"], vorbereitung,
                         "const s={start_date:'2026-11-02',end_date:'2026-11-13'};"
                         "AUFRUFE.push({alle:geraetFolgen(s,{tage:null}),einzeln:geraetFolgen(s,{tage:['2026-11-06','2026-11-02','2026-11-03','2026-11-13']})});")
    [f] = aufrufe
    assert f["alle"] == [["2026-11-02", "2026-11-13"]]
    assert f["einzeln"] == [["2026-11-02", "2026-11-03"], ["2026-11-06", "2026-11-06"], ["2026-11-13", "2026-11-13"]]  # je Folge ein Balken


def test_seitenkopf_mit_einsatz_und_menue():
    """Seitenkopf nach der Zeichnung: „+ Einsatz“ als Hauptaktion, im Menü „Abwesenheit eintragen“, „Kranvermietung anlegen“ (bis zum Dialog, Punkt 4,
    ausgeblendet) und „Einstellungen der Planung“; Leiste mit Zeitraum, Ansicht und Filter."""
    import re
    from tests import vorlagen_js as vj
    eigen = (vj.TEMPLATES / "planning.html").read_text(encoding="utf-8")
    kopf = re.search(r"\{% call\(teil\) seitenkopf\((.*?)\{% endcall %\}", eigen, flags=re.S).group(0)
    assert '"Plantafel", untertitel="Wer ist wann wo – Einsätze, Kran und Geräte, Abwesenheiten"' in kopf
    assert 'id="neuerEinsatz"' in kopf and ">Einsatz</button>" in kopf
    assert re.findall(r'class="ds-menue-eintrag"[^>]*>([^<]+)<', kopf) == ["Abwesenheit eintragen", "Kranvermietung anlegen", "Einstellungen der Planung"]
    assert 'href="/settings#planning"' in kopf
    leiste = re.search(r'<div class="leiste".*?</div>\n<div class="ds-status"', eigen, flags=re.S).group(0)
    assert [x for x in re.findall(r'<option value="(\d+)">', leiste)] == ["14", "21", "28"]
    assert re.findall(r'data-view="(\w+)"[^>]*>(\w+)<', leiste) == [("teams", "Kolonnen"), ("employees", "Personen"), ("resources", "Geräte")]
    assert 'id="filterKnopf"' in leiste


@nur_mit_node
def test_schulferien_nur_zur_anzeige():
    """Wie bis 1.9.246: Schulferien tönen Kopf und Zellen der Arbeitstage und stehen im title des Tags; keine Wirkung auf Kapazität oder Konflikte."""
    board = {"holidays": [], "school_holidays": [{"name": "Herbstferien", "start_date": "2026-11-03", "end_date": "2026-11-04"}]}
    vorbereitung = (ESC + f";let board={json.dumps(board)};"
                    "const geo={spalten:['2026-11-02','2026-11-03','2026-11-04'].map((d,i)=>({d,x:i*60,w:60})),breite:180};"
                    "function fmt(s){const t=String(s).slice(0,10).split('-');return t[2]+'.'+t[1]+'.'}function fmtJahr(s){return fmt(s)+String(s).slice(0,4)}"
                    "function berlinToday(){return '2026-11-02'}function wochentag(s){return 'Di'}function kalenderwoche(){return 45}")
    aufrufe = im_browser("planning.html", ["istWochenende", "feiertagAm", "schoolAt", "zellenHtml", "kopfHtml"], vorbereitung,
                         "AUFRUFE.push({z:zellenHtml(),k:kopfHtml()});")
    [r] = aufrufe
    assert r["z"].count("school-holiday") == 2 and r["k"].count("school-holiday") == 2
    assert "Herbstferien" in r["k"]
