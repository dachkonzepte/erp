"""Seit 1.9.46 (Stufe 4, R2, Punkt 7): jeder angezeigte Zeitpunkt in Europe/Berlin -- gespeicherte Werte bleiben, wie sie sind.

    Helfer         berlinZeitpunkt(wert, art) in _berlin_date.html: ein gespeicherter Zeitpunkt aus datetime.utcnow() (naives UTC ohne 'Z',
                   wie die API ihn liefert) als „TT.MM.JJJJ HH:MM“ ('zeit'), „TT.MM.JJJJ“ ('datum') oder „JJJJ-MM-TT“ ('tag') in Berlin --
                   unabhängig von der Zeitzone des Browsers, wie app/berlin_time.py::to_berlin() auf dem Server
    Wächter        keine Vorlage zeigt ein UTC-Feld über new Date()/toLocale…/fmtDate()/slice() oder hängt 'Z' an; wer den Helfer nimmt, bindet
                   _berlin_date.html ein. Naive Ortszeit (Beginn/Ende einer Zeitbuchung, Termine, Wiedervorlage) und die *_local-Felder
                   (vom Server schon in Berlin) laufen NICHT durch den Helfer.
    Unterschrift   die Zeit der Unterschrift auf der Berichtsseite = die Zeit im PDF (bis 1.9.45 zeigte die Seite UTC, 15:33 statt 17:33)
"""

import json
import re
from datetime import datetime

import pytest

from app.models import ServiceReport
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren
from tests.test_v467_zeiten_einsatzbericht import _bericht, _pdf, _unterschreiben, welt  # noqa: F401  (Fixture)

# Felder der API, die einen gespeicherten Zeitpunkt in UTC tragen (Spalten mit datetime.utcnow) -- Bestand aus dem Inventar 1.9.46
UTC_FELDER = ("uploaded_at", "created_at", "updated_at", "completed_at", "released_at", "signed_at", "installer_signed_at", "last_login_at",
              "changed_at", "occurred_at", "published_at", "locked_at", "executed_at", "email_sent_at", "discarded_at", "finished_at",
              "resolved_at", "voided_at", "recorded_at", "reverted_at", "superseded_at", "archived_at", "finalized_at", "closed_at")
UTC_FELD = r"\b[\w.?]*\.(?:" + "|".join(UTC_FELDER) + r")\b"


def _helfer() -> str:
    text = (vj.TEMPLATES / "_berlin_date.html").read_text(encoding="utf-8")
    return re.sub(r"</?script>", "", text)


FAELLE = [
    ("2026-10-22T15:33:00", "zeit", "22.10.2026 17:33"),                # Sommerzeit: + 2 h (der Befund: Seite 15:33, PDF 17:33)
    ("2026-10-22T15:33:00.123456", "zeit", "22.10.2026 17:33"),
    ("2026-10-22T15:33:00Z", "zeit", "22.10.2026 17:33"),               # mit 'Z' derselbe Zeitpunkt
    ("2026-10-22T17:33:00+02:00", "zeit", "22.10.2026 17:33"),
    ("2026-12-01T23:30:00", "zeit", "02.12.2026 00:30"),                # Winterzeit: + 1 h, über Mitternacht
    ("2026-12-01T23:30:00", "datum", "02.12.2026"),                     # das Datum in Berlin, nicht das der UTC-Uhr
    ("2026-12-01T23:30:00", "tag", "2026-12-02"),
    ("2026-12-31T23:30:00", "datum", "01.01.2027"),                     # Silvester
    ("2026-03-29T00:59:59", "zeit", "29.03.2026 01:59"),                # Umstellung auf Sommerzeit
    ("2026-03-29T01:00:00", "zeit", "29.03.2026 03:00"),
    ("2026-10-25T00:30:00", "zeit", "25.10.2026 02:30"),                # Umstellung auf Winterzeit
    ("2026-10-25T01:30:00", "zeit", "25.10.2026 02:30"),
    ("", "zeit", ""), (None, "zeit", ""), ("kaputt", "zeit", "kaputt"),
]


