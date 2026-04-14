from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles, get_current_user
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.user import UsuarioCreate, UsuarioRead, UsuarioUpdate, UsuarioRolUpdate
from app.services.usuario_service import UsuarioService


router = APIRouter(dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))])


@router.get("", response_model=list[UsuarioRead])
def list_usuarios(db: Session = Depends(get_db)):
    """Lista todos los usuarios. Solo ADMINISTRADOR."""
    return UsuarioService.list_usuarios(db)


@router.get("/{usuario_id}", response_model=UsuarioRead)
def get_usuario(usuario_id: UUID, db: Session = Depends(get_db)):
    """Obtiene detalles de un usuario específico. Solo ADMINISTRADOR."""
    return UsuarioService.get_usuario(db, usuario_id)


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def create_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Crea un nuevo usuario y registra en bitácora. Solo ADMINISTRADOR."""
    return UsuarioService.create_usuario(db, payload.model_dump(), current_user)


@router.put("/{usuario_id}", response_model=UsuarioRead)
def update_usuario(usuario_id: UUID, payload: UsuarioUpdate, db: Session = Depends(get_db)):
    """Actualiza un usuario. Solo ADMINISTRADOR."""
    return UsuarioService.update_usuario(db, usuario_id, payload.model_dump())


@router.patch("/{usuario_id}/rol", response_model=UsuarioRead)
def change_user_role(
    usuario_id: UUID,
    payload: UsuarioRolUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cambia el rol de un usuario.
    
    **Autorización:**
    - Solo ADMINISTRADOR puede efectuar este cambio
    - Validado en endpoint (via dependencies) y en servicio (dual-layer security)
    
    **Bitácora:**
    - Se registra automáticamente en la bitácora de auditoría
    
    **Request body:**
    ```json
    {
        "rol": "CLIENTE"  // o TALLER o ADMINISTRADOR
    }
    ```
    """
    return UsuarioService.change_user_role(db, usuario_id, payload.rol, current_user)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_usuario(usuario_id: UUID, db: Session = Depends(get_db)):
    """Elimina un usuario. Solo ADMINISTRADOR."""
    UsuarioService.delete_usuario(db, usuario_id)
