"""Einmaliger Datenumzug von SQLite nach PostgreSQL (siehe CLAUDE.md "PostgreSQL-Umstieg").

Aufruf, Beispiel gegen die lokale, portable Testinstanz:

    python scripts/migrate_sqlite_to_postgres.py \
        --target-url postgresql+psycopg://erp:erp@127.0.0.1:5433/spielwiese

Liest standardmäßig die reale, produktive dachkonzepte_erp.db im Projektordner --
AUSSCHLIESSLICH LESEND: die Datei wird zuerst über SQLites eigene, für laufende
Anwendungen sichere Online-Backup-API (sqlite3.Connection.backup(), verträgt sich mit
einem parallel schreibenden Prozess) in eine temporäre Kopie gesichert, und diese Kopie
öffnet SQLite zusätzlich per "mode=ro"-URI -- ein Schreibversuch würde vom Treiber selbst
abgelehnt, nicht nur durch dieses Skript vermieden. Alles, was danach passiert, arbeitet
ausschließlich auf der temporären Kopie; die Originaldatei wird kein zweites Mal berührt.

Sicherheitsnetz gegen eine falsch übergebene Zielverbindung (Nutzervorgabe): das Skript
verweigert den Dienst, sobald in der Zieldatenbank auch nur eine Zeile in einer der
bekannten Tabellen (Base.metadata) steht -- außer --force-truncate wird ausdrücklich
gesetzt. Das Leeren selbst passiert dann ausschließlich über eine einzige
TRUNCATE-Anweisung, beschränkt auf genau die Tabellen, die dieses Projekt über sein
ORM-Modell kennt -- nie ein pauschales DROP SCHEMA/DROP DATABASE anhand der übergebenen
Verbindungszeichenfolge. Ohne --yes fragt es dafür zusätzlich interaktiv nach dem
Datenbanknamen zur Bestätigung (Muster: reset_admin_2fa.py).

Ablauf:
  1. Sicherheitsprüfung (Quelle ist SQLite, Ziel ist PostgreSQL, Zielverbindung sichtbar).
  2. alembic upgrade head gegen das Ziel (siehe Begründung weiter unten, warum das ein
     eigener Schritt in diesem Skript ist statt eine separate, manuelle Vorbedingung).
  3. Zielzustand prüfen -- leer, oder --force-truncate.
  4. Daten laden, Tabelle für Tabelle in der Reihenfolge von Base.metadata.sorted_tables --
     innerhalb einer selbstreferenzierenden Tabelle (quote_sections, order_sections tragen
     ein parent_id auf sich selbst) zusätzlich in mehreren Durchläufen, jeweils erst die
     Zeilen ohne offene Selbstreferenz, dann die, deren Elternzeile bereits geladen ist --
     siehe Begründung unten, warum NICHT stattdessen die Fremdschlüssel-Trigger
     abgeschaltet werden.
  5. Fremdschlüssel-Konsistenz der geladenen Daten selbst prüfen (nicht nur auf die
     Ladereihenfolge vertrauen) -- siehe Begründung unten, warum das hier nötig ist.
  6. Sequenzen auf den höchsten vorhandenen Wert je Tabelle mit Integer-Primärschlüssel
     setzen (nicht nur die drei ursprünglich vermuteten -- jede betroffene Tabelle).
  7. Verifikation: Zeilenzahl je Tabelle, Quelle gegen Ziel.
  8. Verschlüsselte Felder (SMTP-/Microsoft-365-Zugangsdaten, TOTP-Geheimnisse) probeweise
     entschlüsseln -- ohne den Klartext je auszugeben.

Warum alembic upgrade head EIN SCHRITT DIESES SKRIPTS ist, nicht eine separate manuelle
Vorbedingung: es ist rein additiv (legt nur Struktur an, verändert nie Daten) und wird bei
jedem Testlauf dieser Runde ohnehin gebraucht, bevor sich "ist die Zieltabelle leer?"
überhaupt sinnvoll prüfen lässt -- ein separater, leicht zu vergessender Handgriff hätte
hier keinen Sicherheitsgewinn gebracht, nur eine zusätzliche Fehlerquelle.

Warum NICHT ALTER TABLE ... DISABLE TRIGGER ALL (erster, verworfener Ansatz): zwei
Tabellen (quote_sections, order_sections) referenzieren sich selbst (parent_id), Zeilen
könnten also vor ihrem eigenen Elternknoten geladen werden -- PostgreSQL prüft eine
Fremdschlüssel-Bedingung standardmäßig SOFORT bei jeder einzelnen Zeile, nicht erst beim
Commit (ein DEFERRABLE-Constraint würde das lösen, aber Alembic/SQLAlchemy legt
Fremdschlüssel in diesem Projekt nicht als DEFERRABLE an -- SET CONSTRAINTS ALL DEFERRED
hätte deshalb keine Wirkung). ALTER TABLE ... DISABLE TRIGGER ALL wäre der dafür in der
PostgreSQL-Dokumentation vorgesehene Weg, tatsächlich ausprobiert -- schlägt aber mit
"InsufficientPrivilege: ... ist ein Systemtrigger" fehl, sobald die eigene Rolle (hier:
erp) nicht Superuser ist: die internen RI_ConstraintTrigger-Trigger, die eine
Fremdschlüssel-Bedingung durchsetzen, lassen sich nur von einem Superuser abschalten.
Auf einem echten, gehosteten Server wird die Anwendungsrolle aller Erfahrung nach KEIN
Superuser sein -- ein auf Superuser-Rechte angewiesenes Skript wäre dort schlicht
unbrauchbar. Deshalb: keine Trigger anfassen, sondern die beiden selbstreferenzierenden
Tabellen genau dort, wo sie tatsächlich betroffen sind, in Abhängigkeits-Reihenfolge
laden (mehrere Durchläufe je Tabelle) -- braucht keine besonderen Rechte, funktioniert
mit jeder Rolle, die INSERT auf ihre eigenen Tabellen darf.

Warum eine eigene Fremdschlüssel-Konsistenzprüfung NACH dem Laden nötig ist, nicht nur
Vertrauen in die Quelle: app/database.py setzt PRAGMA foreign_keys für SQLite bewusst
NICHT (siehe app/roof_areas.py, Kommentar "SQLite erzwingt Fremdschlüssel in diesem
Projekt nicht selbst") -- die reale Datenbank KANN also bereits verwaiste Zeilen
enthalten, die unter SQLite nie aufgefallen sind, aber unter PostgreSQLs sonst aktiven
Fremdschlüssel-Prüfungen zu echten Fehlern würden. Deshalb ein eigener, expliziter Scan
über jede einzelne Fremdschlüsselbeziehung (Base.metadata kennt sie alle), der etwaige
Wanderleichen laut und deutlich meldet, statt sie unbemerkt durchzulassen.
"""

