from datetime import datetime
from pydantic import BaseModel


class EstadisticaDiagnostico(BaseModel):
    """Estadística de diagnóstico más frecuente"""
    diagnostico: str
    cantidad: int
    porcentaje: float
    requiere_seguimiento: int  # Cantidad que requiere seguimiento


class EstadisticaDemacruzada(BaseModel):
    """Estadística de demanda (día u hora)"""
    periodo: str  # Ej: "2024-04-12" o "14:00"
    cantidad: int


class EstadisticaTiempoAtencion(BaseModel):
    """Estadística de tiempo promedio de atención"""
    tiempo_promedio_minutos: float
    tiempo_minimo_minutos: float
    tiempo_maximo_minutos: float


class EstadisticaGeneralTaller(BaseModel):
    """Estadística general del taller"""
    fecha_inicio: datetime
    fecha_fin: datetime
    total_solicitudes_atendidas: int
    total_solicitudes_canceladas: int
    total_servicios_completados: int
    tasa_completacion: float  # Porcentaje
    diagnosticos: list[EstadisticaDiagnostico]
    total_diagnosticos_con_seguimiento: int
    dias_mayor_demanda: list[EstadisticaDemacruzada]
    horas_mayor_demanda: list[EstadisticaDemacruzada]
    tiempo_promedio_atencion: EstadisticaTiempoAtencion
    

class EstadisticasTallerResponse(BaseModel):
    """Respuesta con todas las estadísticas del taller"""
    id_taller: str
    nombre_taller: str
    estadisticas: EstadisticaGeneralTaller
    mensaje_vacio: str | None = None  # Mensaje si no hay datos
