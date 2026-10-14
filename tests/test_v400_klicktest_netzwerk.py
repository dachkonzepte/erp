"""Version 1.8.97 -- Klicktest-Werkzeug: Netzwerkprotokoll (scripts/cdp_klicktest.py, Netzprotokoll, Tab.netz_melden()).

Anlass: in einem Gesamtlauf von 1.8.95 kam beim Öffnen der Kundenakte eine von neun Anfragen nie beim Server an, die Seite wartete --
das Werkzeug konnte nicht sagen, welche Anfrage hing und ob der Browser sie gesendet hatte. Jetzt zeichnet jeder Tab die
Network-Ereignisse je Anfrage auf; scheitert eine Prüfung, eine Seite, ein Warte-Helfer oder der Lauf, druckt das Werkzeug die offenen
Anfragen (Adresse, Methode, Startzeit, gesendet, Antwort-Kopf). "Gesendet" heißt: requestWillBeSentExtraInfo kam (Festlegung 1.8.97).

Hier ohne Chrome: gestellte CDP-Ereignisse in den Recorder und ein gestellter websocket für die Helfer des Tabs. Dass eine im Netz
angehaltene Anfrage im echten Chrome kein requestWillBeSentExtraInfo bekommt (also "nicht gesendet" ist), prüft der Klicktest
scripts/klicktest_anmelden.py."""

import asyncio
import collections
import importlib.util
import json
import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BASIS = "http://127.0.0.1:8000"
T0 = 1_760_000_000.25


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_netz", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


W = _werkzeug()


# -- gestellte Ereignisse ---------------------------------------------------------

def rwbs(rid, pfad, methode="GET", art="Fetch", loader="L1", wall=T0, ts=100.0, umleitung=False):
    params = {"requestId": rid, "loaderId": loader, "request": {"url": BASIS + pfad, "method": methode}, "type": art,
              "wallTime": wall, "timestamp": ts}
    if umleitung:
        params["redirectResponse"] = {"status": 302}
    return "Network.requestWillBeSent", params


def extra(rid):
    return "Network.requestWillBeSentExtraInfo", {"requestId": rid, "headers": {}, "associatedCookies": []}


def kopf_extra(rid, status=200):
    return "Network.responseReceivedExtraInfo", {"requestId": rid, "statusCode": status, "headers": {}}


def antwort(rid, status=200, ts=100.5):
    return "Network.responseReceived", {"requestId": rid, "timestamp": ts, "type": "Fetch", "response": {"status": status}}


def fertig(rid, ts=100.6):
    return "Network.loadingFinished", {"requestId": rid, "timestamp": ts, "encodedDataLength": 10}


def fehlgeschlagen(rid, text="net::ERR_ABORTED", abgebrochen=True):
    return "Network.loadingFailed", {"requestId": rid, "timestamp": 101.0, "type": "Fetch", "errorText": text,
                                     "canceled": abgebrochen}


def navigiert(loader, pfad):
    return "Page.frameNavigated", {"frame": {"id": "F1", "loaderId": loader, "url": BASIS + pfad}, "type": "Navigation"}


def angehalten(fetch_id, rid, pfad, methode="POST"):
    return "Fetch.requestPaused", {"requestId": fetch_id, "networkId": rid, "request": {"url": BASIS + pfad, "method": methode}}


def protokoll(*ereignisse):
    n = W.Netzprotokoll(BASIS)
    for methode, params in ereignisse:
        n.ereignis(methode, params, jetzt=T0 + 1)
    return n


def eintrag(n, rid):
    return next(e for e in n.verlauf if e["id"] == rid)


# -- Recorder -------------------------------------------------------------------

def test_a_finished_request_is_not_reported():
    n = protokoll(navigiert("L1", "/kunden"), rwbs("1", "/api/x"), extra("1"), antwort("1"), fertig("1"))
    assert n.offen() == [] and n.fehlgeschlagen() == []
    assert n.bericht(jetzt=T0 + 5) == ["    Netzwerk: keine offenen Anfragen"]


