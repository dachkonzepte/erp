"""Alle Klicktests (seit 1.8.75): scripts/klicktest_*.py, je einer in einem eigenen Prozess mit eigenem Arbeitsordner, danach eine
Übersicht mit Ergebnis, Prüfungen und Laufzeit je Test und gesamt. Seit 1.8.108 auf Wunsch mehrere zugleich (--gleichzeitig).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_alle.py [--gleichzeitig N] [--nur TEIL ...] [--ab NAME] [--ausgabe ORDNER]
                                                         [--zeitlimit SEK]

    --gleichzeitig N  so viele Klicktests zugleich (Vorgabe 1 = nacheinander, alphabetisch wie bisher; gemessen: 4). Ein
                    Klicktest mit ALLEIN = "<Grund>" auf Modulebene läuft dabei allein -- zuerst, nacheinander, solange kein
                    anderer läuft --, danach die übrigen zu N zugleich, die längsten zuerst (Dauer aus KLICKTEST_DAUERN,
                    unbekannte vorn)
    --nur TEIL      nur Klicktests, deren Name TEIL enthält (mehrfach möglich)
    --ab NAME       erst ab diesem Klicktest (alphabetisch), z. B. nach einem Abbruch
    --ausgabe       Ordner für Protokolle, Screenshots und die Übersicht (Vorgabe: neuer Temp-Ordner); je Klicktest ein
                    Unterordner als dessen --arbeitsordner, dazu <name>.log mit der vollen Ausgabe
    --zeitlimit     Sekunden je Klicktest (Vorgabe 900); danach wird der Klicktest samt seinen Kindprozessen (ERP-Instanz,
                    Chrome) über die eigene PID beendet (taskkill /T, Regel 12) und als "Zeitlimit" geführt. Ein Klicktest,
                    der selbst abbricht (Rückgabecode 3: eigenes Zeitlimit, Gegenprobe), heißt ebenso "Zeitlimit".

WIEDERHOLUNG (seit 1.9.19): ein Klicktest, der rot endet (Rückgabecode 1) oder ins Zeitlimit läuft und dessen einzige Abweichung eine
Anfrage ist, die laut Verbindungsprotokoll nie beim Server ankam (nur_nicht_angekommen(); Befund Runde 6 Punkt 2 in
docs/archiv/testablauf-und-klicktests.md: Testaufbau, nicht das Programm), läuft genau einmal neu -- mit eigenem Protokoll
<name>.wiederholt.log und Arbeitsordner <name>_wiederholt, das erste Protokoll bleibt. Zeile und Zusammenfassung nennen jede Wiederholung
mit dem Ergebnis des ersten Laufs und der Anfrage; gezählt wird das Ergebnis des zweiten. Nie wiederholt: Rückgabecode 2 (Aufbau
gescheitert), 3 (eigenes Zeitlimit, Gegenprobe), eine Abweichung ohne Netzwerkprotokoll oder mit einer angekommenen, fehlgeschlagenen oder
beim Seitenwechsel offen gebliebenen Anfrage.

Rückgabecode 0, wenn alle wie erwartet liefen. Jeder Klicktest startet seine eigene Wegwerf-Instanz (Regel 16, eigene Ports, eigener
Arbeitsordner) und beendet seine Prozesse selbst; dieses Skript beendet nur die eigenen Kindprozesse und deren Baum. Kein Teil der
pytest-Suite."""

import argparse
import ast
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
CODE_ZEITLIMIT = 3  # wie cdp_klicktest.CODE_ZEITLIMIT

