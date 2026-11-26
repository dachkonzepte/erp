"""kundenportal_freigaben -- Freigaben der Unterlagen fürs Kundenportal und die Funktionen der Datenbank zum Lesen (seit 1.11.31, Stufe P2a, Bauplan P2)

- Tabelle portal_freigaben (app/models.py::PortalFreigabe): je Zeile eine Unterlage, die ein Kunde im Portal sieht -- Kunde fest, Quelle als Tabelle und
  ID ohne Fremdschlüssel, Titel und Datum fürs Portal, freigegeben / zurückgenommen (nie gelöscht), Kopie (ab P2b). Feste Werte als CHECK (CHECKS).
- portal_zugriffe: zwei neue Aktionen („unterlagen“, „datei_angefordert“) -- der CHECK ck_portal_zugriff_aktion wird ersetzt (vorher AKTION_VORHER).
- Nur unter PostgreSQL: die Helfer und drei Funktionen mit SECURITY DEFINER aus app/portal/unterlagen.py::ANWEISUNGEN, wörtlich -- portal_unterlagen,
  portal_datei_anfordern, portal_datei; danach keine für alle ausführbar. EXECUTE für den Benutzer des Portals setzt scripts/portal_rechte.py nach der
  Migration (update.sh). @SCHEMA@ wird beim Ausführen durch das Schema der Verbindung ersetzt (current_schema()).

downgrade(): verweigert, solange es eine Freigabe oder einen Eintrag mit einer der neuen Aktionen gibt; sonst fallen Funktionen, Tabelle und die beiden
Aktionen weg.

Revision ID: e5c8a1f3b9d2
Revises: d7f3a9c1e284
Create Date: 2026-11-26

"""
import re

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e5c8a1f3b9d2'
down_revision = 'd7f3a9c1e284'
branch_labels = None
depends_on = None

CHECKS = {
    'ck_portal_freigabe_art': "art IN ('angebot', 'auftrag', 'vertrag', 'rechnung', 'mahnung', 'abnahmeprotokoll', 'einsatzbericht', 'brief', 'checkliste', 'foto', 'dokument')",
    'ck_portal_freigabe_quelle': "quelle IN ('sent_documents', 'invoices', 'reminders', 'service_reports', 'checklist_versions', 'notice_letters', 'service_report_photos', 'customer_documents', 'project_documents', 'property_documents', 'defect_files', 'order_acceptance_files')",
    'ck_portal_freigabe_kopie_typ': "kopie_typ IS NULL OR kopie_typ IN ('application/pdf', 'image/jpeg')",
    'ck_portal_freigabe_kopie_fehler': "kopie_fehler IS NULL OR kopie_fehler IN ('zu_gross', 'nicht_lesbar', 'falscher_typ', 'pruefsumme', 'abbruch')",
    'ck_portal_zugriff_aktion': "aktion IN ('link_geoeffnet', 'code_angefordert', 'code_gesendet', 'code_fehler', 'code_falsch', 'code_abgelaufen', 'angemeldet', 'verlaengert', 'abgemeldet', 'ueberall_abgemeldet', 'unterlagen', 'datei_angefordert')",
}

AKTION_VORHER = "aktion IN ('link_geoeffnet', 'code_angefordert', 'code_gesendet', 'code_fehler', 'code_falsch', 'code_abgelaufen', 'angemeldet', 'verlaengert', 'abgemeldet', 'ueberall_abgemeldet')"

