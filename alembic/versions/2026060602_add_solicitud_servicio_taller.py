"""Add workshop service requests

Revision ID: 2026060602_add_solicitud_servicio_taller
Revises: 2026060601_remove_ida_and_fixed_cancellation
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026060602_add_solicitud_servicio_taller"
down_revision = "2026060601_remove_ida_and_fixed_cancellation"
branch_labels = None
depends_on = None


estado_solicitud_servicio = sa.Enum("EN_ESPERA", "APROBADO", "RECHAZADO", name="estado_solicitud_servicio")


def upgrade() -> None:
    bind = op.get_bind()
    estado_solicitud_servicio.create(bind, checkfirst=True)

    op.create_table(
        "solicitud_servicio_taller",
        sa.Column("id_solicitud_servicio_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre_servicio", sa.String(length=255), nullable=False),
        sa.Column("descripcion", sa.String(length=1000), nullable=True),
        sa.Column("estado", estado_solicitud_servicio, nullable=False, server_default="EN_ESPERA"),
        sa.Column("motivo_rechazo", sa.String(length=1000), nullable=True),
        sa.Column("id_servicio_creado", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id_usuario_solicitante", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_usuario_resolutor", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fecha_solicitud", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fecha_resolucion", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.ForeignKeyConstraint(["id_servicio_creado"], ["servicio.id_servicio"]),
        sa.ForeignKeyConstraint(["id_usuario_solicitante"], ["usuario.id_usuario"]),
        sa.ForeignKeyConstraint(["id_usuario_resolutor"], ["usuario.id_usuario"]),
        sa.PrimaryKeyConstraint("id_solicitud_servicio_taller"),
    )
    op.create_index(
        "ix_solicitud_servicio_taller_id_taller",
        "solicitud_servicio_taller",
        ["id_taller"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_solicitud_servicio_taller_id_taller", table_name="solicitud_servicio_taller")
    op.drop_table("solicitud_servicio_taller")
    bind = op.get_bind()
    estado_solicitud_servicio.drop(bind, checkfirst=True)
