"""Funktionen der Datenbank für Link und Sitzung des Kundenportals (seit 1.11.1, Stufe P1a; Nachtrag N1 zum Bauplan P1).

Alles, was an einem Link oder einer Sitzung hängt, läuft über diese Funktionen. Sie gehören dem Benutzer des ERP und laufen mit seinen Rechten (SECURITY
DEFINER); der Benutzer des Portals darf nur sie aufrufen (app/portal/rechte.py::FUNKTIONEN) und hat auf keine Tabelle portal_* und keine Kundendaten ein
Recht. Ohne Link legt so auch ein übernommener Portal-Prozess keine Sitzung an und liest keine Namen.

Regeln (Wächter in tests/test_v800_portal_funktionen.py):
- Jede Funktion mit festem search_path: pg_catalog, das Schema der Tabellen, pg_temp -- @SCHEMA@ setzt beim Anlegen current_schema() ein (auf dem Server
  public, in Tests das Wegwerf-Schema). Kein dynamisches SQL (kein EXECUTE, kein format()). Für alle nicht ausführbar (REVOKE ALL … FROM PUBLIC); die
  Helfer (ohne SECURITY DEFINER) laufen nur aus den Funktionen heraus.
- Eingaben nur als Prüfwerte (64 Zeichen hexadezimal, app/portal/pruefwerte.py) -- Link, Cookie und Code selbst kommen nie in die Datenbank, auch nicht als
  Parameter im Log von PostgreSQL. Alles andere: „ungueltig“, ohne etwas zu schreiben.
- Zeit nur aus portal_jetzt() (now() der Datenbank, naiv UTC wie die übrigen Spalten), nie vom Portal -- sonst verlängerte ein übernommener Prozess Codes.
- Sperren in fester Reihenfolge: Zugang (FOR NO KEY UPDATE) -> Sitzung -> Code. Das ERP sperrt beim Sperren und neu Erzeugen ebenso zuerst den Zugang.
- Ergebnisse als feste Wörter. Unbekannt, abgelaufen, gesperrt, Portal aus, Archiv und Modul aus sehen von außen gleich aus („ungueltig“); das Protokoll
  unterscheidet sie (app/portal/werte.py::ERGEBNISSE).

Grenzen: unbestätigte Sitzung 15 Minuten; bestätigte 30 Tage gleitend, verlängert höchstens einmal je Stunde; Code 5 Versuche, ein neuer frühestens nach
60 Sekunden; Bremsen: Link öffnen je Anschluss 30 je Stunde; Code anfordern je Zugang 3 je 15 Minuten und 10 je Tag, je Anschluss 10 je Stunde, gesamt 200
je Stunde; Code prüfen je Anschluss 30 je Stunde. Die 10 Minuten des Codes setzt der Postbote beim Anlegen (P1c).

Der Text steht wörtlich in der Migration b5d1e8a3c247 (tests/test_v800_portal_funktionen.py vergleicht beide); eine Änderung braucht eine neue Migration
(CREATE OR REPLACE). Unter PostgreSQL legt jedes create_all() sie ebenso an (Testschemas, lokale Entwicklung; app/database.py); unter SQLite gibt es sie
nicht -- der Dienst des Portals läuft nur gegen PostgreSQL.
"""

_PFAD = "SET search_path = pg_catalog, @SCHEMA@, pg_temp"

