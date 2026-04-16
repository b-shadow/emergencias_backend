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
    )

    # Nota: BitacoraService.registrar() no existe, comentado por ahora
    # BitacoraService.registrar(...) 

    return estadisticas