def test_an_open_request_with_address_method_start_and_sent_flags():
    n = protokoll(navigiert("L1", "/customers/3"), rwbs("7", "/api/customers/3/documents"))
    zeilen = n.bericht(jetzt=T0 + 12.34)
    assert zeilen[0] == "    Netzwerk: 1 offen"
    assert zeilen[1] == (f"      GET /api/customers/3/documents [Fetch]  seit {W._uhrzeit(T0)} (12,3 s)  gesendet: nein"
                         "  Antwort-Kopf: nein")
    assert re.fullmatch(r"\d\d:\d\d:\d\d\.250", W._uhrzeit(T0))
    assert len(zeilen) == 2


@pytest.mark.parametrize("ereignisse, gesendet, kopf", [
    ([rwbs("1", "/api/x")], False, False),                                  # die Seite will senden -- mehr nicht
    ([rwbs("1", "/api/x"), extra("1")], True, False),                       # auf der Leitung
    ([extra("1"), rwbs("1", "/api/x")], True, False),                       # Reihenfolge ist nicht garantiert
    ([rwbs("1", "/api/x"), kopf_extra("1")], True, True),                   # ein Antwort-Kopf belegt das Senden auch
    ([rwbs("1", "/api/x"), extra("1"), antwort("1")], True, True),
    ([rwbs("1", "/api/x"), ("Network.requestServedFromCache", {"requestId": "1"}), antwort("1")], False, True),
])
def test_sent_means_extra_info_or_a_response(ereignisse, gesendet, kopf):
    e = eintrag(protokoll(navigiert("L1", "/"), *ereignisse), "1")
    assert (W.gesendet(e), W.antwort_kopf(e)) == (gesendet, kopf)


def test_after_a_redirect_the_new_step_must_be_sent_again():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/a"), extra("1"), kopf_extra("1", 302), rwbs("1", "/b", umleitung=True))
    e = eintrag(n, "1")
    assert (W.gesendet(e), W.antwort_kopf(e), e["url"]) == (False, False, BASIS + "/b")
    n.ereignis(*extra("1"))
    assert W.gesendet(e)


def test_a_request_from_the_cache_is_shown_as_not_sent():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/seite", art="Document"), ("Network.requestServedFromCache", {"requestId": "1"}))
    assert "gesendet: nein (Cache)" in n.bericht()[1]


def test_a_failed_request_is_reported_with_its_error_text():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/auth/logout", "POST"), fehlgeschlagen("1"))
    zeilen = n.bericht()
    assert zeilen[0] == "    Netzwerk: keine offenen Anfragen"
    assert zeilen[1] == "    Netzwerk: fehlgeschlagen: 1"
    assert zeilen[2] == (f"      POST /api/auth/logout [Fetch]  {W._uhrzeit(T0)}  net::ERR_ABORTED (abgebrochen)  gesendet: nein"
                         "  Antwort-Kopf: nein")


