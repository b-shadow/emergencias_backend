from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class IncidenteFrequente(BaseModel):
    """Representa un tipo de incidente frecuente"""
    tipo_incidente: str
    cantidad: int
    porcentaje: float


class TallerActividad(BaseModel):
    """Representa actividad de un taller"""
    nombre_taller: str
    solicitudes_atendidas: int
    servicios_realizados: int
    calificacion_promedio: Optional[float] = None


class ZonaEmergencia(BaseModel):
    """Representa emergencias por zona"""
    zona: str  # Puede ser ciudad, barrio, o coordenadas aproximadas
    cantidad_emergencias: int
    talleres_disponibles: int


class TiempoRespuesta(BaseModel):
    """Estadísticas de tiempo de respuesta"""
    minimo: float  # En minutos
    maximo: float
    promedio: float
    mediana: float


class EstadisticasGeneralesResponse(BaseModel):
    """Respuesta con estadísticas generales del sistema"""
    fecha_inicio: datetime
    fecha_fin: datetime
    
    # Resumen general
    total_emergencias: int
    total_solicitudes_atendidas: int
    total_servicios_realizados: int
    talleres_activos: int
    clientes_activos: int
    
    # Incidentes más frecuentes (top 5)
    incidentes_frecuentes: List[IncidenteFrequente]
    
    # Talleres con mayor actividad (top 5)
    talleres_top: List[TallerActividad]
    
    # Zonas con más emergencias (top 5)
    zonas_criticas: List[ZonaEmergencia]
    
    # Tiempo promedio de respuesta
    tiempo_respuesta: Optional[TiempoRespuesta] = None
    
    # Estado de las solicitudes
    solicitudes_completadas: int
    solicitudes_pendientes: int
    solicitudes_canceladas: int
    
    # Mensaje en caso de no haya datos
    mensaje_vacio: Optional[str] = None

    class Config:
        from_attributes = True