ANWEISUNGEN = (
    'CREATE OR REPLACE FUNCTION portal_projekt_offen(p_projekt integer) RETURNS boolean LANGUAGE sql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nSELECT coalesce((SELECT NOT p.is_template AND NOT p.archived AND p.archiviert_am IS NULL FROM projects p WHERE p.id = p_projekt), false)\n$$',
    "CREATE OR REPLACE FUNCTION portal_adresse(p_objekt integer) RETURNS text LANGUAGE sql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nSELECT nullif(concat_ws(', ', nullif(pr.street, ''), nullif(concat_ws(' ', nullif(pr.postal_code, ''), nullif(pr.city, '')), '')), '')\nFROM properties pr WHERE pr.id = p_objekt\n$$",
    "CREATE OR REPLACE FUNCTION portal_fassung_gilt(p_fassung integer) RETURNS boolean LANGUAGE sql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nSELECT NOT EXISTS (\n  SELECT 1 FROM checklist_versions v JOIN checklist_attachments a ON a.checklist_id = v.checklist_id\n  WHERE v.id = p_fassung AND a.discarded_at IS NOT NULL\n    AND a.id IN (SELECT e::integer FROM jsonb_array_elements_text(coalesce(nullif(v.signature_ids, ''), '[]')::jsonb) AS e))\n$$",
    "CREATE OR REPLACE FUNCTION portal_quelle(p_quelle text, p_id integer)\nRETURNS TABLE (kunde integer, auftrag text, objekt text) LANGUAGE plpgsql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nBEGIN\n  IF p_quelle = 'invoices' THEN\n    RETURN QUERY SELECT i.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM invoices i JOIN orders o ON o.id = i.order_id JOIN projects p ON p.id = o.project_id\n      WHERE i.id = p_id AND i.status <> 'entwurf' AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'reminders' THEN\n    RETURN QUERY SELECT i.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM reminders r JOIN invoices i ON i.id = r.invoice_id JOIN orders o ON o.id = i.order_id JOIN projects p ON p.id = o.project_id\n      WHERE r.id = p_id AND r.status = 'versendet' AND r.replaced_by_id IS NULL AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'sent_documents' THEN\n    RETURN QUERY SELECT p.customer_id, NULL::text, portal_adresse(p.property_id)\n      FROM sent_documents s JOIN quotes q ON q.id = s.document_id JOIN projects p ON p.id = q.project_id\n      WHERE s.id = p_id AND s.document_type = 'angebot' AND portal_projekt_offen(p.id)\n    UNION ALL SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM sent_documents s JOIN orders o ON o.id = s.document_id JOIN projects p ON p.id = o.project_id\n      WHERE s.id = p_id AND s.document_type = 'auftrag' AND portal_projekt_offen(p.id)\n    UNION ALL SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM sent_documents s JOIN order_contracts c ON c.id = s.document_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n      WHERE s.id = p_id AND s.document_type = 'vertrag' AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'service_reports' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM service_reports sr JOIN orders o ON o.id = sr.order_id JOIN projects p ON p.id = o.project_id\n      WHERE sr.id = p_id AND sr.status = 'unterschrieben' AND sr.pdf_document_id IS NOT NULL AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'checklist_versions' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM checklist_versions v JOIN checklists c ON c.id = v.checklist_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n      WHERE v.id = p_id AND portal_fassung_gilt(v.id) AND portal_projekt_offen(p.id)\n    UNION ALL SELECT pr.customer_id, NULL::text, portal_adresse(pr.id)\n      FROM checklist_versions v JOIN checklists c ON c.id = v.checklist_id JOIN properties pr ON pr.id = c.property_id\n      WHERE v.id = p_id AND c.order_id IS NULL AND portal_fassung_gilt(v.id);\n  ELSIF p_quelle = 'notice_letters' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM notice_letters n JOIN checklists c ON c.id = n.checklist_id JOIN orders o ON o.id = c.order_id JOIN projects p ON p.id = o.project_id\n      WHERE n.id = p_id AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'service_report_photos' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM service_report_photos f JOIN service_reports sr ON sr.id = f.service_report_id JOIN orders o ON o.id = sr.order_id\n      JOIN projects p ON p.id = o.project_id\n      WHERE f.id = p_id AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'customer_documents' THEN\n    RETURN QUERY SELECT d.customer_id, NULL::text, NULL::text FROM customer_documents d WHERE d.id = p_id;\n  ELSIF p_quelle = 'project_documents' THEN\n    RETURN QUERY SELECT p.customer_id, NULL::text, portal_adresse(p.property_id)\n      FROM project_documents d JOIN projects p ON p.id = d.project_id\n      WHERE d.id = p_id AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'property_documents' THEN\n    RETURN QUERY SELECT pr.customer_id, NULL::text, portal_adresse(pr.id)\n      FROM property_documents d JOIN properties pr ON pr.id = d.property_id LEFT JOIN webanfragen w ON w.id = d.webanfrage_id\n      WHERE d.id = p_id AND w.archiviert_am IS NULL;\n  ELSIF p_quelle = 'defect_files' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM defect_files f JOIN defects d ON d.id = f.defect_id JOIN orders o ON o.id = d.order_id JOIN projects p ON p.id = o.project_id\n      WHERE f.id = p_id AND portal_projekt_offen(p.id);\n  ELSIF p_quelle = 'order_acceptance_files' THEN\n    RETURN QUERY SELECT o.customer_id, o.order_number::text, portal_adresse(p.property_id)\n      FROM order_acceptance_files f JOIN order_acceptances a ON a.id = f.acceptance_id JOIN orders o ON o.id = a.order_id\n      JOIN projects p ON p.id = o.project_id\n      WHERE f.id = p_id AND a.discarded_at IS NULL AND portal_projekt_offen(p.id);\n  END IF;\nEND\n$$",
    'CREATE OR REPLACE FUNCTION portal_sichtbar(p_freigabe integer, p_kunde integer) RETURNS boolean LANGUAGE sql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nSELECT EXISTS (\n  SELECT 1 FROM portal_freigaben f\n  WHERE f.id = p_freigabe AND f.customer_id = p_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL\n    AND EXISTS (SELECT 1 FROM portal_quelle(f.quelle, f.quelle_id) q WHERE q.kunde = p_kunde))\n$$',
    'CREATE OR REPLACE FUNCTION portal_kunde_der_sitzung(p_sitzung text)\nRETURNS TABLE (zugang integer, sitzung integer, kunde integer) LANGUAGE sql STABLE SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nSELECT s.zugang_id, s.id, z.customer_id FROM portal_sitzungen s JOIN portal_zugaenge z ON z.id = s.zugang_id\nWHERE s.id = portal_sitzung_id(p_sitzung, true)\n$$',
    "CREATE OR REPLACE FUNCTION portal_protokoll_freigabe(p_zugang integer, p_sitzung integer, p_aktion text, p_ergebnis text, p_freigabe integer)\nRETURNS void LANGUAGE sql SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\nINSERT INTO portal_zugriffe (zeitpunkt, zugang_id, sitzung_id, aktion, ergebnis, objekt_art, objekt_id)\nVALUES (portal_jetzt(), p_zugang, p_sitzung, p_aktion, p_ergebnis, 'freigabe', p_freigabe)\n$$",
    "CREATE OR REPLACE FUNCTION portal_unterlagen(p_sitzung text)\nRETURNS TABLE (ergebnis text, minuten integer, freigabe integer, art text, titel text, datum date, typ text, groesse integer, auftrag text,\n  objekt text) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_zugang integer;\n  v_sitzung integer;\n  v_kunde integer;\n  v_rest integer;\nBEGIN\n  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer, NULL::integer, NULL::text, NULL::text, NULL::date, NULL::text, NULL::integer, NULL::text, NULL::text;\n    RETURN;\n  END IF;\n  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n  IF v_rest > 0 THEN\n    PERFORM portal_protokoll(v_zugang, v_sitzung, 'unterlagen', 'bremse');\n    RETURN QUERY SELECT 'bremse'::text, v_rest, NULL::integer, NULL::text, NULL::text, NULL::date, NULL::text, NULL::integer, NULL::text, NULL::text;\n    RETURN;\n  END IF;\n  PERFORM portal_protokoll(v_zugang, v_sitzung, 'unterlagen', 'ok');\n  RETURN QUERY SELECT 'ok'::text, NULL::integer, f.id, f.art::text, f.titel::text, f.datum, f.kopie_typ::text, f.kopie_groesse, q.auftrag, q.objekt\n    FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n    WHERE f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL\n      AND q.kunde = v_kunde\n    ORDER BY f.datum DESC, f.id DESC;\n  IF NOT FOUND THEN\n    RETURN QUERY SELECT 'leer'::text, NULL::integer, NULL::integer, NULL::text, NULL::text, NULL::date, NULL::text, NULL::integer, NULL::text, NULL::text;\n  END IF;\nEND\n$$",
    "CREATE OR REPLACE FUNCTION portal_datei_anfordern(p_sitzung text, p_freigabe integer, p_anschluss text)\nRETURNS TABLE (ergebnis text, minuten integer) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_zugang integer;\n  v_sitzung integer;\n  v_kunde integer;\n  v_rest integer;\nBEGIN\n  IF NOT portal_hash_gueltig(p_anschluss) OR p_freigabe IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n    RETURN;\n  END IF;\n  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer;\n    RETURN;\n  END IF;\n  v_rest := greatest(\n    portal_bremse('datei:z:' || v_zugang, 300, interval '1 hour'),\n    portal_bremse('datei:zt:' || v_zugang, 1500, interval '1 day'),\n    portal_bremse('datei:a:' || p_anschluss, 300, interval '1 hour'),\n    portal_bremse('datei:g', 5000, interval '1 hour'));\n  IF v_rest > 0 THEN\n    PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'bremse', p_freigabe);\n    RETURN QUERY SELECT 'bremse'::text, v_rest;\n    RETURN;\n  END IF;\n  IF NOT portal_sichtbar(p_freigabe, v_kunde) THEN\n    PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'unbekannt', p_freigabe);\n    RETURN QUERY SELECT 'unbekannt'::text, NULL::integer;\n    RETURN;\n  END IF;\n  PERFORM portal_protokoll_freigabe(v_zugang, v_sitzung, 'datei_angefordert', 'ok', p_freigabe);\n  RETURN QUERY SELECT 'ok'::text, NULL::integer;\nEND\n$$",
    "CREATE OR REPLACE FUNCTION portal_datei(p_sitzung text, p_freigabe integer)\nRETURNS TABLE (ergebnis text, name text, typ text, groesse integer, titel text) LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_sitzung integer;\n  v_kunde integer;\nBEGIN\n  SELECT k.sitzung, k.kunde INTO v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL OR p_freigabe IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::text, NULL::text, NULL::integer, NULL::text;\n    RETURN;\n  END IF;\n  IF NOT portal_sichtbar(p_freigabe, v_kunde) OR NOT EXISTS (\n      SELECT 1 FROM portal_zugriffe z WHERE z.sitzung_id = v_sitzung AND z.aktion = 'datei_angefordert' AND z.ergebnis = 'ok'\n        AND z.objekt_art = 'freigabe' AND z.objekt_id = p_freigabe AND z.zeitpunkt > portal_jetzt() - interval '30 minutes') THEN\n    RETURN QUERY SELECT 'unbekannt'::text, NULL::text, NULL::text, NULL::integer, NULL::text;\n    RETURN;\n  END IF;\n  RETURN QUERY SELECT 'ok'::text, f.kopie_name::text, f.kopie_typ::text, f.kopie_groesse, f.titel::text FROM portal_freigaben f WHERE f.id = p_freigabe;\nEND\n$$",
    'REVOKE ALL ON FUNCTION portal_projekt_offen(integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_adresse(integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_fassung_gilt(integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_quelle(text, integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_sichtbar(integer, integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_kunde_der_sitzung(text) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_protokoll_freigabe(integer, integer, text, text, integer) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_unterlagen(text) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_datei_anfordern(text, integer, text) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_datei(text, integer) FROM PUBLIC',
)


