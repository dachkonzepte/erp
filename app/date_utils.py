"""Reine Datumsarithmetik ohne Domänenbezug (seit 1.2.22) -- ausgelagert aus
app/maintenance_contracts.py, damit app/service_reports.py sie ebenfalls auf Modulebene
importieren kann, ohne einen Zirkel-Import zwischen den beiden Domänenmodulen zu erzeugen."""

import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