def test_a_document_change_keeps_the_open_requests_of_the_old_document_until_the_next_one():
    n = protokoll(
        navigiert("L1", "/customers/1"),
        rwbs("a", "/api/auth/logout", "POST"), extra("a"), antwort("a"),     # beantwortet, Ende noch nicht gemeldet
        rwbs("b", "/api/customers/1"), extra("b"), antwort("b"), fertig("b"),
        rwbs("c", "/api/projects"), fehlgeschlagen("c"),
        rwbs("L2", "/login?next=%2Fcustomers%2F1", art="Document", loader="L2"), extra("L2"), antwort("L2"), fertig("L2"),
        navigiert("L2", "/login?next=%2Fcustomers%2F1"),
    )
    zeilen = n.bericht()
    assert zeilen[0] == "    Netzwerk: keine offenen Anfragen"
    assert zeilen[1] == "    Netzwerk: beim Wechsel auf /login?next=%2Fcustomers%2F1 offen geblieben: 1"
    assert zeilen[2].startswith("      POST /api/auth/logout [Fetch]  seit ") and zeilen[2].endswith("gesendet: ja  Antwort-Kopf: ja")
    assert zeilen[3:] == ["    Netzwerk: fehlgeschlagen: 1",
                          f"      GET /api/projects [Fetch]  {W._uhrzeit(T0)}  net::ERR_ABORTED (abgebrochen)  gesendet: nein"
                          "  Antwort-Kopf: nein"]
    n.ereignis(*fertig("a"))          # kommt spät (z. B. erst, wenn die Seite aus dem Back-Forward-Cache zurückkommt)
    assert n.bericht() == ["    Netzwerk: keine offenen Anfragen", zeilen[3], zeilen[4]]
    n.ereignis(*navigiert("L3", "/customers/1"))
    assert n.bericht() == ["    Netzwerk: keine offenen Anfragen"]
    assert [e["id"] for e in n.suche(r"/api/", None)] == ["a", "b", "c"]  # der Verlauf behält alles
    assert [e["id"] for e in n.suche(r"/api/auth/logout$", "post")] == ["a"]


def test_a_new_document_request_stays_current_and_an_iframe_does_not_change_the_document():
    n = protokoll(navigiert("L1", "/a"), rwbs("L2", "/b", art="Document", loader="L2"),
                  ("Page.frameNavigated", {"frame": {"id": "F2", "parentId": "F1", "loaderId": "L9", "url": BASIS + "/pdf"}}),
                  navigiert("L2", "/b"))
    assert [e["id"] for e in n.offen()] == ["L2"] and n.dokument == "L2"


def test_a_request_paused_in_the_network_is_open_not_sent_and_marked():
    n = protokoll(navigiert("L1", "/customers/1"), rwbs("9", "/api/auth/logout", "POST"),
                  angehalten("interception-job-1.0", "9", "/api/auth/logout"))
    assert n.angehalten == {"interception-job-1.0": "9"}
    assert n.bericht()[1].endswith("gesendet: nein  Antwort-Kopf: nein  im Netz angehalten")
    n.fortgesetzt("interception-job-1.0")
    n.ereignis(*extra("9"))
    assert n.angehalten == {} and n.bericht()[1].endswith("gesendet: ja  Antwort-Kopf: nein")


def test_a_paused_request_that_the_browser_cancels_is_no_longer_paused():
    n = protokoll(navigiert("L1", "/"), rwbs("9", "/api/auth/logout", "POST"), angehalten("f1", "9", "/api/auth/logout"),
                  fehlgeschlagen("9"))
    assert n.angehalten == {} and not eintrag(n, "9")["angehalten"]


def test_the_page_counter_is_shown_only_when_it_differs():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/x"), rwbs("2", "/app.js", art="Script"))
    assert not any(z.startswith("    Seite:") for z in n.bericht(seite={"offen": 1, "gestartet": 5, "gehalten": 0}))
    assert n.bericht(seite={"offen": 2, "gestartet": 5, "gehalten": 1})[-1] == (
        "    Seite: Anfragenzähler offen 2, davon zurückgehalten 1 -- im Netz offen (Fetch/XHR): 1")


def test_long_lists_are_cut():
    n = protokoll(navigiert("L1", "/"), *(rwbs(str(i), f"/api/{i}") for i in range(12)))
    zeilen = n.bericht()
    assert zeilen[0] == "    Netzwerk: 12 offen" and len(zeilen) == 1 + W.NETZ_ZEILEN + 1
    assert zeilen[-1] == "      … und 4 weitere"


