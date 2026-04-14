from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import (
    RolUsuario,
    TipoNotificacion,
    CategoriaNotificacion,
    EstadoLecturaNotificacion,
    EstadoEnvioNotificacion,
)
from app.models.usuario import Usuario
from app.schemas.notification import (
    NotificationRead,
    NotificationReadAdmin,
    NotificationListResponse,
    NotificationListResponseAdmin,
)
from app.services.notificacion_service import NotificacionService
from app.schemas.common import MessageResponse

router = APIRouter()


# ==================== Endpoints para Usuarios (Clientes y Talleres) ====================

@router.get(
    "/mias",
    response_model=NotificationListResponse,
    summary="Listar mis notificaciones",
    description="Lista las notificaciones del usuario autenticado con opciones de filtro y paginación."
)
def list_my_notifications(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE, RolUsuario.TALLER)),
    tipo_notificacion: TipoNotificacion | None = Query(None),
    categoria_evento: CategoriaNotificacion | None = Query(None),
    estado_lectura: EstadoLecturaNotificacion | None = Query(None),
    fecha_desde: datetime | None = Query(None),
    fecha_hasta: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Lista las notificaciones del usuario autenticado.
    
    Parámetros de filtro (todos opcionales):
    - tipo_notificacion: PUSH, INTERNA, EMAIL
    - categoria_evento: SOLICITUD, POSTULACION, ASIGNACION, ESTADO, SISTEMA
    - estado_lectura: LEIDA, NO_LEIDA
    - fecha_desde, fecha_hasta: Rango de fechas
    - limit, offset: Paginación
    
    Roles permitidos: CLIENTE, TALLER
    """
    result = NotificacionService.list_my_notifications(
        db=db,
        id_usuario=current_user.id_usuario,
        tipo_notificacion=tipo_notificacion,
        categoria_evento=categoria_evento,
        estado_lectura=estado_lectura,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )

    return NotificationListResponse(
        items=[NotificationRead.from_orm(n) for n in result['items']],
        total=result['total'],
        limit=limit,
        offset=offset
    )


@router.get(
    "/mias/{id_notificacion}",
    response_model=NotificationRead,
    summary="Obtener detalle de mi notificación",
    description="Obtiene el detalle completo de una notificación. Si no estaba leída, la marca como leída."
)
def get_my_notification_detail(
    id_notificacion: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE, RolUsuario.TALLER)),
):
    """
    Obtiene el detalle de una notificación propia.
    
    - Si la notificación no estaba leída, la marca como leída automáticamente
    - Registra la consulta en bitácora
    
    Roles permitidos: CLIENTE, TALLER
    """
    notificacion = NotificacionService.get_my_notification_detail(
        db=db,
        id_usuario=current_user.id_usuario,
        id_notificacion=id_notificacion,
        registrar_consulta=False,
    )

    return NotificationRead.from_orm(notificacion)


@router.patch(
    "/mias/{id_notificacion}/leer",
    response_model=MessageResponse,
    summary="Marcar como leída",
    description="Marca explícitamente una notificación como leída."
)
def mark_notification_as_read(
    id_notificacion: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.CLIENTE, RolUsuario.TALLER)),
):
    """
    Marca una notificación como leída.
    
    Roles permitidos: CLIENTE, TALLER
    """
    NotificacionService.mark_as_read(
        db=db,
        id_usuario=current_user.id_usuario,
        id_notificacion=id_notificacion,
        registrar_en_bitacora=True,
    )

    return MessageResponse(message="Notificación marcada como leída")


# ==================== Endpoints para Administrador ====================

@router.get(
    "/admin/historial",
    response_model=NotificationListResponseAdmin,
    summary="Historial global de notificaciones",
    description="Lista todas las notificaciones del sistema (solo ADMINISTRADOR).",
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))]
)
def list_all_notifications_admin(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    tipo_notificacion: TipoNotificacion | None = Query(None),
    categoria_evento: CategoriaNotificacion | None = Query(None),
    id_usuario_destino: UUID | None = Query(None),
    estado_envio: EstadoEnvioNotificacion | None = Query(None),
    estado_lectura: EstadoLecturaNotificacion | None = Query(None),
    fecha_desde: datetime | None = Query(None),
    fecha_hasta: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Lista todas las notificaciones del sistema con filtros avanzados.
    
    Parámetros de filtro (todos opcionales):
    - tipo_notificacion: PUSH, INTERNA, EMAIL
    - categoria_evento: SOLICITUD, POSTULACION, ASIGNACION, ESTADO, SISTEMA
    - id_usuario_destino: Filtrar por usuario destino
    - estado_envio: ENVIADA, FALLIDA, PENDIENTE
    - estado_lectura: LEIDA, NO_LEIDA
    - fecha_desde, fecha_hasta: Rango de fechas
    
    Roles permitidos: ADMINISTRADOR
    """
    result = NotificacionService.list_all_notifications_admin(
        db=db,
        tipo_notificacion=tipo_notificacion,
        categoria_evento=categoria_evento,
        id_usuario_destino=id_usuario_destino,
        estado_envio=estado_envio,
        estado_lectura=estado_lectura,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limit=limit,
        offset=offset,
    )

    return NotificationListResponseAdmin(
        items=[NotificationReadAdmin(**n) if isinstance(n, dict) else NotificationReadAdmin.from_orm(n) for n in result['items']],
        total=result['total'],
        limit=limit,
        offset=offset
    )


@router.get(
    "/admin/{id_notificacion}",
    response_model=NotificationReadAdmin,
    summary="Detalle de notificación (admin)",
    description="Obtiene el detalle completo de cualquier notificación (solo ADMINISTRADOR)."
)
def get_notification_detail_admin(
    id_notificacion: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Obtiene el detalle completo de una notificación con datos del usuario destino.
    
    - Incluye nombre de usuario y rol
    - Registra la consulta en bitácora
    - No modifica el estado de lectura
    
    Roles permitidos: ADMINISTRADOR
    """
    notif_dict = NotificacionService.get_notification_detail_admin(
        db=db,
        id_notificacion=id_notificacion,
        registrar_consulta=False,
    )

    return NotificationReadAdmin(**notif_dict)


# ==================== Endpoint de estado ====================

@router.get(
    "/estado",
    response_model=MessageResponse,
    summary="Estado del módulo",
    description="Verifica el estado del módulo de notificaciones."
)
def estado_modulo() -> MessageResponse:
    """Endpoint de salud del módulo de notificaciones"""
    return MessageResponse(message="Módulo de notificaciones operacional")
