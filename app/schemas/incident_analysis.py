"""
Schemas para análisis de incidentes vehiculares
Incluye requests y responses para transcripción y clasificación
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ==================== Transcription Schemas ====================

class AudioTranscriptionRequest(BaseModel):
    """Request para transcribir audio"""
    audio_url: str = Field(..., min_length=5, description="URL del archivo de audio")
    language: Optional[str] = Field("es", description="Código de idioma ISO (ej: es, en)")


class AudioTranscriptionResponse(BaseModel):
    """Response de transcripción de audio"""
    texto: str = Field(..., description="Texto transcrito")
    idioma: Optional[str] = Field(None, description="Idioma detectado")
    estado_comprension: str = Field(
        ...,
        description="COMPRENDIDO, PARCIALMENTE_COMPRENDIDO o NO_ENTENDIBLE"
    )
    duracion_segundos: Optional[float] = Field(None, description="Duración del audio")
    confianza_promedio: Optional[float] = Field(
        None,
        description="Confianza promedio de transcripción (0-1)"
    )


# ==================== Text Classification Schemas ====================

class TextClassificationRequest(BaseModel):
    """Request para clasificar texto"""
    texto: str = Field(..., min_length=3, description="Texto a clasificar")
    min_confidence: Optional[float] = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Confianza mínima requerida"
    )


class TextClassificationResponse(BaseModel):
    """Response de clasificación de texto"""
    categoria: str = Field(..., description="Categoría del incidente")
    subcategoria: Optional[str] = Field(None, description="Subcategoría si aplica")
    nivel_urgencia: Optional[str] = Field(
        None,
        description="Nivel de urgencia: BAJO, MEDIO, ALTO, CRITICO"
    )
    confianza: float = Field(..., ge=0.0, le=1.0, description="Puntuación de confianza")
    especialidad_sugerida: Optional[str] = Field(
        None,
        description="Nombre de especialidad recomendada"
    )
    servicio_sugerido: Optional[str] = Field(
        None,
        description="Nombre de servicio recomendado"
    )
    observaciones: Optional[str] = Field(None, description="Notas adicionales")
    fuente_clasificacion: str = Field(
        ...,
        description="Origen de la clasificación: REGLAS_BASADAS, ML, etc"
    )


# ==================== Complete Incident Analysis Schemas ====================

class IncidentAnalysisRequest(BaseModel):
    """Request para analizar incidente completo (debe existir solicitud)"""
    force_reanalysis: Optional[bool] = Field(
        False,
        description="Forzar reanálisis incluso si existe clasificación previa"
    )


class EspecialidadSugeridaResponse(BaseModel):
    """Respuesta con datos de especialidad"""
    id_especialidad: Optional[UUID] = None
    nombre_especialidad: Optional[str] = None


class ServicioSugeridoResponse(BaseModel):
    """Respuesta con datos de servicio"""
    id_servicio: Optional[UUID] = None
    nombre_servicio: Optional[str] = None


class IncidentAnalysisResponse(BaseModel):
    """Response completa de análisis de incidente"""
    solicitud_id: Optional[UUID] = Field(None, description="ID de la solicitud analizada")
    descripcion_texto: Optional[str] = Field(None, description="Descripción manual del incidente")
    transcripcion_audio: Optional[str] = Field(None, description="Texto transcrito del audio")
    estado_comprension: Optional[str] = Field(
        None,
        description="Estado de comprensión del audio"
    )
    categoria_predicha: Optional[str] = Field(None, description="Categoría clasificada")
    subcategoria_predicha: Optional[str] = Field(None, description="Subcategoría si aplica")
    especialidad_sugerida: Optional[str] = Field(
        None,
        description="Nombre de especialidad recomendada"
    )
    id_especialidad_requerida: Optional[UUID] = Field(
        None,
        description="ID de especialidad si existe en catálogo"
    )
    servicio_sugerido: Optional[str] = Field(
        None,
        description="Nombre de servicio recomendado"
    )
    id_servicio_sugerido: Optional[UUID] = Field(
        None,
        description="ID de servicio si existe en catálogo"
    )
    nivel_urgencia_predicho: Optional[str] = Field(
        None,
        description="Nivel de urgencia predicho"
    )
    confianza_modelo: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confianza del modelo (0-1)"
    )
    fuente_entrada: Optional[str] = Field(
        None,
        description="Fuente de análisis: TEXTO_MANUAL, TRANSCRIPCION_AUDIO o COMBINADO"
    )
    observaciones: Optional[str] = Field(None, description="Observaciones adicionales")


# ==================== Tool Endpoints Schemas ====================

class TranscribeAudioToolRequest(BaseModel):
    """Request para endpoint de herramienta de transcripción"""
    audio_url: str = Field(..., min_length=5, description="URL del audio a transcribir")


class TranscribeAudioToolResponse(BaseModel):
    """Response del endpoint herramienta de transcripción"""
    success: bool
    data: Optional[AudioTranscriptionResponse] = None
    error: Optional[str] = None


class ClassifyTextToolRequest(BaseModel):
    """Request para endpoint de herramienta de clasificación"""
    texto: str = Field(..., min_length=3, description="Texto a clasificar")
    min_confidence: Optional[float] = Field(0.5, ge=0.0, le=1.0)


class ClassifyTextToolResponse(BaseModel):
    """Response del endpoint herramienta de clasificación"""
    success: bool
    data: Optional[TextClassificationResponse] = None
    error: Optional[str] = None


class AnalyzeIncidentToolResponse(BaseModel):
    """Response del endpoint herramienta de análisis completo"""
    success: bool
    data: Optional[IncidentAnalysisResponse] = None
    error: Optional[str] = None


class ProblemUrgencyRequest(BaseModel):
    """Request para procesar descripcion de problema con IA."""
    texto: str = Field(..., min_length=8, description="Descripcion del problema")
    id_vehiculo: UUID | None = Field(None, description="Vehiculo afectado para enriquecer sugerencias")
    categoria_incidente: str | None = Field(None, description="Categoria detectada previamente por imagen u otro medio")


class ProblemUrgencyResponse(BaseModel):
    """Resultado de clasificacion de urgencia y sugerencia operativa."""
    nivel_urgencia: str = Field(..., description="BAJO, MEDIO, ALTO o CRITICO")
    criterio_detectado: Optional[str] = Field(None, description="Resumen del criterio aplicado")
    mensaje_chatbot: str = Field(..., description="Mensaje para mostrar al usuario")
    accion_recomendada: Optional[str] = Field(None, description="Accion sugerida en app")
    confianza: float = Field(..., ge=0.0, le=1.0, description="Confianza de clasificacion")
    proveedor: str = Field(..., description="Proveedor de IA usado")
    modelo: str = Field(..., description="Modelo LLM usado")
    categoria_incidente: Optional[str] = Field(None, description="Categoria de incidente sugerida")
    servicio_sugerido: Optional[str] = Field(None, description="Servicio principal sugerido")
    especialidad_sugerida: Optional[str] = Field(None, description="Especialidad principal sugerida")
    id_servicio_sugerido: UUID | None = Field(None, description="ID del servicio principal si existe en catalogo")
    nombre_servicio_sugerido: Optional[str] = Field(None, description="Nombre legible del servicio principal")
    id_especialidad_sugerida: UUID | None = Field(None, description="ID de la especialidad principal si existe en catalogo")
    nombre_especialidad_sugerida: Optional[str] = Field(None, description="Nombre legible de la especialidad principal")
    servicios_sugeridos: list[str] = Field(default_factory=list, description="Lista de servicios sugeridos")
    especialidades_sugeridas: list[str] = Field(default_factory=list, description="Lista de especialidades sugeridas")
    ids_servicios_sugeridos: list[UUID] = Field(default_factory=list, description="IDs de servicios sugeridos encontrados")
    ids_especialidades_sugeridas: list[UUID] = Field(default_factory=list, description="IDs de especialidades sugeridas encontradas")
    motivo: Optional[str] = Field(None, description="Razon principal de la sugerencia")
    requiere_grua: bool = Field(False, description="Indica si conviene remolque")
    requiere_cotizacion_previa: bool = Field(False, description="Indica si requiere cotizacion")
    aplica_pago_minimo_ida: bool = Field(False, description="Indica si aplica pago minimo de ida")


class ProcessProblemToolResponse(BaseModel):
    """Response del endpoint herramienta procesar-problema."""
    success: bool
    data: Optional[ProblemUrgencyResponse] = None
    error: Optional[str] = None


class SmartServiceSuggestionRequest(BaseModel):
    """Request para sugerencia inteligente previa a crear solicitud."""
    descripcion: str = Field(..., min_length=5)
    id_vehiculo: UUID | None = None
    categoria_incidente: str | None = None


class SmartServiceSuggestionResponse(BaseModel):
    """Sugerencia inteligente de servicio/especialidad para emergencia."""
    servicio_sugerido: str
    motivo: str
    prioridad: str
    requiere_grua: bool
    requiere_cotizacion_previa: bool
    aplica_pago_minimo_ida: bool
    id_servicio_sugerido: UUID | None = None
    nombre_servicio_sugerido: str | None = None
    id_especialidad_sugerida: UUID | None = None
    nombre_especialidad_sugerida: str | None = None


# ==================== Batch/Admin Schemas ====================

class IncidentAnalysisSummary(BaseModel):
    """Resumen de análisis para listas y reportes"""
    solicitud_id: UUID
    categoria_predicha: str
    confianza_modelo: float
    fuente_entrada: str
    nivel_urgencia_predicho: Optional[str] = None
    fecha_procesamiento: datetime


class BatchAnalysisResult(BaseModel):
    """Resultado de análisis en lote"""
    total_solicitudes: int = Field(..., description="Total de solicitudes procesadas")
    exitosas: int = Field(..., description="Solicitudes analizadas exitosamente")
    fallidas: int = Field(..., description="Solicitudes que fallaron")
    sin_clasificacion: int = Field(
        ...,
        description="Solicitudes sin clasificación clara"
    )
    duracion_segundos: float = Field(..., description="Tiempo total de procesamiento")
    errores: list[str] = Field(default_factory=list, description="Detalles de errores")
