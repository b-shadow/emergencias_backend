from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.core.exceptions import bad_request, not_found
from app.models.servicio import Servicio
from app.models.usuario import Usuario
from pydantic import BaseModel

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
    # Validar que no exista servicio con el mismo nombre
    existente = db.query(Servicio).filter(
        Servicio.nombre_servicio == data.nombre_servicio
    ).first()
    
    if existente:
        raise bad_request("Ya existe un servicio con ese nombre")
    
    servicio = Servicio(
        nombre_servicio=data.nombre_servicio,
        descripcion=data.descripcion,
        estado="ACTIVO"
    )
    db.add(servicio)
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
