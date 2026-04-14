from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import (
    RolUsuario,
    EstadoAprobacionTaller,
    EstadoOperativoTaller,
)
from app.models.usuario import Usuario
from app.schemas.workshop import (
    TallerCreate,
    TallerRead,
    TallerUpdate,
    TallerAdminListItem,
    TallerAdminDetail,
    TallerAdminUpdate,
    TallerDecisionRequest,
    TallerEstadoResponse,
    TallerPerfilUpdate,
    TallerPerfilResponse,
)
from app.services.taller_service import TallerService


router = APIRouter(dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.TALLER))])


@router.get("", response_model=list[TallerRead])
def list_talleres(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista talleres.
    - ADMINISTRADOR: Ve todos los talleres
    - TALLER: Solo ve su propio perfil
    """
    return TallerService.list_talleres(db, current_user)


@router.post("", response_model=TallerRead, status_code=status.HTTP_201_CREATED)
def create_taller(
    payload: TallerCreate, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea un nuevo taller (solo ADMINISTRADOR).
    Los talleres normales se crean mediante el endpoint de solicitud de registro.
    """
    return TallerService.create_taller(db, payload.model_dump(), current_user)


# ============================================================================
# ENDPOINTS ADMINISTRATIVOS PARA GESTIÓN DE TALLERES
# ============================================================================


@router.get("/admin", response_model=list[TallerAdminListItem])
def list_talleres_admin(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
    estado_aprobacion: EstadoAprobacionTaller | None = Query(None),
    estado_operativo: EstadoOperativoTaller | None = Query(None),
    es_activo: bool | None = Query(None),
    nombre_taller: str | None = Query(None),
    nit: str | None = Query(None),
    correo: str | None = Query(None),
):
    """
    Lista talleres registrados con filtros administrativos.
    Solo ADMINISTRADOR puede acceder.
    
    Filtros opcionales:
    - estado_aprobacion: PENDIENTE, APROBADO, RECHAZADO
    - estado_operativo: DISPONIBLE, NO_DISPONIBLE, SUSPENDIDO
    - es_activo: true/false
    - nombre_taller: búsqueda parcial
    - nit: búsqueda exacta
    - correo: búsqueda parcial
    """
    talleres = TallerService.list_talleres_admin(
        db=db,
        current_user=current_user,
        estado_aprobacion=estado_aprobacion,
        estado_operativo=estado_operativo,
        es_activo=es_activo,
        nombre_taller=nombre_taller,
        nit=nit,
        correo=correo,
    )
    
    # Enriquecer respuesta con datos del usuario
    resultado = []
    for taller in talleres:
        item = TallerAdminListItem(
            id_taller=taller.id_taller,
            id_usuario=taller.id_usuario,
            nombre_taller=taller.nombre_taller,
            razon_social=taller.razon_social,
            nit=taller.nit,
            telefono=taller.telefono,
            correo=taller.usuario.correo if taller.usuario else "",
            estado_aprobacion=taller.estado_aprobacion,
            estado_operativo=taller.estado_operativo,
            es_activo=taller.usuario.es_activo if taller.usuario else False,
            fecha_registro=taller.fecha_registro,
            fecha_aprobacion=taller.fecha_aprobacion,
        )
        resultado.append(item)
    
    return resultado


@router.get("/admin/{taller_id}", response_model=TallerAdminDetail)
def get_taller_admin_detail(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Obtiene el detalle administrativo completo de un taller.
    Solo ADMINISTRADOR puede acceder.
    """
    taller = TallerService.get_taller_admin_detail(db, taller_id, current_user)
    
    return TallerAdminDetail(
        id_taller=taller.id_taller,
        id_usuario=taller.id_usuario,
        nombre_taller=taller.nombre_taller,
        razon_social=taller.razon_social,
        nit=taller.nit,
        telefono=taller.telefono,
        direccion=taller.direccion,
        latitud=taller.latitud,
        longitud=taller.longitud,
        descripcion=taller.descripcion,
        estado_aprobacion=taller.estado_aprobacion,
        estado_operativo=taller.estado_operativo,
        fecha_registro=taller.fecha_registro,
        fecha_aprobacion=taller.fecha_aprobacion,
        correo=taller.usuario.correo if taller.usuario else "",
        es_activo=taller.usuario.es_activo if taller.usuario else False,
    )


@router.patch("/admin/{taller_id}", response_model=TallerAdminDetail)
def update_taller_admin(
    taller_id: UUID,
    payload: TallerAdminUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Actualiza información administrativa de un taller.
    Solo ADMINISTRADOR puede acceder.
    
    Campos editables:
    - nombre_taller
    - razon_social
    - nit
    - telefono
    - direccion
    - latitud
    - longitud
    - descripcion
    
    Nota: Estados de aprobación y operatividad se gestionan con endpoints específicos.
    """
    taller = TallerService.update_taller_admin(db, taller_id, payload.model_dump(), current_user)
    
    return TallerAdminDetail(
        id_taller=taller.id_taller,
        id_usuario=taller.id_usuario,
        nombre_taller=taller.nombre_taller,
        razon_social=taller.razon_social,
        nit=taller.nit,
        telefono=taller.telefono,
        direccion=taller.direccion,
        latitud=taller.latitud,
        longitud=taller.longitud,
        descripcion=taller.descripcion,
        estado_aprobacion=taller.estado_aprobacion,
        estado_operativo=taller.estado_operativo,
        fecha_registro=taller.fecha_registro,
        fecha_aprobacion=taller.fecha_aprobacion,
        correo=taller.usuario.correo if taller.usuario else "",
        es_activo=taller.usuario.es_activo if taller.usuario else False,
    )


# ============================================================================
# ENDPOINTS DE PERFIL PROPIO DEL TALLER (CASO DE USO: GESTIONAR PERFIL)
# ============================================================================


@router.get("/me", response_model=TallerPerfilResponse)
def get_my_taller_profile(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.TALLER)),
):
    """
    Obtiene el perfil propio del taller autenticado.
    
    Solo accesible por usuarios con rol TALLER.
    Retorna información completa del perfil incluida información del usuario.
    """
    taller = TallerService.get_my_taller_profile(db, current_user)
    
    # Construir respuesta manualmente para incluir correo del usuario
    return TallerPerfilResponse(
        id_taller=taller.id_taller,
        id_usuario=taller.id_usuario,
        nombre_taller=taller.nombre_taller,
        razon_social=taller.razon_social,
        nit=taller.nit,
        telefono=taller.telefono,
        direccion=taller.direccion,
        latitud=taller.latitud,
        longitud=taller.longitud,
        descripcion=taller.descripcion,
        estado_aprobacion=taller.estado_aprobacion,
        estado_operativo=taller.estado_operativo,
        fecha_registro=taller.fecha_registro,
        fecha_aprobacion=taller.fecha_aprobacion,
        correo=taller.usuario.correo if taller.usuario else None,
    )


