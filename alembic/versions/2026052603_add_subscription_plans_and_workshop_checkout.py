"""Add subscription plans and workshop checkout flow tables

Revision ID: 2026052603
Revises: 2026052602
Create Date: 2026-05-26 13:10:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026052603"
down_revision = "2026052602"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plan",
        sa.Column("id_plan", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("codigo_plan", sa.String(length=80), nullable=False),
        sa.Column("nombre_plan", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("precio_mensual_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=120), nullable=True),
        sa.Column("es_activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id_plan"),
        sa.UniqueConstraint("codigo_plan", name="uq_subscription_plan_codigo_plan"),
    )
    op.create_index("ix_subscription_plan_codigo_plan", "subscription_plan", ["codigo_plan"], unique=True)

    op.create_table(
        "workshop_checkout",
        sa.Column("id_checkout", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_plan", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkout_token", sa.String(length=120), nullable=False),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=True),
        sa.Column("estado_checkout", sa.String(length=40), nullable=False, server_default="PENDIENTE"),
        sa.Column("correo_taller", sa.String(length=255), nullable=False),
        sa.Column("registro_payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("id_usuario_creado", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id_taller_creado", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_validacion", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_plan"], ["subscription_plan.id_plan"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id_checkout"),
        sa.UniqueConstraint("checkout_token", name="uq_workshop_checkout_token"),
        sa.UniqueConstraint("stripe_session_id", name="uq_workshop_checkout_stripe_session_id"),
    )
    op.create_index("ix_workshop_checkout_checkout_token", "workshop_checkout", ["checkout_token"], unique=True)
    op.create_index("ix_workshop_checkout_stripe_session_id", "workshop_checkout", ["stripe_session_id"], unique=True)
    op.create_index("ix_workshop_checkout_id_plan", "workshop_checkout", ["id_plan"], unique=False)
    op.create_index("ix_workshop_checkout_correo_taller", "workshop_checkout", ["correo_taller"], unique=False)

    # Seed de planes iniciales (sin stripe_price_id para configurar luego en entorno)
    plans = [
        (
            uuid.uuid4(),
            "BASICO",
            "Plan Básico",
            "Ideal para talleres pequeños con atención estándar.",
            19.99,
            None,
        ),
        (
            uuid.uuid4(),
            "PRO",
            "Plan Pro",
            "Incluye mayor visibilidad, métricas avanzadas y prioridad operativa.",
            49.99,
            None,
        ),
        (
            uuid.uuid4(),
            "EMPRESARIAL",
            "Plan Empresarial",
            "Pensado para redes de talleres con operación intensiva multi-sede.",
            99.99,
            None,
        ),
    ]
    op.bulk_insert(
        sa.table(
            "subscription_plan",
            sa.column("id_plan", postgresql.UUID(as_uuid=True)),
            sa.column("codigo_plan", sa.String),
            sa.column("nombre_plan", sa.String),
            sa.column("descripcion", sa.Text),
            sa.column("precio_mensual_usd", sa.Numeric),
            sa.column("stripe_price_id", sa.String),
        ),
        [
            {
                "id_plan": p[0],
                "codigo_plan": p[1],
                "nombre_plan": p[2],
                "descripcion": p[3],
                "precio_mensual_usd": p[4],
                "stripe_price_id": p[5],
            }
            for p in plans
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_workshop_checkout_correo_taller", table_name="workshop_checkout")
    op.drop_index("ix_workshop_checkout_id_plan", table_name="workshop_checkout")
    op.drop_index("ix_workshop_checkout_stripe_session_id", table_name="workshop_checkout")
    op.drop_index("ix_workshop_checkout_checkout_token", table_name="workshop_checkout")
    op.drop_table("workshop_checkout")

    op.drop_index("ix_subscription_plan_codigo_plan", table_name="subscription_plan")
    op.drop_table("subscription_plan")

