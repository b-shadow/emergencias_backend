from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.core.enums import EstadoPostulacion


class PostulacionCreateRequest(BaseModel):
    """Schema para crear una postulacion"""
    tiempo_estimado_llegada_min: int | None = Field(None, ge=1, le=180)
    mensaje_propuesta: str | None = Field(None, max_length=1000)


class SolicitudInfoForPostulacion(BaseModel):
    """Informacion minima de solicitud para postulacion"""
    id_solicitud: UUID
    codigo_solicitud: str
    categoria_incidente: str | None
    nivel_urgencia: str
    radio_busqueda_km: float

    class Config:
        from_attributes = True


class PostulacionResponse(BaseModel):
    """Schema para respuestas de postulacion"""
    id_postulacion: UUID
    id_solicitud: UUID
    id_taller: UUID
    tiempo_estimado_llegada_min: int | None
    mensaje_propuesta: str | None
    estado_postulacion: EstadoPostulacion
    fecha_postulacion: datetime
    fecha_respuesta: datetime | None

    class Config:
        from_attributes = True


class PostulacionResponseWithSolicitud(PostulacionResponse):
    """Schema para postulacion con informacion de solicitud incluida"""
    solicitud: SolicitudInfoForPostulacion | None = None


class PostulacionActionRequest(BaseModel):
    """Schema para acciones sobre postulacion (aceptar, rechazar, retirar)."""
    id_trabajador: UUID | None = None
