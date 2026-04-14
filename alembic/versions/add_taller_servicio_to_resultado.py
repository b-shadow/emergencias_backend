"""Add id_taller_servicio to resultado_servicio

Revision ID: add_taller_servicio_to_resultado
Revises: 92c3fa671428
Create Date: 2026-04-12 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_taller_servicio_to_resultado'
down_revision = '92c3fa671428'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna id_taller_servicio a resultado_servicio
    op.add_column('resultado_servicio',
        sa.Column('id_taller_servicio', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Agregar foreign key constraint
    op.create_foreign_key(
        'fk_resultado_servicio_taller_servicio',
        'resultado_servicio',
        'taller_servicio',
        ['id_taller_servicio'],
        ['id_taller_servicio']
    )


def downgrade():
    # Remover foreign key
    op.drop_constraint('fk_resultado_servicio_taller_servicio', 'resultado_servicio')
    
    # Remover columna
    op.drop_column('resultado_servicio', 'id_taller_servicio')
