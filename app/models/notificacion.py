import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TipoNotificacion, CategoriaNotificacion, EstadoLecturaNotificacion, EstadoEnvioNotificacion
from app.models.base import Base


class Notificacion(Base):
    __tablename__ = "notificacion"

    id_notificacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_usuario_destino: Mapped[str] = mapped_column(String(50), nullable=False)  # cliente, taller, administrador
    id_usuario_destino: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_notificacion: Mapped[TipoNotificacion] = mapped_column(Enum(TipoNotificacion, name="notification_type"), nullable=False)
    categoria_evento: Mapped[CategoriaNotificacion] = mapped_column(Enum(CategoriaNotificacion, name="notification_category"), nullable=False)
    referencia_entidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    estado_lectura: Mapped[EstadoLecturaNotificacion] = mapped_column(Enum(EstadoLecturaNotificacion, name="notification_read_status"), nullable=False)
    estado_envio: Mapped[EstadoEnvioNotificacion] = mapped_column(Enum(EstadoEnvioNotificacion, name="notification_send_status"), nullable=False)
    fecha_envio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_lectura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario = relationship("Usuario", back_populates="notificaciones")
