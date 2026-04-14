import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClasificacionIncidente(Base):
    __tablename__ = "clasificacion_incidente"

    id_clasificacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    categoria_predicha: Mapped[str] = mapped_column(String(255), nullable=False)
    subcategoria_predicha: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_especialidad_requerida: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("especialidad.id_especialidad"), nullable=True)
    id_servicio_sugerido: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("servicio.id_servicio"), nullable=True)
    nivel_urgencia_predicho: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confianza_modelo: Mapped[float | None] = mapped_column(nullable=True)
    modelo_utilizado: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fuente_entrada: Mapped[str] = mapped_column(String(50), nullable=False)
    resultado_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_procesamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    solicitud = relationship("SolicitudEmergencia", back_populates="clasificaciones")
