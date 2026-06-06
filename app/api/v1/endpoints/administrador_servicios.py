from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.core.exceptions import bad_request, not_found
from app.models.servicio import Servicio
from app.models.taller import Taller
from app.models.usuario import Usuario
from pydantic import BaseModel
from app.schemas.solicitud_servicio import (
    SolicitudServicioCreate,
    SolicitudServicioResponse,
    SolicitudServicioResolver,
)
from app.services.servicio_service import ServicioService

router = APIRouter()


class ServicioCreate(BaseModel):
    nombre_servicio: str
    descripcion: str | None = None


class ServicioUpdate(BaseModel):
    nombre_servicio: str | None = None
    descripcion: str | None = None


class ServicioResponse(BaseModel):
    id_servicio: UUID
    nombre_servicio: str
    descripcion: str | None
    estado: str

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=ServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def crear_servicio(
    data: ServicioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crear nuevo servicio.
    Solo ADMINISTRADOR puede crear.
    """
    servicio = ServicioService.crear_servicio_global(db, data.nombre_servicio, data.descripcion)
    db.commit()
    db.refresh(servicio)
    return servicio


@router.get(
    "",
    response_model=list[ServicioResponse],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_servicios(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Listar todos los servicios.
    Solo ADMINISTRADOR puede acceder.
    """
    return db.query(Servicio).all()


@router.get(
    "/{servicio_id}",
    response_model=ServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def obtener_servicio(
    servicio_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener un servicio por ID.
    Solo ADMINISTRADOR puede acceder.
    """
    servicio = db.query(Servicio).filter(
        Servicio.id_servicio == servicio_id
    ).first()
    
    if not servicio:
        raise not_found("Servicio no encontrado")
    
    return servicio


@router.put(
    "/{servicio_id}",
    response_model=ServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def actualizar_servicio(
    servicio_id: UUID,
    data: ServicioUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar un servicio.
    Solo ADMINISTRADOR puede actualizar.
    """
    servicio = db.query(Servicio).filter(
        Servicio.id_servicio == servicio_id
    ).first()
    
    if not servicio:
        raise not_found("Servicio no encontrado")
    
    # Si se cambió el nombre, validar que no exista otro con ese nombre
    if data.nombre_servicio and data.nombre_servicio != servicio.nombre_servicio:
        existente = db.query(Servicio).filter(
            Servicio.nombre_servicio == data.nombre_servicio
        ).first()
        if existente:
            raise bad_request("Ya existe un servicio con ese nombre")
        servicio.nombre_servicio = data.nombre_servicio
    
    if data.descripcion is not None:
        servicio.descripcion = data.descripcion
    
    db.commit()
    db.refresh(servicio)
    
    return servicio


@router.delete(
    "/{servicio_id}",
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_servicio(
    servicio_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Eliminar un servicio.
    Solo ADMINISTRADOR puede eliminar.
    """
    servicio = db.query(Servicio).filter(
        Servicio.id_servicio == servicio_id
    ).first()
    
    if not servicio:
        raise not_found("Servicio no encontrado")
    
    db.delete(servicio)
    db.commit()
    
    return {"mensaje": f"Servicio '{servicio.nombre_servicio}' eliminado correctamente"}


@router.get(
    "/solicitudes",
    response_model=list[SolicitudServicioResponse],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_solicitudes_servicio(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    solicitudes = ServicioService.listar_solicitudes_servicio(db)
    return [
        SolicitudServicioResponse(
            id_solicitud_servicio_taller=s.id_solicitud_servicio_taller,
            id_taller=s.id_taller,
            nombre_taller=s.taller.nombre_taller if s.taller else None,
            nombre_servicio=s.nombre_servicio,
            descripcion=s.descripcion,
            estado=s.estado,
            motivo_rechazo=s.motivo_rechazo,
            id_servicio_creado=s.id_servicio_creado,
            fecha_solicitud=s.fecha_solicitud,
            fecha_resolucion=s.fecha_resolucion,
        )
        for s in solicitudes
    ]


@router.post(
    "/solicitudes/{solicitud_id}/aprobar",
    response_model=SolicitudServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def aprobar_solicitud_servicio(
    solicitud_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    solicitud, _ = ServicioService.aprobar_solicitud_servicio(db, solicitud_id, current_user.id_usuario)
    return SolicitudServicioResponse(
        id_solicitud_servicio_taller=solicitud.id_solicitud_servicio_taller,
        id_taller=solicitud.id_taller,
        nombre_taller=solicitud.taller.nombre_taller if solicitud.taller else None,
        nombre_servicio=solicitud.nombre_servicio,
        descripcion=solicitud.descripcion,
        estado=solicitud.estado,
        motivo_rechazo=solicitud.motivo_rechazo,
        id_servicio_creado=solicitud.id_servicio_creado,
        fecha_solicitud=solicitud.fecha_solicitud,
        fecha_resolucion=solicitud.fecha_resolucion,
    )


@router.post(
    "/solicitudes/{solicitud_id}/rechazar",
    response_model=SolicitudServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def rechazar_solicitud_servicio(
    solicitud_id: UUID,
    payload: SolicitudServicioResolver,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    solicitud = ServicioService.rechazar_solicitud_servicio(
        db, solicitud_id, current_user.id_usuario, payload.motivo_rechazo
    )
    return SolicitudServicioResponse(
        id_solicitud_servicio_taller=solicitud.id_solicitud_servicio_taller,
        id_taller=solicitud.id_taller,
        nombre_taller=solicitud.taller.nombre_taller if solicitud.taller else None,
        nombre_servicio=solicitud.nombre_servicio,
        descripcion=solicitud.descripcion,
        estado=solicitud.estado,
        motivo_rechazo=solicitud.motivo_rechazo,
        id_servicio_creado=solicitud.id_servicio_creado,
        fecha_solicitud=solicitud.fecha_solicitud,
        fecha_resolucion=solicitud.fecha_resolucion,
    )
