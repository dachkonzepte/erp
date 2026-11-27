"""Funktionen der Datenbank für das Schaufenster des Kundenportals (seit 1.11.42, Stufe P2d, Teil 2; Bauplan P2, B3, B10).

Wie app/portal/unterlagen.py: sie gehören dem Benutzer des ERP und laufen mit seinen Rechten (SECURITY DEFINER); der Benutzer des Portals darf nur die
Funktionen unten aufrufen (app/portal/rechte.py::FUNKTIONEN) und hat auf portal_rechnungen, portal_termine, portal_schaufenster und jede Tabelle des ERP kein
Recht. Sie **rechnen nichts** -- Zahlstand und Termine hat das ERP gerechnet und abgelegt (app/portal_schaufenster.py, 1.11.41); sie lesen nur das und prüfen
dazu live, was die Unterlagen auch prüfen:

- **Rechnungen** (portal_rechnungen): jede Rechnung, die als Unterlage sichtbar ist (Freigabe für den Kunden der Sitzung, nicht zurückgenommen, Kopie bereit,
  Kette heute zu ihm -- portal_quelle()), mit ihrem Zahlstand aus dem Schaufenster; fehlt er noch (der Postbote rechnet in Sekunden), ohne Zustand. Dazu jede
  sichtbare Mahnung mit der Freigabe ihrer Rechnung (zu_freigabe; leer, wenn die Rechnung selbst nicht sichtbar ist) -- sie heißt, wie ihre Stufe im ERP heißt
  (Bezeichnung der Mahnstufe, z. B. „Zahlungserinnerung“; Entwurf P2, Seite 5). Ausgabe nur die Felder unten.
- **Termine** (portal_termine): die Folgen fester Baustellentage, live dazu: der Auftrag gehört heute dem Kunden, läuft oder ist pausiert, das Projekt ist offen.
- **Übersicht** (Entwurf P2, Seite 1) in einer Zeile: Zahl und Summe der offenen Rechnungen (nur offen und teilweise bezahlt, mit offenem Betrag) und die
  zuerst fällige; der nächste Einsatz (die erste Folge, die heute oder später endet -- heute in Berlin); Zahl der Unterlagen (ohne Rechnungen, Mahnungen,
  Fotos) und die jüngste; Zahl der Fotos und wann zuletzt eins freigegeben wurde (in Berlin). Ein Aufruf, ein Eintrag im Protokoll.
- **Betreff** (seit 1.11.43): neben der Auftragsnummer der Titel des Auftrags (Order.title -- was der Kunde auf Angebot und Auftragsbestätigung gedruckt
  hat, nie der Projekttitel), leer ohne Text.
- **Vorschau** (seit 1.11.44): `portal_vorschau(sitzung, freigabe)` nennt die Vorschau eines sichtbaren Fotos (400 px) -- liest nur, ohne Anforderung und
  ohne Protokoll (die Liste der Fotos steht schon im Protokoll und zählt die Bremse).
- **Stand**: wann der Postbote das Schaufenster des Kunden zuletzt gerechnet hat (portal_schaufenster), in jeder Zeile -- auch bei „leer“.
- **Kein GET schreibt** (P1): alle drei schreiben das Zugriffsprotokoll (Aktion „rechnungen“, „termine“ bzw. „uebersicht“) und zählen die Bremse der Listen
  ('liste:s:' je Sitzung, 120 je Stunde, dieselbe wie portal_unterlagen()) -- im Portal je ein POST.

Der Text steht wörtlich in der Migration (MIGRATIONEN); eine Änderung braucht eine neue Migration (CREATE OR REPLACE) und einen Eintrag in MIGRATIONEN. Unter
PostgreSQL legt jedes create_all() sie nach denen aus unterlagen.py an (app/database.py); unter SQLite gibt es sie nicht.
"""

from .funktionen import _typen

_PFAD = "SET search_path = pg_catalog, @SCHEMA@, pg_temp"

_LEER_RECHNUNG = ("NULL::integer, NULL::text, NULL::text, NULL::text, NULL::date, NULL::date, NULL::numeric, NULL::text, NULL::numeric, NULL::boolean, "
                  "NULL::text, NULL::integer, NULL::text, NULL::text, NULL::text")
