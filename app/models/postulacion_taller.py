import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoPostulacion
from app.models.base import Base


class PostulacionTaller(Base):
    __tablename__ = "postulacion_taller"

    id_postulacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False)
    tiempo_estimado_llegada_min: Mapped[int | None] = mapped_column(nullable=True)
    mensaje_propuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_postulacion: Mapped[EstadoPostulacion] = mapped_column(Enum(EstadoPostulacion, name="estado_postulacion"), nullable=False)
    fecha_postulacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_respuesta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    solicitud = relationship("SolicitudEmergencia", back_populates="postulaciones")
    taller = relationship("Taller", back_populates="postulaciones")
    asignacion = relationship("AsignacionAtencion", back_populates="postulacion", uselist=False)
