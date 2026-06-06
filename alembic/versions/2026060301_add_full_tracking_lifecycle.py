"""add full tracking lifecycle

Revision ID: 2026060301_full_tracking
Revises: 2026053101_tracking
Create Date: 2026-06-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2026060301_full_tracking"
down_revision = "2026053101_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_orden_recojo ADD VALUE IF NOT EXISTS 'LLEGADA_AUXILIO'")
    op.execute("ALTER TYPE estado_orden_recojo ADD VALUE IF NOT EXISTS 'FINALIZADA'")
    op.add_column("orden_recojo", sa.Column("fecha_llegada_auxilio", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orden_recojo", sa.Column("fecha_inicio_regreso", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orden_recojo", sa.Column("fecha_llegada_taller", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orden_recojo", sa.Column("duracion_total_segundos", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("orden_recojo", "duracion_total_segundos")
    op.drop_column("orden_recojo", "fecha_llegada_taller")
    op.drop_column("orden_recojo", "fecha_inicio_regreso")
    op.drop_column("orden_recojo", "fecha_llegada_auxilio")
