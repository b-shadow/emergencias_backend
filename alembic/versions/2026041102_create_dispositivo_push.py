"""Create dispositivo_push table and plataforma_push enum

Revision ID: 2026041102
Revises: 2026041101
Create Date: 2026-04-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError

# revision identifiers, used by Alembic.
revision = '2026041102'
down_revision = '2026041101'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear enum plataforma_push (si no existe)
    try:
        op.execute("CREATE TYPE plataforma_push AS ENUM ('WEB', 'ANDROID', 'IOS')")
    except ProgrammingError:
        # El tipo ya existe, continuamos
        pass

    # Crear tabla dispositivo_push
    op.create_table(
        'dispositivo_push',
        sa.Column('id_dispositivo_push', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('id_usuario', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('plataforma', postgresql.ENUM('WEB', 'ANDROID', 'IOS', name='plataforma_push', create_type=False), nullable=False),
        sa.Column('token_fcm', sa.String(500), nullable=False, index=True),
        sa.Column('device_id', sa.String(255), nullable=True),
        sa.Column('nombre_dispositivo', sa.String(255), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('ultima_vez_usado', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_registro', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('fecha_actualizacion', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['id_usuario'], ['usuario.id_usuario'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id_dispositivo_push')
    )

    # Crear índices
    op.create_index(
        'ix_dispositivo_push_usuario_activo',
        'dispositivo_push',
        ['id_usuario', 'activo']
    )
    op.create_index(
        'ix_dispositivo_push_token_activo',
        'dispositivo_push',
        ['token_fcm', 'activo']
    )


def downgrade() -> None:
    # Eliminar índices
    op.drop_index('ix_dispositivo_push_token_activo', table_name='dispositivo_push')
    op.drop_index('ix_dispositivo_push_usuario_activo', table_name='dispositivo_push')

    # Eliminar tabla
    op.drop_table('dispositivo_push')

    # Eliminar enum
    plataforma_push = postgresql.ENUM('WEB', 'ANDROID', 'IOS', name='plataforma_push')
    plataforma_push.drop(op.get_bind(), checkfirst=True)
