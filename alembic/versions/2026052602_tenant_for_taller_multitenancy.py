"""Add tenant_taller and link talleres to tenant

Revision ID: 2026052602
Revises: 2026052601
Create Date: 2026-05-26 10:15:00
"""

from __future__ import annotations

import re
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2026052602"
down_revision = "2026052601"
branch_labels = None
depends_on = None


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return base or "taller"


def upgrade() -> None:
    op.create_table(
        "tenant_taller",
        sa.Column("id_tenant", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre_tenant", sa.String(length=255), nullable=False),
        sa.Column("slug_tenant", sa.String(length=120), nullable=False),
        sa.Column("es_activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id_tenant"),
    )
    op.create_index("ix_tenant_taller_slug_tenant", "tenant_taller", ["slug_tenant"], unique=True)

    op.add_column("taller", sa.Column("id_tenant", postgresql.UUID(as_uuid=True), nullable=True))

    bind = op.get_bind()
    talleres = bind.execute(sa.text("SELECT id_taller, nombre_taller FROM taller")).fetchall()

    used_slugs: set[str] = set()
    for row in talleres:
        id_taller = row[0]
        nombre_taller = row[1] or "Taller"
        base_slug = _slugify(nombre_taller)
        slug = base_slug
        counter = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        used_slugs.add(slug)
        id_tenant = uuid.uuid4()

        bind.execute(
            sa.text(
                """
                INSERT INTO tenant_taller (id_tenant, nombre_tenant, slug_tenant, es_activo)
                VALUES (:id_tenant, :nombre_tenant, :slug_tenant, true)
                """
            ),
            {"id_tenant": id_tenant, "nombre_tenant": nombre_taller, "slug_tenant": slug},
        )
        bind.execute(
            sa.text("UPDATE taller SET id_tenant = :id_tenant WHERE id_taller = :id_taller"),
            {"id_tenant": id_tenant, "id_taller": id_taller},
        )

    op.alter_column("taller", "id_tenant", nullable=False)
    op.create_index("ix_taller_id_tenant", "taller", ["id_tenant"], unique=False)
    op.create_foreign_key("fk_taller_id_tenant", "taller", "tenant_taller", ["id_tenant"], ["id_tenant"])


def downgrade() -> None:
    op.drop_constraint("fk_taller_id_tenant", "taller", type_="foreignkey")
    op.drop_index("ix_taller_id_tenant", table_name="taller")
    op.drop_column("taller", "id_tenant")
    op.drop_index("ix_tenant_taller_slug_tenant", table_name="tenant_taller")
    op.drop_table("tenant_taller")