# Helfer: keine SECURITY DEFINER -- sie laufen nur aus den Funktionen unten (dort mit den Rechten des Eigentümers)
_HELFER = (
    ("portal_jetzt()",
     f"CREATE OR REPLACE FUNCTION portal_jetzt() RETURNS timestamp LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT (now() AT TIME ZONE 'utc')::timestamp\n"
     "$$"),
    ("portal_hash_gueltig(text)",
     f"CREATE OR REPLACE FUNCTION portal_hash_gueltig(p text) RETURNS boolean LANGUAGE sql IMMUTABLE {_PFAD} AS $$\n"
     "SELECT coalesce(p ~ '^[0-9a-f]{64}$', false)\n"
     "$$"),
    ("portal_bremse(text, integer, interval)",
     f"CREATE OR REPLACE FUNCTION portal_bremse(p_schluessel text, p_grenze integer, p_fenster interval) RETURNS integer LANGUAGE plpgsql {_PFAD} AS $$\n"
     "DECLARE\n"
     "  v_sekunden double precision := extract(epoch FROM p_fenster);\n"
     "  v_jetzt timestamp := portal_jetzt();\n"
     "  v_beginn timestamp;\n"
     "  v_zaehler integer;\n"
     "BEGIN\n"
     "  v_beginn := to_timestamp(floor(extract(epoch FROM v_jetzt) / v_sekunden) * v_sekunden) AT TIME ZONE 'utc';\n"
     "  INSERT INTO portal_bremsen AS b (schluessel, fenster_beginn, zaehler) VALUES (p_schluessel, v_beginn, 1)\n"
     "    ON CONFLICT (schluessel, fenster_beginn) DO UPDATE SET zaehler = b.zaehler + 1\n"
     "    RETURNING b.zaehler INTO v_zaehler;\n"
     "  IF v_zaehler <= p_grenze THEN\n"
     "    RETURN 0;\n"
     "  END IF;\n"
     "  RETURN greatest(1, ceil(extract(epoch FROM (v_beginn + p_fenster - v_jetzt)) / 60)::integer);\n"
     "END\n"
     "$$"),
    ("portal_protokoll(integer, integer, text, text)",
     f"CREATE OR REPLACE FUNCTION portal_protokoll(p_zugang integer, p_sitzung integer, p_aktion text, p_ergebnis text) RETURNS void LANGUAGE sql {_PFAD} AS $$\n"
     "INSERT INTO portal_zugriffe (zeitpunkt, zugang_id, sitzung_id, aktion, ergebnis) VALUES (portal_jetzt(), p_zugang, p_sitzung, p_aktion, p_ergebnis)\n"
     "$$"),
    ("portal_zugang_grund(integer)",
     f"CREATE OR REPLACE FUNCTION portal_zugang_grund(p_zugang integer) RETURNS text LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT CASE\n"
     "  WHEN z.id IS NULL THEN 'unbekannt'\n"
     "  WHEN NOT EXISTS (SELECT 1 FROM enabled_modules m WHERE m.module_key = 'kundenportal' AND m.enabled) THEN 'modul_aus'\n"
     "  WHEN c.archiviert_am IS NOT NULL THEN 'archiv'\n"
     "  WHEN NOT c.portal_aktiv THEN 'portal_aus'\n"
     "  WHEN z.gesperrt_am IS NOT NULL THEN 'gesperrt'\n"
     "  WHEN z.link_sha256 IS NULL OR z.gueltig_bis IS NULL OR z.gueltig_bis <= portal_jetzt() THEN 'abgelaufen'\n"
     "END\n"
     "FROM (SELECT p_zugang AS id) AS x\n"
     "LEFT JOIN portal_zugaenge z ON z.id = x.id\n"
     "LEFT JOIN customers c ON c.id = z.customer_id\n"
     "$$"),
    ("portal_sitzung_id(text, boolean)",
     f"CREATE OR REPLACE FUNCTION portal_sitzung_id(p_sitzung text, p_bestaetigt boolean) RETURNS integer LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT s.id FROM portal_sitzungen s\n"
     "WHERE portal_hash_gueltig(p_sitzung) AND s.wert_sha256 = p_sitzung AND s.beendet_am IS NULL AND s.laeuft_ab > portal_jetzt()\n"
     "  AND (s.bestaetigt_am IS NOT NULL) = p_bestaetigt AND portal_zugang_grund(s.zugang_id) IS NULL\n"
     "$$"),
)

