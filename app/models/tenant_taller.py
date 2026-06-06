import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TenantTaller(Base):
    __tablename__ = "tenant_taller"

    id_tenant: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_tenant: Mapped[str] = mapped_column(String(255), nullable=False)
    slug_tenant: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    talleres = relationship("Taller", back_populates="tenant")
