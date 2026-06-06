"""Add BS price/duration to subscription_plan and create taller_subscription

Revision ID: 2026052701
Revises: 2026052603
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "2026052701"
down_revision = "2026052603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_plan",
        sa.Column("precio_bs", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "subscription_plan",
        sa.Column("duracion_dias", sa.Integer(), nullable=False, server_default="30"),
    )

    op.create_table(
        "taller_subscription",
        sa.Column("id_subscription", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_plan", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False, server_default="ACTIVA"),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["id_plan"], ["subscription_plan.id_plan"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_subscription"),
    )
    op.create_index("ix_taller_subscription_id_taller", "taller_subscription", ["id_taller"], unique=False)
    op.create_index("ix_taller_subscription_id_plan", "taller_subscription", ["id_plan"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_taller_subscription_id_plan", table_name="taller_subscription")
    op.drop_index("ix_taller_subscription_id_taller", table_name="taller_subscription")
    op.drop_table("taller_subscription")
    op.drop_column("subscription_plan", "duracion_dias")
    op.drop_column("subscription_plan", "precio_bs")