# Die Funktionen für den Benutzer des Portals (SECURITY DEFINER); Name -> Argumente wie pg_get_function_identity_arguments()
_FUNKTIONEN = (
    ("portal_link_oeffnen", "p_link text, p_anschluss text, p_sitzung text, p_neue_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_link_oeffnen(p_link text, p_anschluss text, p_sitzung text, p_neue_sitzung text)\n"
     f"RETURNS TABLE (ergebnis text, email_anzeige text, minuten integer) LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_rest integer;\n"
     "  v_zugang integer;\n"
     "  v_anzeige text;\n"
     "  v_grund text;\n"
     "  v_sitzung integer;\n"
     "BEGIN\n"
     "  IF NOT (portal_hash_gueltig(p_link) AND portal_hash_gueltig(p_anschluss)) THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_rest := portal_bremse('link:a:' || p_anschluss, 30, interval '1 hour');\n"
     "  IF v_rest > 0 THEN\n"
     "    PERFORM portal_protokoll(NULL, NULL, 'link_geoeffnet', 'bremse');\n"
     "    RETURN QUERY SELECT 'bremse'::text, NULL::text, v_rest;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT z.id, z.email_anzeige INTO v_zugang, v_anzeige FROM portal_zugaenge z WHERE z.link_sha256 = p_link FOR NO KEY UPDATE;\n"
     "  IF v_zugang IS NULL THEN\n"
     "    PERFORM portal_protokoll(NULL, NULL, 'link_geoeffnet', 'unbekannt');\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_grund := portal_zugang_grund(v_zugang);\n"
     "  IF v_grund IS NOT NULL THEN\n"
     "    PERFORM portal_protokoll(v_zugang, NULL, 'link_geoeffnet', v_grund);\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT s.id INTO v_sitzung FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, true) AND s.zugang_id = v_zugang;\n"
     "  IF v_sitzung IS NOT NULL THEN\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'link_geoeffnet', 'angemeldet');\n"
     "    RETURN QUERY SELECT 'angemeldet'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  IF NOT portal_hash_gueltig(p_neue_sitzung) THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  BEGIN\n"
     "    INSERT INTO portal_sitzungen (zugang_id, wert_sha256, angelegt_am, laeuft_ab)\n"
     "      VALUES (v_zugang, p_neue_sitzung, portal_jetzt(), portal_jetzt() + interval '15 minutes') RETURNING id INTO v_sitzung;\n"
     "  EXCEPTION WHEN unique_violation THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END;\n"
     "  PERFORM portal_protokoll(v_zugang, v_sitzung, 'link_geoeffnet', 'code_noetig');\n"
     "  RETURN QUERY SELECT 'code_noetig'::text, v_anzeige, NULL::integer;\n"
     "END\n"
     "$$"),
    ("portal_code_anfordern", "p_sitzung text, p_anschluss text",
     "CREATE OR REPLACE FUNCTION portal_code_anfordern(p_sitzung text, p_anschluss text)\n"
     f"RETURNS TABLE (ergebnis text, minuten integer) LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "  v_rest integer;\n"
     "BEGIN\n"
     "  IF NOT portal_hash_gueltig(p_anschluss) THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT s.zugang_id INTO v_zugang FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, false);\n"
     "  IF v_zugang IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  PERFORM 1 FROM portal_zugaenge z WHERE z.id = v_zugang FOR NO KEY UPDATE;\n"
     "  SELECT s.id INTO v_sitzung FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, false) FOR UPDATE;\n"
     "  IF v_sitzung IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  IF EXISTS (SELECT 1 FROM portal_post p WHERE p.sitzung_id = v_sitzung AND p.angefordert_am > portal_jetzt() - interval '60 seconds') THEN\n"
     "    RETURN QUERY SELECT 'bremse'::text, 1;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_rest := greatest(\n"
     "    portal_bremse('code:z:' || v_zugang, 3, interval '15 minutes'),\n"
     "    portal_bremse('code:zt:' || v_zugang, 10, interval '1 day'),\n"
     "    portal_bremse('code:a:' || p_anschluss, 10, interval '1 hour'),\n"
     "    portal_bremse('code:g', 200, interval '1 hour'));\n"
     "  IF v_rest > 0 THEN\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'code_angefordert', 'bremse');\n"
     "    RETURN QUERY SELECT 'bremse'::text, v_rest;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status) VALUES ('code', v_zugang, v_sitzung, portal_jetzt(), 'wartet');\n"
     "  PERFORM pg_notify('portal_post', '');\n"
     "  PERFORM portal_protokoll(v_zugang, v_sitzung, 'code_angefordert', 'ok');\n"
     "  RETURN QUERY SELECT 'angefordert'::text, NULL::integer;\n"
     "END\n"
     "$$"),
    ("portal_post_stand", "p_sitzung text",
     f"CREATE OR REPLACE FUNCTION portal_post_stand(p_sitzung text) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER {_PFAD} AS $$\n"
     "SELECT CASE WHEN portal_sitzung_id(p_sitzung, false) IS NULL THEN 'ungueltig'\n"
     "  ELSE coalesce((SELECT p.status FROM portal_post p WHERE p.sitzung_id = portal_sitzung_id(p_sitzung, false) ORDER BY p.id DESC LIMIT 1), 'keiner')\n"
     "END\n"
     "$$"),
    ("portal_code_pruefen", "p_sitzung text, p_pruefwert text, p_neue_sitzung text, p_anschluss text",
     "CREATE OR REPLACE FUNCTION portal_code_pruefen(p_sitzung text, p_pruefwert text, p_neue_sitzung text, p_anschluss text)\n"
     f"RETURNS TABLE (ergebnis text, zahl integer) LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_rest integer;\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "  v_code integer;\n"
     "  v_wert text;\n"
     "  v_gueltig timestamp;\n"
     "  v_versuche integer;\n"
     "BEGIN\n"
     "  IF NOT (portal_hash_gueltig(p_pruefwert) AND portal_hash_gueltig(p_neue_sitzung) AND portal_hash_gueltig(p_anschluss)) THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_rest := portal_bremse('pruefen:a:' || p_anschluss, 30, interval '1 hour');\n"
     "  IF v_rest > 0 THEN\n"
     "    PERFORM portal_protokoll(NULL, NULL, 'angemeldet', 'bremse');\n"
     "    RETURN QUERY SELECT 'bremse'::text, v_rest;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT s.zugang_id INTO v_zugang FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, false);\n"
     "  IF v_zugang IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  PERFORM 1 FROM portal_zugaenge z WHERE z.id = v_zugang FOR NO KEY UPDATE;\n"
     "  SELECT s.id INTO v_sitzung FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, false) FOR UPDATE;\n"
     "  IF v_sitzung IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT c.id, c.pruefwert, c.gueltig_bis, c.versuche INTO v_code, v_wert, v_gueltig, v_versuche FROM portal_codes c\n"
     "    WHERE c.sitzung_id = v_sitzung AND c.verbraucht_am IS NULL AND c.ersetzt_am IS NULL ORDER BY c.id DESC LIMIT 1 FOR UPDATE;\n"
     "  IF v_code IS NULL OR v_gueltig <= portal_jetzt() OR v_versuche >= 5 THEN\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'code_abgelaufen', 'ungueltig');\n"
     "    RETURN QUERY SELECT 'neu_anfordern'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  UPDATE portal_codes SET versuche = versuche + 1 WHERE id = v_code;\n"
     "  IF v_wert <> p_pruefwert THEN\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'code_falsch', 'ungueltig');\n"
     "    RETURN QUERY SELECT 'falsch'::text, 5 - (v_versuche + 1);\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  BEGIN\n"
     "    UPDATE portal_sitzungen SET bestaetigt_am = portal_jetzt(), wert_sha256 = p_neue_sitzung, zuletzt_am = portal_jetzt(),\n"
     "      laeuft_ab = portal_jetzt() + interval '30 days' WHERE id = v_sitzung;\n"
     "  EXCEPTION WHEN unique_violation THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END;\n"
     "  UPDATE portal_codes SET verbraucht_am = portal_jetzt() WHERE id = v_code;\n"
     "  UPDATE portal_zugaenge SET zuletzt_genutzt_am = portal_jetzt() WHERE id = v_zugang;\n"
     "  PERFORM portal_protokoll(v_zugang, v_sitzung, 'angemeldet', 'ok');\n"
     "  RETURN QUERY SELECT 'angemeldet'::text, NULL::integer;\n"
     "END\n"
     "$$"),
    ("portal_sitzung", "p_sitzung text",
     f"CREATE OR REPLACE FUNCTION portal_sitzung(p_sitzung text) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER {_PFAD} AS $$\n"
     "SELECT CASE WHEN portal_sitzung_id(p_sitzung, true) IS NULL THEN 'ungueltig' ELSE 'gueltig' END\n"
     "$$"),
    ("portal_sitzung_weiter", "p_sitzung text",
     f"CREATE OR REPLACE FUNCTION portal_sitzung_weiter(p_sitzung text) RETURNS text LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "DECLARE\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "  v_zuletzt timestamp;\n"
     "BEGIN\n"
     "  SELECT s.zugang_id INTO v_zugang FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, true);\n"
     "  IF v_zugang IS NULL THEN\n"
     "    RETURN 'ungueltig';\n"
     "  END IF;\n"
     "  PERFORM 1 FROM portal_zugaenge z WHERE z.id = v_zugang FOR NO KEY UPDATE;\n"
     "  SELECT s.id, s.zuletzt_am INTO v_sitzung, v_zuletzt FROM portal_sitzungen s WHERE s.id = portal_sitzung_id(p_sitzung, true) FOR UPDATE;\n"
     "  IF v_sitzung IS NULL THEN\n"
     "    RETURN 'ungueltig';\n"
     "  END IF;\n"
     "  IF v_zuletzt IS NOT NULL AND v_zuletzt > portal_jetzt() - interval '1 hour' THEN\n"
     "    RETURN 'gueltig';\n"
     "  END IF;\n"
     "  UPDATE portal_sitzungen SET zuletzt_am = portal_jetzt(), laeuft_ab = portal_jetzt() + interval '30 days' WHERE id = v_sitzung;\n"
     "  UPDATE portal_zugaenge SET zuletzt_genutzt_am = portal_jetzt() WHERE id = v_zugang;\n"
     "  PERFORM portal_protokoll(v_zugang, v_sitzung, 'verlaengert', 'ok');\n"
     "  RETURN 'verlaengert';\n"
     "END\n"
     "$$"),
    ("portal_abmelden", "p_sitzung text, p_ueberall boolean",
     f"CREATE OR REPLACE FUNCTION portal_abmelden(p_sitzung text, p_ueberall boolean) RETURNS text LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "DECLARE\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "BEGIN\n"
     "  IF NOT portal_hash_gueltig(p_sitzung) THEN\n"
     "    RETURN 'ungueltig';\n"
     "  END IF;\n"
     "  SELECT s.zugang_id INTO v_zugang FROM portal_sitzungen s WHERE s.wert_sha256 = p_sitzung AND s.beendet_am IS NULL;\n"
     "  IF v_zugang IS NULL THEN\n"
     "    RETURN 'ungueltig';\n"
     "  END IF;\n"
     "  PERFORM 1 FROM portal_zugaenge z WHERE z.id = v_zugang FOR NO KEY UPDATE;\n"
     "  SELECT s.id INTO v_sitzung FROM portal_sitzungen s WHERE s.wert_sha256 = p_sitzung AND s.beendet_am IS NULL FOR UPDATE;\n"
     "  IF v_sitzung IS NULL THEN\n"
     "    RETURN 'ungueltig';\n"
     "  END IF;\n"
     "  IF p_ueberall THEN\n"
     "    IF portal_sitzung_id(p_sitzung, true) IS NULL THEN\n"
     "      RETURN 'ungueltig';\n"
     "    END IF;\n"
     "    UPDATE portal_sitzungen SET beendet_am = portal_jetzt(), beendet_grund = 'ueberall' WHERE zugang_id = v_zugang AND beendet_am IS NULL;\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'ueberall_abgemeldet', 'ok');\n"
     "  ELSE\n"
     "    UPDATE portal_sitzungen SET beendet_am = portal_jetzt(), beendet_grund = 'abgemeldet' WHERE id = v_sitzung;\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'abgemeldet', 'ok');\n"
     "  END IF;\n"
     "  RETURN 'abgemeldet';\n"
     "END\n"
     "$$"),
    ("portal_willkommen", "p_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_willkommen(p_sitzung text)\n"
     f"RETURNS TABLE (anrede text, titel text, vorname text, nachname text, name text) LANGUAGE sql STABLE SECURITY DEFINER {_PFAD} AS $$\n"
     "SELECT c.salutation::text, c.title::text, c.first_name::text, c.last_name::text, c.name::text\n"
     "FROM portal_sitzungen s JOIN portal_zugaenge z ON z.id = s.zugang_id JOIN customers c ON c.id = z.customer_id\n"
     "WHERE s.id = portal_sitzung_id(p_sitzung, true)\n"
     "$$"),
)

