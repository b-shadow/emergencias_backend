import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoServicio
from app.models.base import Base


class Servicio(Base):
    __tablename__ = "servicio"

    id_servicio: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_servicio: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    estado: Mapped[EstadoServicio] = mapped_column(Enum(EstadoServicio, name="service_status"), nullable=False)

    talleres = relationship("TallerServicio", back_populates="servicio")
