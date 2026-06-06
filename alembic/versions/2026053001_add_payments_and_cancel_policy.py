"""Add payments and cancellation policy tables

Revision ID: 2026053001_payments_cancel
Revises: 2026052701
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026053001_payments_cancel"
down_revision = "2026052701"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "politica_cancelacion_taller",
        sa.Column("id_politica", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monto_penalidad", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.PrimaryKeyConstraint("id_politica"),
        sa.UniqueConstraint("id_taller", name="uq_politica_cancelacion_taller_id_taller"),
    )
    op.create_index("ix_politica_cancelacion_taller_id_taller", "politica_cancelacion_taller", ["id_taller"], unique=True)

    op.create_table(
        "cargo_cancelacion_solicitud",
        sa.Column("id_cargo", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_solicitud", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monto_cargo", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["id_solicitud"], ["solicitud_emergencia.id_solicitud"]),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.PrimaryKeyConstraint("id_cargo"),
        sa.UniqueConstraint("id_solicitud", name="uq_cargo_cancelacion_solicitud_id_solicitud"),
    )
    op.create_index("ix_cargo_cancelacion_solicitud_id_solicitud", "cargo_cancelacion_solicitud", ["id_solicitud"], unique=True)
    op.create_index("ix_cargo_cancelacion_solicitud_id_taller", "cargo_cancelacion_solicitud", ["id_taller"], unique=False)

    op.create_table(
        "pago_atencion",
        sa.Column("id_pago", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_solicitud", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_usuario_registra", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("moneda", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("metodo_pago", sa.String(length=30), nullable=False),
        sa.Column("estado_pago", sa.String(length=30), nullable=False, server_default="PENDIENTE"),
        sa.Column("referencia_externa", sa.String(length=255), nullable=True),
        sa.Column("observacion", sa.String(length=1000), nullable=True),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fecha_confirmacion", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_solicitud"], ["solicitud_emergencia.id_solicitud"]),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.ForeignKeyConstraint(["id_usuario_registra"], ["usuario.id_usuario"]),
        sa.PrimaryKeyConstraint("id_pago"),
    )
    op.create_index("ix_pago_atencion_id_solicitud", "pago_atencion", ["id_solicitud"], unique=False)
    op.create_index("ix_pago_atencion_id_taller", "pago_atencion", ["id_taller"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pago_atencion_id_taller", table_name="pago_atencion")
    op.drop_index("ix_pago_atencion_id_solicitud", table_name="pago_atencion")
    op.drop_table("pago_atencion")

    op.drop_index("ix_cargo_cancelacion_solicitud_id_taller", table_name="cargo_cancelacion_solicitud")
    op.drop_index("ix_cargo_cancelacion_solicitud_id_solicitud", table_name="cargo_cancelacion_solicitud")
    op.drop_table("cargo_cancelacion_solicitud")

    op.drop_index("ix_politica_cancelacion_taller_id_taller", table_name="politica_cancelacion_taller")
    op.drop_table("politica_cancelacion_taller")
