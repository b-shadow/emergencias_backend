from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import EstadoPostulacion, EstadoSolicitud, RolUsuario
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.asignacion_atencion import AsignacionAtencion
from app.models.cargo_cancelacion_solicitud import CargoCancelacionSolicitud
from app.models.cliente import Cliente
from app.models.cotizacion_atencion import CotizacionAtencion
from app.models.pago_atencion import PagoAtencion
from app.models.politica_cancelacion_taller import PoliticaCancelacionTaller
from app.models.postulacion_taller import PostulacionTaller
from app.models.solicitud_emergencia import SolicitudEmergencia
from app.models.taller import Taller


class PagoService:
    STRIPE_API = "https://api.stripe.com/v1"

    @staticmethod
    def _assert_real_stripe() -> None:
        if not settings.stripe_secret_key:
            raise bad_request("Stripe no está configurado")


    @staticmethod
    def _stripe_headers() -> dict[str, str]:
        PagoService._assert_real_stripe()
        return {"Authorization": f"Bearer {settings.stripe_secret_key}"}

    @staticmethod
    def _get_solicitud_for_user(db: Session, id_solicitud: UUID, current_user):
        solicitud = db.query(SolicitudEmergencia).filter(SolicitudEmergencia.id_solicitud == id_solicitud).first()
        if not solicitud:
            raise not_found("Solicitud no encontrada")
        if current_user.rol == RolUsuario.CLIENTE:
            cliente = db.query(Cliente).filter(Cliente.id_usuario == current_user.id_usuario).first()
            if not cliente or solicitud.id_cliente != cliente.id_cliente:
                raise forbidden("No tienes acceso a esta solicitud")
        if current_user.rol == RolUsuario.TALLER:
            taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
            if not taller:
                raise not_found("Taller no encontrado")
            id_taller_solicitud = PagoService._get_taller_for_solicitud(db, solicitud.id_solicitud)
            if id_taller_solicitud != taller.id_taller:
                raise forbidden("No tienes acceso a esta solicitud")
        return solicitud

    @staticmethod
    def _get_taller_for_solicitud(db: Session, id_solicitud: UUID):
        asignacion = (
            db.query(AsignacionAtencion)
            .filter(AsignacionAtencion.id_solicitud == id_solicitud)
            .order_by(AsignacionAtencion.fecha_asignacion.desc())
            .first()
        )
        if asignacion:
            return asignacion.id_taller
        postulacion = (
            db.query(PostulacionTaller)
            .filter(
                PostulacionTaller.id_solicitud == id_solicitud,
                PostulacionTaller.estado_postulacion == EstadoPostulacion.ACEPTADA,
            )
            .order_by(PostulacionTaller.fecha_postulacion.desc())
            .first()
        )
        return postulacion.id_taller if postulacion else None

    @staticmethod
    def _get_cotizacion_total(db: Session, id_solicitud: UUID) -> tuple[float, UUID | None]:
        postulacion = (
            db.query(PostulacionTaller)
            .filter(
                PostulacionTaller.id_solicitud == id_solicitud,
                PostulacionTaller.estado_postulacion == EstadoPostulacion.ACEPTADA,
            )
            .first()
        )
        if not postulacion:
            return 0.0, None
        cot = db.query(CotizacionAtencion).filter(CotizacionAtencion.id_postulacion == postulacion.id_postulacion).first()
        if not cot:
            return 0.0, postulacion.id_taller
        return float(cot.precio_total_estimado or 0), postulacion.id_taller

    @staticmethod
    def _calcular_resumen(db: Session, solicitud: SolicitudEmergencia):
        total_cotizacion, id_taller_cot = PagoService._get_cotizacion_total(db, solicitud.id_solicitud)
        cargo_row = db.query(CargoCancelacionSolicitud).filter(CargoCancelacionSolicitud.id_solicitud == solicitud.id_solicitud).first()
        cargo_cancelacion = float(cargo_row.monto_cargo) if cargo_row else 0.0

        total_exigible = cargo_cancelacion if solicitud.estado_actual == EstadoSolicitud.CANCELADA and cargo_cancelacion > 0 else total_cotizacion

        pagos = db.query(PagoAtencion).filter(PagoAtencion.id_solicitud == solicitud.id_solicitud, PagoAtencion.estado_pago == "CONFIRMADO").all()
        total_pagado = float(sum(Decimal(str(p.monto or 0)) for p in pagos))
        saldo = max(total_exigible - total_pagado, 0)

        estado_pago = "PENDIENTE"
        if total_exigible > 0 and total_pagado >= total_exigible:
            estado_pago = "PAGADO_TOTAL"
        elif total_pagado > 0:
            estado_pago = "PAGO_PARCIAL"

        return {
            "id_taller": cargo_row.id_taller if cargo_row else id_taller_cot,
            "total_cotizacion": total_cotizacion,
            "cargo_cancelacion": cargo_cancelacion,
            "total_exigible": total_exigible,
            "total_pagado": total_pagado,
            "saldo_pendiente": saldo,
            "estado_pago": estado_pago,
        }

    @staticmethod
    def obtener_resumen(db: Session, id_solicitud: UUID, current_user):
        solicitud = PagoService._get_solicitud_for_user(db, id_solicitud, current_user)
        resumen = PagoService._calcular_resumen(db, solicitud)
        pagos = db.query(PagoAtencion).filter(PagoAtencion.id_solicitud == solicitud.id_solicitud).order_by(PagoAtencion.fecha_registro.desc()).all()
        return {
            "id_solicitud": solicitud.id_solicitud,
            "id_taller": resumen["id_taller"],
            "estado_solicitud": solicitud.estado_actual.value if hasattr(solicitud.estado_actual, "value") else str(solicitud.estado_actual),
            **resumen,
            "pagos": pagos,
        }

    @staticmethod
    async def crear_pago_stripe(db: Session, id_solicitud: UUID, monto: float, current_user):
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo el cliente puede pagar por Stripe")
        solicitud = PagoService._get_solicitud_for_user(db, id_solicitud, current_user)
        resumen = PagoService._calcular_resumen(db, solicitud)
        if monto > resumen["saldo_pendiente"]:
            raise bad_request("El monto no puede superar el saldo pendiente")
        if resumen["id_taller"] is None:
            raise bad_request("No hay taller asociado para procesar el pago")

        minor_units = int(round(monto * 100))
        form_pairs = [
            ("amount", str(minor_units)),
            ("currency", "usd"),
            ("automatic_payment_methods[enabled]", "true"),
            ("metadata[id_solicitud]", str(id_solicitud)),
            ("metadata[id_usuario]", str(current_user.id_usuario)),
        ]

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                f"{PagoService.STRIPE_API}/payment_intents",
                headers=PagoService._stripe_headers() | {"Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode(form_pairs),
            )
        if response.status_code >= 400:
            raise bad_request(f"No se pudo crear el pago en Stripe: {response.text}")
        data = response.json()

        pago = PagoAtencion(
            id_solicitud=id_solicitud,
            id_taller=resumen["id_taller"],
            id_usuario_registra=current_user.id_usuario,
            monto=monto,
            moneda="USD",
            metodo_pago="STRIPE",
            estado_pago="PENDIENTE",
            referencia_externa=data.get("id"),
            observacion="Pago cliente iniciado por Stripe",
        )
        db.add(pago)
        db.commit()
        db.refresh(pago)
        return {
            "id_pago": pago.id_pago,
            "payment_intent_id": data.get("id"),
            "client_secret": data.get("client_secret"),
        }

    @staticmethod
    async def confirmar_pago_stripe(db: Session, id_solicitud: UUID, payment_intent_id: str, current_user):
        if current_user.rol != RolUsuario.CLIENTE:
            raise forbidden("Solo el cliente puede confirmar su pago")
        solicitud = PagoService._get_solicitud_for_user(db, id_solicitud, current_user)
        pago = db.query(PagoAtencion).filter(
            PagoAtencion.id_solicitud == id_solicitud,
            PagoAtencion.referencia_externa == payment_intent_id,
            PagoAtencion.metodo_pago == "STRIPE",
        ).first()
        if not pago:
            raise not_found("Pago Stripe no encontrado")

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(
                f"{PagoService.STRIPE_API}/payment_intents/{payment_intent_id}",
                headers=PagoService._stripe_headers(),
            )
        if response.status_code >= 400:
            raise bad_request(f"No se pudo validar el pago en Stripe: {response.text}")
        intent = response.json()
        status = (intent.get("status") or "").lower()

        if status != "succeeded":
            pago.estado_pago = "FALLIDO"
            db.commit()
            raise bad_request("El pago no está confirmado en Stripe")

        pago.estado_pago = "CONFIRMADO"
        pago.fecha_confirmacion = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(pago)

        return PagoService.obtener_resumen(db, solicitud.id_solicitud, current_user)

    @staticmethod
    def registrar_pago_manual_taller(db: Session, id_solicitud: UUID, monto: float, observacion: str | None, current_user):
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede registrar pagos manuales")
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("Taller no encontrado")

        solicitud = db.query(SolicitudEmergencia).filter(SolicitudEmergencia.id_solicitud == id_solicitud).first()
        if not solicitud:
            raise not_found("Solicitud no encontrada")

        resumen = PagoService._calcular_resumen(db, solicitud)
        if resumen["id_taller"] != taller.id_taller:
            raise forbidden("No puedes registrar pagos para una solicitud de otro taller")
        if monto > float(resumen["saldo_pendiente"]):
            raise bad_request("El monto manual no puede exceder el saldo pendiente")

        pago = PagoAtencion(
            id_solicitud=id_solicitud,
            id_taller=taller.id_taller,
            id_usuario_registra=current_user.id_usuario,
            monto=monto,
            moneda="USD",
            metodo_pago="MANUAL_TALLER",
            estado_pago="CONFIRMADO",
            observacion=observacion or "Pago registrado manualmente por taller",
            fecha_confirmacion=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(pago)
        db.commit()
        db.refresh(pago)
        return pago

    @staticmethod
    def upsert_politica_cancelacion(db: Session, monto_penalidad: float, activa: bool, current_user):
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede configurar política de cancelación")
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("Taller no encontrado")

        row = db.query(PoliticaCancelacionTaller).filter(PoliticaCancelacionTaller.id_taller == taller.id_taller).first()
        if not row:
            row = PoliticaCancelacionTaller(id_taller=taller.id_taller, monto_penalidad=monto_penalidad, activa=activa)
            db.add(row)
        else:
            row.monto_penalidad = monto_penalidad
            row.activa = activa
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_politica_cancelacion(db: Session, current_user):
        if current_user.rol != RolUsuario.TALLER:
            raise forbidden("Solo el taller puede ver su política de cancelación")
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("Taller no encontrado")
        row = db.query(PoliticaCancelacionTaller).filter(PoliticaCancelacionTaller.id_taller == taller.id_taller).first()
        if not row:
            return {"id_taller": taller.id_taller, "monto_penalidad": 0.0, "activa": False, "fecha_actualizacion": None}
        return row


