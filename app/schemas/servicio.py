from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import CategoriaTarifaServicio


class ServicioBase(BaseModel):
    nombre_servicio: str = Field(..., min_length=1, max_length=255)
    descripcion: str | None = Field(None, max_length=1000)
    estado: str = Field(..., pattern="^(ACTIVO|INACTIVO)$")


class ServicioResponse(ServicioBase):
    id_servicio: UUID

    class Config:
        from_attributes = True


class TallerServicioResponse(BaseModel):
    id_taller_servicio: UUID
    id_servicio: UUID
    nombre_servicio: str
    descripcion: str | None
    estado: str
    disponible: bool
    observaciones: str | None
    categoria_tarifa: CategoriaTarifaServicio
    precio_base: float
    precio_ida_minimo: float
    tipo_pintura_chaperio: str | None

    class Config:
        from_attributes = True


class TallerServicioCreate(BaseModel):
    id_servicio: UUID = Field(..., description="ID del servicio a agregar")
    disponible: bool = Field(default=True, description="Si el servicio esta disponible")
    observaciones: str | None = Field(None, max_length=1000, description="Observaciones sobre el servicio")
    categoria_tarifa: CategoriaTarifaServicio = Field(default=CategoriaTarifaServicio.MECANICO)
    precio_base: float = Field(default=0, ge=0)
    precio_ida_minimo: float = Field(default=0, ge=0)
    tipo_pintura_chaperio: str | None = Field(None, max_length=120)
