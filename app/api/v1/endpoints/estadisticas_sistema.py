from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria
from app.models.usuario import Usuario
from app.schemas.estadisticas_sistema import EstadisticasGeneralesResponse
from app.services.estadisticas_sistema_service import EstadisticasSistemaService
from app.services.bitacora_service import BitacoraService

router = APIRouter()


@router.get(
    "/estadisticas-sistema",
    response_model=EstadisticasGeneralesResponse,
    summary="Consultar estadísticas generales del sistema",
    description="Obtiene estadísticas globales sobre el funcionamiento de la plataforma (solo ADMINISTRADOR)"
)
def obtener_estadisticas_sistema(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
    fecha_inicio: datetime | None = Query(None, description="Fecha de inicio del rango (YYYY-MM-DD)"),
    fecha_fin: datetime | None = Query(None, description="Fecha de fin del rango (YYYY-MM-DD)"),
    agrupar_por: str = Query(
        "dia",
        description="Agrupacion del reporte: dia|semana|mes|categoria|urgencia|estado|taller",
    ),
    nivel_urgencia: str | None = Query(None, description="Filtro por urgencia"),
    categoria_incidente: str | None = Query(None, description="Filtro por categoria"),
    estado_solicitud: str | None = Query(None, description="Filtro por estado de solicitud"),
    id_taller: str | None = Query(None, description="Filtro por id de taller"),
):
    """
    Obtiene estadísticas generales del sistema:
    - Total de emergencias y solicitudes
    - Tipos de incidentes más frecuentes
    - Talleres con mayor actividad
    - Zonas con más emergencias
    - Tiempo promedio de respuesta
    
    Parámetros opcionales:
    - fecha_inicio: Fecha de inicio (por defecto, hace 30 días)
    - fecha_fin: Fecha de fin (por defecto, hoy)
    
    Roles permitidos: ADMINISTRADOR
    """
    
    # Obtener estadísticas
    estadisticas = EstadisticasSistemaService.obtener_estadisticas_sistema(
        db=db,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        agrupar_por=agrupar_por,
        nivel_urgencia=nivel_urgencia,
        categoria_incidente=categoria_incidente,
        estado_solicitud=estado_solicitud,
        id_taller=id_taller,
    )

    # Nota: BitacoraService.registrar() no existe, comentado por ahora
    # BitacoraService.registrar(...) 

    return estadisticas
