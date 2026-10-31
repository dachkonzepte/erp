"""ganztaegige_termine_reparieren -- ein Tag bleibt ein Tag (seit 1.9.157, Stufe 6, R2, Punkt 1)

Bis 1.9.156 rechnete der Abgleich auch ganztägige Termine aus Outlook von UTC nach Berlin um: der 10.11. steht im Bestand als 10.11. 01:00 bis 11.11. 01:00 (im Sommer 02:00) und zeigt sich an zwei
Tagen. Der Delta-Abruf bringt ihn nicht von selbst neu, die Zeile bliebe falsch. upgrade() setzt jede ganztägige Zeile mit einer Uhrzeit auf die Form des Kalenders: Mitternacht, end_at der letzte
Tag. updated_at bleibt (sonst schöbe der Abgleich den Termin nach Outlook, dort stimmt er). Zeilen auf Mitternacht bleiben, wie sie sind: so legt sie der Dialog an.

downgrade(): nichts. Der Vorzustand war der Fehler; die alte Fassung liest die neue Form ohne Weiteres. Keine Spalte ändert sich.

Revision ID: 4f7a1c9e2b60
Revises: b2c7f4e19a06
Create Date: 2026-10-31

"""
from datetime import datetime, time, timedelta

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f7a1c9e2b60'
down_revision = 'b2c7f4e19a06'
branch_labels = None
depends_on = None

_TERMINE = sa.table("calendar_events", sa.column("id", sa.Integer), sa.column("start_at", sa.DateTime), sa.column("end_at", sa.DateTime), sa.column("all_day", sa.Boolean))
_AUS_UTC = {time(1, 0), time(2, 0)}  # Mitternacht UTC, nach Berlin umgerechnet: Winter, Sommer
_MITTERNACHT = time(0, 0)


def reparieren(bind) -> int:
    anzahl = 0
    for kennung, beginn, ende in bind.execute(sa.select(_TERMINE.c.id, _TERMINE.c.start_at, _TERMINE.c.end_at).where(_TERMINE.c.all_day.is_(True))).all():
        if beginn.time() == _MITTERNACHT and ende.time() == _MITTERNACHT:
            continue
        letzter = ende.date() - timedelta(days=1) if beginn.time() in _AUS_UTC and ende.time() in _AUS_UTC else ende.date()
        letzter = max(beginn.date(), letzter)
        bind.execute(_TERMINE.update().where(_TERMINE.c.id == kennung).values(start_at=datetime.combine(beginn.date(), _MITTERNACHT), end_at=datetime.combine(letzter, _MITTERNACHT)))
        anzahl += 1
    return anzahl


def upgrade() -> None:
    reparieren(op.get_bind())


def downgrade() -> None:
    pass