import argparse
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import Integer, create_engine, func, select, text  # noqa: E402
from sqlalchemy.engine import Engine, make_url  # noqa: E402

from app import models  # noqa: E402,F401 (Import registriert alle Tabellen bei Base.metadata)
from app.crypto import decrypt_secret  # noqa: E402
from app.database import Base  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DB_FILE = PROJECT_ROOT / "dachkonzepte_erp.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--target-url", required=True,
        help="SQLAlchemy-Verbindungszeichenfolge der PostgreSQL-Zieldatenbank, "
             "z. B. postgresql+psycopg://erp:erp@127.0.0.1:5433/spielwiese",
    )
    parser.add_argument(
        "--source-db-file", default=str(DEFAULT_SOURCE_DB_FILE),
        help=f"Pfad zur SQLite-Quelldatei (Standard: {DEFAULT_SOURCE_DB_FILE}). "
             "Wird ausschließlich lesend geöffnet.",
    )
    parser.add_argument(
        "--force-truncate", action="store_true",
        help="Erlaubt das Leeren einer bereits nicht-leeren Zieldatenbank (nur die "
             "dem ORM bekannten Tabellen). Ohne dieses Kennzeichen verweigert das "
             "Skript den Dienst, sobald die Zieldatenbank bereits Daten enthält.",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Überspringt die interaktive Rückfrage vor dem Leeren einer nicht-leeren "
             "Zieldatenbank (nur zusammen mit --force-truncate relevant).",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000,
        help="Zeilen je INSERT-Stapel beim Laden (Standard: 1000).",
    )
    return parser.parse_args()


