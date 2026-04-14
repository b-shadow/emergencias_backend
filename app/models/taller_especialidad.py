import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoTallerEspecialidad
from app.models.base import Base


class TallerEspecialidad(Base):
    __tablename__ = "taller_especialidad"
    __table_args__ = (UniqueConstraint("id_taller", "id_especialidad", name="uq_taller_especialidad"),)

    id_taller_especialidad: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False)
    id_especialidad: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("especialidad.id_especialidad"), nullable=False)
    estado: Mapped[EstadoTallerEspecialidad] = mapped_column(Enum(EstadoTallerEspecialidad, name="estado_taller_especialidad"), nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    taller = relationship("Taller", back_populates="especialidades")
    especialidad = relationship("Especialidad", back_populates="talleres")
