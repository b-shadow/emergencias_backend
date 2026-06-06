import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CalificacionAtencion(Base):
    __tablename__ = "calificacion_atencion"

    id_calificacion_atencion: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    id_asignacion: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asignacion_atencion.id_asignacion"), nullable=False, unique=True, index=True
    )
    id_solicitud: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False, index=True
    )
    id_cliente: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cliente.id_cliente"), nullable=False, index=True
    )
    id_taller: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False, index=True
    )
    estrellas: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmo_estado: Mapped[bool] = mapped_column(nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    asignacion = relationship("AsignacionAtencion", back_populates="calificacion")
    solicitud = relationship("SolicitudEmergencia")
    cliente = relationship("Cliente")
    taller = relationship("Taller")
