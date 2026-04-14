from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    ClienteRegisterRequest,
    TallerRegisterRequest,
    LogoutResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def registrar_cliente(payload: ClienteRegisterRequest, db: Session = Depends(get_db)):
    """Registra un nuevo cliente en el sistema"""
    try:
        # Validar concordancia de contraseñas aquí antes de pasar al servicio
        payload.validar_coincidencia_contrasena()
        
        # Construir nombre_completo a partir de nombre y apellido
        nombre_completo = f"{payload.nombre} {payload.apellido}".strip()
        
        return AuthService.registrar_cliente(
            db=db,
            correo=payload.correo,
            contrasena=payload.contrasena,
            confirmar_contrasena=payload.confirmar_contrasena,
            nombre_completo=nombre_completo,
            nombre=payload.nombre,
            apellido=payload.apellido,
            telefono=payload.telefono,
            ci=payload.ci,
            direccion=payload.direccion,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en registro de cliente: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")


@router.post("/register-taller", response_model=dict, status_code=status.HTTP_201_CREATED)
def registrar_taller(payload: TallerRegisterRequest, db: Session = Depends(get_db)):
    """Registra una solicitud de nuevo taller (requiere aprobación del administrador)"""
    # Validar concordancia de contraseñas
    payload.validar_coincidencia_contrasena()
    
    return AuthService.registrar_taller(
        db=db,
        correo=payload.correo,
        contrasena=payload.contrasena,
        confirmar_contrasena=payload.confirmar_contrasena,
        nombre_taller=payload.nombre_taller,
        telefono=payload.telefono,
        direccion=payload.direccion,
        razon_social=payload.razon_social,
        nit=payload.nit,
        latitud=payload.latitud,
        longitud=payload.longitud,
        descripcion=payload.descripcion,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Autentica un usuario y devuelve tokens de acceso"""
    result = AuthService.login(db, correo=payload.correo, contrasena=payload.contrasena, client_type=payload.client_type)
    return TokenResponse(**result)


@router.post("/logout", response_model=LogoutResponse)
def logout(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Cierra la sesión del usuario autenticado"""
    return AuthService.logout(db, current_user)


@router.get("/validate", status_code=status.HTTP_200_OK)
def validate_token(current_user: Usuario = Depends(get_current_user)):
    """Valida que el token de acceso sea válido y devuelve los datos del usuario autenticado"""
    return {
        "valid": True,
        "usuario_id": str(current_user.id_usuario),
        "correo": current_user.correo,
        "nombre_completo": current_user.nombre_completo,
        "rol": current_user.rol.value if current_user.rol else None,
    }


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Inicia proceso de recuperación de contraseña. Envía enlace al correo del usuario."""
    return AuthService.forgot_password(db, correo=payload.correo)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Finaliza la recuperación de contraseña con un token válido"""
    # Validar concordancia de contraseñas
    payload.validar_coincidencia_contrasena()
    
    return AuthService.reset_password(
        db=db,
        token=payload.token,
        nueva_contrasena=payload.nueva_contrasena,
        confirmar_contrasena=payload.confirmar_contrasena,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Refresca el token de acceso usando el refresh token"""
    tokens = AuthService.refresh_access_token(refresh_token=payload.refresh_token)
    return TokenResponse(**tokens)