# Name -> Argumente der Funktionen, die der Benutzer des Portals aufrufen darf (app/portal/rechte.py::FUNKTIONEN nimmt genau diese)
FUER_DAS_PORTAL = {name: argumente for name, argumente, _sql in _FUNKTIONEN}


def _typen(argumente: str) -> str:
    """„p_link text, p_ueberall boolean“ -> „text, boolean“ (für REVOKE)."""
    return ", ".join(teil.split()[-1] for teil in argumente.split(", ")) if argumente else ""


# Alle Anweisungen in Reihenfolge: Helfer, Funktionen, dann für alle nicht ausführbar. @SCHEMA@ = Schema der Tabellen.
ANWEISUNGEN = tuple(
    [sql for _sig, sql in _HELFER]
    + [sql for _n, _a, sql in _FUNKTIONEN]
    + [f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC" for sig, _sql in _HELFER]
    + [f"REVOKE ALL ON FUNCTION {name}({_typen(argumente)}) FROM PUBLIC" for name, argumente, _sql in _FUNKTIONEN]
)


def anweisungen(schema: str) -> list[str]:
    """Die Anweisungen für ein Schema (der Name ist vorher geprüft: nur Kleinbuchstaben, Ziffern, Unterstrich)."""
    from .rechte import _name
    schema = _name(schema)
    return [a.replace("@SCHEMA@", schema) for a in ANWEISUNGEN]


def pg_anlegen(target, connection, **kw):
    """Nach jedem create_all() unter PostgreSQL (Testschemas, lokale Entwicklung) -- auf dem Server legt die Migration sie an. Fehlen die Tabellen des
    Portals (create_all() nur für einzelne Tabellen), bleibt es bei nichts."""
    if connection.dialect.name != "postgresql":
        return
    da = connection.exec_driver_sql(
        "SELECT to_regclass('portal_zugaenge') IS NOT NULL AND to_regclass('portal_sitzungen') IS NOT NULL AND to_regclass('customers') IS NOT NULL "
        "AND to_regclass('enabled_modules') IS NOT NULL AND to_regclass('portal_post') IS NOT NULL AND to_regclass('portal_codes') IS NOT NULL "
        "AND to_regclass('portal_zugriffe') IS NOT NULL AND to_regclass('portal_bremsen') IS NOT NULL").scalar()
    if not da:
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    for a in anweisungen(schema):
        connection.exec_driver_sql(a)
