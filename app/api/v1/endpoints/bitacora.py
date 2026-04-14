from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria
from app.models.usuario import Usuario
from app.schemas.bitacora import (
    BitacoraFiltro,
    BitacoraListResponse,
)
from app.services.bitacora_service import BitacoraService

router = APIRouter()


@router.get(
    "",
    response_model=BitacoraListResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def consultar_bitacora(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=10000),
    tipo_actor: TipoActor | None = None,
    accion: str | None = None,
    modulo: str | None = None,
    resultado: ResultadoAuditoria | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Consultar registros de bitácora con filtros.
    Solo accesible para ADMINISTRADOR.
    
    Parámetros:
    - pagina: Número de página (por defecto 1)
    - por_pagina: Registros por página (por defecto 20, máximo 100)
    - tipo_actor: Filtrar por tipo de actor (CLIENTE, TALLER, ADMINISTRADOR, SISTEMA)
    - accion: Filtrar por acción (búsqueda parcial)
    - modulo: Filtrar por módulo (búsqueda parcial)
    - resultado: Filtrar por resultado (EXITO, ERROR, ADVERTENCIA)
    - fecha_inicio: Filtrar desde esta fecha (formato YYYY-MM-DD)
    - fecha_fin: Filtrar hasta esta fecha (formato YYYY-MM-DD)
    """
    filtro = BitacoraFiltro(
        pagina=pagina,
        por_pagina=por_pagina,
        tipo_actor=tipo_actor,
        accion=accion,
        modulo=modulo,
        resultado=resultado,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    return BitacoraService.consultar_bitacora(db, filtro)


@router.get(
    "/opciones/acciones",
    response_model=list[str],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def obtener_acciones_disponibles(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Obtiene la lista de acciones disponibles en la bitácora"""
    return BitacoraService.obtener_acciones_disponibles(db)


@router.get(
    "/opciones/modulos",
    response_model=list[str],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def obtener_modulos_disponibles(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Obtiene la lista de módulos disponibles en la bitácora"""
    return BitacoraService.obtener_modulos_disponibles(db)
