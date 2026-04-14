from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import EstadoRegistroVehiculo


class VehiculoBase(BaseModel):
    id_cliente: UUID
    placa: str = Field(min_length=5, max_length=20)
    marca: str | None = Field(default=None, max_length=120)
    modelo: str | None = Field(default=None, max_length=120)
    anio: int | None = None
    color: str | None = Field(default=None, max_length=50)
    tipo_combustible: str | None = Field(default=None, max_length=50)
    observaciones: str | None = Field(default=None, max_length=1000)


class VehiculoCreate(VehiculoBase):
    pass


class VehiculoUpdate(BaseModel):
    placa: str | None = Field(default=None, min_length=5, max_length=20)
    marca: str | None = Field(default=None, max_length=120)
    modelo: str | None = Field(default=None, max_length=120)
    anio: int | None = None
    color: str | None = Field(default=None, max_length=50)
    tipo_combustible: str | None = Field(default=None, max_length=50)
    observaciones: str | None = Field(default=None, max_length=1000)
    estado_registro: EstadoRegistroVehiculo | None = None


class VehiculoRead(VehiculoBase):
    id_vehiculo: UUID
    estado_registro: EstadoRegistroVehiculo
    fecha_registro: datetime

    model_config = {"from_attributes": True}


# Schemas específicos para cliente
class VehiculoCreateByClient(BaseModel):
    """Schema para que cliente cree su propio vehículo"""
    placa: str = Field(min_length=5, max_length=20, description="Placa del vehículo")
    marca: str | None = Field(default=None, max_length=120, description="Marca del vehículo")
    modelo: str | None = Field(default=None, max_length=120, description="Modelo del vehículo")
    anio: int | None = Field(default=None, ge=1900, le=2100, description="Año de fabricación")
    color: str | None = Field(default=None, max_length=50, description="Color del vehículo")
    tipo_combustible: str | None = Field(default=None, max_length=50, description="Tipo de combustible")
    observaciones: str | None = Field(default=None, max_length=1000, description="Observaciones adicionales")

    @field_validator("placa")
    @classmethod
    def placa_uppercase(cls, v):
        """Normalizar placa a mayúsculas"""
        if v:
            return v.upper().strip()
        return v


class VehiculoUpdateByClient(BaseModel):
    """Schema para que cliente actualice su vehículo"""
    placa: str | None = Field(default=None, min_length=5, max_length=20)
    marca: str | None = Field(default=None, max_length=120)
    modelo: str | None = Field(default=None, max_length=120)
    anio: int | None = Field(default=None, ge=1900, le=2100)
    color: str | None = Field(default=None, max_length=50)
    tipo_combustible: str | None = Field(default=None, max_length=50)
    observaciones: str | None = Field(default=None, max_length=1000)

    @field_validator("placa")
    @classmethod
    def placa_uppercase(cls, v):
        """Normalizar placa a mayúsculas"""
        if v:
            return v.upper().strip()
        return v


class VehiculoResponseClient(BaseModel):
    """Schema de respuesta para cliente"""
    id_vehiculo: UUID
    placa: str
    marca: str | None
    modelo: str | None
    anio: int | None
    color: str | None
    tipo_combustible: str | None
    observaciones: str | None
    estado_registro: EstadoRegistroVehiculo
    fecha_registro: datetime

    model_config = {"from_attributes": True}
