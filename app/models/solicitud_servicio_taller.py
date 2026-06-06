import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoSolicitudServicio
from app.models.base import Base


class SolicitudServicioTaller(Base):
    __tablename__ = "solicitud_servicio_taller"

    id_solicitud_servicio_taller: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    id_taller: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False, index=True
    )
    nombre_servicio: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    estado: Mapped[EstadoSolicitudServicio] = mapped_column(
        Enum(EstadoSolicitudServicio, name="estado_solicitud_servicio"),
        nullable=False,
        default=EstadoSolicitudServicio.EN_ESPERA,
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    id_servicio_creado: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servicio.id_servicio"), nullable=True
    )
    id_usuario_solicitante: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), nullable=False
    )
    id_usuario_resolutor: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), nullable=True
    )
    fecha_solicitud: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fecha_resolucion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    taller = relationship("Taller", back_populates="solicitudes_servicio")
    servicio_creado = relationship("Servicio", back_populates="solicitudes")
    solicitante = relationship("Usuario", foreign_keys=[id_usuario_solicitante])
    resolutor = relationship("Usuario", foreign_keys=[id_usuario_resolutor])
