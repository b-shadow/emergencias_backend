"""Add trabajador role, trabajador table and orden_recojo tracking

Revision ID: 2026052501
Revises: add_taller_servicio_to_resultado
Create Date: 2026-05-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026052501"
down_revision = "add_taller_servicio_to_resultado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE rol_usuario ADD VALUE IF NOT EXISTS 'TRABAJADOR'")
    op.execute("ALTER TYPE tipo_actor ADD VALUE IF NOT EXISTS 'TRABAJADOR'")
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE estado_orden_recojo AS ENUM
            ('PENDIENTE_ACEPTACION','ACEPTADA','EN_CAMINO_RECOJO','VEHICULO_RECOGIDO','CANCELADA');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )

    op.create_table(
        "trabajador",
        sa.Column("id_trabajador", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_usuario", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("licencia_conducir", sa.String(length=80), nullable=True),
        sa.Column("es_activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["id_taller"], ["taller.id_taller"]),
        sa.ForeignKeyConstraint(["id_usuario"], ["usuario.id_usuario"]),
        sa.PrimaryKeyConstraint("id_trabajador"),
        sa.UniqueConstraint("id_usuario"),
    )
    op.create_index("ix_trabajador_id_taller", "trabajador", ["id_taller"])

    op.create_table(
        "orden_recojo",
        sa.Column("id_orden_recojo", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_asignacion", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_trabajador", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "estado_orden",
            postgresql.ENUM(
                "PENDIENTE_ACEPTACION",
                "ACEPTADA",
                "EN_CAMINO_RECOJO",
                "VEHICULO_RECOGIDO",
                "CANCELADA",
                name="estado_orden_recojo",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("distancia_metros", sa.Float(), nullable=True),
        sa.Column("duracion_segundos", sa.Float(), nullable=True),
        sa.Column("ruta_geojson", sa.String(), nullable=True),
        sa.Column("latitud_actual", sa.Float(), nullable=True),
        sa.Column("longitud_actual", sa.Float(), nullable=True),
        sa.Column("fecha_asignacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_aceptacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_ultima_ubicacion", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_asignacion"], ["asignacion_atencion.id_asignacion"]),
        sa.ForeignKeyConstraint(["id_trabajador"], ["trabajador.id_trabajador"]),
        sa.PrimaryKeyConstraint("id_orden_recojo"),
        sa.UniqueConstraint("id_asignacion"),
    )
    op.create_index("ix_orden_recojo_id_asignacion", "orden_recojo", ["id_asignacion"])
    op.create_index("ix_orden_recojo_id_trabajador", "orden_recojo", ["id_trabajador"])


def downgrade() -> None:
    op.drop_index("ix_orden_recojo_id_trabajador", table_name="orden_recojo")
    op.drop_index("ix_orden_recojo_id_asignacion", table_name="orden_recojo")
    op.drop_table("orden_recojo")

    op.drop_index("ix_trabajador_id_taller", table_name="trabajador")
    op.drop_table("trabajador")

    op.execute("DROP TYPE IF EXISTS estado_orden_recojo")