def test_an_unchanged_report_is_printed_once():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/x"))
    jetzt = T0 + 5
    assert n.melden(jetzt) == n.bericht(jetzt)
    assert n.melden(jetzt + 3) == ["    Netzwerk: unverändert seit der letzten Meldung (1 offen)"]
    assert n.melden(jetzt, immer=True) == n.bericht(jetzt)
    n.ereignis(*extra("1"))
    assert n.melden(jetzt) == n.bericht(jetzt)
    for ereignis in (rwbs("2", "/api/y"), fehlgeschlagen("2"), navigiert("L2", "/login")):
        n.ereignis(*ereignis)
    n.melden(jetzt)
    assert n.melden(jetzt) == ["    Netzwerk: unverändert seit der letzten Meldung (0 offen, 1 beim Wechsel offen geblieben, "
                               "1 fehlgeschlagen)"]


# -- Tab mit gestelltem websocket -----------------------------------------------------

class GestellterWs:
    """Antwortet auf jeden Befehl. ereignisse(methode, params) liefert die Ereignisse, die vor der Antwort ankommen; ergebnis(methode,
    params) das Ergebnis (ein dict mit "__fehler__" wird zur Fehlerantwort)."""

    def __init__(self, ereignisse=None, ergebnis=None):
        self.befehle: list[dict] = []
        self._schlange = collections.deque()
        self.ereignisse = ereignisse or (lambda m, p: [])
        self.ergebnis = ergebnis or (lambda m, p: {"result": {"type": "boolean", "value": False}} if m == "Runtime.evaluate" else {})

    async def send(self, text):
        msg = json.loads(text)
        self.befehle.append(msg)
        for methode, params in self.ereignisse(msg["method"], msg.get("params", {})):
            self._schlange.append(json.dumps({"method": methode, "params": params}))
        ergebnis = self.ergebnis(msg["method"], msg.get("params", {}))
        if "__fehler__" in ergebnis:
            self._schlange.append(json.dumps({"id": msg["id"], "error": {"message": ergebnis["__fehler__"]}}))
        else:
            self._schlange.append(json.dumps({"id": msg["id"], "result": ergebnis}))

    async def recv(self):
        return self._schlange.popleft()


def _haengende_seite(m, p):
    """Beim Navigieren: neues Dokument, eine Anfrage hängt (nie gesendet), eine zweite ist noch unterwegs -- ihr Ende kommt erst
    mit dem nächsten Lesen nach dem Scheitern (SEITE_STAND)."""
    if m == "Page.navigate":
        return [navigiert("L1", "/customers/3"), rwbs("7", "/api/haengt"), rwbs("8", "/api/spaet"), extra("8")]
    if m == "Runtime.evaluate" and p.get("expression") == W.SEITE_STAND:
        return [antwort("8"), fertig("8")]
    return []


def _seite_stand(m, p):
    if m == "Runtime.evaluate" and p.get("expression") == W.SEITE_STAND:
        return {"result": {"type": "object", "value": {"offen": 2, "gestartet": 9, "gehalten": 0}}}
    if m == "Runtime.evaluate":
        return {"result": {"type": "boolean", "value": False}}
    return {}


def _tab(ws, tmp_path):
    return W.Tab(ws, BASIS, tmp_path)


def test_cmd_feeds_network_events_into_the_protocol(tmp_path):
    tab = _tab(GestellterWs(_haengende_seite), tmp_path)
    asyncio.run(tab.cmd("Page.navigate", url=BASIS + "/customers/3"))
    assert [e["id"] for e in tab.netz.offen()] == ["7", "8"] and W.gesendet(eintrag(tab.netz, "8"))