_LEER_TERMIN = "NULL::text, NULL::text, NULL::text, NULL::date, NULL::date"
_LEER_UEBERSICHT = ("NULL::integer, NULL::numeric, NULL::text, NULL::text, NULL::date, NULL::date, NULL::date, NULL::text, NULL::text, NULL::text, "
                    "NULL::integer, NULL::text, NULL::date, NULL::integer, NULL::date")


def _kopf(aktion: str, leer: str) -> str:
    """Sitzung, Bremse, Protokoll, Stand -- gleich in beiden Funktionen."""
    return (
        "#variable_conflict use_column\n"
        "DECLARE\n"
        "  v_zugang integer;\n"
        "  v_sitzung integer;\n"
        "  v_kunde integer;\n"
        "  v_rest integer;\n"
        "  v_stand timestamp;\n"
        "BEGIN\n"
        "  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n"
        "  IF v_sitzung IS NULL THEN\n"
        f"    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer, NULL::timestamp, {leer};\n"
        "    RETURN;\n"
        "  END IF;\n"
        "  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n"
        "  IF v_rest > 0 THEN\n"
        f"    PERFORM portal_protokoll(v_zugang, v_sitzung, '{aktion}', 'bremse');\n"
        f"    RETURN QUERY SELECT 'bremse'::text, v_rest, NULL::timestamp, {leer};\n"
        "    RETURN;\n"
        "  END IF;\n"
        f"  PERFORM portal_protokoll(v_zugang, v_sitzung, '{aktion}', 'ok');\n"
        "  SELECT s.stand_am INTO v_stand FROM portal_schaufenster s WHERE s.customer_id = v_kunde;\n"
    )


_SICHTBAR = ("f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL "
             "AND q.kunde = v_kunde")

