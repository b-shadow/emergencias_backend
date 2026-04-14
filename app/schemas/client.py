from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClienteBase(BaseModel):
    id_usuario: UUID
    nombre: str = Field(min_length=2, max_length=100)
    apellido: str = Field(min_length=2, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    ci: str | None = Field(default=None, min_length=5, max_length=50)
    direccion: str | None = Field(default=None, max_length=255)
    foto_perfil_url: str | None = Field(default=None, max_length=500)


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    apellido: str | None = Field(default=None, min_length=2, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    ci: str | None = Field(default=None, min_length=5, max_length=50)
    direccion: str | None = Field(default=None, max_length=255)
    foto_perfil_url: str | None = Field(default=None, max_length=500)


class ClienteRead(ClienteBase):
    id_cliente: UUID
    fecha_registro: datetime

    model_config = {"from_attributes": True}


class ClientePerfilUpdate(BaseModel):
    """Schema para actualizar el perfil propio del cliente"""
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    apellido: str | None = Field(default=None, min_length=2, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    ci: str | None = Field(default=None, min_length=5, max_length=50)
    direccion: str | None = Field(default=None, max_length=255)
    foto_perfil_url: str | None = Field(default=None, max_length=500)


class ClientePerfilResponse(BaseModel):
    """Schema para la respuesta del perfil del cliente autenticado"""
    id_cliente: UUID
    id_usuario: UUID
    nombre: str
    apellido: str
    telefono: str | None
    ci: str | None
    direccion: str | None
    foto_perfil_url: str | None
    fecha_registro: datetime
    correo: str | None = None  # Del usuario asociado

    model_config = {"from_attributes": True}
