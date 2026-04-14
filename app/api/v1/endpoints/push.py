from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
import os

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario, TipoActor, ResultadoAuditoria
from app.models.usuario import Usuario
from app.schemas.push import (
    PushTokenRegisterRequest,
    PushTokenUnregisterRequest,
    DispositivoPushListResponse,
    DispositivoPushRead,
)
from app.services.dispositivo_push_service import DispositivoPushService
from app.services.notificacion_service import NotificacionService
from app.schemas.common import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register-token",
    response_model=DispositivoPushRead,
    summary="Registrar token push",
    description="Registra o actualiza un token FCM para notificaciones push."
)
def register_token(
    request: PushTokenRegisterRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Registra un token FCM para el usuario autenticado.
    
    Si el token ya existe, lo actualiza.
    Si existía pero estaba desactivado, lo reactiva.
    
    Roles permitidos: CLIENTE, TALLER, ADMINISTRADOR
    """
    logger.info(f"[PUSH_REGISTER] Usuario {current_user.id_usuario} registrando token - Plataforma: {request.plataforma}")
    logger.debug(f"[PUSH_REGISTER] Token (primeros 20 chars): {request.token_fcm[:20]}...")
    logger.debug(f"[PUSH_REGISTER] Device: {request.device_id}, Nombre: {request.nombre_dispositivo}")
    
    try:
        dispositivo = DispositivoPushService.register_token(
            db=db,
            id_usuario=current_user.id_usuario,
            plataforma=request.plataforma,
            token_fcm=request.token_fcm,
            device_id=request.device_id,
            nombre_dispositivo=request.nombre_dispositivo,
        )
        
        logger.info(f"[PUSH_REGISTER] OK - Dispositivo guardado: {dispositivo.id_dispositivo_push}")

        # Registrar en bitácora
        NotificacionService._registrar_bitacora(
            db=db,
            tipo_actor=current_user.rol,
            id_actor=current_user.id_usuario,
            accion="Registrar token push",
            modulo="Push",
            entidad_afectada="DispositivoPush",
            id_entidad_afectada=dispositivo.id_dispositivo_push,
            resultado=ResultadoAuditoria.EXITO,
            detalle=f"Token registrado para plataforma {request.plataforma.value}",
        )

        return DispositivoPushRead.from_orm(dispositivo)
    
    except Exception as e:
        logger.error(f"[PUSH_REGISTER] ERROR - {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registrando token: {str(e)}")


@router.post(
    "/unregister-token",
    response_model=MessageResponse,
    summary="Desregistrar token push",
    description="Desactiva un token FCM."
)
def unregister_token(
    request: PushTokenUnregisterRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Desregistra un token FCM (lo marca como inactivo).
    
    Roles permitidos: CLIENTE, TALLER, ADMINISTRADOR
    """
    success = DispositivoPushService.unregister_token(
        db=db,
        id_usuario=current_user.id_usuario,
        token_fcm=request.token_fcm
    )

    if not success:
        raise HTTPException(status_code=404, detail="Token no encontrado")

    # Registrar en bitácora
    NotificacionService._registrar_bitacora(
        db=db,
        tipo_actor=current_user.rol,
        id_actor=current_user.id_usuario,
        accion="Desregistrar token push",
        modulo="Push",
        entidad_afectada="DispositivoPush",
        resultado=ResultadoAuditoria.EXITO,
        detalle=f"Token desactivado: {request.token_fcm[:20]}...",
    )

    return MessageResponse(message="Token desregistrado correctamente")


@router.get(
    "/mis-dispositivos",
    response_model=DispositivoPushListResponse,
    summary="Listar dispositivos registrados",
    description="Lista todos los dispositivos push registrados del usuario."
)
def list_my_devices(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista todos los dispositivos push del usuario autenticado.
    
    Roles permitidos: CLIENTE, TALLER, ADMINISTRADOR
    """
    dispositivos = DispositivoPushService.list_devices_for_user(
        db=db,
        id_usuario=current_user.id_usuario
    )

    return DispositivoPushListResponse(
        dispositivos=[DispositivoPushRead.from_orm(d) for d in dispositivos],
        total=len(dispositivos)
    )


@router.get(
    "/mi-estado",
    summary="Estado de push notifications del usuario",
    description="Devuelve diagnóstico rápido del estado de push para el usuario autenticado."
)
def get_push_status(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Devuelve estado de push para diagnóstico.
    
    Roles permitidos: CLIENTE, TALLER, ADMINISTRADOR
    """
    from app.core.config import settings
    
    dispositivos = DispositivoPushService.list_devices_for_user(
        db=db,
        id_usuario=current_user.id_usuario
    )
    
    dispositivos_activos = [d for d in dispositivos if d.activo]
    
    logger.info(f"[PUSH_STATUS] Usuario {current_user.id_usuario}: {len(dispositivos_activos)} dispositivos activos de {len(dispositivos)} totales")
    
    return {
        "usuario_id": str(current_user.id_usuario),
        "tokens_activos": len(dispositivos_activos),
        "tokens_totales": len(dispositivos),
        "fcm_enabled": settings.FCM_ENABLED,
        "firebase_configurado": bool(settings.FIREBASE_CREDENTIALS_JSON or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        "dispositivos": [
            {
                "id": str(d.id_dispositivo_push),
                "plataforma": d.plataforma.value if d.plataforma else None,
                "activo": d.activo,
                "dispositivo": d.nombre_dispositivo or "Desconocido",
            }
            for d in dispositivos
        ]
    }
