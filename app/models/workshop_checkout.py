import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkshopCheckout(Base):
    __tablename__ = "workshop_checkout"

    id_checkout: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_plan: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plan.id_plan"), nullable=False, index=True
    )
    checkout_token: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    estado_checkout: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDIENTE")
    correo_taller: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    registro_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    id_usuario_creado: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    id_taller_creado: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    fecha_validacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
