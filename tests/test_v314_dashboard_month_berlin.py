"""Version 1.8.10 -- Dashboard "Meine Stunden (Monat)": Monatsgrenzen in Europe/Berlin statt UTC.

Bis 1.8.9 bildete das Dashboard den Monat über new Date(j, m, 1).toISOString().slice(0, 10). Das
ist Mitternacht Ortszeit in UTC umgerechnet, in Deutschland also der Vortag: der letzte Tag des
Vormonats zählte mit, der letzte Tag des laufenden Monats fehlte. Jetzt liefert berlinMonthRange()
aus app/templates/_berlin_date.html den Monat ausdrücklich in Europe/Berlin.

Beide Tests führen den echten JavaScript-Code der Vorlagen in node aus, an den Sekunden vor und
nach Mitternacht Berliner Zeit (Monats- und Jahreswechsel, Sommer- und Winterzeit) und jeweils mit
einer anderen Zeitzone des Prozesses, wie ein Browser mit anderer Systemzeitzone. node ist keine
Python-Abhängigkeit; fehlt es, werden die Tests übersprungen."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node nicht installiert -- die Tests führen JavaScript aus den Vorlagen aus.")

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
PROCESS_TIMEZONES = ("Europe/Berlin", "UTC", "America/New_York", "Asia/Tokyo")

# Zeitpunkt in UTC -> Monat in Europe/Berlin
MONTH_CHANGES = {
    "2026-09-30T21:59:59Z": ["2026-09-01", "2026-09-30"],  # 23:59:59 Sommerzeit: noch September
    "2026-09-30T22:00:00Z": ["2026-10-01", "2026-10-31"],  # 0:00 Sommerzeit: Oktober, in UTC noch der 30.
    "2026-10-31T22:59:59Z": ["2026-10-01", "2026-10-31"],  # seit dem 25.10. Winterzeit, UTC+1
    "2026-10-31T23:00:00Z": ["2026-11-01", "2026-11-30"],
    "2026-12-31T22:59:59Z": ["2026-12-01", "2026-12-31"],
    "2026-12-31T23:00:00Z": ["2027-01-01", "2027-01-31"],  # Jahreswechsel
    "2028-02-29T12:00:00Z": ["2028-02-01", "2028-02-29"],  # Schaltjahr
}


def _scripts(name: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S))


def _node(script: str, tz: str):
    result = subprocess.run([NODE], input=script, capture_output=True, text=True, encoding="utf-8",
                            env={**os.environ, "TZ": tz}, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("tz", PROCESS_TIMEZONES)
def test_berlin_month_range_changes_at_berlin_midnight(tz):
    script = _scripts("_berlin_date.html") + (
        f"\nconst instants = {json.dumps(list(MONTH_CHANGES))};"
        "\nprocess.stdout.write(JSON.stringify(Object.fromEntries(instants.map(s => [s, berlinMonthRange(new Date(s))]))));"
    )
    assert _node(script, tz) == MONTH_CHANGES


# Dashboard-Kachel selbst: renderKpisWidget() mit festgehaltener Uhr, die Abfrage an
# GET /api/time-entries/summary muss den Berliner Monat nennen.
DASHBOARD_CASES = {
    "2026-09-30T21:30:00Z": ("2026-09-01", "2026-09-30"),  # 23:30 Uhr am 30.09.
    "2026-09-30T22:30:00Z": ("2026-10-01", "2026-10-31"),  # 0:30 Uhr am 01.10., in UTC noch der 30.09.
    "2026-12-31T23:30:00Z": ("2027-01-01", "2027-01-31"),  # 0:30 Uhr am 01.01.2027
    "2026-10-15T10:00:00Z": ("2026-10-01", "2026-10-31"),  # Monatsmitte: alter Code lag auch hier daneben
}
HARNESS = r"""
const RealDate = Date;
let FIXED = null;
globalThis.Date = class extends RealDate {
  constructor(...args) { super(...(args.length ? args : [FIXED])); }
  static now() { return new RealDate(FIXED).getTime(); }
};
const authStatus = {authenticated: true, user: {employee_id: 7}};
const money = x => String(x);
let requested = [];
async function api(url) { requested.push(url); return url.startsWith('/api/time-entries/summary') ? {productive_hours: '12.50'} : []; }
(async () => {
  const out = {};
  for (const instant of INSTANTS) {
    FIXED = instant; requested = [];
    const container = {innerHTML: ''};
    await renderKpisWidget(container);
    const url = requested.find(u => u.startsWith('/api/time-entries/summary'));
    const q = new URLSearchParams(url.split('?')[1]);
    out[instant] = [q.get('start_date'), q.get('end_date'), q.get('employee_id'), container.innerHTML.includes('12,50 h')];
  }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


@pytest.mark.parametrize("tz", PROCESS_TIMEZONES)
def test_dashboard_requests_my_hours_for_the_berlin_month(tz):
    assert '{% include "_berlin_date.html" %}' in (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    dashboard = _scripts("dashboard.html")
    widget = re.search(r"async function renderKpisWidget\(container\)\{.*?\n\}\n", dashboard, flags=re.S)
    assert widget, "renderKpisWidget() in dashboard.html nicht gefunden"
    script = _scripts("_berlin_date.html") + "\n" + widget.group(0) + HARNESS.replace("INSTANTS", json.dumps(list(DASHBOARD_CASES)))
    assert _node(script, tz) == {k: [start, end, "7", True] for k, (start, end) in DASHBOARD_CASES.items()}
