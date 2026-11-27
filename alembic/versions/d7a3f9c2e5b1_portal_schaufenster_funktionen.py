"""portal_schaufenster_funktionen -- Funktionen der Datenbank für Rechnungen und Termine des Kundenportals (seit 1.11.42, Stufe P2d, Teil 2)

portal_rechnungen(sitzung), portal_termine(sitzung) und portal_uebersicht(sitzung): SECURITY DEFINER, fester search_path, lesen nur das Schaufenster (1.11.41) und prüfen live wie die
Unterlagen; Text wörtlich aus app/portal/schaufenster.py. Dazu drei Aktionen im Zugriffsprotokoll („rechnungen“, „termine“, „uebersicht“) -- der CHECK
ck_portal_zugriff_aktion wird ersetzt (CHECKS, vorher AKTION_VORHER). Keine Daten geändert.

downgrade(): verweigert, solange das Zugriffsprotokoll Einträge der neuen Aktionen hat (sie gingen verloren); sonst Funktionen weg, CHECK zurück.

Revision ID: d7a3f9c2e5b1
Revises: c4e8a2f6b1d3
Create Date: 2026-11-27

"""
import re

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd7a3f9c2e5b1'
down_revision = 'c4e8a2f6b1d3'
branch_labels = None
depends_on = None

