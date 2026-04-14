from uuid import UUID

from pydantic import BaseModel, Field


# ==================== Servicio Base ====================
class ServicioBase(BaseModel):
    nombre_servicio: str = Field(..., min_length=1, max_length=255)
    descripcion: str | None = Field(None, max_length=1000)
    estado: str = Field(..., pattern="^(ACTIVO|INACTIVO)$")


# ==================== Servicio Response ====================
class ServicioResponse(ServicioBase):
    id_servicio: UUID

    class Config:
        from_attributes = True


# ==================== Taller Servicio Response ====================
class TallerServicioResponse(BaseModel):
    id_taller_servicio: UUID
    id_servicio: UUID
    nombre_servicio: str
    descripcion: str | None
    estado: str
    disponible: bool
    observaciones: str | None

    class Config:
        from_attributes = True


# ==================== Taller Servicio Create ====================
class TallerServicioCreate(BaseModel):
    id_servicio: UUID = Field(..., description="ID del servicio a agregar")
    disponible: bool = Field(default=True, description="Si el servicio está disponible")
    observaciones: str | None = Field(None, max_length=1000, description="Observaciones sobre el servicio")
