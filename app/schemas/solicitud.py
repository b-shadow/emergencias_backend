from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.core.enums import EstadoSolicitud, NivelUrgencia, EstadoAsignacion, TipoActor


class SolicitudCreateRequest(BaseModel):
    """Schema para crear una solicitud de emergencia"""
    codigo_solicitud: str = Field(..., min_length=1, max_length=50)
    descripcion_texto: str | None = None
    descripcion_audio_url: str | None = None
    transcripcion_audio: str | None = None
    latitud: float | None = None
    longitud: float | None = None
    direccion_referencial: str | None = None
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None = None
    radio_busqueda_km: float = Field(default=5.0, ge=0.5, le=100.0)
    id_vehiculo: UUID | None = None
    # NAS: Nuevos campos para especialidades y servicios requeridos
    id_especialidades: list[UUID] = Field(default_factory=list, description="IDs de especialidades necesarias")
    id_servicios: list[UUID] = Field(default_factory=list, description="IDs de servicios necesarios")


class SolicitudUpdateRequest(BaseModel):
    """Schema para actualizar una solicitud de emergencia"""
    descripcion_texto: str | None = None
    descripcion_audio_url: str | None = None
    transcripcion_audio: str | None = None
    latitud: float | None = None
    longitud: float | None = None
    direccion_referencial: str | None = None
    radio_busqueda_km: float | None = None
    categoria_incidente: str | None = None
    nivel_urgencia: NivelUrgencia | None = None
    # NAS: Campos para actualizar especialidades y servicios
    id_especialidades: list[UUID] | None = None
    id_servicios: list[UUID] | None = None


class SolicitudResponse(BaseModel):
    """Schema para respuestas de solicitud de emergencia"""
    id_solicitud: UUID
    id_cliente: UUID
    id_vehiculo: UUID | None
    codigo_solicitud: str
    descripcion_texto: str | None
    descripcion_audio_url: str | None
    transcripcion_audio: str | None
    latitud: float | None
    longitud: float | None
    direccion_referencial: str | None
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None
    radio_busqueda_km: float
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    fecha_cierre: datetime | None
    # NAS: Nuevos campos para especialidades y servicios (retorna nombres)
    especialidades_requeridas: list[str] = Field(default_factory=list, description="Nombres de especialidades solicitadas")
    servicios_requeridos: list[str] = Field(default_factory=list, description="Nombres de servicios solicitados")

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_relations(cls, solicitud_obj):
        """Enriquece la respuesta con especialidades y servicios relacionados"""
        data = {
            "id_solicitud": solicitud_obj.id_solicitud,
            "id_cliente": solicitud_obj.id_cliente,
            "id_vehiculo": solicitud_obj.id_vehiculo,
            "codigo_solicitud": solicitud_obj.codigo_solicitud,
            "descripcion_texto": solicitud_obj.descripcion_texto,
            "descripcion_audio_url": solicitud_obj.descripcion_audio_url,
            "transcripcion_audio": solicitud_obj.transcripcion_audio,
            "latitud": solicitud_obj.latitud,
            "longitud": solicitud_obj.longitud,
            "direccion_referencial": solicitud_obj.direccion_referencial,
            "estado_actual": solicitud_obj.estado_actual,
            "nivel_urgencia": solicitud_obj.nivel_urgencia,
            "categoria_incidente": solicitud_obj.categoria_incidente,
            "radio_busqueda_km": solicitud_obj.radio_busqueda_km,
            "fecha_creacion": solicitud_obj.fecha_creacion,
            "fecha_actualizacion": solicitud_obj.fecha_actualizacion,
            "fecha_cierre": solicitud_obj.fecha_cierre,
            "especialidades_requeridas": [rel.especialidad.nombre_especialidad for rel in solicitud_obj.especialidades],
            "servicios_requeridos": [rel.servicio.nombre_servicio for rel in solicitud_obj.servicios],
        }
        return cls(**data)


# ================== Schemas para Consulta de Estado (Caso de Uso: Consultar estado) ==================

