from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import EstadoCotizacion


class CotizacionServicioItem(BaseModel):
    id_taller_servicio: UUID
    precio_servicio: float = Field(..., ge=0)
    nombre_servicio: str | None = Field(default=None, max_length=120)
    categoria_tarifa: str | None = Field(default=None, max_length=80)
    incluido_en_solicitud: bool = True


class CotizacionCreateRequest(BaseModel):
    servicios: list[CotizacionServicioItem] = Field(..., min_length=1)
    costo_ida: float = Field(default=0, ge=0)
    tipo_pintura: str | None = Field(None, max_length=120)
    detalle: str | None = Field(None, max_length=2000)


class CotizacionClienteDecisionRequest(BaseModel):
    aceptar: bool


class CotizacionResponse(BaseModel):
    id_cotizacion: UUID
    id_postulacion: UUID
    id_taller_servicio: UUID
    precio_servicio: float
    costo_ida: float
    precio_total_estimado: float
    estado_cotizacion: EstadoCotizacion
    tipo_pintura: str | None
    detalle: str | None
    fecha_creacion: datetime
    fecha_respuesta_cliente: datetime | None
    servicios: list[CotizacionServicioItem] = Field(default_factory=list)
    tiempo_estimado_llegada_min: int | None = None

    class Config:
        from_attributes = True
