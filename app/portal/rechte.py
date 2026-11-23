"""Rechte des Datenbank-Benutzers des Portals (seit 1.11.0, Bauplan P1, Abschnitt 1, und Nachtrag N1).

Eine Quelle: was hier nicht steht, darf der Benutzer des Portals nicht. Er liest nur die Firmendaten (für „Willkommen“ und die Fehlerseite, öffentliche
Angaben) und die Revision der Datenbank (Startprüfung); alles an Link und Sitzung ruft er ab 1.11.1 über Funktionen der Datenbank auf (FUNKTIONEN), die
dem Benutzer des ERP gehören. Auf keine Tabelle portal_* und auf keine Tabelle mit Kundendaten hat er ein Recht.

Gesetzt und geprüft vom Benutzer des ERP (Eigentümer der Tabellen) nach jeder Migration: scripts/portal_rechte.py --setzen / --pruefen (update.sh).
Bewusst nicht in den Migrationen -- eine alte Migration darf nicht vom heutigen Stand dieser Datei abhängen.

Jede Tabelle des Modells ist eingeordnet: hier oder in KEIN_ZUGRIFF (tests/test_v799_portal_rechte.py) -- eine neue Tabelle macht den Test rot.
"""

from __future__ import annotations

import re

from .funktionen import FUER_DAS_PORTAL

ROLLE = "dkportal"

# Tabelle -> Spalten, die der Benutzer des Portals lesen darf (nur SELECT, nur diese Spalten).
LESEN: dict[str, tuple[str, ...]] = {
    "general_settings": ("id", "company_name", "street", "postal_code", "city", "phone", "email", "website"),
    "alembic_version": ("version_num",),
}

# Funktionen, die der Benutzer des Portals aufrufen darf: Name -> Argumente (wie pg_get_function_identity_arguments()). Seit 1.11.1 genau die
# SECURITY-DEFINER-Funktionen aus app/portal/funktionen.py -- für Link und Sitzung (Nachtrag N1); die Helfer dort darf er nicht.
FUNKTIONEN: dict[str, str] = dict(FUER_DAS_PORTAL)

_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# Rechte, die der Benutzer des Portals auf keine ganze Tabelle hat; Rechte je Spalte (nur SELECT laut LESEN).
_TABELLENRECHTE = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
_SPALTENRECHTE = ("SELECT", "INSERT", "UPDATE", "REFERENCES")


def _name(wert: str) -> str:
    if not _NAME.match(wert or ""):
        raise ValueError(f"Ungültiger Name: {wert!r}")
    return wert


def _eigene_funktionen(conn, schema: str) -> list[tuple[str, str]]:
    """Funktionen im Schema, die dem angemeldeten Benutzer gehören und zu keiner Erweiterung gehören: (Name, Argumenttypen)."""
    from sqlalchemy import text
    return [tuple(r) for r in conn.execute(text(
        "SELECT p.proname, pg_get_function_identity_arguments(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = :s AND pg_get_userbyid(p.proowner) = current_user "
        "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e') "
        "ORDER BY p.proname, 2"), {"s": schema})]


def setzen(conn, *, rolle: str = ROLLE, schema: str = "public", datenbank: str | None = None) -> list[str]:
    """Setzt genau die Rechte aus LESEN und FUNKTIONEN für rolle im Schema (in der Transaktion von conn; der Aufrufer committet). Vorher fällt jedes andere
    Recht der Rolle auf Tabellen, Sequenzen und Funktionen des Schemas weg; jede eigene Funktion des Schemas ist danach nicht mehr für alle (PUBLIC)
    ausführbar, auch künftige nicht (ALTER DEFAULT PRIVILEGES). datenbank: dazu CONNECT auf diese Datenbank (auf dem Server; in Tests nicht).
    Rückgabe: die ausgeführten Anweisungen (ohne Geheimnisse). Fehlt eine Tabelle, Spalte oder Funktion, bricht es ab (erst die Migration)."""
    from sqlalchemy import text
    rolle, schema = _name(rolle), _name(schema)
    if conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": rolle}).first() is None:
        raise ValueError(f"Die Rolle {rolle} fehlt -- erst anlegen (Server-Schritt S3).")
    fehlt = pruefen_vorhanden(conn, schema=schema)
    if fehlt:
        raise ValueError("Erst die Migration: " + "; ".join(fehlt))
    anweisungen = [
        f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {rolle}",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {rolle}",
        f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {schema} FROM {rolle}",
        f"REVOKE ALL ON SCHEMA {schema} FROM {rolle}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC",
    ]
    anweisungen += [f"REVOKE ALL ON FUNCTION {schema}.{name}({argumente}) FROM PUBLIC" for name, argumente in _eigene_funktionen(conn, schema)]
    anweisungen.append(f"GRANT USAGE ON SCHEMA {schema} TO {rolle}")
    for tabelle, spalten in LESEN.items():
        anweisungen.append(f"GRANT SELECT ({', '.join(_name(s) for s in spalten)}) ON {schema}.{_name(tabelle)} TO {rolle}")
    for name, argumente in FUNKTIONEN.items():
        anweisungen.append(f"GRANT EXECUTE ON FUNCTION {schema}.{_name(name)}({argumente}) TO {rolle}")
    if datenbank:
        anweisungen.append(f"GRANT CONNECT ON DATABASE {_name(datenbank)} TO {rolle}")
    for a in anweisungen:
        conn.exec_driver_sql(a)
    return anweisungen


