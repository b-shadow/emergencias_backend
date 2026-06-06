from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.especialidad import (
    EspecialidadResponse,
    TallerEspecialidadResponse,
    TallerEspecialidadCreate,
)
from app.schemas.servicio import (
    ServicioResponse,
    TallerServicioResponse,
    TallerServicioCreate,
)
from app.schemas.solicitud_servicio import (
    SolicitudServicioCreate,
    SolicitudServicioResponse,
)
from app.services.especialidad_service import EspecialidadService
from app.services.servicio_service import ServicioService


router = APIRouter(prefix="/talleres", tags=["Especialidades y Servicios"])


# ============================================================================
# ENDPOINTS PÚBLICOS (SIN RESTRICCIÓN DE ROLES) - Para clientes
# ============================================================================

@router.get(
    "/especialidades/publicas",
    response_model=list[EspecialidadResponse],
)
def get_all_especialidades_publicas(db: Session = Depends(get_db)):
    """
    Obtener todas las especialidades disponibles (master data).
    PÚBLICO - Accesible para cualquier usuario autenticado.
    """
    return EspecialidadService.get_all_especialidades(db)


@router.get(
    "/servicios/publicas",
    response_model=list[ServicioResponse],
)
def get_all_servicios_publicas(db: Session = Depends(get_db)):
    """
    Obtener todos los servicios disponibles (master data).
    PÚBLICO - Accesible para cualquier usuario autenticado.
    """
    return ServicioService.get_all_servicios(db)


# ============================================================================
# ENDPOINTS PARA ESPECIALIDADES
# ============================================================================

@router.get(
    "/especialidades/disponibles",
    response_model=list[EspecialidadResponse],
    dependencies=[Depends(require_roles(RolUsuario.TALLER, RolUsuario.ADMINISTRADOR))],
)
def get_all_especialidades(db: Session = Depends(get_db)):
    """
    Obtener todas las especialidades disponibles (master data).
    Accesible para: TALLER, ADMINISTRADOR
    """
    return EspecialidadService.get_all_especialidades(db)


