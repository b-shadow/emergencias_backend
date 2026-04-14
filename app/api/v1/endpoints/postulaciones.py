from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.schemas.postulacion import (
    PostulacionCreateRequest,
    PostulacionResponse,
    PostulacionResponseWithSolicitud,
    PostulacionActionRequest,
)
from app.schemas.common import MessageResponse
from app.services.postulacion_service import PostulacionService


router = APIRouter()


@router.get("/mis-postulaciones", response_model=list[PostulacionResponseWithSolicitud])
def get_mis_postulaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista las postulaciones del taller actual.
    - Solo TALLER puede acceder a sus propias postulaciones
    - Retorna todas las postulaciones creadas por el taller actual
    - Incluye información de las solicitudes
    """
    return PostulacionService.get_mis_postulaciones(db, current_user)


@router.get("/solicitud/{solicitud_id}", response_model=list[PostulacionResponse])
def list_postulaciones_for_solicitud(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista postulaciones para una solicitud específica.
    - CLIENTE: Solo ve postulaciones de sus propias solicitudes
    - TALLER: Solo ve su propia postulación
    - ADMINISTRADOR: Ve todas
    """
    return PostulacionService.list_postulaciones_for_solicitud(db, solicitud_id, current_user)


@router.get("/{postulacion_id}", response_model=PostulacionResponse)
def get_postulacion(
    postulacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene una postulación específica.
    - CLIENTE: Puede ver postulaciones de sus solicitudes
    - TALLER: Puede ver su propia postulación
    - ADMINISTRADOR: Puede ver cualquiera
    """
    return PostulacionService.get_postulacion(db, postulacion_id, current_user)


@router.post("/solicitud/{solicitud_id}", response_model=PostulacionResponse, status_code=status.HTTP_201_CREATED)
def create_postulacion(
    solicitud_id: UUID,
    payload: PostulacionCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una postulación (TALLER se postula para atender una solicitud).
    - Solo TALLER puede crear postulaciones
    - La solicitud debe estar en estado permitido
    """
    return PostulacionService.create_postulacion(
        db, solicitud_id, payload.model_dump(), current_user
    )


@router.post("/{postulacion_id}/accept", response_model=MessageResponse)
def accept_postulacion(
    postulacion_id: UUID,
    payload: PostulacionActionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Acepta una postulación (CLIENTE selecciona el taller).
    - Solo CLIENTE puede aceptar postulaciones de su solicitud
    - Rechaza automáticamente otras postulaciones
    - Crea asignación
    """
    PostulacionService.accept_postulacion(db, postulacion_id, current_user)
    return MessageResponse(message="Postulación aceptada. Taller asignado correctamente")


@router.post("/{postulacion_id}/reject", response_model=MessageResponse)
def reject_postulacion(
    postulacion_id: UUID,
    payload: PostulacionActionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Rechaza una postulación (CLIENTE desestima el taller).
    - Solo CLIENTE puede rechazar postulaciones de su solicitud
    """
    PostulacionService.reject_postulacion(db, postulacion_id, current_user)
    return MessageResponse(message="Postulación rechazada")


@router.post("/{postulacion_id}/withdraw", response_model=MessageResponse)
def withdraw_postulacion(
    postulacion_id: UUID,
    payload: PostulacionActionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Retira una postulación (TALLER se arrepiente).
    - Solo TALLER propietario puede retirar su postulación
    - Solo si está en estado POSTULADA
    """
    PostulacionService.withdraw_postulacion(db, postulacion_id, current_user)
    return MessageResponse(message="Postulación retirada")
