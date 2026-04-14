import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OrigenEvidencia, TipoEvidencia
from app.models.base import Base


class Evidencia(Base):
    __tablename__ = "evidencia"

    id_evidencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False)
    tipo_evidencia: Mapped[TipoEvidencia] = mapped_column(Enum(TipoEvidencia, name="evidence_type"), nullable=False)
    url_archivo: Mapped[str] = mapped_column(String(1000), nullable=False)
    nombre_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamano_bytes: Mapped[int | None] = mapped_column(nullable=True)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    origen: Mapped[OrigenEvidencia] = mapped_column(Enum(OrigenEvidencia, name="evidence_origin"), nullable=False)
    fecha_subida: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    solicitud = relationship("SolicitudEmergencia", back_populates="evidencias")