# Seit 1.8.108: Laufzeit je Klicktest in Sekunden (allein gemessen, 1.8.108) -- nur für die Reihenfolge mit --gleichzeitig: die längsten
# zuerst, damit am Ende nicht einer allein übrig bleibt. Ein fehlender Eintrag (neuer Klicktest) kommt vorn; veraltete Werte schaden
# nur der Laufzeit, nicht dem Ergebnis.
KLICKTEST_DAUERN: dict[str, float] = {
    "klicktest_abgleich_sperre": 11, "klicktest_abnahme": 17, "klicktest_abnahme_aus_protokoll": 15,
    "klicktest_abnahmeprotokoll": 13, "klicktest_abschliessen": 20, "klicktest_angebot_interne_notiz": 8,
    "klicktest_anmelden": 42, "klicktest_anmeldung_abgelaufen": 9, "klicktest_arbeitsvorbereitung": 8,
    "klicktest_aufgaben_ohne_zustaendigkeit": 10, "klicktest_auftrag_sperren": 10, "klicktest_auswahl_inaktiv": 9,
    "klicktest_auswahl_restfaelle": 11, "klicktest_bedenkenanzeige": 17, "klicktest_bedenkenanzeige_versand": 12,
    "klicktest_behinderungsanzeige": 14, "klicktest_behinderungsanzeige_abschluss": 32, "klicktest_behinderungsanzeige_versand": 16,
    "klicktest_beleg_und_hinweis": 15, "klicktest_beteiligte": 15, "klicktest_beteiligte_stammdaten": 13,
    "klicktest_browser_datum": 13, "klicktest_checkliste_abschnitte": 12, "klicktest_checkliste_unterschrift": 13,
    "klicktest_checkliste_verwerfen": 11, "klicktest_checkliste_zweck": 12, "klicktest_dashboard_monatswechsel": 9,
    "klicktest_dateien_nie_aktiv": 32, "klicktest_daten_im_html": 13, "klicktest_ds_schriften": 9, "klicktest_endrechnung": 12,
    "klicktest_feierabend": 10, "klicktest_feste_fassung": 12, "klicktest_finanzen_zahlbetrag": 11,
    "klicktest_fremde_seite": 10, "klicktest_hochladen": 12, "klicktest_leistungszeitraum": 11,
    "klicktest_maengel": 14, "klicktest_maengel_monteur": 12, "klicktest_mahnen_endrechnung": 11,
    "klicktest_mahnwesen": 13, "klicktest_monteur_dachflaechen": 8, "klicktest_monteur_navigation": 12,
    "klicktest_nachtrag": 11, "klicktest_nebenforderungen": 13, "klicktest_neue_ordnung": 26, "klicktest_objekt_anderer_kunde": 10,
    "klicktest_protokoll_maengel": 12, "klicktest_protokoll_versand": 11, "klicktest_rahmen": 47, "klicktest_rechnung_rundung": 9,
    "klicktest_rechnungen_sperren": 13, "klicktest_rechnungsdatum": 9, "klicktest_teil_updates": 9,
    "klicktest_ueberzahlung": 12, "klicktest_unterzeichner": 13, "klicktest_veraltete_antworten": 19,
    "klicktest_versand_im_kontext": 11,
    "klicktest_versandprotokoll": 30, "klicktest_versandverlauf": 30, "klicktest_vertrag_abschrift": 14,
    "klicktest_vertrag_festschreiben": 15, "klicktest_vertrag_gewaehrleistung": 11, "klicktest_vertrag_unterschrift": 32,
    "klicktest_vertragsgrundlage": 12, "klicktest_vertragsvorlagen": 13, "klicktest_vertraute_geraete": 9,
    "klicktest_verzugszinsen": 17, "klicktest_zahlungen": 17, "klicktest_zahlungen_kleinkram": 15,
    "klicktest_zeichenflaeche": 13, "klicktest_zeitbuchungen_liste": 17,
}