def snapshot_source(db_file: Path) -> tuple[Path, Path]:
    """Sichert die Quelldatei über SQLites Online-Backup-API in eine temporäre Kopie --
    verträgt sich mit einer parallel laufenden Anwendung, die dieselbe Datei offen hat.
    Die Quellverbindung wird dafür zusätzlich per "mode=ro"-URI geöffnet (siehe
    Moduldocstring). Gibt (Pfad zur Kopie, temporäres Verzeichnis zum späteren Aufräumen)
    zurück."""
    if not db_file.is_file():
        raise SystemExit(f"Quelldatei nicht gefunden: {db_file}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="dk_pg_migrate_"))
    tmp_path = tmp_dir / "source_snapshot.db"

    source_uri = f"file:{db_file.resolve().as_posix()}?mode=ro"
    src_conn = sqlite3.connect(source_uri, uri=True)
    try:
        dst_conn = sqlite3.connect(str(tmp_path))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return tmp_path, tmp_dir


def _chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def table_row_count(conn, table) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar() or 0


def ensure_target_ready(target_engine: Engine, tables: list, force_truncate: bool, yes: bool) -> None:
    with target_engine.begin() as conn:
        counts = {t.name: table_row_count(conn, t) for t in tables}
        nonempty = {name: c for name, c in counts.items() if c}
        if not nonempty:
            print("  Zieldatenbank ist leer (alle dem ORM bekannten Tabellen) -- kein Leeren nötig.")
            return

        total_rows = sum(nonempty.values())
        print(f"  Zieldatenbank enthält bereits Daten -- {len(nonempty)} von {len(tables)} "
              f"Tabellen nicht leer, {total_rows} Zeilen insgesamt:")
        for name, c in sorted(nonempty.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    {name}: {c} Zeilen")
        if len(nonempty) > 15:
            print(f"    ... und {len(nonempty) - 15} weitere Tabellen mit Daten.")

        if not force_truncate:
            raise SystemExit(
                "\nAbbruch: Zieldatenbank ist nicht leer. Mit --force-truncate ausdrücklich "
                "erlauben, dass genau die oben genannten, dem ORM bekannten Tabellen geleert "
                "werden (kein DROP DATABASE/SCHEMA, keine anderen Tabellen)."
            )

        target_name = make_url(str(target_engine.url)).database
        if not yes:
            confirm = input(
                f"\nZum Bestätigen den Datenbanknamen '{target_name}' erneut eintippen "
                f"(leert {total_rows} Zeilen in {len(nonempty)} Tabellen): "
            )
            if confirm.strip() != target_name:
                raise SystemExit("Abgebrochen -- Eingabe stimmt nicht mit dem Datenbanknamen überein.")

        table_list = ", ".join(f'"{t.name}"' for t in tables)
        conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
        print(f"  Geleert: {len(tables)} Tabellen (TRUNCATE ... RESTART IDENTITY CASCADE).")


def run_alembic_upgrade(target_url: str) -> None:
    env = {**__import__("os").environ, "DATABASE_URL": target_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
    )
    for line in (result.stdout + result.stderr).splitlines():
        print(f"  [alembic] {line}")
    if result.returncode != 0:
        raise SystemExit(f"alembic upgrade head gegen das Ziel ist fehlgeschlagen (exit {result.returncode}).")


def copy_table(source_conn, target_conn, table, batch_size: int) -> tuple[int, int]:
    rows = source_conn.execute(select(table)).mappings().all()
    if not rows:
        return 0, 0

    self_ref_cols = [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]
    if not self_ref_cols:
        for chunk in _chunked(rows, batch_size):
            target_conn.execute(table.insert(), [dict(r) for r in chunk])
        return len(rows), len(rows)

    # Selbstreferenzierende Tabelle (z. B. quote_sections/order_sections, parent_id auf
    # sich selbst) -- in Abhängigkeits-Reihenfolge laden, statt sich auf abgeschaltete
    # Fremdschlüssel-Trigger zu verlassen (siehe Moduldocstring). Mehrere Durchläufe:
    # erst die Zeilen ohne offene Selbstreferenz, dann die, deren Elternzeile bereits
    # geladen wurde -- deckt beliebige Verschachtelungstiefe ab.
    fk_col = self_ref_cols[0]
    pk_col = list(table.primary_key.columns)[0].name
    remaining = [dict(r) for r in rows]
    inserted_ids: set = set()
    inserted_total = 0
    while remaining:
        ready = [r for r in remaining if r[fk_col] is None or r[fk_col] in inserted_ids]
        if not ready:
            raise RuntimeError(
                f"Tabelle '{table.name}': {len(remaining)} Zeile(n) mit einer Selbstreferenz "
                f"({fk_col}), die auf keine bekannte Zeile zeigt -- verwaister Verweis bereits "
                f"in der Quelle (SQLite erzwingt Fremdschlüssel in diesem Projekt nicht)."
            )
        for chunk in _chunked(ready, batch_size):
            target_conn.execute(table.insert(), chunk)
        ready_ids = {r[pk_col] for r in ready}
        inserted_ids |= ready_ids
        inserted_total += len(ready)
        remaining = [r for r in remaining if r[pk_col] not in ready_ids]
    return len(rows), inserted_total


def find_orphans(conn, tables: list) -> list[tuple[str, str, str, str, int]]:
    problems = []
    for table in tables:
        for fk in table.foreign_keys:
            local_col = fk.parent
            ref_col = fk.column
            ref_table = ref_col.table
            ref_alias = ref_table.alias()
            join_cond = local_col == ref_alias.c[ref_col.name]
            query = (
                select(func.count())
                .select_from(table.outerjoin(ref_alias, join_cond))
                .where(local_col.isnot(None))
                .where(ref_alias.c[ref_col.name].is_(None))
            )
            count = conn.execute(query).scalar() or 0
            if count:
                problems.append((table.name, local_col.name, ref_table.name, ref_col.name, count))
    return problems


def reset_sequences(target_engine: Engine, tables: list) -> list[tuple[str, str, str]]:
    log = []
    with target_engine.begin() as conn:
        for table in tables:
            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) != 1 or not isinstance(pk_cols[0].type, Integer):
                continue
            col = pk_cols[0]
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": col.name}
            ).scalar()
            if not seq:
                continue
            conn.execute(
                text(
                    f'SELECT setval(:seq, COALESCE((SELECT MAX("{col.name}") FROM "{table.name}"), 1), '
                    f'(SELECT MAX("{col.name}") FROM "{table.name}") IS NOT NULL)'
                ),
                {"seq": seq},
            )
            log.append((table.name, col.name, seq))
    return log


