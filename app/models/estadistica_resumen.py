import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PeriodoEstadistica, TipoEstadistica
from app.models.base import Base


class EstadisticaResumen(Base):
    __tablename__ = "estadistica_resumen"

    id_estadistica: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_estadistica: Mapped[TipoEstadistica] = mapped_column(Enum(TipoEstadistica, name="tipo_estadistica"), nullable=False)
    periodo: Mapped[PeriodoEstadistica] = mapped_column(Enum(PeriodoEstadistica, name="estadistica_periodo"), nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_taller: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=True)
    metrica: Mapped[str] = mapped_column(String(255), nullable=False)
    valor_numerico: Mapped[int | None] = mapped_column(nullable=True)
    valor_texto: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