@router.get(
    "/me/especialidades",
    response_model=list[TallerEspecialidadResponse],
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def get_mi_taller_especialidades(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener especialidades del taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    especialidades = EspecialidadService.get_taller_especialidades(db, taller.id_taller)
    
    # Enriquecer respuesta con nombres y descripción de especialidades
    result = []
    for te in especialidades:
        result.append(
            TallerEspecialidadResponse(
                id_taller_especialidad=te.id_taller_especialidad,
                id_especialidad=te.id_especialidad,
                nombre_especialidad=te.especialidad.nombre_especialidad,
                descripcion=te.especialidad.descripcion,
                estado=te.especialidad.estado,
            )
        )
    return result


@router.post(
    "/me/especialidades",
    response_model=TallerEspecialidadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def add_especialidad_to_mi_taller(
    payload: TallerEspecialidadCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Agregar una especialidad al taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    taller_especialidad = EspecialidadService.add_especialidad_to_taller(
        db=db,
        taller_id=taller.id_taller,
        especialidad_id=payload.id_especialidad,
        usuario_id=current_user.id_usuario,
        rol=current_user.rol,
    )
    
    return TallerEspecialidadResponse(
        id_taller_especialidad=taller_especialidad.id_taller_especialidad,
        id_especialidad=taller_especialidad.id_especialidad,
        nombre_especialidad=taller_especialidad.especialidad.nombre_especialidad,
        descripcion=taller_especialidad.especialidad.descripcion,
        estado=taller_especialidad.especialidad.estado,
    )


@router.delete(
    "/me/especialidades/{id_especialidad}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def remove_especialidad_from_mi_taller(
    id_especialidad: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Remover una especialidad del taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    EspecialidadService.remove_especialidad_from_taller(
        db=db,
        taller_id=taller.id_taller,
        especialidad_id=id_especialidad,
        usuario_id=current_user.id_usuario,
        rol=current_user.rol,
    )


# ============================================================================
# ENDPOINTS PARA SERVICIOS
# ============================================================================

@router.get(
    "/servicios/disponibles",
    response_model=list[ServicioResponse],
    dependencies=[Depends(require_roles(RolUsuario.TALLER, RolUsuario.ADMINISTRADOR))],
)
def get_all_servicios(db: Session = Depends(get_db)):
    """
    Obtener todos los servicios disponibles (master data).
    Accesible para: TALLER, ADMINISTRADOR
    """
    return ServicioService.get_all_servicios(db)


@router.get(
    "/me/servicios",
    response_model=list[TallerServicioResponse],
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def get_mi_taller_servicios(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener servicios del taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    servicios = ServicioService.get_taller_servicios(db, taller.id_taller)
    
    # Enriquecer respuesta con nombres y descripción de servicios
    result = []
    for ts in servicios:
        result.append(
            TallerServicioResponse(
                id_taller_servicio=ts.id_taller_servicio,
                id_servicio=ts.id_servicio,
                nombre_servicio=ts.servicio.nombre_servicio,
                descripcion=ts.servicio.descripcion,
                estado=ts.servicio.estado,
                disponible=ts.disponible,
                observaciones=ts.observaciones,
                categoria_tarifa=ts.categoria_tarifa,
                precio_base=ts.precio_base,
                tipo_pintura_chaperio=ts.tipo_pintura_chaperio,
            )
        )
    return result


@router.post(
    "/me/servicios",
    response_model=TallerServicioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def add_servicio_to_mi_taller(
    payload: TallerServicioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Agregar un servicio al taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    taller_servicio = ServicioService.add_servicio_to_taller(
        db=db,
        taller_id=taller.id_taller,
        servicio_id=payload.id_servicio,
        usuario_id=current_user.id_usuario,
        rol=current_user.rol,
        disponible=payload.disponible,
        observaciones=payload.observaciones,
        categoria_tarifa=payload.categoria_tarifa,
        precio_base=payload.precio_base,
        tipo_pintura_chaperio=payload.tipo_pintura_chaperio,
    )
    
    return TallerServicioResponse(
        id_taller_servicio=taller_servicio.id_taller_servicio,
        id_servicio=taller_servicio.id_servicio,
        nombre_servicio=taller_servicio.servicio.nombre_servicio,
        descripcion=taller_servicio.servicio.descripcion,
        estado=taller_servicio.servicio.estado,
        disponible=taller_servicio.disponible,
        observaciones=taller_servicio.observaciones,
        categoria_tarifa=taller_servicio.categoria_tarifa,
        precio_base=taller_servicio.precio_base,
        tipo_pintura_chaperio=taller_servicio.tipo_pintura_chaperio,
    )


@router.delete(
    "/me/servicios/{id_servicio}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def remove_servicio_from_mi_taller(
    id_servicio: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Remover un servicio del taller del usuario actual.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    ServicioService.remove_servicio_from_taller(
        db=db,
        taller_id=taller.id_taller,
        servicio_id=id_servicio,
        usuario_id=current_user.id_usuario,
        rol=current_user.rol,
    )


@router.patch(
    "/me/servicios/{id_servicio}",
    response_model=TallerServicioResponse,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def update_servicio_disponibilidad(
    id_servicio: UUID,
    payload: TallerServicioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar disponibilidad y observaciones de un servicio.
    Solo accesible para TALLER.
    """
    from app.models.taller import Taller
    
    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")
    
    taller_servicio = ServicioService.update_servicio_disponibilidad(
        db=db,
        taller_id=taller.id_taller,
        servicio_id=id_servicio,
        usuario_id=current_user.id_usuario,
        rol=current_user.rol,
        disponible=payload.disponible,
        observaciones=payload.observaciones,
        categoria_tarifa=payload.categoria_tarifa,
        precio_base=payload.precio_base,
        tipo_pintura_chaperio=payload.tipo_pintura_chaperio,
    )
    
    return TallerServicioResponse(
        id_taller_servicio=taller_servicio.id_taller_servicio,
        id_servicio=taller_servicio.id_servicio,
        nombre_servicio=taller_servicio.servicio.nombre_servicio,
        descripcion=taller_servicio.servicio.descripcion,
        estado=taller_servicio.servicio.estado,
        disponible=taller_servicio.disponible,
        observaciones=taller_servicio.observaciones,
        categoria_tarifa=taller_servicio.categoria_tarifa,
        precio_base=taller_servicio.precio_base,
        tipo_pintura_chaperio=taller_servicio.tipo_pintura_chaperio,
    )


@router.get(
    "/me/servicios/solicitudes",
    response_model=list[SolicitudServicioResponse],
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def get_mis_solicitudes_servicio(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from app.models.taller import Taller

    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")

    solicitudes = ServicioService.listar_solicitudes_servicio(db, taller.id_taller)
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
    "/me/servicios/solicitudes",
    response_model=SolicitudServicioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def solicitar_nuevo_servicio(
    payload: SolicitudServicioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    from app.models.taller import Taller

    taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
    if not taller:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Taller no encontrado para el usuario")

    solicitud = ServicioService.solicitar_nuevo_servicio_taller(
        db=db,
        taller_id=taller.id_taller,
        usuario_id=current_user.id_usuario,
        nombre_servicio=payload.nombre_servicio,
        descripcion=payload.descripcion,
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