def verify_row_counts(source_conn, target_engine: Engine, tables: list) -> list[tuple[str, int, int]]:
    mismatches = []
    with target_engine.connect() as conn:
        for table in tables:
            src = source_conn.execute(select(func.count()).select_from(table)).scalar() or 0
            tgt = table_row_count(conn, table)
            status = "OK" if src == tgt else "!!! ABWEICHUNG !!!"
            print(f"  {table.name}: Quelle={src} Ziel={tgt}  [{status}]")
            if src != tgt:
                mismatches.append((table.name, src, tgt))
    return mismatches


def verify_sensitive_fields(target_engine: Engine) -> list[tuple[str, bool, str | None]]:
    results: list[tuple[str, bool, str | None]] = []
    with target_engine.connect() as conn:
        smtp_rows = conn.execute(
            text("SELECT id, password_encrypted, graph_client_secret_encrypted FROM smtp_settings")
        ).fetchall()
        for row in smtp_rows:
            for field_name, value in (("password_encrypted", row[1]), ("graph_client_secret_encrypted", row[2])):
                if value is None:
                    continue
                label = f"smtp_settings.{field_name} (id={row[0]})"
                try:
                    decrypt_secret(value)
                    results.append((label, True, None))
                except ValueError as e:
                    results.append((label, False, str(e)))

        totp_rows = conn.execute(
            text("SELECT username, totp_secret_encrypted FROM app_users WHERE totp_secret_encrypted IS NOT NULL")
        ).fetchall()
        for username, secret in totp_rows:
            label = f"app_users.totp_secret_encrypted ({username})"
            try:
                decrypt_secret(secret)
                results.append((label, True, None))
            except ValueError as e:
                results.append((label, False, str(e)))

        recovery_count = conn.execute(text("SELECT COUNT(*) FROM two_factor_recovery_codes")).scalar() or 0
        if recovery_count:
            results.append((
                f"two_factor_recovery_codes: {recovery_count} Zeilen (Hash, nicht entschlüsselbar per Design)",
                True, None,
            ))
    return results


