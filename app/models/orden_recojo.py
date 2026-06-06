import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoOrdenRecojo
from app.models.base import Base


class OrdenRecojo(Base):
    __tablename__ = "orden_recojo"

    id_orden_recojo: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_asignacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asignacion_atencion.id_asignacion"), nullable=False, unique=True, index=True)
    id_trabajador: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trabajador.id_trabajador"), nullable=False, index=True)
    estado_orden: Mapped[EstadoOrdenRecojo] = mapped_column(Enum(EstadoOrdenRecojo, name="estado_orden_recojo"), nullable=False, default=EstadoOrdenRecojo.PENDIENTE_ACEPTACION)
    distancia_metros: Mapped[float | None] = mapped_column(nullable=True)
    duracion_segundos: Mapped[float | None] = mapped_column(nullable=True)
    ruta_geojson: Mapped[str | None] = mapped_column(String, nullable=True)
    ruta_recorrida_geojson: Mapped[str | None] = mapped_column(String, nullable=True)
    latitud_destino: Mapped[float | None] = mapped_column(nullable=True)
    longitud_destino: Mapped[float | None] = mapped_column(nullable=True)
    latitud_actual: Mapped[float | None] = mapped_column(nullable=True)
    longitud_actual: Mapped[float | None] = mapped_column(nullable=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_aceptacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_llegada_auxilio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_inicio_regreso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_llegada_taller: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_ultima_ubicacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duracion_total_segundos: Mapped[float | None] = mapped_column(nullable=True)

    asignacion = relationship("AsignacionAtencion", back_populates="orden_recojo")
    trabajador = relationship("Trabajador", back_populates="ordenes_recojo")
