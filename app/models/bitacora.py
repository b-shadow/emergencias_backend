import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TipoActor, ResultadoAuditoria
from app.models.base import Base


class Bitacora(Base):
    __tablename__ = "bitacora"

    id_bitacora: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_actor: Mapped[TipoActor] = mapped_column(Enum(TipoActor, name="tipo_actor"), nullable=False)
    id_actor: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    accion: Mapped[str] = mapped_column(String(255), nullable=False)
    modulo: Mapped[str] = mapped_column(String(100), nullable=False)
    entidad_afectada: Mapped[str] = mapped_column(String(100), nullable=False)
    id_entidad_afectada: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resultado: Mapped[ResultadoAuditoria] = mapped_column(Enum(ResultadoAuditoria, name="resultado_auditoria"), nullable=False)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_origen: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fecha_evento: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