CHECKS = {'ck_portal_zugriff_aktion': "aktion IN ('link_geoeffnet', 'code_angefordert', 'code_gesendet', 'code_fehler', 'code_falsch', 'code_abgelaufen', 'angemeldet', 'verlaengert', 'abgemeldet', 'ueberall_abgemeldet', 'unterlagen', 'datei_angefordert', 'rechnungen', 'termine', 'uebersicht')"}
AKTION_VORHER = "aktion IN ('link_geoeffnet', 'code_angefordert', 'code_gesendet', 'code_fehler', 'code_falsch', 'code_abgelaufen', 'angemeldet', 'verlaengert', 'abgemeldet', 'ueberall_abgemeldet', 'unterlagen', 'datei_angefordert')"
ANWEISUNGEN = (
    "CREATE OR REPLACE FUNCTION portal_rechnungen(p_sitzung text)\nRETURNS TABLE (ergebnis text, minuten integer, stand timestamp, freigabe integer, art text, titel text, nummer text, datum date, faellig date,\n  betrag numeric, zustand text, offen numeric, ueberfaellig boolean, bezug text, zu_freigabe integer, auftrag text, objekt text)\nLANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_zugang integer;\n  v_sitzung integer;\n  v_kunde integer;\n  v_rest integer;\n  v_stand timestamp;\nBEGIN\n  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer, NULL::timestamp, NULL::integer, NULL::text, NULL::text, NULL::text, NULL::date, NULL::date, NULL::numeric, NULL::text, NULL::numeric, NULL::boolean, NULL::text, NULL::integer, NULL::text, NULL::text;\n    RETURN;\n  END IF;\n  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n  IF v_rest > 0 THEN\n    PERFORM portal_protokoll(v_zugang, v_sitzung, 'rechnungen', 'bremse');\n    RETURN QUERY SELECT 'bremse'::text, v_rest, NULL::timestamp, NULL::integer, NULL::text, NULL::text, NULL::text, NULL::date, NULL::date, NULL::numeric, NULL::text, NULL::numeric, NULL::boolean, NULL::text, NULL::integer, NULL::text, NULL::text;\n    RETURN;\n  END IF;\n  PERFORM portal_protokoll(v_zugang, v_sitzung, 'rechnungen', 'ok');\n  SELECT s.stand_am INTO v_stand FROM portal_schaufenster s WHERE s.customer_id = v_kunde;\n  RETURN QUERY\n    SELECT 'ok'::text, NULL::integer, v_stand, f.id, 'rechnung'::text, coalesce(r.art_text, f.titel)::text, r.nummer::text, coalesce(r.datum, f.datum),\n           r.faellig, r.brutto, r.zustand::text, r.offen, r.ueberfaellig, r.bezug_nummer::text, NULL::integer, q.auftrag, q.objekt\n      FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n      LEFT JOIN portal_rechnungen r ON r.invoice_id = f.quelle_id AND r.customer_id = v_kunde\n      WHERE f.quelle = 'invoices' AND f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL AND q.kunde = v_kunde\n    UNION ALL\n    SELECT 'ok'::text, NULL::integer, v_stand, f.id, 'mahnung'::text,\n           coalesce((SELECT nullif(trim(l.label), '') FROM reminder_levels l WHERE l.level = m.level ORDER BY l.id LIMIT 1), m.level || '. Mahnung')::text,\n           m.reminder_number::text, f.datum, NULL::date, NULL::numeric, NULL::text,\n           NULL::numeric, NULL::boolean, NULL::text,\n           (SELECT g.id FROM portal_freigaben g WHERE g.quelle = 'invoices' AND g.quelle_id = m.invoice_id AND portal_sichtbar(g.id, v_kunde)\n             ORDER BY g.id DESC LIMIT 1),\n           q.auftrag, q.objekt\n      FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q JOIN reminders m ON m.id = f.quelle_id\n      WHERE f.quelle = 'reminders' AND f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL AND q.kunde = v_kunde\n    ORDER BY 8 DESC, 4 DESC;\n  IF NOT FOUND THEN\n    RETURN QUERY SELECT 'leer'::text, NULL::integer, v_stand, NULL::integer, NULL::text, NULL::text, NULL::text, NULL::date, NULL::date, NULL::numeric, NULL::text, NULL::numeric, NULL::boolean, NULL::text, NULL::integer, NULL::text, NULL::text;\n  END IF;\nEND\n$$",
    "CREATE OR REPLACE FUNCTION portal_termine(p_sitzung text)\nRETURNS TABLE (ergebnis text, minuten integer, stand timestamp, auftrag text, objekt text, von date, bis date)\nLANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_zugang integer;\n  v_sitzung integer;\n  v_kunde integer;\n  v_rest integer;\n  v_stand timestamp;\nBEGIN\n  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer, NULL::timestamp, NULL::text, NULL::text, NULL::date, NULL::date;\n    RETURN;\n  END IF;\n  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n  IF v_rest > 0 THEN\n    PERFORM portal_protokoll(v_zugang, v_sitzung, 'termine', 'bremse');\n    RETURN QUERY SELECT 'bremse'::text, v_rest, NULL::timestamp, NULL::text, NULL::text, NULL::date, NULL::date;\n    RETURN;\n  END IF;\n  PERFORM portal_protokoll(v_zugang, v_sitzung, 'termine', 'ok');\n  SELECT s.stand_am INTO v_stand FROM portal_schaufenster s WHERE s.customer_id = v_kunde;\n  RETURN QUERY\n    SELECT 'ok'::text, NULL::integer, v_stand, o.order_number::text, portal_adresse(p.property_id), t.von, t.bis\n      FROM portal_termine t JOIN orders o ON o.id = t.order_id JOIN projects p ON p.id = o.project_id\n      WHERE t.customer_id = v_kunde AND o.customer_id = v_kunde AND o.status IN ('laeuft', 'pausiert') AND portal_projekt_offen(p.id)\n    ORDER BY t.von, t.order_id, t.id;\n  IF NOT FOUND THEN\n    RETURN QUERY SELECT 'leer'::text, NULL::integer, v_stand, NULL::text, NULL::text, NULL::date, NULL::date;\n  END IF;\nEND\n$$",
    "CREATE OR REPLACE FUNCTION portal_uebersicht(p_sitzung text)\nRETURNS TABLE (ergebnis text, minuten integer, stand timestamp, offen_anzahl integer, offen_summe numeric, faellig_titel text, faellig_nummer text,\n  faellig_am date, einsatz_von date, einsatz_bis date, einsatz_auftrag text, einsatz_objekt text, unterlagen integer, unterlage_titel text,\n  unterlage_datum date, fotos integer, foto_am date)\nLANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$\n#variable_conflict use_column\nDECLARE\n  v_zugang integer;\n  v_sitzung integer;\n  v_kunde integer;\n  v_rest integer;\n  v_stand timestamp;\n  v_heute date;\nBEGIN\n  SELECT k.zugang, k.sitzung, k.kunde INTO v_zugang, v_sitzung, v_kunde FROM portal_kunde_der_sitzung(p_sitzung) k;\n  IF v_sitzung IS NULL THEN\n    RETURN QUERY SELECT 'ungueltig'::text, NULL::integer, NULL::timestamp, NULL::integer, NULL::numeric, NULL::text, NULL::text, NULL::date, NULL::date, NULL::date, NULL::text, NULL::text, NULL::integer, NULL::text, NULL::date, NULL::integer, NULL::date;\n    RETURN;\n  END IF;\n  v_rest := portal_bremse('liste:s:' || v_sitzung, 120, interval '1 hour');\n  IF v_rest > 0 THEN\n    PERFORM portal_protokoll(v_zugang, v_sitzung, 'uebersicht', 'bremse');\n    RETURN QUERY SELECT 'bremse'::text, v_rest, NULL::timestamp, NULL::integer, NULL::numeric, NULL::text, NULL::text, NULL::date, NULL::date, NULL::date, NULL::text, NULL::text, NULL::integer, NULL::text, NULL::date, NULL::integer, NULL::date;\n    RETURN;\n  END IF;\n  PERFORM portal_protokoll(v_zugang, v_sitzung, 'uebersicht', 'ok');\n  SELECT s.stand_am INTO v_stand FROM portal_schaufenster s WHERE s.customer_id = v_kunde;\n  v_heute := ((portal_jetzt() AT TIME ZONE 'utc') AT TIME ZONE 'Europe/Berlin')::date;\n  RETURN QUERY\n    WITH sichtbar AS (\n      SELECT f.id, f.art, f.titel, f.datum, f.quelle, f.quelle_id, f.freigegeben_am\n        FROM portal_freigaben f CROSS JOIN LATERAL portal_quelle(f.quelle, f.quelle_id) q\n        WHERE f.customer_id = v_kunde AND f.zurueckgenommen_am IS NULL AND f.kopie_bereit_am IS NOT NULL AND f.kopie_name IS NOT NULL AND q.kunde = v_kunde),\n    offen AS (\n      SELECT r.invoice_id, r.art_text, r.nummer, r.datum, r.faellig, r.offen FROM sichtbar s JOIN portal_rechnungen r ON r.invoice_id = s.quelle_id\n        WHERE s.quelle = 'invoices' AND r.customer_id = v_kunde AND r.zustand IN ('offen', 'teilweise_bezahlt') AND r.offen > 0),\n    faellig AS (SELECT o.art_text, o.nummer, o.faellig FROM offen o ORDER BY o.faellig NULLS LAST, o.datum, o.invoice_id LIMIT 1),\n    einsatz AS (\n      SELECT t.von, t.bis, o.order_number, portal_adresse(p.property_id) AS objekt\n        FROM portal_termine t JOIN orders o ON o.id = t.order_id JOIN projects p ON p.id = o.project_id\n        WHERE t.customer_id = v_kunde AND o.customer_id = v_kunde AND o.status IN ('laeuft', 'pausiert') AND portal_projekt_offen(p.id)\n          AND t.bis >= v_heute\n        ORDER BY t.von, t.order_id, t.id LIMIT 1),\n    unterlagen AS (SELECT s.id, s.titel, s.datum FROM sichtbar s WHERE s.art NOT IN ('rechnung', 'mahnung', 'foto')),\n    letzte AS (SELECT u.titel, u.datum FROM unterlagen u ORDER BY u.datum DESC, u.id DESC LIMIT 1)\n    SELECT 'ok'::text, NULL::integer, v_stand, (SELECT count(*)::integer FROM offen), (SELECT coalesce(sum(o.offen), 0) FROM offen o),\n           fa.art_text::text, fa.nummer::text, fa.faellig, e.von, e.bis, e.order_number::text, e.objekt, (SELECT count(*)::integer FROM unterlagen),\n           l.titel::text, l.datum, (SELECT count(*)::integer FROM sichtbar s WHERE s.art = 'foto'),\n           (SELECT ((max(s.freigegeben_am) AT TIME ZONE 'utc') AT TIME ZONE 'Europe/Berlin')::date FROM sichtbar s WHERE s.art = 'foto')\n      FROM (SELECT 1) AS eins LEFT JOIN faellig fa ON true LEFT JOIN einsatz e ON true LEFT JOIN letzte l ON true;\nEND\n$$",
    'REVOKE ALL ON FUNCTION portal_rechnungen(text) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_termine(text) FROM PUBLIC',
    'REVOKE ALL ON FUNCTION portal_uebersicht(text) FROM PUBLIC',
)


def _schema() -> str:
    schema = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar()
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema or ""):
        raise RuntimeError("Ungültiges Schema für die Funktionen des Kundenportals.")
    return schema


def upgrade() -> None:
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
    neu = bind.execute(sa.text("SELECT COUNT(*) FROM portal_zugriffe WHERE aktion IN ('rechnungen', 'termine', 'uebersicht')")).scalar()
    if neu:
        raise RuntimeError(f"Downgrade verweigert: {neu} Einträge im Zugriffsprotokoll zu Rechnungen und Terminen -- sie gingen verloren.")
    if bind.dialect.name == "postgresql":
        for anweisung in reversed(ANWEISUNGEN):
            if anweisung.startswith("REVOKE ALL ON FUNCTION "):
                signatur = anweisung[len("REVOKE ALL ON FUNCTION "):-len(" FROM PUBLIC")]
                bind.exec_driver_sql(f"DROP FUNCTION IF EXISTS {signatur}")
    with op.batch_alter_table('portal_zugriffe') as batch_op:
        batch_op.drop_constraint('ck_portal_zugriff_aktion', type_='check')
        batch_op.create_check_constraint('ck_portal_zugriff_aktion', AKTION_VORHER)