def test_a_failing_check_prints_the_open_requests(tmp_path, capsys):
    tab = _tab(GestellterWs(_haengende_seite), tmp_path)
    asyncio.run(tab.cmd("Page.navigate", url=BASIS + "/customers/3"))
    p = W.Pruefungen()
    p.netz = tab.netz
    p.pruefe("passt", 1, 1)
    assert "Netzwerk" not in capsys.readouterr().out
    p.pruefe("passt nicht", 1, 2)
    aus = capsys.readouterr().out
    assert "XX  passt nicht: 1   (erwartet 2)" in aus
    assert "    Netzwerk: 2 offen" in aus and "GET /api/haengt [Fetch]" in aus and "gesendet: nein" in aus
    p.pruefe("passt wieder nicht", 1, 3)
    assert "    Netzwerk: unverändert seit der letzten Meldung (2 offen)" in capsys.readouterr().out


def test_oeffnen_reads_on_and_prints_the_open_requests(tmp_path, capsys):
    """Die Seite wird nicht bereit: das Werkzeug liest erst nach (das Ende von /api/spaet kommt dabei an) und druckt dann -- mit dem
    Anfragenzähler der Seite, weil er abweicht."""
    tab = _tab(GestellterWs(_haengende_seite, _seite_stand), tmp_path)
    assert asyncio.run(tab.oeffnen("/customers/3", "document.querySelector('#fertig')", timeout=0.3)) is False
    aus = capsys.readouterr().out
    assert "XX  /customers/3: Seite nicht bereit" in aus
    assert "    Netzwerk: 1 offen" in aus and "GET /api/haengt [Fetch]  seit " in aus
    assert "/api/spaet" not in aus
    assert "    Seite: Anfragenzähler offen 2 -- im Netz offen (Fetch/XHR): 1" in aus
    assert tab.fehler == []


@pytest.mark.parametrize("helfer", [
    lambda tab: tab.warte_auf_neu_geladene_liste(timeout=0.3),
    lambda tab: tab.warte_bis_gehalten(1, timeout=0.3),
    lambda tab: tab.warte_auf_ruhe(timeout=0.3),
    lambda tab: tab.warte_bis_im_netz_angehalten(1, timeout=0.3),
    lambda tab: tab.warten("document.querySelector('#fertig')", 0.3),
], ids=["warte_auf_neu_geladene_liste", "warte_bis_gehalten", "warte_auf_ruhe", "warte_bis_im_netz_angehalten", "warten"])
def test_a_waiting_helper_that_gives_up_prints_the_open_requests(helfer, tmp_path, capsys):
    tab = _tab(GestellterWs(_haengende_seite, _seite_stand), tmp_path)
    asyncio.run(tab.cmd("Page.navigate", url=BASIS + "/customers/3"))
    assert asyncio.run(helfer(tab)) is False
    aus = capsys.readouterr().out
    assert "GET /api/haengt [Fetch]  seit " in aus and "gesendet: nein  Antwort-Kopf: nein" in aus


def test_a_wanted_pause_prints_nothing(tmp_path, capsys):
    tab = _tab(GestellterWs(_haengende_seite, _seite_stand), tmp_path)
    asyncio.run(tab.cmd("Page.navigate", url=BASIS + "/customers/3"))
    assert asyncio.run(tab.warten("false", 0.2, melden=False)) is False
    assert capsys.readouterr().out == ""


def test_the_end_of_an_unsuccessful_run_prints_the_protocol(tmp_path, capsys):
    tab = _tab(GestellterWs(_haengende_seite, _seite_stand), tmp_path)
    p = W.Pruefungen()
    p.netz = tab.netz

    async def gut(t, seed, pr):
        await t.cmd("Page.navigate", url=BASIS + "/customers/3")

    async def nicht_geladen(t, seed, pr):
        await gut(t, seed, pr)
        t.nicht_geladen.append("/customers/3")

    async def ausnahme(t, seed, pr):
        await gut(t, seed, pr)
        raise ValueError("kaputt")

    assert asyncio.run(W._pruefen_und_melden(gut, tab, {}, p)) is True
    assert capsys.readouterr().out == ""
    assert asyncio.run(W._pruefen_und_melden(nicht_geladen, tab, {}, p)) is False
    aus = capsys.readouterr().out
    assert "--  Netzwerk am Ende des Laufs (nicht wie erwartet):" in aus and "GET /api/haengt" in aus
    tab.nicht_geladen.clear()
    with pytest.raises(ValueError, match="kaputt"):
        asyncio.run(W._pruefen_und_melden(ausnahme, tab, {}, p))
    assert "GET /api/haengt" in capsys.readouterr().out  # auch unverändert: am Ende immer der ganze Bericht


