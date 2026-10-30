"""Prüfung: wie steht der Outlook-Abgleich? (seit 1.9.142, Stufe 6, R1, Punkt 0)

Keine Seite zeigt den Stand des Abgleichs (Befund Stufe 6, 5.2 und L9). Das Skript nennt:

    je Postfach     letzter Lauf, letzter Fehler (nur die Art, wie im Protokoll), Alter des Delta-Links, wohin der Link zeigt
    warten          Termine, die auf Senden warten (dieselbe Prüfung wie der Abgleich: app/outlook_calendar_sync.py::_needs_push())
    doppelt         Outlook-Kennungen, die mehrere Termine tragen
    ganztägig       ganztägige Termine aus dem ERP -- nach der Doku von Microsoft braucht „isAllDay“ Beginn und Ende um Mitternacht der Zeitzone
                    der Anfrage; das ERP schickt UTC (Befund Stufe 6, 5.4)

Das Alter des Delta-Links ist die Zeit seit dem letzten erfolgreichen Lauf: nur der schreibt den Link (sync_user_calendar()). Der Pfad des
Links zeigt nach einem Wechsel des Postfachs auf das alte (Befund, XC1); Microsoft kann die Adresse darin durch eine Kennung ersetzen, das
Skript sagt deshalb nur, dass der Pfad das Postfach nicht nennt. Das Token im Link druckt es nie.

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_outlook.py

Nur lesen wie scripts/pruefe_stornos.py (schreibgeschützte Sitzung, am Ende zurückgerollt), keine Anfrage an Microsoft. Ohne Inhalt der Termine
(Regel 18): nur Kennung, Besitzer, Tag. Rückgabe: 0 nichts gefunden, 1 etwas gefunden (Fehler, wartende, doppelte oder ganztägige Termine), 2
Umgebung fehlt.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from pruefe_stornos import nur_lesende_sitzung  # noqa: E402


def _zeit(wert: datetime | None) -> str:
    """Gespeicherte Zeitstempel sind naives UTC (Regel 20)."""
    if wert is None:
        return "—"
    from app.berlin_time import to_berlin

    return to_berlin(wert).strftime("%d.%m.%Y %H:%M")


def _alter(wert: datetime | None, jetzt: datetime) -> str:
    if wert is None:
        return "—"
    stunden = max(0, int((jetzt - wert).total_seconds() // 3600))
    if stunden < 48:
        return f"{stunden} h"
    return f"{stunden // 24} Tage"


def _delta_pfad(link: str | None) -> str:
    """Nur der Pfad -- die Abfrage trägt das Token."""
    return unquote(urlsplit(link).path) if link else ""


def _besitzer(user) -> str:
    if user is None:
        return "unbekanntes Konto"
    return user.username + (f" ({user.outlook_mailbox})" if user.outlook_mailbox else " (kein Postfach)")


def pruefen(db, *, jetzt: datetime | None = None) -> dict:
    """Der Stand des Abgleichs -- liest nur, fragt Microsoft nicht."""
    from app.models import AppUser, CalendarEvent, OutlookCalendarSyncState, OutlookSyncSettings
    from app.outlook_calendar_sync import _needs_push

    jetzt = jetzt or datetime.utcnow()
    einstellung = db.get(OutlookSyncSettings, 1)
    konten = {u.id: u for u in db.scalars(select(AppUser))}
    staende = {s.app_user_id: s for s in db.scalars(select(OutlookCalendarSyncState))}
    termine = list(db.scalars(select(CalendarEvent).order_by(CalendarEvent.id)))

    postfaecher = []
    for user in sorted((u for u in konten.values() if u.outlook_mailbox), key=lambda u: u.username):
        stand = staende.get(user.id)
        pfad = _delta_pfad(stand.delta_link if stand else None)
        postfaecher.append({
            "konto": user.username, "postfach": user.outlook_mailbox, "aktiv": bool(user.active),
            "letzter_lauf": stand.last_synced_at if stand else None,
            "fehler": stand.last_error_type if stand else None, "fehler_am": stand.last_error_at if stand else None,
            "delta_link": bool(stand and stand.delta_link),
            "delta_alter": _alter(stand.last_synced_at, jetzt) if stand and stand.delta_link else "—",
            "delta_pfad": pfad,
            "pfad_nennt_postfach": not pfad or user.outlook_mailbox.casefold() in pfad.casefold(),
        })

    warten, ganztaegig = [], []
    kennungen = defaultdict(list)
    for t in termine:
        user = konten.get(t.owner_user_id)
        if user is not None and user.outlook_mailbox and _needs_push(t):
            warten.append({"id": t.id, "besitzer": _besitzer(user), "tag": t.start_at.date(),
                           "grund": "noch nie gesendet" if t.outlook_event_id is None else "im ERP geändert"})
        if t.outlook_event_id:
            kennungen[t.outlook_event_id].append(t)
        if t.all_day and (t.external_source or "erp") == "erp":
            ganztaegig.append({"id": t.id, "besitzer": _besitzer(user), "tag": t.start_at.date(), "bis": t.end_at.date(),
                               "gesendet": bool(t.outlook_event_id)})
    doppelt = [{"kennung": k[:24] + ("…" if len(k) > 24 else ""), "termine": [t.id for t in zeilen],
                "besitzer": sorted({_besitzer(konten.get(t.owner_user_id)) for t in zeilen})}
               for k, zeilen in kennungen.items() if len(zeilen) > 1]
    return {"eingeschaltet": bool(einstellung and einstellung.enabled), "postfaecher": postfaecher, "warten": warten,
            "doppelt": doppelt, "ganztaegig": ganztaegig}


def etwas_gefunden(stand: dict) -> bool:
    return bool(any(p["fehler"] for p in stand["postfaecher"]) or stand["warten"] or stand["doppelt"] or stand["ganztaegig"])


def ausgeben(stand: dict, ausgabe=print) -> None:
    ausgabe("Abgleich: " + ("eingeschaltet" if stand["eingeschaltet"] else "ausgeschaltet (Einstellungen → Outlook-Synchronisation)"))
    ausgabe("")
    if not stand["postfaecher"]:
        ausgabe("Postfächer: keins hinterlegt.")
    else:
        ausgabe(f"Postfächer ({len(stand['postfaecher'])}):")
    for p in stand["postfaecher"]:
        ausgabe(f"  {p['konto']} · {p['postfach']}" + ("" if p["aktiv"] else " · Konto inaktiv"))
        ausgabe(f"    letzter Lauf: {_zeit(p['letzter_lauf'])}")
        ausgabe("    letzter Fehler: " + (f"{p['fehler']} am {_zeit(p['fehler_am'])}" if p["fehler"] else "keiner"))
        if p["delta_link"]:
            ausgabe(f"    Delta-Link: {p['delta_alter']} alt, Pfad {p['delta_pfad']}")
            if not p["pfad_nennt_postfach"]:
                ausgabe("    Achtung: der Pfad nennt das Postfach nicht -- nach einem Wechsel des Postfachs liest der Abgleich weiter das alte.")
        else:
            ausgabe("    Delta-Link: keiner (der nächste Lauf fragt den ganzen Kalender ab)")
    ausgabe("")
    ausgabe(f"Warten auf Senden: {len(stand['warten'])}")
    for w in stand["warten"]:
        ausgabe(f"  Termin {w['id']} · {w['besitzer']} · {w['tag']:%d.%m.%Y} · {w['grund']}")
    ausgabe(f"Doppelte Outlook-Kennungen: {len(stand['doppelt'])}")
    for d in stand["doppelt"]:
        ausgabe(f"  {d['kennung']} · Termine {', '.join(str(i) for i in d['termine'])} · {'; '.join(d['besitzer'])}")
    ausgabe(f"Ganztägige Termine aus dem ERP: {len(stand['ganztaegig'])}")
    for g in stand["ganztaegig"]:
        ausgabe(f"  Termin {g['id']} · {g['besitzer']} · {g['tag']:%d.%m.%Y}–{g['bis']:%d.%m.%Y} · "
                + ("in Outlook angelegt" if g["gesendet"] else "nicht in Outlook"))


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print, jetzt=None) -> int:
    """sitzung/umgebung/ausgabe/jetzt nur für Tests; im Betrieb die nur lesende Sitzung aus DATABASE_URL, os.environ, print."""
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    eigene = sitzung is None
    if eigene:
        url = (umgebung.get("DATABASE_URL") or "").strip()
        if not url:
            ausgabe("DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a")
            return 2
        sitzung = nur_lesende_sitzung(url)
    try:
        stand = pruefen(sitzung, jetzt=jetzt)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    ausgeben(stand, ausgabe)
    return 1 if etwas_gefunden(stand) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
