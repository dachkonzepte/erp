"""postfach_je_termin_und_sperre -- die Outlook-Kennung gilt je Postfach, der Stand hängt am Postfach (seit 1.9.159, Stufe 6, R2, Punkt 3)

upgrade(), auf einem Bestand:
- app_users.outlook_mailbox: klein, ohne Leerzeichen, leer wird NULL, eindeutig. Zwei Konten am selben Postfach: das aktive behält es, sonst das ältere; das andere wird leer.
- calendar_events.outlook_postfach aus dem Postfach des Besitzers (auch eines, das sein Postfach gerade verlor). Dann eindeutig mit outlook_event_id. Doppelte: es bleibt die Zeile mit Projekt oder
  Angebot, sonst die älteste. Eine weitere mit eigenem Bezug bleibt ohne Verbindung zu Outlook und geht beim nächsten Lauf neu hinaus, eine ohne eigenen Bezug fällt weg (derselbe Termin).
- outlook_series_occurrences.outlook_postfach: Pflicht. Vorkommen ohne Postfach fallen weg, sie sind ein Schnappschuss, den der nächste Lauf neu holt.
- outlook_calendar_sync_state: postfach statt app_user_id, dazu die Sperre lauf_kennung, lauf_seit. Ohne Postfach fällt die Zeile weg. Zeigt der Delta-Link auf eine andere Adresse (Befund XP1),
  wird er geleert: der nächste Lauf liest den ganzen Kalender.

downgrade(): stellt die Spalten wieder her, app_user_id aus der Adresse. Die Klein-Schreibung und, was upgrade() als doppelt entfernt hat, kommen nicht zurück.

Revision ID: 7c2e9b41d3a8
Revises: 4f7a1c9e2b60
Create Date: 2026-10-31

"""
from collections import defaultdict
from urllib.parse import unquote, urlsplit

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2e9b41d3a8'
down_revision = '4f7a1c9e2b60'
branch_labels = None
depends_on = None

_KONTEN = sa.table("app_users", sa.column("id", sa.Integer), sa.column("outlook_mailbox", sa.String), sa.column("active", sa.Boolean))
_TERMINE = sa.table("calendar_events", sa.column("id", sa.Integer), sa.column("owner_user_id", sa.Integer), sa.column("project_id", sa.Integer), sa.column("quote_id", sa.Integer),
                    sa.column("outlook_event_id", sa.String), sa.column("outlook_postfach", sa.String), sa.column("outlook_etag", sa.String), sa.column("outlook_synced_at", sa.DateTime))
_VORKOMMEN = sa.table("outlook_series_occurrences", sa.column("id", sa.Integer), sa.column("owner_user_id", sa.Integer), sa.column("outlook_event_id", sa.String), sa.column("outlook_postfach", sa.String))
_STAND = sa.table("outlook_calendar_sync_state", sa.column("id", sa.Integer), sa.column("app_user_id", sa.Integer), sa.column("postfach", sa.String), sa.column("delta_link", sa.Text), sa.column("last_synced_at", sa.DateTime))


def adressen_vereinheitlichen(bind) -> dict[int, str]:
    """Konto -> Adresse, auch für Konten, die ihre Adresse hier verlieren: an ihren Terminen steht noch, wo sie liegen."""
    konten = bind.execute(sa.select(_KONTEN.c.id, _KONTEN.c.outlook_mailbox, _KONTEN.c.active).where(_KONTEN.c.outlook_mailbox.is_not(None))).all()
    adressen, vergeben = {}, set()
    for kennung, roh, _aktiv in sorted(konten, key=lambda z: (not z[2], z[0])):
        adresse = (roh or "").strip().lower() or None
        if adresse:
            adressen[kennung] = adresse
        wert = None if adresse in vergeben else adresse
        vergeben.add(wert)
        if wert != roh:
            bind.execute(_KONTEN.update().where(_KONTEN.c.id == kennung).values(outlook_mailbox=wert))
    return adressen


def termine_zuordnen(bind, adressen: dict[int, str]) -> None:
    zeilen = bind.execute(sa.select(_TERMINE.c.id, _TERMINE.c.owner_user_id, _TERMINE.c.project_id, _TERMINE.c.quote_id, _TERMINE.c.outlook_event_id).where(_TERMINE.c.outlook_event_id.is_not(None))).all()
    gruppen = defaultdict(list)
    for zeile in zeilen:
        adresse = adressen.get(zeile.owner_user_id)
        if adresse:
            bind.execute(_TERMINE.update().where(_TERMINE.c.id == zeile.id).values(outlook_postfach=adresse))
            gruppen[(adresse, zeile.outlook_event_id)].append(zeile)
    for gruppe in gruppen.values():
        gruppe.sort(key=lambda z: (z.project_id is None and z.quote_id is None, z.id))
        bleibt = (gruppe[0].project_id, gruppe[0].quote_id)
        for zeile in gruppe[1:]:
            if (zeile.project_id, zeile.quote_id) in ((None, None), bleibt):
                bind.execute(_TERMINE.delete().where(_TERMINE.c.id == zeile.id))
            else:
                bind.execute(_TERMINE.update().where(_TERMINE.c.id == zeile.id).values(outlook_event_id=None, outlook_postfach=None, outlook_etag=None, outlook_synced_at=None))


def vorkommen_zuordnen(bind, adressen: dict[int, str]) -> None:
    gesehen = set()
    for zeile in bind.execute(sa.select(_VORKOMMEN.c.id, _VORKOMMEN.c.owner_user_id, _VORKOMMEN.c.outlook_event_id).order_by(_VORKOMMEN.c.id)).all():
        adresse = adressen.get(zeile.owner_user_id)
        if adresse is None or (adresse, zeile.outlook_event_id) in gesehen:
            bind.execute(_VORKOMMEN.delete().where(_VORKOMMEN.c.id == zeile.id))
            continue
        gesehen.add((adresse, zeile.outlook_event_id))
        bind.execute(_VORKOMMEN.update().where(_VORKOMMEN.c.id == zeile.id).values(outlook_postfach=adresse))


