from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EstadoOperativoTaller, ResultadoAuditoria, TipoActor
from app.core.exceptions import bad_request, forbidden, not_found
from app.models.bitacora import Bitacora
from app.models.subscription_plan import SubscriptionPlan
from app.models.taller import Taller
from app.models.taller_subscription import TallerSubscription
from app.models.usuario import Usuario


class SubscriptionService:
    @staticmethod
    def list_active_plans(db: Session) -> list[SubscriptionPlan]:
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.es_activo.is_(True))
            .order_by(SubscriptionPlan.precio_mensual_usd.asc())
            .all()
        )

    @staticmethod
    def get_active_plan(db: Session, id_plan: str) -> SubscriptionPlan | None:
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.id_plan == id_plan, SubscriptionPlan.es_activo.is_(True))
            .first()
        )

    @staticmethod
    def _now_naive_utc() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _to_naive_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _log_subscription_event(
        db: Session,
        *,
        actor_type: TipoActor,
        actor_id: UUID | None,
        action: str,
        detail: str,
        entity_id: UUID | None = None,
        result: ResultadoAuditoria = ResultadoAuditoria.EXITO,
    ) -> None:
        db.add(
            Bitacora(
                tipo_actor=actor_type,
                id_actor=actor_id,
                accion=action,
                modulo="Suscripciones SaaS",
                entidad_afectada="TallerSubscription",
                id_entidad_afectada=entity_id,
                resultado=result,
                detalle=detail,
            )
        )

    @staticmethod
    def get_taller_for_user(db: Session, current_user: Usuario) -> Taller:
        if current_user.rol.value != "TALLER":
            raise forbidden("Solo un taller puede consultar su suscripción.")
        taller = db.query(Taller).filter(Taller.id_usuario == current_user.id_usuario).first()
        if not taller:
            raise not_found("No se encontró taller asociado al usuario autenticado")
        return taller

    @staticmethod
    def get_subscription_summary(db: Session, id_taller: UUID) -> dict:
        now = SubscriptionService._now_naive_utc()
        active = (
            db.query(TallerSubscription, SubscriptionPlan)
            .join(SubscriptionPlan, SubscriptionPlan.id_plan == TallerSubscription.id_plan)
            .filter(TallerSubscription.id_taller == id_taller)
            .order_by(TallerSubscription.fecha_creacion.desc())
            .all()
        )
        historial = []
        for sub, plan in active:
            fecha_inicio = SubscriptionService._to_naive_utc(sub.fecha_inicio)
            fecha_fin = SubscriptionService._to_naive_utc(sub.fecha_fin)
            dias = (fecha_fin - now).days if fecha_fin else None
            historial.append(
                {
                    "id_subscription": str(sub.id_subscription),
                    "id_plan": str(sub.id_plan),
                    "nombre_plan": plan.nombre_plan,
                    "codigo_plan": plan.codigo_plan,
                    "estado": sub.estado,
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "fecha_creacion": sub.fecha_creacion,
                    "dias_restantes": dias,
                }
            )

        current = next(
            (
                item
                for item in historial
                if item["estado"] == "ACTIVA" and item["fecha_inicio"] <= now <= item["fecha_fin"]
            ),
            historial[0] if historial else None,
        )
        return {
            "id_taller": str(id_taller),
            "plan_actual": current["nombre_plan"] if current else None,
            "codigo_plan_actual": current["codigo_plan"] if current else None,
            "estado_suscripcion": current["estado"] if current else None,
            "fecha_inicio": current["fecha_inicio"] if current else None,
            "fecha_fin": current["fecha_fin"] if current else None,
            "dias_restantes": current["dias_restantes"] if current else None,
            "historial": historial,
        }

    @staticmethod
    def renew_subscription_for_taller(
        db: Session,
        *,
        taller: Taller,
        plan: SubscriptionPlan,
        actor_user: Usuario,
    ) -> dict:
        now = SubscriptionService._now_naive_utc()
        active = (
            db.query(TallerSubscription)
            .filter(
                TallerSubscription.id_taller == taller.id_taller,
                TallerSubscription.estado == "ACTIVA",
                TallerSubscription.fecha_inicio <= now,
                TallerSubscription.fecha_fin >= now,
            )
            .first()
        )
        if active:
            active.estado = "FINALIZADA"

        start = now
        end = start + timedelta(days=int(plan.duracion_dias))
        new_sub = TallerSubscription(
            id_taller=taller.id_taller,
            id_plan=plan.id_plan,
            estado="ACTIVA",
            fecha_inicio=start,
            fecha_fin=end,
        )
        db.add(new_sub)
        taller.estado_operativo = EstadoOperativoTaller.DISPONIBLE
        SubscriptionService._log_subscription_event(
            db,
            actor_type=TipoActor.TALLER if actor_user.rol.value == "TALLER" else TipoActor.ADMINISTRADOR,
            actor_id=actor_user.id_usuario,
            action="Renovación de suscripción SaaS",
            detail=f"Taller {taller.nombre_taller} renovó al plan {plan.codigo_plan} ({plan.nombre_plan})",
            entity_id=new_sub.id_subscription,
        )
        db.commit()
        return SubscriptionService.get_subscription_summary(db, taller.id_taller)

    @staticmethod
    def _latest_subscription(db: Session, id_taller: UUID) -> TallerSubscription | None:
        return (
            db.query(TallerSubscription)
            .filter(TallerSubscription.id_taller == id_taller)
            .order_by(TallerSubscription.fecha_creacion.desc())
            .first()
        )

    @staticmethod
    def admin_suspend_subscription(db: Session, id_taller: UUID, actor_user: Usuario) -> dict:
        taller = db.query(Taller).filter(Taller.id_taller == id_taller).first()
        if not taller:
            raise not_found("Taller no encontrado")
        sub = SubscriptionService._latest_subscription(db, id_taller)
        if not sub:
            raise bad_request("El taller no tiene suscripciones registradas")
        if sub.estado == "SUSPENDIDA":
            raise bad_request("La suscripción ya se encuentra suspendida")
        sub.estado = "SUSPENDIDA"
        taller.estado_operativo = EstadoOperativoTaller.SUSPENDIDO
        SubscriptionService._log_subscription_event(
            db,
            actor_type=TipoActor.ADMINISTRADOR,
            actor_id=actor_user.id_usuario,
            action="Suspensión de suscripción SaaS",
            detail=f"Administrador suspendió suscripción del taller {taller.nombre_taller}",
            entity_id=sub.id_subscription,
        )
        db.commit()
        return {
            "mensaje": "Suscripción suspendida correctamente",
            "id_taller": str(taller.id_taller),
            "estado_suscripcion": sub.estado,
            "estado_operativo_taller": taller.estado_operativo.value,
        }

    @staticmethod
    def admin_enable_subscription(db: Session, id_taller: UUID, actor_user: Usuario) -> dict:
        taller = db.query(Taller).filter(Taller.id_taller == id_taller).first()
        if not taller:
            raise not_found("Taller no encontrado")
        sub = SubscriptionService._latest_subscription(db, id_taller)
        if not sub:
            raise bad_request("El taller no tiene suscripciones registradas")
        now = SubscriptionService._now_naive_utc()
        if sub.fecha_fin < now:
            raise bad_request("La suscripción está vencida. Debe renovarse antes de habilitar.")
        if sub.estado == "ACTIVA":
            raise bad_request("La suscripción ya se encuentra activa")
        sub.estado = "ACTIVA"
        taller.estado_operativo = EstadoOperativoTaller.DISPONIBLE
        SubscriptionService._log_subscription_event(
            db,
            actor_type=TipoActor.ADMINISTRADOR,
            actor_id=actor_user.id_usuario,
            action="Habilitación de suscripción SaaS",
            detail=f"Administrador habilitó suscripción del taller {taller.nombre_taller}",
            entity_id=sub.id_subscription,
        )
        db.commit()
        return {
            "mensaje": "Suscripción habilitada correctamente",
            "id_taller": str(taller.id_taller),
            "estado_suscripcion": sub.estado,
            "estado_operativo_taller": taller.estado_operativo.value,
        }
