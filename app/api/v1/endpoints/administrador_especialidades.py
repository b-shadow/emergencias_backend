from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.core.exceptions import bad_request, not_found
from app.models.especialidad import Especialidad
from app.models.usuario import Usuario
from pydantic import BaseModel

router = APIRouter()


class EspecialidadCreate(BaseModel):
    nombre_especialidad: str
    descripcion: str | None = None


class EspecialidadUpdate(BaseModel):
    nombre_especialidad: str | None = None
    descripcion: str | None = None


class EspecialidadResponse(BaseModel):
    id_especialidad: UUID
    nombre_especialidad: str
    descripcion: str | None
    estado: str

    class Config:
        from_attributes = True


@router.post(
    "",
    response_model=EspecialidadResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def crear_especialidad(
    data: EspecialidadCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crear nueva especialidad.
    Solo ADMINISTRADOR puede crear.
    """
    # Validar que no exista especialidad con el mismo nombre
    existente = db.query(Especialidad).filter(
        Especialidad.nombre_especialidad == data.nombre_especialidad
    ).first()
    
    if existente:
        raise bad_request("Ya existe una especialidad con ese nombre")
    
    especialidad = Especialidad(
        nombre_especialidad=data.nombre_especialidad,
        descripcion=data.descripcion,
        estado="ACTIVA"
    )
    db.add(especialidad)
    db.commit()
    db.refresh(especialidad)
    
    return especialidad


@router.get(
    "",
    response_model=list[EspecialidadResponse],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def listar_especialidades(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Listar todas las especialidades.
    Solo ADMINISTRADOR puede acceder.
    """
    return db.query(Especialidad).all()


@router.get(
    "/{especialidad_id}",
    response_model=EspecialidadResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def obtener_especialidad(
    especialidad_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener una especialidad por ID.
    Solo ADMINISTRADOR puede acceder.
    """
    especialidad = db.query(Especialidad).filter(
        Especialidad.id_especialidad == especialidad_id
    ).first()
    
    if not especialidad:
        raise not_found("Especialidad no encontrada")
    
    return especialidad


@router.put(
    "/{especialidad_id}",
    response_model=EspecialidadResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def actualizar_especialidad(
    especialidad_id: UUID,
    data: EspecialidadUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar una especialidad.
    Solo ADMINISTRADOR puede actualizar.
    """
    especialidad = db.query(Especialidad).filter(
        Especialidad.id_especialidad == especialidad_id
    ).first()
    
    if not especialidad:
        raise not_found("Especialidad no encontrada")
    
    # Si se cambió el nombre, validar que no exista otro con ese nombre
    if data.nombre_especialidad and data.nombre_especialidad != especialidad.nombre_especialidad:
        existente = db.query(Especialidad).filter(
            Especialidad.nombre_especialidad == data.nombre_especialidad
        ).first()
        if existente:
            raise bad_request("Ya existe una especialidad con ese nombre")
        especialidad.nombre_especialidad = data.nombre_especialidad
    
    if data.descripcion is not None:
        especialidad.descripcion = data.descripcion
    
    db.commit()
    db.refresh(especialidad)
    
    return especialidad


@router.delete(
    "/{especialidad_id}",
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def eliminar_especialidad(
    especialidad_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Eliminar una especialidad.
    Solo ADMINISTRADOR puede eliminar.
    """
    especialidad = db.query(Especialidad).filter(
        Especialidad.id_especialidad == especialidad_id
    ).first()
    
    if not especialidad:
        raise not_found("Especialidad no encontrada")
    
    db.delete(especialidad)
    db.commit()
    
    return {"mensaje": f"Especialidad '{especialidad.nombre_especialidad}' eliminada correctamente"}
