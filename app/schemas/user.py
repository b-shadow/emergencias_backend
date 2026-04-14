from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import RolUsuario


class UsuarioBase(BaseModel):
    correo: EmailStr
    rol: RolUsuario


class UsuarioCreate(UsuarioBase):
    contrasena: str = Field(min_length=8, max_length=128)
    nombre_completo: str = Field(min_length=1, max_length=255)


class UsuarioUpdate(BaseModel):
    rol: RolUsuario | None = None
    contrasena: str | None = Field(default=None, min_length=8, max_length=128)


class UsuarioRolUpdate(BaseModel):
    """Schema específico para cambio de rol por parte de administrador"""
    rol: RolUsuario


class UsuarioRead(UsuarioBase):
    id_usuario: UUID
    nombre_completo: str
    es_activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    ultimo_acceso: datetime | None = None

    model_config = {"from_attributes": True}