# Die Funktionen für den Benutzer des Portals (SECURITY DEFINER): (Name, Argumente, SQL)
_FUNKTIONEN = (
    ("portal_rechnungen", "p_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_rechnungen(p_sitzung text)\n"
     "RETURNS TABLE (ergebnis text, minuten integer, stand timestamp, freigabe integer, art text, titel text, nummer text, datum date, faellig date,\n"
     "  betrag numeric, zustand text, offen numeric, ueberfaellig boolean, bezug text, zu_freigabe integer, auftrag text, betreff text, objekt text)\n"
     f"LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     + _kopf("rechnungen", _LEER_RECHNUNG) +
     "  RETURN QUERY\n"
     "    SELECT 'ok'::text, NULL::integer, v_stand, f.id, 'rechnung'::text, coalesce(r.art_text, f.titel)::text, r.nummer::text, coalesce(r.datum, f.datum),\n"
     "           r.faellig, r.brutto, r.zustand::text, r.offen, r.ueberfaellig, r.bezug_nummer::text, NULL::integer, q.auftrag,\n"
     "           (SELECT nullif(btrim(ob.title), '') FROM orders ob WHERE ob.order_number = q.auftrag)::text, q.objekt\n"
     "      FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n"
     "      LEFT JOIN portal_rechnungen r ON r.invoice_id = f.quelle_id AND r.customer_id = v_kunde\n"
     f"      WHERE f.quelle = 'invoices' AND {_SICHTBAR}\n"
     "    UNION ALL\n"
     "    SELECT 'ok'::text, NULL::integer, v_stand, f.id, 'mahnung'::text,\n"
     "           coalesce((SELECT nullif(trim(l.label), '') FROM reminder_levels l WHERE l.level = m.level ORDER BY l.id LIMIT 1), m.level || '. Mahnung')::text,\n"
     "           m.reminder_number::text, f.datum, NULL::date, NULL::numeric, NULL::text,\n"
     "           NULL::numeric, NULL::boolean, NULL::text,\n"
     "           (SELECT g.id FROM portal_freigaben g WHERE g.quelle = 'invoices' AND g.quelle_id = m.invoice_id AND portal_sichtbar(g.id, v_kunde)\n"
     "             ORDER BY g.id DESC LIMIT 1),\n"
     "           q.auftrag, (SELECT nullif(btrim(ob.title), '') FROM orders ob WHERE ob.order_number = q.auftrag)::text, q.objekt\n"
     "      FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q JOIN reminders m ON m.id = f.quelle_id\n"
     f"      WHERE f.quelle = 'reminders' AND {_SICHTBAR}\n"
     "    ORDER BY 8 DESC, 4 DESC;\n"
     "  IF NOT FOUND THEN\n"
     f"    RETURN QUERY SELECT 'leer'::text, NULL::integer, v_stand, {_LEER_RECHNUNG};\n"
     "  END IF;\n"
     "END\n"
     "$$"),
    ("portal_termine", "p_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_termine(p_sitzung text)\n"
     "RETURNS TABLE (ergebnis text, minuten integer, stand timestamp, auftrag text, betreff text, objekt text, von date, bis date)\n"
     f"LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     + _kopf("termine", _LEER_TERMIN) +
     "  RETURN QUERY\n"
     "    SELECT 'ok'::text, NULL::integer, v_stand, o.order_number::text, nullif(btrim(o.title), '')::text, portal_adresse(p.property_id), t.von, t.bis\n"
     "      FROM portal_termine t JOIN orders o ON o.id = t.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE t.customer_id = v_kunde AND o.customer_id = v_kunde AND o.status IN ('laeuft', 'pausiert') AND portal_projekt_offen(p.id)\n"
     "    ORDER BY t.von, t.order_id, t.id;\n"
     "  IF NOT FOUND THEN\n"
     f"    RETURN QUERY SELECT 'leer'::text, NULL::integer, v_stand, {_LEER_TERMIN};\n"
     "  END IF;\n"
     "END\n"
     "$$"),
    ("portal_uebersicht", "p_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_uebersicht(p_sitzung text)\n"
     "RETURNS TABLE (ergebnis text, minuten integer, stand timestamp, offen_anzahl integer, offen_summe numeric, faellig_titel text, faellig_nummer text,\n"
     "  faellig_am date, einsatz_von date, einsatz_bis date, einsatz_auftrag text, einsatz_betreff text, einsatz_objekt text, unterlagen integer,\n"
     "  unterlage_titel text, unterlage_datum date, fotos integer, foto_am date)\n"
     f"LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     + _kopf("uebersicht", _LEER_UEBERSICHT).replace("  v_stand timestamp;\n", "  v_stand timestamp;\n  v_heute date;\n") +
     "  v_heute := ((portal_jetzt() AT TIME ZONE 'utc') AT TIME ZONE 'Europe/Berlin')::date;\n"
     "  RETURN QUERY\n"
     "    WITH sichtbar AS (\n"
     "      SELECT f.id, f.art, f.titel, f.datum, f.quelle, f.quelle_id, f.freigegeben_am\n"
     "        FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n"
     f"        WHERE {_SICHTBAR}),\n"
     "    offen AS (\n"
     "      SELECT r.invoice_id, r.art_text, r.nummer, r.datum, r.faellig, r.offen FROM sichtbar s JOIN portal_rechnungen r ON r.invoice_id = s.quelle_id\n"
     "        WHERE s.quelle = 'invoices' AND r.customer_id = v_kunde AND r.zustand IN ('offen', 'teilweise_bezahlt') AND r.offen > 0),\n"
     "    faellig AS (SELECT o.art_text, o.nummer, o.faellig FROM offen o ORDER BY o.faellig NULLS LAST, o.datum, o.invoice_id LIMIT 1),\n"
     "    einsatz AS (\n"
     "      SELECT t.von, t.bis, o.order_number, nullif(btrim(o.title), '') AS betreff, portal_adresse(p.property_id) AS objekt\n"
     "        FROM portal_termine t JOIN orders o ON o.id = t.order_id JOIN projects p ON p.id = o.project_id\n"
     "        WHERE t.customer_id = v_kunde AND o.customer_id = v_kunde AND o.status IN ('laeuft', 'pausiert') AND portal_projekt_offen(p.id)\n"
     "          AND t.bis >= v_heute\n"
     "        ORDER BY t.von, t.order_id, t.id LIMIT 1),\n"
     "    unterlagen AS (SELECT s.id, s.titel, s.datum FROM sichtbar s WHERE s.art NOT IN ('rechnung', 'mahnung', 'foto')),\n"
     "    letzte AS (SELECT u.titel, u.datum FROM unterlagen u ORDER BY u.datum DESC, u.id DESC LIMIT 1)\n"
     "    SELECT 'ok'::text, NULL::integer, v_stand, (SELECT count(*)::integer FROM offen), (SELECT coalesce(sum(o.offen), 0) FROM offen o),\n"
     "           fa.art_text::text, fa.nummer::text, fa.faellig, e.von, e.bis, e.order_number::text, e.betreff::text, e.objekt,\n"
     "           (SELECT count(*)::integer FROM unterlagen),\n"
     "           l.titel::text, l.datum, (SELECT count(*)::integer FROM sichtbar s WHERE s.art = 'foto'),\n"
     "           (SELECT ((max(s.freigegeben_am) AT TIME ZONE 'utc') AT TIME ZONE 'Europe/Berlin')::date FROM sichtbar s WHERE s.art = 'foto')\n"
     "      FROM (SELECT 1) AS eins LEFT JOIN faellig fa ON true LEFT JOIN einsatz e ON true LEFT JOIN letzte l ON true;\n"
     "END\n"
     "$$"),
)

