import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoAprobacionTaller, EstadoOperativoTaller
from app.models.base import Base


class Taller(Base):
    __tablename__ = "taller"

    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), unique=True, nullable=False)
    nombre_taller: Mapped[str] = mapped_column(String(255), nullable=False)
    razon_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nit: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitud: Mapped[float | None] = mapped_column(nullable=True)
    longitud: Mapped[float | None] = mapped_column(nullable=True)
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    estado_aprobacion: Mapped[EstadoAprobacionTaller] = mapped_column(Enum(EstadoAprobacionTaller, name="estado_aprobacion_taller"), nullable=False)
    estado_operativo: Mapped[EstadoOperativoTaller] = mapped_column(Enum(EstadoOperativoTaller, name="estado_operativo_taller"), nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_aprobacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario = relationship("Usuario", back_populates="taller")
    especialidades = relationship("TallerEspecialidad", back_populates="taller", cascade="all, delete-orphan")
    servicios = relationship("TallerServicio", back_populates="taller", cascade="all, delete-orphan")
    postulaciones = relationship("PostulacionTaller", back_populates="taller")
    asignaciones = relationship("AsignacionAtencion", back_populates="taller")
