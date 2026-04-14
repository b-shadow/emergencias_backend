import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PlataformaPush
from app.models.base import Base


class DispositivoPush(Base):
    __tablename__ = "dispositivo_push"

    id_dispositivo_push: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    id_usuario: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), nullable=False, index=True
    )
    plataforma: Mapped[PlataformaPush] = mapped_column(
        Enum(PlataformaPush, name="plataforma_push"), nullable=False
    )
    token_fcm: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nombre_dispositivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    ultima_vez_usado: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship
    usuario = relationship("Usuario", back_populates="dispositivos_push")

    # Índices
    __table_args__ = (
        Index("ix_dispositivo_push_usuario_activo", id_usuario, activo),
        Index("ix_dispositivo_push_token_activo", token_fcm, activo),
    )
