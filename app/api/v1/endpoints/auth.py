from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import RolUsuario
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
    SubscriptionPlanResponse,
    SubscriptionManagementResponse,
    SubscriptionRenewRequest,
    SubscriptionRenewCheckoutRequest,
    SubscriptionAdminActionResponse,
    TallerRegisterCheckoutRequest,
    TallerRegisterCheckoutResponse,
    TallerRegisterCheckoutValidationResponse,
)
from app.services.auth_service import AuthService
from app.services.stripe_service import StripeService
from app.services.subscription_service import SubscriptionService


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


@router.get("/subscription-plans", response_model=list[SubscriptionPlanResponse], status_code=status.HTTP_200_OK)
def list_subscription_plans(db: Session = Depends(get_db)):
    plans = SubscriptionService.list_active_plans(db)
    return [
        SubscriptionPlanResponse(
            id_plan=str(p.id_plan),
            codigo_plan=p.codigo_plan,
            nombre_plan=p.nombre_plan,
            descripcion=p.descripcion,
            precio_bs=float(p.precio_bs),
            duracion_dias=int(p.duracion_dias),
            precio_mensual_usd=float(p.precio_mensual_usd),
            stripe_price_id=p.stripe_price_id,
        )
        for p in plans
    ]


@router.post("/register-taller/checkout", response_model=TallerRegisterCheckoutResponse, status_code=status.HTTP_201_CREATED)
async def registrar_taller_checkout(payload: TallerRegisterCheckoutRequest, db: Session = Depends(get_db)):
    payload.validar_coincidencia_contrasena()
    plan = SubscriptionService.get_active_plan(db, payload.id_plan)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan de suscripción inválido o inactivo")
    data = await StripeService.create_checkout_session_for_workshop(db, plan, payload.model_dump())
    return TallerRegisterCheckoutResponse(**data)


@router.post("/register-taller/checkout/validate", response_model=TallerRegisterCheckoutValidationResponse, status_code=status.HTTP_200_OK)
async def validate_taller_checkout(session_id: str, token: str, db: Session = Depends(get_db)):
    data = await StripeService.validate_checkout_and_register(db, session_id=session_id, token=token)
    return TallerRegisterCheckoutValidationResponse(**data)


@router.post("/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    raw_payload = await request.body()
    signature = request.headers.get("stripe-signature")
    data = await StripeService.process_webhook_checkout_completed(
        db=db,
        payload=raw_payload,
        signature_header=signature,
    )
    return {"ok": True, **data}


@router.get(
    "/subscriptions/me",
    response_model=SubscriptionManagementResponse,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    taller = SubscriptionService.get_taller_for_user(db, current_user)
    summary = SubscriptionService.get_subscription_summary(db, taller.id_taller)
    return SubscriptionManagementResponse(**summary)


@router.post(
    "/subscriptions/me/renew",
    response_model=SubscriptionManagementResponse,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
def renew_my_subscription(
    payload: SubscriptionRenewRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    taller = SubscriptionService.get_taller_for_user(db, current_user)
    plan = SubscriptionService.get_active_plan(db, payload.id_plan)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan de suscripción inválido o inactivo")
    summary = SubscriptionService.renew_subscription_for_taller(
        db,
        taller=taller,
        plan=plan,
        actor_user=current_user,
    )
    return SubscriptionManagementResponse(**summary)


@router.post(
    "/subscriptions/me/renew/checkout",
    response_model=TallerRegisterCheckoutResponse,
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
async def renew_my_subscription_checkout(
    payload: SubscriptionRenewCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    taller = SubscriptionService.get_taller_for_user(db, current_user)
    plan = SubscriptionService.get_active_plan(db, payload.id_plan)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan de suscripción inválido o inactivo")
    data = await StripeService.create_checkout_session_for_subscription_renewal(
        db,
        taller=taller,
        plan=plan,
        actor_user=current_user,
        frontend_base_url=payload.frontend_base_url,
    )
    return TallerRegisterCheckoutResponse(**data)


@router.post(
    "/subscriptions/me/renew/checkout/validate",
    dependencies=[Depends(require_roles(RolUsuario.TALLER))],
)
async def validate_renewal_checkout(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _ = SubscriptionService.get_taller_for_user(db, current_user)
    return await StripeService.validate_and_apply_subscription_renewal(db, session_id=session_id)


@router.post(
    "/subscriptions/{taller_id}/suspend",
    response_model=SubscriptionAdminActionResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def admin_suspend_subscription(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    data = SubscriptionService.admin_suspend_subscription(db, taller_id, current_user)
    return SubscriptionAdminActionResponse(**data)


@router.post(
    "/subscriptions/{taller_id}/enable",
    response_model=SubscriptionAdminActionResponse,
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)
def admin_enable_subscription(
    taller_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    data = SubscriptionService.admin_enable_subscription(db, taller_id, current_user)
    return SubscriptionAdminActionResponse(**data)


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
