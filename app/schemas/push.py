from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import PlataformaPush


class PushTokenRegisterRequest(BaseModel):
    """Request para registrar un token push"""
    plataforma: PlataformaPush
    token_fcm: str = Field(..., min_length=1, max_length=500)
    device_id: str | None = Field(None, max_length=255)
    nombre_dispositivo: str | None = Field(None, max_length=255)


class PushTokenUnregisterRequest(BaseModel):
    """Request para desregistrar un token push"""
    token_fcm: str = Field(..., min_length=1, max_length=500)


class DispositivoPushRead(BaseModel):
    """Respuesta con información de un dispositivo push"""
    id_dispositivo_push: UUID
    id_usuario: UUID
    plataforma: PlataformaPush
    token_fcm: str
    device_id: str | None
    nombre_dispositivo: str | None
    activo: bool
    ultima_vez_usado: datetime | None
    fecha_registro: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


class DispositivoPushListResponse(BaseModel):
    """Respuesta con lista de dispositivos push del usuario"""
    dispositivos: list[DispositivoPushRead]
    total: int
