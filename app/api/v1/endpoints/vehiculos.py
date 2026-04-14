from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.vehicle import VehiculoCreate, VehiculoRead, VehiculoUpdate
from app.services.vehiculo_service import VehiculoService


router = APIRouter(dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR, RolUsuario.CLIENTE))])


@router.get("", response_model=list[VehiculoRead])
def list_vehiculos(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista vehículos.
    - ADMINISTRADOR: Ve todos los vehículos del sistema
    - CLIENTE: Solo ve sus propios vehículos
    """
    return VehiculoService.list_vehiculos(db, current_user)


@router.get("/{vehiculo_id}", response_model=VehiculoRead)
def get_vehiculo(
    vehiculo_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene un vehículo específico.
    - CLIENTE solo puede acceder a sus propios vehículos
    - ADMINISTRADOR puede ver cualquier vehículo
    """
    return VehiculoService.get_vehiculo(db, vehiculo_id, current_user)


@router.post("", response_model=VehiculoRead, status_code=status.HTTP_201_CREATED)
def create_vehiculo(
    payload: VehiculoCreate, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea un nuevo vehículo.
    - CLIENTE: Puede crear vehículos asociados a su propio perfil
    - ADMINISTRADOR: Puede crear vehículos para cualquier cliente
    """
    return VehiculoService.create_vehiculo(db, payload.model_dump(), current_user)


@router.put("/{vehiculo_id}", response_model=VehiculoRead)
def update_vehiculo(
    vehiculo_id: UUID,
    payload: VehiculoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza un vehículo.
    - CLIENTE solo puede actualizar sus propios vehículos
    - ADMINISTRADOR puede actualizar cualquier vehículo
    """
    return VehiculoService.update_vehiculo(db, vehiculo_id, payload.model_dump(), current_user)


@router.delete("/{vehiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehiculo(
    vehiculo_id: UUID, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    """
    Elimina un vehículo.
    - CLIENTE solo puede eliminar sus propios vehículos
    - ADMINISTRADOR puede eliminar cualquier vehículo
    """
    VehiculoService.delete_vehiculo(db, vehiculo_id, current_user)
