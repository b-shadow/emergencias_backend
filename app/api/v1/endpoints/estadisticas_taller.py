from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.estadisticas_taller import EstadisticasTallerResponse
from app.services.estadisticas_taller_service import EstadisticasTallerService
from datetime import datetime

router = APIRouter()


@router.get(
    "/mis-estadisticas",
    response_model=EstadisticasTallerResponse,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def obtener_mis_estadisticas(
    fecha_inicio: str | None = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: str | None = Query(None, description="Fecha fin YYYY-MM-DD"),
    agrupar_por: str = Query(
        "dia",
        description="Agrupacion del reporte: dia|semana|mes|categoria|urgencia|estado_solicitud|estado_asignacion|estado_resultado",
    ),
    nivel_urgencia: str | None = Query(None, description="Filtro por urgencia"),
    categoria_incidente: str | None = Query(None, description="Filtro por categoria"),
    estado_solicitud: str | None = Query(None, description="Filtro por estado solicitud"),
    estado_asignacion: str | None = Query(None, description="Filtro por estado asignacion"),
    estado_resultado: str | None = Query(None, description="Filtro por estado resultado"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene las estadísticas del taller autenticado.
    
    Parámetros:
    - fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional)
    - fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional)
    
    Si no se especifican fechas, se usa los últimos 30 días.
    """
    # Obtener el ID del taller desde el usuario autenticado
    if not current_user.taller:
        return EstadisticasTallerResponse(
            id_taller=str(current_user.id_usuario),
            nombre_taller="Desconocido",
            estadisticas=None,
            mensaje_vacio="El usuario no está asociado a un taller.",
        )

    id_taller = str(current_user.taller.id_taller)

    # Parsear fechas
    fecha_inicio_dt = None
    fecha_fin_dt = None

    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d").replace(
                tzinfo=None
            )
        except ValueError:
            return EstadisticasTallerResponse(
                id_taller=id_taller,
                nombre_taller=current_user.taller.nombre_taller,
                estadisticas=None,
                mensaje_vacio="Formato de fecha_inicio inválido. Use YYYY-MM-DD",
            )

    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(
                tzinfo=None
            )
        except ValueError:
            return EstadisticasTallerResponse(
                id_taller=id_taller,
                nombre_taller=current_user.taller.nombre_taller,
                estadisticas=None,
                mensaje_vacio="Formato de fecha_fin inválido. Use YYYY-MM-DD",
            )

    # Obtener estadísticas
    respuesta = EstadisticasTallerService.obtener_estadisticas_taller(
        db=db,
        id_taller=id_taller,
        fecha_inicio=fecha_inicio_dt,
        fecha_fin=fecha_fin_dt,
        agrupar_por=agrupar_por,
        nivel_urgencia=nivel_urgencia,
        categoria_incidente=categoria_incidente,
        estado_solicitud=estado_solicitud,
        estado_asignacion=estado_asignacion,
        estado_resultado=estado_resultado,
    )

    return respuesta