@pytest.mark.parametrize("tz", ["Europe/Berlin", "UTC", "America/New_York", "Asia/Tokyo"])
def test_helfer_rechnet_in_berlin_unabhaengig_vom_browser(tz):
    script = _helfer() + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(FAELLE) + ".map(([w,a])=>berlinZeitpunkt(w,a))))"
    assert node_ausfuehren(script, tz) == [soll for _, _, soll in FAELLE]


def _verstoesse(text: str) -> list[str]:
    funde = []
    for m in re.finditer(r"""\+\s*['"]Z['"]""", text):
        funde.append("'Z' angehängt: " + text[max(0, m.start() - 40):m.end()].replace("\n", " "))
    for m in re.finditer(r"(?<![\w.])(?:new Date|fmtDateTime|fmtDate|fmt|dateDe|accDateTime|accDate|fd|dt|dDe)\(\s*(?:String\()?\(?\s*" + UTC_FELD, text):
        funde.append("UTC-Feld ohne Berlin: " + m.group(0))
    for m in re.finditer(UTC_FELD + r"""(?:\s*\|\|\s*['"]{2}\))?\)?\.slice\(""", text):
        funde.append("UTC-Feld abgeschnitten: " + m.group(0))
    return funde


def test_kein_utc_zeitpunkt_ohne_berlin():
    funde = [f"{name}: {f}" for name in vj.alle_vorlagen() if name != "_berlin_date.html"
             for f in _verstoesse((vj.TEMPLATES / name).read_text(encoding="utf-8"))]
    assert funde == []


@pytest.mark.parametrize("muster, soll", [
    ("new Date(d.uploaded_at).toLocaleString('de-DE')", 1), ("fmtDate(r.email_sent_at.slice(0,10))", 1),
    ("new Date(x.occurred_at+'Z').toLocaleString('de-DE')", 2), ("fmtDate((d.uploaded_at||'').slice(0,10))", 1),
    ("dateDe(String(c.created_at).slice(0,10))", 1), ("berlinZeitpunkt(r.signed_at)", 0), ("fmtDate(e.work_date)", 0),
    ("String(z.started_at||'').slice(11,16)", 0),  # naive Ortszeit einer Zeitbuchung -- kein UTC-Feld
])
def test_waechter_erkennt_die_muster(muster, soll):
    """Gegenprobe des Wächters: die Muster des Inventars (1.9.46) fallen auf, der Helfer und naive Ortszeit nicht."""
    assert len(_verstoesse(muster)) >= soll and (soll > 0) == bool(_verstoesse(muster))


def test_wer_den_helfer_nimmt_bindet_ihn_ein():
    nutzer = [name for name in vj.seiten() if "berlinZeitpunkt(" in vj.zusammensetzen(name)[0]]
    assert len(nutzer) >= 15, nutzer
    assert [name for name in nutzer if not vj.bindet_ein(name, "_berlin_date.html")] == []


def test_unterschriftszeit_auf_der_seite_wie_im_pdf(welt):  # noqa: F811
    """Der Befund: die Berichtsseite zeigte die Unterschrift in UTC (15:33), das PDF in Berlin (17:33). Jetzt rechnet die Seite den Wert
    der API mit dem Helfer -- dieselbe Zeit wie das PDF; der gespeicherte Wert bleibt UTC."""
    rid = _bericht(welt)
    _unterschreiben(welt, rid)
    db = welt["db"]
    report = db.get(ServiceReport, rid)
    report.signed_at = report.installer_signed_at = datetime(2026, 10, 22, 15, 33, 12)  # UTC, wie datetime.utcnow() speichert
    db.commit()
    api_wert = next(r for r in welt["client"].get(f"/api/orders/{welt['order'].id}/service-reports").json() if r["id"] == rid)["signed_at"]
    assert api_wert.startswith("2026-10-22T15:33")  # gespeichert und geliefert unverändert in UTC
    seite = node_ausfuehren(_helfer() + f"\nprocess.stdout.write(JSON.stringify(berlinZeitpunkt({json.dumps(api_wert)})))", "UTC")
    assert seite == "22.10.2026 17:33"
    assert f"am {seite} Uhr".encode() in _pdf(welt, rid)  # _pdf() liefert die Rohbytes der Inhaltsströme
    text, _ = vj.seitentext("service_reports.html")
    assert "Kunde: ${esc(r.signature_name)} (${esc(berlinZeitpunkt(r.signed_at))} Uhr)" in text
