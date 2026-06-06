from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
class PagoManualRequest(BaseModel):
    monto: float = Field(..., gt=0)
    observacion: str | None = Field(default=None, max_length=1000)


class StripePaymentIntentRequest(BaseModel):
    monto: float = Field(..., gt=0)


class StripeConfirmRequest(BaseModel):
    payment_intent_id: str


class PagoResponse(BaseModel):
    id_pago: UUID
    id_solicitud: UUID
    id_taller: UUID
    monto: float
    moneda: str
    metodo_pago: str
    estado_pago: str
    referencia_externa: str | None = None
    observacion: str | None = None
    fecha_registro: datetime
    fecha_confirmacion: datetime | None = None

    class Config:
        from_attributes = True


class ResumenPagoResponse(BaseModel):
    id_solicitud: UUID
    id_taller: UUID | None = None
    estado_solicitud: str
    total_cotizacion: float = 0
    cargo_cancelacion: float = 0
    total_exigible: float = 0
    total_pagado: float = 0
    saldo_pendiente: float = 0
    estado_pago: str
    pagos: list[PagoResponse] = Field(default_factory=list)
