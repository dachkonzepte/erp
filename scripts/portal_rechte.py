"""Rechte des Datenbank-Benutzers des Kundenportals setzen und prüfen (seit 1.11.0, Stufe P1a; app/portal/rechte.py).

Läuft als Benutzer des ERP (Eigentümer der Tabellen und Funktionen) nach jeder Migration, aus update.sh:

    .venv/bin/python scripts/portal_rechte.py --setzen && .venv/bin/python scripts/portal_rechte.py --pruefen

--setzen   setzt genau die Rechte aus app/portal/rechte.py (in einer Transaktion; jedes andere Recht der Rolle im Schema fällt weg; eigene Funktionen
           sind danach nicht mehr für alle ausführbar). Dazu CONNECT auf die Datenbank.
--pruefen  liest nur: jede Abweichung in einer Zeile (Rolle, Benutzer des ERP, Schema, Tabellen, Spalten, Sequenzen, Funktionen, Datenbank).

Optionen: --rolle NAME (Vorgabe dkportal), --schema NAME (Vorgabe public).
Rückgabe: 0 alles in Ordnung; 1 Abweichung oder Fehler beim Setzen; 2 DATABASE_URL fehlt oder ist nicht PostgreSQL (kein stiller Rückfall -- Vorfall 1).
Gibt nie ein Passwort oder die Verbindungszeichenfolge aus.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")


def main(argv=None) -> int:
    teil = argparse.ArgumentParser(description="Rechte des Datenbank-Benutzers des Kundenportals")
    art = teil.add_mutually_exclusive_group(required=True)
    art.add_argument("--setzen", action="store_true")
    art.add_argument("--pruefen", action="store_true")
    teil.add_argument("--rolle", default=None)
    teil.add_argument("--schema", default="public")
    args = teil.parse_args(argv)

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL fehlt -- erst die Umgebung laden (set -a; source .env; set +a).")
        return 2
    if not url.startswith("postgresql"):
        print("Die Rechte des Portals gibt es nur unter PostgreSQL.")
        return 2

    from sqlalchemy import create_engine

    from app.portal import rechte

    rolle = args.rolle or rechte.ROLLE
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            datenbank = conn.exec_driver_sql("SELECT current_database()").scalar()
            if args.setzen:
                try:
                    with conn.begin():
                        anweisungen = rechte.setzen(conn, rolle=rolle, schema=args.schema, datenbank=datenbank)
                except ValueError as exc:
                    print(f"Nicht gesetzt: {exc}")
                    return 1
                print(f"Rechte für {rolle} gesetzt: {len(rechte.LESEN)} Tabellen (nur Lesen), {len(rechte.FUNKTIONEN)} Funktionen, "
                      f"{len(anweisungen)} Anweisungen.")
                return 0
            abweichungen = rechte.pruefen(conn, rolle=rolle, schema=args.schema, datenbank=datenbank)
            conn.rollback()
    finally:
        engine.dispose()
    if abweichungen:
        print(f"Rechte für {rolle}: {len(abweichungen)} Abweichungen")
        for zeile in abweichungen:
            print(f"  {zeile}")
        return 1
    print(f"Rechte für {rolle} stimmen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