def _schema() -> str:
    schema = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema or ""):
        raise RuntimeError("Ungültiges Schema für die Funktionen des Kundenportals.")
    return schema


def upgrade() -> None:
    op.create_table(
        'portal_freigaben',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('art', sa.String(length=20), nullable=False),
        sa.Column('quelle', sa.String(length=30), nullable=False),
        sa.Column('quelle_id', sa.Integer(), nullable=False),
        sa.Column('titel', sa.String(length=120), nullable=False),
        sa.Column('datum', sa.Date(), nullable=False),
        sa.Column('regel', sa.String(length=30), nullable=True),
        sa.Column('freigegeben_am', sa.DateTime(), nullable=False),
        sa.Column('freigegeben_von_user_id', sa.Integer(), nullable=True),
        sa.Column('freigegeben_von_name', sa.String(length=160), server_default='System', nullable=False),
        sa.Column('zurueckgenommen_am', sa.DateTime(), nullable=True),
        sa.Column('zurueckgenommen_von_user_id', sa.Integer(), nullable=True),
        sa.Column('zurueckgenommen_von_name', sa.String(length=160), nullable=True),
        sa.Column('zurueckgenommen_grund', sa.String(length=500), nullable=True),
        sa.Column('kopie_name', sa.String(length=80), nullable=True),
        sa.Column('kopie_typ', sa.String(length=40), nullable=True),
        sa.Column('kopie_groesse', sa.Integer(), nullable=True),
        sa.Column('kopie_sha256', sa.String(length=64), nullable=True),
        sa.Column('kopie_bereit_am', sa.DateTime(), nullable=True),
        sa.Column('kopie_fehler', sa.String(length=30), nullable=True),
        sa.CheckConstraint(CHECKS['ck_portal_freigabe_art'], name='ck_portal_freigabe_art'),
        sa.CheckConstraint(CHECKS['ck_portal_freigabe_quelle'], name='ck_portal_freigabe_quelle'),
        sa.CheckConstraint(CHECKS['ck_portal_freigabe_kopie_typ'], name='ck_portal_freigabe_kopie_typ'),
        sa.CheckConstraint(CHECKS['ck_portal_freigabe_kopie_fehler'], name='ck_portal_freigabe_kopie_fehler'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kopie_name', name='uq_portal_freigabe_kopie'),
    )
    op.create_index('ix_portal_freigaben_customer_id', 'portal_freigaben', ['customer_id'], unique=False)
    op.create_index('uq_portal_freigabe_aktiv', 'portal_freigaben', ['quelle', 'quelle_id'], unique=True,
                    sqlite_where=sa.text('zurueckgenommen_am IS NULL'), postgresql_where=sa.text('zurueckgenommen_am IS NULL'))
    with op.batch_alter_table('portal_zugriffe') as batch_op:
        batch_op.drop_constraint('ck_portal_zugriff_aktion', type_='check')
        batch_op.create_check_constraint('ck_portal_zugriff_aktion', CHECKS['ck_portal_zugriff_aktion'])
    if op.get_bind().dialect.name != "postgresql":
        return
    schema = _schema()
    for anweisung in ANWEISUNGEN:
        op.get_bind().exec_driver_sql(anweisung.replace("@SCHEMA@", schema))


def downgrade() -> None:
    bind = op.get_bind()
    freigaben = bind.execute(sa.text("SELECT COUNT(*) FROM portal_freigaben")).scalar()
    neu = bind.execute(sa.text("SELECT COUNT(*) FROM portal_zugriffe WHERE aktion IN ('unterlagen', 'datei_angefordert')")).scalar()
    if freigaben or neu:
        raise RuntimeError(f"Downgrade verweigert: {freigaben} Freigaben, {neu} Einträge im Zugriffsprotokoll zu Unterlagen -- sie gingen verloren.")
    if bind.dialect.name == "postgresql":
        for anweisung in reversed(ANWEISUNGEN):
            if anweisung.startswith("REVOKE ALL ON FUNCTION "):
                signatur = anweisung[len("REVOKE ALL ON FUNCTION "):-len(" FROM PUBLIC")]
                bind.exec_driver_sql(f"DROP FUNCTION IF EXISTS {signatur}")
    with op.batch_alter_table('portal_zugriffe') as batch_op:
        batch_op.drop_constraint('ck_portal_zugriff_aktion', type_='check')
        batch_op.create_check_constraint('ck_portal_zugriff_aktion', AKTION_VORHER)
    op.drop_index('uq_portal_freigabe_aktiv', table_name='portal_freigaben')
    op.drop_index('ix_portal_freigaben_customer_id', table_name='portal_freigaben')
    op.drop_table('portal_freigaben')
