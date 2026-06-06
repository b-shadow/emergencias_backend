from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CalificacionAtencionCreate(BaseModel):
    estrellas: int = Field(..., ge=1, le=5)
    comentario: str | None = Field(None, max_length=1000)
    confirmo_estado: bool = True


class CalificacionAtencionResponse(BaseModel):
    id_calificacion_atencion: UUID
    id_asignacion: UUID
    id_solicitud: UUID
    id_cliente: UUID
    id_taller: UUID
    estrellas: int
    comentario: str | None
    confirmo_estado: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True