class HistorialEstadoResponse(BaseModel):
    """Historial de transición de estado de una solicitud"""
    id_historial_estado: UUID
    estado_anterior: EstadoSolicitud | None
    estado_nuevo: EstadoSolicitud
    comentario: str | None
    actualizado_por_tipo: TipoActor
    actualizado_por_id: UUID | None
    fecha_cambio: datetime

    class Config:
        from_attributes = True


class TallerInfoResponse(BaseModel):
    """Información básica del taller asignado a una solicitud"""
    id_taller: UUID
    nombre_taller: str
    telefono: str | None
    email: str | None
    direccion: str | None
    calificacion_promedio: float | None

    class Config:
        from_attributes = True


class AsignacionAtencionResponse(BaseModel):
    """Información de asignación y estado de atención"""
    id_asignacion: UUID
    estado_asignacion: EstadoAsignacion
    fecha_asignacion: datetime
    fecha_inicio_atencion: datetime | None
    fecha_fin_atencion: datetime | None
    taller: TallerInfoResponse | None

    class Config:
        from_attributes = True


class SolicitudEstadoDetailResponse(BaseModel):
    """
    Respuesta detallada para Consultar Estado de Solicitud.
    Incluye estado actual, historial y info del taller si existe.
    """
    # Información básica de la solicitud
    id_solicitud: UUID
    codigo_solicitud: str
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None
    
    # Ubicación y descripción
    latitud: float | None
    longitud: float | None
    direccion_referencial: str | None
    descripcion_texto: str | None
    descripcion_audio_url: str | None
    
    # Vehículo y cliente
    id_vehiculo: UUID | None
    id_cliente: UUID
    
    # Fechas
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    fecha_cierre: datetime | None
    
    # Historial de cambios de estado (paso 4 del caso de uso)
    historial_estado: list[HistorialEstadoResponse]
    
    # Información del taller si existe asignación (paso 5 del caso de uso)
    asignacion_actual: AsignacionAtencionResponse | None

    class Config:
        from_attributes = True


class SolicitudCancelRequest(BaseModel):
    """Schema para cancelar una solicitud"""
    razon: str | None = Field(None, max_length=500)


# ================== Schemas para Historial de Emergencias (Caso de Uso: Consultar historial) ==================

class VehiculoInfoResponse(BaseModel):
    """Información básica del vehículo asociado a una solicitud"""
    id_vehiculo: UUID
    placa: str
    marca: str | None
    modelo: str | None
    anio: int | None
    color: str | None

    class Config:
        from_attributes = True


class ResultadoServicioResponse(BaseModel):
    """Información del resultado de la atención de emergencia"""
    id_resultado_servicio: UUID
    diagnostico: str | None
    solucion_aplicada: str | None
    estado_resultado: str  # EstadoResultado
    requiere_seguimiento: bool
    observaciones: str | None
    fecha_registro: datetime

    class Config:
        from_attributes = True


class SolicitudHistorialListItemResponse(BaseModel):
    """Item para el listado de historial de emergencias"""
    id_solicitud: UUID
    codigo_solicitud: str
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    fecha_creacion: datetime
    fecha_cierre: datetime | None
    vehículo_placa: str | None
    taller_nombre: str | None
    categoria_incidente: str | None

    class Config:
        from_attributes = True


class SolicitudHistorialListResponse(BaseModel):
    """Respuesta con listado de historial de emergencias"""
    total_solicitudes: int
    total_finalizadas: int
    total_activas: int
    historial: list[SolicitudHistorialListItemResponse]

    class Config:
        from_attributes = True


class SolicitudHistorialDetalleResponse(BaseModel):
    """Respuesta detallada de una solicitud del historial"""
    # Información básica
    id_solicitud: UUID
    codigo_solicitud: str
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None
    
    # Descripción y ubicación
    descripcion_texto: str | None
    descripcion_audio_url: str | None
    latitud: float | None
    longitud: float | None
    direccion_referencial: str | None
    
    # Fechas
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    fecha_cierre: datetime | None
    
    # Vehículo asociado
    vehiculo: VehiculoInfoResponse | None
    
    # Taller que atendió
    taller_asignado: TallerInfoResponse | None
    
    # Resultado de la atención
    resultado_servicio: ResultadoServicioResponse | None
    
    # Historial de cambios de estado
    historial_estado: list[HistorialEstadoResponse]

    class Config:
        from_attributes = True


