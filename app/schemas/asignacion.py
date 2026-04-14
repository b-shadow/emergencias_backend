from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from app.core.enums import EstadoAsignacion


class AsignacionEstadoUpdateRequest(BaseModel):
    """Schema para actualizar el estado de una asignación."""
    nuevo_estado: str = Field(..., description="Nuevo estado de la atención: EN_CAMINO, EN_PROCESO, ATENDIDA, CANCELADA")
    comentario: str | None = Field(None, description="Comentario adicional sobre el cambio de estado", max_length=500)


class ServicioRealizadoRequest(BaseModel):
    """Schema para servicios realizados en una asignación."""
    id_taller_servicio: UUID = Field(..., description="ID de taller_servicio realizado")
    realizado: bool = Field(default=True, description="Si el servicio fue realizado")
    diagnostico: str | None = Field(None, description="Diagnóstico del problema encontrado", max_length=500)
    solucion_aplicada: str | None = Field(None, description="Solución aplicada para resolver el problema", max_length=500)
    observaciones: str | None = Field(None, description="Observaciones adicionales sobre el servicio", max_length=500)
    requiere_seguimiento: bool = Field(default=False, description="Si requiere seguimiento posterior")


class ServicioRealizadoResponse(BaseModel):
    """Schema de respuesta para servicio realizado."""
    id_servicio: UUID
    nombre_servicio: str
    realizado: bool
    
    model_config = ConfigDict(from_attributes=True)


class ServicioTallerResponse(BaseModel):
    """Schema de servicio disponible para taller."""
    id_taller_servicio: UUID = Field(..., description="ID de taller_servicio (para enlazar en resultado_servicio)")
    id_servicio: UUID = Field(..., description="ID del servicio")
    nombre_servicio: str
    descripcion: str | None = None
    realizado: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class AsignacionResponse(BaseModel):
    """Schema de respuesta simple para asignación."""
    id_asignacion: UUID
    id_solicitud: UUID
    id_taller: UUID
    estado_asignacion: EstadoAsignacion
    fecha_asignacion: datetime
    fecha_inicio_atencion: datetime | None = None
    fecha_fin_atencion: datetime | None = None
    motivo_cancelacion: str | None = None
    
    model_config = ConfigDict(from_attributes=True)
