"""Tracking ida/vuelta with traveled path

Revision ID: 2026053101_tracking
Revises: 2026053001_payments_cancel
Create Date: 2026-05-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2026053101_tracking"
down_revision = "2026053001_payments_cancel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_orden_recojo ADD VALUE IF NOT EXISTS 'EN_CAMINO_TALLER'")
    op.add_column("orden_recojo", sa.Column("ruta_recorrida_geojson", sa.String(), nullable=True))
    op.add_column("orden_recojo", sa.Column("latitud_destino", sa.Float(), nullable=True))
    op.add_column("orden_recojo", sa.Column("longitud_destino", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("orden_recojo", "longitud_destino")
    op.drop_column("orden_recojo", "latitud_destino")
    op.drop_column("orden_recojo", "ruta_recorrida_geojson")
