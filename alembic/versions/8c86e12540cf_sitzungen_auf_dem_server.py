"""sitzungen_auf_dem_server -- Anmeldesitzungen auf dem Server (seit 1.8.98, app/sitzungen.py)

- user_sessions: je Anmeldung eine Zeile mit dem SHA-256 des Cookie-Werts (UNIQUE), fester Ablauf, zweiter Faktor je Sitzung.
  user_id mit ON DELETE CASCADE (die ORM-Beziehung AppUser.sessions löscht ebenfalls mit).

Ändert keine vorhandenen Daten. Die bis 1.8.97 ausgegebenen, zustandslosen Cookies gelten danach nicht mehr -- jede Person meldet sich
nach dem Einspielen einmal neu an.

downgrade(): löscht die Tabelle; danach gelten wieder nur zustandslose Cookies (der Code von 1.8.97), alle Sitzungen dieser Fassung
enden.

Revision ID: 8c86e12540cf
Revises: 7b3e9d1f5a26
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c86e12540cf'
down_revision = '7b3e9d1f5a26'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('second_factor_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_user_session_token_hash'),
    )
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_sessions_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_sessions_expires_at'))
    op.drop_table('user_sessions')
