"""Funktionen der Datenbank für die Unterlagen des Kundenportals (seit 1.11.31, Stufe P2a; Bauplan P2, B1, B4, B7).

Wie app/portal/funktionen.py (P1): sie gehören dem Benutzer des ERP und laufen mit seinen Rechten (SECURITY DEFINER); der Benutzer des Portals darf nur
die drei Funktionen unten aufrufen (app/portal/rechte.py::FUNKTIONEN) und hat auf portal_freigaben und jede Tabelle des ERP kein Recht. Was er sieht:

- **Nur Freigegebenes.** Eine Unterlage ist sichtbar, wenn eine Zeile in portal_freigaben für den Kunden der Sitzung steht, nicht zurückgenommen ist, ihre
  Kopie bereit liegt (ab P2b) -- UND die Kette ihrer Quelle heute noch zu genau diesem Kunden führt (portal_quelle()). Passt die Kette nicht mehr (Kunde
  gewechselt, Objekt umgehängt, Quelle gelöscht, Fassung überholt, Abnahme verworfen, Mahnung ersetzt, Rechnung Entwurf, Bericht ohne feste Fassung,
  Projekt Mustervorgang oder im Archiv), „ruht“ sie: nichts im Portal. Der Kunde im Archiv hat schon keine Sitzung (P1).
- **Kette je Quelle** fest im SQL, ohne dynamisches SQL: eine neue Quelle braucht einen eigenen Zweig (app/portal/werte.py::FREIGABE_QUELLEN; Wächter in
  tests/test_v821_portal_unterlagen.py: jede Quelle hat ihren Zweig). Der Kunde kommt, wo es ihn am Dokument gibt, von dort (Rechnung, Auftrag), sonst
  vom Projekt bzw. Objekt.
- **Kein GET schreibt** (P1): die Liste und das Anfordern einer Datei schreiben das Zugriffsprotokoll und zählen die Bremsen -- im Portal je ein POST.
  portal_datei() liest nur: sie nennt die Kopie nur nach einer Anforderung derselben Sitzung für diese Freigabe in den letzten 30 Minuten (Range-Abrufe eines
  PDF-Betrachters kommen so durch).
- **Ausgabe** nur die Felder unten (Positivliste); die Gruppe ist Auftragsnummer und Adresse des Objekts (Entscheidung P2-10), nie der Projekttitel.

Grenzen (Bauplan P2, B7): Liste je Sitzung 120 je Stunde; Anfordern je Zugang 300 je Stunde und 1500 je Tag, je Anschluss 300 je Stunde, gesamt 5000 je
Stunde. Der Text steht wörtlich in der Migration e5c8a1f3b9d2 (tests/test_v821_portal_unterlagen.py vergleicht beide); eine Änderung braucht eine neue
Migration (CREATE OR REPLACE). Unter PostgreSQL legt jedes create_all() sie nach denen aus funktionen.py an (app/database.py); unter SQLite gibt es sie nicht.
"""

import re

from .funktionen import _typen

_PFAD = "SET search_path = pg_catalog, @SCHEMA@, pg_temp"

