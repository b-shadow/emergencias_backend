import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plan"

    id_plan: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_plan: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    nombre_plan: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_mensual_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    precio_bs: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    duracion_dias: Mapped[int] = mapped_column(nullable=False, default=30)
    stripe_price_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    es_activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