def test_continuing_paused_requests_skips_the_cancelled_ones_and_stops_pausing(tmp_path):
    def ergebnis(m, p):
        if m == "Fetch.continueRequest" and p["requestId"] == "f2":
            return {"__fehler__": "Invalid InterceptionId."}
        return {}

    ws = GestellterWs(lambda m, p: [angehalten("f1", "1", "/a"), angehalten("f2", "2", "/b")] if m == "Fetch.enable" else [],
                      ergebnis)
    tab = _tab(ws, tmp_path)
    asyncio.run(tab.im_netz_anhalten("*/api/auth/logout"))
    assert ws.befehle[-1]["params"] == {"patterns": [{"urlPattern": "*/api/auth/logout", "requestStage": "Request"}]}
    assert asyncio.run(tab.im_netz_fortsetzen()) == 1
    assert [(b["method"], b["params"].get("requestId")) for b in ws.befehle[1:]] == [
        ("Fetch.continueRequest", "f1"), ("Fetch.continueRequest", "f2"), ("Fetch.disable", None)]
    assert tab.netz.angehalten == {} and not eintrag(tab.netz, "1")["angehalten"]


def test_every_run_wires_the_protocol_into_the_checks_and_the_end_report():
    quelle = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    lauf = quelle[quelle.index("async def _lauf("):quelle.index("async def _pruefen_und_melden(")]
    assert "p.netz = tab.netz" in lauf and "await _pruefen_und_melden(pruefen, tab, seed, p)" in lauf
    assert '"Network.enable"' in quelle or "for domain in (\"Page\", \"Runtime\", \"Network\")" in lauf


def test_the_login_click_test_covers_both_forms_and_both_headers():
    """Vorgabe Punkt 5: Anmelden über Formular und Seitenleiste, Abmelden über beide Kopfzeilen."""
    quelle = (SCRIPTS / "klicktest_anmelden.py").read_text(encoding="utf-8")
    for teil in ('"#u"', '"#appSidebarLoginForm button"', '"#appTopbarLogout"', '"#mobileHeaderLogout"',
                 'await tab.im_netz_anhalten("*/api/auth/logout")', 'await tab.im_netz_anhalten("*/api/auth/login")'):
        assert teil in quelle, teil


def test_a_browser_dialog_is_reported_and_accepted_instead_of_hanging(tmp_path, capsys):
    """Seit 1.8.98: "Seite verlassen?" (oder ein anderer Dialog des Browsers) hielt jeden weiteren CDP-Befehl an -- der Klicktest hing
    bis zum Zeitlimit. Jetzt meldet das Werkzeug ihn (der Lauf ist nicht wie erwartet), nimmt ihn an und macht weiter."""
    def dialog(m, p):
        if m == "Page.navigate":
            return [("Page.javascriptDialogOpening", {"type": "beforeunload", "message": "", "url": BASIS + "/customers/3"})]
        return []
    ws = GestellterWs(dialog)
    tab = _tab(ws, tmp_path)
    asyncio.run(tab.cmd("Page.navigate", url=BASIS + "/login"))
    assert [b["method"] for b in ws.befehle] == ["Page.navigate", "Page.handleJavaScriptDialog"]
    assert ws.befehle[1]["params"] == {"accept": True}
    assert tab.nicht_geladen == [f"Dialog beforeunload ('') auf {BASIS}/customers/3"]
    assert "XX  Dialog des Browsers (beforeunload)" in capsys.readouterr().out