# Helfer ohne SECURITY DEFINER -- sie laufen nur aus den Funktionen unten
_HELFER = (
    ("portal_projekt_offen(integer)",
     f"CREATE OR REPLACE FUNCTION portal_projekt_offen(p_projekt integer) RETURNS boolean LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT coalesce((SELECT NOT p.is_template AND NOT p.archived AND p.archiviert_am IS NULL FROM projects p WHERE p.id = p_projekt), false)\n"
     "$$"),
    ("portal_adresse(integer)",
     f"CREATE OR REPLACE FUNCTION portal_adresse(p_objekt integer) RETURNS text LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT nullif(concat_ws(', ', nullif(pr.street, ''), nullif(concat_ws(' ', nullif(pr.postal_code, ''), nullif(pr.city, '')), '')), '')\n"
     "FROM properties pr WHERE pr.id = p_objekt\n"
     "$$"),
    ("portal_fassung_gilt(integer)",
     f"CREATE OR REPLACE FUNCTION portal_fassung_gilt(p_fassung integer) RETURNS boolean LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT NOT EXISTS (\n"
     "  SELECT 1 FROM checklist_versions v JOIN checklist_attachments a ON a.checklist_id = v.checklist_id\n"
     "  WHERE v.id = p_fassung AND a.discarded_at IS NOT NULL\n"
     "    AND a.id IN (SELECT e::integer FROM jsonb_array_elements_text(coalesce(nullif(v.signature_ids, ''), '[]')::jsonb) AS e))\n"
     "$$"),
    ("portal_quelle(text, integer)",
     "CREATE OR REPLACE FUNCTION portal_quelle(p_quelle text, p_id integer)\n"
     f"RETURNS TABLE (kunde integer, auftrag text, objekt text) LANGUAGE plpgsql STABLE {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "BEGIN\n"
     "  IF p_quelle = 'invoices' THEN\n"
     "    RETURN QUERY SELECT i.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM invoices i JOIN orders o ON o.id = i.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE i.id = p_id AND i.status <> 'entwurf' AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'reminders' THEN\n"
     "    RETURN QUERY SELECT i.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM reminders r JOIN invoices i ON i.id = r.invoice_id JOIN orders o ON o.id = i.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE r.id = p_id AND r.status = 'versendet' AND r.replaced_by_id IS NULL AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'sent_documents' THEN\n"
     "    RETURN QUERY SELECT p.customer_id, NULL::text, portal_adresse(p.property_id)\n"
     "      FROM sent_documents s JOIN quotes q ON q.id = s.document_id JOIN projects p ON p.id = q.project_id\n"
     "      WHERE s.id = p_id AND s.document_type = 'angebot' AND portal_projekt_offen(p.id)\n"
     "    UNION ALL SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM sent_documents s JOIN orders o ON o.id = s.document_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE s.id = p_id AND s.document_type = 'auftrag' AND portal_projekt_offen(p.id)\n"
     "    UNION ALL SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM sent_documents s JOIN order_contracts c ON c.id = s.document_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE s.id = p_id AND s.document_type = 'vertrag' AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'service_reports' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM service_reports sr JOIN orders o ON o.id = sr.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE sr.id = p_id AND sr.status = 'unterschrieben' AND sr.pdf_document_id IS NOT NULL AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'checklist_versions' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM checklist_versions v JOIN checklists c ON c.id = v.checklist_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE v.id = p_id AND portal_fassung_gilt(v.id) AND portal_projekt_offen(p.id)\n"
     "    UNION ALL SELECT pr.customer_id, NULL::text, portal_adresse(pr.id)\n"
     "      FROM checklist_versions v JOIN checklists c ON c.id = v.checklist_id JOIN properties pr ON pr.id = c.property_id\n"
     "      WHERE v.id = p_id AND c.order_id IS NULL AND portal_fassung_gilt(v.id);\n"
     "  ELSIF p_quelle = 'notice_letters' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM notice_letters n JOIN checklists c ON c.id = n.checklist_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE n.id = p_id AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'service_report_photos' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM service_report_photos f JOIN service_reports sr ON sr.id = f.service_report_id JOIN orders o ON o.id = sr.order_id\n"
     "      JOIN projects p ON p.id = o.project_id\n"
     "      WHERE f.id = p_id AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'customer_documents' THEN\n"
     "    RETURN QUERY SELECT d.customer_id, NULL::text, NULL::text FROM customer_documents d WHERE d.id = p_id;\n"
     "  ELSIF p_quelle = 'project_documents' THEN\n"
     "    RETURN QUERY SELECT p.customer_id, NULL::text, portal_adresse(p.property_id)\n"
     "      FROM project_documents d JOIN projects p ON p.id = d.project_id\n"
     "      WHERE d.id = p_id AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'property_documents' THEN\n"
     "    RETURN QUERY SELECT pr.customer_id, NULL::text, portal_adresse(pr.id)\n"
     "      FROM property_documents d JOIN properties pr ON pr.id = d.property_id LEFT JOIN webanfragen w ON w.id = d.webanfrage_id\n"
     "      WHERE d.id = p_id AND w.archiviert_am IS NULL;\n"
     "  ELSIF p_quelle = 'defect_files' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM defect_files f JOIN defects d ON d.id = f.defect_id JOIN orders o ON o.id = d.order_id JOIN projects p ON p.id = o.project_id\n"
     "      WHERE f.id = p_id AND portal_projekt_offen(p.id);\n"
     "  ELSIF p_quelle = 'order_acceptance_files' THEN\n"
     "    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n"
     "      FROM order_acceptance_files f JOIN order_acceptances a ON a.id = f.acceptance_id JOIN orders o ON o.id = a.order_id\n"
     "      JOIN projects p ON p.id = o.project_id\n"
     "      WHERE f.id = p_id AND a.discarded_at IS NULL AND portal_projekt_offen(p.id);\n"
     "  END IF;\n"
     "END\n"
     "$$"),
    ("portal_sichtbar(integer, integer)",
     f"CREATE OR REPLACE FUNCTION portal_sichtbar(p_freigabe integer, p_kunde integer) RETURNS boolean LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT EXISTS (\n"
     "  SELECT 1 FROM portal_freigaben f\n"
     "  WHERE f.id = p_freigabe AND f.customer_id = p_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL\n"
     "    AND EXISTS (SELECT 1 FROM portal_quelle(f.quelle, f.quelle_id) q WHERE q.kunde = p_kunde))\n"
     "$$"),
    ("portal_kunde_der_sitzung(text)",
     "CREATE OR REPLACE FUNCTION portal_kunde_der_sitzung(p_sitzung text)\n"
     f"RETURNS TABLE (zugang integer, sitzung integer, kunde integer) LANGUAGE sql STABLE {_PFAD} AS $$\n"
     "SELECT s.zugang_id, s.id, z.customer_id FROM portal_sitzungen s JOIN portal_zugaenge z ON z.id = s.zugang_id\n"
     "WHERE s.id = portal_sitzung_id(p_sitzung, true)\n"
     "$$"),
    ("portal_protokoll_freigabe(integer, integer, text, text, integer)",
     "CREATE OR REPLACE FUNCTION portal_protokoll_freigabe(p_zugang integer, p_sitzung integer, p_aktion text, p_ergebnis text, p_freigabe integer)\n"
     f"RETURNS void LANGUAGE sql {_PFAD} AS $$\n"
     "INSERT INTO portal_zugriffe (zeitpunkt, zugang_id, sitzung_id, aktion, ergebnis, objekt_art, objekt_id)\n"
     "VALUES (portal_jetzt(), p_zugang, p_sitzung, p_aktion, p_ergebnis, 'freigabe', p_freigabe)\n"
     "$$"),
)

