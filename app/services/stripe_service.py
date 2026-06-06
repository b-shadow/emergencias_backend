import secrets
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ResultadoAuditoria, TipoActor
from app.core.exceptions import bad_request
from app.models.bitacora import Bitacora
from app.models.subscription_plan import SubscriptionPlan
from app.models.taller import Taller
from app.models.taller_subscription import TallerSubscription
from app.models.usuario import Usuario
from app.models.workshop_checkout import WorkshopCheckout
from app.services.auth_service import AuthService
from app.core.security import get_password_hash


class StripeService:
    STRIPE_API = "https://api.stripe.com/v1"

    @staticmethod
    def _assert_real_stripe_config() -> None:
        if not settings.stripe_secret_key:
            raise bad_request("Stripe no está configurado. Define STRIPE_SECRET_KEY en el backend.")


    @staticmethod
    def _auth_headers() -> dict[str, str]:
        StripeService._assert_real_stripe_config()
        return {"Authorization": f"Bearer {settings.stripe_secret_key}"}

    @staticmethod
    def _resolve_frontend_base_url(payload: dict) -> str:
        """Toma el origin real del frontend para evitar redirecciones a puertos incorrectos."""
        raw = (payload.get("frontend_base_url") or settings.frontend_url or "").strip()
        if not raw:
            raise bad_request("No se pudo determinar FRONTEND_URL para redirecciÃ³n Stripe.")
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise bad_request("frontend_base_url invÃ¡lido para Stripe.")
        return raw.rstrip("/")

    @staticmethod
    def _parse_stripe_signature(signature_header: str) -> tuple[str | None, str | None]:
        parts = [p.strip() for p in signature_header.split(",") if "=" in p]
        data = dict(p.split("=", 1) for p in parts)
        return data.get("t"), data.get("v1")

    @staticmethod
    def _append_line_item_from_plan(form_pairs: list[tuple[str, str]], plan: SubscriptionPlan) -> None:
        form_pairs.append(("line_items[0][quantity]", "1"))
        if plan.stripe_price_id:
            form_pairs.append(("line_items[0][price]", plan.stripe_price_id))
            return

        bs_amount = Decimal(str(plan.precio_bs or 0))
        if bs_amount <= 0:
            raise bad_request(
                f"El plan {plan.codigo_plan} no tiene stripe_price_id y su precio en Bs es inválido."
            )
        unit_amount_cents = int((bs_amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        form_pairs.extend(
            [
                ("line_items[0][price_data][currency]", "bob"),
                ("line_items[0][price_data][unit_amount]", str(unit_amount_cents)),
                ("line_items[0][price_data][product_data][name]", plan.nombre_plan),
                (
                    "line_items[0][price_data][product_data][description]",
                    plan.descripcion or f"Suscripción {plan.codigo_plan}",
                ),
            ]
        )

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
        if not settings.stripe_webhook_secret:
            raise bad_request("Stripe webhook no configurado. Define STRIPE_WEBHOOK_SECRET.")
        if not signature_header:
            return False
        ts, sig = StripeService._parse_stripe_signature(signature_header)
        if not ts or not sig:
            return False
        signed_payload = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
        computed = hmac.new(
            settings.stripe_webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, sig)

    @staticmethod
    async def create_checkout_session_for_workshop(
        db: Session, plan: SubscriptionPlan, payload: dict
    ) -> dict:
        StripeService._assert_real_stripe_config()

        token = secrets.token_urlsafe(24)
        payload_to_store = dict(payload)
        plain_password = payload_to_store.pop("contrasena", None)
        payload_to_store.pop("confirmar_contrasena", None)
        if not plain_password:
            raise bad_request("La contraseÃ±a es obligatoria para continuar con el registro.")
        payload_to_store["contrasena_hash"] = get_password_hash(plain_password)

        checkout = WorkshopCheckout(
            id_plan=plan.id_plan,
            checkout_token=token,
            estado_checkout="PENDIENTE",
            correo_taller=payload["correo"],
            registro_payload=payload_to_store,
        )
        db.add(checkout)
        db.flush()
        db.add(
            Bitacora(
                tipo_actor=TipoActor.TALLER,
                id_actor=None,
                accion="Registro de compra SaaS (pendiente de pago)",
                modulo="Suscripciones SaaS",
                entidad_afectada="WorkshopCheckout",
                id_entidad_afectada=checkout.id_checkout,
                resultado=ResultadoAuditoria.EXITO,
                detalle=f"Checkout creado para plan {plan.codigo_plan} ({plan.nombre_plan}). Correo: {payload['correo']}",
            )
        )

        frontend_base_url = StripeService._resolve_frontend_base_url(payload)
        success_url = (
            f"{frontend_base_url}/auth/register-taller/stripe/validate?"
            f"session_id={{CHECKOUT_SESSION_ID}}&token={token}"
        )
        cancel_url = f"{frontend_base_url}/auth/register-taller?payment=cancelled"

        form_pairs: list[tuple[str, str]] = [
            ("success_url", success_url),
            ("cancel_url", cancel_url),
            ("mode", "payment"),
            ("customer_email", payload["correo"]),
            ("metadata[checkout_token]", token),
            ("metadata[id_plan]", str(plan.id_plan)),
        ]
        StripeService._append_line_item_from_plan(form_pairs, plan)

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                f"{StripeService.STRIPE_API}/checkout/sessions",
                headers=StripeService._auth_headers() | {"Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode(form_pairs),
            )
        if response.status_code >= 400:
            db.rollback()
            raise bad_request(f"No se pudo crear checkout Stripe: {response.text}")

        data = response.json()
        checkout.stripe_session_id = data.get("id")
        db.commit()

        return {
            "checkout_url": data.get("url"),
            "checkout_token": token,
            "estado": "PENDIENTE_PAGO",
        }

    @staticmethod
    async def validate_checkout_and_register(
        db: Session, session_id: str, token: str
    ) -> dict:
        checkout = (
            db.query(WorkshopCheckout)
            .filter(WorkshopCheckout.checkout_token == token)
            .first()
        )
        if not checkout:
            raise bad_request("Token de checkout invÃ¡lido")
        if checkout.stripe_session_id != session_id:
            raise bad_request("SesiÃ³n Stripe no corresponde al token recibido")

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(
                f"{StripeService.STRIPE_API}/checkout/sessions/{session_id}",
                headers=StripeService._auth_headers(),
            )
        if response.status_code >= 400:
            raise bad_request(f"No se pudo validar sesiÃ³n Stripe: {response.text}")

        sess = response.json()
        status = (sess.get("status") or "").lower()
        payment_status = (sess.get("payment_status") or "").lower()

        if status != "complete" or payment_status not in {"paid", "no_payment_required"}:
            checkout.estado_checkout = "FALLIDO"
            checkout.fecha_validacion = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            raise bad_request("El pago aÃºn no estÃ¡ confirmado por Stripe.")

        if checkout.id_taller_creado and checkout.id_usuario_creado:
            return {
                "estado": "PAGADO_Y_REGISTRADO",
                "mensaje": "Pago validado y solicitud de taller ya registrada previamente.",
                "correo": checkout.correo_taller,
            }

        payload = dict(checkout.registro_payload or {})
        AuthService.registrar_taller(
            db=db,
            correo=payload["correo"],
            contrasena=None,
            confirmar_contrasena=None,
            contrasena_hash=payload["contrasena_hash"],
            nombre_taller=payload["nombre_taller"],
            telefono=payload["telefono"],
            direccion=payload["direccion"],
            razon_social=payload.get("razon_social"),
            nit=payload.get("nit"),
            latitud=payload.get("latitud"),
            longitud=payload.get("longitud"),
            descripcion=payload.get("descripcion"),
        )

        user = db.query(Usuario).filter(Usuario.correo == payload["correo"]).first()
        taller = db.query(Taller).filter(Taller.id_usuario == user.id_usuario).first() if user else None

        checkout.estado_checkout = "PAGADO"
        checkout.id_usuario_creado = user.id_usuario if user else None
        checkout.id_taller_creado = taller.id_taller if taller else None
        checkout.fecha_validacion = datetime.now(timezone.utc).replace(tzinfo=None)

        if taller:
            active_subs = (
                db.query(TallerSubscription)
                .filter(TallerSubscription.id_taller == taller.id_taller, TallerSubscription.estado == "ACTIVA")
                .all()
            )
            for item in active_subs:
                item.estado = "FINALIZADA"
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id_plan == checkout.id_plan).first()
            start = datetime.now(timezone.utc).replace(tzinfo=None)
            end = start + timedelta(days=int(plan.duracion_dias if plan else 30))
            new_sub = TallerSubscription(
                id_taller=taller.id_taller,
                id_plan=checkout.id_plan,
                estado="ACTIVA",
                fecha_inicio=start,
                fecha_fin=end,
            )
            db.add(new_sub)
            db.add(
                Bitacora(
                    tipo_actor=TipoActor.SISTEMA,
                    id_actor=user.id_usuario if user else None,
                    accion="Compra SaaS confirmada",
                    modulo="Suscripciones SaaS",
                    entidad_afectada="TallerSubscription",
                    id_entidad_afectada=new_sub.id_subscription,
                    resultado=ResultadoAuditoria.EXITO,
                    detalle=f"Pago confirmado y taller asociado al plan {plan.codigo_plan if plan else 'N/A'}",
                )
            )
        db.commit()

        return {
            "estado": "PAGADO_Y_REGISTRADO",
            "mensaje": "Pago validado. Tu solicitud de taller estÃ¡ registrada y pendiente de aprobaciÃ³n.",
            "correo": payload["correo"],
        }

    @staticmethod
    async def process_webhook_checkout_completed(
        db: Session, payload: bytes, signature_header: str | None
    ) -> dict:
        if not StripeService.verify_webhook_signature(payload, signature_header):
            raise bad_request("Firma de webhook Stripe invÃ¡lida")
        event = json.loads(payload.decode("utf-8"))
        event_type = event.get("type")
        if event_type != "checkout.session.completed":
            return {"estado": "IGNORADO", "mensaje": f"Evento {event_type} ignorado"}
        session_obj = (event.get("data") or {}).get("object") or {}
        session_id = session_obj.get("id")
        metadata = session_obj.get("metadata") or {}
        action = metadata.get("action")
        if action == "renew_subscription":
            return await StripeService.complete_renewal_from_checkout_metadata(db, metadata, session_id=session_id)

        token = metadata.get("checkout_token")
        if not session_id or not token:
            raise bad_request("Evento Stripe incompleto: faltan session_id o checkout_token")
        return await StripeService.validate_checkout_and_register(db, session_id=session_id, token=token)

    @staticmethod
    async def create_checkout_session_for_subscription_renewal(
        db: Session,
        *,
        taller: Taller,
        plan: SubscriptionPlan,
        actor_user: Usuario,
        frontend_base_url: str | None,
    ) -> dict:
        StripeService._assert_real_stripe_config()
        payload = {"frontend_base_url": frontend_base_url}
        base = StripeService._resolve_frontend_base_url(payload)
        success_url = f"{base}/workshops/subscription?renewal=processing&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}/workshops/subscription?renewal=cancelled"

        form_pairs: list[tuple[str, str]] = [
            ("success_url", success_url),
            ("cancel_url", cancel_url),
            ("mode", "payment"),
            ("metadata[action]", "renew_subscription"),
            ("metadata[id_taller]", str(taller.id_taller)),
            ("metadata[id_plan]", str(plan.id_plan)),
            ("metadata[id_actor_usuario]", str(actor_user.id_usuario)),
        ]
        StripeService._append_line_item_from_plan(form_pairs, plan)

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                f"{StripeService.STRIPE_API}/checkout/sessions",
                headers=StripeService._auth_headers() | {"Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode(form_pairs),
            )
        if response.status_code >= 400:
            raise bad_request(f"No se pudo crear checkout Stripe para renovación: {response.text}")
        data = response.json()
        return {
            "checkout_url": data.get("url"),
            "checkout_token": "",
            "estado": "PENDIENTE_PAGO",
        }

    @staticmethod
    async def _update_checkout_session_metadata(session_id: str, metadata: dict[str, str]) -> None:
        form_pairs: list[tuple[str, str]] = []
        for key, value in metadata.items():
            form_pairs.append((f"metadata[{key}]", value))
        async with httpx.AsyncClient(timeout=25.0) as client:
            await client.post(
                f"{StripeService.STRIPE_API}/checkout/sessions/{session_id}",
                headers=StripeService._auth_headers() | {"Content-Type": "application/x-www-form-urlencoded"},
                content=urlencode(form_pairs),
            )

    @staticmethod
    async def complete_renewal_from_checkout_metadata(db: Session, metadata: dict, session_id: str | None = None) -> dict:
        from app.services.subscription_service import SubscriptionService

        if metadata.get("renewal_applied") == "1":
            return {
                "estado": "RENOVACION_YA_APLICADA",
                "mensaje": "La renovación ya había sido aplicada previamente.",
            }

        id_taller = metadata.get("id_taller")
        id_plan = metadata.get("id_plan")
        id_actor_usuario = metadata.get("id_actor_usuario")
        if not id_taller or not id_plan:
            raise bad_request("Metadata incompleta para renovación de suscripción")

        taller = db.query(Taller).filter(Taller.id_taller == id_taller).first()
        if not taller:
            raise bad_request("Taller no encontrado para renovación")
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id_plan == id_plan).first()
        if not plan or not plan.es_activo:
            raise bad_request("Plan no válido para renovación")

        actor_user = None
        if id_actor_usuario:
            actor_user = db.query(Usuario).filter(Usuario.id_usuario == id_actor_usuario).first()
        if actor_user is None:
            actor_user = db.query(Usuario).filter(Usuario.id_usuario == taller.id_usuario).first()
        if actor_user is None:
            raise bad_request("No se pudo identificar el actor para registrar la renovación")

        summary = SubscriptionService.renew_subscription_for_taller(
            db,
            taller=taller,
            plan=plan,
            actor_user=actor_user,
        )
        if session_id:
            await StripeService._update_checkout_session_metadata(
                session_id,
                {"renewal_applied": "1"},
            )
        return {
            "estado": "RENOVACION_APLICADA",
            "mensaje": "Renovación aplicada correctamente",
            "id_taller": str(taller.id_taller),
            "resumen": summary,
        }

    @staticmethod
    async def validate_and_apply_subscription_renewal(db: Session, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(
                f"{StripeService.STRIPE_API}/checkout/sessions/{session_id}",
                headers=StripeService._auth_headers(),
            )
        if response.status_code >= 400:
            raise bad_request(f"No se pudo validar sesión Stripe: {response.text}")

        sess = response.json()
        status = (sess.get("status") or "").lower()
        payment_status = (sess.get("payment_status") or "").lower()
        if status != "complete" or payment_status not in {"paid", "no_payment_required"}:
            raise bad_request("El pago aún no está confirmado por Stripe.")

        metadata = sess.get("metadata") or {}
        if metadata.get("action") != "renew_subscription":
            raise bad_request("La sesión Stripe no corresponde a renovación de suscripción.")
        return await StripeService.complete_renewal_from_checkout_metadata(db, metadata, session_id=session_id)



