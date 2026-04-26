from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class IncidenteFrequente(BaseModel):
    tipo_incidente: str
    cantidad: int
    porcentaje: float


class TallerActividad(BaseModel):
    nombre_taller: str
    solicitudes_atendidas: int
    servicios_realizados: int
    calificacion_promedio: Optional[float] = None


class ZonaEmergencia(BaseModel):
    zona: str
    cantidad_emergencias: int
    talleres_disponibles: int


class TiempoRespuesta(BaseModel):
    minimo: float
    maximo: float
    promedio: float
    mediana: float


class FiltroReporteSistemaAplicado(BaseModel):
    fecha_inicio: datetime
    fecha_fin: datetime
    agrupar_por: str
    nivel_urgencia: Optional[str] = None
    categoria_incidente: Optional[str] = None
    estado_solicitud: Optional[str] = None
    id_taller: Optional[str] = None


class ReporteTablaSistemaItem(BaseModel):
    grupo: str
    total_solicitudes: int
    solicitudes_atendidas: int
    solicitudes_canceladas: int
    servicios_completados: int
    tasa_completacion: float


class ReporteGraficosSistema(BaseModel):
    categorias: List[str]
    serie_total_solicitudes: List[int]
    serie_solicitudes_atendidas: List[int]
    serie_solicitudes_canceladas: List[int]
    serie_servicios_completados: List[int]


class ReporteFiltradoSistema(BaseModel):
    filtros_aplicados: FiltroReporteSistemaAplicado
    tabla: List[ReporteTablaSistemaItem]
    graficos: ReporteGraficosSistema


class OpcionesFiltrosSistema(BaseModel):
    urgencias: List[str]
    categorias_incidente: List[str]
    estados_solicitud: List[str]
    talleres: List[dict]


class EstadisticasGeneralesResponse(BaseModel):
    fecha_inicio: datetime
    fecha_fin: datetime
    total_emergencias: int
    total_solicitudes_atendidas: int
    total_servicios_realizados: int
    talleres_activos: int
    clientes_activos: int
    incidentes_frecuentes: List[IncidenteFrequente]
    talleres_top: List[TallerActividad]
    zonas_criticas: List[ZonaEmergencia]
    tiempo_respuesta: Optional[TiempoRespuesta] = None
    solicitudes_completadas: int
    solicitudes_pendientes: int
    solicitudes_canceladas: int
    reporte: Optional[ReporteFiltradoSistema] = None
    opciones_filtros: Optional[OpcionesFiltrosSistema] = None
    mensaje_vacio: Optional[str] = None

    class Config:
        from_attributes = True