_LEER_LISTE = "NULL::integer, NULL::integer, NULL::text, NULL::text, NULL::date, NULL::text, NULL::integer, NULL::text, NULL::text"

# Die Funktionen für den Benutzer des Portals (SECURITY DEFINER): (Name, Argumente, SQL)
_FUNKTIONEN = (
    ("portal_unterlagen", "p_sitzung text",
     "CREATE OR REPLACE FUNCTION portal_unterlagen(p_sitzung text)\n"
     "RETURNS TABLE (ergebnis text, minuten integer, freigabe integer, art text, titel text, datum date, typ text, groesse integer, auftrag text,\n"
     f"  objekt text) LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "  v_kunde integer;\n"
     "  v_rest integer;\n"
     "BEGIN\n"
     "  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n"
     "  IF v_sitzung IS NULL THEN\n"
     f"    RETURN QUERY SELECT 'ungueltig'::text, {_LEER_LISTE};\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n"
     "  IF v_rest > 0 THEN\n"
     "    PERFORM portal_protokoll(v_zugang, v_sitzung, 'unterlagen', 'bremse');\n"
     f"    RETURN QUERY SELECT 'bremse'::text, v_rest, {_LEER_LISTE.split(', ', 1)[1]};\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  PERFORM portal_protokoll(v_zugang, v_sitzung, 'unterlagen', 'ok');\n"
     "  RETURN QUERY SELECT 'ok'::text, NULL::integer, f.id, f.art::text, f.titel::text, f.datum, f.kopie_typ::text, f.kopie_groesse, q.auftrag, q.objekt\n"
     "    FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n"
     "    WHERE f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL\n"
     "      AND q.kunde = v_kunde\n"
     "    ORDER BY f.datum DESC, f.id DESC;\n"
     "  IF NOT FOUND THEN\n"
     f"    RETURN QUERY SELECT 'leer'::text, {_LEER_LISTE};\n"
     "  END IF;\n"
     "END\n"
     "$$"),
    ("portal_datei_anfordern", "p_sitzung text, p_freigabe integer, p_anschluss text",
     "CREATE OR REPLACE FUNCTION portal_datei_anfordern(p_sitzung text, p_freigabe integer, p_anschluss text)\n"
     f"RETURNS TABLE (ergebnis text, minuten integer) LANGUAGE plpgsql SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_zugang integer;\n"
     "  v_sitzung integer;\n"
     "  v_kunde integer;\n"
     "  v_rest integer;\n"
     "BEGIN\n"
     "  IF NOT portal_hash_gueltig(p_anschluss) OR p_freigabe IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n"
     "  IF v_sitzung IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  v_rest := greatest(\n"
     "    portal_bremse('datei:z:' || v_zugang, 300, interval '1 hour'),\n"
     "    portal_bremse('datei:zt:' || v_zugang, 1500, interval '1 day'),\n"
     "    portal_bremse('datei:a:' || p_anschluss, 300, interval '1 hour'),\n"
     "    portal_bremse('datei:g', 5000, interval '1 hour'));\n"
     "  IF v_rest > 0 THEN\n"
     "    PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'bremse', p_freigabe);\n"
     "    RETURN QUERY SELECT 'bremse'::text, v_rest;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  IF NOT portal_sichtbar(p_freigabe, v_kunde) THEN\n"
     "    PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'unbekannt', p_freigabe);\n"
     "    RETURN QUERY SELECT 'unbekannt'::text, NULL::integer;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'ok', p_freigabe);\n"
     "  RETURN QUERY SELECT 'ok'::text, NULL::integer;\n"
     "END\n"
     "$$"),
    ("portal_datei", "p_sitzung text, p_freigabe integer",
     "CREATE OR REPLACE FUNCTION portal_datei(p_sitzung text, p_freigabe integer)\n"
     f"RETURNS TABLE (ergebnis text, name text, typ text, groesse integer, titel text) LANGUAGE plpgsql STABLE SECURITY DEFINER {_PFAD} AS $$\n"
     "#variable_conflict use_column\n"
     "DECLARE\n"
     "  v_sitzung integer;\n"
     "  v_kunde integer;\n"
     "BEGIN\n"
     "  SELECT k.sitzung, k.kunde INTO v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n"
     "  IF v_sitzung IS NULL OR p_freigabe IS NULL THEN\n"
     "    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::text, NULL::integer, NULL::text;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  IF NOT portal_sichtbar(p_freigabe, v_kunde) OR NOT EXISTS (\n"
     "      SELECT 1 FROM portal_zugriffe z WHERE z.sitzung_id = v_sitzung AND z.aktion = 'datei_angefordert' AND z.ergebnis = 'ok'\n"
     "        AND z.objekt_art = 'freigabe' AND z.objekt_id = p_freigabe AND z.zeitpunkt > portal_jetzt() - interval '30 minutes') THEN\n"
     "    RETURN QUERY SELECT 'unbekannt'::text, NULL::text, NULL::text, NULL::integer, NULL::text;\n"
     "    RETURN;\n"
     "  END IF;\n"
     "  RETURN QUERY SELECT 'ok'::text, f.kopie_name::text, f.kopie_typ::text, f.kopie_groesse, f.titel::text FROM portal_freigaben f WHERE f.id = p_freigabe;\n"
     "END\n"
     "$$"),
)

