"""Create tables for sollicitud-especialidad and solicitud-servicio many-to-many relationships

Revision ID: 2026041101
Revises: 92c3fa671428
Create Date: 2026-04-11 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026041101'
down_revision = '92c3fa671428'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear tabla especialidad_solicitud_emergencia (relación N:N)
    op.create_table(
        'especialidad_solicitud_emergencia',
        sa.Column('id_relacion', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id_solicitud', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id_especialidad', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fecha_agregada', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['id_solicitud'], ['solicitud_emergencia.id_solicitud'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['id_especialidad'], ['especialidad.id_especialidad'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id_relacion')
    )
    op.create_index(
        'ix_especialidad_solicitud_emergencia_id_solicitud',
        'especialidad_solicitud_emergencia',
        ['id_solicitud']
    )
    op.create_index(
        'ix_especialidad_solicitud_emergencia_id_especialidad',
        'especialidad_solicitud_emergencia',
        ['id_especialidad']
    )

    # Crear tabla servicio_solicitud_emergencia (relación N:N)
    op.create_table(
        'servicio_solicitud_emergencia',
        sa.Column('id_relacion', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id_solicitud', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id_servicio', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fecha_agregada', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['id_solicitud'], ['solicitud_emergencia.id_solicitud'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['id_servicio'], ['servicio.id_servicio'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id_relacion')
    )
    op.create_index(
        'ix_servicio_solicitud_emergencia_id_solicitud',
        'servicio_solicitud_emergencia',
        ['id_solicitud']
    )
    op.create_index(
        'ix_servicio_solicitud_emergencia_id_servicio',
        'servicio_solicitud_emergencia',
        ['id_servicio']
    )


def downgrade() -> None:
    # Eliminar tablas en orden inverso
    op.drop_index(
        'ix_servicio_solicitud_emergencia_id_servicio',
        table_name='servicio_solicitud_emergencia'
    )
    op.drop_index(
        'ix_servicio_solicitud_emergencia_id_solicitud',
        table_name='servicio_solicitud_emergencia'
    )
    op.drop_table('servicio_solicitud_emergencia')

    op.drop_index(
        'ix_especialidad_solicitud_emergencia_id_especialidad',
        table_name='especialidad_solicitud_emergencia'
    )
    op.drop_index(
        'ix_especialidad_solicitud_emergencia_id_solicitud',
        table_name='especialidad_solicitud_emergencia'
    )
    op.drop_table('especialidad_solicitud_emergencia')
