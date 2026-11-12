"""Router: die Daten der Büroseite „Zeiten“ (seit 1.9.95, Stufe 4, R5b).

Nur lesen. Prüfen und Buchungen ab Büro – Auftrag (es liest die Zeiten aller, seit 1.9.89), Monat & Lohn nur mit den Lohndaten (Admin und
Büro – Finanzen, require_lohndaten). Geschrieben wird über die bestehenden Endpunkte (Zeiten, Pausen, Ende nachtragen, Abschluss, Anträge),
die ihre Rechte selbst prüfen; was das Konto davon darf, steht hier je Antwort unter „rechte“ und je Zeit unter „darf_…“ -- dieselben
Regeln wie dort (app/permissions.py), die Seite bietet nur das an."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..absence_requests import arten_fuer_auswahl, list_requests, request_to_dict
from ..arbeitszeitkonto import (KONTOBEGINN, OHNE_STARTWERT, STAND_KATEGORIEN, VORLAEUFIG, grenze_text, grenzen, grenzen_hinweise, gezaehlt_bis,
                                konten as arbeitszeitkonten, stand_danach)
from ..arbeitszeitkalender import naechste as naechste_kalendertage
from ..berlin_time import berlin_today
from ..database import get_db
from ..meldungen import KEIN_MITARBEITER
from ..models import AppUser, Employee
from ..lohndatei import LohndateiVeraendert
from ..lohndatei_abgleich import aenderungen_je_monat, nach_dem_versand
from ..lohnkonten import ERSTES_JAHR, standardjahr
from ..permissions import (LOHNDATEN_ROLLEN, ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, darf_abwesenheit_loeschen, darf_abwesenheiten_aller, darf_antrag_zurueckziehen, darf_konten_aller,
                           darf_lohndaten, darf_zeit_buchen, darf_zeit_fuer_andere_buchen, require_lohndaten, require_min_role, require_role)
from ..urlaubskonto import konten as urlaubskonten, rest_danach_je_antrag
from ..time_backoffice import locked_until
from ..schlechtwetter import SCHLECHTWETTER, ausfall
from ..sollzeit import abwesenheit_tage
from ..zeiten import buchungen, feiertage_bundesland, konto_hinweise, monat, monat_ende, monat_lesen, pruef_beginn, pruefen

router = APIRouter()

_buero_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Die Seite „Zeiten“ ist nur für das Büro."))
_lohn_dep = Depends(require_lohndaten)
# seit 1.9.321 (Lohn L2c-1, Antwort B11): das Arbeitszeitkonto sehen nur Admin und Büro – Finanzen -- dieselben Rollen wie die Lohndaten, eine eigene Meldung
_konto_dep = Depends(require_role(*LOHNDATEN_ROLLEN, message="Das Arbeitszeitkonto sehen nur Admin und Büro – Finanzen."))


def _rechte(user: AppUser) -> dict:
    return {"zeit_buchen": darf_zeit_buchen(user), "zeit_fuer_andere": darf_zeit_fuer_andere_buchen(user), "lohndaten": darf_lohndaten(user),
            "antraege_entscheiden": user.role == ROLE_ADMIN, "admin": user.role == ROLE_ADMIN}


def _monat(text: str | None):
    try:
        return monat_lesen(text, berlin_today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _darf_aendern(user: AppUser, employee_id: int, work_date, lock) -> bool:
    """Wie die Endpunkte der Zeiten: buchen darf das Konto (darf_zeit_buchen()), die Zeit ist die eigene oder es bucht für andere
    (app/routers/time_tracking.py::_time_entry_can_edit()), im abgeschlossenen Zeitraum nur der Admin (_require_open_period())."""
    if not darf_zeit_buchen(user):
        return False
    if not (darf_zeit_fuer_andere_buchen(user) or (user.employee_id is not None and user.employee_id == employee_id)):
        return False
    return user.role == ROLE_ADMIN or lock is None or work_date > lock


def _sichtbare_antraege(db: Session, user: AppUser, status: str | None):
    """Die Anträge, die das Konto sieht -- wie GET /api/absence-requests: seit 1.9.101 Admin und Büro – Finanzen alle (darf_abwesenheiten_aller(),
    bis 1.9.100 nur der Admin), sonst nur die eigenen, ohne Mitarbeiter keine."""
    if darf_abwesenheiten_aller(user):
        return list_requests(db, status=status)
    if user.employee_id is not None:
        return list_requests(db, employee_id=user.employee_id, status=status)
    return []


def _tage(db: Session, r, land: str):
    """Seit 1.9.171 (Lohn L1a, Punkt 6): Arbeitstage nach der Sollzeit der Person (app/sollzeit.py::abwesenheit_tage(): ohne Tage ohne Soll und
    gesetzliche Feiertage, ein halber Tag 0,5; 1.9.171–1.9.173 auch Urlaub am 24.12./31.12. je 0,5) -- bis 1.9.170 Montag bis Freitag ohne
    Feiertage für jeden gleich. Nur Anzeige."""
    from ..planning import automatic_public_holidays
    feiertage = automatic_public_holidays(land, range(r.start_date.year, r.end_date.year + 1))
    return abwesenheit_tage(db, r.employee_id, r.start_date, r.end_date, kategorie=r.absence_category, halber_tag=bool(r.halber_tag),
                            feiertage=feiertage, kalendertag_urlaub=r.kalendertag_urlaub)["tage"]  # seit 1.9.176 mit der Antwort zu Silvester


def _ausfall(db: Session, rows) -> dict:
    """Seit 1.9.216 (L1a Stufe 6, Punkt 5): je offenem oder genehmigtem Schlechtwetter-Antrag der Text seiner Stunden („Ausfall 6,00 h (Sollzeit
    8,00 h − gebucht 2,00 h)“, app/schlechtwetter.py::ausfall()) -- abgeleitet, eine Rechnung für die ganze Liste. {Antrag-ID: Text}."""
    sw = [r for r in rows if r.absence_category == SCHLECHTWETTER and r.status in ("pending", "approved")]
    stunden = ausfall(db, [(r.employee_id, r.start_date) for r in sw])
    return {r.id: stunden[(r.employee_id, r.start_date)]["text"] for r in sw}


def _antraege(db: Session, user: AppUser) -> list[dict]:
    """Die offenen Anträge, die das Konto sieht (_sichtbare_antraege()), mit Arbeitstagen (Feiertage nach dem Bundesland der Plantafel) und
    seit 1.9.216 bei Schlechtwetter den Stunden (ausfall)."""
    land = feiertage_bundesland(db)
    rows = _sichtbare_antraege(db, user, "pending")
    aus = _ausfall(db, rows)
    rest = rest_danach_je_antrag(db, rows)  # seit 1.9.316: „danach Rest n Tage“ an jedem offenen Antrag auf Urlaub (wer ihn sieht, sieht das Konto)
    stand = _konto_danach(db, user, rows)  # seit 1.9.337
    return [{**request_to_dict(db, r), "arbeitstage": _tage(db, r, land), "ausfall": aus.get(r.id), "rest_danach": rest.get(r.id),
             "konto_danach": stand.get(r.id)} for r in rows]


def _konto_danach(db: Session, user: AppUser, rows) -> dict:
    """Seit 1.9.337 (Lohn L2c-3, Punkt 4): je offenem Antrag auf Freizeitausgleich oder Unbezahlt „Stand vorläufig x h · danach y h“
    (app/arbeitszeitkonto.py::stand_danach()) -- nur für Admin und Büro – Finanzen (das Konto sehen nur sie, B11); sonst nichts, auch kein Schlüssel-Inhalt.
    {Antrag-ID: {stand, danach, reicht_nicht, text, hinweis}}."""
    if not darf_konten_aller(user):
        return {}
    ergebnis = {}
    for r in rows:
        if r.status == "pending" and r.absence_category in STAND_KATEGORIEN:
            s = stand_danach(db, r.employee_id, r.start_date, r.end_date)
            if s is not None:
                ergebnis[r.id] = s
    return ergebnis


def _anzahl(n: int, eins: str, mehr: str) -> str:
    return f"{n} {eins if n == 1 else mehr}"


@router.get("/api/zeiten/pruefen")
def zeiten_pruefen(request: Request, db: Session = Depends(get_db, scope="function"), user: AppUser = _buero_dep):
    """„Prüfen“: Zeiten von früher (je mit darf_schliessen), Tage mit unpassender Pause (je mit darf_buchen), offene Anträge, der Monat mit
    Stunden je Mitarbeiter und „Vor dem Abschluss“; dazu die Zahlen an den Reitern. Seit 1.9.322 die Hinweise zum Arbeitszeitkonto (konto)."""
    heute = berlin_today()
    daten = pruefen(db, heute)
    lock = locked_until(db)
    for z in daten["offene_zeiten"]:
        z["darf_schliessen"] = _darf_aendern(user, z["employee_id"], z["tag"], lock)
    for t in daten["pausen"]:
        t["darf_buchen"] = _darf_aendern(user, t["employee_id"], t["tag"], lock)
    for r in daten["rueckfahrten"]:  # seit 1.9.314: „Ändern“ an der Fahrzeit nach Arbeitsende -- zählt nicht am Reiter (nur ein Hinweis)
        r["darf_aendern"] = _darf_aendern(user, r["employee_id"], r["tag"], lock)
    daten["antraege"] = _antraege(db, user)
    # seit 1.9.322 (Lohn L2c-1, Punkt 2): die Hinweise zum Arbeitszeitkonto -- nur Admin und Büro – Finanzen (wie das Konto, Antwort B11; sie nennen Urlaub
    # und Krankheit, die Büro – Auftrag nur bei sich selbst sieht); nur Hinweise, sie zählen nicht am Reiter
    daten["konto"] = (konto_hinweise(db, pruef_beginn(db, heute), heute) if darf_konten_aller(user)
                      else {"ohne_eintrag": [], "arbeit_bei_abwesenheit": []})
    # seit 1.9.331 (Lohn L2c-2, Punkt 4): je Monat die Zahl der Änderungen nach dem Versand -- ohne Namen, nur Admin und Büro – Finanzen (die Liste dahinter
    # sehen nur sie); nur ein Hinweis, zählt nicht am Reiter
    daten["nach_dem_versand"] = aenderungen_je_monat(db, heute) if darf_lohndaten(user) else []
    # seit 1.9.336 (Lohn L2c-3, Punkt 3): Stand an einer Grenze des Kontos -- nur Admin und Büro – Finanzen (wie das Konto, B11); nur ein Hinweis
    daten["konto_grenzen"] = grenzen_hinweise(db, heute) if darf_konten_aller(user) else []
    # seit 1.9.101: „Vor dem Abschluss“ nennt die offenen Anträge, die das Konto sieht; „Anträge entschieden“ nur, wenn keiner offen ist
    # (auch keiner, den das Konto nicht sieht -- Büro – Auftrag sieht nur die eigenen)
    if daten["antraege"]:
        daten["vor_dem_abschluss"].append({"art": "antraege", "text": _anzahl(len(daten["antraege"]), "Antrag offen", "Anträge offen")})
    daten["antraege_entschieden"] = not list_requests(db, status="pending")
    daten["rechte"] = _rechte(user)
    # seit 1.9.102 (Nachrunde, Punkt 4): die Zahl am Reiter „Prüfen“ zählt nur, was auf dieses Konto wartet -- Zeiten von früher, deren Ende es
    # eintragen darf, und Tage, deren Pause es buchen darf; Büro – Auftrag (liest nur) bekommt keine Zahl (bis 1.9.101 alle). Seit 1.9.109
    # (Nachrunde 2, Punkt 3) ebenso „Abwesenheiten“: offene Anträge warten nur auf den Admin (er entscheidet sie), Büro – Finanzen und Büro – Auftrag
    # bekommen keine Zahl (1.9.101–1.9.108 die offenen Anträge, die das Konto sieht); „Vor dem Abschluss“ nennt sie weiter (oben)
    daten["zahlen"] = {"pruefen": sum(1 for z in daten["offene_zeiten"] if z["darf_schliessen"]) + sum(1 for t in daten["pausen"] if t["darf_buchen"]),
                       "abwesenheiten": len(daten["antraege"]) if daten["rechte"]["antraege_entscheiden"] else 0}
    return daten


@router.get("/api/zeiten/urlaubskonto")
def zeiten_urlaubskonto(jahr: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db, scope="function"), user: AppUser = _buero_dep):
    """Seit 1.9.315 (Lohn L2b, Punkt 3): das Urlaubskonto im Jahr (Vorgabe: das laufende, frühestens 2027) -- Admin und Büro – Finanzen alle
    (darf_konten_aller()), sonst nur das eigene (ohne Mitarbeiter keins). Vor 2027 422."""
    jahr = jahr or standardjahr()
    ids = None if darf_konten_aller(user) else ([user.employee_id] if getattr(user, "employee_id", None) else [])
    try:
        liste = urlaubskonten(db, jahr, ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # seit 1.9.316: die wählbaren Jahre -- ab 2027 bis ein Jahr nach dem laufenden (und das gewählte)
    jahre = sorted(set(range(ERSTES_JAHR, standardjahr() + 2)) | {jahr})
    return {"jahr": jahr, "erstes_jahr": ERSTES_JAHR, "jahre": jahre, "konten": [k.als_dict() for k in liste]}


@router.get("/api/zeiten/arbeitszeitkonto")
def zeiten_arbeitszeitkonto(monat_: str | None = Query(None, alias="monat", max_length=7), mitarbeiter: int | None = None,
                            db: Session = Depends(get_db, scope="function"), user: AppUser = _konto_dep):
    """Seit 1.9.321 (Lohn L2c-1, Punkt 1; seit 1.9.323 eine Vorschau: „vorläufig – maßgeblich ist die Lohnabrechnung“, vorlaeufig): das Arbeitszeitkonto eines Monats (Vorgabe: der laufende, frühestens Januar 2027) -- je gewerblicher Person
    die Tage (Soll, Arbeit, Gutschrift, Saldo, Posten), der Monat und der Stand ab dem Startwert (app/arbeitszeitkonto.py), gezählt bis gestern. Nur
    lesend, nur Admin und Büro – Finanzen (Antwort B11 -- „Meine Zeiten“ erst mit L2c-4, auch nicht über diese Schnittstelle); mitarbeiter: nur diese
    Person. Vor Januar 2027 422."""
    heute = berlin_today()
    erster = _monat(monat_) if monat_ else max(heute.replace(day=1), KONTOBEGINN)
    if erster < KONTOBEGINN:
        raise HTTPException(status_code=422, detail=f"Das Arbeitszeitkonto beginnt am {KONTOBEGINN:%d.%m.%Y}.")
    ende = monat_ende(erster)
    liste = arbeitszeitkonten(db, erster, ende, None if mitarbeiter is None else [mitarbeiter], heute=heute)
    plus, minus = grenzen(db)  # seit 1.9.336: der Hinweis an der Person -- am Stand am Ende des Monats (bzw. bis gestern), ohne Startwert keiner
    return {"monat": erster.strftime("%Y-%m"), "kontobeginn": KONTOBEGINN, "gezaehlt_bis": min(ende, gezaehlt_bis(heute)), "vorlaeufig": True,
            "hinweis": VORLAEUFIG, "grenzen": {"plus": plus, "minus": minus},
            "konten": [{**k.als_dict(), "grenze": None if OHNE_STARTWERT in k.hinweise else grenze_text(k.stand, plus, minus)} for k in liste]}


# Seit 1.9.337 (Lohn L2c-3, Punkt 4): beim Stellen eines Antrags auf Freizeitausgleich oder Unbezahlt „Stand vorläufig x h · danach y h“ -- nur Admin und
# Büro – Finanzen (wie das Konto, B11; die Monteurin bekommt hier 403, „Meine Zeiten“ zeigt den Stand erst mit L2c-4). Ohne Konto (keine gewerbliche Person,
# ganz vor dem Kontobeginn) null.
@router.get("/api/zeiten/konto-danach")
def zeiten_konto_danach(employee_id: int, von: date, bis: date, db: Session = Depends(get_db, scope="function"), user: AppUser = _konto_dep):
    if bis < von:
        raise HTTPException(status_code=422, detail="Bis liegt vor Von.")
    return stand_danach(db, employee_id, von, bis)


@router.get("/api/zeiten/buchungen")
def zeiten_buchungen(request: Request, monat_: str | None = Query(None, alias="monat"), mitarbeiter: int | None = None, auftrag: int | None = None,
                     zeitart: str | None = Query(None, max_length=40), zeitraum: str | None = Query(None, max_length=10),
                     db: Session = Depends(get_db, scope="function"), user: AppUser = _buero_dep):
    """„Buchungen“ eines Monats nach den Filtern, mit der „Summe der Auswahl“; je Buchung darf_aendern (Ändern und Löschen). Seit 1.9.128
    (Befund L3) zeitraum=alle: alle Monate eines Auftrags (ohne Auftrag 422)."""
    if zeitraum not in (None, "", "monat", "alle"):
        raise HTTPException(status_code=422, detail="Unbekannter Zeitraum.")
    try:
        daten = buchungen(db, _monat(monat_), employee_id=mitarbeiter, order_id=auftrag, entry_type=zeitart or None, alle_monate=zeitraum == "alle")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lock = locked_until(db)
    for e in daten["eintraege"]:
        e["darf_aendern"] = e["status"] == "booked" and _darf_aendern(user, e["employee_id"], e["work_date"], lock)
        e["darf_schliessen"] = e["laeuft_seit_frueher"] and _darf_aendern(user, e["employee_id"], e["work_date"], lock)
    daten["rechte"] = _rechte(user)
    return daten


NUR_EIGENE_ANTRAEGE = "Hier stehen nur deine eigenen Anträge – die Anträge aller sehen Admin und Büro – Finanzen."
ANTRAG_STATUS = ("pending", "approved", "rejected", "cancelled")


@router.get("/api/zeiten/abwesenheiten")
def zeiten_abwesenheiten(status: str | None = Query(None, max_length=20), db: Session = Depends(get_db, scope="function"),
                         user: AppUser = _buero_dep):
    """Seit 1.9.97 (Stufe 4, R5b, Punkt 5): „Abwesenheiten“ -- seit 1.9.101 (Nachrunde, Punkt 1) sehen Admin und Büro – Finanzen alle Anträge
    und stellen sie auch für andere, Büro – Auftrag nur die eigenen (ohne Mitarbeiter keine, mit Hinweis); je Antrag Arbeitstage,
    darf_entscheiden (nur der Admin, offen), darf_zurueckziehen (offen und von diesem Konto gestellt -- darf_antrag_zurueckziehen()).
    1.9.97–1.9.100 sah und beantragte für andere nur der Admin."""
    if status and status not in ANTRAG_STATUS:
        raise HTTPException(status_code=422, detail="Unbekannter Status.")
    admin = user.role == ROLE_ADMIN
    aller = darf_abwesenheiten_aller(user)
    rows = _sichtbare_antraege(db, user, status or None)
    land = feiertage_bundesland(db)
    aus = _ausfall(db, rows)
    rest = rest_danach_je_antrag(db, rows)  # seit 1.9.316
    stand = _konto_danach(db, user, rows)  # seit 1.9.337
    # offene Anträge, die das Konto sieht (seit 1.9.109 nicht mehr die Zahl am Reiter -- die zählt nur beim Admin, GET /api/zeiten/pruefen)
    offen = len(_sichtbare_antraege(db, user, "pending"))
    return {
        "antraege": [{**request_to_dict(db, r), "arbeitstage": _tage(db, r, land), "ausfall": aus.get(r.id), "rest_danach": rest.get(r.id),  # seit 1.9.216, 1.9.316
                      "konto_danach": stand.get(r.id),  # seit 1.9.337
                      "darf_entscheiden": admin and r.status == "pending",
                      "darf_zurueckziehen": r.status == "pending" and darf_antrag_zurueckziehen(user, r),
                      "darf_loeschen": r.status == "approved" and r.approved_absence_id is not None and darf_abwesenheit_loeschen(user)}  # seit 1.9.146
                     for r in rows],
        "hinweis": None if aller else (NUR_EIGENE_ANTRAEGE if user.employee_id is not None else KEIN_MITARBEITER),
        "darf_beantragen": aller or user.employee_id is not None, "fuer_andere": aller, "eigener_mitarbeiter": user.employee_id,
        "mitarbeiter": [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip(), "employee_number": e.employee_number}
                        for e in db.query(Employee).filter(Employee.active == True).order_by(Employee.last_name, Employee.first_name)]  # noqa: E712
        if aller else [],
        "arten": arten_fuer_auswahl(db),
        "offen": offen,
        # seit 1.9.171 (Lohn L1a, Punkt 6, E9): Kolonnen mit ihren aktiven Mitgliedern für den Sammeleintrag -- nur, wer für andere einträgt
        "kolonnen": _kolonnen(db) if aller else [],
        # seit 1.9.175 (L1a-Nachtrag, Punkt 2): die nächsten Tage des Arbeitszeitkalenders -- ihre Abwesenheit gilt von selbst, ohne Antrag
        "kalender": naechste_kalendertage(db, berlin_today()),
    }


def _kolonnen(db: Session) -> list[dict]:
    from sqlalchemy import select
    from ..models import Team, TeamEmployee
    je: dict[int, dict] = {}
    for tid, name, eid in db.execute(select(Team.id, Team.name, TeamEmployee.employee_id).join(TeamEmployee, TeamEmployee.team_id == Team.id)
                                     .join(Employee, Employee.id == TeamEmployee.employee_id)
                                     .where(Team.active.is_(True), Employee.active.is_(True)).order_by(Team.name, Team.id)):
        je.setdefault(tid, {"id": tid, "name": name, "mitglieder": []})["mitglieder"].append(eid)
    return list(je.values())


@router.get("/api/zeiten/monat")
def zeiten_monat(monat_: str | None = Query(None, alias="monat"), db: Session = Depends(get_db, scope="function"), user: AppUser = _lohn_dep):
    """„Monat & Lohn“ -- nur mit den Lohndaten (Admin und Büro – Finanzen)."""
    return {**monat(db, _monat(monat_)), "rechte": _rechte(user)}


# Seit 1.9.329 (Lohn L2c-2, Punkt 2): „Nach dem Versand geändert“ -- wie „Monat & Lohn“ nur mit den Lohndaten; schreibt nichts
@router.get("/api/zeiten/nach-dem-versand")
def zeiten_nach_dem_versand(monat_: str | None = Query(None, alias="monat"), db: Session = Depends(get_db, scope="function"), user: AppUser = _lohn_dep):
    try:
        return nach_dem_versand(db, _monat(monat_))
    except LohndateiVeraendert as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
