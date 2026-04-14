import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TallerServicio(Base):
    __tablename__ = "taller_servicio"
    __table_args__ = (UniqueConstraint("id_taller", "id_servicio", name="uq_taller_servicio"),)

    id_taller_servicio: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False)
    id_servicio: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servicio.id_servicio"), nullable=False)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    taller = relationship("Taller", back_populates="servicios")
    servicio = relationship("Servicio", back_populates="talleres")