# ================== Schemas para Visualizar Solicitudes (Caso de Uso: Visualizar solicitudes - TALLER) ==================

class EvidenciaResponse(BaseModel):
    """Información de archivos/evidencias adjuntas a una solicitud"""
    id_evidencia: UUID
    tipo_evidencia: str  # TipoEvidencia
    url_archivo: str
    nombre_archivo: str | None
    descripcion: str | None
    fecha_subida: datetime

    class Config:
        from_attributes = True


class SolicitudDisponibleListItemResponse(BaseModel):
    """Item resumido para el listado de solicitudes disponibles (Paso 4)"""
    id_solicitud: UUID
    codigo_solicitud: str
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None
    latitud: float | None
    longitud: float | None
    fecha_creacion: datetime
    distancia_km: float | None  # Calculada en servicio
    vehiculo_marca_modelo: str | None
    descripcion_texto: str | None

    class Config:
        from_attributes = True


class SolicitudDisponibleDetalleResponse(BaseModel):
    """Detalle completo de una solicitud disponible (Paso 6)"""
    # Información básica
    id_solicitud: UUID
    codigo_solicitud: str
    estado_actual: EstadoSolicitud
    nivel_urgencia: NivelUrgencia
    categoria_incidente: str | None
    
    # Descripción
    descripcion_texto: str | None
    descripcion_audio_url: str | None
    
    # Ubicación
    latitud: float | None
    longitud: float | None
    direccion_referencial: str | None
    radio_busqueda_km: float
    
    # Vehículo
    vehiculo_placa: str | None
    vehiculo_marca: str | None
    vehiculo_modelo: str | None
    vehiculo_color: str | None
    
    # Fechas
    fecha_creacion: datetime
    
    # Distancia del taller
    distancia_km: float | None
    
    # Evidencias adjuntas
    evidencias: list[EvidenciaResponse]
    
    # Especialidades y Servicios requeridos
    especialidades_requeridas: list[str]
    servicios_requeridos: list[str]
    
    # Información del cliente
    cliente_nombre: str | None
    cliente_email: str | None
    cliente_telefono: str | None

    class Config:
        from_attributes = True


class ListadoSolicitudesDisponiblesResponse(BaseModel):
    """Respuesta con listado de solicitudes disponibles para el taller"""
    total_disponibles: int
    cantidad_por_especialidad: dict  # especialidad -> cantidad
    solicitudes: list[SolicitudDisponibleListItemResponse]

    class Config:
        from_attributes = True


# Schemas para Postulación a Solicitud (Caso de Uso: Solicitar atención de emergencia)

class PostulacionCreateRequest(BaseModel):
    """Request para que un taller se postule a una solicitud"""
    tiempo_estimado_llegada_min: int | None = Field(default=None, ge=1, le=1440)  # 1 min a 24 horas
    mensaje_propuesta: str | None = Field(default=None, max_length=1000)  # Mensaje adicional del taller


class PostulacionResponse(BaseModel):
    """Respuesta de una postulación de taller"""
    id_postulacion: UUID
    id_solicitud: UUID
    id_taller: UUID
    tiempo_estimado_llegada_min: int | None
    mensaje_propuesta: str | None
    estado_postulacion: str  # EstadoPostulacion enum
    fecha_postulacion: datetime
    fecha_respuesta: datetime | None

    class Config:
        from_attributes = True


class PostulacionDetailResponse(BaseModel):
    """Detalle completo de una postulación con info del taller"""
    id_postulacion: UUID
    id_solicitud: UUID
    id_taller: UUID
    codigo_solicitud: str  # Del lado de solicitud
    nombre_taller: str
    telefono_taller: str | None
    direccion_taller: str | None
    tiempo_estimado_llegada_min: int | None
    mensaje_propuesta: str | None
    estado_postulacion: str
    fecha_postulacion: datetime
    fecha_respuesta: datetime | None

    class Config:
        from_attributes = True
