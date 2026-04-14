from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import (
    TipoNotificacion,
    CategoriaNotificacion,
    EstadoLecturaNotificacion,
    EstadoEnvioNotificacion,
)


class NotificationRead(BaseModel):
    """Respuesta con información completa de una notificación"""
    id_notificacion: UUID
    tipo_usuario_destino: str
    id_usuario_destino: UUID
    titulo: str
    mensaje: str
    tipo_notificacion: TipoNotificacion
    categoria_evento: CategoriaNotificacion
    referencia_entidad: str | None
    referencia_id: UUID | None
    estado_lectura: EstadoLecturaNotificacion
    estado_envio: EstadoEnvioNotificacion
    fecha_envio: datetime
    fecha_lectura: datetime | None

    class Config:
        from_attributes = True


class NotificationReadAdmin(BaseModel):
    """Respuesta con información de notificación para administrador (incluye datos del usuario)"""
    id_notificacion: UUID
    tipo_usuario_destino: str
    id_usuario_destino: UUID
    nombre_usuario: str | None = None  # nombre_completo del usuario
    rol_usuario: str | None = None     # rol del usuario
    titulo: str
    mensaje: str
    tipo_notificacion: TipoNotificacion
    categoria_evento: CategoriaNotificacion
    referencia_entidad: str | None
    referencia_id: UUID | None
    estado_lectura: EstadoLecturaNotificacion
    estado_envio: EstadoEnvioNotificacion
    fecha_envio: datetime
    fecha_lectura: datetime | None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Respuesta con lista paginada de notificaciones"""
    items: list[NotificationRead]
    total: int
    limit: int
    offset: int


class NotificationListResponseAdmin(BaseModel):
    """Respuesta con lista paginada de notificaciones para administrador"""
    items: list[NotificationReadAdmin]
    total: int
    limit: int
    offset: int


class NotificationSendResult(BaseModel):
    """Resultado del envío de una notificación"""
    notification_id: UUID
    estado_envio: EstadoEnvioNotificacion
    tokens_intentados: int
    tokens_exitosos: int
    tokens_fallidos: int
    detalle: str | None = None