def _dauer(sekunden: float) -> str:
    m, s = divmod(int(round(sekunden)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


TASKKILL_SEKUNDEN = 30  # wie cdp_klicktest.TASKKILL_SEKUNDEN (seit 1.8.111)


def _taskkill(pid: int) -> list[str]:
    return ["taskkill", "/PID", str(pid), "/T", "/F"]


def _baum_beenden(pid: int) -> None:
    """Nur der eigene Kindprozess und dessen Kinder (Regel 12) -- nie über einen Prozessnamen. Seit 1.8.111 mit Zeitlimit wie
    cdp_klicktest.beenden() (Nebenbefund 4 aus 1.8.108)."""
    if os.name == "nt":
        try:
            subprocess.run(_taskkill(pid), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TASKKILL_SEKUNDEN)
        except subprocess.TimeoutExpired:
            print(f"Hinweis: taskkill für PID {pid} nach {TASKKILL_SEKUNDEN} s abgebrochen -- prüfen über die PID (Regel 12).",
                  flush=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


NICHT_ANGEKOMMEN = "Server: nicht angekommen"


def nur_nicht_angekommen(protokoll: str) -> list[str] | None:
    """Seit 1.9.19: die Anfragen, die nie beim Server ankamen, wenn jede Abweichung des Protokolls genau an solchen hängt -- sonst None.

    Eine Abweichung ist eine Zeile „XX  …“; das Werkzeug druckt unmittelbar darunter das Netzwerkprotokoll (cdp_klicktest.py):
    „    Netzwerk: N offen“ mit je offener Anfrage einer Zeile „      METHODE /pfad …“ und darunter „          Server: …“, oder
    „    Netzwerk: unverändert seit der letzten Meldung (N offen)“. Sie zählt nur, wenn jede offene Anfrage „Server: nicht angekommen“
    heißt (bzw. der letzte Bericht so war) und der Bericht sonst nichts meldet (fehlgeschlagen, beim Seitenwechsel offen geblieben).
    Eine Abweichung ohne Netzwerkprotokoll, „keine offenen Anfragen“ oder ein Protokoll ohne Abweichung: None."""
    zeilen = protokoll.splitlines()
    anfragen: list[str] = []
    abweichungen = 0
    letzter_zaehlt = False
    for i, zeile in enumerate(zeilen):
        if not zeile.startswith("XX  "):
            continue
        abweichungen += 1
        block = []
        for folge in zeilen[i + 1:]:
            if not folge.startswith("    "):
                break
            block.append(folge)
        kopf = block[0].strip() if block else ""
        if kopf.startswith("Netzwerk: unverändert seit der letzten Meldung"):
            if not letzter_zaehlt:
                return None
            continue
        if not re.fullmatch(r"Netzwerk: \d+ offen", kopf):
            return None
        offen = [b for b in block[1:] if re.match(r" {6}[A-Z]+ /", b)]
        server = [b.strip() for b in block[1:] if b.strip().startswith("Server:")]
        sonst = [b for b in block[1:] if b.strip().startswith("Netzwerk:")]
        if not offen or sonst or len(server) != len(offen) or not all(s.startswith(NICHT_ANGEKOMMEN) for s in server):
            return None
        anfragen += [re.split(r"\s{2,}seit ", o.strip())[0] for o in offen]
        letzter_zaehlt = True
    return anfragen if abweichungen and anfragen else None


def klicktests(nur: list[str], ab: str | None) -> list[Path]:
    alle = sorted(p for p in SCRIPTS.glob("klicktest_*.py") if p.name != Path(__file__).name)
    if nur:
        alle = [p for p in alle if any(t in p.stem for t in nur)]
    if ab:
        alle = [p for p in alle if p.stem >= ab.removesuffix(".py")]
    return alle


def allein_grund(skript: Path) -> str | None:
    """Der Text von ALLEIN = "<Grund>" auf Modulebene des Klicktests, sonst None -- gelesen, nicht importiert."""
    for node in ast.parse(skript.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ALLEIN" for t in node.targets) \
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value.strip():
            return node.value.value.strip()
    return None


def gruppen(liste: list[Path], gleichzeitig: int) -> list[tuple[list[Path], int]]:
    """Reihenfolge des Laufs als (Klicktests, wie viele zugleich): nacheinander alphabetisch wie bisher; mit mehreren zugleich zuerst
    die mit ALLEIN einzeln, dann die übrigen, die längsten zuerst (KLICKTEST_DAUERN, unbekannte vorn)."""
    if gleichzeitig == 1:
        return [(list(liste), 1)]
    allein = [p for p in liste if allein_grund(p)]
    rest = sorted((p for p in liste if p not in allein), key=lambda p: (-KLICKTEST_DAUERN.get(p.stem, float("inf")), p.stem))
    return [(allein, 1), (rest, gleichzeitig)]


class Lauf:
    """Ein laufender Klicktest: eigener Prozess, Ausgabe in <name>.log. Seit 1.9.19 wiederholung = der Hinweis zum ersten Lauf, wenn dies
    der zweite ist (Protokoll <name>.wiederholt.log, Arbeitsordner <name>_wiederholt)."""

    def __init__(self, skript: Path, ausgabe: Path, env: dict, wiederholung: str | None = None):
        self.skript = skript
        self.name = skript.stem
        self.wiederholung = wiederholung
        self.log = ausgabe / f"{self.name}{'.wiederholt' if wiederholung else ''}.log"
        self._out = open(self.log, "wb")
        self.start = time.monotonic()
        arbeitsordner = ausgabe / f"{self.name}{'_wiederholt' if wiederholung else ''}"
        self.proc = subprocess.Popen([sys.executable, str(skript), "--arbeitsordner", str(arbeitsordner)], cwd=ROOT,
                                     env=env, stdout=self._out, stderr=subprocess.STDOUT)
        self.code: int | None = None
        self.zeitlimit = False

    def fertig(self, zeitlimit: float) -> bool:
        if self.proc.poll() is not None:
            self.code = self.proc.returncode
        elif time.monotonic() - self.start > zeitlimit:
            _baum_beenden(self.proc.pid)
            self.proc.wait(timeout=30)
            self.zeitlimit = True
        else:
            return False
        self.dauer = time.monotonic() - self.start
        self._out.close()
        return True

    def abbrechen(self) -> None:
        if self.proc.poll() is None:
            _baum_beenden(self.proc.pid)
        self._out.close()

    def wiederholen(self) -> str | None:
        """Seit 1.9.19: der Hinweis für einen zweiten Lauf, wenn dieser der erste war, rot (1) oder im Zeitlimit von klicktest_alle
        endete und seine einzige Abweichung Anfragen sind, die nie beim Server ankamen -- sonst None."""
        if self.wiederholung is not None or not (self.code == 1 or self.zeitlimit):
            return None
        anfragen = nur_nicht_angekommen(self.log.read_text(encoding="utf-8", errors="replace"))
        if not anfragen:
            return None
        _, ergebnis, pruefungen, _, _ = self.zeile()
        return f"1. Lauf {ergebnis} {pruefungen}, Anfrage nicht angekommen: {'; '.join(anfragen)}"

    def zeile(self) -> tuple[str, str, str, float, str | None]:
        text = self.log.read_text(encoding="utf-8", errors="replace")
        treffer = re.findall(r"(\d+) von (\d+) Prüfungen wie erwartet", text)
        pruefungen = f"{treffer[-1][0]}/{treffer[-1][1]}" if treffer else "-"
        if self.zeitlimit or self.code == CODE_ZEITLIMIT:
            ergebnis = "Zeitlimit"
        else:
            ergebnis = "OK" if self.code == 0 else f"ROT ({self.code})"
        return self.name, ergebnis, pruefungen, self.dauer, self.wiederholung


def ausfuehren(gruppen: list[tuple[list[Path], int]], ausgabe: Path, env: dict, zeitlimit: float, gesamt: int) -> list[tuple]:
    """Gruppen nacheinander, innerhalb einer Gruppe bis zu n zugleich (n = 1: nacheinander). Druckt je fertigem Klicktest eine Zeile.
    Seit 1.9.19: ein Klicktest, dessen einzige Abweichung Anfragen sind, die nie ankamen (Lauf.wiederholen()), läuft einmal neu -- als
    nächster seiner Gruppe; gezählt und gedruckt wird erst der zweite Lauf, mit dem Hinweis zum ersten (5. Feld der Zeile)."""
    zeilen: list[tuple] = []
    laufend: list[Lauf] = []
    try:
        for liste, n in gruppen:
            warteschlange: list[tuple[Path, str | None]] = [(p, None) for p in liste]
            while warteschlange or laufend:
                while warteschlange and len(laufend) < n:
                    skript, wiederholung = warteschlange.pop(0)
                    laufend.append(Lauf(skript, ausgabe, env, wiederholung))
                for lauf in [x for x in laufend if x.fertig(zeitlimit)]:
                    laufend.remove(lauf)
                    hinweis = lauf.wiederholen()
                    if hinweis:
                        print(f"[wiederholt] {lauf.name} -- {hinweis}", flush=True)
                        warteschlange.insert(0, (lauf.skript, hinweis))
                        continue
                    zeile = lauf.zeile()
                    zeilen.append(zeile)
                    zusatz = f"  (wiederholt -- {zeile[4]})" if zeile[4] else ""
                    print(f"[{len(zeilen):>2}/{gesamt}] {zeile[1]:<9} {zeile[2]:>7}  {_dauer(zeile[3]):>7}  {zeile[0]}{zusatz}", flush=True)
                if laufend:
                    time.sleep(0.2)
    finally:
        for lauf in laufend:  # Abbruch (Strg+C): nur die eigenen Prozessbäume
            lauf.abbrechen()
    return zeilen


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Alle Klicktests, nacheinander oder mehrere zugleich")
    parser.add_argument("--gleichzeitig", type=int, default=1, metavar="N")
    parser.add_argument("--nur", action="append", default=[])
    parser.add_argument("--ab")
    parser.add_argument("--ausgabe", type=Path)
    parser.add_argument("--zeitlimit", type=int, default=900)
    args = parser.parse_args()
    if args.gleichzeitig < 1:
        parser.error("--gleichzeitig braucht mindestens 1")

    ausgabe = (args.ausgabe or Path(tempfile.mkdtemp(prefix="erp-klicktests-"))).resolve()
    ausgabe.mkdir(parents=True, exist_ok=True)
    liste = klicktests(args.nur, args.ab)
    reihenfolge = gruppen(liste, args.gleichzeitig)
    if args.gleichzeitig == 1:
        print(f"{len(liste)} Klicktests nacheinander, Ausgabe {ausgabe}", flush=True)
    else:
        (allein, _), (rest, _) = reihenfolge
        print(f"{len(liste)} Klicktests, {len(allein)} davon allein ({', '.join(p.stem for p in allein) or '-'}), die übrigen "
              f"{len(rest)} zu {args.gleichzeitig} zugleich; Ausgabe {ausgabe}", flush=True)
    # Seit 1.8.97 ungepuffert: läuft ein Test ins Zeitlimit, steht im Protokoll bis zuletzt, was er gedruckt hat (auch das
    # Netzwerkprotokoll des Werkzeugs) -- gepuffert ging es beim Beenden verloren.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    gesamt_start = time.monotonic()
    zeilen = sorted(ausfuehren(reihenfolge, ausgabe, env, args.zeitlimit, len(liste)))
    gesamt = time.monotonic() - gesamt_start
    art = "nacheinander" if args.gleichzeitig == 1 else f"zu {args.gleichzeitig} zugleich"
    text = zusammenfassung(zeilen, art, gesamt, ausgabe)
    (ausgabe / "zusammenfassung.txt").write_text(
        "\n".join(text + ["", *(f"{z[1]:<9} {z[2]:>7}  {_dauer(z[3]):>7}  {z[0]}" + (f"  (wiederholt -- {z[4]})" if z[4] else "")
                              for z in zeilen)]) + "\n", encoding="utf-8")
    print("\n".join(text), flush=True)
    return 0 if all(z[1] == "OK" for z in zeilen) else 1


def zusammenfassung(zeilen: list[tuple], art: str, gesamt: float, ausgabe: Path) -> list[str]:
    """Kopfzeile, je nicht erwarteter Klicktest eine Zeile mit Protokoll, seit 1.9.19 je wiederholter eine Zeile mit beiden Protokollen
    -- auch wenn der zweite Lauf wie erwartet war (im Bericht immer ausweisen)."""
    ok = sum(1 for z in zeilen if z[1] == "OK")
    wiederholt = [z for z in zeilen if z[4]]
    kopf = f"{ok} von {len(zeilen)} Klicktests wie erwartet ({art})"
    if wiederholt:
        kopf += f", davon {len(wiederholt)} wiederholt (nur Anfrage nicht angekommen)"
    text = [kopf + f", Laufzeit gesamt {_dauer(gesamt)}"]
    text += [f"  {z[1]:<9} {z[2]:>7}  {_dauer(z[3]):>7}  {z[0]}  (Protokoll: {ausgabe / (z[0] + ('.wiederholt' if z[4] else '') + '.log')})"
             for z in zeilen if z[1] != "OK"]
    text += [f"  wiederholt: {z[0]} -- {z[4]}; 2. Lauf {z[1]} {z[2]} (Protokolle: {z[0]}.log, {z[0]}.wiederholt.log)" for z in wiederholt]
    return text


if __name__ == "__main__":
    sys.exit(main())