def main() -> int:
    args = parse_args()
    started = time.monotonic()

    target_url = make_url(args.target_url)
    if target_url.get_backend_name() != "postgresql":
        raise SystemExit(f"Zielverbindung muss PostgreSQL sein, nicht '{target_url.get_backend_name()}'.")

    source_db_file = Path(args.source_db_file)

    print("=" * 78)
    print("SCHRITT 1: Sicherheitsprüfung")
    print("=" * 78)
    print(f"  Quelle (nur lesend): {source_db_file}")
    print(f"  Ziel:                {target_url.render_as_string(hide_password=True)}")

    tmp_snapshot_path, tmp_dir = snapshot_source(source_db_file)
    print(f"  Konsistente Momentaufnahme der Quelle erstellt: {tmp_snapshot_path}")
    try:
        source_engine = create_engine(f"sqlite:///{tmp_snapshot_path}", future=True)
        target_engine = create_engine(args.target_url, future=True)
        tables = list(Base.metadata.sorted_tables)
        print(f"  {len(tables)} dem ORM bekannte Tabellen (Base.metadata.sorted_tables).")

        print()
        print("=" * 78)
        print("SCHRITT 2: alembic upgrade head gegen das Ziel")
        print("=" * 78)
        run_alembic_upgrade(args.target_url)

        print()
        print("=" * 78)
        print("SCHRITT 3: Zielzustand prüfen")
        print("=" * 78)
        ensure_target_ready(target_engine, tables, args.force_truncate, args.yes)

        print()
        print("=" * 78)
        print("SCHRITT 4: Daten laden")
        print("=" * 78)
        load_results: list[tuple[str, int, int]] = []
        orphans: list[tuple[str, str, str, str, int]] = []
        with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for table in tables:
                src_count, inserted = copy_table(source_conn, target_conn, table, args.batch_size)
                load_results.append((table.name, src_count, inserted))
                if src_count:
                    print(f"  {table.name}: {src_count} Zeilen gelesen, {inserted} geschrieben")

            print()
            print("=" * 78)
            print("SCHRITT 5: Fremdschlüssel-Konsistenz der geladenen Daten prüfen")
            print("=" * 78)
            orphans = find_orphans(target_conn, tables)

        total_rows_loaded = sum(inserted for _, _, inserted in load_results)
        tables_with_rows = sum(1 for _, src, _ in load_results if src)
        print(f"\n  Geladen: {total_rows_loaded} Zeilen über {tables_with_rows} nicht-leere Tabellen "
              f"(von {len(tables)} insgesamt).")

        if orphans:
            print("\n  !!! WARNUNG: verwaiste Fremdschlüssel-Verweise gefunden (bereits in der Quelle so "
                  "vorhanden -- SQLite erzwingt Fremdschlüssel in diesem Projekt nicht, siehe "
                  "app/roof_areas.py) !!!")
            for table_name, col, ref_table, ref_col, count in orphans:
                print(f"    {table_name}.{col} -> {ref_table}.{ref_col}: {count} verwaiste Zeile(n)")
        else:
            print("  Fremdschlüssel-Konsistenz: keine verwaisten Verweise gefunden.")

        print()
        print("=" * 78)
        print("SCHRITT 6: Sequenzen zurücksetzen")
        print("=" * 78)
        seq_log = reset_sequences(target_engine, tables)
        print(f"  {len(seq_log)} Sequenzen auf den höchsten vorhandenen Wert gesetzt "
              f"(Tabellen mit einspaltigem Integer-Primärschlüssel):")
        for table_name, col, seq in seq_log:
            print(f"    {table_name}.{col} -> {seq}")

        print()
        print("=" * 78)
        print("SCHRITT 7: Verifikation -- Zeilenzahl je Tabelle, Quelle gegen Ziel")
        print("=" * 78)
        with source_engine.connect() as source_conn:
            mismatches = verify_row_counts(source_conn, target_engine, tables)

        print()
        print("=" * 78)
        print("SCHRITT 8: Verschlüsselte Felder probeweise entschlüsseln")
        print("=" * 78)
        secret_results = verify_sensitive_fields(target_engine)
        if not secret_results:
            print("  Keine verschlüsselten SMTP-/TOTP-Felder in der Quelle gesetzt -- nichts zu prüfen.")
        for label, ok, error in secret_results:
            print(f"  {label}: {'entschlüsselbar' if ok else 'FEHLER -- ' + str(error)}")

        elapsed = time.monotonic() - started
        print()
        print("=" * 78)
        print("ZUSAMMENFASSUNG")
        print("=" * 78)
        print(f"  Tabellen insgesamt:      {len(tables)}")
        print(f"  Tabellen mit Zeilen:     {tables_with_rows}")
        print(f"  Zeilen geladen:          {total_rows_loaded}")
        print(f"  Dauer:                   {elapsed:.1f} s")
        print(f"  Zeilenzahl-Abweichungen: {len(mismatches)}")
        print(f"  Verwaiste FK-Verweise:   {len(orphans)}")
        secret_failures = [r for r in secret_results if not r[1]]
        print(f"  Nicht entschlüsselbare verschlüsselte Felder: {len(secret_failures)}")

        if mismatches or secret_failures:
            print("\n  ERGEBNIS: Es gab Auffälligkeiten -- siehe oben.")
            return 1
        print("\n  ERGEBNIS: Umzug ohne Auffälligkeiten abgeschlossen.")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
