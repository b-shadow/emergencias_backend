"""Remove ida pricing and fixed cancellation policy

Revision ID: 2026060601_remove_ida_and_fixed_cancellation
Revises: 2026060301_full_tracking
Create Date: 2026-06-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2026060601_remove_ida_and_fixed_cancellation"
down_revision = "2026060301_full_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("cargo_cancelacion_solicitud")
    op.drop_table("politica_cancelacion_taller")
    op.drop_column("cotizacion_atencion", "costo_ida")
    op.drop_column("taller_servicio", "precio_ida_minimo")


def downgrade() -> None:
    op.add_column(
        "taller_servicio",
        sa.Column("precio_ida_minimo", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "cotizacion_atencion",
        sa.Column("costo_ida", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )

    op.create_table(
        "politica_cancelacion_taller",
        sa.Column("id_politica", sa.UUID(), nullable=False),
        sa.Column("id_taller", sa.UUID(), nullable=False),
        sa.Column("monto_penalidad", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.PrimaryKeyConstraint("id_politica"),
        sa.UniqueConstraint("id_taller", name="uq_politica_cancelacion_taller_id_taller"),
    )
    op.create_index(
        "ix_politica_cancelacion_taller_id_taller",
        "politica_cancelacion_taller",
        ["id_taller"],
        unique=True,
    )

    op.create_table(
        "cargo_cancelacion_solicitud",
        sa.Column("id_cargo", sa.UUID(), nullable=False),
        sa.Column("id_solicitud", sa.UUID(), nullable=False),
        sa.Column("id_taller", sa.UUID(), nullable=False),
        sa.Column("monto_cargo", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["id_solicitud"], ["solicitud_emergencia.id_solicitud"]),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.PrimaryKeyConstraint("id_cargo"),
        sa.UniqueConstraint("id_solicitud", name="uq_cargo_cancelacion_solicitud_id_solicitud"),
    )
    op.create_index(
        "ix_cargo_cancelacion_solicitud_id_solicitud",
        "cargo_cancelacion_solicitud",
        ["id_solicitud"],
        unique=True,
    )
    op.create_index(
        "ix_cargo_cancelacion_solicitud_id_taller",
        "cargo_cancelacion_solicitud",
        ["id_taller"],
        unique=False,
    )