def pruefen_vorhanden(conn, *, schema: str = "public") -> list[str]:
    """Was aus LESEN und FUNKTIONEN in der Datenbank fehlt (leer = alles da)."""
    from sqlalchemy import text
    fehlt = []
    for tabelle, spalten in LESEN.items():
        da = {r[0] for r in conn.execute(text(
            "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :s AND c.relname = :t AND a.attnum > 0 AND NOT a.attisdropped"), {"s": schema, "t": tabelle})}
        if not da:
            fehlt.append(f"Tabelle {tabelle} fehlt")
        fehlt += [f"Spalte {tabelle}.{s} fehlt" for s in spalten if da and s not in da]
    vorhanden = set(_eigene_funktionen(conn, schema))
    fehlt += [f"Funktion {name}({argumente}) fehlt" for name, argumente in FUNKTIONEN.items() if (name, argumente) not in vorhanden]
    return fehlt


def pruefen(conn, *, rolle: str = ROLLE, schema: str = "public", datenbank: str | None = None) -> list[str]:
    """Jede Abweichung der tatsächlichen Rechte von LESEN und FUNKTIONEN, je eine Zeile ohne Geheimnisse (leer = alles stimmt). Liest nur.

    Geprüft: Rolle (kein Superuser, darf keine Rollen oder Datenbanken anlegen, umgeht keine Zeilenrechte, keine Replikation, erbt nichts, Mitglied keiner
    Rolle); der angemeldete Benutzer des ERP (kein Superuser, darf keine Rollen anlegen, umgeht keine Zeilenrechte -- die Funktionen laufen mit seinen
    Rechten); Schema (USAGE ja, CREATE nein); jede Tabelle und Sicht (kein Recht auf die ganze Tabelle), jede Spalte (genau LESEN), jede Sequenz (keins),
    jede eigene Funktion (genau FUNKTIONEN, keine für alle ausführbar); die Datenbank (kein CREATE; mit datenbank auch CONNECT)."""
    from sqlalchemy import text
    rolle, schema = _name(rolle), _name(schema)
    abw: list[str] = []
    r = conn.execute(text("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication, rolinherit FROM pg_roles WHERE rolname = :r"),
                     {"r": rolle}).first()
    if r is None:
        return [f"Rolle {rolle} fehlt"]
    for wert, text_ in zip(r, ("ist Superuser", "darf Rollen anlegen", "darf Datenbanken anlegen", "umgeht Zeilenrechte (BYPASSRLS)",
                               "darf replizieren", "erbt Rechte (INHERIT)")):
        if wert:
            abw.append(f"Rolle {rolle} {text_}")
    for (mitglied_von,) in conn.execute(text(
            "SELECT g.rolname FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid JOIN pg_roles u ON u.oid = m.member "
            "WHERE u.rolname = :r ORDER BY 1"), {"r": rolle}):
        abw.append(f"Rolle {rolle} ist Mitglied von {mitglied_von}")
    erp = conn.execute(text("SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = current_user")).first()
    for wert, text_ in zip(erp, ("ist Superuser", "darf Rollen anlegen", "umgeht Zeilenrechte (BYPASSRLS)")):
        if wert:
            abw.append(f"Der Benutzer des ERP {text_} -- die Funktionen mit SECURITY DEFINER liefen mit diesen Rechten")
    if not conn.execute(text("SELECT has_schema_privilege(:r, :s, 'USAGE')"), {"r": rolle, "s": schema}).scalar():
        abw.append(f"Schema {schema}: USAGE fehlt")
    if conn.execute(text("SELECT has_schema_privilege(:r, :s, 'CREATE')"), {"r": rolle, "s": schema}).scalar():
        abw.append(f"Schema {schema}: darf Objekte anlegen (CREATE)")
    if conn.execute(text("SELECT has_database_privilege(:r, current_database(), 'CREATE')"), {"r": rolle}).scalar():
        abw.append("Datenbank: darf Schemas anlegen (CREATE)")
    if datenbank and not conn.execute(text("SELECT has_database_privilege(:r, :d, 'CONNECT')"), {"r": rolle, "d": datenbank}).scalar():
        abw.append(f"Datenbank {datenbank}: CONNECT fehlt")

    # Tabellen, Sichten und Sequenzen des Schemas: je eine Abfrage für die Rechte auf ganze Tabellen, je Spalte und je Sequenz
    vorhanden = {r[0] for r in conn.execute(text(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = :s AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"),
        {"s": schema})}
    abw += [f"Tabelle {name}: {recht} auf die ganze Tabelle" for name, recht in conn.execute(text(
        "SELECT c.relname, p.recht FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "CROSS JOIN unnest(CAST(:rechte AS text[])) AS p(recht) "
        "WHERE n.nspname = :s AND c.relkind IN ('r', 'p', 'v', 'm', 'f') AND has_table_privilege(:r, c.oid, p.recht) ORDER BY 1, 2"),
        {"s": schema, "r": rolle, "rechte": list(_TABELLENRECHTE)})]
    hat = {(t, s, recht) for t, s, recht in conn.execute(text(
        "SELECT c.relname, a.attname, p.recht FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped "
        "CROSS JOIN unnest(CAST(:rechte AS text[])) AS p(recht) "
        "WHERE n.nspname = :s AND c.relkind IN ('r', 'p', 'v', 'm', 'f') AND has_column_privilege(:r, c.oid, a.attnum, p.recht)"),
        {"s": schema, "r": rolle, "rechte": list(_SPALTENRECHTE)})}
    soll = {(t, s, "SELECT") for t, spalten in LESEN.items() for s in spalten}
    abw += [f"Spalte {t}.{s}: {recht} zu viel" for t, s, recht in sorted(hat - soll)]
    abw += [f"Spalte {t}.{s}: {recht} fehlt" for t, s, recht in sorted(soll - hat) if t in vorhanden]
    abw += [f"Tabelle {t} fehlt" for t in LESEN if t not in vorhanden]
    abw += [f"Sequenz {name}: {recht}" for name, recht in conn.execute(text(
        "SELECT c.relname, p.recht FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "CROSS JOIN unnest(CAST(ARRAY['USAGE', 'SELECT', 'UPDATE'] AS text[])) AS p(recht) "
        "WHERE n.nspname = :s AND c.relkind = 'S' AND has_sequence_privilege(:r, c.oid, p.recht) ORDER BY 1, 2"), {"s": schema, "r": rolle})]

    for oid, name, argumente, acl in conn.execute(text(
            "SELECT p.oid, p.proname, pg_get_function_identity_arguments(p.oid), p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = :s AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e') "
            "ORDER BY p.proname, 3"), {"s": schema}):
        if acl is None or re.search(r"(^|[{,])=[^,}]*X", acl):
            abw.append(f"Funktion {name}({argumente}): für alle ausführbar (PUBLIC)")
        darf = conn.execute(text("SELECT has_function_privilege(:r, CAST(:o AS oid), 'EXECUTE')"), {"r": rolle, "o": oid}).scalar()
        soll_f = FUNKTIONEN.get(name) == argumente
        if darf and not soll_f:
            abw.append(f"Funktion {name}({argumente}): EXECUTE zu viel")
        elif soll_f and not darf:
            abw.append(f"Funktion {name}({argumente}): EXECUTE fehlt")
    abw += [f"Funktion {n}({a}) fehlt" for n, a in FUNKTIONEN.items()
            if not conn.execute(text("SELECT 1 FROM pg_proc p JOIN pg_namespace s ON s.oid = p.pronamespace WHERE s.nspname = :s AND p.proname = :n "
                                     "AND pg_get_function_identity_arguments(p.oid) = :a"), {"s": schema, "n": n, "a": a}).first()]
    return abw
