import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoResultado
from app.models.base import Base


class ResultadoServicio(Base):
    __tablename__ = "resultado_servicio"

    id_resultado_servicio: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_asignacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asignacion_atencion.id_asignacion"), nullable=False)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    id_taller_servicio: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller_servicio.id_taller_servicio"), nullable=True)
    diagnostico: Mapped[str | None] = mapped_column(Text, nullable=True)
    solucion_aplicada: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_resultado: Mapped[EstadoResultado] = mapped_column(Enum(EstadoResultado, name="estado_resultado"), nullable=False)
    requiere_seguimiento: Mapped[bool] = mapped_column(nullable=False, default=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asignacion = relationship("AsignacionAtencion", back_populates="resultados")
    solicitud = relationship("SolicitudEmergencia", back_populates="resultados")
    taller_servicio = relationship("TallerServicio")
