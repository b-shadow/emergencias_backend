import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoCotizacion
from app.models.base import Base


class CotizacionAtencion(Base):
    __tablename__ = "cotizacion_atencion"

    id_cotizacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_postulacion: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("postulacion_taller.id_postulacion"),
        nullable=False,
        unique=True,
    )
    id_taller_servicio: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("taller_servicio.id_taller_servicio"),
        nullable=False,
    )
    precio_servicio: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    precio_total_estimado: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    estado_cotizacion: Mapped[EstadoCotizacion] = mapped_column(
        Enum(EstadoCotizacion, name="estado_cotizacion"),
        nullable=False,
        default=EstadoCotizacion.PENDIENTE,
    )
    tipo_pintura: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_respuesta_cliente: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    postulacion = relationship("PostulacionTaller", back_populates="cotizacion")
    taller_servicio = relationship("TallerServicio")
