from collections.abc import Callable
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import RolUsuario
from app.core.exceptions import forbidden, unauthorized
from app.models.usuario import Usuario


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Usuario:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if token_type != "access" or user_id is None:
            raise unauthorized()
    except JWTError as exc:
        raise unauthorized() from exc

    user = db.query(Usuario).filter(Usuario.id_usuario == UUID(user_id)).first()
    if user is None or not user.es_activo:
        raise unauthorized("Usuario inactivo o no existente")
    return user


def require_roles(*allowed_roles: RolUsuario) -> Callable:
    def _validator(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in allowed_roles:
            raise forbidden()
        return current_user

    return _validator
