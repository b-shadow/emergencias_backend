import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoSolicitud, NivelUrgencia
from app.models.base import Base


class SolicitudEmergencia(Base):
    __tablename__ = "solicitud_emergencia"

    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_cliente: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cliente.id_cliente"), nullable=False)
    id_vehiculo: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehiculo.id_vehiculo"), nullable=True)
    codigo_solicitud: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    descripcion_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    descripcion_audio_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    transcripcion_audio: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitud: Mapped[float | None] = mapped_column(nullable=True)
    longitud: Mapped[float | None] = mapped_column(nullable=True)
    direccion_referencial: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estado_actual: Mapped[EstadoSolicitud] = mapped_column(Enum(EstadoSolicitud, name="estado_solicitud"), nullable=False)
    nivel_urgencia: Mapped[NivelUrgencia] = mapped_column(Enum(NivelUrgencia, name="nivel_urgencia"), nullable=False)
    categoria_incidente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    radio_busqueda_km: Mapped[float] = mapped_column(nullable=False, default=5.0)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cliente = relationship("Cliente", back_populates="solicitudes")
    vehiculo = relationship("Vehiculo", foreign_keys=[id_vehiculo])
    evidencias = relationship("Evidencia", back_populates="solicitud", cascade="all, delete-orphan")
    clasificaciones = relationship("ClasificacionIncidente", back_populates="solicitud", cascade="all, delete-orphan")
    postulaciones = relationship("PostulacionTaller", back_populates="solicitud", cascade="all, delete-orphan")
    asignaciones = relationship("AsignacionAtencion", back_populates="solicitud", cascade="all, delete-orphan")
    historial_estado = relationship("HistorialEstadoSolicitud", back_populates="solicitud", cascade="all, delete-orphan")
    resultados = relationship("ResultadoServicio", back_populates="solicitud", cascade="all, delete-orphan")
    especialidades = relationship("EspecialidadSolicitudEmergencia", back_populates="solicitud", cascade="all, delete-orphan")
    servicios = relationship("ServicioSolicitudEmergencia", back_populates="solicitud", cascade="all, delete-orphan")


# ==================== Tablas de Relación Many-to-Many ====================

class EspecialidadSolicitudEmergencia(Base):
    """Tabla puente: Solicitud Emergencia ←→ Especialidad (N:N)"""
    __tablename__ = "especialidad_solicitud_emergencia"

    id_relacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("solicitud_emergencia.id_solicitud", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    id_especialidad: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("especialidad.id_especialidad", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    fecha_agregada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    solicitud = relationship("SolicitudEmergencia", back_populates="especialidades")
    especialidad = relationship("Especialidad")


class ServicioSolicitudEmergencia(Base):
    """Tabla puente: Solicitud Emergencia ←→ Servicio (N:N)"""
    __tablename__ = "servicio_solicitud_emergencia"

    id_relacion: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("solicitud_emergencia.id_solicitud", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    id_servicio: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("servicio.id_servicio", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    fecha_agregada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    solicitud = relationship("SolicitudEmergencia", back_populates="servicios")
    servicio = relationship("Servicio")