# Name -> Argumente der Funktionen, die der Benutzer des Portals aufrufen darf (app/portal/rechte.py::FUNKTIONEN nimmt diese dazu)
FUER_DAS_PORTAL = {name: argumente for name, argumente, _sql in _FUNKTIONEN}

# Alle Anweisungen in Reihenfolge: Helfer, Funktionen, dann für alle nicht ausführbar. @SCHEMA@ = Schema der Tabellen.
ANWEISUNGEN = tuple(
    [sql for _sig, sql in _HELFER]
    + [sql for _n, _a, sql in _FUNKTIONEN]
    + [f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC" for sig, _sql in _HELFER]
    + [f"REVOKE ALL ON FUNCTION {name}({_typen(argumente)}) FROM PUBLIC" for name, argumente, _sql in _FUNKTIONEN]
)

# Für den Wächter: jede Quelle aus app/portal/werte.py::FREIGABE_QUELLEN hat in portal_quelle() genau einen Zweig.
ZWEIGE = tuple(re.findall(r"p_quelle = '(\w+)'", _HELFER[3][1]))


def anweisungen(schema: str) -> list[str]:
    from .rechte import _name
    schema = _name(schema)
    return [a.replace("@SCHEMA@", schema) for a in ANWEISUNGEN]


def pg_anlegen(target, connection, **kw):
    """Nach jedem create_all() unter PostgreSQL, nach den Funktionen aus funktionen.py (sie werden hier gebraucht). Fehlen Tabellen (create_all() nur für
    einzelne Tabellen) oder die Funktionen für Link und Sitzung, bleibt es bei nichts."""
    if connection.dialect.name != "postgresql":
        return
    da = connection.exec_driver_sql(
        "SELECT to_regclass('portal_freigaben') IS NOT NULL AND to_regclass('portal_zugriffe') IS NOT NULL AND to_regclass('invoices') IS NOT NULL "
        "AND to_regclass('checklist_versions') IS NOT NULL AND to_regclass('webanfragen') IS NOT NULL "
        "AND to_regprocedure('portal_sitzung_id(text, boolean)') IS NOT NULL").scalar()
    if not da:
        return
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar()
    for a in anweisungen(schema):
        connection.exec_driver_sql(a)