# Seit 1.11.44 (P2e): die Vorschau eines Fotos -- liest nur (STABLE), ohne Anforderung und ohne Protokoll: sie gehört zur Liste, die schon im
# Protokoll steht und die Bremse zählt; sichtbar wie die Datei selbst (portal_sichtbar()). „keine“: das Foto hat (noch) keine Vorschau.
_FUNKTIONEN = _FUNKTIONEN + (
    ("portal_vorschau", "p_sitzung text, p_freigabe integer",
     "CREATE OR REPLACE FUNCTION portal_vorschau(p_sitzung text, p_freigabe integer)\n"
     f"RETURNS TABLE (ergebnis text, name text) LANGUAGE plpgsql STABLE SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_sitzung integer;\n"
     "  v_kunde integer;\n"
     "BEGIN\n"
     "  SELECT k.sitzung, k.kunde INTO v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n"
     "  IF v_sitzung IS NULL OR p_freigabe IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  IF NOT portal_sichtbar(p_freigabe, v_kunde) THEN\n"
     "    RETURN QUERY SELECT 'unbekannt'::text, NULL::text;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  RETURN QUERY SELECT (CASE WHEN f.kopie_vorschau IS NULL THEN 'keine' ELSE 'ok' END)::text, f.kopie_vorschau::text\n"
     "    FROM portal_freigaben f WHERE f.id = p_freigabe;\n"
     "END\n"
     "$$"),
)

# Die Migrationen mit dem Text dieser Funktionen, älteste zuerst
MIGRATIONEN = ("d7a3f9c2e5b1", "f8b2d6a4c9e1", "b3e7a1d9c5f2")  # f8b2d6a4c9e1 seit 1.11.43: der Betreff; b3e7a1d9c5f2 seit 1.11.44: die Vorschau

# Name -> Argumente der Funktionen, die der Benutzer des Portals aufrufen darf (app/portal/rechte.py::FUNKTIONEN nimmt diese dazu)
FUER_DAS_PORTAL = {name: argumente for name, argumente, _sql in _FUNKTIONEN}

# Alle Anweisungen in Reihenfolge: Funktionen, dann für alle nicht ausführbar. @SCHEMA@ = Schema der Tabellen.
ANWEISUNGEN = tuple(
    [sql for _n, _a, sql in _FUNKTIONEN]
    + [f"REVOKE ALL ON FUNCTION {name}({_typen(argumente)}) FROM PUBLIC" for name, argumente, _sql in _FUNKTIONEN]
)


def anweisungen(schema: str) -> list[str]:
    from .rechte import _name
    schema = _name(schema)
    return [a.replace("@SCHEMA@", schema) for a in ANWEISUNGEN]


def pg_anlegen(target, connection, **kw):
    """Nach jedem create_all() unter PostgreSQL, nach den Funktionen aus unterlagen.py (sie werden hier gebraucht). Fehlen Tabellen oder Funktionen, bleibt es
    bei nichts."""
    if connection.dialect.name != "postgresql":
        return
    da = connection.exec_driver_sql(
        "SELECT to_regclass('portal_rechnungen') IS NOT NULL AND to_regclass('portal_termine') IS NOT NULL AND to_regclass('portal_schaufenster') IS NOT NULL "
        "AND to_regclass('reminders') IS NOT NULL AND to_regclass('reminder_levels') IS NOT NULL AND to_regprocedure('portal_sichtbar(integer, integer)') IS NOT NULL AND to_regprocedure('portal_quelle(text, integer)') IS NOT NULL").scalar()
    if not da:
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    for a in anweisungen(schema):
        connection.exec_driver_sql(a)
