"""Test-Helfer seit 1.9.158: Microsoft Graph mit mehreren Postfächern (Stufe 6, R2). Kein Netz: urlopen() ersetzt app.outlook_calendar_sync.urllib.request.urlopen.

Baut auf FakeGraphServer (tests/test_v297_outlook_calendar_sync.py), je Postfach einer. Dazu, wie Microsoft es beschreibt und was die Attrappe bis 1.9.157 nicht konnte:

    Adresse     jeder Aufruf geht an /users/<postfach>/…; ein Postfach, das es nicht gibt, antwortet 404
    Delta-Link  trägt das Postfach im Pfad; ablaufen(): der gespeicherte Link antwortet 410 (oder ein anderer Status mit syncStateNotFound)
    Löschen     DELETE, danach 404; die nächste Delta-Zeile trägt @removed; was vor dem ersten Abruf gelöscht wurde, kommt dort nicht vor
    GET je ID   404, wenn es den Termin nicht (mehr) gibt
    Rechte      sperren(): jeder Aufruf an dieses Postfach 403 (nicht in der Gruppe ERP-Zugriff)
"""

import io
import json
import urllib.error
import urllib.parse
from datetime import datetime

from tests.test_v297_outlook_calendar_sync import FakeGraphServer, TOKEN_URL_MARKER, _FakeResponse, _parse_graph_datetime

GRAPH = "https://graph.microsoft.com/v1.0"


def http_fehler(status: int, code: str = "ErrorAccessDenied", *, inner: str | None = None, kopf: dict | None = None) -> urllib.error.HTTPError:
    fehler = {"code": code, "message": "Titel und Ort könnten hier im Klartext stehen"}
    if inner:
        fehler["innerError"] = {"code": inner}
    return urllib.error.HTTPError(url=GRAPH, code=status, msg="err", hdrs=kopf, fp=io.BytesIO(json.dumps({"error": fehler}).encode("utf-8")))


class Postfach(FakeGraphServer):
    """Ein Postfach mit Löschen und @removed."""

    def __init__(self, kennung: str):
        super().__init__(kennung)
        self.geloescht: dict[str, int] = {}

    def loeschen(self, kennung: str) -> None:
        del self.events[kennung]
        self._seq += 1
        self.geloescht[kennung] = self._seq

    def aendern(self, kennung: str, **felder) -> None:
        """Eine Änderung direkt in Outlook."""
        last_modified, change_key, etag = self._advance()
        self.events[kennung].update({**felder, "lastModifiedDateTime": last_modified, "changeKey": change_key, "@odata.etag": etag, "_seq": self._seq})

    def anlegen(self, titel: str, beginn: datetime, ende: datetime, **felder) -> str:
        """Ein Termin direkt in Outlook."""
        zeile = self.create({"subject": titel, "isAllDay": False, "start": {"dateTime": beginn.isoformat(), "timeZone": "UTC"}, "end": {"dateTime": ende.isoformat(), "timeZone": "UTC"},
                             "location": {"displayName": ""}, "body": {"content": ""}})
        self.events[zeile["id"]].update(felder)
        return zeile["id"]

    def delta(self, since_seq: int) -> tuple[list[dict], int]:
        items, max_seq = super().delta(since_seq)
        if since_seq:  # beim ersten Abruf kommt nur vor, was es gibt
            items += [{"id": k, "@removed": {"reason": "deleted"}} for k, seq in self.geloescht.items() if seq > since_seq]
        return items, max(max_seq, self._seq)


class Microsoft:
    def __init__(self):
        self.postfaecher: dict[str, Postfach] = {}
        self.anfragen: list[tuple[str, str]] = []
        self.gesperrt: set[str] = set()
        self._abgelaufen: dict[str, tuple] = {}
        self.vor_antwort = None  # Haken für Gleichzeitigkeit: vor_antwort(methode, adresse, weg)

    def postfach(self, adresse: str) -> Postfach:
        return self.postfaecher.setdefault(adresse, Postfach(adresse.split("@")[0]))

    def ablaufen(self, adresse: str, status: int = 410, code: str = "syncStateNotFound", inner: str | None = None, *, wie_oft: int = 1) -> None:
        self._abgelaufen[adresse] = (status, code, inner, wie_oft, wie_oft > 1)

    def schreibend(self, methode: str | None = None) -> list[tuple[str, str]]:
        return [(m, u) for m, u in self.anfragen if (m == methode if methode else m != "GET")]

    def urlopen(self, req, timeout=None):
        url = req.full_url
        if TOKEN_URL_MARKER in url:
            return _FakeResponse({"access_token": "faketoken"})
        methode = req.get_method()
        self.anfragen.append((methode, url))
        teile = urllib.parse.urlsplit(url)
        pfad = urllib.parse.unquote(teile.path).split("/users/", 1)[1].split("/")
        adresse, weg = pfad[0], pfad[1:]
        if self.vor_antwort:
            self.vor_antwort(methode, adresse, weg)
        if adresse in self.gesperrt:
            raise http_fehler(403)
        if adresse not in self.postfaecher:
            raise http_fehler(404, "ErrorInvalidUser")
        postfach = self.postfaecher[adresse]
        if weg[:1] == ["calendarView"]:
            return self._kalenderansicht(postfach, teile)
        if weg[-1:] == ["delta"]:
            return self._delta(adresse, postfach, teile)
        kennung = weg[1] if len(weg) > 1 else None
        if methode == "POST":
            return _FakeResponse(postfach.create(json.loads(req.data)))
        if kennung not in postfach.events:
            raise http_fehler(404, "ErrorItemNotFound")
        if methode == "PATCH":
            return _FakeResponse(postfach.patch(kennung, json.loads(req.data)))
        if methode == "DELETE":
            postfach.loeschen(kennung)
            return _FakeResponse(None)
        return _FakeResponse({k: v for k, v in postfach.events[kennung].items() if k != "_seq"})

    def _delta(self, adresse: str, postfach: Postfach, teile) -> _FakeResponse:
        abfrage = urllib.parse.parse_qs(teile.query)
        gespeichert = "$deltatoken" in abfrage
        if adresse in self._abgelaufen:
            status, code, inner, rest, auch_ohne_link = self._abgelaufen[adresse]
            if gespeichert or auch_ohne_link:  # wie_oft > 1: auch der Abruf von vorn läuft ab
                if rest > 1:
                    self._abgelaufen[adresse] = (status, code, inner, rest - 1, auch_ohne_link)
                else:
                    del self._abgelaufen[adresse]
                raise http_fehler(status, code, inner=inner, kopf={"Location": f"{GRAPH}/users/{adresse}/events/delta"})
        seit = int(abfrage["$deltatoken"][0]) if gespeichert else 0
        items, stand = postfach.delta(seit)
        return _FakeResponse({"value": items, "@odata.deltaLink": f"{GRAPH}/users/{urllib.parse.quote(adresse)}/events/delta?$deltatoken={stand}"})

    def _kalenderansicht(self, postfach: Postfach, teile) -> _FakeResponse:
        abfrage = urllib.parse.parse_qs(teile.query)
        return _FakeResponse({"value": postfach.calendar_view(_parse_graph_datetime(abfrage["startDateTime"][0]), _parse_graph_datetime(abfrage["endDateTime"][0]))})
