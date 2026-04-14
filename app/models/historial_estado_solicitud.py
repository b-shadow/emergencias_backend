import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoSolicitud, TipoActor
from app.models.base import Base


class HistorialEstadoSolicitud(Base):
    __tablename__ = "historial_estado_solicitud"

    id_historial_estado: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    estado_anterior: Mapped[EstadoSolicitud | None] = mapped_column(Enum(EstadoSolicitud, name="request_status"), nullable=True)
    estado_nuevo: Mapped[EstadoSolicitud] = mapped_column(Enum(EstadoSolicitud, name="request_status"), nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    actualizado_por_tipo: Mapped[TipoActor] = mapped_column(Enum(TipoActor, name="actor_type"), nullable=False)
    actualizado_por_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fecha_cambio: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    solicitud = relationship("SolicitudEmergencia", back_populates="historial_estado")
