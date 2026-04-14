from uuid import UUID

from pydantic import BaseModel, Field


# ==================== Especialidad Base ====================
class EspecialidadBase(BaseModel):
    nombre_especialidad: str = Field(..., min_length=1, max_length=255)
    descripcion: str | None = Field(None, max_length=1000)
    estado: str = Field(..., pattern="^(ACTIVA|INACTIVA)$")


# ==================== Especialidad Response ====================
class EspecialidadResponse(EspecialidadBase):
    id_especialidad: UUID

    class Config:
        from_attributes = True


# ==================== Taller Especialidad Response ====================
class TallerEspecialidadResponse(BaseModel):
    id_taller_especialidad: UUID
    id_especialidad: UUID
    nombre_especialidad: str
    descripcion: str | None
    estado: str

    class Config:
        from_attributes = True


# ==================== Taller Especialidad Create ====================
class TallerEspecialidadCreate(BaseModel):
    id_especialidad: UUID = Field(..., description="ID de la especialidad a agregar")
