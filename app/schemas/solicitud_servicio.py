from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import EstadoSolicitudServicio


class SolicitudServicioCreate(BaseModel):
    nombre_servicio: str = Field(..., min_length=1, max_length=255)
    descripcion: str | None = Field(None, max_length=1000)


class SolicitudServicioResponse(BaseModel):
    id_solicitud_servicio_taller: UUID
    id_taller: UUID
    nombre_taller: str | None = None
    nombre_servicio: str
    descripcion: str | None
    estado: EstadoSolicitudServicio
    motivo_rechazo: str | None = None
    id_servicio_creado: UUID | None = None
    fecha_solicitud: datetime
    fecha_resolucion: datetime | None = None

    class Config:
        from_attributes = True


class SolicitudServicioResolver(BaseModel):
    motivo_rechazo: str | None = Field(None, max_length=1000)
