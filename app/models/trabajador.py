import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Trabajador(Base):
    __tablename__ = "trabajador"

    id_trabajador: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), unique=True, nullable=False)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False, index=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    licencia_conducir: Mapped[str | None] = mapped_column(String(80), nullable=True)
    es_activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="trabajador")
    taller = relationship("Taller", back_populates="trabajadores")
    ordenes_recojo = relationship("OrdenRecojo", back_populates="trabajador")