@router.patch("/me", response_model=TallerPerfilResponse)
def update_my_taller_profile(
    payload: TallerPerfilUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.TALLER)),
):
    """
    Actualiza el perfil propio del taller autenticado.
    
    Solo accesible por usuarios con rol TALLER.
    
    Campos permitidos para edición:
    - nombre_taller
    - razon_social
    - nit
    - telefono
    - direccion
    - latitud
    - longitud
    - descripcion
    
    Campos que NO se pueden modificar:
    - estado_aprobacion
    - estado_operativo
    - id_usuario
    - fecha_aprobacion
    
    Precondiciones:
    - El taller debe estar APROBADO (estado_aprobacion == "APROBADO")
    
    Efectos:
    - Actualiza la información del taller en base de datos
    - Registra la acción en bitácora
    - Retorna el perfil actualizado
    """
    taller = TallerService.update_my_taller_profile(db, current_user, payload.model_dump())
    
    # Construir respuesta manualmente para incluir correo del usuario
    return TallerPerfilResponse(
        id_taller=taller.id_taller,
        id_usuario=taller.id_usuario,
        nombre_taller=taller.nombre_taller,
        razon_social=taller.razon_social,
        nit=taller.nit,
        telefono=taller.telefono,
        direccion=taller.direccion,
        latitud=taller.latitud,
        longitud=taller.longitud,
        descripcion=taller.descripcion,
        estado_aprobacion=taller.estado_aprobacion,
        estado_operativo=taller.estado_operativo,
        fecha_registro=taller.fecha_registro,
        fecha_aprobacion=taller.fecha_aprobacion,
        correo=taller.usuario.correo if taller.usuario else None,
    )


