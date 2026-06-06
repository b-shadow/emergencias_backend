"""Add customer rating for completed attention

Revision ID: 2026060603_add_calificacion_atencion
Revises: 2026060602_add_solicitud_servicio_taller
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026060603_add_calificacion_atencion"
down_revision = "2026060602_add_solicitud_servicio_taller"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calificacion_atencion",
        sa.Column("id_calificacion_atencion", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_asignacion", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_solicitud", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_cliente", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("estrellas", sa.Integer(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("confirmo_estado", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["id_asignacion"], ["asignacion_atencion.id_asignacion"]),
        sa.ForeignKeyConstraint(["id_solicitud"], ["solicitud_emergencia.id_solicitud"]),
        sa.ForeignKeyConstraint(["id_cliente"], ["cliente.id_cliente"]),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.PrimaryKeyConstraint("id_calificacion_atencion"),
        sa.UniqueConstraint("id_asignacion", name="uq_calificacion_atencion_id_asignacion"),
    )
    op.create_index("ix_calificacion_atencion_id_asignacion", "calificacion_atencion", ["id_asignacion"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_calificacion_atencion_id_asignacion", table_name="calificacion_atencion")
    op.drop_table("calificacion_atencion")
