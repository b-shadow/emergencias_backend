"""Phase 2: quotes, tariffs and vehicle insurance

Revision ID: 2026052601
Revises: 2233056ec4e4
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026052601"
down_revision = "2233056ec4e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE categoria_tarifa_servicio AS ENUM ('MECANICO','ELECTRONICO','CHAPERIO');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE estado_cotizacion AS ENUM ('PENDIENTE','ACEPTADA_CLIENTE','RECHAZADA_CLIENTE','EXPIRADA');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE tipo_seguro_vehiculo AS ENUM ('SIN_SEGURO','BASICO','COMPLETO');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END$$;
        """
    )

    op.add_column(
        "vehiculo",
        sa.Column(
            "tipo_seguro",
            postgresql.ENUM("SIN_SEGURO", "BASICO", "COMPLETO", name="tipo_seguro_vehiculo", create_type=False),
            nullable=False,
            server_default="SIN_SEGURO",
        ),
    )
    op.add_column("vehiculo", sa.Column("aseguradora", sa.String(length=120), nullable=True))

    op.add_column(
        "taller_servicio",
        sa.Column(
            "categoria_tarifa",
            postgresql.ENUM("MECANICO", "ELECTRONICO", "CHAPERIO", name="categoria_tarifa_servicio", create_type=False),
            nullable=False,
            server_default="MECANICO",
        ),
    )
    op.add_column("taller_servicio", sa.Column("precio_base", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("taller_servicio", sa.Column("precio_ida_minimo", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("taller_servicio", sa.Column("tipo_pintura_chaperio", sa.String(length=120), nullable=True))

    op.create_table(
        "cotizacion_atencion",
        sa.Column("id_cotizacion", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_postulacion", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id_taller_servicio", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("precio_servicio", sa.Numeric(10, 2), nullable=False),
        sa.Column("costo_ida", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("precio_total_estimado", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "estado_cotizacion",
            postgresql.ENUM(
                "PENDIENTE",
                "ACEPTADA_CLIENTE",
                "RECHAZADA_CLIENTE",
                "EXPIRADA",
                name="estado_cotizacion",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDIENTE",
        ),
        sa.Column("tipo_pintura", sa.String(length=120), nullable=True),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_respuesta_cliente", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_postulacion"], ["postulacion_taller.id_postulacion"]),
        sa.ForeignKeyConstraint(["id_taller_servicio"], ["taller_servicio.id_taller_servicio"]),
        sa.PrimaryKeyConstraint("id_cotizacion"),
        sa.UniqueConstraint("id_postulacion"),
    )


def downgrade() -> None:
    op.drop_table("cotizacion_atencion")

    op.drop_column("taller_servicio", "tipo_pintura_chaperio")
    op.drop_column("taller_servicio", "precio_ida_minimo")
    op.drop_column("taller_servicio", "precio_base")
    op.drop_column("taller_servicio", "categoria_tarifa")

    op.drop_column("vehiculo", "aseguradora")
    op.drop_column("vehiculo", "tipo_seguro")
