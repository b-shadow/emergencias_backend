import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PagoAtencion(Base):
    __tablename__ = "pago_atencion"

    id_pago: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_solicitud: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("solicitud_emergencia.id_solicitud"), nullable=False, index=True)
    id_taller: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("taller.id_taller"), nullable=False, index=True)
    id_usuario_registra: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuario.id_usuario"), nullable=True)

    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    metodo_pago: Mapped[str] = mapped_column(String(30), nullable=False)  # STRIPE, MANUAL_TALLER
    estado_pago: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDIENTE")  # PENDIENTE, CONFIRMADO, FALLIDO
    referencia_externa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_confirmacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    solicitud = relationship("SolicitudEmergencia")
    taller = relationship("Taller")
    usuario = relationship("Usuario")
