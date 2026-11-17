"""Version 1.9.345 -- die Rückfrage bei „Deaktivieren“ und „Löschen“ auf der Seite „Benutzer“ nennt Anzeigename und Benutzername (Runde ab 1.9.343,
Punkt 3); seit 1.9.347 auch „Zweiten Faktor zurücksetzen“ und „Alle Sitzungen beenden“. Bei 412 px rollt die Tabelle in ihrem Rahmen, neben dem Knopf steht kein Name. Die Rückfrage bleibt ein confirm() (Regel 4, Antwort Tobias
17.11.2026). Klicktest mit Bildern: scripts/klicktest_benutzer_rueckfrage.py."""

import json
from pathlib import Path

from tests.test_v314_dashboard_month_berlin import _node
from tests.test_v333_auswahl_inaktiv import nur_mit_node

VORLAGE = Path(__file__).resolve().parents[1] / "app" / "templates" / "users.html"
ANFAENGE = ("function kontoName(", "async function deleteUser(", "async function deactivateUser(", "async function resetTwoFactor(",
            "async function endSessions(")


@nur_mit_node
def test_rueckfrage_nennt_anzeigename_und_benutzername():
    zeilen = [z for z in VORLAGE.read_text(encoding="utf-8").splitlines() if z.startswith(ANFAENGE)]
    assert len(zeilen) == 5, zeilen
    konten = [{"id": 1, "display_name": "Bea <b>Büro</b>", "username": "bea", "verwendet_in": ["Aufgaben"]}]
    skript = (f"let users={json.dumps(konten)};const status={{user:{{id:9}}}};const fragen=[];function confirm(m){{fragen.push(m);return false}}\n"
              + "\n".join(zeilen) + "\n(async()=>{await deleteUser(1);await deactivateUser(1);await resetTwoFactor(1);await endSessions(1);"
              "process.stdout.write(JSON.stringify(fragen))})();")
    loeschen, deaktivieren, zweiter_faktor, sitzungen = _node(skript, "Europe/Berlin")
    assert loeschen.split("\n")[0] == "Benutzer „Bea <b>Büro</b>“ (Benutzername „bea“) wirklich löschen?"  # confirm() zeigt Text, kein HTML
    assert deaktivieren.split("\n")[0] == "Benutzer „Bea <b>Büro</b>“ (Benutzername „bea“) deaktivieren?"
    assert "Was es angelegt hat (Aufgaben), bleibt erhalten." in deaktivieren
    # seit 1.9.347 (Runde ab 1.9.346, Punkt 3) auch die beiden anderen Rückfragen der Zeile
    assert zweiter_faktor.split("\n")[0] == "Zweiten Faktor von Benutzer „Bea <b>Büro</b>“ (Benutzername „bea“) wirklich zurücksetzen?"
    assert sitzungen.split("\n")[0] == "Alle Sitzungen von Benutzer „Bea <b>Büro</b>“ (Benutzername „bea“) beenden?"
