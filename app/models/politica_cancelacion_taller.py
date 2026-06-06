import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PoliticaCancelacionTaller(Base):
    __tablename__ = "politica_cancelacion_taller"

    id_politica: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False, unique=True, index=True)
    monto_penalidad: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    taller = relationship("Taller")
