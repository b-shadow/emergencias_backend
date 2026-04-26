from datetime import datetime
from pydantic import BaseModel


class EstadisticaDiagnostico(BaseModel):
    diagnostico: str
    cantidad: int
    porcentaje: float
    requiere_seguimiento: int


class EstadisticaDemacruzada(BaseModel):
    periodo: str
    cantidad: int


class EstadisticaTiempoAtencion(BaseModel):
    tiempo_promedio_minutos: float
    tiempo_minimo_minutos: float
    tiempo_maximo_minutos: float


class EstadisticaGeneralTaller(BaseModel):
    fecha_inicio: datetime
    fecha_fin: datetime
    total_solicitudes_atendidas: int
    total_solicitudes_canceladas: int
    total_servicios_completados: int
    tasa_completacion: float
    diagnosticos: list[EstadisticaDiagnostico]
    total_diagnosticos_con_seguimiento: int
    dias_mayor_demanda: list[EstadisticaDemacruzada]
    horas_mayor_demanda: list[EstadisticaDemacruzada]
    tiempo_promedio_atencion: EstadisticaTiempoAtencion


class FiltroReporteAplicado(BaseModel):
    fecha_inicio: datetime
    fecha_fin: datetime
    agrupar_por: str
    nivel_urgencia: str | None = None
    categoria_incidente: str | None = None
    estado_solicitud: str | None = None
    estado_asignacion: str | None = None
    estado_resultado: str | None = None


class ReporteTablaItem(BaseModel):
    grupo: str
    total_solicitudes: int
    solicitudes_atendidas: int
    solicitudes_canceladas: int
    servicios_completados: int
    tasa_completacion: float


class ReporteGraficos(BaseModel):
    categorias: list[str]
    serie_total_solicitudes: list[int]
    serie_solicitudes_atendidas: list[int]
    serie_solicitudes_canceladas: list[int]
    serie_servicios_completados: list[int]


class ReporteFiltradoTaller(BaseModel):
    filtros_aplicados: FiltroReporteAplicado
    tabla: list[ReporteTablaItem]
    graficos: ReporteGraficos


class OpcionesFiltrosTaller(BaseModel):
    urgencias: list[str]
    categorias_incidente: list[str]
    estados_solicitud: list[str]
    estados_asignacion: list[str]
    estados_resultado: list[str]


class EstadisticasTallerResponse(BaseModel):
    id_taller: str
    nombre_taller: str
    estadisticas: EstadisticaGeneralTaller | None = None
    reporte: ReporteFiltradoTaller | None = None
    opciones_filtros: OpcionesFiltrosTaller | None = None
    mensaje_vacio: str | None = None