# ============================================================================
# ENDPOINTS DE GESTIÓN OPERATIVA (DINÁMICOS)
# ============================================================================


@router.get("/{taller_id}", response_model=TallerRead)
def get_taller(
    taller_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene un taller específico.
    - TALLER solo puede acceder a su propio perfil
    - ADMINISTRADOR puede ver cualquier taller
    """
    return TallerService.get_taller(db, taller_id, current_user)


@router.put("/{taller_id}", response_model=TallerRead)
def update_taller(
    taller_id: UUID,
    payload: TallerUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza un taller.
    - TALLER solo puede actualizar su propio perfil
    - ADMINISTRADOR puede actualizar cualquier taller
    """
    return TallerService.update_taller(db, taller_id, payload.model_dump(), current_user)


@router.delete("/{taller_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_taller(
    taller_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Elimina un taller (solo ADMINISTRADOR).
    """
    TallerService.delete_taller(db, taller_id, current_user)


@router.post("/{taller_id}/aprobar", response_model=dict)
def aprobar_taller(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Aprueba un taller pendiente (solo ADMINISTRADOR).
    Automáticamente activa el usuario asociado al taller.
    """
    return TallerService.aprobar_taller(db, taller_id, current_user)


@router.post("/{taller_id}/rechazar", response_model=TallerEstadoResponse)
def rechazar_taller(
    taller_id: UUID,
    payload: TallerDecisionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Rechaza una solicitud de taller pendiente.
    Solo ADMINISTRADOR puede acceder.
    
    Efectos:
    - estado_aprobacion = RECHAZADO
    - estado_operativo = NO_DISPONIBLE
    - usuario.es_activo = False
    - Se registra en bitácora con motivo si se proporciona
    """
    resultado = TallerService.rechazar_taller(
        db=db,
        taller_id=taller_id,
        current_user=current_user,
        motivo=payload.motivo,
    )
    
    return TallerEstadoResponse(
        mensaje=resultado["mensaje"],
        id_taller=resultado["id_taller"],
        estado_aprobacion=resultado["estado_aprobacion"],
        estado_operativo=resultado["estado_operativo"],
        es_activo=resultado["es_activo"],
    )


@router.post("/{taller_id}/habilitar", response_model=TallerEstadoResponse)
def habilitar_taller(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Habilita un taller aprobado para que pueda operar.
    Solo ADMINISTRADOR puede acceder.
    
    Requisito: El taller debe estar en estado APROBADO.
    
    Efectos:
    - estado_operativo = DISPONIBLE
    - usuario.es_activo = True
    - Se registra en bitácora
    """
    resultado = TallerService.habilitar_taller(db, taller_id, current_user)
    
    return TallerEstadoResponse(
        mensaje=resultado["mensaje"],
        id_taller=resultado["id_taller"],
        estado_aprobacion=resultado["estado_aprobacion"],
        estado_operativo=resultado["estado_operativo"],
        es_activo=resultado["es_activo"],
    )


@router.post("/{taller_id}/deshabilitar", response_model=TallerEstadoResponse)
def deshabilitar_taller(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.ADMINISTRADOR)),
):
    """
    Deshabilita un taller aprobado sin eliminarlo.
    Solo ADMINISTRADOR puede acceder.
    
    Requisito: El taller debe estar en estado APROBADO.
    
    Efectos:
    - estado_operativo = SUSPENDIDO (deshabilitación administrativa)
    - No cambia usuario.es_activo (puede reactivarse sin re-aprobación)
    - Se registra en bitácora
    """
    resultado = TallerService.deshabilitar_taller(db, taller_id, current_user)
    
    return TallerEstadoResponse(
        mensaje=resultado["mensaje"],
        id_taller=resultado["id_taller"],
        estado_aprobacion=resultado["estado_aprobacion"],
        estado_operativo=resultado["estado_operativo"],
        es_activo=resultado["es_activo"],
    )
