import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Cliente(Base):
    __tablename__ = "cliente"

    id_cliente: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    apellido: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ci: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    direccion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    foto_perfil_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="cliente")
    vehiculos = relationship("Vehiculo", back_populates="cliente", cascade="all, delete-orphan")
    solicitudes = relationship("SolicitudEmergencia", back_populates="cliente")
