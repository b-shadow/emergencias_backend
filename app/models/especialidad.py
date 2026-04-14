import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoEspecialidad
from app.models.base import Base


class Especialidad(Base):
    __tablename__ = "especialidad"

    id_especialidad: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_especialidad: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    estado: Mapped[EstadoEspecialidad] = mapped_column(Enum(EstadoEspecialidad, name="estado_especialidad"), nullable=False)

    talleres = relationship("TallerEspecialidad", back_populates="especialidad")
