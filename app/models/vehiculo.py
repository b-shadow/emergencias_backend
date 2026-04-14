import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EstadoRegistroVehiculo
from app.models.base import Base


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    id_vehiculo: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_cliente: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cliente.id_cliente"), nullable=False)
    placa: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    marca: Mapped[str | None] = mapped_column(String(120), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    anio: Mapped[int | None] = mapped_column(nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tipo_combustible: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    estado_registro: Mapped[EstadoRegistroVehiculo] = mapped_column(Enum(EstadoRegistroVehiculo, name="vehicle_registration_status"), nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cliente = relationship("Cliente", back_populates="vehiculos")
