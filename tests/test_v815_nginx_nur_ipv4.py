"""Version 1.11.20 (P1f, S0 auf dem Server am 25.11.2026): nginx lauscht dort nur auf 0.0.0.0:80 und 0.0.0.0:443, nicht auf [::], und keine der Adressen
(app, web, www, kunde) hat einen AAAA-Eintrag. Der Block des Kundenportals lauscht deshalb wie die übrigen Seiten des Servers nur über IPv4.

    Blöcke      je server{} genau eine Zeile listen: der erste „listen 80;“, der zweite „listen 443 ssl;“ mit „http2 on;“ (seit 1.11.40; bis dahin
                „listen 443 ssl http2;“, veraltet seit nginx 1.25.1)
    IPv6        außerhalb der Kommentare keine Adresse [::] und kein ipv6only
    S7          der erste Teil der Datei (awk bis zum zweiten „server {“) zählt mit grep -c „listen 80;“ einmal und „listen 443“ keinmal -- Kommentare
                eingeschlossen, wie grep sie zählt
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = (ROOT / "scripts" / "server" / "nginx-kunde.conf").read_text(encoding="utf-8")


def _ohne_kommentar(text):
    return [z.split("#")[0].strip() for z in text.splitlines() if z.split("#")[0].strip()]


def _bloecke():
    teile = re.split(r"(?m)^server \{", CONF)
    return teile[1:]


def test_je_block_genau_ein_listen_ueber_ipv4():
    bloecke = _bloecke()
    assert len(bloecke) == 2
    listen = [[z for z in _ohne_kommentar(b) if z.startswith("listen")] for b in bloecke]
    assert listen == [["listen 80;"], ["listen 443 ssl;"]]
    assert [[z for z in _ohne_kommentar(b) if z.startswith("http2")] for b in bloecke] == [[], ["http2 on;"]]  # seit 1.11.40
    assert not [z for z in _ohne_kommentar(CONF) if z.startswith("listen") and "http2" in z]


def test_keine_adresse_fuer_ipv6():
    zeilen = _ohne_kommentar(CONF)
    assert not [z for z in zeilen if "[::" in z]
    assert not [z for z in zeilen if "ipv6only" in z]


def test_erster_teil_fuer_s7():
    # wie in S7: awk '/^server [{]/{n++} n<2' -- alles vor dem zweiten Block, dann grep -c (zählt Zeilen, auch Kommentare)
    erster, n = [], 0
    for z in CONF.splitlines():
        if re.match(r"server [{]", z):
            n += 1
        if n < 2:
            erster.append(z)
    assert sum("listen 80;" in z for z in erster) == 1
    assert sum("listen 443" in z for z in erster) == 0