def _link_passt(link: str | None, adresse: str) -> bool:
    if not link:
        return True
    pfad = unquote(urlsplit(link).path).casefold()
    return "@" not in pfad or adresse in pfad  # Microsoft kann die Adresse durch eine Kennung ersetzen: dann lässt sich nichts sagen


def staende_zuordnen(bind, adressen: dict[int, str]) -> None:
    gruppen = defaultdict(list)
    for zeile in bind.execute(sa.select(_STAND.c.id, _STAND.c.app_user_id, _STAND.c.delta_link, _STAND.c.last_synced_at)).all():
        adresse = adressen.get(zeile.app_user_id)
        if adresse is None:
            bind.execute(_STAND.delete().where(_STAND.c.id == zeile.id))
        else:
            gruppen[adresse].append(zeile)
    for adresse, gruppe in gruppen.items():
        gruppe.sort(key=lambda z: (z.last_synced_at is None, z.last_synced_at and -z.last_synced_at.timestamp(), z.id))
        for zeile in gruppe[1:]:
            bind.execute(_STAND.delete().where(_STAND.c.id == zeile.id))
        werte = {"postfach": adresse}
        if not _link_passt(gruppe[0].delta_link, adresse):
            werte["delta_link"] = None
        bind.execute(_STAND.update().where(_STAND.c.id == gruppe[0].id).values(**werte))


def upgrade() -> None:
    bind = op.get_bind()
    adressen = adressen_vereinheitlichen(bind)
    op.create_index("ix_app_users_outlook_mailbox", "app_users", ["outlook_mailbox"], unique=True)

    op.add_column("calendar_events", sa.Column("outlook_postfach", sa.String(length=255), nullable=True))
    termine_zuordnen(bind, adressen)
    op.create_index("uq_calendar_events_postfach_kennung", "calendar_events", ["outlook_postfach", "outlook_event_id"], unique=True)

    op.add_column("outlook_series_occurrences", sa.Column("outlook_postfach", sa.String(length=255), nullable=True))
    vorkommen_zuordnen(bind, adressen)
    with op.batch_alter_table("outlook_series_occurrences") as batch_op:
        batch_op.drop_constraint("uq_outlook_series_occurrence_owner_event", type_="unique")
        batch_op.alter_column("outlook_postfach", existing_type=sa.String(length=255), nullable=False)
    op.create_index("uq_outlook_series_postfach_kennung", "outlook_series_occurrences", ["outlook_postfach", "outlook_event_id"], unique=True)

    op.add_column("outlook_calendar_sync_state", sa.Column("postfach", sa.String(length=255), nullable=True))
    op.add_column("outlook_calendar_sync_state", sa.Column("lauf_kennung", sa.String(length=36), nullable=True))
    op.add_column("outlook_calendar_sync_state", sa.Column("lauf_seit", sa.DateTime(), nullable=True))
    staende_zuordnen(bind, adressen)
    with op.batch_alter_table("outlook_calendar_sync_state") as batch_op:
        batch_op.drop_index("ix_outlook_calendar_sync_state_app_user_id")
        batch_op.drop_constraint("uq_outlook_sync_state_app_user_id", type_="unique")
        batch_op.drop_column("app_user_id")
        batch_op.alter_column("postfach", existing_type=sa.String(length=255), nullable=False)
        batch_op.create_unique_constraint("uq_outlook_sync_state_postfach", ["postfach"])


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("outlook_calendar_sync_state") as batch_op:
        batch_op.add_column(sa.Column("app_user_id", sa.Integer(), nullable=True))
    konten = {z.outlook_mailbox: z.id for z in bind.execute(sa.select(_KONTEN.c.id, _KONTEN.c.outlook_mailbox).where(_KONTEN.c.outlook_mailbox.is_not(None))).all()}
    for zeile in bind.execute(sa.select(_STAND.c.id, _STAND.c.postfach)).all():
        if zeile.postfach in konten:
            bind.execute(_STAND.update().where(_STAND.c.id == zeile.id).values(app_user_id=konten[zeile.postfach]))
        else:
            bind.execute(_STAND.delete().where(_STAND.c.id == zeile.id))
    with op.batch_alter_table("outlook_calendar_sync_state") as batch_op:
        batch_op.drop_constraint("uq_outlook_sync_state_postfach", type_="unique")
        batch_op.drop_column("postfach")
        batch_op.drop_column("lauf_kennung")
        batch_op.drop_column("lauf_seit")
        batch_op.alter_column("app_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint("uq_outlook_sync_state_app_user_id", ["app_user_id"])
        batch_op.create_foreign_key("outlook_calendar_sync_state_app_user_id_fkey", "app_users", ["app_user_id"], ["id"])
        batch_op.create_index("ix_outlook_calendar_sync_state_app_user_id", ["app_user_id"], unique=False)

    op.drop_index("uq_outlook_series_postfach_kennung", table_name="outlook_series_occurrences")
    with op.batch_alter_table("outlook_series_occurrences") as batch_op:
        batch_op.drop_column("outlook_postfach")
        batch_op.create_unique_constraint("uq_outlook_series_occurrence_owner_event", ["owner_user_id", "outlook_event_id"])

    op.drop_index("uq_calendar_events_postfach_kennung", table_name="calendar_events")
    op.drop_column("calendar_events", "outlook_postfach")
    op.drop_index("ix_app_users_outlook_mailbox", table_name="app_users")
