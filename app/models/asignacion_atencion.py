import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoAsignacion
from app.models.base import Base


class AsignacionAtencion(Base):
    __tablename__ = "asignacion_atencion"

    id_asignacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False)
    id_postulacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("postulacion_taller.id_postulacion"), nullable=False)
    estado_asignacion: Mapped[EstadoAsignacion] = mapped_column(Enum(EstadoAsignacion, name="estado_asignacion"), nullable=False)
    fecha_asignacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_inicio_atencion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_fin_atencion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(500), nullable=True)

    solicitud = relationship("SolicitudEmergencia", back_populates="asignaciones")
    taller = relationship("Taller", back_populates="asignaciones")
    postulacion = relationship("PostulacionTaller", back_populates="asignacion")
    resultados = relationship("ResultadoServicio", back_populates="asignacion", cascade="all, delete-orphan")
