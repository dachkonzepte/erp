"""telefonbuch -- Sortierschlüssel für Listen nach Namen (seit 1.9.353, F6)

Runde V2b, Punkt 1: Listen nach Namen ohne Groß- und Kleinschreibung, Umlaute und Akzente beim Grundbuchstaben (Ä wie A, ß wie ss), unter SQLite
und PostgreSQL gleich und unabhängig von der Kollation des Servers. Unter PostgreSQL legt diese Migration die SQL-Funktion telefonbuch(text) an
(IMMUTABLE, ohne lower()/upper() der Datenbank -- die hingen an der Zeichenklassifizierung des Servers); unter SQLite meldet app/telefonbuch.py
dieselbe Rechnung an jeder Verbindung an, hier ist nichts zu tun. Keine Tabelle, keine Spalte, keine Daten.

FUNKTION ist der Text aus app/telefonbuch.py::pg_sql() zum Zeitpunkt dieser Migration, wörtlich -- tests/test_v753_telefonbuch.py vergleicht beide.
Eine geänderte Zeichentabelle braucht eine neue Migration (CREATE OR REPLACE), nie eine Änderung hier.

downgrade(): die Funktion fällt weg; die Fassung davor kennt sie nicht.

Revision ID: 9e4b2c7d1a35
Revises: 7c2e4a9b1d53
Create Date: 2026-11-17

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9e4b2c7d1a35'
down_revision = '7c2e4a9b1d53'
branch_labels = None
depends_on = None

FUNKTION = ('CREATE OR REPLACE FUNCTION telefonbuch(t text) RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE'
            " AS $$ "
            "SELECT NULLIF(replace(replace(replace(replace(replace(replace(translate(btrim(t, ' '), 'AÀÁÂÃÄÅĀĂĄàáâãäåāăąBCÇĆČçćčDĎĐďđEÈÉÊËĒĖĘĚèéêëēėęěFGĞĢğģHIÌÍÎÏĪĮİìíîïīįıJKĶķLĹĻĽŁĺļľłMNÑŃŅŇñńņňOÒÓÔÕÖØŌŐòóôõöøōőPQRŔŘŕřSŚŞŠȘśşšșTŢŤȚţťțUÙÚÛÜŪŮŰŲùúûüūůűųVWXYÝŸýÿZŹŻŽźżž', 'aaaaaaaaaaaaaaaaaaabcccccccdddddeeeeeeeeeeeeeeeeefggggghiiiiiiiiiiiiiiijkkklllllllllmnnnnnnnnnooooooooooooooooopqrrrrrssssssssstttttttuuuuuuuuuuuuuuuuuvwxyyyyyzzzzzzz'), 'ß', 'ss'), 'ẞ', 'ss'), 'Æ', 'ae'), 'æ', 'ae'), 'Œ', 'oe'), 'œ', 'oe'), '') $$")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(FUNKTION)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS telefonbuch(text)")
