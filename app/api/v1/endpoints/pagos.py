from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.schemas.common import MessageResponse
from app.schemas.pago import (
    PagoManualRequest,
    ResumenPagoResponse,
    StripeConfirmRequest,
    StripePaymentIntentRequest,
)
from app.services.pago_service import PagoService


router = APIRouter()


@router.get("/solicitudes/{id_solicitud}/resumen", response_model=ResumenPagoResponse)
def get_resumen_pago(
    id_solicitud: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return PagoService.obtener_resumen(db, id_solicitud, current_user)


@router.post("/solicitudes/{id_solicitud}/stripe/payment-intent")
async def create_payment_intent(
    id_solicitud: UUID,
    payload: StripePaymentIntentRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return await PagoService.crear_pago_stripe(db, id_solicitud, payload.monto, current_user)


@router.post("/solicitudes/{id_solicitud}/stripe/confirm", response_model=ResumenPagoResponse)
async def confirm_payment(
    id_solicitud: UUID,
    payload: StripeConfirmRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return await PagoService.confirmar_pago_stripe(db, id_solicitud, payload.payment_intent_id, current_user)


@router.post("/solicitudes/{id_solicitud}/manual", response_model=MessageResponse)
def register_manual_payment(
    id_solicitud: UUID,
    payload: PagoManualRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    PagoService.registrar_pago_manual_taller(db, id_solicitud, payload.monto, payload.observacion, current_user)
    return MessageResponse(message="Pago manual registrado correctamente")
